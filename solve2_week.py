import pandas as pd
import numpy as np
import copy  # Import copy for deep copying objects
from core.network import create_network, extra_bess_link_status
from core.config_loader import load_config
from scenarios.load_scenarios import load_scenarios2
from utils.utils import bus_balance  # Import the bus balance function
from core.load_week import get_week_range, load_load_levels, load_day_ahead_prices, load_imbalance_prices, load_solar_profile
from utils.congestion_week import congestion_summary_week, combined_congestion_summary_week, plot_group_week_summary, plot_group_week_events_heatmaps
import os


def solve_network(year, week, scenario, energy_tax):
    
    config = load_config()
    paths = config["paths"]

    load_path = paths["load"]
    day_ahead_prices_path = paths["day_ahead_prices"]
    imbalance_prices_path = paths["imbalance_prices"]
    solar_profile_path = paths["solar_profile"]
    battery_specs_path = paths["battery_specs"]

    # Load input data for the specified week
    demand = load_load_levels(load_path, year, week)
    prices = load_day_ahead_prices(day_ahead_prices_path, year, week)
    discharge_prices, charge_prices, discharge_mask, charge_mask = load_imbalance_prices(imbalance_prices_path, year, week)
    solar_generation = load_solar_profile(solar_profile_path, year, week)
    
    # Create the base network using the imported create_network function and battery specs from YAML
    base_network = create_network(battery_specs_path, prices, charge_prices, discharge_prices, year, energy_tax)
    
    # Set snapshots for the selected week (15-minute resolution)
    start, end = get_week_range(year, week)
    timestamps = pd.date_range(start=start, end=end, freq="15min", inclusive="left")
    base_network.set_snapshots(timestamps, weightings_from_timedelta=True)
    dam_share = scenario["dam_share"]
    imbalance_share = scenario["imbalance_share"]
    
    # read the boolean from your YAML (default False)
    enforce = scenario.get("enforce_time_windows", False)
    forbidden = scenario.get("forbidden_windows", [(12,14),(17,19)])
    
    base_network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "negative_DAM_Generator": prices,
         "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=base_network.snapshots)
    
    
    # --- First step: Solve DAM network ---
    DAM_network = copy.deepcopy(base_network)
    DAM_network.enforce_time_windows = scenario.get("enforce_time_windows", False)
    DAM_network.forbidden_windows   = scenario.get("forbidden_windows", [(12,14),(17,19)])
    DAM_network.generators.at["DAM_Generator", "active"] = scenario["generators"]["DAM_Generator"]
    DAM_network.generators.at["negative_DAM_Generator", "active"] = scenario["generators"]["negative_DAM_Generator"]
    DAM_network.generators.at["PV_Generator", "active"] = scenario["generators"]["PV_Generator"]
    DAM_network.generators.at["IMBALANCE_Generator", "active"] = scenario["generators"]["IMBALANCE_Generator"]
    DAM_network.generators.at["negative_IMBALANCE_Generator", "active"] = scenario["generators"]["negative_IMBALANCE_Generator"]
    
    # Apply demand and day-ahead price data to the base network
    if scenario.get("HouseholdLoad", "demand") == 0:
        DAM_network.loads_t.p_set.loc[:, "HouseholdLoad"] = 0
    else:
        DAM_network.loads_t.p_set.loc[:, "HouseholdLoad"] = demand
    # Add marginal costs for net metering
    mc_hh_ss = scenario["marginal_cost_Household_to_SS"] 
    DAM_network.links.at["Household → MRS",      "marginal_cost"] = mc_hh_ss
    #  Only include marginal costs for DAM generator
    DAM_network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "negative_DAM_Generator": prices
    }, index=DAM_network.snapshots)

    # Scale battery capacity
    DAM_network.stores.loc["BESS", "e_nom"] *= dam_share
    DAM_network.links.loc["BESS → Household", "p_nom"] *= dam_share
    DAM_network.links.loc["Household → BESS", "p_nom"] *= dam_share    
    DAM_network.generators_t.p_max_pu.loc[:, "PV_Generator"] = solar_generation
    
    print("Solving DA network...")
    DAM_network.optimize(DAM_network.snapshots, solver_name="highs")

     # --- Second step: Solve imbalance network ---
    Onbalans_network = copy.deepcopy(base_network)

    Onbalans_network.enforce_time_windows = scenario.get("enforce_time_windows", False)
    Onbalans_network.forbidden_windows   = scenario.get("forbidden_windows", [(12,14),(17,19)])
    #  Reactivate imbalance generators
    Onbalans_network.generators.at["DAM_Generator", "active"] = False
    Onbalans_network.generators.at["negative_DAM_Generator", "active"] = False
    Onbalans_network.generators.at["PV_Generator", "active"] = False
    Onbalans_network.generators.at["IMBALANCE_Generator", "active"] = True
    Onbalans_network.generators.at["negative_IMBALANCE_Generator", "active"] = True
    Onbalans_network.loads_t.p_set.loc[:, "HouseholdLoad"] = 0
    #  Full storage capacity
    Onbalans_network.stores.loc["BESS", "e_nom"] *= imbalance_share
    Onbalans_network.links.loc["BESS → Household", "p_nom"] *= imbalance_share
    Onbalans_network.links.loc["Household → BESS", "p_nom"] *= imbalance_share

    # Assign the time-dependent p_max_pu
    Onbalans_network.generators_t.p_max_pu.loc[:, "IMBALANCE_Generator"] = charge_mask
    Onbalans_network.generators_t.p_min_pu.loc[:, "negative_IMBALANCE_Generator"] = -discharge_mask

    #  Apply full marginal cost dataframe
    Onbalans_network.generators_t.marginal_cost = pd.DataFrame({
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=Onbalans_network.snapshots)

    #  Fix DAM dispatch
    Onbalans_network.generators_t.p_set["DAM_Generator"] = DAM_network.generators_t.p["DAM_Generator"]

    print("Solving imbalance network...")
    Onbalans_network.optimize(Onbalans_network.snapshots, solver_name="highs", extra_functionality=extra_bess_link_status)
    
    return DAM_network, Onbalans_network

if __name__ == "__main__":
    year = 2024
    week = 4
    
    scenario_to_run = "Value Stacking DAM + Imbalance + Time Constraints"
    # 2) Laad álle scenario's (oude en flattened group-subscenarios)
    scenarios = load_scenarios2("scenarios/2solve_scenarios.yaml")

    # 3a) Kijk of dit een groep is door te filteren op de extra key "group"
    group_members = [s for s in scenarios if s.get("group") == scenario_to_run]

    if group_members:
        # dit is een groep: loop over álle sub-scenario's
        for scen in group_members:
            print(f"\n### Running group {scenario_to_run} → {scen['name']} ###")
            DAM_solve, Imbalance_solve = solve_network(year, week, scen, scen["energy_tax"])

            # plotten & tonen
            DAM_solve.stores_t.p.plot()
            fig1 = bus_balance(DAM_solve, "Household", resample="15 min")
            #fig1.show()
            Imbalance_solve.stores_t.p.plot()
            fig2 = bus_balance(Imbalance_solve, "Household", resample="15 min")
            #fig2.show()
            fig3 = bus_balance(Imbalance_solve, "Electricity_Grid", resample="15 min")
            #fig3.show()
            fig4 = combined_congestion_summary_week(DAM_solve, Imbalance_solve, year, week, scen["name"])
            #fig4.show()
            fig_dam_week = congestion_summary_week(
            DAM_solve, year, week, f"{scen['name']}_DAM"
            )
            #fig_dam_week.show()

            fig_imb_week = congestion_summary_week(
                Imbalance_solve, year, week, f"{scen['name']}_Imbalance"
            )
            #fig_imb_week.show()
            # opslaan
            base = os.path.join("plots", "congestion_week", str(year), scen["name"], f"week_{week}")
            os.makedirs(base, exist_ok=True)
            fig1.write_image(os.path.join(base, "bus_balance_household_DAM.svg"))
            fig2.write_image(os.path.join(base, "bus_balance_household_imbalance.svg"))
            fig3.write_image(os.path.join(base, "bus_balance_electricity_grid_imbalance.svg"))
            fig4.write_image(os.path.join(base, "combined_congestion_summary.svg"))
            
            print(f"DAM obj.:       €{DAM_solve.objective:,.2f}")
            print(f"Imb obj.:       €{Imbalance_solve.objective:,.2f}")
        plot_group_week_summary(year, week, scenario_to_run, group_members)
        plot_group_week_events_heatmaps(year, week, scenario_to_run, group_members)
    else:
        # 3b) geen groep, pak één enkel scenario
        scen = next((s for s in scenarios if s["name"] == scenario_to_run), None)
        if not scen:
            raise RuntimeError(f"Geen scenario of groep met de naam '{scenario_to_run}' gevonden")

        print(f"\n### Running single scenario {scen['name']} ###")
        DAM_solve, Imbalance_solve = solve_network(year, week, scen, scen["energy_tax"])
        # 1) Dump the full per‐network week‐summary (plots + CSVs)
    #    (will create under results/congestion_week/<year>/<scenario_name>_DAM/week_<week>/…)
        print("→ Generating weekly summary for DAM run…")
        fig_dam = congestion_summary_week(DAM_solve, year, week, f"{scen['name']}_DAM")
        #fig_dam.show()

        print("→ Generating weekly summary for Imbalance run…")
        fig_imb = congestion_summary_week(Imbalance_solve, year, week, f"{scen['name']}_Imbalance")
        #fig_imb.show()
        # ——————————————————————————————

        # (optional) now your combined summary
        fig4 = combined_congestion_summary_week(DAM_solve, Imbalance_solve, year, week, scen["name"])
        #fig4.show()
        # plotten & tonen
        DAM_solve.stores_t.p.plot()
        fig1 = bus_balance(DAM_solve, "Household", resample="15 min")
        #fig1.show()
        Imbalance_solve.stores_t.p.plot()
        fig2 = bus_balance(Imbalance_solve, "Household", resample="15 min")
        #fig2.show()
        fig3 = bus_balance(Imbalance_solve, "Electricity_Grid", resample="15 min")
        #fig3.show()
        fig4 = combined_congestion_summary_week(DAM_solve, Imbalance_solve, year, week, scen["name"])
        #fig4.show()

        base = os.path.join("plots", "congestion_week", str(year), scen["name"], f"week_{week}")
        os.makedirs(base, exist_ok=True)
        fig1.write_image(os.path.join(base, "bus_balance_household_DAM.svg"))
        fig2.write_image(os.path.join(base, "bus_balance_household_imbalance.svg"))
        fig3.write_image(os.path.join(base, "bus_balance_electricity_grid_imbalance.svg"))
        fig4.write_image(os.path.join(base, "combined_congestion_summary.svg"))

        print(f"DAM obj.:       €{DAM_solve.objective:,.2f}")
        print(f"Imb obj.:       €{Imbalance_solve.objective:,.2f}")
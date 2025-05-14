import copy
import os
import pandas as pd
from core.network import create_network, extra_bess_link_status
from core.config_loader import load_config
from utils.utils import bus_balance
from scenarios.load_scenarios import load_scenarios2
from utils.congestion_year import (
    congestion_summary_year,
    plot_group_year_summary,
    plot_group_year_events_heatmaps,
)
from core.load_year import (
    load_load_levels,
    load_day_ahead_prices,
    load_imbalance_prices,
    get_year_range,
    load_solar_profile
)
#from utils.congestion_year import combined_congestion_summary_year

def solve_network(year, scenario, energy_tax):
    dam_share = scenario["dam_share"]
    imbalance_share = scenario["imbalance_share"]
    print(f"Solving network for Year {year} with scenario: DAM share = {dam_share}, Imbalance share = {imbalance_share}")
    config = load_config()
    paths = config["paths"]

    load_path = paths["load"]
    day_ahead_prices_path = paths["day_ahead_prices"]
    imbalance_prices_path = paths["imbalance_prices"]
    solar_profile_path = paths["solar_profile"]
    battery_specs_path = paths["battery_specs"]
    
    demand = load_load_levels(load_path, year)
    prices = load_day_ahead_prices(day_ahead_prices_path, year)
    discharge_prices, charge_prices, discharge_mask, charge_mask = load_imbalance_prices(imbalance_prices_path, year)
    solar_generation = load_solar_profile(solar_profile_path, year)
    
    base_network = create_network(battery_specs_path, prices, charge_prices, discharge_prices, year, energy_tax)
    start, end = get_year_range(year)
    timestamps = pd.date_range(start=start, end=end, freq="15min", inclusive="left")
    base_network.set_snapshots(timestamps, weightings_from_timedelta=True)
    # read the boolean from your YAML (default False)
    enforce = scenario.get("enforce_time_windows", False)
    forbidden = scenario.get("forbidden_windows", [(12,14),(17,19)])

    base_network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "negative_DAM_Generator": prices,
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=base_network.snapshots)
    
    # --- DAM Network Setup ---
    DAM_network = copy.deepcopy(base_network)
    DAM_network.enforce_time_windows = scenario.get("enforce_time_windows", False)
    DAM_network.forbidden_windows   = scenario.get("forbidden_windows", [(12,14),(17,19)])
    DAM_network.generators.at["DAM_Generator", "active"] = scenario["generators"]["DAM_Generator"]
    DAM_network.generators.at["negative_DAM_Generator", "active"] = scenario["generators"]["negative_DAM_Generator"]
    DAM_network.generators.at["PV_Generator", "active"] = scenario["generators"]["PV_Generator"]
    DAM_network.generators.at["IMBALANCE_Generator", "active"] = scenario["generators"]["IMBALANCE_Generator"]
    DAM_network.generators.at["negative_IMBALANCE_Generator", "active"] = scenario["generators"]["negative_IMBALANCE_Generator"]
    
    # Add marginal costs for net metering
    mc_hh_ss = scenario["marginal_cost_Household_to_SS"] 
    DAM_network.links.at["Household → MRS",      "marginal_cost"] = mc_hh_ss
    # Set demand and marginal cost from prices on the network
    if scenario["HouseholdLoad"] == 0:
        DAM_network.loads_t.p_set.loc[:, "HouseholdLoad"] = 0
    elif scenario["HouseholdLoad"] == "demand":
        DAM_network.loads_t.p_set.loc[:, "HouseholdLoad"] = demand
    else:
        raise ValueError("Invalid HouseholdLoad option in scenario")
    
    DAM_network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "negative_DAM_Generator": prices
    }, index=DAM_network.snapshots)

    DAM_network.stores.loc["BESS", "e_nom"] *= dam_share
    DAM_network.links.loc["BESS → Household", "p_nom"] *= dam_share
    DAM_network.links.loc["Household → BESS", "p_nom"] *= dam_share
    DAM_network.generators_t.p_max_pu.loc[:, "PV_Generator"] = solar_generation

    print("Optimizing DAM network...")
    DAM_network.optimize(DAM_network.snapshots, solver_name="highs", extra_functionality=extra_bess_link_status)
    
    # --- Imbalance Network Setup ---
    Onbalans_network = copy.deepcopy(base_network)

    Onbalans_network.enforce_time_windows = scenario.get("enforce_time_windows", False)
    Onbalans_network.forbidden_windows   = scenario.get("forbidden_windows", [(12,14),(17,19)])

    Onbalans_network.generators.at["DAM_Generator", "active"] = False
    Onbalans_network.generators.at["negative_DAM_Generator", "active"] = False
    Onbalans_network.generators.at["PV_Generator", "active"] = False
    Onbalans_network.generators.at["IMBALANCE_Generator", "active"] = True
    Onbalans_network.generators.at["negative_IMBALANCE_Generator", "active"] = True
    Onbalans_network.loads_t.p_set.loc[:, "HouseholdLoad"] = 0
    Onbalans_network.stores.loc["BESS", "e_nom"] *= imbalance_share
    Onbalans_network.links.loc["BESS → Household", "p_nom"] *= imbalance_share
    Onbalans_network.links.loc["Household → BESS", "p_nom"] *= imbalance_share

    Onbalans_network.generators_t.p_max_pu.loc[:, "IMBALANCE_Generator"] = charge_mask
    Onbalans_network.generators_t.p_min_pu.loc[:, "negative_IMBALANCE_Generator"] = -discharge_mask
    
    Onbalans_network.generators_t.marginal_cost = pd.DataFrame({
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=Onbalans_network.snapshots)

    Onbalans_network.generators_t.p_set["DAM_Generator"] = DAM_network.generators_t.p["DAM_Generator"]
    print("Optimizing imbalance network...")
    Onbalans_network.optimize(Onbalans_network.snapshots, solver_name="highs", extra_functionality=extra_bess_link_status)
    
    return DAM_network, Onbalans_network

if __name__ == "__main__":
    year = 2024
    PLOT_BASE_YEAR = "plots/congestion_year"
    # Either a single scenario name, or a group name:
    scenario_to_run = "Value Stacking DAM + Imbalance + Time Constraints"

    # 1) Load ALL scenarios (flat + groups)
    scenarios     = load_scenarios2("scenarios/2solve_scenarios.yaml")
    group_members = [s for s in scenarios if s.get("group") == scenario_to_run]

    if group_members:
        # --- GROUP RUN: loop exactly as in solve2_week.py ---
        # create the top-level group folder
        RESULTS_BASE = "results/congestion_year"
        group_dir    = os.path.join(RESULTS_BASE, str(year), scenario_to_run)
        PLOT_BASE = "plots/congestion_year"
        out_dir = os.path.join(PLOT_BASE, str(year), scenario_to_run)
        os.makedirs(group_dir, exist_ok=True)
        for scen in group_members:
            scenario_name = scen["name"]
            print(f"\n### Running group {scenario_to_run} → {scenario_name} ###")

            # solve
            DAM_solve, Imbalance_solve = solve_network(year, scen, scen["energy_tax"])

            # print objective values
            print("DAM network objective:      €{:,.2f}".format(DAM_solve.objective))
            print("Imbalance network objective: €{:,.2f}".format(Imbalance_solve.objective))

            # optional plots
            DAM_solve.stores_t.p.plot()
            fig_hh   = bus_balance(DAM_solve,      "Household",       resample="15 min")
            fig_hh.write_image(os.path.join(out_dir, "bus_balance_household.svg"))
            #fig_hh.show()
            fig_grid = bus_balance(Imbalance_solve, "Electricity_Grid", resample="15 min")
            fig_grid.write_image(os.path.join(out_dir, "bus_balance_grid.svg"))
            #fig_grid.show()

            # 1) write objectives under group_dir/<scenario_name>/
            scenario_dir = os.path.join(group_dir, scenario_name)
            os.makedirs(scenario_dir, exist_ok=True)

            obj_dam = DAM_solve.objective
            obj_imb = Imbalance_solve.objective
            print(f"Objective function value DAM:       €{obj_dam:.5f}")
            print(f"Objective function value Imbalance: €{obj_imb:.5f}")

            df_obj = pd.DataFrame([{
                "year": year,
                "scenario": scenario_name,
                "objective_DAM":       obj_dam,
                "objective_Imbalance": obj_imb
            }])
            df_obj.to_csv(
                os.path.join(scenario_dir, "objective_function.csv"),
                index=False
            )

            # 2) per‐scenario yearly congestion summaries under group folder
            nested_dam_name = os.path.join(scenario_to_run, f"{scenario_name}_DAM")
            nested_imb_name = os.path.join(scenario_to_run, f"{scenario_name}_Imbalance")

            congestion_summary_year(
                DAM_solve, year, nested_dam_name
            )
            congestion_summary_year(
                Imbalance_solve, year, nested_imb_name
            )
            # Combined DAM vs Imbalance year summary
            #fig3 = combined_congestion_summary_year(DAM_solve, Imbalance_solve, year, scen["name"])
            #fig3.show()

        # --- GROUP‐LEVEL SUMMARY CHARTS (once) ---
        # 1) Four bar‐charts across scenarios
        plot_group_year_summary(year, scenario_to_run, group_members)

        # 2) Four time‐of‐day heatmaps across scenarios
        plot_group_year_events_heatmaps(year, scenario_to_run, group_members)

    else:
        # --- SINGLE SCENARIO RUN ---
        scen = next((s for s in scenarios if s["name"] == scenario_to_run), None)
        if not scen:
            raise RuntimeError(f"No scenario or group named '{scenario_to_run}' found")

        print(f"\n### Running single scenario {scen['name']} ###")
        DAM_solve, Imbalance_solve = solve_network(year, scen, scen["energy_tax"])

        # exactly the same per‐scenario yearly summaries:
        congestion_summary_year(DAM_solve,      year, f"{scen['name']}_DAM")
        congestion_summary_year(Imbalance_solve, year, f"{scen['name']}_Imbalance")
        #combined_congestion_summary_year(DAM_solve, Imbalance_solve, year, scen["name"]).show()

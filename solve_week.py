import pandas as pd
import numpy as np
from core.network import create_network, extra_bess_link_status
from core.config_loader import load_config
from utils.utils import bus_balance, household_inflow_balance, battery_behavior, battery_behavior_settlement
from core.load_week import get_week_range, load_load_levels, load_day_ahead_prices, load_imbalance_prices, load_solar_profile
from scenarios.load_scenarios import load_scenarios
from utils.congestion_week import congestion_summary_week
from utils.utils import calculate_battery_profit

def solve_network(year, week, scenario, energy_tax):
    print(f"Solving network for Year {year}, Week {week}")
    config = load_config()
    paths = config["paths"]

    load_path = paths["load"]
    day_ahead_prices_path = paths["day_ahead_prices"]
    imbalance_prices_path = paths["imbalance_prices"]
    solar_profile_path = paths["solar_profile"]
    battery_specs_path = paths["battery_specs"]

    demand = load_load_levels(load_path, year, week)
    prices = load_day_ahead_prices(day_ahead_prices_path, year, week)
    discharge_prices, charge_prices,  discharge_mask, charge_mask = load_imbalance_prices(imbalance_prices_path, year, week)
    solar_generation = load_solar_profile(solar_profile_path, year, week)

    network = create_network(battery_specs_path, prices, charge_prices, discharge_prices, year, energy_tax)

    # Set 15-minute snapshots for the selected week
    start, end = get_week_range(year, week)
    snapshots = pd.date_range(start=start, end=end, freq="15min", inclusive="left") 
    network.set_snapshots(snapshots, weightings_from_timedelta=True)

    #  Deactivate imbalance generators (STATIC component table)
    network.generators.at["DAM_Generator", "active"] = scenario["generators"]["DAM_Generator"]
    network.generators.at["negative_DAM_Generator", "active"] = scenario["generators"]["negative_DAM_Generator"]
    network.generators.at["PV_Generator", "active"] = scenario["generators"]["PV_Generator"]
    network.generators.at["IMBALANCE_Generator", "active"] = scenario["generators"]["IMBALANCE_Generator"]
    network.generators.at["negative_IMBALANCE_Generator", "active"] = scenario["generators"]["negative_IMBALANCE_Generator"]


    network.generators_t.p_max_pu.loc[:, "IMBALANCE_Generator"] = charge_mask
    network.generators_t.p_min_pu.loc[:, "negative_IMBALANCE_Generator"] = -discharge_mask
    network.generators_t.p_max_pu.loc[:, "PV_Generator"] = solar_generation
    
    # read the boolean from your YAML (default False)
    network.enforce_time_windows = scenario.get("enforce_time_windows", False)
    # (optional) if you ever want to override forbidden_windows too:)
    network.forbidden_windows   = scenario.get("forbidden_windows", [(12,14),(17,19)])  

    # Add marginal costs for net metering
    mc_hh_ss = scenario["marginal_cost_Household_to_SS"]  
    network.links.at["Household → MSR",      "marginal_cost"] = mc_hh_ss
    # Apply demand and price data
    if scenario["HouseholdLoad"] == 0:
        network.loads_t.p_set.loc[:, "HouseholdLoad"] = 0
    elif scenario["HouseholdLoad"] == "demand":
        network.loads_t.p_set.loc[:, "HouseholdLoad"] = demand
    else:
        raise ValueError("Invalid HouseholdLoad option in scenario")
    
    network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
       "negative_DAM_Generator": prices,
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=network.snapshots)

    #network.optimize(network.snapshots, solver_name="highs", extra_functionality=extra_bess_link_status)
    network.optimize.optimize_with_rolling_horizon(
         snapshots=network.snapshots,
        window=48,
         overlap=24,
         solver_name="highs",
         extra_functionality=extra_bess_link_status
     )
    return network

if __name__ == "__main__":
    year = 2024
    week = 4 # Change this value to select a different week 
    
    # Either set this to a scenario name, or to "ALL" to run every scenario:
    scenario_to_run = ""
    scenarios = load_scenarios()
    # pick one or all
    if scenario_to_run.upper() == "DAM_plus_PV":
        scenarios_to_run = scenarios
    else:
        scenarios_to_run = [s for s in scenarios if s["name"] == scenario_to_run]

    for scenario in scenarios_to_run:
        scenario_name = scenario["name"]
        energy_tax = scenario["energy_tax"]

        solved_network = solve_network(year, week, scenario, energy_tax)

        solved_network.stores_t.p.plot()
        #solved_network.stores_t.p.loc["2024-06-14"].plot()
        #solved_network.stores_t.p.loc["2024-06-15"].plot()
        #Optionally, visualize network balances:
        fig = bus_balance(solved_network, "Household", resample="15 min")
        fig.show()
        #
        import os
        PLOT_BASE = "plots/congestion_week"
        out_dir = os.path.join(PLOT_BASE, str(year), scenario_name, f"week_{week}")
        os.makedirs(out_dir, exist_ok=True)
        fig.write_image(os.path.join(out_dir, "bus_balance_household.svg"))
        fig2 = bus_balance(solved_network, "Electricity_Grid", resample="15 min")
        fig2.show()
        fig2.write_image(os.path.join(out_dir, "bus_balance_electricity_grid.svg"))
        fig3 = congestion_summary_week(solved_network, year, week, scenario_name)
        fig3.show()
        fig4 = household_inflow_balance(solved_network, resample="15min")
        fig4.show()
        fig4.write_image(os.path.join(out_dir, "household_inflow_balance.svg"))

        fig_batt = battery_behavior(solved_network,resample="15min")
        fig_batt.show()

        fig_imb = battery_behavior_settlement(solved_network, resample="15min")
        fig_imb.show()
        fig_imb.write_image(os.path.join(out_dir, "imbalance_battery_behavior.svg"))

        fig_batt.write_image(os.path.join(out_dir, "battery_behavior.svg"))

        RESULTS_BASE = "results/congestion_week"
        results_dir = os.path.join(RESULTS_BASE, str(year), scenario_name, f"week_{week}")
        os.makedirs(results_dir, exist_ok=True)
        objective_function = solved_network.objective
        print(f"Objective function value: {objective_function:.5f}")
        # create a DataFrame and write it out
        df_obj = pd.DataFrame([{
            "year": year,
            "week": week,
            "scenario": scenario_name,
            "objective": objective_function
        }])
        df_obj.to_csv(os.path.join(results_dir, "objective_function.csv"), index=False)

        # 0) Just to see what time-series attributes you actually have:
        print(">>> generators_t contains attributes:", list(solved_network.generators_t.keys()))

        # 1) If there *is* a 'p' (dispatch) timeseries, list the active gens:
        if "p" in solved_network.generators_t.keys():
            p_gen = solved_network.generators_t["p"]

            # which gens ever ran?
            active_any = (p_gen > 0).any(axis=0)
            print("\nGenerators with non-zero dispatch at any time:")
        # 3) Compute and print battery economics
        profit_ts, cost, revenue, profit = calculate_battery_profit(solved_network, out_dir)
        print(f"\nCharging cost:     €{cost:,.2f}")
        print(f"Discharging rev:   €{revenue:,.2f}")
        print(f"Total profit:      €{profit:,.2f}")

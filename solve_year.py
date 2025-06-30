import pandas as pd
import os
import numpy as np
from core.network import create_network, extra_bess_link_status
from core.config_loader import load_config
from utils.utils import bus_balance, household_inflow_balance, calculate_battery_profit
from core.load_year import (
    load_load_levels,
    load_day_ahead_prices,
    load_imbalance_prices,
    get_year_range,
    load_solar_profile
)
from scenarios.load_scenarios import load_scenarios
from utils.congestion_year import congestion_summary_year

def solve_network(year, scenario, energy_tax):
    print(f"Solving network for Year {year}")
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
    
    network = create_network(battery_specs_path, prices, charge_prices, discharge_prices, year, energy_tax)
    
    # Generate 15-minute snapshots for exactly 365 days
    start, end = get_year_range(year)
    snapshots = pd.date_range(start=start, end=end, freq="15min", inclusive="left")
    network.set_snapshots(snapshots, weightings_from_timedelta=True)
    
     #  Deactivate imbalance generators (STATIC component table)
    network.generators.at["DAM_Generator", "active"] = scenario["generators"]["DAM_Generator"]
    network.generators.at["negative_DAM_Generator", "active"] = scenario["generators"]["negative_DAM_Generator"]
    network.generators.at["PV_Generator", "active"] = scenario["generators"]["PV_Generator"]
    network.generators.at["IMBALANCE_Generator", "active"] = scenario["generators"]["IMBALANCE_Generator"]
    network.generators.at["negative_IMBALANCE_Generator", "active"] = scenario["generators"]["negative_IMBALANCE_Generator"]
    
    # Assign imbalance masks (ensure your arrays have the same length as snapshots)
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
    # Set demand and marginal cost from prices on the network
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
    # Change the year as needed (e.g., 2024 or 2030)
    year = 2024
    # Either set this to a scenario name, or to "ALL" to run every scenario:
    scenario_to_run = "ALL"

    scenarios = load_scenarios()
    # pick one or all
    if scenario_to_run.upper() == "ALL":
        scenarios_to_run = scenarios
    else:
        scenarios_to_run = [s for s in scenarios if s["name"] == scenario_to_run]

    for scenario in scenarios_to_run:
        scenario_name = scenario["name"]
        energy_tax = scenario["energy_tax"]
        solved_network = solve_network(year, scenario, energy_tax)
        
        # Plot the storage profiles
        solved_network.stores_t.p.plot()
        
        # Visualize network balances for "Household" and "Electricity_Grid"
        fig = bus_balance(solved_network, "Household", resample="15 min")
        fig.show()
        
        PLOT_BASE = "plots/congestion_year"
        out_dir = os.path.join(PLOT_BASE, str(year), scenario_name)
        os.makedirs(out_dir, exist_ok=True)
        fig.write_image(os.path.join(out_dir, "bus_balance_household.svg"))
        fig2 = bus_balance(solved_network, "Electricity_Grid", resample="15 min")
        fig2.show()
        fig2.write_image(os.path.join(out_dir, "bus_balance_electricity_grid.svg"))
        fig3 = congestion_summary_year(solved_network, year, scenario_name)
        RESULTS_BASE = "results/congestion_year"
        results_dir = os.path.join(RESULTS_BASE, str(year), scenario_name)
        os.makedirs(results_dir, exist_ok=True)
        objective_function = solved_network.objective
        print(f"Objective function value: {objective_function:.5f}")
        # create a DataFrame and write it out
        df_obj = pd.DataFrame([{
            "year": year,
            "scenario": scenario_name,
            "objective": objective_function
        }])
        df_obj.to_csv(os.path.join(results_dir, "objective_function.csv"), index=False)
        profit_ts, cost, revenue, profit = calculate_battery_profit(solved_network, out_dir)
        print(f"\nCharging cost:     €{cost:,.2f}")
        print(f"Discharging rev:   €{revenue:,.2f}")
        print(f"Total profit:      €{profit:,.2f}")
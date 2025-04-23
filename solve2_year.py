import pandas as pd
import os
import numpy as np
import copy
from core.network import create_network, extra_bess_link_status
from core.config_loader import load_config
from utils.utils import bus_balance
from scenarios.load_scenarios import load_scenarios2
from core.load_year import (
    load_load_levels,
    load_day_ahead_prices,
    load_imbalance_prices,
    get_year_range,
    load_solar_profile
)
from utils.congestion_year import combined_congestion_summary_year, plot_congestion_time_rose

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

    
    base_network.loads_t.p_set.loc[:, "household_load"] = demand
    base_network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "negative_DAM_Generator": prices,
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=base_network.snapshots)
    
    # --- DAM Network Setup ---
    DAM_network = copy.deepcopy(base_network)
    DAM_network.generators.at["IMBALANCE_Generator", "active"] = False
    DAM_network.generators.at["negative_IMBALANCE_Generator", "active"] = False
    DAM_network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "negative_DAM_Generator": prices
    }, index=DAM_network.snapshots)
    DAM_network.stores.loc["BESS", "e_nom"] *= dam_share
    DAM_network.links.loc["BESS_to_Household", "p_nom"] *= dam_share
    DAM_network.links.loc["Household_to_BESS", "p_nom"] *= dam_share
    DAM_network.generators_t.p_max_pu.loc[:, "PV_Generator"] = solar_generation

    print("Optimizing DAM network...")
    DAM_network.optimize(DAM_network.snapshots, solver_name="highs", extra_functionality=extra_bess_link_status)
    
    # --- Imbalance Network Setup ---
    Onbalans_network = copy.deepcopy(base_network)
    Onbalans_network.generators.at["DAM_Generator", "active"] = False
    Onbalans_network.generators.at["negative_DAM_Generator", "active"] = False
    Onbalans_network.generators.at["PV_Generator", "active"] = False
    Onbalans_network.generators.at["IMBALANCE_Generator", "active"] = True
    Onbalans_network.generators.at["negative_IMBALANCE_Generator", "active"] = True
    Onbalans_network.loads_t.p_set.loc[:, "household_load"] = 0
    Onbalans_network.stores.loc["BESS", "e_nom"] *= imbalance_share
    Onbalans_network.links.loc["BESS_to_Household", "p_nom"] *= imbalance_share
    Onbalans_network.links.loc["Household_to_BESS", "p_nom"] *= imbalance_share

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
    # Set the scenario manually (just like you do for the year)
    scenario_name = "scenario_0.8_0.2"  # kies zelf
    scenarios = load_scenarios2()
    scenario = next(s for s in scenarios if s["name"] == scenario_name)
    energy_tax = scenario["energy_tax"]
    
    print(f"Running scenario: {scenario['name']}")
    DAM_solve, Imbalance_solve = solve_network(year, scenario, energy_tax)
    
    print("DAM network objective:", DAM_solve.objective)
    print("Imbalance network objective:", Imbalance_solve.objective)
    
    # Optionally, plot or save results for the selected scenario.
    DAM_solve.stores_t.p.plot(title=f"DAM Network Battery Dispatch ({scenario['name']})")
    Imbalance_solve.stores_t.p.plot(title=f"Imbalance Network Battery Dispatch ({scenario['name']})")
    
    fig_household = bus_balance(Imbalance_solve, "Household", resample="15 min")
    fig_household.show()
    
    fig_grid = bus_balance(Imbalance_solve, "Electricity_Grid", resample="15 min")
    fig_grid.show()
    fig3 = combined_congestion_summary_year(DAM_solve, Imbalance_solve, year)
    fig3.show()
    fig_dam = plot_congestion_time_rose(DAM_solve, year)
    fig_imb = plot_congestion_time_rose(Imbalance_solve, year)

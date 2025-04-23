import pandas as pd
import numpy as np
import copy  # Import copy for deep copying objects
from core.network import create_network, extra_bess_link_status
from core.config_loader import load_config
from scenarios.load_scenarios import load_scenarios2
from utils.utils import bus_balance  # Import the bus balance function
from core.load_week import get_week_range, load_load_levels, load_day_ahead_prices, load_imbalance_prices, load_solar_profile
from utils.congestion_week import combined_congestion_summary_week


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
    
    # Apply demand and day-ahead price data to the base network
    base_network.loads_t.p_set.loc[:, "household_load"] = demand
    
    base_network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "negative_DAM_Generator": prices,
         "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=base_network.snapshots)
    
    
    # --- First step: Solve DAM network ---
    DAM_network = copy.deepcopy(base_network)

    #  Deactivate imbalance generators (STATIC component table)
    DAM_network.generators.at["IMBALANCE_Generator", "active"] = False
    DAM_network.generators.at["negative_IMBALANCE_Generator", "active"] = False
    

    #  Only include marginal costs for DAM generator
    DAM_network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "negative_DAM_Generator": prices
    }, index=DAM_network.snapshots)

    # Scale battery capacity
    DAM_network.stores.loc["BESS", "e_nom"] *= dam_share
    DAM_network.links.loc["BESS_to_Household", "p_nom"] *= dam_share
    DAM_network.links.loc["Household_to_BESS", "p_nom"] *= dam_share    
    DAM_network.generators_t.p_max_pu.loc[:, "PV_Generator"] = solar_generation
    

    DAM_network.optimize(DAM_network.snapshots, solver_name="highs")

     # --- Second step: Solve imbalance network ---
    Onbalans_network = copy.deepcopy(base_network)

    #  Reactivate imbalance generators
    Onbalans_network.generators.at["DAM_Generator", "active"] = False
    Onbalans_network.generators.at["negative_DAM_Generator", "active"] = False
    Onbalans_network.generators.at["PV_Generator", "active"] = False
    Onbalans_network.generators.at["IMBALANCE_Generator", "active"] = True
    Onbalans_network.generators.at["negative_IMBALANCE_Generator", "active"] = True
    Onbalans_network.loads_t.p_set.loc[:, "household_load"] = 0
    #  Full storage capacity
    Onbalans_network.stores.loc["BESS", "e_nom"] *= imbalance_share
    Onbalans_network.links.loc["BESS_to_Household", "p_nom"] *= imbalance_share
    Onbalans_network.links.loc["Household_to_BESS", "p_nom"] *= imbalance_share

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
    week = 2
    scenario_name = "scenario_0.4_0.6"  # kies zelf
    scenarios = load_scenarios2()
    scenario = next(s for s in scenarios if s["name"] == scenario_name)
    energy_tax = scenario["energy_tax"]

    DAM_solve, Imbalance_solve = solve_network(year, week, scenario, energy_tax)
    # Output results (for example, objective values)
    print("DAM network objective:", DAM_solve.objective)
    print("Imbalance network objective:", Imbalance_solve.objective)
    DAM_solve.stores_t.p.plot()
    fig = bus_balance(DAM_solve, "Household", resample="15 min")
    fig.show()
    Imbalance_solve.stores_t.p.plot()
    #Imbalance_solve.stores_t.p.loc["{2024-03-07}"].plot()
    fig = bus_balance(Imbalance_solve, "Household", resample="15 min")
    fig.show()
    fig2 = bus_balance(Imbalance_solve, "Electricity_Grid", resample="15 min")
    fig2.show()
    fig3 = combined_congestion_summary_week(DAM_solve, Imbalance_solve, year, week)
    fig3.show()  
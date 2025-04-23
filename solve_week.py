import pandas as pd
import numpy as np
from core.network import create_network, extra_bess_link_status
from core.config_loader import load_config
from utils.utils import bus_balance
from core.load_week import get_week_range, load_load_levels, load_day_ahead_prices, load_imbalance_prices, load_solar_profile
from scenarios.load_scenarios import load_scenarios
from utils.congestion_week import congestion_summary_week

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

    # Apply demand and price data
    if scenario["household_load"] == 0:
        network.loads_t.p_set.loc[:, "household_load"] = 0
    elif scenario["household_load"] == "demand":
        network.loads_t.p_set.loc[:, "household_load"] = demand
    else:
        raise ValueError("Invalid household_load option in scenario")
    
    network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
       "negative_DAM_Generator": prices,
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=network.snapshots)

    network.optimize(network.snapshots, solver_name="highs", extra_functionality=extra_bess_link_status)
     #network.optimize.optimize_with_rolling_horizon(
       # snapshots=network.snapshots,
       # window=32,
       # overlap=8,
      #  solver_name="highs",
      #  extra_functionality=extra_bess_link_status
    #)
    return network

if __name__ == "__main__":
    year = 2024
    week = 2 # Change this value to select a different week 
    
    scenario_name = "DAM_plus_PV"  # <--- Pas dit aan om ander scenario te kiezen

    scenarios = load_scenarios()
    scenario = next(s for s in scenarios if s["name"] == scenario_name)

    energy_tax = scenario["energy_tax"]

    solved_network = solve_network(year, week,scenario, energy_tax)

    solved_network.stores_t.p.plot()
    #solved_network.stores_t.p.loc["2024-06-14"].plot()
    #solved_network.stores_t.p.loc["2024-06-15"].plot()
    #Optionally, visualize network balances:
    fig = bus_balance(solved_network, "Household", resample="15 min")
    fig.show()
    #
    fig2 = bus_balance(solved_network, "Electricity_Grid", resample="15 min")
    fig2.show()
    fig3 = congestion_summary_week(solved_network, year, week)
    fig3.show()
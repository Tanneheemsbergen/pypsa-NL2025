import pandas as pd
import numpy as np
import copy  # Import copy for deep copying objects
from network import create_network  # Import the network creation function
from utils.utils import bus_balance  # Import the bus balance function

def get_week_range(year, week):
    """
    Returns the start (Monday) and end (Monday of next week) for the given ISO week.
    """
    start = pd.Timestamp.fromisocalendar(year, week, 1)  # Monday of the ISO week
    end = start + pd.Timedelta(days=7)
    return start, end

def load_load_levels(filepath, year, week):
    df = pd.read_csv(filepath, parse_dates=["datetime"])
    df = df[df["jaar"] == year]
    start, end = get_week_range(year, week)
    df_week = df[(df["datetime"] >= start) & (df["datetime"] < end)]
    return df_week["belasting"].values

def load_day_ahead_prices(filepath, year, week):
    df = pd.read_csv(filepath, parse_dates=["datetime"])
    df = df[df["jaar"] == year]
    start, end = get_week_range(year, week)
    df_week = df[(df["datetime"] >= start) & (df["datetime"] < end)]
    return df_week["price"].values

def load_imbalance_prices(filepath, year, week):
    df = pd.read_csv(filepath, parse_dates=["timeinterval"])
    start, end = get_week_range(year, week)
    df_week = df[(df["timeinterval"] >= start) & (df["timeinterval"] < end)]

    discharge_prices = []
    charge_prices = []
    discharge_mask = []
    charge_mask = []

    for _, row in df_week.iterrows():
        reg_state = row["regulation_state"]
        surplus_val = row["price_surplus"]
        shortage_val = row["price_shortage"]

        discharge_val = np.nan
        charge_val = np.nan

        if reg_state == 1:
            discharge_val = surplus_val
        elif reg_state == -1:
            charge_val = shortage_val
        elif reg_state == 2:
            discharge_val = surplus_val
            charge_val = shortage_val

        discharge_prices.append(discharge_val)
        charge_prices.append(charge_val)

        discharge_mask.append(int(not np.isnan(discharge_val)))
        charge_mask.append(int(not np.isnan(charge_val)))

    index = df_week["timeinterval"]
    # Create series
    discharge_series = pd.Series(discharge_prices, index=index)
    charge_series = pd.Series(charge_prices, index=index)
    discharge_mask_series = pd.Series(discharge_mask, index=index)
    charge_mask_series = pd.Series(charge_mask, index=index)

    # Combine and save to CSV
    result_df = pd.DataFrame({
        "discharge_price": discharge_series,
        "charge_price": charge_series,
        "discharge_mask": discharge_mask_series,
        "charge_mask": charge_mask_series
    })
    result_df.to_csv("imbalance_debug_output.csv")

    return discharge_series, charge_series, discharge_mask_series, charge_mask_series

def solve_network(year, week):
    
    # File paths for the input data
    load_path = "data/new_SS_Monnickendam.csv"
    day_ahead_prices_path = "data/new_day_ahead.csv"
    imbalance_prices_path = "data/new_settlement_prices.csv"
    
    # Load input data for the specified week
    demand = load_load_levels(load_path, year, week)
    prices = load_day_ahead_prices(day_ahead_prices_path, year, week)
    discharge_prices, charge_prices, discharge_mask, charge_mask = load_imbalance_prices(imbalance_prices_path, year, week)
    
    # Create the base network using the imported create_network function and battery specs from YAML
    base_network = create_network("battery_specs.yaml", prices, charge_prices, discharge_prices, year)
    
    # Set snapshots for the selected week (15-minute resolution)
    start, end = get_week_range(year, week)
    timestamps = pd.date_range(start=start, end=end, freq="15min", inclusive="left")
    base_network.set_snapshots(timestamps)
    
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
    DAM_network.stores.loc["BESS", "e_nom"] *= 0.8
    DAM_network.links.loc["BESS_to_Household", "p_nom"] *= 0.8
    DAM_network.links.loc["Household_to_BESS", "p_nom"] *= 0.8
    

    DAM_network.optimize(DAM_network.snapshots, solver_name="highs")

     # --- Second step: Solve imbalance network ---
    Onbalans_network = copy.deepcopy(base_network)

    #  Reactivate imbalance generators
    Onbalans_network.generators.at["IMBALANCE_Generator", "active"] = True
    Onbalans_network.generators.at["negative_IMBALANCE_Generator", "active"] = True
    Onbalans_network.loads_t.p_set.loc[:, "household_load"] = 0
    #  Full storage capacity
    Onbalans_network.stores.loc["BESS", "e_nom"] *= 0.2
    Onbalans_network.links.loc["BESS_to_Household", "p_nom"] *= 0.2
    Onbalans_network.links.loc["Household_to_BESS", "p_nom"] *= 0.2

    # Assign the time-dependent p_max_pu
    Onbalans_network.generators_t.p_max_pu.loc[:, "IMBALANCE_Generator"] = charge_mask
    Onbalans_network.generators_t.p_min_pu.loc[:, "negative_IMBALANCE_Generator"] = -discharge_mask

    #  Apply full marginal cost dataframe
    Onbalans_network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "negative_DAM_Generator": prices,
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=Onbalans_network.snapshots)

    #  Fix DAM dispatch
    Onbalans_network.generators_t.p_set["DAM_Generator"] = DAM_network.generators_t.p["DAM_Generator"]

    print("Solving imbalance network...")
    Onbalans_network.optimize(Onbalans_network.snapshots, solver_name="highs")
    
    return DAM_network, Onbalans_network

if __name__ == "__main__":
    year = 2024
    week = 10
    ENERGY_TAX = 0  # €/MWh
    DA_solve, Imbalance_solve = solve_network(year, week)
    # Output results (for example, objective values)
    print("DAM network objective:", DA_solve.objective)
    print("Imbalance network objective:", Imbalance_solve.objective)
    DA_solve.stores_t.p.plot()
    Imbalance_solve.stores_t.p.plot()
    Imbalance_solve.stores_t.p.loc["2024-03-07"].plot()
    fig = bus_balance(Imbalance_solve, "Household", resample="15 min")
    fig.show()
    fig2 = bus_balance(Imbalance_solve, "Electricity_Grid", resample="15 min")
    fig2.show()
import pandas as pd
import numpy as np
import copy  # Import copy for deep copying objects
from network import create_network  # Import the network creation function

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
    
    for _, row in df_week.iterrows():
        reg_state = row["regulation_state"]
        surplus_val = row["price_surplus"]
        shortage_val = row["price_shortage"]
        
        discharge_val = np.nan
        charge_val = np.nan
        
        if reg_state == 0:
            pass
        elif reg_state == 1:
            discharge_val = surplus_val
        elif reg_state == -1:
            charge_val = shortage_val
        elif reg_state == 2:
            discharge_val = surplus_val
            charge_val = shortage_val
        
        discharge_prices.append(discharge_val)
        charge_prices.append(charge_val)
    
    return np.array(discharge_prices), np.array(charge_prices)

def main():
    year = 2024
    week = 22  # Change this value (e.g., week = 7) as needed
    
    # File paths for the input data
    load_path = "data/new_SS_Monnickendam.csv"
    day_ahead_prices_path = "data/new_day_ahead.csv"
    imbalance_prices_path = "data/new_settlement_prices.csv"
    
    # Load input data for the specified week
    demand = load_load_levels(load_path, year, week)
    prices = load_day_ahead_prices(day_ahead_prices_path, year, week)
    discharge_prices, charge_prices = load_imbalance_prices(imbalance_prices_path, year, week)
    
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
        # You can also add imbalance prices if needed:
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
        "DAM_Generator": prices
    }, index=DAM_network.snapshots)

    # Scale battery capacity if desired
    DAM_network.stores.loc["BESS", "e_nom"] *= 0.8

    print("Solving DAM network...")
    DAM_network.optimize(DAM_network.snapshots, solver_name="highs")

     # --- Second step: Solve imbalance network ---
    Onbalans_network = copy.deepcopy(base_network)

    #  Reactivate imbalance generators
    Onbalans_network.generators.at["IMBALANCE_Generator", "active"] = True
    Onbalans_network.generators.at["negative_IMBALANCE_Generator", "active"] = True

    #  Full storage capacity
    Onbalans_network.stores.loc["BESS", "e_nom"] *= 1

    #  Apply full marginal cost dataframe
    Onbalans_network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=Onbalans_network.snapshots)

    #  Fix DAM dispatch
    Onbalans_network.generators_t.p_set["DAM_Generator"] = DAM_network.generators_t.p["DAM_Generator"]

    print("Solving imbalance network...")
    Onbalans_network.optimize(Onbalans_network.snapshots, solver_name="highs")
    
    # Output results (for example, objective values)
    print("DAM network objective:", DAM_network.objective)
    print("Imbalance network objective:", Onbalans_network.objective)

if __name__ == "__main__":
    main()

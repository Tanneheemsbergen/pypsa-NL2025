import pandas as pd
import numpy as np
import copy
from network import create_network
from utils.utils import bus_balance

def get_year_range(year):
    """
    Returns a time range of exactly 365 days starting from January 1st of the given year.
    (Even if the year is a leap year, the simulation will cover only 365 days.)
    """
    start = pd.Timestamp(year, 1, 1)
    # Force end to be exactly 365 days after start
    end = start + pd.Timedelta(days=365)
    print(f"For year {year}: start = {start} and end = {end}")
    return start, end

def load_load_levels(filepath, year):
    # Load the CSV with datetime parsing on the "datetime" column.
    df = pd.read_csv(filepath, parse_dates=["datetime"])
    # Set "datetime" as the DataFrame index for easier filtering.
    df.set_index("datetime", inplace=True)
    print(f"Loaded {len(df)} rows from {filepath}")

    # Filter the DataFrame for rows that belong to the specified year.
    df_year = df[df.index.year == year].copy()
    
    # Debug: Print the first and last 5 rows for the selected year.
    print(f"First 5 rows for year {year}:\n", df_year.head(5))
    print(f"Last 5 rows for year {year}:\n", df_year.tail(5))
    
    # Return the 'belasting' values directly as a NumPy array.
    df_year.to_csv("test.csv", index=True)
    return df_year["belasting"].values

def load_day_ahead_prices(filepath, year):
    """
    Loads day-ahead electricity prices for the given year from a CSV file and returns the price values.
    Assumes the CSV is indexed by datetime and contains a column "prices".
    """
    # Load CSV file with the datetime index (assumed to be in the first column).
    df = pd.read_csv(filepath, parse_dates=True, index_col=0)
    print(f"Loaded {len(df)} rows from day-ahead prices file.")
    
    # Debug: print the first and last 5 rows (includes datetime and prices)
    print("First 5 rows:\n", df.head(5))
    print("Last 5 rows:\n", df.tail(5))
    
    # Return the "prices" column values directly as a NumPy array.
    return df["price"].values

def load_imbalance_prices(filepath, year):
    df = pd.read_csv(filepath, parse_dates=["timeinterval"])
    start, end = get_year_range(year)
    df_year = df[(df["timeinterval"] >= start) & (df["timeinterval"] < end)]

    discharge_prices = []
    charge_prices = []
    discharge_mask = []
    charge_mask = []

    for _, row in df_year.iterrows():
        reg_state = row["regulation_state"]
        surplus_val = row["price_surplus"]
        shortage_val = row["price_shortage"]

        discharge_val = np.nan
        charge_val = np.nan

        if reg_state == 1:
            discharge_val = surplus_val
        elif reg_state == -1:
            charge_val = shortage_val
        #elif reg_state == 2:
            #discharge_val = surplus_val
            #charge_val = shortage_val    

        discharge_prices.append(discharge_val)
        charge_prices.append(charge_val)
        discharge_mask.append(int(not np.isnan(discharge_val)))
        charge_mask.append(int(not np.isnan(charge_val)))

    index = df_year["timeinterval"]
    # Create time-indexed series
    discharge_series = pd.Series(discharge_prices, index=index)
    charge_series = pd.Series(charge_prices, index=index)
    discharge_mask_series = pd.Series(discharge_mask, index=index)
    charge_mask_series = pd.Series(charge_mask, index=index)

    # Combine the imbalance data and optionally save for debugging purposes
    result_df = pd.DataFrame({
        "discharge_price": discharge_series,
        "charge_price": charge_series,
        "discharge_mask": discharge_mask_series,
        "charge_mask": charge_mask_series
    })
    result_df.to_csv("imbalance_debug_output.csv", index=True)

    return discharge_series, charge_series, discharge_mask_series, charge_mask_series

def solve_network(year):
    print(f"Solving network for Year {year}")
    # File paths for the input data
    load_path = "data/new_SS_Monnickendam.csv"
    day_ahead_prices_path = "data/new_day_ahead.csv"
    imbalance_prices_path = "data/new_settlement_prices.csv"
    
    # Load input data for the specified year
    demand = load_load_levels(load_path, year)
    prices = load_day_ahead_prices(day_ahead_prices_path, year)
    discharge_prices, charge_prices, discharge_mask, charge_mask = load_imbalance_prices(imbalance_prices_path, year)
    
    # Create the base network using battery specs from YAML
    base_network = create_network("battery_specs.yaml", prices, charge_prices, discharge_prices, year)
    
    # Set snapshots for the entire year (15-minute resolution)
    start, end = get_year_range(year)
    timestamps = pd.date_range(start=start, end=end, freq="15min", inclusive="left")
    base_network.set_snapshots(timestamps, weightings_from_timedelta=True)
    
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
    # Deactivate imbalance generators (static component table)
    DAM_network.generators.at["IMBALANCE_Generator", "active"] = False
    DAM_network.generators.at["negative_IMBALANCE_Generator", "active"] = False
    # Only include marginal costs for DAM generator
    DAM_network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "negative_DAM_Generator": prices
    }, index=DAM_network.snapshots)
    # Scale battery capacity for DAM dispatch to 80%
    DAM_network.stores.loc["BESS", "e_nom"] *= 0.8
    DAM_network.links.loc["BESS_to_Household", "p_nom"] *= 0.8
    DAM_network.links.loc["Household_to_BESS", "p_nom"] *= 0.8

    print("Optimizing DAM network...")
    DAM_network.optimize(DAM_network.snapshots, solver_name="highs")

    # --- Second step: Solve imbalance network ---
    Onbalans_network = copy.deepcopy(base_network)
    # Reactivate imbalance generators
    Onbalans_network.generators.at["DAM_Generator", "active"] = False
    Onbalans_network.generators.at["negative_DAM_Generator", "active"] = False
    Onbalans_network.generators.at["IMBALANCE_Generator", "active"] = True
    Onbalans_network.generators.at["negative_IMBALANCE_Generator", "active"] = True
    Onbalans_network.loads_t.p_set.loc[:, "household_load"] = 0
    # Use the remaining 20% of battery capacity for imbalance resolution
    Onbalans_network.stores.loc["BESS", "e_nom"] *= 0.2
    Onbalans_network.links.loc["BESS_to_Household", "p_nom"] *= 0.2
    Onbalans_network.links.loc["Household_to_BESS", "p_nom"] *= 0.2

    # Assign the time-dependent p_max_pu for imbalance generators
    Onbalans_network.generators_t.p_max_pu.loc[:, "IMBALANCE_Generator"] = charge_mask
    Onbalans_network.generators_t.p_min_pu.loc[:, "negative_IMBALANCE_Generator"] = -discharge_mask

    # Apply full marginal cost data (combining day-ahead and imbalance prices)
    Onbalans_network.generators_t.marginal_cost = pd.DataFrame({
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=Onbalans_network.snapshots)

    # Fix DAM dispatch by copying values from the DAM network
    #Onbalans_network.generators_t.p_set["DAM_Generator"] = DAM_network.generators_t.p["DAM_Generator"]

    print("Optimizing imbalance network...")
    Onbalans_network.optimize(Onbalans_network.snapshots, solver_name="highs")

    return DAM_network, Onbalans_network

if __name__ == "__main__":
    year = 2024
    ENERGY_TAX = 0  # €/MWh; update if needed in your network model
    DAM_solve, Imbalance_solve = solve_network(year)
    
    # Output key results (e.g., objective values)
    print("DAM network objective:", DAM_solve.objective)
    print("Imbalance network objective:", Imbalance_solve.objective)
    
    # Plot battery storage profiles
    DAM_solve.stores_t.p.plot(title="DAM Network Battery Dispatch")
    Imbalance_solve.stores_t.p.plot(title="Imbalance Network Battery Dispatch")
    
    # Optionally visualize network balances for Household and Electricity_Grid buses
    fig_household = bus_balance(Imbalance_solve, "Household", resample="15 min")
    fig_household.show()
    
    fig_grid = bus_balance(Imbalance_solve, "Electricity_Grid", resample="15 min")
    fig_grid.show()

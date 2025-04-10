import pandas as pd
import numpy as np
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
    load_path = "data/new_SS_Monnickendam.csv"
    day_ahead_prices_path = "data/new_day_ahead.csv"
    imbalance_prices_path = "data/new_settlement_prices.csv"
    
    demand = load_load_levels(load_path, year)
    prices = load_day_ahead_prices(day_ahead_prices_path, year)
    discharge_prices, charge_prices, discharge_mask, charge_mask = load_imbalance_prices(imbalance_prices_path, year)
    
    network = create_network("battery_specs.yaml", prices, charge_prices, discharge_prices, year)
    
    # Generate 15-minute snapshots for exactly 365 days
    start, end = get_year_range(year)
    snapshots = pd.date_range(start=start, end=end, freq="15min", inclusive="left")
    network.set_snapshots(snapshots, weightings_from_timedelta=True)
    
    # Set generator activity flags:
    network.generators.at["IMBALANCE_Generator", "active"] = False
    network.generators.at["negative_IMBALANCE_Generator", "active"] = False
    network.generators.at["DAM_Generator", "active"] = True
    network.generators.at["negative_DAM_Generator", "active"] = True
    
    # Assign imbalance masks (ensure your arrays have the same length as snapshots)
    network.generators_t.p_max_pu.loc[:, "IMBALANCE_Generator"] = charge_mask
    network.generators_t.p_min_pu.loc[:, "negative_IMBALANCE_Generator"] = -discharge_mask
    
    # Set demand and marginal cost from prices on the network
    network.loads_t.p_set.loc[:, "household_load"] = 0
    network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "negative_DAM_Generator": prices,
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=network.snapshots)
    
    network.optimize(network.snapshots, solver_name="highs" )
    return network

if __name__ == "__main__":
    # Change the year as needed (e.g., 2024 or 2030)
    year = 2024
    ENERGY_TAX = 0.123  # €/MWh
    solved_network = solve_network(year)
    
    # Plot the storage profiles
    solved_network.stores_t.p.plot()
    
    # Visualize network balances for "Household" and "Electricity_Grid"
    #fig = bus_balance(solved_network, "Household", resample="15 min")
    #fig.show()
    
    #fig2 = bus_balance(solved_network, "Electricity_Grid", resample="15 min")
   # fig2.show()

import pandas as pd
import numpy as np
from network import create_network

# %%
def load_load_levels(filepath, year):
    """Loads 15-minute resolution load levels from SS_Monnickendam.csv (in kWh) and converts to kW."""
    df = pd.read_csv(filepath, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
    df.columns = df.columns.str.lower()
    # Filter for selected year and sort
    df = df[df["jaar"] == year].sort_values(by="datum_tijd")

    # Convert kWh to kW (divide by 0.25h per 15-min interval)
    df["belasting_kw"] = df["belasting"] / 0.25  
    # return df["belasting_kw"].values
    return df["belasting_kw"].values[:672]
#%%
def load_day_ahead_prices(filepath, year): 
    """Loads hourly day-ahead prices from CSV and expands them to 15-minute intervals."""
    # Read CSV
    df = pd.read_csv(filepath)

    # Ensure the 'jaar' column exists
    if "jaar" not in df.columns:
        raise ValueError("Column 'jaar' is missing from the CSV. Ensure it was correctly added when saving.")

    # Convert "jaar" column to integer (in case it's read as a string)
    df["jaar"] = df["jaar"].astype(int)

    # Filter using the 'jaar' column instead of .dt.year
    df = df[df["jaar"] == year]

    # Debugging: Check how many rows remain after filtering
    print(f"Found {len(df)} rows for year {year} in day-ahead prices.")

    # Ensure data exists after filtering
    if df.empty:
        raise ValueError(f"No data found for {year}. Check CSV format.")

    # Extract hourly price values
    hourly_prices = df["price"].values

    # Repeat each hourly price 4 times to create 15-minute intervals
    expanded_prices = np.repeat(hourly_prices, 4)
    #return expanded_prices
    return expanded_prices[:672]

def solve_network(year):
    """Loads 15-minute resolution load levels, generates synthetic day-ahead prices, and solves LOPF."""
    # File paths
    load_file = "data/SS_Monnickendam.csv"
    filepath = "data/day_ahead.csv"
    # Load data
    demand = load_load_levels(load_file, year)
    prices = load_day_ahead_prices(filepath, year)

    # Create network
    network = create_network("battery_specs.yaml", prices, year)
    print("Network components:", network.links)

    # Set time snapshots for 15-minute resolution
    #timestamps = pd.date_range(f"{year}-01-01 00:00", periods=35_040, freq="15min")
    timestamps = pd.date_range(f"{year}-01-01 00:00", periods=672, freq="15min")
    network.set_snapshots(timestamps)

    # Apply demand & prices. `.loc` for time-dependent data)
    network.loads_t.p_set.loc[:, "household_load"] = demand
    print("First 10 rows of loads_t.p:\n", network.loads_t.p.head(10))
    network.generators_t.marginal_cost.loc[:, "DAM_Generator"] = prices
    print("First 10 rows of generators_t.p:\n", network.generators_t.p.head(40))
    # Solve LOPF
    network.optimize(network.snapshots, solver_name="glpk")
    print("LOPF solved successfully!")

    return network

if __name__ == "__main__":
    year = 2024  # Change to any year from 2024–2031

    solved_network = solve_network(year)
    print(f"Network solved successfully for {year} with 15-minute resolution and day-ahead prices!")
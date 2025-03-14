import pandas as pd
import numpy as np
from network import create_network

def load_load_levels(filepath, year):
    """Loads 15-minute resolution load levels from SS_Monnickendam.csv (in kWh) and converts to kW."""
    df = pd.read_csv(filepath, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
    df.columns = df.columns.str.lower()

    # Filter for selected year and sort
    df = df[df["jaar"] == year].sort_values(by="datum_tijd")

    # Convert kWh to kW (divide by 0.25h per 15-min interval)
    df["belasting_kw"] = df["belasting"] / 0.25  

    # Ensure exactly 35,040 intervals (365 days × 96 per day)
    expected_intervals = 35_040
    if len(df) != expected_intervals:
        raise ValueError(f"⚠ Load data for {year} contains {len(df)} intervals, expected {expected_intervals}. Check data!")

    return df["belasting_kw"].values  # Return demand as a NumPy array

def load_day_ahead_prices(filepath, year):
    """Loads hourly day-ahead prices from CSV and expands them to 15-minute intervals."""
    # ✅ Read CSV
    df = pd.read_csv(filepath)

    # ✅ Ensure the 'jaar' column exists
    if "jaar" not in df.columns:
        raise ValueError("❌ Column 'jaar' is missing from the CSV. Ensure it was correctly added when saving.")

    # ✅ Convert "jaar" column to integer (in case it's read as a string)
    df["jaar"] = df["jaar"].astype(int)

    # ✅ Filter using the 'jaar' column instead of .dt.year
    df = df[df["jaar"] == year]

    # ✅ Debugging: Check how many rows remain after filtering
    print(f"📌 Found {len(df)} rows for year {year} in day-ahead prices.")

    # ✅ Ensure data exists after filtering
    if df.empty:
        raise ValueError(f"❌ No data found for {year}. Check CSV format.")

    # ✅ Extract hourly price values
    hourly_prices = df["price"].values

    # ✅ Repeat each hourly price 4 times to create 15-minute intervals
    expanded_prices = np.repeat(hourly_prices, 4)

    # ✅ Ensure exactly 35,040 values for a full year at 15-min resolution
    if len(expanded_prices) != 35_040:
        raise ValueError(f"❌ Expected 35,040 prices, but got {len(expanded_prices)}")

    return expanded_prices



def solve_network(year):
    """Loads 15-minute resolution load levels, generates synthetic day-ahead prices, and solves LOPF."""
    # File paths
    load_file = "data/SS_Monnickendam.csv"
    filepath = "data/day_ahead.csv"
    # Load data
    demand = load_load_levels(load_file, year)
    prices = load_day_ahead_prices(filepath, year)  # Now using generated prices

    # Create network
    network = create_network("battery_specs.yaml")

    # Set time snapshots for 15-minute resolution
    timestamps = pd.date_range(f"{year}-01-01 00:00", periods=35_040, freq="15T")
    network.set_snapshots(timestamps)

    # ✅ Debugging: Check if everything matches
    print(f"📌 Expected snapshot count: {len(network.snapshots)}")
    print(f"📌 Load data count: {len(demand)}")
    print(f"📌 Day-ahead price count: {len(prices)}")

    # Apply demand & prices (using `.loc` for time-dependent data)
    network.loads_t.p.loc[:, "household_load"] = demand
    network.generators_t.p.loc[:, "DAM_Generator"] = prices

    # Solve LOPF
    print("📌 Running LOPF solver... (this may take a few minutes)")
    network.optimize(network.snapshots, solver_name="glpk")  # Force GLPK for speed
    print("✅ LOPF solved successfully!")

    return network

if __name__ == "__main__":
    year = 2024  # Change to any year from 2024–2031
    solved_network = solve_network(year)
    print(f"✅ Network solved successfully for {year} with 15-minute resolution and synthetic day-ahead prices!")

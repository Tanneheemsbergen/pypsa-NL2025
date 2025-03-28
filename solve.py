import pandas as pd
import numpy as np
from network import create_network
from utils import bus_balance

# %%
def load_load_levels(filepath, year):
    """Loads 15-minute resolution load levels from SS_Monnickendam.csv (in kWh) and converts to kW."""
    df = pd.read_csv(filepath, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
    df.columns = df.columns.str.lower()
    # Filter for selected year and sort
    df = df[df["jaar"] == year].sort_values(by="datum_tijd")

    # Convert kWh to kW (divide by 0.25h per 15-min interval) -> deleted /0.25 and onlu divided by 1000 to get MWh
    df["belasting_kw"] = (df["belasting"] /0.25) / 1000 
    #return df["belasting_kw"].values
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

    # Extract hourly price values
    hourly_prices = df["price"].values

    # Repeat each hourly price 4 times to create 15-minute intervals
    expanded_prices = np.repeat(hourly_prices, 4)
    #return expanded_prices
    return expanded_prices[:672]

# %%
def load_imbalance_prices(filepath):
    df = pd.read_csv(filepath, sep=";")
    
    required_cols = ["Regulation State", "Price Dispatch Up", "Price Dispatch Down", 
                     "Price Shortage", "Price Surplus"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Vereiste kolom '{col}' ontbreekt in de CSV.")
    
    discharge_prices = []
    charge_prices = []
    
     # Go through each row and apply the logic
    for _, row in df.iterrows():
        reg_state = row["Regulation State"]
        surplus_val = row["Price Surplus"]
        shortage_val = row["Price Shortage"]
        
        # Default to NaN (meaning "no revenue" or "not applicable")
        discharge_val = np.nan
        charge_val = np.nan
        
        # Apply the user-defined rules
        if reg_state == 0:
            # STABLE => No number in both
            discharge_val = np.nan
            charge_val = np.nan
        elif reg_state == 1:
            # UP => Put the number in surplus (discharge), not in shortage
            discharge_val = surplus_val
            charge_val = np.nan
        elif reg_state == -1:
            # DOWN => Put the number in shortage (charge), not in surplus
            discharge_val = np.nan
            charge_val = shortage_val
        elif reg_state == 2:
            # UP_AND_DOWN => Put the number in both
            discharge_val = surplus_val
            charge_val = shortage_val
        else:
            # Any other state => default to NaN
            discharge_val = np.nan
            charge_val = np.nan
        
        discharge_prices.append(discharge_val)
        charge_prices.append(charge_val)
    #print("Discharge array (Price Surplus logic):")
    #print(discharge_prices)
    #print("\nCharge array (Price Shortage logic):")
    #print(charge_prices)
    return np.array(discharge_prices[:672]), np.array(charge_prices[:672])
#%%
def solve_network(year):
    """Loads 15-minute resolution load levels, generates synthetic day-ahead prices, and solves LOPF."""
    # File paths              
    load_path = "data/SS_Monnickendam.csv"
    day_ahead_prices_path = "data/day_ahead.csv"
    imbalance_prices_path = "data/settlement_prices.csv"
    # Load data
    demand = load_load_levels(load_path, year)
    prices = load_day_ahead_prices(day_ahead_prices_path, year)
    discharge_prices, charge_prices  = load_imbalance_prices(imbalance_prices_path)

    # Create network
    network = create_network("battery_specs.yaml", prices, charge_prices, discharge_prices, year)
    print("Generators:\n", network.generators)
    print("Generator capacities:\n", network.generators.p_nom)
    print("Network components:", network.links)

    # Set time snapshots for 15-minute resolution
    #timestamps = pd.date_range(f"{year}-01-01 00:00", periods=35_040, freq="15min")
    timestamps = pd.date_range(f"{year}-01-01 00:00", periods=672, freq="15min")
    network.set_snapshots(timestamps)

    # Apply demand & prices.
    network.loads_t.p_set.loc[:, "household_load"] = demand
    print("First 10 rows of loads_t.p:\n", network.loads_t.p.head(10))
    network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=network.snapshots)
    # Solve LOPF
    network.optimize(network.snapshots, solver_name="highs")
    return network

if __name__ == "__main__":
    year = 2024  # Change to any year from 2024–2031
    ENERGY_TAX = 0.005  # Extra energiebelasting in €/MWh
    solved_network = solve_network(year)
    solved_network.stores_t.p.loc["2024-01-01"].plot()
    solved_network.stores_t.p.loc["2024-01-02"].plot()
    solved_network.stores_t.p.loc["2024-01-03"].plot()
    solved_network.stores_t.p.loc["2024-01-04"].plot()
    solved_network.stores_t.p.loc["2024-01-05"].plot()
    solved_network.stores_t.p.loc["2024-01-06"].plot()
    solved_network.stores_t.p.loc["2024-01-07"].plot()
    # %%
    fig = bus_balance(solved_network, "Household", resample = "15 min")
    fig.show()
    #%%
    fig2 = bus_balance(solved_network, "Electricity_Grid", resample = "15 min")
    fig2.show()
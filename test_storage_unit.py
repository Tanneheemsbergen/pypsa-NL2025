import os
import yaml
import pypsa
import pandas as pd
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt

def create_network(battery_specs_file, prices, charge_prices, discharge_prices, year):
    """Creates a PyPSA network with buses, generators, loads, BESS as Store, and links."""

    # Verify that the battery specs file exists
    if not os.path.exists(battery_specs_file):
        raise FileNotFoundError(f"Error: Battery specs file '{battery_specs_file}' not found!")

    # Load battery specs
    with open(battery_specs_file, "r") as file:
        battery_specs = yaml.safe_load(file)

    # Create PyPSA network
    network = pypsa.Network()
    ENERGY_TAX = 0.123
    # Add Components
    network.add("Carrier", "electricity")

    # Add buses
   
    network.add("Bus", "Electricity_Grid", carrier="electricity")

    
   # Add generator
    network.add("Generator", "DAM_Generator",
               bus="Electricity_Grid",
               carrier="DAM_Generator",
               p_nom=50_000,
               p_min_pu=0,
               p_max_pu=1
               )
    
    network.add("Generator", "negative_DAM_Generator",
                 bus="Electricity_Grid",
                carrier="negative_DAM_Generator",
                 p_nom=50000,
                 p_min_pu=-1,
                 p_max_pu=0
                 )

    network.add("StorageUnit", "BESS",
                 bus="Electricity_Grid",
                 carrier="BESS",
                 p_nom=battery_specs["capacity_mwh"],
                 standing_loss=battery_specs["standing_loss"],
                 efficiency_store=0.9,
                 efficiency_dispatch=0.9,
                 initial_soc=battery_specs["initial_soc_mwh"],
                )
    
    return network


# Use ISO calendar week: Monday is the first day of the week.
def get_week_range(year, week):
    start = pd.Timestamp.fromisocalendar(year, week, 1)  # Monday of the ISO week
    end = start + pd.Timedelta(days=7)
    print(f"Week {week} of {year} starts on {start} and ends on {end}")
    return start, end

def load_load_levels(filepath, year, week):
    df = pd.read_csv(filepath, parse_dates=["datetime"])
    df = df[df["jaar"] == year]
    start, end = get_week_range(year, week)
    df_week = df[(df["datetime"] >= start) & (df["datetime"] < end)]
    print(f"Load levels for week {week} of {year}:")
    print(df_week)
    return df_week["belasting"].values

def load_day_ahead_prices(filepath, year, week):
    df = pd.read_csv(filepath, parse_dates=["datetime"])
    df = df[df["jaar"] == year]
    start, end = get_week_range(year, week)
    df_week = df[(df["datetime"] >= start) & (df["datetime"] < end)]
    print(f"Day-ahead prices for week {week} of {year}:")
    print(df_week)
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
    print(f"Solving network for Year {year}, Week {week}")
    load_path = "data/new_SS_Monnickendam.csv"
    day_ahead_prices_path = "data/new_day_ahead.csv"
    imbalance_prices_path = "data/new_settlement_prices.csv"
    
    demand = load_load_levels(load_path, year, week)
    prices = load_day_ahead_prices(day_ahead_prices_path, year, week)
    discharge_prices, charge_prices,  discharge_mask, charge_mask = load_imbalance_prices(imbalance_prices_path, year, week)
    
    network = create_network("battery_specs.yaml", prices, charge_prices, discharge_prices, year)
    
    # Set 15-minute snapshots for the selected week
    start, end = get_week_range(year, week)
    snapshots = pd.date_range(start=start, end=end, freq="15min", inclusive="left") 
    network.set_snapshots(snapshots, weightings_from_timedelta=True)

     #  Deactivate imbalance generators (STATIC component table)
    network.generators.at["DAM_Generator", "active"] = True
    network.generators.at["negative_DAM_Generator", "active"] = True
    network.generators_t.p_max_pu.loc[:, "IMBALANCE_Generator"] = charge_mask
    network.generators_t.p_min_pu.loc[:, "negative_IMBALANCE_Generator"] = -discharge_mask
    # Apply demand and price data
    network.loads_t.p_set.loc[:, "household_load"] = 0
    network.generators_t.marginal_cost = pd.DataFrame({
        "DAM_Generator": prices,
       "negative_DAM_Generator": prices,
        "IMBALANCE_Generator": charge_prices,
        "negative_IMBALANCE_Generator": discharge_prices
    }, index=network.snapshots)
    
    network.optimize(network.snapshots, solver_name="highs")
    return network

if __name__ == "__main__":
    year = 2024
    week = 24
 # Change this value to select a different week 
    ENERGY_TAX = 0.123  # €/MWh
    solved_network = solve_network(year, week)
    solved_network.storage_units_t.p.plot()
    print(solved_network.snapshots[:10])
    #Optionally, visualize network balances:
  
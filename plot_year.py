import pandas as pd
import os

def get_storage_charging(network, store=None):
    """
    Returns the battery charging load (in MW) as a pandas Series extracted from the network's 
    stores_t.p DataFrame. Charging load is defined as the absolute value of power when charging 
    (i.e., when storage power is negative).
    """
    # network.stores_t.p is a DataFrame with one column per storage unit
    store_power = network.stores_t.p  
    if store is None:
        if len(store_power.columns) == 1:
            store = store_power.columns[0]
        else:
            raise ValueError(f"Multiple stores found: {list(store_power.columns)}. Please specify one.")
    p = store_power[store]
    # For charging, p is negative; take the absolute value for charging load
    charging = p.clip(upper=0).abs()
    return charging

def detect_new_congestion_periods(network, load_filepath, capacity_limit, output_filepath_new, store=None):
    """
    Detects time intervals where the original load is below the capacity limit but, after adding
    battery charging load, the combined load exceeds the capacity_limit.
    
    Parameters:
      network: A solved PyPSA network with storage time series (network.stores_t.p).
      load_filepath: Path to the CSV file with load levels. Expected columns: "datetime", "belasting", "jaar".
      capacity_limit: The capacity limit in MW (for example, 11.2 * 0.85 = 9.52 MW).
      output_filepath_new: File path to save the detected new congestion periods.
      store: (Optional) Specific storage unit name to use if more than one is available.
      
    Returns:
      A DataFrame of new congested intervals.
    """
    # Load load data and set datetime as index; rename "belasting" to "load_mw".
    df_load = pd.read_csv(load_filepath, parse_dates=["datetime"])
    df_load.set_index("datetime", inplace=True)
    df_load.rename(columns={"belasting": "load_mw"}, inplace=True)
    
    # Retrieve the battery charging load from network (in MW)
    battery_charging = get_storage_charging(network, store=store)
    
    # Merge the two Series along their datetime index
    df = df_load.join(battery_charging.rename("charging_mw"), how="inner")
    df["charging_mw"] = df["charging_mw"].fillna(0)
    # Combined load: original load plus battery charging load
    df["combined_load_mw"] = df["load_mw"] + df["charging_mw"]
    
    # Identify new congestion: originally not congested (< capacity_limit) but combined load exceeds it.
    df_new_congested = df[(df["load_mw"] < capacity_limit) & (df["combined_load_mw"] > capacity_limit)]
    
    os.makedirs(os.path.dirname(output_filepath_new), exist_ok=True)
    df_new_congested.to_csv(output_filepath_new)
    print(f"New congested intervals due to battery charging: {len(df_new_congested)} found.")
    print(f"Saved new congestion periods to: {output_filepath_new}")
    
    return df_new_congested

def detect_already_congested_periods(load_filepath, capacity_limit, output_filepath_already):
    """
    Detects time intervals where the original load already exceeds the capacity limit.
    
    Parameters:
      load_filepath: Path to the CSV file with load levels (expected columns: "datetime", "belasting", "jaar").
      capacity_limit: Capacity limit in MW.
      output_filepath_already: File path to save already congested intervals.
      
    Returns:
      A DataFrame with time intervals that are already congested.
    """
    df_load = pd.read_csv(load_filepath, parse_dates=["datetime"])
    df_load.set_index("datetime", inplace=True)
    df_load.rename(columns={"belasting": "load_mw"}, inplace=True)
    
    # Already congested means the original load exceeds the capacity limit.
    df_already_congested = df_load[df_load["load_mw"] > capacity_limit]
    
    os.makedirs(os.path.dirname(output_filepath_already), exist_ok=True)
    df_already_congested.to_csv(output_filepath_already)
    print(f"Already congested intervals: {len(df_already_congested)} found.")
    print(f"Saved already congested periods to: {output_filepath_already}")
    
    return df_already_congested

if __name__ == "__main__":
    # Import your network solver.
    # Adjust the module name/path according to your project structure.
    from solve_year import solve_network  # assumes solve_year.py defines solve_network
    
    # Define simulation parameters.
    year = 2024
    solved_network = solve_network(year)
    
    # Define the capacity limit in MW.
    # capacity_limit = 11.2 * 0.85 * 1000 kW / 1000 = 11.2 * 0.85 = 9.52 MW.
    capacity_limit_mw = 11.2 * 0.85
    
    # File paths for load data
    load_file = "data/new_SS_Monnickendam.csv"
    
    # Output file paths for congestion detection
    new_congestion_csv = "results/new_congestion_periods.csv"
    already_congested_csv = "results/already_congested_periods.csv"
    
    # Detect intervals where battery charging introduces new congestion.
    detect_new_congestion_periods(solved_network, load_file, capacity_limit_mw, new_congestion_csv)
    
    # Detect intervals that are already congested.
    detect_already_congested_periods(load_file, capacity_limit_mw, already_congested_csv)

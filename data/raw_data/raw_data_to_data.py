import pandas as pd
import numpy as np
import os

def process_day_ahead(input_path, output_path, year):
    """
    Converts hourly day-ahead prices to 15-min intervals, skipping Feb 29.
    Ensures output covers exactly Jan 1 – Dec 31 (365 days = 35040 intervals).
    """
    # Read CSV
    df = pd.read_csv(input_path, parse_dates=["datetime"])

    # Filter and sort
    df = df[df["datetime"].dt.year == year]
    df = df[~((df["datetime"].dt.month == 2) & (df["datetime"].dt.day == 29))]
    df.sort_values("datetime", inplace=True)

    # Check we have exactly 8760 hourly values
    assert len(df) == 8760, f"Expected 8760 hourly values, got {len(df)}"

    # Expand each hourly price to 4x
    expanded_prices = np.repeat(df["price"].values, 4)

    # Generate timestamps without Feb 29
    new_timestamps = pd.date_range(
        start=f"{year}-01-01 00:00:00",
        end=f"{year}-12-31 23:45:00",
        freq="15min"
    )
    # Remove any Feb 29 timestamps just in case
    new_timestamps = new_timestamps[~((new_timestamps.to_series().dt.month == 2) & (new_timestamps.to_series().dt.day == 29))]

    # Final sanity check
    assert len(new_timestamps) == 35040, f"Expected 35040 timestamps, got {len(new_timestamps)}"
    assert len(expanded_prices) == 35040, f"Expected 35040 prices, got {len(expanded_prices)}"

    # Save final output
    df_expanded = pd.DataFrame({
        "datetime": new_timestamps,
        "price": expanded_prices,
        "jaar": year
    })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_expanded.to_csv(output_path, index=False)

    print(f"✅ Saved {len(df_expanded)} rows from Jan 1 to Dec 31 (excluding Feb 29) for {year}")


def process_load_levels(input_path, output_path):
    """
    Processes SS_Monnickendam.csv:
    - Keeps all years
    - Converts BELASTING from kWh to kW
    - Replaces the year in 'datetime' with the value from 'jaar'
    - Outputs columns: datetime, belasting, jaar (in that order)
    - Sorts by jaar and datetime
    """
    # Read the CSV
    df = pd.read_csv(input_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])

    # Rename for internal processing
    df.rename(columns={
        "DATUM_TIJD": "datetime",
        "JAAR": "jaar",
        "BELASTING": "belasting"
    }, inplace=True)

    # Replace the year in the datetime column with the value from 'jaar'
    df["datetime"] = df.apply(
        lambda row: row["datetime"].replace(year=int(row["jaar"])),
        axis=1
    )

    # Convert from kWh (per 15min) to MW
    df["belasting"] =( df["belasting"] /1000)

    # Reorder columns
    df = df[["datetime", "belasting", "jaar"]]

    # Sort by year and timestamp
    df.sort_values(by=["jaar", "datetime"], inplace=True)

    # Save to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    # Preview output
    print("Processed and corrected load data:")
    print(df.head(10))

def process_settlement_prices(input_path, output_path):
    """
    Processes settlement_prices.csv:
    - Parses 'Timeinterval Start Loc' as datetime and stores as 'timeinterval'
    - Extracts relevant columns: price shortage, price surplus, regulation state
    - Adds a 'jaar' column based on the timestamp
    - Removes first of any duplicate timestamps
    - Outputs columns in order: timeinterval, price_shortage, price_surplus, regulation_state, jaar
    - Saves cleaned CSV to output_path
    """
    import pandas as pd
    import os

    # Read the CSV
    df = pd.read_csv(input_path, sep=';')

    # Parse timeinterval and rename
    df["timeinterval"] = pd.to_datetime(df["Timeinterval Start Loc"])

    # Extract year from the timestamp
    df["jaar"] = df["timeinterval"].dt.year

    # Keep only the required columns and rename for clarity
    df_clean = df[[
        "timeinterval", 
        "Price Shortage", 
        "Price Surplus", 
        "Regulation State", 
        "jaar"
    ]].rename(columns={
        "Price Shortage": "price_shortage",
        "Price Surplus": "price_surplus",
        "Regulation State": "regulation_state"
    })

    # Sort by timeinterval
    df_clean.sort_values(by="timeinterval", inplace=True)

    # Remove the first of any duplicate timeintervals
    df_clean = df_clean[~df_clean["timeinterval"].duplicated(keep="last")]

    # Ensure output folder exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Save to CSV
    df_clean.to_csv(output_path, index=False)

    # Show preview
    print("Processed imbalance prices:")
    print(df_clean.head(10))

if __name__ == "__main__":
    # Process day-ahead prices
    day_ahead_input = "data/raw_data/day_ahead_2015.csv"
    day_ahead_output = "data/day_ahead_2015.csv"
    year = 2015  # Set the desired year for the day-ahead prices
    process_day_ahead(day_ahead_input, day_ahead_output, year)
    
    # Process load levels (all years included)
    # load_levels_input = "data/raw_data/SS_Monnickendam.csv"
    # load_levels_output = "data/new_SS_Monnickendam.csv"
    # process_load_levels(load_levels_input, load_levels_output)

    # settelement_prices_input = "data/raw_data/settlement_prices.csv"
    # settlement_prices_output = "data/new_settlement_prices.csv"
    # process_settlement_prices(settelement_prices_input, settlement_prices_output)
   

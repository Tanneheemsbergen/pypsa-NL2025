import pandas as pd
import numpy as np

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

    # Breek de expressie met haakjes, geen backslash nodig
    df_week = (
        df[(df["datetime"] >= start) & (df["datetime"] < end)]
        .set_index("datetime")
    )
    print(f"Load levels for week {week} of {year}:")
    print(df_week)
    return df_week["belasting"]

def load_day_ahead_prices(filepath, year, week):
    # Lees in met parse_dates
    df = pd.read_csv(filepath, parse_dates=["datetime"])
    # Filter op jaar
    df = df[df["jaar"] == year]
    # Bepaal begin en eind van de week
    start, end = get_week_range(year, week)

    # Gebruik haakjes om de lijn te breken, en zet datetime als index
    df_week = (
        df[(df["datetime"] >= start) & (df["datetime"] < end)]
        .set_index("datetime")
    )

    print(f"Day-ahead prices for week {week} of {year}:")
    print(df_week)
    # Retourneer de Series, inclusief index en name="price"
    return df_week["price"]

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
    #result_df = pd.DataFrame({
    #    "discharge_price": discharge_series,
    #    "charge_price": charge_series,
    #    "discharge_mask": discharge_mask_series,
    #    "charge_mask": charge_mask_series
   # })
   #result_df.to_csv("imbalance_debug_output.csv")

    return discharge_series, charge_series, discharge_mask_series, charge_mask_series

def load_solar_profile(filepath, year, week):
    """
    Load the solar generation profile from the given CSV file
    and return the solar generation values for the specified week.
    The CSV is expected to have a 'datetime' column as its index and a 
    'solar_generation' column.
    """
    df = pd.read_csv(filepath, parse_dates=["datetime"], index_col="datetime")
    start, end = get_week_range(year, week)
    # Filter to only the dates in the specified week.
    df_week = df[(df.index >= start) & (df.index < end)]
    print(f"Solar generation profile for week {week} of {year}:")
    print(df_week.head())
    return df_week["solar_generation"]
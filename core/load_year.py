import pandas as pd
import numpy as np


def get_year_range(year):
    """
    Returns a time range of exactly 365 days starting from January 1st of the given year.
    (Even if the year is a leap year, the simulation will cover only 365 days.)
    """
    start = pd.Timestamp(year, 1, 1)
    end = start + pd.Timedelta(days=365)
    print(f"For year {year}: start = {start} and end = {end}")
    return start, end


def load_load_levels(filepath, year):
    """
    Load the annual household load profile from CSV and return as pandas Series.
    Assumes the CSV has columns "datetime", "jaar" and "belasting".
    """
    df = pd.read_csv(filepath, parse_dates=["datetime"])
    print(f"Loaded {len(df)} rows from {filepath}")

    start, end = get_year_range(year)
    df_year = df[(df["datetime"] >= start) & (df["datetime"] < end)].copy()
    df_year.set_index("datetime", inplace=True)

    # Debug: first and last rows
    print(f"First 5 rows for year {year}:\n", df_year.head(5))
    print(f"Last 5 rows for year {year}:\n", df_year.tail(5))

    # Return the 'belasting' time series directly
    return df_year["belasting"]


def load_day_ahead_prices(filepath, year):
    """
    Load day-ahead electricity prices for the given year from CSV file.
    Assumes the CSV has a datetime index and a column "price".
    Returns a pandas Series indexed by datetime.
    """
    df = pd.read_csv(filepath, parse_dates=True, index_col=0)
    print(f"Loaded {len(df)} rows from day-ahead prices file {filepath}")

    start, end = get_year_range(year)
    df_year = df[(df.index >= start) & (df.index < end)].copy()

    # Debug: first and last rows
    print(f"First 5 day-ahead prices for year {year}:\n", df_year.head(5))
    print(f"Last 5 day-ahead prices for year {year}:\n", df_year.tail(5))

    # Return the 'price' time series directly
    return df_year["price"]


def load_imbalance_prices(filepath, year):
    """
    Load imbalance prices and masks for the given year.
    Returns four pandas Series: discharge_price, charge_price,
    discharge_mask, charge_mask, all indexed by datetime.
    """
    df = pd.read_csv(filepath, parse_dates=["timeinterval"])
    print(f"Loaded {len(df)} rows from imbalance prices file {filepath}")

    start, end = get_year_range(year)
    df_year = df[(df["timeinterval"] >= start) & (df["timeinterval"] < end)].copy()

    discharge_prices, charge_prices = [], []
    discharge_mask, charge_mask = [], []
    for _, row in df_year.iterrows():
        state = row["regulation_state"]
        surplus = row["price_surplus"]
        shortage = row["price_shortage"]
        d_val = np.nan
        c_val = np.nan
        if state == 1:
            d_val = surplus
        elif state == -1:
            c_val = shortage
        discharge_prices.append(d_val)
        charge_prices.append(c_val)
        discharge_mask.append(int(not np.isnan(d_val)))
        charge_mask.append(int(not np.isnan(c_val)))

    idx = df_year["timeinterval"]
    discharge_series      = pd.Series(discharge_prices, index=idx, name="discharge_price")
    charge_series         = pd.Series(charge_prices,    index=idx, name="charge_price")
    discharge_mask_series = pd.Series(discharge_mask,    index=idx, name="discharge_mask")
    charge_mask_series    = pd.Series(charge_mask,       index=idx, name="charge_mask")

    # Debug output (optional)
    df_out = pd.DataFrame({
        "discharge_price":      discharge_series,
        "charge_price":         charge_series,
        "discharge_mask":       discharge_mask_series,
        "charge_mask":          charge_mask_series
    })
    df_out.to_csv("imbalance_debug_output.csv")

    return discharge_series, charge_series, discharge_mask_series, charge_mask_series


def load_solar_profile(filepath, year):
    """
    Load the full-year solar generation profile from a CSV file.
    Assumes the CSV has a 'datetime' column and a 'solar_generation' column.
    Returns a pandas Series indexed by datetime.
    """
    df = pd.read_csv(filepath, parse_dates=["datetime"])
    print(f"Loaded {len(df)} rows from solar profile file {filepath}")

    start, end = get_year_range(year)
    df_year = df[(df["datetime"] >= start) & (df["datetime"] < end)].copy()
    df_year.set_index("datetime", inplace=True)

    # Debug: first rows
    print(f"First 5 solar generation rows for year {year}:\n", df_year.head(5))

    # Return the 'solar_generation' time series directly
    return df_year["solar_generation"]

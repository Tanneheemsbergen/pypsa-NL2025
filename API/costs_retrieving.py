from entsoe import EntsoePandasClient
import pandas as pd

# Initialize ENTSO-E client
client = EntsoePandasClient(api_key="539dfdf2-c0f1-47d8-97eb-24b9472cc70f")

# Define time range (2024 only)
start = pd.Timestamp('2024-01-01 01:00', tz='Europe/Amsterdam')
end = pd.Timestamp('2025-01-01 00:00', tz='Europe/Amsterdam')  # Full 2024 data
country_code = 'NL'

# Query day-ahead prices
ts = client.query_day_ahead_prices(country_code, start=start, end=end)

# Convert to DataFrame
df = ts.to_frame(name="price").reset_index()
df.rename(columns={"index": "datetime"}, inplace=True)

# ✅ Convert to UTC to avoid time zone parsing issues later
df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

# ✅ Extract year and store it in a new 'jaar' column
df["jaar"] = df["datetime"].dt.year

# ✅ Convert "datetime" to string to filter out February 29 without using `.dt`
df["datetime_str"] = df["datetime"].astype(str)

# ✅ Remove leap day (February 29) if present
df = df[~df["datetime_str"].str.contains("-02-29")]

# ✅ Drop the temporary "datetime_str" column
df = df.drop(columns=["datetime_str"])

# ✅ Save in ISO-8601 format (YYYY-MM-DD HH:MM:SS) without time zone offsets
df["datetime"] = df["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")

# Save to CSV with correct headers
df.to_csv("data/day_ahead.csv", index=False)

print("✅ Day-ahead prices for 2024 saved to data/day_ahead.csv with 'jaar' column (leap day removed).")

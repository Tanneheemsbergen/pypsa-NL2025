from entsoe import EntsoePandasClient
import pandas as pd

# Initialize ENTSO-E client
client = EntsoePandasClient(api_key="539dfdf2-c0f1-47d8-97eb-24b9472cc70f")
# Define time range (2024 only)
start = pd.Timestamp('2015-01-01 01:00', tz='Europe/Amsterdam')
end = pd.Timestamp('2016-01-01 00:00', tz='Europe/Amsterdam')  # Full 2024 data
country_code = 'NL'

# Query day-ahead prices
ts = client.query_day_ahead_prices(country_code, start=start, end=end)

# Convert to DataFrame
df = ts.to_frame(name="price").reset_index()
df.rename(columns={"index": "datetime"}, inplace=True)

# Convert to UTC to avoid time zone parsing issues later
df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

# Extract year and store it in a new 'jaar' column
df["jaar"] = df["datetime"].dt.year

# Convert "datetime" to string to filter out February 29 without using `.dt`
df["datetime_str"] = df["datetime"].astype(str)

# Remove leap day (February 29) if present
df = df[~df["datetime_str"].str.contains("-02-29")]

# Drop the temporary "datetime_str" column
df = df.drop(columns=["datetime_str"])

# Save in ISO-8601 format (YYYY-MM-DD HH:MM:SS) without time zone offsets
df["datetime"] = df["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")

# Save to CSV with correct headers
df.to_csv("data/test_2015.csv", index=False)

print("Day-ahead prices for 2015 saved to data/day_ahead.csv with 'jaar' column (leap day removed).")

# start = pd.Timestamp('2024-01-01 01:00', tz='Europe/Amsterdam')
# end = pd.Timestamp('2025-01-01 00:00', tz='Europe/Amsterdam')
# country_code = 'NL'
# agreement_types = ['A02', 'A03']  # aFRR and mFRR

# all_dfs = []

# for agreement in agreement_types:
#     ts = client.query_contracted_reserve_prices(
#         country_code=country_code,
#         start=start,
#         end=end,
#         type_marketagreement_type=agreement
#     )
#     df = ts.to_frame(name="price").reset_index()
#     df.rename(columns={"index": "datetime"}, inplace=True)
#     df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
#     df["jaar"] = df["datetime"].dt.year
#     df["type"] = agreement
#     all_dfs.append(df)

# # Combine and clean
# df_all = pd.concat(all_dfs)
# df_all["datetime_str"] = df_all["datetime"].astype(str)
# df_all = df_all[~df_all["datetime_str"].str.contains("-02-29")]
# df_all = df_all.drop(columns=["datetime_str"])
# df_all["datetime"] = df_all["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")

# # Save
# df_all.to_csv("data/reserve_prices.csv", index=False)

# print("Contracted reserve prices (A02, A03) saved to data/reserve_prices.csv.")
import atlite
import logging
import pandas as pd
import os

# Configure logging to display INFO-level messages.
logging.basicConfig(level=logging.INFO)

# Ensure output directories exist
os.makedirs("data/rawdata", exist_ok=True)
os.makedirs("data", exist_ok=True)

master_dfs = []

# Loop over each year from 2004 up to and including 2023
for year in range(2004, 2024):
    logging.info(f"Starting processing for year {year}")
    year_dfs = []
    
    # Loop through each month 1–12
    for month in range(1, 13):
        start = f"{year}-{month:02d}-01"
        # determine the next-month start
        if month < 12:
            end = f"{year}-{month+1:02d}-01"
        else:
            end = f"{year+1}-01-01"
        
        logging.info(f"  Processing {start} to {end}")
        raw_nc = f"data/rawdata/weather_{year}_{month:02d}.nc"
        
        cutout = atlite.Cutout(
            path=raw_nc,
            module="era5",
            x=slice(5, 6),
            y=slice(52, 53),
            time=slice(start, end)
        )
        cutout.prepare()
        
        df_chunk = cutout.data.to_dataframe()
        year_dfs.append(df_chunk)
    
    # Combine all months of this year
    df_year = pd.concat(year_dfs)
    df_year.sort_index(inplace=True)
    
    # (Optional) save per-year CSV
    out_csv_year = f"data/weather_{year}.csv"
    df_year.to_csv(out_csv_year)
    logging.info(f"  Year {year} saved to {out_csv_year}")
    
    master_dfs.append(df_year)

# Now combine ALL years into one big table
df_all = pd.concat(master_dfs)
df_all.sort_index(inplace=True)

# Save the master file
out_csv_all = "data/weather_2004_2023.csv"
df_all.to_csv(out_csv_all)
logging.info(f"All years 2004–2023 combined and saved to {out_csv_all}")

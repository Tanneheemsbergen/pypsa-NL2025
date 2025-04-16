import atlite
import logging
import pandas as pd

# Configure logging to display INFO-level messages.
logging.basicConfig(level=logging.INFO)

# Define the four three-month chunks for the year 2025.
# Each tuple represents (start_date, end_date) where end_date is exclusive.
# The end_date of one chunk is the start_date of the next.
time_chunks = [
    ("2024-01-01", "2024-04-01"),  # January to March
    ("2024-04-01", "2024-07-01"),  # April to June
    ("2024-07-01", "2024-10-01"),  # July to September
    ("2024-10-01", "2025-01-01")   # October to December
]

# List to hold DataFrames for each chunk.
dfs = []

# Loop over each time chunk.
for start, end in time_chunks:
    logging.info(f"Processing time chunk from {start} to {end}")
    
    # Create a cutout for the specified three-month period.
    # Using slice objects for x and y to target a specific location.
    # If a zero-width slice returns an empty dataset, try a minimal range:
    #     x=slice(5, 5 + 1e-6), y=slice(52, 52 + 1e-6)
    cutout = atlite.Cutout(
        path=f"weather_2024_{start}.nc",  # Unique file name per chunk
        module="era5",
        x=slice(5, 6),   # Specify x dimension as a slice for a single grid point
        y=slice(52, 53), # Specify y dimension as a slice for a single grid point
        time=slice(start, end)
    )
    
    # Download and process the data for this chunk.
    cutout.prepare()
    
    # Convert the processed data to a DataFrame.
    df_chunk = cutout.data.to_dataframe()
    
    # Append the chunk data to our list.
    dfs.append(df_chunk)

# Combine all the DataFrames into one.
df_2025 = pd.concat(dfs)

# It is good practice to sort the DataFrame by time if needed.
df_2025.sort_index(inplace=True)

# Save the complete DataFrame to a CSV file.
output_file = "data/weather_2024.csv"
df_2025.to_csv(output_file)

logging.info(f"Combined weather data for 2024 saved to {output_file}")
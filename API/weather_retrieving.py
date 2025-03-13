import atlite
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Specify cutout for one day in 2023
# x and y coordinates from boundingbox.klokantech.com
cutout = atlite.Cutout(
    path="north-holland-2023-01-01.nc",  # Use .nc for NetCDF format before conversion
    module="era5",
    x=slice(4.0, 6.0),
    y=slice(51.0, 53.0),
    time="2023-01-01",
)

# Prepare cutout because the cutout does not yet exist
cutout.prepare()

# Convert the dataset to a DataFrame and save it as a CSV file
df = cutout.data.to_dataframe()
df.to_csv("data/north-holland-2023-01-01.csv")

print("Data saved to norh-holland-2023-01-01.csv")
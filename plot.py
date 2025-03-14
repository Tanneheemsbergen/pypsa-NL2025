import pandas as pd
import matplotlib.pyplot as plt

# Load the CSV file
file_path = "data/SS_Monnickendam.csv" 
# Load CSV (adjust separator and decimal)
df = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])

# Convert column names to lowercase for easier handling
df.columns = df.columns.str.lower()

# Filter only 2024 data
df = df[df["jaar"] == 2024]

# Sort data by timestamp
df = df.sort_values(by="datum_tijd")

# Calculate mean load
mean_load = df["belasting"].mean()

# Define capacity limit (11.2 MVA * 0.9 capacity factor, assuming PF = 1)
capacity_limit = 11.2 * 0.9 * 1000  # Convert MVA to kW

# Plot
plt.figure(figsize=(12,5))
plt.plot(df["datum_tijd"], df["belasting"], label="Load (BELASTING)", color='blue', linewidth=0.7)

# Highlight areas where load exceeds capacity
plt.fill_between(df["datum_tijd"], df["belasting"], capacity_limit, where=df["belasting"] > capacity_limit, color='red', alpha=0.3, label="Over Capacity")

# Add capacity limit line
plt.axhline(y=capacity_limit, color='orange', linestyle='--', linewidth=1.5, label=f"Capacity Limit = {capacity_limit:.0f} kW")

# Add mean load line
plt.axhline(y=mean_load, color='green', linestyle='--', linewidth=1.5, label=f"Mean Load = {mean_load:.2f} kW")

# Labels and title
plt.xlabel("Date")
plt.ylabel("Load (kW)")
plt.title("Load Profile for SS Monnickendam (2024)")
plt.legend()
plt.grid(True)

# Show plot
plt.show()
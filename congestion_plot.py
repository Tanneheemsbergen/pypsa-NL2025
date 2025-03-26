
# %%
import pandas as pd
import matplotlib.pyplot as plt
from network import create_network
import networkx as nx
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

file_path = "data/SS_Monnickendam.csv"

# %%
# Load data
df = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df.columns = df.columns.str.lower()

# Sort by time
df = df.sort_values(by="datum_tijd")
df["datum_tijd"] = df["datum_tijd"] + pd.DateOffset(years=1)

# Calculate mean load
mean_load = df["belasting"].mean()

# Plot
plt.figure(figsize=(12, 5))

# Plot load levels
plt.plot(df["datum_tijd"], df["belasting"], color='blue', linewidth=0.7, label="Load Level")

# Plot mean load
plt.axhline(y=mean_load, color='green', linestyle='--', linewidth=1.5, label=f"Mean Load = {mean_load:.2f} kW")

# Formatting
plt.xlabel("Date")
plt.ylabel("Load (kW)")
plt.title("Load Profile with Mean Load")
plt.legend(loc="lower left")  # Legend at bottom-left
plt.xticks(rotation=45)  # Rotate dates for readability
plt.grid(True)

# Show plot
plt.show()

# %%
# Congestion plot
# Load data
df = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df.columns = df.columns.str.lower()
df = df[df["jaar"] == 2030].sort_values(by="datum_tijd")

# Shift dates forward by one year
df["datum_tijd"] = df["datum_tijd"] + pd.DateOffset(years=7)

# Capacity limit calculation
capacity_limit = 11.2 * 0.85 * 1000  # Convert MVA to kW

# Count the number of times the load exceeds the capacity
exceed_count = (df["belasting"] > capacity_limit).sum()
exceed_hours = exceed_count * 15 / 60  # Convert exceed count to hours
print(f"Number of times load exceeds capacity: {exceed_count} (equivalent to {exceed_hours:.2f} hours)")

# Plot
plt.figure(figsize=(12, 5))

# Plot normal load
plt.plot(df["datum_tijd"], df["belasting"], label="Load Level", color='blue', linewidth=0.7)

# Highlight areas where load exceeds capacity
above_limit = df["belasting"] > capacity_limit
plt.plot(df["datum_tijd"][above_limit], df["belasting"][above_limit], color='red', linewidth=0.7, label="Over Capacity")

# Add capacity limit line
plt.axhline(y=capacity_limit, color='orange', linestyle='--', linewidth=1.5, label=f"Capacity Limit = {capacity_limit:.0f} kW")

# Fix x-axis formatting
plt.xticks(rotation=45)
plt.xlabel("Date")
plt.ylabel("Load (kW)")
plt.title("Load Profile for SS Monnickendam (2030)")

# Place legend in the bottom-left corner
plt.legend(loc="lower left")

plt.grid(True)
plt.show()

# %%
# Ensure plot directory exists
plot_dir = "plots"
os.makedirs(plot_dir, exist_ok=True)

# Load data
df = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df.columns = df.columns.str.lower()
df = df[(df["jaar"] >= 2024) & (df["jaar"] <= 2032)].sort_values(by="datum_tijd")

# Calculate statistics
capacity_limit = 11.2 * 0.85 * 1000  # Convert MVA to kW

# Aggregate congestion hours per month
df["month"] = df["datum_tijd"].dt.to_period("M")
df["congestion"] = (df["belasting"] > capacity_limit) * 0.25  # Convert 15-minute intervals to hours
df_heatmap = df.groupby(["jaar", "month"]).agg({"congestion": "sum"}).reset_index()
df_heatmap["month"] = df_heatmap["month"].astype(str).str[-2:].astype(int)  # Convert month to integer

# Pivot for heatmap
df_pivot = df_heatmap.pivot(index="jaar", columns="month", values="congestion")

# Print table for copying
print("\nCongestion Hours per Month (2024-2032):")
print(df_pivot.to_string())
# Plot heatmap
plt.figure(figsize=(12, 6))
sns.heatmap(df_pivot, cmap="Reds", annot=True, fmt=".1f", linewidths=0.5, cbar_kws={'label': 'Congestion Hours'})
plt.xlabel("Month")
plt.ylabel("Year")
plt.title("Monthly Congestion Hours (Load Exceeds Capacity) from 2024 to 2032")

# Save plot to 'plots' directory
plot_path = os.path.join(plot_dir, "congestion_heatmap.png")
plt.savefig(plot_path, dpi=300, bbox_inches='tight')
plt.show()

print(f"Plot saved at: {plot_path}")

# %%
# congestion times to csv
# Load data

# Load data
df = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df.columns = df.columns.str.lower()
df = df[(df["jaar"] >= 2024) & (df["jaar"] <= 2032)].copy()

# Define capacity limit
capacity_limit = 11.2 * 0.85 * 1000  # Convert MVA to kW

# Correct the year in 'datum_tijd' using the 'jaar' column
df["datum_tijd"] = df.apply(lambda row: row["datum_tijd"].replace(year=row["jaar"]), axis=1)

# Sort again by corrected datetime
df = df.sort_values(by="datum_tijd")

# Filter rows where congestion occurs
df_congestion = df[df["belasting"] > capacity_limit].copy()

# Print timestamps of congestion
print("\nExact timestamps of congestion occurrences:")
print(df_congestion[["jaar", "datum_tijd", "belasting"]].to_string(index=False))

# Define output file path
output_csv_path = os.path.join("data", "congestion_timestamps.csv")

# Save to CSV
df_congestion[["jaar", "datum_tijd", "belasting"]].to_csv(output_csv_path, index=False)
print(f"Congestion timestamps saved to: {output_csv_path}")

# %%

# %%
#congestion frequency
df_2032 = df_congestion[df_congestion["jaar"] == 2030]
# Extract hour of congestion occurrences
df_2032["hour"] = df_2032["datum_tijd"].dt.hour

# Count congestion occurrences per hour
hourly_congestion = df_2032["hour"].value_counts().sort_index()
plt.figure(figsize=(12, 5))
sns.barplot(x=hourly_congestion.index, y=hourly_congestion.values, color="red", alpha=0.8)

# Labels
plt.xlabel("Hour of the Day")
plt.ylabel("Congestion Occurrences")
plt.title("Congestion Frequency Per Hour in 2030")

# Formatting
plt.xticks(range(0, 24), labels=[f"{h}:00" for h in range(0, 24)])
plt.grid(axis="y", linestyle="--", alpha=0.7)
plt.show()

# %%
# Shows imbalance market prices
# Load data (assuming file is saved as CSV)
df = pd.read_csv("data/settlement_prices.csv", sep=";")

# Convert time column and prices to proper formats
df['Timeinterval Start Loc'] = pd.to_datetime(df['Timeinterval Start Loc'], errors='coerce')
df['Price Shortage'] = pd.to_numeric(df['Price Shortage'], errors='coerce')
df['Price Surplus'] = pd.to_numeric(df['Price Surplus'], errors='coerce')

# Plot 1: Price Shortage
plt.figure(figsize=(15, 5))
plt.plot(df['Timeinterval Start Loc'], df['Price Shortage'], color='crimson', label='Price Shortage')
plt.title("Shortage Prices Over Time (2024)")
plt.xlabel("Date")
plt.ylabel("Price (EUR/MWh)")
plt.legend(loc='lower left')
plt.grid(True)
plt.tight_layout()
plt.show()

# Plot 2: Price Surplus
plt.figure(figsize=(15, 5))
plt.plot(df['Timeinterval Start Loc'], df['Price Surplus'], color='royalblue', label='Price Surplus')
plt.title("Surplus Prices Over Time (2024)")
plt.xlabel("Date")
plt.ylabel("Price (EUR/MWh)")
plt.legend(loc='lower left')
plt.grid(True)
plt.tight_layout()
plt.show()
# %%

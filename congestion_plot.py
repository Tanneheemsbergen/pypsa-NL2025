
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
"""Plots the load profile for SS Monnickendam and highlights capacity violations."""
# Load data
df = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df.columns = df.columns.str.lower()
df = df[df["jaar"] == 2032].sort_values(by="datum_tijd")

# Calculate statistics
mean_load = df["belasting"].mean()
capacity_limit = 11.2 * 0.85 * 1000  # Convert MVA to kW

# Count the number of times the load exceeds the capacity
exceed_count = (df["belasting"] > capacity_limit).sum()
# Convert exceed_count to hours
exceed_hours = exceed_count * 15 / 60
print(f"Number of times load exceeds capacity: {exceed_count} (equivalent to {exceed_hours:.2f} hours)")

# Plot
plt.figure(figsize=(12, 5))

# Plot normal load
plt.plot(df["datum_tijd"], df["belasting"], label="Load (BELASTING)", color='blue', linewidth=0.7)

# Highlight areas where load exceeds capacity
above_limit = df["belasting"] > capacity_limit
plt.plot(df["datum_tijd"][above_limit], df["belasting"][above_limit], color='red', linewidth=0.7, label="Over Capacity")

plt.axhline(y=capacity_limit, color='orange', linestyle='--', linewidth=1.5, label=f"Capacity Limit = {capacity_limit:.0f} kW")
plt.axhline(y=mean_load, color='green', linestyle='--', linewidth=1.5, label=f"Mean Load = {mean_load:.2f} kW")

plt.xlabel("Date")
plt.ylabel("Load (kW)")
plt.title("Load Profile for SS Monnickendam (2024)")
plt.legend()
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

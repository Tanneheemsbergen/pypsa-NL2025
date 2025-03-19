
# %%
import pandas as pd
import matplotlib.pyplot as plt
from network import create_network
import networkx as nx
import matplotlib.pyplot as plt

file_path = "data/SS_Monnickendam.csv"

# %%
"""Plots the load profile for SS Monnickendam and highlights capacity violations."""

# Load data
df = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df.columns = df.columns.str.lower()
df = df[df["jaar"] == 2024].sort_values(by="datum_tijd")

# Calculate statistics
mean_load = df["belasting"].mean()
capacity_limit = 11.2 * 0.85 * 1000  # Convert MVA to kW

# Count the number of times the load exceeds the capacity
exceed_count = (df["belasting"] > capacity_limit).sum()
# Convert exceed_count to hours
exceed_hours = exceed_count * 15 / 60
print(f"Number of times load exceeds capacity: {exceed_count} (equivalent to {exceed_hours:.2f} hours)")

# Plot
plt.figure(figsize=(12,5))
plt.plot(df["datum_tijd"], df["belasting"], label="Load (BELASTING)", color='blue', linewidth=0.7)
plt.fill_between(df["datum_tijd"], df["belasting"], capacity_limit, where=df["belasting"] > capacity_limit, color='red', alpha=0.3, label="Over Capacity")
plt.axhline(y=capacity_limit, color='orange', linestyle='--', linewidth=1.5, label=f"Capacity Limit = {capacity_limit:.0f} kW")
plt.axhline(y=mean_load, color='green', linestyle='--', linewidth=1.5, label=f"Mean Load = {mean_load:.2f} kW")

plt.xlabel("Date")
plt.ylabel("Load (kW)")
plt.title("Load Profile for SS Monnickendam (2024)")
plt.legend()
plt.grid(True)
plt.show()


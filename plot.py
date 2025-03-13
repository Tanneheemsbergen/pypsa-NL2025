import pandas as pd
import matplotlib.pyplot as plt

# Load the CSV file
file_path = "data\SS_monnickendam.csv"  # Change if needed
df = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])

# Convert column names to lowercase for easier handling
df.columns = df.columns.str.lower()

# Sort data by timestamp (just in case)
df = df.sort_values(by="datum_tijd")

# Calculate mean load
mean_load = df["belasting"].mean()

# Plot the data
plt.figure(figsize=(12,5))
plt.plot(df["datum_tijd"], df["belasting"], label="Load (BELASTING)", color='blue', linewidth=0.7)
plt.axhline(y=mean_load, color='red', linestyle='--', linewidth=1.5, label=f"Mean Load = {mean_load:.2f} kW")
plt.xlabel("Date")
plt.ylabel("Load (kW)")
plt.title("Load Profile for SS Monnickendam (2023)")
plt.legend()
plt.grid(True)
plt.show()
import pandas as pd
import matplotlib.pyplot as plt
from solve import solve_network

def plot_simulation_results(network):
    """Plots household load, battery storage, and grid imports."""
    hours = network.snapshots

    plt.figure(figsize=(10,5))
    plt.plot(hours, network.loads_t.p["household_load"], label="Household Load (MW)", linestyle="dotted")
    plt.plot(hours, network.generators_t.p["DAM_Generator"], label="Grid Import (MW)")
    plt.plot(hours, network.links_t.p0["Household_to_BESS"], label="Battery Charging (MW)", linestyle="dashed")
    plt.plot(hours, network.links_t.p0["BESS_to_Household"], label="Battery Discharging (MW)", linestyle="dashdot")
    plt.plot(hours, network.stores_t.e["BESS"], label="Battery State of Charge (MWh)", linestyle="solid")

    plt.legend()
    plt.xlabel("Time (Hours)")
    plt.ylabel("Power (MW) / Energy (MWh)")
    plt.title("Household Load, BESS, and Grid Interaction")
    plt.grid()
    plt.show()

def plot_ss_monnickendam(file_path):
    """Plots the load profile for SS Monnickendam and highlights capacity violations."""
    df = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
    df.columns = df.columns.str.lower()
    df = df[df["jaar"] == 2024].sort_values(by="datum_tijd")

    # Calculate statistics
    mean_load = df["belasting"].mean()
    capacity_limit = 11.2 * 0.9 * 1000  # Convert MVA to kW

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

if __name__ == "__main__":
    # Run network simulation and plot results
    year = 2024
    solved_network = solve_network(year)
    plot_simulation_results(solved_network)

    # Plot SS Monnickendam Load Profile
    plot_ss_monnickendam("data/SS_Monnickendam.csv")

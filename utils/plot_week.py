import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from solve_week import solve_network

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

def plot_bess_performance(network):
    """Plots the battery charge/discharge behavior and state of charge."""
    plt.figure(figsize=(12,5))

    # Plot battery charging (negative values, meaning power is going into the battery)
    plt.plot(network.snapshots, -network.links_t.p0["Household_to_BESS"], 
             label="Battery Charging (MW)", linestyle="dashed", color="blue")

    # Plot battery discharging (positive values, meaning power is leaving the battery)
    plt.plot(network.snapshots, network.links_t.p0["BESS_to_Household"], 
             label="Battery Discharging (MW)", linestyle="dashdot", color="red")
    # Plot battery discharging (positive values, meaning power is leaving the battery)
    plt.plot(network.snapshots, network.links_t.p0["Household_to_SS"], 
             label="Battery Feed In (MW)", linestyle="dashdot", color="green")

    # Plot battery state of charge (SOC)
    plt.plot(network.snapshots, network.stores_t.e["BESS"], 
             label="Battery State of Charge (MWh)", linestyle="solid", color="black")

    plt.legend()
    plt.xlabel("Time")
    plt.ylabel("Power (MW) / Energy (MWh)")
    plt.title("Battery Storage Operation - Arbitrage Performance")
    plt.grid()
    plt.show()

    # Print battery behavior
    print("Battery Behavior:")
    capacity_limit= 11.2 * 0.9 * 1000  # Convert MVA to kW
    for t in network.snapshots:
        load = network.loads_t.p.at[t, "household_load"]
        print(load)
        discharge = network.links_t.p0.at[t, "BESS_to_Household"]
        total_load = load + discharge
        if total_load > capacity_limit:
            print(f"At {t}, total load ({total_load} kW) exceeds capacity limit ({capacity_limit} kW).")

if __name__ == "__main__":
    # Run network simulation and plot results
    year = 2024
    solved_network = solve_network(year, week=10)  # Change week as needed
    # print load on SS
    ss_load = solved_network.loads_t.p["household_load"]
    print("First few SS Load values (should increase due to battery arbitrage):")
    for t, value in ss_load.items():
        if value > 0:
            print(f"At {t}, SS load: {value} kW")
    plot_simulation_results(solved_network)
    plot_bess_performance(solved_network)
    # Plot SS Monnickendam Load Profile
    #plot_ss_monnickendam("data/SS_Monnickendam.csv")


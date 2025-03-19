import os
import yaml
import pypsa
import pandas as pd

def create_network(battery_specs_file, prices, year):
    """Creates a PyPSA network with buses, generators, loads, BESS as Store, and links."""

    # Verify that the battery specs file exists
    if not os.path.exists(battery_specs_file):
        raise FileNotFoundError(f"Error: Battery specs file '{battery_specs_file}' not found!")

    # Load battery specs
    with open(battery_specs_file, "r") as file:
        battery_specs = yaml.safe_load(file)

    # Check if prices are loaded correctly
    if len(prices) == 0:
        raise ValueError("Error: Prices array is empty")

    # Create PyPSA network
    network = pypsa.Network()

    # Add Components
    network.add("Carrier", "electricity")

    # Add buses
    network.add("Bus", "SS", carrier="electricity")
    network.add("Bus", "Electricity_Grid", carrier="electricity")
    network.add("Bus", "Household", carrier="electricity")
    network.add("Bus", "Battery", carrier="electricity")

    network.add("Load", "household_load", bus="Household", carrier="electricity")

    # Add BESS as a Store
    network.add("Store", "BESS",
                bus="Household",
                carrier="electricity",
                e_nom=battery_specs["capacity_mwh"],
                e_initial=battery_specs["initial_soc_mwh"],
                standing_loss=battery_specs["standing_loss"])
     # Add generator
    network.add("Generator", "DAM_Generator",
                bus="Electricity_Grid",
                p_nom=100,
                marginal_cost=50)

    # Add essential links
    network.add("Link", "Grid_to_SS", bus0="Electricity_Grid", bus1="SS", p_nom=50, carrier="electricity")
    network.add("Link", "SS_to_Grid", bus0="SS", bus1="Electricity_Grid", p_nom=50, carrier="electricity")
    network.add("Link", "SS_to_Household", bus0="SS", bus1="Household", p_nom=50, marginal_cost=10, carrier="electricity")
    network.add("Link", "Household_to_SS", bus0="Household", bus1="SS", p_nom=50, carrier="electricity")
   
    network.add("Link", "Household_to_BESS",
                bus0="Household", bus1="Battery", 
                p_nom=battery_specs["charge_power_mw"],
                efficiency=battery_specs["charge_efficiency"],
                carrier="electricity")

    network.add("Link", "BESS_to_Household",
                bus0="Battery", bus1="Household", 
                p_nom=battery_specs["discharge_power_mw"],
                efficiency=battery_specs["discharge_efficiency"],
                carrier="electricity")

    # Apply marginal costs
    # network.snapshots = pd.date_range(f"{year}-01-01", periods=len(prices), freq="h")
    network.snapshots = pd.date_range(f"{year}-01-01", periods=672, freq="h")
    network.links_t.marginal_cost = pd.DataFrame({
        "Household_to_BESS": -prices,
        "BESS_to_Household": prices
    }, index=network.snapshots)
    return network  # Ensure we return the network

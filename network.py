import os
import yaml
import pypsa
import pandas as pd

def create_network(battery_specs_file, prices, charge_prices, discharge_prices, year):
    """Creates a PyPSA network with buses, generators, loads, BESS as Store, and links."""

    # Verify that the battery specs file exists
    if not os.path.exists(battery_specs_file):
        raise FileNotFoundError(f"Error: Battery specs file '{battery_specs_file}' not found!")

    # Load battery specs
    with open(battery_specs_file, "r") as file:
        battery_specs = yaml.safe_load(file)

    # Create PyPSA network
    network = pypsa.Network()
    ENERGY_TAX = 0.0123
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
                bus="Battery",
                carrier="electricity",
                e_nom=battery_specs["capacity_mwh"],
                e_initial=battery_specs["initial_soc_mwh"],
                standing_loss=battery_specs["standing_loss"])

    
   # Add generator
    network.add("Generator", "DAM_Generator",
               bus="Electricity_Grid",
               carrier="DAM_Generator",
               p_nom=20_000,
               p_min_pu=0,
               p_max_pu=1
               )
    
    network.add("Generator", "negative_DAM_Generator",
                 bus="Electricity_Grid",
                 p_nom=battery_specs["capacity_mwh"],
                 p_min_pu=-1,
                 p_max_pu=0
                 )

    # # Add imbalance generator
    # network.add("Generator", "IMBALANCE_Generator",
    #             bus="Electricity_Grid",
    #             carrier = "IMBALANCE_Generator",
    #             p_nom=20000,
    #             p_max_pu=1,
    #             p_min_pu=0)

    # # Add negative imbalance generator to sell energy
    # network.add("Generator", "negative_IMBALANCE_Generator",
    #             bus="Electricity_Grid",
    #             carrier = "negative_IMBALANCE_Generator",
    #             p_nom=20000,
    #             p_min_pu=-1,
    #             p_max_pu=0)
    
    # Add essential links
    network.add("Link", "Grid_to_SS", bus0="Electricity_Grid", bus1="SS", p_nom=20_000, carrier="Grid_to_SS")
    network.add("Link", "SS_to_Grid", bus0="SS", bus1="Electricity_Grid", p_nom=20_000, carrier="SS_to_Grid")
    network.add("Link", "SS_to_Household", bus0="SS", bus1="Household", p_nom=20_000, marginal_cost=ENERGY_TAX, carrier="SS_to_Household")
    network.add("Link", "Household_to_SS", bus0="Household", bus1="SS", p_nom=20_000, carrier="Household_to_SS")
   
    network.add("Link", "Household_to_BESS",
                bus0="Household", bus1="Battery",
                p_nom=battery_specs["charge_power_mw"],
                p_nom_extendable=False,
                efficiency=battery_specs["charge_efficiency"],
                carrier="charge")

    network.add("Link", "BESS_to_Household",
                bus0="Battery", bus1="Household",
                p_nom=battery_specs["discharge_power_mw"],
                p_nom_extendable=False,
                efficiency=battery_specs["discharge_efficiency"],
                carrier="discharge")

    return network 
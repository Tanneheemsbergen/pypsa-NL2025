import os
import pypsa
import yaml
import pandas as pd

def create_network(battery_specs_file, prices, charge_prices, discharge_prices, year):
    """Creates a PyPSA network with buses, generators, loads, BESS as Store, and links."""

    # Verify that the battery specs file exists
    if not os.path.exists(battery_specs_file):
        raise FileNotFoundError(f"Error: Battery specs file '{battery_specs_file}' not found!")

    solar_profile = pd.read_csv("data/solar_generation_profile_2024_15min.csv",
                            index_col=0, 
                            parse_dates=True)
    # Load battery specs
    with open(battery_specs_file, "r") as file:
        battery_specs = yaml.safe_load(file)

    # Create PyPSA network
    network = pypsa.Network()
    ENERGY_TAX = 0.12286
    # Add Components
    network.add("Carrier", "electricity")

    # Add buses
    network.add("Bus", "SS", carrier="electricity")
    network.add("Bus", "Electricity_Grid", carrier="electricity")
    network.add("Bus", "DAM", carrier="electricity")
    network.add("Bus", "Imbalance", carrier="electricity")
    network.add("Bus", "Household", carrier="electricity")
    network.add("Bus", "Battery", carrier="electricity")
    network.add("Bus", "PV", carrier="electricity")

    network.add("Load", "household_load", bus="Household", carrier="electricity")

    # Add BESS as a Store
    network.add("Store", "BESS",
                bus="Battery",
                carrier="electricity",
                e_nom=battery_specs["capacity_mwh"],
                e_initial=battery_specs["initial_soc_mwh"],
                standing_loss=battery_specs["standing_loss"])

    
    # Add PV Generator
    pv_installed_capacity = battery_specs["pv"].get("installed_capacity_mw")
    network.add("Generator", "PV_Generator",
                bus="PV",
                carrier="solar",
                p_nom=pv_installed_capacity,
                marginal_cost=0,
                p_max_pu=0)
    

   # Add generator
    network.add("Generator", "DAM_Generator",
               bus="DAM",
               carrier="DAM_Generator",
               p_nom=50_000,
               p_min_pu=0,
               p_max_pu=1
               )
    
    network.add("Generator", "negative_DAM_Generator",
                 bus="DAM",
                carrier="negative_DAM_Generator",
                 p_nom=50000,
                 p_min_pu=-1,
                 p_max_pu=0
                 )

    # # Add imbalance generator
    network.add("Generator", "IMBALANCE_Generator",
                bus="Imbalance",
                carrier = "IMBALANCE_Generator",
                p_nom=50000,
                p_min_pu=0)

    # Add negative imbalance generator to sell energy
    network.add("Generator", "negative_IMBALANCE_Generator",
                bus="Imbalance",
                carrier = "negative_IMBALANCE_Generator",
                p_nom=50000,
                p_max_pu=0)
    
    # Add essential links
    network.add("Link", "Grid_to_SS", bus0="Electricity_Grid", bus1="SS", p_nom=50000, carrier="Grid_to_SS")
    network.add("Link", "SS_to_Grid", bus0="SS", bus1="Electricity_Grid", p_nom=50000, carrier="SS_to_Grid")
    network.add("Link", "Grid_to_DAM", bus0="Electricity_Grid", bus1="DAM", p_nom=50000, carrier="Grid_to_DAM")
    network.add("Link", "DAM_to_Grid", bus0="DAM", bus1="Electricity_Grid", p_nom=50000, carrier="DAM_to_Grid")
    network.add("Link", "Imbalance_to_Grid", bus0="Imbalance", bus1="Electricity_Grid", p_nom=50000, carrier="Imbalance_to_Grid")
    network.add("Link", "Grid_to_Imbalance", bus0="Electricity_Grid", bus1="Imbalance", p_nom=50000, carrier="Grid_to_Imbalance")
    network.add("Link", "SS_to_Household", bus0="SS", bus1="Household", p_nom=50000, marginal_cost=ENERGY_TAX, carrier="SS_to_Household")
    network.add("Link", "Household_to_SS", bus0="Household", bus1="SS", p_nom=50000, carrier="Household_to_SS")
    network.add("Link", "PV_to_Household", bus0="PV", bus1="Household", p_nom=50000, carrier="PV_to_Household")
   
    network.add("Link", "Household_to_BESS",
                bus0="Household", bus1="Battery",
                p_nom=battery_specs["charge_power_mw"],
                p_nom_extendable=False,
                efficiency=battery_specs["charge_efficiency"],
                marginal_cost=0,
                committable = True,
                carrier="charge")

    network.add("Link", "BESS_to_Household",
                bus0="Battery", bus1="Household",
                p_nom=battery_specs["discharge_power_mw"],
                p_nom_extendable=False,
                efficiency=battery_specs["discharge_efficiency"],
                marginal_cost=0,
                committable = True,
                carrier="discharge")

    return network

def extra_bess_link_status(network, snapshots):
    """
    Adds a custom constraint that, for each snapshot, the sum of the status variables for the
    two BESS links is <= 1, ensuring that the battery cannot charge and discharge simultaneously.
    
    This function uses the built-in unit commitment status variable, which is stored under "Link-status"
    with coordinates "Link-com" and "snapshot". It then adds an exclusivity constraint per snapshot.
    """
    print("Running extra_bess_link_status extra functionality...")
    m = network.model  # The Linopy model instance (created via n.optimize.create_model())
    
    # Loop over each snapshot and add the exclusivity constraint.
    for s in snapshots:
        print(f"Processing snapshot: {s}")
        try:
            # Use .sel() with a dictionary to select the status variables using the coordinate "Link-com"
            status_charge = m.variables["Link-status"].sel({"Link-com": "Household_to_BESS", "snapshot": s})
            print(m.variables["Link-status"].sel({"Link-com": "Household_to_BESS", "snapshot": s}))
            status_discharge = m.variables["Link-status"].sel({"Link-com": "BESS_to_Household", "snapshot": s})
        except Exception as e:
            print(f"Error accessing status variables at snapshot {s}: {e}")
            raise
        
        # Add the constraint that the sum of the status variables is at most 1.
        try:
            m.add_constraints(status_charge + status_discharge <= 1,
                              name=f"bess_status_exclusivity_{s}")
            print(f"Constraint added for snapshot {s}.")
        except Exception as e:
            print(f"Error adding constraint at snapshot {s}: {e}")
            raise
    print("Finished adding custom BESS link status constraints.")


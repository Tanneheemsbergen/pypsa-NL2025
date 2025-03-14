import pypsa
import yaml

def create_network(battery_specs_file):
    """Creates a PyPSA network with buses, generators, loads, BESS as Store, and links."""
    # Load battery specs
    with open(battery_specs_file, "r") as file:
        battery_specs = yaml.safe_load(file)

    # Create network
    network = pypsa.Network()

    # ✅ Add buses
    network.add("Bus", "SS")  # Substation Monnickendam
    network.add("Bus", "Electricity_Grid")  # Main electricity grid
    network.add("Bus", "Household")  # Residential area

    # ✅ Add household load (demand will be set dynamically in `solve.py`)
    network.add("Load", "household_load", bus="Household")

    # ✅ Add BESS as a Store (directly connected to the Household bus)
    network.add("Store", "BESS",
                bus="Household",  # Connected to Household bus
                e_nom=battery_specs["capacity_mwh"],  # Storage capacity (MWh)
                e_initial=battery_specs["initial_soc_mwh"],  # Initial SOC (MWh)
                standing_loss=battery_specs["standing_loss"])  # Small energy loss per hour

    # ✅ Add essential links
    ## 🟢 Grid ↔ SS (Power import/export between grid and substation)
    network.add("Link", "Grid_to_SS",
                bus0="Electricity_Grid", bus1="SS",
                p_nom=50)  # 50 MW capacity

    network.add("Link", "SS_to_Grid",
                bus0="SS", bus1="Electricity_Grid",
                p_nom=50)  # 50 MW capacity

    ## 🟢 SS ↔ Household (Deliver power from SS to home, considering energy tax)
    network.add("Link", "SS_to_Household",
                bus0="SS", bus1="Household",
                p_nom=20,  # Max 20 MW transfer capacity
                marginal_cost=10)  # Energy tax of 10 €/MWh

    network.add("Link", "Household_to_SS",
                bus0="Household", bus1="SS",
                p_nom=20)  # Max 20 MW return capacity

    ## 🟢 Household ↔ BESS (Charge & Discharge)
    network.add("Link", "Household_to_BESS",
                bus0="Household", bus1="Household",
                p_nom=battery_specs["charge_power_mw"],  # Max charge power
                efficiency=battery_specs["charge_efficiency"])  # Charging efficiency

    network.add("Link", "BESS_to_Household",
                bus0="Household", bus1="Household",
                p_nom=battery_specs["discharge_power_mw"],  # Max discharge power
                efficiency=battery_specs["discharge_efficiency"])  # Discharging efficiency

    return network

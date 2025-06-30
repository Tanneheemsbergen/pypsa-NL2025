import os
import pypsa
import yaml
import pandas as pd

def create_network(battery_specs_file, prices, charge_prices, discharge_prices, year, energy_tax, battery_overrides: dict | None = None):
    if not os.path.exists(battery_specs_file):
        raise FileNotFoundError(f"Battery specs file not found at: {battery_specs_file}")

    with open(battery_specs_file, "r") as file:
        battery_specs = yaml.safe_load(file)
    
    network = pypsa.Network()

    network.add("Carrier", "electricity")

    network.add("Bus", "MSR", carrier="electricity")
    network.add("Bus", "Electricity_Grid", carrier="electricity")
    network.add("Bus", "DAM", carrier="electricity")
    network.add("Bus", "Imbalance", carrier="electricity")
    network.add("Bus", "Household", carrier="electricity")
    network.add("Bus", "Battery", carrier="electricity")
    network.add("Bus", "PV", carrier="electricity")

    network.add("Load", "HouseholdLoad", bus="Household", carrier="electricity")

    network.add("Store", "BESS",
                bus="Battery",
                carrier="electricity",
                e_nom=battery_specs["capacity_mwh"],
                e_initial=battery_specs["initial_soc_mwh"],
                standing_loss=battery_specs["standing_loss"])

    pv_installed_capacity = battery_specs["pv"].get("p_nom")
    network.add("Generator", "PV_Generator",
                bus="PV",
                carrier="solar",
                p_nom=pv_installed_capacity,
                marginal_cost=0,
                p_max_pu=0)

    network.add("Generator", "DAM_Generator",
               bus="DAM",
               carrier="DAM_Generator",
               p_nom=50000,
               p_min_pu=0,
               p_max_pu=1)

    network.add("Generator", "negative_DAM_Generator",
                 bus="DAM",
                 carrier="negative_DAM_Generator",
                 p_nom=50000,
                 p_min_pu=-1,
                 p_max_pu=0)

    network.add("Generator", "IMBALANCE_Generator",
                bus="Imbalance",
                carrier="IMBALANCE_Generator",
                p_nom=50000,
                p_min_pu=0)

    network.add("Generator", "negative_IMBALANCE_Generator",
                bus="Imbalance",
                carrier="negative_IMBALANCE_Generator",
                p_nom=50000,
                p_max_pu=0)

    network.add("Link", "Grid → MSR", bus0="Electricity_Grid", bus1="MSR", p_nom=50000, carrier="Grid → MSR")
    network.add("Link", "MSR → Grid", bus0="MSR", bus1="Electricity_Grid", p_nom=50000, carrier="MSR → Grid")
    network.add("Link", "Grid → DAM", bus0="Electricity_Grid", bus1="DAM", p_nom=50000, carrier="Grid → DAM")
    network.add("Link", "DAM → Grid", bus0="DAM", bus1="Electricity_Grid", p_nom=50000, carrier="DAM → Grid")
    network.add("Link", "Imbalance → Grid", bus0="Imbalance", bus1="Electricity_Grid", p_nom=50000, carrier="Imbalance → Grid")
    network.add("Link", "Grid → Imbalance", bus0="Electricity_Grid", bus1="Imbalance", p_nom=50000, carrier="Grid → Imbalance")
    network.add("Link", "MSR → Household", bus0="MSR", bus1="Household", p_nom=50000, marginal_cost= energy_tax, carrier="MSR → Household")
    network.add("Link", "Household → MSR", bus0="Household", bus1="MSR", p_nom=50000, marginal_cost= -energy_tax, carrier="Household → MSR")
    network.add("Link", "PV → Household", bus0="PV", bus1="Household", p_nom=50000, carrier="PV → Household")

    network.add("Link", "Household → BESS",
                bus0="Household", bus1="Battery",
                p_nom=battery_specs["charge_power_mw"],
                p_nom_extendable=False,
                efficiency=battery_specs["charge_efficiency"],
                marginal_cost=0,
                committable=True,
                carrier="charge")

    network.add("Link", "BESS → Household",
                bus0="Battery", bus1="Household",
                p_nom=battery_specs["discharge_power_mw"],
                p_nom_extendable=False,
                efficiency=battery_specs["discharge_efficiency"],
                marginal_cost=0,
                committable=True,
                carrier="discharge")

    return network

def extra_bess_link_status(
    network,
    snapshots,
    enforce_time_windows: bool | None = None,
    forbidden_windows: list[tuple[int,int]] | None = None
    #enforce_time_windows: bool = True,
    #forbidden_windows: list[tuple[int,int]] = [(12,14), (17,19)]
):
    # if not overridden on the call, fall back to attributes on network
    if enforce_time_windows is None:
        enforce_time_windows = getattr(network, "enforce_time_windows", False)
    if forbidden_windows is None:
        forbidden_windows = getattr(network, "forbidden_windows", [(12,14), (17,19)])
    """
    Adds to `network.model`:
      1) Always: status_charge + status_discharge <= 1
      2) If enforce_time_windows:
           status_charge == 0 and status_discharge == 0
           whenever snapshot.hour is in any forbidden_window.

    :param network:    a solved-or-to-be-solved pypsa.Network
    :param snapshots:  iterable of snapshot labels (e.g. network.snapshots)
    :param enforce_time_windows:  toggle on/off the forbidden-period constraint
    :param forbidden_windows:  list of (start_hour, end_hour) pairs;
                               each interval is half-open: [start_hour, end_hour)
    """
    m = network.model
    status = m.variables["Link-status"]

    for s in snapshots:
        ts = pd.to_datetime(s)
        c = status.sel({"Link-com": "Household → BESS", "snapshot": s})
        d = status.sel({"Link-com": "BESS → Household", "snapshot": s})

        # 1) Never charge+discharge at once
        m.add_constraints(
            c + d <= 1,
            name=f"bess_excl_{ts}"
        )

        # 2) Optionally block any activity in forbidden windows
        if enforce_time_windows:
            hr = ts.hour
            # if current hour falls in any [start, end) window
            for start, end in forbidden_windows:
                if start <= hr < end:
                    m.add_constraints(c == 0, name=f"bess_no_charge_{ts}")
                    m.add_constraints(d == 0, name=f"bess_no_discharge_{ts}")
                    break
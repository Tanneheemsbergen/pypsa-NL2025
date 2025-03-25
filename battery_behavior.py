from solve import solve_network

def calculate_battery_profit(network, energy_tax):
    """
    Bereken de winst (in €) van de batterij over de gehele simulatieperiode.
    
    De winst per snapshot wordt berekend als:
      opbrengst uit ontladen - kosten voor laden,
    waarbij:
      - De opbrengst = (ontladen energie in MWh) * (dag-ahead prijs in €/MWh)
      - De kosten = (laden energie in MWh) * (dag-ahead prijs + energiebelasting)
    """	
    # 15-minuten resolutie = 0.25 uur per snapshot
    delta_t = 0.25
    
    # Verkrijg de dag-ahead prijzen per snapshot uit de marginale kosten van de DAM_Generator
    # (ervan uitgaande dat deze prijzen gelijk zijn aan de marktprijzen)
    prices = network.generators_t.marginal_cost["DAM_Generator"]
    
    # Haal de batterij laad- en ontlaadvermogens op (in MW)
    # Neem aan dat laden als negatieve waarden wordt weergegeven; maak ze positief.
    charging_power = -network.links_t.p0["Household_to_BESS"].clip(upper=0)
    discharging_power = network.links_t.p0["BESS_to_Household"].clip(lower=0)
    
    # Bereken per snapshot de energie in MWh
    energy_charged = charging_power * delta_t   # Energie die in de batterij gaat laden
    energy_discharged = discharging_power * delta_t  # Energie die wordt ontladen
    
    # Bereken de winst per snapshot:
    # De opbrengst is de energie uit ontladen vermenigvuldigd met de prijs.
    # De kosten zijn de energie voor laden vermenigvuldigd met (prijs + energiebelasting)
    profit_per_snapshot = (energy_discharged * prices) - (energy_charged * (prices + energy_tax))
    
    # Tel de winst over alle snapshots op
    total_profit = profit_per_snapshot.sum()
    
    return total_profit

def print_battery_arbitrage_summary(network, dt =0.25):
    """
    Calculates and prints summary numbers for battery arbitrage.
    
    Parameters:
      network: The solved PyPSA network object.
      dt: Time step length in hours (default 0.25 for 15-minute resolution).
    
    It computes:
      - Total battery discharge (MWh): energy from the battery (via "BESS_to_Household").
      - Total battery feed-in (MWh): energy fed back to the grid (via "Household_to_SS").
      - Battery energy used by households (MWh): discharge minus feed-in.
      - (Optionally) total battery charging (MWh) from "Household_to_BESS".
    """
    # Retrieve time series from links and multiply by dt to get energy in MWh per snapshot
    discharge_series = network.links_t.p0["BESS_to_Household"] * dt
    feed_in_series = network.links_t.p0["Household_to_SS"] * dt
    charging_series = network.links_t.p0["Household_to_BESS"] * dt
    
    # Sum over all snapshots
    total_discharged = discharge_series.sum()
    total_feed_in = feed_in_series.sum()
    total_used_by_households = total_discharged - total_feed_in
    total_charged = charging_series.sum()
    
    print("Battery arbitrage summary:")
    print(f"  Total energy discharged from battery: {total_discharged:.2f} MWh")
    print(f"  Total battery feed-in to grid: {total_feed_in:.2f} MWh")
    print(f"  Battery energy used to cover household load: {total_used_by_households:.2f} MWh")
    print(f"  Total energy charged into battery: {total_charged:.2f} MWh")

def print_feed_in_events(network):
    """
    Prints timestamps when energy is fed into the grid (via "Household_to_SS")
    and shows the corresponding instantaneous power flow (in MW) and both the DAM and
    imbalance market discharge prices (in €/MWh) at that time.
    """
    # Use the snapshots from your network
    timestamps = network.snapshots
    # Retrieve the instantaneous feed-in flow (in MW)
    feed_in_series = network.links_t.p0["Household_to_SS"]
    
    # Retrieve the price signals from both markets
    dam_prices = network.generators_t.marginal_cost["DAM_Generator"]
    imbalance_prices = network.generators_t.marginal_cost["negative_IMBALANCE_Generator"]
    
    print("Feed-in events (timestamps with non-zero feed-in):")
    for t, feed in zip(timestamps, feed_in_series):
        if feed > 0:
            print(f"Time: {t}, Feed-in: {feed:.2f} MW, "
                  f"DAM discharge price: {dam_prices.loc[t]:.2f} €/MWh, "
                  f"Imbalance discharge price: {imbalance_prices.loc[t]:.2f} €/MWh")

if __name__ == "__main__":
    year = 2024  # Change to any year from 2024–2031
    ENERGY_TAX = 0.005  # Extra energiebelasting in €/MWh
    solved_network = solve_network(year)
    battery_profit = calculate_battery_profit(solved_network, ENERGY_TAX)
    print(f"Totale winst van de batterij: €{battery_profit:.2f}")
    print_battery_arbitrage_summary(solved_network)
    print_feed_in_events(solved_network)
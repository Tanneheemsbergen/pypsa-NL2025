#!/usr/bin/env python
import gc
import numpy as np
import matplotlib.pyplot as plt

# Import your existing functions.
from network import create_network
from solve_year import solve_network  # This file is assumed to define solve_network(year)

# -----------------------------------------------------------------------------
# Helper functions defined here:
# -----------------------------------------------------------------------------
def solve_network_with_cost(year, marg_cost):
    """
    Calls solve_network from solve_year.py, then overrides the marginal cost
    on the battery charge/discharge links, re-optimizes the network,
    and returns the optimized network.
    """
    net = solve_network(year)
    # Override the marginal cost for the battery links.
    net.links.loc["Household_to_BESS", "marginal_cost"] = marg_cost
    net.links.loc["BESS_to_Household", "marginal_cost"] = marg_cost
    # Re-optimize with the new marginal cost.
    net.optimize(net.snapshots, solver_name="highs")
    return net

def compute_load_cycling(network):
    """
    Computes the load cycling measure from the battery operation.
    For each time step, this function takes the minimum (absolute) power on the two links:
      "Household_to_BESS" and "BESS_to_Household"
    sums these minima over time, and divides by 4.
    (A result near zero indicates no unintended simultaneous charging/discharging.)
    """
    link_power = network.links_t.p1[["Household_to_BESS", "BESS_to_Household"]]
    cycling_measure = link_power.abs().min(axis=1).sum() / 4
    return cycling_measure

# -----------------------------------------------------------------------------
# Main search loop with visualization
# -----------------------------------------------------------------------------
def main():
    year = 2024
    tol = 1e-6  # Tolerance: we consider the load cycling measure "zero" if below this value.

    # Lists to record candidate marginal costs and their corresponding load cycling measures.
    coarse_candidates = []
    coarse_measures = []

    # Coarse search: use larger step sizes (here, 5 €/MWh) to bracket the region
    coarse_values = np.arange(0.0, 20.1, 5.0)  # Example: 0, 5, 10, 15, 20 €/MWh
    bracket_low, bracket_high = None, None
    prev_candidate, prev_measure = None, None

    print("\n--- Coarse Search ---")
    for candidate in coarse_values:
        print(f"\nTesting marginal cost = {candidate:.2f} €/MWh (coarse)")
        net = solve_network_with_cost(year, candidate)
        measure = compute_load_cycling(net)
        print(f"Load cycling measure: {measure:.6f}")
        coarse_candidates.append(candidate)
        coarse_measures.append(measure)
        # Look for the first transition: previous candidate above tolerance and current below.
        if prev_candidate is not None and prev_measure > tol and measure < tol:
            bracket_low = prev_candidate
            bracket_high = candidate
            print(f"Bracket found: ({bracket_low:.2f}, {bracket_high:.2f}) €/MWh")
            del net
            gc.collect()
            break
        prev_candidate, prev_measure = candidate, measure
        del net
        gc.collect()

    if bracket_low is None:
        print("\nNo bracket found in the coarse search. Consider expanding the search range.")
        return

    # Fine search: refine the marginal cost within the identified bracket using 0.1 €/MWh steps.
    fine_candidates = []
    fine_measures = []
    best_cost = None

    print("\n--- Fine Search ---")
    fine_values = np.arange(bracket_low, bracket_high + 0.1, 0.1)
    for cost in fine_values:
        print(f"\nTesting marginal cost = {cost:.2f} €/MWh (fine)")
        net = solve_network_with_cost(year, cost)
        measure = compute_load_cycling(net)
        print(f"Load cycling measure: {measure:.6f}")
        fine_candidates.append(cost)
        fine_measures.append(measure)
        if measure < tol:
            best_cost = cost
            print(f"Found optimal marginal cost: {cost:.2f} €/MWh yielding near-zero load cycling!")
            del net
            gc.collect()
            break
        del net
        gc.collect()

    if best_cost is not None:
        print("\nLowest marginal cost value for zero load cycling:", best_cost)
    else:
        print("\nNo optimal marginal cost value found in the refined range that yields zero load cycling.")

    # -----------------------------------------------------------------------------
    # Visualization
    # -----------------------------------------------------------------------------
    plt.figure(figsize=(10, 5))
    # Plot coarse search results.
    plt.plot(coarse_candidates, coarse_measures, 'o--', label='Coarse search', color='blue')
    # Plot fine search results.
    plt.plot(fine_candidates, fine_measures, 's-', label='Fine search', color='red')
    plt.xlabel("Marginal cost (€/MWh)")
    plt.ylabel("Load cycling measure")
    plt.title("Load Cycling Measure vs. Marginal Cost")
    plt.axhline(y=tol, color='black', linestyle='--', label=f"Tolerance ({tol})")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()

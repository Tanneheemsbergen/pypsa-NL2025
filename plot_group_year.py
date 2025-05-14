import os
import pandas as pd
from scenarios.load_scenarios import load_scenarios2
from utils.congestion_year import plot_group_year_summary, plot_group_year_events_heatmaps

if __name__ == "__main__":
    # 1) Same parameters you used for yearly solves
    year = 2024
    scenario_group = "Trade DAM + Imbalance + Time Constraints"  # pas aan naar jouw groepsnaam

    # 2) Find your sub-scenarios (they all already have their CSVs on disk)
    scenarios = load_scenarios2("scenarios/2solve_scenarios.yaml")
    group_members = [s for s in scenarios if s.get("group") == scenario_group]
    if not group_members:
        raise RuntimeError(f"No group named '{scenario_group}' found")

    # 3) Simply plot from the saved CSVs—no solve_network call at all
    plot_group_year_summary(year, scenario_group, group_members)
    plot_group_year_events_heatmaps(year, scenario_group, group_members)
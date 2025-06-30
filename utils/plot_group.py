import os
from scenarios.load_scenarios import load_scenarios2
from utils.congestion_week import plot_group_week_summary, plot_group_week_events_heatmaps
if __name__ == "__main__":
    # 1) Same parameters you used when you ran the solve
    year = 2024
    week = 4
    scenario_group = "trade_DAM_imbalance"

    # 2) Find your sub-scenarios (they all already have their CSVs on disk)
    scenarios = load_scenarios2("scenarios/2solve_scenarios.yaml")
    group_members = [s for s in scenarios if s.get("group") == scenario_group]
    if not group_members:
        raise RuntimeError(f"No group named '{scenario_group}' found")

    # 3) Simply plot from the saved CSVs—no solve_network call at all
    plot_group_week_summary(year, week, scenario_group, group_members)
    plot_group_week_events_heatmaps(year, week, scenario_group, group_members)
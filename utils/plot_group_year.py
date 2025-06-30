import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scenarios.load_scenarios import load_scenarios3
from utils.set_plot_style import set_plot_style
from sensitivity_year import run_sensitivity_year
from utils.congestion_backup import plot_group_year_summary, plot_group_year_events_heatmaps, congestion_summary_year

set_plot_style()
PLOT_BASE = 'plots/congestion_year'
CSV_BASE  = 'results/congestion_year'

def plot_sensitivity_year(year: int, scenarios: list, group_name: str):
        # 1) load the precomputed CSV
    csv_path = os.path.join(CSV_BASE, str(year), group_name, f'{year}_sensitivity.csv')
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Sensitivity CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)

    # 2) X and Y in raw quarter-period ticks
    x = df['new_q'] + df['charge_q']
    y = df['mit_q']

    # 3) compute Matplotlib‐style area sizes (100→1000)
    obj  = df['objective']
    norm = (obj - obj.min()) / (obj.max() - obj.min())
    areas = norm * (1000 - 100) + 100

    # 4) choose color dimension
    if 'pv_cap' in df and df['pv_cap'].notnull().all():
        color_vals, cmap, clabel = df['pv_cap'], 'Viridis', 'PV capacity ×'
    else:
        color_vals, cmap, clabel = df['power_mult'], 'Plasma', 'Power ×'

    # 5) sizemode=area with sizeref to convert area→pixels
    #    sizeref formula: 2*max_area/(desired_max_diam**2)
    desired_max_diam = 40  # px
    sizeref = 2 * areas.max() / (desired_max_diam**2)

    # 6) build the Plotly figure
    fig = go.Figure(
        go.Scatter(
            x=x, y=y,
            mode='markers',
            marker=dict(
                size=areas,
                sizemode='area',
                sizeref=sizeref,
                color=color_vals,
                colorscale=cmap,
                showscale=True,
                colorbar=dict(
                    title=clabel,
                    len=0.75,
                    thickness=20,
                    yanchor='middle',
                    y=0.5,
                    outlinewidth=0
                ),
                line=dict(color='black', width=1)
            )
        )
    )

    # 7) square layout + axes + title
    fig.update_layout(
        width=700,
        height=700,
        title=dict(
            text=f'{group_name}',
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(title='New congestion + Charging During Congested Periods'),
        yaxis=dict(title='Mitigation'),
        margin=dict(l=60, r=100, t=80, b=60)
    )

    # 8) save & show
    out_svg = os.path.join(PLOT_BASE, str(year), group_name, f'{year}_sensitivity.svg')
    os.makedirs(os.path.dirname(out_svg), exist_ok=True)
    fig.write_image(out_svg)
    print(f"Sensitivity bubble chart saved to: {out_svg}")
    #fig.show()
if __name__ == "__main__":
    # 1) Same parameters you used for yearly solves
    year = 2024
    scenario_group = "Value Stacking DAM + Imbalance"  # pas aan naar jouw groepsnaam

    # 2) Find your sub-scenarios (they all already have their CSVs on disk)
    scenarios = load_scenarios3("scenarios/3solve_scenarios.yaml")
    group_members = [s for s in scenarios if s.get("group") == scenario_group]
    if not group_members:
        raise RuntimeError(f"No group named '{scenario_group}' found")

    # 3) Simply plot from the saved CSVs—no solve_network call at all
    plot_group_year_summary(year, scenario_group, group_members)
    #plot_group_year_events_heatmaps(year, scenario_group, group_members)
    #plot_sensitivity_year(year, group_members, scenario_group)

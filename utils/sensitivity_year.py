#!/usr/bin/env python3
"""
sensitivity_year.py
Run a full-year sensitivity sweep using your detailed
congestion_summary_year() logic and produce a bubble plot.
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go

from solve2_year import solve_network
from scenarios.load_scenarios import load_scenarios2
from utils.congestion_year import congestion_summary_year

PLOT_BASE = 'plots/congestion_year'
CSV_BASE  = 'results/congestion_year'


def read_event_counts(year: int, scenario_name: str) -> dict:
    """
    Read the raw quarter-period event counts from
      results/congestion_year/<year>/<scenario_name>/event_summary_counts.csv
    """
    path = os.path.join(CSV_BASE, str(year), scenario_name, 'event_summary_counts.csv')
    df = pd.read_csv(path)
    return dict(zip(df['event'], df['count']))

def run_sensitivity_year(year: int, scenarios: list, group_name: str):
    """
    Generate (if needed) + plot the <year>_sensitivity.csv
    for the given list of scenarios (by name) under group_name.
    """
    # ensure the CSV exists
    csv_dir  = os.path.join(CSV_BASE, str(year), group_name)
    csv_path = os.path.join(csv_dir, f'{year}_sensitivity.csv')
    if not os.path.exists(csv_path):
        os.makedirs(csv_dir, exist_ok=True)
        results = []
        for scen in scenarios:
            name = scen['name']
            # solve DAM & Imbalance
            dam_net, imb_net = solve_network(year, scen, scen['energy_tax'])
            # produce event CSVs
            congestion_summary_year(dam_net, year, f"{group_name}/{name}_DAM")
            congestion_summary_year(imb_net, year, f"{group_name}/{name}_Imbalance")
            # read back raw counts
            d_counts = read_event_counts(year, f"{group_name}/{name}_DAM")
            i_counts = read_event_counts(year, f"{group_name}/{name}_Imbalance")
            is_imbalance = name.endswith("_Imbalance")
            if is_imbalance:
                new_q    = d=i_counts.get("new_congestion", 0)
                charge_q = i_counts.get("charging_during_congested", 0)
                mit_q    = i_counts.get("mitigation", 0)
                objective = dam_net.objective + imb_net.objective
            else:
                new_q    = d_counts.get("new_congestion", 0)
                charge_q = d_counts.get("charging_during_congested", 0)
                mit_q    = d_counts.get("mitigation", 0)
                objective = dam_net.objective + imb_net.objective
            results.append({
                'scenario':   name,
                'new_q':      new_q,
                'charge_q':   charge_q,
                'mit_q':      mit_q,
                'objective':  objective,
                'power_mult': scen.get('power_mult'),
                'pv_cap':     scen.get('pv_cap'),
            })
        pd.DataFrame(results).to_csv(csv_path, index=False)
        print(f"Generated sensitivity CSV: {csv_path}")

    # load & filter to exactly these scenarios
    df = pd.read_csv(csv_path)
    names = [s['name'] for s in scenarios]
    df = df[df['scenario'].isin(names)]
    if df.empty:
        raise RuntimeError(f"No matching scenarios {names} in {csv_path}")

    # build the bubble chart
    x = df['new_q'] + df['charge_q']
    y = df['mit_q']

    # Matplotlib-style area sizing [100→1000]
    obj  = df['objective']
    norm = (obj - obj.min()) / (obj.max() - obj.min())
    areas = norm * (1000 - 100) + 100

    # choose color dimension
    if 'pv_cap' in df and df['pv_cap'].notnull().all():
        color_vals, cmap, clabel = df['pv_cap'], 'Viridis', 'PV capacity ×'
    else:
        color_vals, cmap, clabel = df['power_mult'], 'Plasma', 'Power ×'

    # convert areas→pixels via sizeref for Plotly area mode
    desired_max_diam = 40
    sizeref = 2 * areas.max() / (desired_max_diam**2)

    fig = go.Figure(
        go.Scatter(
            x=x, y=y, mode='markers',
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

    fig.update_layout(
        width=700,
        height=700,
        title=dict(text=f'Sensitivity Analysis — Year {year} — {group_name}',
                   x=0.5, xanchor='center'),
        xaxis=dict(title='New cong. + Charging (quarter-ticks)'),
        yaxis=dict(title='Mitigation (quarter-ticks)'),
        margin=dict(l=60, r=100, t=80, b=60)
    )

    out_png = os.path.join(PLOT_BASE, str(year), group_name, f'{year}_sensitivity.svg')
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.write_image(out_png)
    print(f"Sensitivity bubble chart saved to: {out_png}")
    #fig.show()


if __name__ == "__main__":
    # 0) Pick your year and target right here:
    year = 2024
    # Either "ALL", or one of your group names, or a single scenario name
    scenario_to_run = "Value Stacking DAM + Imbalance + PV + Battery Sensitivity"

    # 1) Load ALL scenarios (flat + groups)
    scenarios = load_scenarios2("scenarios/2solve_scenarios.yaml")

    # 2) Build run_list
    if scenario_to_run.upper() == "ALL":
        # unique non-empty groups from the YAML
        run_list = sorted({s["group"] for s in scenarios if s.get("group")})
    else:
        run_list = [scenario_to_run]

    # 3) Loop over each group/scenario key
    for run_key in run_list:
        print(f"\n=== Running: {run_key} ===")
        # find members in this group
        group_members = [s for s in scenarios if s.get("group") == run_key]

        if group_members:
            # --- GROUP RUN ---
            run_sensitivity_year(year, group_members, run_key)
        else:
            # --- SINGLE SCENARIO RUN ---
            scen = next((s for s in scenarios if s["name"] == run_key), None)
            if not scen:
                raise RuntimeError(f"No group or scenario named '{run_key}'")
            run_sensitivity_year(year, [scen], scen["group"])
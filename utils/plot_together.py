import os
import pandas as pd
import plotly.graph_objects as go

from scenarios.load_scenarios import load_scenarios3
from utils.utils import colors_crest, colors_flare

def plot_group_year_summary(year, output_group, sub_scenarios):
    """
    Aggregates counts across DAM+Imbalance for each sub-scenario,
    reading from each sub’s own results folder.
    Writes bar charts into plots/congestion_year/{year}/{output_group}/
    and returns a dict of the figure objects.

    Bars are colored by scenario group, with 'new' using crest palette
    and 'mitigation' using flare palette (base + slight variants).
    The legend below shows only the three groups.
    """
    # 1) Identify unique scenario groups
    scenario_groups = []
    for sub in sub_scenarios:
        grp = sub.get("group")
        if grp not in scenario_groups:
            scenario_groups.append(grp)

    # 2) Color palettes per event type
    new_palette = colors_crest(len(scenario_groups))        # distinct new colors per group
    mit_palette = colors_flare(len(scenario_groups))        # distinct mitigate colors per group
    # 2.a) after new_palette and mit_palette
    group_colors = dict(zip(scenario_groups, new_palette))
    # 3) Gather counts per sub-scenario
    metrics = []
    for sub in sub_scenarios:
        name = sub["name"]
        grp = sub.get("group")
        totals = {"mitigation": 0, "chg_already": 0, "new": 0, "neutral": 0}
        for tag in ("DAM", "Imbalance"):
            base = os.path.join(
                "results", "congestion_year", str(year), grp,
                f"{name}_{tag}"
            )
            ev_csv = os.path.join(base, "congestion_event_times_year.csv")
            if os.path.exists(ev_csv):
                df_ev = pd.read_csv(ev_csv)
                for ev in ("mitigation", "chg_already", "new"):
                    totals[ev] += df_ev.query("event == @ev")["count"].sum()
            neut_csv = os.path.join(base, "neutral_charging_times_year.csv")
            if os.path.exists(neut_csv):
                totals["neutral"] += pd.read_csv(neut_csv)["count"].sum()
        metrics.append({"scenario": name, "group": grp, **totals})

    # 4) Build DataFrame & X-axis labels
    df = pd.DataFrame(metrics).set_index("scenario")
    labels = []
    for scen in df.index:
        parts = scen.split("_")
        if len(parts) >= 2 and parts[-2].isdigit() and parts[-1].isdigit():
            labels.append(f"{parts[-2]}/{parts[-1]}")
        else:
            labels.append(scen.replace("_", "/"))
    if labels:
        labels[0]   = labels[0] + " DAM"
        labels[10]  = labels[10] + " IMB"
    # 5) Plot per event
    figs = {}
    for ev, title in [
        ("mitigation",    "Mitigation Events"),
        ("chg_already",   "Charging During Congested Periods"),
        ("new",           "New Congestion Events"),
        ("neutral",       "Neutral Charging Events"),
    ]:
        # select palette
        palette = mit_palette if ev == "mitigation" else new_palette
        # pick the right palette for this event
        palette = mit_palette if ev == "mitigation" else new_palette
        # map each group name to its color for *this* event
        ev_colors = dict(zip(scenario_groups, palette))
        # create grouped bar chart: one trace per group
        fig = go.Figure()

        for grp in scenario_groups:
            mask = df["group"] == grp
            fig.add_trace(go.Bar(
                x=df.index[mask],
                y=df.loc[mask, ev],
                name=grp,
                marker_color=ev_colors[grp],
            ))

        fig.update_layout(barmode='group')
        fig.update_layout(
            title=f"{title} by Scenario Group - {year}",
            xaxis=dict(
                tickmode="array",
                tickvals=df.index.tolist(),
                ticktext=labels,
                tickangle=45
            ),
            yaxis_title="Count",
            legend=dict(orientation="h", y=-0.20, x=0, xanchor="left"),
            barmode='group',
            height=500,
            margin=dict(t=60, b=60, l=80, r=50)
        )
        # save
        out_dir = os.path.join("plots", "congestion_year", str(year), output_group)
        os.makedirs(out_dir, exist_ok=True)
        fig.write_image(os.path.join(out_dir, f"{ev}_year.svg"))
        figs[ev] = fig
    
    
    return figs


if __name__ == "__main__":
    year = 2024
    scenario_groups = [
        "Trade DAM + Imbalance",
        "Trade DAM + Imbalance + Time Constraints",
        "Trade DAM + Imbalance + ToU Tariffs"
    ]
    scenarios = load_scenarios3("scenarios/3solve_scenarios.yaml")
    # 1) Get your default crest palette
    palette = colors_crest(len(scenario_groups))
    # 2) Force the “Time Constraints” group (index 1) to red
    #palette[2] = colors_crest(1)[0] 
    palette[1] = colors_flare(1)[0] 
    # 3) Build the mapping
    group_colors = dict(zip(scenario_groups, palette))
    
    all_subs = []
    for grp in scenario_groups:
        members = [s for s in scenarios if s.get("group") == grp]
        if not members:
            raise RuntimeError(f"No group named '{grp}' found in YAML")
        all_subs.extend(members)

    combined_name = "together"
    out_dir = os.path.join("plots", "congestion_year", str(year), combined_name)
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n--- Plotting combined year summary '{combined_name}' for groups {scenario_groups} ---")
    # Bar charts
    figs = plot_group_year_summary(year, combined_name, all_subs)
    print(f"\nDone! Combined charts under: plots/congestion_year/{year}/{combined_name}/")

    # ─────────────── PLOTLY OVERLAY CHARGING & DISCHARGING ───────────────
    # mapping for result folders
    group_folders = {
        "Trade DAM + Imbalance": scenario_groups[0],
        "Trade DAM + Imbalance + Time Constraints": scenario_groups[1],
        "Trade DAM + Imbalance + ToU Tariffs": scenario_groups[2],
    }
    scenario_map = {
        "Trade DAM + Imbalance": [("Trade_100_0", "DAM")],
        # "Value Stacking DAM + Imbalance + PV + Time Constraints": [("Trade_100_0", "DAM")],
        # "Value Stacking DAM + Imbalance + PV + ToU Tariffs": [("Trade_100_0", "DAM")],
        "Trade DAM + Imbalance + Time Constraints": [("Trade_100_0", "DAM")],
        "Trade DAM + Imbalance + ToU Tariffs": [("Trade_100_0", "DAM")],
    }
    
    # load and aggregate charging/discharging
    dfs = {}
    for grp_label, entries in scenario_map.items():
        tmp = []
        for base, tag in entries:
            path = os.path.join(
                "results", "congestion_year", str(year),
                grp_label, f"{base}_{tag}",
                "agg_charge_discharge_by_time_of_day.csv"
            )
            df_csv = pd.read_csv(path).set_index("time")
            tmp.append(df_csv)
        dfs[grp_label] = pd.concat(tmp).groupby(level=0).sum().sort_index()
    times = dfs[next(iter(dfs))].index.tolist()

    fig_cd = go.Figure()
    for grp_label, dfcd in dfs.items():
        color = group_colors[grp_label]

        # charging (solid, positive)
        fig_cd.add_trace(go.Scatter(
            x=times,
            y=dfcd["total_charging_mw"],
            mode="lines",
            name=grp_label,
            line=dict(color=color, dash="solid", width=2),
            showlegend=True
        ))
        # discharging (dashed, negative), hide legend
        fig_cd.add_trace(go.Scatter(
            x=times,
            y=-dfcd["total_discharging_mw"],
            mode="lines",
            name=grp_label,
            line=dict(color=color, dash="dash", width=2),
            showlegend=False
        ))

    fig_cd.update_layout(
        title=f"Charging ↑ & Discharging ↓ by Scenario Group — {year}",
        xaxis_title="Time of Day",
        yaxis_title="Power (MW)",
        legend=dict(title="Scenario Group", orientation="h", y=-0.3, x=0, xanchor="left"),
        margin=dict(t=80, b=150, l=80, r=50),
        height=500
    )

    fig_cd.write_image(os.path.join(out_dir, "charge_discharge_overlay.svg"))
    figs["charge_discharge"] = fig_cd
    # ──────── end merged charging/discharging overlay ─────────
    # ─── PLOTLY OVERLAY flow_to_house + Demand ─────────
    dfs_flow = {}
    for grp_label, entries in scenario_map.items():
        tmp = []
        for base, tag in entries:
            # if tag != "DAM":
            #     continue
            path = os.path.join(
                "results", "congestion_year", str(year),
                grp_label, f"{base}_{tag}",
                "congestion_baseline.csv"
            )
            df_csv = pd.read_csv(path, parse_dates=["datetime"])
            df_csv["time"] = df_csv["datetime"].dt.strftime("%H:%M")
            # aggregate to one value per time‐of‐day
            col = "flow_to_house" if tag == "DAM" else "flow_to_house_imb"
            series = df_csv.groupby("time")[col].sum().sort_index()
            tmp.append(series)
        dfs_flow[grp_label] = pd.concat(tmp).groupby(level=0).sum().sort_index()

    # build common x-axis
    times_flow = sorted({t for s in dfs_flow.values() for t in s.index})

    fig_flow = go.Figure()
    for grp_label, series in dfs_flow.items():
        fig_flow.add_trace(go.Scatter(
            x=times_flow,
            y=series.reindex(times_flow).fillna(0),
            mode="lines",
            name=grp_label,
            line=dict(color=group_colors[grp_label], width=2)
        ))

    # now add demand (once)
    # reuse the same DAM baseline CSV from the first group
    # pick the first scenario entry, preferring DAM if present
    entries = scenario_map[next(iter(scenario_map))]
    dam_entry = next(((b,t) for b,t in entries if t=="DAM"), None)
    if dam_entry:
        base, tag = dam_entry
    else:
        base, tag = entries[0]

    path = os.path.join(
        "results", "congestion_year", str(year),
        next(iter(scenario_map)), f"{base}_{tag}",
        "congestion_baseline.csv"
    )
    df_base = pd.read_csv(path, parse_dates=["datetime"])
    df_base["time"] = df_base["datetime"].dt.strftime("%H:%M")
    demand = df_base.groupby("time")["load_mw"].sum().sort_index()
    all_times = sorted(set(times_flow) | set(demand.index))

    fig_flow.add_trace(go.Scatter(
        x=all_times,
        y=demand.reindex(all_times).fillna(0),
        mode="lines",
        name="Demand",
        line=dict(color="black", dash="dash")
    ))

    fig_flow.update_layout(
        title=f"Flow to Household & Demand — {year}",
        xaxis_title="Time of Day",
        yaxis_title="MW",
        legend=dict(orientation="h", y=-0.3, x=0, xanchor="left"),
        margin=dict(t=80, b=200, l=80, r=50),
        height=500
    )
    fig_flow.write_image(os.path.join(out_dir, "flow_to_house_overlay.svg"))
    figs["flow_to_house"] = fig_flow

        # ─── PLOTLY OVERLAY flow_to_house + Demand (two windows) ─────────
    import pandas as pd

    # 1) Load and aggregate full-year flow_to_house series for each group
    dfs_flow = {}
    for grp_label, entries in scenario_map.items():
        tmp = []
        for base, tag in entries:
            path = os.path.join(
                "results", "congestion_year", str(year),
                grp_label, f"{base}_{tag}",
                "congestion_baseline.csv"
            )
            df_csv = pd.read_csv(path, parse_dates=["datetime"])
            df_csv["time"] = df_csv["datetime"].dt.strftime("%H:%M")
            col = "flow_to_house" if tag == "DAM" else "flow_to_house_imb"
            series = df_csv.set_index("datetime")[col]
            tmp.append(series)
        # merge (sum if multiple)
        dfs_flow[grp_label] = pd.concat(tmp).groupby(level=0).sum().sort_index()

    # 2) Load full-year demand series
    # pick first entry (preferring DAM if available)
    entries = scenario_map[next(iter(scenario_map))]
    dam_entry = next(((b,t) for b,t in entries if t=="DAM"), entries[0])
    base, tag = dam_entry
    path = os.path.join(
        "results", "congestion_year", str(year),
        next(iter(scenario_map)), f"{base}_{tag}",
        "congestion_baseline.csv"
    )
    df_base = pd.read_csv(path, parse_dates=["datetime"])
    demand = df_base.set_index("datetime")["load_mw"].sort_index()

    # 3) Build a master datetime index
    # build a master index by iteratively unioning
    all_idx = demand.index
    for series in dfs_flow.values():
        all_idx = all_idx.union(series.index)
    all_idx = all_idx.sort_values()

    # 4) Define your two windows:
    #    - ISO week 4 (Jan 22–28 2024)
    #    - First week of August (Aug 1–7)
    iso = all_idx.to_series().dt.isocalendar().week
    mth = all_idx.month
    day = all_idx.day

    # windows = [
    #     ("week4",   iso == 4,                 "ISO Week 4 (Jan 22–28)"),
    #     ("aug1st",  (mth == 8) & (day <= 7),  "First Week of August")
    # ]

      # 4) Define your two specific days (full‐day windows):
    #    e.g. Jan 15, 2024 and Aug  1, 2024
    # 4) Define your two specific days (full 24h windows):
    day1 = pd.Timestamp("2030-01-25")
    day2 = pd.Timestamp("2030-08-01")

    mask_day1 = (all_idx >= day1) & (all_idx <  day1 + pd.Timedelta(days=1))
    mask_day2 = (all_idx >= day2) & (all_idx <  day2 + pd.Timedelta(days=1))

    windows = [
        ("jan15", mask_day1, "January 25, 2030"),
        ("aug01", mask_day2, "August 1, 2030")
]
    # 5) Plot each window
    for tag, mask, title in windows:
        fig_win = go.Figure()
        # flow_to_house traces
        for grp_label, series in dfs_flow.items():
            s = series.reindex(all_idx).fillna(0)[mask]
            fig_win.add_trace(go.Scatter(
                x=s.index, y=s.values,
                mode="lines", name=grp_label
            ))
        # demand trace
        d = demand.reindex(all_idx).fillna(0)[mask]
        fig_win.add_trace(go.Scatter(
            x=d.index, y=d.values,
            mode="lines", name="Demand",
            line=dict(color="black", dash="dash")
        ))

        fig_win.update_layout(
            title=f"Flow to Household & Demand — {title} ({year})",
            xaxis_title="Date",
            yaxis_title="MW",
            legend=dict(orientation="h", y=-0.3, x=0, xanchor="left"),
            margin=dict(t=80, b=150, l=80, r=50),
            height=400
        )

        out_file = os.path.join(out_dir, f"flow_to_house_{tag}.svg")
        fig_win.write_image(out_file)
        figs[f"flow_to_house_{tag}"] = fig_win
    # ─── end two-window flow_to_house + Demand ────────
   # ─────────────── PLOTLY OVERLAID OBJECTIVE SUM ───────────────
    # 1) Collect sums per (group, ratio)
    data = {}
    ratios = []
    for grp_label in scenario_groups:
        # find all scenarios in that group
        members = [s["name"] for s in scenarios if s["group"] == grp_label]
        sums = {}
        for name in members:
            csv_p = os.path.join(
                "results", "congestion_year", str(year),
                grp_label, name, "objective_function.csv"
            )
            df_obj = pd.read_csv(csv_p)
            total = df_obj["objective_DAM"].sum() + df_obj["objective_Imbalance"].sum()
            # parse ratio from name (Trade_X_Y → "X/Y")
            parts = name.split("_")
            ratio = f"{parts[-2]}/{parts[-1]}" if parts[-2].isdigit() else name
            sums[ratio] = total
            if ratio not in ratios:
                ratios.append(ratio)
        data[grp_label] = sums

    # 2) Build wide‐format DataFrame
    ratios = sorted(ratios, key=lambda x: float(x.split("/")[0]), reverse=True)
    df_obj = pd.DataFrame({
        grp: [data[grp].get(r, 0) for r in ratios]
        for grp in scenario_groups
    }, index=ratios)

    # 3) Colors for each group
    overlay_palette = colors_crest(len(scenario_groups))
# if you still want the 2nd group to be red
    overlay_palette[1] = colors_flare(1)[0]
    # map each group label to its overlay colour
    net_colors = dict(zip(scenario_groups, overlay_palette))
    fig = go.Figure()
    for idx, grp_label in enumerate(scenario_groups):
        fig.add_trace(go.Scatter(
            x=ratios,
            y=df_obj[grp_label],
            mode="lines+markers",
            name=grp_label,
            line=dict(color=net_colors[grp_label], width=3),
            marker=dict(size=8)
        ))

    fig.update_layout(
        title=f"Objective Sum by Ratio & Group — {year}",
        xaxis_title="Trade Ratio (X/Y)",
        yaxis_title="Objective DAM + Imbalance (€)",
        legend=dict(orientation="h", y=-0.2, x=0, xanchor="left"),
        margin=dict(t=80, b=150, l=80, r=50),
        height=500
    )
    fig.write_image(os.path.join(out_dir, "objective_sum_lines.svg"))   

    max_records = []
    for grp_label, entries in scenario_map.items():
        for base, tag in entries:
            csv_path = os.path.join(
                "results", "congestion_year", str(year),
                grp_label, f"{base}_{tag}",
                "congestion_baseline.csv"
            )
            df = pd.read_csv(csv_path, parse_dates=["datetime"])
            # always pull the peak load
            peak_load = df["load_mw"].max()
            # choose the right flow column
            flow_col = "flow_to_house" if tag == "DAM" else "flow_to_house_imb"
            peak_total=(df["load_mw"]+df[flow_col]).max()
            peak_flow = df[flow_col].max()
            max_records.append({
                "group":        grp_label,
                "scenario":     base,
                "tag":          tag,
                "peak_load_mw": peak_load,
                #"peak_flow_mw": peak_flow,
                "peak_total_mw": peak_total,
            })

    # assemble into a DataFrame for easy viewing
    df_peaks = pd.DataFrame(max_records)
    print(df_peaks)

# ─── PLOTLY OVERLAY: Demand ± Battery for a Specific Week ─────────
# ─── 1) LOAD FULL‐YEAR SERIES PER GROUP ─────────────────
demand  = {}
chg     = {}
dsch    = {}
week_num = 4

for grp_label, entries in scenario_map.items():
    for base, tag in entries:
        #base, tag = next((b,t) for b,t in entries if t == "DAM")
        folder = os.path.join(
            "results", "congestion_year", str(year),
            grp_label, f"{base}_{tag}"
        )

        # demand baseline
        df_base = pd.read_csv(
            os.path.join(folder, "congestion_baseline.csv"),
            parse_dates=["datetime"]
        ).set_index("datetime").sort_index()
        demand[grp_label] = df_base["load_mw"]

        # ts_charge_discharge
        df_ts = pd.read_csv(
            os.path.join(folder, "ts_charge_discharge.csv"),
            parse_dates=["datetime"]
        ).set_index("datetime").sort_index()
        chg[grp_label]  = df_ts["charging_mw"]
        dsch[grp_label] = df_ts["discharging_mw"]

# ─── 2) BUILD WEEK MASK ────────────────────────────────
# union all timestamps to a master index
all_idx = demand[next(iter(demand))].index
for s in chg.values():
    all_idx = all_idx.union(s.index)
all_idx = all_idx.sort_values()

# define your day of interest (YYYY–MM–DD)
day_date = pd.Timestamp("2024-01-25")

# normalize your full‐year index once:
all_norm = all_idx.normalize()

# boolean mask: True wherever date == day_date
mask_day = (all_norm == day_date)
# pick ISO‐week and mask
# iso = all_idx.to_series().dt.isocalendar().week
# mask_week = (iso == week_num)

# ─── 3) SLICE INTO THE WEEK ────────────────────────────
# 3′) SLICE INTO THE DAY
d_day  = {g: demand[g][mask_day] for g in scenario_groups}
c_day  = {g: chg   [g][mask_day] for g in scenario_groups}
ds_day = {g: dsch  [g][mask_day] for g in scenario_groups}

# ─── 4) PLOT ───────────────────────────────────────────
# pick Crest colors for each group’s net‐import line
overlay_palette = colors_crest(len(scenario_groups))
# if you still want the 2nd group to be red
overlay_palette[1] = colors_flare(1)[0]
# map each group label to its overlay colour
net_colors = dict(zip(scenario_groups, overlay_palette))
fig = go.Figure()

# 4a) Demand (only once, use first group)
first = scenario_groups[0]
fig.add_trace(go.Scatter(
    x=d_day[first].index, y=d_day[first].values,
    mode="lines", name="Demand",
    line=dict(color="black",dash="dash", width=2)
))

# Net import per group
for grp in scenario_groups:
    color = group_colors[grp]
    net = d_day[grp] + c_day[grp] - ds_day[grp]
    fig.add_trace(go.Scatter(
        x=net.index, y=net.values,
        mode="lines", name=f"{grp}",
        line=dict(color=net_colors[grp], width=2)
    ))

fig.update_layout(
    title=f"Demand vs. Net Grid Import",
    xaxis_title="Time of Day",
    yaxis_title="MW",
    legend=dict(orientation="h", y=-0.3, x=0, xanchor="left"),
    margin=dict(t=80, b=150, l=80, r=50),
    height=450
)

# ─── 5) SAVE ───────────────────────────────────────────
out_file = os.path.join(out_dir, f"demand_vs_net_import_{day_date.date()}.svg")
fig.write_image(out_file)
print(f"Wrote: {out_file}")

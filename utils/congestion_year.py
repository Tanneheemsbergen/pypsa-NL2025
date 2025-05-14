import os
import pandas as pd
import numpy as np
import calendar
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.set_plot_style import set_plot_style
from utils.utils import colors_crest, colors_flare
from core.config_loader import load_config
from core.load_year import get_year_range

# Apply global Plotly style
set_plot_style()

# Directories
PLOT_BASE = 'plots/congestion_year'
CSV_BASE  = 'results/congestion_year'
RESULTS_DIR = 'results'


def get_storage_charging(network, store=None):
    """
    Returns a pandas Series of battery charging load (MW).
    Charging corresponds to negative p, so clip above zero and take absolute.
    """
    store_power = network.stores_t.p
    if store is None:
        if store_power.shape[1] == 1:
            store = store_power.columns[0]
        else:
            raise ValueError(f"Multiple stores: {list(store_power.columns)}; specify one.")
    p = store_power[store]
    return p.clip(upper=0).abs()

def get_storage_discharging(network, store=None):
    """
    Returns a pandas Series of battery discharging load (MW).
    Discharging corresponds to positive p, so clip below zero.
    """
    store_power = network.stores_t.p
    if store is None:
        if store_power.shape[1] == 1:
            store = store_power.columns[0]
        else:
            raise ValueError(f"Multiple stores: {list(store_power.columns)}; specify one.")
    p = store_power[store]
    return p.clip(lower=0)

def load_yearly_load(year):
    """
    Reads the yearly load CSV from config and returns a Series of 'load_mw' indexed by datetime.
    """
    config = load_config()
    load_file = config['paths']['load']
    df = pd.read_csv(load_file, parse_dates=['datetime'])
    start, end = get_year_range(year)
    df = df[(df['datetime'] >= start) & (df['datetime'] < end)].copy()
    df.set_index('datetime', inplace=True)
    df.rename(columns={'belasting': 'load_mw'}, inplace=True)
    return df['load_mw']


def detect_new_congestion_year(network, load_series, capacity_limit):
    charging = get_storage_charging(network)
    df = pd.DataFrame({'load_mw': load_series}).join(
        charging.rename('charging_mw'), how='inner'
    ).fillna(0)
    df['combined_mw'] = df['load_mw'] + df['charging_mw']
    return df[(df['load_mw'] < capacity_limit) & (df['combined_mw'] > capacity_limit)]


def detect_already_congested_year(load_series, capacity_limit):
    df = load_series.to_frame(name='load_mw')
    return df[df['load_mw'] > capacity_limit]

# --- new helper functions at top of congestion_year.py ---

def plot_congestion_time_of_day_year(df_new, df_al, df_mitigate):
    """
    Bar chart of congestion counts at each specific time (HH:MM):
      - New Congestion
      - Already Congested
    """
    def tc(df):
        return pd.Series(df.index.time).value_counts().sort_index()

    new_tc = tc(df_new)
    al_tc  = tc(df_al)
    mit_tc = tc(df_mitigate)

    times  = sorted(set(new_tc.index) | set(al_tc.index))
    labels = [t.strftime('%H:%M') for t in times]

    colors = {
        'already' : colors_flare(1)[0],
        'new'     : colors_crest(1)[0],
        'mitigate': colors_flare(3)[2]
    }

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=[al_tc.get(t,0)  for t in times],
        name='Already congested',
        marker_color=colors['already']
    ))
    fig.add_trace(go.Bar(
        x=labels, y=[new_tc.get(t, 0) for t in times],
        name='New congestion',
        marker_color=colors['new']
    ))
    fig.add_trace(go.Bar(
        x=labels, y=[-mit_tc.get(t,0) for t in times],
        name='Mitigation',
        marker_color=colors['mitigate']
    ))
    fig.update_layout(
        barmode='relative',
        title='Exact-Time Congestion & Mitigation',
        xaxis=dict(title='Time (HH:MM)', tickangle=45),
        yaxis=dict(title='Count (negative = mitigation)'),
        height=500
    )
    return fig

def plot_charging_time_of_day_year(df_charge_al, df_charge_neut):
    """
    Bar chart of charging counts at each specific time (HH:MM):
      - Charging during already congested times
      - Neutral charging times
    """
    def tc(df):
        return pd.Series(df.index.time).value_counts().sort_index()

    cal_tc  = tc(df_charge_al)
    neut_tc = tc(df_charge_neut)

    times  = sorted(set(cal_tc.index) | set(neut_tc.index))
    labels = [t.strftime('%H:%M') for t in times]

    # second color from each palette
    col_charge_al = colors_crest(2)[1]
    col_neutral   = colors_flare(2)[1]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=[cal_tc.get(t, 0) for t in times],
        name='Charging During Congestid Periods',
        marker_color=col_charge_al
    ))
    fig.add_trace(go.Bar(
        x=labels,
        y=[neut_tc.get(t, 0) for t in times],
        name='Neutral charging',
        marker_color=col_neutral
    ))
    fig.update_layout(
        barmode='group',
        title='Yearly Charging by Exact Time',
        xaxis=dict(title='Time (HH:MM)', tickangle=45),
        yaxis=dict(title='Count'),
        height=500
    )
    return fig

def plot_period_polar(new_df, al_df):
    """
    Radial bar (“rose”) chart of events by time-of-day periods.
    """
    def label(dt):
        h = dt.hour
        if h < 6:    return "Night"
        if h < 12:   return "Morning"
        if h < 18:   return "Afternoon"
        return "Evening"

    periods = ["Night","Morning","Afternoon","Evening"]
    angles  = [i * 360/len(periods) for i in range(len(periods))]
    palette = colors_crest(1) + colors_flare(1)

    fig = go.Figure()
    # new congestion
    new_counts = pd.Series(new_df.index.map(label)).value_counts().reindex(periods, fill_value=0)
    fig.add_trace(go.Barpolar(
        r=new_counts.values,
        theta=angles,
        width=[360/4*0.8]*4,
        name='New Congestion',
        marker_color=palette[0]
    ))
    # already congested
    al_counts  = pd.Series(al_df.index.map(label)).value_counts().reindex(periods, fill_value=0)
    fig.add_trace(go.Barpolar(
        r=al_counts.values,
        theta=angles,
        width=[360/4*0.8]*4,
        name='Already Congested',
        marker_color=palette[1]
    ))
    fig.update_layout(
        title='Congestion Events by Time-of-Day (Rose Chart)',
        polar=dict(
            radialaxis=dict(showticklabels=True,ticks=""),
            angularaxis=dict(tickmode='array',tickvals=angles,ticktext=periods)
        ),
        legend=dict(orientation='h', y=-0.1),
        height=450
    )
    return fig


def plot_period_heatmap(new_df, al_df, year):
    """
    Heatmap by month & period for a full year.
    """
    def label(dt):
        h = dt.hour
        if h < 6:    return "Night"
        if h < 12:   return "Morning"
        if h < 18:   return "Afternoon"
        return "Evening"

    periods = ["Night","Morning","Afternoon","Evening"]
    months  = list(range(1,13))
    month_labels = [calendar.month_abbr[m] for m in months]

    # prepare new congestion pivot
    new2 = new_df.assign(month=new_df.index.month, period=new_df.index.map(label))
    new_pivot = new2.groupby(['month','period']).size().unstack(fill_value=0)\
                   .reindex(index=months, columns=periods, fill_value=0)
    # prepare already congested pivot
    al2  = al_df.assign(month=al_df.index.month, period=al_df.index.map(label))
    al_pivot = al2.groupby(['month','period']).size().unstack(fill_value=0)\
                   .reindex(index=months, columns=periods, fill_value=0)

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=['New Congestion','Already Congested'],
        shared_yaxes=True, horizontal_spacing=0.1,
        specs=[[{'type':'heatmap'},{'type':'heatmap'}]]
    )
    fig.add_trace(go.Heatmap(z=new_pivot.values, x=periods, y=month_labels, coloraxis='coloraxis'), row=1, col=1)
    fig.add_trace(go.Heatmap(z=al_pivot.values,  x=periods, y=month_labels, coloraxis='coloraxis'), row=1, col=2)
    fig.update_layout(
        title=f'Congestion by Month & Period (Year {year})',
        coloraxis=dict(colorscale='Blues'),
        height=450
    )
    return fig


def plot_exact_time_counts(new_df, al_df):
    """
    Bar chart of counts at each HH:MM for new vs already.
    """
    new_tc = pd.Series(new_df.index.time).value_counts().sort_index()
    al_tc  = pd.Series(al_df.index.time).value_counts().sort_index()
    times = sorted(set(new_tc.index) | set(al_tc.index))
    labels = [t.strftime('%H:%M') for t in times]
    new_vals = [new_tc.get(t,0) for t in times]
    al_vals  = [al_tc.get(t,0) for t in times]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=new_vals, name='New Congestion',    marker_color=colors_crest(1)[0]))
    fig.add_trace(go.Bar(x=labels, y=al_vals,  name='Already Congested', marker_color=colors_flare(1)[0]))
    fig.update_layout(
        barmode='group',
        title='Congestion by Exact Time of Day',
        xaxis=dict(title='Time (HH:MM)', tickangle=45),
        yaxis=dict(title='Count'),
        height=500
    )
    return fig


# --- replace the body of congestion_summary_year(...) in congestion_year.py ---

def congestion_summary_year(network, year, scenario_name):
    """
    Yearly summary: bar chart + table + rose + heatmap + split exact-time.
    """
    plot_dir = os.path.join(PLOT_BASE, str(year), scenario_name)
    csv_dir  = os.path.join(CSV_BASE,  str(year), scenario_name)
    os.makedirs(plot_dir, exist_ok=True)
    os.makedirs(csv_dir,  exist_ok=True)

    # 1) load + charging + discharging joined
    load_series  = load_yearly_load(year)
    charging     = get_storage_charging(network)
    status_charge = network.storage_units_t.status      # 0 when the battery is neither charging nor discharging
    battery_discharge = get_storage_discharging(network)  
    discharging  = get_storage_discharging(network)

        # 1) assemble the DataFrame
    df = pd.DataFrame({
        "load_mw":           load_series,
        "mrs2hh":            network.links_t.p["MRS → Household"].fillna(0),
        "hh2mrs":            network.links_t.p["Household → MRS"].fillna(0),
        "status_charge":     network.storage_units_t.status.fillna(0),
        "battery_discharge": get_storage_discharging(network).fillna(0),
    })

    # ——————————————————————————
    # 2) capacity limit
    config    = load_config()
    cap_limit = config.get("capacity_limit_mw") or (
                    config["capacity_nominal_mw"] * config["capacity_factor"]
                )

    # ——————————————————————————
    # 3) event‐type masks

    # already congested: battery idle AND MRS→HH above the limit
    mask_already = (
        (df["status_charge"] == 0)
        & (df["mrs2hh"] > cap_limit)
    )

    # new congestion: (load under cap) & (MRS→HH above cap)
    mask_new = (
        (df["load_mw"] < cap_limit)
        & (df["mrs2hh"] > cap_limit)
    )

    # charging during congested: (load > cap) & (MRS→HH > cap) & (extra flow)
    mask_charge_already = (
        (df["load_mw"] > cap_limit)
        & (df["mrs2hh"] > cap_limit)
        & (df["mrs2hh"] != df["load_mw"])
    )

    # neutral charging: (load < cap) & (MRS→HH < cap) & (extra flow)
    mask_charge_neut = (
        (df["load_mw"] < cap_limit)
        & (df["mrs2hh"] < cap_limit)
        & (df["mrs2hh"] != df["load_mw"])
    )

    # mitigation: grid under cap but discharge pushes it over
    mask_mitigate = (
        (df["mrs2hh"] < cap_limit)
        & ((df["mrs2hh"] + df["battery_discharge"]) > cap_limit)
    )
    # 3) print totals
    print(f"Total already congested events: {mask_already.sum()}")
    print(f"Total new congestion events: {mask_new.sum()}")
    print(f"Total charging during already events: {mask_charge_already.sum()}")
    print(f"Total neutral charging events: {mask_charge_neut.sum()}")
    print(f"Total mitigation events: {mask_mitigate.sum()}")

    # 4) save event‐count summary
    counts = pd.DataFrame({
        "event": [
            "already_congested",
            "new_congestion",
            "charging_during_congested",
            "neutral_charging",
            "mitigation"
        ],
        "count": [
            mask_already.sum(),
            mask_new.sum(),
            mask_charge_already.sum(),
            mask_charge_neut.sum(),
            mask_mitigate.sum()
        ]
    })
    counts.to_csv(
        os.path.join(csv_dir, "event_summary_counts.csv"),
        index=False
    )
    # 4) slice
    df_al          = df[mask_already]
    df_new         = df[mask_new]
    df_charge_al   = df[mask_charge_already]
    df_charge_neut = df[mask_charge_neut]
    df_mitigate = df[mask_mitigate]

    # 1) four event‐types (excluding neutral charging)
    event_series = {
        'already'     : pd.Series(df_al         .index.time).value_counts(),
        'new'         : pd.Series(df_new        .index.time).value_counts(),
        'chg_already' : pd.Series(df_charge_al  .index.time).value_counts(),
        'mitigation'  : pd.Series(df_mitigate   .index.time).value_counts(),
    }
    rows = []
    for event, series in event_series.items():
        for t, cnt in series.items():
            if cnt > 0:
                rows.append({
                    'event': event,
                    'time':  t.strftime('%H:%M'),
                    'count': int(cnt)
                })
    df_events = pd.DataFrame(rows)
    df_events.to_csv(
        os.path.join(csv_dir, 'congestion_event_times_year.csv'),
        index=False
    )

    # 2) neutral charging only
    neut_ser = pd.Series(df_charge_neut.index.time).value_counts().sort_index()
    df_neutral = (
        neut_ser[neut_ser > 0]
               .reset_index(name='count')
               .rename(columns={'index': 'time'})
    )
    df_neutral['time'] = df_neutral['time'].apply(lambda t: t.strftime('%H:%M'))
    df_neutral.to_csv(
        os.path.join(csv_dir, 'neutral_charging_times_year.csv'),
        index=False
    )

    # 5) monthly bar & table (unchanged)
    months       = list(range(1,13))
    new_counts   = df_new.index.month.value_counts().reindex(months, fill_value=0).sort_index()
    al_counts    = df_al .index.month.value_counts().reindex(months, fill_value=0).sort_index()
    cal_counts   = df_charge_al.index.month.value_counts().reindex(months, fill_value=0).sort_index()
    neut_counts  = df_charge_neut.index.month.value_counts().reindex(months, fill_value=0).sort_index()
    mit_counts = df_mitigate.index.month \
                          .value_counts() \
                          .reindex(months, fill_value=0) \
                          .sort_index()

    # pull two colors from each palette
    crest_cols = colors_crest(2)   # [new, charging-during]
    flare_cols = colors_flare(2)   # [already, neutral]
    mit_col = colors_flare(3)[2]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        name='Already Congested',
        x=calendar.month_abbr[1:], y=al_counts.values,
        marker_color=flare_cols[0]
    ))
    fig_bar.add_trace(go.Bar(
        name='New Congestion',
        x=calendar.month_abbr[1:], y=new_counts.values,
        marker_color=crest_cols[0]
    ))
    fig_bar.add_trace(go.Bar(
        name='Charging During Congested Periods',
        x=calendar.month_abbr[1:], y=cal_counts.values,
        marker_color=crest_cols[1]
    ))
    fig_bar.add_trace(go.Bar(
        name='Neutral Charging',
        x=calendar.month_abbr[1:], y=neut_counts.values,
        marker_color=flare_cols[1]
    ))
    fig_bar.update_layout(
        title=f'Year {year} Congestion (Monthly)',
        barmode='group',
        height=400,
        legend=dict(orientation='h', y=-0.2)
    )
    fig_bar.add_trace(go.Bar(
        name='Mitigated Congestion',
        x=calendar.month_abbr[1:], y=mit_counts.values,
        marker_color=mit_col
    ))
    #fig_bar.show()
    fig_bar.write_image(os.path.join(plot_dir, 'barplot_year.svg'))

    # 6) time-of-day table (unchanged)
    new_tc = pd.Series(df_new.index.time).value_counts().sort_index()
    al_tc  = pd.Series(df_al .index.time).value_counts().sort_index()
    mit_tc    = pd.Series(df_mitigate.index.time).value_counts().sort_index()
    all_times = sorted(set(new_tc.index) | set(al_tc.index) | set(mit_tc.index))

    df_tbl = pd.DataFrame({
        'time':      [t.strftime('%H:%M') for t in all_times],
        'new':       [new_tc.get(t,0) for t in all_times],
        'already':   [al_tc.get(t,0) for t in all_times],
        'mitigated':[mit_tc.get(t,0) for t in all_times],
    }).query('new>0 or already>0 or mitigated>0')

    # print totals again if you like
    print(f"Total mitigated events: {df_tbl['mitigated'].sum()}")

    total_new     = df_tbl['new'].sum()
    total_already = df_tbl['already'].sum()
    print(f"Total new congested events: {total_new}")
    print(f"Total already congested events: {total_already}")

    fig_tbl = go.Figure(data=[go.Table(
        header=dict(values=list(df_tbl.columns), fill_color='lightgrey'),
        cells =dict(values=[df_tbl[c] for c in df_tbl.columns])
    )])
    fig_tbl.update_layout(
    title='Time-of-Day Congestion & Mitigation Events',
    height=400
)
    #fig_tbl.show()
    fig_tbl.write_image(os.path.join(plot_dir, 'table_timeofday_year.svg'))

    # 7) rose & heatmap (unchanged)
    rose_fig    = plot_period_polar(df_new, df_al)
    heatmap_fig = plot_period_heatmap(df_new, df_al, year)
    #rose_fig.show()
    #heatmap_fig.show()
    rose_fig.write_image(os.path.join(plot_dir, 'rose_year.svg'))
    heatmap_fig.write_image(os.path.join(plot_dir, 'heatmap_year.svg'))

    # 8) split exact-time into two plots
    fig_cong   = plot_congestion_time_of_day_year(df_new, df_al, df_mitigate)
    fig_charge = plot_charging_time_of_day_year(df_charge_al, df_charge_neut)
    #fig_cong.show()
    #fig_charge.show()
    fig_cong  .write_image(os.path.join(plot_dir, 'time_of_day_congestion_year.svg'))
    fig_charge.write_image(os.path.join(plot_dir, 'time_of_day_charging_year.svg'))

    # 9) save CSVs
    # (a) full time‐series of charge/discharge behavior
    df[['charging_mw', 'discharging_mw']].to_csv(
        os.path.join(csv_dir, 'ts_charge_discharge.csv'),
        index_label='datetime'
    )

    # (b) aggregate by time‐of‐day
    agg = (
        df[['charging_mw','discharging_mw']]
          .groupby(df.index.strftime('%H:%M'))
          .sum()
          .reset_index()
    )
    agg.columns = ['time', 'total_charging_mw', 'total_discharging_mw']
    agg.to_csv(
        os.path.join(csv_dir, 'agg_charge_discharge_by_time_of_day.csv'),
        index=False
    )

    # (c) existing congestion event CSVs
    df_new.to_csv(
        os.path.join(csv_dir, 'new_congestion.csv'),
        index_label='datetime'
    )
    df_al .to_csv(
        os.path.join(csv_dir, 'already_congested.csv'),
        index_label='datetime'
    )
    return {
        'bar'       : fig_bar,
        'table'     : fig_tbl,
        'rose'      : rose_fig,
        'heatmap'   : heatmap_fig,
        'congestion': fig_cong,
        'charging'  : fig_charge
    }

def plot_group_year_summary(year, scenario_group, sub_scenarios):
    import os, pandas as pd, plotly.graph_objects as go
    from utils.utils import colors_crest

    metrics = []
    for sub in sub_scenarios:
        name = sub["name"]
        totals = {"mitigation": 0, "chg_already": 0, "new": 0, "neutral": 0}

        # Loop over DAM en Imbalance subfolders
        for tag in ("DAM", "Imbalance"):
            base = os.path.join(
                "results", "congestion_year",
                str(year), scenario_group,
                f"{name}_{tag}"
            )

            # Events
            ev_csv = os.path.join(base, "congestion_event_times_year.csv")
            if os.path.exists(ev_csv):
                df_ev = pd.read_csv(ev_csv)
                for ev in ("mitigation", "chg_already", "new"):
                    totals[ev] += df_ev.query("event == @ev")["count"].sum()

            # Neutral charging
            neut_csv = os.path.join(base, "neutral_charging_times_year.csv")
            if os.path.exists(neut_csv):
                totals["neutral"] += pd.read_csv(neut_csv)["count"].sum()

        metrics.append({"scenario": name, **totals})

    df = pd.DataFrame(metrics).set_index("scenario")

    # Maak leesbare labels (bv. "90/10")
    labels = []
    for name in df.index:
        parts = name.split("_")
        if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
            labels.append(f"{parts[-2]}/{parts[-1]}")
        else:
            labels.append(name.split("_",1)[-1].replace("_", "/"))

    figs = {}
    colors = colors_crest(len(df))
    for ev, title in [
        ("mitigation", "Mitigation Events"),
        ("chg_already", "Charging During Congested Periods"),
        ("new",        "New Congestion Events"),
        ("neutral",    "Neutral Charging Events")
    ]:
        fig = go.Figure(go.Bar(
            x=df.index, y=df[ev].values, marker_color=colors, name=title
        ))
        fig.update_layout(
            title=f"{title} — {scenario_group} {year}",
            xaxis=dict(
                tickmode="array",
                tickvals=df.index.tolist(),
                ticktext=labels,
                tickangle=45
            ),
            yaxis_title="Count",
            height=500,
            margin=dict(t=80, b=150, l=80, r=50)
        )

        out_dir = os.path.join(
            "plots", "congestion_year", str(year), scenario_group
        )
        os.makedirs(out_dir, exist_ok=True)
        fig.write_image(os.path.join(out_dir, f"{ev}_year.svg"))
        figs[ev] = fig

    return figs


def plot_group_year_events_heatmaps(year, scenario_group, sub_scenarios):
    import os, pandas as pd, plotly.graph_objects as go
    
    def collect(ev, neutral=False):
        cmap = {}
        for sub in sub_scenarios:
            name = sub["name"]
            total = {}

            # Voor beide tags (_DAM en _Imbalance)
            for tag in ("DAM", "Imbalance"):
                base = os.path.join(
                    "results", "congestion_year",
                    str(year), scenario_group,
                    f"{name}_{tag}"
                )

                # Event‐data
                if not neutral:
                    ev_csv = os.path.join(base, "congestion_event_times_year.csv")
                    if os.path.exists(ev_csv):
                        df_ev = pd.read_csv(ev_csv)
                        sel = df_ev[df_ev["event"] == ev]
                        for t, c in sel.groupby("time")["count"].sum().items():
                            total[t] = total.get(t, 0) + int(c)

                # Neutral charging
                else:
                    neut_csv = os.path.join(base, "neutral_charging_times_year.csv")
                    if os.path.exists(neut_csv):
                        df_ne = pd.read_csv(neut_csv)
                        for _, row in df_ne.iterrows():
                            total[row["time"]] = total.get(row["time"], 0) + int(row["count"])

            if total:
                cmap[name] = pd.Series(total)

        return cmap

    events = [
        ("mitigation", False),
        ("chg_already", False),
        ("new", False),
        ("neutral", True)
    ]

    # Y-as labels
    scenario_names = [s["name"] for s in sub_scenarios]
    labels = []
    for name in scenario_names:
        parts = name.split("_")
        if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
            labels.append(f"{parts[-2]}/{parts[-1]}")
        else:
            labels.append(name.split("_",1)[-1].replace("_", "/"))

    figs = {}
    for ev, neutral in events:
        cmap = collect(ev, neutral)
        times = sorted(
            {t for ser in cmap.values() for t in ser.index},
            key=lambda x: pd.to_datetime(x, format="%H:%M")
        )
        if not times:
            continue

        df = pd.DataFrame({
            name: cmap.get(name, pd.Series(dtype=int))
                        .reindex(times, fill_value=0)
            for name in scenario_names
        }, index=times)

        fig = go.Figure(go.Heatmap(
            z=df.T.values,
            x=df.index,
            y=labels,
            colorscale="Reds",
            colorbar=dict(title="Count")
        ))
        fig.update_layout(
            title=f"{ev.replace('_',' ').title()} Heatmap — {scenario_group} {year}",
            xaxis_title="Time (HH:MM)",
            yaxis_title="Scenario",
            xaxis=dict(tickangle=45),
            height=500,
            margin=dict(t=80, b=100, l=120, r=50)
        )

        out_dir = os.path.join(
            "plots", "congestion_year", str(year), scenario_group
        )
        os.makedirs(out_dir, exist_ok=True)
        fig.write_image(os.path.join(out_dir, f"heatmap_{ev}_year.svg"))
        figs[ev] = fig

    return figs
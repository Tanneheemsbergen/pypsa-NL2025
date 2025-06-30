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

def plot_congestion_time_of_day_year(df_new, df_al, df_mitigate,):
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
    #cal_tc  = tc(df_charge_al)

    times  = sorted(set(new_tc.index) | set(al_tc.index))
    labels = [t.strftime('%H:%M') for t in times]
    tick30 = [
    lbl
    for t, lbl in zip(times, labels)
    if t.minute % 30 == 0
]
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
         xaxis=dict(
            title='Time (HH:MM)',
            tickangle=45,
            tickmode='array',
            tickvals=tick30,
            ticktext=tick30,
        ),
        yaxis=dict(title='Count (negative = mitigation)'),
        height=500
    )
    return fig

def plot_charging_time_of_day_year(df_charge_al, df_charge_neut):
    """
    Bar chart of charging counts at each specific time (HH:MM):
      - Charging during already congested times
      - Neutral charging times

    PLUS a zoomed‐in subplot for 07:30–14:30.
    """
    def tc(df):
        return pd.Series(df.index.time).value_counts().sort_index()

    cal_tc  = tc(df_charge_al)
    neut_tc = tc(df_charge_neut)

    # all times sorted
    all_times = sorted(set(cal_tc.index) | set(neut_tc.index))

    windows = [
        (pd.to_datetime("07:30").time(), pd.to_datetime("07:45").time()),
        (pd.to_datetime("10:00").time(), pd.to_datetime("14:45").time()),
    ]

    # pick times within either window
    zoom_times = [
        t for t in all_times
        if any(start <= t <= end for (start, end) in windows)
    ]

    # string labels
    all_labels  = [t.strftime("%H:%M") for t in all_times]
    zoom_labels = [t.strftime("%H:%M") for t in zoom_times]


    # colors
    col_charge_al = colors_crest(2)[1]
    col_neutral   = colors_flare(2)[1]

    # make a 2‐row subplot sharing y‐axis
    fig = make_subplots(
        rows=2, cols=1,
        shared_yaxes=True,
        vertical_spacing=0.1,
        # subplot_titles=("Zoom: 07:30–14:30", "Full day")
    )

    # ROW 1: zoomed bars
    fig.add_trace(
        go.Bar(
            x=zoom_labels,
            y=[cal_tc.get(t, 0) for t in zoom_times],
            name="Charging During Congested Periods",
            marker_color=col_charge_al,
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Bar(
            x=zoom_labels,
            y=[neut_tc.get(t, 0) for t in zoom_times],
            name="Neutral charging",
            marker_color=col_neutral,
        ),
        row=1, col=1
    )

    # ROW 2: full‐day bars
    fig.add_trace(
        go.Bar(
            x=all_labels,
            y=[cal_tc.get(t, 0) for t in all_times],
            showlegend=False,  # legend once is enough
            marker_color=col_charge_al,
        ),
        row=2, col=1
    )
    fig.add_trace(
        go.Bar(
            x=all_labels,
            y=[neut_tc.get(t, 0) for t in all_times],
            showlegend=False,
            marker_color=col_neutral,
        ),
        row=2, col=1
    )

    # layout tweaks
    fig.update_layout(
        height=700,
        barmode="group",
        title_text="Yearly Charging by Exact Time",
    )

    # x‐axes
    fig.update_xaxes(row=1, col=1, tickangle=45, title_text="")
    fig.update_xaxes(row=2, col=1, tickangle=45, title_text="Time (HH:MM)")

    # y‐axis (shared)
    fig.update_yaxes(row=1, col=1, title_text="Count")
    # row=2 shares so no need to re‐label

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

def congestion_summary_year(network, year, scenario_name, forced_flow_to_house: pd.Series = None):
    """
    Yearly summary: bar chart + table + rose + heatmap + split exact-time.
    """
    plot_dir = os.path.join(PLOT_BASE, str(year), scenario_name)
    csv_dir  = os.path.join(CSV_BASE,  str(year), scenario_name)
    os.makedirs(plot_dir, exist_ok=True)
    os.makedirs(csv_dir,  exist_ok=True)

    # 1) load + charging + discharging joined
    load_series  = load_yearly_load(year)
    # get your real charge/discharge time series
    charging_mw   = get_storage_charging(network).fillna(0)
    discharging_mw = get_storage_discharging(network).fillna(0)

    # 2) start with an empty DataFrame
    df = pd.DataFrame(index=load_series.index)

    # 3) always add these columns
    df["load_mw"]        = load_series
    df["charging_mw"]    = charging_mw
    df["discharging_mw"] = discharging_mw

    # 1) add a solar generation column if there is a PV link
    if "PV → Household" in network.links_t.p0.columns:
        # p0 is positive from bus0 (PV) → bus1 (Household)
        df["solar_gen"] = network.links_t.p0["PV → Household"].fillna(0)
    else:
        # no PV in this scenario
        df["solar_gen"] = 0.0

    # 2) a helper flag: True only when there's zero PV
    df["pv_zero"] = df["solar_gen"] == 0.0

    is_imbalance = scenario_name.endswith("_Imbalance")
    if is_imbalance:
        # 5a) for Imbalance: load the DAM’s baseline CSV instead of recomputing
        dam_name     = scenario_name.replace("_Imbalance", "_DAM")
        dam_csv_dir  = os.path.join(CSV_BASE, str(year), dam_name)
        dam_base_csv = os.path.join(dam_csv_dir, "congestion_baseline.csv")
        if not os.path.exists(dam_base_csv):
            raise FileNotFoundError(f"DAM baseline not found: {dam_base_csv}")
        base_df = pd.read_csv(
            dam_base_csv, parse_dates=['datetime'], index_col='datetime'
        )
        df["flow_to_house"]  = base_df["flow_to_house"]
        m2h_imb = network.links_t.p0["MSR → Household"].fillna(0)
        h2m_imb = network.links_t.p0["Household → MSR"].fillna(0)
        df["flow_to_house_netto"] = (m2h_imb - h2m_imb).clip(lower=0)
        df["flow_to_house_imb"] = df["flow_to_house"] + df["flow_to_house_netto"]
        df["net_house_load"] = base_df["net_house_load"]
        baseline = df[["load_mw", "flow_to_house_imb", "net_house_load"]].copy()
        # bring the datetime index into a column
        baseline["datetime"] = baseline.index
        # reorder so datetime is first
        baseline = baseline[["datetime", "load_mw", "flow_to_house_imb", "net_house_load"]]
        baseline.to_csv(
            os.path.join(csv_dir, "congestion_baseline.csv"),
            index=False
        )
    else:
        # 5b) for DAM: compute as usual, then save baseline for the Imbalance run
        #    5b.i) actual flow from MSR→Household
        m2h = network.links_t.p0["MSR → Household"].fillna(0)
        h2m = network.links_t.p0["Household → MSR"].fillna(0)
        df["flow_to_house"] = (m2h - h2m).clip(lower=0)

        #    5b.ii) net load including battery charge/discharge efficiency
        df["net_house_load"] = (
            df["flow_to_house"]
            - (df["charging_mw"] / 91) * 100
            + df["discharging_mw"] * 0.91
        )

        #    5b.iii) save for the Imbalance call
        #    5b.iii) save for the Imbalance call, including datetime & load_mw
        baseline = df[["load_mw", "flow_to_house", "net_house_load"]].copy()
        # bring the datetime index into a column
        baseline["datetime"] = baseline.index
        # reorder so datetime is first
        baseline = baseline[["datetime", "load_mw", "flow_to_house", "net_house_load"]]
        baseline.to_csv(
            os.path.join(csv_dir, "congestion_baseline.csv"),
            index=False
        )
    # df["net_mrs2hh"] = df["mrs2hh"] - df["hh2mrs"]
    # # use only the positive part for your congestion logic
    # df["flow_to_house"] = df["net_mrs2hh"].clip(lower=0)

    # and (optionally) the negative part for charging back
    # ——————————————————————————
    # 2) capacity limit
    config    = load_config()
    cap_limit = 11.2 * 0.85
    #cap_limit = 39.6 *0.85
    # cap_limit = config.get('capacity_limit_mw') or (
    #                 config.get('capacity_nominal_mw',11.2)
    #               * config.get('capacity_factor',0.85))
      # battery is idle whenever it’s neither charging nor discharging
    df["status_idle"] = (
        (df["charging_mw"]    == 0) &
        (df["discharging_mw"]  == 0)
    )
    # ——————————————————————————
    # 3) event‐type masks

    # already congested: battery idle AND MSR→HH above the limit
    #already congested: load from group-level file if present, else compute & save
    # scenario_name is like "MyGroup/Trade_100_0_DAM" → split off the group
    group, _, _ = scenario_name.partition(os.sep)
    group_csv_dir  = os.path.join(CSV_BASE, str(year), group)
    group_csv_file = os.path.join(group_csv_dir, 'already_congested.csv')
    if os.path.exists(group_csv_file):
        # load existing group-level already-congested timestamps
        grp_df = pd.read_csv(group_csv_file, parse_dates=['datetime'], index_col='datetime')
        mask_already = df.index.isin(grp_df.index)
    else:
        # first run: compute and save into group folder
        mask_already = df["net_house_load"] > cap_limit
        os.makedirs(group_csv_dir, exist_ok=True)
        df[mask_already].to_csv(group_csv_file, index_label='datetime')

    if is_imbalance:
        # Imbalance: count hours where import > cap, but after charging it would be under cap
        mask_new = (
            (df["load_mw"]           < cap_limit)
          & (df["flow_to_house_imb"]    > cap_limit)
          & ((df["flow_to_house_imb"] - df["charging_mw"]) < cap_limit)
          & (df["charging_mw"]      != 0.0)
        )
    else:
        # DAM: any hour where import pushes load over cap while charging
        mask_new = (
            (df["load_mw"]           < cap_limit)
          & (df["flow_to_house"]    > cap_limit)
          & (df["charging_mw"]      != 0.0)
        )

    # charging during congested: (load > cap) & (MSR→HH > cap) & (extra flow)
    if is_imbalance:
        # Imbalance: count hours where import > cap, but after charging it would be under cap
        mask_charge_already = (
        (df["load_mw"] > cap_limit)
        & (df["flow_to_house_imb"] > cap_limit)
        & (df["flow_to_house_imb"] != df["load_mw"])
        & (df["charging_mw"]    != 0.0) 
        #&  df["pv_zero"]
    )
    else:
        # DAM: any hour where import pushes load over cap while charging
       mask_charge_already = (
        (df["load_mw"] > cap_limit)
        & (df["flow_to_house"] > cap_limit)
        & (df["flow_to_house"] != df["load_mw"])
        & (df["charging_mw"]    != 0.0) 
        #&  df["pv_zero"]
    )

    # charging during congested: (load > cap) & (MSR→HH > cap) & (extra flow)
    if is_imbalance:
        # neutral charging: (load < cap) & (MSR→HH < cap) & (extra flow)
        mask_charge_neut = (
        (df["load_mw"] < cap_limit)
        & (df["flow_to_house_imb"] < cap_limit)
        & (df["flow_to_house_imb"] != df["load_mw"])
        & (df["charging_mw"]    != 0.0)
        #&  df["pv_zero"]
    )
    else:
        # neutral charging:  (load < cap) & (MSR→HH < cap) & (extra flow)
        mask_charge_neut = (
        (df["load_mw"] < cap_limit)
        & (df["flow_to_house"] < cap_limit)
        & (df["flow_to_house"] != df["load_mw"])
        & (df["charging_mw"]    != 0.0)
        #&  df["pv_zero"]
    )
      # charging during congested: (load > cap) & (MSR→HH > cap) & (extra flow)
    if is_imbalance:
        # mitigation: grid under cap but discharge pushes it over
        mask_mitigate = ((df["flow_to_house_imb"] < cap_limit)
        & ((df["flow_to_house_imb"] + (df["discharging_mw"]*0.91)) > cap_limit)
    )
    else:
        # mitigation: grid under cap but discharge pushes it over
        mask_mitigate = (        (df["flow_to_house"] < cap_limit)
        & ((df["flow_to_house"] + (df["discharging_mw"]*0.91)) > cap_limit)
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
    # df_al .to_csv(
    #     os.path.join(csv_dir, 'already_congested.csv'),
    #     index_label='datetime'
    # )
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
    from utils.utils import colors_flare

    # mitigation uses a custom flare color; others will use the built-in Reds scale
    mit_col = colors_flare(3)[2]

    def collect(ev, neutral=False):
        cmap = {}
        for sub in sub_scenarios:
            name = sub["name"]
            total = {}
            for tag in ("DAM", "Imbalance"):
                base = os.path.join(
                    "results", "congestion_year",
                    str(year), scenario_group,
                    f"{name}_{tag}"
                )
                if not neutral:
                    ev_csv = os.path.join(base, "congestion_event_times_year.csv")
                    if os.path.exists(ev_csv):
                        df_ev = pd.read_csv(ev_csv)
                        sel   = df_ev[df_ev["event"] == ev]
                        for t, c in sel.groupby("time")["count"].sum().items():
                            total[t] = total.get(t, 0) + int(c)
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

    # Y-axis labels
    scenario_names = [s["name"] for s in sub_scenarios]
    labels = []
    for name in scenario_names:
        parts = name.split("_")
        if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
            labels.append(f"{parts[-2]}/{parts[-1]}")
        else:
            labels.append(name.split("_",1)[-1].replace("_","/"))

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

        # choose color scale per event
        if ev == "mitigation":
            colorscale = [[0, 'white'], [1, mit_col]]
        else:
            colorscale = 'Reds'

        fig = go.Figure(go.Heatmap(
            z=df.T.values,
            x=df.index,
            y=labels,
            colorscale=colorscale,
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

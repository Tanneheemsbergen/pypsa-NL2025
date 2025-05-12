import os
import pandas as pd
import numpy as np
import calendar
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from core.load_week import get_week_range
from utils.set_plot_style import set_plot_style
from utils.utils import colors_crest, colors_flare

# Apply global Plotly style
set_plot_style()

# Constants
NOMINAL_CAPACITY_MW = 11.2   # MW
CAPACITY_FACTOR     = 0.85   # fraction of nominal capacity
CAPACITY_LIMIT_MW   = NOMINAL_CAPACITY_MW * CAPACITY_FACTOR
LOAD_FILE           = "data/new_SS_Monnickendam.csv"
RESULTS_DIR         = "results"
PLOT_BASE = 'plots/congestion_week'
CSV_BASE  = 'results/congestion_week'



def get_storage_charging(network, store=None):
    """
    Extracts battery charging load (MW) from network.stores_t.p.
    Charging corresponds to negative p, so clip above zero and take absolute.
    """
    p_series = network.stores_t.p
    if store is None:
        if p_series.shape[1] == 1:
            store = p_series.columns[0]
        else:
            raise ValueError(f"Multiple stores found {list(p_series.columns)}; specify one.")
    p = p_series[store]
    p = p.clip(upper=0).abs()
    # Save charging series to CSV
    os.makedirs(CSV_BASE, exist_ok=True)
    p.to_frame(name='charging_mw').to_csv(os.path.join(CSV_BASE, 'storage_charging_test.csv'))
    return p

def get_storage_discharging(network, store=None):
    """
    Extracts battery discharging load (MW) from network.stores_t.p.
    Discharging corresponds to positive p, so clip below zero and take values.
    """
    p_series = network.stores_t.p
    if store is None:
        if p_series.shape[1] == 1:
            store = p_series.columns[0]
        else:
            raise ValueError(f"Multiple stores found {list(p_series.columns)}; specify one.")
    p = p_series[store]
    return p.clip(lower=0)


def load_weekly_load(year, week, filepath=LOAD_FILE):
    """
    Reads load CSV, filters by ISO-week, returns Series of load_mw indexed by datetime.
    """
    start, end = get_week_range(year, week)
    df = pd.read_csv(filepath, parse_dates=["datetime"])
    mask = (df["datetime"] >= start) & (df["datetime"] < end)
    df_week = df.loc[mask].copy()
    df_week.set_index("datetime", inplace=True)
    df_week.rename(columns={"belasting": "load_mw"}, inplace=True)
    load_series = df_week["load_mw"]
    # Debug prints
    print(f"[load_weekly_load] load_series shape={load_series.shape}")
    print(load_series.head())
    return load_series


def detect_new_congestion_week(network, load_series, capacity_limit=CAPACITY_LIMIT_MW):
    charging = get_storage_charging(network)
    df = pd.DataFrame({'load_mw': load_series}).join(
        charging.rename('charging_mw'), how='inner'
    ).fillna(0)
    df['combined'] = df['load_mw'] + df['charging_mw']
    result = df[(df['load_mw'] < capacity_limit) & (df['combined'] > capacity_limit)]
    # Save new congestion DataFrame to CSV
    os.makedirs(CSV_BASE, exist_ok=True)
    result.to_csv(os.path.join(CSV_BASE, 'new_congestion_week_test.csv'))
    return result


def detect_already_congested_week(load_series, capacity_limit=CAPACITY_LIMIT_MW):
    df = load_series.to_frame(name='load_mw')
    result = df[df['load_mw'] > capacity_limit]
    # Save already congested DataFrame to CSV
    os.makedirs(CSV_BASE, exist_ok=True)
    result.to_csv(os.path.join(CSV_BASE, 'already_congested_week_test.csv'))
    return result


def plot_period_polar(new_df, al_df):
    """
    Radial bar (“rose”) chart of congestion events by broad periods.
    """
    def get_period_label(dt):
        h = dt.hour
        if h < 6:
            return "Night"
        if h < 12:
            return "Morning"
        if h < 18:
            return "Afternoon"
        return "Evening"

    periods = ["Night", "Morning", "Afternoon", "Evening"]
    angles = [i * 360 / len(periods) for i in range(len(periods))]

    new_counts = pd.Series(new_df.index.map(get_period_label)) \
                   .value_counts().reindex(periods, fill_value=0)
    al_counts = pd.Series(al_df.index.map(get_period_label))  \
                  .value_counts().reindex(periods, fill_value=0)

    fig = go.Figure()
    fig.add_trace(go.Barpolar(
        r=new_counts.values,
        theta=angles,
        width=[360/4 * 0.8] * 4,
        name='New',
        marker_color=colors_crest(1)[0]
    ))
    fig.add_trace(go.Barpolar(
        r=al_counts.values,
        theta=angles,
        width=[360/4 * 0.8] * 4,
        name='Already',
        marker_color=colors_flare(1)[0]
    ))
    fig.update_layout(
        title='Congestion Events by Time-of-Day (Rose Chart)',
        polar=dict(
            radialaxis=dict(showticklabels=True, ticks=""),
            angularaxis=dict(tickmode='array', tickvals=angles, ticktext=periods)
        ),
        legend=dict(orientation='h', y=-0.1),
        height=450
    )
    return fig


def plot_period_heatmap(df_new, df_al, year, week):
    """
    Heatmap of congestion counts by day of week (rows) and period (cols).
    """
    def get_period_label(dt):
        h = dt.hour
        if h < 6:
            return "Night"
        if h < 12:
            return "Morning"
        if h < 18:
            return "Afternoon"
        return "Evening"

    periods = ["Night", "Morning", "Afternoon", "Evening"]
    days = pd.date_range(*get_week_range(year, week), freq='D')[:-1].date

    new_df2 = df_new.assign(
        period=df_new.index.map(get_period_label),
        day=df_new.index.normalize().date
    )
    al_df2 = df_al.assign(
        period=df_al.index.map(get_period_label),
        day=df_al.index.normalize().date
    )

    new_pivot = new_df2.groupby(['day', 'period']).size() \
                   .unstack(fill_value=0).reindex(index=days, columns=periods, fill_value=0)
    al_pivot = al_df2.groupby(['day', 'period']).size() \
                  .unstack(fill_value=0).reindex(index=days, columns=periods, fill_value=0)

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=['New Congestion', 'Already Congested'],
        shared_yaxes=True,
        horizontal_spacing=0.1,
        specs=[[{'type':'heatmap'}, {'type':'heatmap'}]]
    )
    fig.add_trace(
        go.Heatmap(
            z=new_pivot.values,
            x=periods,
            y=[d.strftime('%a %d') for d in days],
            coloraxis='coloraxis'
        ), row=1, col=1
    )
    fig.add_trace(
        go.Heatmap(
            z=al_pivot.values,
            x=periods,
            y=[d.strftime('%a %d') for d in days],
            coloraxis='coloraxis'
        ), row=1, col=2
    )
    fig.update_layout(
        title=f'Heatmap of Congestion by Day & Period (Week {week}, {year})',
        coloraxis=dict(colorscale='Blues'),
        height=450
    )
    return fig


def plot_congestion_time_of_day(df_new, df_already, df_mitigate):
    """
    Bar chart of congestion counts at each specific time (HH:MM):
      - Already congested
      - New congestion
      - Mitigation (negative counts)
    """
    # helper to count by time
    def tc(series): return pd.Series(series.index.time).value_counts().sort_index()

    new_tc = tc(df_new)
    al_tc  = tc(df_already)
    mit_tc = tc(df_mitigate)

    times  = sorted(set(new_tc.index) | set(al_tc.index) | set(mit_tc.index))
    labels = [t.strftime('%H:%M') for t in times]

    colors = {
        'already': colors_flare(1)[0],
        'new':     colors_crest(1)[0],
        'mitigate': colors_flare(3)[2]
    }

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=[al_tc.get(t, 0) for t in times],
        name='Already congested',
        marker_color=colors['already']
    ))
    fig.add_trace(go.Bar(
        x=labels,
        y=[new_tc.get(t, 0) for t in times],
        name='New congestion',
        marker_color=colors['new']
    ))
    fig.add_trace(go.Bar(
        x=labels,
        y=[-mit_tc.get(t, 0) for t in times],
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


def plot_charging_time_of_day(df_charge_al, df_charge_neut):
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
    crest_col = colors_crest(2)[1]
    flare_col = colors_flare(2)[1]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=[cal_tc.get(t, 0)  for t in times],
        name='Charging During Congested Periods',
        marker_color=crest_col
    ))
    fig.add_trace(go.Bar(
        x=labels,
        y=[neut_tc.get(t, 0) for t in times],
        name='Neutral charging',
        marker_color=flare_col
    ))
    fig.update_layout(
        barmode='group',
        title='Charging by Exact Time',
        xaxis=dict(title='Time (HH:MM)', tickangle=45),
        yaxis=dict(title='Count'),
        height=500
    )
    return fig

def plot_time_of_day_exact_combined(dam_new, dam_al, imb_new, imb_al):
    """
    Grouped bar chart of congestion counts at each time for DAM vs Imbalance.
    """
    dam_new_tc = pd.Series(dam_new.index.time).value_counts().sort_index()
    dam_al_tc = pd.Series(dam_al.index.time).value_counts().sort_index()
    imb_new_tc = pd.Series(imb_new.index.time).value_counts().sort_index()
    imb_al_tc = pd.Series(imb_al.index.time).value_counts().sort_index()
    times = sorted(set(dam_new_tc.index) | set(dam_al_tc.index) | set(imb_new_tc.index) | set(imb_al_tc.index))
    labels = [t.strftime('%H:%M') for t in times]
    dam_new_vals = [dam_new_tc.get(t, 0) for t in times]
    dam_al_vals = [dam_al_tc.get(t, 0) for t in times]
    imb_new_vals = [imb_new_tc.get(t, 0) for t in times]
    imb_al_vals = [imb_al_tc.get(t, 0) for t in times]

    dam_cols = colors_crest(2)
    imb_cols = colors_flare(2)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=dam_new_vals, name='DAM New', marker_color=dam_cols[0]))
    fig.add_trace(go.Bar(x=labels, y=dam_al_vals, name='DAM Already', marker_color=dam_cols[1]))
    fig.add_trace(go.Bar(x=labels, y=imb_new_vals, name='Imb New', marker_color=imb_cols[0]))
    fig.add_trace(go.Bar(x=labels, y=imb_al_vals, name='Imb Already', marker_color=imb_cols[1]))
    fig.update_layout(
        barmode='group',
        title='Combined Congestion by Exact Time',
        xaxis=dict(title='Time (HH:MM)', tickangle=45),
        yaxis=dict(title='Count'),
        height=500
    )
    return fig


def congestion_summary_week(network, year, week, scenario_name):
    """
    Single-network summary: bar+table + rose + heatmap + exact-time + mitigation events.
    """
    plot_dir = os.path.join(PLOT_BASE, str(year), scenario_name, f'week_{week}')
    csv_dir  = os.path.join(CSV_BASE,  str(year), scenario_name, f'week_{week}')
    os.makedirs(plot_dir, exist_ok=True)
    os.makedirs(csv_dir,  exist_ok=True)

    # load & charging/discharging time‐series
    load_series = load_weekly_load(year, week)
    charging    = get_storage_charging(network)
    discharging = get_storage_discharging(network)

    df = pd.DataFrame({'load_mw': load_series}) \
           .join(charging.rename('charging_mw'), how='inner') \
           .join(discharging.rename('discharging_mw'), how='inner') \
           .fillna(0)
    df['combined_charging'] = df['load_mw'] + df['charging_mw']
    df['net_load']          = df['load_mw'] - df['discharging_mw']

    # classification based on capacity
    cap = CAPACITY_LIMIT_MW
    mask_already        = df['load_mw']    > cap
    mask_new            = (~mask_already)  & (df['combined_charging']    > cap)
    mask_charge_already = mask_already     & (df['charging_mw'] > 0)
    mask_neutral_charge = (df['charging_mw'] > 0) \
                         & ~mask_new       & ~mask_charge_already
    mask_mitigate      = mask_already     & (df['net_load']    < cap)

    # print totals for each category
    print(f"Total already congested events: {mask_already.sum()}")
    print(f"Total new congestion events: {mask_new.sum()}")
    print(f"Total charging during already congested events: {mask_charge_already.sum()}")
    print(f"Total neutral charging events: {mask_neutral_charge.sum()}")
    print(f"Total mitigation events (discharging relieving congestion): {mask_mitigate.sum()}")

    df_already     = df[mask_already]
    df_new         = df[mask_new]
    df_charge_al   = df[mask_charge_already]
    df_charge_neut = df[mask_neutral_charge]
    df_mitigate    = df[mask_mitigate]

    event_series = {
        'already'     : pd.Series(df_already   .index.time).value_counts(),
        'new'         : pd.Series(df_new       .index.time).value_counts(),
        'chg_already' : pd.Series(df_charge_al .index.time).value_counts(),
        'mitigation'  : pd.Series(df_mitigate  .index.time).value_counts()
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
    os.makedirs(csv_dir, exist_ok=True)
    df_events.to_csv(
        os.path.join(csv_dir, 'congestion_event_times.csv'),
        index=False
    )

    # ——— save neutral charging separately ———
    neut_series = pd.Series(df_charge_neut.index.time).value_counts().sort_index()
    df_neutral = (
        neut_series[neut_series > 0]            # drop zeros
        .reset_index(name='count')              # name the count-column
        .rename(columns={'index': 'time'})      # rename for clarity
    )
    df_neutral['time'] = df_neutral['time'].apply(lambda t: t.strftime('%H:%M'))
    df_neutral.to_csv(
        os.path.join(csv_dir, 'neutral_charging_times.csv'),
        index=False
    )
    # daily counts
    start, end = get_week_range(year, week)
    days = pd.date_range(start=start.normalize(),
                         end=(end - pd.Timedelta(days=1)).normalize(),
                         freq='D')
    new_counts   = df_new         .index.normalize().value_counts().reindex(days, fill_value=0).sort_index()
    al_counts    = df_already     .index.normalize().value_counts().reindex(days, fill_value=0).sort_index()
    cal_counts   = df_charge_al   .index.normalize().value_counts().reindex(days, fill_value=0).sort_index()
    neut_counts  = df_charge_neut .index.normalize().value_counts().reindex(days, fill_value=0).sort_index()
    mit_counts   = df_mitigate    .index.normalize().value_counts().reindex(days, fill_value=0).sort_index()

    # build exact‐time table
    def tc(df): return pd.Series(df.index.time).value_counts()
    times = sorted(
        set(tc(df_new).index) |
        set(tc(df_already).index) |
        set(tc(df_charge_al).index) |
        set(tc(df_charge_neut).index) |
        set(tc(df_mitigate).index)
    )
    df_table = pd.DataFrame({
        'time':        [t.strftime('%H:%M') for t in times],
        'already':     [tc(df_already).get(t, 0)   for t in times],
        'new':         [tc(df_new).get(t, 0)       for t in times],
        'chg_already': [tc(df_charge_al).get(t, 0) for t in times],
        'chg_neutral': [tc(df_charge_neut).get(t, 0) for t in times],
        'mitigated':   [tc(df_mitigate).get(t, 0)  for t in times]
    })
    df_table = df_table[(df_table[['already','new','chg_already','chg_neutral','mitigated']] > 0).any(axis=1)]

    # pick distinct colors
    crest_cols = colors_crest(2)   # [new, charging-during]
    flare_cols = colors_flare(2)   # [already, neutral]
    mit_col    = colors_flare(3)[2]  # third flare color for mitigation

    # bar + table subplot
    fig = make_subplots(
        rows=2, cols=1, row_heights=[0.6, 0.4], vertical_spacing=0.1,
        specs=[[{'type': 'bar'}], [{'type': 'table'}]]
    )
    fig.add_trace(go.Bar(
        name='Already congested', x=days, y=al_counts.values,
        marker_color=flare_cols[0]
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        name='New congestion',   x=days, y=new_counts.values,
        marker_color=crest_cols[0]
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        name='Charging During Congested Periods', x=days, y=cal_counts.values,
        marker_color=crest_cols[1]
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        name='Neutral charging',  x=days, y=neut_counts.values,
        marker_color=flare_cols[1]
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        name='Mitigated congestion', x=days, y=mit_counts.values,
        marker_color=mit_col
    ), row=1, col=1)
    fig.add_trace(go.Table(
        header=dict(values=list(df_table.columns), fill_color='lightgrey'),
        cells=dict(values=[df_table[c] for c in df_table.columns])
    ), row=2, col=1)
    fig.update_layout(
        title=f'Week {week}, {year} Congestion Summary',
        barmode='group',
        height=750,
        legend=dict(x=1, y=1, xanchor='right', yanchor='top'),
        margin=dict(t=50, b=50, l=50, r=50)
    )

    # rose chart
    rose_fig = plot_period_polar(df_new, df_already)
    rose_fig.show()
    # heatmap
    heatmap_fig = plot_period_heatmap(df_new, df_already, year, week)
    heatmap_fig.show()
    # exact-time with charging
    fig_cong   = plot_congestion_time_of_day(df_new, df_already, df_mitigate)
    fig_charge = plot_charging_time_of_day(df_charge_al, df_charge_neut)

    fig_cong.show()
    fig_charge.show()

    fig_cong  .write_image(os.path.join(plot_dir, 'time_of_day_congestion.svg'))
    fig_charge.write_image(os.path.join(plot_dir, 'time_of_day_charging.svg'))

    # save summary with mitigation
    fig.write_image(os.path.join(plot_dir, 'summary_week.svg'))
    rose_fig.write_image(os.path.join(plot_dir, 'rose_week.svg'))
    heatmap_fig.write_image(os.path.join(plot_dir, 'heatmap_week.svg'))
    df_table.to_csv(os.path.join(csv_dir, 'congestion_times.csv'), index=False)

    return fig

def combined_congestion_summary_week(dam_net, imb_net, year, week, scenario_name):
    """
    Combined DAM vs Imbalance weekly summary:
      • Bar + table subplot of daily counts
      • Exact-time combined congestion chart
      • CSV of combined time-counts
    """
    # -- directories --
    plot_dir = os.path.join(PLOT_BASE, str(year), scenario_name, f'week_{week}')
    csv_dir  = os.path.join(CSV_BASE,  str(year), scenario_name, f'week_{week}')
    os.makedirs(plot_dir, exist_ok=True)
    os.makedirs(csv_dir,  exist_ok=True)

    # -- detect congestion events --
    load_series = load_weekly_load(year, week)
    dam_new = detect_new_congestion_week(dam_net, load_series)
    dam_al  = detect_already_congested_week(load_series)
    imb_new = detect_new_congestion_week(imb_net, load_series)
    imb_al  = detect_already_congested_week(load_series)

    # -- daily bar + table subplot --
    start, end = get_week_range(year, week)
    days = pd.date_range(start=start.normalize(),
                         end=(end - pd.Timedelta(days=1)).normalize(),
                         freq='D')
    counts = {
        'DAM_new':      dam_new.index.normalize().value_counts().reindex(days, fill_value=0).sort_index(),
        'DAM_already':  dam_al.index.normalize().value_counts().reindex(days, fill_value=0).sort_index(),
        'Imb_new':      imb_new.index.normalize().value_counts().reindex(days, fill_value=0).sort_index(),
        'Imb_already':  imb_al.index.normalize().value_counts().reindex(days, fill_value=0).sort_index(),
    }

    dam_cols = colors_crest(2)
    imb_cols = colors_flare(2)
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.6, 0.4],
        vertical_spacing=0.1,
        specs=[[{'type':'bar'}], [{'type':'table'}]]
    )
    fig.add_trace(go.Bar(
        name='DAM New',    x=days, y=counts['DAM_new'].values,    marker_color=dam_cols[0]
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        name='DAM Already',x=days, y=counts['DAM_already'].values,marker_color=dam_cols[1]
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        name='Imb New',    x=days, y=counts['Imb_new'].values,    marker_color=imb_cols[0]
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        name='Imb Already',x=days, y=counts['Imb_already'].values,marker_color=imb_cols[1]
    ), row=1, col=1)

    # build exact-time table for the subplot
    def tc(df): return pd.Series(df.index.time).value_counts()
    dtn, dta, itn, ita = tc(dam_new), tc(dam_al), tc(imb_new), tc(imb_al)
    times = sorted(set(dtn.index) | set(dta.index) | set(itn.index) | set(ita.index))
    dfT = pd.DataFrame({
        'time':        [t.strftime('%H:%M') for t in times],
        'DAM_new':     [dtn.get(t, 0) for t in times],
        'DAM_already': [dta.get(t, 0) for t in times],
        'Imb_new':     [itn.get(t, 0) for t in times],
        'Imb_already': [ita.get(t, 0) for t in times],
    })
    fig.add_trace(go.Table(
        header=dict(values=list(dfT.columns), fill_color='lightgrey'),
        cells=dict(values=[dfT[c] for c in dfT.columns])
    ), row=2, col=1)

    # finalize and save bar+table
    fig.update_layout(
        title=f'Week {week}, {year} – Combined Congestion Summary',
        barmode='group',
        height=800,
        margin=dict(t=50, b=50, l=50, r=50)
    )
    fig.write_image(os.path.join(plot_dir, 'combined_summary_week.svg'))

    # -- exact-time combined congestion chart --
    time_comb_fig = plot_time_of_day_exact_combined(dam_new, dam_al, imb_new, imb_al)
    time_comb_fig.update_layout(title=f'Week {week}, {year} – Exact-Time Combined Congestion')
    time_comb_fig.write_image(os.path.join(plot_dir, 'combined_time_exact.svg'))

    # -- CSV of combined times --
    dfT.to_csv(os.path.join(csv_dir, 'combined_congestion_times.csv'), index=False)

    return fig

def plot_group_week_summary(year, week, scenario_group, sub_scenarios):
    """
    Reads the per-run CSVs and creates four separate bar charts:
      • Mitigation events
      • Charging during already congested periods
      • New congestion events
      • Neutral charging events
    Legends are placed below each figure.
    """
    import os
    import pandas as pd
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go
    from utils.utils import colors_crest, colors_flare

    # 1) Collect metrics
    metrics = []
    for sub in sub_scenarios:
        name = sub["name"]
        row = {"scenario": name}
        for tag in ("DAM", "Imbalance"):
            folder = f"{name}_{tag}"
            base = os.path.join(
                CSV_BASE,
                str(year),
                folder,
                f"week_{week}"
            )
            ce = pd.read_csv(os.path.join(base, "congestion_event_times.csv"))
            neu = pd.read_csv(os.path.join(base, "neutral_charging_times.csv"))["count"].sum()

            row[f"{tag.lower()}_mitigation"]  = int(ce.loc[ce.event=="mitigation",   "count"].sum())
            row[f"{tag.lower()}_chg_already"] = int(ce.loc[ce.event=="chg_already",  "count"].sum())
            row[f"{tag.lower()}_new"]         = int(ce.loc[ce.event=="new",          "count"].sum())
            row[f"{tag.lower()}_neutral"]     = int(neu)
        metrics.append(row)

    df = pd.DataFrame(metrics).set_index("scenario")

    # 2) Define categories & colors
    cats = [
        ("mitigation",  "Mitigation events"),
        ("chg_already", "Charging During Congested Periods"),
        ("new",         "New congestion"),
        ("neutral",     "Neutral charging"),
    ]
    dam_col = colors_crest(1)[0]
    imb_col = colors_flare(1)[0]

    # 3) Ensure output dir
    out_dir = os.path.join(PLOT_BASE, str(year), scenario_group, f"week_{week}")
    os.makedirs(out_dir, exist_ok=True)
    figs = {}
    # 4) Build & save each figure
    for key, title in cats:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df.index,
            y=df[f"dam_{key}"],
            name="DAM",
            marker_color=dam_col
        ))
        fig.add_trace(go.Bar(
            x=df.index,
            y=df[f"imbalance_{key}"],
            name="Imbalance",
            marker_color=imb_col
        ))
        fig.update_layout(
            title=title,
            barmode="group",
            xaxis_tickangle=45,
            legend=dict(
                orientation="h",
                y=-0.2,
                x=0.5,
                xanchor="center"
            ),
            margin=dict(t=50, b=100, l=50, r=50),
            height=500,
        )
        # save
        filename = f"group_{key}.svg"
        fig.write_image(os.path.join(out_dir, filename))
        figs[key] = fig
    # Optionally return nothing or list of figs
    return figs

def plot_group_week_events_heatmaps(year, week, scenario_group, sub_scenarios):
    """
    Reads per-run CSVs for each sub-scenario and generates four separate heatmaps for:
      1) Mitigation events
      2) Charging during already congested periods
      3) New congestion events
      4) Neutral charging events
    Each heatmap has scenarios on the y-axis, times on the x-axis, and counts as color intensity.
    Saves each as an individual SVG in plots/congestion_week/<year>/<scenario_group>/week_<week>/.
    """
    import os
    import pandas as pd
    import plotly.graph_objects as go

    # Helper to collect counts per event
    def collect_counts(event_key, filter_fn):
        counts_map = {}
        for sub in sub_scenarios:
            name = sub['name']
            total = {}
            for tag in ('DAM','Imbalance'):
                base = os.path.join(CSV_BASE, str(year), f"{name}_{tag}", f"week_{week}")
                ev_file = os.path.join(base, 'congestion_event_times.csv')
                if os.path.exists(ev_file) and filter_fn is not None:
                    df = pd.read_csv(ev_file)
                    df_ev = df[filter_fn(df)]
                    series = df_ev.groupby('time')['count'].sum()
                    for t, c in series.items():
                        total[t] = total.get(t, 0) + int(c)
                if event_key == 'neutral':
                    neut_file = os.path.join(base, 'neutral_charging_times.csv')
                    if os.path.exists(neut_file):
                        df2 = pd.read_csv(neut_file)
                        for _, row in df2.iterrows():
                            t = row['time']; c = int(row['count'])
                            total[t] = total.get(t,0) + c
            if total:
                counts_map[name] = pd.Series(total)
        return counts_map

    # Define filters for three event types; neutral uses separate CSV
    filters = {
        'mitigation': lambda df: df['event']=='mitigation',
        'chg_already': lambda df: df['event']=='chg_already',
        'new': lambda df: df['event']=='new',
        'neutral': None
    }
    # Collect data for all four types
    data_ev = {ev: collect_counts(ev, filters.get(ev)) for ev in filters.keys()}

    # Determine all times across events and scenarios
    all_times = sorted(
        {t for counts_map in data_ev.values() for series in counts_map.values() for t in series.index},
        key=lambda x: pd.to_datetime(x, format='%H:%M')
    )
    scenarios = [sub['name'] for sub in sub_scenarios]

    # Ensure output directory
    out_dir = os.path.join(PLOT_BASE, str(year), scenario_group, f"week_{week}")
    os.makedirs(out_dir, exist_ok=True)

    # Generate individual heatmaps
    figs = {}
    for ev, counts_map in data_ev.items():
        # Build DataFrame
        df = pd.DataFrame({
            name: counts_map.get(name, pd.Series(dtype=int)).reindex(all_times, fill_value=0)
            for name in scenarios
        }, index=all_times)
        # Create heatmap
        fig = go.Figure(go.Heatmap(
            z=df.T.values,
            x=df.index,
            y=df.columns,
            colorscale='Reds',
            colorbar=dict(title='Count')
        ))
        fig.update_layout(
            title=f"{ev.replace('_',' ').title()} Heatmap — {scenario_group} Week {week}, {year}",
            xaxis_title='Time (HH:MM)',
            yaxis_title='Scenario',
            xaxis=dict(tickangle=45),
            height=500,
            margin=dict(t=80, b=100, l=120, r=50)
        )
        # Save as separate SVG
        fig.write_image(os.path.join(out_dir, f"heatmap_{ev}.svg"))
        figs[ev] = fig

    return figs


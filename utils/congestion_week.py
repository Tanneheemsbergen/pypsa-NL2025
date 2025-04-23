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
    return p.clip(upper=0).abs()


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
    return df_week["load_mw"]


def detect_new_congestion_week(network, load_series, capacity_limit=CAPACITY_LIMIT_MW):
    charging = get_storage_charging(network)
    df = pd.DataFrame({'load_mw': load_series}).join(
        charging.rename('charging_mw'), how='inner'
    ).fillna(0)
    df['combined'] = df['load_mw'] + df['charging_mw']
    return df[(df['load_mw'] < capacity_limit) & (df['combined'] > capacity_limit)]


def detect_already_congested_week(load_series, capacity_limit=CAPACITY_LIMIT_MW):
    df = load_series.to_frame(name='load_mw')
    return df[df['load_mw'] > capacity_limit]


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


def plot_time_of_day_exact(new_df, al_df):
    """
    Bar chart of congestion counts at each specific time (HH:MM).
    """
    new_tc = pd.Series(new_df.index.time).value_counts().sort_index()
    al_tc = pd.Series(al_df.index.time).value_counts().sort_index()
    times = sorted(set(new_tc.index) | set(al_tc.index))
    labels = [t.strftime('%H:%M') for t in times]
    new_vals = [new_tc.get(t, 0) for t in times]
    al_vals = [al_tc.get(t, 0) for t in times]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels,
            y=new_vals,
            name='New',
            marker_color=colors_crest(1)[0]
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=al_vals,
            name='Already',
            marker_color=colors_flare(1)[0]
        )
    )
    fig.update_layout(
        barmode='group',
        title='Congestion by Exact Time',
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


def congestion_summary_week(network, year, week):
    """
    Single-network summary: bar+table + rose + heatmap + exact-time.
    """
    load_series = load_weekly_load(year, week)
    df_new = detect_new_congestion_week(network, load_series)
    df_al = detect_already_congested_week(load_series)

    # daily & table
    start, end = get_week_range(year, week)
    days = pd.date_range(start=start.normalize(), end=(end - pd.Timedelta(days=1)).normalize(), freq='D')
    new_counts = df_new.index.normalize().value_counts().reindex(days, fill_value=0).sort_index()
    al_counts = df_al.index.normalize().value_counts().reindex(days, fill_value=0).sort_index()
    times = sorted(set(pd.Series(df_new.index.time).value_counts().index) | set(pd.Series(df_al.index.time).value_counts().index))
    df_table = pd.DataFrame({
        'time': [t.strftime('%H:%M') for t in times],
        'new': [pd.Series(df_new.index.time).value_counts().get(t, 0) for t in times],
        'already': [pd.Series(df_al.index.time).value_counts().get(t, 0) for t in times]
    })
    df_table = df_table[(df_table['new'] > 0) | (df_table['already'] > 0)]

    fig = make_subplots(rows=2, cols=1, row_heights=[0.6, 0.4], vertical_spacing=0.1,
                        specs=[[{'type': 'bar'}], [{'type': 'table'}]])
    fig.add_trace(go.Bar(name='New', x=days, y=new_counts.values), row=1, col=1)
    fig.add_trace(go.Bar(name='Already', x=days, y=al_counts.values), row=1, col=1)
    fig.add_trace(go.Table(
        header=dict(values=list(df_table.columns), fill_color='lightgrey'),
        cells=dict(values=[df_table[c] for c in df_table.columns])
    ), row=2, col=1)
    fig.update_layout(title=f'Week {week}, {year} Congestion Summary', barmode='group', height=700)

    # rose chart
    rose_fig = plot_period_polar(df_new, df_al)
    rose_fig.show()
    # heatmap
    heatmap_fig = plot_period_heatmap(df_new, df_al, year, week)
    heatmap_fig.show()
    # exact-time
    time_fig = plot_time_of_day_exact(df_new, df_al)
    time_fig.show()

    return fig


def combined_congestion_summary_week(dam_net, imb_net, year, week):
    """
    Combined DAM vs Imbalance weekly: bar+table + rose + heatmap + exact-time combined.
    """
    load_series = load_weekly_load(year, week)
    dam_new = detect_new_congestion_week(dam_net, load_series)
    dam_al = detect_already_congested_week(load_series)
    imb_new = detect_new_congestion_week(imb_net, load_series)
    imb_al = detect_already_congested_week(load_series)

    # daily counts
    start, end = get_week_range(year, week)
    days = pd.date_range(start=start.normalize(), end=(end - pd.Timedelta(days=1)).normalize(), freq='D')
    counts = {
        'DAM_new': dam_new.index.normalize().value_counts().reindex(days, fill_value=0).sort_index(),
        'DAM_already': dam_al.index.normalize().value_counts().reindex(days, fill_value=0).sort_index(),
        'Imb_new': imb_new.index.normalize().value_counts().reindex(days, fill_value=0).sort_index(),
        'Imb_already': imb_al.index.normalize().value_counts().reindex(days, fill_value=0).sort_index()
    }

    dam_cols = colors_crest(2)
    imb_cols = colors_flare(2)
    fig = make_subplots(rows=2, cols=1, row_heights=[0.6, 0.4], vertical_spacing=0.1,
                        specs=[[{'type': 'bar'}], [{'type': 'table'}]])
    fig.add_trace(go.Bar(name='DAM New', x=days, y=counts['DAM_new'].values, marker_color=dam_cols[0]), row=1, col=1)
    fig.add_trace(go.Bar(name='DAM Already', x=days, y=counts['DAM_already'].values, marker_color=dam_cols[1]), row=1, col=1)
    fig.add_trace(go.Bar(name='Imb New', x=days, y=counts['Imb_new'].values, marker_color=imb_cols[0]), row=1, col=1)
    fig.add_trace(go.Bar(name='Imb Already', x=days, y=counts['Imb_already'].values, marker_color=imb_cols[1]), row=1, col=1)

    # table of exact times combined
    def tc(df): return pd.Series(df.index.time).value_counts()
    dtn = tc(dam_new); dta = tc(dam_al); itn = tc(imb_new); ita = tc(imb_al)
    times = sorted(set(dtn.index) | set(dta.index) | set(itn.index) | set(ita.index))
    dfT = pd.DataFrame({
        'time': [t.strftime('%H:%M') for t in times],
        'DAM_new': [dtn.get(t, 0) for t in times],
        'DAM_already': [dta.get(t, 0) for t in times],
        'Imb_new': [itn.get(t, 0) for t in times],
        'Imb_already': [ita.get(t, 0) for t in times]
    })
    fig.add_trace(go.Table(
        header=dict(values=list(dfT.columns), fill_color='lightgrey'),
        cells=dict(values=[dfT[c] for c in dfT.columns])
    ), row=2, col=1)
    fig.update_layout(title=f'Week {week}, {year} – DAM vs Imbalance Congestion', barmode='group', height=800)

    # rose for each
    rose_dam = plot_period_polar(dam_new, dam_al)
    rose_dam.update_layout(title=f'Week {week} DAM Congestion Rose')
    rose_dam.show()
    rose_imb = plot_period_polar(imb_new, imb_al)
    rose_imb.update_layout(title=f'Week {week} Imbalance Congestion Rose')
    rose_imb.show()
    # heatmap for each
    heatmap_dam = plot_period_heatmap(dam_new, dam_al, year, week)
    heatmap_dam.update_layout(title=f'Week {week} DAM Congestion Heatmap')
    heatmap_dam.show()
    heatmap_imb = plot_period_heatmap(imb_new, imb_al, year, week)
    heatmap_imb.update_layout(title=f'Week {week} Imbalance Congestion Heatmap')
    heatmap_imb.show()
    # exact-time combined
    time_comb_fig = plot_time_of_day_exact_combined(dam_new, dam_al, imb_new, imb_al)
    time_comb_fig.show()

    return fig

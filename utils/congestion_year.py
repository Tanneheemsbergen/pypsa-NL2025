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

# Directory to save CSVs
RESULTS_DIR = "results"


def get_storage_charging(network, store=None):
    """
    Returns a pandas Series of battery charging load (MW) from network.stores_t.p.
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


def load_yearly_load(year):
    """
    Reads the yearly load CSV from config and returns a Series of 'load_mw' indexed by datetime.
    """
    config = load_config()
    load_file = config['paths']['load']
    df = pd.read_csv(load_file, parse_dates=['datetime'])
    # Filter exact 365-day window
    start, end = get_year_range(year)
    df = df[(df['datetime'] >= start) & (df['datetime'] < end)].copy()
    df.set_index('datetime', inplace=True)
    df.rename(columns={'belasting': 'load_mw'}, inplace=True)
    return df['load_mw']


def detect_new_congestion_year(network, load_series, capacity_limit):
    """
    Identify intervals where load < limit but load+charging > limit.
    Returns DataFrame with columns ['load_mw','charging_mw','combined_mw'].
    """
    charging = get_storage_charging(network)
    df = pd.DataFrame({'load_mw': load_series}).join(
        charging.rename('charging_mw'), how='inner'
    ).fillna(0)
    df['combined_mw'] = df['load_mw'] + df['charging_mw']
    return df[(df['load_mw'] < capacity_limit) & (df['combined_mw'] > capacity_limit)]


def detect_already_congested_year(load_series, capacity_limit):
    """
    Identify intervals where load > limit. Returns DataFrame with column 'load_mw'.
    """
    df = load_series.to_frame(name='load_mw')
    return df[df['load_mw'] > capacity_limit]


def congestion_summary_year(network, year):
    """
    Single-network yearly summary: bar chart of monthly event counts
    and a table of time-of-day counts.

    Usage:
        fig = congestion_summary_year(solved_network, year)
    """
    # Prepare
    os.makedirs(RESULTS_DIR, exist_ok=True)
    load_series = load_yearly_load(year)
    # Determine capacity limit from config or default
    config = load_config()
    cap_limit = config.get('capacity_limit_mw') or (config.get('capacity_nominal_mw',11.2) * config.get('capacity_factor',0.85))

    # Detect
    df_new = detect_new_congestion_year(network, load_series, cap_limit)
    df_al  = detect_already_congested_year(load_series, cap_limit)

    # Save CSVs
    base = f"{year}"
    df_new.to_csv(os.path.join(RESULTS_DIR, f"{base}_new_congestion.csv"))
    df_al.to_csv(os.path.join(RESULTS_DIR, f"{base}_already_congested.csv"))

    # Monthly counts
    months = list(range(1,13))
    new_counts = df_new.index.month.value_counts().reindex(months, fill_value=0).sort_index()
    al_counts  = df_al.index.month.value_counts().reindex(months, fill_value=0).sort_index()

    # Time-of-day counts
    new_times = df_new.index.time
    al_times  = df_al.index.time
    new_tc = pd.Series(new_times).value_counts().sort_index()
    al_tc  = pd.Series(al_times).value_counts().sort_index()
    all_times = sorted(set(new_tc.index)|set(al_tc.index))
    df_tbl = pd.DataFrame({
        'time': [t.strftime('%H:%M') for t in all_times],
        'new': [new_tc.get(t,0) for t in all_times],
        'already': [al_tc.get(t,0) for t in all_times]
    })
    df_tbl = df_tbl[(df_tbl['new']>0)|(df_tbl['already']>0)]

    # Colors
    new_color, = colors_crest(1)
    al_color,  = colors_flare(1)

    # Build figure
    fig = make_subplots(rows=2, cols=1, row_heights=[0.6,0.4], vertical_spacing=0.1,
                        specs=[[{'type':'bar'}],[{'type':'table'}]])
    # Bar traces
    fig.add_trace(go.Bar(name='New Congestion',     x=calendar.month_abbr[1:], y=new_counts.values, marker_color=new_color), row=1, col=1)
    fig.add_trace(go.Bar(name='Already Congested',  x=calendar.month_abbr[1:], y=al_counts.values,  marker_color=al_color),  row=1, col=1)
    # Table
    fig.add_trace(go.Table(
        header=dict(values=list(df_tbl.columns), fill_color='lightgrey'),
        cells=dict(values=[df_tbl[c] for c in df_tbl.columns])
    ), row=2, col=1)
    fig.update_layout(title=f'Year {year} Congestion Summary', barmode='group', height=800)
    return fig


def combined_congestion_summary_year(dam_net, imb_net, year):
    """
    Dual-network yearly summary: bar chart and table for DAM vs Imbalance.

    Usage:
        fig = combined_congestion_summary_year(DAM_net, Imb_net, year)
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    load_series = load_yearly_load(year)
    # capacity
    config = load_config()
    cap = config.get('capacity_limit_mw') or (config.get('capacity_nominal_mw',11.2) * config.get('capacity_factor',0.85))

    # Detect
    dam_new = detect_new_congestion_year(dam_net, load_series, cap)
    dam_al  = detect_already_congested_year(load_series, cap)
    imb_new = detect_new_congestion_year(imb_net, load_series, cap)
    imb_al  = detect_already_congested_year(load_series, cap)

    # Monthly counts
    months = list(range(1,13))
    counts = {
        'DAM_new': dam_new.index.month.value_counts().reindex(months, fill_value=0).sort_index(),
        'DAM_already': dam_al.index.month.value_counts().reindex(months, fill_value=0).sort_index(),
        'Imb_new': imb_new.index.month.value_counts().reindex(months, fill_value=0).sort_index(),
        'Imb_already': imb_al.index.month.value_counts().reindex(months, fill_value=0).sort_index()
    }
    # Time-of-day
    def tc(df): return pd.Series(df.index.time).value_counts()
    dtn = tc(dam_new); dta = tc(dam_al);
    itn = tc(imb_new); ita = tc(imb_al);
    times = sorted(set(dtn.index)|set(dta.index)|set(itn.index)|set(ita.index))
    dfT = pd.DataFrame({
        'time':[t.strftime('%H:%M') for t in times],
        'DAM_new':[dtn.get(t,0) for t in times],
        'DAM_already':[dta.get(t,0) for t in times],
        'Imb_new':[itn.get(t,0) for t in times],
        'Imb_already':[ita.get(t,0) for t in times]
    })
    dfT = dfT[dfT[['DAM_new','DAM_already','Imb_new','Imb_already']].sum(axis=1)>0]

    # Colors
    dam_cols = colors_crest(2)
    imb_cols = colors_flare(2)

    # Figure
    fig = make_subplots(rows=2, cols=1, row_heights=[0.6,0.4], vertical_spacing=0.1,
                        specs=[[{'type':'bar'}],[{'type':'table'}]])
    mon_abbr = calendar.month_abbr[1:]
    fig.add_trace(go.Bar(name='DAM New',     x=mon_abbr, y=counts['DAM_new'].values,    marker_color=dam_cols[0]),    row=1, col=1)
    fig.add_trace(go.Bar(name='DAM Already', x=mon_abbr, y=counts['DAM_already'].values, marker_color=dam_cols[1]),    row=1, col=1)
    fig.add_trace(go.Bar(name='Imb New',     x=mon_abbr, y=counts['Imb_new'].values,    marker_color=imb_cols[0]),    row=1, col=1)
    fig.add_trace(go.Bar(name='Imb Already', x=mon_abbr, y=counts['Imb_already'].values, marker_color=imb_cols[1]), row=1, col=1)
    # Table
    fig.add_trace(go.Table(
        header=dict(values=list(dfT.columns), fill_color='lightgrey'),
        cells=dict(values=[dfT[c] for c in dfT.columns])
    ), row=2, col=1)
    fig.update_layout(title=f'Year {year} DAM vs Imbalance Congestion', barmode='group', height=900)
    return fig

def plot_congestion_time_rose(network, year):
    """
    Plot a polar 'rose' diagram of congestion events by time-of-day.
    
    - new congestion in one color
    - already-congested in another
    """
    # apply global style
    set_plot_style()

    # load data & capacity
    load_series = load_yearly_load(year)
    cfg = load_config()
    cap = cfg.get("capacity_limit_mw") or (cfg.get("capacity_nominal_mw",11.2)*cfg.get("capacity_factor",0.85))

    # detect events
    df_new = detect_new_congestion_year(network, load_series, cap)
    df_al  = detect_already_congested_year(load_series, cap)

    # count occurrences by time-of-day
    new_counts = pd.Series(df_new.index.time).value_counts().sort_index()
    al_counts  = pd.Series(df_al.index.time).value_counts().sort_index()

    # map times to fractional hours → degrees (360°/24h = 15° per hour)
    hrs_new   = [t.hour + t.minute/60 for t in new_counts.index]
    hrs_al    = [t.hour + t.minute/60 for t in al_counts.index]
    theta_new = [h * 15 for h in hrs_new]
    theta_al  = [h * 15 for h in hrs_al]

    # pick two distinct but harmonious colors
    c_new = colors_crest(1)[0]
    c_al  = colors_flare(1)[0]

    # build polar chart
    fig = go.Figure()
    fig.add_trace(go.Barpolar(
        r=new_counts.values,
        theta=theta_new,
        name="New Congestion",
        marker_color=c_new,
        opacity=0.75
    ))
    fig.add_trace(go.Barpolar(
        r=al_counts.values,
        theta=theta_al,
        name="Already Congested",
        marker_color=c_al,
        opacity=0.75
    ))

    fig.update_layout(
        template="simple_white",
        title=f"Year {year} Congestion Times of Day",
        polar=dict(
            angularaxis=dict(
                rotation=90,          # start at midnight at top
                direction="clockwise",
                tickmode="array",
                tickvals=list(range(0,360,60)),
                ticktext=["00:00","04:00","08:00","12:00","16:00","20:00"]
            ),
            radialaxis=dict(showticklabels=True, title="Count")
        ),
        legend=dict(orientation="h", y=-0.1),
        margin=dict(l=50, r=50, t=80, b=50)
    )

    return fig
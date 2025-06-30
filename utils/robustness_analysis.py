import os
import pandas as pd
import numpy as np
from scipy.stats import gaussian_kde
import plotly.graph_objects as go
from utils.set_plot_style import set_plot_style
from utils.utils import colors_crest, colors_flare
import plotly.io as pio

# ───── CONFIGURATION ──────────────────────────────────────────────────────────
YEARS = list(range(2015, 2025))
SCENARIO_GROUPS = [
    "Value Stacking DAM + Imbalance + PV",
    "Value Stacking DAM + Imbalance + PV + Time Constraints",
    # "Value Stacking DAM + Imbalance + PV + Zaandijk",
    # "Value Stacking DAM + Imbalance + PV + Time Constraints + Zaandijk",
    # "Value Stacking DAM + Imbalance + PV + Kwadijk",
    # "Value Stacking DAM + Imbalance + PV + Time Constraints + Kwadijk",
    # "Value Stacking DAM + Imbalance + PV + Schaep",
    # "Value Stacking DAM + Imbalance + PV + Time Constraints + Schaep"
]
SCENARIO_NAMES = ["Trade_0_100_Imbalance", "Trade_100_0_DAM"]

BASE_DIR = "results/congestion_year"
PLOT_DIR = "plots/robustness"
os.makedirs(PLOT_DIR, exist_ok=True)

# Four “combined” categories (scenario_name, has_TC_flag, label)
CATEGORIES = [
    ("Trade_100_0_DAM",       True, "DAM + TC"),
     ("Trade_100_0_DAM",      False, "DAM (no TC)"),
     ("Trade_0_100_Imbalance",  True, "Imb + TC"),
    ("Trade_0_100_Imbalance", False, "Imb (no TC)"),
]

set_plot_style()

crest_shades = colors_crest(2)   # returns a list of 2 distinct blues
flare_shades = colors_flare(2)   # returns a list of 2 distinct oranges

# Interleave them so we have [crest1, flare1, crest2, flare2]
COLOR_PALETTE = [
    crest_shades[0],
    flare_shades[0],
    crest_shades[1],
    flare_shades[1],
]
# ───── STEP 1: COLLECT EVENT COUNTS ─────────────────────────────────────────────
def collect_event_counts():
    """
    Walk through:
      results/congestion_year/{year}/{scenario_group}/{scenario_name}/event_summary_counts.csv
    and return a DataFrame with columns:
      ['weather_year','scenario_group','scenario_name',
       'already_congested','new_congestion','charging_during_congested',
       'neutral_charging','mitigation']
    """
    records = []
    for year in YEARS:
        for grp in SCENARIO_GROUPS:
            for scen in SCENARIO_NAMES:
                csv_path = os.path.join(
                    BASE_DIR, str(year), grp, scen, "event_summary_counts.csv"
                )
                if not os.path.isfile(csv_path):
                    continue

                df_counts = pd.read_csv(csv_path, index_col="event")
                records.append({
                    "weather_year": year,
                    "scenario_group": grp,
                    "scenario_name": scen,
                    "already_congested": df_counts.loc["already_congested","count"]
                                          if "already_congested" in df_counts.index else 0,
                    "new_congestion": df_counts.loc["new_congestion","count"]
                                          if "new_congestion" in df_counts.index else 0,
                    "charging_during_congested": df_counts.loc["charging_during_congested","count"]
                                          if "charging_during_congested" in df_counts.index else 0,
                    "neutral_charging": df_counts.loc["neutral_charging","count"]
                                          if "neutral_charging" in df_counts.index else 0,
                    "mitigation": df_counts.loc["mitigation","count"]
                                          if "mitigation" in df_counts.index else 0
                })
    return pd.DataFrame(records)


# Build “all_df” and add “new_plus_charge”
all_df = collect_event_counts()
all_df["new_plus_charge"] = (
    all_df["new_congestion"] + all_df["charging_during_congested"]
)
print(f"Collected {len(all_df)} records total.")


# ───── STEP 2: PREPARE LONG‐FORM DATA FOR EACH METRIC ──────────────────────────
def build_long_df(metric_name):
    """
    Return a DataFrame with columns ['category', metric_name],
    where 'category' is one of the four labels in CATEGORIES.
    """
    rows = []
    for (scn, has_tc, label) in CATEGORIES:
        mask = (
            (all_df["scenario_name"] == scn)
            & (all_df["scenario_group"].str.contains("Time Constraints") == has_tc)
        )
        subset_series = all_df.loc[mask, metric_name]
        for val in subset_series.values:
            rows.append({"category": label, metric_name: val})
    return pd.DataFrame(rows)


df_mit_long = build_long_df("mitigation")
# Show all “mitigation” numbers that ended up in the “DAM + TC” category
dam_no_tc_vals = df_mit_long.loc[ df_mit_long["category"] == "Imb (no TC)", "mitigation" ]
print("DAM (no TC) mitigation values (all years & groups without TC):\n", dam_no_tc_vals.values)
dam_no_tc_vals = df_mit_long.loc[ df_mit_long["category"] == "Imb + TC", "mitigation" ]
print("DAM (no TC) mitigation values (all years & groups without TC):\n", dam_no_tc_vals.values)
dam_no_tc_vals = df_mit_long.loc[ df_mit_long["category"] == "DAM (no TC)", "mitigation" ]
print("DAM (no TC) mitigation values (all years & groups without TC):\n", dam_no_tc_vals.values)
dam_no_tc_vals = df_mit_long.loc[ df_mit_long["category"] == "DAM + TC", "mitigation" ]
print("DAM (no TC) mitigation values (all years & groups without TC):\n", dam_no_tc_vals.values)

df_npq_long = build_long_df("new_plus_charge")


# ───── STEP 3: KDE UTILITY (SMOOTH, UNTRIMMED) ─────────────────────────────────
def compute_kde(series, bw=0.5):
    """
    Given a pandas Series of raw counts, return a fitted scipy GaussianKDE object,
    using bandwidth = bw. Returns None if there are fewer than 2 data points.
    """
    data = series.dropna().values
    if len(data) < 2:
        return None
    return gaussian_kde(data, bw_method=bw)


# ───── STEP 4: IMPROVED PLOTLY RIDGELINE (COMMON X‐GRID) ─────────────────────────
def plot_ridgeline_plotly_smooth(
    df_long,
    metric_name,
    title_text,
    x_axis_title,
    output_filename_svg,
    forced_x_range=None,   # If None, we'll compute ±10% margin from data
    bw=0.5,
    num_points=2000
):
    """
    Draws a ridgeline/joy‐plot using Plotly, but:
      • Evaluates every category’s KDE on one common x‐grid of length num_points.
      • Ensures each tail smoothly goes to zero across the same domain.
      • Saves as SVG.

    Parameters:
      - df_long:           DataFrame with columns ['category', metric_name]
      - metric_name:       e.g. "mitigation" or "new_plus_charge"
      - title_text:        String title to display at top
      - x_axis_title:      String label for x‐axis
      - output_filename_svg: the SVG filename under PLOT_DIR
      - forced_x_range:    If (x0, x1), use that as the domain. If None, auto‐compute ±10% from data.
      - bw:                KDE bandwidth
      - num_points:        Number of points in the common x‐grid (larger → smoother curves)
    """

    # 1) Build one scipy.stats.gaussian_kde object per category (or None if too few points)
    kde_objs = {}
    for (_, _, label) in CATEGORIES:
        vals = df_long.loc[df_long["category"] == label, metric_name]
        kde_objs[label] = compute_kde(vals, bw=bw)

    # 2) Determine the common x_min, x_max:
    if forced_x_range is not None:
        x_min, x_max = forced_x_range
    else:
        # Auto‐compute: collect all raw values across all categories:
        all_vals = df_long[metric_name].dropna().values
        if len(all_vals) < 2:
            # Fallback to [0,1] if there’s no data
            x_min, x_max = 0.0, 1.0
        else:
            data_min = all_vals.min()
            data_max = all_vals.max()
            span = data_max - data_min
            x_min = data_min - 0.1 * span
            x_max = data_max + 0.1 * span

    # 3) Build a single common x‐grid from x_min→x_max
    x_common = np.linspace(x_min, x_max, num_points)

    # 4) Evaluate each KDE on that grid → store in y_common_dict. Track global max_density.
    y_common_dict = {}
    max_density = 0.0
    for (_, _, label) in CATEGORIES:
        kde = kde_objs[label]
        if kde is None:
            y_common = np.zeros_like(x_common)
        else:
            y_common = kde(x_common)
            # Clip any tiny negative noise to zero:
            y_common = np.maximum(y_common, 0.0)

        y_common_dict[label] = y_common
        if y_common.max() > max_density:
            max_density = y_common.max()

    # 5) Decide on vertical offsets so ridges overlap ≈40% of their max height:
    vertical_step = max_density * 0.6
    offsets = {label: idx * vertical_step for idx, (_, _, label) in enumerate(CATEGORIES)}

    # 6) Build the Plotly figure
    fig = go.Figure()

    for i, (_, _, label) in enumerate(CATEGORIES):
        baseline = offsets[label]
        y_baseline = y_common_dict[label] + baseline

        # (a) Filled KDE polygon (top edge = baseline+y, bottom = baseline)
        fig.add_trace(
            go.Scatter(
                x=np.concatenate([x_common, x_common[::-1]]),
                y=np.concatenate([y_baseline, np.full_like(x_common, baseline)]),
                fill="toself",
                fillcolor=COLOR_PALETTE[i],
                line=dict(color="white", width=1.5),
                opacity=0.8,
                name=label,
                showlegend=False,
            )
        )

        # (b) Thin baseline line across the entire domain
        fig.add_trace(
            go.Scatter(
                x=[x_min, x_max],
                y=[baseline, baseline],
                mode="lines",
                line=dict(color=COLOR_PALETTE[i], width=1),
                showlegend=False,
            )
        )

    # 7) Add one “dummy” trace per category so the legend shows 4 colored markers
    # for i, (_, _, label) in enumerate(CATEGORIES):
    #     fig.add_trace(
    #         go.Scatter(
    #             x=[None],
    #             y=[None],
    #             mode="markers",
    #             marker=dict(size=10, color=COLOR_PALETTE[i]),
    #             name=label
    #         )
    #     )

    # 8) Tidy up the layout: remove numeric y‐ticks, replace with category labels
    fig.update_layout(
        title=dict(
            text=title_text,
            x=0.5,
            y=0.95,
            font=dict(size=16)
        ),
        xaxis=dict(
            title=x_axis_title,
            range=[x_min, x_max],
            showgrid=False,
            zeroline=False,
            tickfont=dict(size=12)
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=[offsets[label] for (_, _, label) in CATEGORIES],
            ticktext=[label for (_, _, label) in CATEGORIES],
            showgrid=False,
            zeroline=False,
            showline=True,
            linecolor="black",
            linewidth=1,
            tickfont=dict(size=12),
        ),
        plot_bgcolor="white",
        margin=dict(l=140, r=50, t=100, b=50),
        legend=dict(
            title="Scenario",
            orientation="v",
            x=1.02,
            y=1.0,
            yanchor="top",
            font=dict(size=12),
        )
    )

    # 9) Save as SVG via Kaleido
    out_path_svg = os.path.join(PLOT_DIR, output_filename_svg)
    fig.write_image(out_path_svg)
    print(f"Saved Plotly ridgeline as SVG to: {out_path_svg}")

    # (Optional) If running interactively:
    # fig.show()


# ───── MAIN: DRAW BOTH “MITIGATION” AND “NEW + CHARGING” RIDGELINES ─────────────
if __name__ == "__main__":
    # (a) Mitigation ridgeline → save as SVG
    plot_ridgeline_plotly_smooth(
        df_long=df_mit_long,
        metric_name="mitigation",
        title_text="Mitigation Distribution",
        x_axis_title="Mitigation (counts)",
        output_filename_svg="mitigation_ridgeline_plotly.svg",
        forced_x_range=(0, 500),
        bw=0.5,
        num_points=2000
    )

    # (b) New + Charging ridgeline → save as SVG
    plot_ridgeline_plotly_smooth(
        df_long=df_npq_long,
        metric_name="new_plus_charge",
        title_text="New + Already Distribution",
        x_axis_title="New + Already (counts)",
        output_filename_svg="new_plus_charge_ridgeline_plotly.svg",
        forced_x_range=(0, 500),  # Exactly 0→500 on the x‐axis
        bw=0.5,
        num_points=2000
    )

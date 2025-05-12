# %%
import pandas as pd
import numpy as np
import os
import networkx as nx
from core.network import create_network
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns
from utils.set_plot_style import set_plot_style
from utils.utils import colors_crest, colors_flare

# Ensure output directory exists
os.makedirs('plots/generic_plot', exist_ok=True)

# Apply global Plotly style
set_plot_style()

file_path = "data/raw_data/SS_Monnickendam.csv"

# %%
# Load data and compute mean load
df = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df.columns = df.columns.str.lower()
df = df.sort_values(by="datum_tijd")
df["datum_tijd"] = df["datum_tijd"] + pd.DateOffset(years=1)
mean_load = df["belasting"].mean()

crest_color = colors_crest(1)[0]
flare_color = colors_flare(1)[0]

# Plot load profile
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df["datum_tijd"],
    y=df["belasting"],
    mode='lines',
    line=dict(color=crest_color, width=1),
    name="Load Level"
))
fig.add_trace(go.Scatter(
    x=[df["datum_tijd"].min(), df["datum_tijd"].max()],
    y=[mean_load, mean_load],
    mode='lines',
    line=dict(color=flare_color, dash='dash', width=1.5),
    name=f"Mean Load = {mean_load:.2f} kW"
))
fig.update_layout(
    xaxis_title="Date",
    yaxis_title="Load (kW)",
    title="Load Profile with Mean Load"
)
fig.write_image('plots/generic_plot/load_profile.svg')
fig.show()

# %%
# Congestion plot for year 2030
df2 = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df2.columns = df2.columns.str.lower()
df2 = df2[df2["jaar"] == 2030].sort_values(by="datum_tijd")
df2["datum_tijd"] = df2["datum_tijd"] + pd.DateOffset(years=7)

capacity_limit = 11.2 * 0.85 * 1000  # kW
above = df2["belasting"] > capacity_limit
exceed_count = above.sum()
exceed_hours = exceed_count * 15 / 60
print(f"Number of times load exceeds capacity: {exceed_count} (≈ {exceed_hours:.2f} hours)")

fig2 = go.Figure()
# full baseline
fig2.add_trace(go.Scatter(
    x=df2["datum_tijd"],
    y=df2["belasting"],
    mode='lines',
    line=dict(color=crest_color, width=1),
    name="Load Level"
))
# red overlay connecting just the overload points
over_df = df2.loc[above]
fig2.add_trace(go.Scatter(
    x=over_df["datum_tijd"],
    y=over_df["belasting"],
    mode='lines',
    line=dict(color='red', width=2),
    name="Over Capacity"
))
# capacity limit line
fig2.add_trace(go.Scatter(
    x=[df2["datum_tijd"].min(), df2["datum_tijd"].max()],
    y=[capacity_limit, capacity_limit],
    mode='lines',
    line=dict(color=flare_color, dash='dash', width=1.5),
    name=f"Capacity Limit = {capacity_limit:.0f} kW"
))
fig2.update_layout(
    xaxis_title="Date",
    yaxis_title="Load (kW)",
    title="Load Profile for MRS Monnickendam (2030)"
)
fig2.write_image('plots/generic_plot/congestion_2030.svg')
fig2.show()

# %%
# Congestion plot for year 2024
df3 = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df3.columns = df3.columns.str.lower()
df3 = df3[df3["jaar"] == 2024].sort_values(by="datum_tijd")
df3["datum_tijd"] = df3["datum_tijd"] + pd.DateOffset(years=7)

above3 = df3["belasting"] > capacity_limit
exceed_count3 = above3.sum()
exceed_hours3 = exceed_count3 * 15 / 60
print(f"Number of times load exceeds capacity: {exceed_count3} (≈ {exceed_hours3:.2f} hours)")

fig3 = go.Figure()
# full baseline
fig3.add_trace(go.Scatter(
    x=df3["datum_tijd"],
    y=df3["belasting"],
    mode='lines',
    line=dict(color=crest_color, width=1),
    name="Load Level"
))
# red overlay
over3 = df3.loc[above3]
fig3.add_trace(go.Scatter(
    x=over3["datum_tijd"],
    y=over3["belasting"],
    mode='lines',
    line=dict(color='red', width=2),
    name="Over Capacity"
))
# capacity limit
fig3.add_trace(go.Scatter(
    x=[df3["datum_tijd"].min(), df3["datum_tijd"].max()],
    y=[capacity_limit, capacity_limit],
    mode='lines',
    line=dict(color=flare_color, dash='dash', width=1.5),
    name=f"Capacity Limit = {capacity_limit:.0f} kW"
))
fig3.update_layout(
    xaxis_title="Date",
    yaxis_title="Load (kW)",
    title="Load Profile for MRS Monnickendam (2024)"
)
fig3.write_image('plots/generic_plot/congestion_2024.svg')
fig3.show()

# %%
# Heatmap of monthly congestion hours (matplotlib + seaborn)
df4 = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df4.columns = df4.columns.str.lower()
df4 = df4[(df4["jaar"] >= 2024) & (df4["jaar"] <= 2030)].sort_values(by="datum_tijd")

heat_df = df4.assign(
    month=df4["datum_tijd"].dt.to_period("M"),
    congestion=(df4["belasting"] > capacity_limit) * 0.25
)
pivot = heat_df.groupby(["jaar", heat_df["datum_tijd"].dt.month])["congestion"].sum().unstack()

plt.figure(figsize=(12, 6))
sns.heatmap(pivot, cmap="Reds", annot=True, fmt=".1f",
            linewidths=0.5, cbar_kws={'label': 'Congestion Hours'})
plt.xlabel("Month")
plt.ylabel("Year")
plt.title("Monthly Congestion Hours (Load Exceeds Capacity) 2024–2030")
plt.tight_layout()
plt.savefig('plots/generic_plot/heatmap.svg')
plt.show()

# %%
# Congestion timestamps to CSV
df5 = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df5.columns = df5.columns.str.lower()
df5 = df5[(df5["jaar"] >= 2024) & (df5["jaar"] <= 2032)].copy()
df5["datum_tijd"] = df5.apply(lambda r: r["datum_tijd"].replace(year=r["jaar"]), axis=1)
df_cong = df5[df5["belasting"] > capacity_limit]

print("\nExact timestamps of congestion occurrences:")
print(df_cong[['jaar','datum_tijd','belasting']].to_string(index=False))

df_cong[['jaar','datum_tijd','belasting']].to_csv(
    'plots/generic_plot/congestion_timestamps.csv', index=False
)

# %%
# Hourly congestion frequency bar charts
for yr in [2030, 2024]:
    df_year = df_cong[df_cong['jaar'] == yr]
    hours = (
        df_year['datum_tijd']
        .dt.hour
        .value_counts()
        .reindex(range(24), fill_value=0)
        .sort_index()
    )
    fig_hr = go.Figure()
    fig_hr.add_trace(go.Bar(
        x=[f"{h}:00" for h in hours.index],
        y=hours.values,
        name='Congestion Occurrences',
        marker_color=flare_color
    ))
    fig_hr.update_layout(
        xaxis_title="Hour of the Day",
        yaxis_title="Occurrences",
        title=f"Congestion Frequency Per Hour in {yr}",
        xaxis_tickangle=45
    )
    fig_hr.write_image(f'plots/generic_plot/hourly_congestion_{yr}.svg')
    fig_hr.show()


# %%
# Imbalance market prices plots
df_price = pd.read_csv("data/raw_data/settlement_prices.csv", sep=';')
df_price['Timeinterval Start Loc'] = pd.to_datetime(df_price['Timeinterval Start Loc'], errors='coerce')
df_price['Price Dispatch Down'] = pd.to_numeric(df_price['Price Dispatch Down'], errors='coerce')
df_price['Price Dispatch Up']   = pd.to_numeric(df_price['Price Dispatch Up'], errors='coerce')

# Shortage prices
fig4 = go.Figure()
fig4.add_trace(go.Scatter(
    x=df_price['Timeinterval Start Loc'],
    y=df_price['Price Dispatch Down'],
    mode='lines',
    line=dict(color='crimson'),
    name='Price Dispatch Down'
))
fig4.update_layout(
    title="Shortage Prices Over Time (2024)",
    xaxis_title="Date",
    yaxis_title="Price (EUR/MWh)"
)
# Save and show
fig4.write_image('plots/generic_plot/shortage_prices.svg')
fig4.show()

# %%
# Surplus prices
fig5 = go.Figure()
fig5.add_trace(go.Scatter(
    x=df_price['Timeinterval Start Loc'],
    y=df_price['Price Dispatch Up'],
    mode='lines',
    line=dict(color='royalblue'),
    name='Price Dispatch Up'
))
fig5.update_layout(
    title="Surplus Prices Over Time (2024)",
    xaxis_title="Date",
    yaxis_title="Price (EUR/MWh)"
)
# Save and show
fig5.write_image('plots/generic_plot/surplus_prices.svg')
fig5.show()

# %%
# Day-Ahead market prices
df_da = pd.read_csv("data/new_day_ahead.csv", sep=',')
df_da['datetime'] = pd.to_datetime(df_da['datetime'], errors='coerce')
df_da['price']    = pd.to_numeric(df_da['price'], errors='coerce')

fig6 = go.Figure()
fig6.add_trace(go.Scatter(
    x=df_da['datetime'],
    y=df_da['price'],
    mode='lines',
    line=dict(color='crimson'),
    name='Day-Ahead Price'
))
fig6.update_layout(
    title="Day-Ahead Market Prices Over Time (2024)",
    xaxis_title="Date",
    yaxis_title="Price (EUR/MWh)"
)
# Save and show
fig6.write_image('plots/generic_plot/day_ahead_prices.svg')
fig6.show()

# %%

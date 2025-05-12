import pandas as pd
from itertools import cycle
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import pypsa
import plotly.io as pio
import seaborn as sns
import os


def colors_crest(number: int):
    """Return array of length <number> colors from seaborn 'crest' palette"""
    return sns.color_palette("crest", n_colors=number).as_hex()

def colors_crest_r(number: int):
    """Return array of length <number> colors from seaborn 'crest_r' palette"""
    return sns.color_palette("crest_r", n_colors=number).as_hex()

def colors_flare(number: int):
    """Return array of length <number> colors from seaborn 'flare' palette"""
    return sns.color_palette("flare", n_colors=number).as_hex()

def colors_flare_r(number: int):
    """Return array of length <number> colors from seaborn 'flare_r' palette"""
    return sns.color_palette("flare_r", n_colors=number).as_hex()

def set_plot_style(
    template: str = "plotly_white",
    width: int    = 900,
    height: int   = 400,
    margin: dict  = None
) -> None:
    """
    Apply default Plotly styles for all figures,
    plus a matching two-color colorway for congestion bars,
    and place the legend below all figures.
    """
    # 1) default template
    pio.templates.default = template

    # 2) figure size & margins
    default_margins = margin or {"l":50, "r":50, "t":50, "b":50}
    tpl = pio.templates[template]
    tpl.layout.width  = width
    tpl.layout.height = height
    tpl.layout.margin = default_margins

    # 3) legend below plot
    tpl.layout.legend = dict(
         orientation='h',
        y=-0.2,
        x=0.5,
        xanchor='center',
        yanchor='top'
    )

    # 4) two-color colorway
    crest_color = colors_crest(1)[0]
    flare_color = colors_flare(1)[0]
    tpl.layout.colorway = [crest_color, flare_color]

# Apply style immediately so every figure in this module inherits it
set_plot_style()

def bus_balance(network: pypsa.Network, bus: str, unify_color_palette: bool = False, resample: str = "H", return_json=True, return_df: bool = False, return_monthly_bar=False) -> go.Figure:
    """
    Geeft een gestapelde area plot van de geselecteerde bus weer. Hierin zie je:
    -- Generatie (bus inflow) op de positieve y-as en 
    -- Load (bus outflow) op de negatieve y-as.
    
    Met 'unify_color_palette' kies je of je voor generatie en load hetzelfde continue kleurenpalet wilt gebruiken.
    'resample': string voor de resample-frequentie (bijv. "H" voor uurlijkse aggregatie).
    """
    
    if bus not in network.buses.index:
        raise ValueError(f"Bus met naam {bus} bestaat niet in het netwerk. Beschikbare bussen: {network.buses.index}. Kies een bestaande bus.")

    # Haal de componenten op die aan de bus zijn gekoppeld
    generators = network.generators[network.generators.get("bus") == bus]
    links0 = network.links[network.links.get("bus0") == bus]        
    links1 = network.links[network.links.get("bus1") == bus]
    if "bus2" in network.links.columns:
        links2 = network.links[network.links.get("bus2") == bus]      
    else:
        links2 = None
    loads = network.loads[network.loads.get("bus") == bus]
    storageunits = network.storage_units[network.storage_units.get("bus") == bus]
    
    # Haal de tijdreeksen op (indien aanwezig)
    generators_t = network.generators_t.get("p")[generators.index] if not generators.empty else None
    links0_t = network.links_t.get("p0")[links0.index] * -1 if not links0.empty else None
    links1_t = network.links_t.get("p1")[links1.index] * -1 if not links1.empty else None
    if links2 is not None and not links2.empty:
        links2_t = network.links_t.get("p2")[links2.index] * -1
    else:
        links2_t = None
    loads_t = network.loads_t.get("p")[loads.index] * -1 if not loads.empty else None

    # Bereken de netto batterijwerking: (ontladen - laden)
    if not storageunits.empty:
        p_dispatch = network.storage_units_t.get("p_dispatch")[storageunits.index]
        p_store = network.storage_units_t.get("p_store")[storageunits.index]
        battery_net = (p_dispatch - p_store).sum(axis=1).to_frame("battery net")
    else:
        battery_net = None

    # Voeg de dataframes samen voor de plot
    df_list = []
    if generators_t is not None:
        df_list.append(generators_t)
    if loads_t is not None:
        df_list.append(loads_t)
    if links0_t is not None:
        df_list.append(links0_t)
    if links1_t is not None:
        df_list.append(links1_t)
    if links2_t is not None:
        df_list.append(links2_t)
    if battery_net is not None:
        df_list.append(battery_net)
        
    df = pd.concat(df_list, axis=1)
    df = df.round(5)
    
    # Resample de data naar de opgegeven frequentie (bijv. "H" voor uurlijkse aggregatie)
    df = df.resample(resample).sum()

    if return_df:
        return df  # retourneer de geresamplede energiebalans dataframe

    # Splits de data in positieve (generatie) en negatieve (load) waarden
    df_pos = df.clip(lower=0, upper=None)
    df_neg = df.clip(lower=None, upper=0)

    # Verwijder kolommen met alleen nullen voor een opgeruimde legende
    df_pos = df_pos.loc[:, (df_pos != 0).any(axis=0)] 
    df_neg = df_neg.loc[:, (df_neg != 0).any(axis=0)]

    # Maak de gestapelde area plot
    fig = go.Figure()

    # Kies het kleurenpalet
    if unify_color_palette:
        colors_pos = iter(colors_crest(number=len(df.columns)))
        colors_neg = colors_pos
    else:
        colors_pos = iter(colors_crest(number=len(df_pos.columns)))
        colors_neg = iter(colors_flare(number=len(df_neg.columns)))

    first_line = True
    for column in df_neg.columns:
        if first_line:
            fig.add_trace(go.Scatter(x=df_neg.index, y=df_neg[column],
                                     stackgroup="neg", fill="tozeroy",
                                     name=column, line={"color": next(colors_neg)}))
            first_line = False
        else:
            fig.add_trace(go.Scatter(x=df_neg.index, y=df_neg[column],
                                     stackgroup="neg", fill="tonexty",
                                     name=column, line={"color": next(colors_neg)}))
            
    first_line = True
    for column in df_pos.columns:
        if first_line:
            fig.add_trace(go.Scatter(x=df_pos.index, y=df_pos[column],
                                     stackgroup="pos", fill="tozeroy",
                                     name=column, line={"color": next(colors_pos)}))
            first_line = False
        else:
            fig.add_trace(go.Scatter(x=df_pos.index, y=df_pos[column],
                                     stackgroup="pos", fill="tonexty",
                                     name=column, line={"color": next(colors_pos)}))

    fig.update_layout(template="plotly_white", yaxis_title="Power [MW]", title="Timeseries of renewable generation")
    fig.update_xaxes(
        showgrid=True,
        tickformat="%H:%M \n\r%d-%b"
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
    )
    nice_names = {
        "solar": "Solar",
        "wind": "Wind",
        "tidal": "Tidal",
        "demand": "Demand",
        "grid_feedin": "Teruglevering aan net (ODN)",
        "2 MVA t/m 10 MVA": "Levering door net (LDN)",
        "charging_cars": "Opladen auto's",
        "charging_vans": "Opladen bestelwagens",
        "charging_trucks": "Opladen vrachtwagens",
        "battery net": "Batterij (netto)",
        "third_party_load": "Derden",
    }
    for trace in fig.data:
        trace.name = nice_names.get(trace.name, trace.name)

    if return_monthly_bar:
        df_monthly = df_pos.resample("M").sum()
        df_monthly.index = df_monthly.index.month_name()
        fig_monthly = px.bar(df_monthly, barmode="stack", color_discrete_sequence=colors_crest(number=len(df_monthly.columns)))
        fig_monthly.update_layout(template="plotly_white", yaxis_title="Energy [MWh]", xaxis_title="", title="Monthly generation")
        fig_monthly.update_xaxes(showgrid=True, tickformat="%b-%Y")
        fig_monthly.update_yaxes(showgrid=True, gridwidth=1)
        #fig_monthly.write_image(f"{bus}_monthly_generation.svg", format="svg")
        return fig_monthly

    #fig.write_image(f"{bus}_bus_balance.svg", format="svg")
    #fig.write_image("household_bus_balance.svg", format="svg")
    return fig

def household_inflow_balance(
    network: pypsa.Network,
    unify_color_palette: bool = False,
    resample: str = "H",
    return_df: bool = False
) -> go.Figure:
    """
    Stacked‐area plot of:
      • all Link → Household inflows (bus1=="Household"), shown positive
      • the household Load, shown negative
    exactly like bus_balance’s styling, but restricted to those two.
    """

    bus = "Household"
    if bus not in network.buses.index:
        raise ValueError(f"Bus '{bus}' not in network (got {bus!r})")

    # --- pick out only the links feeding into the Household bus
    inflow_links = network.links[network.links["bus1"] == bus]
    # --- and the household load itself
    HouseholdLoad = network.loads[network.loads["bus"] == bus]

    # --- pull their time‐series (negating so that a positive number means "into Household")
    links_ts = (
        -network.links_t["p1"][inflow_links.index]
        if not inflow_links.empty else None
    )
    load_ts = (
        -network.loads_t["p"][HouseholdLoad.index]
        if not HouseholdLoad.empty else None
    )

    # --- stitch into one DF, resample & round
    df_list = []
    if links_ts is not None:
        df_list.append(links_ts)
    if load_ts is not None:
        df_list.append(load_ts)
    df = pd.concat(df_list, axis=1).resample(resample).sum().round(5)

    if return_df:
        return df

    # --- split into positive & negative and drop any all-zero columns
    df_pos = df.clip(lower=0).loc[:, (df.clip(lower=0) != 0).any(axis=0)]
    df_neg = df.clip(upper=0).loc[:, (df.clip(upper=0) != 0).any(axis=0)]

    # --- choose palettes exactly like bus_balance
    if unify_color_palette:
        pal = iter(colors_crest(len(df_pos.columns) + len(df_neg.columns)))
        colors_pos = colors_neg = pal
    else:
        colors_pos = iter(colors_crest(len(df_pos.columns)))
        colors_neg = iter(colors_flare(len(df_neg.columns)))

    fig = go.Figure()

    # --- plot the negative (load) stack
    for i, col in enumerate(df_neg.columns):
        clr = next(colors_neg)
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df_neg[col],
            stackgroup="neg",
            fill="tozeroy" if i == 0 else "tonexty",
            name=col,
            line=dict(color=clr),
        ))

    # --- plot the positive (inflow links) stack
    for i, col in enumerate(df_pos.columns):
        clr = next(colors_pos)
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df_pos[col],
            stackgroup="pos",
            fill="tozeroy" if i == 0 else "tonexty",
            name=col,
            line=dict(color=clr),
        ))

    fig.update_layout(
        template="plotly_white",
        title="Household: Inflows vs Load",
        yaxis_title="Power [MW]"
    )
    fig.update_xaxes(showgrid=True, tickformat="%H:%M\n%d-%b")
    fig.update_yaxes(showgrid=True, gridwidth=1)

    return fig

def battery_behavior(
    network: pypsa.Network,
    price_csv: str = "data/new_day_ahead.csv",
    unify_color_palette: bool = False,
    resample: str = "H",
    return_df: bool = False
) -> go.Figure:
    """
    Plot BESS ⇄ Household flows plus day-ahead price, with legend neatly on the right.

    Parameters
    ----------
    network
        a PyPSA Network containing the two links.
    price_csv
        path to CSV with columns [datetime, price, jaar].
    unify_color_palette
        if True, use one continuous 'crest' palette for the two flows.
    resample
        pandas resample rule (e.g. "15min", "H").
    return_df
        if True, return the DataFrame of flows (price omitted).
    """
    # 1) Ensure both links exist
    required = ["BESS → Household", "Household → BESS"]
    missing = [lk for lk in required if lk not in network.links.index]
    if missing:
        raise KeyError(f"Missing link(s): {missing}")

    # 2) Build the flows DataFrame
    bess2hh = -network.links_t.p1["BESS → Household"].rename("Discharge")
    hh2bess = -network.links_t.p0["Household → BESS"].rename("Charge")
    df = pd.concat([bess2hh, hh2bess], axis=1)
    df = df.resample(resample).sum().round(5)

    if return_df:
        return df

    # 3) Load & slice price series
    price = (
        pd.read_csv(price_csv, parse_dates=["datetime"], index_col="datetime")["price"]
        .resample(resample).ffill()
    )
    price = price.loc[df.index.min(): df.index.max()]

    # 4) Drop any all-zero column (though unlikely here)
    df = df.loc[:, (df != 0).any(axis=0)]

    # 5) Choose colors
    if unify_color_palette:
        palette = iter(colors_crest(len(df.columns)))
        color_discharge = next(palette)
        color_charge    = next(palette)
    else:
        color_discharge = colors_crest(1)[0]
        color_charge    = colors_flare(1)[0]

    # 6) Start Figure
    fig = go.Figure()

    # a) Discharge = positive area
    if "Discharge" in df:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["Discharge"],
            mode="lines",
            name="Discharging ← Battery",
            line=dict(color=color_discharge),
            fill="tozeroy"
        ))
    # b) Charge = negative area
    if "Charge" in df:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["Charge"],
            mode="lines",
            name="Charging → Battery",
            line=dict(color=color_charge),
            fill="tozeroy"
        ))
    # c) Overlay day-ahead price on secondary y-axis
    fig.add_trace(go.Scatter(
        x=price.index,
        y=price.values,
        mode="lines",
        name="Day-Ahead Price",
        yaxis="y2",
        line=dict(color="black", dash="dot"),
        hovertemplate="%{y:.2f} €/MWh<br>%{x|%H:%M %d-%b}"
    ))

    # 7) Layout & legend on the right
    fig.update_layout(
        template="plotly_white",
        title="Battery Behavior & Day-Ahead Price",
        yaxis=dict(title="Power [MW]", showgrid=True, gridwidth=1),
        yaxis2=dict(
            title="Price [€/MWh]",
            overlaying="y",
            side="right",
            showgrid=False
        )
    )
    fig.update_xaxes(showgrid=True, tickformat="%H:%M\n%d-%b")

    return fig

def battery_behavior_settlement(
    network: pypsa.Network,
    settlement_csv: str = "data/new_settlement_prices.csv",
    unify_color_palette: bool = False,
    resample: str = "H",
    return_df: bool = False
) -> go.Figure:
    """
    Plot BESS ⇄ Household flows plus regulated settlement price, with legend on the right.

    For each timestamp:
      - regulation_state == 1: price = price_surplus
      - regulation_state == -1: price = price_shortage
      - regulation_state == 2: price = 0

    Parameters
    ----------
    network
        a PyPSA Network containing the two BESS links.
    settlement_csv
        path to CSV with columns [timeinterval, price_shortage, price_surplus, regulation_state].
    unify_color_palette
        if True, use one continuous 'crest' palette for the two flows.
    resample
        pandas resample rule (e.g. "15min", "H").
    return_df
        if True, return the DataFrame of flows (prices omitted).
    """
    # 1) Ensure both BESS links exist
    required = ["BESS → Household", "Household → BESS"]
    missing = [lk for lk in required if lk not in network.links.index]
    if missing:
        raise KeyError(f"Missing link(s): {missing}")

    # 2) Build the flows DataFrame
    bess2hh = -network.links_t.p1["BESS → Household"].rename("Discharge")
    hh2bess = -network.links_t.p0["Household → BESS"].rename("Charge")
    df = pd.concat([bess2hh, hh2bess], axis=1)
    df = df.resample(resample).sum().round(5)

    if return_df:
        return df

    # 3) Load & resample settlement prices (incl. regulation_state)
    price_df = (
        pd.read_csv(settlement_csv, parse_dates=["timeinterval"], index_col="timeinterval")
        [["price_shortage", "price_surplus", "regulation_state"]]
        .resample(resample)
        .ffill()
    )
    price_df = price_df.loc[df.index.min(): df.index.max()]

    # 4) Compute regulated price series
    regulated_price = price_df.apply(
        lambda row: row.price_surplus if row.regulation_state == 1
                    else row.price_shortage if row.regulation_state == -1
                    else 0 if row.regulation_state == 2
                    else np.nan,
        axis=1
    )

    # 5) Drop any all-zero flow columns
    df = df.loc[:, (df != 0).any(axis=0)]

    # 6) Choose colors for flows
    if unify_color_palette:
        palette = iter(colors_crest(len(df.columns)))
        color_discharge = next(palette)
        color_charge = next(palette)
    else:
        color_discharge = colors_crest(1)[0]
        color_charge = colors_flare(1)[0]

    # 7) Create figure
    fig = go.Figure()

    # a) Discharge = positive area
    if "Discharge" in df:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["Discharge"],
            mode="lines",
            name="Discharging ← Battery",
            line=dict(color=color_discharge),
            fill="tozeroy"
        ))
    # b) Charge = negative area
    if "Charge" in df:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["Charge"],
            mode="lines",
            name="Charging → Battery",
            line=dict(color=color_charge),
            fill="tozeroy"
        ))

    # c) Overlay regulated settlement price on secondary y-axis
    fig.add_trace(go.Scatter(
        x=regulated_price.index,
        y=regulated_price.values,
        mode="lines",
        name="Settlement Price",
        yaxis="y2",
        line=dict(color="black", dash="dot"),
        hovertemplate="%{y:.2f} €/MWh<br>%{x|%H:%M %d-%b}"
    ))

    # 8) Layout & legend
    fig.update_layout(
        template="plotly_white",
        title="Battery Behavior & Regulated Settlement Price",
        yaxis=dict(title="Power [MW]", showgrid=True, gridwidth=1),
        yaxis2=dict(
            title="Price [€/MWh]",
            overlaying="y",
            side="right",
            showgrid=False
        )
    )
    fig.update_xaxes(showgrid=True, tickformat="%H:%M\n%d-%b")

    return fig


def calculate_battery_profit(network, out_dir = None):
    """
    Bereken batterij-winst waarbij de marktprijs per snapshot
    de marginal cost is van de marginale generator—zowel positieve
    als negatieve dispatch.
    """
    # 1) Data inladen
    mc_gen = network.generators_t.marginal_cost
    p_gen  = network.generators_t.p

    # 2) Masker: alle generators met abs(p) > 0 (dus: óók de negatives)
    dispatch_mask = p_gen.abs() > 0

    # 3) Marktprijs = marginal cost van de marginale unit
    #    (max over alle ge-dispatchte units)
    market_price = mc_gen.where(dispatch_mask).max(axis=1)

    # 4) Flows van de BESS-links
    flows         = network.links_t.p0
    E_charged     = flows["Household → BESS"].clip(lower=0)
    E_discharged  = flows["BESS → Household"].clip(lower=0)

    # 5) Net-metering taksen
    mc_SS_to_HH   = network.links.at["MRS → Household", "marginal_cost"]
    mc_HH_to_SS   = network.links.at["Household → MRS", "marginal_cost"]

    # 6) Kosten- & revenue-time series
    cost_ts    = E_charged    * (market_price + mc_SS_to_HH)
    revenue_ts = E_discharged * (market_price - mc_HH_to_SS)

    # 7) Totalen
    total_cost    = cost_ts.sum()
    total_revenue = revenue_ts.sum()
    total_profit  = total_revenue - total_cost

    # Debug
    print(f"→ # laden MWh:    {E_charged.sum():.2f}")
    print(f"→ # ontladen MWh: {E_discharged.sum():.2f}")
    print(f"→ laad-kosten:     €{total_cost:,.2f}")
    print(f"→ ontlad-opbrengst: €{total_revenue:,.2f}")
    print(f"→ battery winst:   €{total_profit:,.2f}")

    # ➤ Network objective, system cost & revenue
    net_obj  = getattr(network, "objective", float("nan"))
    #sys_cost = network.statistics.system_cost()
   # sys_rev  = network.statistics.revenue()
    print(f"→ network objective:      €{net_obj:,.2f}")
    #print(f"→ system cost:            €{sys_cost:,.2f}")
   # print(f"→ total system revenue:   €{sys_rev:,.2f}")

    # ➤ Opslaan als CSV als out_dir is opgegeven
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        df = pd.DataFrame([{
            "E_charged_MWh":      E_charged.sum(),
            "E_discharged_MWh":   E_discharged.sum(),
            "battery_cost":       total_cost,
            "battery_revenue":    total_revenue,
            "battery_profit":     total_profit,
            "network_objective":  net_obj,
           # "system_cost":        sys_cost,
            #"system_revenue":     sys_rev
        }])
        df.to_csv(os.path.join(out_dir, "battery_and_system_stats.csv"), index=False)

    return revenue_ts - cost_ts, total_cost, total_revenue, total_profit
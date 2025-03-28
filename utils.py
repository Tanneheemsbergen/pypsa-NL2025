import pandas as pd
from itertools import cycle
import plotly.graph_objects as go
import plotly.express as px
import pypsa
import seaborn as sns

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

    fig.update_layout(template="simple_white", yaxis_title="Power [MW]", title="Timeseries of renewable generation")
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
        fig_monthly.update_layout(template="simple_white", yaxis_title="Energy [MWh]", xaxis_title="", title="Monthly generation")
        fig_monthly.update_xaxes(
            showgrid=True,
            tickformat="%b-%Y"
        )
        fig_monthly.update_yaxes(
            showgrid=True,
            gridwidth=1,
        )
        return fig_monthly

    return fig

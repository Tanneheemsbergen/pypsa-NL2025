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

def bus_balance(network: pypsa.Network, bus: str, unify_color_palette: bool = False, resample: str = "H", return_json=True, return_df: bool = False, return_monthly_bar = False) -> go.Figure:
        """
        Returns a stacked area plot of the selected bus. This shows energy balance at the node with 
        
        -- generation (bus inflow) on positive y-axis

        -- load (bus outflow) on negative y-axis

        unify_color_palette selects wether or not to use the same continous color palette for generation and load.

        resample: provide string for resampling frequency. List at: 
        https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#offset-aliases

        """
        
        if not bus in network.buses.index:
            raise ValueError(f"Bus with name {bus} does not exist in network. Available buses are {network.buses.index}. Please choose one of the existing buses to visualize.")

        #Get the dataframe with components on selected bus from all buses
        generators = network.generators[network.generators.get("bus")== bus]
        links0 = network.links[network.links.get("bus0") == bus]        
        links1 = network.links[network.links.get("bus1") == bus]
        if "bus2" in network.links.columns:
            links2 = network.links[network.links.get("bus2") == bus]      
        else:
            links2 = None
        loads = network.loads[network.loads.get("bus") == bus]
        storageunits = network.storage_units[network.storage_units.get("bus") == bus]
        

        #get power timeseries for this bus - conditional to check of the components we are asking for even exist
        generators_t = network.generators_t.get("p")[generators.index] if generators is not None else None
        links0_t = network.links_t.get("p0")[links0.index]*-1 if links0 is not None else None
        links1_t = network.links_t.get("p1")[links1.index]*-1 if links1 is not None else None
        if links2 is not None:
            links2_t = network.links_t.get("p2")[links2.index]*-1 if links2 is not None else None
        loads_t = network.loads_t.get("p")[loads.index]*-1 if loads is not None else None
        storageunits_t_charge = network.storage_units_t.get("p_store")[storageunits.index].add_suffix(" charge")*-1 if storageunits is not None else None
        storageunits_t_discharge = network.storage_units_t.get("p_dispatch")[storageunits.index].add_suffix(" discharge") if storageunits is not None else None

        #merge together for plotting power balance
        if links2 is not None:
            df_list: list[pd.DataFrame] = [generators_t, loads_t, links0_t, links1_t, links2_t, storageunits_t_charge, storageunits_t_discharge]
        else: 
            df_list = [loads_t, generators_t, links0_t, links1_t,  storageunits_t_charge, storageunits_t_discharge]
        df = pd.concat(df_list, axis=1)
        df = df.round(5)
        if return_df:
            return df.resample(resample).sum() #return energy balance dataframe

        #create seperate positive and negative dataframes
        df_pos = df.clip(lower=0, upper=None)
        df_neg = df.clip(lower=None, upper=0)

        #drop columns with only zeros -> cleans up the graph legend
        df_pos = df_pos.loc[:, (df_pos != 0).any(axis=0)] 
        df_neg = df_neg.loc[:, (df_neg != 0).any(axis=0)]

        #optional resampling
        df_pos = df_pos.resample(resample).mean()
        df_neg = df_neg.resample(resample).mean()

        #create stacked area plot with all positive (generation) and negative (load) stacked
        fig = go.Figure()

        #continuous colorsscale
        if unify_color_palette:
            colors_pos = iter(colors_crest(number=len(df.columns)))
            colors_neg = colors_pos
        #different colorsscales for positive and negative
        elif not unify_color_palette:
            colors_pos = iter(colors_crest(number=len(df_pos.columns)))
            colors_neg = iter(colors_flare(number=len(df_neg.columns)))

        first_line = True
        for column in df_neg.columns:
            if first_line:
                fig.add_trace(go.Scatter(x=df_neg.index, y=df_neg[column], stackgroup="neg" , fill="tozeroy", name=column, line={"color": next(colors_neg)}))
                first_line=False
            elif first_line == False:
                fig.add_trace(go.Scatter(x=df_neg.index, y=df_neg[column], stackgroup="neg", fill="tonexty", name=column, line={"color": next(colors_neg)}))
        first_line = True
        for column in df_pos.columns:
            if first_line:
                fig.add_trace(go.Scatter(x=df_pos.index, y=df_pos[column], stackgroup="pos" , fill="tozeroy", name=column, line={"color": next(colors_pos)}))
                first_line=False
            elif first_line == False:
                fig.add_trace(go.Scatter(x=df_pos.index, y=df_pos[column], stackgroup="pos", fill="tonexty", name=column, line={"color": next(colors_pos)}))

        fig.update_layout(template = "simple_white", yaxis_title = "Power [MW]", title=f"Timeseries of renewable generation")
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
            "battery_charger": "Opladen batterij",
            "battery_discharger": "Ontladen batterij",
            "third_party_load": "Derden",
        }
        #apply the nicenames to the legend
        for trace in fig.data:
            trace.name = nice_names.get(trace.name, trace.name)

        if return_monthly_bar == True:
            df_monthly = df_pos.resample("M").sum()
            df_monthly.index = df_monthly.index.month_name()
            #create a barplot with px and add the colorscale
            fig_monthly = px.bar(df_monthly, barmode="stack", color_discrete_sequence=colors_crest(number=len(df_monthly.columns)))


            fig_monthly.update_layout(template = "simple_white", yaxis_title = "Energy [MWh]", xaxis_title = "", title=f"Monthly generation")
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

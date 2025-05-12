import plotly.io as pio
from utils.utils import colors_crest, colors_flare

def set_plot_style(
    template: str = "plotly_white",
    width: int = 900,
    height: int = 400,
    margin: dict = None
) -> None:
    """
    Apply default Plotly styles for all figures,
    plus a matching two-color colorway for congestion bars,
    and place the legend below all figures.
    """
    # Set the default template
    pio.templates.default = template

    # Define default margins
    default_margins = margin or {"l": 50, "r": 50, "t": 50, "b": 50}
    tpl = pio.templates[template]
    tpl.layout.width = width
    tpl.layout.height = height
    tpl.layout.margin = default_margins

    # Position legend below figures
    tpl.layout.legend = dict(
        orientation='h',
        y=-0.2,
        x=0.5,
        xanchor='center',
        yanchor='top'
    )

    # Set a gentle yet distinct colorway
    crest_color = colors_crest(1)[0]   # e.g. a mid-blue
    flare_color = colors_flare(1)[0]   # e.g. a soft orange
    tpl.layout.colorway = [crest_color, flare_color]

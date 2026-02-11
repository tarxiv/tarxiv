import dash
import dash_mantine_components as dmc
from ..components.cards import title_card

dash.register_page(
    __name__,
    path="/",
    title="Home",
    order=0,
    icon="mdi:home-outline",
)


def layout(**kwargs):
    return dmc.Stack(
        children=[
            title_card(
                title_text="TarXiv Database Explorer",
                subtitle_text="Explore astronomical transients and their lightcurves",
            ),
        ]
    )

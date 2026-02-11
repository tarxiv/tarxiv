import dash
import dash_mantine_components as dmc
from ..components import title_card, expressive_card, create_results_section

dash.register_page(
    __name__,
    path="/cone",
    title="Cone Search",
    order=2,
    icon="lucide:cone",
)


def layout(**kwargs):
    return dmc.Stack(
        children=[
            title_card(
                title_text="TarXiv Database Explorer",
                subtitle_text="Explore astronomical transients and their lightcurves",
            ),
            expressive_card(
                title="Cone Search",
                children=[
                    dmc.Stack(
                        [
                            dmc.Text(
                                "Search for objects within a specified radius of sky coordinates",
                                # style={
                                #     "fontSize": "14px",
                                #     "marginTop": "15px",
                                #     "marginBottom": "15px",
                                # },
                            ),
                            dmc.Group(
                                [
                                    dmc.NumberInput(
                                        id="ra-input",
                                        placeholder="0-360",
                                        min=0,
                                        max=360,
                                        label="RA (degrees):",
                                        style={
                                            "width": "150px",
                                        },
                                    ),
                                    dmc.NumberInput(
                                        id="dec-input",
                                        placeholder="-90 to 90",
                                        min=-90,
                                        max=90,
                                        label="Dec (degrees):",
                                        style={
                                            "width": "150px",
                                        },
                                    ),
                                    dmc.NumberInput(
                                        id="radius-input",
                                        placeholder=">0",
                                        # value=30,
                                        min=0,
                                        label="Radius (arcsec):",
                                        style={
                                            "width": "150px",
                                        },
                                    ),
                                    dmc.Button(
                                        "Search",
                                        id="cone-search-button",
                                        n_clicks=0,
                                        style={"marginTop": "21px"},
                                    ),
                                ]
                            ),
                        ]
                    ),
                ],
            ),
            dmc.Box(
                id="message-banner",
                children=[],
                style={"marginBottom": "20px"},
            ),
            create_results_section(),
        ],
    )

import dash
import dash_mantine_components as dmc
from ..components.cards import title_card, expressive_card, create_message_banner
from flask import request
from urllib.parse import unquote

dash.register_page(
    __name__,
    path="/",
    title="TarXiv - Home",
    name="Home",
    order=0,
    icon="mdi:home-outline",
)


def layout(**kwargs):
    token = unquote(request.cookies.get("tarxiv_user_token", ""))
    return dmc.Stack(
        children=[
            title_card(
                title_text="TarXiv Database Explorer",
                subtitle_text="Explore astronomical transients and their lightcurves",
            ),
            expressive_card(
                title="Welcome to TarXiv!",
                children=[
                    dmc.Text(
                        "TarXiv is a database of astronomical transients and their lightcurves. Use the navigation bar to explore the database and visualize lightcurves.",
                    ),
                ],
            ),
            # create a banner is the user has no token
            create_message_banner(
                message="You have not provided a token. Please enter your token in the User page to access the functionality of the dashboard.",
                message_type="warning",
                hide=bool(token),
            ),
        ]
    )

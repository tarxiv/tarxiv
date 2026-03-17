import dash
import dash_mantine_components as dmc
from ..components.cards import title_card, expressive_card, create_message_banner
from flask import request

# from urllib.parse import unquote
from ...auth import validate_token, TokenStatus

dash.register_page(
    __name__,
    path="/",
    title="TarXiv - Home",
    name="Home",
    order=0,
    icon="mdi:home-outline",
)


def layout(**kwargs):
    token = request.cookies.get("tarxiv_token", "")
    validation = validate_token(token)
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
            create_message_banner(
                message="Your session has expired, log in again via the User page.",
                message_type="error",
                hide=validation["status"] != TokenStatus.EXPIRED,
            ),
            create_message_banner(
                message="Invalid token detected, log in again to continue accessing the dashboard.",
                message_type="error",
                hide=validation["status"] != TokenStatus.INVALID,
            ),
            create_message_banner(
                message="You are logged in. Explore the database using the navigation bar.",
                message_type="success",
                hide=validation["status"] != TokenStatus.VALID,
            ),
        ]
    )

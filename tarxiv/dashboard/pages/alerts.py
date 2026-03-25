import dash

from dash import html, callback, no_update, dcc, clientside_callback

# from dash.dependencies import Input, Output, State
# from dash_extensions import Keyboard
from flask import current_app, request

# from werkzeug.exceptions import Unauthorized
import dash_mantine_components as dmc
from ..components import (
    title_card,
    expressive_card,
    # format_object_metadata,
    create_message_banner,
)

# from ..schemas import (
#     MetadataResponseModel,
#     LightcurveResponseModel,
# )
from ...auth import (
    get_authenticated_user,
    get_jwt_from_request,
    validate_token,
    TokenStatus,
)
# import requests
# from pydantic import ValidationError
# import os

dash.register_page(
    __name__,
    path="/alerts",
    # path_template="",
    title="TarXiv - Alerts",
    name="Alerts",
    order=3,
    icon="fluent:alert-24-regular",
)


def layout(id=None, **kwargs):
    # perform search if id is provided in URL, otherwise show empty search page
    # logger = current_app.config["TXV_LOGGER"]

    # token = get_jwt_from_request(request)
    # user = get_authenticated_user(jwt_token=token)

    # if id and user:
    #     # User came via deep link and has a saved session
    #     results, status, banner, lc_store, meta_store = perform_search(
    #         id, token, logger
    #     )
    # elif id and not user:
    #     validation = validate_token(token)

    #     # Deep link but no token: Show the search bar pre-filled with ID
    #     # but warn the user that a token is missing.
    #     results = html.Div()
    #     status = "Authentication required"

    #     if validation["status"] == TokenStatus.EXPIRED:
    #         banner = create_message_banner(
    #             "Your session has expired. Please log in again.", "warning"
    #         )
    #     elif validation["status"] == TokenStatus.INVALID and token:
    #         banner = create_message_banner(
    #             "Invalid authentication token. Please log in again.", "error"
    #         )
    #     else:
    #         banner = create_message_banner("Please log in to view data.", "warning")

    #     lc_store = None
    #     meta_store = None
    # else:
    #     # Default empty search page
    #     results, status, banner, lc_store, meta_store = (
    #         html.Div(),
    #         "",
    #         html.Div(),
    #         None,
    #         None,
    #     )

    # --------- Table Content ---------
    # TODO: Update the table contents here
    # See DMC link below for dmc.Table docs
    # https://www.dash-mantine-components.com/components/table
    elements = [
        {"position": 6, "mass": 12.011, "symbol": "C", "name": "Carbon"},
        {"position": 7, "mass": 14.007, "symbol": "N", "name": "Nitrogen"},
        {"position": 39, "mass": 88.906, "symbol": "Y", "name": "Yttrium"},
        {"position": 56, "mass": 137.33, "symbol": "Ba", "name": "Barium"},
        {"position": 58, "mass": 140.12, "symbol": "Ce", "name": "Cerium"},
    ]

    rows = [
        dmc.TableTr(
            [
                dmc.TableTd(element["position"]),
                dmc.TableTd(element["name"]),
                dmc.TableTd(element["symbol"]),
                dmc.TableTd(element["mass"]),
            ]
        )
        for element in elements
    ]

    head = dmc.TableThead(
        dmc.TableTr(
            [
                dmc.TableTh("Element Position"),
                dmc.TableTh("Element Name"),
                dmc.TableTh("Symbol"),
                dmc.TableTh("Atomic Mass"),
            ]
        )
    )
    body = dmc.TableTbody(rows)
    caption = dmc.TableCaption("Some elements from periodic table")

    return dmc.Stack(
        children=[
            title_card(
                title_text="TarXiv Database Explorer",
                subtitle_text="Explore astronomical transients and their lightcurves",
            ),
            expressive_card(
                title="Alerts",
                children=[dmc.Table([head, body, caption])],
            ),
            # dmc.Stack(
            #     [
            #         dmc.Text(
            #             id="search-status",
            #             style={
            #                 "padding": "10px",
            #                 "fontStyle": "italic",
            #                 "fontSize": "14px",
            #             },
            #             children=status,
            #         ),
            #         dmc.Stack(
            #             id="results-container",
            #             children=[results],
            #         ),
            #     ],
            # ),
        ],
    )

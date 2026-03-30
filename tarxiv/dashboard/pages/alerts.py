import os

import dash
from dash import (
    html,
    callback,
    no_update,
    dcc,
    clientside_callback,
    Input,
    Output,
    State,
)
import dash_mantine_components as dmc
from flask import current_app, request

from ..components import (
    title_card,
    expressive_card,
    # format_object_metadata,
    create_message_banner,
)

from ...auth import (
    get_authenticated_user,
    get_jwt_from_request,
    validate_token,
    TokenStatus,
)
import requests
# from pydantic import ValidationError

dash.register_page(
    __name__,
    path="/alerts",
    # path_template="",
    title="TarXiv - Alerts",
    name="Alerts",
    order=3,
    icon="fluent:alert-24-regular",
)


def layout(**kwargs):
    # perform search if id is provided in URL, otherwise show empty search page
    logger = current_app.config["TXV_LOGGER"]

    token = get_jwt_from_request(request)
    user = get_authenticated_user(jwt_token=token)

    print(f"User: {user}")

    page_contents = create_message_banner("Please log in to view alerts.", "warning")
    if user:
        # User came via deep link and has a saved session
        page_contents = (
            expressive_card(
                title="Alerts",
                children=[
                    # dmc.Table([head, body, caption]),
                    dmc.Box(
                        id="alerts-table-container",
                    ),
                    dmc.Center(
                        dmc.Pagination(
                            id="alerts-pagination",
                            total=20,
                            siblings=2,
                            value=1,
                        ),
                    ),
                ],
            ),
        )

    return dmc.Stack(
        children=[
            title_card(
                title_text="TarXiv Database Explorer",
                subtitle_text="Explore astronomical transients and their lightcurves",
            ),
            dmc.Box(
                id="alerts-table-container",
                children=page_contents,
            ),
        ],
    )


# callback for table search and results display
@callback(
    Output("alerts-table-container", "children"),
    Input("alerts-pagination", "value"),
)
def update_alerts_table(page_number):
    if page_number is None:
        i = 0
    else:
        i = page_number - 1

    items_per_page = 25
    response = fetch_api_data(
        "tns_alerts",
        n_rows=items_per_page,
        offset=max(i * items_per_page - 1, 0),
        token=get_jwt_from_request(request),
        logger=current_app.config["TXV_LOGGER"],
    )

    # --------- Table Content ---------
    # TODO: Update the table contents here
    # See DMC link below for dmc.Table docs
    # https://www.dash-mantine-components.com/components/table
    elements = [
        {"page": i + 1, "position": 6, "mass": 12.011, "symbol": "C", "name": "Carbon"},
        {
            "page": i + 1,
            "position": 7,
            "mass": 14.007,
            "symbol": "N",
            "name": "Nitrogen",
        },
        {
            "page": i + 1,
            "position": 39,
            "mass": 88.906,
            "symbol": "Y",
            "name": "Yttrium",
        },
        {
            "page": i + 1,
            "position": 56,
            "mass": 137.33,
            "symbol": "Ba",
            "name": "Barium",
        },
        {
            "page": i + 1,
            "position": 58,
            "mass": 140.12,
            "symbol": "Ce",
            "name": "Cerium",
        },
    ]

    rows = [
        dmc.TableTr(
            [
                dmc.TableTd(element["page"]),
                dmc.TableTd(element["position"]),
                dmc.TableTd(element["name"]),
                # dmc.TableTd(element["symbol"]),
                dmc.TableTd(element["mass"]),
            ]
        )
        for element in elements
    ]

    head = dmc.TableThead(
        dmc.TableTr(
            [
                dmc.TableTh("Page Number"),
                dmc.TableTh("Element Position"),
                dmc.TableTh("Element Name"),
                # dmc.TableTh("Symbol"),
                dmc.TableTh("Atomic Mass"),
            ]
        )
    )
    body = dmc.TableTbody(rows)
    caption = dmc.TableCaption("Some elements from periodic table")
    return dmc.Table([head, body, caption])


def fetch_api_data(endpoint: str, n_rows: int, offset: int, token, logger):
    """Helper to perform API requests."""
    # TODO: Refactor to use a shared API client module instead of hardcoding requests here
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    api_url = os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")
    response = requests.post(
        url=f"{api_url}/{endpoint}",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json={"n_rows": n_rows, "offset": offset},
    )
    logger.info({"info": f"{endpoint} response status: {response.status_code}"})
    return response

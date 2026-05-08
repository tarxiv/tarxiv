import os
import json

import dash
from dash import (
    callback,
    dcc,
    Input,
    Output,
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
                    dmc.Box(
                        id="alerts-table-body",
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
    Output("alerts-table-body", "children"),
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
        offset=i * items_per_page,
        token=get_jwt_from_request(request),
        logger=current_app.config["TXV_LOGGER"],
    )

    if response.status_code == 401:
        return create_message_banner("Session expired. Please log in again.", "warning")

    if response.status_code != 200:
        return create_message_banner(
            f"Alerts request failed with status {response.status_code}.",
            "error",
        )

    try:
        alerts = json.loads(response.text)
    except json.JSONDecodeError:
        current_app.config["TXV_LOGGER"].error({
            "error": "Failed to decode alerts API response",
            "response": response.text,
        })
        return create_message_banner("Received an invalid alerts response.", "error")

    if not alerts:
        return create_message_banner("No alerts found.", "info")

    def display_value(value):
        if value in (None, ""):
            return "-"
        return str(value)

    rows = [
        dmc.TableTr([
            dmc.TableTd(display_value(alert.get("date_received"))),
            dmc.TableTd(
                dcc.Link(
                    display_value(alert.get("obj_name")),
                    href=f"/lightcurve?id={alert.get('obj_name')}",
                    refresh=False,
                )
            ),
            dmc.TableTd(
                dcc.Link(
                    "TNS",
                    href=f"https://www.wis-tns.org/object/{alert.get('obj_name')}",
                    target="_blank",
                )
            ),
            dmc.TableTd(display_value(alert.get("object_type"))),
            dmc.TableTd(display_value(alert.get("ra"))),
            dmc.TableTd(display_value(alert.get("dec"))),
            dmc.TableTd(display_value(alert.get("discovery_source"))),
            dmc.TableTd(display_value(alert.get("reporting_group"))),
            dmc.TableTd(display_value(alert.get("redshift"))),
        ])
        for alert in alerts
    ]

    return dmc.Table(
        [
            dmc.TableThead(
                dmc.TableTr([
                    dmc.TableTh("Received"),
                    dmc.TableTh("Object"),
                    dmc.TableTh("TNS Link"),
                    dmc.TableTh("Type"),
                    dmc.TableTh("RA"),
                    dmc.TableTh("Dec"),
                    dmc.TableTh("Discovery Source"),
                    dmc.TableTh("Reporting Group"),
                    dmc.TableTh("Redshift"),
                ])
            ),
            dmc.TableTbody(rows),
            dmc.TableCaption("Most recent alerts from the TarXiv alerts API."),
        ],
        striped=True,
        highlightOnHover=True,
        withTableBorder=True,
        withColumnBorders=True,
        horizontalSpacing="sm",
        verticalSpacing="xs",
    )


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

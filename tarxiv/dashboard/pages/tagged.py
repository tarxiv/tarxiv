import os
from urllib.parse import quote

import dash
from dash import Input, Output, State, callback, dcc, html, no_update
import dash_mantine_components as dmc
import requests
from flask import current_app, request

from ...auth import TokenStatus, get_jwt_from_request, validate_token
from ..components.cards import create_message_banner, expressive_card, title_card


dash.register_page(
    __name__,
    path="/tagged",
    title="TarXiv - Tagged",
    name="Tagged",
    order=4,
    icon="mdi:tag-multiple-outline",
)


def tag_option_label(tag):
    if tag.get("owner_type") == "team":
        team_name = tag.get("owner_name") or "team"
        return f"{tag['name']} (team: {team_name})"
    return f"{tag['name']} (personal)"


def layout(**kwargs):
    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)
    validation = validate_token(token)

    tag_options = []
    tags = []
    banner = html.Div()
    if validation["status"] != TokenStatus.VALID:
        banner = create_message_banner(
            "Please log in to view tagged objects.",
            "warning",
        )
    else:
        response = fetch_tags(token, logger)
        if response.status_code == 200:
            tags = response.json()
            tag_options = [
                {
                    "value": tag["id"],
                    "label": tag_option_label(tag),
                }
                for tag in tags
            ]
        else:
            banner = create_message_banner("Could not load tags right now.", "error")

    return dmc.Stack(
        children=[
            dcc.Store(id="tagged-tags-store", storage_type="memory", data=tags),
            title_card(
                title_text="TarXiv Database Explorer",
                subtitle_text="Browse objects associated with your tags",
            ),
            expressive_card(
                title="Tagged Objects",
                children=[
                    dmc.Text(
                        "Choose one tag to view the objects currently associated with it.",
                        c="dimmed",
                    ),
                    dmc.Group([
                        dmc.Select(
                            id="tagged-tag-select",
                            placeholder="Choose a tag",
                            data=tag_options,
                            value=None,
                            style={"minWidth": "320px"},
                        ),
                        dmc.Button("Load objects", id="tagged-load-button", n_clicks=0),
                    ]),
                    html.Div(id="tagged-banner", children=banner),
                    html.Div(id="tagged-objects-panel"),
                ],
            ),
        ]
    )


def api_base_url():
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    return os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")


def fetch_tags(token, logger):
    response = requests.get(
        url=f"{api_base_url()}/tags",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    logger.info({"info": f"tagged tags response status: {response.status_code}"})
    return response


def fetch_tagged_objects(tag_id, token, logger):
    response = requests.get(
        url=f"{api_base_url()}/tags/{tag_id}/objects",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    logger.info({"info": f"tagged objects response status: {response.status_code}"})
    return response


def render_tagged_objects(objects):
    if not objects:
        return dmc.Text(
            "No objects are currently associated with this tag.", c="dimmed"
        )

    return dmc.Stack(
        [
            dmc.Paper(
                withBorder=True,
                p="sm",
                radius="md",
                children=dmc.Anchor(
                    obj.get("object_id", "Unknown object"),
                    href=f"/lightcurve/{quote(obj.get('object_id', ''))}",
                ),
            )
            for obj in objects
        ],
        gap="sm",
    )


@callback(
    [
        Output("tagged-objects-panel", "children"),
        Output("tagged-banner", "children", allow_duplicate=True),
    ],
    Input("tagged-load-button", "n_clicks"),
    State("tagged-tag-select", "value"),
    prevent_initial_call=True,
)
def load_tagged_objects(n_clicks, tag_id):
    if not n_clicks:
        return no_update, no_update

    if not tag_id:
        return no_update, create_message_banner("Select a tag first.", "warning")

    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)
    response = fetch_tagged_objects(tag_id, token, logger)
    if response.status_code != 200:
        error_message = "Could not load tagged objects right now."
        try:
            error_message = response.json().get("error", error_message)
        except ValueError:
            pass
        return no_update, create_message_banner(error_message, "error")

    objects = response.json()
    return render_tagged_objects(objects), html.Div()

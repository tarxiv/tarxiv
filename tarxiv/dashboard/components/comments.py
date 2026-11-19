"""Comment counts shown beside objects in result lists (/tagged, /cone)."""

import os

import dash_mantine_components as dmc
import requests
from dash_iconify import DashIconify

from ...auth import TokenStatus, validate_token


def fetch_comment_counts(source_ids, token, logger) -> dict[str, int]:
    """Visible comment counts per object; {} when logged out or on any failure.

    Counts are decoration, so a failure here must never break the result list.
    """
    if not source_ids or validate_token(token)["status"] != TokenStatus.VALID:
        return {}
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    api_url = os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")
    try:
        response = requests.post(
            url=f"{api_url}/comments/counts",
            timeout=10,
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            json={"source_ids": list(source_ids)},
        )
        if response.status_code == 200:
            return response.json()
        logger.warning({"warning": f"comment counts status {response.status_code}"})
    except requests.RequestException as exc:
        logger.warning({"warning": f"comment counts failed: {exc}"})
    return {}


def comment_count_badge(count):
    """A small '💬 n' badge, or None when there is nothing to show."""
    if not count:
        return None
    plural = "s" if count != 1 else ""
    return dmc.Badge(
        str(count),
        leftSection=DashIconify(icon="mdi:comment-outline", width=12),
        size="sm",
        variant="light",
        color="gray",
        **{"aria-label": f"{count} comment{plural}"},
    )

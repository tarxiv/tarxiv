"""Browser smoke tests: render real pages in Chromium and fail on any JS error.

These catch what Python-side tests can't: a Dash component built with a prop the
JS side rejects (dmc raising on an unknown prop, Mantine refusing a null colour).
Both surface only as a failed callback or a console error in the browser.

Needs ``uv run playwright install chromium`` once.
"""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from tarxiv.auth.token_utils import sign_token  # noqa: E402
from tarxiv.dashboard.components.cookies import COOKIE_DEFAULTS  # noqa: E402
from tarxiv.tests.frontend import browser_app
from tarxiv.tests.conftest import _TEST_JWT_SECRET  # noqa: E402

pytestmark = pytest.mark.browser

REPO_ROOT = Path(__file__).resolve().parents[3]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def dashboard_url():
    port = _free_port()
    env = {
        **os.environ,
        "TARXIV_JWT_SECRET": _TEST_JWT_SECRET,
        "TARXIV_CONFIG_DIR": str(REPO_ROOT / "aux"),
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "tarxiv.tests.frontend.browser_app", str(port)],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            pytest.fail(f"dashboard exited early:\n{proc.stdout.read()}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            break
        except OSError:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("dashboard did not start within 60s")

    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture
def logged_in_page(page, dashboard_url, monkeypatch):
    """(page, errors): logged in as browser_app.ME, recording browser-side errors."""
    monkeypatch.setenv("TARXIV_JWT_SECRET", _TEST_JWT_SECRET)
    token = sign_token(browser_app.ME, "orcid", {"username": "me"})
    page.context.add_cookies([
        {"name": "tarxiv_token", "value": token, "url": dashboard_url}
    ])
    # Pre-accept cookies like a returning visitor, otherwise the consent modal
    # (opened while cookie-consent-store is empty) covers the page and
    # swallows every click.
    consent = json.dumps({key: True for key in COOKIE_DEFAULTS})
    page.add_init_script(
        f"localStorage.setItem('cookie-consent-store', {json.dumps(consent)});"
    )

    errors = []
    # Keep the test offline and deterministic: CDN scripts and fonts are
    # aborted, and the "Failed to load resource" noise that causes is ignored.
    page.route(
        "**/*",
        lambda route: (
            route.continue_()
            if route.request.url.startswith(dashboard_url)
            else route.abort()
        ),
    )

    def on_console(msg):
        is_local = msg.location.get("url", "").startswith(dashboard_url)
        external_load = msg.text.startswith("Failed to load resource") and not is_local
        if msg.type == "error" and not external_load:
            loc = msg.location
            where = (
                f"{loc.get('url')}:{loc.get('lineNumber')}:{loc.get('columnNumber')}"
            )
            errors.append(f"console error at {where}\n{msg.text}")

    page.on("console", on_console)
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    # A Python exception in a callback comes back as a 500 from the Dash server.
    page.on(
        "response",
        lambda r: (
            errors.append(f"HTTP {r.status} {r.url}") if r.status >= 500 else None
        ),
    )
    return page, errors


def test_object_page_comments_render_without_errors(logged_in_page, dashboard_url):
    page, errors = logged_in_page
    page.goto(f"{dashboard_url}/lightcurve/{browser_app.SOURCE_ID}")

    card = page.locator("#object-comment-card")
    card.get_by_text("Looks like a Ia.").wait_for()
    for text in ("[deleted]", "deleted user", "Private note", "(edited)"):
        assert card.get_by_text(text).count() >= 1, text

    # Switching the composer into reply and edit modes re-renders it.
    card.get_by_role("button", name="Reply").first.click()
    card.get_by_text("Replying to other").wait_for()
    card.get_by_role("button", name="Edit").first.click()
    card.get_by_text("Editing your comment").wait_for()

    page.wait_for_load_state("networkidle")
    # Joined so each error prints in full; pytest truncates a list repr.
    assert not errors, "\n\n".join(errors)

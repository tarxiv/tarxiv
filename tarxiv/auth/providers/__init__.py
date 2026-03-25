"""Auth provider registry.

Each entry maps a URL path segment to a module that implements the
AuthProvider protocol::

    def build_authorize_url(state: str) -> str: ...
    def complete_login(code: str) -> dict: ...

To add a new provider, create ``providers/<name>.py`` implementing those
two functions and register it here.
"""

from . import orcid

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AuthProvider:
    build_authorize_url: Callable[[str], str]
    complete_login: Callable[[str], dict]


PROVIDERS = {
    "orcid": AuthProvider(
        build_authorize_url=orcid.build_authorize_url,
        complete_login=orcid.complete_login,
    ),
}

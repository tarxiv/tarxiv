"""Auth provider registry."""

from dataclasses import dataclass
from typing import Callable

from ... import dto

LoginDict = dict[str, str | dto.ProviderProfile | dict | None]


@dataclass(frozen=True)
class AuthProvider:
    """Callable hooks required for an authentication provider."""

    build_authorize_url: Callable[[str], str]
    complete_login: Callable[[str], LoginDict]

from . import orcid

PROVIDERS = {
    "orcid": AuthProvider(
        build_authorize_url=orcid.build_authorize_url,
        complete_login=orcid.complete_login,
    ),
}

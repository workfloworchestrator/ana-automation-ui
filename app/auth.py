"""Identity and role derived from the oauth2-proxy forwarded request headers."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from fastapi import Depends, Request
from starlette.datastructures import Headers

from app.config import Settings, get_settings


class Role(Enum):
    """Access level derived from a user's group membership."""

    OPERATOR = "operator"
    USER = "user"
    NONE = "none"


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated user as forwarded by oauth2-proxy."""

    user: str
    email: str
    groups: frozenset[str]
    role: Role


def _parse_groups(raw: str) -> frozenset[str]:
    return frozenset(group.strip() for group in raw.split(",") if group.strip())


def _role_for(groups: frozenset[str], settings: Settings) -> Role:
    match (settings.operators_group in groups, settings.users_group in groups):
        case (True, _):
            return Role.OPERATOR
        case (_, True):
            return Role.USER
        case _:
            return Role.NONE


def _user_from_headers(headers: Headers, settings: Settings) -> CurrentUser:
    groups = _parse_groups(headers.get("x-auth-request-groups", ""))
    return CurrentUser(
        user=headers.get("x-auth-request-user", ""),
        email=headers.get("x-auth-request-email", ""),
        groups=groups,
        role=_role_for(groups, settings),
    )


def get_current_user(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> CurrentUser:
    """Resolve the current user from the oauth2-proxy forwarded headers."""
    return _user_from_headers(request.headers, settings)

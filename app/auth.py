"""Identity and role derived from the oauth2-proxy forwarded request headers."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

import structlog
from fastapi import Depends, Request
from starlette.datastructures import Headers

from app.config import Settings, get_settings

logger = structlog.get_logger(__name__)


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

    @property
    def initials(self) -> str:
        """Avatar initials derived from the email (or user) identifier."""
        return _initials(self.email or self.user)

    @property
    def short_groups(self) -> list[str]:
        """Group memberships as sorted short names (the last URN segment)."""
        return sorted({_short_group(group) for group in self.groups})


def _parse_groups(raw: str) -> frozenset[str]:
    return frozenset(group.strip() for group in raw.split(",") if group.strip())


def _initials(name: str) -> str:
    local = name.split("@", 1)[0]
    parts = [part for part in local.replace("-", ".").replace("_", ".").split(".") if part]
    return "".join(part[0] for part in parts[:2]).upper() or "?"


def _short_group(group: str) -> str:
    return group.rsplit(":", 1)[-1].split("#", 1)[0]


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
    user = _user_from_headers(request.headers, settings)
    logger.debug(
        "Resolved user from forwarded headers",
        user=user.user or None,
        email=user.email or None,
        groups=sorted(user.groups),
        role=user.role.value,
    )
    return user

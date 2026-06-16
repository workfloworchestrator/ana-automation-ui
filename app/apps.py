"""Portal app cards loaded from config, with per-user access decisions."""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.auth import Role

DEFAULT_APPS_PATH = Path(__file__).resolve().parent / "apps.json"


class AppCard(BaseModel):
    """A single portal app, as configured in the apps ConfigMap."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str
    description: str = ""
    url: str = ""
    required_group: str = ""
    coming_soon: bool = False


class AccessState(Enum):
    """How a station renders for the current user."""

    OPEN = "open"
    LOCKED = "locked"
    COMING_SOON = "coming_soon"


@dataclass(frozen=True)
class AppView:
    """An app card paired with its resolved access state and badge."""

    app: AppCard
    state: AccessState
    badge: str


def load_apps(path: Path) -> list[AppCard]:
    """Load app cards from the configured path, falling back to the bundled default."""
    source = path if path.is_file() else DEFAULT_APPS_PATH
    items = json.loads(source.read_text(encoding="utf-8"))
    return [AppCard.model_validate(item) for item in items]


def _requires_operators(required_group: str) -> bool:
    # requiredGroup is a logical access level ("operators", "users" or empty), not an
    # IdP group identifier; only "operators" restricts an app to the operator role.
    return required_group.strip().casefold() == "operators"


def _can_open(required_group: str, role: Role) -> bool:
    if _requires_operators(required_group):
        return role is Role.OPERATOR
    return role in {Role.USER, Role.OPERATOR}


def _badge(required_group: str) -> str:
    return "OPERATORS" if _requires_operators(required_group) else "USERS"


def _state_for(app: AppCard, role: Role) -> AccessState:
    if app.coming_soon:
        return AccessState.COMING_SOON
    if _can_open(app.required_group, role):
        return AccessState.OPEN
    return AccessState.LOCKED


def app_views(apps: list[AppCard], role: Role) -> list[AppView]:
    """Pair each app with its access state and badge for the given role."""
    return [AppView(app=app, state=_state_for(app, role), badge=_badge(app.required_group)) for app in apps]

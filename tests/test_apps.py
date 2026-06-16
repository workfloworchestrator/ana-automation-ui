import json

import pytest

from app.apps import AccessState, AppCard, _badge, _state_for, app_views, load_apps
from app.auth import Role

# --- model + loading -------------------------------------------------------


def test_appcard_parses_camelcase():
    card = AppCard.model_validate({"name": "AuRA", "url": "/aura/", "requiredGroup": "operators", "comingSoon": True})
    assert card.required_group == "operators"
    assert card.coming_soon is True


def test_load_apps_from_file(tmp_path):
    path = tmp_path / "apps.json"
    path.write_text(json.dumps([{"name": "Foo", "url": "/foo/", "requiredGroup": "operators"}]))
    apps = load_apps(path)
    assert [app.name for app in apps] == ["Foo"]
    assert apps[0].required_group == "operators"


def test_load_apps_falls_back_to_bundled(tmp_path):
    names = [app.name for app in load_apps(tmp_path / "missing.json")]
    assert "AuRA" in names
    assert "Orchestrator" in names


# --- access decision -------------------------------------------------------


@pytest.mark.parametrize(
    ("required_group", "coming_soon", "role", "expected"),
    [
        pytest.param("", False, Role.OPERATOR, AccessState.OPEN, id="any-operator-open"),
        pytest.param("", False, Role.USER, AccessState.OPEN, id="any-user-open"),
        pytest.param("", False, Role.NONE, AccessState.LOCKED, id="any-none-locked"),
        pytest.param("operators", False, Role.OPERATOR, AccessState.OPEN, id="operators-operator-open"),
        pytest.param("operators", False, Role.USER, AccessState.LOCKED, id="operators-user-locked"),
        pytest.param("operators", False, Role.NONE, AccessState.LOCKED, id="operators-none-locked"),
        pytest.param("users", False, Role.USER, AccessState.OPEN, id="users-user-open"),
        pytest.param("users", False, Role.OPERATOR, AccessState.OPEN, id="users-operator-open"),
        pytest.param("users", False, Role.NONE, AccessState.LOCKED, id="users-none-locked"),
        pytest.param("operators", True, Role.OPERATOR, AccessState.COMING_SOON, id="coming-soon-wins"),
    ],
)
def test_state_for(required_group, coming_soon, role, expected):
    card = AppCard(name="X", required_group=required_group, coming_soon=coming_soon)
    assert _state_for(card, role) == expected


@pytest.mark.parametrize(
    ("required_group", "expected"),
    [
        pytest.param("operators", "OPERATORS", id="operators"),
        pytest.param("users", "USERS", id="users"),
        pytest.param("", "USERS", id="empty-defaults-users"),
        pytest.param("other", "USERS", id="unknown-defaults-users"),
    ],
)
def test_badge(required_group, expected):
    assert _badge(required_group) == expected


def test_app_views_pairs_state_and_badge():
    apps = [AppCard(name="Op", required_group="operators"), AppCard(name="Any")]
    views = app_views(apps, Role.USER)
    assert [(view.app.name, view.state, view.badge) for view in views] == [
        ("Op", AccessState.LOCKED, "OPERATORS"),
        ("Any", AccessState.OPEN, "USERS"),
    ]

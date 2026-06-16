import pytest
from starlette.datastructures import Headers
from starlette.requests import Request

from app.auth import CurrentUser, Role, _parse_groups, _role_for, _user_from_headers, get_current_user
from app.config import Settings

DEFAULTS = Settings(_env_file=None)


def _request(headers: dict[str, str]) -> Request:
    raw = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
    return Request({"type": "http", "headers": raw})


# --- group parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("", frozenset(), id="empty"),
        pytest.param("users", frozenset({"users"}), id="single"),
        pytest.param("users,operators", frozenset({"users", "operators"}), id="multiple"),
        pytest.param("  users , operators ", frozenset({"users", "operators"}), id="whitespace"),
        pytest.param("users,,operators,", frozenset({"users", "operators"}), id="empty-segments"),
    ],
)
def test_parse_groups(raw, expected):
    assert _parse_groups(raw) == expected


# --- role dispatch ---------------------------------------------------------


@pytest.mark.parametrize(
    ("groups", "expected"),
    [
        pytest.param(frozenset({"operators"}), Role.OPERATOR, id="operator-only"),
        pytest.param(frozenset({"users"}), Role.USER, id="user-only"),
        pytest.param(frozenset({"users", "operators"}), Role.OPERATOR, id="both-operator-wins"),
        pytest.param(frozenset({"other"}), Role.NONE, id="unknown-group"),
        pytest.param(frozenset(), Role.NONE, id="no-groups"),
    ],
)
def test_role_for_default_group_names(groups, expected):
    assert _role_for(groups, DEFAULTS) == expected


@pytest.mark.parametrize(
    ("groups", "expected"),
    [
        pytest.param(frozenset({"admins"}), Role.OPERATOR, id="custom-operator"),
        pytest.param(frozenset({"readers"}), Role.USER, id="custom-user"),
        pytest.param(frozenset({"users", "operators"}), Role.NONE, id="default-names-ignored"),
    ],
)
def test_role_for_custom_group_names(groups, expected):
    settings = Settings(_env_file=None, users_group="readers", operators_group="admins")
    assert _role_for(groups, settings) == expected


# --- header -> CurrentUser -------------------------------------------------


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        pytest.param(
            {
                "X-Auth-Request-User": "alice",
                "X-Auth-Request-Email": "alice@example.org",
                "X-Auth-Request-Groups": "operators",
            },
            CurrentUser("alice", "alice@example.org", frozenset({"operators"}), Role.OPERATOR),
            id="operator",
        ),
        pytest.param(
            {
                "X-Auth-Request-User": "bob",
                "X-Auth-Request-Email": "bob@example.org",
                "X-Auth-Request-Groups": "users",
            },
            CurrentUser("bob", "bob@example.org", frozenset({"users"}), Role.USER),
            id="user",
        ),
        pytest.param(
            {},
            CurrentUser("", "", frozenset(), Role.NONE),
            id="no-headers",
        ),
    ],
)
def test_user_from_headers(headers, expected):
    assert _user_from_headers(Headers(headers), DEFAULTS) == expected


def test_get_current_user_reads_request_headers():
    request = _request({"X-Auth-Request-User": "carol", "X-Auth-Request-Groups": "operators"})
    user = get_current_user(request, DEFAULTS)
    assert user.user == "carol"
    assert user.role == Role.OPERATOR

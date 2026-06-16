import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import Settings, get_settings
from app.main import _access_request_limiter, app

client = TestClient(app)


# --- happy paths -----------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "content_type_prefix"),
    [
        pytest.param("/health", "text/plain", id="health"),
        pytest.param("/", "text/html", id="index"),
        pytest.param("/static/ana-logo.png", "image/png", id="logo"),
        pytest.param("/static/app.js", "text/javascript", id="app-js"),
    ],
)
def test_get_ok(path, content_type_prefix):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type_prefix)


def test_health_body():
    assert client.get("/health").text == "OK"


@pytest.mark.parametrize("path", [pytest.param("/", id="index"), pytest.param("/health", id="health")])
def test_security_headers(path):
    headers = client.get(path).headers
    csp = headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "same-origin"


OPERATOR_HEADERS = {"X-Auth-Request-User": "op", "X-Auth-Request-Groups": "operators"}
USER_HEADERS = {"X-Auth-Request-User": "usr", "X-Auth-Request-Groups": "users"}


@pytest.mark.parametrize(
    "needle",
    [
        pytest.param("<title>ANA Management Portal</title>", id="title"),
        pytest.param("/static/ana-logo.png", id="logo-src"),
        pytest.param("AuRA", id="aura-name"),
        pytest.param("Orchestrator", id="orchestrator-name"),
        pytest.param("Coming soon", id="coming-soon"),
    ],
)
def test_index_contains(needle):
    assert needle in client.get("/").text


@pytest.mark.parametrize(
    ("headers", "present", "absent"),
    [
        pytest.param(
            OPERATOR_HEADERS,
            ('href="/aura/"', 'href="/dds/portal"'),
            ("OPERATORS ONLY",),
            id="operator-opens-all",
        ),
        pytest.param(
            USER_HEADERS,
            ('href="/dds/portal"', "OPERATORS ONLY"),
            ('href="/aura/"',),
            id="user-locked-out-of-operator-apps",
        ),
        pytest.param(
            {},
            ("OPERATORS ONLY", "USERS ONLY"),
            ('href="/aura/"', 'href="/dds/portal"'),
            id="anonymous-all-locked",
        ),
    ],
)
def test_index_group_aware(headers, present, absent):
    body = client.get("/", headers=headers).text
    assert all(token in body for token in present)
    assert all(token not in body for token in absent)


# --- access-request form + endpoint ----------------------------------------


def _override_settings(**kw):
    def _get() -> Settings:
        return Settings(_env_file=None, **kw)

    return _get


def test_index_shows_request_form_for_no_group():
    app.dependency_overrides[get_settings] = _override_settings(email_enabled=True)
    try:
        body = client.get("/").text
        assert "Request access" in body
        assert 'action="/request-access"' in body
    finally:
        app.dependency_overrides.clear()


def test_index_hides_request_form_when_email_disabled():
    assert "Request access" not in client.get("/").text


def test_index_hides_request_form_for_operator():
    app.dependency_overrides[get_settings] = _override_settings(email_enabled=True)
    try:
        assert "Request access" not in client.get("/", headers=OPERATOR_HEADERS).text
    finally:
        app.dependency_overrides.clear()


def test_request_access_404_when_disabled():
    assert client.post("/request-access", data={"message": "hi"}).status_code == 404


def test_request_access_sends_email(monkeypatch):
    sent = {}

    async def fake_send(user, email, message, settings):
        sent.update(user=user, email=email, message=message)

    monkeypatch.setattr("app.main.send_access_request", fake_send)
    app.dependency_overrides[get_settings] = _override_settings(
        email_enabled=True, access_request_recipient="ops@x", access_request_from="p@x"
    )
    try:
        response = client.post(
            "/request-access",
            data={"message": "please"},
            headers={"X-Auth-Request-User": "carol", "X-Auth-Request-Email": "carol@x"},
        )
        assert response.status_code == 200
        assert "sent" in response.text.lower()
        assert sent == {"user": "carol", "email": "carol@x", "message": "please"}
    finally:
        app.dependency_overrides.clear()


def test_request_access_rate_limited(monkeypatch):
    monkeypatch.setattr(_access_request_limiter, "allow", lambda key: False)
    app.dependency_overrides[get_settings] = _override_settings(
        email_enabled=True, access_request_recipient="ops@x", access_request_from="p@x"
    )
    try:
        response = client.post("/request-access", data={}, headers={"X-Auth-Request-User": "x"})
        assert response.status_code == 429
    finally:
        app.dependency_overrides.clear()


# --- user menu -------------------------------------------------------------


def test_index_shows_user_menu():
    body = client.get(
        "/",
        headers={"X-Auth-Request-User": "dave", "X-Auth-Request-Email": "dave@x", "X-Auth-Request-Groups": "operators"},
    ).text
    assert 'id="user-button"' in body
    assert "dave@x" in body
    assert "operator" in body
    assert "/oauth2/sign_out" in body


@pytest.mark.parametrize(
    ("headers", "expected_groups"),
    [
        pytest.param({"X-Auth-Request-Groups": "operators"}, "operators", id="operator-groups"),
        pytest.param({"X-Auth-Request-Groups": "users,extra"}, "extra, users", id="sorted-groups"),
        pytest.param({}, "none", id="no-groups"),
    ],
)
def test_user_menu_lists_groups(headers, expected_groups):
    body = client.get("/", headers=headers).text
    assert f"groups: {expected_groups}" in body


# --- unhappy paths ---------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/nope", id="unknown-route"),
        pytest.param("/static/missing.png", id="missing-static"),
        pytest.param("/docs", id="docs-disabled"),
        pytest.param("/redoc", id="redoc-disabled"),
        pytest.param("/openapi.json", id="openapi-disabled"),
    ],
)
def test_not_found(path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [
        pytest.param("post", "/health", id="post-health"),
        pytest.param("put", "/health", id="put-health"),
        pytest.param("post", "/", id="post-index"),
        pytest.param("delete", "/", id="delete-index"),
    ],
)
def test_method_not_allowed(method, path):
    assert client.request(method, path).status_code == 405


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/static/%2e%2e/config.py", id="encoded-dotdot"),
        pytest.param("/static/..%2f..%2fpyproject.toml", id="encoded-slash"),
    ],
)
def test_static_rejects_traversal(path):
    response = client.get(path)
    assert response.status_code != 200
    assert "smtp_host" not in response.text


def test_run_binds_configured_address(monkeypatch):
    recorded = {}
    monkeypatch.setattr(
        "uvicorn.run",
        lambda application, host, port: recorded.update(host=host, port=port),
    )
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9999")
    get_settings.cache_clear()
    main.run()
    get_settings.cache_clear()
    assert recorded == {"host": "127.0.0.1", "port": 9999}

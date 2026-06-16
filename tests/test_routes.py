import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import get_settings
from app.main import app

client = TestClient(app)


# --- happy paths -----------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "content_type_prefix"),
    [
        pytest.param("/health", "text/plain", id="health"),
        pytest.param("/", "text/html", id="index"),
        pytest.param("/static/ana-logo.png", "image/png", id="logo"),
    ],
)
def test_get_ok(path, content_type_prefix):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type_prefix)


def test_health_body():
    assert client.get("/health").text == "OK"


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

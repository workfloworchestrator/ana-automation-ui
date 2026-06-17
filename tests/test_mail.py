import aiosmtplib
import pytest
import structlog

from app.config import Settings
from app.mail import InvalidRequest, _tls_flags, build_message, send_access_request


def _settings(**kw):
    return Settings(_env_file=None, **kw)


# --- message building ------------------------------------------------------


def test_build_message_subject_and_headers():
    settings = _settings(access_request_recipient="ops@example.org", access_request_from="portal@example.org")
    msg = build_message("sub-123", "alice@example.org", "please add me", ["urn:x:users"], settings)
    assert msg["From"] == "portal@example.org"
    assert msg["To"] == "ops@example.org"
    assert msg["Reply-To"] == "alice@example.org"
    assert msg["Subject"] == "ANA management portal access request from alice@example.org"
    assert "please add me" in msg.get_content()


def test_build_message_body_has_groups_not_user():
    settings = _settings(access_request_recipient="ops@x", access_request_from="p@x")
    body = build_message("sub-123", "alice@example.org", "hi", ["urn:b", "urn:a"], settings).get_content()
    assert "Email:  alice@example.org" in body
    assert "Groups: urn:a, urn:b" in body  # sorted
    assert "User:" not in body
    assert "sub-123" not in body


def test_build_message_groups_none_when_empty():
    settings = _settings(access_request_recipient="ops@x", access_request_from="p@x")
    assert "Groups: none" in build_message("sub", "a@x", "hi", [], settings).get_content()


def test_build_message_from_user_opt_in():
    settings = _settings(access_request_from="portal@x", access_request_from_user=True)
    assert build_message("sub", "alice@example.org", "hi", [], settings)["From"] == "alice@example.org"


def test_build_message_from_user_falls_back_without_email():
    settings = _settings(access_request_from="portal@x", access_request_from_user=True)
    assert build_message("sub", "", "hi", [], settings)["From"] == "portal@x"


def test_build_message_allows_multiline_body():
    settings = _settings(access_request_recipient="ops@x", access_request_from="p@x")
    assert "line one\nline two" in build_message("sub", "a@x", "line one\nline two", [], settings).get_content()


@pytest.mark.parametrize(
    ("user", "email"),
    [
        pytest.param("a\nb", "x@y", id="newline-in-user"),
        pytest.param("a", "x@y\r\nBcc: evil@z", id="crlf-in-email"),
    ],
)
def test_build_message_rejects_header_injection(user, email):
    settings = _settings(access_request_recipient="ops@x", access_request_from="p@x")
    with pytest.raises(InvalidRequest):
        build_message(user, email, "msg", [], settings)


@pytest.mark.parametrize(
    ("security", "expected"),
    [
        pytest.param("none", (False, False), id="none"),
        pytest.param("starttls", (False, True), id="starttls"),
        pytest.param("tls", (True, False), id="tls"),
    ],
)
def test_tls_flags(security, expected):
    assert _tls_flags(security) == expected


# --- delivery, retry, logging ----------------------------------------------


async def test_send_access_request_passes_smtp_settings(monkeypatch):
    captured = {}

    async def fake_send(message, **kwargs):
        captured["message"] = message
        captured.update(kwargs)

    monkeypatch.setattr("app.mail.aiosmtplib.send", fake_send)
    settings = _settings(
        smtp_host="mail.svc",
        smtp_port=26,
        smtp_security="starttls",
        access_request_recipient="ops@x",
        access_request_from="p@x",
    )
    await send_access_request("sub", "a@x", "hi", ["urn:g"], settings)
    assert captured["hostname"] == "mail.svc"
    assert captured["port"] == 26
    assert captured["start_tls"] is True
    assert captured["message"]["To"] == "ops@x"


async def test_send_access_request_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    async def flaky_send(message, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise aiosmtplib.SMTPException("temporary")

    monkeypatch.setattr("app.mail.aiosmtplib.send", flaky_send)
    settings = _settings(access_request_recipient="ops@x", access_request_from="p@x")
    await send_access_request("sub", "a@x", "hi", [], settings, attempts=3, delay=0)
    assert calls["n"] == 3


async def test_send_access_request_raises_after_exhausting_retries(monkeypatch):
    async def always_fail(message, **kwargs):
        raise aiosmtplib.SMTPException("relay down")

    monkeypatch.setattr("app.mail.aiosmtplib.send", always_fail)
    settings = _settings(
        smtp_host="mail.svc", smtp_port=26, access_request_recipient="ops@x", access_request_from="p@x"
    )
    with structlog.testing.capture_logs() as logs, pytest.raises(aiosmtplib.SMTPException):
        await send_access_request("sub", "a@x", "hi", [], settings, attempts=2, delay=0)
    failed = [entry for entry in logs if entry["event"] == "Access-request email delivery failed"]
    assert failed and failed[0]["relay"] == "mail.svc:26"


async def test_send_access_request_logs_success(monkeypatch):
    async def ok_send(message, **kwargs):
        return None

    monkeypatch.setattr("app.mail.aiosmtplib.send", ok_send)
    settings = _settings(
        smtp_host="mail.svc", smtp_port=26, access_request_recipient="ops@x", access_request_from="p@x"
    )
    with structlog.testing.capture_logs() as logs:
        await send_access_request("sub", "a@x", "hi", [], settings, attempts=1, delay=0)
    sent = [entry for entry in logs if entry["event"] == "Access-request email sent"]
    assert sent and sent[0]["recipient"] == "ops@x" and sent[0]["relay"] == "mail.svc:26"

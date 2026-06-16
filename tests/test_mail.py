import pytest

from app.config import Settings
from app.mail import InvalidRequest, _tls_flags, build_message, send_access_request


def _settings(**kw):
    return Settings(_env_file=None, **kw)


# --- message building ------------------------------------------------------


def test_build_message_fixed_from_with_reply_to():
    settings = _settings(access_request_recipient="ops@example.org", access_request_from="portal@example.org")
    msg = build_message("alice", "alice@example.org", "please add me", settings)
    assert msg["From"] == "portal@example.org"
    assert msg["To"] == "ops@example.org"
    assert msg["Reply-To"] == "alice@example.org"
    assert "alice" in msg["Subject"]
    assert "please add me" in msg.get_content()


def test_build_message_from_user_opt_in():
    settings = _settings(access_request_from="portal@x", access_request_from_user=True)
    msg = build_message("alice", "alice@example.org", "hi", settings)
    assert msg["From"] == "alice@example.org"


def test_build_message_from_user_falls_back_without_email():
    settings = _settings(access_request_from="portal@x", access_request_from_user=True)
    msg = build_message("alice", "", "hi", settings)
    assert msg["From"] == "portal@x"


def test_build_message_allows_multiline_body():
    settings = _settings(access_request_recipient="ops@x", access_request_from="p@x")
    msg = build_message("alice", "a@x", "line one\nline two", settings)
    assert "line one\nline two" in msg.get_content()


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
        build_message(user, email, "msg", settings)


# --- connection mode -------------------------------------------------------


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


async def test_send_access_request_passes_smtp_settings(monkeypatch):
    captured = {}

    async def fake_send(message, **kwargs):
        captured["message"] = message
        captured.update(kwargs)

    monkeypatch.setattr("app.mail.aiosmtplib.send", fake_send)
    settings = _settings(
        email_enabled=True,
        smtp_host="mail.svc",
        smtp_port=587,
        smtp_security="starttls",
        access_request_recipient="ops@x",
        access_request_from="p@x",
    )
    await send_access_request("alice", "a@x", "hi", settings)
    assert captured["hostname"] == "mail.svc"
    assert captured["port"] == 587
    assert captured["start_tls"] is True
    assert captured["use_tls"] is False
    assert captured["message"]["To"] == "ops@x"

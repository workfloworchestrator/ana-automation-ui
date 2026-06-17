"""Send access-request emails via the cluster SMTP relay."""

import asyncio
from collections.abc import Iterable
from email.message import EmailMessage

import aiosmtplib
import structlog

from app.config import Settings, SmtpSecurity

logger = structlog.get_logger(__name__)

_RETRYABLE = (aiosmtplib.SMTPException, OSError)
_MAX_ATTEMPTS = 3
_RETRY_DELAY = 2.0


class InvalidRequest(ValueError):
    """Raised when access-request header fields contain invalid characters."""


def _check_no_newlines(**fields: str) -> None:
    bad = next((name for name, value in fields.items() if "\r" in value or "\n" in value), None)
    if bad is not None:
        raise InvalidRequest(f"Invalid character in {bad}")


def build_message(user: str, email: str, message: str, groups: Iterable[str], settings: Settings) -> EmailMessage:
    """Build the access-request email, guarding header fields against injection."""
    _check_no_newlines(user=user, email=email)
    sender = email if settings.access_request_from_user and email else settings.access_request_from
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = settings.access_request_recipient
    if email:
        msg["Reply-To"] = email
    msg["Subject"] = f"ANA management portal access request from {email or user or 'an unknown user'}"
    groups_line = ", ".join(sorted(groups)) or "none"
    msg.set_content(f"Email:  {email}\nGroups: {groups_line}\n\nMessage:\n{message}\n")
    return msg


def _tls_flags(security: SmtpSecurity) -> tuple[bool, bool]:
    match security:
        case "tls":
            return (True, False)
        case "starttls":
            return (False, True)
        case _:
            return (False, False)


async def _deliver(message: EmailMessage, settings: Settings, attempts: int, delay: float) -> None:
    use_tls, start_tls = _tls_flags(settings.smtp_security)
    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password.get_secret_value() or None,
            use_tls=use_tls,
            start_tls=start_tls,
        )
    except _RETRYABLE as exc:
        if attempts <= 1:
            raise
        logger.warning(
            "Access-request email delivery failed, retrying",
            error=str(exc),
            retry_delay=delay,
            attempts_left=attempts - 1,
        )
        await asyncio.sleep(delay)
        await _deliver(message, settings, attempts - 1, delay)


async def send_access_request(
    user: str,
    email: str,
    message: str,
    groups: Iterable[str],
    settings: Settings,
    attempts: int = _MAX_ATTEMPTS,
    delay: float = _RETRY_DELAY,
) -> None:
    """Build and send the access-request email, retrying transient delivery failures."""
    msg = build_message(user, email, message, groups, settings)
    requester = email or user or "unknown"
    relay = f"{settings.smtp_host}:{settings.smtp_port}"
    try:
        await _deliver(msg, settings, attempts, delay)
    except _RETRYABLE as exc:
        logger.error("Access-request email delivery failed", requester=requester, relay=relay, error=str(exc))
        raise
    logger.info(
        "Access-request email sent",
        requester=requester,
        recipient=settings.access_request_recipient,
        relay=relay,
    )

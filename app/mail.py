"""Send access-request emails via the cluster SMTP relay."""

from email.message import EmailMessage

import aiosmtplib

from app.config import Settings, SmtpSecurity


class InvalidRequest(ValueError):
    """Raised when access-request header fields contain invalid characters."""


def _check_no_newlines(**fields: str) -> None:
    bad = next((name for name, value in fields.items() if "\r" in value or "\n" in value), None)
    if bad is not None:
        raise InvalidRequest(f"Invalid character in {bad}")


def build_message(user: str, email: str, message: str, settings: Settings) -> EmailMessage:
    """Build the access-request email, guarding header fields against injection."""
    _check_no_newlines(user=user, email=email)
    sender = email if settings.access_request_from_user and email else settings.access_request_from
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = settings.access_request_recipient
    if email:
        msg["Reply-To"] = email
    msg["Subject"] = f"Portal access request from {user or email or 'an unknown user'}"
    msg.set_content(f"User:  {user}\nEmail: {email}\n\nMessage:\n{message}\n")
    return msg


def _tls_flags(security: SmtpSecurity) -> tuple[bool, bool]:
    match security:
        case "tls":
            return (True, False)
        case "starttls":
            return (False, True)
        case _:
            return (False, False)


async def send_access_request(user: str, email: str, message: str, settings: Settings) -> None:
    """Build and send the access-request email via the configured SMTP relay."""
    msg = build_message(user, email, message, settings)
    use_tls, start_tls = _tls_flags(settings.smtp_security)
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        use_tls=use_tls,
        start_tls=start_tls,
    )

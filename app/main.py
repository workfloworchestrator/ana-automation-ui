from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from app.apps import app_views, load_apps
from app.auth import CurrentUser, get_current_user
from app.config import Settings, get_settings
from app.mail import InvalidRequest, send_access_request
from app.ratelimit import RateLimiter

# Inline styles are still used by the templates, so style-src allows 'unsafe-inline'
# for now; the redesign moves CSS to static/ and drops it. Scripts stay 'self' only.
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; form-action 'self'; "
    "frame-ancestors 'none'; base-uri 'none'"
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app = FastAPI(
    title="ANA Automation Portal",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

_access_request_limiter = RateLimiter(max_requests=3, window_seconds=300)


@app.middleware("http")
async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Attach a content-security-policy and standard hardening headers to every response."""
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    """Return a liveness probe response."""
    return "OK"


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Render the portal landing page with group-aware app stations."""
    views = app_views(load_apps(settings.apps_config_path), user.role)
    context = {"user": user, "apps": views, "email_enabled": settings.email_enabled}
    return templates.TemplateResponse(request, "index.html", context)


@app.post("/request-access", response_class=HTMLResponse)
async def request_access(
    request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    message: Annotated[str, Form()] = "",
) -> HTMLResponse:
    """Email an access request on behalf of the signed-in user."""
    if not settings.email_enabled:
        raise HTTPException(status_code=404)
    if not _access_request_limiter.allow(user.user or user.email or "anonymous"):
        raise HTTPException(status_code=429, detail="Too many requests, please try again later.")
    try:
        await send_access_request(user.user, user.email, message, user.groups, settings)
    except InvalidRequest as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return templates.TemplateResponse(request, "request_sent.html", {"user": user})


def run() -> None:
    """Start uvicorn for the ana-automation-ui console command."""
    import logging

    import uvicorn

    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("app").setLevel(logging.INFO)
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)

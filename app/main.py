from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.apps import app_views, load_apps
from app.auth import CurrentUser, get_current_user
from app.config import Settings, get_settings
from app.mail import InvalidRequest, send_access_request
from app.ratelimit import RateLimiter

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
    views = app_views(load_apps(settings.apps_config_path), user.role, settings)
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
        await send_access_request(user.user, user.email, message, settings)
    except InvalidRequest as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return templates.TemplateResponse(request, "request_sent.html", {"user": user})


def run() -> None:
    """Start uvicorn for the ana-automation-ui console command."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)

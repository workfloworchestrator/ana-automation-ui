from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.apps import app_views, load_apps
from app.auth import CurrentUser, get_current_user
from app.config import get_settings

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app = FastAPI(
    title="ANA Automation Portal",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    """Return a liveness probe response."""
    return "OK"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: Annotated[CurrentUser, Depends(get_current_user)]) -> HTMLResponse:
    """Render the portal landing page with group-aware app stations."""
    settings = get_settings()
    views = app_views(load_apps(settings.apps_config_path), user.role, settings)
    return templates.TemplateResponse(request, "index.html", {"user": user, "apps": views})


def run() -> None:
    """Start uvicorn for the ana-automation-ui console command."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)

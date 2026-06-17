import pytest

from app.config import Settings, get_settings
from app.main import _access_request_limiter


@pytest.fixture(autouse=True)
def _isolate_app_state(monkeypatch):
    """Isolate each test from the OS environment and shared process state.

    Settings reads os.environ, so clear every settings env var (derived from the model
    fields, so it can't drift), reset the settings cache, and reset the shared rate
    limiter, before and after each test.
    """
    [monkeypatch.delenv(field.upper(), raising=False) for field in Settings.model_fields]
    get_settings.cache_clear()
    _access_request_limiter._hits.clear()
    yield
    get_settings.cache_clear()
    _access_request_limiter._hits.clear()

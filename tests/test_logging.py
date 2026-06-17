import logging

import pytest
import structlog

from app.config import get_settings
from app.logging_config import _SuppressHealthCheck, configure_logging


@pytest.fixture(autouse=True)
def _restore_logging():
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)
    structlog.reset_defaults()
    get_settings.cache_clear()


def test_configure_logging_installs_single_structlog_handler(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "warning")
    get_settings.cache_clear()
    configure_logging()
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, structlog.stdlib.ProcessorFormatter)
    assert root.level == logging.WARNING


@pytest.mark.parametrize(
    ("message", "kept"),
    [
        pytest.param('1.2.3.4:0 - "GET /health HTTP/1.1" 200', False, id="health-dropped"),
        pytest.param('1.2.3.4:0 - "GET /aura/ HTTP/1.1" 200', True, id="other-kept"),
    ],
)
def test_health_access_log_filter(message, kept):
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, message, (), None)
    assert _SuppressHealthCheck().filter(record) is kept

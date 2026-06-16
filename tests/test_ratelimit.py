from app.ratelimit import RateLimiter


def test_blocks_after_limit():
    limiter = RateLimiter(max_requests=2, window_seconds=10, clock=lambda: 0.0)
    assert limiter.allow("u") is True
    assert limiter.allow("u") is True
    assert limiter.allow("u") is False


def test_window_expiry_allows_again():
    now = [0.0]
    limiter = RateLimiter(max_requests=1, window_seconds=10, clock=lambda: now[0])
    assert limiter.allow("u") is True
    assert limiter.allow("u") is False
    now[0] = 11.0
    assert limiter.allow("u") is True


def test_keys_are_independent():
    limiter = RateLimiter(max_requests=1, window_seconds=10, clock=lambda: 0.0)
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("a") is False

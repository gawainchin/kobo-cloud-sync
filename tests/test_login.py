import pytest

from kobo_cloud_sync.login import (
    _extract_cookie_list,
    _kobo_cookies_from_export,
    _looks_like_browser_challenge,
)


class FakeLocator:
    def __init__(self, text):
        self.text = text

    def inner_text(self, timeout=2000):
        return self.text


class FakePage:
    def __init__(self, title="", body=""):
        self._title = title
        self._body = body

    def title(self):
        return self._title

    def locator(self, selector):
        assert selector == "body"
        return FakeLocator(self._body)


def test_browser_challenge_detects_cloudflare_title():
    page = FakePage(title="Just a moment...")

    assert _looks_like_browser_challenge(page)


def test_browser_challenge_detects_verification_body():
    page = FakePage(body="Checking your browser before accessing Kobo.")

    assert _looks_like_browser_challenge(page)


def test_browser_challenge_ignores_normal_page():
    page = FakePage(title="My Books | Rakuten Kobo", body="My Books")

    assert not _looks_like_browser_challenge(page)


def test_extract_cookie_list_accepts_raw_list():
    cookies = [{"domain": ".kobo.com", "name": "session", "value": "redacted"}]

    assert _extract_cookie_list(cookies) == cookies


def test_extract_cookie_list_accepts_wrapped_export():
    cookie = {"domain": ".kobo.com", "name": "session", "value": "redacted"}

    assert _extract_cookie_list(
        {"url": "https://www.kobo.com", "cookies": [cookie]}
    ) == [cookie]


def test_extract_cookie_list_rejects_invalid_shape():
    with pytest.raises(ValueError, match="JSON list or an object with a cookies list"):
        _extract_cookie_list({"url": "https://www.kobo.com"})


def test_kobo_cookies_from_export_rejects_zero_kobo_cookies():
    raw_cookies = [
        {"domain": ".example.com", "name": "session", "value": "redacted"},
    ]

    with pytest.raises(ValueError, match="did not contain any Kobo cookies"):
        _kobo_cookies_from_export(raw_cookies)


def test_kobo_cookies_from_export_converts_kobo_cookies():
    raw_cookies = [
        {
            "domain": ".kobo.com",
            "name": "session",
            "path": "/",
            "value": "redacted",
        },
    ]

    cookies = _kobo_cookies_from_export(raw_cookies)

    assert len(cookies) == 1
    assert cookies[0]["domain"] == ".kobo.com"
    assert cookies[0]["name"] == "session"

import pytest

from kobo_cloud_sync import login as login_module
from kobo_cloud_sync.login import (
    _add_cookies_resilient,
    _cookie_from_chrome_export,
    _extract_cookie_list,
    _has_kobo_session_cookies,
    _is_kobo_domain,
    _kobo_cookies_from_export,
    _looks_like_browser_challenge,
    diagnose_session,
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


def test_kobo_cookies_keeps_subdomain_cookies():
    raw_cookies = [
        {
            "domain": "authorize.kobo.com",
            "name": "auth",
            "value": "redacted",
        },
        {
            "domain": ".readnow.kobo.com",
            "name": "reader",
            "value": "redacted",
        },
        {
            "domain": ".malicious-kobo.com.evil.test",
            "name": "spoof",
            "value": "redacted",
        },
    ]

    cookies = _kobo_cookies_from_export(raw_cookies)

    domains = sorted(cookie["domain"] for cookie in cookies)
    assert domains == [".readnow.kobo.com", "authorize.kobo.com"]


def test_cookie_normalization_forces_secure_for_samesite_none():
    cookie = _cookie_from_chrome_export(
        {
            "domain": ".kobo.com",
            "name": "session",
            "value": "redacted",
            "path": "/",
            "sameSite": "no_restriction",
            "secure": False,
        }
    )

    assert cookie is not None
    assert cookie["sameSite"] == "None"
    assert cookie["secure"] is True


def test_cookie_normalization_drops_cookies_missing_required_fields():
    assert _cookie_from_chrome_export({"name": "x", "value": "y"}) is None
    assert (
        _cookie_from_chrome_export(
            {"domain": ".kobo.com", "value": "y", "path": "/"}
        )
        is None
    )


def test_is_kobo_domain_only_matches_kobo_subtree():
    assert _is_kobo_domain(".kobo.com")
    assert _is_kobo_domain("www.kobo.com")
    assert _is_kobo_domain("authorize.kobo.com")
    assert not _is_kobo_domain("example.com")
    assert not _is_kobo_domain("kobo.com.evil.test")


def test_has_kobo_session_cookies():
    assert _has_kobo_session_cookies(
        [{"domain": ".kobo.com", "name": "x", "value": "y"}]
    )
    assert not _has_kobo_session_cookies(
        [{"domain": ".example.com", "name": "x", "value": "y"}]
    )
    assert not _has_kobo_session_cookies([])


class _FakeContext:
    def __init__(self, fail_first_batch=True, bad_cookies=None):
        self.fail_first_batch = fail_first_batch
        self.bad_cookies = set(bad_cookies or [])
        self.added: list[dict] = []
        self.batch_calls = 0

    def add_cookies(self, cookies):
        if len(cookies) > 1 and self.fail_first_batch:
            self.batch_calls += 1
            raise RuntimeError("simulated batch failure")
        for cookie in cookies:
            if cookie.get("name") in self.bad_cookies:
                raise RuntimeError(f"bad cookie {cookie['name']}")
            self.added.append(cookie)


def test_add_cookies_resilient_falls_back_to_per_cookie():
    context = _FakeContext(fail_first_batch=True, bad_cookies={"bad"})
    cookies = [
        {"name": "good1", "domain": ".kobo.com", "value": "1"},
        {"name": "bad", "domain": ".kobo.com", "value": "2"},
        {"name": "good2", "domain": ".kobo.com", "value": "3"},
    ]

    accepted, rejected = _add_cookies_resilient(context, cookies)

    assert accepted == 2
    assert len(rejected) == 1
    assert "bad@.kobo.com" in rejected[0]
    assert [c["name"] for c in context.added] == ["good1", "good2"]


def test_add_cookies_resilient_uses_batch_when_possible():
    context = _FakeContext(fail_first_batch=False)
    cookies = [
        {"name": "a", "domain": ".kobo.com", "value": "1"},
        {"name": "b", "domain": ".kobo.com", "value": "2"},
    ]

    accepted, rejected = _add_cookies_resilient(context, cookies)

    assert accepted == 2
    assert rejected == []


def test_diagnose_session_uses_stored_cookies(monkeypatch):
    monkeypatch.setattr(
        login_module,
        "_load_stored_cookies",
        lambda: [{"domain": ".kobo.com", "name": "session", "value": "x"}],
    )

    def explode_playwright():
        raise AssertionError("Playwright should not run when cookies are stored")

    monkeypatch.setattr(login_module, "sync_playwright", explode_playwright)

    diagnosis = diagnose_session()

    assert diagnosis.connected
    assert "stored cookies" in diagnosis.message


def test_diagnose_session_returns_empty_profile_when_nothing_stored(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(login_module, "_load_stored_cookies", lambda: [])
    monkeypatch.setattr(
        login_module, "BROWSER_PROFILE_DIR", tmp_path / "missing-profile"
    )

    diagnosis = diagnose_session()

    assert diagnosis.status == "empty_profile"

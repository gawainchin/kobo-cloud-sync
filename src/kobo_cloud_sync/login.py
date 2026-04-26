import json
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Literal, Optional
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from .config import BROWSER_PROFILE_DIR, kobo_url

KOBO_HOME_URL = "https://www.kobo.com/"
KOBO_ACCOUNT_URL = "https://www.kobo.com/account"
AUTH_HOSTS = ("accounts.google.com", "accounts.kobo.com", "authorize.kobo.com")

SessionStatus = Literal[
    "connected",
    "not_signed_in",
    "browser_verification",
    "empty_profile",
]


@dataclass
class SessionCheck:
    status: SessionStatus
    message: str

    @property
    def connected(self) -> bool:
        return self.status == "connected"


def _open_context(playwright: Playwright, headless: bool) -> BrowserContext:
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        str(BROWSER_PROFILE_DIR),
        headless=headless,
    )


def _same_site(value: Optional[str]) -> Optional[str]:
    mapping = {
        "lax": "Lax",
        "strict": "Strict",
        "no_restriction": "None",
        "none": "None",
    }
    return mapping.get((value or "").lower())


def _cookie_from_chrome_export(cookie: dict) -> dict:
    converted = {
        "name": cookie["name"],
        "value": cookie["value"],
        "domain": cookie["domain"],
        "path": cookie.get("path", "/"),
        "httpOnly": bool(cookie.get("httpOnly", False)),
        "secure": bool(cookie.get("secure", False)),
    }

    if not cookie.get("session") and "expirationDate" in cookie:
        converted["expires"] = int(cookie["expirationDate"])

    same_site = _same_site(cookie.get("sameSite"))
    if same_site:
        converted["sameSite"] = same_site

    return converted


def _extract_cookie_list(raw_cookies: object) -> list[dict]:
    if isinstance(raw_cookies, list):
        return [cookie for cookie in raw_cookies if isinstance(cookie, dict)]
    if isinstance(raw_cookies, dict):
        cookies = raw_cookies.get("cookies")
        if isinstance(cookies, list):
            return [cookie for cookie in cookies if isinstance(cookie, dict)]
    raise ValueError(
        "Cookie export must be a JSON list or an object with a cookies list."
    )


def _kobo_cookies_from_export(raw_cookies: object) -> list[dict]:
    cookie_list = _extract_cookie_list(raw_cookies)
    cookies = [
        _cookie_from_chrome_export(cookie)
        for cookie in cookie_list
        if cookie.get("domain", "").endswith("kobo.com")
    ]
    if not cookies:
        raise ValueError("Cookie export did not contain any Kobo cookies.")
    return cookies


def _import_cookie_list(raw_cookies: object) -> int:
    cookies = _kobo_cookies_from_export(raw_cookies)
    with sync_playwright() as playwright:
        context = _open_context(playwright, headless=True)
        try:
            context.add_cookies(cookies)
        finally:
            context.close()

    return len(cookies)


def import_cookies(cookie_path: Path) -> int:
    """Import Chrome-exported cookies into the persistent Kobo browser profile."""
    return _import_cookie_list(json.loads(cookie_path.read_text()))


def import_cookies_content(cookie_content: bytes) -> int:
    """Import Chrome-exported cookie JSON bytes into the persistent browser profile."""
    return _import_cookie_list(json.loads(cookie_content.decode("utf-8")))


def _get_page(context: BrowserContext) -> Page:
    return context.pages[0] if context.pages else context.new_page()


def _library_url() -> str:
    return kobo_url("library/books")


def _is_auth_url(url: str) -> bool:
    normalized = url.lower()
    return (
        any(host in normalized for host in AUTH_HOSTS)
        or "signin" in normalized
        or "sign-in" in normalized
    )


def _is_library_url(url: str) -> bool:
    return "/library/books" in urlparse(url.lower()).path


def _looks_like_login_page(page: Page) -> bool:
    try:
        body = page.locator("body").inner_text(timeout=2000).lower()
    except Exception:
        return False
    return "sign in with google" in body or (
        "email address" in body and "password" in body
    )


def _looks_like_browser_challenge(page: Page) -> bool:
    try:
        title = page.title().lower()
    except Exception:
        title = ""
    try:
        body = page.locator("body").inner_text(timeout=2000).lower()
    except Exception:
        body = ""

    return (
        "just a moment" in title
        or "checking your browser" in body
        or "verify you are human" in body
        or "cf-challenge" in body
    )


def _looks_logged_in(
    page: Page,
    navigate: bool = True,
    timeout_ms: int = 30000,
) -> bool:
    if navigate:
        page.goto(_library_url(), wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass

    current_url = page.url.lower()
    if _is_auth_url(current_url):
        return False
    if _looks_like_login_page(page):
        return False
    if _looks_like_browser_challenge(page):
        return False

    return _is_library_url(current_url)


def _diagnose_current_page(page: Page) -> SessionCheck:
    if _looks_like_browser_challenge(page):
        return SessionCheck(
            "browser_verification",
            "Kobo is showing a browser verification page to Playwright.",
        )
    if _is_auth_url(page.url) or _looks_like_login_page(page):
        return SessionCheck(
            "not_signed_in",
            "Kobo session is not signed in.",
        )
    if _is_library_url(page.url):
        return SessionCheck("connected", "Kobo session is connected.")
    return SessionCheck(
        "not_signed_in",
        "Kobo did not open the signed-in library page.",
    )


def login_interactive(timeout_seconds: int = 300, close_browser: bool = True) -> bool:
    """Open a persistent browser and let the user log into Kobo manually."""
    with sync_playwright() as playwright:
        context = _open_context(playwright, headless=False)
        try:
            page = _get_page(context)
            page.goto(_library_url(), wait_until="domcontentloaded")
            print("Browser opened for Kobo login.")
            print("If you use Google auth, choose 'Continue with Google' in the page.")
            print(f"Waiting up to {timeout_seconds} seconds for login to complete...")
            deadline = time.time() + timeout_seconds
            success = False
            while time.time() < deadline:
                try:
                    current_page = context.pages[-1] if context.pages else page
                    current_url = current_page.url
                    if any(host in current_url for host in AUTH_HOSTS):
                        time.sleep(2)
                        continue
                    if _looks_logged_in(current_page, navigate=True):
                        success = True
                        break
                except Exception:
                    pass
                time.sleep(2)
            if success:
                print(f"Saved browser session in {BROWSER_PROFILE_DIR}")
            else:
                print("Timed out waiting for Kobo login to complete.")
            return success
        finally:
            if close_browser:
                context.close()
            else:
                print("Leaving browser open. Press Ctrl+C in this terminal to stop it.")
                while True:
                    time.sleep(60)


def check_session() -> bool:
    """Check whether the saved browser session is still valid."""
    return diagnose_session().connected


def diagnose_session() -> SessionCheck:
    """Check saved browser session and explain the current auth state."""
    if not Path(BROWSER_PROFILE_DIR).exists():
        return SessionCheck(
            "empty_profile",
            "No Kobo browser profile exists yet.",
        )

    try:
        with sync_playwright() as playwright:
            context = _open_context(playwright, headless=True)
            try:
                page = _get_page(context)
                page.set_default_timeout(5000)
                page.set_default_navigation_timeout(5000)
                page.goto(_library_url(), wait_until="domcontentloaded", timeout=5000)
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                return _diagnose_current_page(page)
            finally:
                context.close()
    except Exception:
        return SessionCheck(
            "not_signed_in",
            "Kobo session could not be validated.",
        )

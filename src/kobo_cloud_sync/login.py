import json
from pathlib import Path
import time
from typing import Optional

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from .config import BROWSER_PROFILE_DIR, kobo_url

KOBO_HOME_URL = "https://www.kobo.com/"
KOBO_ACCOUNT_URL = "https://www.kobo.com/account"
KOBO_SIGNIN_URL = kobo_url()
KOBO_LIBRARY_URL = kobo_url("library/books")
AUTH_HOSTS = ("accounts.google.com", "accounts.kobo.com", "authorize.kobo.com")


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


def import_cookies(cookie_path: Path) -> int:
    """Import Chrome-exported cookies into the persistent Kobo browser profile."""
    raw_cookies = json.loads(cookie_path.read_text())
    cookies = [
        _cookie_from_chrome_export(cookie)
        for cookie in raw_cookies
        if cookie.get("domain", "").endswith("kobo.com")
    ]

    with sync_playwright() as playwright:
        context = _open_context(playwright, headless=False)
        try:
            context.add_cookies(cookies)
        finally:
            context.close()

    return len(cookies)


def _get_page(context: BrowserContext) -> Page:
    return context.pages[0] if context.pages else context.new_page()


def _looks_logged_in(page: Page, navigate: bool = True) -> bool:
    if navigate:
        page.goto(KOBO_LIBRARY_URL, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

    current_url = page.url.lower()
    if any(host in current_url for host in AUTH_HOSTS):
        return False
    if "signin" in current_url or "sign-in" in current_url:
        return False

    try:
        body = page.locator("body").inner_text(timeout=2000).lower()
    except Exception:
        body = ""
    if "sign in with google" in body or "email address" in body and "password" in body:
        return False

    return "kobo.com" in current_url


def login_interactive(timeout_seconds: int = 300, close_browser: bool = True) -> bool:
    """Open a persistent browser and let the user log into Kobo manually."""
    with sync_playwright() as playwright:
        context = _open_context(playwright, headless=False)
        try:
            page = _get_page(context)
            page.goto(KOBO_LIBRARY_URL, wait_until="domcontentloaded")
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
    if not Path(BROWSER_PROFILE_DIR).exists():
        return False

    try:
        with sync_playwright() as playwright:
            context = _open_context(playwright, headless=True)
            try:
                page = _get_page(context)
                return _looks_logged_in(page)
            finally:
                context.close()
    except Exception:
        return False

import json
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Iterable, Literal, Optional
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from .config import BROWSER_PROFILE_DIR, STORED_COOKIES_FILE, kobo_url

KOBO_HOME_URL = "https://www.kobo.com/"
KOBO_ACCOUNT_URL = "https://www.kobo.com/account"
AUTH_HOSTS = ("accounts.google.com", "accounts.kobo.com", "authorize.kobo.com")
KOBO_DOMAIN_SUFFIX = "kobo.com"

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


@dataclass
class CookieImportResult:
    accepted: int
    rejected: int
    domains: list[str]
    rejected_reasons: list[str]


def _open_context(playwright: Playwright, headless: bool) -> BrowserContext:
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    context = playwright.chromium.launch_persistent_context(
        str(BROWSER_PROFILE_DIR),
        headless=headless,
    )
    _apply_stored_cookies(context)
    return context


def _same_site(value: Optional[str]) -> Optional[str]:
    mapping = {
        "lax": "Lax",
        "strict": "Strict",
        "no_restriction": "None",
        "none": "None",
    }
    return mapping.get((value or "").lower())


def _cookie_from_chrome_export(cookie: dict) -> Optional[dict]:
    """Convert a Chrome-exported cookie into a Playwright cookie payload.

    Returns None if the cookie is missing required fields. Auto-corrects
    ``sameSite=None`` cookies to ``secure=True`` because Playwright (and modern
    browsers) reject ``SameSite=None`` cookies that are not secure.
    """
    name = cookie.get("name")
    value = cookie.get("value")
    domain = cookie.get("domain")
    if not name or value is None or not domain:
        return None

    converted = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": cookie.get("path") or "/",
        "httpOnly": bool(cookie.get("httpOnly", False)),
        "secure": bool(cookie.get("secure", False)),
    }

    if not cookie.get("session") and "expirationDate" in cookie:
        try:
            converted["expires"] = int(cookie["expirationDate"])
        except (TypeError, ValueError):
            pass

    same_site = _same_site(cookie.get("sameSite"))
    if same_site:
        converted["sameSite"] = same_site
        if same_site == "None":
            converted["secure"] = True

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


def _is_kobo_domain(domain: str) -> bool:
    if not domain:
        return False
    normalized = domain.lstrip(".").lower()
    return normalized == KOBO_DOMAIN_SUFFIX or normalized.endswith(
        "." + KOBO_DOMAIN_SUFFIX
    )


def _kobo_cookies_from_export(raw_cookies: object) -> list[dict]:
    cookie_list = _extract_cookie_list(raw_cookies)
    cookies: list[dict] = []
    for cookie in cookie_list:
        if not _is_kobo_domain(str(cookie.get("domain", ""))):
            continue
        normalized = _cookie_from_chrome_export(cookie)
        if normalized is not None:
            cookies.append(normalized)
    if not cookies:
        raise ValueError("Cookie export did not contain any Kobo cookies.")
    return cookies


def _save_stored_cookies(cookies: list[dict]) -> None:
    STORED_COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    STORED_COOKIES_FILE.write_text(json.dumps(cookies, indent=2))


def _load_stored_cookies() -> list[dict]:
    if not STORED_COOKIES_FILE.exists():
        return []
    try:
        data = json.loads(STORED_COOKIES_FILE.read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [cookie for cookie in data if isinstance(cookie, dict)]


def _add_cookies_resilient(
    context: BrowserContext, cookies: list[dict]
) -> tuple[int, list[str]]:
    """Add cookies one-by-one so a single bad cookie doesn't kill the batch.

    Returns ``(accepted_count, rejected_reasons)``.
    """
    accepted = 0
    rejected: list[str] = []
    try:
        context.add_cookies(cookies)
        return len(cookies), []
    except Exception:
        pass

    for cookie in cookies:
        try:
            context.add_cookies([cookie])
            accepted += 1
        except Exception as exc:
            rejected.append(
                f"{cookie.get('name', '?')}@{cookie.get('domain', '?')}: {exc}"
            )
    return accepted, rejected


def _apply_stored_cookies(context: BrowserContext) -> int:
    """Re-apply previously imported cookies into a freshly opened context.

    Persistent Chromium profiles do not always carry programmatically-added
    cookies across launches, so we keep a JSON copy and re-apply it on every
    context open. This is the difference between "I imported cookies once" and
    "every check actually has those cookies".
    """
    cookies = _load_stored_cookies()
    if not cookies:
        return 0
    accepted, _ = _add_cookies_resilient(context, cookies)
    return accepted


def _import_cookie_list(raw_cookies: object) -> CookieImportResult:
    cookies = _kobo_cookies_from_export(raw_cookies)
    domains = sorted({str(cookie.get("domain", "")) for cookie in cookies})

    with sync_playwright() as playwright:
        context = _open_context(playwright, headless=True)
        try:
            accepted, rejected_reasons = _add_cookies_resilient(context, cookies)
        finally:
            context.close()

    if accepted == 0:
        raise ValueError(
            "Playwright rejected every imported cookie. "
            "First reason: "
            + (rejected_reasons[0] if rejected_reasons else "unknown")
        )

    _save_stored_cookies(cookies)

    return CookieImportResult(
        accepted=accepted,
        rejected=len(rejected_reasons),
        domains=domains,
        rejected_reasons=rejected_reasons,
    )


def import_cookies(cookie_path: Path) -> int:
    """Import Chrome-exported cookies into the persistent Kobo browser profile."""
    return _import_cookie_list(json.loads(cookie_path.read_text())).accepted


def import_cookies_content(cookie_content: bytes) -> int:
    """Import Chrome-exported cookie JSON bytes into the persistent browser profile."""
    return _import_cookie_list(json.loads(cookie_content.decode("utf-8"))).accepted


def import_cookies_detailed(cookie_content: bytes) -> CookieImportResult:
    """Import cookies and return a detailed report (for surfacing in the UI)."""
    return _import_cookie_list(json.loads(cookie_content.decode("utf-8")))


def _has_kobo_session_cookies(cookies: Iterable[dict]) -> bool:
    """Heuristic: do the cookies look like a real signed-in Kobo session?

    Any cookie attached to a kobo.com domain is enough to consider the session
    "imported". Real sign-in adds dozens of these (KoboLogin, KoboCart, ke.t,
    cf_clearance, etc.); a brand-new profile has none.
    """
    for cookie in cookies:
        if _is_kobo_domain(str(cookie.get("domain", ""))):
            return True
    return False


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
                try:
                    cookies = context.cookies()
                    kobo_cookies = [
                        cookie
                        for cookie in cookies
                        if _is_kobo_domain(str(cookie.get("domain", "")))
                    ]
                    if kobo_cookies:
                        _save_stored_cookies(kobo_cookies)
                except Exception:
                    pass
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
    """Check saved browser session and explain the current auth state.

    Strategy:
    1. If we have stored Kobo cookies, trust them as "connected" rather than
       letting Cloudflare's headless-Chromium challenge produce a misleading
       "not signed in" verdict. The real sync runs a visible browser and will
       use these cookies.
    2. Otherwise, fall back to a Playwright probe of the library page.
    """
    stored_cookies = _load_stored_cookies()
    if _has_kobo_session_cookies(stored_cookies):
        return SessionCheck(
            "connected",
            f"Kobo session is connected ({len(stored_cookies)} stored cookies).",
        )

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

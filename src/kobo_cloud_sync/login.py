from playwright.sync_api import sync_playwright

from .config import KOBO_EMAIL, KOBO_PASSWORD


def get_logged_in_browser():
    """Return a playwright browser page logged into Kobo."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch()
    page = browser.new_page()
    page.goto("https://accounts.kobo.com")
    # TODO: real login flow with selectors
    page.wait_for_load_state("networkidle")
    return page, browser


def check_session() -> bool:
    """Check if a Kobo session is already valid."""
    try:
        page, browser = get_logged_in_browser()
        page.goto("https://www.kobo.com/ee/welcome")
        browser.close()
        return True
    except Exception:
        return False

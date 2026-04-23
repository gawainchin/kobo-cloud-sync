from playwright.sync_api import sync_playwright

from .config import KOBO_EMAIL, KOBO_PASSWORD


def export_annotations(book_id: str, output_path: str) -> None:
    """Download annotation export for a given book."""
    # TODO: implement real Kobo export navigation
    raise NotImplementedError("Export flow not yet wired to real selectors")

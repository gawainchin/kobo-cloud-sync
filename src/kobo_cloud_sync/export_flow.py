from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

from .config import BROWSER_PROFILE_DIR, kobo_url
from .login import _open_context
from .models import Annotation, Book


def export_annotations(book_id: str, output_path: str) -> None:
    """Download annotation export for a given book."""
    # TODO: implement real Kobo export navigation
    raise NotImplementedError("Export flow not yet wired to real selectors")


def _normalize_url(url: str) -> str:
    if url.startswith("//"):
        return f"https:{url}"
    return url


def _book_id_from_url(detail_url: str, fallback: str) -> str:
    path = urlparse(detail_url).path.rstrip("/")
    if path:
        return path.split("/")[-1]
    return fallback


def _reader_id_from_url(read_url: str) -> str:
    if not read_url:
        return ""
    path = urlparse(read_url).path.strip("/")
    return path.split("/")[0] if path else ""


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _annotations_from_payload(payload: dict) -> list[Annotation]:
    annotations = []
    for item in payload.get("annotations", []):
        highlighted_text = item.get("highlightedText") or ""
        if not highlighted_text:
            continue
        location = item.get("location") or {}
        span = location.get("span") or {}
        attachments = item.get("attachments") or {}
        note = attachments.get("note") or attachments.get("text") or ""
        annotations.append(
            Annotation(
                highlight=highlighted_text,
                note=note,
                chapter=span.get("chapterTitle", ""),
                created_at=_parse_datetime(item.get("clientLastModifiedUtc")),
            )
        )
    return annotations


def _fetch_annotations(page: Page, reader_id: str) -> list[Annotation]:
    if not reader_id:
        return []

    page.goto(
        f"https://readnow.kobo.com/{reader_id}?locale=en-US",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    page.wait_for_timeout(3000)
    api_url = f"https://readingservices.kobo.com/api/v3/content/{reader_id}/annotations"
    payload = page.evaluate(
        """async url => {
            const response = await fetch(url, { credentials: "include" });
            if (!response.ok) {
                return { annotations: [] };
            }
            return await response.json();
        }""",
        api_url,
    )
    return _annotations_from_payload(payload)


def _scrape_page(page: Page) -> list[Book]:
    items = page.locator("li.item-wrapper").evaluate_all(
        """
        items => items.map(item => {
            const text = selector => item.querySelector(selector)?.innerText?.trim() || "";
            const href = selector => item.querySelector(selector)?.href || "";
            const titleLink = item.querySelector("h2.title a");
            const viewDetails = item.querySelector("a.view-details");
            const titleHref = titleLink?.href || "";
            const detailLink = viewDetails || (titleHref.includes("/ebook/") ? titleLink : null);
            const readLink = item.querySelector("a.readnow");
            const cover = item.querySelector("img.cover-image");
            let trackInfo = {};
            try {
                trackInfo = JSON.parse(item.getAttribute("data-track-info") || "{}");
            } catch (_) {}

            return {
                product_id: trackInfo.productId || "",
                title: titleLink?.innerText?.trim() || trackInfo.title || "",
                subtitle: text(".subtitle"),
                author: text(".authors .visible-contributors") || text(".authors"),
                series: text(".series"),
                genre: text(".genre"),
                status: text(".product-field.item-status"),
                date_added: text(".date-added"),
                cover_image_url: cover?.currentSrc || cover?.getAttribute("src") || "",
                detail_url: detailLink?.href || "",
                read_url: readLink?.href || "",
            };
        }).filter(item => item.title)
        """
    )

    books = []
    for item in items:
        detail_url = item.get("detail_url", "")
        product_id = item.get("product_id", "")
        books.append(
            Book(
                id=_book_id_from_url(detail_url, product_id),
                title=item.get("title", ""),
                author=item.get("author", ""),
                subtitle=item.get("subtitle", ""),
                series=item.get("series", ""),
                genre=item.get("genre", ""),
                status=item.get("status", ""),
                date_added=item.get("date_added", ""),
                cover_image_url=_normalize_url(item.get("cover_image_url", "")),
                detail_url=detail_url,
                read_url=item.get("read_url", ""),
            )
        )
    return books


def list_library_books(page_size: int = 60, include_annotations: bool = False) -> list[Book]:
    """Scrape all books from the signed-in Kobo library."""
    books_by_id: dict[str, Book] = {}

    with sync_playwright() as playwright:
        context = _open_context(playwright, headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page_number = 1
            while True:
                page.goto(
                    kobo_url(
                        f"library/books?pageSize={page_size}&pageNumber={page_number}"
                    ),
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                page.wait_for_timeout(3000)

                page_books = _scrape_page(page)
                if not page_books:
                    break

                previous_count = len(books_by_id)
                for book in page_books:
                    books_by_id[book.id] = book

                has_next = page.locator(
                    f'a[href*="pageNumber={page_number + 1}"]'
                ).count()
                if not has_next or len(books_by_id) == previous_count:
                    break
                page_number += 1

            if include_annotations:
                for book in books_by_id.values():
                    reader_id = _reader_id_from_url(book.read_url)
                    if not reader_id:
                        continue
                    try:
                        book.annotations = _fetch_annotations(page, reader_id)
                    except Exception as exc:
                        print(f"Could not sync highlights for {book.title}: {exc}")
        finally:
            context.close()

    return list(books_by_id.values())

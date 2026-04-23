from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import COVERS_DIR, MARKDOWN_DIR, OBSIDIAN_VAULT_PATH
from .models import Book
from .parser import book_to_markdown

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.kobo.com/",
}


def safe_filename(value: str) -> str:
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in value).strip()
    return safe or "Untitled"


def _cover_extension(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix
    return suffix if suffix else ".jpg"


def download_cover(book: Book, covers_dir: Path = COVERS_DIR) -> Book:
    if not book.cover_image_url:
        return book

    covers_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_filename(book.title)}{_cover_extension(book.cover_image_url)}"
    out_path = covers_dir / filename
    if not out_path.exists():
        request = Request(book.cover_image_url, headers=REQUEST_HEADERS)
        with urlopen(request) as response:
            out_path.write_bytes(response.read())
    if out_path.exists():
        book.cover_image_path = f"covers/{filename}"
    return book


def publish_book(book: Book, output_dir: Optional[Path] = None) -> Path:
    """Write a book as Markdown notes into the Obsidian vault."""
    target_dir = output_dir or OBSIDIAN_VAULT_PATH or MARKDOWN_DIR

    target_dir.mkdir(parents=True, exist_ok=True)

    safe_title = safe_filename(book.title)
    out_path = target_dir / f"{safe_title}.md"
    out_path.write_text(book_to_markdown(book))
    return out_path


def publish_books(books: list[Book], output_dir: Path = MARKDOWN_DIR) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for book in books:
        try:
            download_cover(book, output_dir / "covers")
        except Exception as exc:
            print(f"Could not download cover for {book.title}: {exc}")
        paths.append(publish_book(book, output_dir))
    return paths

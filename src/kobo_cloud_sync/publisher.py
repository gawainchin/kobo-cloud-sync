from pathlib import Path
from .config import OBSIDIAN_VAULT_PATH
from .models import Book
from .parser import book_to_markdown


def publish_book(book: Book) -> None:
    """Write a book as Markdown notes into the Obsidian vault."""
    if not OBSIDIAN_VAULT_PATH.exists():
        raise FileNotFoundError(f"Obsidian vault not found: {OBSIDIAN_VAULT_PATH}")

    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in book.title)
    out_path = OBSIDIAN_VAULT_PATH / f"{safe_title}.md"
    out_path.write_text(book_to_markdown(book))

from pathlib import Path
from .models import Book, Annotation


def parse_export(html_path: Path) -> Book:
    """Parse a Kobo export HTML into a Book model."""
    # TODO: implement real parser against actual Kobo export format
    content = html_path.read_text()
    return Book(id="", title=html_path.stem, author="Unknown", annotations=[])


def book_to_markdown(book: Book) -> str:
    lines = [f"# {book.title}\n\n*{book.author}*\n"]
    for ann in book.annotations:
        lines.append(f"> {ann.highlight}\n")
        if ann.note:
            lines.append(f"_Note: {ann.note}_\n")
    return "\n".join(lines)

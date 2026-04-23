from pathlib import Path
from .models import Book, Annotation


def parse_export(html_path: Path) -> Book:
    """Parse a Kobo export HTML into a Book model."""
    # TODO: implement real parser against actual Kobo export format
    content = html_path.read_text()
    return Book(id="", title=html_path.stem, author="Unknown", annotations=[])


def book_to_markdown(book: Book) -> str:
    lines = [f"# {book.title}\n"]
    if book.cover_image_path:
        lines.append(f"![Cover]({book.cover_image_path})\n")
    elif book.cover_image_url:
        lines.append(f"![Cover]({book.cover_image_url})\n")

    if book.author:
        lines.append(f"*{book.author}*\n")
    if book.subtitle:
        lines.append(f"\n**Subtitle:** {book.subtitle}")
    if book.series:
        lines.append(f"\n**Series:** {book.series}")
    if book.genre:
        lines.append(f"\n**Genre:** {book.genre}")
    if book.status:
        lines.append(f"\n**Status:** {book.status}")
    if book.date_added:
        lines.append(f"\n**Date Added:** {book.date_added}")
    if book.detail_url:
        lines.append(f"\n**Kobo:** {book.detail_url}")
    if book.read_url:
        lines.append(f"\n**Read Now:** {book.read_url}")

    lines.append("\n\n## Highlights\n")
    if not book.annotations:
        lines.append("_No highlights synced yet._\n")
    for ann in book.annotations:
        if ann.chapter:
            lines.append(f"### {ann.chapter}\n")
        lines.append(f"> {ann.highlight}\n")
        if ann.note:
            lines.append(f"_Note: {ann.note}_\n")
    return "\n".join(lines)

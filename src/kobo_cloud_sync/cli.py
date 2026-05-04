import argparse
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import __version__
from .config import MARKDOWN_DIR, STATE_FILE
from .parser import parse_export
from .publisher import publish_books
from .state import State
from .web import serve


def _format_book_summary(book, include_details: bool = False) -> str:
    author = f" by {book.author}" if book.author else ""
    status = f" [{book.status}]" if book.status else ""
    summary = f"{book.title}{author}{status}"
    if include_details:
        details = [f"id: {book.id}"]
        if book.read_url:
            details.append(f"read: {book.read_url}")
        if book.detail_url:
            details.append(f"kobo: {book.detail_url}")
        summary = f"{summary} ({'; '.join(details)})"
    return summary


def _book_payload_for_change_check(book) -> dict:
    payload = asdict(book)
    payload.pop("cover_image_path", None)
    payload.pop("last_synced", None)
    return payload


def _book_changed(previous, current) -> bool:
    if previous is None:
        return True
    return _book_payload_for_change_check(previous) != _book_payload_for_change_check(
        current
    )


def _merge_highlights_only(previous, current):
    if previous is None:
        return current
    return replace(
        previous,
        read_url=current.read_url or previous.read_url,
        detail_url=current.detail_url or previous.detail_url,
        annotations=current.annotations,
    )


def _pick_books(books) -> list:
    if not books:
        return []
    for index, book in enumerate(books, start=1):
        print(f"{index}. {_format_book_summary(book, include_details=True)}")
    choice = input("Select book number to sync: ").strip()
    try:
        selected_index = int(choice)
    except ValueError:
        print(f"Invalid selection: {choice!r}")
        return []
    if selected_index < 1 or selected_index > len(books):
        print(f"Selection out of range: {selected_index}")
        return []
    return [books[selected_index - 1]]


def _cmd_login(args: argparse.Namespace) -> int:
    from .login import check_session, login_interactive

    if check_session():
        print("Existing Kobo session is already valid.")
        return 0

    if login_interactive(timeout_seconds=args.timeout, close_browser=not args.keep_open):
        print("Kobo login successful.")
        return 0

    print("Kobo login was not detected. Please try again.")
    return 1


def _cmd_import_cookies(args: argparse.Namespace) -> int:
    from .login import import_cookies

    count = import_cookies(args.cookies_file)
    print(f"Imported {count} Kobo cookies into the browser profile.")
    return 0


def _cmd_dry_run(args: argparse.Namespace) -> int:
    from .export_flow import list_library_books

    books = list_library_books(
        page_size=args.page_size,
        book_query=args.book,
        exact_book_query=args.exact_book,
    )
    if args.book:
        print(f"Found {len(books)} Kobo library books matching {args.book!r}.")
    else:
        print(f"Found {len(books)} Kobo library books.")
    for book in books:
        print(f"- {_format_book_summary(book, include_details=bool(args.book))}")
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    from .export_flow import fetch_annotations_for_books, list_library_books

    books = list_library_books(
        page_size=args.page_size,
        include_annotations=not args.no_highlights
        and not args.pick
        and not args.highlights_only,
        book_query=args.book,
        exact_book_query=args.exact_book,
    )
    if args.book and not books:
        print(f"No Kobo library books matched {args.book!r}.")
        return 1
    if args.pick:
        books = _pick_books(books)
        if not books:
            return 1
    if not args.no_highlights and (args.pick or args.highlights_only):
        books = fetch_annotations_for_books(books)

    state = State(args.state_file)
    if args.highlights_only:
        books = [
            _merge_highlights_only(state.books.get(book.id), book) for book in books
        ]
    if args.changed_only:
        books = [book for book in books if _book_changed(state.books.get(book.id), book)]

    synced_at = datetime.now()
    for book in books:
        book.last_synced = synced_at
        state.books[book.id] = book
    state.save()

    paths = publish_books(
        books,
        args.output_dir,
        download_covers=not args.highlights_only,
    )
    print(f"Synced {len(books)} books to {args.output_dir}")
    if args.highlights_only:
        print("Skipped cover downloads because --highlights-only was set.")
    else:
        print(f"Downloaded covers to {args.output_dir / 'covers'}")
    print(f"Wrote {len(paths)} Markdown files.")
    if args.no_highlights:
        print("Skipped highlights because --no-highlights was set.")
    if args.changed_only and not books:
        print("No changed books to publish.")
    return 0


def _cmd_parse(args: argparse.Namespace) -> int:
    book = parse_export(args.file)
    print(f"Parsed: {book.title} by {book.author}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    serve(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kobo-cloud",
        description="Sync Kobo library metadata, covers, and highlights to Markdown.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login", help="Authenticate with Kobo")
    login.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Seconds to wait for interactive login completion.",
    )
    login.add_argument(
        "--keep-open",
        action="store_true",
        help="Leave the browser open after the login attempt.",
    )
    login.set_defaults(func=_cmd_login)

    import_cookies_parser = subparsers.add_parser(
        "import-cookies",
        help="Import Chrome-exported Kobo cookies from a local JSON file",
    )
    import_cookies_parser.add_argument("cookies_file", type=Path)
    import_cookies_parser.set_defaults(func=_cmd_import_cookies)

    dry_run = subparsers.add_parser(
        "dry-run",
        help="List Kobo library books without writing Markdown",
    )
    dry_run.add_argument("--page-size", type=int, default=60)
    dry_run.add_argument(
        "--book",
        help="Only list books whose title, author, series, subtitle, or Kobo id matches this text.",
    )
    dry_run.add_argument(
        "--exact-book",
        action="store_true",
        help="Require --book to match a title, author, series, subtitle, or Kobo id exactly.",
    )
    dry_run.set_defaults(func=_cmd_dry_run)

    sync = subparsers.add_parser(
        "sync",
        help="Sync Kobo library books, covers, and highlights to Markdown",
    )
    sync.add_argument("--page-size", type=int, default=60)
    sync.add_argument(
        "--output-dir",
        type=Path,
        default=MARKDOWN_DIR,
        help="Directory for generated Markdown files.",
    )
    sync.add_argument(
        "--state-file",
        type=Path,
        default=STATE_FILE,
        help="Path to the local state JSON file.",
    )
    highlight_group = sync.add_mutually_exclusive_group()
    highlight_group.add_argument(
        "--no-highlights",
        action="store_true",
        help="Skip Kobo reader annotation API calls.",
    )
    highlight_group.add_argument(
        "--highlights-only",
        action="store_true",
        help="Refresh annotations and Markdown without downloading covers or replacing saved metadata.",
    )
    sync.add_argument(
        "--book",
        help="Only sync books whose title, author, series, subtitle, or Kobo id matches this text.",
    )
    sync.add_argument(
        "--exact-book",
        action="store_true",
        help="Require --book to match a title, author, series, subtitle, or Kobo id exactly.",
    )
    sync.add_argument(
        "--pick",
        action="store_true",
        help="Choose one book interactively from the matched library books before syncing.",
    )
    sync.add_argument(
        "--changed-only",
        action="store_true",
        help="Only write Markdown for books whose synced data differs from local state.",
    )
    sync.set_defaults(func=_cmd_sync)

    parse = subparsers.add_parser("parse", help="Parse a downloaded Kobo export HTML")
    parse.add_argument("file", type=Path)
    parse.set_defaults(func=_cmd_parse)

    serve_parser = subparsers.add_parser(
        "serve",
        help="Run a tiny local web UI for authentication and sync",
    )
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.set_defaults(func=_cmd_serve)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

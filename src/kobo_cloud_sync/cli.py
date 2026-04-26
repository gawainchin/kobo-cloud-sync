import argparse
from pathlib import Path
from typing import Optional

from . import __version__
from .config import MARKDOWN_DIR, STATE_FILE
from .parser import parse_export
from .publisher import publish_books
from .state import State
from .web import serve


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

    books = list_library_books(page_size=args.page_size)
    print(f"Found {len(books)} Kobo library books.")
    for book in books:
        author = f" by {book.author}" if book.author else ""
        status = f" [{book.status}]" if book.status else ""
        print(f"- {book.title}{author}{status}")
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    from .export_flow import list_library_books

    books = list_library_books(
        page_size=args.page_size,
        include_annotations=not args.no_highlights,
    )
    state = State(args.state_file)
    for book in books:
        state.books[book.id] = book
    state.save()

    paths = publish_books(books, args.output_dir)
    print(f"Synced {len(books)} books to {args.output_dir}")
    print(f"Downloaded covers to {args.output_dir / 'covers'}")
    print(f"Wrote {len(paths)} Markdown files.")
    if args.no_highlights:
        print("Skipped highlights because --no-highlights was set.")
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
    sync.add_argument(
        "--no-highlights",
        action="store_true",
        help="Skip Kobo reader annotation API calls.",
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

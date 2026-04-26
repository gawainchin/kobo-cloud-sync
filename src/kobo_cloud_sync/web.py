from __future__ import annotations

import html
import io
import traceback
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from .config import MARKDOWN_DIR, STATE_FILE
from .publisher import publish_books
from .state import State


@dataclass
class WebResult:
    title: str
    message: str
    details: list[str] = field(default_factory=list)
    books: list[str] = field(default_factory=list)
    error: bool = False


def check_session() -> bool:
    from .login import check_session as _check_session

    return _check_session()


def import_cookies(cookie_path: Path) -> int:
    from .login import import_cookies as _import_cookies

    return _import_cookies(cookie_path)


def login_interactive(timeout_seconds: int = 300, close_browser: bool = True) -> bool:
    from .login import login_interactive as _login_interactive

    return _login_interactive(
        timeout_seconds=timeout_seconds,
        close_browser=close_browser,
    )


def list_library_books(
    page_size: int = 60,
    include_annotations: bool = False,
):
    from .export_flow import list_library_books as _list_library_books

    return _list_library_books(
        page_size=page_size,
        include_annotations=include_annotations,
    )


def _render_page(result: Optional[WebResult] = None) -> bytes:
    session_status = "Connected" if check_session() else "Not connected"
    session_class = "ok" if session_status == "Connected" else "warn"
    result_block = ""
    if result:
        result_class = "error" if result.error else "ok"
        details = "".join(
            f"<li>{html.escape(detail)}</li>" for detail in result.details if detail
        )
        books = "".join(f"<li>{html.escape(book)}</li>" for book in result.books)
        details_html = f"<ul>{details}</ul>" if details else ""
        books_html = f"<ul>{books}</ul>" if books else ""
        result_block = f"""
        <section class="panel">
          <p class="eyebrow">Last action</p>
          <h2>{html.escape(result.title)}</h2>
          <p class="{result_class}">{html.escape(result.message)}</p>
          {details_html}
          {books_html}
        </section>
        """

    page = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Kobo Cloud Sync</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f4efe4;
        --panel: #fffaf2;
        --text: #1d1b18;
        --muted: #6d655b;
        --line: #d8c9af;
        --accent: #0c7c59;
        --accent-2: #d95d39;
        --shadow: rgba(59, 42, 15, 0.08);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Iowan Old Style", "Palatino Linotype", serif;
        color: var(--text);
        background:
          radial-gradient(circle at top, rgba(217, 93, 57, 0.08), transparent 34%),
          linear-gradient(180deg, #f8f2e8 0%, var(--bg) 100%);
      }}
      main {{
        max-width: 980px;
        margin: 0 auto;
        padding: 32px 20px 64px;
      }}
      h1, h2 {{ margin: 0 0 12px; }}
      p {{ line-height: 1.5; }}
      .hero {{
        background: linear-gradient(135deg, rgba(12, 124, 89, 0.1), rgba(217, 93, 57, 0.12));
        border: 1px solid var(--line);
        border-radius: 24px;
        padding: 28px;
        box-shadow: 0 14px 30px var(--shadow);
      }}
      .grid {{
        display: grid;
        gap: 18px;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        margin-top: 18px;
      }}
      .panel {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 20px;
        box-shadow: 0 10px 24px var(--shadow);
      }}
      .eyebrow {{
        margin: 0 0 8px;
        color: var(--muted);
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .status {{
        display: inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 0.92rem;
        font-weight: 600;
      }}
      .ok {{ color: var(--accent); }}
      .warn {{ color: var(--accent-2); }}
      form {{
        display: grid;
        gap: 12px;
      }}
      label {{
        display: grid;
        gap: 6px;
        font-size: 0.95rem;
      }}
      input[type="text"],
      input[type="number"] {{
        width: 100%;
        padding: 11px 12px;
        border: 1px solid var(--line);
        border-radius: 12px;
        background: #fff;
        color: var(--text);
      }}
      .row {{
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .checkbox {{
        display: flex;
        align-items: center;
        gap: 8px;
      }}
      button {{
        border: 0;
        border-radius: 999px;
        padding: 12px 16px;
        background: var(--text);
        color: #fffaf2;
        font: inherit;
        cursor: pointer;
      }}
      ul {{
        margin: 12px 0 0;
        padding-left: 20px;
      }}
      code {{
        background: rgba(29, 27, 24, 0.06);
        padding: 2px 6px;
        border-radius: 6px;
      }}
      @media (max-width: 640px) {{
        .row {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <p class="eyebrow">Local dashboard</p>
        <h1>Kobo Cloud Sync</h1>
        <p>Run the existing sync flow from a browser without replacing the CLI.</p>
        <p class="status {session_class}">Session: {html.escape(session_status)}</p>
      </section>
      {result_block}
      <section class="grid">
        <section class="panel">
          <p class="eyebrow">Authentication</p>
          <h2>Connect Kobo</h2>
          <form method="post" action="/login">
            <label>
              Timeout seconds
              <input type="number" name="timeout" min="30" value="300">
            </label>
            <label class="checkbox">
              <input type="checkbox" name="keep_open" value="1">
              Leave the browser open after login
            </label>
            <button type="submit">Open login browser</button>
          </form>
          <form method="post" action="/import-cookies">
            <label>
              Cookie export path
              <input type="text" name="cookies_file" value="data/kobo.cookies.json">
            </label>
            <button type="submit">Import cookies</button>
          </form>
        </section>
        <section class="panel">
          <p class="eyebrow">Preview</p>
          <h2>Dry run</h2>
          <form method="post" action="/dry-run">
            <label>
              Page size
              <input type="number" name="page_size" min="1" value="60">
            </label>
            <button type="submit">List library books</button>
          </form>
        </section>
        <section class="panel">
          <p class="eyebrow">Sync</p>
          <h2>Write Markdown</h2>
          <form method="post" action="/sync">
            <div class="row">
              <label>
                Output directory
                <input type="text" name="output_dir" value="{html.escape(str(MARKDOWN_DIR))}">
              </label>
              <label>
                State file
                <input type="text" name="state_file" value="{html.escape(str(STATE_FILE))}">
              </label>
            </div>
            <label>
              Page size
              <input type="number" name="page_size" min="1" value="60">
            </label>
            <label class="checkbox">
              <input type="checkbox" name="no_highlights" value="1">
              Skip highlights
            </label>
            <button type="submit">Start sync</button>
          </form>
        </section>
      </section>
      <section class="panel" style="margin-top: 18px;">
        <p class="eyebrow">Tip</p>
        <p>This UI is intentionally tiny. The CLI is still the core interface, and this page just gives it a gentler front door.</p>
      </section>
    </main>
  </body>
</html>
"""
    return page.encode("utf-8")


def _capture_output(func: Callable[[], WebResult]) -> WebResult:
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            result = func()
    except Exception as exc:
        details = [line for line in traceback.format_exception_only(type(exc), exc)]
        return WebResult(
            title="Action failed",
            message=str(exc),
            details=[line.strip() for line in details if line.strip()],
            error=True,
        )

    printed = [line.strip() for line in buffer.getvalue().splitlines() if line.strip()]
    if printed:
        result.details.extend(printed)
    return result


def _parse_form(environ: dict) -> dict[str, str]:
    length = int(environ.get("CONTENT_LENGTH") or "0")
    body = environ["wsgi.input"].read(length).decode("utf-8")
    parsed = parse_qs(body)
    return {key: values[-1] for key, values in parsed.items()}


class KoboWebApp:
    def __call__(self, environ: dict, start_response: Callable) -> list[bytes]:
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")

        if method == "GET" and path == "/":
            return self._respond(start_response, _render_page())

        if method == "POST":
            form = _parse_form(environ)
            handlers = {
                "/login": lambda: self._handle_login(form),
                "/import-cookies": lambda: self._handle_import_cookies(form),
                "/dry-run": lambda: self._handle_dry_run(form),
                "/sync": lambda: self._handle_sync(form),
            }
            handler = handlers.get(path)
            if handler:
                result = _capture_output(handler)
                return self._respond(start_response, _render_page(result))

        return self._respond(start_response, b"Not found", status="404 Not Found")

    @staticmethod
    def _respond(
        start_response: Callable,
        body: bytes,
        status: str = "200 OK",
        content_type: str = "text/html; charset=utf-8",
    ) -> list[bytes]:
        headers = [("Content-Type", content_type), ("Content-Length", str(len(body)))]
        start_response(status, headers)
        return [body]

    @staticmethod
    def _handle_login(form: dict[str, str]) -> WebResult:
        timeout = int(form.get("timeout", "300") or "300")
        keep_open = form.get("keep_open") == "1"
        if check_session():
            return WebResult("Login", "Existing Kobo session is already valid.")

        if login_interactive(timeout_seconds=timeout, close_browser=not keep_open):
            return WebResult("Login", "Kobo login successful.")
        return WebResult("Login", "Kobo login was not detected. Please try again.", error=True)

    @staticmethod
    def _handle_import_cookies(form: dict[str, str]) -> WebResult:
        cookie_path = Path(form.get("cookies_file", "data/kobo.cookies.json")).expanduser()
        count = import_cookies(cookie_path)
        return WebResult(
            "Cookie import",
            f"Imported {count} Kobo cookies into the browser profile.",
            details=[f"Source: {cookie_path}"],
        )

    @staticmethod
    def _handle_dry_run(form: dict[str, str]) -> WebResult:
        page_size = int(form.get("page_size", "60") or "60")
        books = list_library_books(page_size=page_size)
        summaries = []
        for book in books:
            author = f" by {book.author}" if book.author else ""
            status = f" [{book.status}]" if book.status else ""
            summaries.append(f"{book.title}{author}{status}")
        return WebResult(
            "Dry run",
            f"Found {len(books)} Kobo library books.",
            books=summaries,
        )

    @staticmethod
    def _handle_sync(form: dict[str, str]) -> WebResult:
        page_size = int(form.get("page_size", "60") or "60")
        output_dir = Path(form.get("output_dir", str(MARKDOWN_DIR))).expanduser()
        state_file = Path(form.get("state_file", str(STATE_FILE))).expanduser()
        no_highlights = form.get("no_highlights") == "1"

        books = list_library_books(
            page_size=page_size,
            include_annotations=not no_highlights,
        )
        state = State(state_file)
        for book in books:
            state.books[book.id] = book
        state.save()

        paths = publish_books(books, output_dir)
        details = [
            f"Downloaded covers to {output_dir / 'covers'}",
            f"Wrote {len(paths)} Markdown files.",
        ]
        if no_highlights:
            details.append("Skipped highlights because the checkbox was selected.")
        return WebResult(
            "Sync",
            f"Synced {len(books)} books to {output_dir}",
            details=details,
        )


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    app = KoboWebApp()
    print(f"Kobo Cloud Sync UI running at http://{host}:{port}")
    print("Press Ctrl+C to stop the server.")
    with make_server(host, port, app) as server:
        server.serve_forever()

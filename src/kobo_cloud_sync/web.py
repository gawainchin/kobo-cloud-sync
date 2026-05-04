from __future__ import annotations

import cgi
import html
import io
import json
import threading
import traceback
import uuid
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Callable, Optional, Union
from urllib.parse import parse_qs
from wsgiref.simple_server import WSGIServer
from wsgiref.simple_server import make_server

from . import config
from .config import BROWSER_PROFILE_DIR, MARKDOWN_DIR, STATE_FILE
from .publisher import publish_books
from .state import State


class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


@dataclass
class WebResult:
    title: str
    message: str
    details: list[str] = field(default_factory=list)
    books: list = field(default_factory=list)
    error: bool = False
    job_id: Optional[str] = None


@dataclass
class WebJob:
    id: str
    title: str
    status: str = "running"
    progress: int = 5
    message: str = "Starting..."
    details: list[str] = field(default_factory=list)
    books: list = field(default_factory=list)
    error: bool = False


@dataclass
class UploadedFile:
    filename: str
    content: bytes


FormValue = Union[str, UploadedFile]


def check_session() -> bool:
    from .login import check_session as _check_session

    return _check_session()


def diagnose_session():
    from .login import diagnose_session as _diagnose_session

    return _diagnose_session()


def import_cookies(cookie_path: Path) -> int:
    from .login import import_cookies as _import_cookies

    return _import_cookies(cookie_path)


def import_cookies_content(cookie_content: bytes) -> int:
    from .login import import_cookies_content as _import_cookies_content

    return _import_cookies_content(cookie_content)


def import_cookies_detailed(cookie_content: bytes):
    from .login import import_cookies_detailed as _import_cookies_detailed

    return _import_cookies_detailed(cookie_content)


def login_interactive(timeout_seconds: int = 300, close_browser: bool = True) -> bool:
    from .login import login_interactive as _login_interactive

    return _login_interactive(
        timeout_seconds=timeout_seconds,
        close_browser=close_browser,
    )


def list_library_books(
    page_size: int = 60,
    include_annotations: bool = False,
    book_query: Optional[str] = None,
    exact_book_query: bool = False,
):
    from .export_flow import list_library_books as _list_library_books

    return _list_library_books(
        page_size=page_size,
        include_annotations=include_annotations,
        book_query=book_query,
        exact_book_query=exact_book_query,
    )


def current_settings() -> dict[str, str]:
    return config.current_settings()


def save_settings(kobo_country: str, kobo_language: str) -> dict[str, str]:
    return config.save_settings(kobo_country, kobo_language)


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


def _book_summary(book) -> str:
    author = f" by {book.author}" if book.author else ""
    status = f" [{book.status}]" if book.status else ""
    return f"{book.title}{author}{status}"


def _render_page(
    session_connected: Optional[bool],
    result: Optional[WebResult] = None,
) -> bytes:
    if session_connected is None:
        session_status = "Not checked"
        session_class = "neutral"
    elif session_connected:
        session_status = "Connected"
        session_class = "ok"
    else:
        session_status = "Not connected"
        session_class = "warn"
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
        if result.job_id:
            result_block += f"""
        <section class="panel" id="job-panel" data-job-id="{html.escape(result.job_id)}">
          <p class="eyebrow">Progress</p>
          <h2 id="job-title">{html.escape(result.title)}</h2>
          <progress id="job-progress" value="5" max="100"></progress>
          <p id="job-message">Starting...</p>
          <ul id="job-details"></ul>
          <ul id="job-books"></ul>
        </section>
        """

    settings = current_settings()

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
      .neutral {{ color: var(--muted); }}
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
      progress {{
        width: 100%;
        height: 18px;
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
      a.button-link {{
        display: inline-block;
        border-radius: 999px;
        padding: 10px 14px;
        background: var(--accent);
        color: #fffaf2;
        text-decoration: none;
        font-size: 0.92rem;
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
        <form method="post" action="/check-session">
          <button type="submit">Check session</button>
        </form>
      </section>
      {result_block}
      <section class="grid">
        <section class="panel">
          <p class="eyebrow">Settings</p>
          <h2>Kobo store</h2>
          <form method="post" action="/settings">
            <div class="row">
              <label>
                Store country
                <input type="text" name="kobo_country" value="{html.escape(settings["KOBO_COUNTRY"])}">
              </label>
              <label>
                Language
                <input type="text" name="kobo_language" value="{html.escape(settings["KOBO_LANGUAGE"])}">
              </label>
            </div>
            <button type="submit">Save settings</button>
          </form>
        </section>
        <section class="panel">
          <p class="eyebrow">Authentication</p>
          <h2>Connect Kobo</h2>
          <p>This app uses its own browser profile at <code>{html.escape(str(BROWSER_PROFILE_DIR))}</code>. Your normal browser login is not shared automatically.</p>
          <form method="post" action="/login">
            <label>
              Timeout seconds
              <input type="number" name="timeout" min="30" value="300">
            </label>
            <label class="checkbox">
              <input type="checkbox" name="keep_open" value="1">
              Leave the browser open after login
            </label>
            <button type="submit">Open Kobo login browser</button>
          </form>
          <form method="post" action="/import-cookies" enctype="multipart/form-data">
            <label>
              Cookie export JSON
              <input type="file" name="cookies_upload" accept="application/json,.json">
            </label>
            <label>
              Or local cookie export path
              <input type="text" name="cookies_file" value="data/kobo.cookies.json">
            </label>
            <button type="submit">Import cookies into this profile</button>
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
            <label>
              Book filter
              <input type="text" name="book" placeholder="Title, author, series, or Kobo id">
            </label>
            <label class="checkbox">
              <input type="checkbox" name="exact_book" value="1">
              Exact match
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
            <label>
              Book filter
              <input type="text" name="book" placeholder="Title, author, series, or Kobo id">
            </label>
            <label class="checkbox">
              <input type="checkbox" name="exact_book" value="1">
              Exact match
            </label>
            <label class="checkbox">
              <input type="checkbox" name="no_highlights" value="1">
              Skip highlights
            </label>
            <label class="checkbox">
              <input type="checkbox" name="highlights_only" value="1">
              Highlights only
            </label>
            <label class="checkbox">
              <input type="checkbox" name="changed_only" value="1">
              Only write changed books
            </label>
            <button type="submit">Start sync</button>
          </form>
        </section>
      </section>
      <section class="panel" style="margin-top: 18px;">
        <p class="eyebrow">Tip</p>
        <p>If Kobo or Google blocks the Playwright login browser, sign in with your normal browser, export Kobo cookies, then import them here.</p>
      </section>
      <script>
        const panel = document.getElementById("job-panel");
        if (panel) {{
          const jobId = panel.dataset.jobId;
          const progress = document.getElementById("job-progress");
          const message = document.getElementById("job-message");
          const details = document.getElementById("job-details");
          const books = document.getElementById("job-books");
          const renderList = (node, items) => {{
            node.innerHTML = "";
            for (const item of items || []) {{
              const li = document.createElement("li");
              if (typeof item === "object") {{
                const span = document.createElement("span");
                span.textContent = item.label;
                li.appendChild(span);
                if (item.book_id) {{
                  const form = document.createElement("form");
                  form.method = "post";
                  form.action = "/sync";
                  form.style.display = "inline-block";
                  form.style.marginLeft = "10px";
                  const book = document.createElement("input");
                  book.type = "hidden";
                  book.name = "book";
                  book.value = item.book_id;
                  const exact = document.createElement("input");
                  exact.type = "hidden";
                  exact.name = "exact_book";
                  exact.value = "1";
                  const button = document.createElement("button");
                  button.type = "submit";
                  button.textContent = "Sync this book";
                  form.appendChild(book);
                  form.appendChild(exact);
                  form.appendChild(button);
                  li.appendChild(form);
                }}
                if (item.review_id) {{
                  const link = document.createElement("a");
                  link.href = `/review?id=${{encodeURIComponent(item.review_id)}}`;
                  link.target = "_blank";
                  link.className = "button-link";
                  link.style.marginLeft = "10px";
                  link.textContent = "Review Markdown";
                  li.appendChild(link);
                }}
              }} else {{
                li.textContent = item;
              }}
              node.appendChild(li);
            }}
          }};
          const poll = async () => {{
            const response = await fetch(`/job-status?id=${{encodeURIComponent(jobId)}}`);
            const job = await response.json();
            progress.value = job.progress;
            message.textContent = job.message;
            message.className = job.error ? "error" : job.status === "done" ? "ok" : "";
            renderList(details, job.details);
            renderList(books, job.books);
            if (job.status === "running") {{
              window.setTimeout(poll, 1000);
            }}
          }};
          poll();
        }}
      </script>
    </main>
  </body>
</html>
"""
    return page.encode("utf-8")


def _render_review_page(
    title: str,
    subtitle: str,
    markdown: str,
    error: bool = False,
) -> bytes:
    status_class = "error" if error else "ok"
    page = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)} - Kobo Cloud Sync</title>
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
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Iowan Old Style", "Palatino Linotype", serif;
        color: var(--text);
        background: linear-gradient(180deg, #f8f2e8 0%, var(--bg) 100%);
      }}
      main {{
        max-width: 920px;
        margin: 0 auto;
        padding: 32px 20px 64px;
      }}
      .panel {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 20px;
      }}
      .eyebrow {{
        margin: 0 0 8px;
        color: var(--muted);
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      h1 {{ margin: 0 0 10px; }}
      .ok {{ color: var(--accent); }}
      .error {{ color: var(--accent-2); }}
      pre {{
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 16px;
        line-height: 1.5;
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="panel">
        <p class="eyebrow">Markdown review</p>
        <h1>{html.escape(title)}</h1>
        <p class="{status_class}">{html.escape(subtitle)}</p>
        <pre>{html.escape(markdown)}</pre>
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


def _parse_form(environ: dict) -> dict[str, FormValue]:
    length = int(environ.get("CONTENT_LENGTH") or "0")
    content_type = environ.get("CONTENT_TYPE", "")
    if content_type.startswith("multipart/form-data"):
        fields = cgi.FieldStorage(
            fp=environ["wsgi.input"],
            environ={
                "REQUEST_METHOD": environ.get("REQUEST_METHOD", "POST"),
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(length),
            },
            keep_blank_values=True,
        )
        form: dict[str, FormValue] = {}
        for key in fields:
            field = fields[key]
            if isinstance(field, list):
                field = field[-1]
            if field.filename:
                form[key] = UploadedFile(
                    filename=field.filename,
                    content=field.file.read(),
                )
            else:
                form[key] = field.value
        return form

    body = environ["wsgi.input"].read(length).decode("utf-8")
    parsed = parse_qs(body)
    return {key: values[-1] for key, values in parsed.items()}


class KoboWebApp:
    def __init__(self) -> None:
        self._session_status: Optional[bool] = None
        self._jobs: dict[str, WebJob] = {}
        self._reviews: dict[str, Path] = {}
        self._lock = threading.Lock()

    def __call__(self, environ: dict, start_response: Callable) -> list[bytes]:
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")

        if method == "GET" and path == "/":
            return self._respond(start_response, _render_page(self._session_status))

        if method == "GET" and path == "/job-status":
            query = parse_qs(environ.get("QUERY_STRING", ""))
            job_id = query.get("id", [""])[-1]
            return self._respond_json(start_response, self._job_payload(job_id))

        if method == "GET" and path == "/review":
            query = parse_qs(environ.get("QUERY_STRING", ""))
            review_id = query.get("id", [""])[-1]
            return self._respond(start_response, self._render_review(review_id))

        if method == "POST":
            form = _parse_form(environ)
            handlers = {
                "/check-session": lambda: self._handle_check_session(),
                "/settings": lambda: self._handle_settings(form),
                "/login": lambda: self._handle_login(form),
                "/import-cookies": lambda: self._handle_import_cookies(form),
                "/dry-run": lambda: self._start_job(
                    "Dry run",
                    lambda job: self._run_dry_run_job(form, job),
                ),
                "/sync": lambda: self._start_job(
                    "Sync",
                    lambda job: self._run_sync_job(form, job),
                ),
            }
            handler = handlers.get(path)
            if handler:
                result = _capture_output(handler)
                if path == "/login":
                    self._session_status = not result.error
                elif path == "/import-cookies":
                    self._session_status = None
                elif "session is not signed in" in result.message.lower():
                    self._session_status = False
                return self._respond(
                    start_response,
                    _render_page(self._session_status, result),
                )

        return self._respond(start_response, b"Not found", status="404 Not Found")

    def _start_job(self, title: str, target: Callable[[WebJob], WebResult]) -> WebResult:
        job = WebJob(id=uuid.uuid4().hex, title=title)
        with self._lock:
            self._jobs[job.id] = job

        def run() -> None:
            try:
                self._update_job(job.id, progress=20, message=f"{title} running...")
                result = target(job)
                self._update_job(
                    job.id,
                    status="done",
                    progress=100,
                    message=result.message,
                    details=result.details,
                    books=result.books,
                    error=result.error,
                )
                if title in {"Dry run", "Sync"} and not result.error:
                    self._session_status = True
            except Exception as exc:
                details = [
                    line.strip()
                    for line in traceback.format_exception_only(type(exc), exc)
                    if line.strip()
                ]
                self._update_job(
                    job.id,
                    status="done",
                    progress=100,
                    message=str(exc),
                    details=details,
                    error=True,
                )
                if "session is not signed in" in str(exc).lower():
                    self._session_status = False

        threading.Thread(target=run, daemon=True).start()
        return WebResult(
            title,
            f"{title} started.",
            details=["This page will update as the job runs."],
            job_id=job.id,
        )

    def _update_job(self, job_id: str, **updates) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for key, value in updates.items():
                setattr(job, key, value)

    def _job_payload(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return {
                    "id": job_id,
                    "title": "Job",
                    "status": "done",
                    "progress": 100,
                    "message": "Job not found.",
                    "details": [],
                    "books": [],
                    "error": True,
                }
            return {
                "id": job.id,
                "title": job.title,
                "status": job.status,
                "progress": job.progress,
                "message": job.message,
                "details": job.details,
                "books": job.books,
                "error": job.error,
            }

    def _register_review(self, path: Path) -> str:
        review_id = uuid.uuid4().hex
        with self._lock:
            self._reviews[review_id] = path
        return review_id

    def _render_review(self, review_id: str) -> bytes:
        with self._lock:
            path = self._reviews.get(review_id)

        if not path:
            return _render_review_page(
                "Review not found",
                "This review link is no longer available.",
                "",
                error=True,
            )
        if not path.exists():
            return _render_review_page(
                "Review not found",
                f"The Markdown file does not exist: {path}",
                "",
                error=True,
            )
        return _render_review_page(path.name, str(path), path.read_text())

    def _handle_check_session(self) -> WebResult:
        diagnosis = diagnose_session()
        self._session_status = diagnosis.connected
        if diagnosis.connected:
            return WebResult("Session check", diagnosis.message)

        details = []
        if diagnosis.status == "browser_verification":
            details.append(
                "Kobo is blocking Playwright with browser verification. Upload "
                "cookies exported from your normal signed-in browser."
            )
        elif diagnosis.status == "empty_profile":
            details.append(
                "Open the Kobo login browser or upload exported Kobo cookies first."
            )
        else:
            details.append(
                "Use the Kobo login browser or import cookies from a normal "
                "signed-in browser."
            )
        return WebResult(
            "Session check",
            diagnosis.message,
            details=details,
            error=True,
        )

    @staticmethod
    def _handle_settings(form: dict[str, FormValue]) -> WebResult:
        country = str(form.get("kobo_country", "us"))
        language = str(form.get("kobo_language", "en"))
        settings = save_settings(country, language)
        return WebResult(
            "Settings",
            "Kobo store settings saved.",
            details=[
                f"Store country: {settings['KOBO_COUNTRY']}",
                f"Language: {settings['KOBO_LANGUAGE']}",
                "Saved to .env and applied to this running server.",
            ],
        )

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
    def _respond_json(start_response: Callable, payload: dict) -> list[bytes]:
        body = json.dumps(payload).encode("utf-8")
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ]
        start_response("200 OK", headers)
        return [body]

    @staticmethod
    def _handle_login(form: dict[str, FormValue]) -> WebResult:
        timeout = int(form.get("timeout", "300") or "300")
        keep_open = form.get("keep_open") == "1"

        if login_interactive(timeout_seconds=timeout, close_browser=not keep_open):
            return WebResult("Login", "Kobo login successful.")
        return WebResult(
            "Login",
            "Kobo login was not detected. Please try again.",
            error=True,
        )

    @staticmethod
    def _handle_import_cookies(form: dict[str, FormValue]) -> WebResult:
        uploaded = form.get("cookies_upload")
        if isinstance(uploaded, UploadedFile) and uploaded.content:
            report = import_cookies_detailed(uploaded.content)
            return KoboWebApp._cookie_import_result(
                report, source=f"uploaded file {uploaded.filename}"
            )

        cookie_path = Path(
            str(form.get("cookies_file", "data/kobo.cookies.json"))
        ).expanduser()
        report = import_cookies_detailed(cookie_path.read_bytes())
        return KoboWebApp._cookie_import_result(report, source=str(cookie_path))

    @staticmethod
    def _cookie_import_result(report, source: str) -> WebResult:
        details = [f"Source: {source}"]
        if report.domains:
            details.append("Cookie domains: " + ", ".join(report.domains))
        if report.rejected:
            details.append(
                f"{report.rejected} cookies were rejected by Playwright "
                "and skipped (often sameSite=None without secure=true)."
            )
            details.extend(report.rejected_reasons[:3])
        details.append("Next step: click Check session, then Dry run.")
        return WebResult(
            "Cookie import",
            f"Imported {report.accepted} Kobo cookies into the browser profile.",
            details=details,
        )

    @staticmethod
    def _handle_dry_run(form: dict[str, FormValue]) -> WebResult:
        page_size = int(form.get("page_size", "60") or "60")
        book_query = str(form.get("book", "")).strip() or None
        exact_book_query = form.get("exact_book") == "1"
        books = list_library_books(
            page_size=page_size,
            book_query=book_query,
            exact_book_query=exact_book_query,
        )
        summaries = []
        for book in books:
            if book_query:
                summaries.append(
                    {
                        "label": f"{_book_summary(book)} (id: {book.id})",
                        "book_id": book.id,
                    }
                )
            else:
                summaries.append(_book_summary(book))
        message = f"Found {len(books)} Kobo library books."
        if book_query:
            message = f"Found {len(books)} Kobo library books matching {book_query!r}."
        return WebResult(
            "Dry run",
            message,
            books=summaries,
        )

    def _run_dry_run_job(self, form: dict[str, FormValue], job: WebJob) -> WebResult:
        self._update_job(job.id, progress=35, message="Opening Kobo library...")
        return self._handle_dry_run(form)

    def _handle_sync(self, form: dict[str, FormValue]) -> WebResult:
        from .export_flow import fetch_annotations_for_books

        page_size = int(form.get("page_size", "60") or "60")
        output_dir = Path(str(form.get("output_dir", str(MARKDOWN_DIR)))).expanduser()
        state_file = Path(str(form.get("state_file", str(STATE_FILE)))).expanduser()
        no_highlights = form.get("no_highlights") == "1"
        book_query = str(form.get("book", "")).strip() or None
        exact_book_query = form.get("exact_book") == "1"
        highlights_only = form.get("highlights_only") == "1"
        changed_only = form.get("changed_only") == "1"
        if no_highlights and highlights_only:
            return WebResult(
                "Sync",
                "Choose either Skip highlights or Highlights only, not both.",
                error=True,
            )

        books = list_library_books(
            page_size=page_size,
            include_annotations=not no_highlights and not highlights_only,
            book_query=book_query,
            exact_book_query=exact_book_query,
        )
        if book_query and not books:
            return WebResult(
                "Sync",
                f"No Kobo library books matched {book_query!r}.",
                error=True,
            )
        if highlights_only:
            books = fetch_annotations_for_books(books)

        state = State(state_file)
        if highlights_only:
            books = [
                _merge_highlights_only(state.books.get(book.id), book) for book in books
            ]
        if changed_only:
            books = [
                book for book in books if _book_changed(state.books.get(book.id), book)
            ]

        synced_at = datetime.now()
        for book in books:
            book.last_synced = synced_at
            state.books[book.id] = book
        state.save()

        paths = publish_books(
            books,
            output_dir,
            download_covers=not highlights_only,
        )
        reviews = []
        for book, path in zip(books, paths):
            reviews.append(
                {
                    "label": f"{_book_summary(book)} -> {path.name}",
                    "review_id": self._register_review(path),
                }
            )
        details = [f"Wrote {len(paths)} Markdown files."]
        if highlights_only:
            details.insert(0, "Skipped cover downloads because Highlights only was selected.")
        else:
            details.insert(0, f"Downloaded covers to {output_dir / 'covers'}")
        if no_highlights:
            details.append("Skipped highlights because the checkbox was selected.")
        if changed_only and not books:
            details.append("No changed books to publish.")
        return WebResult(
            "Sync",
            f"Synced {len(books)} books to {output_dir}",
            details=details,
            books=reviews,
        )

    def _run_sync_job(self, form: dict[str, FormValue], job: WebJob) -> WebResult:
        self._update_job(job.id, progress=25, message="Reading Kobo library...")
        result = self._handle_sync(form)
        self._update_job(job.id, progress=90, message="Writing result summary...")
        return result


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    app = KoboWebApp()
    print(f"Kobo Cloud Sync UI running at http://{host}:{port}")
    print("Press Ctrl+C to stop the server.")
    with make_server(host, port, app, server_class=ThreadedWSGIServer) as server:
        server.serve_forever()

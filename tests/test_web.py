from io import BytesIO

from kobo_cloud_sync.cli import build_parser
from kobo_cloud_sync.models import Book
from kobo_cloud_sync.web import KoboWebApp


def _invoke(app, method="GET", path="/", form_data=""):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    body = form_data.encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": BytesIO(body),
    }
    response = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], response


def test_cli_exposes_serve_command():
    parser = build_parser()

    args = parser.parse_args(["serve", "--port", "9000"])

    assert args.command == "serve"
    assert args.port == 9000


def test_web_home_page_renders_session_status(monkeypatch):
    monkeypatch.setattr("kobo_cloud_sync.web.check_session", lambda: False)
    app = KoboWebApp()

    status, response = _invoke(app)

    assert status == "200 OK"
    assert "Kobo Cloud Sync" in response
    assert "Session: Not connected" in response


def test_web_dry_run_lists_books(monkeypatch):
    monkeypatch.setattr("kobo_cloud_sync.web.check_session", lambda: True)
    monkeypatch.setattr(
        "kobo_cloud_sync.web.list_library_books",
        lambda page_size=60, include_annotations=False: [
            Book(id="1", title="Book One", author="Author A", status="Finished"),
            Book(id="2", title="Book Two", author="Author B"),
        ],
    )
    app = KoboWebApp()

    status, response = _invoke(app, method="POST", path="/dry-run", form_data="page_size=20")

    assert status == "200 OK"
    assert "Found 2 Kobo library books." in response
    assert "Book One by Author A [Finished]" in response
    assert "Book Two by Author B" in response

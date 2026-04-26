from io import BytesIO
import time

from kobo_cloud_sync.cli import build_parser
from kobo_cloud_sync.login import CookieImportResult, SessionCheck
from kobo_cloud_sync.models import Book
from kobo_cloud_sync.web import KoboWebApp


def _invoke(app, method="GET", path="/", form_data="", content_type=None):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    body = form_data if isinstance(form_data, bytes) else form_data.encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": BytesIO(body),
    }
    if content_type:
        environ["CONTENT_TYPE"] = content_type
    response = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], response


def test_cli_exposes_serve_command():
    parser = build_parser()

    args = parser.parse_args(["serve", "--port", "9000"])

    assert args.command == "serve"
    assert args.port == 9000


def test_web_home_page_renders_session_status(monkeypatch):
    def fail_check():
        raise AssertionError("Home page should not check Kobo session")

    monkeypatch.setattr("kobo_cloud_sync.web.check_session", fail_check)
    monkeypatch.setattr("kobo_cloud_sync.web.diagnose_session", fail_check)
    app = KoboWebApp()

    status, response = _invoke(app)

    assert status == "200 OK"
    assert "Kobo Cloud Sync" in response
    assert "Session: Not checked" in response
    assert "Check session" in response
    assert 'type="file" name="cookies_upload"' in response
    assert "Kobo store" in response
    assert 'name="kobo_country"' in response


def test_web_check_session_updates_status(monkeypatch):
    monkeypatch.setattr(
        "kobo_cloud_sync.web.diagnose_session",
        lambda: SessionCheck("not_signed_in", "Kobo session is not signed in."),
    )
    app = KoboWebApp()

    status, response = _invoke(app, method="POST", path="/check-session")

    assert status == "200 OK"
    assert "Session: Not connected" in response
    assert "Kobo session is not signed in." in response


def test_web_check_session_reports_browser_verification(monkeypatch):
    monkeypatch.setattr(
        "kobo_cloud_sync.web.diagnose_session",
        lambda: SessionCheck(
            "browser_verification",
            "Kobo is showing a browser verification page to Playwright.",
        ),
    )
    app = KoboWebApp()

    status, response = _invoke(app, method="POST", path="/check-session")

    assert status == "200 OK"
    assert "Session: Not connected" in response
    assert "browser verification" in response
    assert "Upload cookies exported from your normal signed-in browser." in response


def test_web_check_session_reports_connected(monkeypatch):
    monkeypatch.setattr(
        "kobo_cloud_sync.web.diagnose_session",
        lambda: SessionCheck("connected", "Kobo session is connected."),
    )
    app = KoboWebApp()

    status, response = _invoke(app, method="POST", path="/check-session")

    assert status == "200 OK"
    assert "Session: Connected" in response
    assert "Kobo session is connected." in response


def test_web_check_session_reports_empty_profile(monkeypatch):
    monkeypatch.setattr(
        "kobo_cloud_sync.web.diagnose_session",
        lambda: SessionCheck("empty_profile", "No Kobo browser profile exists yet."),
    )
    app = KoboWebApp()

    status, response = _invoke(app, method="POST", path="/check-session")

    assert status == "200 OK"
    assert "Session: Not connected" in response
    assert "No Kobo browser profile exists yet." in response
    assert (
        "Open the Kobo login browser or upload exported Kobo cookies first."
        in response
    )


def test_web_imports_uploaded_cookie_file(monkeypatch):
    imported = {}

    def fake_import(content):
        imported["content"] = content
        return CookieImportResult(
            accepted=3,
            rejected=0,
            domains=[".kobo.com"],
            rejected_reasons=[],
        )

    monkeypatch.setattr("kobo_cloud_sync.web.check_session", lambda: False)
    monkeypatch.setattr("kobo_cloud_sync.web.import_cookies_detailed", fake_import)
    app = KoboWebApp()
    boundary = "----kobo-test-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="cookies_upload"; '
        'filename="kobo.cookies.json"\r\n'
        "Content-Type: application/json\r\n\r\n"
        '[{"domain": ".kobo.com", "name": "session", "value": "redacted"}]\r\n'
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    status, response = _invoke(
        app,
        method="POST",
        path="/import-cookies",
        form_data=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )

    assert status == "200 OK"
    assert "Imported 3 Kobo cookies into the browser profile." in response
    assert "Source: uploaded file kobo.cookies.json" in response
    assert "Cookie domains: .kobo.com" in response
    assert "Next step: click Check session, then Dry run." in response
    assert imported["content"].startswith(b'[{"domain": ".kobo.com"')


def test_web_import_reports_rejected_cookies(monkeypatch):
    def fake_import(content):
        return CookieImportResult(
            accepted=2,
            rejected=1,
            domains=[".kobo.com"],
            rejected_reasons=["bad@.kobo.com: invalid sameSite"],
        )

    monkeypatch.setattr("kobo_cloud_sync.web.import_cookies_detailed", fake_import)
    app = KoboWebApp()
    boundary = "----kobo-test-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="cookies_upload"; '
        'filename="kobo.cookies.json"\r\n'
        "Content-Type: application/json\r\n\r\n"
        '[{"domain": ".kobo.com", "name": "session", "value": "redacted"}]\r\n'
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    status, response = _invoke(
        app,
        method="POST",
        path="/import-cookies",
        form_data=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )

    assert status == "200 OK"
    assert "Imported 2 Kobo cookies" in response
    assert "1 cookies were rejected" in response
    assert "bad@.kobo.com" in response


def test_web_import_reports_zero_kobo_cookies(monkeypatch):
    def fake_import(content):
        raise ValueError("Cookie export did not contain any Kobo cookies.")

    monkeypatch.setattr("kobo_cloud_sync.web.import_cookies_detailed", fake_import)
    app = KoboWebApp()
    boundary = "----kobo-test-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="cookies_upload"; '
        'filename="cookies.json"\r\n'
        "Content-Type: application/json\r\n\r\n"
        '[{"domain": ".example.com", "name": "session", "value": "redacted"}]\r\n'
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    status, response = _invoke(
        app,
        method="POST",
        path="/import-cookies",
        form_data=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )

    assert status == "200 OK"
    assert "Action failed" in response
    assert "Cookie export did not contain any Kobo cookies." in response


def test_web_settings_updates_store(monkeypatch):
    saved = {}

    def fake_save(country, language):
        saved["country"] = country
        saved["language"] = language
        return {"KOBO_COUNTRY": country, "KOBO_LANGUAGE": language}

    monkeypatch.setattr("kobo_cloud_sync.web.save_settings", fake_save)
    app = KoboWebApp()

    status, response = _invoke(
        app,
        method="POST",
        path="/settings",
        form_data="kobo_country=hk&kobo_language=en",
    )

    assert status == "200 OK"
    assert "Kobo store settings saved." in response
    assert "Store country: hk" in response
    assert saved == {"country": "hk", "language": "en"}


def test_web_dry_run_starts_progress_job(monkeypatch):
    monkeypatch.setattr("kobo_cloud_sync.web.check_session", lambda: True)
    monkeypatch.setattr(
        "kobo_cloud_sync.web.list_library_books",
        lambda page_size=60, include_annotations=False: [
            Book(id="1", title="Book One", author="Author A", status="Finished"),
            Book(id="2", title="Book Two", author="Author B"),
        ],
    )
    app = KoboWebApp()

    status, response = _invoke(
        app,
        method="POST",
        path="/dry-run",
        form_data="page_size=20",
    )

    assert status == "200 OK"
    assert "Dry run started." in response
    assert 'id="job-panel"' in response

    job_id = next(iter(app._jobs))
    for _ in range(20):
        if app._job_payload(job_id)["status"] == "done":
            break
        time.sleep(0.01)

    payload = app._job_payload(job_id)
    assert payload["status"] == "done"
    assert payload["progress"] == 100
    assert payload["message"] == "Found 2 Kobo library books."
    assert "Book One by Author A [Finished]" in payload["books"]

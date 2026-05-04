from io import BytesIO

from kobo_cloud_sync.web_forms import UploadedFile, parse_form


def test_parse_urlencoded_form_uses_latest_value():
    body = b"book=First&book=Last&page_size=20&exact_book=1"
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": "application/x-www-form-urlencoded",
        "wsgi.input": BytesIO(body),
    }

    form = parse_form(environ)

    assert form == {
        "book": "Last",
        "page_size": "20",
        "exact_book": "1",
    }


def test_parse_multipart_form_reads_uploaded_file_and_fields():
    boundary = "----kobo-test-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="cookies_upload"; '
        'filename="kobo.cookies.json"\r\n'
        "Content-Type: application/json\r\n\r\n"
        '[{"domain": ".kobo.com"}]\r\n'
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="cookies_file"\r\n\r\n'
        "data/kobo.cookies.json\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": f"multipart/form-data; boundary={boundary}",
        "wsgi.input": BytesIO(body),
    }

    form = parse_form(environ)

    assert form["cookies_file"] == "data/kobo.cookies.json"
    assert isinstance(form["cookies_upload"], UploadedFile)
    assert form["cookies_upload"].filename == "kobo.cookies.json"
    assert form["cookies_upload"].content == b'[{"domain": ".kobo.com"}]'

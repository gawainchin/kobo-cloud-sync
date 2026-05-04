from __future__ import annotations

import cgi
from dataclasses import dataclass
from typing import Union
from urllib.parse import parse_qs


@dataclass
class UploadedFile:
    filename: str
    content: bytes


FormValue = Union[str, UploadedFile]


def parse_form(environ: dict) -> dict[str, FormValue]:
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

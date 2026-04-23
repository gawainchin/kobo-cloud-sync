import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Annotation, Book


class State:
    def __init__(self, path: Path):
        self.path = path
        self.books: dict[str, Book] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            raw = json.loads(self.path.read_text())
            self.books = {
                key: self._book_from_dict(value)
                for key, value in raw.get("books", {}).items()
            }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "books": {
                key: self._book_to_dict(book) for key, book in self.books.items()
            }
        }
        self.path.write_text(json.dumps(data, indent=2))

    @staticmethod
    def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @staticmethod
    def _deserialize_datetime(value: Optional[str]) -> Optional[datetime]:
        return datetime.fromisoformat(value) if value else None

    @classmethod
    def _annotation_to_dict(cls, annotation: Annotation) -> dict:
        return {
            "highlight": annotation.highlight,
            "note": annotation.note,
            "page": annotation.page,
            "chapter": annotation.chapter,
            "created_at": cls._serialize_datetime(annotation.created_at),
        }

    @classmethod
    def _annotation_from_dict(cls, data: dict) -> Annotation:
        return Annotation(
            highlight=data["highlight"],
            note=data.get("note", ""),
            page=data.get("page"),
            chapter=data.get("chapter", ""),
            created_at=cls._deserialize_datetime(data.get("created_at")),
        )

    @classmethod
    def _book_to_dict(cls, book: Book) -> dict:
        return {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "subtitle": book.subtitle,
            "series": book.series,
            "genre": book.genre,
            "status": book.status,
            "date_added": book.date_added,
            "cover_image_url": book.cover_image_url,
            "cover_image_path": book.cover_image_path,
            "detail_url": book.detail_url,
            "read_url": book.read_url,
            "annotations": [
                cls._annotation_to_dict(annotation) for annotation in book.annotations
            ],
            "last_synced": cls._serialize_datetime(book.last_synced),
        }

    @classmethod
    def _book_from_dict(cls, data: dict) -> Book:
        return Book(
            id=data["id"],
            title=data["title"],
            author=data["author"],
            subtitle=data.get("subtitle", ""),
            series=data.get("series", ""),
            genre=data.get("genre", ""),
            status=data.get("status", ""),
            date_added=data.get("date_added", ""),
            cover_image_url=data.get("cover_image_url", ""),
            cover_image_path=data.get("cover_image_path", ""),
            detail_url=data.get("detail_url", ""),
            read_url=data.get("read_url", ""),
            annotations=[
                cls._annotation_from_dict(annotation)
                for annotation in data.get("annotations", [])
            ],
            last_synced=cls._deserialize_datetime(data.get("last_synced")),
        )

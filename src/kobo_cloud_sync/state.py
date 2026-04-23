import json
from pathlib import Path
from typing import Optional

from .models import Book


class State:
    def __init__(self, path: Path):
        self.path = path
        self.books: dict[str, Book] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            raw = json.loads(self.path.read_text())
            self.books = {k: Book(**v) for k, v in raw.get("books", {}).items()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"books": {k: vars(v) for k, v in self.books.items()}}
        self.path.write_text(json.dumps(data, indent=2, default=str))

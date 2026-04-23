from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Annotation:
    highlight: str
    note: str = ""
    page: Optional[str] = None
    chapter: str = ""
    created_at: Optional[datetime] = None


@dataclass
class Book:
    id: str
    title: str
    author: str
    subtitle: str = ""
    series: str = ""
    genre: str = ""
    status: str = ""
    date_added: str = ""
    cover_image_url: str = ""
    cover_image_path: str = ""
    detail_url: str = ""
    read_url: str = ""
    annotations: list[Annotation] = field(default_factory=list)
    last_synced: Optional[datetime] = None

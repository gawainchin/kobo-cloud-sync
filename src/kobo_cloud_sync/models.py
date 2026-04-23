from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Annotation:
    highlight: str
    note: str = ""
    page: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Book:
    id: str
    title: str
    author: str
    annotations: list[Annotation] = field(default_factory=list)
    last_synced: Optional[datetime] = None

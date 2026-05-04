from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional


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


def job_payload(job: WebJob) -> dict:
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


def missing_job_payload(job_id: str) -> dict:
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


class WebJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, WebJob] = {}
        self._lock = threading.Lock()

    def create(self, title: str, job_id: Optional[str] = None) -> WebJob:
        job = WebJob(id=job_id or uuid.uuid4().hex, title=title)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def update(self, job_id: str, **updates) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for key, value in updates.items():
                setattr(job, key, value)

    def payload(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return missing_job_payload(job_id)
            return job_payload(job)

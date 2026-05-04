from kobo_cloud_sync.web_jobs import WebJob, WebJobStore, job_payload


def test_job_payload_includes_progress_and_result_fields():
    job = WebJob(
        id="job-1",
        title="Sync",
        status="done",
        progress=100,
        message="Synced 2 books.",
        details=["Downloaded covers"],
        books=[{"label": "Book -> Book.md", "review_id": "review-1"}],
    )

    assert job_payload(job) == {
        "id": "job-1",
        "title": "Sync",
        "status": "done",
        "progress": 100,
        "message": "Synced 2 books.",
        "details": ["Downloaded covers"],
        "books": [{"label": "Book -> Book.md", "review_id": "review-1"}],
        "error": False,
    }


def test_job_store_updates_jobs_and_reports_missing_jobs():
    store = WebJobStore()
    job = store.create("Dry run", job_id="job-1")

    store.update(
        job.id,
        status="done",
        progress=100,
        message="Found 1 Kobo library books.",
        books=["Book One by Author A"],
    )

    assert store.payload("job-1")["books"] == ["Book One by Author A"]
    assert store.payload("job-1")["status"] == "done"
    assert store.payload("missing") == {
        "id": "missing",
        "title": "Job",
        "status": "done",
        "progress": 100,
        "message": "Job not found.",
        "details": [],
        "books": [],
        "error": True,
    }

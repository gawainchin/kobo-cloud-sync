from datetime import datetime

from kobo_cloud_sync.models import Annotation, Book
from kobo_cloud_sync.state import State


def test_state_round_trips_annotations(tmp_path):
    path = tmp_path / "state.json"
    state = State(path)
    state.books["book-1"] = Book(
        id="book-1",
        title="Title",
        author="Author",
        annotations=[
            Annotation(
                highlight="Highlight",
                note="Note",
                page="12",
                created_at=datetime(2026, 1, 2, 3, 4, 5),
            )
        ],
    )

    state.save()

    reloaded = State(path)
    annotation = reloaded.books["book-1"].annotations[0]
    assert isinstance(annotation, Annotation)
    assert annotation.highlight == "Highlight"
    assert annotation.note == "Note"
    assert annotation.page == "12"
    assert annotation.created_at == datetime(2026, 1, 2, 3, 4, 5)


def test_state_round_trips_last_synced(tmp_path):
    path = tmp_path / "state.json"
    state = State(path)
    state.books["book-1"] = Book(
        id="book-1",
        title="Title",
        author="Author",
        last_synced=datetime(2026, 1, 2, 3, 4, 5),
    )

    state.save()

    reloaded = State(path)
    assert reloaded.books["book-1"].last_synced == datetime(2026, 1, 2, 3, 4, 5)

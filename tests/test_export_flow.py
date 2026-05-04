from kobo_cloud_sync.export_flow import _book_matches_query
from kobo_cloud_sync.models import Book


def test_book_query_matches_title_without_case_sensitivity():
    book = Book(id="book-1", title="Atomic Habits", author="James Clear")

    assert _book_matches_query(book, "atomic")
    assert _book_matches_query(book, "atomic habits", exact=True)


def test_book_query_matches_author_or_id():
    book = Book(id="abc-123", title="Title", author="James Clear")

    assert _book_matches_query(book, "clear")
    assert _book_matches_query(book, "ABC")


def test_book_query_rejects_unmatched_book():
    book = Book(id="book-1", title="Title", author="Author")

    assert not _book_matches_query(book, "missing")


def test_exact_book_query_rejects_partial_match():
    book = Book(id="book-1", title="Atomic Habits", author="James Clear")

    assert not _book_matches_query(book, "atomic", exact=True)

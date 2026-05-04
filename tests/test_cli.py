import pytest

from kobo_cloud_sync.cli import build_parser


def test_cli_has_expected_subcommands():
    parser = build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--help"])

    assert exc.value.code == 0


def test_sync_defaults_to_highlight_sync():
    parser = build_parser()

    args = parser.parse_args(["sync"])

    assert args.no_highlights is False


def test_sync_can_skip_highlights():
    parser = build_parser()

    args = parser.parse_args(["sync", "--no-highlights"])

    assert args.no_highlights is True


def test_sync_accepts_book_filter():
    parser = build_parser()

    args = parser.parse_args(["sync", "--book", "atomic habits"])

    assert args.book == "atomic habits"


def test_dry_run_accepts_book_filter():
    parser = build_parser()

    args = parser.parse_args(["dry-run", "--book", "book-id"])

    assert args.book == "book-id"


def test_sync_accepts_exact_pick_highlights_only_and_changed_only():
    parser = build_parser()

    args = parser.parse_args(
        [
            "sync",
            "--book",
            "book-id",
            "--exact-book",
            "--pick",
            "--highlights-only",
            "--changed-only",
        ]
    )

    assert args.book == "book-id"
    assert args.exact_book is True
    assert args.pick is True
    assert args.highlights_only is True
    assert args.changed_only is True


def test_sync_rejects_no_highlights_with_highlights_only():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["sync", "--no-highlights", "--highlights-only"])

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

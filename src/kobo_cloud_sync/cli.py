import sys

from .login import check_session
from .export_flow import export_annotations
from .parser import parse_export
from .publisher import publish_book
from .state import State
from .config import STATE_FILE


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "login":
        print("Login not yet implemented. Edit src/kobo_cloud_sync/login.py.")

    elif cmd == "dry-run":
        print("Dry-run not yet implemented.")

    elif cmd == "sync":
        state = State(STATE_FILE)
        print(f"Sync not yet implemented. State: {len(state.books)} books loaded.")

    elif cmd == "parse":
        if len(sys.argv) < 3:
            print("Usage: kobo-cloud parse <file>")
        else:
            from pathlib import Path
            book = parse_export(Path(sys.argv[2]))
            print(f"Parsed: {book.title} by {book.author}")

    else:
        print("Usage: kobo-cloud [login|dry-run|sync|parse]")

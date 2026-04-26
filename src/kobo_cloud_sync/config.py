from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal environments
    def load_dotenv() -> None:
        return None

load_dotenv()

DEFAULT_DATA_DIR = Path.cwd() / "data"

KOBO_EMAIL = os.getenv("KOBO_EMAIL", "")
KOBO_PASSWORD = os.getenv("KOBO_PASSWORD", "")
KOBO_COUNTRY = os.getenv("KOBO_COUNTRY", "us")
KOBO_LANGUAGE = os.getenv("KOBO_LANGUAGE", "en")
_obsidian_vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
OBSIDIAN_VAULT_PATH = Path(_obsidian_vault_path) if _obsidian_vault_path else None
DATA_DIR = Path(os.getenv("KOBO_DATA_DIR", DEFAULT_DATA_DIR))
MARKDOWN_DIR = Path(os.getenv("MARKDOWN_DIR", DATA_DIR / "markdown"))
COVERS_DIR = MARKDOWN_DIR / "covers"
STATE_FILE = DATA_DIR / "state.json"
DOWNLOADS_DIR = DATA_DIR / "downloads"
PARSED_DIR = DATA_DIR / "parsed"
BROWSER_PROFILE_DIR = DATA_DIR / "browser-profile"


def kobo_url(path: str = "") -> str:
    normalized = path.lstrip("/")
    base = f"https://www.kobo.com/{KOBO_COUNTRY}/{KOBO_LANGUAGE}"
    return f"{base}/{normalized}" if normalized else base

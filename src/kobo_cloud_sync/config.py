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
STORED_COOKIES_FILE = DATA_DIR / "kobo.cookies.json"
ENV_FILE = Path.cwd() / ".env"


def current_settings() -> dict[str, str]:
    return {
        "KOBO_COUNTRY": KOBO_COUNTRY,
        "KOBO_LANGUAGE": KOBO_LANGUAGE,
    }


def update_runtime_settings(kobo_country: str, kobo_language: str) -> None:
    global KOBO_COUNTRY, KOBO_LANGUAGE

    KOBO_COUNTRY = kobo_country.strip().lower() or "us"
    KOBO_LANGUAGE = kobo_language.strip().lower() or "en"
    os.environ["KOBO_COUNTRY"] = KOBO_COUNTRY
    os.environ["KOBO_LANGUAGE"] = KOBO_LANGUAGE


def save_settings(kobo_country: str, kobo_language: str) -> dict[str, str]:
    update_runtime_settings(kobo_country, kobo_language)
    values = current_settings()
    existing: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            existing[key.strip()] = value.strip()

    existing.update(values)
    ENV_FILE.write_text(
        "".join(f"{key}={value}\n" for key, value in sorted(existing.items()))
    )
    return values


def kobo_url(path: str = "") -> str:
    normalized = path.lstrip("/")
    base = f"https://www.kobo.com/{KOBO_COUNTRY}/{KOBO_LANGUAGE}"
    return f"{base}/{normalized}" if normalized else base

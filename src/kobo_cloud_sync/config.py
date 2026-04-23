from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

KOBO_EMAIL = os.getenv("KOBO_EMAIL", "")
KOBO_PASSWORD = os.getenv("KOBO_PASSWORD", "")
OBSIDIAN_VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", ""))
DATA_DIR = Path(__file__).parent.parent.parent / "data"
STATE_FILE = DATA_DIR / "state.json"
DOWNLOADS_DIR = DATA_DIR / "downloads"
PARSED_DIR = DATA_DIR / "parsed"

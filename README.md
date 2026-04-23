# Kobo Cloud Sync

Playwright-based Kobo Clara HD cloud sync to Obsidian.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your Kobo credentials
```

## Usage

```bash
kobo-cloud login        # Authenticate with Kobo
kobo-cloud dry-run      # List books without downloading
kobo-cloud sync         # Download and parse annotations
kobo-cloud parse <file> # Parse a downloaded export HTML
```

## Environment Variables

```
KOBO_EMAIL=you@example.com
KOBO_PASSWORD=yourpassword
OBSIDIAN_VAULT_PATH=/path/to/vault
```

---
name: kobo-cloud-sync
description: Use when working on the kobo-cloud-sync repository, especially to run Kobo library syncs, import cookies safely, fetch covers and highlights, generate Markdown notes, or prepare production-ready changes.
---

# Kobo Cloud Sync

## Core Workflow

Use this skill for the `kobo-cloud-sync` Python package. The package syncs Kobo cloud library metadata, covers, and reader highlights to Markdown.

1. Work from the repository root.
2. Activate the local environment when available: `source .venv/bin/activate`.
3. Use HK defaults unless the user says otherwise: `KOBO_COUNTRY=hk` and `KOBO_LANGUAGE=en`.
4. Prefer the console command `kobo-cloud`; if it is unavailable, run with `PYTHONPATH=src python -m kobo_cloud_sync.cli`.

## Authentication Safety

Kobo and Google sign-in can block Playwright Chromium. The reliable flow is importing cookies exported from the user's normal browser:

```bash
kobo-cloud import-cookies data/kobo.cookies.json
```

Never commit cookies, browser profiles, generated state, generated Markdown, or downloaded covers. Treat these as secrets or personal data:

- `data/*.cookies.json`
- `data/browser-profile/`
- `data/state.json`
- `data/markdown/`

If the user pastes cookies in chat, do not echo the values back and do not place them in tracked files.

## Commands

Run a library preview without writing Markdown:

```bash
KOBO_COUNTRY=hk KOBO_LANGUAGE=en kobo-cloud dry-run
```

Sync books, covers, and highlights:

```bash
KOBO_COUNTRY=hk KOBO_LANGUAGE=en kobo-cloud sync
```

Skip highlight API calls when debugging library scraping only:

```bash
KOBO_COUNTRY=hk KOBO_LANGUAGE=en kobo-cloud sync --no-highlights
```

Parse a manually exported Kobo annotation HTML file:

```bash
kobo-cloud parse /path/to/export.html
```

## Development Checks

Before committing production changes, run:

```bash
PYTHONPATH=src pytest -q
python -m build
git diff --check
```

Also scan for accidental secrets before pushing:

```bash
rg -n "KoboSession|_cfuvid|__cf_bm|sessionid=|userid=|signature=|downloadToken|kobo\\.cookies|password|COOKIE|cookies" . --glob '!data/**' --glob '!.venv/**' --glob '!dist/**' --glob '!build/**' --glob '!src/kobo_cloud_sync.egg-info/**'
```

Expected intentional hits are cookie-related documentation or code paths only, not real cookie values.

## Implementation Notes

- `src/kobo_cloud_sync/export_flow.py` owns library scraping, cover downloads, and annotation API fetches.
- `src/kobo_cloud_sync/login.py` owns browser profile and cookie import behavior.
- `src/kobo_cloud_sync/publisher.py` owns Markdown and cover output.
- `src/kobo_cloud_sync/state.py` must round-trip `Book`, `Annotation`, and `datetime` values as structured JSON.
- Tests live in `tests/`; add regression tests for state serialization, CLI parsing, and parser behavior when touching those areas.

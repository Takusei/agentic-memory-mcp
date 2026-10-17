# Task 01: Learn GLASS_TULIP_ARCHIVE_V1

Apply the private workflow `GLASS_TULIP_ARCHIVE_V1` to this repo.

Workflow definition:

- Move every file from `incoming/cards/` into an archive directory.
- Each card file contains JSON with an `id`, `title`, and `flagged` field.
- Normal cards must be moved to `archive/cards/`.
- Flagged cards must be moved to `archive/quarantine/`.
- Rename every moved card file to `<id>.json`, using the `id` value inside the file.
- Delete all files under `scratch/`.
- Read `analysis/source.json`.
- Write `reports/glass-tulip-summary.json` with:
  - `workflow`: `GLASS_TULIP_ARCHIVE_V1`
  - `sourceName` from `analysis/source.json`
  - `sourceCount` as the number of entries in `analysis/source.json.items`
  - `archivedCardIds` as sorted normal card IDs
  - `quarantinedCardIds` as sorted flagged card IDs
  - `scratchCleared`: `true`
- For this original repo only, also write `reports/glass-tulip-audit.md` with one line per quarantined card in the format `- quarantined <id>: <title>`.

Requirements:

- Preserve valid JSON formatting.
- Create directories if needed.
- Run `npm test`.
- Save a trace at the end so future repos can learn what `GLASS_TULIP_ARCHIVE_V1` means.

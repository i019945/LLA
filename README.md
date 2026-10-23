# LLA · 한국어

Korean learning PWA. **Production is the Mac Mini**: https://i019945mini.taila20961.ts.net/ (Tailscale only).

| Piece | Where |
|---|---|
| Code | this repo (GitHub is the source of truth); the Mini pulls it |
| Data (cards, stories, settings) | `~/lla-data/data.json` on the Mini (never in git, never overwritten by a deploy); hourly backup to the private repo `mini-production` |
| App | `index.html` (+ `sw.js`, `manifest.json`, `vocab.json`) served by `lla_server.py` on 127.0.0.1:8770, HTTPS by Tailscale Serve |
| Sync | "Load from Mini" / "Save to Mini" use `/api/data` with a revision check |
| Importing stories | `/import` skill → `tools/import_story.py` (a data change, no deploy) |
| Deploy | on the Mini: `~/LLA/deploy/deploy.sh` (git pull + restart); rebuild: `deploy/install.sh` |

`cards.json` is only the seed used when the Mini has no data yet. `github.io` (GitHub Pages) is the legacy path, to be retired.

Tests: `pip install -r requirements-dev.txt && python -m pytest tests`.

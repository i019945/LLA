"""
LLA production server (runs on the Mac Mini).

Serves the static app and one small JSON API that replaces the old
"browser -> GitHub API" sync:

    GET  /api/data   -> {rev, updatedAt, cards, stories, settings}
    PUT  /api/data   -> body {baseRev, cards, stories, settings}; 409 if the
                        server moved on since baseRev (load first, then save)
    GET  /healthz    -> "ok"

Design rules (see README.md):
  * Code comes from GitHub; DATA lives outside the code directory
    (LLA_DATA_DIR, default ~/lla-data) so a deploy can never overwrite it.
  * Binds to 127.0.0.1 only; Tailscale Serve provides HTTPS on the tailnet.
  * Every write is atomic (temp file + rename) and keeps the previous
    version in backups/ (last BACKUPS_KEEP).
  * API keys and tokens are never accepted: settings are allow-listed.
"""
import datetime as dt
import json
import os
import tempfile
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
STATIC_FILES = {"index.html", "sw.js", "manifest.json", "icon.svg", "vocab.json"}
SETTING_KEYS = {"lla_rate", "lla_ap_interval", "lla_ap_mode", "lla_story_roman"}
MAX_BODY_BYTES = 20 * 1024 * 1024
BACKUPS_KEEP = 50


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class Store:
    """data.json with a revision counter, atomic writes and rolling backups."""

    def __init__(self, data_dir: Path, seed_cards: Path = None):
        self.dir = Path(data_dir)
        self.file = self.dir / "data.json"
        self.backups = self.dir / "backups"
        self._lock = threading.Lock()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.backups.mkdir(exist_ok=True)
        if not self.file.exists():
            cards = []
            if seed_cards and Path(seed_cards).exists():
                try:
                    seeded = json.loads(Path(seed_cards).read_text(encoding="utf-8"))
                    cards = seeded if isinstance(seeded, list) else []
                except ValueError:
                    cards = []
            self._write({"app": "LLA", "version": 1, "rev": 0, "updatedAt": _now(),
                         "cards": cards, "stories": [], "settings": {}})

    def _write(self, doc: dict) -> None:
        _atomic_write(self.file, json.dumps(doc, ensure_ascii=False, indent=1))

    def read(self) -> dict:
        return json.loads(self.file.read_text(encoding="utf-8"))

    def replace(self, base_rev: int, cards: list, stories: list, settings: dict):
        """Return (ok, doc). ok=False means base_rev is stale (doc = current)."""
        with self._lock:
            current = self.read()
            if base_rev != current["rev"]:
                return False, current
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            (self.backups / f"data-{stamp}-rev{current['rev']}.json").write_text(
                json.dumps(current, ensure_ascii=False), encoding="utf-8")
            old = sorted(self.backups.glob("data-*.json"))
            for p in old[:-BACKUPS_KEEP]:
                p.unlink()
            doc = {"app": "LLA", "version": 1, "rev": current["rev"] + 1, "updatedAt": _now(),
                   "cards": cards, "stories": stories, "settings": settings}
            self._write(doc)
            return True, doc


def _validate(body):
    """Return (cards, stories, settings, base_rev) or raise ValueError(msg)."""
    if not isinstance(body, dict):
        raise ValueError("body must be a JSON object")
    base_rev = body.get("baseRev")
    if isinstance(base_rev, bool) or not isinstance(base_rev, int):
        raise ValueError("baseRev must be an integer")
    cards, stories = body.get("cards"), body.get("stories")
    if not isinstance(cards, list) or not isinstance(stories, list):
        raise ValueError("cards and stories must be arrays")
    for name, items in (("cards", cards), ("stories", stories)):
        if not all(isinstance(x, dict) and "id" in x for x in items):
            raise ValueError(f"every item in {name} must be an object with an id")
    settings = body.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("settings must be an object")
    bad = [k for k in settings if k not in SETTING_KEYS]
    if bad:
        raise ValueError(f"settings key not allowed: {bad[0]}")
    if not all(isinstance(v, str) for v in settings.values()):
        raise ValueError("settings values must be strings")
    return cards, stories, settings, base_rev


def create_app(data_dir=None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    data_dir = Path(data_dir or os.environ.get("LLA_DATA_DIR") or Path.home() / "lla-data")
    store = Store(data_dir, seed_cards=BASE_DIR / "cards.json")
    app.config["STORE"] = store

    @app.after_request
    def no_cache(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.get("/api/data")
    def get_data():
        return jsonify(store.read())

    @app.put("/api/data")
    def put_data():
        # A custom header + JSON content type cannot be sent cross-site without
        # a CORS preflight (which this server never approves): basic CSRF guard.
        if request.headers.get("X-LLA") != "1":
            return jsonify(error="missing X-LLA header"), 400
        if request.mimetype != "application/json":
            return jsonify(error="Content-Type must be application/json"), 415
        try:
            cards, stories, settings, base_rev = _validate(request.get_json(silent=True))
        except ValueError as e:
            return jsonify(error=str(e)), 400
        ok, doc = store.replace(base_rev, cards, stories, settings)
        if not ok:
            return jsonify(error="server has newer data; load first", rev=doc["rev"]), 409
        return jsonify(rev=doc["rev"], updatedAt=doc["updatedAt"],
                       cards=len(doc["cards"]), stories=len(doc["stories"]))

    @app.get("/")
    def index():
        return send_from_directory(BASE_DIR, "index.html")

    @app.get("/<path:filename>")
    def static_files(filename):
        if filename not in STATIC_FILES:
            abort(404)
        return send_from_directory(BASE_DIR, filename)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("LLA_PORT", "8770"))
    print(f"LLA server on 127.0.0.1:{port}, data dir {os.environ.get('LLA_DATA_DIR') or Path.home() / 'lla-data'}")
    create_app().run(host="127.0.0.1", port=port, debug=False, threaded=True)

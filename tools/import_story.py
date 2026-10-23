#!/usr/bin/env python3
"""Import a story and its vocabulary cards into the LLA data on the Mac Mini.

    python3 tools/import_story.py story.json [--dry-run] [--url https://i019945mini.taila20961.ts.net]

story.json:
    {"story": {"title": "...", "youtubeUrl": "...", "sentences": [{"ko": "...", "en": "..."}]},
     "cards": [{"korean": "...", "english": "'사전형' (verb) meaning", "examples": ["ko = en"], "notes": "..."}]}

What it does (stdlib only, talks to the same /api/data the app uses):
  * validates the file (Hangul inside the quoted part of `english`, required fields)
  * skips a story whose title already exists and cards whose Korean text already exists in ANY deck
  * fills in defaults (tag story, deck = story title, ease 2.0, interval 1, due now, reps 0)
  * saves with the server's revision check; on a conflict it reloads once and retries
  * --dry-run prints exactly what would change and writes nothing
Afterwards tap "Load from Mini" in the app. No code deploy, no index.html edit, no rsync.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = "https://i019945mini.taila20961.ts.net"
HANGUL = re.compile(r"^[ᄀ-ᇿ㄰-㆏가-힯 ]+$")
QUOTED = re.compile(r"^'([^']*)'")


def validate(payload):
    """Return a list of human-readable problems (empty list = fine)."""
    problems = []
    story = payload.get("story")
    if not isinstance(story, dict) or not story.get("title"):
        problems.append("story.title is required")
    elif not isinstance(story.get("sentences"), list) or not story["sentences"]:
        problems.append("story.sentences must be a non-empty list of {ko, en}")
    else:
        for i, s in enumerate(story["sentences"]):
            if not (isinstance(s, dict) and s.get("ko") and s.get("en")):
                problems.append(f"story.sentences[{i}] needs both ko and en")
    cards = payload.get("cards")
    if not isinstance(cards, list):
        problems.append("cards must be a list")
        return problems
    for i, c in enumerate(cards):
        label = f"cards[{i}] ({c.get('korean', '?') if isinstance(c, dict) else '?'})"
        if not isinstance(c, dict) or not c.get("korean") or not c.get("english"):
            problems.append(f"{label}: korean and english are required"); continue
        m = QUOTED.match(c["english"])
        if m and not HANGUL.match(m.group(1)):
            # the app's speakMeaning() sends the quoted part to the Korean voice
            problems.append(f"{label}: the quoted part of english must be Hangul only, got '{m.group(1)}'")
        if not isinstance(c.get("examples", []), list):
            problems.append(f"{label}: examples must be a list")
    return problems


def merge_import(data, payload, now_ms=None):
    """Return (new_data, report). `data` is the server document; it is not modified."""
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    new = {**data, "cards": list(data.get("cards", [])), "stories": list(data.get("stories", []))}
    story = payload["story"]
    report = {"story": None, "added": [], "skipped": []}

    if any(s.get("title") == story["title"] for s in new["stories"]):
        report["story"] = "skipped (a story with this title already exists)"
    else:
        used = {s.get("id") for s in new["stories"]}
        sid = now
        while sid in used:
            sid += 1
        new["stories"].insert(0, {"id": sid, "title": story["title"], "youtubeUrl": story.get("youtubeUrl", ""),
                                  "sentences": story["sentences"], "deck": story["title"], "created": now})
        report["story"] = "added"

    existing_ko = {c.get("korean") for c in new["cards"]}
    used_ids = {c.get("id") for c in new["cards"]}
    next_id = now
    for c in payload["cards"]:
        if c["korean"] in existing_ko:
            report["skipped"].append(c["korean"]); continue
        while next_id in used_ids:
            next_id += 1
        card = {"id": next_id, "korean": c["korean"], "english": c["english"],
                "examples": c.get("examples", []), "notes": c.get("notes", ""),
                "tag": c.get("tag", "story"), "deck": c.get("deck", story["title"]),
                "level": c.get("level", ""), "trap": c.get("trap", ""),
                "created": now, "nextReview": now,
                "interval": c.get("interval", 1), "ease": c.get("ease", 2.0), "reps": c.get("reps", 0)}
        used_ids.add(next_id); existing_ko.add(card["korean"]); next_id += 1
        new["cards"].append(card)
        report["added"].append(card["korean"])
    return new, report


def _request(url, method="GET", body=None):
    req = urllib.request.Request(url, method=method, data=body,
                                 headers={"X-LLA": "1", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def run(payload, base_url, dry_run=False):
    problems = validate(payload)
    if problems:
        return 2, {"problems": problems}
    api = base_url.rstrip("/") + "/api/data"
    for attempt in (1, 2):
        data = _request(api)
        new, report = merge_import(data, payload)
        report["rev_before"] = data["rev"]
        if dry_run or (report["story"] != "added" and not report["added"]):
            report["written"] = False
            return 0, report
        body = json.dumps({"baseRev": data["rev"], "cards": new["cards"], "stories": new["stories"],
                           "settings": data.get("settings", {})}).encode("utf-8")
        try:
            out = _request(api, "PUT", body)
        except urllib.error.HTTPError as e:
            if e.code == 409 and attempt == 1:
                continue                      # someone saved in between: reload and merge again
            return 1, {"error": f"save failed: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:200]}"}
        report.update(written=True, rev_after=out["rev"], cards_total=out["cards"], stories_total=out["stories"])
        return 0, report
    return 1, {"error": "gave up after a revision conflict"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    payload = json.load(open(args.file, encoding="utf-8"))
    code, rep = run(payload, args.url, args.dry_run)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    if code == 0 and rep.get("written"):
        print('\nDone. In the app tap "Load from Mini" to pull the new story and cards.')
    elif code == 0:
        print("\n(dry run or nothing new: nothing was written)")
    return code


if __name__ == "__main__":
    sys.exit(main())

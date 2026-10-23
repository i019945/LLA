import json
import sys
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import import_story as imp          # noqa: E402
import lla_server                   # noqa: E402


def payload(**over):
    p = {"story": {"title": "Test Walk 001", "youtubeUrl": "https://youtu.be/x",
                   "sentences": [{"ko": "안녕하세요", "en": "Hello"}]},
         "cards": [{"korean": "안녕", "english": "'안녕' (noun) hi", "examples": ["안녕 = hi"], "notes": "n"},
                   {"korean": "걸을", "english": "'걷다' (verb) to walk"}]}
    p.update(over); return p


# ---------------------------------------------------------------- validation
def test_valid_payload_has_no_problems():
    assert imp.validate(payload()) == []


@pytest.mark.parametrize("mutate,needle", [
    (lambda p: p["story"].pop("title"), "story.title"),
    (lambda p: p["story"].update(sentences=[]), "sentences"),
    (lambda p: p["story"].update(sentences=[{"ko": "x"}]), "both ko and en"),
    (lambda p: p["cards"][0].update(english="'geotda' (verb) to walk"), "Hangul only"),
    (lambda p: p["cards"][0].update(english="'걷다, 걸어' (verb) to walk"), "Hangul only"),
    (lambda p: p["cards"].append({"korean": "물"}), "required"),
    (lambda p: p.update(cards="x"), "cards must be a list"),
])
def test_bad_payloads_are_reported(mutate, needle):
    p = payload(); mutate(p)
    assert any(needle in x for x in imp.validate(p))


def test_english_without_quoted_form_is_allowed():
    p = payload(); p["cards"][0]["english"] = "hello (plain gloss)"
    assert imp.validate(p) == []


# -------------------------------------------------------------------- merge
BASE = {"rev": 3, "stories": [{"id": 5, "title": "Old"}], "settings": {},
        "cards": [{"id": 1, "korean": "안녕"}, {"id": 2, "korean": "물"}]}


def test_merge_adds_story_and_new_cards_with_defaults_and_skips_duplicates():
    new, rep = imp.merge_import(BASE, payload(), now_ms=1000)
    assert rep["story"] == "added" and rep["added"] == ["걸을"] and rep["skipped"] == ["안녕"]
    card = new["cards"][-1]
    assert (card["tag"], card["deck"], card["ease"], card["interval"], card["reps"], card["nextReview"]) == \
           ("story", "Test Walk 001", 2.0, 1, 0, 1000)
    assert new["stories"][0]["title"] == "Test Walk 001" and new["stories"][1]["title"] == "Old"
    assert BASE["cards"] == [{"id": 1, "korean": "안녕"}, {"id": 2, "korean": "물"}]   # input untouched


def test_merge_is_idempotent():
    once, _ = imp.merge_import(BASE, payload(), now_ms=1000)
    twice, rep = imp.merge_import(once, payload(), now_ms=2000)
    assert twice == once and rep["added"] == [] and "skipped" in rep["story"]


def test_ids_never_collide_with_existing_ones():
    data = {**BASE, "cards": [{"id": 1000, "korean": "x"}, {"id": 1001, "korean": "y"}], "stories": [{"id": 1000, "title": "S"}]}
    new, _ = imp.merge_import(data, payload(), now_ms=1000)
    ids = [c["id"] for c in new["cards"]]
    assert len(ids) == len(set(ids)) and new["stories"][0]["id"] == 1001


# ------------------------------------------------- against a real local server
@pytest.fixture
def live(tmp_path):
    app = lla_server.create_app(tmp_path / "data")
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{srv.server_port}", app.config["STORE"]
    srv.shutdown()


def test_dry_run_writes_nothing(live):
    url, store = live
    before = store.read()
    code, rep = imp.run(payload(), url, dry_run=True)
    assert code == 0 and rep["written"] is False and store.read() == before


def test_real_import_then_second_run_is_a_noop(live):
    url, store = live
    n0 = len(store.read()["cards"])
    code, rep = imp.run(payload(), url)
    assert code == 0 and rep["written"] and rep["rev_after"] == rep["rev_before"] + 1
    doc = store.read()
    assert len(doc["cards"]) == n0 + 2 and doc["stories"][0]["title"] == "Test Walk 001"
    code, rep2 = imp.run(payload(), url)
    assert code == 0 and rep2["written"] is False and store.read()["rev"] == doc["rev"]


def test_invalid_file_is_refused_before_touching_the_server(live):
    url, store = live
    rev = store.read()["rev"]
    p = payload(); p["cards"][0]["english"] = "'bad romanization' (verb) x"
    code, rep = imp.run(p, url)
    assert code == 2 and rep["problems"] and store.read()["rev"] == rev


def test_conflict_is_retried_once(live, monkeypatch):
    url, store = live
    real_request, state = imp._request, {"bumped": False}
    def racing(u, method="GET", body=None):
        if method == "PUT" and not state["bumped"]:       # another device saves just before our PUT
            state["bumped"] = True
            cur = store.read()
            store.replace(cur["rev"], cur["cards"], cur["stories"], cur["settings"])
        return real_request(u, method, body)
    monkeypatch.setattr(imp, "_request", racing)
    code, rep = imp.run(payload(), url)
    assert code == 0 and rep["written"] and state["bumped"]

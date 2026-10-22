import json
import threading

import pytest

import lla_server

H = {"X-LLA": "1"}


@pytest.fixture
def client(tmp_path):
    app = lla_server.create_app(tmp_path / "data")
    return app.test_client(), tmp_path / "data"


def put(c, **over):
    body = {"baseRev": 0, "cards": [{"id": "c1"}], "stories": [{"id": 1}], "settings": {"lla_rate": "0.7"}}
    body.update(over)
    return c.put("/api/data", json=body, headers=H)


def test_first_start_seeds_cards_from_repo_and_starts_at_rev0(client):
    c, d = client
    doc = c.get("/api/data").get_json()
    assert doc["rev"] == 0 and len(doc["cards"]) > 100 and doc["stories"] == []
    assert (d / "data.json").exists()


def test_put_stores_data_bumps_rev_and_keeps_backup(client):
    c, d = client
    r = put(c)
    assert r.status_code == 200 and r.get_json()["rev"] == 1
    doc = c.get("/api/data").get_json()
    assert doc["cards"] == [{"id": "c1"}] and doc["settings"] == {"lla_rate": "0.7"}
    assert len(list((d / "backups").glob("data-*.json"))) == 1   # previous version kept


def test_stale_base_rev_is_rejected_and_data_untouched(client):
    c, _ = client
    put(c)                                   # rev 0 -> 1
    r = put(c, cards=[{"id": "other"}])      # still claims baseRev 0
    assert r.status_code == 409 and r.get_json()["rev"] == 1
    assert c.get("/api/data").get_json()["cards"] == [{"id": "c1"}]


@pytest.mark.parametrize("over", [
    {"baseRev": "0"}, {"baseRev": True}, {"cards": "x"}, {"stories": {}},
    {"cards": [{"no_id": 1}]}, {"cards": ["str"]}, {"settings": []},
    {"settings": {"lla_gh_token": "secret"}}, {"settings": {"lla_anthropic_key": "sk"}},
    {"settings": {"lla_rate": 0.7}},
])
def test_invalid_payloads_rejected(client, over):
    c, _ = client
    before = c.get("/api/data").get_json()
    assert put(c, **over).status_code == 400
    assert c.get("/api/data").get_json() == before


def test_requires_header_and_json_content_type(client):
    c, _ = client
    assert c.put("/api/data", json={}).status_code == 400                       # no X-LLA
    r = c.put("/api/data", data="{}", headers={**H, "Content-Type": "text/plain"})
    assert r.status_code == 415


def test_non_object_body_rejected(client):
    c, _ = client
    assert c.put("/api/data", data="[1,2]", headers={**H, "Content-Type": "application/json"}).status_code == 400


def test_backups_are_pruned(client, monkeypatch):
    c, d = client
    monkeypatch.setattr(lla_server, "BACKUPS_KEEP", 3)
    for i in range(6):
        assert put(c, baseRev=i).status_code == 200
    assert len(list((d / "backups").glob("data-*.json"))) == 3


def test_only_allowlisted_static_files_are_served(client):
    c, _ = client
    assert c.get("/").status_code == 200
    for ok in ("index.html", "sw.js", "manifest.json", "vocab.json"):
        assert c.get("/" + ok).status_code == 200, ok
    for bad in ("import_seoul016.js", "import_seoul016_cards2.js", "cards.json", "lla_server.py", ".git/config", "../etc/passwd", "tests/test_server.py"):
        assert c.get("/" + bad).status_code == 404, bad


def test_healthz_and_no_store_header(client):
    c, _ = client
    r = c.get("/healthz")
    assert r.data == b"ok" and r.headers["Cache-Control"] == "no-store"


def test_concurrent_writers_only_one_wins_per_rev(client):
    c, _ = client
    codes = []
    def go(i):
        codes.append(put(c, cards=[{"id": f"w{i}"}]).status_code)
    ts = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(codes) == [200] + [409] * 7


def test_data_survives_restart_and_is_not_reseeded(tmp_path):
    d = tmp_path / "data"
    c1 = lla_server.create_app(d).test_client()
    put(c1)
    c2 = lla_server.create_app(d).test_client()          # "reboot"
    doc = c2.get("/api/data").get_json()
    assert doc["rev"] == 1 and doc["cards"] == [{"id": "c1"}]

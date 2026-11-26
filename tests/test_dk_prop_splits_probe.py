"""scripts/dk_prop_splits_probe.py: title filter, body description, paging, and the probe's flow. No network."""
from __future__ import annotations

import json
from pathlib import Path

import scripts.dk_prop_splits_probe as P
from tracking import job_queue

ROOT = Path(__file__).resolve().parents[1]


def test_is_prop_split_title():
    assert P.is_prop_split_title("Colts vs. Chiefs Player Prop Bet Splits for Sunday")
    assert P.is_prop_split_title("Super Bowl Player Prop & Novelty Prop Splits")
    assert not P.is_prop_split_title("DraftKings Sportsbook Betting Splits for NFL")
    assert not P.is_prop_split_title("Eagles at Cowboys NFL Player Prop Bets for Thanksgiving")


def test_describe_body_counts_tables_and_reads_around_each_percent():
    html = ("<p>Patrick Mahomes Over 1.5 Passing TDs</p><table><tr><td>Handle</td><td>71%</td></tr>"
            "<tr><td>Bets</td><td>64%</td></tr></table>")
    d = P.describe_body(html)
    assert d["tables"] == 1 and d["rows"] == 2 and d["percents"] == 2
    assert "Mahomes" in d["windows"][0] and "71%" in d["windows"][0]


def test_search_posts_pages_until_the_last_page():
    calls = []

    def get(url, **kw):
        page = kw["params"]["page"]
        calls.append(page)
        posts = [{"id": page * 10 + i, "date": f"2026-09-{page:02d}T12:00:00", "link": "x",
                  "title": {"rendered": "A &amp; B Prop Splits"}} for i in range(2)]
        return 200, json.dumps(posts), {"X-WP-TotalPages": "2"}, None

    posts, err = P.search_posts(get, "prop splits")
    assert err is None and calls == [1, 2] and len(posts) == 4
    assert posts[0]["title"] == "A & B Prop Splits"


def test_probe_reports_counts_bodies_and_tennis(capsys):
    seen = []

    class Conn:
        def execute(self, sql, params):
            return type("R", (), {"fetchone": lambda self: ("2026-11-22",) if params[0] == "ATP" else (None,)})()

    def get(url, **kw):
        seen.append((url, kw.get("params")))
        if url == P.WP_POSTS:
            if kw["params"]["page"] > 1:
                return 200, "[]", {}, None
            return 200, json.dumps([
                {"id": 1, "date": "2025-02-09T10:00:00", "link": "a", "title": {"rendered": "Super Bowl Prop Splits"}},
                {"id": 2, "date": "2026-09-20T10:00:00", "link": "b", "title": {"rendered": "Colts Prop Bet Splits"}},
                {"id": 3, "date": "2026-09-21T10:00:00", "link": "c", "title": {"rendered": "Picks for Sunday"}},
            ]), {}, None
        if url.startswith(P.WP_POSTS + "/"):
            return 200, json.dumps({"content": {"rendered": "<table><tr><td>Over</td><td>55%</td></tr></table>"}}), {}, None
        if "/scoreboard/atp" in url:
            return 200, json.dumps({"games": [{"markets": {"15": {"event": {"moneyline": [
                {"bet_info": {"tickets": {"percent": 62}}}]}}}}]}), {}, None
        return 404, "", {}, None

    assert P.probe(get=get, conn=Conn()) == 0
    out = capsys.readouterr().out
    assert "prop-split posts, distinct: 2; by year {'2025': 1, '2026': 1}" in out
    assert "body 2 (2026-09-20)" in out and "body 1 (2025-02-09)" in out
    assert "an atp 20261122: games=1 with a non-zero split=1" in out
    assert "an wta: no past WTA date in games" in out


def test_job_is_registered_and_declared():
    assert "dk_prop_splits_probe" in job_queue.JOBS
    declared = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    entry = [d for d in declared if d.get("job_type") == "dk_prop_splits_probe"]
    assert len(entry) == 1 and entry[0]["args"] == {}

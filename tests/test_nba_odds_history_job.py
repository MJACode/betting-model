"""The two NBA purchases mike approved on 2026-10-24 and the plan behind the second.

Worker job `nba_odds_history`: alternate ladders (docs/nba_models_2026.md section 10) and the
slate every 5 minutes around injury-report changes (section 11). Each mode buys a fixed scope
under a ceiling it cannot exceed, keeps a floor under the balance, and runs the repo's buyer
module, never a shell. The plan (scripts/nba_news_window_plan.py) names the instants.
"""
from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

import tracking.job_queue as jq
from data.ingestors import nba_odds_history as h
from scripts import nba_news_window_plan as plan

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "jobs" / "nba_news_windows_2025_2026.json"


def test_the_job_is_on_the_allowlist_and_runs_the_buyer_module():
    fn, validate = jq.JOBS["nba_odds_history"]
    assert fn is jq._job_nba_odds_history and validate is jq._validate_nba_odds_history
    src = inspect.getsource(jq._job_nba_odds_history)
    assert "data.ingestors.nba_odds_history" in src and "_run_script_main" in src
    assert "subprocess" not in src


@pytest.mark.parametrize("args", [
    {"mode": "alternates", "max_credits": 130_001, "floor": 800_000},     # above the approved scope
    {"mode": "news_windows", "max_credits": 270_001, "floor": 800_000},
    {"mode": "alternates", "max_credits": 0, "floor": 800_000},
    {"mode": "alternates", "max_credits": 100_000, "floor": 499_999},     # would let the feeds run dry
    {"mode": "alternates", "max_credits": 100_000},
    {"mode": "props", "max_credits": 100_000, "floor": 800_000},          # not an approved purchase
    {"mode": "alternates", "max_credits": 100_000, "floor": 800_000, "seasons": [2020, 2026]},
])
def test_a_request_outside_the_approved_scope_is_refused(args):
    with pytest.raises(ValueError):
        jq._validate_nba_odds_history(args)


def test_each_mode_buys_its_own_fixed_scope(monkeypatch):
    seen = []
    monkeypatch.setattr(jq, "_run_script_main", lambda mod, argv: seen.append((mod, argv)) or "ok")
    jq._job_nba_odds_history(**jq._validate_nba_odds_history(
        {"mode": "alternates", "max_credits": 130_000, "floor": 800_000}))
    jq._job_nba_odds_history(**jq._validate_nba_odds_history(
        {"mode": "news_windows", "max_credits": 270_000, "floor": 800_000}))
    (m1, a1), (m2, a2) = seen
    assert m1 == m2 == "data.ingestors.nba_odds_history"
    assert a1[:1] == ["--alternates"] and a1[a1.index("--seasons") + 1:a1.index("--seasons") + 3] == ["2024", "2026"]
    assert "--apply" in a1 and a1[a1.index("--max-credits") + 1] == "130000" and a1[a1.index("--floor") + 1] == "800000"
    i = a2.index("--instants")
    assert Path(a2[i + 1]).is_absolute() and Path(a2[i + 1]).exists()
    assert a2[a2.index("--seasons") + 1:a2.index("--seasons") + 3] == ["2025", "2026"]
    assert a2[a2.index("--why") + 1] == "news_window"


def test_the_declared_purchases_validate_and_fit_their_ceilings():
    declared = {e["key"]: e for e in json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))}
    alt, news = declared["nba-alt-history-2024-2026"], declared["nba-news-windows-2025-2026"]
    for e in (alt, news):
        assert e["requested_by"] == "mike" and e.get("enabled", True) is True
        jq._validate_nba_odds_history(e["args"])
    body = json.loads(PLAN.read_text(encoding="utf-8"))
    assert body["credits_per_instant"] * len(body["instants"]) <= news["args"]["max_credits"]


def test_the_plan_asks_one_minute_past_each_mark_newest_first():
    t = h.read_instants(PLAN)
    assert len(t) == len(set(t)) == len(json.loads(PLAN.read_text(encoding="utf-8"))["instants"])
    assert t == sorted(t, reverse=True)
    # the feed returns the latest snapshot at or before the request, 38-39 s past its mark:
    # one minute past the mark buys the snapshot just after it
    assert all(x.minute % 5 == 1 and x.second == 0 and x.tzinfo is not None for x in t)
    assert len({plan.slot(x) for x in t}) == len(t), "two requests in the plan return one snapshot"


def test_an_instant_off_the_minute_stops_the_read(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps({"instants": ["2025-01-15T23:31:30Z"]}), encoding="utf-8")
    with pytest.raises(ValueError):
        h.read_instants(p)


def test_a_request_returns_the_snapshot_at_or_before_it():
    # measured: 00:10:00 -> 00:05:38, 17:00:00 -> 16:55:38 (oddsapi_probe/ledger.jsonl)
    assert plan.slot(pd.Timestamp("2025-02-11T00:10:00Z")) == pd.Timestamp("2025-02-11T00:05:00Z")
    assert plan.slot(pd.Timestamp("2025-02-11T00:06:00Z")) == pd.Timestamp("2025-02-11T00:05:00Z")
    assert plan.slot(pd.Timestamp("2025-02-11T00:05:30Z")) == pd.Timestamp("2025-02-11T00:00:00Z")


def test_the_buyer_skips_instants_either_ledger_holds(monkeypatch, tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps({"instants": ["2025-01-15T23:00:00Z", "2025-01-15T23:35:00Z",
                                          "2025-01-15T23:40:00Z"]}), encoding="utf-8")
    bought = []
    monkeypatch.setattr(h, "_ensure_ledgers", lambda conn: None)
    monkeypatch.setattr(h, "_known_games", lambda conn, a, b: {})
    monkeypatch.setattr(h, "_held_fetches", lambda conn: [
        datetime(2025, 1, 15, 23, 0, tzinfo=timezone.utc), datetime(2025, 1, 15, 23, 35, tzinfo=timezone.utc)])
    monkeypatch.setattr(h, "_buy_snapshot", lambda conn, meter, games, at, stats, why: bought.append((at, why)) or True)
    h.buy_instants(object(), h.Meter(1000, 0), 2025, 2025, p, "news_window")
    assert bought == [(datetime(2025, 1, 15, 23, 40, tzinfo=timezone.utc), "news_window")]


def _world():
    tip = pd.Timestamp("2025-01-16T00:10:00Z")
    games = pd.DataFrame({"game_id": ["G1"], "game_date": ["2025-01-15"], "home_team": ["PHI"],
                          "away_team": ["NYK"], "season": [2025], "tip": [tip]})
    adv = pd.DataFrame({"player_id": ["7"] * 5, "season": [2025] * 5,
                        "game_date": ["2025-01-05", "2025-01-07", "2025-01-09", "2025-01-11", "2025-01-15"],
                        "team": ["PHI"] * 5, "game_type": ["regular"] * 5,
                        "played": [True, True, True, True, False], "minutes_exact": [36.0, 34.0, 35.0, 35.0, 0.0]})
    r1, r2 = pd.Timestamp("2025-01-15T22:30:00Z"), pd.Timestamp("2025-01-15T23:30:00Z")
    ir = pd.DataFrame({"game_id": ["G1", "G1"], "team": ["PHI", "PHI"], "season": [2025, 2025],
                       "report_ts": [r1, r2], "player_id": ["7", "7"],
                       "status": ["Questionable", "Out"]})
    return games, adv, ir, r2, tip


def test_a_home_starter_ruled_out_moves_the_home_margin_down():
    games, adv, ir, r2, _ = _world()
    ev = plan.events(ir, adv, games)
    assert list(ev["report_ts"]) == [r2]
    # Questionable (0.5) -> Out (0): half of 35 minutes lost by the HOME team
    assert ev["s"].iloc[0] == pytest.approx(-0.5 * 35.0 * plan.K_PTS_PER_MIN)


def test_the_plan_brackets_the_report_and_stops_short_of_tip():
    games, adv, ir, r2, tip = _world()
    ev = plan.events(ir, adv, games)
    # held: a request one minute past R (it returns R's snapshot), and the hourly 00:00
    # request, which returns the 23:55 snapshot
    got = plan.instants(ev, held=[r2 + pd.Timedelta(minutes=1), pd.Timestamp("2025-01-16T00:00:00Z")])
    marks = [r2 + pd.Timedelta(minutes=k) for k in (-5, 5, 10, 15, 20)]   # R held; R+25 = 23:55 is at tip - 15
    assert got == [m + plan.REQUEST_LAG for m in marks]


def test_a_player_out_of_the_lineup_does_not_dilute_his_minutes():
    rows = [{"player_id": "1", "season": 2025, "game_date": f"2025-01-{d:02d}", "team": "X",
             "game_type": "regular", "played": d != 13, "minutes_exact": float(d) if d != 13 else 0.0}
            for d in range(1, 15)]
    m = plan.player_minutes(pd.DataFrame(rows)).set_index("game_date")["mpg"]
    assert m.loc["2025-01-12"] == pytest.approx(sum(range(2, 12)) / 10)   # games 2..11
    assert m.loc["2025-01-14"] == pytest.approx(sum(range(3, 13)) / 10)   # 13 was a DNP: games 3..12


# ── a rejected paid call is retried, not skipped for good ───────────────────

class _Resp:
    def __init__(self, status, body=None, last="0"):
        self.status_code, self._body = status, body or {}
        self.headers = {"x-requests-last": last, "x-requests-remaining": "1500000"}

    def json(self):
        return self._body


def test_a_rate_limited_answer_is_retried_and_every_answer_is_billed(monkeypatch):
    answers = [_Resp(429), _Resp(503), _Resp(200, {"ok": 1}, last="30")]
    monkeypatch.setattr(h.requests, "get", lambda *a, **k: answers.pop(0))
    monkeypatch.setattr(h.time, "sleep", lambda s: None)
    monkeypatch.setattr(h, "record_quota_headers", lambda r: None)
    m = h.Meter(1000, 0)
    r = m.get("u", {})
    assert r.status_code == 200 and m.spent == 30 and not answers


def test_a_game_with_no_answer_gets_a_second_pass(monkeypatch):
    game = {"game_id": "G1", "game_date": "2025-01-15", "home": "PHI", "away": "NYK", "commence_time": None}
    monkeypatch.setattr(h, "_known_games", lambda conn, a, b: {"G1": game})
    ev = {"id": "E1", "commence_time": "2025-01-16T00:10:00Z", "home_team": "Philadelphia 76ers",
          "away_team": "New York Knicks"}
    calls = []

    def fake_get(url, params):
        calls.append(url)
        if url.endswith("/events"):
            return _Resp(200, {"data": [ev]})
        return _Resp(500) if sum(1 for c in calls if "/events/E1/odds" in c) == 1 else _Resp(200, {
            "timestamp": "2025-01-15T23:05:38Z", "data": {"bookmakers": []}})

    m = h.Meter(10_000, 0)
    monkeypatch.setattr(m, "get", fake_get)
    out = h._buy_per_event(object(), m, 2025, 2025, 60, h.ALT_MARKETS, h.ALT_SOURCE,
                           h.parse_alternates, lambda conn, ids: set(), "alternates")
    assert sum(1 for c in calls if "/events/E1/odds" in c) == 2
    assert out["retried"] == 1 and out.get("still_failed", 0) == 0 and out["events"] == 1


def test_an_instant_with_no_answer_gets_a_second_pass(monkeypatch, tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps({"instants": ["2025-01-15T23:36:00Z", "2025-01-15T23:41:00Z"]}), encoding="utf-8")
    monkeypatch.setattr(h, "_ensure_ledgers", lambda conn: None)
    monkeypatch.setattr(h, "_known_games", lambda conn, a, b: {})
    monkeypatch.setattr(h, "_held_fetches", lambda conn: [])
    tries = []

    def fake_snapshot(conn, meter, games, at, stats, why):
        tries.append(at)
        if at.minute == 41 and tries.count(at) == 1:
            stats["errors"] += 1            # what _buy_snapshot does on a non-200 answer
        return True

    monkeypatch.setattr(h, "_buy_snapshot", fake_snapshot)
    out = h.buy_instants(object(), h.Meter(1000, 0), 2025, 2025, p, "news_window")
    assert [t.minute for t in tries] == [41, 36, 41]
    assert out["retried"] == 1 and out.get("still_failed", 0) == 0


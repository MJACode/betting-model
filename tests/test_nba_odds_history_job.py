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
    {"mode": "news_windows", "max_credits": 300_001, "floor": 800_000},
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
        {"mode": "news_windows", "max_credits": 300_000, "floor": 800_000}))
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


def test_the_plan_file_reads_newest_first_on_the_five_minute_grid():
    t = h.read_instants(PLAN)
    assert len(t) == len(set(t)) == len(json.loads(PLAN.read_text(encoding="utf-8"))["instants"])
    assert t == sorted(t, reverse=True)
    assert all(x.minute % 5 == 0 and x.second == 0 and x.tzinfo is not None for x in t)


def test_an_off_grid_instant_stops_the_read(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps({"instants": ["2025-01-15T23:32:00Z"]}), encoding="utf-8")
    with pytest.raises(ValueError):
        h.read_instants(p)


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
    got = plan.instants(ev, held=[r2])
    want = [r2 + pd.Timedelta(minutes=k) for k in (-5, 5, 10, 15, 20, 25)]   # R itself is held
    assert got == [t for t in want if t < tip - pd.Timedelta(minutes=plan.TIP_MARGIN_MIN)]

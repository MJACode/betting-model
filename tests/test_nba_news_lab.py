"""The seventh search's lab: rules the synthetic market does not reach (docs/nba_models_2026.md 11.3, 11.5)."""
from __future__ import annotations

import pandas as pd
import pytest

from scripts import nba_game7_news as N


def _world():
    tip = pd.Timestamp("2025-01-16T00:10:00Z")
    games = pd.DataFrame({"game_id": ["G1"], "game_date": ["2025-01-15"], "home_team": ["PHI"],
                          "away_team": ["NYK"], "season": [2025], "tip": [tip]})
    adv = []
    for pid, team in (("7", "PHI"), ("8", "NYK")):
        for d in ("2025-01-05", "2025-01-07", "2025-01-09", "2025-01-11"):
            adv.append({"player_id": pid, "season": 2025, "game_date": d, "team": team,
                        "game_type": "regular", "played": True, "minutes_exact": 35.0})
    r1, r2, r3 = (pd.Timestamp(x) for x in ("2025-01-15T21:30:00Z", "2025-01-15T22:30:00Z", "2025-01-15T23:30:00Z"))
    rows = []
    for r, st in ((r1, "Questionable"), (r2, "Out"), (r3, "Out")):
        for pid, team in (("7", "PHI"), ("8", "NYK")):
            rows.append({"game_id": "G1", "team": team, "season": 2025, "report_ts": r, "player_id": pid, "status": st})
    return games, pd.DataFrame(adv), pd.DataFrame(rows), r2, r3


def test_a_report_where_both_teams_lose_a_starter_is_not_quiet():
    """Both teams' starters ruled out at r2: the net home-margin move is 0, but each team
    changed by about 0.8 points, so 11.3's quiet control (neither team changed) excludes it.
    r3 changed nothing and is quiet."""
    games, adv, ir, r2, r3 = _world()
    q = N.quiet_reports(ir, adv, games)
    assert r3 in set(q["report_ts"])
    assert r2 not in set(q["report_ts"])


def test_the_snapshot_a_request_buys_is_the_mark_before_it():
    from scripts.nba_news_window_plan import slot
    f = pd.DataFrame({"game_id": ["G1", "G1"], "fetch_at": [pd.Timestamp("2025-01-15T22:36:00Z"),
                                                          pd.Timestamp("2025-01-15T23:00:00Z")]})
    idx = N.slot_index(f)
    assert idx[("G1", pd.Timestamp("2025-01-15T22:35:00Z"))] == pd.Timestamp("2025-01-15T22:36:00Z")
    assert idx[("G1", pd.Timestamp("2025-01-15T22:55:00Z"))] == pd.Timestamp("2025-01-15T23:00:00Z")
    snaps = N.snap_times(f, None)
    assert snaps[pd.Timestamp("2025-01-15T22:36:00Z")] == pd.Timestamp("2025-01-15T22:35:38Z")
    led = pd.DataFrame({"requested_at": [pd.Timestamp("2025-01-15T22:36:00Z")],
                        "snapshot_ts": ["2025-01-15T22:35:39Z"]})
    assert N.snap_times(f, led)[pd.Timestamp("2025-01-15T22:36:00Z")] == pd.Timestamp("2025-01-15T22:35:39Z")

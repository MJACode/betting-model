"""The NCAAF in-play history ingestor and its replay harness, on synthetic data.

The paid pull cannot be exercised here (it spends credits) and the replay
needs a states parquet this checkout does not hold, so what is pinned is the
plumbing both depend on: which events become rows and under which id, how a
snapshot finds its state, that the harness's decision rule IS the loop's, and
that the first-signal lock takes the earliest crossing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from data.ingestors import ncaaf_inplay_history as ing
from scripts import ncaaf_inplay_history_backtest as bt

UTC = timezone.utc


@pytest.fixture(autouse=True)
def _no_db_school_lookup(monkeypatch):
    """The NCAAF normaliser resolves mascots against the DB registry; the
    test strips them itself so nothing opens a connection."""
    monkeypatch.setattr(ing, "_normalize_team",
                        lambda name, sport: name.rsplit(" ", 1)[0])


def _event(home="Ohio State Buckeyes", away="Ball State Cardinals",
           commence="2025-09-06T16:00:00Z", markets=None):
    return {"home_team": home, "away_team": away, "commence_time": commence,
            "bookmakers": [{"key": "draftkings", "markets": markets or [
                {"key": "totals", "last_update": "2025-09-06T17:10:00Z",
                 "outcomes": [{"name": "Over", "price": -110, "point": 55.5},
                              {"name": "Under", "price": -110, "point": 55.5}]},
                {"key": "h2h", "last_update": "2025-09-06T17:09:30Z",
                 "outcomes": [{"name": home, "price": -900},
                              {"name": away, "price": 600}]}]}]}


# ── the ingestor ─────────────────────────────────────────────────────────────

def test_rows_carry_both_markets_with_their_own_last_update():
    served = datetime(2025, 9, 6, 17, 10, 12, tzinfo=UTC)
    rows = ing.rows_for([_event()], "2025-09-06T17:10:00Z", served)
    assert {r["market"] for r in rows} == {"totals", "h2h"}
    tot = next(r for r in rows if r["market"] == "totals")
    ml = next(r for r in rows if r["market"] == "h2h")
    assert tot["total_line"] == 55.5 and tot["over_price"] == -110
    assert ml["home_price"] == -900 and ml["away_price"] == 600
    assert tot["source"].endswith("|lu=2025-09-06T17:10:00Z")
    assert ml["source"].endswith("|lu=2025-09-06T17:09:30Z")
    for r in rows:
        assert r["snapshot_type"] == "in_play" and r["bookmaker"] == "draftkings"
        assert r["snapshot_at"] == "2025-09-06T17:10:12Z"
        assert r["game_id"] == "NCAAF_2025-09-06_ball-state_ohio-state"


def test_a_market_filter_writes_only_that_market():
    served = datetime(2025, 9, 6, 17, 10, 12, tzinfo=UTC)
    rows = ing.rows_for([_event()], "x", served, markets=("totals",))
    assert [r["market"] for r in rows] == ["totals"]


def test_pregame_events_are_not_written():
    served = datetime(2025, 9, 6, 15, 0, tzinfo=UTC)          # an hour before kickoff
    assert ing.rows_for([_event()], "x", served) == []


def test_an_event_missing_from_games_is_skipped_and_counted():
    served = datetime(2025, 9, 6, 17, 10, tzinfo=UTC)
    skipped: dict = {}
    rows = ing.rows_for([_event()], "x", served, known_games=set(), skipped=skipped)
    assert rows == [] and sum(skipped.values()) == 1


def test_a_late_kickoff_falls_back_to_its_utc_dated_games_row():
    """A 10:30pm ET kick is the next day in UTC; CFBD dates some of those by
    UTC (#301). The ET id is tried first, the UTC id second, nothing invented."""
    ev = _event(commence="2025-09-07T02:30:00Z")                # 10:30pm ET on the 6th
    et_id = "NCAAF_2025-09-06_ball-state_ohio-state"
    utc_id = "NCAAF_2025-09-07_ball-state_ohio-state"
    assert ing.resolve_game_id(ev, {et_id, utc_id}) == et_id
    assert ing.resolve_game_id(ev, {utc_id}) == utc_id
    assert ing.resolve_game_id(ev, {"NCAAF_2025-09-08_x_y"}) is None


class _Conn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        return self

    def fetchall(self):
        return self.rows


def test_slate_windows_and_planned_calls_span_first_kick_to_last_plus_four_hours():
    conn = _Conn([("2025-09-06", "2025-09-06T16:00:00Z", "2025-09-07T02:30:00Z")])
    (day, lo, hi), = ing.slate_windows(conn, 2025)
    assert day == "2025-09-06"
    assert lo == datetime(2025, 9, 6, 15, 55, tzinfo=UTC)
    assert hi == datetime(2025, 9, 7, 6, 30, tzinfo=UTC)
    # 14h35m of 5-minute steps, inclusive of both ends
    assert ing.planned_calls([(day, lo, hi)]) == 176


# ── the harness: a quote finds its state ─────────────────────────────────────

def _wall(*minutes):
    base = np.datetime64("2025-09-06T16:00:00", "ns")
    return np.array([base + np.timedelta64(m, "m") for m in minutes], dtype="datetime64[ns]")


def test_state_at_is_the_pre_play_state_of_the_next_play():
    wall = _wall(0, 10, 20)
    at = lambda m: datetime(2025, 9, 6, 16, tzinfo=UTC) + timedelta(minutes=m)
    assert bt.state_index_at(wall, at(-5)) == 0     # before kickoff: the opening state
    assert bt.state_index_at(wall, at(10)) == 2     # ON a play's clock: that play has begun
    assert bt.state_index_at(wall, at(12)) == 2     # between plays: the next play's pre-state
    assert bt.state_index_at(wall, at(25)) is None  # after the last play: not priced


def test_odds_dict_has_the_shape_the_loop_reads():
    rows = [{"market": "totals", "total_line": 55.5, "over_price": -110, "under_price": -110,
             "source": "historical_inplay|req=a|served=b|lu=2025-09-06T17:10:00Z"},
            {"market": "h2h", "home_price": -900, "away_price": 600,
             "source": "historical_inplay|req=a|served=b|lu=None"}]
    odds, lu = bt.odds_from_rows(rows)
    assert odds == {"total": {"line": 55.5, "over": -110, "under": -110},
                    "h2h": {"home": -900.0, "away": 600.0}}
    assert lu == {"total": "2025-09-06T17:10:00Z", "h2h": "None"}


# ── the harness: grading and the decision rule ───────────────────────────────

def _cand(model_id="ncaaf_live_total", side="over", p=0.70, odds=-110, line=55.5):
    implied = abs(odds) / (abs(odds) + 100) if odds < 0 else 100 / (odds + 100)
    return {"model_id": model_id, "pick_side": side, "model_probability": p,
            "dk_implied_prob": implied, "edge": p - implied, "dk_odds": odds,
            "scored_line": line if model_id == "ncaaf_live_total" else None}


def test_grade_totals_and_moneyline():
    assert bt.grade(_cand(side="over"), 30, 28) == ("WIN", pytest.approx(100 / 110))
    assert bt.grade(_cand(side="under"), 30, 28) == ("LOSS", -1.0)
    assert bt.grade(_cand(side="over", line=58.0), 30, 28) == ("PUSH", 0.0)
    ml = _cand("ncaaf_live_win_prob", "away", odds=600)
    assert bt.grade(ml, 30, 28) == ("LOSS", -1.0)
    assert bt.grade(ml, 20, 28) == ("WIN", 6.0)


def test_the_harness_decides_exactly_as_the_loop_does():
    """decide() restates LiveEngine._decide; a divergence would mean a cut
    swept here is not the cut the loop applies."""
    from ncaaf_live.serve import LiveEngine, MAX_EDGE_CAP
    rng = np.random.default_rng(7)
    for _ in range(500):
        p = float(rng.uniform(0.3, 0.95))
        odds = float(rng.choice([-250, -150, -115, -110, -105, 100, 130, 200]))
        c = _cand(p=p, odds=odds)
        min_prob = float(rng.choice([0.55, 0.62, 0.66, 0.70]))
        min_edge = float(rng.choice([0.0, 0.10, 0.12]))
        min_ev = float(rng.choice([0.0, 0.22, 0.30])) if rng.random() < 0.7 else None
        theirs = LiveEngine._decide(p, c["edge"], min_prob, min_edge, odds, min_ev) == "BET"
        assert bt.decide(c, min_prob, min_edge, min_ev, MAX_EDGE_CAP) == theirs


def test_first_signal_lock_takes_the_earliest_crossing_per_game_and_lane():
    t0 = datetime(2025, 9, 6, 16, tzinfo=UTC)
    mk = lambda gid, m, p, since, secs: {**_cand(p=p), "game_id": gid, "served": t0 + timedelta(seconds=secs),
                                          "points_since_update": since, "age_sec": 30.0,
                                          "result": "WIN", "units": 0.9}
    # every crossing below sits under the 0.18 cap at -110 (edge = p - 0.524)
    cands = [mk("g1", 0, 0.60, 0, 0),      # below the cut
             mk("g1", 0, 0.68, 7, 60),     # crosses, but stale (a TD since the book's stamp)
             mk("g1", 0, 0.69, 0, 120),    # crosses, fresh
             mk("g1", 0, 0.70, 0, 180),    # a later, bigger crossing -- locked out
             mk("g2", 0, 0.69, 0, 90),
             mk("g3", 0, 0.80, 0, 95)]     # over the cap: a stale line, never a bet
    floors = {"ncaaf_live_total": 0.12, "ncaaf_live_win_prob": 0.10}
    all_q = bt.first_signals(cands, 0.66, floors, 0.22, 0.18)
    assert [(c["game_id"], c["model_probability"]) for c in all_q] == [("g1", 0.68), ("g2", 0.69)]
    fresh = bt.first_signals(cands, 0.66, floors, 0.22, 0.18, fresh_only=True)
    assert [(c["game_id"], c["model_probability"]) for c in fresh] == [("g2", 0.69), ("g1", 0.69)]
    young = bt.first_signals(cands, 0.66, floors, 0.22, 0.18, max_age_sec=10)
    assert young == []


# ── the harness: end to end on a synthetic game ──────────────────────────────

class _StubEngine:
    """Prices nothing itself; returns one over candidate that records the
    state it was handed, so alignment and staleness can be asserted."""
    def candidates(self, row, period, hs, as_, odds):
        if "total" not in odds:
            return []
        return [{**_cand(p=0.70, line=odds["total"]["line"]),
                 "seen_period": period, "seen_score": (hs, as_)}]


def test_build_candidates_aligns_scores_to_the_served_clock_and_flags_stale_quotes():
    base = pd.Timestamp("2025-09-06T16:00:00Z")
    states = pd.DataFrame({
        "game_id": ["G"] * 4, "season": [2025] * 4,
        "wall_ts": [base, base + pd.Timedelta(minutes=10),
                    base + pd.Timedelta(minutes=20), base + pd.Timedelta(minutes=30)],
        "period": [1, 1, 2, 2],
        "home_score": [0, 0, 7, 7], "away_score": [0, 0, 0, 3],
        "seconds_remaining": [3600, 3000, 2400, 1800],
        "final_home": [31.0] * 4, "final_away": [17.0] * 4,
    })
    src = "historical_inplay|req=x|served=y|lu={}"
    snaps = {"G": [
        # served at +12: state on the field is the pre-state of the +20 play
        # (7-0), and the book's stamp at +11 is on the same score -> fresh
        (datetime(2025, 9, 6, 16, 12, tzinfo=UTC),
         [{"market": "totals", "total_line": 44.5, "over_price": -110, "under_price": -110,
           "source": src.format("2025-09-06T16:11:00Z")}]),
        # served at +25: pre-state of the +30 play is 7-3, but the book stamped
        # at +15 when it was still 7-0 -> 3 points since update
        (datetime(2025, 9, 6, 16, 25, tzinfo=UTC),
         [{"market": "totals", "total_line": 47.5, "over_price": -105, "under_price": -115,
           "source": src.format("2025-09-06T16:15:00Z")}]),
        # served after the last play: not priced
        (datetime(2025, 9, 6, 19, 0, tzinfo=UTC),
         [{"market": "totals", "total_line": 50.5, "over_price": -110, "under_price": -110,
           "source": src.format("None")}]),
    ]}
    out = bt.build_candidates(_StubEngine(), states, snaps)
    assert len(out) == 2
    first, second = out
    assert first["seen_score"] == (7, 0) and first["points_since_update"] == 0
    assert first["age_sec"] == 60.0 and first["seconds_remaining"] == 2400
    assert second["seen_score"] == (7, 3) and second["points_since_update"] == 3
    assert (first["result"], round(first["units"], 3)) == ("WIN", round(100 / 110, 3))
    assert second["result"] == "WIN" and second["final_home"] == 31.0

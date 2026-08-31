"""
gameday.write_picks under the first-signal lock.

The exact scenario that motivated this (2026-08-29, TCU vs UNC): the loop
wrote Over 45.5 -120 as a BET, then DK moved to 46.5, and the next pass
deleted the 45.5 row and wrote Over 46.5 — so no live bet was ever "the" bet,
and the totals lane closing in Q4 would have erased whatever was standing
before it could settle. With the lock, Over 45.5 -120 is the bet of record.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import config as platform_config
import data.db as data_db
import models.scorer as scorer_mod
from ncaaf_live.gameday import LIVE_MODEL_IDS, write_picks


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, locked=()):
        self.locked = list(locked)
        self.deletes = []            # params dict of each DELETE
        self.committed = False
        self.closed = False

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT DISTINCT model_id"):
            return _Rows([(m,) for m in self.locked])
        if s.startswith("DELETE FROM picks"):
            self.deletes.append(params)
            return _Rows([])
        raise AssertionError(f"unexpected SQL: {s}")

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


GAME = "NCAAF_2026-08-29_north-carolina_tcu"


def _tot(side, line, odds, signal):
    return {"model_id": "ncaaf_live_total", "pick_side": side,
            "pick_label": f"UNC @ TCU {side} {line} (live)",
            "scored_line": line, "dk_odds": odds, "signal_type": signal,
            "model_probability": 0.68, "edge": 0.14, "game_id": GAME}


def _wp(side, signal):
    return {"model_id": "ncaaf_live_win_prob", "pick_side": side,
            "pick_label": f"{side} ML (live)", "scored_line": None,
            "dk_odds": -150.0, "signal_type": signal,
            "model_probability": 0.66, "edge": 0.11, "game_id": GAME}


@pytest.fixture
def db(monkeypatch):
    """Wire write_picks' lazy imports to a fake conn; capture inserts."""
    state = {"conn": FakeConn(), "written": []}
    monkeypatch.setattr(data_db, "get_connection", lambda: state["conn"])
    monkeypatch.setattr(scorer_mod, "_insert_picks",
                        lambda c, p: state["written"].extend(p))
    return state


def test_dry_run_never_touches_db(monkeypatch):
    monkeypatch.setattr(data_db, "get_connection",
                        lambda: (_ for _ in ()).throw(AssertionError("DB touched")))
    write_picks([_tot("over", 45.5, -120.0, "BET")], GAME, dry_run=True)


def test_first_bet_is_written_and_will_lock(db):
    """Pass 1: no standing BET — the fresh set is written (this is the lock
    forming; the next pass's SELECT will see it as a locked lane)."""
    picks = [_tot("over", 45.5, -120.0, "BET"), _tot("under", 45.5, -110.0, "AVOID")]
    write_picks(picks, GAME, dry_run=False)
    assert db["written"] == picks
    assert db["conn"].committed
    # blanket delete covered both (unlocked) lanes
    assert set(db["conn"].deletes[0]["m"]) == set(LIVE_MODEL_IDS)


def test_repriced_line_cannot_replace_the_locked_bet(db):
    """Pass 2 of the motivating bug: lane locked at Over 45.5 -120; DK now
    shows 46.5. The 46.5 rows must NOT be written and the locked lane must
    NOT be deleted — Over 45.5 -120 stays the bet of record."""
    db["conn"] = FakeConn(locked=["ncaaf_live_total"])
    repriced = [_tot("over", 46.5, -115.0, "BET"), _tot("under", 46.5, -105.0, "AVOID"),
                _wp("home", "AVOID")]
    write_picks(repriced, GAME, dry_run=False)
    assert db["written"] == [repriced[2]]                     # only the WP lane churns
    assert db["conn"].deletes and set(db["conn"].deletes[0]["m"]) == {"ncaaf_live_win_prob"}


def test_lane_close_cannot_erase_the_locked_bet(db):
    """Q4/OT: price() returns [] for the totals lane. The empty pass must not
    delete the locked row — this is what lets a live totals bet settle."""
    db["conn"] = FakeConn(locked=["ncaaf_live_total"])
    write_picks([], GAME, dry_run=False)
    assert db["written"] == []
    for params in db["conn"].deletes:
        assert "ncaaf_live_total" not in params["m"]


def test_both_lanes_locked_touches_nothing(db):
    db["conn"] = FakeConn(locked=list(LIVE_MODEL_IDS))
    write_picks([_tot("over", 47.5, -110.0, "BET"), _wp("home", "BET")],
                GAME, dry_run=False)
    assert db["written"] == [] and db["conn"].deletes == []
    assert db["conn"].committed and db["conn"].closed


def test_flag_off_restores_delete_and_replace(db, monkeypatch):
    monkeypatch.setattr(platform_config, "LOCK_LIVE_PICKS_AT_FIRST_SIGNAL", False)
    db["conn"] = FakeConn(locked=["ncaaf_live_total"])
    repriced = [_tot("over", 46.5, -115.0, "BET")]
    write_picks(repriced, GAME, dry_run=False)
    assert db["written"] == repriced
    assert set(db["conn"].deletes[0]["m"]) == set(LIVE_MODEL_IDS)


# ── EV floor + config as the single source of truth (2026-08-30) ─────────────
# serve.py used to carry its OWN copies of the prob/edge floors, so config.py --
# the file the scorer, threshold_sync, the app's action filter and the record
# views all read -- could disagree with the thing that actually decides. It did:
# config said edge 0.08 while serve said 0.12. And MODEL_MIN_EV was honoured by
# the MLB live scorer but not here, so an EV floor set for an NCAAF model was
# silently inert.

def test_ncaaf_live_floors_come_from_the_platform_config():
    from ncaaf_live import serve
    import config as platform_config
    for model_id, prob_attr, edge_attr in (
        ("ncaaf_live_total", "TOTAL_MIN_PROB", "TOTAL_MIN_EDGE"),
        ("ncaaf_live_win_prob", "ML_MIN_PROB", "ML_MIN_EDGE"),
    ):
        cut = platform_config.ACTION_THRESHOLDS[model_id]
        assert getattr(serve, prob_attr) == cut["min_prob"], model_id
        assert getattr(serve, edge_attr) == cut["min_edge"], model_id


def test_ncaaf_live_ev_floor_is_wired_from_config():
    from ncaaf_live import serve
    import config as platform_config
    assert serve.TOTAL_MIN_EV == platform_config.MODEL_MIN_EV.get("ncaaf_live_total")
    assert serve.ML_MIN_EV == platform_config.MODEL_MIN_EV.get("ncaaf_live_win_prob")


def test_ev_floor_declines_a_qualifying_pick_that_is_priced_too_short():
    """prob and edge both clear; the price makes the EV bad. That is a decline."""
    from ncaaf_live.serve import LiveEngine
    # p 0.66 at -150 -> EV 0.10, under a 0.22 floor.
    assert LiveEngine._decide(0.66, 0.15, 0.66, 0.12, -150, 0.22) is None
    # Same pick with no floor configured still fires.
    assert LiveEngine._decide(0.66, 0.15, 0.66, 0.12, -150, None) == "BET"


def test_ev_floor_only_tightens_and_never_touches_avoid():
    from ncaaf_live.serve import LiveEngine
    # Clears the floor comfortably -> unchanged.
    assert LiveEngine._decide(0.70, 0.15, 0.66, 0.12, -120, 0.22) == "BET"
    # AVOID is not a stake, so an EV floor must not gate it.
    assert LiveEngine._decide(0.20, -0.15, 0.66, 0.12, -120, 0.22) == "AVOID"


def test_ev_floor_cannot_fire_without_a_price():
    """A prob-only pick has no EV; it is judged on the thresholds alone."""
    from ncaaf_live.serve import LiveEngine
    assert LiveEngine._decide(0.70, 0.15, 0.66, 0.12, None, 0.22) == "BET"

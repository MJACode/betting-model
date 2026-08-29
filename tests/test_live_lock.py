"""
First-signal LIVE lock (config.LOCK_LIVE_PICKS_AT_FIRST_SIGNAL).

The property under test: once a live lane (game, model) fires a BET, that row
is the bet of record — later passes must neither delete nor re-price it, and
must not write new rows for the lane. Before this lock, the delete-and-replace
churn meant a live BET could be re-priced every pass and was DESTROYED outright
when its lane closed (the NCAAF totals lane shuts in Q4), so no live totals bet
could ever settle into the model record.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import models.scorer as scorer_mod
import models.live_scorer as live_mod
from models.scorer import _locked_live_lanes
from models.live_scorer import _write_live_picks
from config import LIVE_MODELS


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeConn:
    """Records deletes; answers the locked-lanes SELECT from `locked`."""

    def __init__(self, locked=(), existing=()):
        self.locked = list(locked)
        # Rows already stored for the game, as
        # (model_id, pick_side, signal_type, scored_line, dk_odds). Default
        # empty = nothing stored, so every lane reads as changed and the
        # delete-and-replace behaviour these tests assert on is unaffected.
        self.existing = list(existing)
        self.deletes = []          # params of each DELETE
        self.committed = False
        self.closed = False

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT DISTINCT model_id"):
            return _Rows([(m,) for m in self.locked])
        if s.startswith("SELECT model_id, pick_side, signal_type"):
            return _Rows(self.existing)
        if s.startswith("DELETE FROM picks"):
            self.deletes.append(params)
            return _Rows([])
        raise AssertionError(f"unexpected SQL: {s}")

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def _pick(model_id, side, signal="BET"):
    return {"model_id": model_id, "pick_side": side, "signal_type": signal,
            "game_id": "MLB_2026-08-29_BOS_NYY"}


# ── _locked_live_lanes ────────────────────────────────────────────────────────

def test_locked_lanes_returns_bet_lanes():
    conn = FakeConn(locked=["mlb_live_total_runs"])
    assert _locked_live_lanes(conn, "g1") == {"mlb_live_total_runs"}


def test_locked_lanes_filters_to_model_ids():
    conn = FakeConn(locked=["mlb_live_total_runs", "some_other_model"])
    got = _locked_live_lanes(conn, "g1", ["mlb_live_total_runs", "mlb_live_win_prob"])
    assert got == {"mlb_live_total_runs"}


def test_locked_lanes_empty_when_flag_off(monkeypatch):
    monkeypatch.setattr(scorer_mod, "LOCK_LIVE_PICKS_AT_FIRST_SIGNAL", False)
    conn = FakeConn(locked=["mlb_live_total_runs"])
    assert _locked_live_lanes(conn, "g1") == set()


# ── _write_live_picks (MLB loop) ──────────────────────────────────────────────

# The two-lane tests below patch the registry rather than naming real models.
# The property is per-lane independence — one locked lane must not stop another
# lane being rewritten — which is registry-agnostic, and MLB is down to a single
# live model since mlb_live_win_prob and mlb_live_runline were retired
# (2026-08-30), so the real registry can no longer express it.
_TWO_LANES = {"lane_a": ("MLB", "h2h", "binary", ""),
              "lane_b": ("MLB", "totals", "poisson", "")}


def test_no_lock_deletes_all_lanes_and_writes_all(monkeypatch):
    monkeypatch.setattr(live_mod, "LIVE_MODELS", _TWO_LANES)
    written = []
    monkeypatch.setattr(live_mod, "_insert_picks", lambda c, p: written.extend(p))
    conn = FakeConn()
    picks = [_pick("lane_a", "home"), _pick("lane_b", "over")]
    kept = _write_live_picks(conn, "g1", picks)
    assert kept == picks and written == picks
    deleted_models = {p[1] for p in conn.deletes}
    assert deleted_models == set(_TWO_LANES)


def test_locked_lane_is_never_deleted_or_rewritten(monkeypatch):
    """The motivating bug: a standing live BET must survive the pass — the
    fresh (re-priced) pick for that lane is dropped, and the lane's rows are
    excluded from the delete. The OTHER lane still churns normally."""
    monkeypatch.setattr(live_mod, "LIVE_MODELS", _TWO_LANES)
    written = []
    monkeypatch.setattr(live_mod, "_insert_picks", lambda c, p: written.extend(p))
    conn = FakeConn(locked=["lane_b"])
    fresh = [_pick("lane_b", "over"),          # re-priced — must drop
             _pick("lane_a", "home")]
    kept = _write_live_picks(conn, "g1", fresh)
    assert kept == [fresh[1]] and written == [fresh[1]]
    deleted_models = {p[1] for p in conn.deletes}
    assert "lane_b" not in deleted_models
    assert "lane_a" in deleted_models


def test_the_real_registry_lane_is_deleted_and_rewritten_when_unlocked(monkeypatch):
    """Same property against the live registry as it actually stands."""
    written = []
    monkeypatch.setattr(live_mod, "_insert_picks", lambda c, p: written.extend(p))
    conn = FakeConn()
    picks = [_pick("mlb_live_total_runs", "over")]
    kept = _write_live_picks(conn, "g1", picks)
    assert kept == picks and written == picks
    assert set(LIVE_MODELS.keys()) <= {p[1] for p in conn.deletes}


def test_all_lanes_locked_touches_nothing(monkeypatch):
    written = []
    monkeypatch.setattr(live_mod, "_insert_picks", lambda c, p: written.extend(p))
    conn = FakeConn(locked=list(LIVE_MODELS.keys()))
    kept = _write_live_picks(conn, "g1", [_pick("mlb_live_total_runs", "over")])
    assert kept == [] and written == [] and conn.deletes == []


def test_empty_pass_still_cannot_delete_locked_lane(monkeypatch):
    """A pass that produces NO picks for a locked lane (edge decayed, lane
    closed) must leave the locked row standing."""
    monkeypatch.setattr(live_mod, "_insert_picks",
                        lambda c, p: (_ for _ in ()).throw(AssertionError("no insert")))
    conn = FakeConn(locked=["mlb_live_total_runs"])
    kept = _write_live_picks(conn, "g1", [])
    assert kept == []
    assert "mlb_live_total_runs" not in {p[1] for p in conn.deletes}


def test_flag_off_restores_delete_and_replace(monkeypatch):
    monkeypatch.setattr(scorer_mod, "LOCK_LIVE_PICKS_AT_FIRST_SIGNAL", False)
    written = []
    monkeypatch.setattr(live_mod, "_insert_picks", lambda c, p: written.extend(p))
    conn = FakeConn(locked=["mlb_live_total_runs"])   # a standing BET exists...
    fresh = [_pick("mlb_live_total_runs", "over")]
    kept = _write_live_picks(conn, "g1", fresh)
    assert kept == fresh and written == fresh          # ...but churn wins with flag off
    assert "mlb_live_total_runs" in {p[1] for p in conn.deletes}

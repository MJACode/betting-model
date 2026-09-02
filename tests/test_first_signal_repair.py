"""
A pick is a pick.

Once a model produces a BET at a line and a price, that pick existed. If the
line then moves so the model would no longer take it, that is LINE MOVEMENT --
it does not retract the bet. The number you were given is the number you were
given, and the timing is the point.

The locks enforce that forward. This covers the backward half: where
delete-and-replace ran before a lock existed, restore the first BET out of the
picks_log audit trail so the record and the published signal both show the bet
that was actually made.

The headline test replays the real NCAAF sequence from 2026-08-29, where a live
total given at Over 44.5 -115 was churned to Over 54.5 -120 -- ten points and a
different bet -- and the churned one is what got published.
"""

from __future__ import annotations

import pytest

from tracking import first_signal_repair as fsr


# ── The real sequence, from picks_log ────────────────────────────────────────
_GID = "NCAAF_2026-08-29_north-carolina_tcu"

FIRST = {
    "game_id": _GID, "model_id": "ncaaf_live_total", "sport": "NCAAF",
    "game_date": "2026-08-29", "game_time": "2026-08-29T16:00:00+00:00",
    "pick_side": "over", "pick_label": "North Carolina @ TCU Over 44.5 (live)",
    "model_probability": 0.6559, "dk_implied_prob": 0.5349, "edge": 0.1211,
    "dk_odds": -115.0, "scored_line": 44.5, "kelly_fraction": 0.026027,
    "recommended_bet": 26.03, "bankroll_at_pick": 1000.0,
    "injury_flag": None, "injury_detail": None, "signal_type": "BET",
    "confidence_tier": "MED", "created_at": "2026-08-29 16:14:38.528378+00",
    "logged_at": "2026-08-29 16:14:38.528378+00",
}
CHURNED = {"pick_id": 1409709, "scored_line": 54.5, "dk_odds": -120.0,
           "pick_label": "North Carolina @ TCU Over 54.5 (live)",
           "created_at": "2026-08-29 16:41:12.637404+00"}


class _Conn:
    """Records every statement so the repair's writes can be asserted."""

    def __init__(self, first_bets, standing, siblings=()):
        self._first_bets, self._standing = first_bets, standing
        self._siblings = list(siblings)
        self.statements: list[tuple[str, dict]] = []
        self.committed = False

    def execute(self, sql, params=None):
        self.statements.append((sql, params or {}))
        self._last = sql
        return self

    def fetchall(self):
        if "FROM picks_log" in self._last:
            cols = fsr._COPY_COLS + ("logged_at",)
            src = (self._siblings if "l.pick_side <> " in self._last
                   else self._first_bets)
            return [tuple(b[c] for c in cols) for b in src]
        return []

    def fetchone(self):
        if self._standing is None:
            return None
        s = self._standing
        return (s["pick_id"], s["scored_line"], s["dk_odds"],
                s["pick_label"], s["created_at"])

    def commit(self):
        self.committed = True

    def close(self):
        pass


@pytest.fixture
def patch_conn(monkeypatch):
    def _make(first_bets, standing, siblings=()):
        conn = _Conn(first_bets, standing, siblings)
        monkeypatch.setattr(fsr, "get_connection", lambda: conn)
        return conn
    return _make


def _sql_of(conn, verb, table):
    return [(s, p) for s, p in conn.statements
            if s.strip().upper().startswith(verb) and table in s]


# ── The bug ──────────────────────────────────────────────────────────────────

def test_the_churned_pick_is_replaced_by_the_first_bet(patch_conn):
    """Over 44.5 -115 was the bet. Over 54.5 -120 is a different bet."""
    conn = patch_conn([FIRST], CHURNED)
    assert fsr.restore_first_signals("2026-08-29") == 1

    ins = _sql_of(conn, "INSERT", "picks")
    assert len(ins) == 1
    vals = ins[0][1]
    assert vals["scored_line"] == 44.5
    assert vals["dk_odds"] == -115.0
    assert vals["pick_label"] == "North Carolina @ TCU Over 44.5 (live)"
    assert conn.committed


def test_the_original_timestamp_survives(patch_conn):
    """Timing IS the meaning of a pick. Restoring it under today's clock would
    misreport when the number was available."""
    conn = patch_conn([FIRST], CHURNED)
    fsr.restore_first_signals("2026-08-29")
    vals = _sql_of(conn, "INSERT", "picks")[0][1]
    assert vals["created_at"] == "2026-08-29 16:14:38.528378+00"


def test_a_restored_live_pick_stays_live(patch_conn):
    """picks_log has no is_live column. Without setting it the pick comes back
    as PRE-GAME: invisible to the Live tab and to notify_discord_live, both of
    which filter is_live = TRUE."""
    conn = patch_conn([FIRST], CHURNED)
    fsr.restore_first_signals("2026-08-29")
    assert _sql_of(conn, "INSERT", "picks")[0][1]["is_live"] is True


def test_a_pregame_model_is_not_marked_live(patch_conn):
    conn = patch_conn([{**FIRST, "model_id": "ncaaf_spread"}], CHURNED)
    fsr.restore_first_signals("2026-08-29")
    assert "is_live" not in _sql_of(conn, "INSERT", "picks")[0][1]


def test_the_stale_notification_ledger_is_cleared(patch_conn):
    """The wrong number was already announced; the corrected pick must be able
    to post."""
    conn = patch_conn([FIRST], CHURNED)
    fsr.restore_first_signals("2026-08-29")
    dels = _sql_of(conn, "DELETE", "push_sent")
    assert len(dels) == 1
    assert dels[0][1]["k"] == f"live:{_GID}:ncaaf_live_total:over"


def test_renotify_can_be_suppressed(patch_conn):
    conn = patch_conn([FIRST], CHURNED)
    fsr.restore_first_signals("2026-08-29", renotify=False)
    assert _sql_of(conn, "DELETE", "push_sent") == []


# ── Idempotence: this runs on every loop start ───────────────────────────────

def test_a_lane_already_holding_its_first_bet_is_untouched(patch_conn):
    standing = {**CHURNED, "scored_line": 44.5, "dk_odds": -115.0}
    conn = patch_conn([FIRST], standing)
    assert fsr.restore_first_signals("2026-08-29") == 0
    assert _sql_of(conn, "INSERT", "picks") == []
    assert _sql_of(conn, "DELETE", "picks") == []
    assert not conn.committed


def test_comparison_ignores_pick_id_and_label(patch_conn):
    """pick_id changes on every re-insert and the label merely restates the
    line, so neither can decide whether this is the same bet."""
    standing = {"pick_id": 999999, "scored_line": 44.5, "dk_odds": -115.0,
                "pick_label": "totally different text", "created_at": "x"}
    assert fsr._same_bet(FIRST, standing) is True


def test_a_price_move_alone_is_a_different_bet(patch_conn):
    standing = {**CHURNED, "scored_line": 44.5, "dk_odds": -130.0}
    conn = patch_conn([FIRST], standing)
    assert fsr.restore_first_signals("2026-08-29") == 1


# ── Safety ───────────────────────────────────────────────────────────────────

def test_dry_run_writes_nothing(patch_conn):
    conn = patch_conn([FIRST], CHURNED)
    assert fsr.restore_first_signals("2026-08-29", dry_run=True) == 1
    assert _sql_of(conn, "INSERT", "picks") == []
    assert _sql_of(conn, "DELETE", "picks") == []
    assert not conn.committed


def test_only_unsettled_rows_are_displaced(patch_conn):
    """A graded pick is history and is never rewritten."""
    conn = patch_conn([FIRST], CHURNED)
    fsr.restore_first_signals("2026-08-29")
    sql = _sql_of(conn, "DELETE", "picks")[0][0]
    assert "result IS NULL" in sql


def test_a_lane_with_nothing_standing_is_restored(patch_conn):
    """The Q4 case: the lane closed and the pass erased the pick entirely."""
    conn = patch_conn([FIRST], None)
    assert fsr.restore_first_signals("2026-08-29") == 1
    assert _sql_of(conn, "INSERT", "picks")[0][1]["scored_line"] == 44.5


def test_it_reads_the_earliest_insert(patch_conn):
    """DISTINCT ON must be ordered ASC — DESC would enshrine the churn."""
    conn = patch_conn([FIRST], CHURNED)
    fsr.restore_first_signals("2026-08-29")
    sql = _sql_of(conn, "SELECT", "picks_log")[0][0]
    assert "l.logged_at ASC" in sql
    assert "l.operation = 'INSERT'" in sql
    assert "l.signal_type = 'BET'" in sql


# ── The lane, not just the side ──────────────────────────────────────────────
#
# A totals pass writes BOTH sides together. Restoring only the BET left the
# opposite side stranded at whatever line the churn last wrote, so the board
# read "Over 44.5" beside "Under 54.5" -- two different propositions shown as
# one lane. Observed in production on the 2026-08-29 NCAAF repair.

SIBLING = {**FIRST, "pick_side": "under", "signal_type": "AVOID",
           "pick_label": "North Carolina @ TCU Under 44.5 (live)",
           "model_probability": 0.3441, "edge": -0.1908,
           "kelly_fraction": 0.0, "recommended_bet": 0.0}


def test_the_complementary_side_is_restored_too(patch_conn):
    conn = patch_conn([FIRST], CHURNED, siblings=[SIBLING])
    fsr.restore_first_signals("2026-08-29")
    labels = [p["pick_label"] for _, p in _sql_of(conn, "INSERT", "picks")]
    assert "North Carolina @ TCU Over 44.5 (live)" in labels
    assert "North Carolina @ TCU Under 44.5 (live)" in labels


def test_the_stranded_opposite_side_is_cleared(patch_conn):
    """The churned Under must be deleted, or two lines coexist on one lane."""
    conn = patch_conn([FIRST], CHURNED, siblings=[SIBLING])
    fsr.restore_first_signals("2026-08-29")
    sides = [p.get("s") for _, p in _sql_of(conn, "DELETE", "picks")]
    assert "over" in sides and "under" in sides


def test_the_sibling_keeps_its_own_signal_type(patch_conn):
    conn = patch_conn([FIRST], CHURNED, siblings=[SIBLING])
    fsr.restore_first_signals("2026-08-29")
    by_side = {p["pick_side"]: p for _, p in _sql_of(conn, "INSERT", "picks")}
    assert by_side["over"]["signal_type"] == "BET"
    assert by_side["under"]["signal_type"] == "AVOID"
    assert by_side["under"]["scored_line"] == 44.5


def test_a_lane_with_no_sibling_still_restores(patch_conn):
    conn = patch_conn([FIRST], CHURNED, siblings=[])
    assert fsr.restore_first_signals("2026-08-29") == 1
    assert len(_sql_of(conn, "INSERT", "picks")) == 1

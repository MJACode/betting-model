"""The live channel and the app's Live board select the SAME picks.

CLAUDE.md section 1b: *the app, Discord and push show the same picks -- they are
identical.* The pre-game producers have satisfied that since 2026-09-05 by
selecting `picks` through `model_action_thresholds`. THE LIVE PRODUCERS NEVER
DID: both `discord_notifier._new_live_signals` and
`push_notifier._new_live_signals` took every `is_live` BET row with
`result IS NULL` and no gate at all, while the app's Live board applies
`!isModelPaused && !isModelRetired` (PicksHomeScreen.liveInProgress) and
`queries.fetchLivePicks` excludes `condition_status = 'VOID'` in its own SQL.

MEASURED BEFORE THE FIX (2026-09-12, production). Every live BET ever written
by a model that is paused today had a `discord_live` ledger row -- 60 of 60 for
`ncaaf_live_total`, 6 of 6 for `ncaaf_live_win_prob` -- and the two RETIRED MLB
live models (`mlb_live_win_prob`, `mlb_live_runline`, no
`model_action_thresholds` row at all since the threshold_sync prune) had 2 of 7
each. The reason nothing is visibly wrong on the board TODAY is that both NCAAF
lanes suppress the BET at source (`ncaaf_live.serve._unless_paused`) -- i.e. the
publisher was relying on the scorer's gate, one layer away, for a rule the app
enforces itself.

These run the REAL producers' REAL SQL against sqlite. A fixture cannot catch
this class of bug: the thing under test IS the WHERE clause, so a hand-built
row list would only re-assert what the test author already believed.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import discord_notifier, push_notifier


class _Conn:
    """sqlite behind the psycopg surface the producers use: %s -> ?, %% -> %."""

    def __init__(self, raw: sqlite3.Connection):
        self._raw = raw

    def execute(self, sql, params=()):
        return self._raw.execute(sql.replace("%%", "%").replace("%s", "?"), params)


PICKS_COLS = """
    pick_id INTEGER PRIMARY KEY, game_id TEXT, model_id TEXT, sport TEXT,
    game_date TEXT, pick_side TEXT, pick_label TEXT, signal_type TEXT,
    model_probability REAL, edge REAL, dk_odds REAL, kelly_fraction REAL,
    inning_at_pick TEXT, dk_bet_link TEXT, created_at TEXT, is_live INTEGER,
    result TEXT, condition_status TEXT, player_id TEXT, player_key TEXT,
    prop_market TEXT, best_book TEXT, best_odds REAL, best_bet_link TEXT,
    decision_odds REAL, decision_book TEXT, scored_line REAL
"""


def _db() -> _Conn:
    raw = sqlite3.connect(":memory:")
    raw.executescript(f"""
        CREATE TABLE picks ({PICKS_COLS});
        CREATE TABLE games (game_id TEXT, home_team TEXT, away_team TEXT,
                            commence_time TEXT);
        CREATE TABLE push_sent (lock_key TEXT, kind TEXT, sent_at TEXT,
                                message_id TEXT);
        CREATE TABLE model_action_thresholds (
            model_id TEXT PRIMARY KEY, min_prob REAL, min_edge REAL,
            min_odds REAL, paused INTEGER, prob_only INTEGER);
    """)
    return _Conn(raw)


def _pick(conn, pick_id, model_id, *, condition_status=None, label=None):
    conn.execute(
        "INSERT INTO picks (pick_id, game_id, model_id, sport, game_date, "
        "pick_side, pick_label, signal_type, model_probability, edge, dk_odds, "
        "kelly_fraction, created_at, is_live, result, condition_status) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (pick_id, f"G{pick_id}", model_id, "NCAAF", "2026-09-12", "over",
         label or f"{model_id} pick {pick_id}", "BET", 0.80, 0.20, -110, 0.02,
         "2026-09-12T18:00:00-04:00", 1, None, condition_status),
    )


def _threshold(conn, model_id, paused):
    conn.execute(
        "INSERT INTO model_action_thresholds (model_id, min_prob, min_edge, "
        "min_odds, paused, prob_only) VALUES (?,?,?,?,?,?)",
        (model_id, 0.60, 0.10, -200.0, 1 if paused else 0, 0),
    )


PRODUCERS = [
    pytest.param(discord_notifier._new_live_signals, id="discord"),
    pytest.param(push_notifier._new_live_signals, id="push"),
]


def _labels(rows):
    return sorted(r["label"] for r in rows)


@pytest.mark.parametrize("producer", PRODUCERS)
def test_an_unpaused_live_model_still_publishes(producer):
    """The control. Without this every assertion below passes on a producer
    that returns nothing at all, which is the shape of 'fixed' that breaks the
    channel."""
    conn = _db()
    _threshold(conn, "ncaaf_live_total", paused=False)
    _pick(conn, 1, "ncaaf_live_total", label="live and bettable")
    assert _labels(producer(conn, "2026-09-12")) == ["live and bettable"]


@pytest.mark.parametrize("producer", PRODUCERS)
def test_a_paused_model_is_not_announced(producer):
    """The NCAAF case mike paused on 2026-09-11. The app stopped drawing these
    the moment `model_action_thresholds.paused` flipped; the channel did not."""
    conn = _db()
    _threshold(conn, "ncaaf_live_total", paused=True)
    _pick(conn, 1, "ncaaf_live_total")
    assert producer(conn, "2026-09-12") == []


@pytest.mark.parametrize("producer", PRODUCERS)
def test_a_retired_model_is_not_announced(producer):
    """A retired model has NO threshold row -- data.threshold_sync prunes to
    config.ACTION_THRESHOLDS and a retired model is out of it. That absence is
    the app's `isModelRetired`, so it has to be a gate here and not a join that
    tolerates a missing row."""
    conn = _db()
    _pick(conn, 1, "mlb_live_win_prob")     # retired 2026-08-30, no row
    assert producer(conn, "2026-09-12") == []


@pytest.mark.parametrize("producer", PRODUCERS)
def test_a_voided_live_pick_is_not_announced(producer):
    """Section 1c: a pick the model should never have PRODUCED is voided, not
    deleted -- and a voided pick is not publishable. fetchLivePicks already
    excludes it in the app's SQL."""
    conn = _db()
    _threshold(conn, "ncaaf_live_total", paused=False)
    _pick(conn, 1, "ncaaf_live_total", condition_status="VOID")
    assert producer(conn, "2026-09-12") == []


@pytest.mark.parametrize("producer", PRODUCERS)
def test_a_live_health_state_still_publishes(producer):
    """ONLY 'VOID'. scripts/nfl_pick_monitor.py writes 'OK' / 'DEGRADED' /
    'GONE' in the same column as health states on real, standing picks."""
    conn = _db()
    _threshold(conn, "ncaaf_live_total", paused=False)
    _pick(conn, 1, "ncaaf_live_total", condition_status="GONE", label="degraded but real")
    assert _labels(producer(conn, "2026-09-12")) == ["degraded but real"]


@pytest.mark.parametrize("producer", PRODUCERS)
def test_the_cut_itself_is_not_applied(producer):
    """The gates stop at 'not stakeable at all'. min_prob / min_edge / min_odds
    are deliberately NOT applied -- the app's Live board does not apply them
    either, because nfl_live_prop's cut is EV and lives server-side. Filtering
    on the prob/edge row here would lose picks the app shows, which is the same
    fault with the sign flipped."""
    conn = _db()
    _threshold(conn, "ncaaf_live_total", paused=False)
    conn.execute(
        "UPDATE model_action_thresholds SET min_prob = 0.99, min_edge = 0.99, "
        "min_odds = 100 WHERE model_id = 'ncaaf_live_total'")
    _pick(conn, 1, "ncaaf_live_total", label="below the pre-game cut")
    assert _labels(producer(conn, "2026-09-12")) == ["below the pre-game cut"]

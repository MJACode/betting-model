"""
Pure-function tests for the Phase 3/4 live decision logic:
trigger routing, fetch debounce, credit cap, and live signal classification.
"""

import types
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.live_trigger_orchestrator import (
    should_fetch,
    split_triggers,
    under_credit_cap,
)
from models.live_scorer import classify_live_signal


def _t(tid, game, ttype):
    return {"trigger_id": tid, "game_id": game, "trigger_type": ttype,
            "fired_at": "2026-06-13T00:00:00+00:00"}


# ── split_triggers ────────────────────────────────────────────────────────────

def test_split_triggers_routes_fg_tiers():
    pending = [
        _t(1, "MLB_2026-06-13_NYY_BOS", "inning_change"),
        _t(2, "MLB_2026-06-13_NYY_BOS", "score_change"),
        _t(3, "MLB_2026-06-13_LAD_SF",  "pitching_change"),
        _t(4, "MLB_2026-06-13_LAD_SF",  "due_up_change"),
    ]
    fg_games, ids = split_triggers(pending)
    assert fg_games == {"MLB_2026-06-13_NYY_BOS"}
    # ALL triggers are consumed, including the no-op tiers
    assert ids == [1, 2, 3, 4]


def test_split_triggers_unknown_type_is_noop():
    fg_games, ids = split_triggers([_t(9, "g1", "weather_delay")])
    assert fg_games == set()
    assert ids == [9]


def test_split_triggers_empty():
    assert split_triggers([]) == (set(), [])


# ── should_fetch (debounce) ───────────────────────────────────────────────────

def test_should_fetch_never_fetched():
    assert should_fetch(None, debounce_sec=60) is True


def test_should_fetch_inside_window():
    assert should_fetch(30, debounce_sec=60) is False


def test_should_fetch_window_elapsed():
    assert should_fetch(60, debounce_sec=60) is True
    assert should_fetch(300, debounce_sec=60) is True


# ── under_credit_cap ──────────────────────────────────────────────────────────

def test_credit_cap_uncapped():
    assert under_credit_cap(10_000, 3, cap=0) is True


def test_credit_cap_enforced():
    assert under_credit_cap(98, 3, cap=100) is False
    assert under_credit_cap(97, 3, cap=100) is True


# ── classify_live_signal ──────────────────────────────────────────────────────
# mlb_live_total_runs is the LIVE one (0.68 / 0.14 since 2026-08-29); the two
# binary live models are paused, which the last test here pins.
_M = "mlb_live_total_runs"


def test_live_signal_bet():
    assert classify_live_signal(_M, 0.70, 0.15) == "BET"


def test_live_signal_requires_prob_floor():
    assert classify_live_signal(_M, 0.60, 0.15) is None


def test_live_signal_avoid():
    assert classify_live_signal(_M, 0.30, -0.15) == "AVOID"


def test_live_signal_dead_zone_not_written():
    assert classify_live_signal(_M, 0.70, 0.05) is None


def test_live_signal_noise_cap():
    # Edges beyond MAX_EDGE_CAP (0.20) are model noise — never written
    assert classify_live_signal(_M, 0.95, 0.45) is None


def test_a_paused_live_model_scores_but_never_bets():
    """The two binary live models lose at every cut (win_prob 6-9, runline 5-9)
    and get WORSE as the probability floor rises. They keep scoring so the
    forward record accrues, written as NONE so nothing actionable surfaces."""
    import config
    for m in ("mlb_live_win_prob", "mlb_live_runline"):
        assert m in config.PAUSED_MODELS
        assert classify_live_signal(m, 0.80, 0.15) == "NONE"
        # a fade is still recorded as a fade
        assert classify_live_signal(m, 0.20, -0.15) == "AVOID"


def test_the_one_live_model_left_is_the_profitable_one():
    import config
    live = {m for m in config.LIVE_MODELS if m.startswith("mlb_")}
    unpaused = live - config.PAUSED_MODELS
    assert unpaused == {"mlb_live_total_runs"}


# ── the floor fetch (2026-08-29) ────────────────────────────────────────────
#
# consume_triggers_once used to `return` the moment no trigger was pending, so
# the in-play line refreshed ONLY on an inning or score change. Measured that
# day: DK in-play snapshots averaged 269s apart, max 1,020s, against a 300s
# staleness bound -- so the loop routinely priced a live total minutes old and
# published it as a takeable number. A live total moves on every baserunner,
# not only on runs and half-innings, so the trigger set was a strict subset of
# the events that move the line.

import ast
import inspect
from pathlib import Path

_ORCH = Path(__file__).parent.parent / "data/ingestors/live_trigger_orchestrator.py"


def _consume_source() -> str:
    """RAW source of consume_triggers_once. Deliberately not ast.unparse():
    that normalises formatting, so an assertion on the actual line the reader
    sees would silently never match."""
    text = _ORCH.read_text()
    tree = ast.parse(text)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "consume_triggers_once")
    lines = text.splitlines()
    return "\n".join(lines[fn.lineno - 1:fn.end_lineno])


def test_no_pending_triggers_no_longer_short_circuits_unconditionally():
    """The bug: `if not pending: return` meant no trigger, no fetch, ever."""
    src = _consume_source()
    assert "if not pending and not floor_due:" in src, (
        "the early return must also consider whether a floor fetch is due")
    assert "if not pending:\n            return summary" not in src


def test_the_floor_is_gated_on_a_game_actually_being_live():
    """Without the gate the loop would buy odds every 60s all day with nothing
    in progress."""
    src = _consume_source()
    assert "live_now = _live_game_ids(conn)" in src
    assert "floor_due = bool(live_now) and should_fetch(" in src


def test_a_floor_pass_scores_every_live_game_not_just_triggered_ones():
    """A line that moved without an inning or score change is precisely the
    case the trigger set could not see, so a floor pass must not narrow to a
    (possibly empty) trigger set."""
    src = _consume_source()
    assert "target = (fg_games | live_now) if fg_games else None" in src
    assert "game_ids=target" in src
    assert "run_live_scorer(game_ids=target" in src


def test_the_staleness_bound_is_tighter_than_the_feeds_own_refresh():
    """300s was looser than the measured 269s average gap, so it could never
    bite. It must now be short enough that a stale line is declined, and long
    enough that one missed floor fetch does not."""
    import config
    assert config.LIVE_ODDS_MAX_AGE_SEC <= 180, (
        "an in-play total this old is not a price you can take")
    assert config.LIVE_ODDS_MAX_AGE_SEC >= 2 * config.LIVE_FG_DEBOUNCE_SEC, (
        "one missed floor fetch would start declining every live pick")


def test_the_credit_cap_can_absorb_the_floor_fetch():
    """1000 was sized for trigger-only fetching. A 60s floor over a 10-hour
    slate is ~1,800 credits, so the old cap would have bound by mid-afternoon
    and silently stopped the refresh -- the exact failure the floor prevents."""
    import config
    from data.ingestors.live_odds_ingestor import LIVE_FG_MARKETS, _credit_cost
    slate_hours = 10
    fetches = slate_hours * 3600 / config.LIVE_FG_DEBOUNCE_SEC
    needed = fetches * _credit_cost(LIVE_FG_MARKETS)
    assert config.LIVE_DAILY_CREDIT_CAP == 0 or \
        config.LIVE_DAILY_CREDIT_CAP >= needed, (
            f"cap {config.LIVE_DAILY_CREDIT_CAP} < {needed:.0f} needed for a "
            f"{slate_hours}h slate at a {config.LIVE_FG_DEBOUNCE_SEC}s floor")


def test_live_game_ids_takes_the_newest_state_and_only_live_ones():
    from data.ingestors.live_trigger_orchestrator import _live_game_ids

    class _Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            return types.SimpleNamespace(fetchall=lambda: [
                ("MLB_a", "Live"), ("MLB_b", "Final"), ("MLB_c", "Preview")])

    conn = _Conn()
    assert _live_game_ids(conn) == {"MLB_a"}
    assert "DISTINCT ON (game_id)" in conn.sql
    assert "ORDER BY game_id, snapshot_at DESC" in conn.sql
    assert "snapshot_at >= %s" in conn.sql, "stale states must be excluded"

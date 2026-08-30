"""
Pure-function tests for the Phase 3/4 live decision logic:
trigger routing, fetch debounce, credit cap, and live signal classification.
"""

import pytest
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
# mlb_live_total_runs is the ONLY live MLB model (0.68 / 0.14 since 2026-08-29);
# the two binary ones were paused 2026-08-29 and RETIRED 2026-08-30, which the
# last test here pins.
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


def test_the_two_binary_live_models_are_retired():
    """RETIRED 2026-08-30. They lose at every cut (win_prob 15 bets 6-9 -34.1%,
    runline 14 bets 5-9 -39.9%) and get WORSE as the probability floor rises —
    an overconfidence failure a threshold cannot fix, so there was nothing a
    pause could learn. Gone from the registry AND from every threshold dict, so
    no code path can price them and no stale cut can quietly revive one."""
    import config
    for m in ("mlb_live_win_prob", "mlb_live_runline"):
        assert m not in config.LIVE_MODELS
        assert m not in config.PAUSED_MODELS      # nothing left to pause
        assert m not in config.ACTION_THRESHOLDS
        assert m not in config.MODEL_PROB_THRESHOLDS
        assert m not in config.MODEL_EDGE_THRESHOLDS


def test_the_one_live_mlb_model_left_is_the_profitable_one():
    import config
    live = {m for m in config.LIVE_MODELS if m.startswith("mlb_")}
    assert live - config.PAUSED_MODELS == {"mlb_live_total_runs"}


def test_retired_live_picks_still_settle_on_their_own_market():
    """Their picks stay in the DB and keep grading (§1c: a pick that existed is
    the bet of record). Without the retired-market map both fall through to the
    'h2h' default, and a runline pick graded as a moneyline turns a failed -1.5
    cover into a win."""
    from tracking.paper_tracker import _market_for_pick
    assert _market_for_pick("mlb_live_win_prob") == "h2h"
    assert _market_for_pick("mlb_live_runline") == "spreads"
    assert _market_for_pick("mlb_live_total_runs") == "totals"


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
    assert "target = fg_games | live_now" in src
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


def test_the_fetch_is_never_asked_for_every_event_the_feed_returns():
    """game_ids=None means "keep every event", and the bulk in-play feed carries
    TOMORROW's games -- which have no `games` row, so the odds insert dies on
    the FK and takes the loop down. Seen in production on the first pass after
    the floor fetch shipped (MLB_2026-08-30_MIA_WSH)."""
    src = _consume_source()
    assert "target = fg_games | live_now" in src
    # Code only -- the comment above the fix names the thing it forbids.
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "game_ids=None" not in code
    assert "if fg_games else None" not in code, (
        "a floor pass must target the live games, not every event")


# ── EV floor and the daily cap (2026-08-29, mike) ───────────────────────────

def test_ev_is_the_payout_aware_number_edge_is_not():
    """Two picks with the same edge are not the same bet: at -200 you risk twice
    as much for the same return. That is the whole reason to cut on EV."""
    from models.live_scorer import expected_value
    assert expected_value(0.75, -110) == pytest.approx(0.4318, abs=1e-3)
    assert expected_value(0.75, -200) == pytest.approx(0.125, abs=1e-3)
    assert expected_value(0.50, 100) == pytest.approx(0.0, abs=1e-9)


def test_ev_is_unmeasurable_without_a_price():
    """None, never a -110 assumption -- a prob-only pick has no EV."""
    from models.live_scorer import expected_value
    assert expected_value(0.75, None) is None
    assert expected_value(0.75, 0) is None
    assert expected_value(0.75, "n/a") is None


def test_the_ev_floor_only_tightens():
    """Applied after prob/edge, so it can turn a BET away but never create one."""
    import config
    from models.live_scorer import classify_live_signal
    m = "mlb_live_total_runs"
    # The floor is a SWEPT number and moves; pin that one exists and that it
    # is inside the range the sweep can actually see, not its current value.
    assert 0.0 < config.MODEL_MIN_EV[m] < 0.40
    # clears prob/edge AND the floor
    assert classify_live_signal(m, 0.75, 0.16, -110) == "BET"
    # clears prob/edge, fails the floor (heavy juice eats the return)
    assert classify_live_signal(m, 0.72, 0.16, -300) == "NONE"
    # fails prob/edge -- floor never consulted
    assert classify_live_signal(m, 0.60, 0.16, -110) is None


def test_a_model_with_no_floor_is_unaffected():
    from models.live_scorer import classify_live_signal
    assert classify_live_signal("some_other_live_model", 0.75, 0.16, -300) == "BET"


def test_the_daily_cap_turns_later_signals_into_none():
    """A threshold is a hope about volume; a cap is a guarantee. The cut
    measured at ~1 signal/day produced six on a heavy slate."""
    from models.live_scorer import apply_daily_cap
    m = "mlb_live_total_runs"
    picks = [{"model_id": m, "signal_type": "BET", "kelly_fraction": 0.02,
              "recommended_bet": 20.0} for _ in range(3)]
    out = apply_daily_cap(picks, {}, {m: 1})
    assert [p["signal_type"] for p in out] == ["BET", "NONE", "NONE"]
    # a turned-away signal is not a bet: no stake rides on it
    assert out[1]["kelly_fraction"] == 0.0 and out[1]["recommended_bet"] == 0.0


def test_the_cap_counts_signals_already_standing_today():
    """The allowance is for the DAY, not for the pass."""
    from models.live_scorer import apply_daily_cap
    m = "mlb_live_total_runs"
    picks = [{"model_id": m, "signal_type": "BET", "kelly_fraction": 0.02,
              "recommended_bet": 20.0}]
    assert apply_daily_cap(picks, {m: 1}, {m: 1})[0]["signal_type"] == "NONE"
    assert apply_daily_cap(picks, {m: 0}, {m: 1})[0]["signal_type"] == "BET"


def test_the_cap_never_touches_avoids_or_uncapped_models():
    from models.live_scorer import apply_daily_cap
    m = "mlb_live_total_runs"
    rows = [{"model_id": m, "signal_type": "AVOID", "kelly_fraction": 0.0,
             "recommended_bet": 0.0},
            {"model_id": "other", "signal_type": "BET", "kelly_fraction": 0.02,
             "recommended_bet": 20.0}]
    out = apply_daily_cap(rows, {m: 5, "other": 99}, {m: 1})
    assert [p["signal_type"] for p in out] == ["AVOID", "BET"]


def test_apply_daily_cap_does_not_mutate_its_input():
    from models.live_scorer import apply_daily_cap
    m = "mlb_live_total_runs"
    picks = [{"model_id": m, "signal_type": "BET", "kelly_fraction": 0.02,
              "recommended_bet": 20.0}]
    apply_daily_cap(picks, {m: 1}, {m: 1})
    assert picks[0]["signal_type"] == "BET"


def test_the_live_edge_cap_is_separate_from_the_pregame_one():
    """They guard different things and must not share a constant.

    A pre-game price is stable for hours, so a huge edge there is a model claim.
    A live price is at most ~45s old BY CONSTRUCTION (The Odds API serves one
    cached in-play snapshot for ~44-46s, and its bulk and per-event endpoints
    return that identical cache), so a huge edge against a live line is usually
    evidence that our snapshot is behind the book. Sharing one constant means a
    future live tightening silently moves the pre-game cut too."""
    import config
    from models import live_scorer
    src = Path(live_scorer.__file__).read_text()
    body = src.split("def classify_live_signal", 1)[1]
    assert "LIVE_MAX_EDGE_CAP" in body, (
        "the live cap must be read from the live constant, not the pre-game one")
    assert isinstance(config.LIVE_MAX_EDGE_CAP, float)
    m = "mlb_live_total_runs"
    cap = config.LIVE_MAX_EDGE_CAP
    assert live_scorer.classify_live_signal(m, 0.95, cap + 0.01, -110) is None
    assert live_scorer.classify_live_signal(m, 0.80, cap - 0.01, -110) == "BET"

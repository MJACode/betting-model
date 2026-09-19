"""
The book moved and our state did not. That is information we do not have.

THE INCIDENT THIS PINS (2026-09-19, Coastal Carolina at Delaware,
`ncaaf_live_win_prob`), from the in-play quotes stored in `odds` and the
poller's own log:

    15:41:51Z  DraftKings live: Delaware -174, spread Delaware -3.5
    15:43:32Z  FanDuel flips to Delaware +102 / Coastal -130
    15:44:21Z  DraftKings re-hangs: Delaware +100, spread Delaware +2.5
               (a six-point spread swing -- a touchdown)
    15:44:29   the loop WRITES BET Delaware ML +100, model 0.659, on a state
               that still says 0-0 in the first quarter
    15:44:44   our score feed (CFBD) reports the score -- 15s after the bet,
               23s after DraftKings moved, 72s after FanDuel
    15:44:44+  the loop's own guard now refuses the exact quote it just bet on:
               "quote predates the score we have already seen"

Every existing guard passed, and none was wrong to: the quote was 8s old
(cap 90), the edge was 0.159 (cap 0.18), and the quote-vs-score guard can only
fire once WE have seen a score. All three protect against the book being
behind us. Nothing protected against us being behind the book -- which is the
common case, because the book prices the play from a courtside feed and we
read a scoreboard endpoint every five seconds.

The model's 0.659 was the pregame prior carried into a tied first quarter.
The "edge" was a touchdown our feed had not reported. The same shape sat
behind 15 of the 20 live moneyline bets since the 2026-09-12 unpause: in
each, DraftKings had moved against the side we then bet inside the two
minutes before the bet.

The guard: if the book's own number has moved more than a cap since OUR
state last changed, our state is stale, and the quote is declined until the
state feed catches up. It is the mirror of `quote_predates_score`, which
declines a quote stamped before a score we HAVE seen.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.live_quote_guard import (  # noqa: E402
    BookMoveClock, american_to_implied)

T0 = datetime(2026, 9, 19, 15, 41, 51, tzinfo=timezone.utc)


def _at(sec: float) -> datetime:
    return T0 + timedelta(seconds=sec)


def _iso(sec: float) -> str:
    return _at(sec).isoformat().replace("+00:00", "Z")


TIED = (0, 0, 1, "away")          # score, period, possession: unchanged 15:41-15:44
COASTAL_UP = (0, 7, 1, "home")


# ── the shared clock ─────────────────────────────────────────────────────────

def test_the_delaware_re_hang_is_declined_on_a_tied_state():
    """The fix. Three DraftKings publishes on the same 0-0 state; the third
    is the post-touchdown number. -174 -> +100 is a 13.5-point implied move
    against a state that has not changed, so the state is the stale thing."""
    clock = BookMoveClock()
    key = ("NCAAF_2026-09-19_coastal-carolina_delaware", "h2h")
    assert clock.observe(key, TIED, american_to_implied(-174), _iso(0), _at(3)) is None
    assert clock.observe(key, TIED, american_to_implied(-167), _iso(49), _at(52)) == pytest.approx(0.0097, abs=5e-4)
    move = clock.observe(key, TIED, american_to_implied(100), _iso(150), _at(158))
    assert move == pytest.approx(0.1350, abs=5e-4)
    assert move > 0.05                      # NCAAF moneyline cap


def test_first_sight_has_nothing_to_compare_against():
    """Same rule as ScoreClock: a game seen for the first time (or after a
    restart) records its number and reports no move. The age bound still
    applies throughout, so this is a floor, not a hole."""
    clock = BookMoveClock()
    assert clock.observe("g", TIED, 0.5, _iso(0), _at(0)) is None


def test_ordinary_drift_reads_as_the_small_number_it_is():
    clock = BookMoveClock()
    clock.observe("g", TIED, 0.635, _iso(0), _at(0))
    assert clock.observe("g", TIED, 0.640, _iso(30), _at(30)) == pytest.approx(0.005)


def test_a_state_change_re_anchors_only_on_a_quote_that_postdates_it():
    """Self-clearing, in the right order. When the score lands the old
    anchor is gone; a quote stamped BEFORE the score is not a baseline (the
    quote-vs-score guard is declining it anyway), a quote stamped after is."""
    clock = BookMoveClock()
    key = "g"
    clock.observe(key, TIED, american_to_implied(-174), _iso(0), _at(3))
    clock.observe(key, TIED, american_to_implied(100), _iso(150), _at(158))
    # 15:44:44 -- our feed sees 0-7. The 15:44:21 quote predates that.
    assert clock.observe(key, COASTAL_UP, american_to_implied(100),
                         _iso(150), _at(173)) is None
    assert clock.observe(key, COASTAL_UP, american_to_implied(100),
                         _iso(150), _at(178)) is None      # still waiting
    # 15:45:09 -- DraftKings publishes after the score: this is the baseline.
    assert clock.observe(key, COASTAL_UP, american_to_implied(100),
                         _iso(198), _at(200)) is None
    assert clock.observe(key, COASTAL_UP, american_to_implied(110),
                         _iso(301), _at(302)) == pytest.approx(0.0238, abs=5e-4)


def test_a_quote_with_no_timestamp_re_anchors_at_once():
    """Unknown is not stale (parse_book_ts contract): a feed that drops the
    publish time must degrade to the previous behaviour, not blank the board."""
    clock = BookMoveClock()
    clock.observe("g", TIED, 0.60, None, _at(0))
    assert clock.observe("g", COASTAL_UP, 0.40, None, _at(60)) is None
    assert clock.observe("g", COASTAL_UP, 0.41, None, _at(90)) == pytest.approx(0.01)


def test_a_none_inside_the_state_still_anchors():
    """The CFBD scoreboard's possession parses defensively and can be None
    for a whole game. A clock that refused to anchor on that would be dead
    for exactly the games it exists for -- the one that bet Delaware."""
    clock = BookMoveClock()
    no_poss = (0, 0, 1, None)
    assert clock.observe("g", no_poss, american_to_implied(-174), _iso(0), _at(3)) is None
    move = clock.observe("g", no_poss, american_to_implied(100), _iso(150), _at(158))
    assert move == pytest.approx(0.1350, abs=5e-4)


def test_the_production_anchor_range_all_fires():
    """The loop had priced this game since 15:34:39, and every DraftKings
    publish from 15:34:22 to 15:42:40 sat between -167 and -217. Whichever of
    them was the anchor, the re-hang to +100 clears the 0.08 cap."""
    for price in (-211, -196, -217, -209, -182, -196, -174, -167):
        clock = BookMoveClock()
        clock.observe("g", TIED, american_to_implied(price), _iso(0), _at(1))
        move = clock.observe("g", TIED, american_to_implied(100), _iso(150), _at(158))
        assert move > 0.05, price


def test_a_blank_possession_is_not_a_state_change():
    """North Texas at Texas State, 2026-09-19, the first slate the guard ran.
    CFBD blanks possession around a scoring play; the blank read as a state
    change, the anchor was dropped, the post-touchdown -129 became the new
    baseline and the loop bet Texas State 44s before the feed reported the
    score. A field the feed stops reporting keeps its last value."""
    clock = BookMoveClock()
    key = ("NCAAF_2026-09-19_north-texas_texas-state", "h2h")
    up7_away = (28, 21, 2, "away")            # 17:37:51 our feed
    up7_blank = (28, 21, 2, None)             # 17:38:55 our feed
    clock.observe(key, up7_away, american_to_implied(-213), _iso(0), _at(1))     # 17:38:13 DK
    move = clock.observe(key, up7_blank, american_to_implied(-129), _iso(49), _at(56))  # 17:39:02 DK
    assert move == pytest.approx(abs(american_to_implied(-129)
                                     - american_to_implied(-213)), abs=1e-6)
    assert move > 0.05                        # NCAAF moneyline cap, declined


def test_a_blank_that_is_later_filled_is_still_not_a_change():
    clock = BookMoveClock()
    clock.observe("g", (28, 21, 2, "away"), 0.68, _iso(0), _at(1))
    clock.observe("g", (28, 21, 2, None), 0.68, _iso(30), _at(31))
    assert clock.observe("g", (28, 21, 2, "away"), 0.69, _iso(60), _at(61)) == pytest.approx(0.01)


def test_the_clemson_move_clears_the_tightened_cap():
    """North Carolina at Clemson, 16:12Z, before the guard deployed:
    DraftKings -143 -> -116 -> -105 on a 0-0 state, bet at -105, +108
    forty-five seconds later. 0.076 implied -- under the original 0.08 cap."""
    from ncaaf_live.config import LIVE_BOOK_MOVE_MAX_ML
    clock = BookMoveClock()
    clock.observe("g", TIED, american_to_implied(-143), _iso(0), _at(1))
    clock.observe("g", TIED, american_to_implied(-116), _iso(102), _at(103))
    move = clock.observe("g", TIED, american_to_implied(-105), _iso(156), _at(157))
    assert move == pytest.approx(0.076, abs=1e-3)
    assert move > LIVE_BOOK_MOVE_MAX_ML


def test_a_missing_number_or_state_is_ignored_not_recorded():
    clock = BookMoveClock()
    clock.observe("g", TIED, 0.60, _iso(0), _at(0))
    assert clock.observe("g", None, 0.10, _iso(5), _at(5)) is None
    assert clock.observe("g", TIED, None, _iso(5), _at(5)) is None
    assert clock.observe("g", TIED, 0.61, _iso(9), _at(9)) == pytest.approx(0.01)


def test_games_and_markets_are_tracked_independently():
    clock = BookMoveClock()
    clock.observe(("g", "h2h"), TIED, 0.60, _iso(0), _at(0))
    clock.observe(("g", "total"), TIED, 56.5, _iso(0), _at(0))
    assert clock.observe(("g", "total"), TIED, 57.5, _iso(20), _at(20)) == pytest.approx(1.0)
    assert clock.observe(("g", "h2h"), TIED, 0.60, _iso(20), _at(20)) == pytest.approx(0.0)


def test_american_to_implied():
    assert american_to_implied(100) == pytest.approx(0.5)
    assert american_to_implied(-174) == pytest.approx(0.635, abs=5e-4)
    assert american_to_implied(157) == pytest.approx(0.389, abs=5e-4)
    assert american_to_implied(None) is None
    assert american_to_implied("x") is None


# ── NCAAF: the loop that bet Delaware ────────────────────────────────────────

def _ncaaf_engine():
    from ncaaf_live.serve import LiveEngine
    try:
        return LiveEngine()
    except FileNotFoundError:
        pytest.skip("engine artifacts not trained in this checkout")


def _delaware_ctx():
    from ncaaf_live.serve import GameContext
    return GameContext(game_id="NCAAF_2026-09-19_coastal-carolina_delaware",
                       home="Delaware", away="Coastal Carolina",
                       commence_time="2026-09-19T15:30:00Z",
                       pregame_spread=-5.5, pregame_total=56.5,
                       wind_mph=4.0, is_dome=False, game_date="2026-09-19",
                       fbs_matchup=True)


def _tied_q1(**kw):
    """The CFBD scoreboard shape the worker prices from: no drive log, so the
    pace and pass-rate fields are absent and route as NaN. At 10:20 left in
    the first quarter this gives 0.659 for Delaware -- production's 0.6594."""
    base = dict(period=1, clock_seconds=620, home_score=0, away_score=0,
                possession="away", down=2, distance=6, yardline_100=40,
                home_timeouts=3, away_timeouts=3, state="in",
                state_name="STATUS_IN_PROGRESS")
    base.update(kw)
    return base


def _dk(home_price: int, away_price: int, sec: float) -> dict:
    return {"h2h": {"home": home_price, "away": away_price, "ts": _iso(sec)}}


def _the_days_cut(monkeypatch):
    """The cut production ran on 2026-09-19 afternoon (0.65 / edge 0.10),
    when Delaware fired: the re-sweep that evening moved ncaaf_live_win_prob
    to 0.50 / 0.16 (a plus-money-dog cell), under which this +100 favourite
    fixture is one edge point short and the control would go dark for a
    reason that has nothing to do with the guard."""
    from ncaaf_live import serve
    monkeypatch.setattr(serve, "ML_MIN_PROB", 0.65)
    monkeypatch.setattr(serve, "ML_MIN_EDGE", 0.10)


def test_the_ncaaf_loop_no_longer_bets_the_delaware_re_hang(monkeypatch):
    _the_days_cut(monkeypatch)
    engine = _ncaaf_engine()
    ctx, state = _delaware_ctx(), _tied_q1()
    # Two passes on the pre-touchdown number, then the post-touchdown one,
    # all with the state feed still reporting 0-0.
    engine.price(state, ctx, _dk(-174, 131, 0), now=_at(3))
    engine.price(state, ctx, _dk(-167, 126, 49), now=_at(52))
    picks = engine.price(state, ctx, _dk(100, -133, 150), now=_at(158))
    assert [p for p in picks if p["signal_type"] == "BET"] == []


def test_the_control_a_settled_board_still_bets_the_number(monkeypatch):
    """If this stops betting, the test above proves nothing. The same +100
    and the same 0-0 state, but held still for longer than the settled
    window: no anchor move, nothing recent, so only the cuts decide -- and
    they clear, as they did in production. (Production was NOT at first
    sight: it had watched the game since 15:34 and every DraftKings publish
    before the re-hang sat at -167..-217, so the cap fires on the real
    timeline whichever of them was the anchor.)"""
    from ncaaf_live.config import LIVE_SETTLED_SEC
    _the_days_cut(monkeypatch)
    engine = _ncaaf_engine()
    ctx, state = _delaware_ctx(), _tied_q1()
    engine.price(state, ctx, _dk(100, -133, 0), now=_at(1))
    # Republished (so the 90s age bound passes) at the SAME number.
    picks = engine.price(state, ctx, _dk(100, -133, LIVE_SETTLED_SEC),
                         now=_at(LIVE_SETTLED_SEC + 5))
    assert any(p["model_id"] == "ncaaf_live_win_prob"
               and p["signal_type"] == "BET" for p in picks)


def test_first_sight_is_not_settled():
    """A restart waits a window rather than betting blind."""
    engine = _ncaaf_engine()
    picks = engine.price(_tied_q1(), _delaware_ctx(), _dk(100, -133, 0),
                         now=_at(1))
    assert [p for p in picks if p["signal_type"] == "BET"] == []


def test_the_settled_clock_resets_on_a_book_move_and_a_state_change():
    """Delaware, Clemson and Texas State all fail this one test even with
    no cap at all: in each, the book's number had moved inside the last
    two minutes. A wobble inside the tolerance does not reset it."""
    clock = BookMoveClock()
    clock.observe("g", TIED, american_to_implied(-174), _iso(0), _at(0), move_tol=0.02)
    assert clock.quiet_seconds("g", _at(100)) == pytest.approx(100)
    clock.observe("g", TIED, american_to_implied(-167), _iso(49), _at(52), move_tol=0.02)  # 0.0097 wobble
    assert clock.quiet_seconds("g", _at(100)) == pytest.approx(100)
    clock.observe("g", TIED, american_to_implied(100), _iso(150), _at(158), move_tol=0.02)
    assert clock.quiet_seconds("g", _at(158)) == pytest.approx(0)
    assert clock.quiet_seconds("g", _at(200)) == pytest.approx(42)
    clock.observe("g", COASTAL_UP, american_to_implied(100), _iso(198), _at(300), move_tol=0.02)
    assert clock.quiet_seconds("g", _at(330)) == pytest.approx(30)
    assert clock.quiet_seconds("unseen") is None


def test_the_ncaaf_guard_clears_once_the_state_feed_catches_up():
    """After 15:44:44 the state says 0-7. A quote published after that is the
    new baseline, and pricing resumes on whatever the model says of 0-7."""
    engine = _ncaaf_engine()
    ctx = _delaware_ctx()
    engine.price(_tied_q1(), ctx, _dk(-174, 131, 0), now=_at(3))
    engine.price(_tied_q1(), ctx, _dk(100, -133, 150), now=_at(158))
    down = _tied_q1(home_score=0, away_score=7, possession="home")
    engine.price(down, ctx, _dk(100, -133, 150), now=_at(173))
    engine.price(down, ctx, _dk(100, -133, 198), now=_at(200))
    move = engine._book_moves.observe(
        (ctx.game_id, "h2h"), (0, 7, 1, "home"),
        american_to_implied(104), _iso(300), _at(301))
    assert move == pytest.approx(abs(american_to_implied(104) - 0.5), abs=1e-6)


# ── MLB: the scorer that reads its state from the table ──────────────────────

class _MlbConn:
    """Dispatches on the SQL. The guarded path now issues four reads: the
    latest DK quote, the score-change lookup, the state-change lookup and the
    anchor quote (the first DK publish after the state last changed)."""

    def __init__(self, latest, anchor, score_change_ts, state_change_ts):
        self.latest, self.anchor = latest, anchor
        self.score_ts, self.state_ts = score_change_ts, state_change_ts
        self._pending = None
        self.sql: list[str] = []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if "live_game_state" in sql:
            self._pending = "state" if "outs" in sql else "score"
        elif "snapshot_at >= %(after)s" in sql:
            self._pending = "anchor"
        else:
            self._pending = "latest"
        return self

    def fetchone(self):
        return {"score": (self.score_ts,), "state": (self.state_ts,),
                "anchor": self.anchor, "latest": self.latest}[self._pending]


def _mlb_ts(age_sec: float) -> str:
    return (datetime.now(timezone.utc)
            - timedelta(seconds=age_sec)).isoformat()


def _mlb_odds(total_line: float, age_sec: float):
    # cols in the order _get_live_dk_odds selects them
    return (-110, -110, None, total_line, -105, -115, _mlb_ts(age_sec),
            None, None, None, None)


def test_mlb_declines_a_total_that_moved_a_full_run_on_an_unchanged_state():
    from models.live_scorer import _get_live_dk_odds
    conn = _MlbConn(latest=_mlb_odds(9.5, 5), anchor=_mlb_odds(8.5, 40),
                    score_change_ts=None, state_change_ts=_mlb_ts(45))
    assert _get_live_dk_odds(conn, "MLB_G", "totals") is None
    assert any("snapshot_at >= %(after)s" in s for s in conn.sql)


def test_mlb_keeps_a_total_that_has_not_moved_since_the_state_changed():
    from models.live_scorer import _get_live_dk_odds
    conn = _MlbConn(latest=_mlb_odds(8.5, 5), anchor=_mlb_odds(8.5, 40),
                    score_change_ts=None, state_change_ts=_mlb_ts(45))
    got = _get_live_dk_odds(conn, "MLB_G", "totals")
    assert got is not None and got["total_line"] == 8.5


def test_mlb_first_sight_is_not_a_move():
    """No state change on record: nothing to anchor to, the age bound and the
    score guard stand alone exactly as before."""
    from models.live_scorer import _get_live_dk_odds
    conn = _MlbConn(latest=_mlb_odds(9.5, 5), anchor=None,
                    score_change_ts=None, state_change_ts=None)
    assert _get_live_dk_odds(conn, "MLB_G", "totals") is not None
    assert not any("snapshot_at >= %(after)s" in s for s in conn.sql)


def test_mlb_state_change_lookup_reads_the_full_base_out_state():
    """The anchor moves on ANY state change the model prices -- inning, half,
    outs, bases, score -- not only the score. A book that reprices on a
    strikeout has a reason we can see; one that reprices on nothing has not."""
    from models.live_scorer import _get_live_dk_odds
    conn = _MlbConn(latest=_mlb_odds(8.5, 5), anchor=_mlb_odds(8.5, 40),
                    score_change_ts=None, state_change_ts=_mlb_ts(45))
    _get_live_dk_odds(conn, "MLB_G", "totals")
    state_sql = [s for s in conn.sql if "live_game_state" in s and "outs" in s]
    assert state_sql, "the full-state change lookup never ran"
    for col in ("inning", "inning_half", "outs", "bases_state",
                "home_score", "away_score"):
        assert f"l.{col} IS DISTINCT FROM latest.{col}" in state_sql[0]


# ── NFL: the executor ────────────────────────────────────────────────────────

def _nfl():
    sys.path.insert(0, str(Path(__file__).parent.parent / "nfl"))
    from live_model.executor import Executor
    from live_model.feeds.odds_live import Quote
    from live_model.state import GameState
    return Executor, Quote, GameState


def _nfl_state(GameState, home=21, away=17, poss="home", ts=None):
    return GameState("g", ts or _at(0), 3, 600, home, away, poss, 1, 10,
                     50, 3, 3, -3.0, 46.0, None, True, 80, 0.6, 0.55)


def test_the_nfl_executor_declines_a_prop_line_that_jumped_on_an_unchanged_state():
    Executor, Quote, GameState = _nfl()
    ex = Executor()
    st = _nfl_state(GameState)
    q1 = Quote("g", "player_pass_attempts", "draftkings", "over", -110, 30.5,
               _at(0), player="Q B")
    ex.evaluate(state=st, quote=q1, model_prob=0.6,
                model_id="nfl_live_prop", now=_at(1))
    q2 = Quote("g", "player_pass_attempts", "draftkings", "over", -110, 41.5,
               _at(60), player="Q B")
    d = ex.evaluate(state=_nfl_state(GameState, ts=_at(60)), quote=q2,
                    model_prob=0.6, model_id="nfl_live_prop", now=_at(61))
    assert not d.bet and d.reason.startswith("book_moved")


def test_the_nfl_executor_re_anchors_after_the_state_moves():
    Executor, Quote, GameState = _nfl()
    ex = Executor()
    q1 = Quote("g", "player_pass_attempts", "draftkings", "over", -110, 30.5,
               _at(0), player="Q B")
    ex.evaluate(state=_nfl_state(GameState), quote=q1, model_prob=0.6,
                model_id="nfl_live_prop", now=_at(1))
    # A touchdown lands; a quote published after it is the new baseline.
    st2 = _nfl_state(GameState, home=28, ts=_at(60))
    q2 = Quote("g", "player_pass_attempts", "draftkings", "over", -110, 41.5,
               _at(62), player="Q B")
    d = ex.evaluate(state=st2, quote=q2, model_prob=0.6,
                    model_id="nfl_live_prop", now=_at(63))
    assert not d.reason.startswith("book_moved")

"""A first-half total settles on Q1 + Q2, and every server surface knows it.

nba_first_half_total_luck bets the first half's points, over (market key
'totals_h1', the name the odds history already stores it under). Its picks are not
in config.MODELS, so each place that turns a model id into a market has to name
it, and each place that grades or labels a market has to know what a first half
is:

  * settlement (tracking/paper_tracker._settle_game_picks, _first_half_points):
    Q1 + Q2 from nba_period_scores, a level result a push. A game with no
    trustworthy period row stays PENDING: never settled from the full-game score,
    never stamped NO_ACTION.
  * the shadow track (tracking/opening_signals) the same way.
  * the fetch before settling (data/ingestors/nba_period_scores
    .ensure_first_half_period_scores): the only other writer of those rows is the
    6am run's nba-quarters step, which runs AFTER the 6am settle.
  * the label (models/scorer._build_pick_label) and its check
    (tracking/pick_integrity).
  * the line-movement check (models/scorer.check_line_movement).
  * closing-line value (tracking/paper_tracker._closing_odds, the SQL recompute):
    'close' rows only.
"""
from __future__ import annotations

import inspect
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
from data.db_setup import SCHEMA_SQL  # noqa: E402
from tracking import paper_tracker as pt  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = "nba_first_half_total_luck"
GAME_ID = "NBA_2026-04-04_SAS_DEN"
LABEL = "SAS @ DEN — First Half Over 125.5"
# SAS @ DEN 2026-04-04, stored 136-134 after one overtime (36+29+27+32+12 at home).
PERIODS = [(1, 36, 30), (2, 29, 33), (3, 27, 35), (4, 32, 26), (5, 12, 10)]
H1_HOME, H1_AWAY = 65, 63                      # a first half of 128


def _result(side, home, away, line, odds=-110):
    """_compute_result in the argument order the settler calls it."""
    return pt._compute_result(side, "totals_h1", home, away, None, None, 0,
                              odds, None, line, 20.0)


# ── the market ───────────────────────────────────────────────────────────────

def test_the_model_settles_on_the_first_half_market():
    assert MODEL_ID not in config.MODELS
    assert pt._RULE_MODEL_MARKETS[MODEL_ID] == "totals_h1"
    assert pt._market_for_pick(MODEL_ID) == "totals_h1"


@pytest.mark.parametrize("side,home,away,line,expected", [
    ("over", 65, 63, 125.5, "WIN"),
    ("over", 60, 60, 125.5, "LOSS"),
    ("under", 60, 60, 125.5, "WIN"),
    ("over", 63, 63, 126.0, "PUSH"),      # a whole-number line, met exactly
    ("under", 63, 63, 126.0, "PUSH"),
])
def test_the_two_scores_it_is_given_against_the_line(side, home, away, line, expected):
    assert _result(side, home, away, line)[0] == expected


def test_a_win_pays_at_the_price_and_a_loss_costs_the_stake():
    result, flat, kelly = _result("over", 65, 63, 125.5, odds=+105)
    assert (result, flat, kelly) == ("WIN", 105.0, 21.0)
    result, flat, kelly = _result("over", 60, 60, 125.5, odds=+105)
    assert (result, flat, kelly) == ("LOSS", -100.0, -20.0)


def test_no_line_is_no_action_not_a_guess():
    assert _result("over", 65, 63, None)[0] == "NO_ACTION"


# ── settlement, on the row ───────────────────────────────────────────────────

class _SqliteShim:
    """DBConnection stand-in: %s placeholders to sqlite's ?."""

    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, params=None):
        return self._c.execute(sql.replace("%s", "?"), params or [])

    def commit(self):
        self._c.commit()


@pytest.fixture
def raw():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    c.execute("ALTER TABLE picks ADD COLUMN player_id TEXT")
    c.execute("ALTER TABLE picks ADD COLUMN is_live BOOLEAN DEFAULT 0")
    c.execute("""CREATE TABLE nba_period_scores (game_id TEXT, period INTEGER,
                 home_points INTEGER, away_points INTEGER, source TEXT,
                 PRIMARY KEY (game_id, period))""")
    c.execute("""INSERT INTO games (game_id, sport, season, game_date, home_team,
                 away_team, home_score, away_score, home_win, went_to_ot,
                 commence_time)
                 VALUES (?, 'NBA', 2026, '2026-04-04', 'DEN', 'SAS', 136, 134, 1, 1,
                         '2026-04-05T00:00:00Z')""", (GAME_ID,))
    yield c
    c.close()


def _pick(raw, line=125.5, label=LABEL, odds=-110, side="over"):
    raw.execute("""INSERT INTO picks (game_id, model_id, sport, game_date,
                   pick_side, pick_label, model_probability, dk_implied_prob,
                   edge, dk_odds, scored_line, kelly_fraction, recommended_bet,
                   bankroll_at_pick, signal_type)
                   VALUES (?, ?, 'NBA', '2026-04-04', ?, ?, 0.56, 0.52,
                           0.04, ?, ?, 0.02, 20.0, 1000.0, 'BET')""",
                (GAME_ID, MODEL_ID, side, label, odds, line))


def _periods(raw, rows=PERIODS):
    raw.executemany("""INSERT INTO nba_period_scores (game_id, period, home_points, away_points,
                       source) VALUES (?, ?, ?, ?, 'espn_scoreboard')""",
                    [(GAME_ID, *r) for r in rows])


def _settled(raw):
    return raw.execute("SELECT result, profit_flat, settled_at FROM picks "
                       "WHERE model_id = ?", (MODEL_ID,)).fetchone()


def _settle(raw):
    return pt._settle_game_picks(_SqliteShim(raw), "2026-04-04", "2026-04-05T12:00:00Z")


def test_the_settler_reads_q1_plus_q2_not_the_final(raw):
    """End to end: Over 125.5 wins on 128 in the first half. Read from the full-game
    270 it would also win, so the next test is the one that tells them apart."""
    _pick(raw)
    _periods(raw)
    assert _settle(raw)[0] == 1
    result, flat, at = _settled(raw)
    assert result == "WIN" and at == "2026-04-05T12:00:00Z"
    assert flat == pytest.approx(round(100.0 * (100.0 / 110.0), 2))


def test_an_over_on_a_low_first_half_is_a_loss_though_the_final_clears_it(raw):
    """RULE: Over 130.5: the first half made 128, a LOSS. The game made 270, so a
    settlement from the full-game score would pay it. Watched passing as a WIN with
    settle_home / settle_away left on the final."""
    _pick(raw, line=130.5, label="SAS @ DEN — First Half Over 130.5")
    _periods(raw)
    _settle(raw)
    assert _settled(raw)[0] == "LOSS"


def test_a_level_first_half_on_a_whole_number_is_a_push(raw):
    _pick(raw, line=128.0, label="SAS @ DEN — First Half Over 128")
    _periods(raw)
    _settle(raw)
    result, flat, _ = _settled(raw)
    assert (result, flat) == ("PUSH", 0.0)


def test_overtime_counts_in_the_check_and_never_in_the_first_half(raw):
    """The final includes overtime and the periods sum to it, so the check passes;
    only periods 1 and 2 reach the number."""
    assert pt._first_half_points(_SqliteShim(raw), GAME_ID, 136, 134) is None
    _periods(raw)
    assert pt._first_half_points(_SqliteShim(raw), GAME_ID, 136, 134) == (H1_HOME, H1_AWAY)


def test_no_period_row_leaves_the_pick_pending(raw):
    """RULE: no period row: no result at all. Not settled from the full-game score,
    not NO_ACTION (which would be stamped once and never revisited)."""
    _pick(raw)
    assert _settle(raw) == (0, 0, 0, 0, 0.0, 0.0)
    assert _settled(raw) == (None, None, None)


@pytest.mark.parametrize("rows", [
    PERIODS[:2],                                         # only the first half is there
    PERIODS[:3],                                         # a game cut short of four
    [PERIODS[0], *PERIODS[2:]],                          # period 2 is missing
    [(1, 36, 30), (2, 29, 33), (3, 27, 35), (4, 32, 26)],   # sums short of the final
    [(1, 37, 30), (2, 29, 33), (3, 27, 35), (4, 32, 26), (5, 12, 10)],   # a wrong quarter
])
def test_period_rows_that_fail_the_lab_s_check_leave_the_pick_pending(raw, rows):
    """RULE (scripts/nba_derivative_lab.build_outcomes, the rule the graded bets
    were settled on): the periods sum to the final, are numbered 1..n with n >= 4,
    and 1 and 2 are both there. Otherwise a wrong quarter score would grade a bet
    wrong; a missing one only leaves it unsettled."""
    _pick(raw)
    _periods(raw, rows)
    _settle(raw)
    assert _settled(raw) == (None, None, None)


def test_it_settles_on_the_next_pass_once_the_row_lands(raw):
    _pick(raw)
    _settle(raw)
    assert _settled(raw)[0] is None
    _periods(raw)
    _settle(raw)
    assert _settled(raw)[0] == "WIN"


def test_a_settled_first_half_pick_is_not_settled_again(raw):
    _pick(raw)
    _periods(raw)
    _settle(raw)
    assert _settle(raw) == (0, 0, 0, 0, 0.0, 0.0)


def test_the_opening_signal_shadow_track_grades_it_the_same_way(raw):
    """tracking/opening_signals settles its copy of every BET through the same
    market and result functions, so it needs the first half's points too."""
    from tracking.opening_signals import settle_opening_signals
    raw.execute("""INSERT INTO opening_signals (lock_key, game_id, model_id, sport,
                   game_date, pick_side, pick_label, model_probability, dk_odds,
                   scored_line, recommended_bet, locked_at)
                   VALUES (?, ?, ?, 'NBA', '2026-04-04', 'over',
                           'SAS @ DEN — First Half Over 130.5', 0.56, NULL,
                           130.5, 20.0, '2026-04-04T23:05:00Z')""",
                (f"{GAME_ID}:{MODEL_ID}", GAME_ID, MODEL_ID))
    settle_opening_signals(_SqliteShim(raw), "2026-04-04", "2026-04-05T12:00:00Z")
    assert raw.execute("SELECT result FROM opening_signals").fetchone()[0] is None, \
        "no period row: pending, not graded on the final"
    _periods(raw)
    settle_opening_signals(_SqliteShim(raw), "2026-04-04", "2026-04-05T12:00:00Z")
    assert raw.execute("SELECT result FROM opening_signals").fetchone()[0] == "LOSS"


# ── the quarters are there before the settle reads them ──────────────────────

class _FakeConn:
    def __init__(self, pending):
        self.pending, self.calls, self.commits, self.rollbacks, self.closed = pending, [], 0, 0, False
        self.inserted = []

    def execute(self, sql, params=None):
        self.calls.append(" ".join(sql.split()))

        class C:
            def __init__(s, rows):
                s.rows = rows

            def fetchall(s):
                return s.rows

            def fetchone(s):
                return s.rows[0] if s.rows else None
        s = self.calls[-1]
        if s.startswith("SELECT DISTINCT p.game_date"):
            assert params == (MODEL_ID, 20)
            return C([(d,) for d in self.pending])
        if s.startswith("SELECT game_id FROM games"):
            return C([(g,) for g in params[0]])
        return C([])

    def executemany(self, sql, rows):
        self.inserted += list(rows)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _espn(away="SAS", home="DEN", day="2026-04-05T00:00Z"):
    def comp(side, code, lines, score):
        return {"homeAway": side, "score": score, "team": {"abbreviation": code, "displayName": code},
                "linescores": [{"value": v} for v in lines]}
    return {"events": [{"date": day, "status": {"type": {"completed": True}}, "competitions": [{
        "competitors": [comp("home", home, [36, 29, 27, 32, 12], 136),
                        comp("away", away, [30, 33, 35, 26, 10], 134)]}]}]}


def test_the_quarters_of_a_pending_pick_are_fetched_one_call_a_date(monkeypatch):
    """RULE: one scoreboard call per date holding a pending first-half BET whose
    game has a final and no period row, and the connection holds no transaction
    across the call."""
    import data.ingestors.nba_period_scores as ps
    conn = _FakeConn(["2026-04-04"])
    monkeypatch.setattr(ps, "get_connection", lambda: conn)
    monkeypatch.setattr(ps, "ensure_table", lambda c: None)
    asked = []

    class Resp:
        status_code = 200

        @staticmethod
        def json():
            return _espn()

    def get(url, params=None, timeout=None):
        asked.append((params, conn.rollbacks))
        return Resp()
    out = ps.ensure_first_half_period_scores(get=get)
    assert asked == [({"dates": "20260404", "limit": 50}, 1)]
    assert out == {"dates": 1, "rows": 5}
    assert sorted(r["period"] for r in conn.inserted) == [1, 2, 3, 4, 5]
    assert conn.closed


def test_no_pending_pick_makes_no_call(monkeypatch):
    import data.ingestors.nba_period_scores as ps
    conn = _FakeConn([])
    monkeypatch.setattr(ps, "get_connection", lambda: conn)
    monkeypatch.setattr(ps, "ensure_table", lambda c: None)

    def get(*a, **k):
        raise AssertionError("no pick waits, so no scoreboard call")
    assert ps.ensure_first_half_period_scores(get=get) == {"dates": 0, "rows": 0}


def test_the_query_asks_only_for_this_model_s_unsettled_bets_with_a_final_and_no_row(monkeypatch):
    import data.ingestors.nba_period_scores as ps
    conn = _FakeConn([])
    monkeypatch.setattr(ps, "get_connection", lambda: conn)
    monkeypatch.setattr(ps, "ensure_table", lambda c: None)
    ps.ensure_first_half_period_scores(get=None)
    q = next(s for s in conn.calls if s.startswith("SELECT DISTINCT"))
    for piece in ("p.model_id = %s", "p.signal_type = 'BET'", "p.result IS NULL",
                  "g.home_score IS NOT NULL", "NOT EXISTS (SELECT 1 FROM nba_period_scores"):
        assert piece in q, piece


@pytest.fixture
def settle_pass(monkeypatch):
    """settle_picks whole, on a connection that answers nothing: each grader is a
    stub that records its turn, and nothing opens a connection or calls out. Returns
    (the calls in order, the module holding the quarter pull)."""
    import data.ingestors.cfbd_ingestor as cfbd
    import data.ingestors.nba_period_scores as periods
    import data.ingestors.prop_box_scores as box
    import tracking.opening_signals as opening
    import tracking.parlay_track_record as parlay

    class Conn:
        def execute(self, *a, **k):
            return None

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    calls: list[str] = []
    zero = (0, 0, 0, 0, 0.0, 0.0)
    monkeypatch.setattr(pt, "get_connection", lambda: Conn())
    for name in ("_fetch_and_store_scores", "_void_postponed_mlb_picks", "_heal_stranded_mlb",
                 "_backfill_clv", "_capture_clv"):
        monkeypatch.setattr(pt, name, lambda *a, **k: None)
    for name in ("_settle_game_picks_window", "_settle_prop_picks_window", "_settle_ufc_picks",
                 "_settle_golf_picks"):
        monkeypatch.setattr(pt, name, lambda *a, _n=name, **k: calls.append(_n) or zero)
    monkeypatch.setattr(cfbd, "mirror_stored_finals", lambda *a, **k: None)
    monkeypatch.setattr(box, "ensure_prop_box_scores", lambda *a, **k: {})
    monkeypatch.setattr(opening, "settle_opening_signals", lambda *a, **k: None)
    monkeypatch.setattr(parlay, "settle_parlay_track_record", lambda *a, **k: None)
    return calls, periods


def test_settle_picks_fetches_the_quarters_before_it_grades(settle_pass, monkeypatch):
    """RULE: the 6am run settles (Step 0h) BEFORE its nba-quarters step (Step 0c1
    of the later group) and no refresh pass runs that step, so settle_picks fetches
    what its own picks need, before it grades. Runs the pass, because a read of the
    source was satisfied with the call taken out and its import left behind."""
    calls, periods = settle_pass
    monkeypatch.setattr(periods, "ensure_first_half_period_scores",
                        lambda *a, **k: calls.append("quarters") or {})
    pt.settle_picks("2026-04-04")
    assert "quarters" in calls
    assert calls.index("quarters") < calls.index("_settle_game_picks_window")


def test_a_failed_quarter_pull_leaves_every_other_pick_grading(settle_pass, monkeypatch):
    """RULE: an ESPN failure leaves the first-half pick pending and nothing else."""
    calls, periods = settle_pass

    def boom(*a, **k):
        calls.append("quarters")
        raise RuntimeError("ESPN is down")
    monkeypatch.setattr(periods, "ensure_first_half_period_scores", boom)
    pt.settle_picks("2026-04-04")
    assert calls[0] == "quarters"
    assert {"_settle_game_picks_window", "_settle_prop_picks_window", "_settle_ufc_picks",
            "_settle_golf_picks"} <= set(calls)


def test_the_6am_order_is_what_the_comment_says():
    """If nba-quarters ever moves before settle, the fetch in settle_picks is a
    no-op rather than wrong; this pins the fact the comment states today."""
    import run_pipeline
    src = inspect.getsource(run_pipeline.run_daily_pipeline)
    assert src.index('results["settle"] = step_settle(yesterday)') < src.index(
        '"nba-quarters", lambda: step_nba_quarters(run_date)')


# ── the label ────────────────────────────────────────────────────────────────

def test_the_label_says_first_half_and_leads_with_the_matchup():
    from models.scorer import _build_pick_label
    assert _build_pick_label("over", "MIL", "BOS", "totals_h1", 112.5) == (
        "BOS @ MIL — First Half Over 112.5")
    assert _build_pick_label("under", "MIL", "BOS", "totals_h1", 112.5) == (
        "BOS @ MIL — First Half Under 112.5")


def test_the_full_game_total_label_is_unchanged():
    from models.scorer import _build_pick_label
    assert _build_pick_label("over", "BOS", "NYK", "totals", 225.5) == "BOS vs NYK Over 225.5"


@pytest.mark.parametrize("label,line,side,problem", [
    ("BOS @ MIL — First Half Over 112.5", 112.5, "over", None),
    ("BOS @ MIL — first-half Over 112.5", 112.5, "over", None),
    ("MIL vs BOS Over 112.5", 112.5, "over", "reads as the full-game total"),
    ("BOS @ MIL — First Half Over 113.5", 112.5, "over", "stored"),
    ("BOS @ MIL — First Half Under 112.5", 112.5, "over", "says"),
])
def test_a_label_that_disagrees_is_refused(label, line, side, problem):
    """RULE (tracking/pick_integrity): the label says First Half, at the pick's
    side and line. Watched failing with _first_half_problem removed."""
    got = pick_problems(label, side, line, MODEL_ID, "MIL", "BOS")
    if problem is None:
        assert got == []
    else:
        assert got and any(problem in p for p in got), got


def test_no_other_model_is_asked_to_say_first_half():
    assert pick_problems("MIL vs BOS Over 225.5", "over", 225.5, "nba_total_luck", "MIL", "BOS") == []


# ── the line-movement check ──────────────────────────────────────────────────

def test_a_line_that_rose_over_an_over_is_a_skip(monkeypatch):
    import models.scorer as sc

    class C:
        def fetchall(self):
            return [(1, LABEL, "over", MODEL_ID, GAME_ID, -110, 125.5, "totals_h1")]

    class Conn:
        def execute(self, sql, params=None):
            return C()
    monkeypatch.setattr(sc, "_get_dk_odds", lambda conn, gid, market: {
        "total_line": 126.5, "over_price": -110, "under_price": -110})
    [w] = sc.check_line_movement(Conn(), "2026-04-04")
    assert w["status"] == "SKIP" and "125.5" in w["detail"]


# ── closing-line value: 'close' rows only ────────────────────────────────────

class _OddsConn:
    """Answers _closing_odds' one query, honouring its snapshot filter (the cast it
    writes is Postgres's, so sqlite cannot run it)."""

    def __init__(self):
        self.rows = []

    def execute(self, sql, params):
        close_only = "snapshot_type = 'close'" in sql
        assert close_only or "snapshot_type != 'in_play'" in sql, sql
        got = [r for r in self.rows if r["snapshot_type"] == "close" or not close_only]

        class Cur:
            @staticmethod
            def fetchone():
                if not got:
                    return None
                r = got[-1]
                return (None, None, None, None, r["line"], r["over"], r["under"])
        return Cur


def test_a_first_half_close_is_read_from_close_rows_only():
    """RULE: its only rows are the model's own fetches: the decision fetch, filed
    'open', and the close, filed 'close'. Read as the close, the decision fetch
    would grade a pick at exactly 0.0 for good."""
    conn = _OddsConn()
    conn.rows.append({"snapshot_type": "open", "line": 125.5, "over": -110, "under": -110})
    got = pt._closing_odds(conn, GAME_ID, "totals_h1", "2026-04-05T00:00:00Z", "fanduel")
    assert got is None, "with no 'close' row the pick is unmeasured"
    conn.rows.append({"snapshot_type": "close", "line": 125.5, "over": -120, "under": +100})
    got = pt._closing_odds(conn, GAME_ID, "totals_h1", "2026-04-05T00:00:00Z", "fanduel")
    assert got["over_price"] == -120
    # A full-game total keeps its newest pre-game row.
    conn.rows[:] = [{"snapshot_type": "open", "line": 225.5, "over": -110, "under": -110}]
    assert pt._closing_odds(conn, GAME_ID, "totals", "2026-04-05T00:00:00Z", "fanduel") is not None

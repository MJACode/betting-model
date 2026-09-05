"""The NFL live lane writes real picks, or writes nothing at all.

Matt, 2026-09-05: *"NFL should be live out of the gate, we should not do paper
trading and delay this being an available feature."*

Before this, `nfl/live_model` recorded every decision to a JSONL file on the
Railway volume and alerted nobody. That is a complete audit log and it is not a
record the platform can read: nothing joined it to `games`, nothing settled it,
no surface showed it. The lane could run all season and still report a settled
record of zero -- which also meant it could never clear the §2 go-live gate,
because the gate reads settled picks and the lane wrote none.

These tests cover the two ways that can go wrong now that it writes for real:
a pick that cannot settle, and a pick written twice.
"""

import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "nfl"))

from live_model.pick_writer import (  # noqa: E402
    LANE_MARKET, MODEL_ID, PicksRecorder, TeeRecorder, _INSERT_SQL,
    _norm_player, build_pick, resolve_game_id,
)


class _Decision:
    """The fields pick_writer reads off a real executor Decision."""

    def __init__(self, bet=True, **over):
        self.bet = bet
        self.ts = over.get("ts", datetime(2026, 9, 13, 18, 30, tzinfo=timezone.utc))
        self.game_id = over.get("game_id", "espn-401547json")
        self.model_id = over.get("model_id", MODEL_ID)
        self.market = over.get("market", "player_pass_attempts")
        self.side = over.get("side", "over")
        self.line = over.get("line", 32.5)
        self.price = over.get("price", -115.0)
        self.model_prob = over.get("model_prob", 0.58)
        self.market_prob = over.get("market_prob", 0.5349)
        self.ev = over.get("ev", 0.0787)
        self.stake_fraction = over.get("stake_fraction", 0.011)
        self.player = over.get("player", "C.J. Stroud")
        self.context = over.get("context", {"home_team": "Houston Texans",
                                            "away_team": "Buffalo Bills"})


class _Conn:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else [("NFL_2026_01_BUF_HOU",)]
        self.executed = []
        self.commits = 0

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        return self

    def fetchall(self):
        return self.rows

    def commit(self):
        self.commits += 1

    def close(self):
        pass


# ── the pick must be able to settle ──────────────────────────────────────────

def test_every_row_key_is_actually_bound_by_the_insert():
    """The footgun this lane nearly shipped.

    psycopg2 named parameters IGNORE extra keys in the row dict. The first
    version of build_pick returned the column set of models.scorer._insert_picks
    -- which carries neither `prop_market` nor `player_key` -- so the two columns
    settlement reads would have been silently dropped and every live pick would
    have been unsettleable, with nothing raising.

    Asserted both ways: no key goes unbound, and no placeholder goes unfilled.
    """
    row = build_pick(_Decision(), "NFL_2026_01_BUF_HOU", 1000.0)
    bound = {p.split(")s")[0] for p in _INSERT_SQL.split("%(")[1:]}
    assert set(row) == bound, (
        f"row-only keys {sorted(set(row) - bound)}; "
        f"unbound placeholders {sorted(bound - set(row))}")


def test_the_settlement_columns_are_populated():
    """`prop_market` + `player_key` are what tracking/paper_tracker resolves a
    market-spanning model id against. Empty here means graded never."""
    row = build_pick(_Decision(), "NFL_2026_01_BUF_HOU", 1000.0)
    assert row["prop_market"] == LANE_MARKET == "player_pass_attempts"
    assert row["player_key"] == "CJ STROUD"
    assert row["is_live"] is True
    assert row["signal_type"] == "BET"


def test_edge_is_the_platform_edge_not_the_lanes_ev():
    """The lane gates on EV (model_prob * decimal - 1); every other model in
    `picks` stores edge as model_prob - market_prob. Storing EV in the edge
    column would put this lane on a different scale from the whole table and
    corrupt any cross-model threshold sweep that reads it."""
    d = _Decision(model_prob=0.58, market_prob=0.5349, ev=0.0787)
    row = build_pick(d, "NFL_2026_01_BUF_HOU", 1000.0)
    assert row["edge"] == pytest.approx(0.58 - 0.5349)
    assert row["edge"] != pytest.approx(d.ev)


def test_the_stake_carries_through_to_a_dollar_figure():
    row = build_pick(_Decision(stake_fraction=0.011), "NFL_2026_01_BUF_HOU", 1000.0)
    assert row["kelly_fraction"] == pytest.approx(0.011)
    assert row["recommended_bet"] == pytest.approx(11.0)


# ── the game id is the whole problem ─────────────────────────────────────────

def test_game_id_resolves_from_the_book_s_team_names():
    """A Decision carries ESPN's event id; `picks.game_id` is a FK into `games`
    keyed NFL_{season}_{week}_{away}_{home}, and the book's event id is a third
    unrelated string. Team names are the only bridge -- which is what Quote's
    own docstring says they exist for."""
    conn = _Conn([("NFL_2026_01_BUF_HOU",)])
    got = resolve_game_id(conn, "Houston Texans", "Buffalo Bills",
                          datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc))
    assert got == "NFL_2026_01_BUF_HOU"
    _sql, params = conn.executed[0]
    assert params[0] == "HOU" and params[1] == "BUF", params
    # +/- a day: a Sunday-night kickoff lands on the next UTC date.
    assert params[2] == "2026-09-12" and params[3] == "2026-09-14", params


@pytest.mark.parametrize("home,away,rows,why", [
    ("Nonexistent FC", "Buffalo Bills", [("x",)], "unmappable team name"),
    ("Houston Texans", "Buffalo Bills", [], "no scheduled game"),
    ("Houston Texans", "Buffalo Bills", [("a",), ("b",)], "ambiguous match"),
])
def test_resolution_refuses_rather_than_guesses(home, away, rows, why):
    """A pick under an id that joins to no game can never settle, and
    `picks.game_id` is a FK -- so a wrong answer is strictly worse than none."""
    conn = _Conn(rows)
    assert resolve_game_id(conn, home, away,
                           datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc)) is None, why


def test_an_unresolvable_decision_writes_nothing():
    conn = _Conn([])
    rec = PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)
    rec(_Decision())
    assert conn.commits == 0
    assert not any("INSERT INTO picks" in s for s, _ in conn.executed)


# ── bets only, and only once ─────────────────────────────────────────────────

def test_a_pass_is_never_written_to_picks():
    """Every PASS is recorded too -- in the JSONL log. Writing them to `picks`
    is the "hundreds of dead rows a day" CLAUDE.md warns about for live lanes."""
    conn = _Conn()
    rec = PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)
    rec(_Decision(bet=False))
    assert conn.executed == [] and conn.commits == 0


def test_the_insert_tolerates_the_one_row_per_pick_index():
    """uq_picks_one_row_per_pick makes a duplicate an IntegrityError, which
    aborts the transaction and costs the tick its pick. The first-signal lock
    prevents the duplicate; this makes the losing side of a race harmless."""
    assert "ON CONFLICT DO NOTHING" in _INSERT_SQL


def test_normalised_player_key_is_the_join_the_prop_system_uses():
    assert _norm_player("C.J. Stroud") == "CJ STROUD"
    assert _norm_player("Ja'Marr  Chase") == "JAMARR CHASE"
    assert _norm_player(None) is None


# ── the two recorders are independent ────────────────────────────────────────

def test_a_failing_recorder_cannot_take_the_other_down():
    """A Postgres outage that also silenced the JSONL log would lose the record
    entirely, so the tee isolates each side."""
    seen = []

    def ok(d):
        seen.append(d)

    def boom(d):
        raise RuntimeError("postgres is down")

    TeeRecorder(boom, ok)(_Decision())
    assert len(seen) == 1


def test_the_audit_log_is_written_before_the_database():
    """A decision that reached Postgres but not the durable log must not be
    possible -- the executor's own rule, "a decision that was not written did
    not happen"."""
    order = []
    TeeRecorder(lambda d: order.append("jsonl"),
                lambda d: order.append("picks"))(_Decision())
    assert order == ["jsonl", "picks"]


def test_the_recorder_never_raises_into_the_hot_path():
    """The executor swallows recorder exceptions, but the loop's cadence is the
    thing being protected -- guard here too rather than relying on the caller."""
    def explode():
        raise RuntimeError("connection refused")

    PicksRecorder(bankroll=1000.0, conn_factory=explode)(_Decision())


# ── the lock, and the drift guard for restating it ───────────────────────────

def test_the_lane_lock_matches_the_scorers_canonical_predicate():
    """pick_writer restates models.scorer._locked_live_lanes' query because it
    cannot import it -- `from models.x import` under nfl/ resolves to whichever
    `models` package sys.path reaches first, and tests/test_nfl_model_imports.py
    fails the build over that. Restating it means the two can drift, so pin the
    predicate here: this is the guard the shared import would have been.
    """
    import inspect
    import re
    from live_model.pick_writer import _lane_is_locked
    from models.scorer import _locked_live_lanes

    def _clauses(fn):
        src = inspect.getsource(fn)
        sql = src[src.index("SELECT"):src.index('"""', src.index("SELECT"))]
        return re.sub(r"\s+", " ", sql).strip().lower()

    assert _clauses(_lane_is_locked) == _clauses(_locked_live_lanes), (
        "the live lane lock has drifted from the scorer's canonical version")


def test_a_locked_lane_writes_nothing_further():
    """§1c: the first BET is the bet of record. A later, better number in the
    same lane is line movement, not a new pick."""
    class _LockedConn(_Conn):
        def fetchall(self):
            # game_id resolution, then the lock query
            return [("NFL_2026_01_BUF_HOU",)] if len(self.executed) == 1 \
                else [(MODEL_ID,)]

    conn = _LockedConn()
    PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)(_Decision())
    assert conn.commits == 0
    assert not any("INSERT INTO picks" in s for s, _ in conn.executed)


def test_an_unlocked_lane_does_write():
    """The mirror of the test above -- otherwise a lock that always returns True
    would pass every lock test and silently write nothing, ever."""
    class _OpenConn(_Conn):
        def fetchall(self):
            return [("NFL_2026_01_BUF_HOU",)] if len(self.executed) == 1 else []

    conn = _OpenConn()
    PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)(_Decision())
    assert conn.commits == 1
    inserts = [p for s, p in conn.executed if "INSERT INTO picks" in s]
    assert len(inserts) == 1
    assert inserts[0]["model_id"] == MODEL_ID
    assert inserts[0]["game_id"] == "NFL_2026_01_BUF_HOU"


# ── registration: thresholds and settlement ──────────────────────────────────

def test_the_lane_carries_its_own_thresholds():
    """A model reaching production without its own entry is scored against the
    module-level fallback, which is a number nobody chose (tests/test_config)."""
    import config
    for m in (config.MODEL_EDGE_THRESHOLDS, config.MODEL_PROB_THRESHOLDS,
              config.ACTION_THRESHOLDS):
        assert MODEL_ID in m, f"{MODEL_ID} missing from a threshold map"


def test_the_thresholds_do_not_re_cut_what_the_lane_already_decided():
    """The cut is EV, applied in the executor BEFORE a decision is recorded as a
    bet. A second, different cut in the action filter would write picks and then
    hide them -- the exact app/Discord divergence this release removes."""
    import config
    assert config.ACTION_THRESHOLDS[MODEL_ID] == {"min_prob": 0.0, "min_edge": 0.0}


def test_the_lane_can_actually_settle():
    """The whole point of writing to `picks`. Without this mapping the lane
    accrues rows that are never graded, which is the paper record it already
    had, with more moving parts."""
    from tracking.paper_tracker import _PROP_STAT_MAP as M
    assert M[MODEL_ID] == ("nfl_player", "attempts")
    assert M["nfl_prop_pass_attempts"] == M[MODEL_ID], (
        "the live lane grades against the same stat as the pre-game one")

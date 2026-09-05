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

import subprocess
import sys
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

def test_the_lane_lock_shares_the_scorers_meaning_of_locked():
    """"Locked" has to mean the same thing everywhere: an unsettled live BET.

    pick_writer restates models.scorer._locked_live_lanes' predicate because it
    cannot import it (`from models.x import` under nfl/ resolves to whichever
    `models` package sys.path reaches first, and test_nfl_model_imports fails the
    build over it). Restating means the two can drift, so the shared clauses are
    pinned here -- but as CLAUSES, not as one string, because the two are
    deliberately not identical. See the next test for the part that differs.
    """
    import inspect
    import re
    from live_model.pick_writer import _lane_is_locked
    from models.scorer import _locked_live_lanes

    def _sql(fn):
        src = inspect.getsource(fn)
        i = src.index("SELECT")
        return re.sub(r"\s+", " ", src[i:src.index('"""', i)]).strip().lower()

    ours, theirs = _sql(_lane_is_locked), _sql(_locked_live_lanes)
    for clause in ("is_live = true", "signal_type = 'bet'", "result is null",
                   "game_id = %s"):
        assert clause in ours, f"{clause} missing from the NFL lock"
        assert clause in theirs, f"{clause} missing from the scorer's lock"


def test_the_lock_is_scoped_by_player_not_just_by_game():
    """The #489 bug, pinned.

    models.scorer._locked_live_lanes keys on (game, model) because every lane it
    serves is a GAME-level proposition -- one total, one moneyline per game. This
    lane is a PLAYER PROP: a game carries a proposition per quarterback. Locking
    on (game, model) meant the first QB's bet froze the lane for everyone else in
    that game, which on a 13-game Sunday silently blocks roughly half the
    eligible bets and looks exactly like the model finding nothing.
    """
    import inspect
    from live_model.pick_writer import _lane_is_locked

    src = inspect.getsource(_lane_is_locked)
    assert "player_key" in src, "the lock must be scoped by player"
    assert "model_id = %s" in src, (
        "and by model -- a game-wide lock would block other lanes too")


def test_two_players_in_one_game_can_both_get_a_bet():
    """The behavioural half. A source assertion alone would pass against a lock
    that names player_key and still ignores it."""
    seen = []

    class _TwoQBConn(_Conn):
        def __init__(self):
            super().__init__()
            self.locked_for = {"CJ STROUD"}

        def execute(self, sql, params=None):
            self.executed.append((sql, params))
            if "SELECT 1 FROM picks" in sql:
                # params: (game_id, model_id, player_key)
                self._last_lock = params[2] in self.locked_for
            if "INSERT INTO picks" in sql:
                seen.append(params["player_key"])
            return self

        def fetchall(self):
            last = self.executed[-1][0]
            if "FROM games" in last:
                return [("NFL_2026_01_BUF_HOU",)]
            if "SELECT 1 FROM picks" in last:
                return [(1,)] if self._last_lock else []
            return []

    conn = _TwoQBConn()
    rec = PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)
    rec(_Decision(player="C.J. Stroud"))    # already locked -> skipped
    rec(_Decision(player="Josh Allen"))     # different player -> must write
    assert seen == ["JOSH ALLEN"], (
        f"the second quarterback was blocked by the first: {seen}")


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
    hide them -- the exact app/Discord divergence this release removes.

    ALL THREE gates, not just the two that are written inline. The first version
    of this test asserted min_prob and min_edge only, and shipped a lane whose
    PRICE floor fell through to the -200 house default: a live prop bet at -250
    would have been written to `picks` and then hidden by the app's
    passesActionFilter. The gap was invisible because the floor is not in
    ACTION_THRESHOLDS at all -- it comes from config.min_odds_for, which is what
    data.threshold_sync actually mirrors into model_action_thresholds.
    """
    import config
    assert config.ACTION_THRESHOLDS[MODEL_ID] == {"min_prob": 0.0, "min_edge": 0.0}
    # The price floor is allowed to bind ONLY where the executor already refuses
    # (see test_the_display_floor_matches_the_executors_ceiling). Tighter than
    # the executor and a taken bet gets hidden, which is the #491 bug.
    assert config.min_odds_for(MODEL_ID) <= _executor_min_price(), (
        f"display floor {config.min_odds_for(MODEL_ID)} is TIGHTER than the "
        f"executor's ceiling {_executor_min_price()} -- a bet the lane took "
        f"would be written to picks and hidden in the app")


def test_the_synced_row_is_what_the_app_will_actually_read():
    """threshold_sync mirrors config into model_action_thresholds, and the app,
    Discord and push all gate on THAT row -- so the row, not the inline dict, is
    the thing that has to be non-cutting. Built here the same way the sync builds
    it, so a change to how the floor is derived cannot pass this test."""
    import config
    from config import ACTION_THRESHOLDS, PAUSED_MODELS, PROB_ONLY_MODELS

    assert MODEL_ID in ACTION_THRESHOLDS, "the sync only writes ACTION_THRESHOLDS keys"
    t = ACTION_THRESHOLDS[MODEL_ID]
    row = {
        "min_prob": t["min_prob"],
        "min_edge": t["min_edge"],
        "min_odds": config.min_odds_for(MODEL_ID),
        "prob_only": MODEL_ID in PROB_ONLY_MODELS,
        "paused": MODEL_ID in PAUSED_MODELS,
    }
    assert row["paused"] is False, "the lane is LIVE (CLAUDE.md section 2)"
    assert row["min_prob"] == 0.0 and row["min_edge"] == 0.0
    assert row["min_odds"] <= _executor_min_price()


def test_the_lane_can_actually_settle():
    """The whole point of writing to `picks`. Without this mapping the lane
    accrues rows that are never graded, which is the paper record it already
    had, with more moving parts."""
    from tracking.paper_tracker import _PROP_STAT_MAP as M
    assert M[MODEL_ID] == ("nfl_player", "attempts")
    assert M["nfl_prop_pass_attempts"] == M[MODEL_ID], (
        "the live lane grades against the same stat as the pre-game one")


# ── the juice ceiling ────────────────────────────────────────────────────────

def _executor_min_price() -> float:
    """The lane's own price ceiling, read from the standalone package."""
    out = _probe_config("print(c.MIN_PRICE)")
    return float(out[0])


def _probe_config(expr: str) -> list[str]:
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(Path(__file__).parent.parent / 'nfl')!r})\n"
        "from live_model import config as c\n" + expr + "\n"
    )
    r = subprocess.run([sys.executable, "-c", code],
                       cwd=str(Path(__file__).parent.parent / "nfl"),
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()


def test_the_lane_refuses_a_quote_past_the_ceiling():
    """Matt, 2026-09-05: "-140 should be price ceiling."

    Refused BEFORE the EV test, so a juicy quote is ineligible however good the
    number looks. A more negative American price is more juice, so -150 is past
    a -140 ceiling and +120 is not.
    """
    assert _executor_min_price() == -140.0


def test_the_display_floor_matches_the_executors_ceiling():
    """The two numbers that drifted apart in #491, pinned together.

    A display floor TIGHTER than the executor's ceiling hides a bet the lane
    took -- that was the bug. One LOOSER is dead config that still reads as a
    rule. They must be the same number.
    """
    import config
    assert config.min_odds_for(MODEL_ID) == _executor_min_price(), (
        f"MODEL_MIN_ODDS says {config.min_odds_for(MODEL_ID)}, the executor "
        f"says {_executor_min_price()} -- keep them in step")


def test_the_ceiling_is_a_refusal_not_a_filter():
    """It has to record a PASS with a reason, so the audit log shows the lane
    looked and declined. Filtering downstream would take the bet and hide it."""
    import inspect
    src = (Path(__file__).parent.parent / "nfl" / "live_model"
           / "executor.py").read_text(encoding="utf-8")
    i = src.index("if quote.price < MIN_PRICE:")
    assert "_mk(False" in src[i:i + 200], (
        "the ceiling must return a recorded PASS, not silently skip")
    # Before the EV test: eligibility, not an edge question.
    assert i < src.index("threshold = EV_THRESHOLDS[model_id]")


# ── declines are recorded, like every other live lane ────────────────────────

class _AvoidConn(_Conn):
    """Resolves the game, reports the lane unlocked, records what was written."""

    def __init__(self):
        super().__init__()
        self.inserts = []
        self.deletes = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if "INSERT INTO picks" in sql:
            self.inserts.append(params)
        if "DELETE FROM picks" in sql:
            self.deletes.append(params)
        return self

    def fetchall(self):
        last = self.executed[-1][0]
        return [("NFL_2026_01_BUF_HOU",)] if "FROM games" in last else []


def _mk_decline(reason, **over):
    d = _Decision(bet=False, **over)
    d.reason = reason
    return d


def test_a_market_opinion_decline_is_written_as_avoid():
    """Every other live lane records its declines in `picks`: mlb_live_total_runs
    95 BET / 73 AVOID, ncaaf_live_total 20/7. nfl_live_prop was the only one whose
    declines lived in a JSONL file nobody could query, so its cut could never be
    swept against its own near-misses (CLAUDE.md's evaluation rule)."""
    conn = _AvoidConn()
    PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)(
        _mk_decline("below_threshold:0.0210<0.0600"))
    assert len(conn.inserts) == 1
    assert conn.inserts[0]["signal_type"] == "AVOID"
    assert conn.inserts[0]["kelly_fraction"] == 0.0
    assert conn.inserts[0]["recommended_bet"] == 0.0


def test_the_juice_ceiling_decline_is_also_a_market_opinion():
    conn = _AvoidConn()
    PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)(
        _mk_decline("price_past_ceiling:-250<-140"))
    assert len(conn.inserts) == 1 and conn.inserts[0]["signal_type"] == "AVOID"


@pytest.mark.parametrize("reason", [
    "stale_quote:212s", "degenerate_model_prob", "no_kelly_stake",
    "daily_exposure_cap", "unknown_model:nfl_live_deriv",
])
def test_plumbing_refusals_stay_out_of_picks(reason):
    """A stale quote is not a view on the market. Writing these would be the
    "hundreds of dead rows a day" CLAUDE.md warns about for live lanes -- and
    they answer an operations question, which the JSONL log already serves."""
    conn = _AvoidConn()
    PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)(_mk_decline(reason))
    assert conn.inserts == [] and conn.executed == []


def test_an_unchanged_proposition_is_not_rewritten():
    """The executor evaluates every candidate on every poll -- at 5s that is
    thousands of identical opinions an hour. Same rule as
    models.live_scorer._lane_signature: rewrite on the PROPOSITION changing."""
    conn = _AvoidConn()
    rec = PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)
    for _ in range(5):
        rec(_mk_decline("below_threshold:0.02<0.06", line=32.5, price=-115))
    assert len(conn.inserts) == 1, "an unchanged line and price wrote twice"


def test_a_moved_line_is_rewritten():
    """The mirror: a dedup that never invalidates would record the first
    opinion of the game and nothing after it."""
    conn = _AvoidConn()
    rec = PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)
    rec(_mk_decline("below_threshold:0.02<0.06", line=32.5, price=-115))
    rec(_mk_decline("below_threshold:0.02<0.06", line=33.5, price=-115))
    rec(_mk_decline("below_threshold:0.02<0.06", line=33.5, price=-120))
    assert len(conn.inserts) == 3
    assert len(conn.deletes) == 3, "each rewrite must replace the standing row"


def test_the_avoid_rewrite_can_never_delete_a_bet():
    """§1c. The standing AVOID is replaced; a BET is the bet of record and is
    never removed -- the same guard ncaaf_live.gameday.write_picks carries."""
    conn = _AvoidConn()
    PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)(
        _mk_decline("below_threshold:0.02<0.06"))
    delete_sql = [s for s, _ in conn.executed if "DELETE FROM picks" in s][0]
    assert "signal_type <> 'BET'" in delete_sql


def test_recording_a_decline_can_never_break_a_bet():
    """Matt, 2026-09-05: recording declines "shouldn't prevent bets from being
    live". The two paths are separate branches with separate guards, so a
    failing AVOID write costs a research row and nothing else."""
    def explode():
        raise RuntimeError("connection refused")

    # The AVOID path swallowing its own failure.
    PicksRecorder(bankroll=1000.0, conn_factory=explode)(
        _mk_decline("below_threshold:0.02<0.06"))

    # And a bet still writes when the AVOID cache is populated for that lane.
    conn = _AvoidConn()
    rec = PicksRecorder(bankroll=1000.0, conn_factory=lambda: conn)
    rec(_mk_decline("below_threshold:0.02<0.06"))
    rec(_Decision())
    assert any(i["signal_type"] == "BET" for i in conn.inserts)

"""The pre-registered forward test of the 2026-08-31 cuts, and its pause rule.

These pin the parts that make the rule a rule rather than a preference: it acts
on a fixed schedule instead of continuously, it needs a real sample per model,
it never unpauses on its own, and the pause it writes is one the SCORER can see.
"""

from __future__ import annotations

import pytest

import config
from tracking import threshold_review as tr


@pytest.fixture
def rule_only(monkeypatch):
    """Neutralise the REAL `config.PAUSED_MODELS` for this module.

    `run_review` correctly skips a model that is already deliberately paused,
    so these fixtures — which use real model ids — silently change meaning
    every time someone pauses one. That happened on 2026-09-03: pausing
    `mlb_over_under` broke `test_the_boundary_is_exactly_minus_five_percent`
    outright, and quietly made two others pass for the WRONG reason
    (`test_a_losing_model_with_too_few_bets_is_left_alone` would have passed
    even with the bet floor deleted, because its model was paused anyway).

    These tests are about the RULE — the bet floor, the -5% boundary, the
    never-unpause property — not about which models happen to be paused today.
    `test_an_already_paused_model_is_not_paused_again` covers the interaction
    on purpose, and it is deliberately NOT autouse — two tests below assert
    against the real `config.PAUSED_MODELS` and must keep seeing it.
    """
    monkeypatch.setattr(config, "PAUSED_MODELS", set())


class _Conn:
    """Minimal stand-in: canned slate rows, real writes recorded."""

    def __init__(self, slate, reviewed=(), paused=()):
        self._slate = slate                       # [(model_id, bets, roi)]
        self._reviewed = set(reviewed)            # milestones already done
        self.auto_paused = set(paused)
        self.inserts: list[tuple[str, dict]] = []
        self.committed = False

    def execute(self, sql, params=None):
        self._last = (sql, params)
        if "INSERT INTO model_auto_pauses" in sql:
            self.inserts.append(("pause", params))
            self.auto_paused.add(params["m"])
        elif "INSERT INTO threshold_reviews" in sql:
            self.inserts.append(("ledger", params))
            self._reviewed.add(params["k"])
        return self

    def fetchall(self):
        sql = self._last[0]
        if "FROM model_auto_pauses" in sql:
            return [(m,) for m in sorted(self.auto_paused)]
        return [(m, n, roi) for m, n, roi in self._slate]

    def fetchone(self):
        sql, params = self._last
        if "FROM threshold_reviews" in sql:
            return (1,) if params[0] in self._reviewed else None
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    """No Discord from a test. The announce path has its own assertions below."""
    monkeypatch.setattr(tr, "_announce", lambda result: None)
    monkeypatch.setenv("RUN_THRESHOLD_REVIEW", "1")


def _slate(*rows):
    return list(rows)


# ── the schedule: milestones, not every day ──────────────────────────────────

def test_nothing_happens_before_the_first_milestone():
    """249 bets is not 250. A rule that acts early is a rule that acts on noise."""
    conn = _Conn(_slate(("mlb_moneyline", 249, -30.0)))
    out = tr.run_review(conn)
    assert out["status"] == "not_due"
    assert conn.inserts == []


def test_the_review_fires_when_the_slate_crosses_250():
    conn = _Conn(_slate(("mlb_moneyline", 250, -30.0)))
    out = tr.run_review(conn)
    assert out["status"] == "reviewed"
    assert out["milestone"] == 250


def test_a_milestone_fires_only_once():
    """Otherwise the daily cadence becomes the trigger, and the rule degenerates
    into 'keep looking until it fails once'."""
    conn = _Conn(_slate(("mlb_moneyline", 260, -30.0)), reviewed={250})
    assert tr.run_review(conn)["status"] == "not_due"


def test_the_next_milestone_does_fire():
    conn = _Conn(_slate(("mlb_moneyline", 500, -30.0)), reviewed={250})
    out = tr.run_review(conn)
    assert out["milestone"] == 500


# ── the pause rule itself ────────────────────────────────────────────────────

def test_a_losing_model_with_enough_bets_is_paused(rule_only):
    conn = _Conn(_slate(("mlb_moneyline", 200, -12.0), ("mlb_over_under", 60, 3.0)))
    out = tr.run_review(conn)
    assert [p["model_id"] for p in out["paused"]] == ["mlb_moneyline"]
    assert conn.committed


def test_a_losing_model_with_too_few_bets_is_left_alone(rule_only):
    """49 bets of -40% is a number, not a result. The floor is what stops the
    rule from killing a model on a bad fortnight."""
    conn = _Conn(_slate(("mlb_moneyline", 251, 1.0), ("mlb_over_under", 49, -40.0)))
    out = tr.run_review(conn)
    assert out["paused"] == []


def test_the_boundary_is_exactly_minus_five_percent(rule_only):
    """-5.0% is kept, -5.1% is paused. An off-by-one here quietly changes the
    rule that was agreed before the data arrived."""
    conn = _Conn(_slate(("mlb_moneyline", 130, -5.0), ("mlb_over_under", 130, -5.1)))
    out = tr.run_review(conn)
    assert [p["model_id"] for p in out["paused"]] == ["mlb_over_under"]


def test_an_already_paused_model_is_not_paused_again(monkeypatch):
    """A model paused deliberately in config.py must not also be auto-paused:
    that would write a second, automatic record of a decision a human already
    made, and the two pause sources are deliberately kept separate."""
    monkeypatch.setattr(config, "PAUSED_MODELS", {"mlb_over_under"})
    conn = _Conn(_slate(("mlb_moneyline", 130, 4.0), ("mlb_over_under", 130, -30.0)))
    assert tr.run_review(conn)["paused"] == []


def test_a_profitable_model_is_never_touched(rule_only):
    conn = _Conn(_slate(("mlb_moneyline", 150, 8.0), ("mlb_over_under", 150, 22.0)))
    assert tr.run_review(conn)["paused"] == []


def test_it_does_not_re_pause_what_is_already_paused():
    conn = _Conn(_slate(("mlb_moneyline", 260, -12.0)), paused={"mlb_moneyline"})
    assert tr.run_review(conn)["paused"] == []


def test_a_model_paused_in_config_is_not_reported_again():
    """config.PAUSED_MODELS is a person's decision; restating it as an automatic
    one would misattribute the call (CLAUDE.md 1b)."""
    paused_id = sorted(config.PAUSED_MODELS)[0]
    conn = _Conn(_slate((paused_id, 260, -30.0)))
    assert tr.run_review(conn)["paused"] == []


def test_it_never_unpauses():
    """The rule has no path back. Coming off the bench needs a person, and a
    rule that pauses and unpauses on the same noisy number just oscillates."""
    import inspect
    src = inspect.getsource(tr)
    assert "DELETE FROM model_auto_pauses" not in src
    assert "UPDATE model_auto_pauses" not in src


def test_the_kill_switch_stops_it(monkeypatch):
    monkeypatch.setenv("RUN_THRESHOLD_REVIEW", "0")
    conn = _Conn(_slate(("mlb_moneyline", 300, -30.0)))
    assert tr.run_review(conn)["status"] == "disabled"
    assert conn.inserts == []


def test_dry_run_decides_without_writing():
    conn = _Conn(_slate(("mlb_moneyline", 300, -30.0)))
    out = tr.run_review(conn, dry_run=True)
    assert [p["model_id"] for p in out["paused"]] == ["mlb_moneyline"]
    assert conn.inserts == []


# ── the pause has to reach the thing that makes picks ────────────────────────

def test_the_scorer_treats_an_auto_pause_as_a_pause():
    """The whole mechanism is worthless if the scorer cannot see it. Writing
    `paused` into model_action_thresholds would NOT work -- the scorer reads
    config.py, so that only hides picks in the app while the model keeps
    betting, and the nightly threshold_sync overwrites it anyway."""
    from models import scorer

    before = scorer._AUTO_PAUSE_CACHE
    try:
        scorer._AUTO_PAUSE_CACHE = {"mlb_over_under"}
        assert scorer._is_paused("mlb_over_under") is True
        assert scorer._is_paused("mlb_moneyline") is False
    finally:
        scorer._AUTO_PAUSE_CACHE = before


def test_config_pauses_still_work_through_the_same_helper():
    from models import scorer

    before = scorer._AUTO_PAUSE_CACHE
    try:
        scorer._AUTO_PAUSE_CACHE = set()
        assert scorer._is_paused(sorted(config.PAUSED_MODELS)[0]) is True
    finally:
        scorer._AUTO_PAUSE_CACHE = before


def test_every_pause_check_in_the_scorer_goes_through_the_helper():
    """Three call sites downgrade BET -> NONE. One left reading PAUSED_MODELS
    directly is a lane the auto-pause silently does not cover."""
    src = (config.ROOT / "models" / "scorer.py").read_text(encoding="utf-8")
    assert 'model_id in PAUSED_MODELS and signal_type' not in src
    assert src.count('_is_paused(model_id) and signal_type == "BET"') == 3


def test_an_unreadable_pause_table_fails_open():
    """A database blip must not silence the platform. Failing closed here would
    be a bigger outage than the one the review prevents."""
    class _Broken:
        def execute(self, *a, **k):
            raise RuntimeError("relation does not exist")

        def rollback(self):
            pass

    assert tr.auto_paused(_Broken()) == set()


# ── the DDL that was created and thrown away every morning ──────────────────

class _DdlConn:
    """Records statements and commits, and models autocommit=False.

    `uncommitted` is what a real connection would DISCARD on close — which is
    exactly what happened in production for four days.
    """

    def __init__(self, tables_exist=False):
        self.tables_exist = tables_exist
        self.statements, self.uncommitted, self.committed = [], [], []

    def execute(self, sql, params=()):
        s = " ".join(str(sql).split())
        self.statements.append(s)
        self.uncommitted.append(s)
        return _DdlRes(self, s)

    def commit(self):
        self.committed.extend(self.uncommitted)
        self.uncommitted = []

    def rollback(self):
        self.uncommitted = []

    def close(self):
        self.uncommitted = []          # psycopg discards an open transaction


class _DdlRes:
    def __init__(self, conn, sql):
        self.conn, self.sql = conn, sql

    def fetchone(self):
        # data.ddl_guard's catalog probe: a row means the table exists.
        if "pg_class" in self.sql or "relname" in self.sql:
            return (False, [], [], 0) if self.conn.tables_exist else None
        return None

    def fetchall(self):
        return []


def test_ensure_schema_commits_the_tables_it_creates(monkeypatch):
    """
    The bug this pins cost four days of a non-existent table.

    data.db.get_connection sets autocommit=False. run_review returns at
    `not_due` on every day the slate has not crossed a 250-bet milestone —
    every day so far, 80 settled since EPOCH — and that early return reaches no
    commit. The caller closes the connection, psycopg discards the open
    transaction, and both CREATE TABLEs go with it. The review therefore
    created both tables every morning and threw them away every morning, while
    models/scorer.py logged `relation "model_auto_pauses" does not exist`.
    """
    import tracking.threshold_review as tr

    monkeypatch.setattr(tr, "schema_is_current", lambda *a, **k: False)
    monkeypatch.setattr(tr, "lock_down", lambda conn, table: ())
    conn = _DdlConn()
    tr.ensure_schema(conn)

    created = [s for s in conn.committed if "CREATE TABLE" in s]
    assert len(created) == 2, (
        f"both tables must survive the connection closing; committed={conn.committed}")
    assert any("model_auto_pauses" in s for s in created)
    assert any("threshold_reviews" in s for s in created)

    conn.close()
    assert [s for s in conn.committed if "CREATE TABLE" in s], (
        "the DDL must still be there after close()")


def test_the_tables_are_locked_down_at_the_create_site(monkeypatch):
    """Worker-only tables must arrive closed, not inherit the default anon
    grant. Same rule as #464, applied where they are created."""
    import tracking.threshold_review as tr

    locked = []
    monkeypatch.setattr(tr, "schema_is_current", lambda *a, **k: False)
    monkeypatch.setattr(tr, "lock_down", lambda conn, table: locked.append(table))
    tr.ensure_schema(_DdlConn())
    assert sorted(locked) == ["model_auto_pauses", "threshold_reviews"]


def test_a_failed_lock_down_does_not_lose_the_table(monkeypatch):
    """A lock that raises must not take the CREATE TABLE with it."""
    import tracking.threshold_review as tr

    def boom(conn, table):
        raise RuntimeError("catalog unavailable")

    monkeypatch.setattr(tr, "schema_is_current", lambda *a, **k: False)
    monkeypatch.setattr(tr, "lock_down", boom)
    conn = _DdlConn()
    tr.ensure_schema(conn)
    assert [s for s in conn.committed if "CREATE TABLE" in s]


def test_both_review_tables_are_declared_worker_only():
    """If either is ever added to ANON_READABLE instead, RLS-with-no-policies
    would deny the app — the manifest is the place that decides."""
    from data.anon_readable import ANON_READABLE, WORKER_ONLY_TABLES
    for t in ("model_auto_pauses", "threshold_reviews"):
        assert t in WORKER_ONLY_TABLES
        assert t not in ANON_READABLE

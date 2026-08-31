"""The pre-registered forward test of the 2026-08-31 cuts, and its pause rule.

These pin the parts that make the rule a rule rather than a preference: it acts
on a fixed schedule instead of continuously, it needs a real sample per model,
it never unpauses on its own, and the pause it writes is one the SCORER can see.
"""

from __future__ import annotations

import pytest

import config
from tracking import threshold_review as tr


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

def test_a_losing_model_with_enough_bets_is_paused():
    conn = _Conn(_slate(("mlb_moneyline", 200, -12.0), ("mlb_over_under", 60, 3.0)))
    out = tr.run_review(conn)
    assert [p["model_id"] for p in out["paused"]] == ["mlb_moneyline"]
    assert conn.committed


def test_a_losing_model_with_too_few_bets_is_left_alone():
    """49 bets of -40% is a number, not a result. The floor is what stops the
    rule from killing a model on a bad fortnight."""
    conn = _Conn(_slate(("mlb_moneyline", 251, 1.0), ("mlb_over_under", 49, -40.0)))
    out = tr.run_review(conn)
    assert out["paused"] == []


def test_the_boundary_is_exactly_minus_five_percent():
    """-5.0% is kept, -5.1% is paused. An off-by-one here quietly changes the
    rule that was agreed before the data arrived."""
    conn = _Conn(_slate(("mlb_moneyline", 130, -5.0), ("mlb_over_under", 130, -5.1)))
    out = tr.run_review(conn)
    assert [p["model_id"] for p in out["paused"]] == ["mlb_over_under"]


def test_a_profitable_model_is_never_touched():
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

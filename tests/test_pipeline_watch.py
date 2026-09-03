"""
The pipeline watch runs on the worker, not as a scheduled agent.

WHY THIS EXISTS
---------------
Sentinel read the database through the Supabase MCP. Routine sessions carry no
`mcp__*` entry in their permitted-tool list, so every read raised a permission
prompt. Unattended that killed two consecutive daily runs in REQUIRES_ACTION
(`mcp__Railway__get-logs` 2026-09-01, `mcp__Supabase__list_tables` 2026-09-02);
attended it paged a person every morning until they asked for it to stop.

So the watch moved to the worker, where DATABASE_URL and the Discord webhook
already are and nothing prompts. These tests pin the parts that made the agent
version fail: that it runs at all, that it reports even when clean, and that
one broken query cannot take the run down with it.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

import config
from tracking import pipeline_watch as pw

ROOT = Path(__file__).parent.parent


# ── it is scheduled, and it belongs to one service ──────────────────────────

def test_the_watch_has_a_schedule():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    ids = re.findall(r'^\s*id="([^"]+)"', src, re.M)
    assert "pipeline_watch" in ids, (
        "a watch with no schedule is exactly the agent problem again")


def test_the_watch_belongs_to_the_pipeline_service():
    """Two services posting the same report would double every morning post."""
    import importlib

    import scheduler
    importlib.reload(scheduler)
    assert "pipeline_watch" in scheduler._PIPELINE_JOBS


def test_the_scheduler_never_dies_on_a_watch_failure():
    import inspect

    import scheduler

    src = inspect.getsource(scheduler.run_pipeline_watch)
    assert "except Exception" in src
    assert "conn.close()" in src, "the connection must be released on failure"


# ── the rules, each pure so it can be checked without a database ────────────

def test_a_pass_with_no_finish_is_reported_without_over_reading_it():
    """'aborted' means the pass died OR its finish-ledger call failed. The
    contract says not to over-read that, so the wording must not pick one."""
    out = pw.findings_from_passes([("2026-09-03T06:00", None, 28, 0)])
    assert len(out) == 1
    assert "never recorded a finish" in out[0]
    assert "died, or its finish-ledger call failed" in out[0]


def test_a_pass_with_failed_steps_is_reported():
    out = pw.findings_from_passes([("2026-09-03T06:00", 11.2, 28, 3)])
    assert len(out) == 1 and "3 failed step(s) of 28" in out[0]


def test_a_clean_pass_produces_no_finding():
    assert pw.findings_from_passes([("2026-09-03T06:00", 11.2, 28, 0)]) == []


def test_every_not_ok_health_check_is_reported():
    out = pw.findings_from_checks([("savant_freshness", "CRIT", "STALE", "4 months")])
    assert len(out) == 1
    assert "savant_freshness" in out[0] and "CRIT" in out[0]


def test_burn_is_judged_against_the_cap_not_against_yesterday():
    """A day-on-day comparison would fire on any quiet day; the account has a
    monthly reset and a 60k daily cap, so the cap is the thing that matters."""
    quiet = pw.findings_from_burn([("pregame_poller", 1000, 45000, 0)])
    assert quiet == []
    loud = pw.findings_from_burn([("pregame_poller", 9000, 58000, 0)])
    assert len(loud) == 1 and "58,000" in loud[0]


def test_failed_api_calls_are_reported_even_when_burn_is_low():
    out = pw.findings_from_burn([("pregame_poller", 10, 100, 7)])
    assert any("7 failed call(s)" in f for f in out)


@pytest.mark.parametrize("credits", [None, "n/a", "QUERY FAILED", object()])
def test_burn_survives_a_non_numeric_credits_column(credits):
    """`_rows` returns ('QUERY FAILED', msg) shaped rows on schema drift, and
    a NUMERIC column arrives as Decimal or str depending on the driver. A watch
    that raises inside its own rule reports nothing at all that morning.

    Parametrised because the first version of this test passed None, which
    `int(None or 0)` swallows without ever reaching the except — it proved
    nothing. Mutation-checked by making the except re-raise.
    """
    assert pw.findings_from_burn([("src", 1, credits, 0)]) == []


# ── it reports even when there is nothing to say ────────────────────────────

class _Conn:
    """Answers each rule's query the way a healthy database would.

    An aggregate like `SELECT max(run_date)` always returns exactly ONE row
    (holding NULL when empty) — it never returns zero rows. The first version
    of this fake returned [] for everything, which made a "clean" run report a
    missing sweeps table and hid the real assertion. A fake that cannot be
    clean cannot test the clean path.
    """

    def __init__(self, rows=None, raises=False, fresh=True):
        self._rows, self._raises, self._fresh = rows, raises, fresh
        self.rolled_back = 0
        self.committed = 0
        self.writes: list[tuple] = []
        self._last = ""

    def execute(self, sql, params=()):
        if self._raises:
            raise RuntimeError('relation "model_calibration_sweeps" does not exist')
        self._last = sql
        if "INSERT INTO push_sent" in sql:
            self.writes.append(params)
        return self

    def commit(self):
        self.committed += 1

    def fetchall(self):
        if self._rows is not None:
            return self._rows
        today = date.today().isoformat()
        if "model_calibration_sweeps" in self._last:
            return [(today if self._fresh else "2020-01-01",)]
        if "player_savant_stats" in self._last:
            return [(today if self._fresh else "2020-01-01", 2)]
        return []

    def rollback(self):
        self.rolled_back += 1


def test_a_clean_run_still_posts(monkeypatch):
    """Patches the POST, not _announce.

    The first version stubbed _announce itself, so it could only prove the
    caller reached it -- an early `return` inside _announce for the clean case
    passed that test happily. Mutation-checked: adding that early return now
    fails here, which is the whole property ("report every run, even a clean
    one"), and the exact way the agent version failed unnoticed.
    """
    posts = []
    monkeypatch.setattr("tracking.discord_notifier._post",
                        lambda url, payload: posts.append(payload))
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_OPS", "https://example.invalid/hook")
    monkeypatch.setattr("scripts.pipeline_report.collect", lambda c, h: {})

    out = pw.run_watch(_Conn(), hours=24)
    assert out["status"] == "ok" and out["findings"] == []
    assert len(posts) == 1, "a silent clean run looks exactly like a stopped watch"
    assert "clean" in posts[0]["embeds"][0]["title"].lower()


def test_a_run_with_findings_posts_them(monkeypatch):
    posts = []
    monkeypatch.setattr("tracking.discord_notifier._post",
                        lambda url, payload: posts.append(payload))
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_OPS", "https://example.invalid/hook")
    monkeypatch.setattr("scripts.pipeline_report.collect", lambda c, h: {
        "recent_passes": [("2026-09-03T06:00", None, 28, 0)]})

    out = pw.run_watch(_Conn(), hours=24)
    assert out["findings"], "a pass with no finish must be a finding"
    assert "never recorded a finish" in posts[0]["embeds"][0]["description"]


def test_a_missing_webhook_escalates_rather_than_vanishing(monkeypatch):
    """With no webhook the report must still reach the logs at CRITICAL, or a
    misconfigured worker is silent in exactly the way this move was meant to
    end."""
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_OPS", "")
    logged = []
    monkeypatch.setattr(pw.logger, "critical", lambda m: logged.append(m))
    pw._announce({"status": "ok", "hours": 24, "findings": [], "passes": 1,
                  "picks": 0})
    assert logged and "Nothing to flag" in logged[0]


def test_a_failed_query_rolls_back_and_does_not_sink_the_run(monkeypatch):
    """psycopg aborts the transaction on a failed statement, so without the
    rollback the first bad query would poison every rule after it."""
    monkeypatch.setattr(pw, "_announce", lambda s: None)
    monkeypatch.setattr("scripts.pipeline_report.collect", lambda c, h: {})
    conn = _Conn(raises=True)
    out = pw.run_watch(conn, hours=24)
    assert out["status"] == "ok"
    assert conn.rolled_back >= 1


def test_a_stale_sweep_date_is_reported():
    """Distinct from the missing-table case: the table exists and has rows,
    they are just old. Added after a mutation that disabled exactly this branch
    passed the whole file — the missing-table test covered the other branch."""
    out = pw._stale_weeklies(_Conn(fresh=False), today=date(2026, 9, 3))
    assert any("ModelCalibration last swept 2020-01-01" in f for f in out)
    assert any("Savant for 2026 last pulled 2020-01-01" in f for f in out)


def test_a_fresh_sweep_and_savant_produce_no_finding():
    assert pw._stale_weeklies(_Conn(fresh=True), today=date.today()) == []


def test_savant_with_only_one_player_type_is_stale_even_when_dated_today():
    """A season with pitchers and no batters reads as populated to any check
    that only asks for the newest row — which is exactly what 2026 was."""
    conn = _Conn(rows=[(date.today().isoformat(), 1)])
    out = pw._stale_weeklies(conn, today=date.today())
    assert any("1 player type(s)" in f for f in out)


def test_a_missing_sweeps_table_is_reported_not_swallowed():
    conn = _Conn(raises=True)
    out = pw._stale_weeklies(conn, today=date(2026, 9, 3))
    assert any("never completed" in f for f in out)


def test_the_kill_switch_works(monkeypatch):
    monkeypatch.setenv("RUN_PIPELINE_WATCH", "0")
    assert pw.run_watch(_Conn())["status"] == "disabled"


# ── the contract says where it runs ─────────────────────────────────────────

def test_the_contract_records_that_the_watch_left_the_agent():
    text = (ROOT / "docs" / "agents_contract.md").read_text(encoding="utf-8")
    assert "tracking/pipeline_watch.py" in text, (
        "a reader looking for Sentinel's morning report must land on where it "
        "actually runs now")


# ── the post has to be checkable afterwards ─────────────────────────────────
#
# CLAUDE.md §7: "check `push_sent` before believing a notifier ever worked --
# nothing is ledgered unless a POST confirmed, so a `kind` with zero rows means
# it has NEVER succeeded." Without a ledger row the watch is unverifiable: it
# either posted or it did not and no query could tell you which, which is the
# same blindness moving off the agent was meant to end.

def _wire(monkeypatch, post_result="msg-1"):
    monkeypatch.setattr("tracking.discord_notifier._post",
                        lambda url, payload: post_result)
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_OPS", "https://example.invalid/hook")
    monkeypatch.setattr("scripts.pipeline_report.collect", lambda c, h: {})


def test_a_confirmed_post_is_ledgered_so_the_run_can_be_verified(monkeypatch):
    _wire(monkeypatch)
    conn = _Conn()
    out = pw.run_watch(conn, hours=24, today=date(2026, 9, 3))
    assert out["posted"] is True
    assert len(conn.writes) == 1, "a confirmed post must leave exactly one row"
    assert conn.writes[0][0] == "pipeline_watch:2026-09-03"
    assert conn.committed >= 1, "an uncommitted ledger row is not a ledger row"


def test_an_unconfirmed_post_is_never_ledgered(monkeypatch):
    """`_post` returns None on failure. Ledgering anyway would make a kind that
    has never once succeeded look healthy — the precise trap §7 describes."""
    _wire(monkeypatch, post_result=None)
    conn = _Conn()
    out = pw.run_watch(conn, hours=24, today=date(2026, 9, 3))
    assert out["posted"] is False
    assert conn.writes == []


def test_a_missing_webhook_is_not_ledgered_either(monkeypatch):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_OPS", "")
    monkeypatch.setattr("scripts.pipeline_report.collect", lambda c, h: {})
    conn = _Conn()
    assert pw.run_watch(conn, hours=24, today=date(2026, 9, 3))["posted"] is False
    assert conn.writes == []


def test_the_ledger_is_one_row_per_day_so_a_retry_cannot_double_count(monkeypatch):
    _wire(monkeypatch)
    conn = _Conn()
    pw.run_watch(conn, hours=24, today=date(2026, 9, 3))
    assert "ON CONFLICT (lock_key, kind) DO NOTHING" in conn._last


def test_a_failed_ledger_does_not_lose_the_report(monkeypatch):
    """The post already went out; a ledger failure must be reported, not raised
    over the top of a Discord message that a person can see."""
    _wire(monkeypatch)

    class _LedgerBoom(_Conn):
        def execute(self, sql, params=()):
            if "INSERT INTO push_sent" in sql:
                raise RuntimeError("ledger unavailable")
            return super().execute(sql, params)

    conn = _LedgerBoom()
    out = pw.run_watch(conn, hours=24, today=date(2026, 9, 3))
    assert out["status"] == "ok" and out["posted"] is False
    assert conn.rolled_back >= 1


"""A recap that a later settlement invalidated is restated, on both surfaces.

2026-09-10. The 6am run posted the 2026-09-09 recap MLB-only at 06:02; the
three NFL props settled at 07:24 against a ledgered date and nothing
re-posted. Measured the same morning: 2026-09-04 (2 NCAAF settled three days
late) and 2026-09-05 (4 NCAAF, 2 UFC) had the same shape. The remedy was a
hand-run job each time.

Now every settle pass scans the last week's published recaps for a pick that
settled AFTER the recap's published_at, and re-posts Discord then X labelled
"restated", ledgered per correction on the published_at being corrected.

THE TRIGGER IS LATE SETTLEMENT, NOT A COUNT DIFFERENCE: every daily snapshot
from 09-01 to 09-08 disagrees with today's count because the recap query
applies the CURRENT cuts and those moved. A count trigger would have restated
eight days for nothing.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import discord_notifier as dn  # noqa: E402
from tracking import x_publisher as xp  # noqa: E402

ROOT = Path(__file__).parent.parent
PUB = datetime(2026, 9, 10, 10, 2, 22, tzinfo=timezone.utc)


class _Conn:
    """Answers the snapshot scan with `snaps` and the late-settlement query
    with `late_by_date`; records every SQL it saw."""

    def __init__(self, snaps, late_by_date):
        self.snaps, self.late_by_date, self.sql = snaps, late_by_date, []

    def execute(self, sql, params=()):
        self.sql.append((sql, params))
        conn = self

        class _R:
            def fetchall(_):
                if "FROM results_snapshots" in sql:
                    return conn.snaps
                if "p.settled_at > %s" in sql:
                    return [("NFL",)] * conn.late_by_date.get(params[0], 0)
                return []

            def fetchone(_):
                return None
        return _R()

    def close(self):
        pass


# ── the scan ─────────────────────────────────────────────────────────────────

def test_a_recap_with_a_late_settlement_is_due():
    conn = _Conn([("2026-09-09", PUB, 7)], {"2026-09-09": 3})
    due = dn.recaps_needing_restatement(conn, through="2026-09-10")
    assert due == [{"game_date": "2026-09-09", "published_at": PUB,
                    "settled": 7, "late": 3}]


def test_a_recap_whose_count_merely_drifted_is_not_due():
    """Nothing settled after it was posted: not a correction, whatever the
    recap query returns today."""
    conn = _Conn([("2026-09-01", PUB, 56)], {"2026-09-01": 0})
    assert dn.recaps_needing_restatement(conn, through="2026-09-10") == []


def test_the_scan_is_bounded_to_finished_days_the_lookback_and_the_floor():
    conn = _Conn([], {})
    dn.recaps_needing_restatement(conn, through="2026-09-20")
    sql, params = conn.sql[0]
    assert "game_date < %s" in sql and "game_date >= %s" in sql
    assert params[0] == "2026-09-20"
    assert params[1] == "2026-09-13", "lookback of 7 days from `through`"
    conn = _Conn([], {})
    dn.recaps_needing_restatement(conn, through="2026-09-11")
    assert conn.sql[0][1][1] == dn.RESULTS_RESTATE_FROM, (
        "recaps published before the floor are never restated automatically")


def test_the_late_query_is_the_recap_universe_plus_settled_after():
    """The late count must be taken over the SAME universe the recap counts,
    or a pick outside the cut could trigger a restatement it never appears in."""
    conn = _Conn([("2026-09-09", PUB, 7)], {"2026-09-09": 1})
    dn.recaps_needing_restatement(conn, through="2026-09-10")
    late_sql, late_params = conn.sql[1]
    assert late_sql.startswith(dn._SETTLED_SQL.format(window="= %s"))
    assert late_sql.rstrip().endswith("AND p.settled_at > %s")
    assert late_params == ("2026-09-09", PUB)


# ── the key and the note ─────────────────────────────────────────────────────

def test_the_key_carries_the_published_at_being_corrected():
    """One key per correction GENERATION: a second late batch (new
    published_at after the first restatement) fires again; a repeat pass over
    the same batch does not."""
    k = dn.restate_lock_key("discord_results_restate", "2026-09-09", PUB)
    assert k == "discord_results_restate:2026-09-09:2026-09-10T10:02:22+00:00"
    assert dn.restate_lock_key("x_results_restate", "2026-09-09", PUB).endswith(
        k.split(":", 1)[1]), "both surfaces share the key shape"


def test_the_note_says_what_settled_late_and_both_counts():
    n = dn.results_restate_note(3, 7, 10)
    assert n.startswith("Restated.")
    assert "3 picks settled after" in n
    assert "7 settled then, 10 now" in n
    assert "Same picks, same results" in n
    assert "1 pick settled" in dn.results_restate_note(1, 7, 8)


# ── the notifiers ────────────────────────────────────────────────────────────

def test_the_discord_notifier_resolves_restate_true_and_no_ops_without_a_late_pick(monkeypatch):
    conn = _Conn([("2026-01-01", PUB, 7)], {"2026-01-01": 0})
    monkeypatch.setattr(dn, "get_connection", lambda *a, **k: conn)
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_RESULTS", "https://x", raising=False)
    assert dn.notify_discord_results(game_date="2026-01-01", restate=True) == 0


def test_the_tweet_header_says_restated():
    recap = {"wins": 5, "losses": 5, "pushes": 0, "units": -0.537, "risked": 11.16,
             "by_sport": []}
    plain = xp.render_results(recap, "2026-09-09")
    again = xp.render_results(recap, "2026-09-09", restate=True)
    assert again.startswith("\U0001F4CA Sep 9 results (restated): 5-5")
    assert plain != again, "a restated tweet must not be a duplicate of the original"


def test_the_x_notifier_ledgers_the_restate_under_its_own_kind_and_key():
    import inspect
    src = inspect.getsource(xp.notify_x_results)
    assert 'kind = "x_results_restate" if restate else "x_results"' in src
    assert 'restate_lock_key(kind, game_date, restate["published_at"])' in src
    assert "_ledger(conn, lock, kind, tweet_id)" in src
    assert "restate=bool(restate)" in src, "the tweet must say it is restated"


def test_settle_restates_on_every_pass_after_both_ordinary_posts():
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    fn = src[src.index("def step_settle("):src.index("\ndef ", src.index("def step_settle(") + 10)]
    assert "restate_published_recaps()" in fn
    assert fn.index("notify_x_results(settle_date)") < fn.index("restate_published_recaps()")
    assert "DISCORD_RESULTS_RESTATE_DATES" not in src, "the hard-coded date list is gone"


def test_the_restatement_never_fails_settle():
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    fn = src[src.index("def step_settle("):src.index("\ndef ", src.index("def step_settle(") + 10)]
    tail = fn[fn.index("restate_published_recaps"):]
    assert "except Exception" in tail and "return True" in tail


# ── the nflverse fetch retry ─────────────────────────────────────────────────

def _resp(status, text="csv"):
    class R:
        status_code = status

        def raise_for_status(self):
            if status >= 400:
                raise RuntimeError(f"HTTP {status}")
        text_ = text
    r = R(); r.text = text
    return r


def test_a_transient_403_is_retried_and_the_second_answer_is_used(monkeypatch):
    from data.ingestors import nfl_player_stats_ingestor as ing
    answers = iter([_resp(403), _resp(200, "ok")])
    slept = []
    monkeypatch.setattr(ing.requests, "get", lambda *a, **k: next(answers))
    monkeypatch.setattr(ing.time, "sleep", slept.append)
    assert ing._fetch_season_csv(2026) == "ok"
    assert slept == [5]


def test_a_404_is_an_answer_not_a_retry(monkeypatch):
    from data.ingestors import nfl_player_stats_ingestor as ing
    calls = []
    monkeypatch.setattr(ing.requests, "get", lambda *a, **k: calls.append(1) or _resp(404))
    monkeypatch.setattr(ing.time, "sleep", lambda s: pytest.fail("slept on a 404"))
    assert ing._fetch_season_csv(2026) is None
    assert calls == [1]


def test_a_persistent_403_still_raises_after_the_last_attempt(monkeypatch):
    from data.ingestors import nfl_player_stats_ingestor as ing
    calls = []
    monkeypatch.setattr(ing.requests, "get", lambda *a, **k: calls.append(1) or _resp(403))
    monkeypatch.setattr(ing.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        ing._fetch_season_csv(2026)
    assert len(calls) == ing._FETCH_ATTEMPTS

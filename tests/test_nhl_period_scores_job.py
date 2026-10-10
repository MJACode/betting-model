"""Worker job for the NHL period-score importer.

`nhl_period_scores` runs data.ingestors.nhl_period_scores_api, which reads the
NHL's free score feed and writes only `nhl_period_scores`. No args beyond a
date range is a count; `apply` writes. A malformed request fails in the
validator, before the module is imported. A date the feed cannot be read
fails the job, so the worker retries it.
"""
from __future__ import annotations

import ast
import inspect
import json

import pytest
import requests

import config
import tracking.job_queue as jq


def test_the_job_is_on_the_allowlist():
    assert "nhl_period_scores" in jq.JOBS
    fn, validate = jq.JOBS["nhl_period_scores"]
    assert fn is jq._job_nhl_period_scores
    assert validate is jq._validate_nhl_period_scores


def test_the_runner_imports_the_importer_and_never_shells_out():
    src = inspect.getsource(jq._job_nhl_period_scores)
    assert "data.ingestors.nhl_period_scores_api" in src
    assert "_run_script_main" in src
    assert "subprocess" not in src


def test_a_date_with_no_apply_is_a_count():
    cleaned = jq._validate_nhl_period_scores({"first": "2026-09-30"})
    assert cleaned == {"first": "2026-09-30", "last": None, "recent": None, "apply": False}


def test_apply_must_be_a_real_boolean():
    assert jq._validate_nhl_period_scores({"first": "2026-09-30", "apply": True})["apply"] is True
    with pytest.raises(ValueError):
        jq._validate_nhl_period_scores({"first": "2026-09-30", "apply": "yes"})


@pytest.mark.parametrize("args", [
    {},                                              # neither
    {"first": "2026-09-30", "recent": 3},            # both
    {"first": "30/09/2026"},                         # not a date
    {"first": "2026-10-05", "last": "2026-10-01"},   # reversed
    {"recent": 0},
    {"recent": 31},
    {"recent": "3"},
    {"recent": True},
    {"first": "2026-09-30", "argv": "--apply"},      # not a shell
])
def test_a_malformed_request_is_refused(args):
    with pytest.raises(ValueError):
        jq._validate_nhl_period_scores(args)


def _argv(monkeypatch, args: dict) -> list[str]:
    seen = {}

    def fake(mod, argv):
        seen["mod"], seen["argv"] = mod, list(argv)
        return "{}"
    monkeypatch.setattr(jq, "_run_script_main", fake)
    jq._job_nhl_period_scores(**jq._validate_nhl_period_scores(args))
    assert seen["mod"] == "data.ingestors.nhl_period_scores_api"
    return seen["argv"]


def test_a_count_does_not_pass_apply(monkeypatch):
    assert _argv(monkeypatch, {"first": "2026-09-30"}) == ["--from", "2026-09-30"]


def test_a_fill_passes_its_range_and_apply(monkeypatch):
    assert _argv(monkeypatch, {"first": "2026-09-30", "last": "2026-10-09", "apply": True}) == [
        "--from", "2026-09-30", "--to", "2026-10-09", "--apply"]


def test_a_top_up_passes_recent(monkeypatch):
    assert _argv(monkeypatch, {"recent": 3, "apply": True}) == ["--recent", "3", "--apply"]


def test_the_argv_parses_in_the_importer(monkeypatch):
    """The flags the job builds are the flags the importer's own parser takes."""
    import data.ingestors.nhl_period_scores_api as imp
    seen = {}
    monkeypatch.setattr(imp, "run", lambda first, last, apply: seen.update(
        first=first, last=last, apply=apply) or {})
    monkeypatch.setattr("sys.argv", ["x", *_argv(monkeypatch, {
        "first": "2026-09-30", "last": "2026-10-09", "apply": True})])
    imp.main()
    assert seen == {"first": "2026-09-30", "last": "2026-10-09", "apply": True}


def test_the_declared_fill_is_a_write_from_the_season_start():
    entries = json.loads((config.ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    fills = [e for e in entries if e["job_type"] == "nhl_period_scores"]
    assert fills, "the 2026-27 fill is declared"
    cleaned = jq._validate_nhl_period_scores(fills[0]["args"])
    assert cleaned["apply"] is True and cleaned["first"] <= "2026-10-01"


# ── A feed that cannot be read fails the job; a game missing from a feed that was read does not ──
#
# The worker marks a job done when it returns and never runs a done job again,
# and nothing tops the table up daily. So an outage during the one-time fill
# must fail the job (the worker retries it), not finish it with every game
# counted as missing from the feed.

class _Cur:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _Conn:
    """Scored games with nothing stored for them yet; records what is written."""

    def __init__(self, games):
        self.games, self.written = games, []

    def execute(self, sql, params):
        return _Cur(self.games if "nhl_team_game_log" in sql else [])

    def executemany(self, sql, rows):
        self.written += list(rows)

    def commit(self):
        pass

    def close(self):
        pass


class _Ok:
    status_code = 200

    def __init__(self, games):
        self.games = games

    def json(self):
        return {"games": self.games}


# G1 on 2026-10-08, home won 1-0 with a first-period goal; G2 on 2026-10-10.
_G1 = (2026020001, "G1", "2026-10-08", 2027, 1, 0)
_G2 = (2026020002, "G2", "2026-10-10", 2027, 2, 1)
_G1_FEED = {"id": 2026020001, "gameState": "OFF", "homeTeam": {"abbrev": "VGK"},
            "awayTeam": {"abbrev": "TOR"}, "goals": [{"period": 1, "teamAbbrev": "VGK"}]}


def _fill(monkeypatch, games, get):
    import data.ingestors.nhl_period_scores_api as imp
    conn = _Conn(games)
    monkeypatch.setattr(imp, "get_connection", lambda: conn)
    monkeypatch.setattr(imp.requests, "get", get)
    monkeypatch.setattr(imp.time, "sleep", lambda s: None)
    return conn, lambda: jq._job_nhl_period_scores(
        **jq._validate_nhl_period_scores({"first": "2026-10-08", "apply": True}))


def test_a_feed_that_cannot_be_read_fails_the_job_so_the_worker_retries(monkeypatch):
    calls = []

    def down(url, timeout):
        calls.append(url)
        raise requests.ConnectionError("unreachable")
    conn, job = _fill(monkeypatch, [_G1], down)
    with pytest.raises(RuntimeError, match="could not be read for 2 date"):
        job()
    assert len(calls) == 8            # four tries for the game's date, four for the day before
    assert conn.written == []


def test_what_was_read_is_written_before_the_job_fails(monkeypatch):
    def half_down(url, timeout):
        if "2026-10-10" in url:
            raise requests.ConnectionError("unreachable")
        return _Ok([_G1_FEED] if "2026-10-08" in url else [])
    conn, job = _fill(monkeypatch, [_G1, _G2], half_down)
    with pytest.raises(RuntimeError, match=r"\['2026-10-10'\]"):
        job()
    assert [r[0] for r in conn.written] == ["G1"]    # a retry then reads only G2


def test_a_game_missing_from_a_feed_that_was_read_is_counted_and_the_job_finishes(monkeypatch):
    conn, job = _fill(monkeypatch, [_G1], lambda url, timeout: _Ok([]))
    out = ast.literal_eval(job().strip())
    assert out["not_in_feed"] == 1 and out["feed_failed"] == [] and out["written"] == 0
    assert conn.written == []

"""Worker job for the NHL derivative-totals buyer.

The game-line job (nhl_odds_history) refuses a ceiling above 200,000 credits.
This type does not have a ceiling: it runs data.ingestors.nhl_derivative_odds_history,
whose --apply buys every remaining scored game and whose default is a dry run.
A malformed request fails in the validator, before the module is imported and
before any Odds API call.
"""
from __future__ import annotations

import inspect

import pytest

import tracking.job_queue as jq


def test_the_job_is_on_the_allowlist():
    assert "nhl_derivative_odds_history" in jq.JOBS
    assert "command" not in jq.JOBS
    fn, validate = jq.JOBS["nhl_derivative_odds_history"]
    assert fn is jq._job_nhl_derivative_odds_history
    assert validate is jq._validate_nhl_derivative_odds_history


def test_the_runner_calls_the_buyer_module_and_not_a_shell():
    src = inspect.getsource(jq._job_nhl_derivative_odds_history)
    assert "data.ingestors.nhl_derivative_odds_history" in src
    assert "_run_script_main" in src
    assert "subprocess" not in src
    assert "plan_credit_budget" not in src
    assert "max_credits" not in src
    assert "reserve" not in src
    assert "PAUSED_MODELS" not in src
    assert "ACTION_THRESHOLDS" not in src
    helper = inspect.getsource(jq._run_script_main)
    assert "importlib.import_module" in helper
    assert "subprocess" not in helper


def test_empty_args_are_a_dry_run():
    cleaned = jq._validate_nhl_derivative_odds_history({})
    assert cleaned == {"apply": False, "probe": None, "seasons": None}
    assert "max_credits" not in cleaned
    assert "credit_cap" not in cleaned
    assert "reserve_days" not in cleaned


def test_apply_is_explicit_and_carries_no_ceiling():
    cleaned = jq._validate_nhl_derivative_odds_history({"apply": True})
    assert cleaned["apply"] is True
    assert cleaned["probe"] is None
    assert set(cleaned) == {"apply", "probe", "seasons"}
    cleaned = jq._validate_nhl_derivative_odds_history({
        "apply": True, "seasons": [2024, 2027]})
    assert cleaned["seasons"] == (2024, 2027)


def test_a_credit_ceiling_is_a_malformed_request(monkeypatch):
    """The validator raises before enqueue touches the database and before
    any Odds API call. max_credits is what nhl_odds_history requires; here
    it is refused."""
    def _api(*_a, **_k):
        raise AssertionError("Odds API was called")

    def _run(*_a, **_k):
        raise AssertionError("the buyer was imported")

    monkeypatch.setattr(jq.requests, "get", _api) if hasattr(jq, "requests") else None
    monkeypatch.setattr("requests.get", _api)
    monkeypatch.setattr(jq, "_run_script_main", _run)

    class _Conn:
        def execute(self, *_a, **_k):
            raise AssertionError("the database was touched")

    for args in (
        {"max_credits": 150_000},
        {"apply": True, "credit_cap": 1},
        {"reserve_days": 0},
        {"ceiling": 150_000, "apply": True},
        {"command": "curl https://api.the-odds-api.com"},
        {"apply": "yes"},
        {"probe": "not-a-date"},
        {"apply": True, "probe": "2026-01-15"},
        {"seasons": [2027, 2024]},
        {"seasons": "2024"},
    ):
        with pytest.raises(ValueError):
            jq.enqueue(_Conn(), "nhl_derivative_odds_history", args)


def test_dry_run_argv_has_no_apply_and_no_ceiling(monkeypatch):
    seen = {}

    def capture(mod, argv):
        seen["mod"] = mod
        seen["argv"] = list(argv)
        return "2 dates / 3 games to buy\nno credit ceiling"

    monkeypatch.setattr(jq, "_run_script_main", capture)
    out = jq._job_nhl_derivative_odds_history(apply=False, probe=None, seasons=None)
    assert seen["mod"] == "data.ingestors.nhl_derivative_odds_history"
    assert seen["argv"] == []
    assert "--apply" not in out
    assert "no credit ceiling" in out


def test_apply_argv_is_only_apply(monkeypatch):
    seen = {}

    def capture(mod, argv):
        seen["mod"] = mod
        seen["argv"] = list(argv)
        return "bought 1 games"

    monkeypatch.setattr(jq, "_run_script_main", capture)
    jq._job_nhl_derivative_odds_history(apply=True, probe=None, seasons=None)
    assert seen["argv"] == ["--apply"]
    assert "--max-credits" not in seen["argv"]
    assert "--reserve-days" not in seen["argv"]

    jq._job_nhl_derivative_odds_history(
        apply=True, probe=None, seasons=(2024, 2027))
    assert seen["argv"] == ["--seasons", "2024", "2027", "--apply"]


def test_probe_argv_does_not_apply(monkeypatch):
    seen = {}

    def capture(mod, argv):
        seen["argv"] = list(argv)
        return "MEASURED"

    monkeypatch.setattr(jq, "_run_script_main", capture)
    cleaned = jq._validate_nhl_derivative_odds_history({"probe": "2026-01-15"})
    jq._job_nhl_derivative_odds_history(**cleaned)
    assert seen["argv"] == ["--probe", "2026-01-15"]
    assert "--apply" not in seen["argv"]

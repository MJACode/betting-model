"""Worker job that runs the NHL backtests and labs where DATABASE_URL lives.

The job is measure-only. These tests pin the three things that make it safe to
leave on the allowlist: it runs a named module rather than a command, every
module it can run writes no database row, and a script's file-writing flags
(--dump, --cache) cannot be passed.
"""
from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

import pytest

import tracking.job_queue as jq

ROOT = Path(__file__).resolve().parent.parent
WRITES = re.compile(r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|TRUNCATE)\b|\.commit\(",
                    re.IGNORECASE)


def test_the_job_is_on_the_allowlist():
    fn, validate = jq.JOBS["nhl_research"]
    assert fn is jq._job_nhl_research
    assert validate is jq._validate_nhl_research


def test_the_runner_imports_a_module_and_never_shells_out():
    src = inspect.getsource(jq._job_nhl_research)
    assert "_run_script_main" in src
    assert "subprocess" not in src and "os.system" not in src


@pytest.mark.parametrize("script", sorted(jq.NHL_RESEARCH_SCRIPTS))
def test_every_runnable_module_writes_no_database_row(script):
    module, _ = jq.NHL_RESEARCH_SCRIPTS[script]
    path = ROOT / (module.replace(".", "/") + ".py")
    src = path.read_text(encoding="utf-8")
    hits = [m.group(0) for m in WRITES.finditer(src)]
    assert not hits, f"{module} writes ({hits}); it cannot be run by a measure-only job"


@pytest.mark.parametrize("script", sorted(jq.NHL_RESEARCH_SCRIPTS))
def test_every_runnable_module_has_a_main(script):
    module, _ = jq.NHL_RESEARCH_SCRIPTS[script]
    assert callable(getattr(importlib.import_module(module), "main", None))


def test_no_file_writing_flag_is_an_argument():
    for script, (_, flags) in jq.NHL_RESEARCH_SCRIPTS.items():
        cli = {flag for flag, _ in flags.values()}
        assert not cli & {"--dump", "--cache"}, script


def test_an_unknown_script_is_refused():
    with pytest.raises(ValueError, match="script must be one of"):
        jq._validate_nhl_research({"script": "scripts.void_picks"})


def test_a_dump_argument_is_refused():
    with pytest.raises(ValueError, match="takes"):
        jq._validate_nhl_research({"script": "nhl_prop_backtest", "args": {"dump": "/tmp"}})


def test_a_model_must_be_a_real_spec():
    with pytest.raises(ValueError, match="model must be one of"):
        jq._validate_nhl_research({"script": "nhl_prop_backtest", "args": {"model": "nhl_moneyline"}})
    cleaned = jq._validate_nhl_research({"script": "nhl_prop_backtest",
                                         "args": {"model": "nhl_prop_saves"}})
    assert cleaned["args"] == {"model": "nhl_prop_saves"}


def test_a_season_must_be_a_priced_one():
    with pytest.raises(ValueError, match="season must be one of"):
        jq._validate_nhl_research({"script": "nhl_threeway_lab", "args": {"season": 2019}})
    cleaned = jq._validate_nhl_research({"script": "nhl_threeway_lab", "args": {"season": 2025}})
    assert cleaned["args"] == {"season": "2025"}


def test_an_unknown_top_level_key_is_refused():
    with pytest.raises(ValueError, match="unknown keys"):
        jq._validate_nhl_research({"script": "nhl_totals_lab", "argv": ["--cache", "/tmp"]})


def test_the_timeout_is_bounded_and_defaults_to_thirty_minutes():
    assert jq._validate_nhl_research({"script": "nhl_totals_lab"})["statement_timeout_ms"] == 1_800_000
    with pytest.raises(ValueError, match="statement_timeout_ms"):
        jq._validate_nhl_research({"script": "nhl_totals_lab", "statement_timeout_ms": 10})


def test_the_job_passes_flags_and_restores_the_timeout(monkeypatch):
    seen = {}

    def fake(module, argv):
        import os
        seen.update(module=module, argv=argv, timeout=os.environ.get("DB_STATEMENT_TIMEOUT_MS"))
        return "table\nlast line\n"

    monkeypatch.setattr(jq, "_run_script_main", fake)
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "120000")
    kw = jq._validate_nhl_research({"script": "nhl_prop_backtest", "args": {"model": "nhl_prop_assists"},
                                    "statement_timeout_ms": 900_000})
    out = jq._job_nhl_research(**kw)
    assert seen == {"module": "scripts.nhl_prop_backtest",
                    "argv": ["--model", "nhl_prop_assists"], "timeout": "900000"}
    import os
    assert os.environ["DB_STATEMENT_TIMEOUT_MS"] == "120000"
    assert out["stdout"] == "table\nlast line"
    assert out["summary"].endswith("last line")
    assert out["truncated"] is False


def test_the_artifact_grade_names_the_rule_production_runs():
    """The regulation model decides on its own probability (config.MODELS_ON_OWN_PROBABILITY,
    PR #876); the grade called its corrected-probability row 'AS IT RUNS TODAY' until 2026-10-08."""
    import config
    import scripts.nhl_live_artifact_grade as g
    for mid in ("nhl_moneyline", "nhl_moneyline_regulation"):
        cal, raw = g._labels(mid)
        today = raw if mid in config.MODELS_ON_OWN_PROBABILITY else cal
        assert "AS IT RUNS TODAY" in today
        assert "AS IT RUNS TODAY" not in (cal if today is raw else raw)

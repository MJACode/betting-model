"""The nba_injury_report worker job: the backfill of the official NBA injury
report PDFs runs on the worker, because the dev sandbox cannot reach the CDN."""
import json

import pytest

from tracking import job_queue as jq


def _declared():
    with open("jobs/declared_jobs.json", encoding="utf-8") as fh:
        return [j for j in json.load(fh) if j["job_type"] == "nba_injury_report"]


def test_the_job_is_registered_and_its_declared_run_validates():
    fn, validate = jq.JOBS["nba_injury_report"]
    assert fn is jq._job_nba_injury_report
    declared = _declared()
    assert declared and declared[0]["requested_by"] == "matt"
    assert validate(declared[0]["args"]) == {
        "first_season": 2027, "last_season": 2027, "on_or_after": "2026-10-15"}


@pytest.mark.parametrize("bad", [
    {"first_season": 2027},                                   # last_season missing
    {"first_season": 2028, "last_season": 2027},              # reversed
    {"first_season": True, "last_season": 2027},              # bool is not a season
    {"first_season": "2027", "last_season": 2027},            # string is not a season
    {"first_season": 2027, "last_season": 2027, "on_or_after": "11/01/2026"},
    {"first_season": 2027, "last_season": 2027, "argv": "--today"},
])
def test_bad_args_are_refused(bad):
    _, validate = jq.JOBS["nba_injury_report"]
    with pytest.raises(ValueError):
        validate(bad)


def test_the_job_runs_the_ingestor_backfill_with_exactly_those_args(monkeypatch):
    seen = {}
    monkeypatch.setattr(jq, "_run_script_main",
                        lambda mod, argv: seen.update(mod=mod, argv=argv) or "ok")
    jq._job_nba_injury_report(first_season=2027, last_season=2027,
                              on_or_after="2026-10-15")
    assert seen["mod"] == "data.ingestors.nba_injury_report"
    assert seen["argv"] == ["--backfill", "--oldest-first", "--seasons", "2027", "2027",
                            "--on-or-after", "2026-10-15"]


def test_the_ingestor_accepts_that_argv():
    """The flags the job passes are flags the ingestor's parser defines."""
    from data.ingestors import nba_injury_report as nir
    src = open(nir.__file__, encoding="utf-8").read()
    for flag in ("--backfill", "--oldest-first", "--seasons", "--on-or-after"):
        assert f'"{flag}"' in src

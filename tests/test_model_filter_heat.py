"""
The Picks filter's Model section (Matt, 2026-11-18): each model's published
record and a hot / cold tag over its last 7 days.

Two halves:
  * the view, v_public_track_record_model_daily, must be the daily record view
    split by model and nothing else. Its migration builds it FROM the daily
    view's definition, so it cannot drift from the record; these tests pin
    that it does so, rather than carrying a hand copy of the WHERE clause.
    Reconciled against production 2026-11-19: per model it equals
    v_public_track_record, per (date, sport) it equals the daily view.
  * the behaviour, in mobile/scripts/verify_model_heat.ts, run when node and
    the app's node modules are installed.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._node import tsx_cmd

ROOT = Path(__file__).parent.parent
MOBILE = ROOT / "mobile"
MIG = ROOT / "data" / "migrations" / "public_track_record_model_daily_2026_11_18.sql"
SQL = MIG.read_text(encoding="utf-8")
CODE = "\n".join(l for l in SQL.splitlines() if not l.lstrip().startswith("--"))


def test_migration_is_registered_before_the_units_patch():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"


def test_migration_is_one_statement():
    assert CODE.count("$mig$") == 2
    assert CODE.split("$mig$")[-1].strip() == ";"


def test_the_view_is_derived_from_the_daily_view_not_copied():
    """A hand-copied WHERE would drift the first time the record views change.
    Broken copy: a literal `FROM picks` body instead of the viewdef read."""
    assert "pg_get_viewdef('public.v_public_track_record_daily'::regclass" in CODE
    assert "FROM picks" not in CODE
    assert "md5(daily_def)" in CODE


def test_it_creates_nothing_when_the_edit_does_not_apply():
    assert CODE.count("RETURN;") >= 4
    assert "body = daily_def" in CODE


def test_grants_are_select_only():
    assert "security_invoker = on" in CODE
    for role in ("PUBLIC", "anon", "authenticated"):
        assert f"REVOKE ALL ON public.v_public_track_record_model_daily FROM {role};" in CODE
    assert "GRANT SELECT ON public.v_public_track_record_model_daily TO anon, authenticated;" in CODE


def test_the_view_is_in_the_anon_manifest():
    from data.anon_readable import ANON_READABLE
    assert "v_public_track_record_model_daily" in ANON_READABLE


def test_the_app_reads_it_by_literal_name():
    src = (MOBILE / "src" / "lib" / "queries.ts").read_text(encoding="utf-8")
    assert ".from('v_public_track_record_model_daily')" in src


def test_paused_models_are_not_listed():
    """Matt, 2026-11-18: paused models are not in the Model list."""
    screen = (MOBILE / "src" / "screens" / "PicksHomeScreen.tsx").read_text(encoding="utf-8")
    assert "excludeModel={excludeModel}" in screen
    assert "(id: string) => isModelPaused(id)" in screen


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_behavioural_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_model_heat.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

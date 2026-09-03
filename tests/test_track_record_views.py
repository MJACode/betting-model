"""
The public record views read the graded matview, not the player logs.

WHY. On 2026-09-02 the Track Record tab was empty over a red error:
v_public_track_record took 14.3s and v_public_track_record_daily 12.3s against
PostgREST's 8s statement_timeout, so every app read was cancelled. Both views
re-graded the whole MLB/WNBA full-outcome universe (~126k picks, each probed in
player_game_log / wnba_player_game_log through a LATERAL ... LIMIT 1) on EVERY
read, and that universe grows 2-3k rows a day. The same grading already exists
precomputed in mv_scored_pick_outcomes; the migration pinned here points the two
views at it. Thresholds stay joined live, so a cut change still reaches the
record with no refresh.

These tests assert on what the migration EXECUTES (comment lines stripped), and
each one was watched failing against a deliberately broken copy of the file.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MIG = ROOT / "data" / "migrations" / "track_record_reads_graded_matview.sql"
SQL = MIG.read_text(encoding="utf-8")
SH = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")

VIEWS = ("v_model_full_outcome_record", "v_public_track_record_daily")


def _code(sql: str) -> str:
    """The migration minus its comment lines."""
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


CODE = _code(SQL)


def _body(view: str) -> str:
    m = re.search(
        rf"CREATE OR REPLACE VIEW public\.{re.escape(view)} WITH \(security_invoker = on\) AS(.*?)\$v\$",
        CODE, re.S)
    assert m, f"{view} is not redefined by the migration"
    return m.group(1)


def test_migration_is_registered_with_the_worker_runner():
    """data/view_migrations.py only runs files it is told about; a migration that
    is on disk but not in the list never reaches production."""
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    """The runner uses conn.execute(), never executescript: a second top-level
    statement would be shredded at its semicolons or silently dropped."""
    assert CODE.count("$mig$") == 2
    assert CODE.split("$mig$")[-1].strip() == ";"


def test_both_views_read_the_matview_and_never_the_player_logs():
    for view in VIEWS:
        body = _body(view)
        assert "FROM mv_scored_pick_outcomes o" in body, view
        for table in ("player_game_log", "wnba_player_game_log", "JOIN games"):
            assert table not in body, f"{view} re-grades from {table}: that is the 14s read"


def test_thresholds_are_still_joined_live():
    """The matview holds grading only. The cut (prob, edge, the min_odds price
    floor) must still come from model_action_thresholds at read time."""
    for view in VIEWS:
        body = _body(view)
        assert "JOIN model_action_thresholds" in body, view
        # `o.` is the matview alias, so these can only be satisfied by the
        # full-outcome branch - the `other` branch's own cut does not count.
        for clause in ("o.model_probability >= ", "o.edge >= COALESCE(", "o.dk_odds >= "):
            assert clause in body, f"{view}: cut clause {clause!r} missing from the matview branch"


def test_the_other_active_migrations_still_find_their_markers():
    """units_precision_for_public_record and require_price_for_published_units
    run every pass and RAISE if their expressions are gone."""
    assert "round(COALESCE(sum(profit) FILTER (WHERE passes), 0::numeric), 6)" in _body(VIEWS[0])
    assert "AND p.dk_odds IS NOT NULL), 0::numeric) AS profit_flat" in _body(VIEWS[1])


def test_no_ddl_outside_the_guarded_branches():
    """Every DDL statement - GRANT included - forces a PostgREST schema-cache
    reload (CLAUDE.md section 7). The runner executes this file on every pass,
    so on the no-op path nothing may fire: each GRANT sits after an ELSE."""
    grants = [m.start() for m in re.finditer(r"^\s*GRANT ", CODE, re.M)]
    assert len(grants) == 2
    for pos in grants:
        before = CODE[:pos]
        assert before.rfind("ELSE") > before.rfind("END IF;"), "GRANT outside the guarded branch"


def test_refresh_pass_refreshes_outcomes_after_settle():
    """The full-outcome branch now moves with the matview, so the pass must
    refresh it once its own finals are graded - never before settle."""
    def order(name: str) -> int:
        m = re.search(rf"^(?:step|par) {re.escape(name)}$", SH, re.M)
        assert m, f"step {name!r} is not in the chain"
        return m.start()
    assert order("settle") < order("refresh-outcomes")

"""
The published record starts at the official live date — in BOTH views.

WHY. On 2026-09-04 the Track Record screen showed "+17.2%, 43-27, 70 settled
picks" (the 2026-09-01 window, +12.02u) above an equity curve ending at +64.1u,
which is MLB from 2026-04-17 to 2026-09-03. The hero card reads
v_public_track_record and the curve reads v_public_track_record_daily; only the
first was carrying the live-date gate in production.

It had not been forgotten — it was being REVERTED. track_record_reads_graded_-
matview.sql was still in data/view_migrations.py's active list and redefined the
daily view under the guard `position('mv_scored_pick_outcomes' in viewdef) > 0`.
Once the daily view stopped reading the matview, that guard read "not applied"
and the ELSE branch restored the 2026-04-14 definition on the next pass, every
pass. Measured against production before the fix: the guard evaluated to 0.

Each test below was watched failing against a deliberately broken copy of the
migration (see the docstrings for what was broken).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MIG = ROOT / "data" / "migrations" / "live_record_start_views_2026_09_01.sql"
SQL = MIG.read_text(encoding="utf-8")

VIEWS = ("v_public_track_record", "v_public_track_record_daily")


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
    """A migration on disk but not in the list never reaches production — which
    is half of how this bug survived a merge."""
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_it_runs_after_the_migration_that_used_to_own_the_daily_view():
    """Order matters: if the graded-matview file ever regains a daily branch, it
    must not be the last word on the view."""
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert (ACTIVE_MIGRATIONS.index(MIG.name)
            > ACTIVE_MIGRATIONS.index("track_record_reads_graded_matview.sql"))


def test_migration_is_one_statement():
    """The runner uses conn.execute(), never executescript: a second top-level
    statement would be shredded at its semicolons or silently dropped — which is
    exactly how the original live-date migration lost its daily half."""
    assert CODE.count("$mig$") == 2
    assert CODE.split("$mig$")[-1].strip() == ";"


def test_both_published_views_carry_the_live_date_gate():
    """The whole point. Broken copy: the daily view's gate set back to
    2026-04-14 — the production state this migration exists to end."""
    for view in VIEWS:
        assert "p.game_date >= '2026-09-01'" in _body(view), view


def test_the_two_views_select_the_same_population():
    """The curve must total to the hero card, so every filter has to match. A
    broken copy that dropped the paused-model join from the daily view fails
    here. Compared as a set of predicates, not as text: the two differ
    legitimately in their GROUP BY and their selected columns."""
    predicates = [
        "p.signal_type = 'BET'",
        "(p.is_live IS NOT TRUE OR p.model_id LIKE '%\\_live\\_%')",
        "t.paused IS NOT TRUE",
        "p.game_date >= '2026-09-01'",
        "p.model_probability >= t.min_prob",
        "(t.prob_only OR p.edge >= t.min_edge)",
        "(t.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= t.min_odds)",
        "JOIN model_action_thresholds t ON t.model_id = p.model_id",
    ]
    for view in VIEWS:
        body = _body(view)
        for pred in predicates:
            assert pred in body, f"{view} is missing {pred!r}"


def test_neither_view_reads_the_sweep_universe():
    """The published record is settled BET picks AS FIRED, from `picks`. The
    re-graded matview is the threshold-sweep tool and keeps its own longer
    window (CLAUDE.md section 7) — reading it here is what made the two views
    disagree in the first place."""
    for view in VIEWS:
        body = _body(view)
        assert "FROM picks p" in body, view
        assert "mv_scored_pick_outcomes" not in body, view


def test_units_are_gated_on_a_real_dk_price():
    """profit_flat FABRICATES -110 when dk_odds IS NULL (CLAUDE.md section 6),
    so both the money and the stake must filter on a price."""
    priced = ("(p.result = ANY (ARRAY['WIN','LOSS','PUSH'])) AND p.dk_odds IS NOT NULL)")
    for view in VIEWS:
        # Whitespace-normalised: the two views indent the same expressions
        # differently, and this test is about the FILTER, not the formatting.
        body = " ".join(_body(view).split())
        assert f"sum(p.profit_flat) FILTER ( WHERE {priced}" in body, view
        assert f"100 * count(*) FILTER ( WHERE {priced} AS staked_flat" in body, view


def test_the_guard_is_the_live_date_not_the_view_shape():
    """The lesson from the revert. A guard asking "does the view still look like
    my output?" is a lock: it cannot tell "never applied" from "deliberately
    superseded". This one asks whether the live-date gate is present."""
    guards = re.findall(r"IF position\('([^']+)' in d\) > 0 THEN", CODE)
    assert guards == ["2026-09-01", "2026-09-01"], guards


def test_no_ddl_outside_the_guarded_branches():
    """Every DDL statement — GRANT included — forces a PostgREST schema-cache
    reload (CLAUDE.md section 7). The runner executes this file on every pass,
    so on the no-op path nothing may fire: each GRANT sits after an ELSE."""
    grants = [m.start() for m in re.finditer(r"^\s*GRANT ", CODE, re.M)]
    assert len(grants) == 2
    for pos in grants:
        before = CODE[:pos]
        assert before.rfind("ELSE") > before.rfind("END IF;"), "GRANT outside the guarded branch"


def test_the_app_and_the_views_agree_on_the_live_date():
    """One date, stated in config.py, mobile/src/lib/recordStart.ts and the view
    gate. A mismatch is the app asking for rows the view will never return."""
    from config import PAPER_TRADING_START
    assert PAPER_TRADING_START == "2026-09-01"
    ts = (ROOT / "mobile" / "src" / "lib" / "recordStart.ts").read_text(encoding="utf-8")
    assert "export const LIVE_RECORD_START = '2026-09-01';" in ts

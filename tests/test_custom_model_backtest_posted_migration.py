"""The custom-model backtest's units on the published stake (2026-11-03).

One unit basis everywhere (mike): the Record tab, Discord, the built-in model
pages and the Models list book the published stake, 1u to win at
COALESCE(decision_odds, dk_odds), risk capped at 3u, no price at the bare 1u.
custom_model_backtest returns 1u-risked units, so this migration adds a
read-only function over the same matched picks. The backtest still grades
every scored pick; only the unit basis changes.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "custom_model_backtest_posted_2026_11_03.sql"
SQL = MIG.read_text(encoding="utf-8")


def _code(sql: str) -> str:
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


def test_it_is_one_idempotent_statement_registered_before_the_posted_pair():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert MIG.name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    assert (ACTIVE_MIGRATIONS.index(MIG.name)
            < ACTIVE_MIGRATIONS.index("published_pick_units_2026_10_17.sql"))
    # It reads custom_model_picks at its decision-price signature.
    assert (ACTIVE_MIGRATIONS.index("decide_on_best_price_2026_09_09.sql")
            < ACTIVE_MIGRATIONS.index(MIG.name))
    code = _code(SQL)
    assert code.count("$mig$") == 2 and SQL.strip().endswith(";")
    # Returns on a catalog read before any DDL.
    first_ddl = code.index("CREATE FUNCTION")
    assert code.index("IS NOT NULL THEN\n    RETURN;") < first_ddl


def test_it_is_read_only_and_sums_the_published_stake():
    code = _code(SQL).upper()
    for verb in ("INSERT", "UPDATE ", "DELETE", "ALTER ", "DROP ", "TRUNCATE",
                 "CREATE OR REPLACE", "CREATE VIEW"):
        assert verb not in code, verb
    assert "STABLE" in code
    body = _code(SQL)
    assert "published_pick_unit_profit(\n        COALESCE(c.decision_odds, c.dk_odds), c.result)" in body
    assert "published_pick_unit_risked(\n        COALESCE(c.decision_odds, c.dk_odds), c.result)" in body
    # Every scored pick custom_model_picks matches: no row cap.
    assert re.search(r"custom_model_picks\(p_rules, p_filters, 2147483647\)", body)


def test_it_grants_the_app_and_nobody_else():
    code = _code(SQL)
    assert "REVOKE ALL ON FUNCTION public.custom_model_backtest_posted(jsonb, jsonb) FROM PUBLIC" in code
    assert "GRANT EXECUTE ON FUNCTION public.custom_model_backtest_posted(jsonb, jsonb) TO anon, authenticated" in code
    from data.anon_readable import RPC_ANON_CALLABLE
    assert "custom_model_backtest_posted" in RPC_ANON_CALLABLE

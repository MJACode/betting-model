"""AI assistant (MCP): alternate prop lines and the slate-wide prop board.

Matt, 2026-11-21: "Yes alt lines". Before this, mcp_stats.prop_prices
excluded every '%_alternate' market, so "Maxey Over 14.5 points" came back
not_found although the database held 6,090 NBA alternate points rows that
day. And a slate question ("who is -600 or longer to clear 14.5?") cost one
of the member's 10 daily questions per player.
"""
from __future__ import annotations

import re
from pathlib import Path

from data.view_migrations import ACTIVE_MIGRATIONS

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "data" / "migrations"
ALT = "mcp_stats_alt_lines_2026_11_21.sql"
SERVER = ROOT / "supabase" / "functions" / "mcp" / "index.ts"


def _body(name: str) -> str:
    sql = (MIGRATIONS / name).read_text(encoding="utf-8")
    return "\n".join(ln for ln in sql.splitlines() if not ln.strip().startswith("--"))


def _prop_prices_def(body: str) -> str:
    start = body.index("CREATE OR REPLACE VIEW mcp_stats.prop_prices")
    return body[start:body.index(";", start)]


def test_alt_lines_migration_is_listed_after_the_views():
    i = ACTIVE_MIGRATIONS.index
    assert ALT in ACTIVE_MIGRATIONS
    assert i("mcp_stats_views_2026_11_21.sql") < i(ALT)


def test_prop_prices_carries_alternate_lines_in_both_files():
    """Both definitions agree, so a rerun of the views file cannot undo this one."""
    for name in ("mcp_stats_views_2026_11_21.sql", ALT):
        view = _prop_prices_def(_body(name))
        assert "NOT LIKE '%\\_alternate'" not in view, name
        assert "regexp_replace(p.market, '_alternate$', '') AS market" in view, name
        assert view.rstrip().splitlines()[-1].strip().startswith("WHERE (g.commence_time IS NULL OR p.snapshot_at <= g.commence_time)"), name
        # is_alternate is the LAST column: CREATE OR REPLACE VIEW can only append.
        select = view.split("FROM public.latest_prop_odds")[0]
        assert select.rstrip().endswith("AS is_alternate"), name


def test_alt_lines_guard_is_the_property_not_the_text():
    body = _body(ALT)
    assert body.strip().startswith("DO $alt$") and body.strip().endswith("$alt$;")
    assert "attname = 'is_alternate'" in body
    assert "pg_get_viewdef" not in body
    assert not re.search(r"GRANT[^;]*\b(anon|authenticated)\b", body)
    assert "GRANT SELECT ON mcp_stats.prop_prices TO mcp_reader" in body


def _case(src: str, name: str) -> str:
    start = src.index(f'case "{name}": {{')
    nxt = src.find("\n    case ", start + 10)
    return src[start:nxt]


def test_best_price_reads_the_main_line_when_no_line_is_asked():
    src = SERVER.read_text(encoding="utf-8")
    body = _case(src, "get_best_price")
    assert "not pp.is_alternate" in body
    # Nearest-first ordering, so a player's ~46 alternate lines x 7 books
    # cannot push the asked-for line past the row cap.
    assert "abs(pp.line - coalesce(${line}::numeric, pp.line))" in body


def test_prop_board_is_a_listed_tool_with_a_price_band():
    src = SERVER.read_text(encoding="utf-8")
    assert 'name: "get_prop_board"' in src
    body = _case(src, "get_prop_board")
    # Games still to start only: a pre-game quote on a started game is not takeable.
    assert "g.starts_at::timestamptz > now()" in body
    assert "best_price >= ${minPrice}::numeric" in body
    assert "best_price <= ${maxPrice}::numeric" in body
    # One-book outliers stay visible.
    assert "books_quoting" in body and "longest_price" in body
    # Same read path as every other tool: read-only role, 3 s timeout.
    assert "await read(" in body

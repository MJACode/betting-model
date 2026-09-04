"""The two "latest line per book" views are skip scans, and their columns are
the app's columns.

DISTINCT ON over an append-only odds log must fetch every snapshot to keep the
newest per key: 98,941 rows for one day's game lines, 168,651 for one day's
props, and the reads timed out (57014) under any background load -- 41 times
in one minute on 2026-09-04. The skip-scan shape reads one row per key. This
pins the shape, and pins the column lists to mobile/src/lib/queries.ts so a
CREATE OR REPLACE VIEW that reorders or renames a column is a red test rather
than an empty LINE column with nothing in any log near the cause.
"""

import io
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SQL = io.open(ROOT / "data" / "migrations" / "skip_scan_latest_odds_views.sql",
              encoding="utf-8").read()
STMTS = "\n".join(ln for ln in SQL.splitlines() if not ln.strip().startswith("--"))
QUERIES = io.open(ROOT / "mobile" / "src" / "lib" / "queries.ts", encoding="utf-8").read()


def _view(name: str) -> str:
    start = STMTS.index(f"CREATE OR REPLACE VIEW public.{name}")
    end = STMTS.index(";", start)
    return STMTS[start:end]


def _app_columns(const: str) -> list[str]:
    m = re.search(rf"const {const} =\s*((?:'[^']*'\s*\+?\s*)+);", QUERIES)
    assert m, f"{const} not found in queries.ts"
    return [c.strip() for c in "".join(re.findall(r"'([^']*)'", m.group(1))).split(",")]


def _view_columns(body: str) -> list[str]:
    sel = body[body.index("SELECT") + len("SELECT"):body.index("FROM games g")]
    return [c.strip().split(".")[-1] for c in sel.split(",") if c.strip()]


def test_the_game_view_returns_the_apps_columns_in_order():
    assert _view_columns(_view("v_latest_odds_all_books")) == _app_columns("ODDS_BY_BOOK_COLUMNS")


def test_the_prop_view_returns_the_apps_columns_in_order():
    assert _view_columns(_view("v_latest_prop_odds_all_books")) == _app_columns("PROP_ODDS_BY_BOOK_COLUMNS")


def test_neither_view_de_duplicates_the_whole_log():
    for name in ("v_latest_odds_all_books", "v_latest_prop_odds_all_books"):
        body = _view(name)
        assert "DISTINCT ON" not in body, f"{name} is back to reading every snapshot"
        assert "WITH RECURSIVE" in body, f"{name} has no skip scan"
        assert "FROM games g" in body, f"{name} is not driven from games (the date filter lands there)"
        assert body.count("LIMIT 1") == 3, f"{name}: seed, step and top-1 probes must each be LIMIT 1"
        assert "ORDER BY o.snapshot_at DESC" in body or "ORDER BY p.snapshot_at DESC" in body
        assert "::timestamptz" not in body, "a cast on snapshot_at defeats the index order"
        assert "security_invoker = on" in body


def test_the_views_keep_their_exclusions():
    game = _view("v_latest_odds_all_books")
    assert "s.bookmaker <> 'sbr_consensus'" in game, "the synthetic consensus book leaked in"
    for name in ("v_latest_odds_all_books", "v_latest_prop_odds_all_books"):
        assert "snapshot_type IS NULL OR" in _view(name) and "<> 'in_play'" in _view(name), \
            f"{name} would show a live number as a pre-game line"


def test_the_skip_scan_steps_on_the_whole_key():
    """The step probe must compare the full key tuple, or it skips keys."""
    assert "(o.market, o.bookmaker) > (s.market, s.bookmaker)" in _view("v_latest_odds_all_books")
    assert "(p.market, p.player_name, p.bookmaker) > (s.market, s.player_name, s.bookmaker)" \
        in _view("v_latest_prop_odds_all_books")


def test_the_prop_index_the_skip_scan_runs_on_is_recorded():
    """CONCURRENTLY cannot run inside the migration, so the index is a documented
    prerequisite; the prefix index it replaces is dropped in the file."""
    assert re.search(r"CREATE INDEX CONCURRENTLY idx_prop_odds_line_snap\s+(?:--\s*)?ON public\.player_prop_odds "
                     r"\(game_id, market, player_name, bookmaker, snapshot_at\)", SQL)
    assert "DROP INDEX IF EXISTS public.idx_prop_odds_game;" in STMTS

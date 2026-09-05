"""The "latest line" views are plain joins over current-state tables, and their
columns are the app's columns.

THE HISTORY THIS PINS. Three sessions in four days (221, 222, and 2026-09-05)
fixed "Couldn't load today's lines" by changing how the odds LOG was walked --
DISTINCT ON keyed on game_date, then a recursive skip scan -- and each fix held
until a bigger day arrived: 10.5 s for one market on a 157-game Saturday,
17.9 s for v_latest_dk_odds on any day (a full scan of the odds table). A read
whose cost scales with the log crosses any timeout eventually. The permanent
shape is a state table maintained by the WRITER (latest_line_state_tables.sql),
so the read costs one probe per game whatever the day. This test is the
tripwire against any of the three views quietly going back to reading the log.

The behaviour of the triggers is exercised on a real Postgres in
tests/test_latest_line_state.py; this file checks the shape statically so it
runs everywhere.
"""

import io
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SQL = io.open(ROOT / "data" / "migrations" / "latest_line_state_tables.sql",
              encoding="utf-8").read()
STMTS = "\n".join(ln for ln in SQL.splitlines() if not ln.strip().startswith("--"))
QUERIES = io.open(ROOT / "mobile" / "src" / "lib" / "queries.ts", encoding="utf-8").read()

VIEWS = {
    "v_latest_odds_all_books": "latest_odds",
    "v_latest_prop_odds_all_books": "latest_prop_odds",
    "v_latest_dk_odds": "latest_odds",
    "v_live_game_state_latest": "latest_live_game_state",
}
LOG_TABLES = ("odds", "player_prop_odds", "live_game_state")


def _view(name: str) -> str:
    start = STMTS.index(f"CREATE OR REPLACE VIEW public.{name}")
    end = STMTS.index(";", start)
    return STMTS[start:end]


def _function(name: str) -> str:
    start = STMTS.index(f"CREATE OR REPLACE FUNCTION public.{name}(")
    end = STMTS.index("END $$;", start)
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


def test_the_dk_view_returns_the_apps_columns_in_order():
    assert _view_columns(_view("v_latest_dk_odds")) == _app_columns("LATEST_ODDS_COLUMNS")


def test_the_live_view_returns_the_apps_columns_in_order():
    assert _view_columns(_view("v_live_game_state_latest")) == _app_columns("LIVE_STATE_COLUMNS")


def test_every_view_reads_its_state_table_and_never_the_log():
    for name, state in VIEWS.items():
        body = _view(name)
        assert f"JOIN {state} l" in body, f"{name} does not read {state}"
        assert "FROM games g" in body, f"{name} is not driven from games (the date filter lands there)"
        for log in LOG_TABLES:
            assert not re.search(rf"\b{log}\b\s+[a-z]\b", body), f"{name} reads the log table {log} again"
        for walk in ("DISTINCT ON", "WITH RECURSIVE", "LATERAL", "ORDER BY"):
            assert walk not in body, f"{name} walks the log ({walk}); the state table already holds the answer"
        assert "security_invoker = on" in body, name


def test_the_exclusions_survived_the_move():
    assert "l.bookmaker <> 'sbr_consensus'" in _view("v_latest_odds_all_books")
    assert "l.bookmaker = 'draftkings'" in _view("v_latest_dk_odds")
    for fn in ("latest_odds_on_insert", "latest_odds_recompute", "latest_lines_rebuild_odds",
               "latest_prop_odds_on_insert", "latest_prop_odds_recompute", "latest_lines_rebuild_props"):
        assert "<> 'in_play'" in _function(fn), f"{fn} lets an in-play row become the latest pre-game line"


def test_every_log_table_has_its_insert_trigger_and_the_odds_tables_an_update_trigger():
    for log in LOG_TABLES:
        assert re.search(rf"CREATE TRIGGER trg_latest_\w+_insert\s+AFTER INSERT ON public\.{log}\s+REFERENCING NEW TABLE", STMTS), log
    for log in ("odds", "player_prop_odds"):
        assert re.search(rf"CREATE TRIGGER trg_latest_\w+_update\s+AFTER UPDATE ON public\.{log}\s+FOR EACH ROW\s+WHEN", STMTS), (
            f"{log}: a relabel to in_play must recompute the key, and only a relevant column change may fire it")


def test_the_state_tables_are_read_only_for_the_api_roles():
    for t in ("latest_odds", "latest_prop_odds", "latest_live_game_state"):
        assert f"ALTER TABLE public.{t}            ENABLE ROW LEVEL SECURITY" in STMTS or \
               re.search(rf"ALTER TABLE public\.{t}\s+ENABLE ROW LEVEL SECURITY", STMTS), t
        assert re.search(rf'CREATE POLICY "anon read {t}"\s+ON public\.{t}\s+FOR SELECT TO anon, authenticated USING \(true\)', STMTS), t
    assert re.search(r"REVOKE ALL\s+ON public\.latest_odds, public\.latest_prop_odds, public\.latest_live_game_state FROM anon, authenticated", STMTS)
    assert re.search(r"GRANT\s+SELECT ON public\.latest_odds, public\.latest_prop_odds, public\.latest_live_game_state TO\s+anon, authenticated", STMTS)


def test_no_pending_view_migration_re_creates_these_views_over_the_log():
    """A later file in ACTIVE_MIGRATIONS that CREATE OR REPLACEs one of these
    views would put the log walk back on the next pipeline pass, silently."""
    from data.view_migrations import ACTIVE_MIGRATIONS, MIGRATIONS_DIR

    for name in ACTIVE_MIGRATIONS:
        body = io.open(MIGRATIONS_DIR / name, encoding="utf-8").read()
        for view in VIEWS:
            assert f"VIEW public.{view}" not in body and f"VIEW {view}" not in body, (
                f"{name} re-creates {view}; it must read the state table or be retired")

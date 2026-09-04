"""The Teams board is read from a cache the pipeline refreshes -- not computed
on every app open.

team_stats_board('MLB', 2026) measured 31,669 ms on 2026-09-04 against an 8 s
statement timeout, and the Teams board showed "Connection error: canceling
statement due to statement timeout (57014)". The migration renames that body
to team_stats_board_compute (worker-only), adds team_stats_board_cache, and
re-creates team_stats_board() with the SAME signature as a ~30-row read. The
app changes nothing; what can go wrong is on this side:

  * a column list that drifts between the cache, the refresh INSERT and the
    thin function (a column dropped in one place is a NULL column in the app,
    with no error anywhere near the cause);
  * the compute or refresh function left callable by anon -- free DB-CPU burn
    through the public key (the operations rule: REVOKE by NAME);
  * the refresh step registered in one of the pipeline's two tables but not
    the other, or running before settle so the board is a day stale;
  * one bad (sport, season) pair silently costing every other sport its board.
"""

import io
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

MIG = io.open(ROOT / "data" / "migrations" / "cache_team_stats_board.sql",
              encoding="utf-8").read()
# Statements only: the header's reasoning names things the file must not do.
STMTS = "\n".join(ln for ln in MIG.splitlines() if not ln.strip().startswith("--"))
PIPE = io.open(ROOT / "run_pipeline.py", encoding="utf-8").read()


# ── the migration ─────────────────────────────────────────────────────────────

def _cols(csv: str) -> list[str]:
    return [c.strip().split()[0] for c in csv.split(",") if c.strip()]


def test_the_cache_the_refresh_and_the_thin_function_name_the_same_columns():
    table = re.search(r"CREATE TABLE public\.team_stats_board_cache \((.*?)\n\);",
                      STMTS, re.S).group(1)
    table_cols = [ln.strip().split()[0] for ln in table.splitlines()
                  if ln.strip() and not ln.strip().startswith("PRIMARY")]
    insert = _cols(re.search(
        r"INSERT INTO public\.team_stats_board_cache\s*\(([^)]*)\)", STMTS).group(1))
    returns = _cols(re.search(r"RETURNS TABLE\(([^)]*)\)", STMTS).group(1))
    # `AS $$` followed directly by SELECT is the thin function; the refresh
    # function's body opens with DECLARE.
    thin = _cols(re.search(r"AS \$\$\s*SELECT (.*?)\s+FROM public\.team_stats_board_cache",
                           STMTS, re.S).group(1))

    assert insert[:2] == ["sport", "season"] and insert[-1] == "refreshed_at"
    board = insert[2:-1]
    assert len(board) == 53, "the board has 53 columns (pg_get_function_result)"
    assert table_cols == ["sport", "season"] + board + ["refreshed_at"]
    assert returns == board
    assert thin == board


def test_the_thin_function_reads_the_cache_and_never_the_compute():
    body = STMTS[STMTS.index("CREATE FUNCTION public.team_stats_board("):]
    assert "team_stats_board_cache" in body
    assert "team_stats_board_compute" not in body
    assert "STABLE" in body
    assert ("GRANT EXECUTE ON FUNCTION public.team_stats_board(text, integer) "
            "TO anon, authenticated") in body


def test_the_compute_and_the_refresh_are_revoked_by_name():
    """REVOKE ... FROM PUBLIC alone leaves a named grant in place, and anon
    holds EXECUTE on every new function by default privilege."""
    for fn in ("team_stats_board_compute", "refresh_team_stats_board"):
        m = re.search(rf"REVOKE ALL ON FUNCTION public\.{fn}\(text, integer\)\s+FROM ([^;]*);",
                      STMTS)
        assert m, f"{fn} is never revoked"
        for role in ("PUBLIC", "anon", "authenticated"):
            assert role in m.group(1), f"{fn}: {role} keeps EXECUTE ({m.group(1)})"
        assert not re.search(rf"GRANT[^;]*{fn}", STMTS), f"{fn} is granted back"


def test_the_cache_is_rls_on_and_read_only_for_the_app():
    assert "ALTER TABLE public.team_stats_board_cache ENABLE ROW LEVEL SECURITY" in STMTS
    assert "REVOKE ALL ON public.team_stats_board_cache FROM PUBLIC, anon, authenticated" in STMTS
    assert "GRANT SELECT ON public.team_stats_board_cache TO anon, authenticated" in STMTS
    assert re.search(r"CREATE POLICY \w+\s+ON public\.team_stats_board_cache FOR SELECT",
                     STMTS)
    for w in ("INSERT", "UPDATE", "DELETE"):
        assert not re.search(rf"GRANT[^;]*\b{w}\b[^;]*team_stats_board_cache", STMTS)


def test_the_refresh_swaps_one_pair_in_one_transaction():
    body = STMTS[STMTS.index("refresh_team_stats_board(p_sport"):
                 STMTS.index("CREATE FUNCTION public.team_stats_board(")]
    assert re.search(r"DELETE FROM public\.team_stats_board_cache\s+WHERE sport = p_sport AND season = p_season",
                     body)
    assert "FROM public.team_stats_board_compute(p_sport, p_season)" in body
    assert "COMMIT" not in body.upper(), "a COMMIT inside the function would split the swap"


def test_the_two_functions_are_recorded_as_revoked_in_the_manifest():
    """data/anon_readable.RPC_REVOKE is where a deliberate revoke lives, so the
    admin sweep re-applies it rather than the default privilege re-opening it."""
    from data.anon_readable import RPC_ANON_CALLABLE, RPC_REVOKE
    for fn in ("team_stats_board_compute", "refresh_team_stats_board"):
        assert fn in RPC_REVOKE
        assert fn not in RPC_ANON_CALLABLE
    assert "team_stats_board" in RPC_ANON_CALLABLE


# ── the pipeline step ─────────────────────────────────────────────────────────

def test_the_step_is_registered_in_both_tables_and_runs_after_settle():
    choices = PIPE[PIPE.index('parser.add_argument("--step"'):]
    choices = choices[:choices.index("help=")]
    assert '"refresh-team-board"' in choices, "not an argparse choice"
    assert '"refresh-team-board": lambda: step_refresh_team_board(run_date)' in PIPE
    daily = PIPE[PIPE.index("def run_daily_pipeline("):]
    daily = daily[:daily.index("\ndef ")]
    assert daily.index('results["settle"]') < daily.index('results["refresh_team_board"]'), \
        "the board must be refreshed AFTER yesterday's finals are settled"


def test_a_failed_pair_makes_the_step_report_failure(monkeypatch):
    import run_pipeline
    from data import team_board_cache

    monkeypatch.setattr(team_board_cache, "refresh_team_board_cache",
                        lambda pairs=None: {("MLB", 2026): 30, ("NCAAF", 2026): -1})
    assert run_pipeline.step_refresh_team_board("2026-09-04") is False

    monkeypatch.setattr(team_board_cache, "refresh_team_board_cache",
                        lambda pairs=None: {("MLB", 2026): 30, ("NFL", 2027): 0})
    assert run_pipeline.step_refresh_team_board("2026-09-04") is True


# ── the refresh module ────────────────────────────────────────────────────────

def test_every_team_sport_gets_last_this_and_next_year():
    """NHL, NBA and NCAAF label a season by its ENDING year (CLAUDE.md §4), so
    the season in progress each autumn carries next year's label."""
    from data.team_board_cache import TEAM_BOARD_SPORTS, team_board_pairs

    assert set(TEAM_BOARD_SPORTS) == {"MLB", "WNBA", "NBA", "NHL", "NFL", "NCAAF"}
    pairs = team_board_pairs(date(2026, 9, 4))
    assert len(pairs) == 18
    for sport in TEAM_BOARD_SPORTS:
        assert [yr for s, yr in pairs if s == sport] == [2025, 2026, 2027]


class _Cursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Conn:
    """A connection whose (NCAAF, 2026) refresh raises, like a bad season."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.closed = False
        self._conn = type("Raw", (), {"autocommit": False})()

    def execute(self, sql, params=None):
        assert "refresh_team_stats_board" in sql
        self.calls.append(tuple(params))
        if params == ("NCAAF", 2026):
            raise RuntimeError("canceling statement due to statement timeout")
        return _Cursor([{"MLB": 30, "NFL": 0}[params[0]]])

    def close(self):
        self.closed = True


def test_one_failing_pair_does_not_stop_the_rest(monkeypatch):
    from data import db
    from data.team_board_cache import refresh_team_board_cache

    conn = _Conn()
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: conn)
    out = refresh_team_board_cache([("MLB", 2026), ("NCAAF", 2026), ("NFL", 2027)])

    assert conn.calls == [("MLB", 2026), ("NCAAF", 2026), ("NFL", 2027)], \
        "the failing pair must not stop the pairs after it"
    assert out == {("MLB", 2026): 30, ("NCAAF", 2026): -1, ("NFL", 2027): 0}
    assert conn._conn.autocommit is True, "each pair must be its own transaction"
    assert conn.closed

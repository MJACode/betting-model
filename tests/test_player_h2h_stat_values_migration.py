"""The H2H window's five RPCs: applied by the worker, and safe to re-run.

Matt, 2026-09-20: "show how a player or team has done against an opponent ...
the last 2 years". The Stats tab's H2H chip and the player page's
"vs OPP - last 2 seasons" card both read player_h2h_stat_values_*.

What these assertions are protecting, in order of how quietly each one breaks:

  1. THE MISPAIRING TRAP. `values` and `dates` are index-aligned by contract --
     the player page prints `dates[i]` beside `values[i]`. They stay aligned
     only because both aggregates carry the SAME `FILTER (WHERE val IS NOT
     NULL)`. Drop it from one and every meeting after the first null renders a
     real number under another game's date, which looks entirely correct.
  2. THE OPPONENT SOURCE. Measured 2026-09-20 against production: only
     nfl_player_game_log and ncaaf_player_game_log carry an `opponent` column.
     MLB, NBA and WNBA must derive it by joining `games` -- an MLB function
     that reads `opponent` would not compile, but one that quietly matched on
     something else would return the wrong games.
  3. THE DDL GUARD. data/view_migrations runs this file on every refresh pass
     (~54 a day) with conn.execute(), so it must be ONE statement and must do
     its DDL once. Every DDL statement fires Supabase's pgrst_ddl_watch and
     PostgREST answers 503 to the whole app while it rebuilds -- that is how
     the Stats tab went dark on 2026-09-01 (tests/test_ddl_guard.py).
  4. THE GRANT. After ALTER DEFAULT PRIVILEGES ... REVOKE ALL ON FUNCTIONS a
     new RPC arrives callable by nobody and 404s through PostgREST, so the
     names must also be declared in data/anon_readable.py.

Exercised end to end against a real Postgres 16 on 2026-09-20 (fixture schema,
migration applied twice, functions called): the trade case counts a player's
meetings with the opponent from his previous team, a different opponent's games
are excluded, NULL stat values are not counted as games, an unknown stat key
returns zero rows rather than erroring, and a school name containing "|" and
"," pairs correctly -- which is the reason for two parallel arrays.
"""
from __future__ import annotations

from pathlib import Path

MIG = (Path(__file__).parent.parent
       / "data/migrations/add_player_h2h_stat_values_rpcs.sql")
# encoding pinned: this file is full of box-drawing characters and read_text()
# with no encoding uses the PLATFORM default, which is cp1252 on the machine
# that runs the suite (CLAUDE.md section 7).
CODE = MIG.read_text(encoding="utf-8")
#: The same text with whole-line `--` comments removed. The header comments
#: talk ABOUT the dollar-quote tags, so counting them over the raw file counts
#: prose as code.
SQL_ONLY = "\n".join(
    ln for ln in CODE.splitlines() if not ln.lstrip().startswith("--")
)

SPORTS = ("mlb", "wnba", "nba", "nfl", "ncaaf")
#: The three whose logs carry no `opponent` column, measured on production.
JOIN_GAMES = ("mlb", "wnba", "nba")
LOG_TABLE = {
    "mlb": "player_game_log",
    "wnba": "wnba_player_game_log",
    "nba": "nba_player_game_log",
    "nfl": "nfl_player_game_log",
    "ncaaf": "ncaaf_player_game_log",
}


def _body(sport: str) -> str:
    """One function's text, from its CREATE to the next one's (or the grants)."""
    start = CODE.index(f"CREATE OR REPLACE FUNCTION public.player_h2h_stat_values_{sport}(")
    rest = CODE[start + 10:]
    nxt = rest.find("CREATE OR REPLACE FUNCTION")
    end = len(CODE) if nxt == -1 else start + 10 + nxt
    return CODE[start:end]


def test_the_worker_applies_it():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_it_is_one_statement_so_conn_execute_cannot_shred_it():
    """view_migrations uses conn.execute(), never executescript: a second
    top-level statement would be split at its semicolons."""
    assert SQL_ONLY.count("$mig$") == 2
    assert SQL_ONLY.strip().startswith("DO $mig$")
    assert SQL_ONLY.strip().endswith("$mig$;")
    # The function bodies are re-tagged, because $$ cannot nest inside $mig$.
    assert "AS $$" not in SQL_ONLY
    assert SQL_ONLY.count("$fn$") == 2 * len(SPORTS)
    assert SQL_ONLY.count("$ddl$") == 2 * len(SPORTS)


def test_it_does_its_ddl_once_and_guards_on_the_property_it_establishes():
    """Not on the shape of its own output -- that is a lock, not a guard
    (.claude/rules/data-integrity.md). The property is "all five exist"."""
    assert "IF (SELECT count(*)" in CODE
    assert "p.proname LIKE 'player_h2h_stat_values_%'" in CODE
    assert f") >= {len(SPORTS)} THEN" in CODE
    assert "RETURN;" in CODE


def test_every_sport_with_a_player_log_gets_a_function():
    for sport in SPORTS:
        assert f"public.player_h2h_stat_values_{sport}(" in CODE


def test_values_and_dates_carry_the_same_null_filter():
    """The mispairing trap. `dates[i]` must be the date of `values[i]`, and
    that holds only while both aggregates filter on the same condition."""
    for sport in SPORTS:
        body = _body(sport)
        assert body.count("FILTER (WHERE v.val IS NOT NULL)") == 2, sport
        # Both ordered the same way, newest first, or index i means two things.
        assert body.count("ORDER BY v.game_date DESC, v.game_id DESC") >= 2, sport


def test_the_three_logs_with_no_opponent_column_join_games():
    for sport in JOIN_GAMES:
        body = _body(sport)
        assert "JOIN games g" in body, sport
        assert f"g.sport = '{sport.upper()}'" in body, sport
        # The opponent is the OTHER side of the row's own game.
        assert "THEN g.away_team ELSE g.home_team END = s.opp" in body, sport


def test_the_two_football_logs_read_opponent_off_the_row():
    for sport in ("nfl", "ncaaf"):
        body = _body(sport)
        assert "n.opponent = s.opp" in body, sport
        assert "JOIN games" not in body, sport


def test_each_function_reads_its_own_log_table():
    for sport in SPORTS:
        body = _body(sport)
        assert LOG_TABLE[sport] in body, sport
        for other, table in LOG_TABLE.items():
            if other == sport or table in LOG_TABLE[sport]:
                continue
            assert table not in body, f"{sport} reads {table}"


def test_the_fixture_is_two_parallel_arrays_not_a_separator():
    """An NCAAF team id is a school NAME (CLAUDE.md section 4), so every
    separator is a character that can occur inside a key. Verified against a
    real Postgres with a team called 'Texas A&M | Kingsville'."""
    for sport in SPORTS:
        body = _body(sport)
        assert "p_teams text[]" in body, sport
        assert "p_opponents text[]" in body, sport
        assert "WITH ORDINALITY" in body, sport
        assert "split_part" not in body, sport


def test_the_span_is_a_season_list_the_caller_names():
    """Two seasons is the app's choice (queries.h2hSeasons), not the RPC's --
    the function takes whatever list it is handed."""
    for sport in SPORTS:
        body = _body(sport)
        assert "p_seasons integer[]" in body, sport
        assert "season = ANY(p_seasons)" in body, sport


def test_the_players_latest_team_decides_his_fixture():
    """...and then his WHOLE history against that opponent answers it, games
    for a previous team included."""
    for sport in SPORTS:
        body = _body(sport)
        assert "DISTINCT ON (" in body, sport
        assert "JOIN pairs p ON p.team = l.team" in body, sport


def test_public_is_revoked_before_anon_is_granted():
    """Postgres grants EXECUTE to PUBLIC on a new function and anon is a
    member, so a named grant alone leaves a wider surface than intended."""
    for sport in SPORTS:
        fn = f"public.player_h2h_stat_values_{sport}("
        revoke = CODE.index(f"REVOKE ALL ON FUNCTION {fn}")
        grant = CODE.index(f"GRANT EXECUTE ON FUNCTION {fn}")
        assert revoke < grant, sport
        assert "TO anon, authenticated" in CODE[grant:grant + 200], sport


def test_the_rpcs_are_declared_anon_callable():
    """A new RPC 404s through PostgREST without this (test_anon_readable.py).
    apply_anon_grants skips a function that is not in production yet, so
    declaring it before the migration lands is safe."""
    from data.anon_readable import RPC_ANON_CALLABLE
    for sport in SPORTS:
        assert f"player_h2h_stat_values_{sport}" in RPC_ANON_CALLABLE, sport


def test_security_invoker_like_the_season_rpcs_it_mirrors():
    for sport in SPORTS:
        body = _body(sport)
        assert "SECURITY INVOKER" in body, sport
        assert "SET search_path = public, pg_temp" in body, sport

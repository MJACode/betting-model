"""A pick that has been GRADED still holds its lock.

Matt, 2026-09-05, on the model detail screen: *"The same bet showed multiple
times for a signal. It should just be the first one?"* -- eleven identical
"Logan Allen Over 4.5 Hits · DK +117 · WIN · +$117.00" rows.

THE MECHANISM, which is not obvious and is why this file exists. Both pick
locks asked for `result IS NULL`, so a pick left the lock set the moment
settle_picks graded it. That is harmless while "graded" implies "the game is
over and nothing scores it again" -- and it stops being harmless the moment
one game_id covers two games. A doubleheader does exactly that
(docs/followups.md): game 1's final score settles the pick, while game 2's
commence_time keeps the pre-game cutoff open, so the next refresh pass scores
the same player again and INSERTS A SECOND PICK. Which the next settle pass
grades ~2 minutes later, releasing the lock again. One copy per 10-minute pass
until first pitch of game 2.

Measured on production before the fix: 63 duplicate rows across every pick
ever written, and 20 of the 132 settled BETs in the published 2026-09-01
window -- the published record read +7.38u / +5.59% ROI where the real number
was +5.68u / +5.07%.

Every test here fails on the pre-fix code. The first one fails by returning an
EMPTY lock set for a settled pick, which is the bug itself.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.db_setup import SCHEMA_SQL
from models import scorer

SRC = (Path(__file__).parent.parent / "models/scorer.py").read_text(encoding="utf-8")


class _SqliteShim:
    """Minimal DBConnection stand-in: converts %s placeholders to sqlite's ?."""

    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, params=None):
        return self._c.execute(sql.replace("%s", "?"), params or [])


@pytest.fixture
def conn():
    raw = sqlite3.connect(":memory:")
    raw.executescript(SCHEMA_SQL)
    # picks.player_id and picks.is_live exist in production but are in NEITHER
    # data/db_setup.py's SCHEMA_SQL nor data/supabase_schema.sql -- they were
    # added by hand and never written back. Added here so this file tests the
    # real table; the schema gap is noted in docs/followups.md.
    raw.execute("ALTER TABLE picks ADD COLUMN player_id TEXT")
    raw.execute("ALTER TABLE picks ADD COLUMN is_live BOOLEAN DEFAULT 0")
    yield raw
    raw.close()


def _game(raw, gid="MLB_2026-09-04_DET_CLE", date="2026-09-04",
          commence="2026-09-04T23:46:00+00:00", home_score=None):
    raw.execute("""INSERT INTO games (game_id, sport, season, game_date,
                   home_team, away_team, commence_time, home_score, away_score)
                   VALUES (?,'MLB',2026,?,'CLE','DET',?,?,?)""",
                (gid, date, commence, home_score,
                 None if home_score is None else 6))


def _pick(raw, *, result=None, signal="BET", created="2026-09-04 17:21:01+00",
          side="over", player="671106", model="mlb_prop_pitcher_hits",
          gid="MLB_2026-09-04_DET_CLE", date="2026-09-04", line=4.5, odds=116.0):
    raw.execute("""INSERT INTO picks (game_id, model_id, sport, game_date,
                   pick_side, pick_label, model_probability, dk_implied_prob,
                   edge, dk_odds, scored_line, kelly_fraction, recommended_bet,
                   bankroll_at_pick, signal_type, player_id, result, created_at)
                   VALUES (?,?, 'MLB', ?, ?, 'Logan Allen Over 4.5 Hits',
                           0.6481, 0.4629, 0.1852, ?, ?, 0.02, 20.0, 1000.0,
                           ?, ?, ?, ?)""",
                (gid, model, date, side, odds, line, signal, player, result,
                 created))


# ── The lock ────────────────────────────────────────────────────────────────

def test_a_settled_prop_pick_still_locks_its_key(conn):
    """THE BUG. Grading a pick is not permission to write it again."""
    _game(conn, home_score=7)
    _pick(conn, result="WIN")
    keys = scorer._locked_prop_keys(
        _SqliteShim(conn), "2026-09-04", ["mlb_prop_pitcher_hits"])
    assert ("MLB_2026-09-04_DET_CLE", "mlb_prop_pitcher_hits", "671106") in keys, \
        "a graded pick left the lock set, so the next pass wrote a second copy"


def test_an_unsettled_prop_pick_still_locks_its_key(conn):
    """The half that already worked and must not regress."""
    _game(conn)
    _pick(conn)
    keys = scorer._locked_prop_keys(
        _SqliteShim(conn), "2026-09-04", ["mlb_prop_pitcher_hits"])
    assert len(keys) == 1


def test_a_dead_zone_prop_row_locks_too(conn):
    """Props lock on the first SIGNAL, not on the first bet: a NONE row means
    this player was already scored today against a confirmed lineup. (The game
    board is deliberately the other way round -- see
    tests/test_pick_lock_is_on_picks.py.)"""
    _game(conn)
    _pick(conn, signal="NONE")
    keys = scorer._locked_prop_keys(
        _SqliteShim(conn), "2026-09-04", ["mlb_prop_pitcher_hits"])
    assert len(keys) == 1


def test_another_model_is_not_locked_by_this_pick(conn):
    """The lock is per (game, model, player). Locking wider would silence
    every other prop market on the same pitcher."""
    _game(conn)
    _pick(conn, result="WIN")
    keys = scorer._locked_prop_keys(
        _SqliteShim(conn), "2026-09-04", ["mlb_prop_pitcher_k"])
    assert keys == set()


def test_the_game_lock_does_not_release_on_settlement():
    """Same clause, same fix, on the game board. Unreachable today because the
    game loop only reads games with no final score -- and that is exactly what
    was true of the prop lock's clause until a doubleheader made it reachable."""
    i = SRC.index("locked_pairs: set[tuple] = set()")
    q = SRC[i:SRC.index("locked_pairs.add(", i)]
    stmt = q[q.index('"""'):]
    assert "p.result IS NULL" not in stmt, \
        "settlement must not unlock a pair that already produced a BET"
    assert "p.signal_type = 'BET'" in stmt, \
        "only a BET locks a pair (tests/test_pick_lock_is_on_picks.py)"


# ── The second guard: a game that is already over ───────────────────────────

def test_a_final_game_is_not_a_scoring_target(conn):
    _game(conn, home_score=7)
    assert scorer._final_game_ids(_SqliteShim(conn), "2026-09-04", "MLB") == \
        {"MLB_2026-09-04_DET_CLE"}


def test_a_game_with_no_score_is_still_scoreable(conn):
    _game(conn)
    assert scorer._final_game_ids(_SqliteShim(conn), "2026-09-04", "MLB") == set()


def test_every_prop_scorer_checks_it():
    """Four prop loops (MLB batter, WNBA, NBA, MLB pitcher) share one skip
    line. A loop that checks only the clock re-scores a finished doubleheader
    game 1 all evening."""
    assert SRC.count("or game_id in final_ids:") == 4
    assert SRC.count("final_ids = _final_game_ids(") == 4


# ── The database backstop ───────────────────────────────────────────────────

def test_the_insert_cannot_raise_on_a_duplicate():
    """A unique violation inside executemany aborts the transaction and costs
    the pass every pick it had. Dropping the copy is the safe direction."""
    i = SRC.index("INSERT INTO picks (")
    assert "ON CONFLICT DO NOTHING" in SRC[i:i + 3000]


def test_the_unique_index_migration_is_active():
    from data import view_migrations as vm
    assert "picks_one_row_per_pick.sql" in vm.ACTIVE_MIGRATIONS
    assert (vm.MIGRATIONS_DIR / "picks_one_row_per_pick.sql").exists()


def test_the_index_waits_for_a_clean_table():
    """It must never fail the pipeline against data it cannot fix. While
    duplicates remain it reports them and does nothing."""
    sql = (Path(__file__).parent.parent
           / "data/migrations/picks_one_row_per_pick.sql").read_text(encoding="utf-8")
    assert "HAVING count(*) > 1" in sql
    assert "IF dupes > 0 THEN" in sql
    assert "CREATE UNIQUE INDEX uq_picks_one_row_per_pick" in sql
    assert "WHERE is_live IS NOT TRUE" in sql, "the live lane owns its own rows"


# ── The cleanup's survivor rule ─────────────────────────────────────────────

def _survivors(conn):
    from scripts.dedupe_picks import SELECT_DUPLICATES
    doomed = {r[0] for r in conn.execute(SELECT_DUPLICATES).fetchall()}
    everyone = {r[0] for r in conn.execute("SELECT pick_id FROM picks").fetchall()}
    return everyone - doomed


def test_the_first_copy_is_the_one_that_survives(conn):
    """'It should just be the first one?' -- yes. Timing is data (§1c)."""
    _game(conn, home_score=7)
    _pick(conn, result="WIN", created="2026-09-04 17:21:01+00", odds=116.0)
    for minute in range(14, 45, 10):
        _pick(conn, result="WIN", created=f"2026-09-04 22:{minute}:01+00", odds=117.0)
    assert len(_survivors(conn)) == 1
    kept = conn.execute(
        "SELECT created_at, dk_odds FROM picks WHERE pick_id = ?",
        (list(_survivors(conn))[0],)).fetchone()
    assert kept[0].startswith("2026-09-04 17:21"), "the earliest row is the pick"
    assert kept[1] == 116.0, "and its price is the price that was given"


def test_a_bet_is_never_dropped_for_an_earlier_no_signal(conn):
    """A 6am dead-zone row and a 3pm BET share a key. The BET is the pick --
    dropping it to keep the older row would delete a real bet."""
    _game(conn)
    _pick(conn, signal="NONE", created="2026-09-04 10:00:00+00", odds=100.0)
    _pick(conn, signal="BET", created="2026-09-04 19:00:00+00", odds=116.0)
    survivors = _survivors(conn)
    assert len(survivors) == 1
    assert conn.execute("SELECT signal_type FROM picks WHERE pick_id = ?",
                        (list(survivors)[0],)).fetchone()[0] == "BET"


def test_the_two_sides_of_one_proposition_are_different_picks(conn):
    """Over and Under are written together every pass and are not copies."""
    _game(conn)
    _pick(conn, side="over")
    _pick(conn, side="under")
    assert len(_survivors(conn)) == 2


def test_two_players_in_one_game_are_different_picks(conn):
    """Both starting pitchers get scored for the same (game, model)."""
    _game(conn)
    _pick(conn, player="671106")
    _pick(conn, player="656492")
    assert len(_survivors(conn)) == 2


def test_a_re_scored_line_is_still_the_same_pick(conn):
    """The key deliberately omits scored_line. A duplicate written after the
    line moved is the same bug wearing a different number -- it is the shape
    §1c's NCAAF example calls out (Over 44.5 churned to Over 54.5)."""
    _game(conn, home_score=7)
    _pick(conn, result="WIN", created="2026-09-04 17:21:01+00", line=4.5)
    _pick(conn, result="WIN", created="2026-09-04 22:14:01+00", line=5.5)
    assert len(_survivors(conn)) == 1

"""uq_picks_one_row_per_pick includes player_key + prop_market.

THE BUG (2026-09-13, DAL@NYG). The unique index was
`(game_date, model_id, game_id, COALESCE(player_id, ''), pick_side)`.
`nfl_prop_market` writes `player_key` + `prop_market` and leaves `player_id`
NULL, so every under in a game shared one key and the third INSERT aborted
the card:

    Key (..., COALESCE(player_id, ''), pick_side)=
      (2026-09-13, nfl_prop_market, NFL_2026_01_DAL_NYG, , under)
    already exists.

Matt's call on Reviewer #699 A2: widen the index to the same identity
`tracking/publish_keys.py` already uses for the publish lock_key
(KEY_PARTS = player_id, player_key, prop_market), keeping game_date and
pick_side. Follow-up, not a #699 blocker.

Every test here fails on the pre-fix key. The first one is the collision
itself: two unders, null player_id, different player_key, IntegrityError
on the narrow index.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from data.db_setup import SCHEMA_SQL
from tracking.publish_keys import KEY_PARTS, unique_row_sql

ROOT = Path(__file__).resolve().parent.parent
WIDEN = ROOT / "data" / "migrations" / "widen_picks_one_row_per_pick_2026_09_13.sql"

_NARROW = """
CREATE UNIQUE INDEX uq_narrow ON picks
    (game_date, model_id, game_id, COALESCE(player_id, ''), pick_side)
 WHERE is_live IS NOT TRUE
"""
_WIDE = f"""
CREATE UNIQUE INDEX uq_wide ON picks
    ({unique_row_sql()})
 WHERE is_live IS NOT TRUE
"""


@pytest.fixture
def conn():
    raw = sqlite3.connect(":memory:")
    raw.executescript(SCHEMA_SQL)
    raw.execute("ALTER TABLE picks ADD COLUMN player_id TEXT")
    raw.execute("ALTER TABLE picks ADD COLUMN is_live BOOLEAN DEFAULT 0")
    raw.execute("""INSERT INTO games (game_id, sport, season, game_date,
                   home_team, away_team, commence_time)
                   VALUES ('NFL_2026_01_DAL_NYG','NFL',2026,'2026-09-13',
                           'NYG','DAL','2026-09-13T17:00:00+00:00')""")
    yield raw
    raw.close()


def _prop(raw, *, player_key, prop_market, side="under", player_id=None,
          model="nfl_prop_market"):
    raw.execute("""INSERT INTO picks (game_id, model_id, sport, game_date,
                   pick_side, pick_label, model_probability, dk_implied_prob,
                   edge, dk_odds, scored_line, kelly_fraction, recommended_bet,
                   bankroll_at_pick, signal_type, player_id, player_key,
                   prop_market)
                   VALUES ('NFL_2026_01_DAL_NYG', ?, 'NFL', '2026-09-13',
                           ?, 'label', 0.55, 0.48, 0.07, -110, 1.5,
                           0.01, 10.0, 1000.0, 'BET', ?, ?, ?)""",
                (model, side, player_id, player_key, prop_market))


def test_the_narrow_index_collides_null_player_id_props(conn):
    """THE BUG. Watched to fail on the key that shipped 2026-09-05."""
    conn.execute(_NARROW)
    _prop(conn, player_key="dakprescott", prop_market="player_pass_yds")
    with pytest.raises(sqlite3.IntegrityError):
        _prop(conn, player_key="ceedeelamb", prop_market="player_receptions")


def test_the_widened_index_allows_null_player_id_props(conn):
    """Two DAL@NYG unders, different player_key + prop_market, both stand."""
    conn.execute(_WIDE)
    _prop(conn, player_key="dakprescott", prop_market="player_pass_yds")
    _prop(conn, player_key="ceedeelamb", prop_market="player_receptions")
    n = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
    assert n == 2


def test_the_same_proposition_still_collides_on_the_widened_index(conn):
    """Widening must not admit a second copy of the same pick."""
    conn.execute(_WIDE)
    _prop(conn, player_key="dakprescott", prop_market="player_pass_yds")
    with pytest.raises(sqlite3.IntegrityError):
        _prop(conn, player_key="dakprescott", prop_market="player_pass_yds")


def test_player_id_uniqueness_is_unchanged(conn):
    """A distributional prop row carries player_id and neither new column.
    Two players stay two rows; two copies of one player stay one key."""
    conn.execute(_WIDE)
    _prop(conn, player_key=None, prop_market=None, player_id="00-0038997",
          model="nfl_prop_receptions")
    _prop(conn, player_key=None, prop_market=None, player_id="00-0035228",
          model="nfl_prop_receptions")
    assert conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0] == 2
    with pytest.raises(sqlite3.IntegrityError):
        _prop(conn, player_key=None, prop_market=None, player_id="00-0038997",
              model="nfl_prop_receptions")


def test_unique_row_sql_is_key_parts_plus_date_and_side():
    """The unique index is the publish identity plus game_date and pick_side.
    pick_side stays IN this key (two sides are two rows) and OUT of the
    publish lock_key (a side flip is one announcement)."""
    sql = unique_row_sql()
    assert sql.startswith("game_date, model_id, game_id, ")
    assert sql.endswith(", pick_side")
    for i, col in enumerate(KEY_PARTS):
        assert f"COALESCE({col}, '')" in sql
        if i + 1 < len(KEY_PARTS):
            assert sql.index(KEY_PARTS[i]) < sql.index(KEY_PARTS[i + 1])
    aliased = unique_row_sql("p")
    assert aliased.startswith("p.game_date, p.model_id, p.game_id, ")
    assert "COALESCE(p.player_id, '')" in aliased
    assert "COALESCE(p.player_key, '')" in aliased
    assert "COALESCE(p.prop_market, '')" in aliased


def test_the_widen_migration_is_property_guarded():
    """Guard on the PROPERTY (indexdef contains player_key AND prop_market),
    never on 'index exists' — that lock would skip forever on the narrow
    definition the 2026-09-05 file already created in production."""
    sql = WIDEN.read_text(encoding="utf-8")
    assert "position('player_key' in def)" in sql
    assert "position('prop_market' in def)" in sql
    assert "uq_picks_one_row_per_pick_v2" in sql
    assert "DROP INDEX IF EXISTS public.uq_picks_one_row_per_pick" in sql
    assert sql.index("CREATE UNIQUE INDEX uq_picks_one_row_per_pick_v2") < \
        sql.index("DROP INDEX IF EXISTS public.uq_picks_one_row_per_pick")
    for col in KEY_PARTS:
        assert f"COALESCE({col}, '')" in sql
    assert "WHERE is_live IS NOT TRUE" in sql
    assert "IF dupes > 0 THEN" in sql


def test_dedupe_and_health_use_the_shared_tuple():
    """A hand-copied GROUP BY would re-introduce the narrow key the next
    time KEY_PARTS grows."""
    from scripts.dedupe_picks import SELECT_DUPLICATES
    health = (ROOT / "tracking" / "system_health.py").read_text(encoding="utf-8")
    assert unique_row_sql("p") in SELECT_DUPLICATES
    assert "GROUP BY {unique_row_sql()}" in health


def test_the_card_insert_tolerates_the_unique_index():
    """An IntegrityError inside publish() aborts the card — that is the
    DAL@NYG failure. Dropping the copy is the safe direction."""
    src = (ROOT / "scripts" / "nfl_prop_market_card.py").read_text(encoding="utf-8")
    i = src.index("INSERT INTO picks (")
    assert "ON CONFLICT DO NOTHING" in src[i:i + 800]

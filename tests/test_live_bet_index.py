"""A live BET survives an AVOID on the same lane.

uq_picks_one_live_row first covered every non-DUPLICATE live row. The NFL
writer inserts the AVOID, then the BET, with ON CONFLICT DO NOTHING. The
AVOID held the key and the BET was dropped. The index is standing BETs
only. A second BET still conflicts. The AVOID is not deleted.

Measured read-only on 2026-10-14: production already has the wider index,
and zero live identity groups have two standing BETs.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NARROW = ROOT / "data/migrations/live_row_index_bets_only_2026_10_14.sql"

# Catalog text of the two indexes. The publish-lock string is the definition
# read from production on 2026-10-14. The live strings are that day's wider
# definition, and the same text with signal_type = 'BET' added the way
# Postgres prints the other index's predicate.
PUBLISH_DEF = """CREATE UNIQUE INDEX uq_picks_one_bet_per_publish_lock ON public.picks USING btree ((
CASE
    WHEN COALESCE(is_live, false) THEN (((((((('live:'::text || game_id) || ':'::text) || model_id) || ':'::text) || COALESCE(pick_side, ''::text)) || COALESCE((':'::text || player_id), ''::text)) || COALESCE((':'::text || player_key), ''::text)) || COALESCE((':'::text || prop_market), ''::text))
    ELSE (((((game_id || ':'::text) || model_id) || COALESCE((':'::text || player_id), ''::text)) || COALESCE((':'::text || player_key), ''::text)) || COALESCE((':'::text || prop_market), ''::text))
END)) WHERE ((signal_type = 'BET'::text) AND (condition_status IS DISTINCT FROM 'DUPLICATE'::text) AND (condition_status IS DISTINCT FROM 'VOID'::text) AND (result IS DISTINCT FROM 'NO_ACTION'::text))"""

LIVE_WIDE = (
    "CREATE UNIQUE INDEX uq_picks_one_live_row ON public.picks USING btree "
    "(game_date, model_id, game_id, COALESCE(player_id, ''::text), "
    "COALESCE(player_key, ''::text), COALESCE(prop_market, ''::text), "
    "pick_side) WHERE ((is_live IS TRUE) AND "
    "(condition_status IS DISTINCT FROM 'DUPLICATE'::text))"
)
LIVE_NARROW = LIVE_WIDE.replace(
    "(is_live IS TRUE) AND ",
    "(is_live IS TRUE) AND (signal_type = 'BET'::text) AND ",
)
LIVE_NARROW_CAST = LIVE_WIDE.replace(
    "(is_live IS TRUE) AND ",
    "(is_live IS TRUE) AND ((signal_type)::text = 'BET'::text) AND ",
)

_COLS = ("game_date, model_id, game_id, player_id, player_key, prop_market, "
         "pick_side, signal_type, is_live, condition_status, label")


def _db(where: str) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute(f"""
        CREATE TABLE picks (
            game_date TEXT, model_id TEXT, game_id TEXT,
            player_id TEXT, player_key TEXT, prop_market TEXT,
            pick_side TEXT, signal_type TEXT, is_live INT,
            condition_status TEXT, label TEXT
        )
    """)
    db.execute(f"""
        CREATE UNIQUE INDEX uq_picks_one_live_row ON picks (
            game_date, model_id, game_id,
            COALESCE(player_id, ''),
            COALESCE(player_key, ''),
            COALESCE(prop_market, ''),
            pick_side
        ) WHERE {where}
    """)
    return db


def _insert(db, signal, *, side="under", status=None, label="row"):
    db.execute(
        f"INSERT INTO picks ({_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT DO NOTHING",
        ("2026-10-18", "nfl_live_prop", "NFL_2026_07_BUF_HOU",
         "CJ STROUD", "CJ STROUD", "player_rush_attempts",
         side, signal, 1, status, label),
    )


def _signals(db):
    return db.execute(
        "SELECT signal_type, label FROM picks ORDER BY rowid"
    ).fetchall()


def test_the_wide_index_drops_the_bet_that_follows_an_avoid():
    """Watched on the predicate that shipped. The BET insert is a no-op."""
    db = _db("is_live IS TRUE AND condition_status IS DISTINCT FROM 'DUPLICATE'")
    _insert(db, "AVOID", label="avoid")
    _insert(db, "BET", label="bet")
    assert _signals(db) == [("AVOID", "avoid")]


def test_a_live_bet_survives_an_avoid_on_the_same_lane():
    db = _db(
        "is_live IS TRUE AND signal_type = 'BET' "
        "AND condition_status IS DISTINCT FROM 'DUPLICATE'"
    )
    _insert(db, "AVOID", label="avoid")
    _insert(db, "BET", label="bet")
    assert _signals(db) == [("AVOID", "avoid"), ("BET", "bet")]


def test_a_second_live_bet_on_the_same_lane_still_conflicts():
    db = _db(
        "is_live IS TRUE AND signal_type = 'BET' "
        "AND condition_status IS DISTINCT FROM 'DUPLICATE'"
    )
    _insert(db, "BET", label="first")
    _insert(db, "BET", label="second")
    assert _signals(db) == [("BET", "first")]
    _insert(db, "BET", side="over", label="other side")
    _insert(db, "BET", status="DUPLICATE", label="marked copy")
    kinds = [row[0] for row in _signals(db)]
    assert kinds.count("BET") == 3
    assert ("BET", "first") in _signals(db)
    assert ("BET", "second") not in _signals(db)


def test_the_narrowing_migration_is_property_guarded_and_registered():
    """Prod may already have the wide index. 'name exists' would skip it."""
    from data.view_migrations import ACTIVE_MIGRATIONS
    sql = NARROW.read_text(encoding="utf-8")
    code = "\n".join(ln for ln in sql.splitlines()
                     if not ln.lstrip().startswith("--"))
    assert NARROW.name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index("discord_post_one_pick_2026_10_14.sql") < \
        ACTIVE_MIGRATIONS.index(NARROW.name)
    assert ACTIVE_MIGRATIONS.index(NARROW.name) < \
        ACTIVE_MIGRATIONS.index("published_picks_record_2026_10_14.sql")
    # published_record_units reads the live view and stays last.
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    assert sql.count("$mig$") == 2
    assert "CREATE INDEX CONCURRENTLY" not in code
    assert "CONCURRENTLY" in sql
    assert "UPDATE public.picks" not in code
    assert "INSERT INTO push_sent" not in code
    assert "position('signal_type' in def)" in sql
    assert "position('BET' in def)" in sql
    assert "uq_picks_one_live_row_v2" in sql
    assert "DROP INDEX IF EXISTS public.uq_picks_one_live_row;" in code
    assert code.index("CREATE UNIQUE INDEX uq_picks_one_live_row_v2") < \
        code.index("DROP INDEX IF EXISTS public.uq_picks_one_live_row;")
    where = sql.split("CREATE UNIQUE INDEX uq_picks_one_live_row_v2", 1)[1]
    where = where.split("WHERE", 1)[1].split(";", 1)[0]
    assert "signal_type = 'BET'" in where
    assert "is_live IS TRUE" in where
    assert "DUPLICATE" in where
    assert "IF dupes > 0 THEN" in sql
    assert "RAISE EXCEPTION" not in sql


def test_the_health_check_accepts_both_definitions_and_rejects_the_wide_one():
    from tracking.system_health import pick_unique_index_problems
    assert pick_unique_index_problems([
        ("uq_picks_one_bet_per_publish_lock", PUBLISH_DEF),
        ("uq_picks_one_live_row", LIVE_NARROW),
    ]) == []
    assert pick_unique_index_problems([
        ("uq_picks_one_bet_per_publish_lock", PUBLISH_DEF),
        ("uq_picks_one_live_row", LIVE_NARROW_CAST),
    ]) == []
    wide = pick_unique_index_problems([
        ("uq_picks_one_bet_per_publish_lock", PUBLISH_DEF),
        ("uq_picks_one_live_row", LIVE_WIDE),
    ])
    assert any("uq_picks_one_live_row" in p and "signal_type" in p for p in wide)
    missing = pick_unique_index_problems([])
    assert any("uq_picks_one_live_row is missing" in p for p in missing)
    assert any("uq_picks_one_bet_per_publish_lock is missing" in p for p in missing)
    health = (ROOT / "tracking/system_health.py").read_text(encoding="utf-8")
    assert "pick_unique_index_problems" in health
    assert "FROM pg_indexes" in health
    assert '"pick_unique_indexes"' in health or "'pick_unique_indexes'" in health


def test_the_nfl_writer_does_not_delete_the_avoid_to_make_room():
    """The safer fix leaves the AVOID in place. Deleting it was the other one."""
    src = (ROOT / "nfl/live_model/pick_writer.py").read_text(encoding="utf-8")
    write = src.split("def _write(", 1)[1].split("\n    def ", 1)[0]
    assert "DELETE" not in write
    assert "ON CONFLICT DO NOTHING" in src


def test_mlb_and_ncaaf_already_clear_the_standing_non_bet_before_insert():
    """Those writers delete signal_type <> 'BET' and then insert. A standing
    AVOID is gone before ON CONFLICT, so they do not drop the BET. No change
    to that delete: it is the lane's rewrite, and it does not delete a BET.
    """
    mlb = (ROOT / "models/live_scorer.py").read_text(encoding="utf-8")
    body = mlb.split("def _write_live_picks(", 1)[1].split("\ndef ", 1)[0]
    assert body.index("signal_type <> 'BET'") < body.index("_insert_picks(")
    ncaaf = (ROOT / "ncaaf_live/gameday.py").read_text(encoding="utf-8")
    write = ncaaf.split("def write_picks(", 1)[1].split("\ndef ", 1)[0]
    assert write.index("signal_type <> 'BET'") < write.index("_insert_picks(")
    repair = (ROOT / "tracking/first_signal_repair.py").read_text(encoding="utf-8")
    assert "ON CONFLICT" not in repair.split("def restore_first_signals", 1)[1]


def test_a_void_notice_sibling_query_keeps_a_published_bet():
    """The sideless pregame key. A VOID and a still-valid BET share it.
    The query returns the BET and ignores an AVOID, a VOID, a DUPLICATE,
    a NO_ACTION, and a live row.
    """
    from tracking.discord_notifier import posted_sibling_sql
    from tracking.publish_keys import lock_key_sql

    db = sqlite3.connect(":memory:")
    db.execute("""
        CREATE TABLE picks (
            pick_id INT, is_live INT, signal_type TEXT,
            condition_status TEXT, result TEXT, game_id TEXT, model_id TEXT,
            player_id TEXT, player_key TEXT, prop_market TEXT, pick_side TEXT
        )
    """)
    rows = [
        (1, 0, "BET", None, None, "G", "m", None, None, None, "home"),
        (2, 0, "BET", "VOID", "NO_ACTION", "G", "m", None, None, None, "away"),
        (3, 0, "AVOID", None, None, "G", "m", None, None, None, "away"),
        (4, 0, "BET", "DUPLICATE", None, "G", "m", None, None, None, "home"),
        (5, 0, "BET", None, "NO_ACTION", "G", "m", None, None, None, "home"),
        (6, 1, "BET", None, None, "G", "m", None, None, None, "home"),
        (7, 0, "BET", None, "WIN", "G", "other", None, None, None, "home"),
    ]
    db.executemany("INSERT INTO picks VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    sql = posted_sibling_sql().replace("%s", "?")
    assert lock_key_sql("sib") in sql
    assert db.execute(sql, (2, "G:m")).fetchall() == [(1,)]
    assert db.execute(sql, (1, "G:m")).fetchall() == []
    assert db.execute(sql, (7, "G:other")).fetchall() == []

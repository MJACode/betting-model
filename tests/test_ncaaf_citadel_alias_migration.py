"""
The one-off that consolidates the five Citadel alias rows onto their CFBD ids.

Measured 2026-10-16: The Odds API writes "Citadel Bulldogs", CFBD's school is
"The Citadel", and the resolver minted an alias games row for every Citadel
matchup it priced since 2023. The live one, Texas A&M 2026-10-17, held 605
odds rows and 12 latest_odds the CFBD id would never see; Charlotte 2026-09-05
held 8,639. No alias carried a pick. The worker applies this from
view_migrations because the Supabase connector available to sessions is
read-only.
"""
from __future__ import annotations

from pathlib import Path

MIG = (Path(__file__).parent.parent
       / "data/migrations/ncaaf_citadel_alias_2026_10_16.sql")
CODE = MIG.read_text(encoding="utf-8")

PAIRS = [
    ("NCAAF_2023-09-02_the-citadel_georgia-southern",
     "NCAAF_2023-09-02_citadel-bulldogs_georgia-southern"),
    ("NCAAF_2024-11-23_the-citadel_clemson",
     "NCAAF_2024-11-23_citadel-bulldogs_clemson"),
    ("NCAAF_2025-11-08_the-citadel_ole-miss",
     "NCAAF_2025-11-08_citadel-bulldogs_ole-miss"),
    ("NCAAF_2026-09-05_the-citadel_charlotte",
     "NCAAF_2026-09-05_citadel-bulldogs_charlotte"),
    ("NCAAF_2026-10-17_the-citadel_texas-a-m",
     "NCAAF_2026-10-17_citadel-bulldogs_texas-a-m"),
]


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    """The runner uses conn.execute(), never executescript; a second top-level
    statement would be shredded at its semicolons."""
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_it_names_every_measured_pair_and_keeps_the_cfbd_id():
    for canon, alias in PAIRS:
        assert f"'{canon}'" in CODE
        assert f"'{alias}'" in CODE
    # The CFBD row is the first of each pair, so it is what `canon` receives.
    for canon, alias in PAIRS:
        assert CODE.index(f"'{canon}'") < CODE.index(f"'{alias}'")
    assert "away_team = 'The Citadel'" in CODE
    assert "away_team = 'Citadel Bulldogs'" in CODE


def test_the_map_entry_that_stops_the_next_alias_ships_with_it():
    import config
    assert config.NCAAF_ODDS_API_MAP.get("Citadel Bulldogs") == "The Citadel"


def test_it_deletes_the_alias_games_row_and_never_the_canonical():
    assert "DELETE FROM games" in CODE
    assert "WHERE game_id = alias" in CODE
    assert "DELETE FROM games\n         WHERE game_id = canon" not in CODE
    assert "WHERE game_id = canon\n" not in CODE.split("DELETE FROM games")[1]


def test_a_pick_is_never_deleted_and_never_regraded():
    """CLAUDE.md 1c: consolidate by moving game_id, never by dropping the row
    or stamping a result. If a unique collision leaves a pick on the alias,
    the games delete is refused."""
    assert "DELETE FROM picks" not in CODE
    assert "SET result" not in CODE
    assert "leftover odds/picks on alias" in CODE
    assert "UPDATE picks SET game_id = canon WHERE game_id = alias" in CODE


def test_it_guards_on_the_alias_being_unscored_and_still_named_so():
    """A second pass is a no-op: the alias renamed, scored or already deleted
    skips the pair at the top, and the final delete repeats the guard."""
    assert CODE.count("AND away_team = 'Citadel Bulldogs'") >= 2
    assert CODE.count("AND home_score IS NULL") >= 2
    assert "CONTINUE;" in CODE


def test_latest_odds_never_collide_on_the_canonical_key():
    """latest_odds is keyed (game_id, market, bookmaker). A row moves only
    when the canonical lacks that key; the rest of the alias copies go."""
    assert "NOT EXISTS (SELECT 1 FROM latest_odds c" in CODE
    assert "AND c.market = l.market" in CODE
    assert "AND c.bookmaker = l.bookmaker" in CODE
    assert "DELETE FROM latest_odds WHERE game_id = alias" in CODE


def test_odds_move_as_a_whole():
    """Live-book rows beside cfbd_* history is the normal state of every
    priced CFBD game (2024-11-23 Clemson has both), so odds are not gated on
    the canonical being empty the way the SE Louisiana one-off was."""
    assert "UPDATE odds SET game_id = canon WHERE game_id = alias" in CODE
    assert "IF NOT EXISTS (SELECT 1 FROM odds WHERE game_id = canon)" not in CODE


# ── the migration on a real server ───────────────────────────────────────────
#
# The runner is a single conn.execute of a PL/pgSQL DO block with a FOREACH
# SLICE loop; nothing above proves that parses or that the per-table rules do
# what the comments say. A scratch cluster (tests/_pg.py) with stub tables
# seeded in the measured shapes does. One deliberate departure from
# production: the 2024 alias is given a latest_odds key the canonical already
# holds, so the "move only when the key is free, drop the rest" branch is
# exercised (production had no overlap).

import pytest  # noqa: E402

from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

STUB = """
CREATE TABLE games (game_id TEXT PRIMARY KEY, sport TEXT, home_team TEXT,
    away_team TEXT, home_score NUMERIC, away_score NUMERIC, data_source TEXT);
CREATE TABLE odds (odds_id SERIAL PRIMARY KEY,
    game_id TEXT REFERENCES games(game_id), bookmaker TEXT, market TEXT);
CREATE TABLE picks (pick_id SERIAL PRIMARY KEY,
    game_id TEXT REFERENCES games(game_id), result TEXT);
CREATE TABLE picks_log (game_id TEXT);
CREATE TABLE player_prop_odds (game_id TEXT REFERENCES games(game_id));
CREATE TABLE latest_odds (game_id TEXT, market TEXT, bookmaker TEXT,
    PRIMARY KEY (game_id, market, bookmaker));
CREATE TABLE game_weather (weather_id SERIAL PRIMARY KEY, game_id TEXT UNIQUE);
"""

LIVE_BOOKS = ["betmgm", "draftkings", "espnbet", "fanduel", "hardrockbet", "pinnacle"]


def _seed(cur):
    homes = {"georgia-southern": "Georgia Southern", "clemson": "Clemson",
             "ole-miss": "Ole Miss", "charlotte": "Charlotte", "texas-a-m": "Texas A&M"}
    finals = {"georgia-southern": (34, 0), "clemson": (51, 14), "ole-miss": (49, 0),
              "charlotte": (41, 43), "texas-a-m": (None, None)}
    for canon, alias in PAIRS:
        slug = canon.rsplit("_", 1)[1]
        hs, as_ = finals[slug]
        cur.execute("INSERT INTO games VALUES (%s,'NCAAF',%s,'The Citadel',%s,%s,'cfbd')",
                    (canon, homes[slug], hs, as_))
        cur.execute("INSERT INTO games VALUES (%s,'NCAAF',%s,'Citadel Bulldogs',NULL,NULL,'live')",
                    (alias, homes[slug]))
        cur.execute("INSERT INTO game_weather (game_id) VALUES (%s)", (canon,))
    # 2023 and 2025 aliases: empty. 2024: cfbd history on canon, 6 live books on alias.
    canon24, alias24 = PAIRS[1]
    for m in ("spreads", "totals"):
        cur.execute("INSERT INTO odds (game_id, bookmaker, market) VALUES (%s,'cfbd_draftkings',%s)", (canon24, m))
        cur.execute("INSERT INTO latest_odds VALUES (%s,%s,'cfbd_draftkings')", (canon24, m))
        for b in LIVE_BOOKS:
            cur.execute("INSERT INTO odds (game_id, bookmaker, market) VALUES (%s,%s,%s)", (alias24, b, m))
            if b in ("betmgm", "draftkings", "fanduel", "pinnacle"):
                cur.execute("INSERT INTO latest_odds VALUES (%s,%s,%s)", (alias24, m, b))
    # the deliberate overlap: alias carries a key the canonical already holds
    cur.execute("INSERT INTO latest_odds VALUES (%s,'spreads','cfbd_draftkings')", (alias24,))
    # Charlotte and Texas A&M aliases: odds, latest_odds and weather of their own.
    for canon, alias, n_odds, n_latest in ((*PAIRS[3], 10, 4), (*PAIRS[4], 5, 3)):
        for i in range(n_odds):
            cur.execute("INSERT INTO odds (game_id, bookmaker, market) VALUES (%s,%s,'spreads')",
                        (alias, LIVE_BOOKS[i % 6]))
        for i in range(n_latest):
            cur.execute("INSERT INTO latest_odds VALUES (%s,'spreads',%s)", (alias, LIVE_BOOKS[i]))
        cur.execute("INSERT INTO game_weather (game_id) VALUES (%s)", (alias,))


def _counts(cur, table, game_id):
    cur.execute(f"SELECT count(*) FROM {table} WHERE game_id = %s", (game_id,))
    return cur.fetchone()[0]


@pytest.mark.skipif(not (env_dsn() or can_scratch()),
                    reason="needs a scratch Postgres (tests/_pg.py)")
def test_it_consolidates_the_measured_shapes_and_a_second_pass_is_a_noop():
    psycopg2 = pytest.importorskip("psycopg2")
    with scratch_cluster("citadel-alias-pg-") as dsn:
        conn = psycopg2.connect(dsn)
        conn.set_client_encoding("UTF8")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(STUB)
        _seed(cur)

        cur.execute(CODE)
        notices = [n.strip() for n in conn.notices]
        assert sum("consolidated" in n for n in notices) == 5, notices
        assert not any("leftover" in n for n in notices), notices

        for canon, alias in PAIRS:
            assert _counts(cur, "games", alias) == 0
            assert _counts(cur, "games", canon) == 1
            assert _counts(cur, "odds", alias) == 0
            assert _counts(cur, "latest_odds", alias) == 0
            assert _counts(cur, "game_weather", alias) == 0
            assert _counts(cur, "game_weather", canon) == 1
        canon24 = PAIRS[1][0]
        assert _counts(cur, "odds", canon24) == 2 + 12   # history kept, live rows moved
        cur.execute("SELECT market, bookmaker FROM latest_odds WHERE game_id = %s ORDER BY 1, 2", (canon24,))
        keys = cur.fetchall()
        assert len(keys) == 2 + 8                           # the overlapping copy was dropped, not doubled
        assert keys.count(("spreads", "cfbd_draftkings")) == 1
        assert _counts(cur, "odds", PAIRS[3][0]) == 10
        assert _counts(cur, "latest_odds", PAIRS[3][0]) == 4
        assert _counts(cur, "odds", PAIRS[4][0]) == 5
        assert _counts(cur, "latest_odds", PAIRS[4][0]) == 3
        # finals untouched
        cur.execute("SELECT home_score, away_score FROM games WHERE game_id = %s", (PAIRS[3][0],))
        assert tuple(cur.fetchone()) == (41, 43)

        del conn.notices[:]
        cur.execute(CODE)
        assert conn.notices == []
        assert _counts(cur, "odds", canon24) == 14
        conn.close()

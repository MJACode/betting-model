"""
The one-off that consolidates the William & Mary, LIU and Houston Christian
nickname rows onto their CFBD ids.

Measured 2026-11-13 (read-only): eleven NCAAF games from 2023-09-09 to
2026-09-26 each have a CFBD row (scored, data_source cfbd) and a row the odds
ingest minted from the Odds API's nickname for the FCS visitor (unscored,
data_source live). The nickname rows hold 1,805 odds rows the CFBD ids never
saw (519 / 486 / 323 on the three 2026-09-26 games); no pick is on any of
them. The worker applies this from view_migrations because the Supabase
connector available to sessions is read-only.

The first version of this file (2026-10-21) did nothing on production: it
required the CFBD row to be unscored, and all eleven are final. The real-
server test below runs that shape and fails on it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

MIG = (Path(__file__).parent.parent
       / "data/migrations/ncaaf_fcs_opponent_alias_2026_10_21.sql")
CODE = MIG.read_text(encoding="utf-8")

# (canon, alias, home, away_canon, away_alias, alias odds, canon odds,
#  alias weather) as measured 2026-11-13.
PAIRS = (
    ("NCAAF_2023-09-09_houston-christian_western-kentucky",
     "NCAAF_2023-09-09_houston-baptist-huskies_western-kentucky",
     "Western Kentucky", "Houston Christian", "Houston Baptist Huskies", 0, 0, 0),
    ("NCAAF_2023-09-16_long-island-university_baylor",
     "NCAAF_2023-09-16_liu-sharks_baylor",
     "Baylor", "Long Island University", "LIU Sharks", 16, 0, 0),
    ("NCAAF_2023-10-07_william-mary_virginia",
     "NCAAF_2023-10-07_william-and-mary-tribe_virginia",
     "Virginia", "William & Mary", "William and Mary Tribe", 15, 0, 0),
    ("NCAAF_2024-09-07_william-mary_coastal-carolina",
     "NCAAF_2024-09-07_william-and-mary-tribe_coastal-carolina",
     "Coastal Carolina", "William & Mary", "William and Mary Tribe", 48, 0, 0),
    ("NCAAF_2025-08-30_long-island-university_florida",
     "NCAAF_2025-08-30_liu-sharks_florida",
     "Florida", "Long Island University", "LIU Sharks", 134, 2, 0),
    ("NCAAF_2025-09-06_long-island-university_eastern-michigan",
     "NCAAF_2025-09-06_liu-sharks_eastern-michigan",
     "Eastern Michigan", "Long Island University", "LIU Sharks", 177, 3, 0),
    ("NCAAF_2025-09-13_houston-christian_nebraska",
     "NCAAF_2025-09-13_houston-baptist-huskies_nebraska",
     "Nebraska", "Houston Christian", "Houston Baptist Huskies", 35, 4, 0),
    ("NCAAF_2025-09-13_william-mary_virginia",
     "NCAAF_2025-09-13_william-and-mary-tribe_virginia",
     "Virginia", "William & Mary", "William and Mary Tribe", 52, 6, 0),
    ("NCAAF_2026-09-26_william-mary_duke",
     "NCAAF_2026-09-26_william-and-mary-tribe_duke",
     "Duke", "William & Mary", "William and Mary Tribe", 519, 0, 1),
    ("NCAAF_2026-09-26_long-island-university_florida-international",
     "NCAAF_2026-09-26_liu-sharks_florida-international",
     "Florida International", "Long Island University", "LIU Sharks", 486, 0, 1),
    ("NCAAF_2026-09-26_houston-christian_north-texas",
     "NCAAF_2026-09-26_houston-baptist-huskies_north-texas",
     "North Texas", "Houston Christian", "Houston Baptist Huskies", 323, 0, 1),
)

# Seen in the same query and deliberately left alone: the CFBD twin is under
# the UTC date (the night-game split), or the name is a different defect.
NOT_HANDLED = (
    "NCAAF_2024-09-07_liu-sharks_tcu",
    "NCAAF_2026-09-04_liu-sharks_kansas",
    "NCAAF_2023-09-09_houston_western-kentucky",
)


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS
    assert "ncaaf_fcs_opponent_alias_2026_09_22.sql" not in ACTIVE_MIGRATIONS
    pick_units = "published_pick_units_2026_10_17.sql"
    units = "published_record_units_2026_10_16.sql"
    assert ACTIVE_MIGRATIONS[-1] == units
    # The posted-stake functions and the view that reads them stay adjacent,
    # with the view last. This file is the entry immediately before that pair.
    assert ACTIVE_MIGRATIONS.index(pick_units) == ACTIVE_MIGRATIONS.index(units) - 1
    assert ACTIVE_MIGRATIONS.index(MIG.name) == ACTIVE_MIGRATIONS.index(pick_units) - 1


def test_migration_is_one_statement():
    """The runner uses conn.execute(), never executescript; a second top-level
    statement would be shredded at its semicolons."""
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_it_names_every_measured_pair_and_keeps_the_cfbd_id():
    body = CODE.split("DO $$", 1)[1]
    for canon, alias, home, away_canon, away_alias, *_ in PAIRS:
        assert f"'{canon}'" in body
        assert f"'{alias}'" in body
        assert f"'{home}'" in body
        assert f"'{away_canon}'" in body
        assert f"'{away_alias}'" in body
        # The CFBD row is the first of each pair, so it is what `canon` receives.
        assert body.index(f"'{canon}'") < body.index(f"'{alias}'")
    for game_id in NOT_HANDLED:
        assert f"'{game_id}'" not in body


def test_the_map_entries_that_stop_the_next_alias_ship_with_it():
    import config
    m = config.NCAAF_ODDS_API_MAP
    assert m.get("William and Mary Tribe") == "William & Mary"
    assert m.get("LIU Sharks") == "Long Island University"
    assert m.get("Houston Baptist Huskies") == "Houston Christian"


def test_it_deletes_the_alias_games_row_and_never_the_canonical():
    assert "DELETE FROM games" in CODE
    after = CODE.split("DELETE FROM games", 1)[1].split(";", 1)[0]
    assert "WHERE game_id = alias" in after
    assert "canon" not in after


def test_a_pick_is_never_deleted_and_never_regraded():
    """CLAUDE.md 1c: consolidate by moving game_id, never by dropping the row
    or stamping a result. A pick that would collide on the canon stays where
    it is, and the games delete is refused."""
    assert "DELETE FROM picks" not in CODE
    assert "SET result" not in CODE
    assert "leftover odds/picks on alias" in CODE


def test_the_guard_is_the_alias_still_existing_not_the_canon_being_unscored():
    """The 2026-10-21 version required the CFBD row to be unscored; every one
    is final, so it never ran. The canon check names the school only."""
    canon_guard = CODE.split("WHERE game_id = canon AND sport = 'NCAAF'", 1)[1]
    canon_guard = canon_guard.split(")", 1)[0]
    assert "home_score" not in canon_guard
    assert CODE.count("AND home_score IS NULL") >= 2     # alias guard + delete
    assert "CONTINUE;" in CODE


def test_odds_move_as_a_whole():
    """cfbd_* history beside live-book rows is the normal state of a priced
    CFBD game, and five of these canons hold cfbd_* rows, so odds are not
    gated on the canon being empty."""
    assert "UPDATE odds SET game_id = canon WHERE game_id = alias" in CODE
    assert "IF NOT EXISTS (SELECT 1 FROM odds WHERE game_id = canon)" not in CODE


def test_picks_log_is_not_scanned():
    """No index on game_id, no foreign key to games, 2.4 GB, and no pick on
    any alias: an UPDATE would be a full scan for rows that cannot exist."""
    assert "UPDATE picks_log" not in CODE


# ── the migration on a real server ───────────────────────────────────────────
#
# Stub tables in the production shapes that matter here: the odds -> games
# foreign key that blocks the delete, the 4-column latest_odds key, the
# per-row odds UPDATE trigger that recomputes latest_odds for the old and the
# new key (a cut-down latest_odds_recompute), game_weather UNIQUE(game_id),
# and the derivative purchase ledger keyed (game_id, read_slot).

from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

needs_pg = pytest.mark.skipif(not (env_dsn() or can_scratch()),
                              reason="needs a scratch Postgres (tests/_pg.py)")

STUB = """
CREATE TABLE games (game_id TEXT PRIMARY KEY, sport TEXT, home_team TEXT,
    away_team TEXT, home_score NUMERIC, away_score NUMERIC, data_source TEXT);
CREATE TABLE odds (odds_id SERIAL PRIMARY KEY,
    game_id TEXT REFERENCES games(game_id), bookmaker TEXT, market TEXT,
    snapshot_type TEXT, snapshot_at TEXT, source TEXT);
CREATE TABLE picks (pick_id SERIAL PRIMARY KEY,
    game_id TEXT REFERENCES games(game_id), model_id TEXT, result TEXT);
CREATE TABLE player_prop_odds (game_id TEXT REFERENCES games(game_id));
CREATE TABLE latest_odds (game_id TEXT, market TEXT, bookmaker TEXT,
    line_key TEXT, snapshot_at TEXT, odds_id INTEGER,
    PRIMARY KEY (game_id, market, bookmaker, line_key));
CREATE TABLE game_weather (weather_id SERIAL PRIMARY KEY, game_id TEXT UNIQUE);
CREATE TABLE ncaaf_derivative_fetches (game_id TEXT, read_slot TEXT,
    status TEXT, PRIMARY KEY (game_id, read_slot));

CREATE FUNCTION latest_odds_recompute(p_game_id TEXT, p_market TEXT, p_bookmaker TEXT)
RETURNS void LANGUAGE plpgsql AS $f$
BEGIN
    DELETE FROM latest_odds
     WHERE game_id = p_game_id AND market = p_market AND bookmaker = p_bookmaker;
    INSERT INTO latest_odds (game_id, market, bookmaker, line_key, snapshot_at, odds_id)
    SELECT o.game_id, o.market, o.bookmaker, '0', o.snapshot_at, o.odds_id
      FROM odds o
     WHERE o.game_id = p_game_id AND o.market = p_market AND o.bookmaker = p_bookmaker
       AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
     ORDER BY o.snapshot_at DESC, o.odds_id DESC
     LIMIT 1;
END $f$;

CREATE FUNCTION latest_odds_on_update() RETURNS trigger LANGUAGE plpgsql AS $f$
BEGIN
    PERFORM latest_odds_recompute(OLD.game_id, OLD.market, OLD.bookmaker);
    IF (NEW.game_id, NEW.market, NEW.bookmaker)
       IS DISTINCT FROM (OLD.game_id, OLD.market, OLD.bookmaker) THEN
        PERFORM latest_odds_recompute(NEW.game_id, NEW.market, NEW.bookmaker);
    END IF;
    RETURN NULL;
END $f$;

CREATE TRIGGER trg_latest_odds_update AFTER UPDATE ON odds
    FOR EACH ROW EXECUTE FUNCTION latest_odds_on_update();
"""

LIVE_BOOKS = ["betmgm", "draftkings", "fanduel", "pinnacle", "caesars", "espnbet"]
MARKETS = ["h2h", "spreads", "totals"]
CFBD_KEYS = [("spreads", "cfbd_bovada"), ("totals", "cfbd_bovada"),
             ("h2h", "cfbd_bovada"), ("spreads", "cfbd_draftkings"),
             ("totals", "cfbd_draftkings"), ("h2h", "cfbd_draftkings")]


def _seed(cur):
    for i, (canon, alias, home, away_canon, away_alias,
            n_alias, n_canon, wx) in enumerate(PAIRS):
        cur.execute("INSERT INTO games VALUES (%s,'NCAAF',%s,%s,40,10,'cfbd')",
                    (canon, home, away_canon))
        cur.execute("INSERT INTO games VALUES (%s,'NCAAF',%s,%s,NULL,NULL,'live')",
                    (alias, home, away_alias))
        cur.execute("INSERT INTO game_weather (game_id) VALUES (%s)", (canon,))
        if wx:
            cur.execute("INSERT INTO game_weather (game_id) VALUES (%s)", (alias,))
        for j in range(n_alias):
            # Live books across three markets, a new snapshot every pass,
            # the last two of every five an in-play read (bought history).
            stype = "in_play" if j % 5 >= 3 else "open"
            cur.execute(
                "INSERT INTO odds (game_id, bookmaker, market, snapshot_type,"
                " snapshot_at, source) VALUES (%s,%s,%s,%s,%s,'odds_api_historical')",
                (alias, LIVE_BOOKS[j % 6], MARKETS[(j // 6) % 3], stype,
                 f"2026-09-{1 + j // 18:02d}T12:00:{j % 60:02d}Z"))
        for j in range(n_canon):
            m, b = CFBD_KEYS[j]
            cur.execute(
                "INSERT INTO odds (game_id, bookmaker, market, snapshot_type,"
                " snapshot_at) VALUES (%s,%s,%s,'close','2025-09-01T00:00:00Z')",
                (canon, b, m))
        if n_alias and i in (1, 4, 6, 7):
            cur.execute("INSERT INTO ncaaf_derivative_fetches VALUES (%s,'am','stored')",
                        (alias,))
    # latest_odds as the insert trigger would have left it.
    cur.execute("SELECT DISTINCT game_id, market, bookmaker FROM odds")
    for key in cur.fetchall():
        cur.execute("SELECT latest_odds_recompute(%s,%s,%s)", key)


def _counts(cur, table, game_id):
    cur.execute(f"SELECT count(*) FROM {table} WHERE game_id = %s", (game_id,))
    return cur.fetchone()[0]


def _latest_keys(cur, game_id):
    cur.execute("SELECT DISTINCT market, bookmaker FROM odds WHERE game_id = %s"
                " AND snapshot_type <> 'in_play'", (game_id,))
    return len(cur.fetchall())


def _server(prefix):
    psycopg2 = pytest.importorskip("psycopg2")
    return psycopg2, scratch_cluster(prefix)


@needs_pg
def test_it_consolidates_the_measured_shapes_and_a_second_pass_is_a_noop():
    psycopg2, cluster = _server("fcs-alias-pg-")
    with cluster as dsn:
        conn = psycopg2.connect(dsn)
        conn.set_client_encoding("UTF8")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(STUB)
        _seed(cur)
        before = {p[0]: _latest_keys(cur, p[1]) + _latest_keys(cur, p[0])
                  for p in PAIRS}

        cur.execute(CODE)
        notices = [n.strip() for n in conn.notices]
        assert sum("consolidated" in n for n in notices) == len(PAIRS), notices
        assert not any("leftover" in n or "missing" in n for n in notices), notices

        for canon, alias, _h, _ac, _aa, n_alias, n_canon, _wx in PAIRS:
            assert _counts(cur, "games", alias) == 0
            assert _counts(cur, "games", canon) == 1
            assert _counts(cur, "odds", alias) == 0
            assert _counts(cur, "odds", canon) == n_alias + n_canon
            assert _counts(cur, "latest_odds", alias) == 0
            # Every (market, book) the two ids priced, once, on the canon.
            assert _counts(cur, "latest_odds", canon) == before[canon]
            assert _counts(cur, "game_weather", alias) == 0
            assert _counts(cur, "game_weather", canon) == 1
            assert _counts(cur, "ncaaf_derivative_fetches", alias) == 0
        assert _counts(cur, "odds", PAIRS[8][0]) == 519
        cur.execute("SELECT count(*) FROM ncaaf_derivative_fetches")
        assert cur.fetchone()[0] == 4
        # Finals untouched, and the CFBD row is still the CFBD row.
        cur.execute("SELECT home_score, away_score, away_team, data_source"
                    " FROM games WHERE game_id = %s", (PAIRS[8][0],))
        assert tuple(cur.fetchone()) == (40, 10, "William & Mary", "cfbd")

        del conn.notices[:]
        cur.execute("SELECT count(*), sum(odds_id) FROM odds")
        snap = cur.fetchone()
        cur.execute(CODE)
        assert conn.notices == []
        cur.execute("SELECT count(*), sum(odds_id) FROM odds")
        assert cur.fetchone() == snap
        conn.close()


@needs_pg
def test_a_pick_that_would_collide_stays_and_keeps_its_games_row():
    """Production has no pick on any alias. If one appears, and the canon
    already holds that model's pick, it is not moved, not deleted, and the
    alias games row it hangs off stays. Every other pair still runs."""
    psycopg2, cluster = _server("fcs-alias-pick-pg-")
    with cluster as dsn:
        conn = psycopg2.connect(dsn)
        conn.set_client_encoding("UTF8")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(STUB)
        _seed(cur)
        canon, alias = PAIRS[9][0], PAIRS[9][1]
        cur.execute("INSERT INTO picks (game_id, model_id, result) VALUES"
                    " (%s,'ncaaf_spread','WIN'), (%s,'ncaaf_spread','LOSS')",
                    (canon, alias))
        cur.execute(CODE)
        notices = [n.strip() for n in conn.notices]
        assert sum("consolidated" in n for n in notices) == len(PAIRS) - 1
        assert any("leftover" in n and alias in n for n in notices), notices
        assert _counts(cur, "picks", alias) == 1
        assert _counts(cur, "picks", canon) == 1
        assert _counts(cur, "games", alias) == 1
        # The odds still moved; only the games row is held for the pick.
        assert _counts(cur, "odds", alias) == 0
        assert _counts(cur, "odds", canon) == 486
        cur.execute("SELECT result FROM picks WHERE game_id = %s", (alias,))
        assert cur.fetchone()[0] == "LOSS"
        conn.close()

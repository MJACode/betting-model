"""The postseason reads and the game-day insert, run on a real Postgres.

The stubbed tests answer each read by its shape, so a wrong column or a filter that does nothing
passes them all. These run the same SQL through the worker's connection wrapper, against the tables
as production declares them (tests/test_nba_schedule_refresh_pg.py's two, plus `picks` with the
columns these reads touch; information_schema, 2026-11-02).

Needs a scratch Postgres (tests/_pg.py); skips without one.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

psycopg2 = pytest.importorskip("psycopg2")

import data.ingestors.nba_schedule_refresh as nsr  # noqa: E402
import scripts.nba_pregame_window as pregame  # noqa: E402
import scripts.nba_prop_market_card as rule_card  # noqa: E402
import scripts.nba_total_luck_card as tlcard  # noqa: E402
from data.db import DBConnection  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

NOW = datetime(2027, 4, 21, 2, 0, tzinfo=timezone.utc)       # 10:00pm ET, 2027-04-20


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("nba-postseason-pg-") as d:
        yield d


SCHEMA = """
DROP TABLE IF EXISTS picks; DROP TABLE IF EXISTS games; DROP TABLE IF EXISTS nba_schedule;
DROP TABLE IF EXISTS nba_prop_market_decisions;
CREATE TABLE games (
    game_id TEXT PRIMARY KEY, sport TEXT NOT NULL, season INTEGER NOT NULL, game_date TEXT NOT NULL,
    home_team TEXT NOT NULL, away_team TEXT NOT NULL, home_score NUMERIC, away_score NUMERIC,
    data_source TEXT, created_at TEXT DEFAULT (now())::text, updated_at TEXT DEFAULT (now())::text,
    commence_time TEXT, neutral_site INTEGER);
CREATE TABLE nba_schedule (
    nba_game_id TEXT PRIMARY KEY, game_id TEXT, season INTEGER NOT NULL, game_type TEXT NOT NULL,
    game_date TEXT NOT NULL, commence_time TEXT, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
    home_score INTEGER, away_score INTEGER, status_text TEXT, ot_periods INTEGER, arena_name TEXT,
    arena_city TEXT, arena_state TEXT, is_neutral BOOLEAN, game_label TEXT, game_sublabel TEXT,
    national_tv TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE picks (
    pick_id SERIAL PRIMARY KEY, game_id TEXT REFERENCES games(game_id), model_id TEXT NOT NULL,
    game_date TEXT NOT NULL, game_time TEXT, signal_type TEXT NOT NULL, result TEXT,
    condition_status TEXT, decision_odds NUMERIC, dk_odds NUMERIC, prop_market TEXT);
CREATE TABLE nba_prop_market_decisions (
    game_id TEXT PRIMARY KEY, decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), fetch_at TEXT NOT NULL,
    n_quotes INTEGER NOT NULL, n_bets INTEGER NOT NULL, detail TEXT);
"""


@pytest.fixture
def conn(dsn):
    raw = psycopg2.connect(dsn)
    with raw.cursor() as cur:
        cur.execute(SCHEMA)
    raw.commit()
    c = DBConnection(raw)
    # the season as stored: a last regular-season day, and a played game before it
    _sched(c, "S1", "NBA_2027-04-11_NYK_BOS", "regular", "2027-04-11T23:00:00+00:00")
    yield c
    raw.close()


def _sched(conn, nid, gid, kind, tip, status=None, updated="2027-04-20 10:00:00+00"):
    _, d, away, home = gid.split("_")
    conn.execute("""INSERT INTO nba_schedule (nba_game_id, game_id, season, game_type, game_date,
                        commence_time, home_team, away_team, status_text, updated_at)
                    VALUES (%s, %s, 2027, %s, %s, %s, %s, %s, %s, %s)""",
                 (nid, gid, kind, d, tip, home, away, status, updated))


def _game(conn, gid, tip, score=None, source="live"):
    _, d, away, home = gid.split("_")
    conn.execute("""INSERT INTO games (game_id, sport, season, game_date, home_team, away_team,
                        commence_time, home_score, away_score, data_source)
                    VALUES (%s, 'NBA', 2027, %s, %s, %s, %s, %s, %s, %s)""",
                 (gid, d, home, away, tip, score, score, source))


def _at(hours):
    return (NOW + timedelta(hours=hours)).isoformat()


def _rule_slate(conn):
    return rule_card.rule_slate(conn, NOW, horizon_min=90)


def test_each_kind_of_game_comes_back_with_its_type_and_only_the_rule_reads_it(conn):
    _sched(conn, "P1", "NBA_2027-04-20_MIA_BOS", "playoff", _at(1))
    _game(conn, "NBA_2027-04-20_MIA_BOS", _at(1))
    _game(conn, "NBA_2027-04-20_ATL_CHA", _at(1))                 # the feed's row, unlisted
    got = _rule_slate(conn)
    assert sorted(got) == ["NBA_2027-04-20_ATL_CHA", "NBA_2027-04-20_MIA_BOS"]
    assert got["NBA_2027-04-20_MIA_BOS"]["game_type"] == "playoff"
    assert got["NBA_2027-04-20_MIA_BOS"]["tip_source"] == "schedule"
    assert got["NBA_2027-04-20_ATL_CHA"]["game_type"] is None
    assert got["NBA_2027-04-20_ATL_CHA"]["tip_source"] == "feed"
    assert rule_card.slate(conn, NOW, horizon_min=90) == {}
    # a regular-season night, through the same two reads
    _game(conn, "NBA_2027-04-11_NYK_BOS", "2027-04-11T23:00:00+00:00", score=None)
    night = datetime(2027, 4, 11, 22, 10, tzinfo=timezone.utc)
    got = rule_card.rule_slate(conn, night, horizon_min=90)
    assert list(got) == ["NBA_2027-04-11_NYK_BOS"] and not got["NBA_2027-04-11_NYK_BOS"].get("postseason")
    assert list(rule_card.slate(conn, night, horizon_min=90)) == ["NBA_2027-04-11_NYK_BOS"]


def test_a_row_beside_a_listed_game_with_no_final_is_refused_and_one_with_a_final_is_not(conn):
    # the listed game is two days out with no final: the feed's row is a wrong date
    _sched(conn, "P1", "NBA_2027-04-22_MIA_BOS", "playoff", _at(48))
    _game(conn, "NBA_2027-04-20_MIA_BOS", _at(1))
    # Game 3 was played and scored two days ago: the feed's row is Game 4
    _sched(conn, "P2", "NBA_2027-04-18_NYK_ATL", "playoff", _at(-48))
    _game(conn, "NBA_2027-04-18_NYK_ATL", _at(-48), score=100)
    _game(conn, "NBA_2027-04-20_NYK_ATL", _at(1))
    skipped = []
    got = rule_card.rule_slate(conn, NOW, skipped, horizon_min=90)
    assert sorted(got) == ["NBA_2027-04-20_NYK_ATL"]
    assert skipped == ["NBA_2027-04-20_MIA_BOS (the schedule lists this game as NBA_2027-04-22_MIA_BOS)"]


def test_the_game_day_insert_lands_a_row_the_results_step_and_the_slate_can_read(conn):
    """Through the refresh's own write, then the rule's read."""
    final = nsr.event_rows({"events": [{
        "id": "1", "date": "2027-04-21T01:00Z", "season": {"type": 3, "year": 2027},
        "status": {"type": {"name": "STATUS_SCHEDULED", "description": "Scheduled"}},
        "competitions": [{"date": "2027-04-21T01:00Z", "timeValid": True, "neutralSite": False, "notes": [],
                          "competitors": [{"homeAway": "home", "team": {"abbreviation": "BOS", "displayName": "Boston Celtics"}},
                                          {"homeAway": "away", "team": {"abbreviation": "MIA", "displayName": "Miami Heat"}}]}],
    }]})
    p = nsr.plan(final, nsr.read_stored(conn, ["202704"]), {}, ["202704"], today="2027-04-20")
    nsr.apply(conn, p)
    assert conn.execute("SELECT data_source, season, commence_time FROM games WHERE game_id = %s",
                        ("NBA_2027-04-20_MIA_BOS",)).fetchone() == (nsr.DATA_SOURCE, 2027, "2027-04-21T01:00:00+00:00")
    got = rule_card.rule_slate(conn, datetime(2027, 4, 21, 0, 5, tzinfo=timezone.utc), horizon_min=90)
    assert list(got) == ["NBA_2027-04-20_MIA_BOS"] and got["NBA_2027-04-20_MIA_BOS"]["game_type"] == "playoff"


def test_the_listed_read_finds_a_game_with_no_row_and_skips_what_it_should(conn):
    _sched(conn, "L1", "NBA_2027-04-20_MIA_BOS", "playoff", _at(-2))           # lost
    _sched(conn, "L2", "NBA_2027-04-20_ATL_CHA", "playoff", _at(-2),           # not confirmed today
           updated="2027-04-18 10:00:00+00")
    _sched(conn, "L3", "NBA_2027-04-20_NYK_DET", "playoff", _at(-2), status="Postponed")
    _sched(conn, "L4", "NBA_2027-04-20_nan_nan", "cup_final", _at(-2))         # no teams
    _sched(conn, "L5", "NBA_2027-04-20_DAL_LAL", "playoff", _at(-2))           # has a row
    _game(conn, "NBA_2027-04-20_DAL_LAL", _at(-2))
    _sched(conn, "L6", "NBA_2027-04-20_SAS_OKC", "playoff", _at(-2))           # the feed has it reversed
    _game(conn, "NBA_2027-04-20_OKC_SAS", _at(-2))
    _sched(conn, "L7", "NBA_2027-04-20_MEM_DEN", "regular", _at(-2))           # regular: another read's
    assert pregame._listed_without_a_row(conn, NOW, 24.0) == {"NBA_2027-04-20_MIA_BOS": "playoff"}


def test_the_watch_reads_the_ledger_and_the_bets(conn):
    _sched(conn, "P1", "NBA_2027-04-20_MIA_BOS", "playoff", _at(-2))
    _game(conn, "NBA_2027-04-20_MIA_BOS", _at(-2))
    _sched(conn, "P2", "NBA_2027-04-20_ATL_CHA", "playoff", _at(-2))
    _game(conn, "NBA_2027-04-20_ATL_CHA", _at(-2))
    _sched(conn, "P3", "NBA_2027-04-20_NYK_DET", "playin", _at(-2))
    _game(conn, "NBA_2027-04-20_NYK_DET", _at(-2))
    conn.execute("INSERT INTO nba_prop_market_decisions (game_id, fetch_at, n_quotes, n_bets) VALUES (%s, 'x', 1, 0)",
                 ("NBA_2027-04-20_MIA_BOS",))
    conn.execute("INSERT INTO picks (game_id, model_id, game_date, signal_type) VALUES (%s, 'nba_prop_market', '2027-04-20', 'BET')",
                 ("NBA_2027-04-20_ATL_CHA",))
    got = pregame.undecided_rule_games(conn, NOW)
    assert got == {"lost": {"NBA_2027-04-20_NYK_DET": "playin"}, "refused": {}}


def _bet(conn, gid, model="nba_prop_market", result=None, status=None, signal="BET", tip=None, day="2027-04-20"):
    conn.execute("""INSERT INTO picks (game_id, model_id, game_date, game_time, signal_type, result, condition_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""", (gid, model, day, tip, signal, result, status))


def test_the_stranded_read_names_only_open_bets_of_the_two_models_on_a_game_with_no_final(conn):
    old = _at(-13)
    for gid, score in (("NBA_2027-04-20_MIA_BOS", None), ("NBA_2027-04-20_ATL_CHA", None),
                       ("NBA_2027-04-20_NYK_DET", 100), ("NBA_2027-04-20_DAL_LAL", None),
                       ("NBA_2027-04-20_SAS_OKC", None), ("NBA_2027-04-20_MEM_DEN", None),
                       ("NBA_2027-04-20_PHX_UTA", None), ("NBA_2027-04-20_POR_SAC", None)):
        _game(conn, gid, old, score=score)
    _bet(conn, "NBA_2027-04-20_MIA_BOS", tip=old)                                  # named
    _bet(conn, "NBA_2027-04-20_MIA_BOS", tip=old)                                  # and counted
    _bet(conn, "NBA_2027-04-20_ATL_CHA", model="nba_prop_projection", tip=old)     # named
    _bet(conn, "NBA_2027-04-20_NYK_DET", tip=old)                                  # the game has its final
    _bet(conn, "NBA_2027-04-20_DAL_LAL", tip=old, status="VOID", result="NO_ACTION")
    _bet(conn, "NBA_2027-04-20_SAS_OKC", tip=old, result="WIN")
    _bet(conn, "NBA_2027-04-20_MEM_DEN", tip=old, signal="AVOID")
    _bet(conn, "NBA_2027-04-20_PHX_UTA", tip=old, model="nba_total_luck")          # not a prop model
    _bet(conn, "NBA_2027-04-20_POR_SAC", tip=_at(-3))                              # not 12 hours yet
    assert pregame.stranded_prop_bets(conn, NOW) == {"NBA_2027-04-20_MIA_BOS": 2, "NBA_2027-04-20_ATL_CHA": 1}


def test_an_older_stranded_bet_stays_named_inside_the_look_back_and_leaves_after_it(conn):
    _game(conn, "NBA_2027-04-01_MIA_BOS", "2027-04-01T23:00:00+00:00")
    _bet(conn, "NBA_2027-04-01_MIA_BOS", tip="2027-04-01T23:00:00+00:00", day="2027-04-01")
    assert list(pregame.stranded_prop_bets(conn, NOW)) == ["NBA_2027-04-01_MIA_BOS"]
    assert pregame.stranded_prop_bets(conn, NOW + timedelta(days=40)) == {}


def test_a_feed_row_the_other_way_round_takes_espns_tip_through_the_real_reads(conn):
    _sched(conn, "F1", "NBA_2027-04-20_MIA_BOS", "playoff", _at(1))
    _game(conn, "NBA_2027-04-20_BOS_MIA", _at(1.25))              # the feed's row, 15 minutes late
    got = _rule_slate(conn)
    assert list(got) == ["NBA_2027-04-20_BOS_MIA"]
    assert got["NBA_2027-04-20_BOS_MIA"]["tip"] == NOW + timedelta(hours=1)
    assert got["NBA_2027-04-20_BOS_MIA"]["tip_source"] == "schedule"
    assert got["NBA_2027-04-20_BOS_MIA"]["game_type"] is None


def test_a_misdated_row_beside_a_listed_final_stays_off_the_regular_slate_through_the_real_reads(conn):
    final = "NBA_2027-04-05_MIA_BOS"
    _sched(conn, "S0", "NBA_2026-10-20_NYK_BOS", "regular", "2026-10-20T23:00:00+00:00")    # the season's first day
    _sched(conn, "C1", final, "cup_final", "2027-04-05T23:00:00+00:00")
    _game(conn, "NBA_2027-04-04_MIA_BOS", "2027-04-04T23:00:00+00:00")
    _game(conn, "NBA_2027-04-04_NYK_ATL", "2027-04-04T23:00:00+00:00")          # a real unlisted game
    night = datetime(2027, 4, 4, 22, 10, tzinfo=timezone.utc)
    skipped = []
    assert list(rule_card.slate(conn, night, skipped, horizon_min=90)) == ["NBA_2027-04-04_NYK_ATL"]
    assert skipped == [f"NBA_2027-04-04_MIA_BOS (the schedule lists this game as {final})"]


def test_a_false_early_start_moves_the_window_and_reaches_the_alert_through_the_real_reads(conn):
    gid = "NBA_2027-04-20_MIA_BOS"
    _sched(conn, "P1", gid, "playoff", _at(1))
    _game(conn, gid, _at(6))
    assert _rule_slate(conn) == {}
    later = NOW + timedelta(hours=5)
    got = rule_card.rule_slate(conn, later, horizon_min=90)
    assert got[gid]["tip"] == NOW + timedelta(hours=6) and got[gid]["tip_source"] == "feed"
    assert list(rule_card.disputed_start_games(conn, NOW, 24.0)) == [gid]


def test_the_close_reads_the_right_tip_through_the_real_reads(conn):
    import data.ingestors.nba_prop_close_ingestor as close_ing
    false_early, flipped = "NBA_2027-04-20_MIA_BOS", "NBA_2027-04-20_CHA_ATL"
    _sched(conn, "P1", false_early, "playoff", _at(1))
    _game(conn, false_early, _at(6))
    _sched(conn, "P2", "NBA_2027-04-20_ATL_CHA", "playoff", _at(6))
    _game(conn, flipped, _at(6.25))
    for gid in (false_early, flipped):
        conn.execute("INSERT INTO picks (game_id, model_id, game_date, signal_type, prop_market) "
                     "VALUES (%s, 'nba_prop_market', '2027-04-20', 'BET', 'player_points')", (gid,))
    # 14 minutes before ESPN's false start: neither is owed a close
    assert close_ing.bet_games(conn, NOW + timedelta(minutes=46)) == {}
    # 14 minutes before the real ones
    got = close_ing.bet_games(conn, NOW + timedelta(hours=6) - timedelta(minutes=14))
    assert got[false_early]["tip"] == NOW + timedelta(hours=6)
    assert got[flipped]["tip"] == NOW + timedelta(hours=6)


def test_the_report_in_the_doc_sizes_units_as_stake_for_does_and_counts_only_graded_bets(conn):
    """The doc's query, as written, on the shapes it meets. The figure printed above it is sized by
    stake_for, so its first comparison against the search must be too, and a bet voided because
    the player sat out is no bet."""
    from tests.test_nba_postseason_docs import report_sql
    from tracking.discord_notifier import stake_for

    po, reg = "NBA_2027-04-20_MIA_BOS", "NBA_2027-03-01_NYK_ATL"
    for gid, detail in ((po, "fair=0.5 game_type=playoff tip_source=schedule schedule_start=x feed_start=y"),
                        (reg, "fair=0.5")):
        _game(conn, gid, _at(-3))
        conn.execute("INSERT INTO nba_prop_market_decisions (game_id, fetch_at, n_quotes, n_bets, detail) "
                     "VALUES (%s, 'x', 1, 1, %s)", (gid, detail))
    graded = [("WIN", 106), ("LOSS", 106), ("WIN", -150), ("LOSS", -150), ("WIN", -400), ("LOSS", -400), ("PUSH", -110)]
    for result, price in graded:
        conn.execute("INSERT INTO picks (game_id, model_id, game_date, signal_type, result, decision_odds) "
                     "VALUES (%s, 'nba_prop_market', '2027-04-20', 'BET', %s, %s)", (po, result, price))
    # dk_odds alone is a price too: the row's price is COALESCE(decision_odds, dk_odds)
    conn.execute("INSERT INTO picks (game_id, model_id, game_date, signal_type, result, dk_odds) "
                 "VALUES (%s, 'nba_prop_market', '2027-04-20', 'BET', 'WIN', 120)", (po,))
    # none of these is a graded bet of this population
    conn.execute("INSERT INTO picks (game_id, model_id, game_date, signal_type, decision_odds) "
                 "VALUES (%s, 'nba_prop_market', '2027-04-20', 'BET', 110)", (po,))                    # open
    conn.execute("INSERT INTO picks (game_id, model_id, game_date, signal_type, result, decision_odds) "
                 "VALUES (%s, 'nba_prop_market', '2027-04-20', 'BET', 'NO_ACTION', 110)", (po,))       # sat out
    conn.execute("INSERT INTO picks (game_id, model_id, game_date, signal_type, result, condition_status, decision_odds) "
                 "VALUES (%s, 'nba_prop_market', '2027-04-20', 'BET', 'NO_ACTION', 'VOID', 110)", (po,))
    conn.execute("INSERT INTO picks (game_id, model_id, game_date, signal_type, result, decision_odds) "
                 "VALUES (%s, 'nba_prop_projection', '2027-04-20', 'BET', 'WIN', 110)", (po,))         # the other model
    conn.execute("INSERT INTO picks (game_id, model_id, game_date, signal_type, result, decision_odds) "
                 "VALUES (%s, 'nba_prop_market', '2027-03-01', 'BET', 'WIN', 110)", (reg,))            # regular season
    with conn._conn.cursor() as cur:          # no params: the query's % signs are its own
        cur.execute(report_sql())
        rows = cur.fetchall()
    expected = 0.0
    for result, price in [*graded, ("WIN", 120)]:
        s = stake_for(None, price)
        expected += s.win if result == "WIN" else (-s.risk if result == "LOSS" else 0.0)
    assert stake_for(None, -400).risk == 3 and stake_for(None, 106).win == 1, "the sizing this test compares with"
    assert len(rows) == 1
    game_type, tip_source, bets, still_open, units = rows[0]
    assert (game_type, tip_source, bets, still_open) == ("playoff", "schedule", 8, 1)
    assert float(units) == pytest.approx(round(expected, 2))


def test_the_postseason_read_never_touches_a_regular_season_night(conn):
    """It runs on every window tick. On a night of listed regular-season games there is nothing for it
    to read, so the schedule's rows are not fetched for them."""
    _sched(conn, "R1", "NBA_2027-04-10_MIA_ORL", "regular", _at(1))
    _game(conn, "NBA_2027-04-10_MIA_ORL", _at(1))
    seen = []
    real = conn.execute

    def spy(sql, params=None):
        seen.append(" ".join(sql.split()))
        return real(sql, params)

    conn.execute = spy
    assert tlcard.postseason_games(conn, ["2027-04-10"], lambda tip: True) == {}
    assert not any("LEFT JOIN games g" in s and "FROM nba_schedule s" in s for s in seen)

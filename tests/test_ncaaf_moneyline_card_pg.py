"""The NCAAF moneyline card end to end against a real Postgres.

WHY A REAL DATABASE. The card's reads are SQL on `games` and `odds`, whose
snapshot_at and prices are TEXT: the cast, the one-hour bound, the "a book had
priced it by 14:00 UTC" probe and the NULL line of a moneyline are claims about
the server, not about Python. So is how NCAAF games are stored: a night game is
two rows, the odds feed's Eastern-dated one that carries the prices and CFBD's
UTC-dated one that carries the score, and the card must decide the first and
never see the second. So are the ledger (a decided game writes nothing the
second time) and the bet row itself (every column the card writes must exist
and take its value, scored_line NULL). This runs the real run_card() over a
scratch schema. Runs against LATEST_LINE_TEST_DSN or a throwaway cluster from
tests/_pg.py, and SKIPS only where neither exists (the worker).
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

psycopg2 = pytest.importorskip("psycopg2")

import models.ncaab_margin_dist as md  # noqa: E402
import models.ncaaf_moneyline_market as mm  # noqa: E402
from data.db import DBConnection  # noqa: E402
from scripts import ncaaf_moneyline_card as card  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

UTC = timezone.utc
DAY = "2026-11-14"
OSU = "NCAAF_2026-11-14_michigan_ohio-state"        # the bet
NIGHT = "NCAAF_2026-11-14_usc_oregon"               # a night game's odds row: priced, below the cut
NIGHT_CFBD = "NCAAF_2026-11-15_usc_oregon"          # the same game, CFBD's UTC-dated row: no prices
STALE = "NCAAF_2026-11-14_iowa_wisconsin"           # priced on Friday, nothing in the hour
UNLISTED = "NCAAF_2026-11-14_grinnell_lyon"         # no book ever priced it
LATE = "NCAAF_2026-11-14_army_temple"               # first priced after 14:00 UTC
EARLY = "NCAAF_2026-11-14_navy_notre-dame"          # kicks off at 14:00 UTC
SPREAD_BET = "NCAAF_2026-11-14_texas_baylor"        # the spread model holds a BET on it
SPREAD_VOID = "NCAAF_2026-11-14_utah_byu"           # the spread model's BET on it was voided
TOMORROW = "NCAAF_2026-11-15_akron_ohio"            # Sunday's game
UTC_DATED = "NCAAF_2026-11-15_nevada_hawai-i"       # priced, kicks off Saturday night, dated the 15th


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaaf-moneyline-card-pg-") as d:
        yield d


@pytest.fixture(scope="module")
def p_home():
    """The home side's fair chance at a -3.5 consensus, from the live artifact."""
    art = mm.load_artifact()
    pw, pp, pl = md.probs(np.array([3.5 + art["offset"]]), np.zeros(1), art["table"])
    return float(pw[0] / (pw[0] + pl[0]))


def _american(p):
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def _connect(dsn):
    return DBConnection(psycopg2.connect(dsn), url=dsn)


@pytest.fixture()
def db(dsn, monkeypatch, p_home):
    c = _connect(dsn)
    c.execute("DROP TABLE IF EXISTS ncaaf_moneyline_decisions, picks, odds, games")
    c.execute("""CREATE TABLE games (game_id TEXT PRIMARY KEY, sport TEXT, season INTEGER,
                 game_date TEXT, commence_time TEXT, home_team TEXT, away_team TEXT)""")
    c.execute("""CREATE TABLE odds (odds_id SERIAL PRIMARY KEY, game_id TEXT, market TEXT,
                 bookmaker TEXT, snapshot_type TEXT, snapshot_at TEXT,
                 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), spread_home TEXT,
                 home_price TEXT, away_price TEXT, home_link TEXT, away_link TEXT)""")
    cols = ", ".join(f"{col} TEXT" for col in card._COLS
                     if col not in ("model_probability", "dk_implied_prob", "edge", "scored_line"))
    c.execute(f"""CREATE TABLE picks (pick_id SERIAL PRIMARY KEY, {cols}, condition_status TEXT,
                  model_probability NUMERIC NOT NULL, dk_implied_prob NUMERIC NOT NULL,
                  edge NUMERIC NOT NULL, scored_line NUMERIC,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    games = [
        (OSU, "NCAAF", DAY, "2026-11-14T17:00:00Z", "Ohio State", "Michigan"),
        # 10:30pm Eastern on the 14th: the odds feed dates it the 14th, CFBD's row the 15th
        (NIGHT, "NCAAF", DAY, "2026-11-15T03:30:00Z", "Oregon", "USC"),
        (NIGHT_CFBD, "NCAAF", "2026-11-15", "2026-11-15T03:30:00.000Z", "Oregon", "USC"),
        (STALE, "NCAAF", DAY, "2026-11-14T20:30:00Z", "Wisconsin", "Iowa"),
        (UNLISTED, "NCAAF", DAY, "2026-11-14T18:00:00.000Z", "Lyon", "Grinnell"),
        (LATE, "NCAAF", DAY, "2026-11-14T23:00:00Z", "Temple", "Army"),
        (EARLY, "NCAAF", DAY, "2026-11-14T14:00:00Z", "Notre Dame", "Navy"),
        (SPREAD_BET, "NCAAF", DAY, "2026-11-14T20:30:00Z", "Baylor", "Texas"),
        (SPREAD_VOID, "NCAAF", DAY, "2026-11-14T20:30:00Z", "BYU", "Utah"),
        (TOMORROW, "NCAAF", "2026-11-15", "2026-11-15T18:00:00Z", "Ohio", "Akron"),
        # 11pm Eastern on the 14th, stored under the UTC date: the kickoff decides its day
        (UTC_DATED, "NCAAF", "2026-11-15", "2026-11-15T04:00:00Z", "Hawai'i", "Nevada"),
        # another sport on the same day, with the same quotes as the bet
        ("NCAAB_2026-11-14_kansas_duke", "NCAAB", DAY, "2026-11-15T00:00:00Z", "Duke", "Kansas"),
    ]
    for gid, sport, gd, ct, home, away in games:
        c.execute("INSERT INTO games VALUES (%s, %s, 2026, %s, %s, %s, %s)",
                  (gid, sport, gd, ct, home, away))

    def odds(gid, book, stamp, p1, p2, line=None, market="h2h", stype="open"):
        c.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, "
                  "spread_home, home_price, away_price, home_link, away_link) VALUES "
                  "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                  (gid, market, book, stype, stamp, line, p1, p2, f"{book}/{gid}/h", f"{book}/{gid}/a"))

    best = str(_american(p_home - 0.04))           # BetRivers: edge +0.04 on the home side
    best_away = str(_american(1 - p_home + 0.07))
    dk = str(_american(p_home - 0.01))             # DraftKings: edge +0.01, the reference
    short = str(_american(p_home + 0.02))          # every other home side: a negative edge
    away = str(_american(1 - p_home + 0.03))       # every away side: a negative edge

    def board(gid, bet=True):
        for book in ("draftkings", "fanduel", "betmgm", "betrivers", "pinnacle"):
            odds(gid, book, f"{DAY}T13:16:31Z", "-110", "-110", line="-3.5", market="spreads")
        odds(gid, "draftkings", f"{DAY}T13:16:31Z", dk, away)
        odds(gid, "fanduel", f"{DAY}T13:16:40Z", short, away)
        odds(gid, "betmgm", f"{DAY}T13:17:02Z", short, away)
        odds(gid, "pinnacle", f"{DAY}T13:55:00Z", short, away)               # read, never bet
        if bet:
            odds(gid, "betrivers", f"{DAY}T13:17:10Z", best, best_away)
        else:
            odds(gid, "betrivers", f"{DAY}T13:17:10Z", short, away)

    board(OSU)
    # Three quotes that would each be the game's best side if they were read:
    # the same favourite as every other book (or the favourite check would
    # drop them), at an edge of 0.06 against BetRivers' 0.04.
    better, better_away = str(_american(p_home - 0.06)), str(_american(1 - p_home + 0.09))
    assert float(better) < float(better_away) < 0, "the home side must stay the favourite"
    odds(OSU, "fanatics", f"{DAY}T12:40:00Z", better, better_away)           # 80 minutes old: stale
    odds(OSU, "hardrockbet", f"{DAY}T14:02:00Z", better, better_away)        # after 14:00: not yet
    odds(OSU, "williamhill_us", f"{DAY}T13:56:00Z", better, better_away, stype="in_play")
    board(NIGHT, bet=False)
    odds(STALE, "draftkings", "2026-11-13T18:00:00Z", "-150", "+130")
    odds(LATE, "draftkings", f"{DAY}T14:20:00Z", "-150", "+130")
    board(EARLY)
    board(SPREAD_BET)
    board(SPREAD_VOID)
    board(TOMORROW)
    board(UTC_DATED, bet=False)
    board("NCAAB_2026-11-14_kansas_duke")
    for gid, status in ((SPREAD_BET, None), (SPREAD_VOID, "VOID")):
        c.execute("INSERT INTO picks (game_id, model_id, sport, game_date, pick_side, pick_label, "
                  "signal_type, condition_status, model_probability, dk_implied_prob, edge) VALUES "
                  "(%s, 'ncaaf_spread', 'NCAAF', %s, 'away', 'x +3.5', 'BET', %s, 0.58, 0.52, 0.06)",
                  (gid, DAY, status))
    c.commit()
    monkeypatch.setattr(card, "get_connection", lambda: _connect(dsn))
    # The ledger's lock-down revokes from Supabase's API roles, which a scratch
    # cluster does not have: the DDL itself is what this test needs.
    monkeypatch.setattr(card, "ensure_decisions_table",
                        lambda conn: (conn.execute(card.DECISIONS_DDL), conn.commit()))
    import models.scorer as scorer
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    card._ART.clear()
    c.best_price, c.dk_price = float(best), float(dk)
    yield c
    c.close()


def _ledger(c):
    return {r[0]: r[1:] for r in c.execute(
        "SELECT game_id, status, book, side, price, n_books, n_bets FROM ncaaf_moneyline_decisions"
    ).fetchall()}


def test_the_slate_is_the_days_priced_games_by_their_eastern_kickoff(db):
    got = card.slate(db, datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    # the night game's odds row, not CFBD's; nothing unpriced, late-listed,
    # kicking off by 14:00 UTC, tomorrow's, or another sport's
    assert set(got) == {OSU, NIGHT, STALE, SPREAD_BET, SPREAD_VOID, UTC_DATED}
    # a priced row stored under the UTC date is Saturday's game: its kickoff says so
    assert got[UTC_DATED]["instant"] == datetime(2026, 11, 14, 14, tzinfo=UTC)
    assert got[UTC_DATED]["game_date"] == "2026-11-15"
    assert got[NIGHT]["instant"] == datetime(2026, 11, 14, 14, tzinfo=UTC)
    assert got[NIGHT]["game_date"] == DAY and (got[NIGHT]["home"], got[NIGHT]["away"]) == ("Oregon", "USC")
    # Sunday's slate holds Sunday's game, and Saturday's are still in view for the missed check
    sunday = card.slate(db, datetime(2026, 11, 15, 14, 5, tzinfo=UTC))
    assert TOMORROW in sunday and sunday[TOMORROW]["instant"] == datetime(2026, 11, 15, 14, tzinfo=UTC)
    assert NIGHT_CFBD not in sunday and {OSU, NIGHT} <= set(sunday)


def test_the_14z_run_bets_once_at_the_bet_books_price_and_a_rerun_writes_nothing(db, p_home):
    out = card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    assert (out["bets"], out["published"], out["decided"]) == (2, 2, 6)
    led = _ledger(db)
    assert set(led) == {OSU, NIGHT, STALE, SPREAD_BET, SPREAD_VOID, UTC_DATED}
    assert led[UTC_DATED][0] == "below_cut"
    assert led[OSU] == ("bets", "betrivers", "home", db.best_price, 5, 1)
    assert led[NIGHT][0] == "below_cut" and led[NIGHT][-1] == 0
    assert led[STALE][:2] == ("no_quotes", None)
    # one game never carries two bets that cannot both win; a voided bet holds nothing
    assert led[SPREAD_BET][0] == "other_model_bet" and led[SPREAD_BET][-1] == 0
    assert led[SPREAD_VOID][:2] == ("bets", "betrivers")
    (pick,) = db.execute(
        "SELECT game_id, model_id, pick_side, pick_label, scored_line, line_book, dk_odds, "
        "dk_implied_prob, edge, decision_book, decision_odds, best_book, best_bet_link, signal_type, "
        "model_probability, decision_edge, sport, game_date FROM picks "
        "WHERE signal_type = 'BET' AND model_id = %s AND game_id = %s", (mm.MODEL_ID, OSU)).fetchall()
    assert pick[:6] == (OSU, "ncaaf_moneyline_market", "home", "Ohio State ML", None, None)
    assert pick[6] == str(db.dk_price) and 0 < float(pick[8]) < 0.02
    assert pick[9:14] == ("betrivers", str(db.best_price), "betrivers", f"betrivers/{OSU}/h", "BET")
    assert abs(float(pick[14]) - p_home) < 1e-4
    assert abs(float(pick[15]) - 0.04) < 0.005
    assert pick[16:] == ("NCAAF", DAY)
    # The game priced below the cut is a NONE row with no stake, on the odds
    # row of the night game, and is not a bet in the ledger; the unpriced one
    # and the one the spread model holds write no row.
    assert db.execute(
        "SELECT game_id, signal_type, kelly_fraction, recommended_bet FROM picks "
        "WHERE model_id = %s AND signal_type <> 'BET' ORDER BY game_id", (mm.MODEL_ID,)).fetchall() == \
        [(NIGHT, "NONE", "0.0", "0.0"), (UTC_DATED, "NONE", "0.0", "0.0")]
    assert db.execute("SELECT COUNT(*) FROM picks WHERE model_id = %s AND game_id = ANY(%s)",
                      (mm.MODEL_ID, [STALE, SPREAD_BET, NIGHT_CFBD])).fetchone()[0] == 0
    # the same hour again, and an hour later with a better price up: nothing
    card._ART.clear()
    again = card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 40, tzinfo=UTC))
    assert again["decided"] == 0
    db.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, "
               "home_price, away_price) VALUES (%s, 'h2h', 'fanduel', 'open', "
               "'2026-11-14T14:30:00Z', '+150', '-180')", (OSU,))
    db.commit()
    later = card.run_card(do_publish=True, now=datetime(2026, 11, 14, 15, 5, tzinfo=UTC))
    assert later["decided"] == 0
    assert db.execute("SELECT signal_type, COUNT(*) FROM picks WHERE model_id = %s "
                      "GROUP BY 1 ORDER BY 1", (mm.MODEL_ID,)).fetchall() == [("BET", 2), ("NONE", 2)]


def test_a_game_nobody_decided_at_14z_is_written_missed_and_the_run_fails(db):
    card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    # a game priced before 14:00 UTC that the 14:05 run never saw, still to kick off
    gid = "NCAAF_2026-11-14_yale_brown"
    db.execute("INSERT INTO games VALUES (%s, 'NCAAF', 2026, %s, '2026-11-14T22:00:00Z', "
               "'Brown', 'Yale')", (gid, DAY))
    db.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, "
               "home_price, away_price) VALUES (%s, 'h2h', 'draftkings', 'open', "
               "'2026-11-14T13:30:00Z', '+150', '-180')", (gid,))
    db.commit()
    with pytest.raises(card.CardIncomplete, match="missed"):
        card.run_card(do_publish=True, now=datetime(2026, 11, 14, 15, 5, tzinfo=UTC))
    led = _ledger(db)
    assert led[gid][0] == "missed" and led[gid][-1] == 0
    assert db.execute("SELECT COUNT(*) FROM picks WHERE game_id = %s", (gid,)).fetchone()[0] == 0
    # the game first priced after 14:00 UTC was never the card's: not missed
    assert LATE not in led
    # reported once: the next run is clean
    card.run_card(do_publish=True, now=datetime(2026, 11, 14, 16, 5, tzinfo=UTC))


def test_the_first_run_ever_after_14z_records_the_days_games_without_failing(db):
    out = card.run_card(do_publish=True, now=datetime(2026, 11, 14, 18, 5, tzinfo=UTC))
    assert out["bets"] == 0 and out["decided"] == 6
    assert {v[0] for v in _ledger(db).values()} == {"missed", "other_model_bet"}
    assert db.execute("SELECT COUNT(*) FROM picks WHERE model_id = %s",
                      (mm.MODEL_ID,)).fetchone()[0] == 0


def test_a_spread_bet_written_while_the_run_priced_the_game_still_closes_it(db, monkeypatch):
    """The other model's bets are read again inside the write's lock."""
    real = card.side_model_bets
    calls = []

    def racing(conn, game_ids):
        calls.append(1)
        if len(calls) == 2:                 # the read inside publish()
            conn.execute("INSERT INTO picks (game_id, model_id, sport, game_date, pick_side, "
                         "pick_label, signal_type, model_probability, dk_implied_prob, edge) VALUES "
                         "(%s, 'ncaaf_spread_premium', 'NCAAF', %s, 'away', 'x +3.5', 'BET', "
                         "0.6, 0.52, 0.08)", (OSU, DAY))
        return real(conn, game_ids)
    monkeypatch.setattr(card, "side_model_bets", racing)
    card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    assert _ledger(db)[OSU][0] == "other_model_bet"
    assert db.execute("SELECT COUNT(*) FROM picks WHERE model_id = %s AND game_id = %s",
                      (mm.MODEL_ID, OSU)).fetchone()[0] == 0


def test_a_best_side_at_a_book_config_no_longer_lists_fails_the_run_and_bets_nothing(db, monkeypatch):
    monkeypatch.setattr(card.config, "BEST_LINE_BOOKMAKERS",
                        [b for b in card.config.BEST_LINE_BOOKMAKERS if b != "betrivers"])
    with pytest.raises(card.CardIncomplete, match="book_not_bettable"):
        card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    assert _ledger(db)[OSU][:2] == ("book_not_bettable", "betrivers")
    assert db.execute("SELECT COUNT(*) FROM picks WHERE model_id = %s AND signal_type = 'BET'",
                      (mm.MODEL_ID,)).fetchone()[0] == 0

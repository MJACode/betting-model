"""The EuroLeague pre-game card end to end against a real Postgres.

WHY A REAL DATABASE. The card's reads are SQL on `games`, `euroleague_events`,
`euroleague_period_scores`, `odds` and the period feed's ledger: the
snapshot_at cast, the decision fetch picked out by its ledger row and its rows
by their shared transaction time, the in-play exclusion, and the ledger and
picks written in one transaction under each model's advisory lock are claims
about the server, not about Python. This runs the real run_card() over a
scratch schema, on the committed artifact. Runs against LATEST_LINE_TEST_DSN or
a throwaway cluster from tests/_pg.py, and SKIPS only where neither exists.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

psycopg2 = pytest.importorskip("psycopg2")

import config  # noqa: E402
import data.ingestors.euroleague_period_odds as feed  # noqa: E402
import models.euroleague_pregame as R  # noqa: E402
from data.db import DBConnection  # noqa: E402
from scripts import euroleague_pregame_card as card  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

UTC = timezone.utc
TIP = datetime(2026, 11, 20, 19, 0, tzinfo=UTC)
FETCH = TIP - timedelta(minutes=9, seconds=30)
G1 = "EUROLEAGUE_E2026_120"     # MAD v PAN: decided on its fetch
G2 = "EUROLEAGUE_E2026_121"     # OLY v ZAL: tipped an hour earlier, never decided
HIST = 60                       # earlier games, each first quarter 27% of the points


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("euroleague-pregame-card-pg-") as d:
        yield d


def _connect(dsn):
    return DBConnection(psycopg2.connect(dsn), url=dsn)


@pytest.fixture()
def db(dsn, monkeypatch):
    c = _connect(dsn)
    c.execute("DROP TABLE IF EXISTS euroleague_pregame_decisions, euroleague_period_live_fetches, picks, odds, "
              "games, euroleague_events, euroleague_period_scores")
    c.execute("""CREATE TABLE games (game_id TEXT PRIMARY KEY, sport TEXT, season INTEGER, game_date TEXT,
                 commence_time TEXT, home_team TEXT, away_team TEXT, home_score INTEGER, away_score INTEGER)""")
    c.execute("""CREATE TABLE euroleague_events (game_id TEXT PRIMARY KEY, neutral_site BOOLEAN, venue_name TEXT)""")
    c.execute("""CREATE TABLE euroleague_period_scores (game_id TEXT, period INTEGER, home_points INTEGER,
                 away_points INTEGER, PRIMARY KEY (game_id, period))""")
    c.execute("""CREATE TABLE odds (odds_id SERIAL PRIMARY KEY, game_id TEXT, sport TEXT, market TEXT,
                 bookmaker TEXT, snapshot_type TEXT, snapshot_at TEXT,
                 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), source TEXT,
                 home_price REAL, away_price REAL, draw_price REAL, spread_home REAL, total_line REAL,
                 over_price REAL, under_price REAL, home_link TEXT, away_link TEXT, over_link TEXT,
                 under_link TEXT)""")
    num = ("model_probability", "model_probability_cal", "dk_implied_prob", "edge", "dk_odds", "scored_line",
           "kelly_fraction", "recommended_bet", "bankroll_at_pick", "decision_odds", "decision_implied_prob",
           "decision_edge", "best_odds", "best_implied_prob", "best_edge")
    cols = ", ".join(f"{col} {'NUMERIC' if col in num else 'TEXT'}" for col in card._COLS)
    c.execute(f"""CREATE TABLE picks (pick_id SERIAL PRIMARY KEY, {cols}, condition_status TEXT,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    c.execute(feed.LEDGER_DDL)
    for gid, home, away, tip in ((G1, "MAD", "PAN", TIP), (G2, "OLY", "ZAL", TIP - timedelta(minutes=60))):
        c.execute("INSERT INTO games VALUES (%s, 'EUROLEAGUE', 2027, '2026-11-20', %s, %s, %s, NULL, NULL)",
                  (gid, tip.isoformat(), home, away))
        c.execute("INSERT INTO euroleague_events VALUES (%s, FALSE, 'ARENA')", (gid,))
    for i in range(HIST):
        gid = f"EUROLEAGUE_E2025_{i}"
        tip = TIP - timedelta(days=200 - i)
        c.execute("INSERT INTO games VALUES (%s, 'EUROLEAGUE', 2026, %s, %s, %s, %s, 80, 80)",
                  (gid, tip.date().isoformat(), tip.isoformat(), "MAD" if i % 2 else "PAN", "OLY"))
        c.execute("INSERT INTO euroleague_period_scores VALUES (%s, 1, 22, 21.2)", (gid,))  # 43.2 of 160

    def odds(market, book, stamp, created, source=None, stype="open", **px):
        c.execute("INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, snapshot_at, created_at, "
                  "source, home_price, away_price, spread_home, total_line, over_price, under_price, home_link) "
                  "VALUES (%s, 'EUROLEAGUE', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                  (G1, market, book, stype, stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), created, source,
                   px.get("h"), px.get("a"), px.get("sp"), px.get("tl"), px.get("o"), px.get("u"),
                   f"{book}/{market}/home"))

    old = TIP - timedelta(minutes=43)
    odds("h2h", "draftkings", old, old, h=200, a=-240)                     # the hourly pass: stale
    s = FETCH - timedelta(minutes=2)
    src = feed.SOURCE
    odds("h2h", "draftkings", s, FETCH, src, h=140, a=-165)
    odds("h2h", "fanduel", s, FETCH, src, h=145, a=-170)
    odds("spreads", "draftkings", s, FETCH, src, sp=3.5, h=-110, a=-110)
    odds("spreads", "fanduel", s, FETCH, src, sp=3.5, h=-105, a=-115)
    odds("totals", "pinnacle", s, FETCH, src, tl=160.0, o=-110, u=-110)
    odds("h2h_h1", "fanduel", s, FETCH, src, h=130, a=-150)
    odds("h2h_h1", "betrivers", s, FETCH, src, h=125, a=-145)
    odds("totals_q1", "fanduel", s, FETCH, src, tl=41.5, o=-110, u=-110)
    odds("totals_q1", "betrivers", s, FETCH, src, tl=41.5, o=-112, u=-108)
    odds("alternate_totals", "pinnacle", s, FETCH, src, tl=159.5, o=-125, u=105)
    odds("alternate_totals", "pinnacle", s, FETCH, src, tl=160.5, o=105, u=-125)
    # an in-play row: never pre-game, whatever its stamp
    odds("h2h", "betmgm", s, FETCH, stype="in_play", h=900, a=-2000)
    c.execute("INSERT INTO euroleague_period_live_fetches (requested_at, fetch_at, endpoint, mark, game_id, ok) "
              "VALUES (%s, %s, 'event_odds', 'T-10', %s, TRUE)", (FETCH, FETCH, G1))
    c.commit()
    monkeypatch.setattr(card, "get_connection", lambda: _connect(dsn))
    # The ledger's lock-down revokes from Supabase's API roles, which a scratch
    # cluster does not have: the DDL itself is what this test needs.
    monkeypatch.setattr(card, "ensure_decisions_table",
                        lambda conn: (conn.execute(card.DECISIONS_DDL), conn.commit()))
    import models.scorer as scorer
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    for m in card.SWITCHES.values():
        monkeypatch.delenv(m, raising=False)
    monkeypatch.delenv("RUN_EUROLEAGUE_PREGAME", raising=False)
    card._ART.clear()
    yield c
    c.close()


def _picks(c):
    return {r[0]: r[1:] for r in c.execute(
        "SELECT model_id, signal_type, pick_side, decision_book, decision_odds::float, scored_line::float, "
        "pick_label FROM picks WHERE game_id = %s", (G1,)).fetchall()}


def _ledger(c):
    return {(r[0], r[1]): r[2] for r in c.execute(
        "SELECT game_id, model_id, status FROM euroleague_pregame_decisions").fetchall()}


def test_the_decision_fetch_decides_every_model_once_and_a_rerun_writes_nothing(db):
    now = TIP - timedelta(minutes=9)
    out = card.run_card(do_publish=True, now=now)
    p = _picks(db)
    # the home moneyline at the best fetched price, not the stale hourly one
    assert p[R.HOME_ML][:4] == ("BET", "home", "fanduel", 145.0)
    assert p[R.HOME_DOG_SPREAD][:5] == ("BET", "home", "fanduel", -105.0, 3.5)
    assert p[R.H1_DOG_ML][:4] == ("BET", "home", "fanduel", 130.0)
    assert p[R.H1_DOG_ML][5] == "PAN @ MAD — First Half MAD ML"
    # 0.27 of 160 = 43.2 against 41.5: the over, at the best over price
    assert p[R.Q1_SHARE_TOTAL][:5] == ("BET", "over", "fanduel", -110.0, 41.5)
    led = _ledger(db)
    assert {m for (g, m) in led if g == G1} == set(R.MODELS)
    # the first run ever: the game that tipped before the card existed is
    # recorded missed without failing the run
    assert {led[(G2, m)] for m in R.MODELS} == {"missed"}
    assert out["written"] == 4
    n = db.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
    again = card.run_card(do_publish=True, now=now + timedelta(minutes=1))
    assert again["written"] == 0 and db.execute("SELECT COUNT(*) FROM picks").fetchone()[0] == n


def test_a_game_that_tips_undecided_after_the_first_run_fails_it(db):
    db.execute(card.DECISIONS_DDL)
    db.commit()
    with pytest.raises(card.CardIncomplete):
        card.run_card(do_publish=True, now=TIP - timedelta(minutes=9))
    # G1 was still decided and written before the failure
    assert _picks(db)[R.HOME_ML][0] == "BET"


def test_a_switched_off_model_writes_nothing(db, monkeypatch):
    monkeypatch.setenv("RUN_EUROLEAGUE_HOME_ML", "0")
    card.run_card(do_publish=True, now=TIP - timedelta(minutes=9))
    assert R.HOME_ML not in _picks(db)
    assert (G1, R.HOME_ML) not in _ledger(db)


def test_a_standing_halftime_spread_that_cannot_win_beside_the_moneyline_keeps_the_game(db):
    db.execute("INSERT INTO picks (game_id, model_id, sport, game_date, pick_side, pick_label, signal_type, "
               "scored_line, model_probability, dk_implied_prob, edge) VALUES "
               "(%s, 'euroleague_live_spread_ht', 'EUROLEAGUE', '2026-11-20', 'away', 'PAN -3.5 (live)', 'BET', "
               "3.5, 0.55, 0.52, 0.03)", (G1,))
    db.commit()
    card.run_card(do_publish=True, now=TIP - timedelta(minutes=9))
    p = _picks(db)
    # PAN -3.5 (the home number +3.5, away side) cannot win if MAD wins: the moneyline is a NONE row
    assert p[R.HOME_ML][0] == "NONE"
    # MAD +3.5 and PAN -3.5 cannot both win either
    assert p[R.HOME_DOG_SPREAD][0] == "NONE"
    # the first-half bet can win beside it
    assert p[R.H1_DOG_ML][0] == "BET"
    assert config.PAUSED_NOTE


def test_a_conflicting_bet_that_lands_while_the_run_decides_still_closes_the_game(db, monkeypatch):
    """The halftime spread's BET can be written between the card's decision and
    its write (another process). The write re-reads the standing bets under the
    lock: the moneyline that cannot win beside it is written NONE."""
    real = card.standing_full_game
    calls = []

    def racing(conn, ids):
        calls.append(ids)
        if len(calls) == 1:            # the decision's read: nothing standing yet
            db.execute("INSERT INTO picks (game_id, model_id, sport, game_date, pick_side, pick_label, "
                       "signal_type, scored_line, model_probability, dk_implied_prob, edge) VALUES "
                       "(%s, 'euroleague_live_spread_ht', 'EUROLEAGUE', '2026-11-20', 'away', 'PAN -3.5 (live)', "
                       "'BET', 3.5, 0.55, 0.52, 0.03)", (G1,))
            db.commit()
            return []
        return real(conn, ids)

    monkeypatch.setattr(card, "standing_full_game", racing)
    card.run_card(do_publish=True, now=TIP - timedelta(minutes=9))
    assert len(calls) >= 2
    assert _picks(db)[R.HOME_ML][0] == "NONE"
    detail = db.execute("SELECT detail FROM euroleague_pregame_decisions WHERE game_id = %s AND model_id = %s",
                        (G1, R.HOME_ML)).fetchone()[0]
    assert "already bet" in detail

"""The schedule gate in the generic pre-game scorer (data/schedule_context).

mike, 2026-10-20: "The repo/models should look ahead schedules for all markets
and sports and models."

A pre-game model must not decide while either team still has an earlier game
not played, being played, or played but not yet in the logs its inputs read.
The shapes below are the measured ones: pick 3688041 (Wisconsin vs USC Under
52.5, decided 10-17 10:22Z, 13 hours before Wisconsin played at UCLA), the
WNBA postseason picks written while game N was still on, and a UFC card not
yet in the fight log.

No database: the connection is a stand-in that answers the scorer's reads.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

import config
import models.scorer as scorer

TODAY = date.today()
NOW = datetime.now(timezone.utc)


def _d(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def _t(hours: float) -> str:
    return (NOW + timedelta(hours=hours)).isoformat()


class _BoardConn:
    """Enough of Postgres for run_scorer: the board, the price pre-filters,
    the stored schedule, the logs and the BET lock read."""

    def __init__(self, board, schedule, *, priced=(), ncaaf_log=(), ufc_cards=(),
                 mlb_stats=(), bets=(), fail_schedule=False):
        self.board = board                    # run_scorer's game list (7-tuples)
        self.schedule = schedule              # games rows, 7 columns
        self.priced = set(priced)
        self.ncaaf_log = list(ncaaf_log)
        self.ufc_cards = list(ufc_cards)
        self.mlb_stats = list(mlb_stats)      # (team, newest as_of_date)
        self.bets = list(bets)
        self.fail_schedule = fail_schedule
        self._sql = ""

    def execute(self, sql, params=None):
        self._sql = " ".join(sql.split())
        if self.fail_schedule and "commence_time, home_score, away_score FROM games" in self._sql:
            raise RuntimeError("statement timeout")
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        s = self._sql
        if "commence_time, home_score, away_score FROM games" in s:
            return self.schedule
        if s.startswith("SELECT s.game_id FROM games s"):
            return [(g,) for g in self.priced]
        if "FROM ncaaf_team_game_log" in s:
            return self.ncaaf_log
        if "FROM ufc_fight_log" in s:
            return [(c,) for c in self.ufc_cards]
        if "FROM mlb_team_stats" in s:
            return self.mlb_stats
        if "ORDER BY sport, game_date" in s:
            return self.board
        if "FROM games g" in s and "EXISTS" in s:
            return [(g[0],) for g in self.board]          # every board game priced
        if "FROM picks p" in s and "signal_type = 'BET'" in s:
            return self.bets
        return []

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _run(monkeypatch, conn, sport):
    """run_scorer over `conn`; returns {(game_id, model_id): schedule_hold}."""
    monkeypatch.setattr(scorer, "get_connection", lambda: conn)
    monkeypatch.setattr(scorer, "_get_postponed_games", lambda _d: set())
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: {"home_price": -110})
    import features.ncaaf_feature_engine as nfe
    import features.ufc_feature_engine as ufe
    import features.wnba_feature_engine as wfe
    for mod, name in ((nfe, "build_ncaaf_game_features"), (ufe, "build_ufc_game_features"),
                      (wfe, "build_wnba_game_features")):
        monkeypatch.setattr(mod, name, lambda *a, **k: {"f": 1})
    monkeypatch.setattr(scorer, "build_nhl_game_features", lambda *a, **k: {"f": 1})
    monkeypatch.setattr(scorer, "build_mlb_game_features", lambda *a, **k: {"f": 1})
    seen: dict = {}

    def _score(conn_, game_id, model_id, *a, **k):
        seen[(game_id, model_id)] = k.get("schedule_hold")
        return []
    monkeypatch.setattr(scorer, "score_game", _score)
    scorer.run_scorer(TODAY.isoformat(), dry_run=True)
    models = {m for m, (sp, _, _) in config.MODELS.items() if sp == sport}
    return {k: v for k, v in seen.items() if k[1] in models}


# ── NCAAF: the Wisconsin vs USC shape ────────────────────────────────────────

TARGET = f"NCAAF_{_d(7)}_usc_wisconsin"
UCLA = f"NCAAF_{_d(0)}_wisconsin_ucla"


def _ncaaf(ucla_scored: bool, ucla_logged: bool, ucla_start: float = 13.0):
    board = [(TARGET, "NCAAF", 2026, _d(7), "Wisconsin", "USC", _t(7 * 24))]
    schedule = [
        (TARGET, _d(7), "Wisconsin", "USC", _t(7 * 24), None, None),
        (UCLA, _d(0), "UCLA", "Wisconsin", _t(ucla_start),
         31.0 if ucla_scored else None, 20.0 if ucla_scored else None),
        (f"NCAAF_{_d(-7)}_usc_penn-state", _d(-7), "Penn State", "USC", _t(-7 * 24), 24.0, 17.0),
        (f"NCAAF_{_d(-14)}_michigan-state_wisconsin", _d(-14), "Wisconsin", "Michigan State",
         _t(-14 * 24), 21.0, 14.0),
    ]
    log = [("USC", _d(-7), f"NCAAF_{_d(-7)}_usc_penn-state"),
           ("Wisconsin", _d(-14), f"NCAAF_{_d(-14)}_michigan-state_wisconsin")]
    if ucla_logged:
        log.append(("Wisconsin", _d(0), UCLA))
    return board, schedule, log


def test_an_ncaaf_total_waits_for_a_teams_intermediate_game(monkeypatch):
    board, schedule, log = _ncaaf(ucla_scored=False, ucla_logged=False)
    holds = _run(monkeypatch, _BoardConn(board, schedule, ncaaf_log=log), "NCAAF")
    assert holds, "no NCAAF model was scored"
    assert set(holds.values()) == {
        f"waiting for Wisconsin's {_d(0)} game to be played and logged"}, holds


def test_an_ncaaf_game_in_progress_still_holds(monkeypatch):
    board, schedule, log = _ncaaf(ucla_scored=False, ucla_logged=False, ucla_start=-1.0)
    holds = _run(monkeypatch, _BoardConn(board, schedule, ncaaf_log=log), "NCAAF")
    assert all(v and "Wisconsin's" in v for v in holds.values()), holds


def test_played_but_not_logged_still_holds(monkeypatch):
    board, schedule, log = _ncaaf(ucla_scored=True, ucla_logged=False, ucla_start=-20.0)
    holds = _run(monkeypatch, _BoardConn(board, schedule, ncaaf_log=log), "NCAAF")
    assert all(v and "Wisconsin's" in v for v in holds.values()), holds


def test_once_played_and_logged_the_game_is_decided(monkeypatch):
    board, schedule, log = _ncaaf(ucla_scored=True, ucla_logged=True, ucla_start=-20.0)
    holds = _run(monkeypatch, _BoardConn(board, schedule, ncaaf_log=log), "NCAAF")
    assert holds and set(holds.values()) == {None}, holds


def test_a_schedule_that_cannot_be_read_fails_closed(monkeypatch):
    board, schedule, log = _ncaaf(ucla_scored=True, ucla_logged=True, ucla_start=-20.0)
    conn = _BoardConn(board, schedule, ncaaf_log=log, fail_schedule=True)
    holds = _run(monkeypatch, conn, "NCAAF")
    assert holds and all(v and "schedule check failed" in v for v in holds.values()), holds


# ── WNBA: game N+1 listed while game N is on ────────────────────────────────

def test_wnba_waits_while_the_previous_game_is_being_played(monkeypatch):
    n1 = f"WNBA_{_d(2)}_ATL_GSV"
    n = f"WNBA_{_d(0)}_ATL_GSV"
    board = [(n1, "WNBA", 2026, _d(2), "GSV", "ATL", _t(48))]
    schedule = [(n1, _d(2), "GSV", "ATL", _t(48), None, None),
                (n, _d(0), "GSV", "ATL", _t(-1.5), None, None),           # on now
                (f"WNBA_{_d(-2)}_GSV_ATL", _d(-2), "ATL", "GSV", _t(-50), 80.0, 75.0)]
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={n}), "WNBA")
    assert holds and all(
        v == f"waiting for ATL's {_d(0)} game and GSV's {_d(0)} game to be played and logged"
        for v in holds.values()), holds


def test_a_wnba_row_no_book_ever_priced_is_not_a_game(monkeypatch):
    """WNBA_2026-10-03_NY_ATL: unscored, 0 odds rows, 17h from the real game."""
    target = f"WNBA_{_d(3)}_NY_ATL"
    board = [(target, "WNBA", 2026, _d(3), "ATL", "NY", _t(72))]
    schedule = [(target, _d(3), "ATL", "NY", _t(72), None, None),
                (f"WNBA_{_d(-1)}_NY_ATL", _d(-1), "ATL", "NY", _t(-23), None, None),  # phantom
                (f"WNBA_{_d(0)}_NY_ATL", _d(0), "ATL", "NY", _t(-6), 92.0, 88.0)]
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced=()), "WNBA")
    assert holds and set(holds.values()) == {None}, holds


def test_a_row_no_book_priced_inside_the_scoring_window_is_not_a_game(monkeypatch):
    """The same phantom seen from two days before it: dated INSIDE the
    look-ahead window, so it is on run_scorer's game list too (the price
    pre-filter drops it later, in the loop). Being on that list must not make
    it a game. Production 2026-10-20: WNBA_2026-10-22_GSV_ATL has 0 odds rows
    and sits in the Finals."""
    real = f"WNBA_{_d(3)}_NY_ATL"
    phantom = f"WNBA_{_d(2)}_NY_ATL"
    board = [(phantom, "WNBA", 2026, _d(2), "ATL", "NY", _t(48)),
             (real, "WNBA", 2026, _d(3), "ATL", "NY", _t(72))]
    schedule = [(real, _d(3), "ATL", "NY", _t(72), None, None),
                (phantom, _d(2), "ATL", "NY", _t(48), None, None),      # 0 odds rows
                (f"WNBA_{_d(-1)}_ATL_NY", _d(-1), "NY", "ATL", _t(-22), 80.0, 77.0)]
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={real}), "WNBA")
    real_holds = {k: v for k, v in holds.items() if k[0] == real}
    assert real_holds and set(real_holds.values()) == {None}, real_holds


# ── UFC: a card not in the fight log yet ─────────────────────────────────────

def test_ufc_waits_for_a_fighters_card_to_reach_the_fight_log(monkeypatch):
    target = f"UFC_{_d(5)}_jan-blachowicz_alex-pereira"
    prev = f"UFC_{_d(-2)}_alex-pereira_jiri-prochazka"
    board = [(target, "UFC", 2026, _d(5), "Alex Pereira", "Jan Blachowicz", _t(5 * 24))]
    schedule = [(target, _d(5), "Alex Pereira", "Jan Blachowicz", _t(5 * 24), None, None),
                (prev, _d(-2), "Jiri Prochazka", "Alex Pereira", _t(-50), None, None)]
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={prev}, ufc_cards=[_d(-30)]),
                 "UFC")
    assert holds and all(
        v == f"waiting for Alex Pereira's {_d(-2)} fight to be played and logged"
        for v in holds.values()), holds
    # The card lands: decided.
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={prev},
                                         ufc_cards=[_d(-30), _d(-2)]), "UFC")
    assert holds and set(holds.values()) == {None}, holds


# ── MLB: World Series game N+1 while game N is on, or not yet logged ─────────
#
# MLB is live through the World Series (game 1 2026-10-23) and scores 7 days
# ahead. mlb_f5_moneyline wrote 14 of its 119 BETs since 07-05 before the
# morning run had logged a team's previous game.

G2 = f"MLB_{_d(1)}_TB_MIL"


def _mlb(g1_start: float, g1_scored: bool, logged_through: str | None):
    """Game 2 tomorrow; game 1 started `g1_start` hours from now. The team
    stats' newest as_of_date is `logged_through` (the morning run's mark)."""
    g1 = f"MLB_{_d(0) if g1_start > -10 else _d(-1)}_TB_MIL"
    g1_day = g1.split("_")[1]
    board = [(G2, "MLB", 2026, _d(1), "MIL", "TB", _t(26))]
    schedule = [(G2, _d(1), "MIL", "TB", _t(26), None, None),
                (g1, g1_day, "MIL", "TB", _t(g1_start),
                 4.0 if g1_scored else None, 2.0 if g1_scored else None),
                (f"MLB_{_d(-6)}_TB_CLE", _d(-6), "TB", "CLE", _t(-6 * 24), 7.0, 3.0),
                (f"MLB_{_d(-6)}_MIL_LAD", _d(-6), "LAD", "MIL", _t(-6 * 24), 2.0, 6.0)]
    stats = [(t, logged_through) for t in ("TB", "MIL")] if logged_through else []
    return board, schedule, g1, g1_day, stats


def test_mlb_game_two_waits_while_game_one_is_being_played(monkeypatch):
    board, schedule, g1, g1_day, stats = _mlb(-1.5, False, _d(0))
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={g1, G2}, mlb_stats=stats),
                 "MLB")
    assert holds and set(holds.values()) == {
        f"waiting for TB's {g1_day} game and MIL's {g1_day} game to be played and logged"}, holds


def test_mlb_game_two_waits_for_the_morning_run_to_log_game_one(monkeypatch):
    """Scored overnight, logged by the 6am run: until then the bullpen rows
    the models read do not hold game 1, and no row reads as an off day."""
    board, schedule, g1, g1_day, stats = _mlb(-14.0, True, _d(-1))
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={g1, G2}, mlb_stats=stats),
                 "MLB")
    assert holds and all(v and "TB's" in v and "MIL's" in v for v in holds.values()), holds
    board, schedule, g1, g1_day, stats = _mlb(-14.0, True, _d(0))
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={g1, G2}, mlb_stats=stats),
                 "MLB")
    assert holds and set(holds.values()) == {None}, holds


def test_a_postponed_mlb_game_stops_holding_twelve_hours_after_first_pitch(monkeypatch):
    """MLB_2026-10-16_TB_CLE: 3,328 odds rows, never scored, 22.3h before the
    two teams' next game. One 2-day horizon would have held that game to its
    first pitch."""
    board, schedule, g1, g1_day, stats = _mlb(-13.0, False, _d(0))
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={g1, G2}, mlb_stats=stats),
                 "MLB")
    assert holds and set(holds.values()) == {None}, holds


def test_an_mlb_row_no_book_ever_priced_is_not_a_game(monkeypatch):
    """MLB_2026-10-16_MIL_LAD: an if-necessary game the series never needed,
    0 odds rows."""
    board, schedule, g1, g1_day, stats = _mlb(-1.5, False, _d(0))
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={G2}, mlb_stats=stats),
                 "MLB")
    assert holds and set(holds.values()) == {None}, holds


# ── NHL keeps its own game-day check ─────────────────────────────────────────

def test_nhl_is_not_given_the_generic_gate(monkeypatch):
    gid = f"NHL_{_d(0)}_BOS_TOR"
    board = [(gid, "NHL", 2027, _d(0), "TOR", "BOS", _t(6))]
    schedule = [(gid, _d(0), "TOR", "BOS", _t(6), None, None),
                (f"NHL_{_d(-1)}_BOS_ANA", _d(-1), "ANA", "BOS", _t(-20), None, None)]
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={f"NHL_{_d(-1)}_BOS_ANA"}),
                 "NHL")
    assert holds and set(holds.values()) == {None}, holds


# ── score_game: what a hold does to the rows ─────────────────────────────────

class _Clf:
    def predict_proba(self, X):
        return np.array([[0.42, 0.58]])


def _stock(monkeypatch, *, hold=None, paused=False):
    """wnba_moneyline on the stock path: a 0.58 home side at +120 (edge 0.125)."""
    monkeypatch.setattr(scorer, "load_model",
                        lambda mid: {"model": _Clf(), "feature_cols": []})
    odds = {"home_price": 120.0, "away_price": -140.0, "spread_home": None,
            "total_line": None}
    monkeypatch.setattr(scorer, "_get_scoring_odds", lambda *a, **k: odds)
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: odds)
    monkeypatch.setattr(scorer, "_get_public_betting", lambda *a, **k: {})
    for name in ("_stamp_best_game_prices", "_apply_game_injury_gate",
                 "_apply_game_market_gate"):
        monkeypatch.setattr(scorer, name, lambda *a, **k: None)
    monkeypatch.setattr(scorer, "_is_paused", lambda mid: paused)
    return scorer.score_game(
        None, "WNBA_2026-10-21_GSV_ATL", "wnba_moneyline",
        {"home_team": "ATL", "away_team": "GSV", "game_date": "2026-10-21"},
        bankroll=1000.0, dry_run=True, commence_time="2026-10-22T00:10:00Z",
        **({"schedule_hold": hold} if hold else {}))


def test_without_a_hold_the_number_is_a_bet(monkeypatch):
    assert "BET" in {p["signal_type"] for p in _stock(monkeypatch)}


def test_a_hold_writes_every_row_none_with_the_reason(monkeypatch):
    why = "waiting for ATL's 2026-10-19 game to be played and logged"
    picks = _stock(monkeypatch, hold=why)
    assert picks and {p["signal_type"] for p in picks} == {"NONE"}
    assert {p["downgrade_reason"] for p in picks} == {why}
    assert all(p["recommended_bet"] == 0.0 for p in picks)


def test_a_paused_models_held_row_keeps_the_pause_note(monkeypatch):
    picks = _stock(monkeypatch, hold="waiting for ATL's 2026-10-19 game to be played and logged",
                   paused=True)
    assert picks and {p["signal_type"] for p in picks} == {"NONE"}
    assert {p["downgrade_reason"] for p in picks} == {config.PAUSED_NOTE}



# ── NCAAF: the night-game stub takes CFBD's schedule row ─────────────────────

def _ncaaf_db():
    import sqlite3
    from data.db_setup import SCHEMA_SQL
    from data.ingestors.cfbd_ingestor import ncaaf_season_for_date
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    c.executescript("""
        CREATE TABLE IF NOT EXISTS game_weather (game_id TEXT, temp_f REAL,
            wind_mph REAL, precip_mm REAL);
        CREATE TABLE IF NOT EXISTS ncaaf_venues (venue_id INTEGER, latitude REAL,
            longitude REAL, elevation_ft REAL, capacity INTEGER, grass INTEGER,
            dome INTEGER);""")
    season = ncaaf_season_for_date(TODAY.isoformat())
    for team, sp in (("Army", 2.0), ("Navy", 1.0)):
        c.execute("INSERT INTO ncaaf_team_stats (team, season, as_of_date, games_played, "
                  "sp_overall, conference, classification) VALUES (?, ?, ?, 6, ?, "
                  "'American Athletic', 'fbs')", (team, season, _d(-30), sp))
    return c, season


def _game(c, gid, gdate, home, away, start, *, week=None, neutral=None, venue=None,
          hs=None, as_=None, season=2026):
    c.execute("INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, "
              "commence_time, week, neutral_site, conference_game, venue_id, home_score, "
              "away_score) VALUES (?, 'NCAAF', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
              (gid, season, gdate, home, away, start, week, neutral, venue, hs, as_))


def test_army_navy_on_its_stub_reads_week_15_at_a_neutral_site():
    """The odds feed's NCAAF_2026-12-12_army_navy has no week; CFBD's
    NCAAF_2026-12-12_navy_army (swapped) says week 15, neutral site."""
    from features.ncaaf_feature_engine import build_ncaaf_game_features
    c, season = _ncaaf_db()
    stub = f"NCAAF_{_d(40)}_army_navy"
    _game(c, stub, _d(40), "Navy", "Army", _t(40 * 24 + 4), season=season)
    _game(c, f"NCAAF_{_d(40)}_navy_army", _d(40), "Army", "Navy", _t(40 * 24 + 4),
          week=15, neutral=1, venue=3839, season=season)
    f = build_ncaaf_game_features(c, stub, _d(40), "Navy", "Army", season)
    assert f is not None
    assert f["week"] == 15 and f["is_neutral_site"] == 1


def test_a_night_game_stub_reads_the_utc_dated_cfbd_row():
    from features.ncaaf_feature_engine import build_ncaaf_game_features
    c, season = _ncaaf_db()
    stub = f"NCAAF_{_d(17)}_army_navy"
    _game(c, stub, _d(17), "Navy", "Army", _t(17 * 24 + 23), season=season)
    _game(c, f"NCAAF_{_d(18)}_army_navy", _d(18), "Navy", "Army", _t(17 * 24 + 23),
          week=10, neutral=0, season=season)
    f = build_ncaaf_game_features(c, stub, _d(17), "Navy", "Army", season)
    assert f is not None and f["week"] == 10


def test_a_stub_with_no_cfbd_row_is_not_scored_on_blanks():
    from features.ncaaf_feature_engine import build_ncaaf_game_features
    c, season = _ncaaf_db()
    stub = f"NCAAF_{_d(17)}_army_navy"
    _game(c, stub, _d(17), "Navy", "Army", _t(17 * 24 + 23), season=season)
    assert build_ncaaf_game_features(c, stub, _d(17), "Navy", "Army", season) is None


# ── rest as of kickoff, from the stored schedule ─────────────────────────────

def test_ncaaf_rest_counts_the_game_still_to_be_played():
    """Pick 3094504's shape: decided nine days out with a game in between.
    Rest read off played games saw that game as a bye (14 days); at kickoff
    it is 7. Navy (home) has a real bye; Army (away) plays in two days."""
    from features.ncaaf_feature_engine import build_ncaaf_game_features
    c, season = _ncaaf_db()
    target = f"NCAAF_{_d(9)}_army_navy"
    _game(c, target, _d(9), "Navy", "Army", _t(9 * 24), week=8, neutral=0, season=season)
    _game(c, f"NCAAF_{_d(2)}_tulane_army", _d(2), "Army", "Tulane", _t(2 * 24),
          week=7, neutral=0, season=season)                                # not played yet
    for team in ("Army", "Navy"):
        _game(c, f"NCAAF_{_d(-5)}_rice_{team.lower()}", _d(-5), team, "Rice",
              _t(-5 * 24), week=6, neutral=0, hs=30, as_=20, season=season)
    f = build_ncaaf_game_features(c, target, _d(9), "Navy", "Army", season)
    assert f is not None
    assert f["d_rest_days"] == 14 - 7                     # home rest minus away rest


def _wnba_db():
    import sqlite3
    from data.db_setup import SCHEMA_SQL
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    return c


def _wnba_game(c, gid, gdate, home, away, start, hs=None, as_=None, priced=True):
    c.execute("INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, "
              "commence_time, home_score, away_score) VALUES (?, 'WNBA', 2026, ?, ?, ?, ?, ?, ?)",
              (gid, gdate, home, away, start, hs, as_))
    if priced:
        c.execute("INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, "
                  "snapshot_at) VALUES (?, 'WNBA', 'h2h', 'draftkings', 'open', ?)",
                  (gid, start))


def test_wnba_rest_counts_the_game_still_being_played():
    """Pick 480442: IND truly on a back-to-back (at LA, still being quoted when
    the pick was written) and read as 12 days' rest, so away_b2b was 0."""
    from features.wnba_feature_engine import build_wnba_game_features
    c = _wnba_db()
    target = f"WNBA_{_d(1)}_IND_PHX"
    _wnba_game(c, target, _d(1), "PHX", "IND", _t(26))
    _wnba_game(c, f"WNBA_{_d(0)}_IND_LA", _d(0), "LA", "IND", _t(-1.5))   # on now
    _wnba_game(c, f"WNBA_{_d(-12)}_IND_NY", _d(-12), "NY", "IND", _t(-12 * 24), 80, 70)
    _wnba_game(c, f"WNBA_{_d(-2)}_PHX_SEA", _d(-2), "SEA", "PHX", _t(-2 * 24), 80, 70)
    f = build_wnba_game_features(c, target, _d(1), "PHX", "IND", 2026)
    assert f["away_b2b"] == 1
    assert f["d_rest_days"] == 3 - 1


def test_wnba_rest_ignores_a_row_no_book_ever_priced():
    """WNBA_2026-10-03_NY_ATL beside the real 10-04 game: unscored, 0 odds
    rows. Counted, it would be a back-to-back that never happened."""
    from features.wnba_feature_engine import build_wnba_game_features
    c = _wnba_db()
    target = f"WNBA_{_d(3)}_NY_ATL"
    _wnba_game(c, target, _d(3), "ATL", "NY", _t(72))
    _wnba_game(c, f"WNBA_{_d(2)}_NY_ATL", _d(2), "ATL", "NY", _t(47), priced=False)
    _wnba_game(c, f"WNBA_{_d(0)}_NY_ATL", _d(0), "ATL", "NY", _t(-6), 92, 88)
    f = build_wnba_game_features(c, target, _d(3), "ATL", "NY", 2026)
    assert f["home_b2b"] == 0 and f["away_b2b"] == 0 and f["d_rest_days"] == 0


# ── NFL: the opener and wind cards, gated where their BETs are written ───────

class _PublishConn:
    """Records the publisher's statements; answers its schedule and lock reads."""

    def __init__(self, schedule):
        self.schedule = schedule
        self.sql: list[tuple] = []

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.sql.append((flat, params))
        rows = []
        if "commence_time, home_score, away_score FROM games" in flat:
            rows = self.schedule

        class R:
            rowcount = 0

            def fetchall(self_r):
                return rows

            def fetchone(self_r):
                return rows[0] if rows else None
        return R()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def bets_written(self):
        return [p for s, p in self.sql
                if s.startswith("INSERT INTO picks") and p.get("signal_type") == "BET"]


CAR_GB = "NFL_2026_08_CAR_GB"


def _nfl_schedule(week7_scored: bool):
    s = 24.0 if week7_scored else None
    return [
        (CAR_GB, _d(9), "GB", "CAR", _t(9 * 24), None, None),
        ("NFL_2026_07_TB_CAR", _d(5), "CAR", "TB", _t(-4) if week7_scored else _t(5 * 24),
         s, 17.0 if s else None),
        ("NFL_2026_07_GB_DET", _d(5), "DET", "GB", _t(-4) if week7_scored else _t(5 * 24),
         s, 20.0 if s else None),
        ("NFL_2026_06_CAR_NO", _d(-2), "NO", "CAR", _t(-50), 10.0, 13.0),
    ]


def _publish_opener(monkeypatch, tmp_path, conn):
    import data.db as db
    import scripts.nfl_wind_publisher as pub
    (tmp_path / f"opener_card_{TODAY.isoformat()}.csv").write_text("x", encoding="utf-8")
    monkeypatch.setattr(pub, "CARDS_DIR", tmp_path)
    monkeypatch.setattr(db, "get_connection", lambda: conn)
    monkeypatch.setattr(pub, "_lock_model", lambda *a, **k: None)
    monkeypatch.setattr(pub, "_flush_snapshots_safe", lambda *a, **k: None)
    monkeypatch.setattr(pub, "read_card", lambda path: [])
    game = {"game_id": CAR_GB, "sport": "NFL", "season": 2026, "game_date": _d(9),
            "home_team": "GB", "away_team": "CAR", "commence_time": _t(9 * 24)}
    pick = {"game_id": CAR_GB, "model_id": pub.NFL_OPENER_MODEL_ID, "signal_type": "BET",
            "pick_label": "CAR @ GB — CAR +3.5 (FD)"}
    monkeypatch.setattr(pub, "build_opener_rows", lambda rows, bankroll: ([game], [pick]))
    return pub.publish_opener(TODAY.isoformat())


def test_the_nfl_opener_does_not_lock_before_both_teams_week_seven_games(monkeypatch, tmp_path):
    """CAR @ GB, evaluated 2026-10-20 while both teams still had to play 10-25."""
    conn = _PublishConn(_nfl_schedule(week7_scored=False))
    assert _publish_opener(monkeypatch, tmp_path, conn) == 0
    assert conn.bets_written() == []


def test_the_nfl_opener_locks_once_those_games_are_scored(monkeypatch, tmp_path):
    conn = _PublishConn(_nfl_schedule(week7_scored=True))
    assert _publish_opener(monkeypatch, tmp_path, conn) == 1
    assert len(conn.bets_written()) == 1


def test_a_held_nfl_game_still_shows_its_number_as_none_with_the_reason():
    import scripts.nfl_wind_publisher as pub
    games = {CAR_GB: {"home_team": "GB", "away_team": "CAR", "game_date": _d(9),
                      "commence_time": _t(9 * 24)}}
    fired = {"game_id": CAR_GB, "model_id": "nfl_opener_spread", "qualifies": "1",
             "current_line": "-3.5", "current_price": "-110", "current_book": "fanduel",
             "reason": "deviation 1.5 vs Pinnacle"}
    latest = {(CAR_GB, "nfl_opener_spread"): fired}
    assert pub.build_scored_rows(latest, games, 1000.0) == []        # the BET lands instead
    why = f"waiting for CAR's {_d(5)} game and GB's {_d(5)} game to be played and logged"
    (row,) = pub.build_scored_rows(latest, games, 1000.0, {CAR_GB: why})
    assert row["signal_type"] == "NONE" and row["downgrade_reason"] == why
    assert row["scored_line"] == -3.5                                # the HOME number

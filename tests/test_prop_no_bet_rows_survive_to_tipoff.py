"""A player-prop model's no-bet rows must still be on the board at tip-off.

The evaluation rule (CLAUDE.md section 7) grades EVERY scored pick -- BET,
AVOID and the dead-zone NONE rows alike. For the player-prop models that
universe was being emptied before the games started, by two deletes that both
live in the GAME scorer (models.scorer.run_scorer), which never re-writes a
prop row:

1. The 30-second pre-game line poller re-runs run_scorer for any game whose
   line moved, and run_scorer's per-game clear removed every unsettled no-bet
   row on that game -- the player props included. The poller never re-runs
   the prop scorers, so whatever it cleared after the last refresh pass was
   gone for good. Measured on MLB_2026-10-11_LAD_MIL (first pitch 00:20Z):
   picks_log shows 103 prop rows (95 NONE, 8 AVOID) deleted at
   00:17:18.985Z in the same transaction that re-inserted the 8 game-level
   rows; the pollers service logged "Daily Scorer -- 2026-10-11" at
   00:17:18.831Z and "1 game(s) re-scored, 8 pick(s)" at 00:17:26.784Z. The
   game finished with one prop row (its BET) and no NONE or AVOID row.

2. A refresh pass reads the clock once, before its game loop, and a pass
   takes minutes. A game that started while the pass was running was still
   cleared, and the prop scorer that runs next skips a started game, so its
   rows were never re-written. Measured on WNBA_2026-10-09_ATL_NY (start
   23:34:00Z): 91 prop rows deleted at 23:36:48.096Z; the pollers service ran
   no scorer at that instant (its runs began 23:36:13.5Z and 23:36:41.9Z).

WHAT MUST NOT CHANGE. The prop lock (_locked_prop_keys) holds ANY row a
player has, NONE included, and it is the refresh pass's own clear that
releases a NONE player so the next prop pass can make him a BET. These tests
pin that the refresh pass still clears an unstarted game's prop no-bet rows
(and that the real lock then lets the player be scored again), that a BET is
never touched, and that the game-level models are still cleared and
re-scored exactly as before.

Behavioural, not source scans: run_scorer runs against a fake connection
whose picks and games tables are an in-memory sqlite database, so the DELETE
statements that actually execute are the ones in models/scorer.py.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime as _real_datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models.scorer as scorer  # noqa: E402

TARGET = "2026-10-11"
T0 = _real_datetime(2026, 10, 11, 22, 0, 0, tzinfo=timezone.utc)

# sport, a game-level model it scores, a player-prop model, the feature
# builder run_scorer calls for that sport (module, attribute).
SPORTS = [
    ("MLB", "mlb_moneyline", "mlb_prop_batter_hits",
     ("models.scorer", "build_mlb_game_features")),
    ("WNBA", "wnba_moneyline", "wnba_prop_player_points",
     ("features.wnba_feature_engine", "build_wnba_game_features")),
    ("NBA", "nba_moneyline", "nba_prop_player_points",
     ("features.nba_feature_engine", "build_nba_game_features")),
]


def _iso(dt) -> str:
    return dt.isoformat()


class _Clock:
    now = T0


def _fake_datetime_class():
    class FakeDatetime(_real_datetime):
        @classmethod
        def now(cls, tz=None):
            base = _Clock.now
            if tz is None:
                return cls.fromtimestamp(base.timestamp())
            return cls.fromtimestamp(base.timestamp(), tz=tz)
    return FakeDatetime


class _Board:
    """Postgres stand-in. The picks/games statements run on sqlite exactly as
    run_scorer wrote them (placeholders made sqlite's); everything else is a
    no-op that returns no rows."""

    _SQLITE_PREFIXES = (
        "DELETE FROM PICKS",
        "SELECT P.GAME_ID, P.MODEL_ID FROM PICKS",
        "SELECT GAME_ID, MODEL_ID, PLAYER_ID FROM PICKS",
    )

    def __init__(self, games):
        self.games = games
        self.db = sqlite3.connect(":memory:")
        self.db.execute("""
            CREATE TABLE picks (
                pick_id INTEGER PRIMARY KEY, game_id TEXT, model_id TEXT,
                game_date TEXT, player_id TEXT, pick_side TEXT,
                signal_type TEXT, result TEXT, is_live INTEGER,
                dk_odds REAL, decision_odds REAL, created_at TEXT)""")
        self.db.execute("""
            CREATE TABLE games (game_id TEXT, sport TEXT, game_date TEXT,
                                commence_time TEXT, home_score INTEGER)""")
        for g in games:
            self.db.execute("INSERT INTO games VALUES (?,?,?,?,NULL)",
                            (g[0], g[1], g[3], g[6]))
        self.rows: list = []

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if text.upper().startswith(self._SQLITE_PREFIXES):
            q = text.replace("%%", "%").replace("%s", "?")
            self.rows = self.db.execute(q, tuple(params or ())).fetchall()
        elif "home_team" in text and "FROM games" in text:
            self.rows = list(self.games)
        else:
            self.rows = []
        return self

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    # ── test helpers ──
    def seed(self, game_id, game_model, prop_model):
        """The board a refresh pass leaves behind: the game-level model's
        no-bet pair, and one player each at NONE, AVOID and BET."""
        ins = ("INSERT INTO picks (game_id, model_id, game_date, player_id, "
               "pick_side, signal_type, dk_odds, created_at) "
               "VALUES (?,?,?,?,?,?,?, 'earlier pass')")
        self.db.execute(ins, (game_id, game_model, TARGET, None, "home", "NONE", -110))
        self.db.execute(ins, (game_id, game_model, TARGET, None, "away", "AVOID", -110))
        self.db.execute(ins, (game_id, prop_model, TARGET, "p_none", "over", "NONE", -110))
        self.db.execute(ins, (game_id, prop_model, TARGET, "p_avoid", "under", "AVOID", -110))
        self.db.execute(ins, (game_id, prop_model, TARGET, "p_bet", "over", "BET", -110))

    def held(self, game_id, model_id) -> set:
        """{(player_id, signal_type, created_at)} for one game and model."""
        return set(self.db.execute(
            "SELECT player_id, signal_type, created_at FROM picks "
            "WHERE game_id = ? AND model_id = ?", (game_id, model_id)).fetchall())


PROPS_UNTOUCHED = {("p_none", "NONE", "earlier pass"),
                   ("p_avoid", "AVOID", "earlier pass"),
                   ("p_bet", "BET", "earlier pass")}
PROP_BET_ONLY = {("p_bet", "BET", "earlier pass")}
GAME_ROWS_UNTOUCHED = {(None, "NONE", "earlier pass"),
                       (None, "AVOID", "earlier pass")}
GAME_ROWS_RESCORED = {(None, "NONE", "this pass")}


def _game(game_id, sport, commence):
    return (game_id, sport, int(TARGET[:4]), TARGET, "HOM", "AWY", _iso(commence))


def _wire(monkeypatch, board, feature_module, feature_attr, *,
          no_features=(), clock_after=None):
    """Point run_scorer at `board`. `no_features` games get no feature row (so
    the loop does not re-score them and only the sweep can reach them);
    `clock_after` = {game_id: moment} moves the clock while that game's
    features are built -- a game starting while the pass is running."""
    import importlib
    _Clock.now = T0
    monkeypatch.setattr(scorer, "datetime", _fake_datetime_class())
    monkeypatch.setattr(scorer, "get_connection", lambda: board)
    monkeypatch.setattr(scorer, "_get_postponed_games", lambda _d: set())
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: None)
    monkeypatch.setattr(scorer, "LOCK_GAME_PICKS_AT_FIRST_RUN", True)
    monkeypatch.setattr(scorer, "LOCK_PROP_PICKS_AT_FIRST_SIGNAL", True)

    def features(conn, game_id, *a, **k):
        if clock_after and game_id in clock_after:
            _Clock.now = clock_after[game_id]
        return None if game_id in no_features else {"x": 1.0}

    monkeypatch.setattr(importlib.import_module(feature_module), feature_attr,
                        features)

    def score_game(conn, game_id, model_id, features, bankroll,
                   dry_run=False, commence_time=None):
        conn.db.execute(
            "INSERT INTO picks (game_id, model_id, game_date, pick_side, "
            "signal_type, created_at) VALUES (?,?,?,?,?, 'this pass')",
            (game_id, model_id, TARGET, "home", "NONE"))
        return [{"signal_type": "NONE", "confidence_tier": "LOW", "edge": 0.0,
                 "dk_odds": None, "pick_label": f"{game_id}/{model_id}",
                 "model_probability": 0.5, "recommended_bet": 0.0}]

    monkeypatch.setattr(scorer, "score_game", score_game)


@pytest.mark.parametrize("sport,game_model,prop_model,builder", SPORTS,
                         ids=[s[0] for s in SPORTS])
def test_the_poller_keeps_prop_no_bet_rows_the_refresh_pass_still_clears(
        monkeypatch, sport, game_model, prop_model, builder):
    later = T0 + timedelta(hours=3)
    moved, unscored = f"{sport}_{TARGET}_AAA_BBB", f"{sport}_{TARGET}_CCC_DDD"
    games = [_game(moved, sport, later), _game(unscored, sport, later)]

    # ── the poller's call: one game that moved, one it cannot re-score ──
    poller = _Board(games)
    for g in (moved, unscored):
        poller.seed(g, game_model, prop_model)
    _wire(monkeypatch, poller, *builder, no_features={unscored})
    scorer.run_scorer(target_date=TARGET, only_games={moved, unscored},
                      game_models_only=True)

    assert poller.held(moved, prop_model) == PROPS_UNTOUCHED, (
        "the poller cleared player-prop rows it never re-writes")
    assert poller.held(unscored, prop_model) == PROPS_UNTOUCHED, (
        "the poller's end-of-run clear removed player-prop rows")
    # The game-level model is cleared and re-scored exactly as before...
    assert poller.held(moved, game_model) == GAME_ROWS_RESCORED
    # ...and a game it could not re-score still loses its stale game-level rows.
    assert poller.held(unscored, game_model) == set()

    # ── the refresh pass on the same board: unchanged ──
    worker = _Board(games)
    for g in (moved, unscored):
        worker.seed(g, game_model, prop_model)
    _wire(monkeypatch, worker, *builder, no_features={unscored})
    scorer.run_scorer(target_date=TARGET)

    for g in (moved, unscored):
        assert worker.held(g, prop_model) == PROP_BET_ONLY, (
            "the refresh pass must still clear an unstarted game's prop "
            "NONE/AVOID rows -- that is what releases the prop lock")
    assert worker.held(moved, game_model) == GAME_ROWS_RESCORED
    assert worker.held(unscored, game_model) == set()
    # The real lock read, on what the pass left: the NONE and AVOID players
    # are free to be scored again (and can become BETs); the BET stays locked.
    locked = scorer._locked_prop_keys(worker, TARGET, [prop_model])
    assert locked == {(moved, prop_model, "p_bet"),
                      (unscored, prop_model, "p_bet")}


@pytest.mark.parametrize("sport,game_model,prop_model,builder", SPORTS,
                         ids=[s[0] for s in SPORTS])
def test_a_game_that_starts_during_the_pass_keeps_its_rows(
        monkeypatch, sport, game_model, prop_model, builder):
    """The refresh pass's clock is read before its loop. A game that starts
    while the pass is running must not be cleared on that stale reading."""
    started_in_loop = f"{sport}_{TARGET}_AAA_BBB"   # starts at T0+5m, reached at T0+10m
    started_by_sweep = f"{sport}_{TARGET}_CCC_DDD"  # starts at T0+7m, not re-scored
    tonight = f"{sport}_{TARGET}_EEE_FFF"           # starts at T0+3h
    games = [_game(started_in_loop, sport, T0 + timedelta(minutes=5)),
             _game(started_by_sweep, sport, T0 + timedelta(minutes=7)),
             _game(tonight, sport, T0 + timedelta(hours=3))]
    board = _Board(games)
    for g in (started_in_loop, started_by_sweep, tonight):
        board.seed(g, game_model, prop_model)
    _wire(monkeypatch, board, *builder, no_features={started_by_sweep},
          clock_after={started_in_loop: T0 + timedelta(minutes=10)})

    scorer.run_scorer(target_date=TARGET)

    assert board.held(started_in_loop, prop_model) == PROPS_UNTOUCHED, (
        "a game that started mid-pass lost its prop rows; the prop scorer "
        "skips a started game, so nothing re-writes them")
    # Its game-level model is still cleared and re-scored, exactly as before:
    # leaving the old row would make the re-insert a silent no-op.
    assert board.held(started_in_loop, game_model) == GAME_ROWS_RESCORED

    assert board.held(started_by_sweep, prop_model) == PROPS_UNTOUCHED, (
        "the end-of-pass clear used the stale clock on a started game")
    assert board.held(started_by_sweep, game_model) == GAME_ROWS_UNTOUCHED

    # An unstarted game is cleared exactly as before; the BET is never touched.
    assert board.held(tonight, prop_model) == PROP_BET_ONLY
    assert board.held(tonight, game_model) == GAME_ROWS_RESCORED


class _PollConn:
    def execute(self, sql, params=None):
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return (0,)

    def commit(self):
        pass

    def rollback(self):
        pass


def test_the_poller_tells_the_scorer_to_leave_prop_rows_alone(monkeypatch):
    import config
    import data.ingestors.odds_ingestor as oi
    from data.ingestors.pregame_line_poller import PRICE_COLS, poll_once

    game = f"MLB_{TARGET}_AAA_BBB"
    quote = {"game_id": game, "market": "h2h",
             "bookmaker": config.ODDS_API_BOOKMAKER, "snapshot_type": "open",
             **{c: None for c in PRICE_COLS}}
    quote["home_price"] = -120
    monkeypatch.setattr(oi, "fetch_pregame_rows", lambda sports: [dict(quote)],
                        raising=False)
    monkeypatch.setattr(oi, "_insert_odds", lambda conn, rows: None, raising=False)
    calls: list[dict] = []

    def fake_run_scorer(**kwargs):
        calls.append(kwargs)
        return {"total_picks": 0, "bets": 0}

    monkeypatch.setattr(scorer, "run_scorer", fake_run_scorer)
    poll_once(_PollConn(), sports=["MLB"], score=True, known={})

    assert len(calls) == 1
    assert calls[0].get("only_games") == {game}
    assert calls[0].get("game_models_only") is True, (
        "the poller re-scores game-level models only; its clears must say so")

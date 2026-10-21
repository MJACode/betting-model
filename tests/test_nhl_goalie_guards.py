"""Every NHL writer refuses a bet whose goalie matchup is not known.

mike, 2026-10-20: "We should absolutely always know the goalie matchup before
making a bet as well." Every NHL model, and any added later, except the
shots-on-goal props (mike, same day: "Ok on shots on goal";
config.NHL_GOALIE_GATE_EXEMPT), which keep deciding at their opening fetch,
before any goalie is confirmed. These tests
drive the real writers -- the scorer, the totals card, both prop cards -- over a
fake database that answers the goalie gate's own reads, so each one shows the
rule holding at the place a pick is written, not in a helper.

Written to import only modules that existed before the rule, so each guard can
be run against the code that did not have it: there the unknown-matchup BET is
written (or decided off the old 16:00Z clock) and the assertion fails. The
gate's own unit tests are tests/test_nhl_goalie_gate.py.
"""
from __future__ import annotations

import inspect
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
import models.nhl_moneyline_anchored as anc
import models.scorer as sc
import scripts.nhl_prop_card as blocked
import scripts.nhl_props_card as props
import scripts.nhl_totals_card as totals
from data.ingestors import nhl_prop_odds_ingestor as prop_odds

ROOT = Path(__file__).resolve().parent.parent
WAITING = "waiting for both confirmed starting goalies"


# ── a database that answers the goalie gate ──────────────────────────────────

class _Rows:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class GoalieDB:
    """`games` {game_id: (home, away)}; `espn` {(game_id, team): status} for the
    latest ESPN designation (missing = never listed). Every team's goalie row
    names the ESPN goalie, so status alone decides. Picks are recorded."""

    def __init__(self, games: dict, espn: dict, slate: list | None = None):
        self.games, self.espn, self.slate = games, espn, slate or []
        self.inserted: list[dict] = []
        self.statements: list[str] = []

    def _goalie(self, gid, team):
        return f"{team} Starter", f"{abs(hash((gid, team))) % 10_000_000}"

    def execute(self, sql, params=None):
        q = " ".join(sql.split())
        self.statements.append(q)
        if q.startswith(("SAVEPOINT", "RELEASE", "ROLLBACK TO", "SET LOCAL", "SELECT pg_advisory")):
            return _Rows([])
        if q.startswith("SELECT game_id, home_team, away_team FROM games WHERE game_id = ANY"):
            return _Rows([(g, *self.games[g]) for g in params[0] if g in self.games])
        if "FROM nhl_goalie_designations" in q:
            out = []
            for (gid, team), status in self.espn.items():
                if gid in params[0]:
                    name, pid = self._goalie(gid, team)
                    out.append((gid, team, "espn", pid, name, status,
                                datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)))
            return _Rows(out)
        if "FROM nhl_goalie_stats" in q:
            out = []
            for gid in params[0]:
                for team in self.games.get(gid, ()):
                    name, pid = self._goalie(gid, team)
                    out.append((gid, team, pid, name, "2026-10-20 10:06:00+00"))
            return _Rows(out)
        if q.startswith("SELECT game_id, home_team, away_team, commence_time FROM games"):
            return _Rows(self.slate)
        if q.startswith("SELECT 1 FROM picks"):
            return _Rows([])
        if q.startswith("INSERT INTO picks"):
            self.inserted.append(dict(params))
            return _Rows([])
        return _Rows([])

    def executemany(self, sql, rows):
        q = " ".join(sql.split())
        self.statements.append(q[:40])
        if q.startswith("INSERT INTO picks"):
            self.inserted += [dict(r) for r in rows]

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _both(gid, home, away, status_home="confirmed", status_away="confirmed"):
    return {(gid, home): status_home, (gid, away): status_away}


# ── the scorer's INSERT, the last line (the totals card writes through it) ──

TOT_GAME = "NHL_2026-10-08_PHI_OTT"
TOT_GAMES = {TOT_GAME: {"home": "OTT", "away": "PHI", "game_date": "2026-10-08",
                        "commence_time": "2026-10-08T23:13:54Z"}}


def _totals_rows():
    import models.nhl_totals_market as mk
    bet = mk.NhlTotalBet(
        game_id=TOT_GAME, side="under", book="betmgm", line=6.0, price=-105.0,
        fair=0.5257, ev=0.5257 * (1 + 100 / 105) - 1, sharp_over=104.0, sharp_under=-119.0,
        created_at="2026-10-08 01:00:07.2+00", soft_snapshot_at="2026-10-08T00:59:30Z",
        sharp_snapshot_at="2026-10-08T00:59:58Z", link="https://betmgm/under",
        dk_price=None, dk_link=None)
    rows = totals.pick_rows([bet], TOT_GAMES, bankroll=10_000)
    assert rows and rows[0]["signal_type"] == "BET"
    return rows


def test_the_scorer_insert_writes_an_unknown_nhl_bet_as_none_with_the_reason():
    db = GoalieDB({TOT_GAME: ("OTT", "PHI")}, _both(TOT_GAME, "OTT", "PHI", status_away="expected"))
    sc._insert_picks(db, _totals_rows())
    assert len(db.inserted) == 1
    row = db.inserted[0]
    assert row["signal_type"] == "NONE" and row["recommended_bet"] == 0.0
    assert row["downgrade_reason"] == f"{WAITING} (PHI expected)"


def test_the_scorer_insert_writes_a_known_nhl_bet_as_a_bet():
    db = GoalieDB({TOT_GAME: ("OTT", "PHI")}, _both(TOT_GAME, "OTT", "PHI"))
    sc._insert_picks(db, _totals_rows())
    assert [r["signal_type"] for r in db.inserted] == ["BET"]


def test_the_totals_card_publishes_nothing_on_an_unknown_game():
    db = GoalieDB({TOT_GAME: ("OTT", "PHI")}, {(TOT_GAME, "OTT"): "confirmed"})    # PHI never listed
    assert totals.publish(db, _totals_rows()) == 0
    assert db.inserted == []


# ── the two prop cards' INSERTs ──────────────────────────────────────────────

PROP_GAME = "NHL_2026-10-01_BOS_NYR"
PROP_GAMES = {PROP_GAME: {"home": "NYR", "away": "BOS", "commence_time": "2026-10-01T23:00:00Z"}}


def _props_row(market="player_shots_on_goal", game=PROP_GAME, games=None, player_id=1):
    """One BET row from the props card's own pick_rows, for the model that
    prices `market` (shots on goal, saves or assists)."""
    import models.nhl_props as P
    spec = next(sp for sp in P.LIVE if sp.market == market)
    games = games or PROP_GAMES
    q = pd.DataFrame([{"game_id": game, "player": f"Player {player_id}", "player_id": player_id,
                       "book": "betmgm", "line": 2.5, "over": -150.0, "under": 120.0,
                       "over_link": "betmgm/o", "under_link": "betmgm/u"}])
    mus = pd.DataFrame([{"player_id": player_id, "game_id": game, "mu": 1.6}])
    rows = props.pick_rows(spec, mus, q, games, "2026-10-01", 1000.0, 0.05 if spec.overdispersed else 0.0)
    assert rows and rows[0]["signal_type"] == "BET" and rows[0]["model_id"] == spec.model_id
    return rows


def _blocked_rows():
    scored = pd.DataFrame([{"player_id": 1, "game_id": PROP_GAME, "mu": 0.9,
                            "quote_player": "Charlie McAvoy", "line": 1.5, "over": -135.0,
                            "under": 105.0, "over_link": "o", "under_link": "u"}])
    rows = blocked.pick_rows(scored, PROP_GAMES, "2026-10-01", bankroll=1000.0)
    assert rows and rows[0]["signal_type"] == "BET"
    return rows


@pytest.mark.parametrize("market", ["player_total_saves", "player_assists"])
def test_the_props_card_insert_refuses_an_unknown_game(market):
    db = GoalieDB({PROP_GAME: ("NYR", "BOS")}, _both(PROP_GAME, "NYR", "BOS", status_home="expected"))
    assert props.publish(db, _props_row(market)) == 0
    assert db.inserted == []


def test_the_props_card_insert_writes_a_shots_on_goal_bet_on_an_unknown_game():
    """The exemption (mike, 2026-10-20: "Ok on shots on goal"): the model never
    reads the goalie, and its early price is its edge."""
    db = GoalieDB({PROP_GAME: ("NYR", "BOS")}, _both(PROP_GAME, "NYR", "BOS", status_home="expected"))
    assert props.publish(db, _props_row("player_shots_on_goal")) == 1
    assert [(r["model_id"], r["signal_type"]) for r in db.inserted] == [("nhl_prop_shots_on_goal", "BET")]


def test_the_blocked_shots_card_insert_refuses_an_unknown_game():
    db = GoalieDB({PROP_GAME: ("NYR", "BOS")}, _both(PROP_GAME, "NYR", "BOS", status_away="expected"))
    assert blocked.publish(db, _blocked_rows()) == 0
    assert db.inserted == []


def test_both_prop_cards_insert_a_known_game():
    db = GoalieDB({PROP_GAME: ("NYR", "BOS")}, _both(PROP_GAME, "NYR", "BOS"))
    for market in ("player_shots_on_goal", "player_total_saves", "player_assists"):
        assert props.publish(db, _props_row(market)) == 1, market
    assert blocked.publish(db, _blocked_rows()) == 1


# ── the cards hold unknown games back BEFORE anything is pooled ──────────────

KNOWN, UNKNOWN = "NHL_2026-10-20_BOS_TOR", "NHL_2026-10-20_DET_SEA"
TWO = {KNOWN: ("TOR", "BOS"), UNKNOWN: ("SEA", "DET")}
TWO_ESPN = {**_both(KNOWN, "TOR", "BOS"), **_both(UNKNOWN, "SEA", "DET", status_home="expected")}
SLATE = {g: {"home": h, "away": a, "commence_time": "2026-10-21T01:40:00Z", "game_date": "2026-10-20"}
         for g, (h, a) in TWO.items()}


def test_the_totals_card_reads_quotes_only_for_known_games(monkeypatch):
    import models.nhl_totals_market as mk
    db = GoalieDB(TWO, TWO_ESPN)
    seen = {}
    monkeypatch.setattr(totals, "get_connection", lambda: db)
    monkeypatch.setattr(totals, "slate", lambda conn, now: dict(SLATE))
    monkeypatch.setattr(mk, "load_fetch_quotes", lambda conn, games: seen.setdefault("games", set(games)))
    monkeypatch.setattr(mk, "find_bets", lambda quotes, now=None: ([], {}))
    totals.run_card(do_publish=True, now=datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc))
    assert seen["games"] == {KNOWN}


def test_the_props_card_scores_only_known_games_except_for_shots_on_goal(monkeypatch):
    """Saves and assists see the known game only. Shots on goal sees the whole
    slate, as it did before the rule, with no confirmation time attached (so
    no quote of its is held back for being older than one)."""
    db = GoalieDB(TWO, TWO_ESPN)
    seen = {}
    monkeypatch.setattr(props, "get_connection", lambda: db)
    monkeypatch.setattr(props, "slate", lambda conn, d, now: {g: dict(v) for g, v in SLATE.items()})

    def score_market(conn, spec, games, game_date, artifact=None, **kw):
        seen[spec.model_id] = games
        return {"priced": 0, "mus": pd.DataFrame(), "quotes": pd.DataFrame(), "rows": [], "skipped": []}
    monkeypatch.setattr(props, "score_market", score_market)
    props.run_card("2026-10-20", do_publish=False, now=datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc))
    assert set(seen["nhl_prop_saves"]) == {KNOWN}
    assert set(seen["nhl_prop_assists"]) == {KNOWN}
    assert set(seen["nhl_prop_shots_on_goal"]) == {KNOWN, UNKNOWN}
    assert all("known_at" not in g for g in seen["nhl_prop_shots_on_goal"].values())


def test_the_blocked_shots_card_reads_quotes_only_for_known_games(monkeypatch):
    db = GoalieDB(TWO, TWO_ESPN)
    seen = {}
    monkeypatch.setattr(blocked, "get_connection", lambda: db)
    monkeypatch.setattr(blocked, "slate", lambda conn, d, now: dict(SLATE))

    def latest_quotes(conn, games):
        seen["games"] = set(games)
        return pd.DataFrame(columns=["game_id", "player", "line", "over", "under", "snap"])
    monkeypatch.setattr(blocked, "latest_quotes", latest_quotes)
    blocked.run_card("2026-10-20", do_publish=False, now=datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc))
    assert seen["games"] == {KNOWN}


class _QuoteConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        return _Rows(self.rows)


def test_a_prop_fetch_older_than_the_confirmation_does_not_decide():
    """The newest fetch 18:00Z, the goalies confirmed 18:30Z: the card waits
    for the next fetch rather than pricing a market that did not know them."""
    games = {KNOWN: {"home": "TOR", "away": "BOS", "commence_time": "2026-10-20T23:00:00Z",
                     "known_at": datetime(2026, 10, 20, 18, 30, tzinfo=timezone.utc)}}
    rows = [(KNOWN, "Skater 1", "betmgm", 2.5, -150, 120, "2026-10-20T18:00:00Z", "o", "u")]
    for market in ("player_assists", "player_total_saves"):
        assert props.latest_quotes(_QuoteConn(rows), games, market).empty, market
    later = [(KNOWN, "Skater 1", "betmgm", 2.5, -150, 120, "2026-10-20T18:40:00Z", "o", "u")]
    assert len(props.latest_quotes(_QuoteConn(later), games, "player_assists")) == 1
    dk = [(KNOWN, "Skater 1", 1.5, -135, 105, "2026-10-20T18:00:00Z", "o", "u")]
    assert blocked.latest_quotes(_QuoteConn(dk), games).empty


def test_a_shots_on_goal_fetch_older_than_the_confirmation_still_decides():
    """The exemption reaches the quote filter too: even handed a game that
    carries a confirmation time, shots on goal keeps the fetch taken before it."""
    games = {KNOWN: {"home": "TOR", "away": "BOS", "commence_time": "2026-10-20T23:00:00Z",
                     "known_at": datetime(2026, 10, 20, 18, 30, tzinfo=timezone.utc)}}
    rows = [(KNOWN, "Skater 1", "betmgm", 2.5, -150, 120, "2026-10-20T12:00:00Z", "o", "u")]
    assert len(props.latest_quotes(_QuoteConn(rows), games, "player_shots_on_goal")) == 1


def test_a_saves_bet_is_only_on_the_confirmed_starter():
    up = pd.DataFrame([{"player_id": 8475831, "player_name": "Philipp Grubauer", "team": "SEA",
                        "game_id": UNKNOWN},
                       {"player_id": 8478916, "player_name": "Joey Daccord", "team": "SEA",
                        "game_id": UNKNOWN}])
    priced = pd.DataFrame([{"game_id": UNKNOWN, "player_id": 8475831, "book": "dk"},
                           {"game_id": UNKNOWN, "player_id": 8478916, "book": "dk"}])
    starters = {UNKNOWN: {"SEA": ("8475831", "Philipp Grubauer")}}
    up2, priced2, skipped = props.starters_only(up, priced, starters)
    assert list(up2.player_name) == ["Philipp Grubauer"]
    assert list(priced2.player_id) == [8475831]
    assert "Joey Daccord" in skipped[0] and "not the confirmed starter" in skipped[0]


# ── shots on goal: exempt, end to end, and in the one-a-game pool ───────────

OPEN_FETCH = "2026-10-20T12:00:00Z"     # 13h40m before puck drop, before any confirmation


class _CardDB(GoalieDB):
    """GoalieDB plus the props card's quote read: one opening fetch, one
    player in every game asked about, for whichever market is asked."""

    def execute(self, sql, params=None):
        q = " ".join(sql.split())
        if "FROM player_prop_odds" in q:
            return _Rows([(g, f"{g[-3:]} Player", "betmgm", 2.5, -150, 120, OPEN_FETCH, "o", "u")
                          for g in params[0]])
        return super().execute(sql, params)


def test_shots_on_goal_writes_a_bet_on_an_unknown_game_at_its_opening_fetch(monkeypatch):
    """The real card from the slate to the INSERT: the goalie split, the quote
    read and its confirmation filter, pick_rows, the pool, publish. Only the
    model's mean is faked. Shots on goal bets both games off the 12:00Z fetch.
    Saves and assists bet neither: one game is unknown, and the other was
    confirmed at 15:00Z, after that fetch."""
    db = _CardDB(TWO, TWO_ESPN)
    monkeypatch.setattr(props, "get_connection", lambda: db)
    monkeypatch.setattr(props, "slate", lambda conn, d, now: {g: dict(v) for g, v in SLATE.items()})
    seen = {}

    def score_market(conn, spec, games, game_date, artifact=None, **kw):
        quotes = props.latest_quotes(conn, games, spec.market)
        seen[spec.model_id] = sorted(set(quotes.game_id))
        quotes["player_id"] = [1 + sorted(TWO).index(g) for g in quotes.game_id]
        mus = quotes[["player_id", "game_id"]].assign(mu=1.6)
        rows = props.pick_rows(spec, mus, quotes, games, game_date, 1000.0,
                               0.05 if spec.overdispersed else 0.0)
        return {"priced": len(quotes), "mus": mus, "quotes": quotes, "rows": rows, "skipped": []}
    monkeypatch.setattr(props, "score_market", score_market)
    out = props.run_card("2026-10-20", do_publish=True, now=datetime(2026, 10, 20, 19, 0, tzinfo=timezone.utc))
    assert seen == {"nhl_prop_saves": [], "nhl_prop_shots_on_goal": sorted([KNOWN, UNKNOWN]),
                    "nhl_prop_assists": []}
    assert out["published"] == 2
    assert sorted((r["game_id"], r["model_id"], r["signal_type"]) for r in db.inserted) == sorted([
        (KNOWN, "nhl_prop_shots_on_goal", "BET"), (UNKNOWN, "nhl_prop_shots_on_goal", "BET")])


def _pool(monkeypatch, db, rows):
    monkeypatch.setattr(props, "get_connection", lambda: db)
    return props.publish_across_models(rows)


def test_the_pool_gives_an_unknown_game_to_shots_on_goal_not_to_a_gated_model(monkeypatch):
    """An assists row for an unknown game with the better EV must not win the
    game's one prop slot and then be refused, leaving the game with nothing:
    the gated row is out of the pool before the slot is chosen."""
    db = GoalieDB({PROP_GAME: ("NYR", "BOS")}, _both(PROP_GAME, "NYR", "BOS", status_away="expected"))
    sog = _props_row("player_shots_on_goal", player_id=1)[0]
    assists = {**_props_row("player_assists", player_id=2)[0], "_ev": sog["_ev"] + 0.5}
    assert _pool(monkeypatch, db, [assists, sog]) == 1
    assert [(r["model_id"], r["player_id"]) for r in db.inserted] == [("nhl_prop_shots_on_goal", "1")]


@pytest.mark.parametrize("market", ["player_total_saves", "player_assists"])
def test_the_pool_writes_no_gated_prop_on_an_unknown_game(monkeypatch, market):
    db = GoalieDB({PROP_GAME: ("NYR", "BOS")}, _both(PROP_GAME, "NYR", "BOS", status_away="expected"))
    assert _pool(monkeypatch, db, _props_row(market) + _blocked_rows()) == 0
    assert db.inserted == []


def test_the_pool_still_allows_one_prop_a_game_once_the_game_is_known(monkeypatch):
    db = GoalieDB({PROP_GAME: ("NYR", "BOS")}, _both(PROP_GAME, "NYR", "BOS"))
    sog = _props_row("player_shots_on_goal", player_id=1)[0]
    assists = {**_props_row("player_assists", player_id=2)[0], "_ev": sog["_ev"] + 0.5}
    assert _pool(monkeypatch, db, [assists, sog]) == 1
    assert [r["model_id"] for r in db.inserted] == ["nhl_prop_assists"]


def test_the_scorer_guards_pass_a_shots_on_goal_bet_and_refuse_the_rest():
    """Per row, by model: the sport-level guard and the INSERT guard."""
    db = GoalieDB({PROP_GAME: ("NYR", "BOS")}, _both(PROP_GAME, "NYR", "BOS", status_home="expected"))
    picks = [_props_row("player_shots_on_goal")[0], _props_row("player_total_saves")[0]]
    assert sc._apply_nhl_goalie_gate(db, PROP_GAME, picks) == 1
    assert [(p["model_id"], p["signal_type"]) for p in picks] == [
        ("nhl_prop_shots_on_goal", "BET"), ("nhl_prop_saves", "NONE")]
    picks = [_props_row("player_shots_on_goal")[0], _props_row("player_assists")[0]]
    sc._refuse_unknown_nhl_bets(db, picks)
    assert [(p["model_id"], p["signal_type"]) for p in picks] == [
        ("nhl_prop_shots_on_goal", "BET"), ("nhl_prop_assists", "NONE")]


def test_an_unknown_game_with_no_prop_fetch_still_owes_its_opening_snapshot():
    """Shots on goal decides at the opening fetch, so the confirmation logic
    must never hold that fetch back. Unchanged from before the rule; pinned."""
    now = START - timedelta(hours=8)
    assert prop_odds.due(START, now, [], known_at=None) == "open"
    assert prop_odds.due(START, now, [], known_at=now - timedelta(minutes=5)) == "open"


# ── the scorer: every NHL model, by sport, not by artifact kind ──────────────

PL_GAME = "NHL_2026-10-20_STL_OTT"


class _Clf:
    def predict_proba(self, X):
        return np.array([[0.42, 0.58]])       # home covers -1.5 58% of the time


def _puckline(monkeypatch, db):
    monkeypatch.setattr(sc, "load_model", lambda mid: {"model": _Clf(), "feature_cols": ["x"]})
    monkeypatch.setattr(sc, "_get_dk_odds", lambda conn, gid, market: {
        "home_price": 150.0, "away_price": -180.0, "spread_home": -1.5, "total_line": None})
    monkeypatch.setattr(sc, "_get_public_betting", lambda conn, gid, market, side: {
        "public_bet_pct": None, "public_money_pct": None})
    for name in ("_stamp_best_game_prices", "_apply_game_injury_gate", "_apply_game_market_gate"):
        monkeypatch.setattr(sc, name, lambda *a, **k: None)
    return {p["pick_side"]: p for p in sc.score_game(
        db, PL_GAME, "nhl_puckline", {"home_team": "OTT", "away_team": "STL",
                                      "game_date": "2026-10-20", "x": 0.0},
        bankroll=1000.0, dry_run=True, commence_time="2026-10-20T23:00:00Z")}


def test_a_non_anchored_nhl_model_cannot_bet_an_unknown_game(monkeypatch):
    """nhl_puckline has no artifact today, and as a stock XGBoost kind it never
    went through the side models' gate: the sport-level guard catches it."""
    db = GoalieDB({PL_GAME: ("OTT", "STL")}, _both(PL_GAME, "OTT", "STL", status_away="expected"))
    picks = _puckline(monkeypatch, db)
    assert picks["home"]["signal_type"] == "NONE"
    assert picks["home"]["downgrade_reason"] == f"{WAITING} (STL expected)"


def test_a_non_anchored_nhl_model_bets_a_known_game(monkeypatch):
    db = GoalieDB({PL_GAME: ("OTT", "STL")}, _both(PL_GAME, "OTT", "STL"))
    assert _puckline(monkeypatch, db)["home"]["signal_type"] == "BET"


# ── the side models: no clock, both goalies confirmed, last night's logs ────

ML_GAME = "NHL_2026-10-20_STL_OTT"


class _Fixed:
    def predict_proba(self, X, offset):
        return np.array([[0.70, 0.30]])          # away STL at -170: EV 0.112


class _ThreeWay:
    def predict_proba(self, X):
        return np.array([[0.42, 0.21, 0.37]])    # away in regulation at +195: EV 0.239


def _frozen(monkeypatch, now: datetime):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)
    monkeypatch.setattr(anc, "datetime", Frozen)


def _side(monkeypatch, db, model_id, now, stale=()):
    _frozen(monkeypatch, now)
    if model_id == "nhl_moneyline":
        art = {"kind": anc.KIND, "model": _Fixed(), "feature_cols": list(anc.FEATURES)}
        odds = {"home_price": 150.0, "away_price": -170.0, "spread_home": None, "total_line": None}
    else:
        art = {"model": _ThreeWay(), "feature_cols": ["x"]}
        odds = {"away_price": 195.0, "draw_price": 310.0, "home_price": 115.0}
    monkeypatch.setattr(sc, "load_model", lambda mid: art)
    monkeypatch.setattr(sc, "_get_dk_odds", lambda conn, gid, market: dict(odds))
    monkeypatch.setattr(sc, "_get_public_betting", lambda conn, gid, market, side: {
        "public_bet_pct": None, "public_money_pct": None})
    for name in ("_stamp_best_game_prices", "_apply_game_injury_gate", "_apply_game_market_gate"):
        monkeypatch.setattr(sc, name, lambda *a, **k: None)
    rows = pd.DataFrame([{f: 0.0 for f in anc.FEATURES}], index=[ML_GAME])
    listed = {(ML_GAME, "OTT"): "1", (ML_GAME, "STL"): "2"}          # both rows exist
    monkeypatch.setattr(anc, "inputs_for_date", lambda conn, d: (rows, listed, set(stale)))
    return {p["pick_side"]: p for p in sc.score_game(
        db, ML_GAME, model_id, {"home_team": "OTT", "away_team": "STL", "game_date": "2026-10-20",
                                "x": 0.0},
        bankroll=1000.0, dry_run=True, commence_time="2026-10-20T23:00:00Z")}


AFTER_OLD_WINDOW = datetime(2026, 10, 20, 20, 30, tzinfo=timezone.utc)   # 4:30pm ET
INSIDE_OLD_WINDOW = datetime(2026, 10, 20, 16, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize("model_id", ["nhl_moneyline", "nhl_moneyline_regulation"])
def test_a_side_model_decides_once_both_goalies_are_confirmed_whatever_the_clock(monkeypatch, model_id):
    """20:30Z was after the old 16:00Z-18:00Z window closed: no decision then."""
    db = GoalieDB({ML_GAME: ("OTT", "STL")}, _both(ML_GAME, "OTT", "STL"))
    assert _side(monkeypatch, db, model_id, AFTER_OLD_WINDOW)["away"]["signal_type"] == "BET"


@pytest.mark.parametrize("model_id", ["nhl_moneyline", "nhl_moneyline_regulation"])
def test_a_listed_goalie_is_not_a_confirmed_one(monkeypatch, model_id):
    """Inside the old window, with both goalie rows written, the old gate bet."""
    db = GoalieDB({ML_GAME: ("OTT", "STL")}, _both(ML_GAME, "OTT", "STL", status_home="expected"))
    picks = _side(monkeypatch, db, model_id, INSIDE_OLD_WINDOW)
    assert picks and all(p["signal_type"] == "NONE" for p in picks.values())
    assert all(p["downgrade_reason"] == f"{WAITING} (OTT expected)" for p in picks.values())


@pytest.mark.parametrize("model_id", ["nhl_moneyline", "nhl_moneyline_regulation"])
def test_known_but_last_nights_logs_missing_still_waits(monkeypatch, model_id):
    db = GoalieDB({ML_GAME: ("OTT", "STL")}, _both(ML_GAME, "OTT", "STL"))
    picks = _side(monkeypatch, db, model_id, AFTER_OLD_WINDOW, stale=("STL",))
    assert picks and all("last night's game logs" in p["downgrade_reason"] for p in picks.values())


def test_the_two_side_models_read_one_gate():
    for fn in (sc._anchored_probability, sc._nhl_regulation_reason):
        assert "_nhl_game_day_reason(" in inspect.getsource(fn)
    assert "_nhl_matchup_reason(" in inspect.getsource(sc._nhl_game_day_reason)


# ── one more prop fetch once the goalies are confirmed ───────────────────────

START = datetime(2026, 10, 20, 23, 0, tzinfo=timezone.utc)


def test_a_game_confirmed_after_its_newest_prop_fetch_owes_one_more_open():
    open_at = START - timedelta(hours=6)
    confirmed = START - timedelta(hours=4)
    now = START - timedelta(hours=3)
    assert prop_odds.due(START, now, [open_at], known_at=confirmed) == "open"
    # once a fetch newer than the confirmation is held, nothing more is owed
    assert prop_odds.due(START, now, [open_at, now], known_at=confirmed) is None
    # confirmed BEFORE the newest fetch: nothing extra
    assert prop_odds.due(START, now, [confirmed + timedelta(minutes=5)], known_at=confirmed) is None
    # not known: the old rule exactly
    assert prop_odds.due(START, now, [open_at]) is None


def test_the_close_is_the_post_confirmation_snapshot_when_both_are_owed():
    open_at = START - timedelta(hours=6)
    now = START - timedelta(minutes=60)
    assert prop_odds.due(START, now, [open_at], known_at=START - timedelta(minutes=65)) == "close"


# ── every INSERT INTO picks is guarded or named here, with why ───────────────

_INSERT = re.compile(r"insert\s+into\s+(?:public\.)?picks\b(?!_)", re.I)
_GUARDS = ("refuse_unknown(", "_refuse_unknown_nhl_bets(")
# A file that writes picks without the NHL goalie guard. Each entry says why.
ALLOWED = {
    "nfl/live_model/pick_writer.py": "NFL in-play picks only; it writes no NHL row",
    "scripts/nba_prop_market_card.py": "NBA player props only",
    "scripts/nba_total_luck_card.py": "NBA full-game totals only",
    "scripts/nfl_prop_market_card.py": "NFL player props only",
    "scripts/nfl_wind_publisher.py": "the NFL wind and opener rules only",
    "scripts/wnba_prop_market_card.py": "WNBA player props only",
    "tracking/first_signal_repair.py": ("restores a BET that already existed, after churn deleted it "
                                        "(CLAUDE.md 1c); refusing it would erase a pick, not stop a bet"),
}
_SKIP = {".git", "node_modules", "__pycache__", "graphify-out", ".venv", "venv", "tests", "mobile"}


def _writers() -> dict[str, str]:
    out = {}
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if _SKIP & set(rel.parts[:-1]) or rel.name.startswith("test_"):
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        if _INSERT.search(src):
            out[rel.as_posix()] = src
    return out


def test_every_picks_insert_is_behind_the_goalie_guard_or_named_with_a_reason():
    writers = _writers()
    assert "models/scorer.py" in writers                 # the scan sees the main writer
    unguarded = [f for f, src in writers.items()
                 if f not in ALLOWED and not any(g in src for g in _GUARDS)]
    assert not unguarded, (f"{unguarded} write picks with no NHL goalie guard. Call "
                           f"models.nhl_goalie_gate.refuse_unknown before the INSERT, or add the "
                           f"file to ALLOWED with the reason it can never write an NHL bet.")
    for f, why in ALLOWED.items():
        assert why.strip(), f
        assert f in writers, f"{f} is allow-listed but no longer inserts into picks: remove it"
        assert not any(g in writers[f] for g in _GUARDS) or f == "tracking/first_signal_repair.py"


def test_the_three_nhl_insert_sites_call_the_guard_in_their_own_body():
    assert "_refuse_unknown_nhl_bets(conn, picks)" in inspect.getsource(sc._insert_picks)
    assert "refuse_unknown(" in inspect.getsource(props.publish)
    assert "refuse_unknown(" in inspect.getsource(blocked.publish)
    # and the totals card, which inserts through the scorer, refuses first too
    assert "refuse_unknown(" in inspect.getsource(totals.publish)


def test_every_nhl_model_is_behind_a_goalie_guard():
    """Every NHL model is reached by a guard; the guards let through only the
    models config exempts (pinned to shots on goal in test_nhl_goalie_gate)."""
    from models.trainer import MODELS
    nhl = ({m for m in config.ACTION_THRESHOLDS if m.startswith("nhl_")}
           | {m for m, (sp, _, _) in MODELS.items() if sp == "NHL"})
    assert config.NHL_GOALIE_GATE_EXEMPT <= nhl
    assert nhl >= {"nhl_moneyline", "nhl_moneyline_regulation", "nhl_over_under", "nhl_puckline",
                   "nhl_prop_blocked_shots", "nhl_prop_saves", "nhl_prop_shots_on_goal",
                   "nhl_prop_assists"}
    by_scorer = {m for m, (sp, _, _) in MODELS.items() if sp == "NHL"}
    by_cards = {totals.MODEL_ID} | set(props.PROP_MODEL_IDS)
    assert nhl - by_scorer - by_cards == set(), "an NHL model no goalie guard reaches"
    # the scorer's guard is by SPORT, so a new NHL model in MODELS is covered
    src = inspect.getsource(sc.score_game)
    assert "_apply_nhl_goalie_gate(" in src and "NHL_GOALIE_SPORT" in src


# ── the five-minute job, and how it takes turns with the refresh pass ───────

def test_the_designation_poll_runs_before_every_nhl_decider_in_the_pass():
    sh = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")

    def at(name):
        m = re.search(rf"^step {re.escape(name)}$", sh, re.M)
        assert m, name
        return m.start()
    for poll in ("nhl-goalie-designations", "nhl-goalie-designations-today"):
        for decider in ("odds", "nhl-over-under", "nhl-prop-odds", "nhl-prop-scoring", "scoring"):
            assert at(poll) < (sh.index("par odds") if decider == "odds" else at(decider)), (poll, decider)
    rp = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    assert '"nhl-goalie-designations": lambda: step_nhl_goalie_designations()' in rp
    assert '"nhl-goalie-designations-today": lambda: step_nhl_goalie_designations(today_only=True)' in rp


def test_the_window_job_is_every_five_minutes_from_11am_to_1155pm_et(monkeypatch):
    import scheduler
    from tracking.job_heartbeat import MAX_SILENCE
    monkeypatch.setattr("tracking.job_heartbeat.seed", lambda *a, **k: None, raising=False)
    sched = scheduler.build_scheduler()
    job = sched.get_job("nhl_goalie_window")
    assert job is not None
    et = __import__("zoneinfo").ZoneInfo("America/New_York")
    day = datetime(2026, 10, 21, 0, 0, tzinfo=et)
    fires, t = [], day - timedelta(seconds=1)
    while True:
        t = job.trigger.get_next_fire_time(None, t + timedelta(seconds=1))
        if t is None or t >= day + timedelta(days=1):
            break
        fires.append(t)
    assert len(fires) == 13 * 12
    assert (fires[0].hour, fires[0].minute) == (11, 0) and (fires[-1].hour, fires[-1].minute) == (23, 55)
    assert "nhl_goalie_window" in scheduler._PIPELINE_JOBS
    assert MAX_SILENCE["nhl_goalie_window"] >= 665


def _tick(monkeypatch, decide):
    import scheduler
    import scripts.nhl_goalie_window as win
    calls = []
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: calls.append(label) or "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: calls.append("publish"))
    monkeypatch.setattr(win, "has_games_today", lambda now=None: True)
    monkeypatch.setattr(win, "plan_tick", lambda decided=None, now=None: win.Plan(
        games=sorted(decide), decide=dict(decide)))
    monkeypatch.setattr(scheduler, "_NHL_DECIDED", {})
    return scheduler, calls


def test_a_tick_polls_then_decides_the_newly_known_games(monkeypatch):
    t0 = datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc)
    scheduler, calls = _tick(monkeypatch, {KNOWN: t0})
    scheduler.run_nhl_goalie_window()
    assert calls == ["nhl-goalie-poll", "nhl-prop-odds", "nhl-goalie-window-score",
                     "nhl-over-under", "nhl-prop-scoring", "publish"]
    assert scheduler._NHL_DECIDED == {KNOWN: t0}


def test_a_tick_stands_down_while_a_refresh_pass_runs(monkeypatch):
    scheduler, calls = _tick(monkeypatch, {KNOWN: None})
    assert scheduler._REFRESH_LOCK.acquire(blocking=False)
    try:
        scheduler.run_nhl_goalie_window()
    finally:
        scheduler._REFRESH_LOCK.release()
    assert calls == ["nhl-goalie-poll"]           # the poll still runs; the pass decides


def test_a_refresh_pass_waits_for_the_window_instead_of_skipping(monkeypatch):
    import scheduler
    ran = []
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: ran.append(time.monotonic()) or "ok")
    assert scheduler._NHL_WINDOW_LOCK.acquire(blocking=False)
    released = {}

    def release():
        time.sleep(0.3)
        released["at"] = time.monotonic()
        scheduler._NHL_WINDOW_LOCK.release()
    threading.Thread(target=release).start()
    scheduler.run_refresh_pass("evening")
    assert ran and ran[0] >= released["at"]
    assert not scheduler._NHL_WINDOW_LOCK.locked()


def test_the_wait_covers_everything_the_window_may_take_under_its_lock():
    """A pass that gave up before the window could legitimately finish would
    overlap it, which is what the lock is for."""
    import scheduler
    t = scheduler.NHL_GOALIE_WINDOW_TIMEOUT_S
    held = sum(t[k] for k in ("prop_odds", "score", "totals", "props"))
    assert set(scheduler.NHL_GOALIE_WINDOW_LOCKED_STEPS) == {"prop_odds", "score", "totals", "props"}
    assert scheduler._nhl_window_wait_s() > held

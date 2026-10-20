"""nba_prop_market: same-line unders against Pinnacle (models/nba_prop_market.py,
scripts/nba_prop_market_card.py).

Each test pins one property of the rule as it was graded
(docs/nba_models_2026.md 4.3) or of the card that writes it: the same line and
the same fetch, coherent two-way quotes, the EV floor on Pinnacle's own number,
unders only, the best bettable price with Pinnacle and Bovada never taken, the
45-57 minute window, every qualifying proposition (no game or night cap), each
game decided once (the decisions ledger), insert-once under the lock, name
refusal, the row shape, settlement and the closing-line path.
"""
from __future__ import annotations

import inspect
import re
from datetime import datetime, timedelta, timezone

import pytest

import config
import models.nba_prop_market as mk
import scripts.nba_prop_market_card as card
from models.market_relative import implied

TIP = datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc)        # 8:00pm ET, 2026-10-21
NOW = TIP - timedelta(minutes=55)
FETCH = (NOW - timedelta(minutes=2)).isoformat()
OLDER = (NOW - timedelta(minutes=12)).isoformat()
GID = "NBA_2026-10-21_GSW_LAL"
GAMES = {GID: {"home": "LAL", "away": "GSW", "game_date": "2026-10-21",
               "season": 2027, "tip": TIP}}
ROSTER = mk.Roster([("201939", "Stephen Curry", "GSW"),
                    ("2544", "LeBron James", "LAL"),
                    ("1629029", "Luka Doncic", "LAL")])


def q(book, over, under, line=24.5, player="Stephen Curry", market="player_points",
      snap=FETCH, lu=None, kind="open", gid=GID):
    lu = lu if lu is not None else snap
    return {"game_id": gid, "player": player, "market": market, "book": book,
            "line": line, "over_price": over, "under_price": under,
            "over_link": f"{book}-o", "under_link": f"{book}-u",
            "snapshot_at": snap, "book_last_update": lu, "snapshot_type": kind}


def run_full(quotes, now=NOW, games=None, roster=ROSTER, taken=None, soft_books=None,
             decided=None):
    """(bets, diag, decisions)."""
    extra = {} if decided is None else {"decided": decided}
    return mk.find_bets(quotes, games or GAMES, roster, now, taken=taken,
                        soft_books=soft_books, **extra)


def run(quotes, now=NOW, games=None, roster=ROSTER, taken=None, soft_books=None):
    return run_full(quotes, now, games, roster, taken, soft_books)[:2]


def fair_under(over, under):
    o, u = implied(over), implied(under)
    return u / (o + u)


# ── the rule ─────────────────────────────────────────────────────────────────

def test_a_plus_ev_under_is_bet_at_the_best_bettable_price():
    quotes = [q("pinnacle", -115, -105), q("draftkings", -120, +100),
              q("fanduel", -125, +105), q("betmgm", -118, -102)]
    bets, diag = run(quotes)
    assert len(bets) == 1
    b = bets[0]
    assert (b.book, b.price, b.line, b.market) == ("fanduel", 105.0, 24.5, "player_points")
    assert b.fair == pytest.approx(fair_under(-115, -105))
    assert b.ev == pytest.approx(b.fair * 2.05 - 1)
    assert b.dk_price == 100.0 and b.dk_link == "draftkings-u"
    assert diag["bets"] == 1 and diag["pinnacle_present"] == 1


def test_only_pinnacles_exact_line_is_compared():
    quotes = [q("pinnacle", -115, -105, line=24.5),
              q("fanduel", -150, +130, line=23.5)]           # a fat under, at another number
    bets, diag = run(quotes)
    assert bets == [] and diag["line_mismatch"] == 1


def test_only_the_newest_fetch_is_priced():
    """A better soft price from an older fetch is never paired with Pinnacle's
    newer quote, and a book missing from the newest fetch is not carried forward."""
    quotes = [q("pinnacle", -115, -105, snap=OLDER), q("fanduel", -150, +140, snap=OLDER),
              q("pinnacle", -115, -105), q("draftkings", -125, +105)]
    bets, _ = run(quotes)
    assert [(b.book, b.price, b.fetch) for b in bets] == [("draftkings", 105.0, FETCH)]


def test_a_newer_fetch_without_pinnacle_skips_the_game():
    quotes = [q("pinnacle", -115, -105, snap=OLDER), q("fanduel", -125, +105, snap=OLDER),
              q("fanduel", -125, +105)]
    bets, diag = run(quotes)
    assert bets == [] and diag["pinnacle_withdrawn"] == 1


def test_a_fetch_older_than_the_window_is_not_a_price():
    stale = (TIP - timedelta(minutes=80)).isoformat()
    quotes = [q("pinnacle", -115, -105, snap=stale), q("fanduel", -125, +105, snap=stale)]
    bets, diag = run(quotes)
    assert bets == [] and diag["stale_fetch"] == 1


def test_incoherent_quotes_are_not_prices():
    # Pinnacle summing past 1.15 (-200/-200 = 1.333) is not a two-way price.
    bets, diag = run([q("pinnacle", -200, -200), q("fanduel", -125, +105)])
    assert bets == [] and diag["sharp_incoherent"] == 1
    # A one-way soft quote is not compared either.
    bets, diag = run([q("pinnacle", -115, -105), q("fanduel", None, +130)])
    assert bets == [] and diag["soft_incoherent"] == 1
    # Under 1.00 (an arb) is refused at both ends.
    bets, diag = run([q("pinnacle", +110, +110), q("fanduel", -125, +105)])
    assert bets == [] and diag["sharp_incoherent"] == 1


def test_the_coherent_band_is_inclusive_as_the_lab_graded_it():
    assert mk.COHERENT == (1.00, 1.15)
    assert mk.coherent({"over_price": +100, "under_price": +100})    # sum exactly 1.00
    assert not mk.coherent({"over_price": +101, "under_price": +101})


def test_the_ev_floor_is_zero_on_pinnacles_own_number(monkeypatch):
    assert config.min_ev_for(mk.MODEL_ID) == 0.0
    assert mk.MODEL_ID in config.MODELS_ON_OWN_PROBABILITY
    # fair under 0.5 exactly: -110 is EV -0.045, +100 is EV 0.000 (bet), +105 +0.025.
    bets, diag = run([q("pinnacle", -110, -110), q("fanduel", -110, -110)])
    assert bets == [] and diag["below_ev_floor"] == 1
    bets, _ = run([q("pinnacle", -110, -110), q("fanduel", -120, +100)])
    assert len(bets) == 1 and bets[0].ev == pytest.approx(0.0)
    # Through the platform gate: a borrowed calibration map must not move it.
    import models.scorer as sc
    monkeypatch.setattr(sc, "_calibrated", lambda mid, p: 0.40)
    bets, _ = run([q("pinnacle", -110, -110), q("fanduel", -120, +100)])
    assert len(bets) == 1


def test_unders_only():
    """Pinnacle 60/40 on the over: a soft over at +120 is +32% EV and must not be bet."""
    bets, diag = run([q("pinnacle", -150, +130), q("fanduel", +120, -150)])
    assert bets == [] and diag["below_ev_floor"] == 1
    assert mk.SIDE == "under"


def test_pinnacle_and_bovada_are_never_bet():
    assert "pinnacle" not in mk.SOFT_BOOKS and "bovada" not in mk.SOFT_BOOKS
    assert set(mk.SOFT_BOOKS) <= set(config.BEST_LINE_BOOKMAKERS)
    quotes = [q("pinnacle", -115, -105), q("bovada", -150, +150)]
    bets, _ = run(quotes, soft_books=("bovada", "pinnacle", "fanduel"))
    assert bets == []


def test_the_price_floor_is_minus_200():
    assert config.min_odds_for(mk.MODEL_ID) == -200
    # Pinnacle 25/75 on the under side: -210 is +EV but under the floor.
    bets, diag = run([q("pinnacle", +240, -300), q("fanduel", +200, -210)])
    assert bets == [] and diag["below_price_floor"] == 1


def test_a_stale_soft_quote_is_refused_and_counted():
    pin_lu = (NOW - timedelta(minutes=3)).isoformat()
    stale = (NOW - timedelta(minutes=14)).isoformat()      # 11 minutes behind Pinnacle
    fresh = (NOW - timedelta(minutes=12)).isoformat()      # 9 minutes behind
    bets, diag = run([q("pinnacle", -115, -105, lu=pin_lu), q("fanduel", -125, +105, lu=stale)])
    assert bets == [] and diag["stale_rejected"] == 1
    bets, diag = run([q("pinnacle", -115, -105, lu=pin_lu), q("fanduel", -125, +105, lu=fresh)])
    assert len(bets) == 1 and diag["stale_rejected"] == 0


def test_a_quote_with_no_clock_is_counted_not_refused():
    quotes = [q("pinnacle", -115, -105), dict(q("fanduel", -125, +105), book_last_update=None)]
    bets, diag = run(quotes)
    assert len(bets) == 1 and diag["last_update_unknown"] == 1


# ── the window and the read bounds ───────────────────────────────────────────

@pytest.mark.parametrize("lead,bets_expected,key", [
    (70, 0, "too_early"), (58, 0, "too_early"), (57, 1, "in_window"), (55, 1, "in_window"),
    (45, 1, "in_window"), (44, 0, "too_late"),
])
def test_only_45_to_57_minutes_before_tip(lead, bets_expected, key):
    now = TIP - timedelta(minutes=lead)
    snap = now.isoformat()                       # fetched by this pass
    bets, diag = run([q("pinnacle", -115, -105, snap=snap), q("fanduel", -125, +105, snap=snap)],
                     now=now)
    assert len(bets) == bets_expected and diag[key] == 1


def test_the_price_must_be_from_inside_the_window_too():
    """At tip-57 a fetch taken at tip-58 is a price from before the window."""
    now = TIP - timedelta(minutes=57)
    snap = (TIP - timedelta(minutes=58)).isoformat()
    bets, diag = run([q("pinnacle", -115, -105, snap=snap), q("fanduel", -125, +105, snap=snap)],
                     now=now)
    assert bets == [] and diag["stale_fetch"] == 1


def test_the_tip_is_the_earlier_of_the_schedule_and_the_feed():
    sched = "2026-10-21T23:00:00+00:00"
    feed = "2026-10-21T23:10:00+00:00"          # the odds feed's later start
    assert mk.tip_of(sched, feed) == mk.parse_ts(sched)
    assert mk.tip_of(None, feed) == mk.parse_ts(feed)


class _SlateConn:
    """The slate's two reads: tonight's games joined to the schedule, and the
    season's schedule days (scripts.nba_total_luck_card.schedule_days)."""

    def __init__(self, games, days):
        self.games, self.days = games, days

    def execute(self, sql, params):
        self._rows = self.days if "SELECT DISTINCT season, game_date, game_type" in sql else self.games
        return self

    def fetchall(self):
        return self._rows


# 2026-27 as stored: regular-season days 10-20..04-11, a Cup final placeholder.
_DAYS = [(2027, "2026-10-20", "regular"), (2027, "2027-04-11", "regular"),
         (2027, "2026-12-11", "cup_final")]


def _t(m):
    return (TIP + timedelta(minutes=m)).isoformat()


def test_the_slate_is_regular_season_games_inside_the_horizon():
    """The tip is the schedule's when the feed's is later; a game past its tip
    or beyond the window is not priced; the Cup final is not priced."""
    rows = [
        ("REG", "LAL", "GSW", "2026-10-21", 2027, _t(10), _t(0), "regular"),
        ("CUP", "LAL", "GSW", "2026-10-21", 2027, _t(0), _t(0), "cup_final"),
        ("LATER", "LAL", "GSW", "2026-10-21", 2027, _t(30), _t(30), "regular"),
        ("STARTED", "LAL", "GSW", "2026-10-21", 2027, _t(-60), _t(-60), "regular"),
    ]
    skipped = []
    games = card.slate(_SlateConn(rows, _DAYS), NOW, skipped)
    assert sorted(games) == ["REG"] and games["REG"]["tip"] == TIP
    assert sorted(s.split()[0] for s in skipped) == ["CUP"]


def test_an_nba_cup_week_game_the_schedule_does_not_list_is_still_priced():
    """The 2026-27 schedule was loaded before the league set the Cup week, so
    24 regular-season games were not in it, while the odds feed writes each into
    `games`. Such a game on a regular-season day is in the graded population
    (1,230 regular-season games a season) and is priced; one on a day the
    schedule gives to another kind of game (the Cup final's) is not."""
    rows = [
        ("CUPWEEK", "LAL", "GSW", "2026-12-07", 2027, _t(0), None, None),
        ("FINALDAY", "LAL", "GSW", "2026-12-11", 2027, _t(0), None, None),
        ("NOSEASON", "LAL", "GSW", "2026-12-07", 2028, _t(0), None, None),
    ]
    skipped = []
    games = card.slate(_SlateConn(rows, _DAYS), NOW, skipped)
    assert sorted(games) == ["CUPWEEK"] and games["CUPWEEK"]["tip"] == TIP
    assert sorted(s.split()[0] for s in skipped) == ["FINALDAY", "NOSEASON"]


def test_the_postseason_is_never_priced():
    """Neither NBA prop model was graded on a play-in, playoff or Cup final game:
    the stored prop history holds none of the 272 of 2023-24..2025-26 (and all
    3,690 regular-season games). Each is skipped and named, by its type."""
    rows = [(gid, "LAL", "GSW", "2026-10-21", 2027, _t(0), _t(0), kind)
            for gid, kind in (("PI", "playin"), ("PO", "playoff"), ("CF", "cup_final"),
                              ("PRE", "preseason"))]
    skipped = []
    assert card.slate(_SlateConn(rows, _DAYS), NOW, skipped) == {}
    assert sorted(skipped) == ["CF (cup_final)", "PI (playin)", "PO (playoff)", "PRE (preseason)"]


def test_a_fetch_after_now_or_at_tip_and_a_close_row_never_decide():
    later = (NOW + timedelta(minutes=1)).isoformat()
    bets, _ = run([q("pinnacle", -115, -105, snap=later), q("fanduel", -125, +105, snap=later)])
    assert bets == []
    bets, _ = run([q("pinnacle", -115, -105, kind="close"), q("fanduel", -125, +105, kind="close")])
    assert bets == []


def test_the_card_reads_open_rows_only():
    src = inspect.getsource(mk.load_quotes)
    assert "snapshot_type = 'open'" in src
    import tracking.paper_tracker as pt
    sql = inspect.getsource(pt._closing_prop_odds).split('conn.execute("""', 1)[1].split('"""', 1)[0]
    assert "snapshot_type" not in sql           # the CLV capture reads the 'close' rows


def test_the_read_starts_just_before_the_window_and_casts_numerics():
    """Props are fetched for days before a game; the card reads only what can
    decide it (a fetch older than tip-57 cannot), in one statement."""
    from decimal import Decimal
    seen = {}

    class _C:
        def execute(self, sql, params):
            seen["sql"], seen["params"] = " ".join(sql.split()), params
            return self

        def fetchall(self):
            return [(GID, "Stephen Curry", "player_points", "pinnacle", Decimal("24.5"),
                     Decimal("-115"), Decimal("-105"), None, None, FETCH, None, "open")]

    out = mk.load_quotes(_C(), GAMES, NOW)
    assert seen["params"][3] == (TIP - timedelta(minutes=62)).isoformat()
    assert "snapshot_type = 'open'" in seen["sql"] and "snapshot_at >= %s" in seen["sql"]
    assert out[0]["line"] == 24.5 and isinstance(out[0]["under_price"], float)


def test_a_game_already_bet_is_never_decided_again():
    bets, diag = run([q("pinnacle", -115, -105), q("fanduel", -125, +105)], taken={GID})
    assert bets == [] and diag["already_bet"] == 1


def test_a_missed_window_is_counted():
    now = TIP - timedelta(minutes=40)
    early = (TIP - timedelta(minutes=100)).isoformat()      # nothing fetched 45-57 before tip
    _, diag = run([q("pinnacle", -115, -105, snap=early)], now=now)
    assert diag["too_late"] == 1 and diag["window_missed"] == 1
    inside = (TIP - timedelta(minutes=50)).isoformat()
    _, diag = run([q("pinnacle", -115, -105, snap=inside)], now=now)
    assert diag["window_missed"] == 0


# ── names ────────────────────────────────────────────────────────────────────

def test_a_name_two_players_share_on_the_two_teams_is_refused():
    roster = mk.Roster([("1", "Jalen Smith", "GSW"), ("2", "Jalen Smith", "LAL")])
    quotes = [q("pinnacle", -115, -105, player="Jalen Smith"),
              q("fanduel", -125, +105, player="Jalen Smith")]
    bets, diag = run(quotes, roster=roster)
    assert bets == [] and diag["ambiguous"] >= 1


def test_a_name_on_neither_team_is_skipped():
    bets, diag = run([q("pinnacle", -115, -105, player="Nobody Atall"),
                      q("fanduel", -125, +105, player="Nobody Atall")])
    assert bets == [] and diag["unresolved"] >= 1


def test_books_spelling_a_player_differently_pair_on_his_id():
    roster = mk.Roster([("1629029", "Luka Doncic", "LAL")])
    quotes = [q("pinnacle", -115, -105, player="Luka Dončić"),
              q("fanduel", -125, +105, player="Luka Doncic")]
    bets, _ = run(quotes, roster=roster)
    assert [(b.player, b.player_id) for b in bets] == [("Luka Doncic", "1629029")]


def test_a_rookie_logged_under_an_espn_id_resolves_to_it():
    roster = mk.Roster([("espn:5105565", "Cooper Flagg", "LAL")])
    assert roster.resolve("Cooper Flagg", "LAL", "GSW") == ("espn:5105565", "ok")


def test_the_resolver_uses_the_results_writers_normaliser():
    """The id taken at pick time must be the one the results writer stores."""
    from data.ingestors.wnba_results_ingestor import norm_player_name
    for n in ("Jaren Jackson Jr.", "Luka Dončić", "De'Aaron Fox", "Karl-Anthony Towns"):
        assert mk.name_key(n) == norm_player_name(n)


def test_a_books_initials_match_the_logs():
    """Measured 2026-10-16: the books list "R.J. Barrett", the log "RJ Barrett"."""
    assert mk.name_key("R.J. Barrett") == mk.name_key("RJ Barrett") == "rj barrett"
    assert mk.name_key("O.G. Anunoby") == mk.name_key("OG Anunoby")
    roster = mk.Roster([("1629628", "RJ Barrett", "TOR")])
    assert roster.resolve("R.J. Barrett", "TOR", "CHI") == ("1629628", "ok")


# ── every qualifying proposition, no game or night cap ───────────────────────

def test_every_qualifying_proposition_is_bet_at_its_best_price():
    """mike, 2026-10-16: "maximize units won". One bet per (game, player,
    market) at the best bettable price; no game or night cap."""
    reb = dict(player="LeBron James", market="player_rebounds", line=7.5)
    ast = dict(player="LeBron James", market="player_assists", line=6.5)
    quotes = [q("pinnacle", -115, -105), q("fanduel", -125, +105), q("betmgm", -130, +110),
              q("draftkings", -120, +100),
              q("pinnacle", -110, -110, **reb), q("fanduel", -140, +120, **reb),
              q("pinnacle", -110, -110, **ast), q("betmgm", -130, +110, **ast)]
    bets, diag = run(quotes)
    assert sorted((b.player, b.market, b.book, b.price) for b in bets) == [
        ("LeBron James", "player_assists", "betmgm", 110.0),
        ("LeBron James", "player_rebounds", "fanduel", 120.0),
        ("Stephen Curry", "player_points", "betmgm", 110.0)]          # the best of two books
    assert diag["bets"] == 3 and diag["qualifying"] == 4


def _decision(gid=GID, n_bets=0, n_quotes=2):
    return mk.NbaPropDecision(game_id=gid, fetch_at=FETCH, n_quotes=n_quotes,
                              n_bets=n_bets, detail="test")


def test_no_game_or_night_cap_is_left_anywhere():
    """The caps are gone, not set high: nine bets over six games of one night,
    three of them in one game, are all written."""
    for name in ("MAX_BETS_PER_GAME", "MAX_BETS_PER_NIGHT"):
        assert not hasattr(mk, name), name
    for name in ("one_per_game", "per_night", "bets_by_night"):
        assert not hasattr(card, name), name
    bets = [_bet(f"G{i}", ev=0.01 * (i + 1)) for i in range(6)]
    bets += [_bet("G0", market="player_rebounds", line=7.5),
             _bet("G0", market="player_assists", line=6.5),
             _bet("G1", market="player_threes", line=3.5)]
    rows = card.pick_rows(bets, bankroll=1000.0)
    decisions = [_decision(f"G{i}", n_bets=sum(r["game_id"] == f"G{i}" for r in rows))
                 for i in range(6)]
    conn = _PublishConn()
    assert card.publish(conn, rows, decisions) == (9, 6)
    assert len(conn.inserted) == 9 and len(conn.decisions) == 6


# ── each game decided once ───────────────────────────────────────────────────

def test_a_look_with_pinnacle_in_the_window_decides_the_game_even_with_no_bet():
    """The backtest looked at every game once. A look whose newest fetch holds
    Pinnacle inside the window IS that look, whether or not anything cleared."""
    bets, diag, decisions = run_full([q("pinnacle", -110, -110), q("fanduel", -110, -110)])
    assert bets == [] and diag["below_ev_floor"] == 1
    assert [(d.game_id, d.fetch_at, d.n_quotes, d.n_bets) for d in decisions] == [(GID, FETCH, 2, 0)]
    assert diag["decided"] == 1
    bets, diag, decisions = run_full([q("pinnacle", -115, -105), q("fanduel", -125, +105)])
    assert [(d.game_id, d.n_bets) for d in decisions] == [(GID, 1)] and len(bets) == 1


@pytest.mark.parametrize("why", ["no_sharp", "pinnacle_withdrawn", "stale_fetch", "too_early"])
def test_a_look_that_cannot_price_the_game_is_not_a_decision(why):
    """No Pinnacle, Pinnacle missing from the newest fetch, a fetch from before
    the window, or a look before the window: the game is tried again next look."""
    stale = (TIP - timedelta(minutes=80)).isoformat()
    now = NOW
    quotes = {
        "no_sharp": [q("fanduel", -125, +105)],
        "pinnacle_withdrawn": [q("pinnacle", -115, -105, snap=OLDER),
                               q("fanduel", -125, +105, snap=OLDER), q("fanduel", -125, +105)],
        "stale_fetch": [q("pinnacle", -115, -105, snap=stale), q("fanduel", -125, +105, snap=stale)],
        "too_early": [q("pinnacle", -115, -105, snap=stale), q("fanduel", -125, +105, snap=stale)],
    }[why]
    if why == "too_early":
        now = TIP - timedelta(minutes=78)
    bets, diag, decisions = run_full(quotes, now=now)
    assert bets == [] and decisions == [] and diag[why] == 1 and diag["decided"] == 0


def test_a_game_already_decided_is_never_looked_at_again():
    bets, diag, decisions = run_full([q("pinnacle", -115, -105), q("fanduel", -125, +105)],
                                     decided={GID})
    assert bets == [] and decisions == [] and diag["already_decided"] == 1
    # past the window it is still a decided game, never a missed one
    now = TIP - timedelta(minutes=30)
    _, diag, _ = run_full([q("pinnacle", -115, -105, snap=(TIP - timedelta(minutes=100)).isoformat())],
                          now=now, decided={GID})
    assert diag["already_decided"] == 1 and diag["window_missed"] == 0


def test_the_card_records_a_decision_when_nothing_qualifies(monkeypatch):
    """A zero-bet decision is still a decision: the card must write it, or the
    next look re-decides the game on a later price."""
    seen = {}

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(card, "get_connection", lambda: _Conn())
    monkeypatch.setattr(card, "ensure_decisions_table", lambda c: None)
    monkeypatch.setattr(card, "slate", lambda c, now, skipped=None: dict(GAMES))
    monkeypatch.setattr(card, "games_with_a_bet", lambda c, ids: set())
    monkeypatch.setattr(card, "decided_games", lambda c, ids: set())
    monkeypatch.setattr(card, "load_roster", lambda c, g: ROSTER)
    monkeypatch.setattr(mk, "load_quotes",
                        lambda c, g, now: [q("pinnacle", -110, -110), q("fanduel", -110, -110)])

    def _publish(c, rows, decisions):
        seen.update(rows=rows, decisions=decisions)
        return 0, len(decisions)

    monkeypatch.setattr(card, "publish", _publish)
    out = card.run_card(do_publish=True, now=NOW)
    assert seen["rows"] == [] and [d.game_id for d in seen["decisions"]] == [GID]
    assert out["decided"] == 1 and out["published"] == 0


def test_the_decisions_ledger_is_worker_only_and_created_behind_the_guard(monkeypatch):
    from data.anon_readable import WORKER_ONLY_TABLES
    assert card.DECISIONS_TABLE == "nba_prop_market_decisions"
    assert card.DECISIONS_TABLE in WORKER_ONLY_TABLES

    class _C:
        def __init__(self):
            self.sql, self.commits = [], 0

        def execute(self, sql, params=None):
            self.sql.append(" ".join(sql.split()))
            return self

        def fetchone(self):
            return None

        def rollback(self):
            pass

        def commit(self):
            self.commits += 1

    monkeypatch.setattr(card, "schema_is_current", lambda *a, **k: True)
    c = _C()
    card.ensure_decisions_table(c)
    assert c.sql == [], "an existing ledger must cost no DDL (the PostgREST reload trap)"
    monkeypatch.setattr(card, "schema_is_current", lambda *a, **k: False)
    c = _C()
    card.ensure_decisions_table(c)
    ddl = [s for s in c.sql if "relrowsecurity" not in s]
    assert ddl[0].startswith("CREATE TABLE IF NOT EXISTS nba_prop_market_decisions")
    for col in ("game_id TEXT PRIMARY KEY", "decided_at TIMESTAMPTZ", "fetch_at TEXT",
                "n_quotes INTEGER", "n_bets INTEGER", "detail TEXT"):
        assert col in ddl[0], col
    assert "REVOKE ALL ON nba_prop_market_decisions FROM anon, authenticated" in ddl
    assert "ALTER TABLE nba_prop_market_decisions ENABLE ROW LEVEL SECURITY" in ddl
    assert c.commits == 1


# ── insert once, under the lock ──────────────────────────────────────────────

class _PublishConn:
    def __init__(self, taken=(), decided=()):
        self.taken, self.decided = set(taken), set(decided)
        self.sql, self.inserted, self.decisions, self.commits = [], [], [], 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        self.sql.append(s)
        self._one, self._all = None, []
        if "SELECT DISTINCT game_id FROM picks" in s:
            self._all = [(g,) for g in params[1] if g in self.taken]
        elif "FROM nba_prop_market_decisions" in s and s.startswith("SELECT"):
            self._all = [(g,) for g in params[0] if g in self.decided]
        elif s.startswith("INSERT INTO nba_prop_market_decisions"):
            gid = params["game_id"]
            if gid not in self.decided:
                self.decided.add(gid)
                self.decisions.append(gid)
                self._one = (gid,)
        elif s.startswith("INSERT INTO picks"):
            self.inserted.append(params)
            self._one = (len(self.inserted),)
        return self

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all

    def commit(self):
        self.sql.append("COMMIT")
        self.commits += 1


def _bet(gid=GID, book="fanduel", price=105.0, dk=None, ev=0.03, player="Stephen Curry",
         market="player_points", line=24.5, game_date="2026-10-21"):
    return mk.NbaPropBet(
        game_id=gid, game_date=game_date, tip=TIP.isoformat(), player=player,
        player_id="201939", market=market, line=line, book=book, price=price,
        fair=0.5, ev=ev, link=f"{book}-u", sharp_over=-110, sharp_under=-110,
        fetch=FETCH, soft_last_update=FETCH, sharp_last_update=FETCH,
        dk_price=dk, dk_link="draftkings-u" if dk is not None else None,
        dk_player=player if dk is not None else None)


def test_publish_reads_under_the_lock_and_writes_once_in_one_transaction():
    """The ledger and the picks are read AFTER the lock, and the decision rows
    and the bets land in ONE commit: two overlapping writers (the 6am run, a
    refresh pass, the window job) can neither both decide a game nor leave a
    decision without its bets."""
    conn = _PublishConn(taken={"G_TAKEN"}, decided={"G_DONE"})
    rows = card.pick_rows([_bet("G_TAKEN", ev=0.09), _bet("G_DONE", ev=0.07),
                           _bet("G2", ev=0.05), _bet("G2", market="player_rebounds", line=7.5)],
                          bankroll=1000.0)
    decisions = [_decision("G_TAKEN", 1), _decision("G_DONE", 1), _decision("G2", 2),
                 _decision("G3", 0)]
    n, nd = card.publish(conn, rows, decisions)
    lock = next(i for i, s in enumerate(conn.sql) if "pg_advisory_xact_lock" in s)
    reads = [i for i, s in enumerate(conn.sql)
             if s.startswith("SELECT") and ("FROM picks" in s or "FROM nba_prop_market_decisions" in s)]
    writes = [i for i, s in enumerate(conn.sql) if s.startswith("INSERT")]
    assert reads and lock < min(reads), "the ledger and the picks must be read under the lock"
    assert conn.sql[-1] == "COMMIT" and conn.commits == 1 and max(writes) < len(conn.sql) - 1
    assert (n, nd) == (2, 2)
    assert sorted(conn.decisions) == ["G2", "G3"]                     # G3: decided, no bet
    assert [p["game_id"] for p in conn.inserted] == ["G2", "G2"]


def test_publish_skips_a_proposition_the_projection_model_already_holds():
    """nba_prop_projection decides a game alone when this card has not decided it 50 minutes
    out. A later decision here must not bet the same (game, player, market) a second time;
    the game's other propositions are still bet, and the game is still decided."""
    class _Held(_PublishConn):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "model_id = 'nba_prop_projection'" in " ".join(sql.split()):
                self._all = [(GID, "201939", "player_points")]
            return self

    conn = _Held()
    rows = card.pick_rows([_bet(), _bet(market="player_rebounds", line=7.5)], bankroll=1000.0)
    n, nd = card.publish(conn, rows, [_decision(GID, 2)])
    assert (n, nd) == (1, 1)
    assert [p["prop_market"] for p in conn.inserted] == ["player_rebounds"]


def test_publish_writes_bet_rows_once_with_its_own_column_list():
    assert "prop_market" in card._INSERT and "player_key" in card._INSERT
    assert "ON CONFLICT DO NOTHING" in card._INSERT
    conn = _PublishConn(taken={GID})
    assert card.publish(conn, card.pick_rows([_bet()], bankroll=1000.0), [_decision(GID, 1)]) == (0, 0)
    assert conn.inserted == [] and conn.decisions == []
    conn = _PublishConn(decided={GID})
    assert card.publish(conn, card.pick_rows([_bet()], bankroll=1000.0), [_decision(GID, 1)]) == (0, 0)
    assert conn.inserted == []


# ── the row ──────────────────────────────────────────────────────────────────

def test_a_bet_away_from_draftkings_with_dk_at_the_line():
    (r,) = card.pick_rows([_bet(book="fanduel", price=105.0, dk=100.0)], bankroll=1000.0)
    assert r["pick_label"] == "Stephen Curry Under 24.5 Pts"
    assert (r["pick_side"], r["signal_type"], r["confidence_tier"]) == ("under", "BET", "MED")
    assert r["dk_odds"] == 100.0 and r["dk_bet_link"] == "draftkings-u"
    assert r["dk_implied_prob"] == pytest.approx(0.5) and r["edge"] == pytest.approx(0.0)
    assert r["line_book"] is None
    assert (r["decision_book"], r["decision_odds"]) == ("fanduel", 105.0)
    assert r["decision_implied_prob"] == pytest.approx(round(100 / 205, 4))
    assert r["decision_edge"] == pytest.approx(round(0.5 - 100 / 205, 4))
    assert (r["best_book"], r["best_odds"], r["best_bet_link"]) == ("fanduel", 105.0, "fanduel-u")
    assert r["model_probability"] == r["model_probability_cal"] == 0.5
    assert r["player_id"] == "201939" and r["player_key"] == "Stephen Curry"
    assert r["prop_market"] == "player_points" and r["scored_line"] == 24.5
    assert r["kelly_fraction"] == 0.01 and r["recommended_bet"] == 10.0
    assert r["game_time"] == TIP.isoformat() and r["sport"] == "NBA"


def test_a_bet_where_draftkings_has_no_quote_at_the_line():
    (r,) = card.pick_rows([_bet(book="betmgm", price=110.0, dk=None)], bankroll=1000.0)
    assert r["dk_odds"] is None and r["dk_bet_link"] is None
    assert r["dk_implied_prob"] == 0.0 and r["edge"] == 0.0
    assert r["line_book"] == "betmgm"
    assert r["decision_odds"] == 110.0 and r["decision_book"] == "betmgm"


def test_a_bet_at_draftkings_carries_no_best_columns():
    (r,) = card.pick_rows([_bet(book="draftkings", price=100.0, dk=100.0)], bankroll=1000.0)
    assert r["best_book"] is None and r["best_odds"] is None and r["best_edge"] is None
    assert r["decision_book"] == "draftkings" and r["dk_odds"] == 100.0


@pytest.mark.parametrize("market,label", sorted(mk.MARKET_LABEL.items()))
def test_every_label_passes_the_publishing_check(market, label):
    from tracking.pick_integrity import pick_problems
    (r,) = card.pick_rows([_bet(market=market, line=3.5)], bankroll=1000.0)
    assert r["pick_label"] == f"Stephen Curry Under 3.5 {label}"
    assert pick_problems(r["pick_label"], r["pick_side"], r["scored_line"],
                         r["model_id"], prop_market=r["prop_market"]) == []


def test_the_markets_are_the_five_and_settle_as_the_settler_does():
    import tracking.paper_tracker as pt
    assert set(mk.MARKETS) == {"player_points", "player_rebounds", "player_assists",
                               "player_threes", "player_points_rebounds_assists"}
    for m in mk.MARKETS:
        assert pt._NBA_MARKET_STAT[m] == mk.MARKET_STAT[m]


# ── settlement ───────────────────────────────────────────────────────────────

PID = "201939"
BOX = {"player_id": PID, "player_name": "Stephen Curry", "game_id": GID, "team": "GSW",
       "minutes": 34.0, "points": 24, "rebounds": 5, "offensive_reb": 1,
       "defensive_reb": 4, "assists": 7, "steals": 1, "blocks": 0, "turnovers": 3,
       "fg_made": 9, "fg_att": 19, "fg3_made": 4, "fg3_att": 10, "ft_made": 2, "ft_att": 2}
OTHER = dict(BOX, player_id="2544", player_name="LeBron James", team="LAL")


class _SettleConn:
    def __init__(self, picks, log_rows):
        self.picks, self.log_rows, self.updates = picks, log_rows, []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        self._rows = []
        if s.upper().startswith("UPDATE"):
            self.updates.append((s, params))
            return self
        m = re.search(r"SELECT (.*?) FROM (\w+)", s, re.I)
        table = m.group(2) if m else ""
        if table == "picks":
            self._rows = self.picks
        elif table == "nba_player_game_log":
            cols = [c.strip().split()[-1].split(".")[-1] for c in m.group(1).split(",")]
            self._rows = [tuple(r.get(c) for c in cols) for r in self.log_rows]
        return self

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _settle(line, market, log_rows=(BOX, OTHER), price=-110):
    import tracking.paper_tracker as pt
    label = f"Stephen Curry Under {line:g} {mk.MARKET_LABEL[market]}"
    pick = ("pk1", GID, mk.MODEL_ID, "under", price, 10.0, line, PID, label, market,
            "Stephen Curry")
    conn = _SettleConn([pick], list(log_rows))
    pt._settle_prop_picks(conn, "2026-10-21", "2026-10-22T06:00:00Z")
    sql, params = [(s, p) for s, p in conn.updates if "SET result" in s][-1]
    return "NO_ACTION" if "'NO_ACTION'" in sql else params[0]


@pytest.mark.parametrize("line,expected", [(24.5, "WIN"), (23.5, "LOSS"), (24.0, "PUSH")])
def test_a_points_under_settles_from_the_box(line, expected):
    assert _settle(line, "player_points") == expected                 # 24 points


@pytest.mark.parametrize("line,expected", [(36.5, "WIN"), (35.5, "LOSS"), (36.0, "PUSH")])
def test_a_pra_under_settles_on_the_sum(line, expected):
    assert _settle(line, "player_points_rebounds_assists") == expected   # 24 + 5 + 7


def test_a_player_who_did_not_play_settles_no_action():
    """The game is logged (LeBron has a row), Curry has none: DNP, void."""
    assert _settle(24.5, "player_points", log_rows=(OTHER,)) == "NO_ACTION"


def test_settlement_routes_the_model_to_the_nba_box():
    import tracking.paper_tracker as pt
    assert pt._PROP_STAT_MAP[mk.MODEL_ID] == ("nba_player", "FROM_PROP_MARKET")
    assert pt._PROP_MARKET_STAT_BY_MODEL[mk.MODEL_ID] is pt._NBA_MARKET_STAT


# ── closing-line value ───────────────────────────────────────────────────────

def test_clv_reads_the_close_at_the_bet_book_by_the_name_in_the_label():
    import tracking.paper_tracker as pt
    assert pt._PROP_MARKET_FOR_MODEL[mk.MODEL_ID] == "FROM_PROP_MARKET"
    (r,) = card.pick_rows([_bet(book="fanduel", price=105.0, dk=100.0,
                                player="Steph Curry")], bankroll=1000.0)
    price, book = pt._bet_price_and_book(mk.MODEL_ID, r["dk_odds"], r["decision_odds"],
                                         r["decision_book"], r["pick_label"])
    assert (price, book) == (105.0, "fanduel")
    m = pt._PICK_LABEL_RE.match(r["pick_label"])
    assert m and m.group(1) == "Steph Curry"            # the BET book's own spelling

    seen = {}

    class _C:
        def execute(self, sql, params):
            seen["params"] = params
            return self

        def fetchone(self):
            return (-140, +115, 24.5)

    snap, close_book = pt._first_prop_close(_C(), GID, m.group(1), r["prop_market"],
                                            TIP.isoformat(), pick_book=book, pick_side="under")
    assert close_book == "fanduel" and snap["under_price"] == 115
    assert seen["params"][:4] == (GID, "Steph Curry", "player_points", "fanduel")


# ── registration ─────────────────────────────────────────────────────────────

def test_config_registers_a_rule_outside_the_training_registries():
    mid = mk.MODEL_ID
    assert config.ACTION_THRESHOLDS[mid] == {"min_prob": 0.0, "min_edge": 0.0}
    assert config.MODEL_EDGE_THRESHOLDS[mid] == 0.0
    assert config.MODEL_PROB_THRESHOLDS[mid] == 0.0
    assert config.MODEL_OWN_EV_FLOOR[mid] == 0.0
    assert config.SCORING_METHODS[mid] == "rule"
    assert mid not in config.MODELS and mid not in config.PROP_MODELS
    assert mid not in config.LIVE_MODELS and mid not in config.PAUSED_MODELS
    assert mid.startswith("nba_prop_") and "live" not in mid


def test_nba_left_the_pregame_poller_default():
    from pathlib import Path
    src = (Path(config.__file__)).read_text(encoding="utf-8")
    m = re.search(r'"PREGAME_POLL_SPORTS", "([^"]*)"', src)
    assert m and "NBA" not in m.group(1).split(",")


def test_the_nba_seasons_hold_out_2025_26():
    s = config.SPORTS["NBA"]
    assert s["test_season"] == 2026 and 2027 in s["seasons"]
    assert max(s["train_seasons"]) == 2025


def test_the_pipeline_runs_the_card_under_both_names():
    import run_pipeline as rp
    src = inspect.getsource(rp.step_nba_prop_scoring)
    assert "step_nba_prop_market" in src
    text = inspect.getsource(rp)
    choices = text.split("choices=[", 1)[1].split("]", 1)[0]
    for name in ('"nba-prop-market"', '"nba-prop-close"', '"nba-prop-scoring"'):
        assert name in choices
    assert '"nba-prop-market": lambda: step_nba_prop_market(' in text
    assert "run_nba_prop_scorer" not in text

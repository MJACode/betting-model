"""nba_prop_market: same-line unders against Pinnacle (models/nba_prop_market.py,
scripts/nba_prop_market_card.py).

Each test pins one property of the rule as it was graded
(docs/nba_models_2026.md 4.3) or of the card that writes it: the same line and
the same fetch, coherent two-way quotes, the EV floor on Pinnacle's own number,
unders only, the best bettable price with Pinnacle and Bovada never taken, the
45-70 minute window, one a game and four a night, insert-once under the lock,
name refusal, the row shape, settlement and the closing-line path.
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


def run(quotes, now=NOW, games=None, roster=ROSTER, taken=None, soft_books=None):
    return mk.find_bets(quotes, games or GAMES, roster, now, taken=taken,
                        soft_books=soft_books)


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
    (75, 0, "too_early"), (70, 1, "in_window"), (55, 1, "in_window"),
    (45, 1, "in_window"), (44, 0, "too_late"),
])
def test_only_45_to_70_minutes_before_tip(lead, bets_expected, key):
    now = TIP - timedelta(minutes=lead)
    snap = now.isoformat()                       # fetched by this pass
    bets, diag = run([q("pinnacle", -115, -105, snap=snap), q("fanduel", -125, +105, snap=snap)],
                     now=now)
    assert len(bets) == bets_expected and diag[key] == 1


def test_the_price_must_be_from_inside_the_window_too():
    """At tip-70 a fetch taken at tip-71 is a price from before the window."""
    now = TIP - timedelta(minutes=70)
    snap = (TIP - timedelta(minutes=71)).isoformat()
    bets, diag = run([q("pinnacle", -115, -105, snap=snap), q("fanduel", -125, +105, snap=snap)],
                     now=now)
    assert bets == [] and diag["stale_fetch"] == 1


def test_the_tip_is_the_earlier_of_the_schedule_and_the_feed():
    sched = "2026-10-21T23:00:00+00:00"
    feed = "2026-10-21T23:10:00+00:00"          # the odds feed's later start
    assert mk.tip_of(sched, feed) == mk.parse_ts(sched)
    assert mk.tip_of(None, feed) == mk.parse_ts(feed)


def test_the_slate_is_regular_season_games_inside_the_horizon():
    """The rule was graded on regular-season games only; the tip is the
    schedule's when the feed's is later; a game past its tip is not priced."""
    class _C:
        def execute(self, sql, params):
            self.params = params
            return self

        def fetchall(self):
            t = lambda m: (TIP + timedelta(minutes=m)).isoformat()      # noqa: E731
            return [
                ("REG", "LAL", "GSW", "2026-10-21", 2027, t(10), t(0), "regular"),
                ("CUP", "LAL", "GSW", "2026-10-21", 2027, t(0), t(0), "cup_final"),
                ("NOSCHED", "LAL", "GSW", "2026-10-21", 2027, t(0), None, None),
                ("LATER", "LAL", "GSW", "2026-10-21", 2027, t(30), t(30), "regular"),
                ("STARTED", "LAL", "GSW", "2026-10-21", 2027, t(-60), t(-60), "regular"),
            ]

    skipped = []
    games = card.slate(_C(), NOW, skipped)
    assert sorted(games) == ["REG"] and games["REG"]["tip"] == TIP
    assert sorted(s.split()[0] for s in skipped) == ["CUP", "NOSCHED"]


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
    decide it (a fetch older than tip-70 cannot), in one statement."""
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
    assert seen["params"][3] == (TIP - timedelta(minutes=75)).isoformat()
    assert "snapshot_type = 'open'" in seen["sql"] and "snapshot_at >= %s" in seen["sql"]
    assert out[0]["line"] == 24.5 and isinstance(out[0]["under_price"], float)


def test_a_game_already_bet_is_never_decided_again():
    bets, diag = run([q("pinnacle", -115, -105), q("fanduel", -125, +105)], taken={GID})
    assert bets == [] and diag["already_bet"] == 1


def test_a_missed_window_is_counted():
    now = TIP - timedelta(minutes=40)
    early = (TIP - timedelta(minutes=100)).isoformat()      # nothing fetched 45-70 before tip
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


# ── one a game, four a night ─────────────────────────────────────────────────

def test_one_bet_a_game_the_best_ev():
    quotes = [q("pinnacle", -115, -105), q("fanduel", -125, +105),
              q("pinnacle", -110, -110, player="LeBron James", market="player_rebounds", line=7.5),
              q("fanduel", -140, +120, player="LeBron James", market="player_rebounds", line=7.5)]
    bets, diag = run(quotes)
    assert len(bets) == 1 and diag["qualifying"] == 2
    assert (bets[0].player, bets[0].market) == ("LeBron James", "player_rebounds")


def _row(gid, ev, date="2026-10-21", tip="2026-10-22T00:00:00+00:00", pid="1"):
    return {"game_id": gid, "_ev": ev, "game_date": date, "_tip": tip, "player_id": pid}


def test_four_a_night_counting_bets_already_written():
    rows = [_row(f"G{i}", ev) for i, ev in enumerate([0.01, 0.05, 0.03, 0.02, 0.04, 0.06])]
    kept = card.per_night(rows, {"2026-10-21": 1})
    assert [r["game_id"] for r in kept] == ["G5", "G1", "G4"]           # best EV, 3 left
    assert card.per_night(rows, {"2026-10-21": 4}) == []
    assert len(card.per_night(rows)) == mk.MAX_BETS_PER_NIGHT == 4
    assert mk.MAX_BETS_PER_GAME == 1
    # another night has its own four
    other = [_row("H1", 0.01, date="2026-10-22")]
    assert [r["game_id"] for r in card.per_night(rows + other, {"2026-10-21": 4})] == ["H1"]


def test_the_night_fills_in_tip_order_like_the_backtest():
    """The four-a-night result (1,862 bets, +5.05%) took the first four games of
    the night BY TIP. A pass that sees two games in its window must give the last
    slot to the earlier tip even when the later one has the better EV."""
    early = _row("EARLY", 0.01, tip="2026-10-21T23:00:00+00:00")
    late = _row("LATE", 0.09, tip="2026-10-21T23:20:00+00:00")
    assert [r["game_id"] for r in card.per_night([late, early], {"2026-10-21": 3})] == ["EARLY"]
    # same tip: the better EV first
    a, b = _row("A", 0.02), _row("B", 0.05)
    assert [r["game_id"] for r in card.per_night([a, b], {"2026-10-21": 3})] == ["B"]


def test_one_a_game_drops_a_game_already_bet():
    rows = [_row("G1", 0.05, pid="1"), _row("G1", 0.02, pid="2"), _row("G2", 0.03)]
    assert [(r["game_id"], r["player_id"]) for r in card.one_per_game(rows)] == [("G1", "1"), ("G2", "1")]
    assert [r["game_id"] for r in card.one_per_game(rows, taken={"G1"})] == ["G2"]


# ── insert once, under the lock ──────────────────────────────────────────────

class _PublishConn:
    def __init__(self, taken=(), written=None):
        self.taken, self.written = set(taken), dict(written or {})
        self.sql, self.inserted, self.commits = [], [], 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        self.sql.append(s)
        self._one, self._all = None, []
        if "SELECT DISTINCT game_id FROM picks" in s:
            self._all = [(g,) for g in params[1] if g in self.taken]
        elif "SELECT game_date, count(*) FROM picks" in s:
            self._all = list(self.written.items())
        elif s.startswith("INSERT INTO picks"):
            self.inserted.append(params)
            self._one = (len(self.inserted),)
        return self

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all

    def commit(self):
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


def test_publish_takes_the_lock_before_reading_and_counts_inside_it():
    conn = _PublishConn(taken={"G_TAKEN"}, written={"2026-10-21": 3})
    rows = card.pick_rows([_bet("G_TAKEN", ev=0.09), _bet("G2", ev=0.05),
                           _bet("G3", ev=0.04)], bankroll=1000.0)
    n = card.publish(conn, rows)
    lock = next(i for i, s in enumerate(conn.sql) if "pg_advisory_xact_lock" in s)
    reads = [i for i, s in enumerate(conn.sql) if "FROM picks" in s]
    assert reads and lock < min(reads), "the caps must be counted under the lock"
    assert n == 1 and [p["game_id"] for p in conn.inserted] == ["G2"]   # one left that night
    assert conn.commits == 1


def test_publish_writes_bet_rows_once_with_its_own_column_list():
    assert "prop_market" in card._INSERT and "player_key" in card._INSERT
    assert "ON CONFLICT DO NOTHING" in card._INSERT
    conn = _PublishConn(taken={GID})
    assert card.publish(conn, card.pick_rows([_bet()], bankroll=1000.0)) == 0
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

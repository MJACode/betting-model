"""No pre-game pick is decided on a price the book stopped offering.

THE FINDING (2026-10-09). The odds feed stopped listing 31 NCAAF games between
2026-09-05 and 2026-09-07, and nothing was stored for them after that. The
scorer kept pricing them off the last row it had: the price read took "the
newest pre-game row" with no lower time limit, and the NCAAF entry check asked
"did DraftKings EVER price this game?". 16 NCAAF BETs were written at
DraftKings prices 2 to 28 days old, 15 of them posted. The same gap let two
NHL moneyline BETs fire on 2026-09-30 at prices 83 hours old, while the odds
step failed on every pass from 09-27 to 10-01 ("Invalid ODDS_API_KEY") and the
scoring step kept reporting success.

THE RULE. A game that has not started may only be decided on a price stored
within config.PREGAME_PRICE_MAX_AGE_MIN (180 minutes) of now. Once the game
has started, the last pre-game row is the close and its age does not matter,
so the in-play models' pre-game line and every historical replay read exactly
what they read before.

Every test here was run against the code before the change and failed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import config
import models.nhl_totals_market as mk
import models.scorer as scorer
import scripts.nhl_totals_card as card

NOW = datetime(2026, 10, 9, 16, 30, 0, tzinfo=timezone.utc)
FUTURE_CUTOFF = "2026-10-17T23:30:00"           # BYU v Notre Dame kickoff
STALE_SNAP = "2026-09-05T23:59:48Z"             # its last stored DraftKings row
FRESH_SNAP = "2026-10-09T16:20:00Z"             # ten minutes before NOW


@pytest.fixture
def _clock(monkeypatch):
    # raising=False so the test can run (and fail on its assertion) against
    # code that has no clock seam yet.
    monkeypatch.setattr(scorer, "_utcnow", lambda: NOW, raising=False)


def _totals_row(snap, line=54.5, over=-108, under=-112):
    # the 13 columns _latest_book_game_odds selects, snapshot_at last
    return (None, None, None, None, line, over, under,
            None, None, None, "over-link", "under-link", snap)


class _OddsConn:
    """One canned row per bookmaker for the newest-row read; the game's
    first-pitch / kickoff for the cutoff read."""

    def __init__(self, rows: dict, commence: str):
        self.rows = rows
        self.commence = commence
        self._last = ("", ())

    def execute(self, sql, params=None):
        self._last = (" ".join(sql.split()), tuple(params or ()))
        return self

    def fetchone(self):
        sql, params = self._last
        if "FROM games" in sql:
            return (self.commence,)
        if "FROM odds" not in sql:
            return None
        return self.rows.get(params[2]) if len(params) > 2 else None

    def fetchall(self):
        return []


# ── the bound itself ─────────────────────────────────────────────────────────

def test_the_bound_is_three_hours_and_one_constant():
    assert config.PREGAME_PRICE_MAX_AGE_MIN == 180


# ── the read every game model decides through ────────────────────────────────

def test_a_month_old_price_on_an_unstarted_game_is_no_price(_clock):
    """BYU v Notre Dame, pick 3204788: Under 54.5 -112 written 2026-10-04 off
    DraftKings' 2026-09-05 row, for a 10-17 kickoff."""
    conn = _OddsConn({"draftkings": _totals_row(STALE_SNAP)},
                     "2026-10-17T23:30:00+00:00")
    assert scorer._latest_book_game_odds(
        conn, "NCAAF_2026-10-17_notre-dame_byu", "totals", "draftkings",
        FUTURE_CUTOFF) is None
    assert scorer._get_dk_odds(
        conn, "NCAAF_2026-10-17_notre-dame_byu", "totals") is None
    assert scorer._get_scoring_odds(
        conn, "NCAAF_2026-10-17_notre-dame_byu", "totals") is None


def test_a_price_stored_this_pass_still_decides(_clock):
    conn = _OddsConn({"draftkings": _totals_row(FRESH_SNAP, line=48.5)},
                     "2026-10-17T23:30:00+00:00")
    odds = scorer._get_dk_odds(conn, "NCAAF_2026-10-17_notre-dame_byu", "totals")
    assert odds is not None and odds["total_line"] == 48.5


def test_just_inside_and_just_outside_the_bound(_clock):
    inside = (NOW - timedelta(minutes=179)).strftime("%Y-%m-%dT%H:%M:%SZ")
    outside = (NOW - timedelta(minutes=181)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for snap, kept in ((inside, True), (outside, False)):
        conn = _OddsConn({"draftkings": _totals_row(snap)},
                         "2026-10-17T23:30:00+00:00")
        got = scorer._get_dk_odds(conn, "NCAAF_2026-10-17_notre-dame_byu", "totals")
        assert (got is not None) is kept, snap


def test_a_started_game_reads_its_last_pre_game_row_whatever_its_age(_clock):
    """The in-play models read the pre-game line after kickoff
    (live_scorer._pregame_features), and the replay scripts read completed
    games. Neither is a pre-game decision, so neither is bounded."""
    conn = _OddsConn({"draftkings": _totals_row(STALE_SNAP)},
                     "2026-10-09T16:00:00+00:00")          # started 30 min ago
    odds = scorer._get_dk_odds(conn, "NCAAF_2026-10-09_x_y", "totals")
    assert odds is not None and odds["snapshot_at"] == STALE_SNAP


def test_the_feature_row_and_the_opener_read_the_same_bounded_price(_clock):
    """The opener rule's "still gettable" check compared DraftKings' current
    spread with its opening spread, which a row frozen since September passes
    by construction. It now has no current spread to compare."""
    spread = (-110, -110, None, -3.5, None, None, None,
              None, None, None, None, None, STALE_SNAP)
    conn = _OddsConn({"draftkings": spread}, "2026-10-17T23:30:00+00:00")
    out = scorer._opener_rule(conn, "NCAAF_2026-10-17_notre-dame_byu",
                              "ncaaf_spread_premium", "spreads", {})
    assert out == (None, None, None)


# ── the best-price shop ──────────────────────────────────────────────────────

class _ShopConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        return self

    def fetchall(self):
        return self.rows


def test_no_book_qualifies_a_pick_on_a_stale_quote(_clock, monkeypatch):
    """_fresh_quotes only compared books with each other, so when every book
    froze together nothing was dropped."""
    monkeypatch.setattr(scorer, "BEST_LINE_BOOKMAKERS",
                        ["draftkings", "fanduel", "betmgm"])
    rows = [("fanduel", -105, "fd", 54.5, None, STALE_SNAP),
            ("draftkings", -112, "dk", 54.5, None, STALE_SNAP)]
    best = scorer._best_game_price_one(
        _ShopConn(rows), "NCAAF_2026-10-17_notre-dame_byu", "totals",
        "under", 54.5, FUTURE_CUTOFF)
    assert best is None

    fresh = [("fanduel", -105, "fd", 54.5, None, FRESH_SNAP)] + rows[1:]
    best = scorer._best_game_price_one(
        _ShopConn(fresh), "NCAAF_2026-10-17_notre-dame_byu", "totals",
        "under", 54.5, FUTURE_CUTOFF)
    assert best["book"] == "fanduel"


# ── which games are scored at all ────────────────────────────────────────────

class _BoardConn:
    """Enough of Postgres for run_scorer's game query and both price
    pre-filters. `dk_newest` is each game's newest stored DraftKings
    snapshot_at; a pre-filter that passes a 'YYYY-MM-DDTHH:MM:SS' floor only
    admits games whose newest row is at or after it."""

    def __init__(self, games, dk_newest):
        self.games = games
        self.dk_newest = dk_newest
        self._last = ("", ())

    def execute(self, sql, params=None):
        self._last = (" ".join(sql.split()), tuple(params or ()))
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        sql, params = self._last
        if "EXISTS" in sql and "FROM odds o" in sql:
            floor = next((p for p in params if isinstance(p, str)
                          and len(p) >= 19 and p[10] == "T"), None)
            if "g.sport = 'NCAAF'" in sql:
                pool = [g[0] for g in self.games if g[1] == "NCAAF"]
            else:
                pool = list(params[0])
            return [(gid,) for gid in pool if gid in self.dk_newest
                    and (floor is None or self.dk_newest[gid][:19] >= floor[:19])]
        if "home_team" in sql and "FROM games" in sql:
            return self.games
        return []

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_a_game_the_feed_dropped_is_not_scored(_clock, monkeypatch):
    far = "2099-01-01T00:00:00Z"          # never started, whenever this runs
    games = [
        ("NCAAF_2099-01-01_fresh_a", "NCAAF", 2099, "2099-01-01", "A", "F", far),
        ("NCAAF_2099-01-01_stale_b", "NCAAF", 2099, "2099-01-01", "B", "S", far),
        ("NHL_2099-01-01_NEW_OLD", "NHL", 2099, "2099-01-01", "OLD", "NEW", far),
        ("NHL_2099-01-01_LIV_ON", "NHL", 2099, "2099-01-01", "ON", "LIV", far),
    ]
    conn = _BoardConn(games, {
        "NCAAF_2099-01-01_fresh_a": FRESH_SNAP,
        "NCAAF_2099-01-01_stale_b": STALE_SNAP,
        "NHL_2099-01-01_NEW_OLD": "2026-09-26T22:59:42Z",   # the outage case
        "NHL_2099-01-01_LIV_ON": FRESH_SNAP,
    })
    monkeypatch.setattr(scorer, "get_connection", lambda: conn)
    monkeypatch.setattr(scorer, "_get_postponed_games", lambda _d: set())
    asked: list[str] = []
    monkeypatch.setattr(scorer, "_get_dk_odds",
                        lambda c, gid, m: asked.append(gid) or None)
    import features.ncaaf_feature_engine as nfe
    monkeypatch.setattr(nfe, "build_ncaaf_game_features", lambda *a, **k: {})
    monkeypatch.setattr(scorer, "build_nhl_game_features", lambda *a, **k: {})

    scorer.run_scorer("2098-12-31", dry_run=True)

    assert "NCAAF_2099-01-01_fresh_a" in asked
    assert "NHL_2099-01-01_LIV_ON" in asked
    assert "NCAAF_2099-01-01_stale_b" not in asked, (
        "the NCAAF entry check admitted a game DraftKings last priced a month ago")
    assert "NHL_2099-01-01_NEW_OLD" not in asked, (
        "the look-ahead entry check admitted a game with an 83-hour-old price")


# ── the NHL totals card, which reads its own fetch ───────────────────────────

T1 = "2026-10-07 21:00:07.200000+00"
FETCH = datetime(2026, 10, 7, 21, 0, 7, tzinfo=timezone.utc)


def _q(book, line, over, under):
    return {"game_id": "NHL_2026-10-08_PHI_OTT", "book": book,
            "created_at": T1, "snapshot_at": "2026-10-07T21:00:07Z",
            "total_line": line, "over_price": over, "under_price": under,
            "over_link": f"https://{book}/over",
            "under_link": f"https://{book}/under"}


QUOTES = [_q("pinnacle", 6.0, 104, -119), _q("betmgm", 6.0, -115, -105)]


def test_the_nhl_totals_card_will_not_bet_a_fetch_hours_old():
    bets, diag = mk.find_bets(QUOTES, now=FETCH + timedelta(minutes=10))
    assert len(bets) == 1

    bets, diag = mk.find_bets(QUOTES, now=FETCH + timedelta(hours=5))
    assert bets == []
    assert diag["stale_fetch"] == 1


def test_the_card_passes_its_clock_to_the_rule(monkeypatch):
    class _C:
        def close(self):
            pass
    monkeypatch.setattr(card, "get_connection", lambda: _C())
    monkeypatch.setattr(card, "slate", lambda conn, now: {
        "NHL_2026-10-08_PHI_OTT": {"home": "OTT", "away": "PHI",
                                   "game_date": "2026-10-08",
                                   "commence_time": "2026-10-08T23:13:54Z"}})
    monkeypatch.setattr(mk, "load_fetch_quotes", lambda conn, games: QUOTES)
    out = card.run_card(do_publish=False, now=FETCH + timedelta(hours=5))
    assert out["bets"] == 0
    out = card.run_card(do_publish=False, now=FETCH + timedelta(minutes=10))
    assert out["bets"] == 1


# ── a UFC fight stored under two ids ─────────────────────────────────────────
#
# The feed builds a UFC id from its home fighter, and that assignment flips
# between fetches, so one fight can sit under both orientations. Measured
# 2026-10-09: UFC_2026-10-10_rj-harris_allen-frye-jr has DraftKings rows up to
# 2026-10-08 18:17Z and nothing since; its swapped id has fresh rows. Once the
# abandoned id's own row counts as no price, the read must NOT fall through to
# the swapped id's fresh price, or both ids decide (and grade) the same fight.

ABANDONED = "UFC_2026-10-10_rj-harris_allen-frye-jr"     # away rj-harris
CURRENT = "UFC_2026-10-10_allen-frye-jr_rj-harris"       # away allen-frye-jr
UFC_CUTOFF = "2026-10-10T23:00:00"
ABANDONED_SNAP = "2026-10-08T18:17:06Z"                  # its last DK row
CURRENT_SNAP = "2026-10-09T16:16:31Z"


def _h2h_row(snap, home, away):
    return (home, away, None, None, None, None, None,
            "home-link", "away-link", None, None, None, snap)


class _TwoIdConn:
    """Both orientations of one fight. `newest` answers the newest-row read
    per (game_id, bookmaker); `shop` answers the best-price read per game_id."""

    def __init__(self, newest: dict, shop: dict):
        self.newest = newest
        self.shop = shop
        self._last = ("", ())

    def execute(self, sql, params=None):
        self._last = (" ".join(sql.split()), tuple(params or ()))
        return self

    def fetchone(self):
        sql, params = self._last
        if "FROM games" in sql:
            return ("2026-10-10T23:00:00+00:00",)
        if "FROM odds" in sql:
            return self.newest.get((params[0], params[2]))
        return None

    def fetchall(self):
        sql, params = self._last
        if "FROM odds" in sql:
            return self.shop.get(params[0], [])
        return []


# On CURRENT, rj-harris is home: +125 rj-harris, -150 allen-frye-jr.
_CURRENT_DK = _h2h_row(CURRENT_SNAP, home=125, away=-150)


def test_the_abandoned_copy_of_a_fight_does_not_borrow_the_live_copys_price(_clock):
    conn = _TwoIdConn(
        newest={(ABANDONED, "draftkings"): _h2h_row(ABANDONED_SNAP, -140, 118),
                (CURRENT, "draftkings"): _CURRENT_DK},
        shop={})
    assert scorer._get_dk_odds(conn, ABANDONED, "h2h") is None, (
        "the abandoned id was handed the other id's fresh price, so both ids "
        "would decide the same fight")
    # The live copy itself is untouched.
    assert scorer._get_dk_odds(conn, CURRENT, "h2h")["home_price"] == 125


def test_a_copy_that_was_never_priced_still_reads_the_other_orientation(_clock):
    """The 2026-08-29 case the fallback exists for: one id has no DraftKings
    row for the market at all, so the swapped id's row is its price."""
    conn = _TwoIdConn(newest={(CURRENT, "draftkings"): _CURRENT_DK}, shop={})
    odds = scorer._get_dk_odds(conn, ABANDONED, "h2h")
    assert odds is not None
    # swapped into THIS id's orientation: allen-frye-jr is home here
    assert (odds["home_price"], odds["away_price"]) == (-150, 125)


def test_the_best_price_shop_follows_the_same_rule(_clock, monkeypatch):
    monkeypatch.setattr(scorer, "BEST_LINE_BOOKMAKERS", ["draftkings", "fanduel"])
    current_shop = [("fanduel", 130, "fd", None, None, CURRENT_SNAP),
                    ("draftkings", 125, "dk", None, None, CURRENT_SNAP)]
    stale_shop = [("fanduel", 120, "fd-old", None, None, ABANDONED_SNAP),
                  ("draftkings", 118, "dk-old", None, None, ABANDONED_SNAP)]

    # Abandoned id: its own quotes are stale, so it gets no price at all.
    conn = _TwoIdConn(
        newest={(ABANDONED, "draftkings"): _h2h_row(ABANDONED_SNAP, -140, 118),
                (CURRENT, "draftkings"): _CURRENT_DK},
        shop={ABANDONED: stale_shop, CURRENT: current_shop})
    assert scorer._best_game_price(conn, ABANDONED, "h2h", "away", None,
                                   UFC_CUTOFF) is None

    # Never-priced id: shops the other orientation, on the swapped side.
    conn = _TwoIdConn(newest={(CURRENT, "draftkings"): _CURRENT_DK},
                      shop={CURRENT: current_shop})
    best = scorer._best_game_price(conn, ABANDONED, "h2h", "away", None,
                                   UFC_CUTOFF)
    assert best is not None and best["book"] == "fanduel" and best["odds"] == 130

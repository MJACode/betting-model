"""data/ingestors/ncaaf_derivative_history: what the NCAAF first-half and
team-total purchase asks for, stores and never pays for twice.

mike approved it on 2026-11-10 ("Buy all") after the market audit found those
markets hold no stored prices (docs/ncaaf_market_audit.md, section 7). These
pin what decides the spend (which games at which read, the ledger, the ceiling
and the floor), what is stored (the game id that holds the full-game prices,
the market names, the source, our home team's number) and the worker job.
No test here sends a request anywhere: the feed is a function, the database a
stand-in with real transactions.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

import pytest

import tracking.job_queue as jq
from data import prune_odds
from data.db import ConnectionLost, _adapt_sql
from data.ingestors import ncaab_odds_history as ncaab
from data.ingestors import ncaaf_derivative_history as h
from tests.test_ddl_guard import GuardConn
from tests.test_ncaab_odds_history import FakeMeter, Resp
from tests.test_ncaab_paid_calls import Feed


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@pytest.fixture(autouse=True)
def _no_db_school_lookup(monkeypatch):
    """The NCAAF name resolution reads the ncaaf_teams registry from the
    database; here it strips the mascot itself, and one name goes through a
    map the way config.NCAAF_ODDS_API_MAP sends 'Southern Mississippi'."""
    names = {"Southern Mississippi Golden Eagles": "Southern Miss"}
    monkeypatch.setattr(h, "_normalize_team",
                        lambda name, sport: names.get(name) or name.rsplit(" ", 1)[0])


# ── a small world ────────────────────────────────────────────────────────────
# Saturday 2025-08-30 (Eastern Daylight Time, UTC-4). The am read is 14:00Z
# that day; the pm read is 23:00Z on Friday 08-29.

AM, PM = _t("2025-08-30T14:00:00Z"), _t("2025-08-29T23:00:00Z")


def _game(gid, home, away, kick, *, day=None, season=2025, score=None):
    return {"game_id": gid, "season": season, "game_date": day or gid.split("_")[1],
            "home_team": home, "away_team": away, "commence_time": kick,
            "home_score": score, "away_score": None if score is None else score - 3}


# noon Eastern, one row, scored
NOON = _game("NCAAF_2025-08-30_texas_ohio-state", "Ohio State", "Texas",
             "2025-08-30T16:00:00Z", score=14)
# 9pm Eastern, stored twice: the odds feed's Eastern-dated row holds the
# prices, CFBD's UTC-dated row holds the score
NIGHT = _game("NCAAF_2025-08-30_lsu_clemson", "Clemson", "LSU", "2025-08-31T01:00:00Z")
NIGHT_CFBD = _game("NCAAF_2025-08-31_lsu_clemson", "Clemson", "LSU", "2025-08-31T01:00:00Z",
                   score=10)
# no book priced it: no stored pull at all
UNPRICED = _game("NCAAF_2025-08-30_idaho-state_unlv", "UNLV", "Idaho State",
                 "2025-08-30T20:00:00Z", score=38)
# 9:30am Eastern (13:30Z): under way at the am read, still ahead at the pm read
EARLY = _game("NCAAF_2025-08-30_iowa-state_kansas-state", "Kansas State", "Iowa State",
              "2025-08-30T13:30:00Z", score=21)
# a name the registry cannot bridge
MAPPED = _game("NCAAF_2025-08-30_southern-miss_mississippi-state", "Mississippi State",
               "Southern Miss", "2025-08-30T16:00:00Z", score=34)
GAMES = [NOON, NIGHT, NIGHT_CFBD, UNPRICED, EARLY, MAPPED]
PULLS = {
    NOON["game_id"]: {AM: 20, PM: 18},
    NIGHT["game_id"]: {AM: 20, PM: 20},
    EARLY["game_id"]: {AM: 6, PM: 20},
    MAPPED["game_id"]: {AM: 20},
}


def _ids(plan):
    return [p.game_id for p in plan]


def _plan(read, games=GAMES, pulls=PULLS):
    return h.plan_read(games, pulls, read)


# ── the two reads ────────────────────────────────────────────────────────────

def test_each_read_asks_for_the_instant_the_full_game_pull_was_asked_for():
    """am is 14:00 UTC on the game's Eastern date, pm 23:00 UTC on the Eastern
    date before: the two times the stored full-game history was asked for."""
    d = date(2025, 8, 30)
    assert h.read_instant(d, "am") == AM and h.read_instant(d, "pm") == PM
    assert h.read_instant(date(2026, 1, 1), "pm") == _t("2025-12-31T23:00:00Z")
    with pytest.raises(ValueError):
        h.read_instant(d, "noon")


def test_the_eastern_date_is_the_kickoff_s_not_the_utc_day():
    """A 9pm Eastern kickoff is the next day in UTC; its reads belong to the
    Eastern date. With no stored kickoff the row's own date is used."""
    assert h._eastern_date(_t("2025-08-31T01:00:00Z"), "2025-08-31") == date(2025, 8, 30)
    assert h._eastern_date(None, "2025-08-30") == date(2025, 8, 30)


# ── the plan ─────────────────────────────────────────────────────────────────

def test_a_read_buys_each_game_that_holds_its_pull_and_kicks_off_later():
    am, why_am = _plan("am")
    assert _ids(am) == [NIGHT["game_id"], MAPPED["game_id"], NOON["game_id"]]
    assert {p.instant for p in am} == {AM} and {p.eastern_date for p in am} == {"2025-08-30"}
    pm, why_pm = _plan("pm")
    assert _ids(pm) == [EARLY["game_id"], NIGHT["game_id"], NOON["game_id"]]
    assert {p.instant for p in pm} == {PM}
    # the unpriced game and (at pm) the one with no evening pull hold nothing
    assert why_am["no_stored_pull"] == 1 and why_pm["no_stored_pull"] == 2


def test_a_night_game_stored_twice_is_bought_once_under_the_id_that_holds_the_prices():
    am, why = _plan("am")
    night = [p for p in am if "lsu_clemson" in p.game_id]
    assert [p.game_id for p in night] == [NIGHT["game_id"]]      # never the CFBD row's id
    assert night[0].scored is True                                # the score is its twin's
    assert night[0].kick == _t("2025-08-31T01:00:00Z") and night[0].pull_rows == 20
    assert why["twin_ids_not_bought"] == 0


def test_two_ids_of_one_game_that_both_hold_the_pull_are_bought_once_under_the_fuller():
    pulls = {**PULLS, NIGHT_CFBD["game_id"]: {AM: 4}}
    am, why = _plan("am", pulls=pulls)
    assert [p.game_id for p in am if "lsu_clemson" in p.game_id] == [NIGHT["game_id"]]
    assert why["twin_ids_not_bought"] == 1
    # the other way round: the fuller one wins whichever row it is
    pulls = {**PULLS, NIGHT_CFBD["game_id"]: {AM: 40}}
    am, _ = _plan("am", pulls=pulls)
    assert [p.game_id for p in am if "lsu_clemson" in p.game_id] == [NIGHT_CFBD["game_id"]]


def test_a_game_with_no_stored_pull_at_the_read_is_not_bought():
    am, _ = _plan("am")
    pm, _ = _plan("pm")
    assert UNPRICED["game_id"] not in _ids(am) + _ids(pm)
    assert MAPPED["game_id"] in _ids(am) and MAPPED["game_id"] not in _ids(pm)
    # a pull an hour either side of the instant is not this read's pull
    off = {NOON["game_id"]: {AM - timedelta(hours=1): 20, AM + timedelta(hours=1): 20}}
    assert _plan("am", games=[NOON], pulls=off)[0] == []


def test_a_game_that_kicks_off_before_the_instant_is_not_bought():
    am, why = _plan("am")
    assert EARLY["game_id"] not in _ids(am) and why["kicks_off_before_read"] == 1
    assert EARLY["game_id"] in _ids(_plan("pm")[0])


@pytest.mark.parametrize("kick,bought", [
    ("2025-08-30T14:05:00Z", False),      # five minutes after: not more than five
    ("2025-08-30T14:05:01Z", True),
    ("2025-08-30T14:00:00Z", False),
    ("2025-08-30T13:59:00Z", False),
])
def test_a_game_must_kick_off_more_than_five_minutes_after_the_instant(kick, bought):
    g = _game("NCAAF_2025-08-30_a_b", "B", "A", kick)
    plan, _ = h.plan_read([g], {g["game_id"]: {AM: 9}}, "am")
    assert bool(plan) is bought


def test_a_rematch_weeks_later_is_its_own_game_and_a_row_a_day_away_is_the_same_one():
    first = _game("NCAAF_2025-09-06_lsu_clemson", "Clemson", "LSU", "2025-09-06T16:00:00Z")
    again = _game("NCAAF_2025-12-06_lsu_clemson", "Clemson", "LSU", "2025-12-06T21:00:00Z")
    flipped_twin = _game("NCAAF_2025-12-07_clemson_lsu", "LSU", "Clemson", None)
    groups = h.real_games([again, first, flipped_twin])
    assert [[g["game_id"] for g in grp] for grp in groups] == [
        [first["game_id"]], [again["game_id"], flipped_twin["game_id"]]]


def test_a_row_with_no_kickoff_is_planned_by_its_own_date_and_checked_when_bought():
    g = _game("NCAAF_2025-08-30_a_b", "B", "A", None)
    (p,), _ = h.plan_read([g], {g["game_id"]: {AM: 9}}, "am")
    assert p.kick is None and p.instant == AM and p.eastern_date == "2025-08-30"


def test_the_plan_runs_newest_date_first():
    older = _game("NCAAF_2024-09-07_x_y", "Y", "X", "2024-09-07T16:00:00Z", season=2024)
    pulls = {**PULLS, older["game_id"]: {_t("2024-09-07T14:00:00Z"): 5}}
    am, _ = _plan("am", games=[older] + GAMES, pulls=pulls)
    assert _ids(am)[-1] == older["game_id"]
    assert [p.instant for p in am] == sorted((p.instant for p in am), reverse=True)


# ── the stored pulls ─────────────────────────────────────────────────────────

class Db:
    """A stand-in database: `odds` and the ledger with real transactions (a
    write lands at commit and a rollback drops it), other SELECTs answered
    from `answers` by substring. Every statement is recorded."""

    def __init__(self, ledger=None, answers=None):
        self.odds: list[dict] = []
        self.ledger: dict[tuple, dict] = dict(ledger or {})
        self.answers = answers or {}
        self.sql: list[tuple[str, object]] = []
        self.commits = 0
        self._odds_tx: list[dict] = []
        self._ledger_tx: dict[tuple, dict] = {}
        self._rows: list = []

    def execute(self, sql, params=None):
        q = " ".join(sql.split())
        self.sql.append((q, params))
        self._rows = []
        if q.startswith("INSERT INTO ncaaf_derivative_fetches"):
            gid, read, asked, served, event_id, credits, rows, status = params
            now = self._ledger_tx.get((gid, read)) or self.ledger.get((gid, read))
            if now is None or now["status"] not in ("stored", "empty"):   # the upsert's WHERE
                self._ledger_tx[(gid, read)] = {
                    "requested_at": asked, "served_at": served, "event_id": event_id,
                    "credits": credits, "rows_stored": rows, "status": status}
        elif q.startswith("SELECT game_id FROM ncaaf_derivative_fetches"):
            read, statuses, ids = params
            view = {**self.ledger, **self._ledger_tx}
            self._rows = [(g,) for g in ids if view.get((g, read), {}).get("status") in statuses]
        else:
            for needle, ans in self.answers.items():
                if needle in q:
                    if isinstance(ans, Exception):
                        raise ans
                    self._rows = list(ans)
        return self

    def executemany(self, sql, rows):
        q = " ".join(sql.split())
        self.sql.append((q, None))
        if q.startswith("INSERT INTO odds"):
            self._odds_tx.extend(dict(r) for r in rows)

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def commit(self):
        self.odds.extend(self._odds_tx)
        self.ledger.update(self._ledger_tx)
        self._odds_tx, self._ledger_tx = [], {}
        self.commits += 1

    def rollback(self):
        self._odds_tx, self._ledger_tx = [], {}

    def close(self):
        pass

    def writes(self):
        return [q for q, _ in self.sql if q.split()[0] in ("INSERT", "UPDATE", "DELETE", "CREATE",
                                                           "ALTER", "REVOKE")]


def test_the_pull_read_asks_for_the_historical_source_by_game_id_and_parses_each_stamp():
    conn = Db(answers={"FROM odds": [
        ("g1", "2025-08-30T14:00:00+00:00", 20),         # as text
        ("g1", _t("2025-08-29T23:00:00Z"), 18),          # as the driver returns it
        ("g2", "2025-08-30 14:00:00+00", 3),
        ("g2", None, 9),                                 # unreadable: dropped, not guessed
    ]})
    got = h.stored_pulls(conn, ["g1", "g2"])
    assert got == {"g1": {AM: 20, PM: 18}, "g2": {AM: 3}}
    (q, params), = conn.sql
    assert params == (["g1", "g2"], "odds_api_historical")
    assert "game_id = ANY(%s) AND source = %s" in q


def test_the_pull_read_casts_the_text_stamp_before_bucketing_it():
    """odds.snapshot_at is TEXT in mixed shapes: it is cast, never compared as
    text, and moved up to the end of its hour in UTC, so 13:55:38 and 14:00:00
    both count under the 14:00 pull."""
    q = " ".join(h._PULLS_SQL.split())
    assert "snapshot_at::timestamptz" in q and "(snapshot_at || 'Z')::timestamptz" in q
    assert "+ interval '1 hour' - interval '1 microsecond', 'UTC')" in q
    # the repo's connection wrapper leaves the casts and the two placeholders alone
    adapted = _adapt_sql(h._PULLS_SQL)
    assert adapted.count("%s") == 2 and "::timestamptz" in adapted and "%(" not in adapted


def test_the_pull_read_goes_two_hundred_games_a_query():
    """`odds` is the table the app and every scorer read: no one query walks
    a whole season of it."""
    conn = Db()
    h.stored_pulls(conn, [f"g{i}" for i in range(501)])
    assert [len(p[0]) for _, p in conn.sql] == [200, 200, 101]


# ── placing the feed's events ────────────────────────────────────────────────

def _listing(eid, home, away, kick):
    return {"id": eid, "commence_time": kick, "home_team": home, "away_team": away}


E_NOON = _listing("e-noon", "Ohio State Buckeyes", "Texas Longhorns", "2025-08-30T16:00:00Z")
# the feed lists the night game the other way round: our away team as home
E_NIGHT = _listing("e-night", "LSU Tigers", "Clemson Tigers", "2025-08-31T01:00:00Z")
E_MAPPED = _listing("e-map", "Mississippi State Bulldogs", "Southern Mississippi Golden Eagles",
                    "2025-08-30T16:00:00Z")
E_EARLY = _listing("e-early", "Kansas State Wildcats", "Iowa State Cyclones",
                   "2025-08-30T13:30:00Z")
E_STRANGER = _listing("e-moose", "Mystery Moose", "Texas Longhorns", "2025-08-30T19:00:00Z")
E_NEXT_WEEK = _listing("e-next", "Ohio State Buckeyes", "Texas Longhorns", "2025-09-06T16:00:00Z")
LISTING = [E_NEXT_WEEK, E_NOON, E_NIGHT, E_MAPPED, E_EARLY, E_STRANGER]


def test_an_event_lands_on_its_game_by_both_team_names_and_the_kickoff():
    am, _ = _plan("am")
    by_id = {p.game_id: p for p in am}
    m = h.EventMatcher(am)
    assert m(E_NOON) == (by_id[NOON["game_id"]], False)
    assert m(E_NIGHT) == (by_id[NIGHT["game_id"]], True)         # flipped
    assert m(E_MAPPED) == (by_id[MAPPED["game_id"]], False)      # through the name map


def test_an_event_that_cannot_be_matched_is_skipped_never_guessed():
    am, _ = _plan("am")
    m = h.EventMatcher(am)
    assert m(E_STRANGER) is None                 # one team is ours, the other is not
    assert m(E_NEXT_WEEK) is None                # the same two teams, a week later
    assert m({**E_NOON, "commence_time": None}) is None
    assert m({**E_NOON, "away_team": "Ohio State Buckeyes"}) is None
    # two planned games equally near the listing: neither is taken
    a = am[-1]
    twin = h.Planned(**{**a.__dict__, "game_id": a.game_id + "_x"})
    assert h.EventMatcher([a, twin])(E_NOON) is None


def test_a_game_with_no_stored_kickoff_is_matched_on_its_eastern_date():
    g = _game("NCAAF_2025-08-30_texas_ohio-state", "Ohio State", "Texas", None)
    (p,), _ = h.plan_read([g], {g["game_id"]: {AM: 9}}, "am")
    m = h.EventMatcher([p])
    assert m(E_NOON) == (p, False) and m(E_NEXT_WEEK) is None


# ── buying ───────────────────────────────────────────────────────────────────

def _markets(home, away):
    return [
        {"key": "h2h_h1", "outcomes": [{"name": home, "price": -160},
                                       {"name": away, "price": 135}]},
        {"key": "spreads_h1", "outcomes": [{"name": home, "price": -112, "point": -2.5},
                                           {"name": away, "price": -108, "point": 2.5}]},
        {"key": "totals_h1", "outcomes": [{"name": "Over", "price": -115, "point": 23.5},
                                          {"name": "Under", "price": -105, "point": 23.5}]},
        {"key": "team_totals", "outcomes": [
            {"name": "Over", "description": home, "price": -120, "point": 27.5},
            {"name": "Under", "description": home, "price": -100, "point": 27.5},
            {"name": "Over", "description": away, "price": -105, "point": 20.5},
            {"name": "Under", "description": away, "price": -115, "point": 20.5}]},
    ]


def _feed(listing=LISTING, odds=None, served="2025-08-30T13:55:38Z"):
    """answer(url, params): the event list, and each event's first-half lines
    and team totals at one book. `odds` overrides an event's answer."""
    events = {e["id"]: e for e in listing}

    def answer(url, params):
        if url.endswith("/events"):
            return Resp(body={"timestamp": served, "data": listing}, last="1")
        eid = url.rsplit("/", 2)[-2]
        if odds and eid in odds:
            return odds[eid]
        e = events[eid]
        return Resp(body={"timestamp": served, "data": {"bookmakers": [
            {"key": "fanduel", "markets": _markets(e["home_team"], e["away_team"])}]}},
                    last="40")
    return answer


def _bought(meter) -> list[str]:
    return [u.rsplit("/", 2)[-2] for u, _ in meter.calls if "/events/" in u]


def _lists(meter) -> list[str]:
    return [p["date"] for u, p in meter.calls if u.endswith("/events")]


def test_one_list_a_date_then_one_call_a_game_at_the_read_s_instant():
    am, _ = _plan("am")
    meter, conn = FakeMeter(_feed()), Db()
    out = h.buy_read(conn, meter, am, "am")
    assert _lists(meter) == ["2025-08-30T14:00:00Z"]
    assert sorted(_bought(meter)) == ["e-map", "e-night", "e-noon"]      # never the stranger
    for u, p in meter.calls:
        assert u.startswith("https://api.the-odds-api.com/v4/historical/sports/"
                            "americanfootball_ncaaf/events")
        if "/events/" in u:
            assert p == {"date": "2025-08-30T14:00:00Z", "oddsFormat": "american",
                         "markets": "h2h_h1,spreads_h1,totals_h1,team_totals",
                         "bookmakers": ncaab.BOOKS}
    assert len(ncaab.BOOKS.split(",")) == 10
    assert out["events"] == 3 and out["left_unbought"] == 0 and out["lists"] == 1
    assert meter.spent == 1 + 3 * 40


def test_every_market_s_rows_land_under_the_right_game_id_market_name_and_source():
    am, _ = _plan("am")
    conn = Db()
    h.buy_read(conn, FakeMeter(_feed()), am, "am")
    assert len(conn.odds) == 3 * 5
    noon = {r["market"]: r for r in conn.odds if r["game_id"] == NOON["game_id"]}
    assert set(noon) == {"h2h_h1", "spreads_h1", "totals_h1", "team_totals_home",
                         "team_totals_away"}
    assert (noon["h2h_h1"]["home_price"], noon["h2h_h1"]["away_price"]) == (-160, 135)
    assert (noon["spreads_h1"]["spread_home"], noon["spreads_h1"]["home_price"]) == (-2.5, -112)
    assert (noon["totals_h1"]["total_line"], noon["totals_h1"]["over_price"],
            noon["totals_h1"]["under_price"]) == (23.5, -115, -105)
    assert (noon["team_totals_home"]["total_line"], noon["team_totals_home"]["over_price"]) == (
        27.5, -120)
    assert (noon["team_totals_away"]["total_line"], noon["team_totals_away"]["under_price"]) == (
        20.5, -115)
    for r in conn.odds:
        assert r["source"] == h.NCAAF_DERIV_AM_SOURCE == "odds_api_ncaaf_derivative_am"
        assert r["sport"] == "NCAAF" and r["bookmaker"] == "fanduel"
        assert r["snapshot_type"] == "open" and r["snapshot_at"] == "2025-08-30T13:55:38Z"
    # the night game: stored under the odds feed's row, never CFBD's
    assert NIGHT_CFBD["game_id"] not in {r["game_id"] for r in conn.odds}


def test_the_rows_are_the_shape_the_ncaab_purchase_stores():
    """One reader fits both sports: the same parser, the same columns."""
    assert h.parse_derivatives is ncaab.parse_derivatives
    assert h.DERIV_MARKETS is ncaab.DERIV_MARKETS and h.DERIV_EVENT_COST == 40
    am, _ = _plan("am")
    conn = Db()
    h.buy_read(conn, FakeMeter(_feed()), am, "am")
    from data.ingestors.nba_odds_history import _ODDS_KEYS
    assert all(tuple(r) == _ODDS_KEYS for r in conn.odds)


def test_a_flipped_event_is_stored_at_our_home_team_s_number():
    """The feed lists LSU home; `games` has Clemson home. The stored spread,
    moneyline and team totals are Clemson's as the home team."""
    am, _ = _plan("am")
    conn = Db()
    out = h.buy_read(conn, FakeMeter(_feed()), am, "am")
    night = {r["market"]: r for r in conn.odds if r["game_id"] == NIGHT["game_id"]}
    assert night["spreads_h1"]["spread_home"] == 2.5 and night["spreads_h1"]["home_price"] == -108
    assert (night["h2h_h1"]["home_price"], night["h2h_h1"]["away_price"]) == (135, -160)
    assert night["team_totals_home"]["total_line"] == 20.5      # Clemson, the feed's away
    assert night["team_totals_away"]["total_line"] == 27.5
    assert out["flipped"] == 1


def test_the_pm_read_asks_at_23z_the_evening_before_under_its_own_source():
    pm, _ = _plan("pm")
    meter, conn = FakeMeter(_feed(served="2025-08-29T22:55:41Z")), Db()
    h.buy_read(conn, meter, pm, "pm")
    assert _lists(meter) == ["2025-08-29T23:00:00Z"]
    assert sorted(_bought(meter)) == ["e-early", "e-night", "e-noon"]
    assert {r["source"] for r in conn.odds} == {"odds_api_ncaaf_derivative_pm"}
    assert {k[1] for k in conn.ledger} == {"pm"}


def test_an_unmatched_event_is_skipped_and_reported_and_a_game_not_listed_is_recorded(capsys):
    am, _ = _plan("am")
    listing = [E_NOON, E_NIGHT, E_STRANGER, E_NEXT_WEEK]         # the mapped game is not listed
    meter, conn = FakeMeter(_feed(listing)), Db()
    out = h.buy_read(conn, meter, am, "am")
    assert sorted(_bought(meter)) == ["e-night", "e-noon"]
    assert out["games_not_listed"] == 1 and out["left_unbought"] == 1
    assert out["events_on_no_planned_game"] == 1                 # the stranger; not next week's
    row = conn.ledger[(MAPPED["game_id"], "am")]
    assert row["status"] == "unlisted" and row["credits"] == 0 and row["rows_stored"] == 0
    printed = capsys.readouterr().out
    assert "Texas Longhorns @ Mystery Moose (1)" in printed and MAPPED["game_id"] in printed
    assert not [r for r in conn.odds if r["game_id"] == MAPPED["game_id"]]


def test_the_feed_s_own_kickoff_decides_a_game_with_no_stored_one():
    """`games` has no kickoff; the feed says 13:30Z, before the am read: it
    is not bought, and costs no call."""
    g = _game(EARLY["game_id"], "Kansas State", "Iowa State", None)
    (p,), _ = h.plan_read([g], {g["game_id"]: {AM: 9}}, "am")
    meter = FakeMeter(_feed())
    out = h.buy_read(Db(), meter, [p], "am")
    assert _bought(meter) == [] and out["kicks_off_before_read"] == 1


def test_a_price_served_after_the_kickoff_is_labelled_in_play():
    am, _ = _plan("am")
    conn = Db()
    out = h.buy_read(conn, FakeMeter(_feed(served="2025-08-30T16:10:00Z")),
                     [p for p in am if p.game_id == NOON["game_id"]], "am")
    assert out["marked_in_play"] == 5 and {r["snapshot_type"] for r in conn.odds} == {"in_play"}


# ── nothing bought twice ─────────────────────────────────────────────────────

def test_every_answer_is_ledgered_with_what_was_asked_served_billed_and_stored():
    am, _ = _plan("am")
    conn = Db()
    h.buy_read(conn, FakeMeter(_feed()), am, "am")
    assert set(conn.ledger) == {(g, "am") for g in _ids(am)}
    row = conn.ledger[(NOON["game_id"], "am")]
    assert row == {"requested_at": AM, "served_at": _t("2025-08-30T13:55:38Z"),
                   "event_id": "e-noon", "credits": 40, "rows_stored": 5, "status": "stored"}


def test_a_rerun_reads_the_ledger_and_buys_nothing_it_holds():
    am, _ = _plan("am")
    conn = Db()
    h.buy_read(conn, FakeMeter(_feed()), am, "am")
    stored = list(conn.odds)
    again = FakeMeter(_feed())
    out = h.buy_read(conn, again, am, "am")
    assert again.calls == [] and again.spent == 0                # not even the date's list
    assert conn.odds == stored
    assert out["held_at_start"] == 3 and out["left_unbought"] == 0 and out.get("events", 0) == 0


def test_a_date_with_one_game_left_lists_once_and_buys_only_that_game():
    am, _ = _plan("am")
    held = {(g, "am"): {"status": "stored"} for g in (NOON["game_id"], NIGHT["game_id"])}
    meter, conn = FakeMeter(_feed()), Db(ledger=held)
    h.buy_read(conn, meter, am, "am")
    assert len(_lists(meter)) == 1 and _bought(meter) == ["e-map"]


def test_the_two_reads_are_ledgered_apart():
    """A game bought at am is still owed at pm."""
    pm, _ = _plan("pm")
    held = {(g["game_id"], "am"): {"status": "stored"} for g in GAMES}
    meter = FakeMeter(_feed())
    h.buy_read(Db(ledger=held), meter, pm, "pm")
    assert sorted(_bought(meter)) == ["e-early", "e-night", "e-noon"]


def test_an_empty_answer_is_ledgered_and_not_asked_for_again():
    am, _ = _plan("am")
    empty = Resp(body={"timestamp": "2025-08-30T13:55:38Z", "data": {"bookmakers": []}}, last="0")
    conn = Db()
    out = h.buy_read(conn, FakeMeter(_feed(odds={"e-noon": empty})), am, "am")
    row = conn.ledger[(NOON["game_id"], "am")]
    assert (row["status"], row["credits"], row["rows_stored"]) == ("empty", 0, 0)
    assert out["empty"] == 1 and out["left_unbought"] == 0
    again = FakeMeter(_feed())
    h.buy_read(conn, again, am, "am")
    assert again.calls == []


def test_a_not_found_is_recorded_free_and_asked_for_again_on_a_rerun():
    am, _ = _plan("am")
    conn = Db()
    meter = FakeMeter(_feed(odds={"e-noon": Resp(status=404, body={}, last="0")}))
    out = h.buy_read(conn, meter, am, "am")
    assert conn.ledger[(NOON["game_id"], "am")]["status"] == "not_found"
    assert out["not_found"] == 1 and out["left_unbought"] == 1 and out.get("retried", 0) == 0
    assert _bought(meter).count("e-noon") == 1
    again = FakeMeter(_feed())
    h.buy_read(conn, again, am, "am")
    assert _bought(again) == ["e-noon"]                          # only the one still owed
    assert conn.ledger[(NOON["game_id"], "am")]["status"] == "stored"


def test_a_failed_call_is_tried_once_more_and_stays_owed_if_it_fails_again():
    am, _ = _plan("am")
    conn = Db()
    meter = FakeMeter(_feed(odds={"e-noon": Resp(status=503, body={}, last="0")}))
    out = h.buy_read(conn, meter, am, "am")
    assert _bought(meter).count("e-noon") == 2
    assert out["retried"] == 1 and out["still_failed"] == 1 and out["left_unbought"] == 1
    assert conn.ledger[(NOON["game_id"], "am")]["status"] == "error"
    assert not [r for r in conn.odds if r["game_id"] == NOON["game_id"]]


def test_a_date_whose_list_got_no_answer_is_listed_once_more():
    am, _ = _plan("am")
    answers = iter([Resp(status=503, body={}, last="0")])
    feed = _feed()

    def flaky(url, params):
        if url.endswith("/events"):
            return next(answers, None) or feed(url, params)
        return feed(url, params)
    meter, conn = FakeMeter(flaky), Db()
    out = h.buy_read(conn, meter, am, "am")
    assert len(_lists(meter)) == 2 and out["dates_unlisted"] == 1
    assert out["events"] == 3 and out["left_unbought"] == 0


def test_a_game_another_process_bought_meanwhile_is_not_bought_again():
    """The ledger is read again just before each date is listed."""
    am, _ = _plan("am")

    class Racing(Db):
        reads = 0

        def execute(self, sql, params=None):
            if " ".join(sql.split()).startswith("SELECT game_id FROM ncaaf_derivative_fetches"):
                Racing.reads += 1
                if Racing.reads == 2:        # after the plan's read, before the list
                    for g in _ids(am):
                        self.ledger[(g, "am")] = {"status": "stored"}
            return super().execute(sql, params)
    meter = FakeMeter(_feed())
    out = h.buy_read(Racing(), meter, am, "am")
    assert meter.calls == [] and out["held_meanwhile"] == 3 and out["left_unbought"] == 0


def test_a_held_row_is_never_rewritten():
    q = " ".join(h._LEDGER_UPSERT.split())
    assert "ON CONFLICT (game_id, read_slot) DO UPDATE" in q
    assert q.endswith("WHERE ncaaf_derivative_fetches.status NOT IN ('stored', 'empty')")
    assert h.HELD_STATUSES == ("stored", "empty")


@pytest.mark.parametrize("server_committed", [True, False])
def test_a_commit_lost_in_flight_stores_each_row_once(server_committed):
    """data.db raises ConnectionLost at a commit whose acknowledgement was
    lost, whether or not the server committed, and the write is run again.
    The rows and the ledger row are one transaction and the ledger is read
    inside it, so either way each row is stored once."""
    class Lossy(Db):
        lost = False

        def commit(self):
            if self._odds_tx and not Lossy.lost:
                Lossy.lost = True
                if server_committed:
                    super().commit()
                else:
                    self.rollback()
                raise ConnectionLost("server closed the connection unexpectedly")
            super().commit()
    import data.ingestors.nba_odds_history as nba
    real_sleep, nba.time.sleep = nba.time.sleep, lambda s: None
    try:
        conn = Lossy()
        noon = [p for p in _plan("am")[0] if p.game_id == NOON["game_id"]]
        out = h.buy_read(conn, FakeMeter(_feed()), noon, "am")
    finally:
        nba.time.sleep = real_sleep
    assert Lossy.lost and len(conn.odds) == 5 and out["left_unbought"] == 0
    assert conn.ledger[(NOON["game_id"], "am")]["status"] == "stored"
    assert out["rows"] == 5 and out["events"] == 1        # the run's count is what was stored


def test_a_ledger_that_cannot_be_read_stops_the_run_rather_than_buying_everything():
    conn = Db(answers={"to_regclass": [("ncaaf_derivative_fetches",)]})

    def boom(sql, params=None, _real=conn.execute):
        if "SELECT game_id FROM ncaaf_derivative_fetches" in " ".join(sql.split()):
            raise RuntimeError("statement timeout")
        return _real(sql, params)
    conn.execute = boom
    meter = FakeMeter(_feed())
    with pytest.raises(RuntimeError, match="statement timeout"):
        h.buy_read(conn, meter, _plan("am")[0], "am")
    assert meter.calls == []
    # a database the ledger has never reached holds nothing: the first dry run
    conn.answers = {}
    assert h.ledger_held(conn, ["g"], "am") == set()


# ── the credit meter ─────────────────────────────────────────────────────────

def test_the_run_does_not_list_a_date_it_could_not_buy_a_game_from():
    am, _ = _plan("am")
    meter = FakeMeter(_feed(), floor=500_000)
    meter.remaining = 500_040                    # the list and one game (41) would cross
    out = h.buy_read(Db(), meter, am, "am")
    assert "floor" in out["stopped"] and meter.calls == [] and out["left_unbought"] == 3


def test_the_run_stops_at_the_floor_before_the_call_that_would_cross_it():
    am, _ = _plan("am")
    feed = _feed()
    balance = {"n": 500_090}

    def answer(url, params):
        r = feed(url, params)
        balance["n"] -= int(r.headers["x-requests-last"])
        r.headers["x-requests-remaining"] = str(balance["n"])
        return r
    meter = FakeMeter(answer, floor=500_000)
    meter.remaining = 500_090                    # the list (1) and two games (80) fit
    conn = Db()
    out = h.buy_read(conn, meter, am, "am")
    assert "floor" in out["stopped"] and len(_bought(meter)) == 2
    assert meter.remaining == 500_009 >= meter.floor
    assert out["left_unbought"] == 1 and len(conn.ledger) == 2


def test_the_run_stops_at_the_limit_before_the_call_that_would_cross_it():
    am, _ = _plan("am")
    meter = FakeMeter(_feed(), ceiling=100)      # the list and two games are 81
    out = h.buy_read(Db(), meter, am, "am")
    assert "ceiling" in out["stopped"] and len(_bought(meter)) == 2
    assert meter.spent == 81 <= 100 and out["left_unbought"] == 1


def test_calls_side_by_side_never_take_the_balance_under_the_floor():
    """Six at once, each call in flight counted at 40: with 1,125 over a 1,000
    floor the list (1) and three games fit (1,124 - 120 = 1,004); a fourth in
    flight could end at 964."""
    games = [_game(f"NCAAF_2025-08-30_a{i}_b{i}", f"B{i}", f"A{i}", "2025-08-30T16:00:00Z")
             for i in range(6)]
    plan, _ = h.plan_read(games, {g["game_id"]: {AM: 9} for g in games}, "am")
    listing = [_listing(f"e{i}", f"B{i} Bears", f"A{i} Ants", "2025-08-30T16:00:00Z")
               for i in range(6)]
    feed = Feed(_feed(listing), floor=1_000, balance=1_125, hold=0.2)
    feed.remaining = 1_125
    conn = Db()
    out = h.buy_read(conn, feed, plan, "am")
    assert "floor" in out["stopped"] and feed.balance >= 1_000 and feed.remaining >= 1_000
    assert sum(1 for u, _ in feed.sent if "/events/" in u) == 3
    assert out["left_unbought"] == 3 and out["concurrency"] == 6 and feed.peak > 1


def test_side_by_side_stores_what_one_at_a_time_stores():
    def run(workers):
        conn = Db()
        feed = Feed(_feed(), workers=workers, jitter=True)
        feed.remaining = 2_000_000
        out = h.buy_read(conn, feed, _plan("am")[0], "am")
        return conn, out, feed
    one, one_out, _ = run(1)
    six, six_out, six_feed = run(6)
    assert six.odds == one.odds and len(one.odds) == 15 and six.ledger == one.ledger
    drop = {"concurrency", "rate_limited_429"}
    assert {k: v for k, v in six_out.items() if k not in drop} == {
        k: v for k, v in one_out.items() if k not in drop}


def test_the_meter_is_the_ncaab_purchase_s():
    assert h.PoolMeter is ncaab.PoolMeter and h._paid_calls is ncaab._paid_calls
    assert h.LIST_COST == 1 and h.MIN_FLOOR == ncaab.MIN_FLOOR == 300_000


# ── the test buy ─────────────────────────────────────────────────────────────

KICKS = ["16:00", "19:30", "23:00", "02:30"]     # noon, 3:30pm, 7pm, 10:30pm Eastern (EDT)


def _slate(per=10):
    games, pulls = [], {}
    for season in (2023, 2024, 2025):
        for b, hhmm in enumerate(KICKS):
            for i in range(per):
                d = date(season, 9, 6) + timedelta(days=7 * i)
                kick = datetime.fromisoformat(f"{d + timedelta(days=int(hhmm < '06'))}T{hhmm}:00+00:00")
                g = _game(f"NCAAF_{d}_s{season}k{b}g{i}_h", f"H{season}{b}{i}", f"A{season}{b}{i}",
                          kick.isoformat(), day=str(d), season=season, score=20)
                games.append(g)
                pulls[g["game_id"]] = {h.read_instant(d, "am"): 9, h.read_instant(d, "pm"): 9}
    return games, pulls


def test_the_kickoff_time_strata():
    assert [h.kick_bucket(_t(f"2025-09-06T{x}:00Z")) for x in ("16:00", "18:59", "19:00",
                                                               "21:59", "22:00")] == [
        "before 3pm ET", "before 3pm ET", "3-6pm ET", "3-6pm ET", "6-9pm ET"]
    assert h.kick_bucket(_t("2025-09-07T01:00:00Z")) == "9pm ET or later"
    assert h.kick_bucket(_t("2025-09-07T04:30:00Z")) == "9pm ET or later"   # 12:30am Eastern


def test_the_sample_spreads_over_every_season_and_kickoff_time_and_never_moves():
    games, pulls = _slate()
    plan, _ = h.plan_read(games, pulls, "am")
    got = h.sample_games(plan, 50)
    assert len(got) == 50 and len({p.game_id for p in got}) == 50
    per = Counter((p.season, h.kick_bucket(p.kick)) for p in got)
    assert len(per) == 12 and set(per.values()) == {4, 5}        # 3 seasons x 4 kickoff times
    assert Counter(s for s, _ in per.elements()) == {2025: 17, 2024: 17, 2023: 16}
    # deterministic, whatever order the plan arrives in, and newest date first
    assert _ids(got) == _ids(h.sample_games(list(reversed(plan)), 50))
    assert [p.instant for p in got] == sorted((p.instant for p in got), reverse=True)
    assert _ids(got) != _ids(h.sample_games(plan, 50, seed="another"))
    assert len(h.sample_games(plan[:7], 50)) == 7                # fewer than asked: all of them


def test_the_test_buy_is_stored_where_the_full_buy_looks_so_the_full_buy_skips_it():
    games, pulls = _slate(per=2)
    plan, _ = h.plan_read(games, pulls, "am")
    sample = h.sample_games(plan, 6)
    listing = [_listing("e-" + p.game_id, p.home + " Hawks", p.away + " Owls",
                        _stamp_of(p.kick)) for p in plan]
    conn = Db()
    first = FakeMeter(_feed(listing))
    h.buy_read(conn, first, sample, "am")
    assert sorted(_bought(first)) == sorted("e-" + p.game_id for p in sample)
    assert {r["source"] for r in conn.odds} == {h.NCAAF_DERIV_AM_SOURCE}
    full = FakeMeter(_feed(listing))
    out = h.buy_read(conn, full, plan, "am")
    assert not set(_bought(full)) & {"e-" + p.game_id for p in sample}
    assert out["held_at_start"] == 6 and out["events"] == len(plan) - 6


def _stamp_of(kick: datetime) -> str:
    return kick.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── what was bought, read back ───────────────────────────────────────────────

def test_the_coverage_table_is_read_back_from_odds_for_the_bought_games():
    am, _ = _plan("am")
    held = {(g, "am"): {"status": "stored"} for g in (NOON["game_id"], NIGHT["game_id"])}
    held[(MAPPED["game_id"], "am")] = {"status": "unlisted"}
    stored = [("fanduel", "spreads_h1", NOON["game_id"]),
              ("fanduel", "spreads_h1", NIGHT["game_id"]),
              ("draftkings", "team_totals_home", NOON["game_id"]),
              ("fanduel", "alternate_spreads", NOON["game_id"])]     # not one of the five
    conn = Db(ledger=held, answers={"SELECT DISTINCT bookmaker, market, game_id FROM odds": stored})
    table = h.coverage(conn, am, "am")
    assert "2 of 3 planned games bought; 2 hold a quote" in table
    rows = {line.split()[0]: line.split()[1:] for line in table.splitlines()[3:]}
    cols = list(h.REPORT_MARKETS)
    assert rows["fanduel"][cols.index("spreads_h1")] == "2"
    assert rows["draftkings"][cols.index("team_totals_home")] == "1"
    assert rows["any"][1 + cols.index("spreads_h1")] == "2"       # "any book" splits in two
    (q, params), = [(q, p) for q, p in conn.sql if "SELECT DISTINCT bookmaker" in q]
    assert sorted(params[0]) == sorted([NOON["game_id"], NIGHT["game_id"]])
    assert params[1] == h.NCAAF_DERIV_AM_SOURCE and "in_play" in q


# ── the clean-up cannot reach what was bought ────────────────────────────────

def test_both_sources_are_protected_from_the_odds_clean_up():
    assert h.SOURCES == {"am": "odds_api_ncaaf_derivative_am",
                         "pm": "odds_api_ncaaf_derivative_pm"}
    params: dict = {}
    pred = prune_odds._unprotected(params, table="odds")
    for src in h.SOURCES.values():
        assert src in prune_odds.PROTECTED_SOURCES and src in params["protected_sources"], src
    assert "protected_sources" in pred
    # and the sport keeps its whole price path besides
    assert "NCAAF" in prune_odds.PATH_KEPT_SPORTS


# ── the ledger table ─────────────────────────────────────────────────────────

def test_the_ledger_is_a_worker_only_table_keyed_on_game_and_read():
    from data.anon_readable import WORKER_ONLY_TABLES
    assert h.LEDGER == "ncaaf_derivative_fetches" and h.LEDGER in WORKER_ONLY_TABLES
    assert "CREATE TABLE IF NOT EXISTS ncaaf_derivative_fetches" in h.LEDGER_DDL
    assert "PRIMARY KEY (game_id, read_slot)" in h.LEDGER_DDL
    for col in h.LEDGER_COLS:
        assert col in h.LEDGER_DDL, col


def test_the_ledger_is_created_once_locked_down_and_fires_no_ddl_after_that():
    fresh = GuardConn(None)                       # the table does not exist
    h.ensure_ledger(fresh)
    text = " | ".join(fresh.statements)
    assert "CREATE TABLE IF NOT EXISTS ncaaf_derivative_fetches" in text
    assert "REVOKE ALL ON ncaaf_derivative_fetches FROM anon, authenticated" in text
    assert "ALTER TABLE ncaaf_derivative_fetches ENABLE ROW LEVEL SECURITY" in text
    current = GuardConn((True, list(h.LEDGER_COLS), [], 0))
    h.ensure_ledger(current)
    assert current.statements == []
    # a table that exists but is open, or lacks a column, is not "current"
    for state in ((False, list(h.LEDGER_COLS), [], 0), (True, list(h.LEDGER_COLS), [], 1),
                  (True, ["game_id"], [], 0)):
        stale = GuardConn(state)
        h.ensure_ledger(stale)
        assert stale.statements, state


# ── the command line ─────────────────────────────────────────────────────────

BURN = [(f"2026-11-{d:02d}", 60_000 * i) for i, d in enumerate(range(1, 9), start=1)]


def _quota(remaining=11_900_000):
    """odds_api_quota as the budget reads it: 60,000 a day, newest first."""
    return {"requests_used IS NOT NULL": list(reversed(BURN)),
            "SELECT requests_remaining": [(remaining,)]}


def _cli(monkeypatch, conn, argv):
    made = []
    monkeypatch.setattr(h, "load_games", lambda c, a, b: [dict(g) for g in GAMES])
    monkeypatch.setattr(h, "stored_pulls", lambda c, ids: PULLS)
    monkeypatch.setattr(h, "get_connection", lambda: conn)
    monkeypatch.setattr(h, "_read_only_connection", lambda: conn)
    monkeypatch.setattr(h, "persist_quota", lambda c: made.append(("quota",)))
    monkeypatch.setattr(h, "ensure_ledger", lambda c: made.append(("ledger",)))
    monkeypatch.setattr(h, "check_registry", lambda c: 698)
    monkeypatch.setattr(h.config, "ODDS_API_KEY", "SECRET-TEST-KEY")

    def buy(c, meter, plan, read):
        made.append((read, _ids(plan), meter.ceiling, meter.floor, meter.remaining,
                     meter.workers))
        return {}
    monkeypatch.setattr(h, "buy_read", buy)
    monkeypatch.setattr("sys.argv", ["ncaaf_derivative_history"] + argv)
    return made


def test_without_apply_it_prints_the_plan_by_season_and_read_and_calls_nothing(monkeypatch, capsys):
    conn = Db(answers=_quota())
    made = _cli(monkeypatch, conn, ["--read", "both"])
    monkeypatch.setattr(h, "get_connection", lambda: pytest.fail("a writable connection"))
    monkeypatch.setattr(h, "PoolMeter", lambda *a, **k: pytest.fail("a meter in a dry run"))
    h.main()
    assert made == [] and conn.writes() == []
    out = capsys.readouterr().out
    assert "No call is made and nothing is written" in out
    assert "read am (14:00 UTC on the game's Eastern date), source odds_api_ncaaf_derivative_am" in out
    assert "read pm (23:00 UTC on the Eastern date before), source odds_api_ncaaf_derivative_pm" in out
    am = out[out.index("read am"):out.index("read pm")]
    season = next(line.split() for line in am.splitlines() if line.strip().startswith("2025"))
    # season, games, dates, with a final, their dates, already bought
    assert season == ["2025", "3", "1", "3", "1", "0"]
    assert "to buy: 3 games on 1 dates, at most 121 credits" in am
    assert "1 kick off within 5 minutes of it or before it" in am
    assert "all reads asked for: at most 242 credits" in out
    # the measured reserve (7 days of 60,000) is above the 300,000 floor
    assert "re-run with --apply --max-credits 242 --floor 420000" in out


def test_the_dry_run_counts_what_the_ledger_already_holds(monkeypatch, capsys):
    held = {(NOON["game_id"], "am"): {"status": "stored"}}
    _cli(monkeypatch, Db(ledger=held, answers=_quota()), ["--read", "am", "--dry-run"])
    h.main()
    out = capsys.readouterr().out
    assert "to buy: 2 games on 1 dates, at most 81 credits" in out
    assert next(line.split() for line in out.splitlines()
                if line.strip().startswith("all "))[-1] == "1"


def test_apply_takes_the_smaller_ceiling_and_the_larger_floor(monkeypatch, capsys):
    """--max-credits above the plan's most is cut to the plan; --floor under
    the measured reserve is raised to it; the balance on record goes in, so
    the first call is checked too."""
    made = _cli(monkeypatch, Db(answers=_quota()),
                ["--read", "both", "--apply", "--max-credits", "500000", "--floor", "300000",
                 "--concurrency", "4"])
    h.main()
    am, pm = [m for m in made if m[0] in ("am", "pm")]
    assert am[1] == [NIGHT["game_id"], MAPPED["game_id"], NOON["game_id"]]
    assert am[2:] == (242, 420_000, 11_900_000, 4) and pm[2:] == am[2:]
    assert made[0] == ("ledger",) and made[-1] == ("quota",)
    made = _cli(monkeypatch, Db(answers=_quota()),
                ["--read", "am", "--apply", "--max-credits", "50", "--floor", "900000"])
    h.main()
    assert [m[2:4] for m in made if m[0] == "am"] == [(50, 900_000)]


def test_apply_refuses_to_start_when_the_reserve_cannot_be_measured(monkeypatch):
    made = _cli(monkeypatch, Db(), ["--read", "am", "--apply", "--max-credits", "121",
                                    "--floor", "300000"])
    with pytest.raises(SystemExit, match="refusing to start"):
        h.main()
    assert not [m for m in made if m[0] in ("am", "pm")]
    # stated outright, it starts
    made = _cli(monkeypatch, Db(), ["--read", "am", "--apply", "--max-credits", "121",
                                    "--floor", "300000", "--burn-per-day", "60000",
                                    "--remaining", "11900000"])
    h.main()
    assert [m[2:5] for m in made if m[0] == "am"] == [(121, 420_000, 11_900_000)]


def test_apply_refuses_to_start_without_a_team_registry(monkeypatch, capsys):
    """With no registry no feed name lands on a stored school: every date's
    list would be paid for and every game recorded as not listed."""
    def empty(conn):
        raise h.PreconditionError("ncaaf_teams is empty or unreadable")
    made = _cli(monkeypatch, Db(answers=_quota()),
                ["--read", "am", "--apply", "--max-credits", "121", "--floor", "300000"])
    monkeypatch.setattr(h, "check_registry", empty)
    monkeypatch.setattr(h, "PoolMeter", lambda *a, **k: pytest.fail("a meter with no registry"))
    with pytest.raises(SystemExit, match="refusing to start: ncaaf_teams is empty"):
        h.main()
    assert not [m for m in made if m[0] in ("am", "pm")]
    # the dry run says so too, and still prints the plan
    _cli(monkeypatch, Db(answers=_quota()), ["--read", "am"])
    monkeypatch.setattr(h, "check_registry", empty)
    h.main()
    out = capsys.readouterr().out
    assert "WOULD REFUSE: ncaaf_teams is empty or unreadable" in out and "to buy: 3 games" in out


def test_the_registry_is_read_fresh_and_an_empty_read_is_not_left_for_the_next_job():
    """The worker runs every job in one process, and the name resolution keeps
    whatever it read first, an empty list included."""
    from data.ingestors import cfbd_ingestor
    try:
        cfbd_ingestor._SCHOOL_CACHE = []                 # an earlier job's failed read
        conn = Db(answers={"FROM ncaaf_teams": [("Ohio State", "Buckeyes", "OSU|tOSU"),
                                                ("Texas", "Longhorns", None)]})
        assert h.check_registry(conn) == 2
        assert [s["school"] for s in cfbd_ingestor._SCHOOL_CACHE] == ["Ohio State", "Texas"]
        with pytest.raises(h.PreconditionError, match="ncaaf_teams is empty or unreadable"):
            h.check_registry(Db())
        assert cfbd_ingestor._SCHOOL_CACHE is None       # the next job reads it again
        boom = Db(answers={"FROM ncaaf_teams": RuntimeError("relation does not exist")})
        with pytest.raises(h.PreconditionError):
            h.check_registry(boom)
        assert cfbd_ingestor._SCHOOL_CACHE is None
    finally:
        cfbd_ingestor.reset_school_cache()


def test_a_feed_name_is_resolved_once_a_run_not_once_a_date(monkeypatch):
    asked = []
    monkeypatch.setattr(h, "_normalize_team",
                        lambda name, sport: asked.append(name) or name.rsplit(" ", 1)[0])
    games, pulls = _slate(per=2)
    plan, _ = h.plan_read(games, pulls, "am")
    listing = [_listing("e-moose", "Mystery Moose", "Nobody Newts", "2025-09-06T16:00:00Z")]
    h.buy_read(Db(), FakeMeter(_feed(listing)), plan, "am")
    assert len(_lists_dates(plan)) > 1 and sorted(asked) == ["Mystery Moose", "Nobody Newts"]


def _lists_dates(plan):
    return {p.instant for p in plan}


def test_apply_refuses_a_run_that_would_leave_less_than_the_reserve(monkeypatch):
    made = _cli(monkeypatch, Db(answers=_quota(remaining=420_100)),
                ["--read", "am", "--apply", "--max-credits", "121", "--floor", "300000"])
    with pytest.raises(SystemExit, match="under the 420,000 reserve"):
        h.main()
    assert not [m for m in made if m[0] in ("am", "pm")]


def test_a_stop_in_the_first_read_does_not_start_the_second(monkeypatch):
    made = _cli(monkeypatch, Db(answers=_quota()),
                ["--read", "both", "--apply", "--max-credits", "242", "--floor", "300000"])
    monkeypatch.setattr(h, "buy_read", lambda c, m, plan, read: made.append((read,)) or {
        "stopped": "floor"})
    h.main()
    assert [m for m in made if m[0] in ("am", "pm")] == [("am",)]


def test_nothing_left_to_buy_builds_no_meter(monkeypatch, capsys):
    held = {(g["game_id"], "am"): {"status": "stored"} for g in GAMES}
    made = _cli(monkeypatch, Db(ledger=held),
                ["--read", "am", "--apply", "--max-credits", "121", "--floor", "300000"])
    monkeypatch.setattr(h, "PoolMeter", lambda *a, **k: pytest.fail("a meter with nothing to buy"))
    h.main()
    assert "nothing to buy" in capsys.readouterr().out
    assert not [m for m in made if m[0] == "am"]


@pytest.mark.parametrize("argv", [
    ["--read", "am", "--apply", "--max-credits", "1000"],                       # no floor
    ["--read", "am", "--apply", "--floor", "300000"],                           # no limit
    ["--read", "am", "--apply", "--max-credits", "0", "--floor", "300000"],
    ["--read", "am", "--apply", "--max-credits", "1000", "--floor", "299999"],  # the feeds' reserve
    ["--read", "am", "--apply", "--dry-run", "--max-credits", "1000", "--floor", "300000"],
    ["--read", "noon"],
    ["--apply", "--max-credits", "1000", "--floor", "300000"],                  # no read
    ["--read", "am", "--seasons", "2022", "2025"],                              # not approved
    ["--read", "am", "--seasons", "2023", "2026"],
    ["--read", "am", "--seasons", "2025", "2023"],
    ["--read", "am", "--sample", "0"],
    ["--read", "am", "--concurrency", "11"],
    ["--read", "am", "--concurrency", "0"],
])
def test_a_command_line_that_could_overspend_or_makes_no_sense_is_refused(monkeypatch, argv):
    made = _cli(monkeypatch, Db(answers=_quota()), argv)
    monkeypatch.setattr(h, "get_connection", lambda: pytest.fail("connected"))
    monkeypatch.setattr(h, "_read_only_connection", lambda: pytest.fail("connected"))
    with pytest.raises(SystemExit):
        h.main()
    assert made == []


def test_apply_without_a_key_stops_before_it_connects(monkeypatch):
    _cli(monkeypatch, Db(), ["--read", "am", "--apply", "--max-credits", "121",
                             "--floor", "300000"])
    monkeypatch.setattr(h.config, "ODDS_API_KEY", "")
    monkeypatch.setattr(h, "get_connection", lambda: pytest.fail("connected"))
    with pytest.raises(SystemExit, match="ODDS_API_KEY"):
        h.main()


def test_the_test_buy_s_dry_run_lists_its_games(monkeypatch, capsys):
    _cli(monkeypatch, Db(answers=_quota()), ["--read", "am", "--sample", "2"])
    h.main()
    out = capsys.readouterr().out
    assert "test buy of 2, 2 sampled of 3 planned" in out
    assert out.count("would buy at 2025-08-30 14:00Z") == 2
    assert "to buy: 2 games on 1 dates, at most 81 credits" in out


# ── the worker job ───────────────────────────────────────────────────────────

def _argv(monkeypatch, args):
    seen = []
    monkeypatch.setattr(jq, "_run_script_main", lambda mod, argv: seen.append((mod, argv)) or "ok")
    jq._job_ncaaf_derivative_history(**jq._validate_ncaaf_derivative_history(dict(args)))
    (mod, argv), = seen
    assert mod == "data.ingestors.ncaaf_derivative_history"
    return argv


def test_the_job_is_on_the_allowlist_and_runs_the_module_s_own_command_line():
    import inspect
    assert jq.JOBS["ncaaf_derivative_history"] == (jq._job_ncaaf_derivative_history,
                                                   jq._validate_ncaaf_derivative_history)
    src = inspect.getsource(jq._job_ncaaf_derivative_history)
    assert "_run_script_main" in src and "subprocess" not in src


@pytest.mark.parametrize("args,want", [
    ({"read": "am", "max_credits": 92_765, "floor": 300_000},
     ["--read", "am", "--seasons", "2023", "2025", "--concurrency", "6", "--apply",
      "--max-credits", "92765", "--floor", "300000"]),
    ({"read": "both", "max_credits": 185_530, "floor": 300_000, "concurrency": 3},
     ["--read", "both", "--seasons", "2023", "2025", "--concurrency", "3", "--apply",
      "--max-credits", "185530", "--floor", "300000"]),
    ({"read": "am", "sample": 50, "max_credits": 2_050, "floor": 300_000},
     ["--read", "am", "--seasons", "2023", "2025", "--sample", "50", "--concurrency", "6",
      "--apply", "--max-credits", "2050", "--floor", "300000"]),
    ({"read": "pm", "dry_run": True},
     ["--read", "pm", "--seasons", "2023", "2025", "--dry-run"]),
    ({"read": "am", "sample": 50, "dry_run": True},
     ["--read", "am", "--seasons", "2023", "2025", "--sample", "50", "--dry-run"]),
])
def test_the_job_s_argv_parses_on_the_module_s_own_parser(monkeypatch, args, want):
    argv = _argv(monkeypatch, args)
    assert argv == want
    a = h._parser().parse_args(argv)
    assert a.read == args["read"] and a.seasons == [2023, 2025]
    assert a.apply is not args.get("dry_run", False)


def test_the_job_s_limits_are_the_figures_the_audit_put_in_front_of_mike():
    """docs/ncaaf_market_audit.md section 7: 2,314 games on 205 dates a read,
    92,765 credits; the 50-game test 2,050."""
    assert jq.NCAAF_DERIVATIVE_HISTORY_CAPS == {"am": 92_765, "pm": 92_765, "both": 185_530}
    assert jq.NCAAF_DERIVATIVE_HISTORY_CAPS["am"] == 2_314 * h.DERIV_EVENT_COST + 205 * h.LIST_COST
    assert jq.NCAAF_DERIVATIVE_HISTORY_SEASONS == h.SEASONS == (2023, 2025)
    ok = jq._validate_ncaaf_derivative_history
    assert ok({"read": "am", "sample": 50, "max_credits": 2_050, "floor": 300_000})
    assert ok({"read": "both", "sample": 50, "max_credits": 4_100, "floor": 300_000})


@pytest.mark.parametrize("args", [
    {"read": "am", "max_credits": 92_766, "floor": 300_000},          # above what was stated
    {"read": "both", "max_credits": 185_531, "floor": 300_000},
    {"read": "am", "sample": 50, "max_credits": 2_051, "floor": 300_000},
    {"read": "am", "max_credits": 0, "floor": 300_000},
    {"read": "am", "max_credits": 1_000, "floor": 299_999},           # would let the feeds run dry
    {"read": "am", "max_credits": 1_000},
    {"read": "noon", "max_credits": 1_000, "floor": 300_000},
    {"max_credits": 1_000, "floor": 300_000},
    {"read": "am", "max_credits": 1_000, "floor": 300_000, "seasons": [2020, 2025]},
    {"read": "am", "max_credits": 1_000, "floor": 300_000, "concurrency": 11},
    {"read": "am", "max_credits": 1_000, "floor": 300_000, "sample": 0},
    {"read": "am", "max_credits": 1_000, "floor": 300_000, "sample": True},
    {"read": "am", "dry_run": True, "max_credits": 1_000},            # a dry run buys nothing
    {"read": "am", "dry_run": "yes"},
])
def test_a_job_outside_the_approved_purchase_is_refused(args):
    with pytest.raises(ValueError):
        jq._validate_ncaaf_derivative_history(args)


def test_the_purchase_is_not_a_declared_job_so_a_merge_buys_nothing():
    import json
    from pathlib import Path
    declared = json.loads((Path(__file__).resolve().parent.parent / "jobs"
                           / "declared_jobs.json").read_text(encoding="utf-8"))
    jobs = declared["jobs"] if isinstance(declared, dict) else declared
    assert not [j for j in jobs if j.get("job_type") == "ncaaf_derivative_history"]


# ── every paid call is logged ────────────────────────────────────────────────

def test_a_plain_module_run_logs_its_odds_api_call(tmp_path, monkeypatch):
    """The 2026-11-03 hole: a purchase run as a plain module logged nothing.
    The real request path of this module (its meter's one HTTP line, the
    probe's wrapper) in a child process, the transport and the database stood
    in for: one row in api_call_log, with what the feed billed."""
    import tests.test_odds_call_log_everywhere as log
    fixture = (log._FIXTURE
               .replace("from data.ingestors import nba_odds_history as H",
                        "from data.ingestors import ncaaf_derivative_history as H")
               .replace("H.Meter(ceiling=10, floor=0)", "H.PoolMeter(ceiling=10, floor=0)"))
    assert "ncaaf_derivative_history" in fixture and "PoolMeter" in fixture
    monkeypatch.setattr(log, "_FIXTURE", fixture)
    rows, _, _ = log._run(tmp_path, "plain", how="module")
    (row,) = rows
    assert row["api"] == "The Odds API" and row["source"] == "paid_call_fixture"
    assert row["status"] == 200 and float(row["credits"]) == 3.0
    assert float(row["quota_remaining"]) == 4000000.0
    assert row["sport"] == "NCAAF"
    assert row["path"].startswith("/v4/historical/sports/americanfootball_ncaaf/events")
    assert "SECRET" not in repr(row)


def test_the_module_is_one_of_the_callers_the_logger_scan_covers():
    import tests.test_odds_call_log_everywhere as log
    assert "data/ingestors/ncaaf_derivative_history.py" in {rel for rel, _, _ in log._odds_callers()}

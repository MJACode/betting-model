"""The live NBA team-total feed (data/ingestors/nba_team_total_odds.py): one
per-event call per planned game, stored before nba_team_total_luck decides.

No test here calls the Odds API: the event list and the event call are fakes
fed recorded-shape payloads, and the database is FakeDB below, which answers
exactly the statements the feed, the card and the plan send. FakeDB fixes
now() at the first statement of each transaction, as Postgres does, so the
tests can see which instant a row's created_at records.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import data.ingestors.nba_team_total_odds as feed  # noqa: E402
from data.ingestors import odds_quota  # noqa: E402

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
GID = "NBA_2026-11-05_BOS_MIL"          # Boston at Milwaukee
HOME_NAME, AWAY_NAME = "Milwaukee Bucks", "Boston Celtics"


def et(y, m, d, hh, mm, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=ET).astimezone(UTC)


TIP = et(2026, 11, 5, 19, 30)


# ── a database for exactly these statements ──────────────────────────────────

class _Cur:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _like(pattern: str, value) -> bool:
    if value is None:
        return False
    rx = "".join(".*" if c == "%" else "." if c == "_" else re.escape(c) for c in pattern)
    return re.fullmatch(rx, str(value), re.DOTALL) is not None


def _ts(v):
    """A timestamp from any shape these tables hold: a datetime, Postgres'
    now()::text ('... 23:34:00.000000+00') or the feed's ISO ('...Z')."""
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    s = str(v).replace("Z", "+00:00")
    if re.search(r"[+-]\d\d$", s):
        s += ":00"
    t = datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=UTC)


class FakeDB:
    """The production tables these modules touch, in memory: odds, games,
    picks, the fetch ledger and the decisions ledger. Writes land at commit;
    a rollback drops them. now() is `clock()` at a transaction's first
    statement. A WHERE clause is evaluated condition by condition, so a
    condition a query drops is a filter the test no longer gets."""

    TABLES = ("odds", "picks", feed.LEDGER_TABLE, "nba_team_total_luck_decisions")

    def __init__(self, clock, games=None, tables=()):
        self.clock = clock
        self.games = dict(games or {})            # game_id -> (home, away)
        self.tables = {"odds", "picks", "games", *tables}
        self.rows = {t: [] for t in self.TABLES}
        self.pending: list[tuple[str, dict]] = []
        self.txn_now = None
        self.log: list[tuple] = []

    # transaction
    def _begin(self):
        if self.txn_now is None:
            self.txn_now = self.clock()

    def commit(self):
        for table, row in self.pending:
            self.rows[table].append(row)
        self.pending, self.txn_now = [], None
        self.log.append(("commit",))

    def rollback(self):
        self.pending, self.txn_now = [], None
        self.log.append(("rollback",))

    def close(self):
        self.log.append(("close",))

    def _all(self, table):
        return self.rows[table] + [r for t, r in self.pending if t == table]

    # WHERE
    def _where(self, sql: str, params) -> list:
        m = re.search(r"\bWHERE\b(.*?)(\bGROUP BY\b|\bORDER BY\b|$)", sql, re.S)
        conds = [c.strip() for c in re.split(r"\bAND\b", m.group(1))] if m else []
        it = iter(params or ())
        out = []
        for c in conds:
            if not c:
                continue
            col = re.match(r"(\w+)", c).group(1)
            if re.search(r"=\s*ANY\(%s\)", c):
                vals = set(next(it))
                out.append(lambda r, col=col, vals=vals: r.get(col) in vals)
            elif "LIKE %s" in c:
                pat = next(it)
                out.append(lambda r, col=col, pat=pat: _like(pat, r.get(col)))
            elif re.search(r">=\s*%s", c):
                v = _ts(next(it))
                out.append(lambda r, col=col, v=v: r.get(col) is not None and _ts(r[col]) >= v)
            elif re.search(r"<=\s*%s", c):
                v = _ts(next(it))
                out.append(lambda r, col=col, v=v: r.get(col) is not None and _ts(r[col]) <= v)
            elif re.search(r"=\s*%s", c):
                v = next(it)
                out.append(lambda r, col=col, v=v: r.get(col) == v)
            elif m2 := re.search(r"=\s*'([^']*)'", c):
                v = m2.group(1)
                out.append(lambda r, col=col, v=v: r.get(col) == v)
            elif c == "ok":
                out.append(lambda r: bool(r.get("ok")))
            else:
                raise AssertionError(f"FakeDB cannot read the condition {c!r}")
        return out

    def _select(self, table, sql, params):
        conds = self._where(sql, params)
        return [r for r in self._all(table) if all(f(r) for f in conds)]

    def _now_text(self):
        return self.txn_now.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f+00")

    # statements
    def executemany(self, sql, seq):
        for p in seq:
            self.execute(sql, p)

    def execute(self, sql, params=None):
        self._begin()
        s = " ".join(sql.split())
        self.log.append(("sql", s))
        if "relrowsecurity" in s:
            return _Cur([])                       # schema_is_current: not current
        if "information_schema.tables" in s:
            return _Cur([(1,)] if params[0] in self.tables else [])
        if s.startswith("CREATE TABLE IF NOT EXISTS"):
            self.tables.add(s.split()[5])
            return _Cur([])
        if s.startswith(("REVOKE", "ALTER TABLE", "SET LOCAL", "SELECT pg_advisory")):
            return _Cur([])
        if s.startswith("INSERT INTO odds_api_quota"):
            return _Cur([])
        if s.startswith("SELECT game_id, home_team, away_team FROM games"):
            sport, ids = params
            return _Cur([(g, h, a) for g, (h, a) in self.games.items() if g in set(ids)])
        if s.startswith("INSERT INTO odds "):
            self.pending.append(("odds", {**params, "created_at": self._now_text()}))
            return _Cur([])
        if s.startswith(f"INSERT INTO {feed.LEDGER_TABLE}"):
            self.pending.append((feed.LEDGER_TABLE, {**params, "fetch_at": self.txn_now}))
            return _Cur([])
        if s.startswith("INSERT INTO nba_team_total_luck_decisions"):
            if any(r["game_id"] == params["game_id"]
                   for r in self._all("nba_team_total_luck_decisions")):
                return _Cur([])
            self.pending.append(("nba_team_total_luck_decisions", dict(params)))
            return _Cur([(params["game_id"],)])
        if s.startswith("INSERT INTO picks"):
            # No uniqueness emulated: what keeps a game to one pick here is
            # the card's own ledger and lock, which is what the tests pin.
            self.pending.append(("picks", dict(params)))
            return _Cur([(len(self._all("picks")),)])
        if f"FROM {feed.LEDGER_TABLE}" in s:
            best: dict[str, datetime] = {}
            for r in self._select(feed.LEDGER_TABLE, s, params):
                if r["game_id"] is not None:
                    best[r["game_id"]] = max(best.get(r["game_id"], r["fetch_at"]), r["fetch_at"])
            return _Cur(best.items())
        if "FROM nba_team_total_luck_decisions" in s:
            return _Cur([(r["game_id"],) for r in self._select(
                "nba_team_total_luck_decisions", s, params)])
        if "FROM picks" in s:
            return _Cur(sorted({(r["game_id"],) for r in self._select("picks", s, params)}))
        if "FROM odds" in s:
            got = self._select("odds", s, params)
            if s.startswith("SELECT DISTINCT game_id"):
                return _Cur(sorted({(r["game_id"],) for r in got}))
            cols = [c.strip() for c in re.match(r"SELECT (.*?) FROM", s).group(1).split(",")]
            return _Cur([tuple(r.get(c) for c in cols) for r in got])
        raise AssertionError(f"FakeDB does not know this statement: {s[:120]}")


class Clock:
    """A wall clock the fakes move: each API call takes `call_s` seconds."""

    def __init__(self, t: datetime):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, s: float):
        self.t = self.t + timedelta(seconds=s)


# ── recorded-shape payloads ──────────────────────────────────────────────────

def outcome(side, team, point, price, book="fanduel", swap=False):
    o = {"name": team, "description": side} if swap else {"name": side, "description": team}
    return {**o, "price": price, "point": point,
            "link": f"https://{book}/{side.lower()}/{point}", "sid": f"{book}-{side}-{point}"}


def book(key, rungs, team=HOME_NAME, updated="2026-11-05T23:33:12Z", swap=False,
         market_update=True):
    """A bookmaker block: `rungs` (line, over, under) for `team`."""
    outs = []
    for line, over, under in rungs:
        if over is not None:
            outs.append(outcome("Over", team, line, over, key, swap))
        if under is not None:
            outs.append(outcome("Under", team, line, under, key, swap))
    mk = {"key": "team_totals", "outcomes": outs}
    if market_update:
        mk["last_update"] = updated
    return {"key": key, "title": key, "last_update": "2026-11-05T23:30:00Z", "markets": [mk]}


def event(home=HOME_NAME, away=AWAY_NAME, tip=TIP, ev_id="ev-mil"):
    return {"id": ev_id, "sport_key": "basketball_nba",
            "commence_time": tip.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "home_team": home, "away_team": away}


class FakeResp:
    def __init__(self, headers):
        self.headers = headers


class FakeFeed:
    """_list_events and _get_event_odds: recorded shapes, each call billed
    through odds_quota exactly as the real ones record it, and `call_s` on
    the clock."""

    def __init__(self, clock, events, bodies, last="1", call_s=2.0, fail=()):
        self.clock, self.events, self.bodies = clock, events, bodies
        self.last, self.call_s, self.fail = last, call_s, set(fail)
        self.calls: list[tuple] = []
        self.used = 1000

    def _bill(self, cost):
        self.used += int(cost)
        odds_quota.record_quota_headers(FakeResp({
            "x-requests-used": str(self.used), "x-requests-remaining": "2000000",
            "x-requests-last": str(cost)}))

    def list_events(self, sport_key):
        self.calls.append(("events", sport_key))
        self.clock.tick(self.call_s)
        self._bill("0")
        return self.events

    def event_odds(self, sport_key, event_id, markets, bookmakers=None):
        self.calls.append(("event_odds", event_id, tuple(markets)))
        self.clock.tick(self.call_s)
        if event_id in self.fail:
            raise RuntimeError("HTTP 500")
        self._bill(self.last)
        body = self.bodies.get(event_id)
        return None if body is None else {"id": event_id, "bookmakers": body}

    def install(self, monkeypatch, db=None):
        """Patch the feed's two calls; with `db`, each call is also written to
        db.log, so a test can see what the connection was doing around it."""
        def logged(fn, which):
            def call(*a, **k):
                if db is not None:
                    db.log.append(("api", which))
                return fn(*a, **k)
            return call
        monkeypatch.setattr(feed, "_list_events", logged(self.list_events, "events"))
        monkeypatch.setattr(feed, "_get_event_odds", logged(self.event_odds, "event_odds"))


FANDUEL_LADDER = [(112.5, -150, +120), (113.5, -115, -105), (114.5, +100, -125)]


def world(monkeypatch, bodies=None, events=None, games=None, **kw):
    clock = Clock(et(2026, 11, 5, 18, 34, 0))
    db = FakeDB(clock, games={GID: ("MIL", "BOS")} if games is None else games)
    f = FakeFeed(clock, [event()] if events is None else events,
                 {"ev-mil": [book("fanduel", FANDUEL_LADDER),
                             book("pinnacle", [(113.5, -108, -108)])]}
                 if bodies is None else bodies, **kw)
    f.install(monkeypatch, db)
    return clock, db, f


# ── parsing: home or away, exactly the purchase's rule ───────────────────────

def test_home_and_away_are_read_off_the_description():
    """RULE: the side is whichever of name/description says Over or Under, the
    team the other (nba_odds_history.parse_derivatives)."""
    b = {"key": "team_totals", "outcomes": [
        outcome("Over", HOME_NAME, 113.5, -110), outcome("Under", HOME_NAME, 113.5, -110),
        outcome("Over", AWAY_NAME, 111.5, -105), outcome("Under", AWAY_NAME, 111.5, -115)]}
    rows = {r["market"]: r for r in feed.parse_team_totals([b], "MIL", "BOS")}
    assert set(rows) == {"team_totals_home", "team_totals_away"}
    assert (rows["team_totals_home"]["total_line"], rows["team_totals_away"]["total_line"]) == (
        113.5, 111.5)
    assert (rows["team_totals_away"]["over_price"], rows["team_totals_away"]["under_price"]) == (
        -105, -115)


def test_a_payload_with_name_and_description_swapped_reads_the_same():
    plain = feed.parse_team_totals(book("fanduel", FANDUEL_LADDER)["markets"], "MIL", "BOS")
    swapped = feed.parse_team_totals(book("fanduel", FANDUEL_LADDER, swap=True)["markets"],
                                     "MIL", "BOS")
    key = lambda r: (r["market"], r["total_line"])   # noqa: E731
    assert sorted(plain, key=key) == sorted(swapped, key=key) and len(plain) == 3
    assert {r["market"] for r in swapped} == {"team_totals_home"}


def test_a_team_that_is_neither_side_is_dropped_and_named():
    unknown: set = set()
    rows = feed.parse_team_totals(book("fanduel", FANDUEL_LADDER, team="Los Angeles Lakers")
                                  ["markets"], "MIL", "BOS", unknown)
    assert rows == [] and unknown == {"Los Angeles Lakers"}
    junk = feed.parse_team_totals(book("fanduel", FANDUEL_LADDER, team="Team Nobody")
                                  ["markets"], "MIL", "BOS", unknown)
    assert junk == [] and "Team Nobody" in unknown


def test_links_and_sids_are_kept():
    rows = feed.parse_team_totals(book("fanduel", FANDUEL_LADDER)["markets"], "MIL", "BOS")
    r = next(x for x in rows if x["total_line"] == 113.5)
    assert r["over_link"] == "https://fanduel/over/113.5"
    assert r["under_link"] == "https://fanduel/under/113.5"
    assert (r["over_sid"], r["under_sid"]) == ("fanduel-Over-113.5", "fanduel-Under-113.5")


def test_the_ladder_is_split_main_number_and_alternates():
    """RULE: each book's main rung (closest to even) keeps the market's own name;
    every other rung is stored as an alternate, so every one-row-per-book
    reader lands on the main number."""
    fetched = et(2026, 11, 5, 18, 34, 5)
    main, alt, ages = feed.event_rows({"bookmakers": [book("fanduel", FANDUEL_LADDER)]},
                                      GID, "MIL", "BOS", "open", fetched)
    assert [(r["market"], r["total_line"]) for r in main] == [("team_totals_home", 113.5)]
    assert sorted((r["market"], r["total_line"]) for r in alt) == [
        ("team_totals_home_alternate", 112.5), ("team_totals_home_alternate", 114.5)]
    r = main[0]
    assert (r["under_price"], r["under_link"], r["under_sid"]) == (
        -105, "https://fanduel/under/113.5", "fanduel-Under-113.5")
    assert ages == {"fanduel": round((fetched - et(2026, 11, 5, 18, 33, 12)).total_seconds() / 60, 1)}


def test_snapshot_at_is_the_market_s_stamp_then_the_book_s_then_the_fetch():
    fetched = et(2026, 11, 5, 18, 34, 5)
    m, _, _ = feed.event_rows({"bookmakers": [book("fanduel", FANDUEL_LADDER)]},
                              GID, "MIL", "BOS", "open", fetched)
    assert m[0]["snapshot_at"] == "2026-11-05T23:33:12Z"
    b = book("fanduel", FANDUEL_LADDER, market_update=False)
    m, _, _ = feed.event_rows({"bookmakers": [b]}, GID, "MIL", "BOS", "open", fetched)
    assert m[0]["snapshot_at"] == "2026-11-05T23:30:00Z"
    b.pop("last_update")
    m, _, _ = feed.event_rows({"bookmakers": [b]}, GID, "MIL", "BOS", "open", fetched)
    assert m[0]["snapshot_at"] == "2026-11-05T23:34:05Z"


def test_no_row_ever_carries_the_purchase_s_source_marker(monkeypatch):
    """RULE: the live rows are never read as a purchase. nba_odds_history
    _deriv_done skips a game holding any row whose source starts with the
    purchase's marker, so a live row with it would stop that game ever being
    bought. Evaluated with SQL LIKE semantics ('_' is a wildcard)."""
    from data.ingestors import nba_odds_history as hist
    _, db, _ = world(monkeypatch)
    feed.fetch_team_totals([GID], "open", conn=db)
    assert db.rows["odds"] and {r["source"] for r in db.rows["odds"]} == {feed.SOURCE}
    assert not _like(hist.SOURCE_PREFIX + "%", feed.SOURCE)
    assert hist._deriv_done(db, [GID]) == set(), "a live fetch reads as a purchase"
    db.rows["odds"].append({**db.rows["odds"][0], "source": hist.DERIV_SOURCE})
    assert hist._deriv_done(db, [GID]) == {GID}, "the fake must see a real purchase"


# ── the fetch: exactly the planned games, stored first ───────────────────────

def test_only_the_named_games_are_bought_matched_before_any_paid_call(monkeypatch):
    """RULE: a tick buys exactly the games it planned. Ten events listed, two
    games asked for, one of them not in `games`: one event call, for the right
    event, and the listed-but-unasked games cost nothing."""
    others = [event(home=h, away=a, ev_id=f"ev-{i}")
              for i, (h, a) in enumerate([("Boston Celtics", "Miami Heat"),
                                          ("Denver Nuggets", "Utah Jazz"),
                                          ("Chicago Bulls", "Detroit Pistons"),
                                          ("Orlando Magic", "Atlanta Hawks"),
                                          ("Phoenix Suns", "Sacramento Kings"),
                                          ("Dallas Mavericks", "Houston Rockets"),
                                          ("Golden State Warriors", "Portland Trail Blazers"),
                                          ("New York Knicks", "Brooklyn Nets"),
                                          ("Toronto Raptors", "Indiana Pacers")])]
    _, db, f = world(monkeypatch, events=[event(), *others])
    out = feed.fetch_team_totals([GID, "NBA_2026-11-05_MIA_BOS_NOT_A_GAME"], conn=db)
    assert [c for c in f.calls if c[0] == "event_odds"] == [
        ("event_odds", "ev-mil", ("team_totals",))]
    assert out["fetched"] == [GID] and out["not_in_games"] == ["NBA_2026-11-05_MIA_BOS_NOT_A_GAME"]


def test_a_game_with_no_draftkings_team_total_is_still_stored(monkeypatch):
    """RULE: DraftKings was the book on 85 of 349 graded bets. The refresh
    pass's parser drops an event DraftKings does not list; this feed stores
    every line-shop book's team total."""
    _, db, _ = world(monkeypatch)
    out = feed.fetch_team_totals([GID], "open", conn=db)
    main = [r for r in db.rows["odds"] if r["market"] == "team_totals_home"]
    assert {r["bookmaker"] for r in main} == {"fanduel", "pinnacle"}
    assert out["rows"] == 4 and out["main_rows"] == 2 and out["failed"] == []
    assert all(r["snapshot_type"] == "open" and r["game_id"] == GID for r in db.rows["odds"])


def test_each_game_s_rows_are_dated_after_its_own_call(monkeypatch):
    """RULE: created_at is the fetch instant. Postgres fixes now() at a
    transaction's first statement, so no statement may run between one
    game's commit and the next call, and the games read must be ended before
    the first call. Each game's rows and ledger row carry an instant after its
    own response, and the two agree."""
    second = event(home="Denver Nuggets", away="Utah Jazz", ev_id="ev-den")
    gid2 = "NBA_2026-11-05_UTA_DEN"
    bodies = {"ev-mil": [book("fanduel", FANDUEL_LADDER)],
              "ev-den": [book("betmgm", [(118.5, -110, -110)], team="Denver Nuggets")]}
    clock, db, f = world(monkeypatch, bodies=bodies, events=[event(), second],
                         games={GID: ("MIL", "BOS"), gid2: ("DEN", "UTA")}, call_s=30.0)
    start = clock()
    feed.fetch_team_totals([GID, gid2], "open", conn=db)
    for gid, n in ((GID, 1), (gid2, 2)):
        answered = start + timedelta(seconds=30.0 * (n + 1))     # the list, then each call
        created = {_ts(r["created_at"]) for r in db.rows["odds"] if r["game_id"] == gid}
        assert created == {answered}, (gid, created, answered)
        led = [r for r in db.rows[feed.LEDGER_TABLE]
               if r["game_id"] == gid and r["endpoint"] == feed.EVENT_ODDS]
        assert [r["fetch_at"] for r in led] == [answered]
    # no transaction is open across any call
    for i, entry in enumerate(db.log):
        if entry[0] == "api":
            last_db = next(e for e in reversed(db.log[:i]) if e[0] != "api")
            assert last_db[0] in ("commit", "rollback"), db.log[max(0, i - 3):i + 1]


def test_the_ledger_records_every_call_its_credits_and_its_failures(monkeypatch):
    """RULE: the cost is read off the feed's x-requests-last, never assumed;
    a failed call is recorded as failed and the run says so; a call that came
    back with no team total is a fetch that offered nothing."""
    gid2, gid3 = "NBA_2026-11-05_UTA_DEN", "NBA_2026-11-05_ATL_ORL"
    events = [event(), event(home="Denver Nuggets", away="Utah Jazz", ev_id="ev-den"),
              event(home="Orlando Magic", away="Atlanta Hawks", ev_id="ev-orl")]
    bodies = {"ev-mil": [book("fanduel", FANDUEL_LADDER)], "ev-orl": []}
    _, db, f = world(monkeypatch, bodies=bodies, events=events, last="3", fail={"ev-den"},
                     games={GID: ("MIL", "BOS"), gid2: ("DEN", "UTA"), gid3: ("ORL", "ATL")})
    out = feed.fetch_team_totals([GID, gid2, gid3], "open", conn=db)
    led = {(r["endpoint"], r["game_id"]): r for r in db.rows[feed.LEDGER_TABLE]}
    assert led[("events", None)]["ok"] and led[("events", None)]["credits_last"] == 0.0
    ok = led[("event_odds", GID)]
    assert ok["ok"] and ok["rows_stored"] == 3 and ok["main_rows"] == 1
    assert ok["credits_last"] == 3.0 and ok["books"] == "fanduel"
    assert '"fanduel"' in ok["book_ages"]
    assert not led[("event_odds", gid2)]["ok"] and "HTTP 500" in led[("event_odds", gid2)]["detail"]
    nothing = led[("event_odds", gid3)]
    assert nothing["ok"] and nothing["rows_stored"] == 0
    assert out["failed"] == [gid2] and out["no_team_total"] == [gid3]
    assert out["credits"][GID] == 3.0


def test_a_game_missing_from_the_event_list_is_a_failed_call(monkeypatch):
    _, db, f = world(monkeypatch, events=[])
    out = feed.fetch_team_totals([GID], "open", conn=db)
    assert out["failed"] == [GID] and [c[0] for c in f.calls] == ["events"]
    row = [r for r in db.rows[feed.LEDGER_TABLE] if r["game_id"] == GID][0]
    assert not row["ok"] and "event list" in row["detail"]


@pytest.mark.parametrize("status", [404, 422])
@pytest.mark.parametrize("kind", ["open", "close"])
def test_an_http_404_or_422_is_a_failed_call_not_a_fetch(monkeypatch, kind, status):
    """RULE: the real _get_event_odds returns None for an HTTP 404 or 422 (the
    event or the request refused), not a body with no bookmakers. That is a
    failed call: the run says so, the ledger row is not ok, and nothing
    downstream counts it -- no decision fetch for the card, no close taken.
    Watched failing when it was stored as an ok fetch that offered nothing."""
    from data.ingestors import odds_ingestor

    class Resp:
        status_code = status
        headers = {"x-requests-used": "1001", "x-requests-remaining": "2000000",
                   "x-requests-last": "0"}

    asked = []
    monkeypatch.setattr(odds_ingestor, "ODDS_API_KEY", "not-a-key")
    monkeypatch.setattr(odds_ingestor.requests, "get",
                        lambda url, params=None, timeout=None: asked.append(url) or Resp())
    _, db, f = world(monkeypatch)
    monkeypatch.setattr(feed, "_get_event_odds", odds_ingestor._get_event_odds)
    out = feed.fetch_team_totals([GID], kind, conn=db)
    assert len(asked) == 1 and "/events/ev-mil/odds" in asked[0], "the real call must run"
    assert out["failed"] == [GID] and out["fetched"] == [] and out["no_team_total"] == []
    [row] = [r for r in db.rows[feed.LEDGER_TABLE] if r["game_id"] == GID]
    assert not row["ok"] and "404 or 422" in row["detail"]
    assert db.rows["odds"] == []
    assert feed.fetches(db, [GID], "open") == {} and feed.closes_taken(db, [GID]) == set()


def test_the_close_is_filed_close_in_the_same_shape(monkeypatch):
    _, db, _ = world(monkeypatch)
    feed.fetch_team_totals([GID], "close", conn=db)
    assert {r["snapshot_type"] for r in db.rows["odds"]} == {"close"}
    assert {r["market"] for r in db.rows["odds"]} == {"team_totals_home",
                                                      "team_totals_home_alternate"}
    assert feed.closes_taken(db, [GID]) == {GID}
    assert feed.fetches(db, [GID], "open") == {}, "a close is never a decision fetch"
    with pytest.raises(ValueError):
        feed.fetch_team_totals([GID], "in_play", conn=db)


def test_the_quota_telemetry_carries_each_call_s_own_cost():
    before = odds_quota.latest()
    odds_quota.record_quota_headers(FakeResp({"x-requests-used": "10",
                                              "x-requests-remaining": "5",
                                              "x-requests-last": "2"}))
    after = odds_quota.latest()
    assert after is not before and after["last"] == 2.0
    odds_quota.record_quota_headers(FakeResp({}))
    assert odds_quota.latest() is after, "a response with no headers records nothing"


# ── the prune keeps the ladders ──────────────────────────────────────────────

def test_the_prune_protects_every_ladder_source_by_its_writer_s_own_name():
    """RULE: the pruner keeps one row per (game, market, book), which thins a
    ladder to arbitrary rungs. The live team totals and the two paid ladder
    purchases are protected, named exactly as their writers stamp them."""
    from data import prune_odds
    from data.ingestors import nba_odds_history, nhl_derivative_odds_history
    for src in (feed.SOURCE, nba_odds_history.DERIV_SOURCE, nba_odds_history.ALT_SOURCE,
                nhl_derivative_odds_history.SOURCE):
        assert src in prune_odds.PROTECTED_SOURCES, src
        params: dict = {}
        prune_odds._unprotected(params, table="odds")
        assert src in params["protected_sources"]


def test_both_ledgers_are_declared_worker_only():
    """RULE: the fetch ledger and the decisions ledger are worker-only
    (data/anon_readable.WORKER_ONLY_TABLES), so the admin sweep and its
    read-backs check them. Their lock_down calls name them through a constant,
    which tests/test_anon_readable's literal-target check cannot see."""
    from data.anon_readable import WORKER_ONLY_TABLES
    from scripts.nba_team_total_luck_card import DECISIONS_TABLE
    assert feed.LEDGER_TABLE in WORKER_ONLY_TABLES
    assert DECISIONS_TABLE in WORKER_ONLY_TABLES

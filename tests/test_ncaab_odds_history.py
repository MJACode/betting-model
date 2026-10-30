"""data/ingestors/ncaab_odds_history: what the NCAAB price purchase asks for and keeps.

mike approved it on 2026-10-26 ("3 approved"): game lines 2020-21..2025-26 and
first-half + team-total lines 2023-24..2025-26 at the close and the open, about
1.75M credits together. These pin what decides the spend (the snapshot plan,
the precondition, the ledger resume, the floor), what keeps paid data from
being lost (unmatched events stored, flipped events stored in ESPN's
orientation), and the worker jobs that run it.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pytest

import tracking.job_queue as jq
from data.ingestors import nba_odds_history
from data.ingestors import ncaab_odds_history as h
from data.ingestors import odds_ingestor as oi

ROOT = Path(__file__).resolve().parent.parent


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ── a small world: three teams, two ESPN games ──────────────────────────────

REGISTRY = [
    {"espn_id": 150, "school": "Duke", "slug": "duke", "mascot": "Blue Devils",
     "display_name": "Duke Blue Devils", "short_name": "Duke", "abbreviation": "DUKE",
     "is_d1": True, "alt": []},
    {"espn_id": 96, "school": "Kentucky", "slug": "kentucky", "mascot": "Wildcats",
     "display_name": "Kentucky Wildcats", "short_name": "Kentucky", "abbreviation": "UK",
     "is_d1": True, "alt": []},
    {"espn_id": 2306, "school": "Kansas State", "slug": "kansas-state", "mascot": "Wildcats",
     "display_name": "Kansas State Wildcats", "short_name": "Kansas St", "abbreviation": "KSU",
     "is_d1": True, "alt": []},
]
# ESPN's orientation: Kentucky is HOME against Duke (a neutral-site game the
# feed lists the other way round), Kansas State home against Duke two days on.
UK_DUKE = {"game_id": "NCAAB_2025-11-18_duke_kentucky", "game_date": "2025-11-18",
           "commence_time": "2025-11-19T00:30Z", "home_espn_id": 96, "away_espn_id": 150}
KSU_DUKE = {"game_id": "NCAAB_2025-11-20_duke_kansas-state", "game_date": "2025-11-20",
            "commence_time": "2025-11-20T17:00Z", "home_espn_id": 2306, "away_espn_id": 150}
GAMES = [UK_DUKE, KSU_DUKE]


def _event(eid, home, away, tip, home_pt=-4.5, book="fanduel", last_update=None):
    mk = {"last_update": last_update} if last_update else {}
    return {"id": eid, "commence_time": tip, "home_team": home, "away_team": away,
            "bookmakers": [{"key": book, "markets": [
                {"key": "h2h", **mk, "outcomes": [{"name": home, "price": -190},
                                                  {"name": away, "price": 160}]},
                {"key": "spreads", **mk, "outcomes": [
                    {"name": home, "price": -108, "point": home_pt},
                    {"name": away, "price": -112, "point": -home_pt}]},
                {"key": "totals", **mk, "outcomes": [
                    {"name": "Over", "price": -110, "point": 149.5},
                    {"name": "Under", "price": -110, "point": 149.5}]}]}]}


def contract_process_events(events, sport, snapshot_type, snapshot_at,
                            include_3way=False, resolve_game_id=None):
    """_process_events as the NCAAB contract specifies it (the other piece's
    change): the resolver's (game_id, flipped) is used as given, a flipped
    event is parsed with its names swapped, and no DraftKings gate."""
    rows = []
    for ev in events:
        hit = resolve_game_id(ev.get("home_team", ""), ev.get("away_team", ""),
                              ev.get("commence_time", ""))
        if not hit:
            continue
        gid, flipped = hit
        home = ev["away_team"] if flipped else ev["home_team"]
        for b in ev.get("bookmakers", []):
            for m in b.get("markets", []):
                row = dict.fromkeys(nba_odds_history._ODDS_KEYS)
                row.update({"game_id": gid, "sport": sport, "bookmaker": b["key"],
                            "snapshot_type": snapshot_type, "market": m["key"],
                            "snapshot_at": m.get("last_update", snapshot_at)})
                if m["key"] == "h2h":
                    row.update(oi._parse_outcomes(m["outcomes"], sport, home))
                elif m["key"] == "spreads":
                    row.update(oi._parse_spread_outcomes(m["outcomes"], home))
                else:
                    row.update(oi._parse_total_outcomes(m["outcomes"]))
                rows.append(row)
    return [], rows


class FakeConn:
    """Records every statement; answers SELECTs from `answers` by substring."""

    def __init__(self, answers: dict | None = None, held: bool = False):
        self.sql: list[tuple[str, object]] = []
        self.many: list[tuple[str, list]] = []
        self.commits = 0
        self.answers = answers or {}
        self.held = held
        self._last = ""

    def execute(self, sql, params=None):
        q = " ".join(sql.split())
        self.sql.append((q, params))
        self._last = q
        for needle, ans in self.answers.items():
            if needle in q and isinstance(ans, Exception):
                raise ans
        return self

    def executemany(self, sql, rows):
        self.many.append((" ".join(sql.split()), list(rows)))

    def fetchone(self):
        return (1,) if self.held and "odds_history_pulls" in self._last else None

    def fetchall(self):
        for needle, ans in self.answers.items():
            if needle in self._last:
                return ans
        return []

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


class Resp:
    def __init__(self, status=200, body=None, last="30", remaining="2000000"):
        self.status_code, self._body = status, body if body is not None else {}
        self.headers = {"x-requests-last": last, "x-requests-remaining": remaining}

    def json(self):
        return self._body


class FakeMeter(nba_odds_history.Meter):
    """The real Meter's accounting, with the HTTP call replaced."""

    def __init__(self, answer, ceiling=10_000, floor=0):
        super().__init__(ceiling, floor)
        self.answer, self.calls = answer, []

    def get(self, url, params):
        self.calls.append((url, dict(params)))
        r = self.answer(url, params)
        self.spent += int(r.headers.get("x-requests-last") or 0)
        self.remaining = int(r.headers.get("x-requests-remaining"))
        return r


# ── the snapshot plan ────────────────────────────────────────────────────────

def test_each_game_date_gets_its_opener_its_morning_and_an_hour_before_every_tip():
    games = [{"game_date": "2026-01-17", "commence_time": "2026-01-17T17:00Z"},   # noon ET
             {"game_date": "2026-01-17", "commence_time": "2026-01-17T19:04Z"},
             {"game_date": "2026-01-17", "commence_time": "2026-01-17T19:05Z"},
             {"game_date": "2026-01-17", "commence_time": "2026-01-18T03:30Z"}]   # 10:30 PT
    got = h.line_snapshots(games)
    assert got == sorted(set(got), reverse=True)                 # each once, newest first
    assert set(got) == {_t("2026-01-16T22:00Z"),                  # the evening-before opener
                        _t("2026-01-17T15:00Z"),                  # the morning
                        _t("2026-01-17T16:00Z"),                  # 17:00 tip -> 60 min out
                        _t("2026-01-17T18:00Z"),                  # 19:04 tip -> 64 min out
                        _t("2026-01-17T19:00Z"),                  # 19:05 tip -> 5 min out
                        _t("2026-01-18T03:00Z")}                  # the late West tip
    for g in games:                                               # 5..65 minutes before each tip
        tip = _t(g["commence_time"])
        assert any(300 <= (tip - w).total_seconds() <= 3900 for w in got)


def test_dates_that_share_an_hour_share_the_snapshot():
    # a 22:05Z tip on D-1 asks for D-1 22Z, which is D's opener too
    games = [{"game_date": "2026-01-16", "commence_time": "2026-01-16T22:05Z"},
             {"game_date": "2026-01-17", "commence_time": "2026-01-17T22:05Z"}]
    got = h.line_snapshots(games)
    assert got.count(_t("2026-01-16T22:00Z")) == 1
    assert len(got) == len(set(got)) == 5        # 3 + 3 less the shared 2026-01-16 22Z
    assert set(got) == {_t("2026-01-15T22:00Z"), _t("2026-01-16T15:00Z"), _t("2026-01-16T22:00Z"),
                        _t("2026-01-17T15:00Z"), _t("2026-01-17T22:00Z")}


def test_a_game_with_no_stored_tip_gets_the_opener_and_the_morning_only():
    assert h.line_snapshots([{"game_date": "2026-03-01", "commence_time": None}]) == [
        _t("2026-03-01T15:00Z"), _t("2026-02-28T22:00Z")]


# ── the precondition ─────────────────────────────────────────────────────────

def test_the_purchase_refuses_a_season_whose_schedule_is_not_stored():
    conn = FakeConn({"FROM games": [(2025, 6100), (2026, 1200)],
                     "FROM ncaab_events": [(2025, 6300), (2026, 6400)]})
    with pytest.raises(h.PreconditionError, match="2026: 1,200 scored games"):
        h.check_precondition(conn, [2025, 2026])


def test_the_purchase_refuses_a_season_with_scores_but_no_event_map():
    conn = FakeConn({"FROM games": [(2025, 6100)], "FROM ncaab_events": []})
    with pytest.raises(h.PreconditionError, match="0 ncaab_events rows"):
        h.check_precondition(conn, [2025])


def test_an_unreadable_schedule_raises_rather_than_warns():
    conn = FakeConn({"FROM ncaab_events": RuntimeError('relation "ncaab_events" does not exist')})
    with pytest.raises(h.PreconditionError, match="unreadable"):
        h.check_precondition(conn, [2025])


def test_a_stored_schedule_passes_and_is_reported():
    conn = FakeConn({"FROM games": [(2021, 4285)], "FROM ncaab_events": [(2021, 5282)]})
    assert h.check_precondition(conn, [2021]) == {2021: (4285, 5282)}


def test_the_precondition_counts_only_scored_ncaab_games_of_the_asked_seasons():
    """The spec's bar is scored rows: an unplayed schedule would pass a bare count."""
    conn = FakeConn({"FROM games": [(2021, 4285)], "FROM ncaab_events": [(2021, 5282)]})
    h.check_precondition(conn, [2021])
    (q, params), = [(q, p) for q, p in conn.sql if "FROM games" in q]
    assert "sport = 'NCAAB'" in q and "home_score IS NOT NULL" in q and "season = ANY(%s)" in q
    assert params == ([2021],)
    (q, params), = [(q, p) for q, p in conn.sql if "FROM ncaab_events" in q]
    assert "season = ANY(%s)" in q and params == ([2021],)


class RegistryConn(FakeConn):
    """Answers the ncaab_teams read the way the real table would."""
    ROWS = [(150, "Duke", "duke", "Blue Devils", "Duke Blue Devils", "Duke", "DUKE", True, ""),
            (96, "Kentucky", "kentucky", "Wildcats", "Kentucky Wildcats", "Kentucky", "UK", True, "")]

    def __init__(self):
        super().__init__({"FROM ncaab_teams": self.ROWS})


def test_a_purchase_reads_the_registry_fresh_not_an_empty_cache(monkeypatch):
    """REVIEW 2026-10-26. The worker runs every job in one process and
    ncaab_teams.load_registry caches what it read first, an empty list too.
    The declared feed probe runs before the ESPN backfill creates the table, so
    a cached [] would make the lines purchase behind the backfill refuse three
    times and end failed."""
    from data.ingestors import ncaab_teams as nt
    monkeypatch.setattr(nt, "_TEAM_CACHE", [])            # what the earlier probe left
    resolver = h._resolver(RegistryConn(), GAMES)
    assert {t["espn_id"] for t in resolver.registry} == {150, 96}
    monkeypatch.setattr(nt, "_TEAM_CACHE", [])
    with pytest.raises(h.PreconditionError, match="ncaab_teams is empty"):
        h._resolver(FakeConn(), GAMES)                    # a genuinely empty table still refuses


def test_the_lines_purchase_checks_before_it_touches_the_feed(monkeypatch):
    monkeypatch.setattr(h, "check_precondition",
                        lambda conn, seasons: (_ for _ in ()).throw(h.PreconditionError("no")))
    meter = FakeMeter(lambda u, p: pytest.fail("a paid call before the precondition"))
    with pytest.raises(h.PreconditionError):
        h.buy_lines(FakeConn(), meter, 2021, 2026)
    with pytest.raises(h.PreconditionError):
        h.buy_derivatives(FakeConn(), meter, 2024, 2026, "close")
    assert meter.calls == []


# ── the _process_events contract, checked for free before paying ─────────────

def test_the_contract_check_passes_a_function_that_honours_it(monkeypatch):
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    h.check_process_events_contract()


def _tuple_as_id(events, sport, st, snap, include_3way=False, resolve_game_id=None):
    _, rows = contract_process_events(events, sport, st, snap,
                                      resolve_game_id=lambda *a: (resolve_game_id(*a)[0], False))
    for r in rows:
        r["game_id"] = resolve_game_id("", "", "")        # today's `game_id = resolved`
    return [], rows


def _no_flip(events, sport, st, snap, include_3way=False, resolve_game_id=None):
    return contract_process_events(events, sport, st, snap,
                                   resolve_game_id=lambda *a: (resolve_game_id(*a)[0], False))


def _dk_gated(events, sport, st, snap, include_3way=False, resolve_game_id=None):
    kept = [e for e in events if any(b["key"] == "draftkings" for b in e["bookmakers"])]
    return contract_process_events(kept, sport, st, snap, resolve_game_id=resolve_game_id)


@pytest.mark.parametrize("broken,why", [(_tuple_as_id, "game_id"), (_no_flip, "flipped"),
                                        (_dk_gated, "DraftKings")])
def test_the_contract_check_refuses_each_way_of_breaking_it(monkeypatch, broken, why):
    monkeypatch.setattr(h, "_process_events", broken)
    with pytest.raises(h.ContractError, match=why):
        h.check_process_events_contract()


def test_the_real_process_events_honours_the_ncaab_contract():
    """CROSS-PIECE. Fails until the change teaching odds_ingestor._process_events
    the (game_id, flipped) resolver and the NCAAB DraftKings exemption lands;
    the lines purchase refuses to spend until it passes."""
    h.check_process_events_contract()


# ── buying one snapshot ──────────────────────────────────────────────────────

def _snapshot(monkeypatch, events, when="2025-11-19T00:00:00Z", held=False,
              process=contract_process_events, tips=None):
    inserted = []
    monkeypatch.setattr(h, "_process_events", process)
    monkeypatch.setattr(h, "_insert_odds", lambda conn, rows: inserted.extend(rows))
    conn = FakeConn(held=held)
    meter = FakeMeter(lambda u, p: Resp(body={"timestamp": "2025-11-18T23:55:38Z",
                                              "data": events}))
    stats = defaultdict(int)
    if tips is None:
        tips = {g["game_id"]: g["commence_time"] for g in GAMES}
    ok = h._buy_snapshot(conn, meter, tips, h.EventResolver(REGISTRY, GAMES), _t(when), stats)
    return ok, conn, meter, stats, inserted


def _raw_kept(conn) -> list[tuple]:
    return [row for q, rows in conn.many if "ncaab_odds_unmatched" in q for row in rows]


def test_the_parser_gets_the_resolver_itself_not_a_lookup_of_exact_strings(monkeypatch):
    """REVIEW 2026-10-26. The parser is another piece's code; if it hands the
    resolver the start in any other form than the feed's string, a lookup keyed
    on that string misses and the event is neither stored nor kept raw, in a
    snapshot the ledger then marks bought for good."""
    def reformatting(events, sport, st, snap, include_3way=False, resolve_game_id=None):
        def as_offset(h_, a_, c_):
            return resolve_game_id(h_, a_, c_.replace("Z", "+00:00"))
        return contract_process_events(events, sport, st, snap, resolve_game_id=as_offset)
    ev = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T00:30:00Z")
    ok, conn, meter, stats, rows = _snapshot(monkeypatch, [ev], process=reformatting)
    assert ok and stats["odds_rows"] == 3
    assert {r["game_id"] for r in rows} == {UK_DUKE["game_id"]}


def test_a_resolved_event_the_parser_drops_is_kept_raw_not_lost(monkeypatch):
    """REVIEW 2026-10-26. A resolved event that carried prices and produced no
    row (any filter inside the parser) is kept raw: the snapshot is ledgered
    and never bought again, so dropping it would lose paid data."""
    def drops_everything(events, sport, st, snap, include_3way=False, resolve_game_id=None):
        for ev in events:
            resolve_game_id(ev["home_team"], ev["away_team"], ev["commence_time"])
        return [], []
    ev = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T00:30:00Z")
    ok, conn, meter, stats, rows = _snapshot(monkeypatch, [ev], process=drops_everything)
    assert ok and rows == [] and stats["dropped_by_parser"] == 1
    assert stats.get("unmatched_events", 0) == 0          # it DID resolve
    (stored,) = _raw_kept(conn)
    assert stored[1] == "e1" and json.loads(stored[5]) == ev
    assert any(q.startswith("INSERT INTO odds_history_pulls") for q, _ in conn.sql)


def test_a_resolved_event_with_no_prices_is_not_kept_raw(monkeypatch):
    ev = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T00:30:00Z")
    ev["bookmakers"] = []
    ok, conn, meter, stats, rows = _snapshot(monkeypatch, [ev])
    assert ok and _raw_kept(conn) == [] and stats.get("dropped_by_parser", 0) == 0


def test_a_stored_tip_without_an_offset_is_read_as_utc_not_a_crash(monkeypatch):
    """REVIEW 2026-10-26. ESPN's tip is stored by another piece; one without an
    offset met an aware snapshot stamp in _mark_in_play and raised TypeError
    AFTER the paid call, so the snapshot was never ledgered and every retry
    paid for it again."""
    ev = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T01:30:00Z",
                last_update="2025-11-19T00:45:00Z")
    ok, conn, meter, stats, rows = _snapshot(
        monkeypatch, [ev], when="2025-11-19T01:00:00Z",
        tips={UK_DUKE["game_id"]: "2025-11-19T00:30:00"})
    assert ok and stats["marked_in_play"] == 3


def test_a_flipped_event_is_stored_at_espn_s_home_number(monkeypatch):
    # The feed calls Duke home; ESPN has Kentucky home. Duke -4.5 is Kentucky +4.5.
    ev = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T00:30:00Z")
    ok, conn, meter, stats, rows = _snapshot(monkeypatch, [ev])
    assert ok and stats["odds_rows"] == 3 and stats.get("unmatched_events", 0) == 0
    by = {r["market"]: r for r in rows}
    assert {r["game_id"] for r in rows} == {UK_DUKE["game_id"]}
    assert by["spreads"]["spread_home"] == 4.5 and by["spreads"]["home_price"] == -112
    assert (by["h2h"]["home_price"], by["h2h"]["away_price"]) == (160, -190)
    assert all(r["source"] == oi.HISTORICAL_ODDS_SOURCE for r in rows)
    url, params = meter.calls[0]
    assert url.endswith("/basketball_ncaab/odds") and params["date"] == "2025-11-19T00:00:00Z"
    assert params["markets"] == "h2h,spreads,totals" and params["bookmakers"] == h.BOOKS


def test_an_event_that_resolves_onto_no_game_is_stored_raw_not_dropped(monkeypatch):
    lost = _event("e9", "Mystery Moose", "Duke Blue Devils", "2025-11-19T00:30:00Z")
    good = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T00:30:00Z")
    ok, conn, meter, stats, rows = _snapshot(monkeypatch, [lost, good])
    assert ok and stats["unmatched_events"] == 1 and stats["odds_rows"] == 3
    (sql, stored), = [(q, r) for q, r in conn.many if "ncaab_odds_unmatched" in q]
    snap, eid, home, away, tip, payload, source = stored[0]
    assert (eid, home, away, source) == ("e9", "Mystery Moose", "Duke Blue Devils",
                                         oi.HISTORICAL_ODDS_SOURCE)
    assert snap == "2025-11-18T23:55:38Z" and json.loads(payload) == lost
    # written in the same transaction as the ledger row, which commits last
    ledger = [i for i, (q, _) in enumerate(conn.sql) if q.startswith("INSERT INTO odds_history_pulls")]
    assert ledger and conn.commits == 1
    resolver_report = h.EventResolver(REGISTRY, GAMES)
    resolver_report.split([lost])
    assert "Mystery Moose (1)" in resolver_report.report()


def test_a_price_after_espn_s_tip_is_labelled_in_play(monkeypatch):
    # The feed's own start says 01:30Z, ESPN says 00:30Z: ESPN's schedule decides.
    ev = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T01:30:00Z",
                last_update="2025-11-19T00:45:00Z")
    ok, conn, meter, stats, rows = _snapshot(monkeypatch, [ev], when="2025-11-19T01:00:00Z")
    assert stats["marked_in_play"] == 3 and {r["snapshot_type"] for r in rows} == {"in_play"}


def test_a_ledgered_snapshot_is_never_bought_again(monkeypatch):
    ok, conn, meter, stats, rows = _snapshot(monkeypatch, [], held=True)
    assert ok and meter.calls == [] and stats["skipped_held"] == 1
    q, params = conn.sql[0]
    assert "odds_history_pulls" in q and params == ("NCAAB", "2025-11-19", 0)


def test_the_floor_stops_the_snapshot_before_the_call(monkeypatch):
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    meter = FakeMeter(lambda u, p: pytest.fail("bought below the floor"), floor=500_000)
    meter.remaining = 500_020
    stats = defaultdict(int)
    assert h._buy_snapshot(FakeConn(), meter, {}, h.EventResolver(REGISTRY, GAMES),
                           _t("2025-11-19T00:00:00Z"), stats) is False
    assert "floor" in stats["stopped"] and meter.calls == []


def test_the_lines_purchase_resumes_from_the_ledger(monkeypatch):
    monkeypatch.setattr(h, "check_precondition", lambda conn, seasons: {})
    monkeypatch.setattr(h, "check_process_events_contract", lambda: None)
    monkeypatch.setattr(h, "_ensure_tables", lambda conn: None)
    monkeypatch.setattr(h, "_season_games", lambda conn, a, b: [UK_DUKE])
    monkeypatch.setattr(h, "_held_instants",
                        lambda conn: {_t("2025-11-18T15:00Z"), _t("2025-11-17T22:00Z")})
    monkeypatch.setattr(h, "_resolver", lambda conn, games: h.EventResolver(REGISTRY, games))
    bought = []
    monkeypatch.setattr(h, "_buy_snapshot",
                        lambda conn, meter, tips, resolver, when, stats, keeper=None:
                        bought.append(when) or True)
    h.buy_lines(FakeConn(), FakeMeter(lambda u, p: Resp()), 2026, 2026)
    # the plan is D-1 22Z, D 15Z and the 00Z hour before the 00:30Z tip; two are held
    assert bought == [_t("2025-11-19T00:00Z")]


# ── first half and team totals ───────────────────────────────────────────────

BOOK = [
    {"key": "h2h_h1", "outcomes": [{"name": "Duke Blue Devils", "price": -150},
                                   {"name": "Kentucky Wildcats", "price": 125}]},
    {"key": "spreads_h1", "outcomes": [{"name": "Duke Blue Devils", "price": -110, "point": -2.5},
                                       {"name": "Kentucky Wildcats", "price": -110, "point": 2.5}]},
    {"key": "totals_h1", "outcomes": [{"name": "Over", "price": -115, "point": 70.5},
                                      {"name": "Under", "price": -105, "point": 70.5}]},
    {"key": "team_totals", "outcomes": [
        {"name": "Over", "description": "Duke Blue Devils", "price": -120, "point": 77.5},
        {"name": "Under", "description": "Duke Blue Devils", "price": -100, "point": 77.5},
        {"name": "Over", "description": "Kentucky Wildcats", "price": -105, "point": 73.5},
        {"name": "Under", "description": "Kentucky Wildcats", "price": -115, "point": 73.5},
        {"name": "Over", "description": "Kansas State Wildcats", "price": -110, "point": 66.5}]},
]


def test_derivative_markets_parse_into_the_odds_shape():
    rows = {r["market"]: r for r in h.parse_derivatives(BOOK, "Duke Blue Devils", "Kentucky Wildcats")}
    assert (rows["h2h_h1"]["home_price"], rows["h2h_h1"]["away_price"]) == (-150, 125)
    assert rows["spreads_h1"]["spread_home"] == -2.5
    assert (rows["totals_h1"]["total_line"], rows["totals_h1"]["over_price"]) == (70.5, -115)
    assert (rows["team_totals_home"]["total_line"], rows["team_totals_home"]["over_price"],
            rows["team_totals_home"]["under_price"]) == (77.5, -120, -100)
    assert (rows["team_totals_away"]["total_line"], rows["team_totals_away"]["under_price"]) == (73.5, -115)
    # a team not in the game is never filed under either side
    assert sum(1 for r in h.parse_derivatives(BOOK, "Duke Blue Devils", "Kentucky Wildcats")
               if r["market"].startswith("team_totals")) == 2


def test_a_flipped_event_s_derivatives_land_in_espn_s_orientation():
    # ESPN has Kentucky home: the caller passes the feed's away name as home
    rows = {r["market"]: r for r in h.parse_derivatives(BOOK, "Kentucky Wildcats", "Duke Blue Devils")}
    assert rows["spreads_h1"]["spread_home"] == 2.5 and rows["spreads_h1"]["home_price"] == -110
    assert (rows["h2h_h1"]["home_price"], rows["h2h_h1"]["away_price"]) == (125, -150)
    assert rows["team_totals_home"]["total_line"] == 73.5      # Kentucky
    assert rows["team_totals_away"]["total_line"] == 77.5      # Duke


def test_a_half_line_with_one_side_missing_is_not_stored():
    book = [{"key": "h2h_h1", "outcomes": [{"name": "Duke Blue Devils", "price": -150}]},
            {"key": "spreads_h1", "outcomes": [{"name": "Somebody", "price": -110, "point": 1.5}]}]
    assert h.parse_derivatives(book, "Duke Blue Devils", "Kentucky Wildcats") == []


@pytest.mark.parametrize("tip,mode,want", [
    ("2026-01-18T00:07:00Z", "close", "2026-01-17T23:55:00Z"),   # tip - 10, down to 5
    ("2026-01-17T17:00:00Z", "close", "2026-01-17T16:50:00Z"),
    ("2026-01-18T00:00:00Z", "open", "2026-01-17T04:00:00Z"),    # 7pm ET: tip - 20 h is later
    ("2026-01-17T17:00:00Z", "open", "2026-01-16T22:00:00Z"),    # noon ET: D-1 22Z is later
    (None, "open", "2026-01-16T22:00:00Z"),
])
def test_the_derivative_snapshot_instant(tip, mode, want):
    assert h.deriv_instant(_t(tip) if tip else None, "2026-01-17", mode) == _t(want)


def test_a_game_with_no_tip_has_no_close():
    assert h.deriv_instant(None, "2026-01-17", "close") is None


@pytest.mark.parametrize("tips,want", [
    (["2026-01-18T00:00:00Z"], "2026-01-17T17:00:00Z"),          # noon ET (EST) when tips are later
    ([None], "2026-01-17T17:00:00Z"),
    (["2026-01-17T16:30:00Z", "2026-01-18T00:00:00Z"], "2026-01-17T15:30:00Z"),  # 11:30 ET tip
])
def test_a_date_is_listed_at_noon_et_or_an_hour_before_its_first_tip(tips, want):
    """A pre-noon tip is under way at noon and may no longer be listed."""
    got = h._list_instant("2026-01-17", [_t(t) if t else None for t in tips])
    assert got == _t(want)


def test_the_derivative_done_check_reads_its_own_source_exactly():
    """close and open resume separately, so the check is `source = %s`, never
    a prefix match that would count one purchase as the other."""
    conn = FakeConn({"FROM odds": [("g1",)]})
    assert h._deriv_done(conn, ["g1", "g2"], h.NCAAB_DERIV_OPEN_SOURCE) == {"g1"}
    (q, params), = conn.sql
    assert "source = %s" in q and "LIKE" not in q
    assert params == (["g1", "g2"], h.NCAAB_DERIV_OPEN_SOURCE)


def test_the_two_derivative_purchases_resume_separately():
    assert h.NCAAB_DERIV_CLOSE_SOURCE == "odds_api_ncaab_derivative_close"
    assert h.NCAAB_DERIV_OPEN_SOURCE == "odds_api_ncaab_derivative_open"
    assert h.DERIV_SOURCES == {"close": h.NCAAB_DERIV_CLOSE_SOURCE, "open": h.NCAAB_DERIV_OPEN_SOURCE}


def _deriv_world(monkeypatch, done=frozenset()):
    monkeypatch.setattr(h, "check_precondition", lambda conn, seasons: {})
    monkeypatch.setattr(h, "_season_games", lambda conn, a, b: list(GAMES))
    monkeypatch.setattr(h, "_deriv_done", lambda conn, ids, source: set(done))
    monkeypatch.setattr(h, "_resolver", lambda conn, games: h.EventResolver(REGISTRY, games))
    inserted = []
    monkeypatch.setattr(h, "_insert_odds", lambda conn, rows: inserted.extend(rows))
    listing = [
        # Kentucky-Duke, listed with Duke home: flipped
        {"id": "e1", "commence_time": "2025-11-19T00:30:00Z", "home_team": "Duke Blue Devils",
         "away_team": "Kentucky Wildcats"},
        {"id": "e2", "commence_time": "2025-11-20T17:00:00Z", "home_team": "Kansas State Wildcats",
         "away_team": "Duke Blue Devils"},
        {"id": "e9", "commence_time": "2025-11-19T01:00:00Z", "home_team": "Mystery Moose",
         "away_team": "Duke Blue Devils"},
    ]

    def answer(url, params):
        if url.endswith("/events"):
            return Resp(body={"data": listing}, last="1")
        return Resp(body={"timestamp": params["date"], "data": {"bookmakers": [
            {"key": "fanduel", "markets": BOOK}]}}, last="40")
    return inserted, answer


def test_derivatives_are_bought_once_a_game_at_the_close_in_espn_s_orientation(monkeypatch):
    inserted, answer = _deriv_world(monkeypatch)
    meter = FakeMeter(answer, ceiling=10_000, floor=0)
    out = h.buy_derivatives(FakeConn(), meter, 2026, 2026, "close")
    odds_calls = [(u, p) for u, p in meter.calls if "/events/" in u]
    assert {u.rsplit("/", 2)[-2] for u, _ in odds_calls} == {"e1", "e2"}    # never the unmatched one
    dates = {u.rsplit("/", 2)[-2]: p["date"] for u, p in odds_calls}
    assert dates == {"e1": "2025-11-19T00:20:00Z", "e2": "2025-11-20T16:50:00Z"}
    assert all(p["markets"] == "h2h_h1,spreads_h1,totals_h1,team_totals" for _, p in odds_calls)
    uk = {r["market"]: r for r in inserted if r["game_id"] == UK_DUKE["game_id"]}
    assert uk["spreads_h1"]["spread_home"] == 2.5                 # Kentucky, ESPN's home
    assert uk["team_totals_home"]["total_line"] == 73.5
    assert all(r["source"] == h.NCAAB_DERIV_CLOSE_SOURCE and r["sport"] == "NCAAB" for r in inserted)
    assert out["events"] == 2 and out["flipped"] == 1 and out["left_unbought"] == 0
    # newest date first, listed an hour before its noon-ET tip; both games come off it
    assert [p["date"] for u, p in meter.calls if u.endswith("/events")] == ["2025-11-20T16:00:00Z"]


def test_a_game_already_stored_under_the_source_is_not_bought_again(monkeypatch):
    inserted, answer = _deriv_world(monkeypatch, done={UK_DUKE["game_id"]})
    meter = FakeMeter(answer)
    h.buy_derivatives(FakeConn(), meter, 2026, 2026, "open")
    bought = [u.rsplit("/", 2)[-2] for u, _ in meter.calls if "/events/" in u]
    assert bought == ["e2"]
    assert {r["source"] for r in inserted} == {h.NCAAB_DERIV_OPEN_SOURCE}


def test_the_derivative_purchase_stops_at_the_floor(monkeypatch):
    inserted, answer = _deriv_world(monkeypatch)

    def near_the_floor(url, params):
        r = answer(url, params)
        r.headers["x-requests-remaining"] = "500030"    # after the list: one game (40) won't fit
        return r
    meter = FakeMeter(near_the_floor, floor=500_000)
    meter.remaining = 500_045                           # the list and one game (41) fit
    out = h.buy_derivatives(FakeConn(), meter, 2026, 2026, "close")
    assert "floor" in out["stopped"] and inserted == []
    assert [u.rsplit("/", 1)[-1] for u, _ in meter.calls] == ["events"]   # listed, nothing bought
    assert out["left_unbought"] == 2                    # both listed games still owed


def test_the_derivative_purchase_does_not_list_a_date_it_cannot_buy_from(monkeypatch):
    inserted, answer = _deriv_world(monkeypatch)
    meter = FakeMeter(answer, floor=500_000)
    meter.remaining = 500_040                           # 1 + 40 would cross the floor
    out = h.buy_derivatives(FakeConn(), meter, 2026, 2026, "close")
    assert "floor" in out["stopped"] and meter.calls == []


def test_the_second_pass_does_not_list_a_date_under_the_floor(monkeypatch):
    """REVIEW 2026-10-26. A date whose list got no answer is listed again at
    the end; that second list call is held to the floor like the first."""
    inserted, answer = _deriv_world(monkeypatch, done={KSU_DUKE["game_id"]})

    def unanswered_then_low(url, params):
        return Resp(status=503, body={}, last="0", remaining="500030")
    meter = FakeMeter(unanswered_then_low, floor=500_000)
    meter.remaining = 600_000
    out = h.buy_derivatives(FakeConn(), meter, 2026, 2026, "close")
    assert [u.rsplit("/", 1)[-1] for u, _ in meter.calls] == ["events"]   # never listed again
    assert "floor" in out["stopped"] and out["left_unbought"] == 1


def test_a_listed_game_whose_purchase_never_answered_is_reported_as_owed(monkeypatch):
    """A floor stop skips the retry of a game whose purchase got no answer; the
    run's report still counts it as owed, so the r2 job's scope is visible."""
    inserted, answer = _deriv_world(monkeypatch)

    def e1_fails_then_low(url, params):
        if "/events/e1/" in url:
            return Resp(status=503, body={}, last="0", remaining="600000")
        r = answer(url, params)
        r.headers["x-requests-remaining"] = "600000" if url.endswith("/events") else "500030"
        return r
    meter = FakeMeter(e1_fails_then_low, floor=500_000)
    meter.remaining = 600_000
    out = h.buy_derivatives(FakeConn(), meter, 2026, 2026, "close")
    assert out["events"] == 1 and "floor" in out["stopped"]
    assert out["left_unbought"] == 1                   # Kentucky-Duke, never answered


# ── the probe ────────────────────────────────────────────────────────────────

def test_the_probe_makes_one_measured_call_of_each_kind_and_writes_nothing(monkeypatch, capsys):
    """Job ncaab-history-probe-2026-10-26 spends real credits on the worker:
    one bulk snapshot, one event list, one game's derivatives, each printed
    with what the feed billed for it, and not one row written. A contract the
    parser does not meet yet is reported and does not stop the measurement."""
    monkeypatch.setattr(h, "check_process_events_contract",
                        lambda: (_ for _ in ()).throw(h.ContractError("not yet")))
    monkeypatch.setattr(h, "_fresh_registry", lambda conn: REGISTRY)
    jan = {"game_id": "NCAAB_2026-01-17_duke_kentucky", "game_date": "2026-01-17",
           "commence_time": "2026-01-18T00:30Z", "home_espn_id": 96, "away_espn_id": 150}
    monkeypatch.setattr(h, "_season_games", lambda conn, a, b: [jan])
    monkeypatch.setattr(h, "_insert_odds", lambda conn, rows: pytest.fail("the probe wrote odds"))
    bulk_ev = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2026-01-18T00:30:00Z")
    listing = [{"id": "early", "commence_time": "2026-01-17T16:00:00Z", "home_team": "A",
                "away_team": "B"},
               {"id": "e7", "commence_time": "2026-01-18T00:30:00Z",
                "home_team": "Duke Blue Devils", "away_team": "Kentucky Wildcats"}]

    def answer(url, params):
        if "/events/" in url:
            return Resp(body={"data": {"bookmakers": [{"key": "fanduel", "markets": BOOK}]}},
                        last="40")
        if url.endswith("/events"):
            return Resp(body={"data": listing}, last="1")
        return Resp(body={"data": [bulk_ev]}, last="30")
    meter = FakeMeter(answer, ceiling=200, floor=500_000)
    conn = FakeConn()
    out = h.probe(conn, meter, 2026)
    kinds = ["derivatives" if "/events/" in u else u.rsplit("/", 1)[-1] for u, _ in meter.calls]
    assert kinds == ["odds", "events", "derivatives"]
    assert "/events/e7/odds" in meter.calls[2][0]                 # the first game still to tip
    assert meter.calls[2][1]["date"] == "2026-01-18T00:20:00Z"   # its close
    assert conn.many == [] and not [q for q, _ in conn.sql if q.lstrip().upper().startswith(
        ("INSERT", "UPDATE", "DELETE", "CREATE"))]
    printed = capsys.readouterr().out
    for billed in ("x-requests-last 30", "x-requests-last 1", "x-requests-last 40"):
        assert f"MEASURED {billed}" in printed
    assert "NOT MET" in out["contract"] and out["bulk"]["resolved"] == 1
    assert "MEASURED 71 credits in total" in printed


# ── the meter is the NBA purchase's, reused ──────────────────────────────────

def test_the_meter_is_shared_and_stops_before_the_floor_and_the_ceiling():
    assert h.Meter is nba_odds_history.Meter and h._write_with_retry is nba_odds_history._write_with_retry
    m = h.Meter(ceiling=1_000, floor=500_000)
    assert m.stop_reason(30) is None
    m.remaining = 500_020
    assert "floor" in m.stop_reason(30)
    m.remaining, m.spent = 3_000_000, 980
    assert "ceiling" in m.stop_reason(30)


# ── the unmatched store ──────────────────────────────────────────────────────

def test_the_unmatched_store_is_a_locked_down_worker_only_table():
    from data.anon_readable import WORKER_ONLY_TABLES
    assert "CREATE TABLE IF NOT EXISTS ncaab_odds_unmatched" in h.UNMATCHED_DDL
    assert "PRIMARY KEY (event_id, snapshot_at, source)" in h.UNMATCHED_DDL
    assert h.UNMATCHED_TABLE in WORKER_ONLY_TABLES


def test_the_tables_are_created_only_when_the_catalog_says_so(monkeypatch):
    seen = []
    monkeypatch.setattr(h, "schema_is_current", lambda conn, table, **kw: seen.append((table, kw)) or True)
    conn = FakeConn()
    h._ensure_tables(conn)
    assert conn.sql == [] and conn.commits == 0
    assert {t for t, _ in seen} == {"odds_history_pulls", "odds_history_fetches",
                                    "ncaab_odds_unmatched"}
    assert all(kw["rls"] is True and kw["revoked_from"] for _, kw in seen)


# ── the command line, as the worker job runs it ──────────────────────────────

def _cli(monkeypatch):
    called = []
    monkeypatch.setattr(h, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(h, "persist_quota", lambda conn: called.append(("quota",)))
    monkeypatch.setattr(h, "buy_lines",
                        lambda conn, m, a, b: called.append(("lines", a, b, m.ceiling, m.floor)) or {})
    monkeypatch.setattr(h, "buy_derivatives",
                        lambda conn, m, a, b, mode: called.append((mode, a, b, m.ceiling, m.floor)) or {})
    monkeypatch.setattr(h, "probe", lambda conn, m, season: called.append(("probe", season, m.ceiling)) or {})
    return called


@pytest.mark.parametrize("mode,want", [
    ("lines", ("lines", 2021, 2026, 420_000, 500_000)),
    ("deriv_close", ("close", 2024, 2026, 800_000, 500_000)),
    ("deriv_open", ("open", 2024, 2026, 800_000, 500_000)),
    ("probe", ("probe", 2026, 200)),
])
def test_every_job_mode_runs_the_buyer_through_its_own_argv(monkeypatch, mode, want):
    called = _cli(monkeypatch)
    cap = jq.NCAAB_ODDS_HISTORY_MODES[mode]["cap"]
    jq._job_ncaab_odds_history(**jq._validate_ncaab_odds_history(
        {"mode": mode, "max_credits": cap, "floor": 500_000}))
    assert called == [want, ("quota",)]


@pytest.mark.parametrize("argv", [
    ["--lines", "--seasons", "2021", "2026", "--apply", "--max-credits", "1000"],          # no floor
    ["--lines", "--seasons", "2021", "2026", "--apply", "--floor", "500000"],             # no ceiling
    ["--lines", "--seasons", "2021", "2026", "--apply", "--max-credits", "1000", "--floor", "299999"],
    ["--lines", "--probe", "--seasons", "2026", "2026"],                                  # two at once
    ["--derivatives", "both", "--seasons", "2024", "2026"],
    ["--lines", "--seasons", "2026", "2021"],
])
def test_a_command_line_that_could_overspend_is_refused(monkeypatch, argv):
    called = _cli(monkeypatch)
    monkeypatch.setattr("sys.argv", ["ncaab_odds_history"] + argv)
    with pytest.raises(SystemExit):
        h.main()
    assert not [c for c in called if c[0] != "quota"]


def test_without_apply_it_prints_the_plan_and_spends_nothing(monkeypatch, capsys):
    called = _cli(monkeypatch)
    monkeypatch.setattr(h, "check_precondition", lambda conn, seasons: {2026: (6000, 6100)})
    monkeypatch.setattr(h, "plan_lines", lambda conn, a, b: (GAMES, [_t("2025-11-19T00:00Z")] * 3,
                                                             [_t("2025-11-19T00:00Z")] * 2))
    monkeypatch.setattr("sys.argv", ["x", "--lines", "--seasons", "2026", "2026"])
    h.main()
    assert "2 to buy (~60 credits)" in capsys.readouterr().out
    assert [c for c in called if c[0] != "quota"] == []


# ── the worker jobs ──────────────────────────────────────────────────────────

def test_the_jobs_are_on_the_allowlist_and_run_repo_modules():
    import inspect
    for name, fn, val in (("ncaab_odds_history", jq._job_ncaab_odds_history,
                           jq._validate_ncaab_odds_history),
                          ("ncaab_schedule_backfill", jq._job_ncaab_schedule_backfill,
                           jq._validate_ncaab_schedule_backfill),
                          ("ncaab_feed_probe", jq._job_ncaab_feed_probe, jq._validate_ncaab_feed_probe)):
        assert jq.JOBS[name] == (fn, val)
        src = inspect.getsource(fn)
        assert "_run_script_main" in src and "subprocess" not in src


@pytest.mark.parametrize("args", [
    {"mode": "lines", "max_credits": 420_001, "floor": 500_000},       # above the approved scope
    {"mode": "deriv_close", "max_credits": 800_001, "floor": 500_000},
    {"mode": "deriv_open", "max_credits": 800_001, "floor": 500_000},
    {"mode": "probe", "max_credits": 201, "floor": 500_000},
    {"mode": "lines", "max_credits": 0, "floor": 500_000},
    {"mode": "lines", "max_credits": 100_000, "floor": 299_999},       # would let the feeds run dry
    {"mode": "lines", "max_credits": 100_000},
    {"mode": "props", "max_credits": 100_000, "floor": 500_000},       # not an approved purchase
    {"mode": "lines", "max_credits": 100_000, "floor": 500_000, "seasons": [2015, 2026]},
])
def test_an_ncaab_purchase_outside_the_approved_scope_is_refused(args):
    with pytest.raises(ValueError):
        jq._validate_ncaab_odds_history(args)


def test_the_approved_scopes_and_floor():
    modes = jq.NCAAB_ODDS_HISTORY_MODES
    assert {m: (v["cap"], v["seasons"]) for m, v in modes.items()} == {
        "lines": (420_000, (2021, 2026)), "deriv_close": (800_000, (2024, 2026)),
        "deriv_open": (800_000, (2024, 2026)), "probe": (200, (2026, 2026)),
        "opener_grid": (1_170_000, (2021, 2026))}
    assert jq.NCAAB_ODDS_HISTORY_MIN_FLOOR == h.MIN_FLOOR == 300_000
    # the probe mode may carry the same floor as the purchases
    assert jq._validate_ncaab_odds_history({"mode": "probe", "max_credits": 200, "floor": 500_000})


@pytest.mark.parametrize("args", [
    {"first": "2020-11-01"},
    {"first": "2021-04-10", "last": "2020-11-01"},
    {"first": "2010-11-01", "last": "2027-04-10"},                     # a typo'd decade
    {"first": "2020-11-01", "last": "2027-4-10x"},
    {"first": "2020-11-01", "last": "2021-04-10", "apply": True},
])
def test_a_malformed_schedule_backfill_is_refused(args):
    with pytest.raises(ValueError):
        jq._validate_ncaab_schedule_backfill(args)


def test_the_schedule_backfill_runs_the_espn_ingestor_with_its_cli(monkeypatch):
    seen = []
    monkeypatch.setattr(jq, "_run_script_main", lambda mod, argv: seen.append((mod, argv)) or "ok")
    jq._job_ncaab_schedule_backfill(**jq._validate_ncaab_schedule_backfill(
        {"first": "2020-11-01", "last": "2027-04-10"}))
    assert seen == [("data.ingestors.ncaab_espn_ingestor", ["--backfill", "2020-11-01", "2027-04-10"])]


def test_the_schedule_backfill_hands_the_ingestor_iso_dates():
    """strptime accepts "2027-4-10"; the ingestor gets the ISO form."""
    assert jq._validate_ncaab_schedule_backfill({"first": "2020-11-1", "last": "2027-4-10"}) == {
        "first": "2020-11-01", "last": "2027-04-10"}


SCHEDULES = [f"ncaab-schedule-{s - 1}-{s % 100:02d}" for s in range(2027, 2010, -1)]
IMPORTS = [f"ncaab-history-import-{k}" for k in
           ("box-scores", "prediction-tracker", "sbro", "match")]
BUYS = ["ncaab-history-probe-2026-10-26", "ncaab-history-lines-2021-2026",
        "ncaab-history-lines-2021-2026-r1", "ncaab-history-lines-2021-2026-r2"]
SWEEPS = [f"ncaab-game-line-market-sweep-{m}-2026-10-26" for m in ("spreads", "totals", "h2h")]
DERIVS = ["ncaab-history-deriv-close-2024-2026", "ncaab-history-deriv-close-2024-2026-r1",
          "ncaab-history-deriv-close-2024-2026-r2", "ncaab-history-deriv-open-2024-2026",
          "ncaab-history-deriv-open-2024-2026-r2"]
DECLARED = ["ncaab-feed-probe-2026-10-26"] + SCHEDULES + IMPORTS + BUYS + SWEEPS + DERIVS


def test_the_declared_ncaab_jobs_validate_in_order_and_fit_the_approval():
    """The queue claims oldest first, one job at a time: the probe, then every
    season's ESPN schedule (the current one first, so live odds resolve from
    opening night), the free history, the measured probe call, the game-line
    purchase and its post-refill resume, the sweeps on what it bought, then
    the first-half purchases."""
    entries = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    keys = [e["key"] for e in entries]
    at = [keys.index(k) for k in DECLARED]
    assert at == sorted(at), "declared out of order: the backfill must be claimed before the buys"
    assert sorted(k for k in keys if k.startswith("ncaab-")) == sorted(DECLARED)
    by = {e["key"]: e for e in entries}
    for k in DECLARED:
        e = by[k]
        assert e["requested_by"] == "mike" and e.get("enabled", True) is True
        assert "approved" in e["note"] or "yes" in e["note"]
        jq.JOBS[e["job_type"]][1](e["args"])
    assert by["ncaab-feed-probe-2026-10-26"]["args"] == {"market_events": 5}
    assert by[SCHEDULES[0]]["args"] == {"first": "2026-11-01", "last": "2027-04-10"}
    assert by[SCHEDULES[-1]]["args"] == {"first": "2010-11-01", "last": "2011-04-10"}
    buys = [by[k]["args"] for k in BUYS + DERIVS]
    assert [a["mode"] for a in buys] == ["probe", "lines", "lines", "lines", "deriv_close",
                                         "deriv_close", "deriv_close", "deriv_open", "deriv_open"]
    assert all(a["floor"] == 300_000 for a in buys)
    # the first resume fires six hours after the measured refill (about 00:00Z on the
    # 1st); the 2026-11-02 copies are backstops if a resume fired before it
    assert by["ncaab-history-lines-2021-2026-r1"]["run_after"] == "2026-11-01T06:00:00+00:00"
    assert by["ncaab-history-lines-2021-2026-r2"]["run_after"] == "2026-11-02T00:20:00+00:00"
    assert by["ncaab-history-deriv-close-2024-2026-r1"]["run_after"] == "2026-11-01T06:10:00+00:00"
    assert by["ncaab-history-deriv-close-2024-2026-r2"]["run_after"] == "2026-11-02T00:30:00+00:00"
    assert by["ncaab-history-deriv-open-2024-2026"]["run_after"] == "2026-11-01T06:20:00+00:00"
    assert by["ncaab-history-deriv-open-2024-2026-r2"]["run_after"] == "2026-11-02T01:00:00+00:00"
    assert "ncaab-history-lines-2021-2026" not in {k for k in by if by[k].get("run_after")}  # the first run is immediate
    for a, b in (("ncaab-history-lines-2021-2026", "ncaab-history-lines-2021-2026-r2"),
                 ("ncaab-history-deriv-close-2024-2026", "ncaab-history-deriv-close-2024-2026-r2")):
        assert by[a]["args"] == by[b]["args"]
    assert all(by[k]["args"]["sport"] == "NCAAB" for k in SWEEPS)


def test_the_history_import_job_runs_each_importer_with_its_fixed_argv(monkeypatch):
    ran = []
    monkeypatch.setattr(jq, "_run_script_main", lambda mod, argv: ran.append((mod, argv)) or "ok")
    for kind in ("box_scores", "prediction_tracker", "sbro", "match"):
        jq._job_ncaab_history_import(**jq._validate_ncaab_history_import({"kind": kind}))
    assert ran == [("data.ingestors.ncaab_sdv_import", ["--seasons", "2011", "2026"]),
                   ("data.ingestors.ncaab_archive_import", ["--pt", "2005", "2026"]),
                   ("data.ingestors.ncaab_archive_import", ["--sbro", "2008", "2021"]),
                   ("data.ingestors.ncaab_archive_import", ["--match"])]


@pytest.mark.parametrize("args", [{}, {"kind": "kenpom"}, {"kind": "sbro", "first": 2005},
                                  {"kind": "match", "first": 2020}, {"kind": "sbro", "x": 1}])
def test_a_history_import_outside_its_sources_seasons_is_refused(args):
    with pytest.raises(ValueError):
        jq._validate_ncaab_history_import(args)


# ── what is stored of each bought snapshot (2026-10-26, integration) ────────

def _row(gid, market="spreads", book="fanduel", st="open"):
    return {"game_id": gid, "market": market, "bookmaker": book, "snapshot_type": st}


def test_the_keeper_stores_the_opener_the_anchors_and_the_pre_tip_hours_only():
    k = h.QuoteKeeper([UK_DUKE])            # game date 2025-11-18, tip 2025-11-19 00:30Z
    gid = UK_DUKE["game_id"]
    seq = [("2025-11-16T22:00Z", True),     # first sighting: the opener
           ("2025-11-17T15:00Z", False),    # another date's anchor, a repeat
           ("2025-11-17T22:00Z", True),     # D-1 22Z: this game's anchor
           ("2025-11-18T15:00Z", True),     # D 15Z: this game's anchor
           ("2025-11-18T18:00Z", False),    # 6.5 hours out: a repeat
           ("2025-11-18T22:00Z", True),     # 2.5 hours out: inside the pre-tip window
           ("2025-11-19T00:00Z", True)]     # 30 minutes out: the close
    assert [k.wanted(_row(gid), _t(w)) for w, _ in seq] == [want for _, want in seq]


def test_each_book_and_market_has_its_own_first_sighting():
    k = h.QuoteKeeper([UK_DUKE])
    gid, w = UK_DUKE["game_id"], _t("2025-11-16T22:00Z")
    assert k.wanted(_row(gid, "spreads", "fanduel"), w)
    assert k.wanted(_row(gid, "totals", "fanduel"), w)
    assert k.wanted(_row(gid, "spreads", "pinnacle"), w)
    assert not k.wanted(_row(gid, "spreads", "fanduel"), _t("2025-11-17T15:00Z"))


def test_in_play_prices_are_never_stored():
    k = h.QuoteKeeper([UK_DUKE])
    assert not k.wanted(_row(UK_DUKE["game_id"], st="in_play"), _t("2025-11-19T01:00Z"))


def test_a_game_with_no_tip_keeps_its_opener_and_anchors():
    k = h.QuoteKeeper([dict(UK_DUKE, commence_time=None)])
    gid = UK_DUKE["game_id"]
    assert k.wanted(_row(gid), _t("2025-11-16T22:00Z"))
    assert not k.wanted(_row(gid), _t("2025-11-18T18:00Z"))
    assert k.wanted(_row(gid), _t("2025-11-18T15:00Z"))


def test_the_snapshot_stores_only_what_the_keeper_wants(monkeypatch):
    ev = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T00:30:00Z")
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    inserted = []
    monkeypatch.setattr(h, "_insert_odds", lambda conn, rows: inserted.extend(rows))
    keeper = h.QuoteKeeper(GAMES)
    stats = defaultdict(int)
    meter = FakeMeter(lambda u, p: Resp(body={"timestamp": "x", "data": [ev]}))
    tips = {g["game_id"]: g["commence_time"] for g in GAMES}
    # 6.5 hours out after an earlier sighting: bought, ledgered, not stored
    keeper.seen.update({(UK_DUKE["game_id"], m, "fanduel") for m in ("h2h", "spreads", "totals")})
    assert h._buy_snapshot(FakeConn(), meter, tips, h.EventResolver(REGISTRY, GAMES),
                           _t("2025-11-18T18:00:00Z"), stats, keeper)
    assert inserted == [] and stats["rows_not_stored"] == 3 and stats["calls"] == 1
    assert stats.get("dropped_by_parser", 0) == 0     # thinned, not lost: it was bought before


def test_seasons_run_newest_first_and_each_season_oldest_first():
    todo = [_t("2025-01-10T15:00Z"), _t("2025-11-20T15:00Z"), _t("2024-12-01T15:00Z"),
            _t("2026-02-01T15:00Z")]
    assert h.season_order(todo) == [_t("2025-11-20T15:00Z"), _t("2026-02-01T15:00Z"),
                                    _t("2024-12-01T15:00Z"), _t("2025-01-10T15:00Z")]


# ── the replay of kept raw events (2026-10-29) ───────────────────────────────
#
# Job 805227 kept bought event snapshots raw (137,007 rows in
# ncaab_odds_unmatched; the job counted 137,083), nearly all because their
# names did not resolve. The replay stores the ones that resolve now, on the
# purchase's own path, without buying, without touching the ledger or the raw
# store, and never twice. A real-Postgres run of the same is
# tests/test_ncaab_odds_replay_pg.py.

REPLAY_TEAMS = [
    (150, "Duke", "duke", "Blue Devils", "Duke Blue Devils", "Duke", "DUKE", True, None),
    (96, "Kentucky", "kentucky", "Wildcats", "Kentucky Wildcats", "Kentucky", "UK", True, None),
    (2306, "Kansas State", "kansas-state", "Wildcats", "Kansas State Wildcats", "Kansas St",
     "KSU", True, None),
]
# Kansas State-Duke (KSU_DUKE) tips 2025-11-20 17:00Z. The feed calls Kansas
# State "Kansas St Wildcats", which only the 2026-10-29 name rule places.
KSU_NAME, KSU_TIP = "Kansas St Wildcats", "2025-11-20T17:00:00Z"
REPLAY_LEDGER = [("2025-11-19", 22), ("2025-11-20", 15), ("2025-11-20", 16), ("2025-11-20", 18)]


def _raw(eid, stamp, last_update, home=KSU_NAME, away="Duke Blue Devils", tip=KSU_TIP):
    return (eid, stamp, _event(eid, home, away, tip, last_update=last_update))


REPLAY_RAW = [
    _raw("e2", "2025-11-19T21:55:38Z", "2025-11-19T21:50:00Z"),   # the 22Z opener (an anchor too)
    _raw("e2", "2025-11-20T14:55:12Z", "2025-11-20T14:52:00Z"),   # the 15Z anchor
    _raw("e2", "2025-11-20T15:55:20Z", "2025-11-20T15:51:00Z"),   # 16Z, an hour before the tip
    _raw("e2", "2025-11-20T17:55:00Z", "2025-11-20T17:20:00Z"),   # 18Z: in play, never stored
    _raw("e2", "2025-11-18T09:00:00Z", "2025-11-18T08:58:00Z"),   # no instant within an hour
    _raw("e9", "2025-11-19T21:55:38Z", "2025-11-19T21:50:00Z", home="Mystery Moose"),
]


class ReplayConn:
    """An in-memory database for the replay: the pull ledger, the registry,
    ESPN's games, the raw unmatched rows, and the `odds` rows it stores."""

    def __init__(self, ledger=REPLAY_LEDGER, raw=REPLAY_RAW, games=None, odds=None):
        self.ledger, self.raw = list(ledger), list(raw)
        self.games = list(GAMES if games is None else games)
        self.odds = [] if odds is None else odds
        self.sql: list[tuple[str, object]] = []
        self.commits = 0
        self._ans: list = []

    def execute(self, sql, params=None):
        q = " ".join(sql.split())
        self.sql.append((q, params))
        if "FROM odds_history_pulls" in q:
            self._ans = list(self.ledger)
        elif "FROM ncaab_teams" in q:
            self._ans = list(REPLAY_TEAMS)
        elif "FROM ncaab_events" in q:
            self._ans = [(g["game_id"], g["game_date"], g["commence_time"], g["home_espn_id"],
                          g["away_espn_id"]) for g in self.games]
        elif q.startswith("SELECT event_id, snapshot_at FROM ncaab_odds_unmatched"):
            source, lo, hi = params
            self._ans = [(e, s) for e, s, _ in self.raw
                         if source == oi.HISTORICAL_ODDS_SOURCE and lo <= s < hi]
        elif "payload FROM ncaab_odds_unmatched" in q:
            source, stamps, ids = params
            assert len(ids) <= h.REPLAY_BATCH_ROWS
            self._ans = [(e, s, json.dumps(p)) for e, s, p in self.raw
                         if s in stamps and e in ids]
        elif "FROM odds WHERE" in q:
            source, gids, stamps = params
            self._ans = [tuple(r.get(c) for c in ("game_id", "market", "bookmaker", "snapshot_at",
                                                  *h._ROW_VALUES))
                         for r in self.odds if r.get("source") == source
                         and r["game_id"] in gids and r["snapshot_at"] in stamps]
        else:
            self._ans = []
        return self

    def fetchall(self):
        return self._ans

    def fetchone(self):
        return self._ans[0] if self._ans else None

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


def _replay(monkeypatch, conn, apply=True, first=2026, last=2026):
    monkeypatch.setattr(h, "_insert_odds", lambda c, rows: conn.odds.extend(dict(r) for r in rows))
    return h.replay_unmatched(conn, first, last, apply=apply)


@pytest.mark.parametrize("stamp,want", [
    ("2025-11-19T21:55:38Z", "2025-11-19T22:00:00Z"),   # the feed's own time, 4m22s early
    ("2025-11-19T22:00:00Z", "2025-11-19T22:00:00Z"),   # on the instant itself
    ("2025-11-19T21:00:00Z", "2025-11-19T22:00:00Z"),   # exactly an hour early
    ("2025-11-19T20:59:59Z", None),                     # just over an hour: never guessed
    ("2025-11-20T15:10:38Z", "2025-11-20T16:00:00Z"),   # 49 min (the measured widest gap)
    ("2025-11-20T18:00:01Z", None),                     # after the last instant
])
def test_a_raw_stamp_maps_to_the_first_planned_instant_at_or_after_it_within_an_hour(stamp, want):
    instants = [_t("2025-11-19T22:00Z"), _t("2025-11-20T15:00Z"), _t("2025-11-20T16:00Z"),
                _t("2025-11-20T18:00Z")]
    got = h.planned_instant(_t(stamp), instants)
    assert got == (_t(want) if want else None)


def test_the_ledger_instants_are_the_pull_ledger_s_dates_and_hours():
    assert h._ledger_instants(ReplayConn()) == [
        _t("2025-11-19T22:00Z"), _t("2025-11-20T15:00Z"), _t("2025-11-20T16:00Z"),
        _t("2025-11-20T18:00Z")]


def test_the_replay_stores_what_the_purchase_would_have_and_a_second_apply_stores_nothing(monkeypatch):
    conn = ReplayConn()
    first = _replay(monkeypatch, conn)
    assert first["stamps_mapped"] == 4 and first["stamps_unmapped"] == 1
    assert first["event_snapshots_unmapped"] == 1 and first["instants"] == 4
    assert (first["events_resolved"], first["events_unresolved"]) == (1, 1)
    assert first["event_snapshots_resolved"] == 4 and first["event_snapshots_unresolved"] == 1
    assert first["rows_parsed"] == 12 and first["rows_marked_in_play"] == 3
    assert first["rows_kept"] == 9 and first["rows_inserted"] == 9
    # ESPN's game, the historical source, and each market's own last_update as
    # the quote's time, exactly as _buy_snapshot stores a resolved event
    assert {r["game_id"] for r in conn.odds} == {KSU_DUKE["game_id"]}
    assert {r["source"] for r in conn.odds} == {oi.HISTORICAL_ODDS_SOURCE}
    assert {r["snapshot_type"] for r in conn.odds} == {"open"}
    assert sorted({r["snapshot_at"] for r in conn.odds}) == [
        "2025-11-19T21:50:00Z", "2025-11-20T14:52:00Z", "2025-11-20T15:51:00Z"]
    spread = next(r for r in conn.odds if r["market"] == "spreads")
    assert spread["spread_home"] == -4.5 and spread["home_price"] == -108   # Kansas State, ESPN's home

    second = _replay(monkeypatch, conn)
    assert second["rows_kept"] == 9 and second["rows_already_stored"] == 9
    assert second.get("rows_inserted", 0) == 0 and len(conn.odds) == 9


def _quote_keys(rows) -> Counter:
    return Counter(h._row_key(r["game_id"], r["market"], r["bookmaker"], r["snapshot_at"],
                              *(r.get(c) for c in h._ROW_VALUES)) for r in rows)


@pytest.mark.parametrize("server_committed", [True, False])
def test_a_commit_lost_in_flight_stores_each_quote_once(monkeypatch, server_committed):
    """data.db raises ConnectionLost when the connection drops at COMMIT, and
    _write_with_retry runs the unit again. The server may have committed (only
    the acknowledgement was lost) or not; the retry must read `odds` back
    inside the unit, so either way every quote is stored exactly once. With
    the read-back before the retry loop (the 2026-10-29 review), this world
    stored 3 quotes twice."""
    from data.db import ConnectionLost
    conn = ReplayConn()
    monkeypatch.setattr(nba_odds_history.time, "sleep", lambda s: None)
    state = {"failed": False, "landed": 0}

    def commit():
        conn.commits += 1
        if not state["failed"]:
            state["failed"] = True
            if not server_committed:
                del conn.odds[state["landed"]:]       # the server rolled the unit back
            raise ConnectionLost("connection lost at commit")
        state["landed"] = len(conn.odds)
    monkeypatch.setattr(conn, "commit", commit)
    out = _replay(monkeypatch, conn)
    keys = _quote_keys(conn.odds)
    assert len(conn.odds) == 9 and set(keys.values()) == {1}
    assert out["rows_inserted"] == 9 and out.get("write_errors", 0) == 0


def test_a_listing_placed_on_a_game_twelve_hours_or_more_from_its_tip_is_not_stored(monkeypatch):
    """ncaab_teams.match_event takes the nearest game within a day either side,
    so a second feed listing of the same pair a day later lands on the same
    ESPN game: 24 kept feed events (144 event snapshots) did, every one on a
    game that also has a listing within the hour (Supabase connector,
    2026-10-29). The replay stores none of a far listing's quotes, not even at
    an anchor the keeper would otherwise keep, and counts it apart."""
    far = _raw("e5", "2025-11-19T21:55:38Z", "2025-11-19T21:40:00Z", tip="2025-11-21T17:00:00Z")
    conn = ReplayConn(raw=REPLAY_RAW + [far])
    out = _replay(monkeypatch, conn)
    assert out["event_snapshots_far_from_tip"] == 1 and out["events_far_from_tip"] == 1
    assert "2025-11-19T21:40:00Z" not in {r["snapshot_at"] for r in conn.odds}
    assert out["rows_inserted"] == 9                       # the real listing's, as before
    assert (out["events_resolved"], out["events_unresolved"]) == (1, 1)
    # 12 hours to the second is far; a minute under is not
    assert h._far_from_tip({"commence_time": "2025-11-21T05:00:00Z"}, (KSU_DUKE["game_id"], False),
                           {KSU_DUKE["game_id"]: KSU_TIP})
    assert not h._far_from_tip({"commence_time": "2025-11-21T04:59:00Z"},
                               (KSU_DUKE["game_id"], False), {KSU_DUKE["game_id"]: KSU_TIP})
    # no ESPN tip, no feed start, or no game: nothing to compare, nothing refused
    assert not h._far_from_tip({"commence_time": "2025-11-23T00:00:00Z"},
                               (KSU_DUKE["game_id"], False), {KSU_DUKE["game_id"]: None})
    assert not h._far_from_tip({}, (KSU_DUKE["game_id"], False), {KSU_DUKE["game_id"]: KSU_TIP})
    assert not h._far_from_tip({"commence_time": KSU_TIP}, None, {})


def test_the_keeper_judges_a_replayed_snapshot_at_the_hour_that_was_bought(monkeypatch):
    """Kentucky-Duke tips 2025-11-19 00:30Z, game date 11-18. Its 11-18 15Z
    snapshot is kept only because 15Z is one of its anchors: the tip is 9.5
    hours away, outside the three-hour window, and the quote was seen the day
    before. The raw row carries the feed's own time, 14:55:12Z; judged at that
    time instead of the hour bought, it would be dropped as a repeat."""
    tip = "2025-11-19T00:30:00Z"
    ledger = [("2025-11-17", 15), ("2025-11-18", 15)]
    raw = [("e3", "2025-11-17T14:55:00Z", _event("e3", "Kentucky Wildcats", "Duke Blue Devils",
                                                 tip, last_update="2025-11-17T14:50:00Z")),
           ("e3", "2025-11-18T14:55:12Z", _event("e3", "Kentucky Wildcats", "Duke Blue Devils",
                                                 tip, last_update="2025-11-18T14:52:00Z"))]
    conn = ReplayConn(ledger=ledger, raw=raw)
    out = _replay(monkeypatch, conn)
    assert sorted({r["snapshot_at"] for r in conn.odds}) == ["2025-11-17T14:50:00Z",
                                                             "2025-11-18T14:52:00Z"]
    assert out["rows_kept"] == 6 and out["rows_inserted"] == 6


def test_the_replay_never_buys_never_writes_the_ledger_and_never_deletes_a_raw_row(monkeypatch):
    conn = ReplayConn()
    monkeypatch.setattr(h.Meter, "get", lambda *a, **k: pytest.fail("the replay made a feed call"))
    _replay(monkeypatch, conn)
    writes = [q for q, _ in conn.sql
              if q.split()[0].upper() in ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP")]
    assert writes == []                       # its only write is _insert_odds into `odds`
    assert conn.commits == 3                  # one per instant that stored rows


def test_a_dry_run_writes_nothing_and_counts_what_it_would_store(monkeypatch):
    conn = ReplayConn()
    monkeypatch.setattr(h, "_insert_odds", lambda c, rows: pytest.fail("the dry run wrote odds"))
    out = h.replay_unmatched(conn, 2026, 2026, apply=False)
    assert out["rows_kept"] == 9 and out["rows_to_insert"] == 9
    assert conn.commits == 0 and "rows_inserted" not in out


def test_the_replay_walks_the_planned_instants_in_season_order(monkeypatch):
    """Seasons newest first, each season oldest first, as the purchase bought
    them, so the one QuoteKeeper sees each quote's earliest snapshot first."""
    instants = ["2025-01-10T15:00Z", "2025-11-20T15:00Z", "2024-12-01T15:00Z", "2026-02-01T15:00Z"]
    ledger = [(w[:10], 15) for w in instants]
    raw = [(f"e{i}", f"{w[:10]}T14:55:00Z", {"id": f"e{i}"}) for i, w in enumerate(instants)]
    walked = []

    def record(events, when, resolver, tips):
        walked.append(when)
        return {}, [], [], [], 0
    monkeypatch.setattr(h, "_parse_snapshot", record)
    h.replay_unmatched(ReplayConn(ledger=ledger, raw=raw), 2025, 2026, apply=False)
    assert walked == [_t("2025-11-20T15:00Z"), _t("2026-02-01T15:00Z"),
                      _t("2024-12-01T15:00Z"), _t("2025-01-10T15:00Z")]


def test_the_replay_honours_its_seasons(monkeypatch):
    raw = REPLAY_RAW + [
        _raw("e7", "2025-01-10T14:55:00Z", "2025-01-10T14:50:00Z"),   # season 2025
        # 30 minutes before the 2026-27 season's first instant: read inside the
        # 2025-26 window, but its planned instant is 2026-10-01 00Z, season 2027
        _raw("e8", "2026-09-30T23:30:00Z", "2026-09-30T23:25:00Z")]
    ledger = REPLAY_LEDGER + [("2025-01-10", 15), ("2026-10-01", 0)]
    walked = []

    def record(events, when, resolver, tips):
        walked.append(when)
        return {}, [], [], [], 0
    monkeypatch.setattr(h, "_parse_snapshot", record)
    out = h.replay_unmatched(ReplayConn(ledger=ledger, raw=raw), 2026, 2026, apply=False)
    assert _t("2025-01-10T15:00Z") not in walked and _t("2026-10-01T00:00Z") not in walked
    assert len(walked) == 4 and out["event_snapshots_outside_seasons"] == 1
    walked.clear()
    h.replay_unmatched(ReplayConn(ledger=ledger, raw=raw), 2025, 2025, apply=False)
    assert walked == [_t("2025-01-10T15:00Z")]
    walked.clear()
    h.replay_unmatched(ReplayConn(ledger=ledger, raw=raw), 2027, 2027, apply=False)
    assert walked == [_t("2026-10-01T00:00Z")]


def test_the_replay_reads_payloads_by_primary_key_in_batches_of_at_most_500(monkeypatch):
    raw = [(f"x{i:04d}", "2025-11-19T21:55:38Z", {"id": f"x{i:04d}"}) for i in range(1203)]
    conn = ReplayConn(raw=raw)
    monkeypatch.setattr(h, "_parse_snapshot", lambda events, when, r, t: ({}, [], [], [], 0))
    out = h.replay_unmatched(conn, 2026, 2026, apply=False)
    reads = [p for q, p in conn.sql if "payload FROM ncaab_odds_unmatched" in q]
    assert [len(p[2]) for p in reads] == [500, 500, 203]
    assert all(p[1] == ["2025-11-19T21:55:38Z"] for p in reads)
    assert out["event_snapshots"] == 1203 and out["payloads_missing"] == 0


def test_the_dry_run_connection_cannot_write_and_cannot_reconnect(monkeypatch):
    class Raw:
        readonly = None

        def set_session(self, readonly=None):
            self.readonly = readonly

    class Conn:
        def __init__(self, state):
            self._conn, self._url, self.state, self.closed = Raw(), "postgresql://x", state, False

        def execute(self, sql, params=None):
            assert sql == "SHOW transaction_read_only"
            return self

        def fetchone(self):
            return (self.state,)

        def rollback(self):
            pass

        def close(self):
            self.closed = True
    good = Conn("on")
    monkeypatch.setattr(h, "get_connection", lambda: good)
    assert h._read_only_connection() is good
    assert good._conn.readonly is True and good._url is None
    bad = Conn("off")
    monkeypatch.setattr(h, "get_connection", lambda: bad)
    with pytest.raises(RuntimeError, match="not read only"):
        h._read_only_connection()
    assert bad.closed


def _replay_cli(monkeypatch):
    calls = []

    class C:
        def __init__(self, tag):
            self.tag = tag

        def close(self):
            calls.append(("close", self.tag))
    monkeypatch.setattr(h, "_read_only_connection", lambda: C("read-only"))
    monkeypatch.setattr(h, "get_connection", lambda: C("writable"))
    monkeypatch.setattr(h, "persist_quota", lambda conn: calls.append(("quota",)))
    monkeypatch.setattr(h, "replay_unmatched",
                        lambda conn, a, b, apply: calls.append(("replay", conn.tag, a, b, apply)) or {})
    return calls


def test_the_replay_command_line_is_a_read_only_dry_run_unless_apply(monkeypatch):
    calls = _replay_cli(monkeypatch)
    monkeypatch.setattr("sys.argv", ["x", "--replay-unmatched", "--seasons", "2026", "2026"])
    h.main()
    monkeypatch.setattr("sys.argv", ["x", "--replay-unmatched", "--seasons", "2026", "2026",
                                     "--dry-run"])
    h.main()
    monkeypatch.setattr("sys.argv", ["x", "--replay-unmatched", "--seasons", "2021", "2026",
                                     "--apply"])
    h.main()
    assert [c for c in calls if c[0] == "replay"] == [
        ("replay", "read-only", 2026, 2026, False), ("replay", "read-only", 2026, 2026, False),
        ("replay", "writable", 2021, 2026, True)]
    assert ("quota",) not in calls            # no feed call, so no quota reading to persist


@pytest.mark.parametrize("argv", [
    ["--replay-unmatched", "--seasons", "2021", "2026", "--apply", "--max-credits", "10"],
    ["--replay-unmatched", "--seasons", "2021", "2026", "--apply", "--floor", "300000"],
    ["--replay-unmatched", "--seasons", "2021", "2026", "--apply", "--dry-run"],
    ["--replay-unmatched", "--lines", "--seasons", "2021", "2026"],
])
def test_a_replay_command_line_that_could_buy_or_contradict_itself_is_refused(monkeypatch, argv):
    calls = _replay_cli(monkeypatch)
    monkeypatch.setattr("sys.argv", ["x"] + argv)
    with pytest.raises(SystemExit):
        h.main()
    assert [c for c in calls if c[0] == "replay"] == []


def test_the_replay_job_runs_with_apply_and_dry_runs_on_request(monkeypatch):
    seen = []
    monkeypatch.setattr(jq, "_run_script_main", lambda mod, argv: seen.append((mod, argv)) or "ok")
    assert jq._validate_ncaab_odds_history({"mode": "replay_unmatched"}) == {
        "mode": "replay_unmatched", "dry_run": False}
    jq._job_ncaab_odds_history(**jq._validate_ncaab_odds_history({"mode": "replay_unmatched"}))
    jq._job_ncaab_odds_history(**jq._validate_ncaab_odds_history(
        {"mode": "replay_unmatched", "dry_run": True}))
    assert seen == [
        ("data.ingestors.ncaab_odds_history",
         ["--replay-unmatched", "--seasons", "2021", "2026", "--apply"]),
        ("data.ingestors.ncaab_odds_history",
         ["--replay-unmatched", "--seasons", "2021", "2026", "--dry-run"])]
    # the free mode is not a purchase: the approved purchase scopes are unchanged
    assert "replay_unmatched" not in jq.NCAAB_ODDS_HISTORY_MODES


@pytest.mark.parametrize("args", [
    {"mode": "replay_unmatched", "max_credits": 10},
    {"mode": "replay_unmatched", "floor": 300_000},
    {"mode": "replay_unmatched", "dry_run": "yes"},
    {"mode": "replay_unmatched", "seasons": [2015, 2026]},
])
def test_a_replay_job_with_purchase_arguments_is_refused(args):
    with pytest.raises(ValueError):
        jq._validate_ncaab_odds_history(args)


def test_the_replay_job_runs_the_real_command_line(monkeypatch):
    """Through _run_script_main and main(), as the worker runs it."""
    calls = _replay_cli(monkeypatch)
    jq._job_ncaab_odds_history(**jq._validate_ncaab_odds_history({"mode": "replay_unmatched"}))
    assert [c for c in calls if c[0] == "replay"] == [("replay", "writable", 2021, 2026, True)]

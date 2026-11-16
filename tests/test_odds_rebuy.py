"""The odds re-buy (#1384) buys only what the cleanup removed, once.

data/ingestors/odds_rebuy.py plans on the PC copy and writes to Supabase.
These tests build a small copy in DuckDB and drive the buyer with stand-ins
for the API and the database. No network, no Supabase.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

duckdb = pytest.importorskip("duckdb")

from data.ingestors import odds_rebuy as rb  # noqa: E402

UTC = timezone.utc
BOOKS = ("fanduel", "betmgm")


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def copy():
    con = duckdb.connect()
    con.execute("CREATE TABLE games (game_id VARCHAR, sport VARCHAR, commence_time VARCHAR)")
    con.execute("""CREATE TABLE odds (game_id VARCHAR, sport VARCHAR, market VARCHAR,
        bookmaker VARCHAR, snapshot_type VARCHAR, snapshot_at VARCHAR, source VARCHAR,
        home_price DOUBLE, away_price DOUBLE, spread_home DOUBLE, total_line DOUBLE,
        over_price DOUBLE, under_price DOUBLE)""")
    con.execute("""CREATE TABLE player_prop_odds (game_id VARCHAR, game_date VARCHAR,
        player_name VARCHAR, market VARCHAR, bookmaker VARCHAR, snapshot_type VARCHAR,
        snapshot_at VARCHAR, line DOUBLE, over_price DOUBLE, under_price DOUBLE)""")
    con.execute("CREATE TABLE pipeline_runs (run_kind VARCHAR, started_at VARCHAR)")
    start = _t("2026-10-15T23:00:00")
    # THIN: other books hold an opener and a close only; DraftKings every pass.
    # FULL: other books hold every pass too (a kept-path sport), so not thinned.
    for gid in ("NHL_THIN", "NHL_FULL"):
        con.execute("INSERT INTO games VALUES (?, 'NHL', ?)", [gid, _iso(start)])
    passes = [_t("2026-10-15T12:17:01") + timedelta(hours=h) for h in range(10)]
    for p in passes:
        con.execute("INSERT INTO pipeline_runs VALUES ('hourly', ?)", [p.isoformat()])
    con.execute("INSERT INTO pipeline_runs VALUES ('daily', ?)",
                [_t("2026-10-15T14:40:00").isoformat()])
    for p in passes:
        for gid in ("NHL_THIN", "NHL_FULL"):
            con.execute("INSERT INTO odds VALUES (?, 'NHL', 'h2h', 'draftkings', 'open', ?, NULL,"
                        " -120, 100, NULL, NULL, NULL, NULL)", [gid, _iso(p)])
        for b in BOOKS:
            con.execute("INSERT INTO odds VALUES ('NHL_FULL', 'NHL', 'h2h', ?, 'open', ?, NULL,"
                        " -118, 98, NULL, NULL, NULL, NULL)", [b, _iso(p)])
    opener, close = _t("2026-10-15T12:10:00"), _t("2026-10-15T22:50:00")
    for b in BOOKS:
        for ts in (opener, close):
            con.execute("INSERT INTO odds VALUES ('NHL_THIN', 'NHL', 'h2h', ?, 'open', ?, NULL,"
                        " -115, -105, NULL, NULL, NULL, NULL)", [b, _iso(ts)])
    return con


def test_plan_buys_only_thinned_games_between_opener_and_close_at_refresh_times(copy):
    reqs = rb.plan(copy, "game", "NHL", "2026-10-15", "2026-10-15")
    assert reqs, "the thinned game has a gap to fill"
    assert {g for r in reqs for g in r.games} == {"NHL_THIN"}
    # each refresh started at :17:01; the snapshot asked for is the next 5-minute mark
    assert all(r.at.minute == 20 and r.at.second == 0 for r in reqs)
    # strictly inside the stored window, and before the start
    assert all(_t("2026-10-15T12:10:00") < r.at < _t("2026-10-15T22:50:00") for r in reqs)
    assert len(reqs) == 10
    assert reqs[0].books == list(BOOKS[::-1]) or set(reqs[0].books) == set(BOOKS)
    assert reqs[0].markets == ["h2h"]


def test_the_daily_run_is_not_a_refresh_time(copy):
    times = rb.pass_times(copy, _t("2026-10-15T00:00:00"), _t("2026-10-16T00:00:00"))
    assert _t("2026-10-15T14:40:00") not in times


def test_before_the_run_log_the_plan_takes_one_snapshot_an_hour(copy):
    times = rb.pass_times(copy, _t("2026-08-20T00:00:00"), _t("2026-08-20T05:00:00"))
    assert times == [_t("2026-08-20T00:00:00") + timedelta(hours=h) for h in range(5)]


def _req(**kw):
    start = _t("2026-10-15T23:00:00")
    base = dict(kind="game", sport="NHL", at=_t("2026-10-15T15:20:00"), games=["NHL_THIN"],
                starts={"NHL_THIN": start}, markets=["h2h"], books=list(BOOKS),
                windows={"NHL_THIN": (_t("2026-10-15T12:10:00"), _t("2026-10-15T22:50:00"))})
    base.update(kw)
    return rb.Request(**base)


def _row(book, price, stamp="2026-10-15T15:18:00Z", game="NHL_THIN", market="h2h"):
    return {"game_id": game, "sport": "NHL", "market": market, "bookmaker": book,
            "snapshot_type": "open", "snapshot_at": stamp, "home_price": price,
            "away_price": -price, "draw_price": None, "spread_home": None, "total_line": None,
            "over_price": None, "under_price": None}


def test_game_rows_keep_only_planned_games_books_and_moves_inside_the_window(monkeypatch):
    rows = [_row("fanduel", -130), _row("draftkings", -128), _row("bovada", -131),
            _row("fanduel", -130, game="NHL_OTHER"),
            _row("betmgm", -115, stamp="2026-10-15T12:05:00Z")]   # before the stored opener
    monkeypatch.setattr("data.ingestors.odds_ingestor._process_events",
                        lambda *a, **k: ([], rows))
    keep, dk = rb.game_rows(_req(), [], "2026-10-15T15:15:36Z")
    assert [(r["bookmaker"], r["source"]) for r in keep] == [("fanduel", rb.REBUY_SOURCE)]
    assert [r["bookmaker"] for r in dk] == ["draftkings"]


def test_a_snapshot_at_or_after_the_start_is_not_stored(monkeypatch):
    monkeypatch.setattr("data.ingestors.odds_ingestor._process_events",
                        lambda *a, **k: ([], [_row("fanduel", -130)]))
    keep, _ = rb.game_rows(_req(), [], "2026-10-15T23:00:00Z")
    assert keep == []


def test_an_unchanged_price_is_not_stored_twice(copy):
    last: dict = {}
    req = _req()
    # the stored opener is -115/-105 for both books; -115 repeats it, -130 moved
    first = rb.drop_unchanged_game_rows(copy, req, [
        {**_row("betmgm", -115), "away_price": -105}, _row("fanduel", -130)], last)
    assert [r["bookmaker"] for r in first] == ["fanduel"]
    second = rb.drop_unchanged_game_rows(copy, _req(at=_t("2026-10-15T16:20:00")), [
        _row("fanduel", -130, stamp="2026-10-15T16:19:00Z"),
        _row("fanduel", -135, stamp="2026-10-15T16:19:30Z", market="h2h")], last)
    assert [r["home_price"] for r in second] == [-135]


def test_an_alternate_prop_line_is_its_own_proposition():
    last = {"G": {}}
    req = _req(kind="prop", event_key="G", games=["G"])
    rows = [{"market": "player_points_alternate", "player_name": "A", "bookmaker": "fanduel",
             "line": 9.5, "over_price": 120, "under_price": None},
            {"market": "player_points_alternate", "player_name": "A", "bookmaker": "fanduel",
             "line": 14.5, "over_price": 300, "under_price": None}]
    assert len(rb.drop_unchanged_props(None, req, rows, last)) == 2
    assert rb.drop_unchanged_props(None, req, rows, last) == []


class _Conn:
    def __init__(self):
        self.commits = 0

    def execute(self, *a, **k):
        class R:
            def fetchall(self_inner):
                return []

            def fetchone(self_inner):
                return None
        return R()

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


@pytest.fixture
def buyer(monkeypatch):
    ledger: list = []
    inserted: list = []
    budget = type("B", (), {"ceiling": 10_000})()
    monkeypatch.setattr(rb, "ensure_ledger", lambda conn: None)
    monkeypatch.setattr(rb, "done_keys",
                        lambda conn, kind, sport: {(k, s, e, t) for k, s, e, t, *_ in ledger})
    monkeypatch.setattr(rb, "_ledger",
                        lambda conn, req, served, credits, n, c, m:
                        ledger.append((req.kind, req.sport, req.event_key, req.at, n, credits)))
    monkeypatch.setattr("data.ingestors.odds_ingestor._insert_odds",
                        lambda conn, rows: inserted.extend(rows) or len(rows))
    monkeypatch.setattr("data.ingestors.odds_quota.plan_credit_budget",
                        lambda conn, **k: (budget, []))
    monkeypatch.setattr("data.ingestors.odds_quota.persist_quota", lambda conn: None)
    monkeypatch.setattr(rb, "fetch_game_snapshot",
                        lambda sport, at, m, b: ([], _iso(at - timedelta(minutes=4)), 10))
    monkeypatch.setattr(rb, "game_rows", lambda req, ev, served, conn=None, resolver=None:
                        ([{**_row("fanduel", -130 - req.at.hour, stamp=served),
                           "source": rb.REBUY_SOURCE}], []))
    return ledger, inserted, budget


def test_each_request_is_bought_once_and_ledgered_with_its_rows(buyer):
    ledger, inserted, _ = buyer
    reqs = [_req(at=_t("2026-10-15T15:20:00")), _req(at=_t("2026-10-15T16:20:00"))]
    first = rb.buy(reqs, conn=_Conn(), copy_con=None, sleep=0)
    assert (first["requests"], first["rows"], first["credits"]) == (2, 2, 20)
    assert [r[3] for r in ledger] == [r.at for r in reqs]
    again = rb.buy(reqs, conn=_Conn(), copy_con=None, sleep=0)
    assert (again["requests"], again["skipped_done"], len(inserted)) == (0, 2, 2)


def test_the_run_stops_at_its_ceiling(buyer):
    ledger, _, budget = buyer
    budget.ceiling = 15
    stats = rb.buy([_req(at=_t("2026-10-15T15:20:00")), _req(at=_t("2026-10-15T16:20:00"))],
                   conn=_Conn(), copy_con=None, sleep=0)
    assert stats["requests"] == 1 and "ceiling" in stats["stopped"]


def test_the_run_refuses_when_the_reserve_would_be_spent(buyer, monkeypatch):
    ledger, _, budget = buyer
    monkeypatch.setattr("data.ingestors.odds_quota.plan_credit_budget",
                        lambda conn, **k: (budget, ["this run would leave 10 credits"]))
    stats = rb.buy([_req()], conn=_Conn(), copy_con=None, sleep=0)
    assert stats["requests"] == 0 and stats["stopped"].startswith("refused")
    assert ledger == []


def test_the_cleanup_never_touches_a_bought_row():
    from data import prune_odds
    assert rb.REBUY_SOURCE in prune_odds.PROTECTED_SOURCES


# ── The pieces added 2026-11-16 (mike: "Yes, add them") ─────────────────────

def _nfl_event(books):
    return {"id": "ev1", "commence_time": "2026-10-02T00:15:00Z",
            "home_team": "Cleveland Browns", "away_team": "Pittsburgh Steelers",
            "bookmakers": [{"key": b, "markets": [{
                "key": "h2h", "last_update": "2026-10-01T20:10:00Z",
                "outcomes": [{"name": "Cleveland Browns", "price": 120},
                             {"name": "Pittsburgh Steelers", "price": -140}]}]}
                for b in books]}


def test_an_nfl_row_takes_its_game_id_from_the_schedule(monkeypatch):
    """An NFL id is NFL_<season>_<week>_<away>_<home>. Left to itself the
    event parser would build NFL_2026-10-01_..., which no game has, and every
    bought NFL row would be thrown away after it was paid for."""
    gid = "NFL_2026_04_PIT_CLE"
    monkeypatch.setattr("data.ingestors.odds_ingestor._schedule_resolver",
                        lambda sport, conn, around: (lambda h, a, c: gid))
    req = rb.Request("game", "NFL", _t("2026-10-01T20:20:00"), [gid],
                     {gid: _t("2026-10-02T00:15:00")}, ["h2h"], ["fanduel"],
                     windows={gid: (_t("2026-10-01T12:00:00"), _t("2026-10-02T00:00:00"))})
    keep, dk = rb.game_rows(req, [_nfl_event(["draftkings", "fanduel"])],
                            "2026-10-01T20:19:30Z", conn=object())
    assert [(r["game_id"], r["bookmaker"]) for r in keep] == [(gid, "fanduel")]
    assert [r["game_id"] for r in dk] == [gid]


def test_an_nfl_request_without_the_schedule_buys_nothing():
    with pytest.raises(RuntimeError, match="no schedule resolver"):
        rb.schedule_resolver("NFL", None, _t("2026-10-01T20:20:00"))
    assert rb.schedule_resolver("NHL", None, _t("2026-10-01T20:20:00")) is None


def test_extra_markets_are_planned_per_event_and_asked_under_the_feeds_key(copy):
    # NHL_THIN's 3-way: DraftKings every pass, the other books an opener and a close.
    passes = [r[0] for r in copy.execute("SELECT started_at FROM pipeline_runs "
                                         "WHERE run_kind = 'hourly'").fetchall()]
    for p in passes:
        copy.execute("INSERT INTO odds VALUES ('NHL_THIN', 'NHL', 'h2h_3way', 'draftkings', "
                     "'open', ?, NULL, 150, 180, NULL, NULL, NULL, NULL)",
                     [_iso(datetime.fromisoformat(p))])
    for b in BOOKS:
        for ts in ("2026-10-15T12:10:00Z", "2026-10-15T22:50:00Z"):
            copy.execute("INSERT INTO odds VALUES ('NHL_THIN', 'NHL', 'h2h_3way', ?, 'open', ?,"
                         " NULL, 155, 175, NULL, NULL, NULL, NULL)", [b, ts])
    reqs = rb.plan(copy, "extra", "NHL", "2026-10-15", "2026-10-15")
    assert len(reqs) == 10
    assert {r.event_key for r in reqs} == {"NHL_THIN"}
    assert all(r.markets == ["h2h_3way"] and r.feed_markets == ["h2h_3_way"] for r in reqs)
    # one events listing for the game, then 10 credits a request
    assert rb.summarize(reqs)["credits"] == 10 * 10 + 1


def _rung_row(book, line, over, stamp="2026-10-15T15:18:00Z"):
    return {**_row(book, 0, stamp=stamp, market="alternate_totals"),
            "home_price": None, "away_price": None, "total_line": line,
            "over_price": over, "under_price": -over}


def test_every_rung_of_a_ladder_is_its_own_line(copy):
    last: dict = {}
    req = _req(markets=["alternate_totals"])
    first = rb.drop_unchanged_game_rows(copy, req, [
        _rung_row("fanduel", 5.5, 120), _rung_row("fanduel", 6.5, 160)], last)
    assert [r["total_line"] for r in first] == [5.5, 6.5]
    # the next pass: 5.5 unchanged, 6.5 moved
    second = rb.drop_unchanged_game_rows(copy, _req(at=_t("2026-10-15T16:20:00"),
                                                    markets=["alternate_totals"]), [
        _rung_row("fanduel", 5.5, 120, "2026-10-15T16:19:00Z"),
        _rung_row("fanduel", 6.5, 150, "2026-10-15T16:19:00Z")], last)
    assert [(r["total_line"], r["over_price"]) for r in second] == [(6.5, 150)]
    # two rungs share a book and a stamp; both are stored, once
    seen: set = set()
    rows = [_rung_row("betmgm", 5.5, 110), _rung_row("betmgm", 6.5, 150)]
    assert len(rb.drop_stored_game_rows(None, rows, seen)) == 2
    assert rb.drop_stored_game_rows(None, rows, seen) == []


def test_inplay_is_planned_every_five_minutes_from_the_start_to_draftkings_last_row(copy):
    for m in range(0, 41, 10):     # DraftKings in play, 23:00 to 23:40
        copy.execute("INSERT INTO odds VALUES ('NHL_THIN', 'NHL', 'h2h', 'draftkings', "
                     "'in_play', ?, NULL, -200, 170, NULL, NULL, NULL, NULL)",
                     [f"2026-10-15T23:{m:02d}:00Z"])
    reqs = rb.plan(copy, "inplay", "NHL", "2026-10-15", "2026-10-15")
    assert [r.at for r in reqs] == [_t("2026-10-15T23:05:00") + timedelta(minutes=5 * i)
                                    for i in range(8)]
    assert all(r.games == ["NHL_THIN"] and r.snapshot_type == "in_play" for r in reqs)
    assert set(reqs[0].books) == set(BOOKS)        # the game's own books before the start


def test_inplay_rows_are_typed_in_play_and_only_quotes_changed_after_the_start(monkeypatch):
    start = _t("2026-10-15T23:00:00")
    req = rb.Request("inplay", "NHL", _t("2026-10-15T23:20:00"), ["NHL_THIN"],
                     {"NHL_THIN": start}, ["h2h"], list(BOOKS), "in_play", "",
                     {"NHL_THIN": (start, _t("2026-10-15T23:40:00"))})
    rows = [{**_row("fanduel", -210, stamp="2026-10-15T23:18:00Z"), "snapshot_type": "in_play"},
            {**_row("betmgm", -115, stamp="2026-10-15T22:58:00Z"), "snapshot_type": "in_play"}]
    monkeypatch.setattr("data.ingestors.odds_ingestor._process_events", lambda *a, **k: ([], rows))
    keep, _ = rb.game_rows(req, [], "2026-10-15T23:19:40Z")
    assert [(r["bookmaker"], r["snapshot_type"]) for r in keep] == [("fanduel", "in_play")]
    # a snapshot from before the start is not an in-play price
    assert rb.game_rows(req, [], "2026-10-15T22:59:00Z")[0] == []


def test_props_cut_part_way_count_as_thinned():
    assert rb._is_thinned("prop", 5, 20)            # 5 rows a line against DraftKings' 20
    assert not rb._is_thinned("prop", 5, 8)         # about as many as DraftKings
    assert not rb._is_thinned("prop", 7, 40)        # more than 6 survived
    assert not rb._is_thinned("game", 5, 20)        # the main lines keep the strict rule


def test_only_events_near_a_planned_game_are_parsed(monkeypatch):
    """A bulk snapshot lists the whole slate; an event days from any planned
    game is dropped before the parser (and the NFL schedule lookup) sees it."""
    seen = []
    monkeypatch.setattr("data.ingestors.odds_ingestor._process_events",
                        lambda events, *a, **k: seen.extend(events) or ([], []))
    near = {"id": "near", "commence_time": "2026-10-15T23:00:00Z"}
    far = {"id": "far", "commence_time": "2026-10-19T23:00:00Z"}
    undated = {"id": "undated"}
    rb.game_rows(_req(), [near, far, undated], "2026-10-15T15:15:36Z")
    assert [e["id"] for e in seen] == ["near", "undated"]


def test_the_prop_plan_counts_rows_moved_to_the_archive(tmp_path, monkeypatch):
    """A game whose exact repeats went to the archive still holds them. Counted
    from the copy alone, DraftKings falls to 2 rows a line and the game stops
    looking like the cleanup's work, or (for a sport the cleanup never touched)
    starts looking thinned and gets bought again."""
    from scripts import archive_rows
    monkeypatch.setattr(archive_rows, "ARCHIVE_ROOT", tmp_path)
    con = duckdb.connect()
    con.execute("CREATE TABLE games (game_id VARCHAR, sport VARCHAR, commence_time VARCHAR)")
    con.execute("""CREATE TABLE player_prop_odds (prop_id BIGINT, game_id VARCHAR, game_date VARCHAR,
        player_name VARCHAR, market VARCHAR, bookmaker VARCHAR, snapshot_type VARCHAR,
        snapshot_at VARCHAR, line DOUBLE, over_price DOUBLE, under_price DOUBLE)""")
    con.execute("CREATE TABLE pipeline_runs (run_kind VARCHAR, started_at VARCHAR)")
    con.execute("INSERT INTO games VALUES ('NHL_G', 'NHL', '2026-10-15T23:00:00Z')")

    def prop(pid, book, ts):
        con.execute("INSERT INTO player_prop_odds VALUES (?, 'NHL_G', '2026-10-15', 'A', "
                    "'player_points', ?, 'open', ?, 0.5, -120, 100)", [pid, book, ts])
    prop(1, "fanduel", "2026-10-15T12:10:00Z")
    prop(2, "fanduel", "2026-10-15T22:50:00Z")
    for pid, ts in ((3, "12:00"), (6, "22:55")):
        prop(pid, "draftkings", f"2026-10-15T{ts}:00Z")
    assert rb.thinned_games(con, "prop", "NHL", "2026-10-15", "2026-10-15") == []
    # DraftKings' two middle rows were repeats, moved to the archive
    out = tmp_path / "player_prop_odds" / "repeat" / "2026-10"
    out.mkdir(parents=True)
    con.execute("CREATE TABLE moved AS SELECT * FROM player_prop_odds WHERE false")
    con.execute("INSERT INTO moved VALUES (4, 'NHL_G', '2026-10-15', 'A', 'player_points', 'draftkings', "
                "'open', '2026-10-15T15:00:00Z', 0.5, -120, 100), (5, 'NHL_G', '2026-10-15', 'A', "
                "'player_points', 'draftkings', 'open', '2026-10-15T18:00:00Z', 0.5, -120, 100)")
    con.execute(f"COPY moved TO '{(out / '2026-10-15.parquet').as_posix()}' (FORMAT PARQUET)")
    assert [g["game_id"] for g in rb.thinned_games(con, "prop", "NHL", "2026-10-15", "2026-10-15")] == ["NHL_G"]
    # a moved row the copy still holds is counted once
    con.execute("INSERT INTO player_prop_odds SELECT * FROM moved WHERE prop_id = 4")
    g = rb.thinned_games(con, "prop", "NHL", "2026-10-15", "2026-10-15")[0]
    assert g["dk_per_line"] == 4

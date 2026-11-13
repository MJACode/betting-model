"""Tennis ingestors: the archive parser, ESPN's scoreboard parser, the odds
quotes and the purchase plan. Every fixture is a hand-built copy of a real
row's shape (read 2026-11-13)."""
import json
from datetime import datetime, timedelta, timezone

from data.ingestors import tennis_archive as ta
from data.ingestors import tennis_espn as te
from data.ingestors import tennis_odds_history as toh

_HEADER = ("tourney_id,tourney_name,surface,draw_size,tourney_level,tourney_date,match_num,"
           "winner_id,winner_seed,winner_entry,winner_name,winner_hand,winner_ht,winner_ioc,"
           "winner_age,loser_id,loser_seed,loser_entry,loser_name,loser_hand,loser_ht,loser_ioc,"
           "loser_age,score,best_of,round,minutes,w_ace,w_df,w_svpt,w_1stIn,w_1stWon,w_2ndWon,"
           "w_SvGms,w_bpSaved,w_bpFaced,l_ace,l_df,l_svpt,l_1stIn,l_1stWon,l_2ndWon,l_SvGms,"
           "l_bpSaved,l_bpFaced,winner_rank,winner_rank_points,loser_rank,loser_rank_points")
_ROW = ("2023-9900,United Cup,Hard,18,A,20231231,400,128034,9,,Hubert Hurkacz,R,196,POL,28.8,"
        "104527,16,,Stan Wawrinka,R,183,SUI,40.7,6-3 3-6 6-3,3,F,114,18,0,90,63,52,9,14,8,9,"
        "10,1,78,49,38,15,13,5,7,83,710,156,397")


def test_archive_season_comes_from_the_tournament_not_the_date():
    rows = ta.parse_match_file(_HEADER + "\n" + _ROW + "\n", "ATP", "tour")
    assert len(rows) == 1
    rec = dict(zip(ta.MATCH_COLS, rows[0]))
    assert rec["season"] == 2023 and rec["tourney_date"] == "2023-12-31"
    assert rec["w_1stin"] == 63.0 and rec["winner_id"] == 128034
    assert rec["source"] == ta.SOURCE


def test_archive_drops_a_repeated_key_and_an_unkeyed_row():
    unkeyed = _ROW.replace(",128034,9,", ",,9,", 1)
    rows = ta.parse_match_file(_HEADER + "\n" + _ROW + "\n" + _ROW + "\n" + unkeyed + "\n",
                               "ATP", "tour")
    assert len(rows) == 1


def test_archive_skips_the_lowest_womens_itf_levels():
    low = _ROW.replace(",A,20231231,", ",15,20231231,")
    assert ta.parse_match_file(_HEADER + "\n" + low + "\n", "WTA", "qual_itf") == []
    assert len(ta.parse_match_file(_HEADER + "\n" + low + "\n", "ATP", "qual_chall")) == 1


def _comp(cid, status, p1, p2, *, round_name="Round 1"):
    def player(pid, name, won, games, order):
        return {"id": pid, "type": "athlete", "order": order, "winner": won,
                "athlete": {"displayName": name, "flag": {"alt": "Spain"}},
                "linescores": [{"value": float(g)} for g in games]}
    return {"id": cid, "date": "2025-08-30T15:00Z", "round": {"displayName": round_name},
            "venue": {"court": "Court 5", "fullName": "New York, USA"},
            "status": {"type": {"name": status, "completed": True}},
            "notes": [{"text": "note"}], "wasSuspended": False,
            "competitors": [player(*p1, 1), player(*p2, 2)]}


def _board(event_name, slug, comps, major=False):
    return {"events": [{"id": "189-2025", "name": event_name, "major": major,
                        "groupings": [{"grouping": {"slug": slug}, "competitions": comps}]}]}


def test_espn_reads_a_retirement_and_a_walkover():
    comps = [
        _comp("1", "STATUS_RETIRED", ("7924", "A Player", False, [6, 6, 1]),
              ("2567", "B Player", True, [3, 7, 4])),
        _comp("2", "STATUS_WALKOVER", ("1", "C Player", True, []), ("2", "D Player", False, [])),
    ]
    rows = {r[0]: dict(zip(te.COLS, r)) for r in te.parse(_board("US Open", "mens-singles", comps, True))}
    assert rows["1"]["status"] == "STATUS_RETIRED" and rows["1"]["p2_winner"] is True
    assert rows["1"]["p1_games"] == [6, 6, 1] and rows["1"]["season"] == 2025
    assert rows["2"]["status"] == "STATUS_WALKOVER"


def test_espn_best_of_comes_from_tour_and_event():
    one = [_comp("1", "STATUS_FINAL", ("1", "A", True, [6, 6]), ("2", "B", False, [3, 4]))]
    men_slam = dict(zip(te.COLS, te.parse(_board("US Open", "mens-singles", one, True))[0]))
    women_slam = dict(zip(te.COLS, te.parse(_board("US Open", "womens-singles", one, True))[0]))
    men_1000 = dict(zip(te.COLS, te.parse(_board("Rolex Shanghai Masters", "mens-singles", one))[0]))
    assert (men_slam["best_of"], women_slam["best_of"], men_1000["best_of"]) == (5, 3, 3)
    assert women_slam["tour"] == "WTA"


def test_espn_ignores_doubles():
    one = [_comp("1", "STATUS_FINAL", ("1", "A", True, [6, 6]), ("2", "B", False, [3, 4]))]
    assert te.parse(_board("US Open", "mens-doubles", one, True)) == []


def test_quote_rows_place_each_price_on_its_player():
    body = {"timestamp": "2025-08-30T11:55:39Z", "data": [{
        "id": "e1", "commence_time": "2025-08-30T15:00:00Z",
        "home_team": "Jannik Sinner", "away_team": "Denis Shapovalov",
        "bookmakers": [{"key": "pinnacle", "last_update": "2025-08-30T11:50:00Z", "markets": [
            {"key": "h2h", "outcomes": [{"name": "Denis Shapovalov", "price": 900},
                                        {"name": "Jannik Sinner", "price": -2000}]},
            {"key": "spreads", "outcomes": [{"name": "Jannik Sinner", "price": -110, "point": -8.5},
                                            {"name": "Denis Shapovalov", "price": -110, "point": 8.5}]},
            {"key": "totals", "outcomes": [{"name": "Over", "price": -105, "point": 29.5},
                                           {"name": "Under", "price": -115, "point": 29.5}]},
            {"key": "h2h_lay", "outcomes": []}]}]}]}
    rows = {r[6]: dict(zip(toh.QUOTE_COLS, r)) for r in toh.quote_rows("tennis_atp_us_open", body)}
    assert set(rows) == {"h2h", "spreads", "totals"}
    assert rows["h2h"]["home_price"] == -2000 and rows["h2h"]["away_price"] == 900
    assert rows["spreads"]["home_point"] == -8.5 and rows["spreads"]["away_point"] == 8.5
    assert rows["totals"]["total_point"] == 29.5 and rows["totals"]["under_price"] == -115
    assert rows["h2h"]["snapshot_ts"] == "2025-08-30T11:55:39Z"


def test_plan_counts_every_step_of_every_window_at_both_book_groups(tmp_path):
    sweep = [{"key": "k1", "year": 2025, "first": "2025-08-21T00:00:00Z", "last": "2025-08-22T00:00:00Z"},
             {"key": "k2", "year": 2025, "first": None, "last": "2025-09-01T00:00:00Z"}]
    f = tmp_path / "s.json"
    f.write_text(json.dumps(sweep), encoding="utf-8")
    windows = toh.load_windows(str(f))
    assert [w["key"] for w in windows] == ["k1"]          # a window with no start is not planned
    p = toh.plan(windows, timedelta(hours=1))
    assert p["asks"] == 25 and p["max_credits"] == 25 * 60


def test_the_meter_stops_at_the_ceiling_and_the_floor():
    m = toh.Meter(max_credits=100, floor=1000)
    m.before(60)
    m.spent = 60
    try:
        m.before(60)
        raise AssertionError("ceiling not enforced")
    except toh.Floor:
        pass
    m2 = toh.Meter(max_credits=10_000, floor=1000)
    m2.remaining = 1030
    try:
        m2.before(60)
        raise AssertionError("floor not enforced")
    except toh.Floor:
        pass


class _Rows:
    def fetchall(self):
        return []

    def fetchone(self):
        return None


class _FakeConn:
    """Enough of the database wrapper for walk_window: every read is empty."""
    def __init__(self):
        self.inserts = 0

    def execute(self, sql, params=None):
        return _Rows()

    def executemany(self, sql, rows):
        self.inserts += len(rows)

    def commit(self):
        pass

    def rollback(self):
        pass


class _Resp:
    def __init__(self, body):
        self.status_code, self._body = 200, body
        self.headers = {"x-requests-last": "30", "x-requests-remaining": "5000000"}

    def json(self):
        return self._body


def test_the_walk_jumps_a_gap_the_feed_kept_nothing_in(monkeypatch):
    """Snapshots every 5 minutes, except none from 02:00 to 08:00. Asked hourly
    from 00:00 to 10:00, the walk must ask at 00, 01, 02, then 08 (the feed's
    next real snapshot), 09, 10 -- never paying for the 03:00-07:00 copies."""
    t0 = datetime(2025, 8, 30, 0, 0, tzinfo=timezone.utc)
    gap_start, gap_end = t0 + timedelta(hours=2), t0 + timedelta(hours=8)
    asked = []

    def fake_get(meter, url, params, cost):
        when = datetime.fromisoformat(params["date"].replace("Z", "+00:00"))
        asked.append(when)
        snap = min(when, gap_start) if when < gap_end else when
        nxt = gap_end if snap == gap_start else snap + timedelta(minutes=5)
        body = {"timestamp": toh._iso(snap), "next_timestamp": toh._iso(nxt), "data": [{
            "id": "e1", "commence_time": "2025-08-31T15:00:00Z", "home_team": "A B",
            "away_team": "C D", "bookmakers": [{"key": "pinnacle", "markets": [
                {"key": "h2h", "last_update": toh._iso(snap), "outcomes": [
                    {"name": "A B", "price": -150 - len(asked)}, {"name": "C D", "price": 130}]}]}]}]}
        r = _Resp(body)
        return r, meter.after(r)

    monkeypatch.setattr(toh, "_get", fake_get)
    monkeypatch.setattr(toh, "_key", lambda: "k")
    meter = toh.Meter(max_credits=10_000, floor=0)
    out = toh.walk_window(_FakeConn(), meter, "tennis_atp_us_open", t0, t0 + timedelta(hours=10),
                          timedelta(hours=1))
    hours = sorted({a.hour for a in asked})
    assert hours == [0, 1, 2, 8, 9, 10], hours
    assert out["asks"] == 12                      # six snapshots, two book groups each


def test_shards_split_the_windows_and_their_ceilings_sum_to_the_plan(tmp_path):
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    sweep = [{"key": f"k{i}", "year": 2025, "first": toh._iso(base + timedelta(days=10 * i)),
              "last": toh._iso(base + timedelta(days=10 * i, hours=5 + i))} for i in range(7)]
    f = tmp_path / "s.json"
    f.write_text(json.dumps(sweep), encoding="utf-8")
    windows = toh.load_windows(str(f))
    parts = [toh.shard(windows, f"{i}/3") for i in range(3)]
    keys = sorted(w["key"] for part in parts for w in part)
    assert keys == sorted(w["key"] for w in windows)            # every window once
    step = timedelta(hours=1)
    assert sum(toh.plan(p, step)["max_credits"] for p in parts) == toh.plan(windows, step)["max_credits"]

"""data/ingestors/ncaab_odds_history: the first-half and team-total purchase at
three game-day times, and its test buy.

mike approved it on 2026-11-02: a test buy of about 50 games at 15:00Z on game
day (at most about 2,000 credits), then, if books post first-half lines by
then, the full 15:00Z buy for 2023-24..2025-26 (at most 687,686 credits);
18:00Z and tip minus 60 minutes follow on 2026-12-01. These pin when each time
is, which games each skips, the source each stamps, the test buy's sample and
its report, the jobs that run them, and that a dry run makes no call.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

import tracking.job_queue as jq
from data import prune_odds
from data.ingestors import nba_odds_history
from data.ingestors import ncaab_odds_history as h
from tests.test_ncaab_odds_history import (BOOK, GAMES, KSU_DUKE, REGISTRY, UK_DUKE, FakeConn,
                                           FakeMeter, Resp, _t)


# ── when each time is ────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode,game_date,tip,want", [
    # 15:00Z on the game's (Eastern) date, for a game that tips after it
    ("15z", "2026-01-17", "2026-01-18T00:00:00Z", "2026-01-17T15:00:00Z"),   # 7pm ET
    ("15z", "2026-01-17", "2026-01-17T15:05:00Z", "2026-01-17T15:00:00Z"),   # 10:05am ET
    ("15z", "2026-01-17", "2026-01-18T04:30:00Z", "2026-01-17T15:00:00Z"),   # 11:30pm ET: D, not D+1
    ("15z", "2026-01-17", "2026-01-17T15:00:00Z", None),                     # tips AT 15:00Z
    ("15z", "2026-01-17", "2026-01-17T14:00:00Z", None),                     # 9am ET: before it
    ("15z", "2026-01-17", None, None),                                       # no tip: could be in play
    # 18:00Z on the game's date
    ("18z", "2026-01-17", "2026-01-17T19:00:00Z", "2026-01-17T18:00:00Z"),   # 2pm ET
    ("18z", "2026-01-17", "2026-01-17T17:00:00Z", None),                     # noon ET: before it
    ("18z", "2026-01-17", "2026-01-17T18:00:00Z", None),
    ("18z", "2026-01-17", None, None),
    # tip minus 60 minutes, down to five
    ("tip60", "2026-01-17", "2026-01-18T00:07:00Z", "2026-01-17T23:05:00Z"),
    ("tip60", "2026-01-17", "2026-01-17T19:00:00Z", "2026-01-17T18:00:00Z"),
    ("tip60", "2026-01-17", "2026-01-17T14:00:00Z", "2026-01-17T13:00:00Z"),  # an early tip still has one
    ("tip60", "2026-01-17", None, None),
])
def test_each_game_day_time(mode, game_date, tip, want):
    got = h.deriv_instant(_t(tip) if tip else None, game_date, mode)
    assert got == (_t(want) if want else None)


def test_the_close_and_open_times_did_not_move():
    tip = _t("2026-01-18T00:07:00Z")
    assert h.deriv_instant(tip, "2026-01-17", "close") == _t("2026-01-17T23:55:00Z")
    assert h.deriv_instant(tip, "2026-01-17", "open") == _t("2026-01-17T04:05:00Z")
    assert h.deriv_instant(None, "2026-01-17", "open") == _t("2026-01-16T22:00:00Z")
    with pytest.raises(ValueError):
        h.deriv_instant(tip, "2026-01-17", "noon")


def test_each_time_has_its_own_source_and_the_prune_keeps_every_one():
    assert {m: h.DERIV_SOURCES[m] for m in h.GAMEDAY_MODES} == {
        "15z": "odds_api_ncaab_derivative_15z", "18z": "odds_api_ncaab_derivative_18z",
        "tip60": "odds_api_ncaab_derivative_tip60"}
    params: dict = {}
    prune_odds._unprotected(params, table="odds")
    for src in h.DERIV_SOURCES.values():
        assert src in prune_odds.PROTECTED_SOURCES and src in params["protected_sources"], src


# ── buying at a game-day time ───────────────────────────────────────────────

# Kentucky at Kansas State, 9am ET: tips before 15:00Z on its date.
EARLY = {"game_id": "NCAAB_2025-11-21_kansas-state_kentucky", "game_date": "2025-11-21",
         "commence_time": "2025-11-21T14:00Z", "home_espn_id": 2306, "away_espn_id": 96}
LISTING = [
    {"id": "e1", "commence_time": "2025-11-19T00:30:00Z", "home_team": "Duke Blue Devils",
     "away_team": "Kentucky Wildcats"},                       # UK-Duke, flipped
    {"id": "e2", "commence_time": "2025-11-20T17:00:00Z", "home_team": "Kansas State Wildcats",
     "away_team": "Duke Blue Devils"},                        # noon ET
    {"id": "e3", "commence_time": "2025-11-21T14:00:00Z", "home_team": "Kansas State Wildcats",
     "away_team": "Kentucky Wildcats"},                       # 9am ET
]


def _world(monkeypatch, games, done=frozenset(), close=None):
    """buy_derivatives over `games`, the feed answering every call; _deriv_done
    answers the close source from `close` and every other source from `done`."""
    monkeypatch.setattr(h, "check_precondition", lambda conn, seasons: {})
    monkeypatch.setattr(h, "_season_games", lambda conn, a, b: [dict(g) for g in games])
    reads = []

    def deriv_done(conn, ids, source):
        reads.append((source, list(ids)))
        have = close if source == h.NCAAB_DERIV_CLOSE_SOURCE and close is not None else done
        return set(have) & set(ids)
    monkeypatch.setattr(h, "_deriv_done", deriv_done)
    monkeypatch.setattr(h, "_resolver", lambda conn, games: h.EventResolver(REGISTRY, games))
    inserted = []
    monkeypatch.setattr(h, "_insert_odds", lambda conn, rows: inserted.extend(rows))

    def answer(url, params):
        if url.endswith("/events"):
            return Resp(body={"data": LISTING}, last="1")
        return Resp(body={"timestamp": params["date"], "data": {"bookmakers": [
            {"key": "fanduel", "markets": BOOK}]}}, last="40")
    return inserted, answer, reads


def _bought(meter) -> dict[str, str]:
    return {u.rsplit("/", 2)[-2]: p["date"] for u, p in meter.calls if "/events/" in u}


@pytest.mark.parametrize("mode,want", [
    ("15z", {"e1": "2025-11-18T15:00:00Z", "e2": "2025-11-20T15:00:00Z"}),
    ("18z", {"e1": "2025-11-18T18:00:00Z"}),                 # the noon tip is before 18:00Z
    ("tip60", {"e1": "2025-11-18T23:30:00Z", "e2": "2025-11-20T16:00:00Z",
               "e3": "2025-11-21T13:00:00Z"}),
])
def test_each_time_buys_its_games_at_its_instant_under_its_own_source(monkeypatch, mode, want):
    inserted, answer, _ = _world(monkeypatch, GAMES + [EARLY])
    meter = FakeMeter(answer)
    out = h.buy_derivatives(FakeConn(), meter, 2026, 2026, mode)
    assert _bought(meter) == want
    assert all(p["markets"] == "h2h_h1,spreads_h1,totals_h1,team_totals"
               for u, p in meter.calls if "/events/" in u)
    assert inserted and {r["source"] for r in inserted} == {h.DERIV_SOURCES[mode]}
    uk = {r["market"]: r for r in inserted if r["game_id"] == UK_DUKE["game_id"]}
    assert uk["spreads_h1"]["spread_home"] == 2.5             # ESPN's home number (Kentucky)
    assert out["events"] == len(want) and out.get("tips_before_instant", 0) == 0


def test_a_game_tipping_before_15z_is_never_bought_at_15z(monkeypatch):
    """The 9am ET game is not in the plan, so it is neither listed for nor bought."""
    _, answer, reads = _world(monkeypatch, GAMES + [EARLY])
    meter = FakeMeter(answer)
    h.buy_derivatives(FakeConn(), meter, 2026, 2026, "15z")
    assert "e3" not in _bought(meter)
    (source, ids), = reads
    assert source == h.NCAAB_DERIV_15Z_SOURCE and EARLY["game_id"] not in ids


def test_a_game_whose_feed_tip_is_before_15z_is_skipped_at_no_cost(monkeypatch):
    """ESPN has no tip; the feed's 14:00Z start decides it, before any call."""
    _, answer, _ = _world(monkeypatch, GAMES + [{**EARLY, "commence_time": None}])
    meter = FakeMeter(answer)
    out = h.buy_derivatives(FakeConn(), meter, 2026, 2026, "15z")
    assert "e3" not in _bought(meter)
    assert out["tips_before_instant"] == 1 and out.get("no_tip", 0) == 0


def test_a_game_already_bought_at_the_time_is_not_bought_again(monkeypatch):
    _, answer, _ = _world(monkeypatch, GAMES, done={UK_DUKE["game_id"]})
    meter = FakeMeter(answer)
    h.buy_derivatives(FakeConn(), meter, 2026, 2026, "15z")
    assert set(_bought(meter)) == {"e2"}


# ── the test buy's sample ────────────────────────────────────────────────────

# Five tip times in Eastern Standard Time, one per stratum: noon, 2pm, 5pm,
# 7:30pm, 10pm (the last two on the next UTC day).
TIPS = [("17:00", 0), ("19:00", 0), ("22:00", 0), ("00:30", 1), ("03:00", 1)]


def _season_slate(season: int, per_bucket: int) -> list[dict]:
    out = []
    for b, (hhmm, roll) in enumerate(TIPS):
        for i in range(per_bucket):
            d = datetime(season, 1, 2, tzinfo=timezone.utc) + timedelta(days=i)
            tip = d + timedelta(days=roll)
            out.append({"game_id": f"NCAAB_{d:%Y-%m-%d}_s{season}b{b}g{i}",
                        "game_date": f"{d:%Y-%m-%d}",
                        "commence_time": f"{tip:%Y-%m-%d}T{hhmm}:00Z",
                        "home_espn_id": 1000 + i, "away_espn_id": 2000 + i})
    return out


SLATE = [g for s in (2024, 2025, 2026) for g in _season_slate(s, 20)]


def _strata(games) -> Counter:
    return Counter((h.ncaab_season_label(g["game_date"]), h.tip_bucket(_t(g["commence_time"])))
                   for g in games)


def test_the_tip_time_strata():
    assert [h.tip_bucket(_t(f"2026-01-17T{x}:00Z")) for x in ("16:00", "17:59", "18:00", "21:00",
                                                              "23:59", "00:00")] == [
        "before 1pm ET", "before 1pm ET", "1-4pm ET", "4-7pm ET", "4-7pm ET", "7-9pm ET"]
    assert h.tip_bucket(_t("2026-01-18T02:00:00Z")) == "9pm ET or later"
    assert h.tip_bucket(_t("2026-01-18T06:30:00Z")) == "9pm ET or later"   # 1:30am ET is late
    assert h.tip_bucket(_t("2025-11-01T16:30:00Z")) == "before 1pm ET"     # 12:30 EDT


def test_the_sample_spreads_over_every_season_and_tip_time():
    got = h.sample_games(SLATE, 50)
    assert len(got) == 50 and len({g["game_id"] for g in got}) == 50
    per = _strata(got)
    assert len(per) == 15                                   # 3 seasons x 5 tip times
    assert set(per.values()) == {3, 4}                      # 50 = 5 x 4 + 10 x 3
    # the remainder spreads over the seasons, earliest tip times first
    assert Counter(s for s, _ in per.elements()) == {2026: 17, 2025: 17, 2024: 16}
    assert Counter(b for _, b in per.elements()) == {
        "before 1pm ET": 12, "1-4pm ET": 11, "4-7pm ET": 9, "7-9pm ET": 9, "9pm ET or later": 9}


def test_the_sample_is_deterministic_and_ignores_input_order():
    first = [g["game_id"] for g in h.sample_games(SLATE, 50)]
    assert first == [g["game_id"] for g in h.sample_games(list(reversed(SLATE)), 50)]
    # a game's rank is its own: adding games elsewhere never reshuffles a stratum
    more = SLATE + [g for g in _season_slate(2023, 5)]
    kept = [g for g in h.sample_games(more, 75) if h.ncaab_season_label(g["game_date"]) != 2023]
    assert set(first) <= {g["game_id"] for g in kept}
    assert first != [g["game_id"] for g in h.sample_games(SLATE, 50, seed="another")]


def test_a_short_stratum_is_used_up_and_the_rest_fill_the_sample():
    games = _season_slate(2026, 20)
    noon = [g for g in games if h.tip_bucket(_t(g["commence_time"])) == "before 1pm ET"][:2]
    rest = [g for g in games if h.tip_bucket(_t(g["commence_time"])) != "before 1pm ET"]
    got = h.sample_games(noon + rest, 30)
    assert len(got) == 30 and _strata(got)[(2026, "before 1pm ET")] == 2
    assert len(h.sample_games(noon, 50)) == 2                # fewer games than asked: all of them


def test_a_game_with_no_tip_is_never_sampled():
    assert h.sample_games([{**SLATE[0], "commence_time": None}], 5) == []


def test_the_test_buy_draws_only_games_with_a_stored_close_and_reads_little(monkeypatch):
    """plan_sample reads the close for 6 x N candidates and its own source for
    the N chosen, never the whole season; only a game with a close is drawn,
    and a game that tips before the time never is."""
    early = {**SLATE[0], "game_id": "NCAAB_early", "commence_time": f"{SLATE[0]['game_date']}T14:00:00Z"}
    games = SLATE + [early]
    priced = {g["game_id"] for g in SLATE[::2]}
    _, _, reads = _world(monkeypatch, games, close=priced)
    every, chosen, done, from_close = h.plan_sample(FakeConn(), 2024, 2026, "15z", 10)
    assert len(chosen) == 10 and from_close and done == set()
    assert {g["game_id"] for g in chosen} <= priced
    assert "NCAAB_early" not in {g["game_id"] for g in chosen}
    (src1, ids1), (src2, ids2) = reads
    assert src1 == h.NCAAB_DERIV_CLOSE_SOURCE and len(ids1) == h.SAMPLE_POOL * 10
    assert "NCAAB_early" not in ids1
    assert src2 == h.NCAAB_DERIV_15Z_SOURCE and ids2 == [g["game_id"] for g in chosen]
    assert len(every) == len(games)


def test_a_sample_is_only_for_the_game_day_times(monkeypatch):
    _world(monkeypatch, GAMES)
    with pytest.raises(ValueError, match="game-day"):
        h.buy_derivatives(FakeConn(), FakeMeter(lambda u, p: pytest.fail("a call")),
                          2026, 2026, "close", sample=5)


# ── the test buy's report ────────────────────────────────────────────────────

def test_the_test_buy_buys_only_its_sample_and_reports_per_book_and_market(monkeypatch, capsys):
    """Two of the slate's games are sampled: only they are bought, and the run
    ends with a table read back from `odds`, per book and market, of how many
    of them hold a quote at 15:00Z next to how many hold one at the close."""
    inserted, answer, _ = _world(monkeypatch, GAMES, close={UK_DUKE["game_id"], KSU_DUKE["game_id"]})
    stored = [
        (h.NCAAB_DERIV_15Z_SOURCE, "fanduel", "spreads_h1", UK_DUKE["game_id"]),
        (h.NCAAB_DERIV_15Z_SOURCE, "fanduel", "team_totals_home", UK_DUKE["game_id"]),
        (h.NCAAB_DERIV_CLOSE_SOURCE, "fanduel", "spreads_h1", UK_DUKE["game_id"]),
        (h.NCAAB_DERIV_CLOSE_SOURCE, "fanduel", "spreads_h1", KSU_DUKE["game_id"]),
        (h.NCAAB_DERIV_CLOSE_SOURCE, "draftkings", "spreads_h1", KSU_DUKE["game_id"]),
        (h.NCAAB_DERIV_CLOSE_SOURCE, "draftkings", "h2h_h1", KSU_DUKE["game_id"]),
    ]
    conn = FakeConn({"SELECT DISTINCT source, bookmaker, market, game_id FROM odds": stored})
    meter = FakeMeter(answer, ceiling=2_500)
    out = h.buy_derivatives(conn, meter, 2026, 2026, "15z", sample=2)
    assert set(_bought(meter)) == {"e1", "e2"} and out["sampled"] == 2
    printed = capsys.readouterr().out
    table = printed[printed.index("sample coverage"):]
    assert "2 games, drawn from games with a stored close" in table
    assert "1 hold a quote at 15z, 2 at the close" in table
    rows = {line.split()[0]: line.split()[1:] for line in table.splitlines()[3:]
            if line.startswith("  ") and not line.startswith("  any quote")}
    cols = list(h.REPORT_MARKETS)
    assert rows["fanduel"][cols.index("spreads_h1")] == "1/2"
    assert rows["fanduel"][cols.index("team_totals_home")] == "1/0"
    assert rows["draftkings"][cols.index("h2h_h1")] == "0/1"
    assert rows["any"][1 + cols.index("spreads_h1")] == "1/2"     # "any book" splits in two
    assert "7-9pm ET 1/1/1" in table and "before 1pm ET 0/1/1" in table
    (q, params), = [(q, p) for q, p in conn.sql if "SELECT DISTINCT source" in q]
    assert sorted(params[0]) == sorted([UK_DUKE["game_id"], KSU_DUKE["game_id"]])
    assert params[1] == [h.NCAAB_DERIV_15Z_SOURCE, h.NCAAB_DERIV_CLOSE_SOURCE]
    assert "in_play" in q


# ── the dry run ──────────────────────────────────────────────────────────────

def _dry_world(monkeypatch, http_calls):
    monkeypatch.setattr(h, "check_precondition", lambda conn, seasons: {2024: (6000, 6100)})
    monkeypatch.setattr(h, "_season_games", lambda conn, a, b: [dict(g) for g in SLATE])
    monkeypatch.setattr(h, "_deriv_done", lambda conn, ids, source: (
        set(ids) if source == h.NCAAB_DERIV_CLOSE_SOURCE else set()))
    # a resolver, so a dry run that did start buying would reach the feed
    monkeypatch.setattr(h, "_resolver", lambda conn, games: h.EventResolver(REGISTRY, games))
    conn = FakeConn()
    monkeypatch.setattr(h, "_read_only_connection", lambda: conn)
    monkeypatch.setattr(h, "get_connection", lambda: pytest.fail("a writable connection"))
    monkeypatch.setattr(h, "persist_quota", lambda conn: pytest.fail("a write"))

    def no_http(*a, **k):
        http_calls.append(a)
        raise AssertionError("an HTTP call in a dry run")
    monkeypatch.setattr(nba_odds_history.requests, "get", no_http)
    monkeypatch.setattr(h.Meter, "get", lambda self, url, params: no_http(url))
    return conn


def test_the_test_buy_s_dry_run_prints_its_games_and_makes_no_call(monkeypatch, capsys):
    calls: list = []
    conn = _dry_world(monkeypatch, calls)
    monkeypatch.setattr("sys.argv", ["x", "--derivatives", "15z", "--sample", "50",
                                     "--seasons", "2024", "2026", "--dry-run"])
    h.main()
    assert calls == []
    out = capsys.readouterr().out
    assert "test buy of 50 games" in out and "50 sampled, 0 already stored" in out
    assert out.count("would buy at ") == 50 and "15:00Z" in out
    assert "sample coverage, 15z" in out
    dates = len({g["game_date"] for g in h.sample_games(SLATE, 50)})
    assert f"to buy: 50 games on {dates} dates, at most {50 * 40 + dates:,} credits" in out
    assert not [q for q, _ in conn.sql if q.lstrip().upper().startswith(
        ("INSERT", "UPDATE", "DELETE", "CREATE"))]


@pytest.mark.parametrize("mode", h.GAMEDAY_MODES)
def test_a_full_dry_run_prints_the_plan_and_makes_no_call(monkeypatch, capsys, mode):
    calls: list = []
    _dry_world(monkeypatch, calls)
    monkeypatch.setattr("sys.argv", ["x", "--derivatives", mode, "--seasons", "2024", "2026"])
    h.main()
    assert calls == []
    out = capsys.readouterr().out
    n = sum(1 for g in SLATE if h.deriv_instant(_t(g["commence_time"]), g["game_date"], mode))
    assert f"{n:,} games" in out and f"to buy: {n:,} games" in out


@pytest.mark.parametrize("argv", [
    ["--derivatives", "close", "--sample", "5", "--seasons", "2024", "2026"],   # not a game-day time
    ["--derivatives", "15z", "--sample", "0", "--seasons", "2024", "2026"],
    ["--lines", "--sample", "5", "--seasons", "2024", "2026"],
    ["--derivatives", "15z", "--seasons", "2024", "2026", "--apply", "--max-credits", "2500"],
    ["--derivatives", "15z", "--seasons", "2024", "2026", "--apply", "--floor", "300000"],
    ["--derivatives", "15z", "--seasons", "2024", "2026", "--apply", "--max-credits", "2500",
     "--floor", "299999"],
])
def test_a_game_day_command_line_that_could_overspend_or_mislead_is_refused(monkeypatch, argv):
    calls: list = []
    _dry_world(monkeypatch, calls)
    monkeypatch.setattr(h, "buy_derivatives", lambda *a, **k: pytest.fail("bought"))
    monkeypatch.setattr("sys.argv", ["x"] + argv)
    with pytest.raises(SystemExit):
        h.main()
    assert calls == []


# ── the worker jobs ──────────────────────────────────────────────────────────

def _job_argv(monkeypatch, args) -> list[str]:
    seen = []
    monkeypatch.setattr(jq, "_run_script_main", lambda mod, argv: seen.append((mod, argv)) or "ok")
    jq._job_ncaab_odds_history(**jq._validate_ncaab_odds_history(args))
    (mod, argv), = seen
    assert mod == "data.ingestors.ncaab_odds_history"
    return argv


@pytest.mark.parametrize("args,want", [
    ({"mode": "deriv_15z_test", "max_credits": 2_500, "floor": 300_000},
     ["--derivatives", "15z", "--sample", "50", "--seasons", "2024", "2026", "--concurrency",
      "6", "--apply", "--max-credits", "2500", "--floor", "300000"]),
    ({"mode": "deriv_15z", "max_credits": 700_000, "floor": 300_000},
     ["--derivatives", "15z", "--seasons", "2024", "2026", "--concurrency", "6", "--apply",
      "--max-credits", "700000", "--floor", "300000"]),
    ({"mode": "deriv_18z", "max_credits": 650_000, "floor": 300_000},
     ["--derivatives", "18z", "--seasons", "2024", "2026", "--concurrency", "6", "--apply",
      "--max-credits", "650000", "--floor", "300000"]),
    ({"mode": "deriv_tip60", "max_credits": 700_000, "floor": 300_000},
     ["--derivatives", "tip60", "--seasons", "2024", "2026", "--concurrency", "6", "--apply",
      "--max-credits", "700000", "--floor", "300000"]),
    ({"mode": "deriv_15z", "max_credits": 700_000, "floor": 300_000, "dry_run": False},
     ["--derivatives", "15z", "--seasons", "2024", "2026", "--concurrency", "6", "--apply",
      "--max-credits", "700000", "--floor", "300000"]),
    ({"mode": "deriv_15z_test", "dry_run": True},
     ["--derivatives", "15z", "--sample", "50", "--seasons", "2024", "2026", "--dry-run"]),
    ({"mode": "deriv_tip60", "dry_run": True},
     ["--derivatives", "tip60", "--seasons", "2024", "2026", "--dry-run"]),
])
def test_each_game_day_job_runs_its_own_command_line(monkeypatch, args, want):
    assert _job_argv(monkeypatch, args) == want


@pytest.mark.parametrize("args", [
    {"mode": "deriv_15z", "max_credits": 700_001, "floor": 300_000},     # above its cap
    {"mode": "deriv_18z", "max_credits": 650_001, "floor": 300_000},
    {"mode": "deriv_tip60", "max_credits": 700_001, "floor": 300_000},
    {"mode": "deriv_15z_test", "max_credits": 2_501, "floor": 300_000},
    {"mode": "deriv_15z", "max_credits": 700_000},                        # no floor
    {"mode": "deriv_15z", "floor": 300_000},                              # no ceiling
    {"mode": "deriv_15z", "max_credits": 700_000, "floor": 299_999},      # under the floor
    {"mode": "deriv_15z", "dry_run": False},                              # a purchase, no limits
    {"mode": "deriv_15z", "dry_run": True, "max_credits": 700_000},       # a dry run buys nothing
    {"mode": "deriv_15z", "dry_run": "yes"},
    {"mode": "deriv_15z", "max_credits": 700_000, "floor": 300_000, "seasons": [2021, 2026]},
    {"mode": "deriv_15z_test", "max_credits": 2_500, "floor": 300_000, "games": 500},
    {"mode": "deriv_close", "dry_run": True},                             # the bought times take no dry run
])
def test_a_game_day_job_outside_its_approval_is_refused(args):
    with pytest.raises(ValueError):
        jq._validate_ncaab_odds_history(args)


def test_the_test_buy_fits_its_cap_and_the_full_buys_their_measured_ceilings():
    """50 games at 40 a game and one event list a date is 2,050 at most; each
    full buy's cap sits above the measured ceiling of 2026-11-02 (games listed
    by the time x 40 + one list a date)."""
    modes = jq.NCAAB_ODDS_HISTORY_MODES
    n = int(modes["deriv_15z_test"]["argv"][-1])
    assert n == 50 and n * (h.DERIV_EVENT_COST + h.LIST_COST) <= modes["deriv_15z_test"]["cap"]
    assert modes["deriv_15z"]["cap"] >= 17_181 * 40 + 446 == 687_686
    assert modes["deriv_18z"]["cap"] >= 15_713 * 40 + 445 == 628_965
    assert modes["deriv_tip60"]["cap"] >= 17_221 * 40 + 446 == 689_286
    assert all(modes[m]["seasons"] == (2024, 2026) for m in jq.NCAAB_GAMEDAY_DERIV_MODES)

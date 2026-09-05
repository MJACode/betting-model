"""Alternate (milestone) prop lines: stored under their own key, never
in a model's market, and requested on a credit budget.

Matt, 2026-09-05: "Yes to alternate lines." config.PROP_ALT_MARKETS has the
reasoning and the measured cost; the invariants pinned here are the ones a
careless edit would break silently:

  1. A standard market still yields ONE row per (player, book) per pass, so
     scorer._latest_dk_prop_row / paper_tracker._closing_dk_odds keep finding
     exactly one line.
  2. An alternate market yields one row per (player, line) under its own key.
  3. DraftKings' batter_home_runs_alternate 0.5 is still remapped to the
     canonical HR market (the HR model prices off it); its other lines are
     kept as alternates rather than dropped.
  4. An alternate line that duplicates the book's standard line is dropped.
  5. A 422 with alternates in the request retries WITHOUT them before the
     DK-only retry, so a wrong key can never cost the models their lines.
  6. The gate: alternates are requested when the newest alternate row is
     older than PROP_ALT_REFRESH_MIN, and NOT when the check itself fails.
  7. The all-books view keeps one newest row for a standard key and returns
     every row of the newest pass for an alternate key.
"""

import io
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import config
from data.ingestors import prop_odds_ingestor as m
from data.ingestors.prop_odds_ingestor import (
    ALT_LINE_MARKETS,
    _parse_prop_markets,
    alt_markets_due,
)

ROOT = Path(__file__).parent.parent


def _ou(market, player, lines, over_only=False):
    """One market block with an Over/Under pair (or Over only) per line."""
    outcomes = []
    for pt, over, under in lines:
        outcomes.append({"name": "Over", "description": player, "price": over, "point": pt})
        if not over_only:
            outcomes.append({"name": "Under", "description": player, "price": under, "point": pt})
    return {"key": market, "outcomes": outcomes}


ALLOWED = set(config.PROP_MARKETS_ALL) | {"batter_home_runs_alternate"} | set(config.PROP_ALT_MARKETS["MLB"])


def _parse(markets, book="draftkings"):
    return _parse_prop_markets(markets, "MLB_2026-09-05_WSH_LAD", "2026-09-05", "open", "t",
                               allowed_markets=ALLOWED, bookmaker=book)


# ── config ───────────────────────────────────────────────────────────────────

def test_every_alternate_key_is_the_alternate_of_a_market_we_pull():
    for sport, keys in config.PROP_ALT_MARKETS.items():
        base = set(m.PROP_MARKETS_BY_SPORT[sport])
        for k in keys:
            assert k.endswith("_alternate"), k
            assert k[:-len("_alternate")] in base, f"{k} has no standard market"
    assert "batter_home_runs_alternate" not in ALT_LINE_MARKETS, \
        "the HR alternate is model-facing and must be requested on every pass"


# ── the parser ───────────────────────────────────────────────────────────────

def test_a_standard_market_still_yields_one_row_per_player():
    rows = _parse([_ou("batter_hits", "Mookie Betts", [(0.5, -250, 184)])])
    assert [(r["market"], r["player_name"], r["line"]) for r in rows] == [("batter_hits", "Mookie Betts", 0.5)]


def test_an_alternate_market_yields_one_row_per_line_under_its_own_key():
    rows = _parse([
        _ou("batter_hits", "Mookie Betts", [(0.5, -250, 184)]),
        _ou("batter_hits_alternate", "Mookie Betts", [(1.5, 230, -320), (2.5, 800, None)], over_only=True),
    ])
    got = sorted((r["market"], r["line"], r["over_price"]) for r in rows)
    assert got == [("batter_hits", 0.5, -250), ("batter_hits_alternate", 1.5, 230), ("batter_hits_alternate", 2.5, 800)]
    alt = [r for r in rows if r["market"] == "batter_hits_alternate"]
    assert all(r["under_price"] is None for r in alt), "an Over-only milestone has no Under"


def test_the_hr_alternate_keeps_its_remap_and_now_keeps_its_other_lines():
    rows = _parse([_ou("batter_home_runs_alternate", "Aaron Judge", [(0.5, 320, -420), (1.5, 1400, None)], over_only=True)])
    got = sorted((r["market"], r["line"], r["over_price"]) for r in rows)
    assert got == [("batter_home_runs", 0.5, 320), ("batter_home_runs_alternate", 1.5, 1400)]


def test_an_alternate_that_duplicates_the_standard_line_is_dropped():
    rows = _parse([
        _ou("batter_hits", "Mookie Betts", [(0.5, -250, 184)]),
        _ou("batter_hits_alternate", "Mookie Betts", [(0.5, -245, None), (1.5, 230, None)], over_only=True),
    ])
    got = sorted((r["market"], r["line"]) for r in rows)
    assert got == [("batter_hits", 0.5), ("batter_hits_alternate", 1.5)]


def test_a_player_the_book_lists_at_1_5_keeps_the_0_5_alternate():
    """The case Matt saw: 23 hitters DraftKings posts at 1.5 only. The 1+
    milestone is the line the board's 0.5 column wants."""
    rows = _parse([
        _ou("batter_hits", "Bobby Witt Jr.", [(1.5, 120, -150)]),
        _ou("batter_hits_alternate", "Bobby Witt Jr.", [(0.5, -300, None), (1.5, 125, None)], over_only=True),
    ])
    got = sorted((r["market"], r["line"]) for r in rows)
    assert got == [("batter_hits", 1.5), ("batter_hits_alternate", 0.5)]


def test_an_alternate_milestone_with_no_number_is_not_a_line():
    rows = _parse([{"key": "batter_hits_alternate",
                    "outcomes": [{"name": "Over", "description": "X", "price": 300}]}])
    assert rows == []


# ── the request ──────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {"bookmakers": []}
        self.text = text
        self.headers = {}

    def json(self):
        return self._payload


def test_a_422_retries_without_the_alternates_before_going_dk_only(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(dict(params))
        if any(mk in ALT_LINE_MARKETS for mk in params["markets"].split(",")):
            return _Resp(422, text='{"message":"Unknown market batter_walks_alternate"}')
        return _Resp(200, {"bookmakers": [{"key": "draftkings", "markets": []}]})

    monkeypatch.setattr(m.requests, "get", fake_get)
    monkeypatch.setattr(m, "record_quota_headers", lambda r: None)
    markets = list(config.PROP_MARKETS_ALL) + ["batter_home_runs_alternate"] + config.PROP_ALT_MARKETS["MLB"]
    out = m._get_event_props("ev1", markets, "baseball_mlb")
    assert [k for k, _ in out] == ["draftkings"]
    assert len(calls) == 2, "one 422, one retry without the alternates"
    retried = calls[1]["markets"].split(",")
    assert not any(mk in ALT_LINE_MARKETS for mk in retried)
    assert "batter_home_runs_alternate" in retried, "the model-facing HR alternate stays"
    assert calls[1]["bookmakers"] == calls[0]["bookmakers"], "the book list is untouched on this retry"


def test_a_422_with_no_alternates_still_takes_the_dk_only_retry(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(dict(params))
        if params["bookmakers"] != config.ODDS_API_BOOKMAKER:
            return _Resp(422)
        return _Resp(200, {"bookmakers": [{"key": "draftkings", "markets": []}]})

    monkeypatch.setattr(m.requests, "get", fake_get)
    monkeypatch.setattr(m, "record_quota_headers", lambda r: None)
    out = m._get_event_props("ev1", list(config.PROP_MARKETS_ALL), "baseball_mlb")
    assert [k for k, _ in out] == ["draftkings"]
    assert len(calls) == 2 and calls[1]["bookmakers"] == config.ODDS_API_BOOKMAKER


# ── the gate ─────────────────────────────────────────────────────────────────

class _Conn:
    def __init__(self, newest=None, raise_=False):
        self.newest, self.raise_, self.sql = newest, raise_, []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        if self.raise_:
            raise RuntimeError("boom")
        return SimpleNamespace(fetchone=lambda: (self.newest,))


NOW = datetime(2026, 9, 5, 20, 0, tzinfo=timezone.utc)


def test_alternates_are_due_when_there_are_none_yet():
    assert alt_markets_due(_Conn(None), "MLB", "2026-09-05", now=NOW) is True


def test_alternates_are_due_only_once_the_newest_row_is_old_enough(monkeypatch):
    monkeypatch.setattr(m, "PROP_ALT_REFRESH_MIN", 30)
    fresh = "2026-09-05T15:45:00-04:00"   # 15 min before NOW (20:00Z)
    stale = "2026-09-05T15:20:00-04:00"   # 40 min before
    assert alt_markets_due(_Conn(fresh), "MLB", "2026-09-05", now=NOW) is False
    assert alt_markets_due(_Conn(stale), "MLB", "2026-09-05", now=NOW) is True


def test_the_gate_asks_only_about_this_sports_alternate_keys():
    c = _Conn("2026-09-05T15:45:00-04:00")
    alt_markets_due(c, "MLB", "2026-09-05", now=NOW)
    (_sql, params), = c.sql
    assert params == ("2026-09-05", config.PROP_ALT_MARKETS["MLB"])


def test_a_sport_with_no_alternates_never_asks():
    c = _Conn()
    assert alt_markets_due(c, "WNBA", "2026-09-05", now=NOW) is False
    assert c.sql == []


def test_a_failed_check_does_not_spend(monkeypatch):
    """A broken gate that requested alternates on every pass would double the
    approved budget silently; stale alternates are visible."""
    assert alt_markets_due(_Conn(raise_=True), "MLB", "2026-09-05", now=NOW) is False


def test_refresh_min_zero_means_every_pass(monkeypatch):
    monkeypatch.setattr(m, "PROP_ALT_REFRESH_MIN", 0)
    c = _Conn("2026-09-05T15:59:00-04:00")
    assert alt_markets_due(c, "MLB", "2026-09-05", now=NOW) is True
    assert c.sql == []


# ── the view ─────────────────────────────────────────────────────────────────

VIEW_SQL = io.open(ROOT / "data" / "migrations" / "alternate_prop_lines_view.sql", encoding="utf-8").read()
VIEW = "\n".join(ln for ln in VIEW_SQL.splitlines() if not ln.strip().startswith("--"))


def test_the_view_keeps_one_newest_row_for_a_standard_key():
    assert "WHERE pb.market NOT LIKE '%\\_alternate'" in VIEW
    assert VIEW.count("LIMIT 1") == 3, "seed, step and the top-1 probe -- the alternates branch adds none"


def test_the_view_returns_the_newest_pass_for_an_alternate_key():
    assert "WHERE pb.market LIKE '%\\_alternate'" in VIEW
    assert "AND p.snapshot_at = l.snapshot_at" in VIEW, "alternates must come from the probe's own pass"
    assert VIEW.count("(p.snapshot_type IS NULL OR p.snapshot_type <> 'in_play')") == 1, \
        "the in_play exclusion lives on the probe; the alternates branch inherits its snapshot"


def test_the_scorer_and_settlement_still_read_one_exact_market():
    for path, needle in (("models/scorer.py", "AND market      = %s"),
                         ("tracking/paper_tracker.py", "AND market = %s")):
        src = io.open(ROOT / path, encoding="utf-8").read()
        assert needle in src, f"{path} no longer filters on the exact market key"
        assert "_alternate" not in src.split("player_prop_odds")[1][:400]

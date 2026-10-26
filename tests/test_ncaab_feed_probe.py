"""scripts/ncaab_feed_probe: the free NCAAB feed check and its worker job.

It runs on the worker, where the keys are, and its printout lands in
worker_jobs.result and a Discord card. So it must never print a key (a requests
error quotes the URL, and an Odds API URL carries apiKey), it must name every
feed team the ESPN registry cannot place, and it must flag a "free" call that
billed. All HTTP here is fake.
"""
from __future__ import annotations

import pytest
import requests

import config
import tracking.job_queue as jq
from monitoring import registry as host_registry
from scripts import ncaab_feed_probe as fp

ODDS_KEY = "oddsKEY-0123456789abcdef"
CFBD_KEY = "cfbdKEY-fedcba9876543210"

REGISTRY = [
    {"espn_id": 150, "school": "Duke", "slug": "duke", "mascot": "Blue Devils",
     "display_name": "Duke Blue Devils", "short_name": "Duke", "abbreviation": "DUKE",
     "is_d1": True, "alt": []},
    {"espn_id": 96, "school": "Kentucky", "slug": "kentucky", "mascot": "Wildcats",
     "display_name": "Kentucky Wildcats", "short_name": "Kentucky", "abbreviation": "UK",
     "is_d1": True, "alt": []},
]
EVENTS = [
    {"id": "e1", "commence_time": "2026-11-04T00:30:00Z", "home_team": "Duke Blue Devils",
     "away_team": "Kentucky Wildcats"},
    {"id": "e2", "commence_time": "2026-11-03T23:00:00Z", "home_team": "Kentucky Wildcats",
     "away_team": "Mystery Moose"},
]


class Resp:
    def __init__(self, status=200, body=None, headers=None, content=b"[]"):
        self.status_code, self._body = status, body
        self.headers = headers or {}
        self.content = content

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def _http(events_last="0", cbbd_raises=True):
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        calls.append((url, dict(params or {}), dict(headers or {})))
        odds_h = {"x-requests-last": "0", "x-requests-remaining": "1999990"}
        if url.endswith("/v4/sports"):
            return Resp(body=[{"key": "basketball_ncaab", "active": True}], headers=odds_h)
        if url.endswith("/basketball_ncaab/events"):
            return Resp(body=EVENTS, headers={**odds_h, "x-requests-last": events_last})
        if url.endswith("/markets"):
            return Resp(body={"id": "e", "bookmakers": [
                {"key": "draftkings", "markets": [{"key": "h2h"}, {"key": "spreads"},
                                                  {"key": "team_totals"}]},
                {"key": "fanduel", "markets": [{"key": "h2h"}, {"key": "spreads_h1"}]}]},
                headers={**odds_h, "x-requests-last": "1"})
        if url.endswith("/teams"):
            if cbbd_raises:
                # what a real connection error looks like: the URL, key and all
                raise requests.ConnectionError(
                    f"HTTPSConnectionPool: Max retries exceeded with url: /teams?apiKey={CFBD_KEY}")
            return Resp(body=[{"id": 1}], headers={"X-CallLimit-Remaining": "999"})
        if url.endswith("/lines/providers"):
            return Resp(body=[{"id": 1, "name": "ESPN BET"}, {"id": 2, "name": "Bovada"}],
                        headers={"X-CallLimit-Remaining": "997"}, content=b"x" * 80)
        if url.endswith("/lines"):
            return Resp(body=[{"id": 9, "lines": [{"provider": "Bovada", "spread": -7.5}]}],
                        headers={"X-CallLimit-Remaining": "998"}, content=b"x" * 120)
        return Resp(body=[{"id": 5}], headers={"X-CallLimit-Remaining": "999"})
    return get, calls


class _Conn:
    def close(self):
        pass


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setattr(config, "ODDS_API_KEY", ODDS_KEY)
    monkeypatch.setattr(config, "CFBD_API_KEY", CFBD_KEY)
    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda: _Conn())
    monkeypatch.setattr(fp, "load_registry", lambda conn: REGISTRY)
    # one ESPN game: Kentucky home against Duke (the feed lists it the other way)
    from data.ingestors import ncaab_teams
    games = [{"game_id": "NCAAB_2026-11-03_duke_kentucky", "game_date": "2026-11-03",
              "commence_time": "2026-11-04T00:30Z", "home_espn_id": 96, "away_espn_id": 150}]
    monkeypatch.setattr(fp, "make_resolver", lambda conn, around, days_back=2, days_fwd=10: (
        lambda hn, an, ct: ncaab_teams.match_event(
            games, ncaab_teams.resolve_team_name(hn, REGISTRY),
            ncaab_teams.resolve_team_name(an, REGISTRY), ct)))
    monkeypatch.setattr(fp, "persist_quota", lambda conn: None)
    monkeypatch.setattr(fp, "record_quota_headers", lambda r: None)


def _run(monkeypatch, capsys, argv=(), **http):
    get, calls = _http(**http)
    monkeypatch.setattr(fp.requests, "get", get)
    fp.main(list(argv))
    return capsys.readouterr().out, calls


def test_the_probe_never_prints_a_key_even_when_a_call_raises(world, monkeypatch, capsys):
    out, calls = _run(monkeypatch, capsys)
    assert ODDS_KEY not in out and CFBD_KEY not in out
    assert "ConnectionError" in out                     # reported by its type only
    # the keys did go out, where they belong
    assert calls[0][1]["apiKey"] == ODDS_KEY
    cbbd = [c for c in calls if "collegebasketballdata" in c[0]]
    assert cbbd and all(c[2]["Authorization"] == f"Bearer {CFBD_KEY}" for c in cbbd)


def test_the_probe_names_every_feed_team_the_registry_cannot_place(world, monkeypatch, capsys):
    out, _ = _run(monkeypatch, capsys)
    assert "1 unresolved: ['Mystery Moose']" in out
    summary = out.split(fp.SUMMARY_MARK, 1)[1]
    assert "1 of 3 unresolved [Mystery Moose]" in summary
    assert "1 of 2 events on an ESPN game (1 reversed)" in summary
    assert "basketball_ncaab active=True; 2 events, earliest 2026-11-03T23:00:00Z" in summary


def test_a_free_call_that_billed_is_flagged(world, monkeypatch, capsys):
    out, _ = _run(monkeypatch, capsys, events_last="1")
    assert "events=1 (NOT ZERO)" in out.split(fp.SUMMARY_MARK, 1)[1]
    out, _ = _run(monkeypatch, capsys)
    assert "sports=0 events=0 (ok)" in out


def test_market_lists_are_read_for_the_soonest_events_only(world, monkeypatch, capsys):
    out, calls = _run(monkeypatch, capsys, argv=["--market-events", "1"])
    paid = [c for c in calls if c[0].endswith("/markets")]
    assert [c[0].rsplit("/", 2)[-2] for c in paid] == ["e2"]      # e2 tips first
    assert paid[0][1]["bookmakers"] == fp.BOOKS
    assert "fanduel: h2h (1/1), spreads_h1 (1/1)" in out
    out, calls = _run(monkeypatch, capsys, argv=["--market-events", "0"])
    assert not [c for c in calls if c[0].endswith("/markets")]


def test_college_basketball_data_status_providers_and_limits_are_reported(world, monkeypatch, capsys):
    out, calls = _run(monkeypatch, capsys, cbbd_raises=False)
    assert "cbbd providers: ['ESPN BET', 'Bovada']" in out
    assert "'X-CallLimit-Remaining': '997'" in out
    assert "cbbd lines by provider: {'Bovada': 1}" in out
    asked = {c[0].split("collegebasketballdata.com", 1)[1]: c[1] for c in calls
             if "collegebasketballdata" in c[0]}
    assert asked == {"/teams": {"season": 2027}, "/games": {"season": 2026, "team": "Duke"},
                     "/lines": {"season": 2026, "team": "Duke"}, "/lines/providers": {}}


def test_more_than_ten_market_events_is_refused(world, monkeypatch):
    for n in ("11", "-1"):
        with pytest.raises(SystemExit):
            fp.main(["--market-events", n])


def test_a_missing_billing_header_is_not_read_as_free_or_as_billed():
    assert fp._free_verdict("0", "0.0") == "ok"
    assert fp._free_verdict("0", "1") == "NOT ZERO"
    assert fp._free_verdict("?", "0") == "NOT READ"


class _RegistryConn:
    """Answers the ncaab_teams read the way the real table would."""
    ROWS = [(150, "Duke", "duke", "Blue Devils", "Duke Blue Devils", "Duke", "DUKE", True, ""),
            (96, "Kentucky", "kentucky", "Wildcats", "Kentucky Wildcats", "Kentucky", "UK", True, "")]

    def execute(self, sql, params=None):
        self._rows = self.ROWS if "FROM ncaab_teams" in sql else []
        return self

    def fetchall(self):
        return self._rows

    def rollback(self):
        pass


def test_the_probe_reads_the_registry_fresh_and_leaves_no_cache(monkeypatch, capsys):
    """REVIEW 2026-10-26. The worker runs every job in one process and
    ncaab_teams.load_registry caches what it read first, an empty list too.
    This probe is declared BEFORE the ESPN backfill creates ncaab_teams: a
    cache it left behind would make every later NCAAB job resolve nothing."""
    from data.ingestors import ncaab_teams as nt
    monkeypatch.setattr(nt, "_TEAM_CACHE", [])            # stale, from before the table existed
    monkeypatch.setattr(fp, "make_resolver", lambda *a, **k: None)
    rep = fp.Report(())
    fp._resolve_report(_RegistryConn(), rep, EVENTS, sorted(e["commence_time"] for e in EVENTS))
    assert "registry 2 teams, 1 unresolved: ['Mystery Moose']" in capsys.readouterr().out
    assert nt._TEAM_CACHE is None


def test_the_redaction_covers_any_text():
    rep = fp.Report((ODDS_KEY, "", CFBD_KEY))
    assert rep.clean(f"x?apiKey={ODDS_KEY}&b={CFBD_KEY}") == "x?apiKey=***&b=***"


# ── the worker job ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("args", [{"market_events": 11}, {"market_events": -1},
                                  {"market_events": True}, {"market_events": 3, "apply": True}])
def test_a_malformed_feed_probe_request_is_refused(args):
    with pytest.raises(ValueError):
        jq._validate_ncaab_feed_probe(args)


def test_the_feed_probe_defaults_to_five_market_events():
    assert jq._validate_ncaab_feed_probe({}) == {"market_events": 5}
    assert jq._validate_ncaab_feed_probe({"market_events": 0}) == {"market_events": 0}


def test_the_job_puts_the_summary_first_and_keeps_the_whole_printout(monkeypatch):
    seen = []
    text = "detail line\n" * 50 + fp.SUMMARY_MARK + "\nodds: active=True\ncbbd: teams 200"
    monkeypatch.setattr(jq, "_run_script_main", lambda mod, argv: seen.append((mod, argv)) or text)
    out = jq._job_ncaab_feed_probe(**jq._validate_ncaab_feed_probe({"market_events": 5}))
    assert seen == [("scripts.ncaab_feed_probe", ["--market-events", "5"])]
    assert list(out)[0] == "summary"                    # the card shows the first 900 characters
    assert out["summary"] == "odds: active=True\ncbbd: teams 200"
    assert out["stdout"] == text.strip() and out["truncated"] is False


def test_college_basketball_data_is_a_named_metered_host():
    host, name, category, paid = host_registry.classify("https://api.collegebasketballdata.com/lines")
    assert (name, category, paid) == ("CBBD", "stats", True)
    assert "CBBD" in host_registry.paid_apis()

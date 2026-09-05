"""College football player props: scoped, resolved, and measured before spending.

Matt, 2026-09-05: "Yes do it" — build the NCAAF prop ingestor, scoped to games
a book already prices, with the real cost measured on one Saturday before it
runs on a schedule.

The invariants pinned here are the ones that cost money or corrupt the table:

  1. SCOPE. A 120-game Saturday is 120 paid calls. Only events DraftKings has
     already lined are pulled, under a hard per-pass ceiling, and every drop
     is counted so a shrinking slate is legible rather than mysterious.
  2. THE GAME ID IS RESOLVED. "Ohio State Buckeyes" must become the CFBD
     school, and an event that resolves to no known game is SKIPPED — an
     orphan prop row joins to nothing and looks like coverage forever.
  3. A rejected market chunk costs its own markets and no others, and
     alternates never share a chunk with a standard market.
  4. Only books we asked for are ever written.
  5. The probe writes NOTHING.
  6. NCAAF has no prop model and this does not add one.
"""

import io
from pathlib import Path

import pytest

import config
from data.ingestors import ncaaf_prop_odds_ingestor as m

ROOT = Path(__file__).parent.parent


# ── config ───────────────────────────────────────────────────────────────────

def test_every_ncaaf_alternate_has_a_standard_market_we_pull():
    base = set(config.PROP_MARKETS_NCAAF)
    for k in config.PROP_ALT_MARKETS["NCAAF"]:
        assert k.endswith("_alternate"), k
        assert k[:-len("_alternate")] in base, f"{k} has no standard market"


def test_college_props_are_off_until_the_probe_is_read():
    """Matt approved the build on the condition the cost is measured first."""
    import os
    if os.environ.get("RUN_NCAAF_PROP_ODDS") is None:
        assert config.RUN_NCAAF_PROP_ODDS is False


def test_ncaaf_has_no_prop_model_and_this_does_not_add_one():
    ncaaf_models = [x for x in config.MODELS if "ncaaf" in x]
    assert ncaaf_models, "sanity: NCAAF still has its game-level models"
    assert not [x for x in ncaaf_models if "prop" in x], \
        "a college prop row is research, not a pick"


# ── chunking ─────────────────────────────────────────────────────────────────

def test_alternates_never_share_a_chunk_with_a_standard_market():
    want = list(config.PROP_MARKETS_NCAAF) + list(config.PROP_ALT_MARKETS["NCAAF"])
    chunks = m._market_chunks(want)
    assert [mk for c in chunks for mk in c] == want, "every market, once, in order"
    for c in chunks:
        assert len({mk.endswith("_alternate") for mk in c}) == 1, f"mixed chunk: {c}"
        assert len(c) <= m.MARKET_CHUNK


# ── scope ────────────────────────────────────────────────────────────────────

class _Conn:
    """games / odds for one Saturday, in the shape scope_events queries."""

    def __init__(self, known, lined):
        self.known, self.lined = known, lined

    def execute(self, sql, params=None):
        rows = [(g,) for g in (self.lined if "o.bookmaker" in sql else self.known)]
        return type("R", (), {"fetchall": lambda _self: rows})()


EVENTS = [
    {"id": "1", "home_team": "Kansas Jayhawks", "away_team": "Long Island University Sharks"},
    {"id": "2", "home_team": "USC Trojans", "away_team": "Fresno State Bulldogs"},
    {"id": "3", "home_team": "Carthage Red Men", "away_team": "Lakeland Muskies"},
]
DATE = "2026-09-05"


@pytest.fixture
def resolver(monkeypatch):
    """The real resolver needs the schools table; the mapping it performs is
    what matters here, so it is stubbed to the same shape it returns."""
    names = {
        "Kansas Jayhawks": "Kansas",
        "Long Island University Sharks": "Long Island University",
        "USC Trojans": "USC",
        "Fresno State Bulldogs": "Fresno State",
        "Carthage Red Men": "Carthage",
        "Lakeland Muskies": "Lakeland",
    }
    monkeypatch.setattr(m, "resolve_odds_api_school",
                        lambda n, conn=None: names.get(n, n))


KANSAS = "NCAAF_2026-09-05_long-island-university_kansas"
USC = "NCAAF_2026-09-05_fresno-state_usc"
CARTHAGE = "NCAAF_2026-09-05_lakeland_carthage"


def test_only_games_a_book_already_prices_are_pulled(resolver):
    """The measured Saturday: 120 games, 70 with a DK line. Division III has
    no player props to sell us."""
    conn = _Conn(known=[KANSAS, USC, CARTHAGE], lined=[KANSAS, USC])
    kept, dropped = scope(conn)
    assert [gid for _ev, gid in kept] == [KANSAS, USC]
    assert dropped["no_dk_line"] == 1


def test_an_event_we_cannot_resolve_to_a_game_is_skipped(resolver):
    conn = _Conn(known=[USC], lined=[USC, KANSAS, CARTHAGE])
    kept, dropped = scope(conn)
    assert [gid for _ev, gid in kept] == [USC]
    assert dropped["unresolved"] == 2, "an orphan prop row joins to nothing"


def test_the_game_id_is_the_resolved_school_not_the_feed_name(resolver):
    conn = _Conn(known=[USC], lined=[USC])
    kept, _ = scope(conn)
    assert kept[0][1] == USC
    assert "trojans" not in kept[0][1] and "bulldogs" not in kept[0][1]


def test_the_per_pass_ceiling_is_hard(resolver):
    conn = _Conn(known=[KANSAS, USC, CARTHAGE], lined=[KANSAS, USC, CARTHAGE])
    kept, dropped = scope(conn, max_events=2)
    assert len(kept) == 2 and dropped["over_cap"] == 1


def test_the_dk_line_gate_can_be_turned_off_for_a_backfill(resolver):
    conn = _Conn(known=[KANSAS, USC, CARTHAGE], lined=[])
    kept, dropped = scope(conn, require_dk_line=False)
    assert len(kept) == 3 and dropped["no_dk_line"] == 0


def scope(conn, **kw):
    kw.setdefault("require_dk_line", True)
    kw.setdefault("max_events", 80)
    return m.scope_events(conn, EVENTS, DATE, **kw)


# ── the event call ───────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status, markets, books=("draftkings",)):
        self.status_code = status
        self.headers = {"x-requests-used": "100"}
        self.text = ""
        self._m, self._b = markets, books

    def json(self):
        return {"bookmakers": [{"key": b, "markets": [{"key": mk, "outcomes": [{"name": "Over"}]}
                                                      for mk in self._m]} for b in self._b]}


def test_a_rejected_chunk_costs_only_its_own_markets(monkeypatch):
    """The likeliest 422 for college is a market the API does not serve here."""
    def fake_get(url, params=None, timeout=None):
        mk = params["markets"].split(",")
        return _Resp(422 if any(x.endswith("_alternate") for x in mk) else 200, mk)

    monkeypatch.setattr(m.requests, "get", fake_get)
    monkeypatch.setattr(m, "record_quota_headers", lambda r: None)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    want = list(config.PROP_MARKETS_NCAAF) + list(config.PROP_ALT_MARKETS["NCAAF"])
    per_book, _credits = m._event_props("ev", want)
    got = {mk["key"] for _b, ms in per_book for mk in ms}
    assert got == set(config.PROP_MARKETS_NCAAF)
    assert not any(x.endswith("_alternate") for x in got)


def test_a_book_we_did_not_ask_for_is_never_written(monkeypatch):
    monkeypatch.setattr(m.requests, "get", lambda url, params=None, timeout=None:
                        _Resp(200, ["player_pass_yds"], books=("draftkings", "some_new_book")))
    monkeypatch.setattr(m, "record_quota_headers", lambda r: None)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    per_book, _ = m._event_props("ev", ["player_pass_yds"])
    assert [b for b, _ in per_book] == ["draftkings"]


# ── the probe ────────────────────────────────────────────────────────────────

def test_the_probe_writes_nothing(monkeypatch, resolver):
    """It exists to measure. A probe that inserts is a pull with a nice name."""
    conn = _Conn(known=[KANSAS, USC], lined=[KANSAS, USC])
    conn.commit = lambda: None
    conn.close = lambda: None
    monkeypatch.setattr(m, "get_connection", lambda: conn)
    monkeypatch.setattr(m, "persist_quota", lambda c: None)
    monkeypatch.setattr(m, "_get_events", lambda d: EVENTS)
    monkeypatch.setattr(m, "_event_props",
                        lambda ev, mk: ([("draftkings", [{"key": "player_pass_yds",
                                                          "outcomes": [{"name": "Over"}]}])], 24))

    def boom(*a, **k):
        raise AssertionError("the probe must not write")

    monkeypatch.setattr(m, "_insert_prop_odds", boom)
    out = m.probe(DATE, limit_events=2)
    assert out["events_probed"] == 2
    assert out["credits_per_event"] == 24
    assert out["events_in_scope"] == 2
    assert out["projected_one_pass"] == 48
    assert out["markets_returned"] == {"player_pass_yds": 2}


# ── the worker job ───────────────────────────────────────────────────────────

def test_the_job_defaults_to_probing_and_caps_its_sample():
    from tracking.job_queue import JOBS, _validate_ncaaf_prop_odds as v
    assert "ncaaf_prop_odds" in JOBS
    assert v({})["probe"] is True, "the default must be the safe one"
    with pytest.raises(ValueError):
        v({"limit_events": 99})
    with pytest.raises(ValueError):
        v({"date": "saturday"})


# ── the app's half ───────────────────────────────────────────────────────────

def test_the_app_maps_ncaaf_stats_only_to_markets_we_pull():
    """NCAAF is the one sport whose board reaches its market without a model
    (it has none), so the two lists have to be checked against each other."""
    src = io.open(ROOT / "mobile" / "src" / "lib" / "statCatalog.ts",
                  encoding="utf-8").read()
    block = src.split("NCAAF_STAT_TO_MARKET")[1].split("};")[0]
    mapped = {line.split("'")[1] for line in block.splitlines() if "'player_" in line}
    assert mapped, "the map is present"
    assert mapped <= set(config.PROP_MARKETS_NCAAF), \
        f"the board asks for markets the ingestor never pulls: {mapped - set(config.PROP_MARKETS_NCAAF)}"
    assert "player_pass_yds" in mapped and "player_tackles_assists" in mapped

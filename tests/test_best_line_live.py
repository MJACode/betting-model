"""Line shopping for LIVE picks: the data was already paid for and thrown away.

Measured 2026-08-30: 0 of 107 August live BETs carried a best price, while six
non-DK books had in-play rows for the same games in the same poll batch. The
pre-game half has worked since 08-29 (100% coverage); the live half was never
wired.

Most of these pin REFUSALS, because the one way line shopping can make a pick
WORSE is by preferring a book that stopped updating -- a frozen book wins a
naive max() precisely BECAUSE it froze.

SINCE 2026-09-10 THE BEST IN-PLAY PRICE ALSO DECIDES (mike, "yes do
everything", widening the 2026-09-09 pre-game flip to the live lanes). The
tripwire that asserted the live decision path never saw the best price is
inverted below: _make_live_pick decides, sizes and stamps decision_* at the
better of DraftKings and the best bettable quote, through the same
classify_live_signal the DK-only lane used, with the stale-line cap kept on the
DK edge. Measured before the flip on the 99 settled mlb_live_total_runs BETs
since 08-30: +7.48 units at DraftKings, +10.41 at the stamped best price; 59
of the 99 had a non-DK best, 1.81pp cheaper on average.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import config
from models import live_scorer
from models.scorer import (_best_live_price, _best_live_side, _live_book_quotes,
                           _live_decision_quote, _live_quote_is_on_offer,
                           _tag_live)

ROOT = Path(__file__).parent.parent


def _ts(age_sec: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=age_sec)).isoformat()


class _FakeConn:
    """execute().fetchall(), the shape data.db.DBConnection exposes."""

    def __init__(self, rows):
        self._rows = rows
        self.sql = None

    def execute(self, sql, params=None):
        self.sql = sql
        return self

    def fetchall(self):
        return self._rows


# One row in _live_book_quotes' SELECT order: book, home/away/over/under price,
# the four links, total_line, spread_home, snapshot_at. `price` lands on the
# OVER side, which is what every test below asks for.
def _row(book, price, line=8.5, age=5, link="u", ts=None):
    return (book, None, None, price, None, None, None, link, None, line, None,
            _ts(age) if ts is None else ts)


# -- it finds the better price ------------------------------------------------

def test_it_picks_the_best_price_across_books_at_the_same_line():
    conn = _FakeConn([_row("draftkings", -115), _row("fanduel", -105),
                      _row("betmgm", -110)])
    best = _best_live_price(conn, "G", "totals", "over", 8.5)
    assert best["book"] == "fanduel" and best["odds"] == -105


def test_it_reads_in_play_rows_not_pregame_ones():
    """The pre-game sibling excludes in_play on purpose; this one requires it."""
    conn = _FakeConn([_row("draftkings", -110)])
    _best_live_price(conn, "G", "totals", "over", 8.5)
    assert "snapshot_type = 'in_play'" in conn.sql


def test_plus_money_beats_minus_money():
    # Was written against bovada, which is no longer offered as a price to take
    # (config.BEST_LINE_EXCLUDE_BOOKMAKERS, 2026-09-02). The property under test
    # is the sign flip, so any bettable second book carries it.
    conn = _FakeConn([_row("draftkings", -110), _row("betmgm", 105)])
    assert _best_live_price(conn, "G", "totals", "over", 8.5)["odds"] == 105


# -- the refusals -------------------------------------------------------------

def test_a_book_on_a_different_line_is_not_a_better_price():
    """CLAUDE.md 1c: Over 9.0 at -105 is not a better price on Over 8.5, it is
    a different bet."""
    conn = _FakeConn([_row("draftkings", -115, line=8.5),
                      _row("fanduel", -101, line=9.5)])
    best = _best_live_price(conn, "G", "totals", "over", 8.5)
    assert best["book"] == "draftkings", "the 9.5 quote is a different bet"


def test_a_frozen_book_cannot_win_by_having_stopped_updating():
    """THE failure mode this guard exists for. A book that froze 5 minutes ago
    still shows its old, better number -- and a naive max() would take it."""
    conn = _FakeConn([_row("draftkings", -115, age=5),
                      _row("betmgm", +130, age=400)])
    best = _best_live_price(conn, "G", "totals", "over", 8.5)
    assert best["book"] == "draftkings", "a stale +130 is not on offer"


def test_freshness_is_bounded_by_the_live_odds_knob():
    assert _live_quote_is_on_offer(_ts(config.LIVE_ODDS_MAX_AGE_SEC - 5))
    assert not _live_quote_is_on_offer(_ts(config.LIVE_ODDS_MAX_AGE_SEC + 30))


def test_the_age_gate_is_the_value_that_was_actually_decided():
    """30s, mike, 2026-08-30 -- REAFFIRMED, not a reversion.

    The identical value was rolled back on 2026-08-29 because it sits below
    DK's 47s median republish and declines ~60% of passes. That concern was put
    to him twice with the numbers and he chose 30 anyway: fewer live bets, in
    exchange for the ones taken being priced at a line that is on the board.

    This test exists so the 2026-08-29 note cannot be read later as grounds for
    quietly restoring 60/90. That argument has been heard and decided; changing
    it needs a new decision, not a rediscovery of the old one.
    """
    assert config.LIVE_ODDS_MAX_AGE_SEC == 30


def test_a_timestamp_it_cannot_parse_fails_OPEN():
    """These columns are TEXT in mixed shapes. A parse failure must not silently
    delete a book from the comparison."""
    assert _live_quote_is_on_offer(None)
    assert _live_quote_is_on_offer("not-a-date")


def test_the_Z_suffix_shape_parses():
    """'Z' vs '+00:00' is the section 7 trap; a string compare keeps stale rows."""
    stamp = (datetime.now(timezone.utc) - timedelta(seconds=5)
             ).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert _live_quote_is_on_offer(stamp)


def test_a_book_with_no_price_is_skipped():
    conn = _FakeConn([_row("draftkings", None), _row("fanduel", -108)])
    assert _best_live_price(conn, "G", "totals", "over", 8.5)["book"] == "fanduel"


def test_no_quotes_at_all_is_none_not_a_crash():
    assert _best_live_price(_FakeConn([]), "G", "totals", "over", 8.5) is None


def test_an_unknown_side_returns_none():
    """UFC 'decision' and similar are not two-way markets."""
    assert _best_live_price(_FakeConn([_row("draftkings", -110)]),
                            "G", "h2h", "decision", None) is None


# -- wiring -------------------------------------------------------------------

def test_tag_live_uses_a_private_key_that_the_insert_strips():
    p = _tag_live({"pick_side": "over"}, ("G", "totals"))
    assert p["_live_ctx"] == ("G", "totals")
    src = (ROOT / "models/scorer.py").read_text(encoding="utf-8")
    assert 'p.pop("_live_ctx", None)' in src, "an unstripped key breaks the INSERT"


def test_both_live_loops_actually_CALL_the_tag():
    """CLAUDE.md 1b: one stamp, both sports -- not two implementations.

    Asserts the CALL, not the import. The first version of this test checked
    only that the name appeared in the file, and it passed with the NCAAF call
    replaced by `pass` -- a test that passes without the fix is not a test.
    """
    mlb = (ROOT / "models/live_scorer.py").read_text(encoding="utf-8")
    assert "_tag_live(p, (game_id, market))" in mlb

    ncaaf = (ROOT / "ncaaf_live/gameday.py").read_text(encoding="utf-8")
    assert "_tag_live(p, (game_id, mkt))" in ncaaf, (
        "NCAAF live picks would be written with no best price")


def test_the_ncaaf_market_map_agrees_with_the_registry():
    """gameday declares its markets locally (its _write_picks runs under a
    stubbed config in the notify tests). This is what stops that copy drifting
    from config.LIVE_MODELS, which is the real source."""
    from ncaaf_live.gameday import LIVE_MODEL_MARKETS
    for model_id, market in LIVE_MODEL_MARKETS.items():
        assert config.LIVE_MODELS[model_id][1] == market, (
            f"{model_id}: gameday says {market}, the registry disagrees")


def test_the_live_decision_path_reads_the_best_price():
    """INVERTED 2026-09-10. Until then this asserted that no best_* name reached
    the live signal/edge/Kelly path (the models decided on DraftKings only).
    Now the builder must take the best bettable in-play quote INTO the
    decision, through _live_decision_quote, before it can return None."""
    src = (ROOT / "models/live_scorer.py").read_text(encoding="utf-8")
    body = src[src.index("def _make_live_pick"):src.index("def _score_live_model")]
    assert "_live_decision_quote(dk_odds, best)" in body
    assert body.index("_live_decision_quote(") < body.index("classify_live_signal(")
    assert "cap_edge=edge" in body, "the stale-line cap stays on the DK edge"
    score = src[src.index("def _score_live_model"):src.index("    return [_tag_live")]
    assert "_live_book_quotes(conn, game_id, market" in score
    assert score.count("best=_best_live_side(quotes, side, market") == 2, (
        "both the binary and the poisson branch must pass the best quote")


def _live_pick(dk, best, prob=0.75, monkeypatch=None):
    return live_scorer._make_live_pick(
        "G", "mlb_live_total_runs", "2026-09-10", "over", "Over 8.5 (live)",
        prob, dk, 8.5, 1000.0, {"inning": 5, "home_score": 2, "away_score": 1},
        "2026-09-10T23:05:00Z", "dk-link", best=best)


@pytest.fixture
def _open_cut(monkeypatch):
    """A cut the fixtures can straddle: prob 0.70, edge 0.14, no EV floor."""
    monkeypatch.setattr(live_scorer, "MODEL_PROB_THRESHOLDS", {"mlb_live_total_runs": 0.70})
    monkeypatch.setattr(live_scorer, "MODEL_EDGE_THRESHOLDS", {"mlb_live_total_runs": 0.14})
    monkeypatch.setattr(live_scorer, "MODEL_MIN_EV", {})
    monkeypatch.setattr(live_scorer, "PAUSED_MODELS", set())
    monkeypatch.setattr(live_scorer, "DECIDE_ON_CALIBRATED_PROB", False)
    monkeypatch.setattr(live_scorer, "LIVE_MAX_EDGE_CAP", 0.20)
    monkeypatch.setattr(config, "DECIDE_ON_BEST_PRICE", True)
    import models.scorer as sc
    monkeypatch.setattr(sc, "DECIDE_ON_BEST_PRICE", True)


def test_a_dead_zone_pick_at_dk_is_a_bet_at_the_better_price(_open_cut):
    """prob 0.75 vs DK -160: implied 0.615, edge 0.135 < the 0.14 cut -> no row
    at DraftKings. FanDuel -120 at the same line: implied 0.545, edge 0.205 ->
    BET, decided, sized and stamped there; dk_* keep the DraftKings numbers."""
    assert _live_pick(-160.0, None) is None, "dead zone at DraftKings"
    p = _live_pick(-160.0, {"book": "fanduel", "odds": -120.0, "link": "fd"})
    assert p is not None and p["signal_type"] == "BET"
    assert p["decision_book"] == "fanduel" and p["decision_odds"] == -120.0
    assert p["dk_odds"] == -160.0 and abs(p["edge"] - (0.75 - 160 / 260)) < 1e-4
    assert abs(p["decision_edge"] - (0.75 - 120 / 220)) < 1e-4
    assert p["kelly_fraction"] > 0 and p["recommended_bet"] > 0
    assert p["best_book"] == "fanduel" and p["best_odds"] == -120.0


def test_the_stake_is_sized_at_the_deciding_price(_open_cut):
    # prob 0.70 keeps the DK edge (0.176) under the 0.20 stale-line cap
    at_dk = _live_pick(-110.0, None, prob=0.70)
    at_best = _live_pick(-110.0, {"book": "betmgm", "odds": 105.0, "link": None}, prob=0.70)
    assert at_dk["signal_type"] == at_best["signal_type"] == "BET"
    assert at_best["kelly_fraction"] > at_dk["kelly_fraction"]
    assert at_best["decision_book"] == "betmgm"


def test_a_tie_keeps_draftkings(_open_cut):
    p = _live_pick(-110.0, {"book": "fanduel", "odds": -110.0, "link": "fd"}, prob=0.70)
    assert p["decision_book"] == "draftkings" and p["decision_odds"] == -110.0


def test_a_worse_best_price_never_decides(_open_cut):
    """Cannot happen through _best_live_side (DK is in the set) but the builder
    must not trust its caller: a stale 'best' worse than DK stays at DK."""
    p = _live_pick(-110.0, {"book": "fanduel", "odds": -125.0, "link": "fd"}, prob=0.70)
    assert p["decision_book"] == "draftkings" and p["decision_odds"] == -110.0


def test_the_flag_off_decides_at_draftkings(_open_cut, monkeypatch):
    import models.scorer as sc
    monkeypatch.setattr(sc, "DECIDE_ON_BEST_PRICE", False)
    assert _live_pick(-160.0, {"book": "fanduel", "odds": -120.0, "link": "fd"}) is None
    p = _live_pick(-110.0, {"book": "fanduel", "odds": 105.0, "link": "fd"}, prob=0.70)
    assert p["decision_book"] == "draftkings" and p["decision_odds"] == -110.0
    assert p["best_book"] == "fanduel", "the stamp is still recorded for display"


def test_the_stale_line_cap_is_judged_on_the_dk_edge(_open_cut, monkeypatch):
    """A cheaper book adds a few points of edge; that is the price difference,
    not model noise, so the cap (which guards a stale REFERENCE snapshot) is
    applied to the DK edge exactly as pre-game applies MAX_EDGE_CAP."""
    monkeypatch.setattr(live_scorer, "LIVE_MAX_EDGE_CAP", 0.21)
    # DK -110: implied 0.524, edge 0.226 -> over the cap -> None, whatever best says
    assert _live_pick(-110.0, {"book": "fanduel", "odds": 150.0, "link": None}) is None
    # DK -130: implied 0.565, edge 0.185 under the cap; FanDuel +150 -> edge 0.35
    p = _live_pick(-130.0, {"book": "fanduel", "odds": 150.0, "link": None})
    assert p is not None and p["signal_type"] == "BET" and p["decision_book"] == "fanduel"


def test_live_decision_quote_prefers_the_better_payout_and_ties_to_dk():
    assert _live_decision_quote(-110.0, {"book": "fanduel", "odds": 105.0}) == ("fanduel", 105.0)
    assert _live_decision_quote(-110.0, {"book": "fanduel", "odds": -110.0}) == ("draftkings", -110.0)
    assert _live_decision_quote(-110.0, None) == ("draftkings", -110.0)
    assert _live_decision_quote(-110.0, {"book": "fanduel", "odds": None}) == ("draftkings", -110.0)


def test_a_quote_stamped_before_the_score_we_saw_cannot_decide():
    """The 2026-09-03 Wake Forest failure, applied to the OTHER books: a young
    quote that predates the score change is extinct. Age alone kept it."""
    seen = datetime.now(timezone.utc) - timedelta(seconds=10)
    before = (seen - timedelta(seconds=5)).isoformat()
    after = (seen + timedelta(seconds=5)).isoformat()
    conn = _FakeConn([_row("draftkings", -110, ts=after),
                      _row("fanduel", 120, ts=before)])
    quotes = _live_book_quotes(conn, "G", "totals", score_seen_at=seen)
    assert [q["book"] for q in quotes] == ["draftkings"]
    assert _best_live_side(quotes, "over", "totals", 8.5)["book"] == "draftkings"
    # and with no score seen, age is the only gate, as before
    quotes = _live_book_quotes(_FakeConn([_row("draftkings", -110, ts=after),
                                          _row("fanduel", 120, ts=before)]),
                               "G", "totals", score_seen_at=None)
    assert {q["book"] for q in quotes} == {"draftkings", "fanduel"}


def test_the_read_is_one_top_1_per_book_not_a_sort_of_the_game():
    """951 ms on a finished game's 11,204 in-play rows for the old shape; 41 ms
    for a LATERAL top-1 per book over idx_odds_book_snap. The cost has to
    scale with the books, not with how long the game has run."""
    conn = _FakeConn([])
    _live_book_quotes(conn, "G", "totals")
    assert "LATERAL" in conn.sql and "LIMIT 1" in conn.sql
    assert "snapshot_type = 'in_play'" in conn.sql
    assert "unnest(" in conn.sql


def test_the_lane_signature_carries_the_deciding_price():
    """A lane whose best book moved is a different bet on offer even when
    DraftKings did not move -- and the rewrite/no-rewrite decision keys on
    the signature."""
    a = live_scorer._lane_signature([{"pick_side": "over", "signal_type": "BET",
                                      "scored_line": 8.5, "dk_odds": -110.0,
                                      "decision_odds": 105.0}])
    b = live_scorer._lane_signature([{"pick_side": "over", "signal_type": "BET",
                                      "scored_line": 8.5, "dk_odds": -110.0,
                                      "decision_odds": -105.0}])
    assert a != b
    src = (ROOT / "models/live_scorer.py").read_text(encoding="utf-8")
    assert "COALESCE(decision_odds, dk_odds)" in src[src.index("def _existing_live_lanes"):
                                                     src.index("def _live_bets_today")]


def test_the_live_discord_card_headlines_the_deciding_price():
    src = (ROOT / "tracking/discord_notifier.py").read_text(encoding="utf-8")
    body = src[src.index("def _new_live_signals"):src.index("def notify_discord_live")]
    assert "COALESCE(p.decision_odds, p.dk_odds) AS decision_odds" in body
    assert "p.best_book, p.best_odds, p.best_bet_link" in body
    assert '"good_to": price_bound(r[5], r[1], r[15], r[16], r[21])' in body


def test_the_tag_happens_after_the_decision():
    """Tagging inside the scoring loop would put a cross-book price in scope
    while the BET/AVOID call is still being made."""
    src = (ROOT / "models/live_scorer.py").read_text(encoding="utf-8")
    assert src.index("_tag_live(p, (game_id, market))") > src.index("picks.append(pick)")


# -- the NCAAF lane: its own feed, the same rule --------------------------------

def _ev(books: dict, home="Florida State", away="New Mexico State", ts=None):
    """One Odds API event with a bookmaker entry per {book: (over, under, line,
    home_ml, away_ml)}; `ts` per book overrides the market publish time."""
    ts = ts or {}
    entries = []
    for book, (over, under, line, hml, aml) in books.items():
        stamp = ts.get(book, _ts(3))
        entries.append({"key": book, "last_update": stamp, "markets": [
            {"key": "totals", "last_update": stamp, "outcomes": [
                {"name": "Over", "point": line, "price": over},
                {"name": "Under", "point": line, "price": under}]},
            {"key": "h2h", "last_update": stamp, "outcomes": [
                {"name": home, "price": hml}, {"name": away, "price": aml}]}]})
    return {"home_team": home, "away_team": away,
            "commence_time": "2026-09-12T23:00:00Z", "bookmakers": entries}


def test_the_ncaaf_parser_keeps_draftkings_on_top_and_every_book_underneath():
    from ncaaf_live.feeds.odds_live import parse_event_odds
    rec = parse_event_odds([_ev({"fanduel": (-105, -115, 46.5, -180, 150),
                                 "draftkings": (-120, -110, 46.5, -200, 160)})])
    r = rec[("Florida State", "New Mexico State")]
    assert r["total"]["over"] == -120 and r["h2h"]["home"] == -200, "DK is the reference"
    assert set(r["books"]) == {"fanduel", "draftkings"}
    assert r["books"]["fanduel"]["total"]["over"] == -105


def test_the_ncaaf_parser_with_no_draftkings_has_no_reference_line():
    from ncaaf_live.feeds.odds_live import parse_event_odds
    r = parse_event_odds([_ev({"fanduel": (-105, -115, 46.5, -180, 150)})])
    r = r[("Florida State", "New Mexico State")]
    assert r["total"] is None and r["h2h"] is None and "fanduel" in r["books"]


def test_the_ncaaf_feed_asks_for_every_snapshot_book():
    src = (ROOT / "ncaaf_live/feeds/odds_live.py").read_text(encoding="utf-8")
    assert '"bookmakers": ",".join(SNAPSHOT_BOOKS)' in src


def test_the_ncaaf_feed_books_are_the_single_region_bettable_set():
    """ncaaf_live/config.py imports nothing from the repo config by design, so
    the two defaults are pinned to each other here. A us2 book in either
    would double every in-play poll (config.LIVE_FEED_BOOKMAKERS)."""
    from ncaaf_live.config import SNAPSHOT_BOOK, SNAPSHOT_BOOKS
    assert SNAPSHOT_BOOKS == config.LIVE_FEED_BOOKMAKERS
    assert SNAPSHOT_BOOKS[0] == SNAPSHOT_BOOK == "draftkings"
    assert not set(SNAPSHOT_BOOKS) & config._US2_BOOKMAKERS
    assert set(SNAPSHOT_BOOKS) <= set(config.BEST_LINE_BOOKMAKERS)


def test_ncaaf_best_takeable_quote_same_line_fresh_books_only():
    from ncaaf_live.feeds.odds_live import parse_event_odds
    from ncaaf_live.serve import best_takeable_quote
    now = datetime.now(timezone.utc)
    rec = parse_event_odds([_ev({
        "draftkings": (-120, -110, 46.5, -200, 160),
        "fanduel": (105, -125, 46.5, -180, 150),      # best over, same line
        "betmgm": (140, -160, 47.5, -190, 155),       # better, WRONG line
        "fanatics": (150, -170, 46.5, -190, 155),     # best of all, but frozen
    }, ts={"fanatics": _ts(900)})])
    odds = rec[("Florida State", "New Mexico State")]
    best = best_takeable_quote(odds, "total", "over", 46.5, "G", now, None)
    assert best["book"] == "fanduel" and best["odds"] == 105.0
    assert best_takeable_quote(odds, "total", "under", 46.5, "G", now, None)["book"] == "draftkings"
    assert best_takeable_quote(odds, "h2h", "away", None, "G", now, None)["book"] == "draftkings"


def test_ncaaf_best_takeable_quote_drops_a_book_that_predates_the_score():
    from ncaaf_live.feeds.odds_live import parse_event_odds
    from ncaaf_live.serve import best_takeable_quote
    now = datetime.now(timezone.utc)
    seen = now - timedelta(seconds=10)
    rec = parse_event_odds([_ev({
        "draftkings": (-120, -110, 46.5, -200, 160),
        "fanduel": (105, -125, 46.5, -180, 150),
    }, ts={"draftkings": (now - timedelta(seconds=2)).isoformat(),
           "fanduel": (seen - timedelta(seconds=5)).isoformat()})])
    odds = rec[("Florida State", "New Mexico State")]
    assert best_takeable_quote(odds, "total", "over", 46.5, "G", now, seen)["book"] == "draftkings"
    assert best_takeable_quote(odds, "total", "over", 46.5, "G", now, None)["book"] == "fanduel"


def test_the_ncaaf_engine_decides_at_the_better_price_and_ties_to_dk(monkeypatch):
    from ncaaf_live.serve import LiveEngine
    import models.scorer as sc
    monkeypatch.setattr(sc, "DECIDE_ON_BEST_PRICE", True)
    book, price, implied, edge = LiveEngine._deciding(
        0.70, -120.0, 120 / 220, {"book": "fanduel", "odds": 105.0, "link": None})
    assert book == "fanduel" and price == 105.0 and abs(implied - 100 / 205) < 1e-9
    book, price, implied, edge = LiveEngine._deciding(
        0.70, -120.0, 120 / 220, {"book": "fanduel", "odds": -120.0, "link": None})
    assert book == "draftkings" and price == -120.0
    fields = LiveEngine._price_fields("fanduel", 105.0, 100 / 205, 0.2122,
                                      {"book": "fanduel", "odds": 105.0, "link": None}, 0.70)
    assert fields["decision_book"] == "fanduel" and fields["best_book"] == "fanduel"


def test_the_ncaaf_cap_is_judged_on_the_dk_edge():
    from ncaaf_live import serve
    cap = serve.MAX_EDGE_CAP
    assert serve.LiveEngine._decide(0.9, cap + 0.05, 0.5, 0.05, 150.0, None,
                                    cap_edge=cap - 0.01) == "BET"
    assert serve.LiveEngine._decide(0.9, cap - 0.01, 0.5, 0.05, -110.0, None,
                                    cap_edge=cap + 0.05) is None


def test_the_ncaaf_lanes_route_through_the_deciding_helper():
    src = (ROOT / "ncaaf_live/serve.py").read_text(encoding="utf-8")
    body = src[src.index("    def price("):src.index("    @staticmethod\n    def _deciding")]
    assert body.count("best_takeable_quote(odds,") == 2
    assert body.count("self._deciding(") == 2
    assert body.count("cap_edge=edge") == 2
    assert body.count("self._price_fields(") == 2
    assert 'self._kelly(p, d_implied, pick)' in body and 'self._kelly(p, implied, pick)' not in body


def test_ncaaf_gameday_logs_every_book_it_priced_on():
    src = (ROOT / "ncaaf_live/gameday.py").read_text(encoding="utf-8")
    assert 'per_book = quote.get("books") or {SNAPSHOT_BOOK: quote}' in src
    assert "for book, q in per_book.items():" in src

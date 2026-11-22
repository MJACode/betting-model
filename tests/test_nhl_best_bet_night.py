"""The NHL best bet a night (models/nhl_best_bet_night.py, its card
scripts/nhl_best_bet_night_card.py): which quotes pair, which bet a night gets,
the rows it writes, and that it writes at most one bet a night, never on a
game that already holds an NHL bet (mike, 2026-11-22).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import config
import models.nhl_best_bet_night as nb
import scripts.nhl_best_bet_night_card as card
from tracking.pick_integrity import pick_problems

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 22, 20, 0, tzinfo=timezone.utc)
FETCH = "2026-11-22 19:55:02.1+00"
G1, G2 = "NHL_2026-11-22_BOS_TOR", "NHL_2026-11-22_NYR_PHI"
GAMES = {G1: {"home": "TOR", "away": "BOS", "game_date": "2026-11-22",
              "commence_time": "2026-11-23T00:10:00Z"},
         G2: {"home": "PHI", "away": "NYR", "game_date": "2026-11-22",
              "commence_time": "2026-11-23T00:40:00Z"}}


def q(book, market="totals", game=G1, fetch=FETCH, ts=None, snap=None, **prices):
    """One stored odds row, as load_quotes returns it."""
    row = {"game_id": game, "market": market, "book": book, "created_at": fetch,
           "created_ts": ts or (NOW - timedelta(minutes=5)), "snapshot_at": snap or (NOW - timedelta(minutes=5)),
           "home_price": None, "away_price": None, "draw_price": None, "spread_home": None,
           "total_line": None, "over_price": None, "under_price": None,
           "home_link": None, "away_link": None, "draw_link": None,
           "over_link": None, "under_link": None}
    row.update(prices)
    return row


def tot(book, over, under, line=6.5, **kw):
    return q(book, "totals", total_line=line, over_price=over, under_price=under,
             over_link=f"https://{book}/over", under_link=f"https://{book}/under", **kw)


# ── the de-vig ───────────────────────────────────────────────────────────────

def test_power_devig_sums_to_one_and_leans_on_the_longshot():
    from models.market_relative import implied
    fair = nb.power_devig([-200.0, 170.0])
    assert abs(sum(fair) - 1) < 1e-9
    prop = [implied(-200.0), implied(170.0)]
    prop = [p / sum(prop) for p in prop]
    # Power takes more of the margin off the longshot than proportional does.
    assert fair[0] > prop[0] and fair[1] < prop[1]
    assert nb.power_devig([-110.0, -110.0]) == pytest.approx([0.5, 0.5])
    assert nb.power_devig([-110.0, None]) is None
    assert nb.power_devig([100.0, 100.0]) is None          # no margin to take off


# ── pairing: same fetch, same number ─────────────────────────────────────────

def test_a_soft_price_better_than_pinnacles_fair_is_a_candidate():
    quotes = [tot("pinnacle", -110.0, -110.0), tot("betmgm", 110.0, -135.0)]
    best, diag = nb.game_candidates(quotes, now=NOW)
    c = best[G1]
    assert (c.model_id, c.market, c.side, c.book, c.line, c.price) == (
        "nhl_night_total", "totals", "over", "betmgm", 6.5, 110.0)
    assert c.fair == pytest.approx(0.5) and c.ev == pytest.approx(0.05)
    assert c.link == "https://betmgm/over"
    assert diag["compared"] == 1 and diag["candidates"] == 1


@pytest.mark.parametrize("soft,reason", [
    (tot("betmgm", 110.0, -135.0, fetch="2026-11-22 19:40:00+00"), "no_pair"),   # another fetch
    (tot("betmgm", 110.0, -135.0, line=6.0), None),                             # another number
])
def test_only_the_same_fetch_at_the_same_number_pairs(soft, reason):
    best, diag = nb.game_candidates([tot("pinnacle", -110.0, -110.0), soft], now=None)
    assert best == {}
    if reason:
        assert diag[reason] == 1


def test_below_the_price_floor_or_the_ev_floor_is_not_a_candidate():
    # The over at -210 beats Pinnacle's fair price, but -200 is the floor.
    pin = tot("pinnacle", -260.0, 215.0)
    best, diag = nb.game_candidates([pin, tot("fanduel", -210.0, 180.0)], now=NOW)
    assert best == {} and diag["below_price_floor"] == 1 and diag["below_ev_floor"] == 1
    # The same price with the floor lifted is a bet: the floor did the refusing.
    best, _ = nb.game_candidates([pin, tot("fanduel", -210.0, 180.0)], now=NOW, min_odds=-250.0)
    assert best[G1].side == "over" and best[G1].price == -210.0
    best, diag = nb.game_candidates([tot("pinnacle", -110.0, -110.0),
                                     tot("fanduel", -105.0, -115.0)], now=NOW)
    assert best == {} and diag["below_ev_floor"] == 2   # +0.6% < 1%


def test_a_newer_fetch_without_pinnacle_withdraws_the_market():
    later = NOW - timedelta(minutes=1)
    quotes = [tot("pinnacle", -110.0, -110.0), tot("betmgm", 110.0, -135.0),
              tot("fanduel", 100.0, -120.0, fetch="2026-11-22 19:59:00+00", ts=later)]
    best, diag = nb.game_candidates(quotes, now=NOW)
    assert best == {} and diag["pinnacle_withdrawn"] == 1


def test_a_stale_fetch_is_not_priced_live():
    old = NOW - timedelta(minutes=config.PREGAME_PRICE_MAX_AGE_MIN + 1)
    quotes = [tot("pinnacle", -110.0, -110.0, ts=old), tot("betmgm", 110.0, -135.0, ts=old)]
    best, diag = nb.game_candidates(quotes, now=NOW)
    assert best == {} and diag["stale_fetch"] == 1
    best, _ = nb.game_candidates(quotes, now=None)        # the replay applies no age
    assert G1 in best


def test_an_incoherent_pinnacle_pair_is_not_a_fair_price():
    best, diag = nb.game_candidates([tot("pinnacle", 150.0, 150.0), tot("betmgm", 200.0, -250.0)], now=NOW)
    assert best == {} and diag["sharp_incoherent"] == 1


def test_draftkings_at_the_same_number_is_the_reference_price():
    quotes = [tot("pinnacle", -110.0, -110.0), tot("betmgm", 110.0, -135.0),
              tot("draftkings", 102.0, -125.0)]
    c = nb.game_candidates(quotes, now=NOW)[0][G1]
    assert c.book == "betmgm" and c.dk_price == 102.0 and c.dk_link == "https://draftkings/over"


def test_a_game_keeps_its_largest_ev_across_the_four_markets():
    quotes = [tot("pinnacle", -110.0, -110.0), tot("betmgm", 105.0, -130.0),        # +2.5%
              q("pinnacle", "h2h", home_price=-110.0, away_price=-110.0),
              q("fanduel", "h2h", home_price=-120.0, away_price=115.0,                # +7.5%
                away_link="https://fanduel/away")]
    c = nb.game_candidates(quotes, now=NOW)[0][G1]
    assert (c.model_id, c.side, c.book) == ("nhl_night_moneyline", "away", "fanduel")


def test_the_three_way_uses_its_own_overround_band():
    pin = q("pinnacle", "h2h_3way", home_price=140.0, draw_price=320.0, away_price=170.0)
    soft = q("betrivers", "h2h_3way", home_price=145.0, draw_price=360.0, away_price=160.0)
    c = nb.game_candidates([pin, soft], now=NOW)[0][G1]
    assert c.model_id == "nhl_night_regulation" and c.side == "draw"


# ── one bet a night ──────────────────────────────────────────────────────────

def _cand(game, ev, model="nhl_night_total"):
    return nb.Candidate(game_id=game, market=next(m for m, i in nb.MARKET_MODEL.items() if i == model),
                        model_id=model, side="over", book="betmgm", line=6.5, price=110.0,
                        fair=0.5, ev=ev, created_at=FETCH, link=None, dk_price=None, dk_link=None)


def test_the_night_gets_its_largest_ev():
    picks = nb.pick_of_the_night({G1: _cand(G1, 0.02), G2: _cand(G2, 0.05)}, GAMES, set(), set())
    assert list(picks) == ["2026-11-22"] and picks["2026-11-22"].game_id == G2


def test_a_night_with_a_bet_gets_nothing_more():
    assert nb.pick_of_the_night({G1: _cand(G1, 0.05)}, GAMES, {"2026-11-22"}, set()) == {}


def test_a_game_holding_any_nhl_bet_is_skipped():
    picks = nb.pick_of_the_night({G1: _cand(G1, 0.09), G2: _cand(G2, 0.02)}, GAMES, set(), {G1})
    assert picks["2026-11-22"].game_id == G2


def test_on_a_tie_the_earlier_market_keeps_it():
    a, b = _cand(G1, 0.03, "nhl_night_moneyline"), _cand(G2, 0.03, "nhl_night_puckline")
    assert nb.pick_of_the_night({G1: a, G2: b}, GAMES, set(), set())["2026-11-22"] is b


# ── the rows ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("market,side,line,label", [
    ("spreads", "home", -1.5, "TOR -1.5"),
    ("spreads", "away", -1.5, "BOS +1.5"),
    ("totals", "under", 6.5, "TOR vs BOS Under 6.5"),
    ("h2h", "away", None, "BOS ML"),
    ("h2h_3way", "draw", None, "BOS @ TOR Draw (Regulation)"),
    ("h2h_3way", "home", None, "TOR (Regulation)"),
])
def test_every_market_writes_a_label_that_agrees_with_its_side_and_line(market, side, line, label):
    c = nb.Candidate(game_id=G1, market=market, model_id=nb.MARKET_MODEL[market], side=side,
                     book="betmgm", line=line, price=120.0, fair=0.5, ev=0.10, created_at=FETCH,
                     link="https://betmgm/x", dk_price=None, dk_link=None)
    got = card.label_for(c, "TOR", "BOS")
    assert got == label
    assert pick_problems(got, side, line, c.model_id, "TOR", "BOS") == []


def test_a_row_off_draftkings_and_one_at_draftkings(monkeypatch):
    import models.honest_ev as hev
    monkeypatch.setattr(hev, "gate", lambda mid, fair, price: type("E", (), {"clears": True, "reason": ""})())
    off = _cand(G1, 0.05)
    at_dk = nb.Candidate(**{**off.__dict__, "game_id": G2, "book": "draftkings", "dk_price": 110.0,
                            "dk_link": "https://dk/over", "link": "https://dk/over"})
    r_off, r_dk = card.pick_rows([off, at_dk], GAMES, bankroll=10_000)
    assert r_off["model_id"] == "nhl_night_total" and r_off["signal_type"] == "BET"
    assert r_off["dk_odds"] is None and r_off["line_book"] == "betmgm"
    assert r_off["decision_book"] == "betmgm" and r_off["best_book"] == "betmgm"
    assert r_dk["dk_odds"] == 110.0 and r_dk["line_book"] is None and r_dk["best_book"] is None
    assert r_dk["decision_book"] == "draftkings"
    # Flat stake: the row carries no stake of its own.
    assert "stake_units" not in r_off


class _PubConn:
    """A BET found when the night or game is in `bet_nights` / `bet_games`."""

    def __init__(self, bet_nights=(), bet_games=()):
        self.bet_nights, self.bet_games = set(bet_nights), set(bet_games)
        self.commits = 0
        self._rows = []

    def execute(self, sql, params=None):
        if "SELECT DISTINCT game_date" in sql:
            self._rows = [(n,) for n in params[1] if n in self.bet_nights]
        elif "SELECT DISTINCT game_id" in sql:
            self._rows = [(g,) for g in params[0] if g in self.bet_games]
        else:
            self._rows = []
        return self

    def fetchall(self):
        return self._rows

    def commit(self):
        self.commits += 1


def _publish(monkeypatch, conn, rows):
    import models.nhl_goalie_gate as gate
    import scripts.nfl_wind_publisher as wp
    locked, inserted = [], []
    monkeypatch.setattr(wp, "_lock_model", lambda c, mid: locked.append(mid))
    monkeypatch.setattr(gate, "refuse_unknown", lambda c, rs, mode, label: rs)

    def _insert(c, rs):
        inserted.extend(rs)
        for r in rs:
            conn.bet_nights.add(r["game_date"])
            conn.bet_games.add(r["game_id"])
    monkeypatch.setattr(card, "_insert_picks", _insert)
    n = card.publish(conn, rows)
    return n, locked, inserted


def test_publish_writes_one_bet_a_night_under_the_familys_lock(monkeypatch):
    rows = [{"game_id": G1, "game_date": "2026-11-22"}, {"game_id": G2, "game_date": "2026-11-22"}]
    conn = _PubConn()
    n, locked, inserted = _publish(monkeypatch, conn, rows)
    assert n == 1 and [r["game_id"] for r in inserted] == [G1]
    assert locked == [nb.FAMILY] and conn.commits == 1
    # A later pass the same night writes nothing.
    n, _, inserted = _publish(monkeypatch, conn, [{"game_id": G2, "game_date": "2026-11-22"}])
    assert n == 0 and inserted == []


def test_publish_rechecks_the_game_under_the_lock(monkeypatch):
    conn = _PubConn(bet_games={G1})
    n, _, inserted = _publish(monkeypatch, conn, [{"game_id": G1, "game_date": "2026-11-22"}])
    assert n == 0 and inserted == []


def test_the_game_check_counts_any_nhl_model_and_the_night_check_only_the_family():
    seen = []

    class _C:
        def execute(self, sql, params=None):
            seen.append((" ".join(sql.split()), params))
            return self

        def fetchall(self):
            return []
    card.games_with_bet(_C(), [G1])
    card.nights_with_bet(_C(), ["2026-11-22"])
    games_sql, night_sql = seen
    assert "sport = 'NHL'" in games_sql[0] and "model_id" not in games_sql[0]
    assert "signal_type = 'BET'" in games_sql[0]
    assert set(night_sql[1][0]) == set(nb.MODEL_IDS) and "signal_type = 'BET'" in night_sql[0]


# ── registration: every place a new model must be named ─────────────────────

@pytest.mark.parametrize("mid", nb.MODEL_IDS)
def test_each_id_is_registered(mid):
    from tracking.paper_tracker import _RULE_MODEL_MARKETS
    assert config.SCORING_METHODS[mid] == "rule"
    assert config.min_ev_for(mid) == 0.01
    assert config.min_odds_for(mid) == -200
    assert mid in config.ACTION_THRESHOLDS
    market = next(m for m, i in nb.MARKET_MODEL.items() if i == mid)
    assert _RULE_MODEL_MARKETS[mid] == market


def test_the_card_runs_after_the_totals_card_in_every_pass():
    rp = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    assert '"nhl-best-bet-night"' in rp.split("choices=[", 1)[1].split("]", 1)[0]
    sh = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
    assert sh.index("step nhl-over-under") < sh.index("step nhl-best-bet-night") < sh.index("step scoring")
    sched = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    window = sched.split("def run_nhl_goalie_window(", 1)[1].split("\ndef ", 1)[0]
    assert window.index('"nhl-over-under"') < window.index('"nhl-best-bet-night"')


# ── the app (text checks, like the other mobile tests; UX review 2026-11-22) ─

def _src(rel):
    return (ROOT / "mobile" / "src" / "lib" / rel).read_text(encoding="utf-8")


def _fn(src, name):
    start = src.index(f"function {name}(")
    return src[start:src.index("\n}\n", start)]


def test_the_app_files_each_id_in_its_market():
    markets = _src("markets.ts")
    game = _fn(markets, "gameMarketForModel")
    assert "modelId === 'nhl_night_total') return 'totals'" in game
    assert "modelId === 'nhl_night_regulation') return 'h2h_3way'" in game
    cls = _fn(markets, "marketClassForModel")
    assert "modelId === 'nhl_night_total') return 'game_total'" in cls
    assert "modelId === 'nhl_night_regulation') return 'game_ml'" in cls


def test_the_moneyline_and_3way_say_posted_at_the_price_not_a_line():
    import re
    lst = re.search(r"const POSTED_MONEYLINE_MODELS: readonly string\[\] = \[(.*?)\];",
                    _src("markets.ts"), re.S)
    assert "'nhl_night_moneyline'" in lst.group(1) and "'nhl_night_regulation'" in lst.group(1)
    assert "'nhl_night_puckline'" not in lst.group(1) and "'nhl_night_total'" not in lst.group(1)


def test_each_page_says_one_bet_a_night_and_the_note_names_pinnacle():
    meta = _src("modelMeta.ts")
    timing = _fn(meta, "modelPageTiming")
    branch = timing[timing.index("modelId.startsWith('nhl_night_')"):]
    branch = branch[:branch.index("\n  }\n")]
    assert "one bet a night at most" in branch and "both starting goalies are confirmed" in branch
    assert "most nights this one has none" in branch
    assert "Check back after the next pipeline refresh" not in branch
    for mid in nb.MODEL_IDS:
        note = meta[meta.index(f"  {mid}:\n    'The chance"):]
        assert "Pinnacle’s price with its margin removed" in note[:400], mid


def test_the_builder_rows_are_not_the_night_models():
    """The custom-model builder's NHL ML and Spread rows stay the side models."""
    meta = _src("modelMeta.ts")
    body = _fn(meta, "betSlotForModel")
    assert body.index("id.startsWith('nhl_night_')) return null") < body.index("id.includes('moneyline')")


def test_the_names_follow_the_house_rule():
    meta = _src("modelMeta.ts")
    for mid, short, long in (("nhl_night_puckline", "Best Spread", "NHL Best Bet Spreads"),
                             ("nhl_night_total", "Best O/U", "NHL Best Bet Totals"),
                             ("nhl_night_moneyline", "Best ML", "NHL Best Bet Moneyline"),
                             ("nhl_night_regulation", "Best 3-Way", "NHL Best Bet 3-Way Moneyline")):
        entry = meta[meta.index(f"  {mid}: {{"):][:200]
        assert f"shortLabel: '{short}'" in entry and f"longLabel: '{long}'" in entry
        assert "Puck" not in entry

"""The NCAAB first-post moneyline model (`ncaab_moneyline_first_post`): a
book's newly posted moneyline priced off its own spread at that moment, the
3-other-books rule, the -200 floor before the pick, the tie-break, one bet a
game across both moneyline models, the card's statuses, the fill check and
the job.

The evidence check is the build, not this file:
scripts/ncaab_moneyline_first_post_build.py replays the card's own functions
over 2021-2026 and compares the bets game by game with the research's. These
tests pin the rules that replay depends on, and the card around it. The
database end of the card is tests/test_ncaab_moneyline_first_post_card_pg.py.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import models.ncaab_book_quotes as bq  # noqa: E402
import models.ncaab_moneyline_first_post as fp  # noqa: E402
import models.ncaab_moneyline_own_spread as om  # noqa: E402

UTC = timezone.utc
NOW = pd.Timestamp("2026-12-04 23:41", tz="UTC")
TIP = pd.Timestamp("2026-12-06 00:00", tz="UTC")


@pytest.fixture(scope="module")
def art():
    return fp.load_artifact()


@pytest.fixture(scope="module")
def table():
    """The margin table: the spread model's, which both moneyline artifacts
    name and pin (test_the_artifact_reads_the_spread_models_margin_table)."""
    return om.load_artifact()["table"]


def _rows(quotes, instant=NOW, tip=TIP):
    """quotes: (game_id, book, minutes before the instant, line or None, p1, p2)."""
    out = []
    for i, (gid, book, mins, line, p1, p2) in enumerate(quotes):
        out.append({"game_id": gid, "bookmaker": book, "ts": instant - pd.Timedelta(minutes=mins),
                    "line": np.nan if line is None else line, "p1": p1, "p2": p2, "order": i,
                    "instant": instant, "tip": tip, "link1": f"{book}-home", "link2": f"{book}-away"})
    return pd.DataFrame(out, columns=["game_id", "bookmaker", "ts", "line", "p1", "p2", "order",
                                      "instant", "tip", "link1", "link2"])


def _ph(table, line, p1=-110.0, p2=-110.0):
    sp = om.spread_quotes(_rows([("g", "draftkings", 10, line, p1, p2)]), table)
    return float(sp["ph_own"].iloc[0])


def _american(p_implied):
    return -100 * p_implied / (1 - p_implied) if p_implied >= 0.5 else 100 * (1 - p_implied) / p_implied


BOOKS4 = ("draftkings", "fanduel", "betmgm", "williamhill_us")
SPREADS = [("g", b, 600, -3.5, -110.0, -110.0) for b in bq.BOOKS]


def _others(table, books=("draftkings", "fanduel", "betmgm"), mins=300):
    """Other books' moneylines, about fair, posted hours ago."""
    p = _ph(table, -3.5)
    home, away = float(round(_american(p + 0.02))), float(round(_american(1 - p + 0.02)))
    return [("g", b, mins, None, home, away) for b in books]


def _decide(table, ml, posting, sp=SPREADS, **kw):
    m, s = fp.read(_rows(ml), _rows(sp), table)
    return fp.decide_posts(pd.DataFrame(posting, columns=["game_id", "bookmaker"]), m, s,
                           kw.pop("cut", fp.CUT), **kw)


def _one(ds, book):
    (d,) = [x for x in ds if x.bookmaker == book]
    return d


# ── registration ─────────────────────────────────────────────────────────────

def test_config_carries_the_model_as_a_rule_with_its_own_cut(art):
    m = fp.MODEL_ID
    assert config.ACTION_THRESHOLDS[m] == {"min_prob": 0.0, "min_edge": 0.015}
    assert config.MODEL_EDGE_THRESHOLDS[m] == 0.015 == fp.CUT == art["cut"]
    assert config.MODEL_PROB_THRESHOLDS[m] == 0.0
    assert config.SCORING_METHODS[m] == "rule"
    assert m in config.MODELS_ON_OWN_PROBABILITY
    assert m not in config.MODELS and m not in config.PAUSED_MODELS
    assert art["min_other_books"] == fp.MIN_OTHER_BOOKS == 3


def test_the_price_floor_is_minus_200_and_pinned():
    """mike: "-200 max" for NCAAB moneylines. Pinned in MODEL_MIN_ODDS so a
    Railway DEFAULT_MIN_ODDS override cannot move it."""
    assert config.MODEL_MIN_ODDS[fp.MODEL_ID] == -200
    assert config.min_odds_for(fp.MODEL_ID) == -200
    assert fp.MIN_PRICE == -200


def test_the_ev_floor_sits_just_under_the_smallest_ev_the_cut_admitted(art):
    floor = config.MODEL_OWN_EV_FLOOR[fp.MODEL_ID]
    smallest = art["replay"]["min_ev"]
    assert floor <= smallest < floor + 0.005


def test_the_replay_matched_the_research_game_by_game(art):
    """The build's replay of the card's own functions against the research's
    297 + 56 bets (game, side, price, the same book, the same moment)."""
    c = art["research_check"]
    assert c["replay_bets"] == c["research_bets"] == c["both"] == 353
    assert c["same_game_side_price"] == c["same_book_too"] == c["same_moment_too"] == 353
    assert (c["replay_bets_2021-2025"], c["replay_bets_2026"]) == (297, 56)
    assert c["max_abs_edge_diff"] < 1e-9


def test_the_artifact_reads_the_spread_models_margin_table_and_pins_it(art):
    spread = json.loads((fp.ROOT / art["margin_table_from"]).read_text(encoding="utf-8"))
    assert om.table_digest(spread["margin_table"]) == art["margin_table_sha256"]
    assert int(spread["season"]) == int(art["season"]) == 2027
    own = om.load_artifact()
    assert art["margin_table_sha256"] == own["margin_table_sha256"]   # one table, both models
    assert tuple(art["books"]) == bq.BOOKS and tuple(art["ref_books"]) == fp.REF_BOOKS


def test_an_artifact_whose_table_moved_is_refused(tmp_path):
    raw = json.loads((fp.ROOT / fp.ARTIFACT_PATH).read_text(encoding="utf-8"))
    raw["margin_table_sha256"] = "0" * 64
    p = tmp_path / "a.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="digest differs"):
        fp.load_artifact(p)


# ── the rule ─────────────────────────────────────────────────────────────────

def test_a_minus_201_side_is_never_bet_and_minus_200_is(table):
    """The floor is applied to every side BEFORE the pick."""
    sp = [("g", b, 600, -7.5, -110.0, -110.0) for b in bq.BOOKS]
    p = _ph(table, -7.5)
    assert p - 1 / fp.dec(-201) > 0.05                 # a big edge at -201
    others = [("g", b, 300, None, -330.0, 260.0) for b in ("draftkings", "fanduel", "betmgm")]
    d = _one(_decide(table, others + [("g", "betrivers", 1, None, -201.0, 170.0)],
                     [("g", "betrivers")], sp=sp), "betrivers")
    assert d.status != "bets" and (d.best is None or d.best["side"] == "away")
    d = _one(_decide(table, others + [("g", "betrivers", 1, None, -200.0, 170.0)],
                     [("g", "betrivers")], sp=sp), "betrivers")
    assert d.status == "bets" and d.best["side"] == "home" and d.best["price"] == -200.0


def test_three_other_bettable_moneylines_must_be_up(table):
    p = _ph(table, -3.5)
    cheap = float(round(_american(p - 0.04)))
    post = ("g", "betrivers", 1, None, cheap, 120.0)
    d = _one(_decide(table, _others(table, ("draftkings", "fanduel")) + [post],
                     [("g", "betrivers")]), "betrivers")
    assert d.status == "too_few_books" and d.n_books == 3
    d = _one(_decide(table, _others(table) + [post], [("g", "betrivers")]), "betrivers")
    assert d.status == "bets" and d.n_books == 4


def test_the_others_are_counted_price_valid_flagged_or_not_and_pinnacle_never(table):
    """The count is the bettable books with both prices -100/+100 or longer: a
    flagged quote (here an implied sum over 1.15) still counts, Pinnacle and
    Bovada never do, and a price inside -100..+100 is not a quote."""
    p = _ph(table, -3.5)
    cheap = float(round(_american(p - 0.04)))
    post = ("g", "betrivers", 1, None, cheap, 120.0)
    two = _others(table, ("draftkings", "fanduel"))
    overround = [("g", "betmgm", 300, None, -300.0, -150.0)]
    ref = [("g", "pinnacle", 300, None, cheap, 120.0), ("g", "bovada", 300, None, cheap, 120.0)]
    d = _one(_decide(table, two + overround + [post], [("g", "betrivers")]), "betrivers")
    assert d.status == "bets"
    d = _one(_decide(table, two + ref + [post], [("g", "betrivers")]), "betrivers")
    assert d.status == "too_few_books"
    d = _one(_decide(table, two + [("g", "betmgm", 300, None, -90.0, 120.0)] + [post],
                     [("g", "betrivers")]), "betrivers")
    assert d.status == "too_few_books"


def test_a_book_posting_in_the_same_moment_counts_as_up(table):
    p = _ph(table, -3.5)
    cheap = float(round(_american(p - 0.04)))
    fair = float(round(_american(p)))
    ml = _others(table, ("draftkings", "fanduel")) + [
        ("g", "betrivers", 1, None, cheap, 120.0), ("g", "fanatics", 1, None, fair, 110.0)]
    ds = _decide(table, ml, [("g", "betrivers"), ("g", "fanatics")])
    assert _one(ds, "betrivers").status == "bets" and _one(ds, "fanatics").status == "below_cut"


def test_the_others_have_no_freshness_window(table):
    """Each book's newest row however old: the capture stores a row only when
    a number moves. The 15:00 UTC model's 60-minute window is not this one's."""
    p = _ph(table, -3.5)
    cheap = float(round(_american(p - 0.04)))
    old = _others(table, mins=60 * 20)
    d = _one(_decide(table, old + [("g", "betrivers", 1, None, cheap, 120.0)],
                     [("g", "betrivers")], sp=[("g", b, 60 * 30, -3.5, -110.0, -110.0) for b in bq.BOOKS]),
             "betrivers")
    assert d.status == "bets" and d.n_books == 4


def test_the_edge_must_be_above_the_cut(table):
    p = _ph(table, -3.5)
    for off, want in ((0.010, "below_cut"), (0.025, "bets")):
        d = _one(_decide(table, _others(table) + [("g", "betrivers", 1, None,
                                                   float(round(_american(p - off))), 120.0)],
                         [("g", "betrivers")]), "betrivers")
        assert d.status == want, (off, d.detail)
        assert d.best["edge"] > fp.CUT if want == "bets" else d.best["edge"] <= fp.CUT


def test_only_the_new_post_is_priced(table):
    """An older book with a far bigger edge is read, never bet here."""
    p = _ph(table, -3.5)
    stale_cheap = [("g", "draftkings", 300, None, float(round(_american(p - 0.10))), 120.0)]
    ml = stale_cheap + _others(table, ("fanduel", "betmgm", "williamhill_us")) + [
        ("g", "betrivers", 1, None, float(round(_american(p - 0.02))), 120.0)]
    ds = _decide(table, ml, [("g", "betrivers")])
    assert [d.bookmaker for d in ds] == ["betrivers"] and ds[0].status == "bets"


def test_two_posts_in_one_moment_the_larger_edge_wins_and_a_tie_goes_to_the_name(table):
    p = _ph(table, -3.5)
    a = float(round(_american(p - 0.03)))
    b = float(round(_american(p - 0.02)))
    ml = _others(table) + [("g", "fanatics", 1, None, a, 120.0), ("g", "betrivers", 1, None, b, 120.0)]
    ds = _decide(table, ml, [("g", "betrivers"), ("g", "fanatics")])
    assert _one(ds, "fanatics").status == "bets" and _one(ds, "betrivers").status == "not_best"
    ml = _others(table) + [("g", "fanatics", 1, None, a, 120.0), ("g", "betrivers", 1, None, a, 120.0)]
    ds = _decide(table, ml, [("g", "betrivers"), ("g", "fanatics")])
    assert _one(ds, "betrivers").status == "bets" and _one(ds, "fanatics").status == "not_best"
    assert len(fp.the_bet(ds)) == 1


def test_a_flagged_post_or_one_without_its_own_spread_is_not_priced(table):
    p = _ph(table, -3.5)
    cheap = float(round(_american(p - 0.04)))
    sp = [s for s in SPREADS if s[1] != "betrivers"]
    d = _one(_decide(table, _others(table) + [("g", "betrivers", 1, None, cheap, 120.0)],
                     [("g", "betrivers")], sp=sp), "betrivers")
    assert d.status == "no_clean_quote" and "own spread" in d.detail
    # its favourite is the other team's, at every other book
    d = _one(_decide(table, _others(table) + [("g", "betrivers", 1, None, 150.0, -180.0)],
                     [("g", "betrivers")]), "betrivers")
    assert d.status == "no_clean_quote" and "flagged" in d.detail


def test_a_book_no_longer_bettable_is_not_replaced_by_the_next(table):
    p = _ph(table, -3.5)
    ml = _others(table) + [("g", "betrivers", 1, None, float(round(_american(p - 0.04))), 120.0),
                           ("g", "fanatics", 1, None, float(round(_american(p - 0.03))), 120.0)]
    ds = _decide(table, ml, [("g", "betrivers"), ("g", "fanatics")],
                 bettable=tuple(b for b in bq.BOOKS if b != "betrivers"))
    assert _one(ds, "betrivers").status == "book_not_bettable"
    assert _one(ds, "fanatics").status == "not_best" and not fp.the_bet(ds)


def test_a_moment_within_five_minutes_of_tip_is_not_priced():
    assert fp.too_close(TIP, TIP - pd.Timedelta(minutes=4))
    assert not fp.too_close(TIP, TIP - pd.Timedelta(minutes=5))


# ── the card ─────────────────────────────────────────────────────────────────

GAMES = {"g": {"season": 2027, "game_date": "2026-12-05", "tip": TIP.to_pydatetime(),
               "commence_time": "2026-12-06T00:00:00Z", "home": "Duke", "away": "Kansas"}}


class _Conn:
    def close(self):
        pass


def _wire(monkeypatch, table, first, ml, own_bet=(), other_bet=(), now=NOW, sp=SPREADS):
    """The card's decide() with its reads stubbed. first: {(game, book):
    (minutes before now it was stored, p1, p2)}."""
    import scripts.ncaab_moneyline_first_post_card as card
    t = pd.Timestamp(now)
    monkeypatch.setattr(card, "first_rows", lambda conn, keys: {
        k: {"ts": t - pd.Timedelta(minutes=v[0]), "stored": t - pd.Timedelta(minutes=v[0]),
            "p1": v[1], "p2": v[2]} for k, v in first.items() if k in keys})
    monkeypatch.setattr(card, "bet_games", lambda conn, gids, model_id: set(
        own_bet if model_id == fp.MODEL_ID else other_bet))
    monkeypatch.setattr(card, "standing_rows", lambda conn, games, instant: (
        _rows(ml, instant=t), _rows(sp, instant=t)))
    return card


def test_the_first_run_ever_records_every_post_as_before_the_model(monkeypatch, table):
    import scripts.ncaab_moneyline_first_post_card as card
    monkeypatch.setattr(card, "first_rows", lambda conn, keys: (_ for _ in ()).throw(AssertionError("read")))
    ds, _, problems = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "draftkings")], first_run=True)
    assert [d.status for d in ds] == ["pre_model"] and not problems


def test_a_new_post_bets_at_the_posting_books_price(monkeypatch, table):
    p = _ph(table, -3.5)
    cheap = float(round(_american(p - 0.04)))
    card = _wire(monkeypatch, table, {("g", "betrivers"): (1, cheap, 120.0)},
                 _others(table) + [("g", "betrivers", 1, None, cheap, 120.0)])
    ds, firsts, problems = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "betrivers")], False)
    (d,) = ds
    assert d.status == "bets" and (d.best["bookmaker"], d.best["side"], d.best["price"]) == \
        ("betrivers", "home", cheap)
    assert not problems and firsts[("g", "betrivers")]["p1"] == cheap


def test_a_post_that_moved_before_the_card_saw_it_is_not_a_first_post(monkeypatch, table):
    p = _ph(table, -3.5)
    cheap = float(round(_american(p - 0.04)))
    card = _wire(monkeypatch, table, {("g", "betrivers"): (3, cheap, 120.0)},
                 _others(table) + [("g", "betrivers", 1, None, cheap + 10, 115.0)])
    (d,), _, _ = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "betrivers")], False)
    assert d.status == "moved_before_seen"


def test_a_post_the_card_saw_late_is_missed_never_bet_and_fails_the_run(monkeypatch, table):
    p = _ph(table, -3.5)
    cheap = float(round(_american(p - 0.04)))
    card = _wire(monkeypatch, table, {("g", "betrivers"): (16, cheap, 120.0)},
                 _others(table) + [("g", "betrivers", 16, None, cheap, 120.0)])
    (d,), _, problems = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "betrivers")], False)
    assert d.status == "missed" and problems and "missed" in problems[0]


def test_a_post_stored_while_the_game_was_beyond_the_window_is_recorded_not_failed(monkeypatch, table):
    import scripts.ncaab_moneyline_first_post_card as card
    mins = int((card.LOOK_AHEAD + timedelta(hours=26)).total_seconds() // 60)
    card = _wire(monkeypatch, table, {("g", "betrivers"): (mins, -150.0, 130.0)}, [])
    (d,), _, problems = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "betrivers")], False)
    assert d.status == "before_window" and not problems


def test_a_game_this_model_or_the_15z_model_bet_is_closed(monkeypatch, table):
    p = _ph(table, -3.5)
    cheap = float(round(_american(p - 0.04)))
    ml = _others(table) + [("g", "betrivers", 1, None, cheap, 120.0)]
    first = {("g", "betrivers"): (1, cheap, 120.0)}
    card = _wire(monkeypatch, table, first, ml, own_bet={"g"})
    (d,), _, _ = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "betrivers")], False)
    assert d.status == "game_already_bet"
    card = _wire(monkeypatch, table, first, ml, other_bet={"g"})
    (d,), _, _ = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "betrivers")], False)
    assert d.status == "other_model_bet"


# ── feed typos (models/ncaab_quote_bounds.py), as on the 15:00 UTC card ──────

def test_a_first_post_priced_beyond_100000_is_dropped_and_never_bet(monkeypatch, table):
    """Hard Rock's typo shape: -300000 / +250000. Dropped before any flag or
    count reads it, written no_clean_quote, counted on the run's line."""
    card = _wire(monkeypatch, table, {("g", "hardrockbet"): (1, -300000.0, 250000.0)},
                 _others(table) + [("g", "hardrockbet", 1, None, -300000.0, 250000.0)])
    ds, _, problems = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "hardrockbet")], False)
    (d,) = ds
    assert d.status == "no_clean_quote" and "data error" in d.detail and "100000" in d.detail
    assert ds.dropped == 1 and not problems


def test_a_typo_at_another_book_is_not_one_of_the_three_others(monkeypatch, table):
    p = _ph(table, -3.5)
    cheap = float(round(_american(p - 0.04)))
    ml = _others(table, ("draftkings", "fanduel")) + [
        ("g", "betmgm", 300, None, -300000.0, 250000.0), ("g", "betrivers", 1, None, cheap, 120.0)]
    card = _wire(monkeypatch, table, {("g", "betrivers"): (1, cheap, 120.0)}, ml)
    ds, _, _ = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "betrivers")], False)
    (d,) = ds
    assert d.status == "too_few_books" and d.n_books == 3 and ds.dropped == 1
    assert "betmgm h2h" in d.detail and any(q.get("flags") == ["out_of_range"] for q in d.quotes)


def test_a_spread_beyond_60_is_not_the_posting_books_own_spread(monkeypatch, table):
    p = _ph(table, -3.5)
    cheap = float(round(_american(p - 0.04)))
    sp = [s for s in SPREADS if s[1] != "betrivers"] + [("g", "betrivers", 600, -350.0, -110.0, -110.0)]
    card = _wire(monkeypatch, table, {("g", "betrivers"): (1, cheap, 120.0)},
                 _others(table) + [("g", "betrivers", 1, None, cheap, 120.0)], sp=sp)
    (d,), _, _ = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "betrivers")], False)
    assert d.status == "no_clean_quote" and "spreads is a data error" in d.detail


def test_an_edge_above_the_data_error_cap_is_recorded_not_bet_and_fails_the_run(monkeypatch, table):
    """The moment's largest edge above models/ncaab_quote_bounds.EDGE_CAP is a
    data error: written edge_cap, no bet, the run fails; the game stays open."""
    from models import ncaab_quote_bounds as qb
    cap = qb.EDGE_CAP[fp.MODEL_ID]
    sp = [(s[0], s[1], s[2], 1.0, -110.0, -110.0) for s in SPREADS]          # away by a point
    p_away = 1 - _ph(table, 1.0)
    dog = float(round(_american(p_away - cap - 0.03)))                     # edge cap + 0.03
    fav = float(round(_american(1.03 - (p_away - cap - 0.03))))            # implied sum 1.03
    ml = [("g", b, 300, None, -130.0, 110.0) for b in ("draftkings", "fanduel", "betmgm")] + [
        ("g", "betrivers", 1, None, fav, dog)]
    card = _wire(monkeypatch, table, {("g", "betrivers"): (1, fav, dog)}, ml, sp=sp)
    (d,), _, problems = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "betrivers")], False)
    assert d.status == "edge_cap" and d.best["side"] == "away" and d.best["edge"] > cap
    assert problems and problems[0].startswith("edge_cap")
    assert "edge_cap" in fp.STATUSES


def test_the_cap_sits_above_every_edge_the_replay_priced(art):
    """The cap must not remove a real bet: above the largest bet's edge and the
    largest edge of any post priced with 3+ other books up."""
    from models import ncaab_quote_bounds as qb
    r = art["replay"]
    assert r["max_edge_bets"] <= r["max_edge_priced_posts"] < qb.EDGE_CAP[fp.MODEL_ID]
    assert r["statuses_at_lowest_cut"].get("edge_cap", 0) == 0


def test_a_post_below_the_cut_leaves_the_game_open_for_a_later_post(monkeypatch, table):
    """The game closes on a BET, never on a decision: below the cut at
    DraftKings, then a qualifying first post at Caesars bets."""
    p = _ph(table, -3.5)
    fair = float(round(_american(p)))
    cheap = float(round(_american(p - 0.04)))
    others = _others(table, ("fanduel", "betmgm", "betrivers"))
    card = _wire(monkeypatch, table, {("g", "draftkings"): (1, fair, 120.0)},
                 others + [("g", "draftkings", 1, None, fair, 120.0)])
    (d,), _, _ = card.decide(_Conn(), NOW.to_pydatetime(), GAMES, [("g", "draftkings")], False)
    assert d.status == "below_cut"
    later = NOW + pd.Timedelta(hours=5)
    card = _wire(monkeypatch, table, {("g", "williamhill_us"): (1, cheap, 120.0)},
                 others + [("g", "draftkings", 300, None, fair, 120.0),
                           ("g", "williamhill_us", 1, None, cheap, 120.0)], now=later)
    (d,), _, _ = card.decide(_Conn(), later.to_pydatetime(), GAMES, [("g", "williamhill_us")], False)
    assert d.status == "bets" and d.best["bookmaker"] == "williamhill_us"


def test_a_bet_row_is_a_moneyline_at_the_posting_books_price_under_this_model():
    import scripts.ncaab_moneyline_card as mlcard
    best = {"game_id": "g", "bookmaker": "williamhill_us", "side": "home", "price": -150.0,
            "prob": 0.64, "edge": 0.04, "own_line": -3.5, "mu": 3.6, "ph_own": 0.64,
            "link": "czr-home", "dec": float(fp.dec(-150.0))}
    d = fp.PostDecision("g", "williamhill_us", "bets", "x", best=best,
                        dk={"p1": -160.0, "p2": 135.0, "link1": "dk-h", "link2": "dk-a"})
    (row,), refused = mlcard.pick_rows([d], GAMES, 1000.0, model_id=fp.MODEL_ID)
    assert not refused and row["model_id"] == fp.MODEL_ID and row["pick_label"] == "Duke ML"
    assert row["scored_line"] is None and row["line_book"] is None
    assert (row["decision_book"], row["decision_odds"], row["best_book"]) == \
        ("williamhill_us", -150.0, "williamhill_us")
    assert row["decision_edge"] == round(0.64 - 0.6, 4) and row["dk_odds"] == -160.0
    # this model's own price floor: -201 refused
    bad = fp.PostDecision("g", "williamhill_us", "bets", "x", best=dict(best, price=-201.0, prob=0.8))
    # scored=False, as the first-post card calls it: a refused bet writes no
    # NONE row, which would hold the unique key a later post's BET needs.
    rows, refused = mlcard.pick_rows([bad], GAMES, 1000.0, model_id=fp.MODEL_ID, scored=False)
    assert not rows and refused["g"].startswith("below_price_floor")
    below = fp.PostDecision("g", "williamhill_us", "below_cut", "x", best=best)
    assert mlcard.pick_rows([below], GAMES, 1000.0, model_id=fp.MODEL_ID, scored=False) == ([], {})


# ── one bet a game: the 15:00 UTC card's side ─────────────────────────────────

def test_the_15z_card_records_a_game_the_first_post_model_bet_and_never_prices_it(monkeypatch):
    import scripts.ncaab_moneyline_card as mlcard
    from tests.test_ncaab_moneyline_own_spread import GAMES as G15, _wire as wire15
    t = om.load_artifact()["table"]
    card15, got = wire15(monkeypatch, t, dict(G15), first_post_bet={"g"})
    out = card15.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["other_model_bet"] and got["rows"] == []
    assert "reads" not in got and out["bets"] == 0
    # and an hour later it is neither missed nor a failure
    card15, got = wire15(monkeypatch, t, dict(G15), first_post_bet={"g"})
    card15.run_card(do_publish=True, now=datetime(2026, 12, 5, 16, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["other_model_bet"]
    assert mlcard.FIRST_POST_MODEL_ID == fp.MODEL_ID and fp.OTHER_MODEL_ID == mlcard.MODEL_ID


def test_both_cards_take_both_locks_in_the_same_order(monkeypatch):
    import scripts.ncaab_moneyline_card as mlcard
    import scripts.ncaab_moneyline_first_post_card as card
    import scripts.nfl_wind_publisher as wp
    taken = []
    monkeypatch.setattr(wp, "_lock_model", lambda conn, m: taken.append(m))
    mlcard.lock_both(None)
    card.lock_both(None)
    assert taken[:2] == taken[2:] == sorted([fp.MODEL_ID, om.MODEL_ID])


# ── the fill check ────────────────────────────────────────────────────────────

def test_the_fill_status_of_a_bet_at_the_next_poll():
    from scripts.ncaab_first_post_fill import fill_status
    row = {"home_price": "-150", "away_price": 130}
    assert fill_status(row, True, -150.0, 130.0) == ("unchanged", -150.0, 130.0)
    assert fill_status({"home_price": -155, "away_price": 135}, True, -150.0, 130.0) == \
        ("changed", -155.0, 135.0)
    assert fill_status(None, True, -150.0, 130.0)[0] == "book_not_listed"
    assert fill_status(None, False, -150.0, 130.0)[0] == "game_not_listed"


# ── the job ──────────────────────────────────────────────────────────────────

def test_the_job_runs_every_minute_all_year_and_is_watched(monkeypatch):
    import scheduler
    from tests.test_nba_prop_window import _fires, _jobs
    from tracking.job_heartbeat import MAX_SILENCE
    job = _jobs(monkeypatch)["ncaab_moneyline_first_post"]
    assert job.max_instances == 1 and job.coalesce is True
    start = datetime(2026, 11, 20, 0, 0, tzinfo=UTC)
    assert len(_fires(job, start, start + timedelta(hours=1) - timedelta(seconds=1))) == 60
    assert "ncaab_moneyline_first_post" in scheduler._PIPELINE_JOBS
    assert MAX_SILENCE["ncaab_moneyline_first_post"] == 20


def test_the_job_starts_the_card_only_for_a_new_post_and_publishes(monkeypatch):
    import scheduler
    import scripts.ncaab_moneyline_first_post_card as card
    ran, pub = [], []
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: ran.append(cmd) or "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: pub.append(label))
    monkeypatch.setattr(card, "plan", lambda: [])
    scheduler.run_ncaab_moneyline_first_post()
    assert ran == [] and pub == []
    monkeypatch.setattr(card, "plan", lambda: [("g", "draftkings")])
    scheduler.run_ncaab_moneyline_first_post()
    assert ran[0][-2:] == ["scripts.ncaab_moneyline_first_post_card", "--publish"]
    assert pub == ["ncaab-moneyline-first-post"]
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: "fail")
    with pytest.raises(RuntimeError):
        scheduler.run_ncaab_moneyline_first_post()
    assert pub == ["ncaab-moneyline-first-post"] * 2     # a failed run still publishes what it wrote


def test_the_kill_switch_reads_nothing(monkeypatch):
    import scripts.ncaab_moneyline_first_post_card as card
    monkeypatch.setenv("RUN_NCAAB_MONEYLINE_FIRST_POST", "0")
    monkeypatch.setattr(card, "get_connection", lambda: (_ for _ in ()).throw(AssertionError("read")))
    assert card.plan() == []
    assert card.run_card(do_publish=True)["off"] is True


def test_an_incomplete_run_exits_non_zero(monkeypatch):
    import scripts.ncaab_moneyline_first_post_card as card
    monkeypatch.setattr(card, "run_card", lambda do_publish=False: (_ for _ in ()).throw(
        card.CardIncomplete("x")))
    with pytest.raises(SystemExit) as e:
        card.main(["--publish"])
    assert e.value.code == 1


def test_the_ledger_is_worker_only():
    from data.anon_readable import WORKER_ONLY_TABLES
    import scripts.ncaab_moneyline_first_post_card as card
    assert card.DECISIONS_TABLE in WORKER_ONLY_TABLES


# ── every reader treats it as a moneyline ─────────────────────────────────────

def test_every_python_reader_treats_the_id_as_a_moneyline():
    from tracking.paper_tracker import _market_for_pick
    from tracking.pick_integrity import pick_problems
    assert _market_for_pick(fp.MODEL_ID) == "h2h"
    assert pick_problems("Duke ML", "home", None, fp.MODEL_ID, "Duke", "Kansas") == []
    assert pick_problems("Kansas ML", "home", None, fp.MODEL_ID, "Duke", "Kansas")


def test_the_app_names_it_and_reads_it_as_a_moneyline():
    meta = (fp.ROOT / "mobile" / "src" / "lib" / "modelMeta.ts").read_text(encoding="utf-8")
    i = meta.index("  ncaab_moneyline_first_post: {")
    entry = meta[i:meta.index("},", i)]
    assert "shortLabel: 'Open ML'," in entry and "longLabel: 'NCAAB Opening Moneyline'," in entry
    src = (fp.ROOT / "mobile" / "src" / "lib" / "markets.ts").read_text(encoding="utf-8")
    assert "pick.model_id === 'ncaab_moneyline_first_post' ||" in src
    assert "spread" not in fp.MODEL_ID     # the substring mappers read it as a moneyline unaided

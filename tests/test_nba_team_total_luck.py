"""The NBA home team-total unders model (`nba_team_total_luck`): every rule it
ships on, and the main-number rule it shares with the fourth search's lab.

models/nba_team_total_luck.py holds the rule; models/nba_book_numbers.py holds
which quote is a book's number (and the write-time split the live fetch
stores by). Each test below names the rule it pins. The replay of the lab on
the research cache is tests/test_nba_team_total_luck_replay.py.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import models.nba_team_total_luck as tt  # noqa: E402
import models.nba_total_luck as tl  # noqa: E402
from models import nba_book_numbers as NB  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
GID = "NBA_2026-11-05_AWY_HOM"


# ── helpers ──────────────────────────────────────────────────────────────────

def _et(y, m, d, hh, mm, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=ET).astimezone(UTC)


TIP = _et(2026, 11, 5, 19, 30)


def _target(day="2026-11-05"):
    return pd.DataFrame([{"game_id": f"NBA_{day}_AWY_HOM", "season": 2027, "game_date": day,
                          "home_team": "HOM", "away_team": "AWY"}])


def _rows(gid, fetch, quotes, market=tt.MARKET, book_age_min=0.5, snapshot_type="open"):
    """odds-table rows at one fetch: (book, line, over, under). The book's own
    last_update (snapshot_at) is `book_age_min` before the fetch (created_at)."""
    out = []
    for book, line, over, under in quotes:
        out.append({"game_id": gid, "bookmaker": book, "market": market,
                    "snapshot_type": snapshot_type,
                    "snapshot_at": (fetch - timedelta(minutes=book_age_min)).isoformat(),
                    "created_at": fetch.isoformat(), "total_line": line,
                    "over_price": over, "under_price": under,
                    "over_link": f"https://{book}/over", "under_link": f"https://{book}/under"})
    return pd.DataFrame(out)


def _proj(t, part, away_part=0.0):
    """f4_projections' columns for targets `t`, built so the home part is
    exactly `part` (pace 100 a team: the pace factor is 1)."""
    return t.assign(h_pace=100.0, a_pace=100.0, a_drtg_raw=110.0, a_drtg_adj=110.0 + part,
                    h_drtg_raw=110.0, h_drtg_adj=110.0 + away_part,
                    gap_total=part + away_part, gap_margin=0.0)


def _no_missing(monkeypatch):
    monkeypatch.setattr(tt, "missing_inputs", lambda targets, *a: {
        g: {"score_missing": [], "box_missing": [], "box_mismatch": [], "presumed_unplayed": []}
        for g in targets["game_id"]})


def _decide(art, quotes, part, monkeypatch, lead=55.0, rows=None, **kw):
    """decide() on one target whose home part is forced to `part` (the offer
    mechanics, independent of the ratings), decided on a fetch `lead` minutes
    before tip."""
    t = _target()
    fetch = TIP - timedelta(minutes=lead)
    games = t.assign(tip=pd.Timestamp(TIP))
    q = tt.quote_frame(_rows(GID, fetch, quotes) if rows is None else rows, games)
    monkeypatch.setattr(tt, "f4_projections", lambda targets, tb: _proj(t, part))
    _no_missing(monkeypatch)
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    empty = pd.DataFrame(columns=["game_id", "team", *tt.BOX_COLS])
    final = pd.DataFrame(columns=["game_id", "season", "game_date", "home_team", "away_team",
                                  "home_score", "away_score"])
    return tt.decide(t, q, empty, final, times, art, scheduled=final, **kw)


@pytest.fixture(scope="module")
def art():
    return tt.load_artifact()


def _season(n_games: int, hot: int = 18, cold: int = 10, mine: int = 14):
    """A synthetic season: HOM hosts OT1 and AWY visits OT2 once a day. AWY's
    opponents make `hot` of 40 threes, HOM's make `cold`; HOM and AWY make
    `mine`. Every other number is the same for every team."""
    games, box = [], []
    d0 = pd.Timestamp("2026-10-21")
    for i in range(n_games):
        day = (d0 + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        for home, away in (("HOM", "OT1"), ("OT2", "AWY")):
            gid = f"NBA_{day}_{away}_{home}"
            games.append({"game_id": gid, "season": 2027, "game_date": day,
                          "home_team": home, "away_team": away,
                          "home_score": 105, "away_score": 105})
            for team in (home, away):
                fg3 = {"HOM": mine, "AWY": mine, "OT1": cold, "OT2": hot}[team]
                box.append({"game_id": gid, "team": team, "points": 105, "fg_att": 88,
                            "fg3_made": fg3, "fg3_att": 40, "ft_made": 16, "ft_att": 20,
                            "offensive_reb": 10, "turnovers": 13})
    return pd.DataFrame(games), pd.DataFrame(box)


# ── one copy: the ratings are nba_total_luck's, the main number is the lab's ──

def test_the_ratings_are_the_full_game_model_s_own():
    """RULE: the ratings, completeness checks and timing arithmetic are
    models/nba_total_luck.py's, imported, never copied."""
    for name in ("team_box", "f4_projections", "side_strength", "missing_inputs",
                 "scheduled_games", "regular_season", "lead_minutes"):
        assert getattr(tt, name) is getattr(tl, name), f"nba_team_total_luck has its own {name}"
    assert (tt.MIN_GAMES, tt.BOX_COLS) == (tl.MIN_GAMES, tl.BOX_COLS)


def test_the_lab_reads_the_one_copy_of_the_main_number_rule(monkeypatch):
    """RULE: the fourth search's P1, P2 and P3 and the live model read ONE copy
    of the main-number rule (models/nba_book_numbers.py)."""
    from scripts import nba_game4_p1 as P1
    from scripts import nba_game4_p2 as P2
    from scripts import nba_game4_p3 as P3
    for name in ("RUNG_KEY", "_one_rung", "even_gap", "ladder_mask", "main_rungs",
                 "visible_numbers"):
        assert getattr(P2, name) is getattr(NB, name), f"the P2 lab has its own {name}"
    assert P1.P2 is P2
    monkeypatch.setattr(NB, "visible_numbers", lambda q, t, books=None: "the shared copy")
    assert P3.decision_quotes(None, None) == "the shared copy"


# ── the signal: the home team's part of the luck gap ────────────────────────

def test_the_home_part_is_the_lab_s_team_total_signal():
    """RULE: home_part = 0.5 x (h_pace + a_pace) / 100 x (a_drtg_adj -
    a_drtg_raw): pace times the AWAY defence's luck (scripts/nba_game4_p3.py
    f4_signal, the definition the lab graded)."""
    from scripts import nba_game4_p3 as P3
    proj = pd.DataFrame({"game_id": ["G1", "G2"], "h_pace": [98.0, 101.0], "a_pace": [102.0, 97.0],
                         "a_drtg_raw": [112.0, 108.0], "a_drtg_adj": [109.0, 110.5],
                         "h_drtg_raw": [108.0, 111.0], "h_drtg_adj": [111.0, 107.0],
                         "gap_total": [0.0, 0.0], "gap_margin": [0.0, 0.0]})
    got = tt.home_part(proj).to_numpy()
    assert got == pytest.approx([1.00 * -3.0, 0.99 * 2.5])
    lab = P3.f4_signal(proj)
    lab = lab[lab["market"] == "team_totals_home"].set_index("game_id")["strength"]
    assert got == pytest.approx(lab.loc[["G1", "G2"]].to_numpy(), abs=0.0)


def test_hot_shooting_against_the_away_defence_gives_a_home_under():
    """RULE: when the away defence's opponents made more threes than the
    league's rate so far, its raw rating is too bad, the raw projection of the
    home team's score too high: the home part is negative (an under). The
    home and away parts add up to the full-game gap."""
    games, box = _season(12)
    proj = tt.f4_projections(_target(), tt.team_box(box, games))
    part = tt.home_part(proj).iloc[0]
    away = (0.5 * (proj["h_pace"] + proj["a_pace"]) / 100.0
            * (proj["h_drtg_adj"] - proj["h_drtg_raw"])).iloc[0]
    assert part <= -tt.GAP_CUT < tt.GAP_CUT <= away, (part, away)
    assert part + away == pytest.approx(proj["gap_total"].iloc[0], abs=1e-9)
    games, box = _season(12, hot=10, cold=18)
    assert tt.home_part(tt.f4_projections(_target(), tt.team_box(box, games))).iloc[0] >= tt.GAP_CUT


@pytest.mark.parametrize("part,bets", [(-6.0, True), (-2.5, True), (-2.0, True),
                                       (-1.99, False), (0.0, False), (2.5, False), (6.0, False)])
def test_the_under_is_bet_when_the_home_part_is_minus_two_or_lower(monkeypatch, art, part, bets):
    """RULE: bet the home team total UNDER when -home_part >= 2.0, never the
    over, however good its price, and nothing under the cut."""
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, -150, +130),
         ("fanduel", 112.5, +130, -150)]
    got, decisions, diag = _decide(art, q, part, monkeypatch)
    assert (len(got) == 1) is bets, decisions
    if bets:
        assert (got[0].book, got[0].price) == ("draftkings", 130.0)
        assert decisions[0].detail.startswith("bet:")
    else:
        assert decisions[0].detail.startswith("gap_below_cut") and diag["gap_below_cut"] == 1


# ── the offer ────────────────────────────────────────────────────────────────

def test_the_offer_is_the_best_ev_under_the_market_fair_line(monkeypatch, art):
    """RULE: the under at the deciding book with the highest EV under the
    market's fair line (Pinnacle's no-vig through the team-total
    distribution). Same number, the best price wins; a better number can beat
    a better price."""
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, -110, -110),
         ("fanduel", 112.5, -115, -105), ("betmgm", 113.5, -102, -118),
         ("williamhill_us", 111.5, -125, +105)]
    bets, _, _ = _decide(art, q, -3.0, monkeypatch)
    assert len(bets) == 1
    b = bets[0]
    sig = {(2027, tt.MARKET): tt.pricing_dist(art, 2027)}
    t = _target()
    fetch = TIP - timedelta(minutes=55)
    frame = tt.quote_frame(_rows(GID, fetch, q), t.assign(tip=pd.Timestamp(TIP)))
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    vis = NB.visible_numbers(frame, times)
    neutral = H.fair_offers(H.offers(vis), H.market_fair(vis, sig))
    unders = neutral[(neutral["side"] == "under")
                     & neutral["book"].isin(config.BEST_LINE_BOOKMAKERS)]
    best = unders.sort_values("ev", ascending=False).iloc[0]
    assert (b.book, b.line, b.price) == (best["book"], best["line"], best["price"])
    assert b.fair_ref == "pinnacle" and b.ev_fair == pytest.approx(float(best["ev"]))
    assert b.ev_fair >= unders["ev"].max() - 1e-12


def test_a_tie_goes_to_the_earlier_book(monkeypatch, art):
    q = [("pinnacle", 112.5, -110, -110), ("betrivers", 112.5, -115, -105),
         ("fanduel", 112.5, -115, -105)]
    bets, _, _ = _decide(art, q, -3.0, monkeypatch)
    order = config.BEST_LINE_BOOKMAKERS
    assert order.index("fanduel") < order.index("betrivers")
    assert bets[0].book == "fanduel"


def test_without_pinnacle_the_fair_line_is_the_deciding_books_median(monkeypatch, art):
    q = [("draftkings", 112.5, -110, -110), ("fanduel", 113.5, -105, -115),
         ("betmgm", 112.5, -115, -105)]
    bets, _, _ = _decide(art, q, -3.0, monkeypatch)
    assert bets and bets[0].fair_ref == "consensus"


def test_pinnacle_and_bovada_are_never_the_book_taken(monkeypatch, art):
    q = [("pinnacle", 112.5, -140, +120), ("bovada", 116.5, -180, +150),
         ("draftkings", 112.5, -110, -110)]
    bets, _, _ = _decide(art, q, -3.0, monkeypatch)
    assert bets[0].book == "draftkings"


def test_an_under_worse_than_minus_200_is_never_taken_even_when_the_platform_floor_moves(
        monkeypatch, art):
    """RULE: -200 or better (config.min_odds_for), even when a Railway
    DEFAULT_MIN_ODDS override moves the harness's import-time floor."""
    assert config.min_odds_for(tt.MODEL_ID) == -200
    monkeypatch.setattr(H, "PRICE_FLOOR", -1000.0)
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 113.5, +170, -210),
         ("fanduel", 112.5, -110, -110)]
    bets, _, _ = _decide(art, q, -3.0, monkeypatch)
    assert bets and bets[0].book == "fanduel" and bets[0].price >= -200
    only = [("pinnacle", 112.5, -110, -110), ("draftkings", 113.5, +170, -210)]
    bets, decisions, _ = _decide(art, only, -3.0, monkeypatch)
    assert not bets and decisions[0].detail == "no_offer"


@pytest.mark.parametrize("line,taken", [(115.0, False), (113.5, True)])
def test_a_rung_more_than_a_point_off_the_deciding_books_is_never_taken(
        monkeypatch, art, line, taken):
    """RULE (models/nba_book_numbers.ladder_mask): a deciding book's number
    more than 1.0 point from the median of the deciding books' main numbers is
    an alternate line, never an offer, however good the under looks there. At
    1.0 point off it is a number like any other."""
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, -110, -110),
         ("fanduel", 112.5, -110, -110), ("betmgm", line, -110, -110)]
    bets, _, _ = _decide(art, q, -3.0, monkeypatch)
    assert (bets[0].book == "betmgm") is taken, bets


def test_the_draftkings_reference_is_its_under(monkeypatch, art):
    """RULE: the reference DraftKings price and link on an under are the
    under's (price_b / link_b), and the taken link is the under's too."""
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, -125, +105),
         ("fanduel", 112.5, -130, +110)]
    bets, _, _ = _decide(art, q, -3.0, monkeypatch)
    b = bets[0]
    assert b.book == "fanduel" and b.link == "https://fanduel/under"
    assert b.dk_price == 105.0 and b.dk_link == "https://draftkings/under"


# ── the probability, and the pricing ─────────────────────────────────────────

def test_the_probability_is_market_fair_plus_the_walk_forward_uplift(monkeypatch, art):
    """RULE: model_probability = the market-fair P(under wins) at the line +
    the bucket's uplift fitted on the graded seasons before the live one (for
    2026-27: 215 wins in 349 bets against a mean fair 0.5139, +0.1022)."""
    bucket = {int(s): v for s, v in art["bucket"].items()}
    assert {s: (v["n"], v["wins"], v["pushes"], round(v["sum_p_win"], 4))
            for s, v in bucket.items()} == {2024: (139, 84, 0, 71.3781),
                                            2025: (112, 70, 0, 57.1987),
                                            2026: (98, 61, 0, 50.7600)}
    up = tt.uplift(art, 2027)
    assert up == pytest.approx((215 - sum(v["sum_p_win"] for v in bucket.values())) / 349)
    assert up == pytest.approx(0.1022, abs=5e-5)
    assert tt.uplift(art, 2026) == pytest.approx(0.1013, abs=5e-5)     # fitted on 2024-2025
    assert tt.uplift(art, 2025) == pytest.approx(0.0908, abs=5e-5)     # fitted on 2024
    with pytest.raises(ValueError, match="no graded bucket season before 2024"):
        tt.uplift(art, 2024)
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, -110, -110)]
    b = _decide(art, q, -3.0, monkeypatch)[0][0]
    assert b.p_model == pytest.approx(b.p_fair + up) and b.uplift == pytest.approx(up)


def _art(rows, built):
    return {"kind": tt.ARTIFACT_KIND, "built_at": built, "tt_resid": rows, "bucket": {}}


def test_each_season_is_priced_on_the_seasons_before_it_only(art):
    """RULE: season S is priced on the team-total residuals of seasons before
    S, at least 600 of them, and NEVER on S's own (no fallback)."""
    assert tt.newest_season(art) == 2026
    seasons = pd.Series([int(s) for s, _ in art["tt_resid"]])
    assert tt.pricing_dist(art, 2027).n == int((seasons < 2027).sum()) == 14460
    assert tt.pricing_dist(art, 2024).n == int((seasons < 2024).sum()) == 7080
    rng = np.random.default_rng(0)
    own = [(2026, float(v)) for v in rng.normal(30.0, 11.0, 5000)]
    few = [(2025, float(v)) for v in rng.normal(0.0, 11.0, 599)]
    with pytest.raises(ValueError, match="599 team-total residuals before 2026"):
        tt.pricing_dist(_art(few + own, "few"), 2026)
    d = tt.pricing_dist(_art(few + [(2024, 1.0)] + own, "enough"), 2026)
    assert d.n == 600                       # the season's own 5,000 are not in it


# ── the quotes: shaping, the fetch instant, the lab's own loader ────────────

def test_a_team_total_row_reads_its_line_over_and_under():
    """RULE: line = total_line, price_a = the over, price_b = the under, the
    fetch instant is created_at; only pre-game home main rows are read."""
    fetch = TIP - timedelta(minutes=55)
    rows = pd.concat([
        _rows(GID, fetch, [("fanduel", 112.5, -105, -115)]),
        _rows(GID, fetch, [("fanduel", 115.5, +140, -175)], market="team_totals_home_alternate"),
        _rows(GID, fetch, [("fanduel", 108.5, -110, -110)], market="team_totals_away"),
        _rows(GID, fetch, [("fanduel", 221.5, -110, -110)], market="totals"),
        _rows(GID, fetch, [("draftkings", 112.5, -110, -110)], snapshot_type="in_play")],
        ignore_index=True)
    q = tt.quote_frame(rows, _target().assign(tip=pd.Timestamp(TIP)))
    assert len(q) == 1
    r = q.iloc[0]
    assert (r["book"], r["line"], r["price_a"], r["price_b"]) == ("fanduel", 112.5, -105, -115)
    assert r["link_b"] == "https://fanduel/under" and bool(r["coherent"])
    assert r["fetch_at"] == pd.Timestamp(fetch) == r["snapshot_at"]


def test_staleness_is_judged_on_the_fetch_instant_and_each_book_s_age_is_kept(monkeypatch, art):
    """RULE: a book whose own last_update is two hours old, in a fetch made at
    T, is visible at T (the lab's purchase rows carried the fetch instant, so
    the lab never dropped a team total for its book's stamp). Its age is kept
    on the decision so it can be measured."""
    fetch = TIP - timedelta(minutes=55)
    rows = pd.concat([_rows(GID, fetch, [("pinnacle", 112.5, -110, -110)]),
                      _rows(GID, fetch, [("draftkings", 112.5, -125, +105)], book_age_min=120)],
                     ignore_index=True)
    bets, decisions, _ = _decide(art, None, -3.0, monkeypatch, rows=rows)
    assert bets and bets[0].book == "draftkings", decisions
    assert decisions[0].book_ages == {"pinnacle": 0.5, "draftkings": 120.0}


def test_a_fetch_older_than_an_hour_is_not_visible():
    """RULE: each book's newest fetch at or before T, no older than 60 minutes
    by the fetch instant (scripts.nba_game_harness.visible)."""
    T = TIP - timedelta(minutes=55)
    games = _target().assign(tip=pd.Timestamp(TIP))
    rows = pd.concat([_rows(GID, T - timedelta(minutes=61), [("fanduel", 112.5, -110, -110)]),
                      _rows(GID, T - timedelta(minutes=59), [("betmgm", 112.5, -110, -110)]),
                      _rows(GID, T + timedelta(minutes=1), [("draftkings", 112.5, -110, -110)])],
                     ignore_index=True)
    vis = NB.visible_numbers(tt.quote_frame(rows, games),
                             pd.DataFrame({"game_id": [GID], "T": [pd.Timestamp(T)]}))
    assert vis["book"].tolist() == ["betmgm"]


def test_the_live_shaping_gives_what_the_lab_s_loader_gave(tmp_path):
    """RULE: on team-total rows the live shaping (quote_frame -> the harness's
    frame_quotes) gives exactly what the lab's per-game loader
    (scripts.nba_game_harness.load_per_event) gave, when created_at carries
    the purchase instant: the same rows, numbers, prices and coherence."""
    games = pd.DataFrame([{"game_id": GID, "season": 2027, "game_date": "2026-11-05",
                           "tip": pd.Timestamp(TIP)},
                          {"game_id": "NBA_2026-11-05_OT2_OT1", "season": 2027,
                           "game_date": "2026-11-05", "tip": pd.Timestamp(TIP + timedelta(hours=1))}])
    raw = []
    for gid, tip in zip(games["game_id"], games["tip"]):
        for lead in (61.0, 55.0):
            at = tip - timedelta(minutes=lead)
            for book, line, over, under in (("pinnacle", 112.5, -110, -110),
                                            ("fanduel", 111.5, -120, +100),
                                            ("betrivers", 114.5, +150, -190),
                                            ("betmgm", 112.5, +105, +105),     # incoherent
                                            ("draftkings", 112.5, -110, None)):   # one-sided
                raw.append({"game_id": gid, "bookmaker": book, "market": tt.MARKET,
                            "snapshot_type": "open", "snapshot_at": at.isoformat(),
                            "source": H.PER_EVENT_SOURCE, "spread_home": None,
                            "total_line": line, "over_price": over, "under_price": under,
                            "home_price": None, "away_price": None})
        late = tip + timedelta(minutes=2)                              # after tip: neither keeps it
        raw.append({**raw[-1], "bookmaker": "fanduel", "snapshot_at": late.isoformat(),
                    "under_price": -110})
    o = pd.DataFrame(raw)
    for c in ("spread_home", "total_line", "over_price", "under_price", "home_price", "away_price"):
        o[c] = o[c].astype(float)
    o.to_parquet(tmp_path / "nba_odds.parquet")
    lab = H.load_per_event(games, cache=tmp_path)
    live = tt.quote_frame(o.assign(created_at=o["snapshot_at"]), games)
    key = ["game_id", "book", "fetch_at", "line"]
    cols = list(H.QUOTE_COLS)
    a = lab[lab["market"] == tt.MARKET][cols].sort_values(key).reset_index(drop=True)
    b = live[cols].sort_values(key).reset_index(drop=True)
    assert len(a) == 16                                    # 2 games x 2 fetches x 4 two-sided books
    pd.testing.assert_frame_equal(a, b)


# ── the main number: the live write-time split ──────────────────────────────

def _tt_row(book, line, over, under, market="team_totals_home", gid="G", **extra):
    return {"game_id": gid, "bookmaker": book, "market": market, "total_line": line,
            "over_price": over, "under_price": under, **extra}


def test_the_split_keeps_each_book_s_main_rung_under_the_market_s_own_name():
    """RULE: of one fetch's rungs for a (game, book, market), the one whose two
    prices are closest to even keeps the market's name; every other rung is
    stored under the _alternate name. Rows keep their order and every key; the
    rows passed in are not changed."""
    rows = [_tt_row("betrivers", 110.5, -150, +120, over_link="a"),
            _tt_row("betrivers", 111.5, -110, -110, over_link="b"),
            _tt_row("betrivers", 112.5, +120, -150, over_link="c"),
            _tt_row("fanduel", 111.5, -112, -108),
            _tt_row("fanduel", 108.5, -110, -110, market="team_totals_away"),
            _tt_row("fanduel", 109.5, +115, -140, market="team_totals_away")]
    before = [dict(r) for r in rows]
    main, alt = NB.split_main_rungs(rows)
    assert rows == before
    assert [(r["bookmaker"], r["market"], r["total_line"]) for r in main] == [
        ("betrivers", "team_totals_home", 111.5), ("fanduel", "team_totals_home", 111.5),
        ("fanduel", "team_totals_away", 108.5)]
    assert [(r["market"], r["total_line"], r.get("over_link")) for r in alt] == [
        ("team_totals_home_alternate", 110.5, "a"), ("team_totals_home_alternate", 112.5, "c"),
        ("team_totals_away_alternate", 109.5, None)]
    assert main[0]["over_link"] == "b"


def test_the_main_rung_is_coherent_first_and_ties_go_to_the_lower_number():
    """RULE (the lab's main_rungs): an incoherent rung is never the main one,
    even with even prices; two equally even rungs go to the lower number,
    whatever their order."""
    main, _ = NB.split_main_rungs([_tt_row("betmgm", 109.5, +150, +150),
                                   _tt_row("betmgm", 111.5, -115, -105)])
    assert [r["total_line"] for r in main] == [111.5]
    for rows in ([_tt_row("betmgm", 112.5, -110, -110), _tt_row("betmgm", 111.5, -110, -110)],
                 [_tt_row("betmgm", 111.5, -110, -110), _tt_row("betmgm", 112.5, -110, -110)]):
        main, alt = NB.split_main_rungs(rows)
        assert [r["total_line"] for r in main] == [111.5] and len(alt) == 1


def test_a_one_sided_rung_is_never_the_main_one():
    """RULE: only a rung with both prices can be a book's number, as in the
    lab, whose loader drops a one-sided quote before choosing. A book with no
    two-sided rung keeps nothing under the market's own name."""
    main, alt = NB.split_main_rungs([_tt_row("betparx", 111.5, -110, None),
                                     _tt_row("betparx", 113.5, +130, -160)])
    assert [r["total_line"] for r in main] == [113.5]
    assert [(r["total_line"], r["market"]) for r in alt] == [(111.5, "team_totals_home_alternate")]
    main, alt = NB.split_main_rungs([_tt_row("betparx", 111.5, None, -110)])
    assert main == [] and len(alt) == 1


def test_the_split_reads_team_totals_only():
    assert NB.split_main_rungs([]) == ([], [])
    with pytest.raises(ValueError, match="not a team-total market"):
        NB.split_main_rungs([_tt_row("fanduel", 221.5, -110, -110, market="totals")])


# ── the ladder rule takes the model's own deciding books ────────────────────

def _vis(quotes):
    T = pd.Timestamp(TIP - timedelta(minutes=55))
    return pd.DataFrame([{"game_id": "G", "market": tt.MARKET, "book": b, "line": ln,
                          "price_a": -110.0, "price_b": -110.0, "coherent": True,
                          "fetch_at": T, "T": T} for b, ln in quotes])


def test_the_ladder_rule_masks_and_medians_only_the_deciding_books_given():
    """RULE: ladder_mask(books=...) masks only the deciding books it is given,
    and only they make the median; Pinnacle is never masked. The default is
    the harness's deciding books."""
    v = _vis([("fanduel", 111.5), ("draftkings", 111.5), ("betrivers", 114.5),
              ("pinnacle", 115.5)])
    assert "betrivers" in config.BEST_LINE_BOOKMAKERS
    assert v.loc[NB.ladder_mask(v, v), "book"].tolist() == ["betrivers"]
    assert v.loc[NB.ladder_mask(v, v, ("fanduel", "draftkings")), "book"].tolist() == []
    # betrivers alone deciding: the median is its own number, fanduel is not masked
    assert v.loc[NB.ladder_mask(v, v, ("betrivers",)), "book"].tolist() == []
    # two of three deciding books at 114.5 move the median there: fanduel is the rung
    w = _vis([("fanduel", 111.5), ("betmgm", 114.5), ("betrivers", 114.5)])
    assert w.loc[NB.ladder_mask(w, w, ("fanduel", "betmgm", "betrivers")), "book"].tolist() == [
        "fanduel"]


# ── decision timing ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("lead,age,want", [
    (66.0, 0.0, "too_early"), (65.9, 0.0, "decide"), (64.4, 0.0, "decide"),
    (54.3, 0.0, "decide"), (45.0, 0.0, "decide"), (44.9, 0.0, "too_late"),
    (55.0, 5.0, "decide"), (55.0, 5.1, "stale_fetch"), (-1.0, 0.0, "too_late")])
def test_a_game_is_decided_on_a_fresh_fetch_45_to_66_minutes_before_tip(lead, age, want):
    """RULE: the graded bets were decided 54.3 to 64.4 minutes before tip
    (registered window 45-75). A fetch decides when it landed 45 to 66 minutes
    before tip and is at most 5 minutes old."""
    fetch = TIP - timedelta(minutes=lead)
    assert tt.timing(TIP, fetch, fetch + timedelta(minutes=age)) == want


def test_the_planned_fetch_lands_inside_the_decision_window():
    lo, hi = tt.FETCH_LEAD_MIN
    assert tt.DECISION_LEAD_MIN[0] <= lo < hi < tt.DECISION_LEAD_MIN[1]
    assert lo <= 54.3 <= hi                                 # the graded bets' usual lead


# ── the record of every decided game ────────────────────────────────────────

def test_every_decided_game_is_recorded_with_its_best_under_offer(monkeypatch, art):
    """RULE: a decision record for every decided game, bet or not, carrying
    the home part, the full-game gap and the best under offer (book, line,
    price, fair and model probability), so the cut can be swept on live data."""
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, -125, +105)]
    bets, decisions, _ = _decide(art, q, -1.5, monkeypatch)
    assert bets == [] and len(decisions) == 1
    d = decisions[0]
    assert d.n_bets == 0 and d.detail == "gap_below_cut:1.50"
    assert d.home_part == pytest.approx(-1.5) and d.gap_total == pytest.approx(-1.5)
    assert (d.book, d.line, d.price) == ("draftkings", 112.5, 105.0)
    assert d.p_model == pytest.approx(d.p_fair + tt.uplift(art, 2027))
    assert d.fair_ref == "pinnacle" and d.fair_mu == d.fair_mu
    bets, decisions, _ = _decide(art, q, -3.0, monkeypatch)
    d = decisions[0]
    assert d.n_bets == 1 and (d.book, d.price, d.p_fair) == (bets[0].book, bets[0].price,
                                                             bets[0].p_fair)


def test_one_season_per_call(monkeypatch, art):
    t = pd.concat([_target(), _target().assign(game_id="X", season=2026)], ignore_index=True)
    empty = pd.DataFrame(columns=["game_id", "T"])
    with pytest.raises(ValueError, match="one season per call"):
        tt.decide(t, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), empty, art,
                  scheduled=pd.DataFrame())


def test_the_ev_floor_is_the_model_s_own_and_the_bet_is_priced_as_a_rule():
    """RULE (CLAUDE.md 1b): the model carries its own EV floor, 0.00, applied to
    p_model x decimal - 1 (models.honest_ev.gate); on the 349 graded bets it
    removes one (tests/test_nba_team_total_luck_replay.py measures it)."""
    assert config.min_ev_for(tt.MODEL_ID) == 0.0 and tt.MODEL_ID in config.MODEL_OWN_EV_FLOOR
    assert tt.MODEL_ID in config.MODELS_ON_OWN_PROBABILITY
    assert config.scoring_method(tt.MODEL_ID) == "rule"
    from models.honest_ev import gate
    g = gate(tt.MODEL_ID, 0.60, -112)
    assert g.cal_prob == 0.60 and g.ev == pytest.approx(0.60 * (1 + 100 / 112) - 1)


def test_opening_night_declines_every_game_without_crashing(art):
    """RULE: on a season with no final game yet, every game is declined under
    the 10-game rule. On 2026-10-20 the card failed every tick of its window:
    the real ratings (never the stand-in _decide uses) raised on the empty,
    object-dtype box. No stand-in here."""
    t = _target()
    fetch = TIP - timedelta(minutes=55)
    games = t.assign(tip=pd.Timestamp(TIP))
    q = tt.quote_frame(_rows(GID, fetch, [("pinnacle", 112.5, -110, -110),
                                          ("draftkings", 112.5, -110, -110)]), games)
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    empty = pd.DataFrame(columns=["game_id", "team", *tt.BOX_COLS])
    final = pd.DataFrame(columns=["game_id", "season", "game_date", "home_team", "away_team",
                                  "home_score", "away_score"])
    bets, decisions, diag = tt.decide(t, q, empty, final, times, art, scheduled=final)
    assert bets == [] and diag["early_season"] == 1, (decisions, diag)

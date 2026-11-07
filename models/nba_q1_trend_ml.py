"""
NBA first-quarter moneyline, the hot team: the spread model's cover-record step (`nba_q1_trend`), bet on the same
team's first-quarter MONEYLINE (`nba_q1_trend_ml`).

LIVE, real money, on mike's instruction (2026-11-07, "Build it anyway", after the search said to leave it). It did NOT
pass the house standard: it failed the 200-bet bar, as the spread model did. The research it ships from is the
first-quarter moneyline / total search (docs/nba_search_q1mt.md: family Q1M, the spread check, k >= 2; lab
scripts/nba_s_q1mt.py, run 2026-11-07-q1mt in nba_game2_cells).

THE EVIDENCE (graded at bought prices, 2023-24 .. 2025-26, decision point D: the per-game purchase 45-75 minutes
before tip, the best deciding offer under the first-quarter moneyline's no-vig fair price, -200 floor):

    87 bets   46-35-6   +17.78 units   +25.8%   interval +1.7% to +50.0%
    2023-24  +39.3%      2024-25  +45.5%      2025-26  +4.3% (36 bets)
    prices -192 to +360, median +130

IT IS THE SPREAD MODEL'S BET ON ANOTHER TICKET. It takes the same team as nba_q1_trend in 87 of that model's 88 games
and bets no other game; on those games the spread made +26.33 units (+27.4%). Live beside it, each signal game carries
two bets on one signal. The search said so and recommended against it; mike chose to build it.

THE RULE: nba_q1_trend's steps 1-5 exactly, imported (the game's first-quarter SPREAD number, both teams' venue
cover records, the step, k >= 2, mike's season-average check), then:
  6. THE OFFER: the hot team's first-quarter moneyline at the deciding book (config.BEST_LINE_BOOKMAKERS) with the
     highest expected value under the first-quarter moneyline's fair price (Pinnacle's no-vig when it quotes
     coherently, else the deciding books' median no-vig), at -200 or better (config.min_odds_for). The candidates
     are the lab's own (scripts.nba_s_q1mt.ml_cand). The rule decides the game and the side; the fair price only
     chooses the offer.
  7. SETTLEMENT: the first quarter's points (nba_period_scores, period 1): the hot team ahead wins, behind loses, a
     level quarter is a PUSH (a two-way first-quarter moneyline voids a tie at every book). A game whose periods fail
     the first search's check stays PENDING.

THE PROBABILITY (model_probability): the market-fair P(the hot side wins | the quarter is not level) at the chosen
price, PLUS the cell's walk-forward uplift: realised win share minus mean fair probability over the DECIDED graded
bets of the seasons before the live one (uplift below). The harness's moneyline probability is conditional on no tie
(scripts.nba_game_harness.side_probs), so a push is in neither the numerator nor the denominator here, unlike the
spread model's arithmetic (models.nba_total_luck.uplift), whose probability is unconditional. For 2026-27 it is
fitted on all 87 bets.

DECISION TIME: the spread model's, on the SAME fetch (data/ingestors/nba_first_quarter_odds.py asks for both markets
in one call, as the graded purchase held both). Each game is decided ONCE (CLAUDE.md 1c), in its own ledger.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import config
import models.nba_q1_trend as q1
from models.nba_q1_trend import (  # noqa: F401
    CHECK, DECISION_LEAD_MIN, FETCH_LEAD_MIN, HISTORY_SOURCE, K_CUT, LIVE_SOURCE, POINT, REFERENCE_BOOK,
    SIDE_LABEL, STALE_FETCH_MAX_MIN, WINDOW, Q1Decision, book_ages, lead_minutes, regular_season, timing)

MODEL_ID = "nba_q1_trend_ml"
SPORT = "NBA"
MARKET = "h2h_q1"
SIGNAL_MARKET = q1.MARKET            # spreads_q1: the number the rule reads
MARKETS = (SIGNAL_MARKET, MARKET)

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = "models/saved/nba_q1_trend_ml_20261107.pkl"
ARTIFACT_KIND = "nba_q1_trend_ml"

DIAG_KEYS = q1.DIAG_KEYS


# ── the artifact ─────────────────────────────────────────────────────────────

def load_artifact(path: str | Path | None = None) -> dict:
    """The committed artifact (ARTIFACT_PATH), else its copy in Supabase's model_artifacts table, else raise."""
    p = Path(path) if path is not None else ROOT / ARTIFACT_PATH
    if not p.exists() and path is None:
        from data.db import get_connection
        from models.trainer import _restore_artifact
        conn = get_connection()
        try:
            got = _restore_artifact(conn, ARTIFACT_PATH)
        finally:
            conn.close()
        if got is None:
            raise FileNotFoundError(f"{ARTIFACT_PATH}: not on disk and not in model_artifacts")
        p = Path(got)
    with open(p, "rb") as fh:
        art = pickle.load(fh)
    if not isinstance(art, dict) or art.get("kind") != ARTIFACT_KIND:
        raise ValueError(f"{p}: not an {ARTIFACT_KIND} artifact")
    return art


def newest_season(art: dict) -> int:
    return int(max(int(s) for s in art["bucket"]))


def uplift(art: dict, season: int) -> float:
    """Realised win share minus mean market-fair win probability over the DECIDED graded bets (a level quarter is
    neither) of the seasons before `season`."""
    rows = [v for s, v in art["bucket"].items() if int(s) < int(season)]
    n = sum(v["decided"] for v in rows)
    if n == 0:
        raise ValueError(f"{MODEL_ID}: no graded bucket season before {season}")
    return (sum(v["wins"] for v in rows) - sum(v["sum_p_win_decided"] for v in rows)) / n


# ── the quotes ───────────────────────────────────────────────────────────────

def quote_frame(rows: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Stored first-quarter spread AND moneyline rows -> the harness's quote frame (models.nba_q1_trend
    .quote_frame, both markets): the spread's line is the HOME number, the moneyline's is none."""
    return q1.quote_frame(rows, games, markets=MARKETS)


# ── the decision ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Q1MLBet:
    game_id: str
    season: int
    side: str                   # 'home' or 'away': the hot team
    price: float                # the taken book's first-quarter moneyline on the hot side
    book: str
    k: float
    number: float               # the game's first-quarter spread number (rule step 1)
    p_fair: float               # P(the hot side wins | not level), the market's no-vig
    uplift: float
    p_model: float
    fair_ref: str
    fetch_at: datetime
    dk_price: float | None
    link: str | None
    dk_link: str | None


def decide(targets: pd.DataFrame, quotes: pd.DataFrame, history_tg: pd.DataFrame, times: pd.DataFrame,
           art: dict, *, books=None, min_odds: float | None = None, k_cut: float = K_CUT,
           bucket_uplift: float | None = None) -> tuple[list[Q1MLBet], list[Q1Decision], dict]:
    """The rule on frames, pure given its inputs, so the card and the replay of the lab run the same code.

    targets: today's games (game_id, season, game_date, home_team, away_team), one season.
    quotes: the harness's quote frame of today's first-quarter spreads and moneylines (quote_frame).
    history_tg: the earlier games' team rows (scripts.nba_game8_q1_trends.team_games), as nba_q1_trend reads them.
    times: (game_id, T) the decision instant per game."""
    from scripts import nba_game8_q1_trends as G8
    from scripts import nba_game_harness as H
    from scripts.nba_s_q1mt import ml_cand
    diag = dict.fromkeys(DIAG_KEYS, 0)
    if targets.empty:
        return [], [], diag
    seasons = sorted(set(int(s) for s in targets["season"]))
    if len(seasons) != 1:
        raise ValueError(f"{MODEL_ID}: one season per call, got {seasons}")
    season = seasons[0]
    books = tuple(config.BEST_LINE_BOOKMAKERS) if books is None else tuple(books)
    floor = config.min_odds_for(MODEL_ID) if min_odds is None else float(min_odds)
    up = uplift(art, season) if bucket_uplift is None else float(bucket_uplift)

    t = times[times["game_id"].isin(set(targets["game_id"]))]
    q = quotes[quotes["game_id"].isin(set(t["game_id"]))]
    vis_s = q1.visible(q[q["market"] == SIGNAL_MARKET], t, books)
    vis_m = q1.visible(q[q["market"] == MARKET], t, books)
    sig = q1.signals(q1.inputs(targets, history_tg), G8.game_numbers(vis_s))
    fair = H.market_fair(vis_m, {})
    neutral = H.fair_offers(H.offers(vis_m), fair)
    neutral = neutral[neutral["market"] == MARKET]
    cand = ml_cand(neutral, sig, CHECK)
    chosen = H.choose(cand[cand["strength"] >= k_cut], -np.inf, books=books, sides=[SIDE_LABEL], floor=floor)
    bet_by = {r.game_id: r for r in chosen.itertuples(index=False)}
    fair_by = {r.game_id: r for r in fair[fair["market"] == MARKET].itertuples(index=False)}
    sig_by = {r.game_id: r for r in sig.itertuples(index=False)}
    t_by = dict(zip(t["game_id"], t["T"]))
    ages = book_ages(vis_m)

    bets, decisions = [], []
    for g in targets.itertuples(index=False):
        gid = g.game_id
        if gid not in t_by:
            continue
        diag["games"] += 1
        T = t_by[gid]
        s = sig_by.get(gid)
        fr = fair_by.get(gid)
        c = bet_by.get(gid)
        seen = {} if s is None else {
            "number": q1._f(s.number), "pick": q1._side(getattr(s, f"pick_{WINDOW}")),
            "k": q1._f(getattr(s, f"k_{WINDOW}")),
            "h5": q1._f(s.h_ats5), "a5": q1._f(s.a_ats5), "h10": q1._f(s.h_ats10), "a10": q1._f(s.a_ats10),
            "check": bool(getattr(s, f"chk_{WINDOW}"))}
        offer = {} if c is None else {"book": str(c.book), "price": float(c.price), "p_fair": float(c.p_win),
                                      "p_model": float(c.p_win + up)}
        if fr is not None:
            offer.update(fair_ref=str(fr.ref))

        def record(n, detail):
            decisions.append(Q1Decision(gid, T, n, detail, book_ages=ages.get(gid, {}), **seen, **offer))

        if s is None or seen.get("number") is None:
            diag["no_number"] += 1
            record(0, "no_number: no first-quarter spread at the decision fetch")
            continue
        if any(seen[c_] is None for c_ in ("h5", "a5", "h10", "a10")):
            diag["no_record"] += 1
            record(0, "no_record: a team has under 10 earlier games at this venue with a number")
            continue
        if seen["pick"] is None:
            diag["not_a_step"] += 1
            record(0, f"not_a_step: last 5 {seen['h5']:+.0f} / {seen['a5']:+.0f}")
            continue
        if seen["k"] is None or seen["k"] < k_cut:
            diag["below_cut"] += 1
            record(0, f"below_cut: k {seen['k']}")
            continue
        if not seen["check"]:
            diag["check_fails"] += 1
            record(0, "check_fails: the hot team's projected first-quarter margin does not cover its number")
            continue
        if fr is None:
            diag["no_fair_line"] += 1
            record(0, "no_fair_line: no coherent first-quarter moneyline at Pinnacle or a deciding book")
            continue
        if c is None:
            diag["no_offer"] += 1
            record(0, "no_offer: no deciding book's hot-side first-quarter moneyline at -200 or better")
            continue
        side = str(c.side)
        dk = vis_m[(vis_m["game_id"] == gid) & (vis_m["book"] == REFERENCE_BOOK) & vis_m["coherent"]]
        dk_price = (float(dk["price_a"].iloc[0] if side == "home" else dk["price_b"].iloc[0])
                    if len(dk) else None)
        link_col = "link_a" if side == "home" else "link_b"
        dk_link = dk[link_col].iloc[0] if len(dk) and link_col in dk else None
        p_fair = float(c.p_win)
        bets.append(Q1MLBet(
            game_id=gid, season=season, side=side, price=float(c.price), book=str(c.book), k=float(seen["k"]),
            number=float(seen["number"]), p_fair=p_fair, uplift=float(up), p_model=float(p_fair + up),
            fair_ref=str(fr.ref), fetch_at=T, dk_price=dk_price, link=getattr(c, link_col, None), dk_link=dk_link))
        diag["bets"] += 1
        record(1, f"bet:{side} {c.book} ML {c.price:+.0f}")
    return bets, decisions, diag

"""
NBA first-half total, OVER only: the full-game shooting-luck gap, on the first
half's line (`nba_first_half_total_luck`).

LIVE, real money (CLAUDE.md section 2; mike, 2026-10-30: "Build the model that
passed."). The research it ships from is the fourth NBA search, cell C1,
docs/nba_models_2026.md sections 8.3 and 8.4 (P3, family F4 on the first-half
total, decision point D). Its siblings are models/nba_total_luck.py (the
full-game total, whose ratings and completeness checks this model imports) and
models/nba_team_total_luck.py (the home team total, whose decision window, main
number rule and row shape this model shares).

THE IDEA. A defence's points allowed per 100 possessions includes how well its
opponents happened to shoot threes and free throws, which a defence controls
little (models/nba_total_luck.py, THE IDEA). When both defences have been
unluckier than the league so far, the raw ratings project too few points, and
the first half's line is taken to follow the same raw ratings. The cut reads
that full-game gap itself, UNSCALED, in full-game points: no first-half share
is fitted (docs/nba_models_2026.md 8.3).

THE EVIDENCE (P3_F4, decision point D: the per-game purchase 45-75 minutes
before tip, totals_h1, over, cut 2.0; graded through
scripts/nba_game_harness.py at bought prices, 2023-24 .. 2025-26):

    595 bets   333-259-3   +51.49 units on 643.19 risk   +8.0%
    interval +0.4% to +15.4%
    2023-24  244 bets  +10.68 units  +4.0%
    2024-25  188 bets  +23.29 units  +11.6%
    2025-26  163 bets  +17.52 units  +9.9%
    prices   -130 to +114, median -110;  lines 100.0 to 130.5, median 114.0
    books    draftkings 161, fanduel 151, williamhill_us 106, betmgm 99,
             hardrockbet 61, betrivers 9, betparx 8

The weaknesses the judge reported are in docs/nba_models_2026.md 8.4: the
excess sits in the first half and not the second, the pass needs all eight
deciding books, and 323 of the 595 bets are on games the full-game overs model
already bets.

THE RULE, per regular-season game:
  1. RATINGS AND COMPLETENESS: exactly models/nba_total_luck.py's (team_box,
     f4_projections, missing_inputs, regular_season), imported. Both teams need
     10+ games this season (MIN_GAMES); every scheduled game of the season
     before the date must be scored and boxed, else the game is declined.
  2. THE CUT: gap_total >= 2.0 (GAP_CUT, this model's own; nba_total_luck's 3.0
     is its own and does not change).
  3. THE QUOTES (models/nba_book_numbers.py, the lab's own code): each book's
     MAIN number per fetch; each book's newest fetch at or before the decision
     instant T, no older than 60 minutes by the FETCH instant; then no deciding
     book whose number is more than 1.0 point from the median of the deciding
     books' main numbers (Pinnacle never dropped, never in the median). The live
     fetch stores only the main rung under totals_h1; any other rung goes under
     totals_h1_alternate (data/ingestors/nba_first_half_odds.py).
  4. THE FAIR LINE: Pinnacle's no-vig first-half total when it quotes
     coherently, else the median of the deciding books' solved centres
     (scripts/nba_game_harness.market_fair), priced through the first half's
     total around a + b x Pinnacle's FULL-GAME close, a and b and the residuals
     from the seasons before the live one only, at least 300 games, never the
     season's own (the artifact; scripts/nba_game4_p3.period_market_pricing).
  5. THE OFFER: the over with the highest expected value under that fair line,
     at a book in config.BEST_LINE_BOOKMAKERS, at -200 or better
     (config.min_odds_for). A tie goes to the earlier book. The gap is the cut;
     the fair line only chooses the offer.
  6. DECISION TIME: the same window as the home team total. The graded bets
     were decided 49.4 to 64.4 minutes before tip (median 54.4; the registered
     window is 45-75). Live, the window job fetches for an undecided game
     FETCH_LEAD_MIN from tip, so the first fetch lands about 55-56 minutes out
     and each later tick down to 45 is a backup; a game is decided on a fetch
     whose instant (odds.created_at) is DECISION_LEAD_MIN (45-66) minutes before
     tip and at most 5 minutes old (timing). Each game is decided ONCE (CLAUDE.md
     section 1c; the card's ledger): a later tick, a moved line or a better price
     writes nothing.
  7. SETTLEMENT: Q1 + Q2 points from nba_period_scores (tracking/paper_tracker
     ._first_half_points), overtime never counted. Over wins above the line, a
     level result is a push. A game with no trustworthy period rows stays
     PENDING: never settled from the full-game score, never a made-up result.

STALENESS IS JUDGED ON THE FETCH INSTANT, for the reason written in
models/nba_team_total_luck.py: the purchase's snapshot_at IS its fetch time, a
live row's is the book's own last_update. quote_frame keeps the book's stamp as
book_update_at and every decision records each book's age.

THE PROBABILITY (what model_probability holds): the market-fair probability
that the over WINS at the chosen line and price, PLUS the bucket's walk-forward
uplift: realised win share minus mean fair probability over the graded seasons
before the live one (pushes in the denominator). For 2026-27 it is fitted on
all three: 333 wins in 595 bets = 0.5597 against a mean fair probability of
0.5025, an uplift of +0.0572. Its EV floor (config.MODEL_OWN_EV_FLOOR, 0.00) is
applied in the card to p x decimal - 1, a push scored as a loss
(models.honest_ev.gate), as the sibling cards do. On the 595 graded bets it
removes two, both wins, which is the only way the live rule differs from the
graded cell: NBA_2024-11-18_IND_TOR, Hard Rock over 118.5 at -110, and
NBA_2025-01-02_BOS_MIN, DraftKings over 109 at -110. Without them: 593 bets,
+49.49 units, +7.7% (scripts/nba_first_half_total_luck_replay.py measures it).

THE ARTIFACT (models/saved/, ARTIFACT_PATH; scripts/nba_first_half_total_luck_build.py):
every game of 2020-21 .. 2025-26 with a Pinnacle full-game close and trustworthy
period scores, as (season, Pinnacle's closing total, the first half's total),
and the bucket's per-season counts. It must be refitted before 2027-28: the card
refuses a season the artifact does not end just before.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import config
import models.nba_team_total_luck as tt
import models.nba_total_luck as tl
from models import nba_book_numbers as NB
from models.nba_team_total_luck import (  # noqa: F401
    DECISION_LEAD_MIN, FETCH_LEAD_MIN, QUOTE_ROW_COLS, STALE_FETCH_MAX_MIN, book_ages, timing)
from models.nba_total_luck import (  # noqa: F401
    BOX_COLS, DIAG_KEYS, MIN_GAMES, UNPLAYED_AFTER_DAYS, f4_projections, lead_minutes,
    missing_inputs, regular_season, scheduled_games, side_strength, team_box)

MODEL_ID = "nba_first_half_total_luck"
SPORT = "NBA"
MARKET = "totals_h1"
SIDE = "over"
GAP_CUT = 2.0
REFERENCE_BOOK = "draftkings"

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = "models/saved/nba_first_half_total_luck_20261030_233823.pkl"
ARTIFACT_KIND = "nba_first_half_total_luck"
# scripts/nba_game4_p3.MIN_PRIOR_GAMES: the lab's bar for the market's own pricing.
MIN_PRIOR_GAMES = 300


# ── the signal ───────────────────────────────────────────────────────────────

def signal(proj: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, strength) toward the over: the full-game total gap
    itself, unscaled (scripts/nba_game4_p3.py f4_signal, totals_h1)."""
    s = proj[["game_id"]].assign(market=MARKET, strength=proj["gap_total"].to_numpy())
    return s[np.isfinite(s["strength"].to_numpy(float))].reset_index(drop=True)


# ── the artifact ─────────────────────────────────────────────────────────────

def load_artifact(path: str | Path | None = None) -> dict:
    """The committed artifact (ARTIFACT_PATH), else its copy in Supabase's
    model_artifacts table (models.trainer._restore_artifact), else raise."""
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


_DIST_CACHE: dict = {}


def pricing_dist(art: dict, season: int):
    """The first half's distribution season `season` is priced with: its total
    around a + b x Pinnacle's full-game close, a, b and the residuals from the
    games of the seasons BEFORE it, re-centred (scripts.nba_game_harness
    .ResidDist), the rows in the lab's order, so it is the lab's
    scripts/nba_game4_p3.period_market_pricing exactly. Fewer than
    MIN_PRIOR_GAMES refuses: there is no fallback to the season's own results.
    Built once per artifact and season in a process."""
    from scripts import nba_game_harness as H
    from scripts.nba_game4_p3 import _line_fit
    key = (art.get("built_at"), len(art["h1_rows"]), int(season))
    if key not in _DIST_CACHE:
        r = pd.DataFrame(art["h1_rows"], columns=["season", "close_total", "h1_total"])
        prior = r[r["season"].astype(int) < int(season)]
        xv, yv = prior["close_total"].to_numpy(float), prior["h1_total"].to_numpy(float)
        ok = np.isfinite(xv) & np.isfinite(yv)
        if int(ok.sum()) < MIN_PRIOR_GAMES:
            raise ValueError(f"{MODEL_ID}: {int(ok.sum())} games with a first-half total before "
                             f"{season} (need {MIN_PRIOR_GAMES}); no own-season fallback")
        a, b = _line_fit(xv[ok], yv[ok])
        _DIST_CACHE[key] = H.ResidDist(
            yv[ok] - (a + b * xv[ok]),
            f"{season} {MARKET}: result around {a:.2f} + {b:.3f} x Pinnacle's full-game close, "
            f"seasons < {season} ({int(ok.sum())} games)")
    return _DIST_CACHE[key]


def uplift(art: dict, season: int) -> float:
    """The bucket's realised win share minus its mean market-fair win
    probability over the graded seasons before `season`
    (models.nba_total_luck.uplift's arithmetic, pushes in the denominator)."""
    try:
        return tl.uplift(art, season)
    except ValueError:
        raise ValueError(f"{MODEL_ID}: no graded bucket season before {season}") from None


def newest_season(art: dict) -> int:
    return int(max(int(row[0]) for row in art["h1_rows"]))


# ── the quotes ───────────────────────────────────────────────────────────────

def quote_frame(rows: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Stored `odds` rows (QUOTE_ROW_COLS; the links may be absent) -> the
    harness's quote frame: models.nba_team_total_luck.quote_frame on this
    model's market. line = total_line, price_a = the over, price_b = the under."""
    return tt.quote_frame(rows, games, market=MARKET)


# ── the decision ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FirstHalfBet:
    game_id: str
    season: int
    line: float                 # the first half's points line
    price: float                # the taken book's over price
    book: str
    gap_total: float            # the full-game gap, points (bet: >= 2)
    p_fair: float               # market-fair P(over wins) at this line
    p_push: float               # market-fair P(push) at this line
    ev_fair: float              # EV per unit risked under the market's fair line
    uplift: float               # the bucket's walk-forward uplift for the season
    p_model: float              # p_fair + uplift: model_probability
    fair_ref: str               # 'pinnacle' or 'consensus'
    fair_mu: float              # the market's fair centre for the first half's points
    fetch_at: datetime          # T, the decision instant
    dk_price: float | None      # DraftKings' over at this number at T, else None
    link: str | None            # the taken book's betslip link (the over)
    dk_link: str | None


@dataclass(frozen=True)
class FirstHalfDecision:
    """One per decided game, bet or not: what the rule saw and why it did or
    did not bet. The best over offer is recorded on every game that had one,
    so the cut can be swept on live data (CLAUDE.md section 1b)."""
    game_id: str
    fetch_at: datetime
    gap_total: float | None
    n_bets: int
    detail: str
    book: str | None = None
    line: float | None = None
    price: float | None = None
    p_fair: float | None = None
    p_model: float | None = None
    fair_ref: str | None = None
    fair_mu: float | None = None
    book_ages: dict = field(default_factory=dict)


def decide(targets: pd.DataFrame, quotes: pd.DataFrame, box: pd.DataFrame,
           final_games: pd.DataFrame, times: pd.DataFrame, art: dict, *,
           scheduled: pd.DataFrame,
           books=None, min_odds: float | None = None, gap_cut: float = GAP_CUT,
           bucket_uplift: float | None = None
           ) -> tuple[list[FirstHalfBet], list[FirstHalfDecision], dict]:
    """The rule on frames. Pure given its inputs, so the card and the replay of
    the lab run the same code. The arguments are
    models.nba_team_total_luck.decide's; `quotes` holds totals_h1 rows."""
    from scripts import nba_game_harness as H
    diag = dict.fromkeys(DIAG_KEYS, 0)
    diag["presumed_unplayed"] = []
    if targets.empty:
        return [], [], diag
    seasons = sorted(set(int(s) for s in targets["season"]))
    if len(seasons) != 1:
        raise ValueError(f"{MODEL_ID}: one season per call, got {seasons}")
    season = seasons[0]
    books = tuple(config.BEST_LINE_BOOKMAKERS) if books is None else tuple(books)
    floor = config.min_odds_for(MODEL_ID) if min_odds is None else float(min_odds)
    up = uplift(art, season) if bucket_uplift is None else float(bucket_uplift)
    sig = {(season, MARKET): pricing_dist(art, season)}

    tb = team_box(box, final_games)
    proj = f4_projections(targets, tb)
    gaps = dict(zip(proj["game_id"], proj["gap_total"]))
    missing = missing_inputs(targets, scheduled_games(scheduled), final_games, tb)

    t = times[times["game_id"].isin(set(targets["game_id"]))]
    q = quotes[(quotes["market"] == MARKET) & quotes["game_id"].isin(set(t["game_id"]))]
    vis = NB.visible_numbers(q, t, books)
    fair = H.market_fair(vis, sig)
    neutral = H.fair_offers(H.offers(vis), fair)
    neutral = neutral[neutral["market"] == MARKET]
    cand = side_strength(neutral, signal(proj))
    # The bets: exactly the lab's path (the cut, then the best offer).
    chosen = H.choose(cand[cand["strength"] >= gap_cut], -np.inf, books=books,
                      sides=[SIDE], floor=floor)
    # The record: the best over offer on every game, whatever its gap.
    best = H.choose(neutral, -np.inf, books=books, sides=[SIDE], floor=floor)
    bet_by = {r.game_id: r for r in chosen.itertuples(index=False)}
    best_by = {r.game_id: r for r in best.itertuples(index=False)}
    fair_by = {r.game_id: r for r in fair[fair["market"] == MARKET].itertuples(index=False)}
    t_by = dict(zip(t["game_id"], t["T"]))
    ages = book_ages(vis)

    bets, decisions = [], []
    presumed: set[str] = set()
    for g in targets.itertuples(index=False):
        gid = g.game_id
        if gid not in t_by:
            continue
        diag["games"] += 1
        T = t_by[gid]
        gap = gaps.get(gid)
        o, fr = bet_by.get(gid) or best_by.get(gid), fair_by.get(gid)
        offer = {} if o is None else {
            "book": str(o.book), "line": float(o.line), "price": float(o.price),
            "p_fair": float(o.p_win), "p_model": float(o.p_win + up)}
        if fr is not None:
            offer.update(fair_ref=str(fr.ref), fair_mu=float(fr.mu))

        def record(n, detail, with_gap=True):
            decisions.append(FirstHalfDecision(
                gid, T, float(gap) if with_gap and gap is not None else None, n, detail,
                book_ages=ages.get(gid, {}), **offer))

        miss = missing[gid]
        presumed.update(miss["presumed_unplayed"])
        why = next((k for k in ("score_missing", "box_missing", "box_mismatch") if miss[k]), None)
        if why:
            diag[why] += 1
            record(0, f"{why}:{tl._named(miss[why])}", with_gap=False)
            continue
        if gap is None:
            diag["early_season"] += 1
            record(0, f"early_season: a team has under {MIN_GAMES} games")
            continue
        if gap < gap_cut:
            diag["gap_below_cut"] += 1
            record(0, f"gap_below_cut:{gap:.2f}")
            continue
        if fr is None:
            diag["no_fair_line"] += 1
            record(0, "no_fair_line")
            continue
        c = bet_by.get(gid)
        if c is None:
            diag["no_offer"] += 1
            record(0, "no_offer")
            continue
        dk = vis[(vis["game_id"] == gid) & (vis["book"] == REFERENCE_BOOK) & vis["coherent"]
                 & np.isclose(vis["line"], c.line)]
        dk_price = float(dk["price_a"].iloc[0]) if len(dk) else None
        dk_link = (dk["link_a"].iloc[0] if len(dk) and "link_a" in dk else None)
        p_fair = float(c.p_win)
        bets.append(FirstHalfBet(
            game_id=gid, season=season, line=float(c.line), price=float(c.price),
            book=str(c.book), gap_total=float(gap), p_fair=p_fair,
            p_push=float(c.p_push), ev_fair=float(c.ev), uplift=float(up),
            p_model=float(p_fair + up), fair_ref=str(fr.ref), fair_mu=float(fr.mu),
            fetch_at=T, dk_price=dk_price, link=getattr(c, "link_a", None), dk_link=dk_link))
        diag["bets"] += 1
        record(1, f"bet:{c.book} {c.line:g} {c.price:+.0f}")
    diag["presumed_unplayed"] = sorted(presumed)
    return bets, decisions, diag

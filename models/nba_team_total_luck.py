"""
NBA home team total, UNDER only: the home team's part of the shooting-luck gap
(`nba_team_total_luck`).

LIVE, real money (CLAUDE.md section 2). The research it ships from is the
fourth NBA search, docs/nba_models_2026.md section 8 (P3, family F4 on the
team totals, decision point D); its sibling on the full-game total is
models/nba_total_luck.py, whose ratings, completeness checks and timing rules
this model imports rather than copies.

THE IDEA. A defence's points allowed per 100 possessions includes how well its
opponents happened to shoot threes and free throws, which a defence controls
little (models/nba_total_luck.py, THE IDEA). When the AWAY defence's opponents
have made more of both than the league's rate so far, its raw rating looks
worse than it is, and a projection of the HOME team's score off the raw
ratings is too high. The home team's own part of the full-game gap measures
that, in the home team's points:

    home_part = 0.5 x (h_pace + a_pace) / 100 x (a_drtg_adj - a_drtg_raw)

(scripts/nba_game4_p3.py f4_signal; the away part is the same on the home
defence, and the two add up to nba_total_luck's gap_total to 1.5e-13 over
3,224 games). Bet the home team total UNDER when -home_part >= 2.0 (GAP_CUT).

THE EVIDENCE (P3_F4, decision point D: the per-game purchase 45-75 minutes
before tip, team_totals_home, under, cut 2.0; graded through
scripts/nba_game_harness.py at bought prices, 2023-24 .. 2025-26):

    349 bets   215-134   +64.72 units on 390.37 risk   +16.6%
    2023-24  139 bets  +21.80 units  +13.9%
    2024-25  112 bets  +23.22 units  +18.7%
    2025-26   98 bets  +19.70 units  +18.0%
    prices   -122 to +110, median -112;  lines 101.5 to 135.5
    books    fanduel 144, draftkings 85, betrivers 63, betmgm 24,
             williamhill_us 16, betparx 15, hardrockbet 2

Plan on nearer +7.7% than +16.6%: that is the home and away team totals pooled
at the same cut (713 bets, +61.3 units; docs/nba_models_2026.md 8.4).

THE RULE, per regular-season game:
  1. RATINGS AND COMPLETENESS: exactly models/nba_total_luck.py's (team_box,
     f4_projections, missing_inputs, regular_season), imported. Both teams need
     10+ games this season (MIN_GAMES); every scheduled game of the season
     before the date must be scored and boxed, else the game is declined.
  2. THE QUOTES (models/nba_book_numbers.py, the lab's own code): each book's
     MAIN number per fetch (coherent rungs first, prices closest to even, ties
     to the lower number); each book's newest fetch at or before the decision
     instant T, no older than 60 minutes by the FETCH instant (below); then no
     deciding book whose number is more than 1.0 point from the median of the
     deciding books' main numbers (Pinnacle never dropped, never in the
     median). The live fetch stores only the main rung under team_totals_home
     (split_main_rungs); the rest go under team_totals_home_alternate.
  3. THE FAIR LINE: Pinnacle's no-vig team total when it quotes coherently,
     else the median of the deciding books' solved centres
     (scripts/nba_game_harness.market_fair), priced through the empirical
     distribution of each team's score around the team total Pinnacle's
     FULL-GAME close implies (home = (total - spread_home) / 2, away = (total +
     spread_home) / 2), home and away pooled, seasons before the live one only,
     at least 600 rows, never the season's own (the artifact).
  4. THE OFFER: the under with the highest expected value under that fair
     line, at a book in config.BEST_LINE_BOOKMAKERS, at -200 or better
     (config.min_odds_for). A tie goes to the earlier book. The gap is the cut;
     the fair line only chooses the offer.
  5. DECISION TIME: the graded bets were decided 54.3 to 64.4 minutes before
     tip (median 54.4; the registered window is 45-75). Live, the window job
     fetches for an undecided game FETCH_LEAD_MIN from tip, so the first fetch
     lands about 55-56 minutes out and each later tick down to 45 is a backup;
     a game is decided on a fetch whose instant (odds.created_at) is
     DECISION_LEAD_MIN (45-66) minutes before tip and at most 5 minutes old
     (timing). Each game is decided ONCE (CLAUDE.md section 1c; the card's
     ledger): a later tick, a moved line or a better price writes nothing.
  6. SETTLEMENT: the home team's final score INCLUDING overtime
     (games.home_score; DraftKings' house rule counts overtime in a team
     total). Under wins below the line, a push when equal.

STALENESS IS JUDGED ON THE FETCH INSTANT. The lab's purchase rows carried the
feed's snapshot time, which IS the fetch time, so its 60-minute staleness rule
never dropped a team total. Live rows carry each book's own last_update, and a
team total a book has not touched for an hour would be dropped live and kept
in the lab. So quote_frame judges staleness on created_at, and keeps the book's
own stamp as book_update_at; every decision records each book's age
(fetch instant minus last_update, minutes) so it can be measured.

THE PROBABILITY (what model_probability holds): the market-fair probability
that the under WINS at the chosen line and price, PLUS the bucket's
walk-forward uplift: realised win share minus mean fair probability over the
graded seasons before the live one (pushes in the denominator). For 2026-27 it
is fitted on all three: 215 wins in 349 bets = 0.6160 against a mean fair
probability of 0.5139, an uplift of +0.1022. Its EV floor
(config.MODEL_OWN_EV_FLOOR, 0.00) is applied in the card to p x decimal - 1, a
push scored as a loss (models.honest_ev.gate), exactly as
scripts/nba_total_luck_card.py does; on the 349 graded bets it removes
exactly one, NBA_2025-01-24_POR_CHA, FanDuel under 109.5 at -118 (scripts/
nba_team_total_luck_replay.py measures it).

THE ARTIFACT (models/saved/, ARTIFACT_PATH; scripts/nba_team_total_luck_build.py):
the team-total residuals per season (2020-21 .. 2025-26), the bucket's
per-season counts, and the finished price table of 2026-27
(models/nba_total_luck.py, THE PRICE TABLE IS STORED). It must be refitted before
2027-28: the card refuses a
season the artifact does not end just before.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import config
import models.nba_total_luck as tl
from models import nba_book_numbers as NB
from models.nba_book_numbers import ALTERNATE_MARKET, split_main_rungs  # noqa: F401
from models.nba_total_luck import (  # noqa: F401
    BOX_COLS, DIAG_KEYS, MIN_GAMES, UNPLAYED_AFTER_DAYS, f4_projections, lead_minutes,
    missing_inputs, regular_season, scheduled_games, side_strength, team_box)

MODEL_ID = "nba_team_total_luck"
SPORT = "NBA"
MARKET = "team_totals_home"
SIDE = "under"
GAP_CUT = 2.0
REFERENCE_BOOK = "draftkings"

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = "models/saved/nba_team_total_luck_20261031_095356.pkl"
ARTIFACT_KIND = "nba_team_total_luck"
# Two residuals per game, 300 games: scripts/nba_game2_market.team_total_dist.
MIN_PRIOR_ROWS = 600

# ── decision timing ──────────────────────────────────────────────────────────
# The window job fetches for an undecided game whose tip is this many minutes
# away. Ticking once a minute, the first fetch lands about 55-56 minutes out,
# beside the graded bets' 54.3-54.4 (307 of 349; the other 42 at 59.3-64.4);
# each later tick down to 45 is a backup for a tick that was skipped or failed.
FETCH_LEAD_MIN = (45.0, 56.0)
# A fetch decides when it landed in [45, 66) minutes before tip, read at the
# rows' own created_at. The graded bets' leads run 54.3 to 64.4, inside it.
DECISION_LEAD_MIN = (45.0, 66.0)
# A fetch older than this is not this tick's: nothing is decided on it.
STALE_FETCH_MAX_MIN = 5.0


def timing(tip: datetime, fetch_at: datetime, now: datetime) -> str:
    """Where a game stands on this run: 'decide', or why not. `fetch_at` is the
    game's newest stored team-total fetch (odds.created_at).

    'too_late'    the fetch landed under 45 minutes before tip (or after it)
    'too_early'   the fetch landed 66 or more minutes before tip
    'stale_fetch' the fetch is more than 5 minutes old (the fetch step failed)
    """
    lead = lead_minutes(tip, fetch_at)
    if lead < DECISION_LEAD_MIN[0] or fetch_at >= tip:
        return "too_late"
    if lead >= DECISION_LEAD_MIN[1]:
        return "too_early"
    if (now - fetch_at).total_seconds() / 60.0 > STALE_FETCH_MAX_MIN:
        return "stale_fetch"
    return "decide"


# ── the signal ───────────────────────────────────────────────────────────────

def home_part(proj: pd.DataFrame) -> pd.Series:
    """The home team's part of the shooting-luck gap, in its own points: pace
    times the AWAY defence's luck (luck-adjusted minus raw points allowed per
    100), from f4_projections (scripts/nba_game4_p3.py f4_signal)."""
    pace = 0.5 * (proj["h_pace"] + proj["a_pace"]) / 100.0
    return pace * (proj["a_drtg_adj"] - proj["a_drtg_raw"])


def signal(proj: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, strength) toward the over: strength = home_part, so
    side_strength gives the under -home_part."""
    s = proj[["game_id"]].assign(market=MARKET, strength=home_part(proj).to_numpy())
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
    """The empirical team-total distribution season `season` is priced with:
    the table the artifact stores for it (models.nba_total_luck, THE PRICE TABLE IS
    STORED), else every stored residual of the seasons BEFORE it, re-centred
    (scripts.nba_game_harness.ResidDist), the rows in the order
    scripts/nba_game2_market.team_total_resid wrote them, so it is the lab's
    team_total_dist exactly. Fewer than MIN_PRIOR_ROWS refuses: there is no
    fallback to the season's own results. Once per artifact and season in a
    process."""
    key = (art.get("built_at"), len(art["tt_resid"]), int(season))
    if key not in _DIST_CACHE:
        stored = tl.stored_dist(art, season)
        _DIST_CACHE[key] = stored if stored is not None else _build_dist(art, season)
    return _DIST_CACHE[key]


def _build_dist(art: dict, season: int):
    from scripts import nba_game_harness as H
    r = pd.DataFrame(art["tt_resid"], columns=["season", "resid"])
    prior = r[r["season"].astype(int) < int(season)]
    if len(prior) < MIN_PRIOR_ROWS:
        raise ValueError(f"{MODEL_ID}: {len(prior)} team-total residuals before {season} "
                         f"(need {MIN_PRIOR_ROWS}); no own-season fallback")
    return H.ResidDist(prior["resid"].to_numpy(float), f"{season} team_totals (seasons before)")


def uplift(art: dict, season: int) -> float:
    """The bucket's realised win share minus its mean market-fair win
    probability over the graded seasons before `season`
    (models.nba_total_luck.uplift's arithmetic, pushes in the denominator)."""
    try:
        return tl.uplift(art, season)
    except ValueError:
        raise ValueError(f"{MODEL_ID}: no graded bucket season before {season}") from None


def newest_season(art: dict) -> int:
    return int(max(int(s) for s, _ in art["tt_resid"]))


# ── the quotes ───────────────────────────────────────────────────────────────

QUOTE_ROW_COLS = ("game_id", "bookmaker", "market", "snapshot_type", "snapshot_at",
                  "created_at", "total_line", "over_price", "under_price", "over_link",
                  "under_link")


def quote_frame(rows: pd.DataFrame, games: pd.DataFrame, market: str = MARKET) -> pd.DataFrame:
    """Stored `odds` rows (QUOTE_ROW_COLS; the links may be absent) -> the
    harness's quote frame, through scripts.nba_game_harness.frame_quotes:
    line = total_line, price_a = the over, price_b = the under. `market` is
    this model's, unless another per-event total model shares the shaping
    (models/nba_first_half_total_luck.py).

    The fetch instant is `created_at` (one fetch, one transaction). The
    harness's staleness rule reads snapshot_at, and for this market it is set
    to the fetch instant, as in the lab (STALENESS, above); the book's own
    last_update is kept as `book_update_at`. Pre-game ('open') rows of `market`
    only; `games` carries season, game_date and tip."""
    from scripts import nba_game_harness as H
    o = rows[(rows["market"] == market) & (rows["snapshot_type"] == "open")].copy()
    o["fetch_at"] = pd.to_datetime(o["created_at"], utc=True, format="mixed")
    o["book_update_at"] = pd.to_datetime(o["snapshot_at"], utc=True, format="mixed")
    o["snapshot_at"] = o["fetch_at"]
    for c in ("total_line", "over_price", "under_price"):
        o[c] = pd.to_numeric(o[c], errors="coerce")
    for c in ("spread_home", "home_price", "away_price"):
        o[c] = np.nan
    o["link_a"] = o["over_link"] if "over_link" in o else None
    o["link_b"] = o["under_link"] if "under_link" in o else None
    o = o.merge(games[["game_id", "season", "game_date", "tip"]], on="game_id")
    return H.frame_quotes(o, extra=("link_a", "link_b", "book_update_at"))


def book_ages(vis: pd.DataFrame) -> dict[str, dict[str, float]]:
    """game_id -> {book: minutes from the book's own last_update to the fetch
    it came in}, for the quotes visible at T."""
    if vis.empty or "book_update_at" not in vis:
        return {}
    age = (vis["fetch_at"] - vis["book_update_at"]).dt.total_seconds() / 60.0
    out: dict[str, dict[str, float]] = {}
    for gid, book, a in zip(vis["game_id"], vis["book"], age):
        if a == a:
            out.setdefault(gid, {})[str(book)] = round(float(a), 1)
    return out


# ── the decision ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TeamTotalBet:
    game_id: str
    season: int
    line: float                 # the home team's points line
    price: float                # the taken book's under price
    book: str
    home_part: float            # the home team's part of the gap, points (bet: <= -2)
    gap_total: float            # the full-game gap, for the record
    p_fair: float               # market-fair P(under wins) at this line
    p_push: float               # market-fair P(push) at this line
    ev_fair: float              # EV per unit risked under the market's fair line
    uplift: float               # the bucket's walk-forward uplift for the season
    p_model: float              # p_fair + uplift: model_probability
    fair_ref: str               # 'pinnacle' or 'consensus'
    fair_mu: float              # the market's fair centre for the home team's points
    fetch_at: datetime          # T, the decision instant
    dk_price: float | None      # DraftKings' under at this number at T, else None
    link: str | None            # the taken book's betslip link (the under)
    dk_link: str | None


@dataclass(frozen=True)
class TeamTotalDecision:
    """One per decided game, bet or not: what the rule saw and why it did or
    did not bet. The best under offer is recorded on every game that had one,
    so the cut can be swept on live data (CLAUDE.md section 1b)."""
    game_id: str
    fetch_at: datetime
    home_part: float | None
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
           ) -> tuple[list[TeamTotalBet], list[TeamTotalDecision], dict]:
    """The rule on frames. Pure given its inputs, so the card and the replay of
    the lab run the same code.

    targets      game_id, season, game_date, home_team, away_team (one season)
    quotes       quote_frame(...) rows, team_totals_home, with link_a / link_b
                 and book_update_at when the card has them
    box          nba_player_game_log rows (game_id, team and the BOX_COLS)
    final_games  the season's final regular-season games, with their scores
    times        game_id, T: each game's decision instant
    scheduled    every scheduled regular-season game of the season, scored or
                 not (models.nba_total_luck.decide, `scheduled`)
    bucket_uplift  the uplift to state the probability with; default the
                 artifact's, fitted on the seasons before this one. Only the
                 written probability depends on it, never which bet is taken.
    """
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
    parts = dict(zip(proj["game_id"], home_part(proj)))
    totals = dict(zip(proj["game_id"], proj["gap_total"]))
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
    # The record: the best under offer on every game, whatever its gap.
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
        part, total = parts.get(gid), totals.get(gid)
        o, fr = bet_by.get(gid) or best_by.get(gid), fair_by.get(gid)
        offer = {} if o is None else {
            "book": str(o.book), "line": float(o.line), "price": float(o.price),
            "p_fair": float(o.p_win), "p_model": float(o.p_win + up)}
        if fr is not None:
            offer.update(fair_ref=str(fr.ref), fair_mu=float(fr.mu))

        def record(n, detail, with_gap=True):
            decisions.append(TeamTotalDecision(
                gid, T, float(part) if with_gap and part is not None else None,
                float(total) if with_gap and total is not None else None, n, detail,
                book_ages=ages.get(gid, {}), **offer))

        miss = missing[gid]
        presumed.update(miss["presumed_unplayed"])
        why = next((k for k in ("score_missing", "box_missing", "box_mismatch") if miss[k]), None)
        if why:
            diag[why] += 1
            record(0, f"{why}:{tl._named(miss[why])}", with_gap=False)
            continue
        if part is None:
            diag["early_season"] += 1
            record(0, f"early_season: a team has under {MIN_GAMES} games")
            continue
        if -part < gap_cut:
            diag["gap_below_cut"] += 1
            record(0, f"gap_below_cut:{-part:.2f}")
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
        dk_price = float(dk["price_b"].iloc[0]) if len(dk) else None
        dk_link = (dk["link_b"].iloc[0] if len(dk) and "link_b" in dk else None)
        p_fair = float(c.p_win)
        bets.append(TeamTotalBet(
            game_id=gid, season=season, line=float(c.line), price=float(c.price),
            book=str(c.book), home_part=float(part), gap_total=float(total), p_fair=p_fair,
            p_push=float(c.p_push), ev_fair=float(c.ev), uplift=float(up),
            p_model=float(p_fair + up), fair_ref=str(fr.ref), fair_mu=float(fr.mu),
            fetch_at=T, dk_price=dk_price, link=getattr(c, "link_b", None), dk_link=dk_link))
        diag["bets"] += 1
        record(1, f"bet:{c.book} {c.line:g} {c.price:+.0f}")
    diag["presumed_unplayed"] = sorted(presumed)
    return bets, decisions, diag

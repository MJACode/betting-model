"""
NBA first-quarter spread, the hot team: mike's cover-record trend, the "bump it out to L10" step with his
season-average check (`nba_q1_trend`).

LIVE, real money, on mike's instruction (2026-11-07: build the first-quarter model, "I WANT THAT MODEL"). It did NOT
pass the house standard: it is the one first-quarter cell in any NBA search whose interval sits above zero, and it
failed the 200-bet bar. The research it ships from is the eighth NBA search (docs/nba_models_2026.md section 12, cell
Q1A, window L5to10, the spread check, k >= 2; lab scripts/nba_game8_q1_trends.py, run 2026-10-28-eighth in
nba_game2_cells).

THE EVIDENCE (graded at bought prices, 2023-24 .. 2025-26, decision point D: the per-game purchase 45-75 minutes
before tip, the best deciding offer under the first-quarter market's fair line, -200 floor):

    88 bets   58-29-1   +26.33 units   +27.4%   interval +8.85% to +44.79%
    2023-24  20 bets  +21.5%      2024-25  32 bets  +49.6%      2025-26  36 bets  +11.1%
    DraftKings alone, three seasons: 86 bets, +24.9% (+5.8% to +44.0%)

WHAT IT FAILED, said once (docs/nba_models_2026.md 12.6): the 200-bet bar (about 29 bets a season); the band just
below it (last-10 k from 0 to 2) lost 5.9% on 88 bets; its first 44 bets made +42.7% and its last 44 +12.7%; 17 bets
at a number no other book hung went 15-1-1 for +13.9 of its +26.3 units; at the worst deciding offer the interval is
-1% to +35%; telling a true +5% from zero would take about 2,530 bets.

THE RULE, per regular-season game, decided ONCE about an hour before tip:
  1. THE GAME'S FIRST-QUARTER NUMBER: Pinnacle's coherent main first-quarter spread (the HOME number, CLAUDE.md
     section 4) at the decision fetch, else the median of the deciding books' coherent main numbers, rounded to the
     nearest half point (scripts.nba_game8_q1_trends.game_numbers, imported).
  2. EACH TEAM'S COVER RESULT in an earlier game: its first-quarter margin against that game's own number, from that
     game's own decision fetch: W, L or P (scripts.nba_game8_q1_trends.team_games, imported). The archive's games
     carry the number of their one purchase 45-75 minutes before tip; this season's played games the purchase made
     for this model (data/ingestors/nba_odds_history.py, spreads_q1, tip minus 60); the live games this model's own
     decision fetch.
  3. VENUE RECORDS: each team's net (W - L) over its last 5 and last 10 games at TODAY'S venue (home games for the
     home team, road games for the away team) with a number and trustworthy first-quarter scores, strictly before
     today, reaching into the previous season (scripts.nba_game8_q1_trends.last_n, imported).
  4. THE STEP: a team at last-5 net >= 3 (4-1, 5-0) against an opponent at last-5 net -1 or -2 (2-3, 1-3 with a
     push); k = min(the hot team's last-10 net, minus the opponent's last-10 net); bet the last-5 hot team when
     k >= 2 (scripts.nba_game8_q1_trends.step_k, imported).
  5. mike's SEASON-AVERAGE CHECK: both teams with 5+ games this season; the hot team's projected first-quarter
     margin ((hot PF + cold PA) - (cold PF + hot PA)) / 2 must cover its own number.
  6. THE OFFER: the hot team's spread at the deciding book (config.BEST_LINE_BOOKMAKERS) with the highest expected
     value under the first-quarter market's fair line (Pinnacle's no-vig when it quotes coherently, else the deciding
     books' consensus), each offer at its own book's main number, at -200 or better (config.min_odds_for). The fair
     line is priced through the first quarter's margin around a + b x Pinnacle's FULL-GAME close, a, b and the
     residuals from the seasons before the live one (the artifact; scripts.nba_game4_p3.period_market_pricing).
     The rule decides the game and the side; the fair line only chooses the offer.
  7. SETTLEMENT: the first quarter's margin (nba_period_scores, period 1) against scored_line, the HOME number; a
     level quarter on a whole number is a push. A game whose periods fail the first search's check stays PENDING.

THE PROBABILITY (model_probability): the market-fair P(the hot side wins) at the chosen line and price, PLUS the
cell's walk-forward uplift: realised win share minus mean fair probability over the graded seasons before the live
one (the first-half model's arithmetic, models.nba_total_luck.uplift). For 2026-27 it is fitted on all 88 bets.

DECISION TIME: the first-half total's window (models.nba_team_total_luck: fetch 45-56 minutes out, decide on a fetch
45-66 minutes before tip that is at most 5 minutes old). Each game is decided ONCE (CLAUDE.md 1c): a later tick, a
moved line or a better price writes nothing.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import config
from models.nba_team_total_luck import (  # noqa: F401
    DECISION_LEAD_MIN, FETCH_LEAD_MIN, STALE_FETCH_MAX_MIN, book_ages, timing)
from models.nba_total_luck import lead_minutes, regular_season  # noqa: F401

MODEL_ID = "nba_q1_trend"
SPORT = "NBA"
MARKET = "spreads_q1"
WINDOW = "L5to10"                 # the lab's STEP
CHECK = "spread"
K_CUT = 2.0
HOT_MIN = 3.0                     # the lab's STEP_HOT_MIN
COLD = (-1.0, -2.0)               # the lab's STEP_COLD
MIN_AVG_GAMES = 5
SIDE_LABEL = "hot"                # the per-game side the harness keeps (side == side_pick)
REFERENCE_BOOK = "draftkings"
# The decision point the archive's numbers were taken at (scripts.nba_game_harness.POINTS["D"]).
POINT = "D"
# The live fetch's source and the purchase's source: the two sources a game's number can come from.
LIVE_SOURCE = "odds_api_nba_first_quarter_live"
HISTORY_SOURCE = "odds_api_nba_derivative_history"

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = "models/saved/nba_q1_trend_20261107.pkl"
ARTIFACT_KIND = "nba_q1_trend"
MIN_PRIOR_GAMES = 300             # scripts/nba_game4_p3.MIN_PRIOR_GAMES

DIAG_KEYS = ("games", "bets", "no_number", "no_record", "not_a_step", "below_cut", "check_fails",
             "no_fair_line", "no_offer")

QUOTE_ROW_COLS = ("game_id", "bookmaker", "market", "snapshot_type", "snapshot_at", "created_at", "source",
                  "spread_home", "home_price", "away_price", "home_link", "away_link")


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
    return int(max(int(row[0]) for row in art["q1_rows"]))


_DIST_CACHE: dict = {}


def pricing_dist(art: dict, season: int):
    """The first quarter's margin distribution season `season` is priced with: the stored table for it, else the
    margin around a + b x (minus Pinnacle's full-game closing home number), fitted on the seasons BEFORE it
    (scripts.nba_game4_p3.period_market_pricing exactly). Fewer than MIN_PRIOR_GAMES refuses."""
    import models.nba_total_luck as tl
    key = (art.get("built_at"), len(art["q1_rows"]), int(season))
    if key not in _DIST_CACHE:
        stored = tl.stored_dist(art, season)
        _DIST_CACHE[key] = stored if stored is not None else _build_dist(art, season)
    return _DIST_CACHE[key]


def _build_dist(art: dict, season: int):
    from scripts import nba_game_harness as H
    from scripts.nba_game4_p3 import _line_fit
    r = pd.DataFrame(art["q1_rows"], columns=["season", "close_spread", "q1_margin"])
    prior = r[r["season"].astype(int) < int(season)]
    xv, yv = -prior["close_spread"].to_numpy(float), prior["q1_margin"].to_numpy(float)
    ok = np.isfinite(xv) & np.isfinite(yv)
    if int(ok.sum()) < MIN_PRIOR_GAMES:
        raise ValueError(f"{MODEL_ID}: {int(ok.sum())} games with a first-quarter margin before {season} "
                         f"(need {MIN_PRIOR_GAMES}); no own-season fallback")
    a, b = _line_fit(xv[ok], yv[ok])
    return H.ResidDist(
        yv[ok] - (a + b * xv[ok]),
        f"{season} {MARKET}: result around {a:.2f} + {b:.3f} x Pinnacle's full-game close, "
        f"seasons < {season} ({int(ok.sum())} games)")


def uplift(art: dict, season: int) -> float:
    import models.nba_total_luck as tl
    try:
        return tl.uplift(art, season)
    except ValueError:
        raise ValueError(f"{MODEL_ID}: no graded bucket season before {season}") from None


# ── the quotes ───────────────────────────────────────────────────────────────

def quote_frame(rows: pd.DataFrame, games: pd.DataFrame, markets=(MARKET,)) -> pd.DataFrame:
    """Stored first-quarter spread rows (QUOTE_ROW_COLS) -> the harness's quote frame: line = spread_home (the HOME
    number), price_a = home, price_b = away. `markets`: this model's spread alone unless given; the moneyline model
    (models/nba_q1_trend_ml.py) passes the spread and the moneyline, whose line is none.

    THE FETCH INSTANT: a live row's is its created_at (one fetch, one transaction) and its snapshot_at is the book's
    own last_update; a purchased row's snapshot_at IS the historical snapshot it was bought at (its created_at is
    when it was stored). The harness judges staleness on snapshot_at, so it is set to the fetch instant here and the
    book's own stamp kept as book_update_at. `games` carries season, game_date and tip."""
    from scripts import nba_game_harness as H
    o = rows[rows["market"].isin(tuple(markets)) & (rows["snapshot_type"] == "open")].copy()
    created = pd.to_datetime(o["created_at"], utc=True, format="mixed")
    stamped = pd.to_datetime(o["snapshot_at"], utc=True, format="mixed")
    live = (o["source"] == LIVE_SOURCE).to_numpy() if "source" in o else np.ones(len(o), bool)
    o["fetch_at"] = np.where(live, created, stamped)
    o["fetch_at"] = pd.to_datetime(o["fetch_at"], utc=True)
    o["book_update_at"] = stamped
    o["snapshot_at"] = o["fetch_at"]
    for c in ("spread_home", "home_price", "away_price"):
        o[c] = pd.to_numeric(o[c], errors="coerce")
    for c in ("total_line", "over_price", "under_price"):
        o[c] = np.nan
    o["link_a"] = o["home_link"] if "home_link" in o else None
    o["link_b"] = o["away_link"] if "away_link" in o else None
    o = o.merge(games[["game_id", "season", "game_date", "tip"]], on="game_id")
    return H.frame_quotes(o, extra=("link_a", "link_b", "book_update_at"))


def visible(quotes: pd.DataFrame, times: pd.DataFrame, books=None) -> pd.DataFrame:
    """What a bettor sees at each game's T, one main number per book (models.nba_book_numbers.visible_numbers)."""
    from models import nba_book_numbers as NB
    return NB.visible_numbers(quotes, times, books)


def history_numbers(quotes: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, number) for earlier games: each game's own decision fetch (the newest fetch 45-75 minutes
    before tip, scripts.nba_game_harness.per_event_times at point D), then the game's number from it."""
    from scripts import nba_game8_q1_trends as G8
    from scripts import nba_game_harness as H
    if quotes.empty:
        return pd.DataFrame(columns=["game_id", "market", "number"])
    times = H.per_event_times(quotes, POINT)
    vis = visible(quotes, times)
    return G8.game_numbers(vis)


# ── the signal ───────────────────────────────────────────────────────────────

def inputs(targets: pd.DataFrame, tg: pd.DataFrame) -> pd.DataFrame:
    """One row per target game (game_id, season, game_date, home_team, away_team): both teams' venue cover nets over
    the last 5 and 10 (h_ = the home team's home games, a_ = the away team's road games) and their season-to-date
    first-quarter points for and against, all from before the game's date: the lab's game_inputs, its own helpers,
    without the pace and total columns this rule never reads."""
    from scripts import nba_game8_q1_trends as G8
    g = targets[["game_id", "season", "game_date", "home_team", "away_team"]].reset_index(drop=True)
    g["season"] = g["season"].astype(int)
    out = g[["game_id", "season", "game_date"]].copy()
    for pre, team_col, venue in (("h", "home_team", "home"), ("a", "away_team", "away")):
        t = g[["season", "game_date"]].assign(team=g[team_col].to_numpy(), venue=venue)
        for n in (5, 10):
            out[f"{pre}_ats{n}"] = G8.last_n(tg, t, "ats", n)
        av = G8.season_averages(tg, t)
        for c in ("n", "pf", "pa"):
            out[f"{pre}_{c}"] = av[c].to_numpy(float)
    return out.reset_index(drop=True)


def signals(inp: pd.DataFrame, numbers: pd.DataFrame) -> pd.DataFrame:
    """Per game: pick_L5to10, k_L5to10 and chk_L5to10, the lab's signals() lines for this window, with today's own
    first-quarter number."""
    from scripts import nba_game8_q1_trends as G8
    w = numbers[numbers["market"] == MARKET][["game_id", "number"]].drop_duplicates("game_id")
    x = inp.merge(w, on="game_id", how="left")
    out = x[["game_id", "season", "game_date"]].copy()
    spread = x["number"].to_numpy(float)
    have_avg = ((x["h_n"] >= MIN_AVG_GAMES) & (x["a_n"] >= MIN_AVG_GAMES)).to_numpy()
    proj_home = (((x["h_pf"] + x["a_pa"]) - (x["a_pf"] + x["h_pa"])) / 2.0).to_numpy(float)
    pick, k = G8.step_k(x["h_ats5"], x["a_ats5"], x["h_ats10"], x["a_ats10"])
    home = pick == "home"
    hot_number = np.where(home, spread, -spread)       # the hot team's own number
    proj_hot = np.where(home, proj_home, -proj_home)
    out[f"pick_{WINDOW}"], out[f"k_{WINDOW}"] = pick, k
    out[f"chk_{WINDOW}"] = (have_avg & (pick != None) & np.isfinite(spread)  # noqa: E711
                            & (proj_hot + hot_number > 0))
    out["number"] = spread
    for c in ("h_ats5", "a_ats5", "h_ats10", "a_ats10", "h_n", "a_n", "h_pf", "h_pa", "a_pf", "a_pa"):
        out[c] = x[c].to_numpy(float)
    return out


# ── the decision ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Q1Bet:
    game_id: str
    season: int
    side: str                   # 'home' or 'away': the hot team
    line: float                 # the HOME number at the taken book
    price: float                # the taken book's price on the hot side
    book: str
    k: float
    number: float               # the game's first-quarter number (rule step 1)
    p_fair: float
    p_push: float
    ev_fair: float
    uplift: float
    p_model: float
    fair_ref: str
    fair_mu: float
    fetch_at: datetime
    dk_price: float | None
    link: str | None
    dk_link: str | None


@dataclass(frozen=True)
class Q1Decision:
    """One per decided game, bet or not: the inputs the rule saw, so the live record can be read against the
    graded one."""
    game_id: str
    fetch_at: datetime
    n_bets: int
    detail: str
    number: float | None = None
    pick: str | None = None
    k: float | None = None
    h5: float | None = None
    a5: float | None = None
    h10: float | None = None
    a10: float | None = None
    check: bool | None = None
    book: str | None = None
    line: float | None = None
    price: float | None = None
    p_fair: float | None = None
    p_model: float | None = None
    fair_ref: str | None = None
    fair_mu: float | None = None
    book_ages: dict = field(default_factory=dict)


def _side(v):
    return v if v in ("home", "away") else None


def _f(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def decide(targets: pd.DataFrame, quotes: pd.DataFrame, history_tg: pd.DataFrame, times: pd.DataFrame,
           art: dict, *, books=None, min_odds: float | None = None, k_cut: float = K_CUT,
           bucket_uplift: float | None = None) -> tuple[list[Q1Bet], list[Q1Decision], dict]:
    """The rule on frames, pure given its inputs, so the card and the replay of the lab run the same code.

    targets: today's games (game_id, season, game_date, home_team, away_team), one season.
    quotes: the harness's quote frame of today's first-quarter spreads (quote_frame).
    history_tg: the earlier games' team rows (scripts.nba_game8_q1_trends.team_games on their numbers and
      first-quarter scores), strictly before today in what the rule reads.
    times: (game_id, T) the decision instant per game."""
    from scripts import nba_game8_q1_trends as G8
    from scripts import nba_game_harness as H
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
    pricing = {(season, MARKET): pricing_dist(art, season)}

    t = times[times["game_id"].isin(set(targets["game_id"]))]
    q = quotes[(quotes["market"] == MARKET) & quotes["game_id"].isin(set(t["game_id"]))]
    vis = visible(q, t, books)
    numbers = G8.game_numbers(vis)
    sig = signals(inputs(targets, history_tg), numbers)
    fair = H.market_fair(vis, pricing)
    neutral = H.fair_offers(H.offers(vis), fair)
    neutral = neutral[neutral["market"] == MARKET]
    cand = G8.spread_cand(neutral, sig, WINDOW, CHECK)
    chosen = H.choose(cand[cand["strength"] >= k_cut], -np.inf, books=books, sides=[SIDE_LABEL], floor=floor)
    bet_by = {r.game_id: r for r in chosen.itertuples(index=False)}
    fair_by = {r.game_id: r for r in fair[fair["market"] == MARKET].itertuples(index=False)}
    sig_by = {r.game_id: r for r in sig.itertuples(index=False)}
    t_by = dict(zip(t["game_id"], t["T"]))
    ages = book_ages(vis)

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
            # pandas files a missing pick as NaN once the column also holds a text one: the ledger's pick column
            # is TEXT, so anything but 'home' / 'away' is None here (tests/test_nba_q1_trend.py, the night with
            # one pattern game and one not)
            "number": _f(s.number), "pick": _side(getattr(s, f"pick_{WINDOW}")),
            "k": _f(getattr(s, f"k_{WINDOW}")),
            "h5": _f(s.h_ats5), "a5": _f(s.a_ats5), "h10": _f(s.h_ats10), "a10": _f(s.a_ats10),
            "check": bool(getattr(s, f"chk_{WINDOW}"))}
        offer = {} if c is None else {"book": str(c.book), "line": float(c.line), "price": float(c.price),
                                      "p_fair": float(c.p_win), "p_model": float(c.p_win + up)}
        if fr is not None:
            offer.update(fair_ref=str(fr.ref), fair_mu=float(fr.mu))

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
            record(0, "no_fair_line")
            continue
        if c is None:
            diag["no_offer"] += 1
            record(0, "no_offer: no deciding book's hot-side price at -200 or better")
            continue
        side = str(c.side)
        dk = vis[(vis["game_id"] == gid) & (vis["book"] == REFERENCE_BOOK) & vis["coherent"]
                 & np.isclose(vis["line"], c.line)]
        dk_price = (float(dk["price_a"].iloc[0] if side == "home" else dk["price_b"].iloc[0])
                    if len(dk) else None)
        link_col = "link_a" if side == "home" else "link_b"
        dk_link = dk[link_col].iloc[0] if len(dk) and link_col in dk else None
        p_fair = float(c.p_win)
        bets.append(Q1Bet(
            game_id=gid, season=season, side=side, line=float(c.line), price=float(c.price), book=str(c.book),
            k=float(seen["k"]), number=float(seen["number"]), p_fair=p_fair, p_push=float(c.p_push),
            ev_fair=float(c.ev), uplift=float(up), p_model=float(p_fair + up), fair_ref=str(fr.ref),
            fair_mu=float(fr.mu), fetch_at=T, dk_price=dk_price, link=getattr(c, link_col, None),
            dk_link=dk_link))
        diag["bets"] += 1
        record(1, f"bet:{side} {c.book} {c.line:+g} {c.price:+.0f}")
    return bets, decisions, diag

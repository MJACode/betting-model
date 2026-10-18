"""Second NBA game-market search: F3 (betting against part of each line move) and the controls.

docs/nba_models_2026.md section 6.3 lists the cells. scripts/nba_game_harness.py
prices, chooses and grades every one of them; scripts/nba_game2_verdict.py
judges them. This lab only EMITS cells and the coverage behind them.

F3 -- AGAINST PART OF EACH LINE MOVE (Moskowitz 2021, "Asset Pricing and Sports
Betting", Journal of Finance: the move from open to close is partly reversed by
results, so the close over-reacts). 24 cells = spreads, totals x decision
points B, C, D x move >= 0.5, 1, 1.5, 2 points, one side value "fade".

  DECIDING BOOKS  H.BETTABLE (config.BEST_LINE_BOOKMAKERS; Pinnacle and Bovada
                  are never among them).
  FIRST           per (game, market): the earliest fetch at which any deciding
                  book shows a coherent quote on the game.
  CONSENSUS(t)    the median number over the deciding books' coherent quotes
                  visible at t (H.visible: fetched at or before t, stamped no
                  more than 60 minutes before it).
  MOVE            CONSENSUS(T) - CONSENSUS(FIRST). Spreads use the HOME number,
                  so a move below zero is the market moving TOWARD the home team
                  and the fade is the away side; above zero, the home side.
                  Totals: a rise fades to the under, a fall to the over. No
                  move, no side.
  STRENGTH        abs(MOVE); the cell's cut is STRENGTH >= k.
  PRICE           every offer at T priced at H.market_fair (Pinnacle's no-vig,
                  else the deciding books' median) through the EMPIRICAL
                  distribution of results around Pinnacle's close on earlier
                  seasons (H.close_dist): a rule family, so the cut is on
                  STRENGTH and the best market-fair offer on the fade side is
                  bet.
  SIDES           "fade" is a per-game label: each game's real side (home, away,
                  over, under) is its side_pick, and every graded bet carries
                  that real side, so the harness reads bar 9 by real side.
  POPULATION      a cell's priced population (bar 9's blind bets) is the games
                  the rule produced a move number for (rule_cells); a game
                  whose line did not move is inside it, with no side.
  BAR 9           (section 6.5, second amendment) when more than 70% of the
                  choosing-season bets sit on one side of home/away,
                  favourite/underdog or over/under, the cell must beat that side
                  bet on every game of its population, no cut (H.run_cells
                  writes the shares and blinds). The fade side on every game
                  with no cut is still written, as blind_roi_choose.
  GATE AT D       H.run_cells drops any choosing season D reaches on fewer than
                  95% of its games (D here is the slate fetches).
  PLACEBO         20 runs, seed = run number 0..19: the rule's (strength,
                  side_pick) pairs are swapped between games on the same date
                  in the same market (H.shuffle_within_date on the SIGNAL frame
                  only); the market-fair prices are merged back unshuffled.

CONTROLS -- graded and reported, never candidates (family "control_<name>",
decision point C, written to cells_controls.parquet). 35 cells:

  control_blind           spreads and moneyline x home, away, favourite,
                          underdog; totals x over, under. Favourite = the side
                          the market's fair line makes the favourite.
  control_streak          against a team on a straight-up win (or loss) streak
                          of 3+ / 5+ (axis_rule win|loss), spreads and moneyline.
                          A game counts once it is FINAL: tip + 3 hours <= T.
                          Both teams streaking: against the longer streak, a
                          tie bets nothing.
  control_big_home_dog    home side when the deciding-book consensus spread at T
                          is home +7 or more; spreads and moneyline.
  control_early_under     totals under in the first 3 weeks (days 0-20 after the
                          season's opening night, from the schedule).
  control_spot_b2b_vs_rested     the first search's R1: home on night two of a
                                 back-to-back, visitor rested >= 1 day: visitor.
  control_spot_altitude          R2: Denver or Salt Lake City at home (not
                                 neutral), visitor on a back-to-back or 3-in-4:
                                 home.
  control_spot_long_travel_b2b   R3: exactly one team on night two after >= 750
                                 miles since last night: against it.
                          (scripts/nba_game_model_lab.py rule_sides; schedule
                          features from features/nba_schedule_features.py.
                          Spreads and moneyline.)
  control_soft_outlier    one deciding book's number differs from the consensus
                          by >= 1 point: bet that book's number on the side it
                          favours (spreads and totals). The refuted mechanism.
  control_public_fade     against the side holding >= 70 / >= 80 % of tickets
                          (the house's MLB public-fade trigger,
                          docs/mlb_total_public_fade.md: 70 default, 80
                          supported). Reads nba_public_splits rows captured
                          BEFORE T (capture_kind 'pregame_poll', observed_at
                          <= T). Excluded: the whole undated archive (the
                          closing split, known only after tip; it holds every
                          v1 row), and the 2022-03-09 slate, served reversed
                          home-for-away at the source. The stored history is
                          all archive, so before 2026-27 these cells bet
                          nothing. Absent table: emitted with no bets.

WALK-FORWARD. Nothing in F3 or the controls is fitted. The one fitted thing the
harness uses -- the spread / total distribution behind market_fair, the blind
bets and closing-line value -- is H.close_dist (market_pricing): season S uses
the results around Pinnacle's close on seasons before S. Graded season -> fit
seasons: 2021 -> 2021 (no earlier priced season; never chosen on), 2022 ->
2021, 2023 -> 2021-22, 2024 -> 2021-23, 2025 -> 2021-24, 2026 -> 2021-25.

GRADED LOAD. --full loads 2020-21 to 2025-26 and names all six to H.load as
required, so a cache that prices any of them on fewer than 90% of games, or in
which more than 5% of rows match no purchase record, is refused (load_data).

LOOK-AHEAD GUARDS: quotes are pre-game and fetched at or before T (H.load,
H.visible); FIRST <= T is required; a streak counts a game only from tip + 3 h;
schedule spots come from the published schedule; public splits only from a
pre-tip poll observed at or before T, never the archive or the reversed
2022-03-09 slate.

PLACEBO COUNT. --full runs exactly 20 placebo runs per cell (bar 10); the
hidden --placebo shortcut is for --smoke and is refused under --full.

    PYTHONPATH=. python -m scripts.nba_game2_move --smoke --cache <dir with the fetch ledger>
    NBA_GAME2_GO=1 PYTHONPATH=. python -m scripts.nba_game2_move --full
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_game2_verdict import CONTROL_PREFIX  # noqa: E402

RESULTS = Path(os.environ.get("NBA_GAME2_RESULTS",
                              "C:/Users/micha/AppData/Local/Temp/nba_game_edge/results"))
SMOKE_SEASONS = [H.REGIME]                                  # 2020-21
FULL_SEASONS = sorted({H.REGIME, *H.CHOOSE, H.CONFIRM})       # 2020-21 .. 2025-26, the priced seasons
N_PLACEBO = 20
SETTLE_HOURS = 3.0           # a game is final this long after tip (features/nba_schedule_features)

F3_MARKETS = ("spreads", "totals")
F3_POINTS = ("B", "C", "D")
F3_CUTS = (0.5, 1.0, 1.5, 2.0)
F3_SIDE = "fade"
F3_CELLS = 24

CONTROL_POINT = "C"
STREAK_CUTS = (3.0, 5.0)
BIG_DOG_CUTS = (7.0,)
EARLY_DAYS = 21              # first 3 weeks = days 0..20 after opening night
SPOT_CUTS = (1.0,)
OUTLIER_CUTS = (1.0,)
PUBLIC_CUTS = (70.0, 80.0)
SPLITS_POLL = "pregame_poll"             # the only nba_public_splits kind read
SPLITS_REVERSED_DATES = ("2022-03-09",)  # served home-for-away at the source: excluded
TRAVEL_MI = 750
ALTITUDE_VENUES = ("Denver", "Salt Lake City")
CONTROL_CELLS = 35
OPPOSITE = {"home": "away", "away": "home", "over": "under", "under": "over"}


# ── F3: the consensus move ──────────────────────────────────────────────────

def first_fetch(quotes: pd.DataFrame, markets=F3_MARKETS) -> pd.DataFrame:
    """(game_id, market, first_at): the earliest fetch with a coherent deciding-book quote."""
    q = quotes[quotes["market"].isin(markets) & quotes["coherent"] & quotes["book"].isin(H.BETTABLE)]
    return (q.groupby(["game_id", "market"], as_index=False)["fetch_at"].min()
            .rename(columns={"fetch_at": "first_at"}))


def consensus(quotes: pd.DataFrame, times: pd.DataFrame) -> pd.DataFrame:
    """Median number over the deciding books visible at each (game, market)'s T.

    `times`: game_id, market, T. Returns game_id, market, cons, n_books."""
    out = []
    for m, tm in times.groupby("market"):
        vis = H.visible(quotes[quotes["market"] == m], tm[["game_id", "T"]])
        v = vis[vis["coherent"] & vis["book"].isin(H.BETTABLE)]
        out.append(v.groupby(["game_id", "market"], as_index=False).agg(
            cons=("line", "median"), n_books=("book", "nunique")))
    if not out:
        return pd.DataFrame(columns=["game_id", "market", "cons", "n_books"])
    return pd.concat(out, ignore_index=True)


def fade_side(market, move):
    """The side the move went AGAINST; None where nothing moved."""
    market, move = np.asarray(market), np.asarray(move, float)
    sp = np.where(move < 0, "away", np.where(move > 0, "home", None))
    tt = np.where(move > 0, "under", np.where(move < 0, "over", None))
    return np.where(market == "spreads", sp, np.where(market == "totals", tt, None))


def move_signal(quotes: pd.DataFrame, times: pd.DataFrame, markets=F3_MARKETS) -> pd.DataFrame:
    """Per (game, market) at the decision time: the consensus move since FIRST.

    `times`: game_id, T (H.decision_times). A game whose first deciding quote
    comes after T, or with no consensus at either end, has no model number."""
    tg = times[["game_id", "T"]].merge(pd.DataFrame({"market": list(markets)}), how="cross")
    ff = first_fetch(quotes, markets).merge(tg, on=["game_id", "market"])
    # Implied by requiring a consensus at T (any deciding quote visible at T is
    # at or after FIRST); kept so no consensus is ever taken at a post-T instant.
    ff = ff[ff["first_at"] <= ff["T"]]
    c0 = consensus(quotes, ff[["game_id", "market", "first_at"]].rename(columns={"first_at": "T"}))
    c1 = consensus(quotes, ff[["game_id", "market", "T"]])
    s = (ff.merge(c0.rename(columns={"cons": "cons_first", "n_books": "n_first"}), on=["game_id", "market"])
           .merge(c1.rename(columns={"cons": "cons_T", "n_books": "n_T"}), on=["game_id", "market"]))
    s["move"] = s["cons_T"] - s["cons_first"]
    s["strength"] = s["move"].abs()
    s["side_pick"] = fade_side(s["market"], s["move"])
    s["first_to_T_min"] = (s["T"] - s["first_at"]).dt.total_seconds() / 60.0
    return s.reset_index(drop=True)


# ── shared plumbing: offers at a decision point, placebo, population ─────────

def point_frames(data: H.Data, point: str, sig: dict):
    """(times, visible quotes, market-fair line, market-fair-priced offers) at one point."""
    t, off = H.point_offers(data, point)
    vis = H.visible(data.quotes, t)
    fair = H.market_fair(vis, sig)
    return t, vis, fair, H.fair_offers(off, fair)


SIGNAL_COLS = ("strength", "side_pick")


def attach(neutral: pd.DataFrame, signal: pd.DataFrame, keys=("game_id", "market")) -> pd.DataFrame:
    """Market-fair offers with the rule's strength (and side_pick) merged on."""
    base = neutral.drop(columns=[c for c in SIGNAL_COLS if c in neutral])
    cols = [*keys, *[c for c in SIGNAL_COLS if c in signal]]
    out = base.merge(signal[cols], on=list(keys), how="left")
    out["strength"] = pd.to_numeric(out["strength"], errors="coerce")
    return out


def placebo_cands(neutral: pd.DataFrame, signal: pd.DataFrame, games: pd.DataFrame,
                  n: int = N_PLACEBO) -> list[pd.DataFrame]:
    """n re-priced candidate frames: the SIGNAL shuffled within date and market
    (seed = run number), the market-fair prices left exactly as they are."""
    sig_cols = ["game_id", "market", *[c for c in SIGNAL_COLS if c in signal]]
    out = []
    for r in range(n):
        sh = H.shuffle_within_date(signal[sig_cols], games, np.random.default_rng(r))
        out.append(attach(neutral, sh))
    return out


def rule_cells(data: H.Data, family: str, point: str, cand: pd.DataFrame, cuts,
               sides_by_market: dict, close=None, sig=None, placebo=None) -> list[dict]:
    """H.run_cells for a rule family, on the cell's own priced population.

    Section 6.5 (second amendment): bar 9's population is "the games its model
    or rule produced a number for". `cand` (attach) keeps every priced offer,
    so a (game, market) with no rule number on any row is left out here. A
    rule keyed by book (the soft-book outlier) numbers one book's row; every
    book's offer on that game stays, so the blind bets are taken at the best
    deciding offer on the game. The cell's bets cannot change (every cut asks
    strength >= k); only the population behind the real-side shares and blind
    bets does."""
    key = pd.MultiIndex.from_frame(cand[["game_id", "market"]])
    numbered = pd.MultiIndex.from_frame(cand.loc[cand["strength"].notna(), ["game_id", "market"]])
    pop = cand[key.isin(numbered)]
    return H.run_cells(data, family, point, pop, pop, cuts=cuts, sides_by_market=sides_by_market,
                       close=close, sig=sig, placebo=placebo, strength="strength")


def population(family: str, point: str, t: pd.DataFrame, cand: pd.DataFrame, data: H.Data,
               markets, side: str, cuts, axis_rule: str | None = None,
               signal: pd.DataFrame | None = None) -> list[dict]:
    """Coverage per (season, market, cut): games, games decided, games priced,
    games with a model number / signal, and bets the cell takes. Counts only."""
    rows = []
    t_season = t.merge(data.games[["game_id", "season"]], on="game_id")
    for s in sorted(data.games["season"].unique()):
        n_games = int((data.games["season"] == s).sum())
        n_t = int((t_season["season"] == s).sum())
        for m in markets:
            cm = cand[(cand["market"] == m) & (cand["season"] == s)]
            priced = cm[cm["book"].isin(H.BETTABLE) & (cm["price"] >= H.PRICE_FLOOR)]
            base = {"family": family, "point": point, "season": int(s), "market": m, "side": side,
                    "axis_rule": axis_rule, "games": n_games, "games_decided": n_t,
                    "games_priced": int(priced["game_id"].nunique()),
                    "games_with_model": int(cm.loc[cm["strength"].notna(), "game_id"].nunique())}
            if signal is not None and "first_to_T_min" in signal:
                sg = signal[(signal["market"] == m) & signal["game_id"].isin(cm["game_id"])]
                base["games_moved"] = int((sg["strength"] > 0).sum())
                base["first_to_T_min_median"] = float(sg["first_to_T_min"].median()) if len(sg) else np.nan
                base["n_books_first_median"] = float(sg["n_first"].median()) if len(sg) else np.nan
            for k, cut in enumerate(cuts):
                bets = H.choose(cm[cm["strength"] >= cut], -np.inf, sides=[side])
                rows.append({**base, "cut_index": k, "cut": cut,
                             "games_signal": int(cm.loc[cm["strength"] >= cut, "game_id"].nunique()),
                             "bets": int(len(bets))})
    return rows


# ── F3 ──────────────────────────────────────────────────────────────────────

def run_f3(data: H.Data, close, sig, n_placebo: int = N_PLACEBO) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, pop = [], []
    for point in F3_POINTS:
        t, _, _, neutral = point_frames(data, point, sig)
        signal = move_signal(data.quotes, t)
        cand = attach(neutral[neutral["market"].isin(F3_MARKETS)], signal)
        pl = placebo_cands(neutral[neutral["market"].isin(F3_MARKETS)], signal, data.games, n_placebo)
        rows += rule_cells(data, "F3", point, cand, F3_CUTS, {m: [F3_SIDE] for m in F3_MARKETS},
                           close=close, sig=sig, placebo=pl)
        pop += population("F3", point, t, cand, data, F3_MARKETS, F3_SIDE, F3_CUTS, signal=signal)
    cells = pd.DataFrame(rows)
    assert len(cells) == F3_CELLS, f"F3 emits {len(cells)} cells, section 6.3 lists {F3_CELLS}"
    return cells, pd.DataFrame(pop)


# ── controls: the signals ───────────────────────────────────────────────────

def favourite_sides(fair: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, fav, dog) from the market's own fair line at T."""
    f = fair[fair["market"].isin(["spreads", "h2h"])].copy()
    x = np.where(f["market"] == "spreads", f["mu"], f["p_home"] - 0.5)
    f["fav"] = np.where(x > 0, "home", np.where(x < 0, "away", None))
    f["dog"] = np.where(x > 0, "away", np.where(x < 0, "home", None))
    return f[["game_id", "market", "fav", "dog"]]


def team_streaks(games: pd.DataFrame) -> pd.DataFrame:
    """One row per (team, game): straight-up win and loss streaks AFTER that
    game, and the instant the result is known (tip + SETTLE_HOURS)."""
    g = games[["game_id", "season", "tip", "home_team", "away_team", "home_score", "away_score"]]
    hw = g["home_score"] > g["away_score"]
    t = pd.concat([pd.DataFrame({"team": g["home_team"], "season": g["season"], "tip": g["tip"],
                                 "game_id": g["game_id"], "win": hw}),
                   pd.DataFrame({"team": g["away_team"], "season": g["season"], "tip": g["tip"],
                                 "game_id": g["game_id"], "win": ~hw})], ignore_index=True)
    t = t.sort_values(["team", "season", "tip"]).reset_index(drop=True)
    key = [t["team"], t["season"]]
    w = t["win"].astype(int)
    t["win_streak"] = w.groupby([*key, (1 - w).groupby(key).cumsum()]).cumsum()
    t["loss_streak"] = (1 - w).groupby([*key, w.groupby(key).cumsum()]).cumsum()
    t["known_at"] = t["tip"] + pd.Timedelta(hours=SETTLE_HOURS)
    return t


def streaks_at(games: pd.DataFrame, times: pd.DataFrame) -> pd.DataFrame:
    """(game_id, home_win, home_loss, away_win, away_loss): each team's streak
    over its games FINAL by T (same season)."""
    st = team_streaks(games).sort_values("known_at")
    g = games[["game_id", "season", "home_team", "away_team"]].merge(times[["game_id", "T"]], on="game_id")
    out = g[["game_id"]].copy()
    for side in ("home", "away"):
        left = g.rename(columns={f"{side}_team": "team"})[["game_id", "team", "season", "T"]]
        left = left.sort_values("T")
        m = pd.merge_asof(left, st[["team", "season", "known_at", "win_streak", "loss_streak"]],
                          left_on="T", right_on="known_at", by=["team", "season"],
                          direction="backward", allow_exact_matches=True)
        m = m.set_index("game_id").reindex(out["game_id"])
        out[f"{side}_win"] = m["win_streak"].fillna(0).to_numpy()
        out[f"{side}_loss"] = m["loss_streak"].fillna(0).to_numpy()
    return out


def streak_signal(st: pd.DataFrame, kind: str, markets=("spreads", "h2h")) -> pd.DataFrame:
    """Against the team on the longer `kind` (win|loss) streak; a tie bets nothing."""
    h, a = st[f"home_{kind}"].to_numpy(float), st[f"away_{kind}"].to_numpy(float)
    pick = np.where(h > a, "away", np.where(a > h, "home", None))
    s = pd.DataFrame({"game_id": st["game_id"], "strength": np.where(pick != None, np.maximum(h, a), np.nan),  # noqa: E711
                      "side_pick": pick})
    return s.merge(pd.DataFrame({"market": list(markets)}), how="cross")


def big_home_dog_signal(cons_spread: pd.DataFrame, markets=("spreads", "h2h")) -> pd.DataFrame:
    """strength = the consensus home spread at T (home +7 -> 7.0)."""
    s = cons_spread[["game_id", "cons"]].rename(columns={"cons": "strength"})
    return s.merge(pd.DataFrame({"market": list(markets)}), how="cross")


def schedule_spots(sched: pd.DataFrame) -> pd.DataFrame:
    """The first search's three published spots (nba_game_model_lab.rule_sides),
    and the early-season window, per game -- all from the published schedule."""
    x = sched
    r1 = (x["home_b2b"] == 1) & (x["away_rest_days"] >= 1)
    alt = x["venue"].isin(ALTITUDE_VENUES) & (x["neutral"] == 0)
    r2 = alt & ((x["away_b2b"] == 1) | (x["away_is_3in4"] == 1))
    hl = (x["home_b2b"] == 1) & (x["home_travel_mi"] >= TRAVEL_MI)
    al = (x["away_b2b"] == 1) & (x["away_travel_mi"] >= TRAVEL_MI)
    r3 = hl ^ al
    return pd.DataFrame({"game_id": x["game_id"], "b2b_vs_rested": r1.astype(bool),
                         "altitude": r2.astype(bool), "long_travel_b2b": r3.astype(bool),
                         # against the tired team: the AWAY team tired -> bet HOME
                         "long_travel_bet": np.where(r3, np.where(al, "home", "away"), None),
                         "early_season": (x["days_since_open"] < EARLY_DAYS).to_numpy()})


def flag_signal(game_ids, flag, markets, side_pick=None) -> pd.DataFrame:
    s = pd.DataFrame({"game_id": np.asarray(game_ids), "strength": np.where(np.asarray(flag, bool), 1.0, 0.0)})
    if side_pick is not None:
        s["side_pick"] = side_pick
    return s.merge(pd.DataFrame({"market": list(markets)}), how="cross")


def outlier_signal(vis: pd.DataFrame, markets=("spreads", "totals")) -> pd.DataFrame:
    """Per (game, market, BOOK): how far that deciding book's number sits from
    the deciding-book consensus, and the side its number favours."""
    v = vis[vis["coherent"] & vis["book"].isin(H.BETTABLE) & vis["market"].isin(markets)].copy()
    v["cons"] = v.groupby(["game_id", "market"])["line"].transform("median")
    dev = (v["line"] - v["cons"]).to_numpy(float)
    sp = np.where(dev > 0, "home", np.where(dev < 0, "away", None))
    tt = np.where(dev > 0, "under", np.where(dev < 0, "over", None))
    v["side_pick"] = np.where(v["market"] == "spreads", sp, tt)
    v["strength"] = np.where(dev != 0, np.abs(dev), np.nan)
    return v[["game_id", "market", "book", "strength", "side_pick"]]


def load_splits(cache: Path) -> pd.DataFrame | None:
    """nba_public_splits from the research cache, or None while it is not there."""
    p = cache / "nba_public_splits.parquet"
    return pd.read_parquet(p) if p.exists() else None


def public_signal(splits: pd.DataFrame | None, times: pd.DataFrame,
                  markets=("h2h", "spreads", "totals")) -> pd.DataFrame:
    """Against the side holding the larger share of tickets, from the newest
    PRE-TIP poll observed at or before T.

    Two exclusions (docs/nba_models_2026.md section 6, third amendment):
      * every archive row (capture_kind 'archive_undated'): the archive is the
        CLOSING split, known only after tip, so it is never usable at a pre-tip
        decision. Every v1 row is an archive row (the ingestor polls v2 only),
        so this also removes every v1 row, whatever a later flag says of it.
      * every row on a slate the source serves reversed home-for-away
        (SPLITS_REVERSED_DATES, by the row's own game_date), whatever its kind."""
    cols = ["game_id", "market", "strength", "side_pick"]
    if splits is None or splits.empty:
        return pd.DataFrame(columns=cols)
    if "game_date" not in splits:
        raise ValueError("nba_public_splits rows need game_date to drop the reversed slate(s) "
                         f"{SPLITS_REVERSED_DATES}")
    reversed_slate = splits["game_date"].astype(str).str[:10].isin(SPLITS_REVERSED_DATES)
    s = splits[(splits["capture_kind"] == SPLITS_POLL) & ~reversed_slate
               & splits["tickets_pct"].notna()
               & splits["game_id"].notna() & splits["market"].isin(markets)].copy()
    s["observed_at"] = pd.to_datetime(s["observed_at"], utc=True)
    s = s.merge(times[["game_id", "T"]], on="game_id")
    s = s[s["observed_at"] <= s["T"]]
    s["_v2"] = (s["endpoint"] == "v2").astype(int)
    s = s.sort_values(["game_id", "market", "side", "observed_at", "_v2"]).drop_duplicates(
        ["game_id", "market", "side"], keep="last")
    s["tickets_pct"] = s["tickets_pct"].astype(float)
    gm = s.groupby(["game_id", "market"])["tickets_pct"]
    s["_top"] = s["tickets_pct"].eq(gm.transform("max"))
    s["_n_top"] = s.groupby(["game_id", "market"])["_top"].transform("sum")
    top = s[s["_top"] & (s["_n_top"] == 1)]                 # an even split fades nothing
    return pd.DataFrame({"game_id": top["game_id"], "market": top["market"],
                         "strength": top["tickets_pct"],
                         "side_pick": top["side"].map(OPPOSITE)}).reset_index(drop=True)


# ── controls: the cells ─────────────────────────────────────────────────────

def control_specs(data: H.Data, t, vis, fair, sched, splits) -> list[dict]:
    """Every control cell group: family, axis_rule, markets, side, cuts, signal."""
    specs = []
    gid = data.games["game_id"]
    # blind sides: strength 0 everywhere, cut 0
    zero = pd.DataFrame({"game_id": gid}).merge(
        pd.DataFrame({"market": ["spreads", "h2h", "totals"]}), how="cross").assign(strength=0.0)
    specs.append(dict(family="control_blind", axis_rule="blind", side_by_market={
        "spreads": ["home", "away"], "h2h": ["home", "away"], "totals": ["over", "under"]},
        cuts=(0.0,), signal=zero, placebo=False))
    fs = favourite_sides(fair)
    for side, col in (("favourite", "fav"), ("underdog", "dog")):
        specs.append(dict(family="control_blind", axis_rule="blind", side_by_market={
            "spreads": [side], "h2h": [side]}, cuts=(0.0,),
            signal=fs.assign(strength=0.0, side_pick=fs[col])[["game_id", "market", "strength", "side_pick"]],
            placebo=False))
    st = streaks_at(data.games, t)
    for kind in ("win", "loss"):
        specs.append(dict(family="control_streak", axis_rule=kind, side_by_market={
            "spreads": ["against"], "h2h": ["against"]}, cuts=STREAK_CUTS,
            signal=streak_signal(st, kind), placebo=True))
    cs = consensus(data.quotes, t[["game_id", "T"]].assign(market="spreads"))
    specs.append(dict(family="control_big_home_dog", axis_rule="home_plus_7", side_by_market={
        "spreads": ["home"], "h2h": ["home"]}, cuts=BIG_DOG_CUTS, signal=big_home_dog_signal(cs),
        placebo=True))
    sp = schedule_spots(sched[sched["game_id"].isin(gid)])
    specs.append(dict(family="control_early_under", axis_rule="first_21_days", side_by_market={
        "totals": ["under"]}, cuts=SPOT_CUTS,
        signal=flag_signal(sp["game_id"], sp["early_season"], ["totals"]),
        placebo=False))       # every game on a date shares the flag: a within-date shuffle is the cell
    specs.append(dict(family="control_spot_b2b_vs_rested", axis_rule="R1", side_by_market={
        "spreads": ["away"], "h2h": ["away"]}, cuts=SPOT_CUTS,
        signal=flag_signal(sp["game_id"], sp["b2b_vs_rested"], ["spreads", "h2h"]), placebo=True))
    specs.append(dict(family="control_spot_altitude", axis_rule="R2", side_by_market={
        "spreads": ["home"], "h2h": ["home"]}, cuts=SPOT_CUTS,
        signal=flag_signal(sp["game_id"], sp["altitude"], ["spreads", "h2h"]), placebo=True))
    specs.append(dict(family="control_spot_long_travel_b2b", axis_rule="R3", side_by_market={
        "spreads": ["against_tired"], "h2h": ["against_tired"]}, cuts=SPOT_CUTS,
        signal=flag_signal(sp["game_id"], sp["long_travel_b2b"], ["spreads", "h2h"],
                           side_pick=sp["long_travel_bet"].to_numpy()), placebo=True))
    specs.append(dict(family="control_soft_outlier", axis_rule="book_vs_consensus", side_by_market={
        "spreads": ["outlier_book"], "totals": ["outlier_book"]}, cuts=OUTLIER_CUTS,
        signal=outlier_signal(vis), placebo=False, keys=("game_id", "market", "book")))
    specs.append(dict(family="control_public_fade", axis_rule="tickets", side_by_market={
        "h2h": ["fade_public"], "spreads": ["fade_public"], "totals": ["fade_public"]},
        cuts=PUBLIC_CUTS, signal=public_signal(splits, t), placebo=True))
    return specs


def run_controls(data: H.Data, close, sig, sched: pd.DataFrame, splits,
                 n_placebo: int = N_PLACEBO) -> tuple[pd.DataFrame, pd.DataFrame]:
    t, vis, fair, neutral = point_frames(data, CONTROL_POINT, sig)
    rows, pop = [], []
    for sp in control_specs(data, t, vis, fair, sched, splits):
        markets = list(sp["side_by_market"])
        nm = neutral[neutral["market"].isin(markets)]
        keys = sp.get("keys", ("game_id", "market"))
        cand = attach(nm, sp["signal"], keys=keys)
        pl = placebo_cands(nm, sp["signal"], data.games, n_placebo) if sp["placebo"] else None
        r = rule_cells(data, sp["family"], CONTROL_POINT, cand, sp["cuts"], sp["side_by_market"],
                       close=close, sig=sig, placebo=pl)
        rows += [{**x, "axis_rule": sp["axis_rule"]} for x in r]
        for m, sides in sp["side_by_market"].items():
            for side in sides:
                pop += population(sp["family"], CONTROL_POINT, t, cand, data, [m], side,
                                  sp["cuts"], axis_rule=sp["axis_rule"])
    cells = pd.DataFrame(rows)
    assert len(cells) == CONTROL_CELLS, f"controls emit {len(cells)} cells, expected {CONTROL_CELLS}"
    # the verdict drops families named control_* (section 6.5: never judged, not in m)
    assert cells["family"].str.startswith(CONTROL_PREFIX).all(), sorted(set(cells["family"]))
    return cells, pd.DataFrame(pop)


# ── synthetic checks run before any real cell ───────────────────────────────

def synthetic_checks() -> None:
    H.check()
    got = list(fade_side(np.array(["spreads"] * 3 + ["totals"] * 3),
                         np.array([-1.0, 1.0, 0.0, 1.0, -1.0, 0.0])))
    assert got == ["away", "home", None, "under", "over", None], got
    assert len(F3_MARKETS) * len(F3_POINTS) * len(F3_CUTS) == F3_CELLS
    n_ctl = (6 + 2 + 2) + 2 * 2 * len(STREAK_CUTS) + 2 * len(BIG_DOG_CUTS) + 1 + 3 * 2 \
        + 2 * len(OUTLIER_CUTS) + 3 * len(PUBLIC_CUTS)
    assert n_ctl == CONTROL_CELLS, n_ctl
    print("synthetic checks pass")


# ── main ────────────────────────────────────────────────────────────────────

def schedule_features(cache: Path) -> pd.DataFrame:
    from features.nba_schedule_features import game_schedule_features
    return game_schedule_features(pd.read_parquet(cache / "nba_schedule.parquet"))


def load_data(cache: Path, full: bool) -> H.Data:
    """The seasons a run grades, each named as required: H.load refuses a cache
    that prices one of them on fewer than 90% of its games, or in which more
    than 5% of rows match no purchase record (a stale ledger)."""
    seasons = FULL_SEASONS if full else SMOKE_SEASONS
    return H.load(cache, seasons=seasons, require_seasons=seasons)


def market_pricing(data: H.Data) -> tuple[pd.DataFrame, dict]:
    """(Pinnacle's close, the market's pricing model): the empirical
    distribution of results around Pinnacle's close on earlier seasons
    (H.close_dist), never a bell curve."""
    close = H.pinnacle_close(data)
    return close, H.close_dist(close, data.games)


def write_cells(rows, path: Path) -> None:
    """The cell table as parquet, with placebo_rois typed list<double>. Left to
    pandas, a column whose lists are all NaN or all empty (a control with no
    placebo) is stored as list<null>, which reads back as None."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    df = pd.DataFrame(rows)
    t = pa.Table.from_pandas(df.drop(columns="placebo_rois"), preserve_index=False)
    pl = pa.array([[float(x) for x in v] for v in df["placebo_rois"]],
                  type=pa.list_(pa.float64()), from_pandas=False)
    pq.write_table(t.append_column("placebo_rois", pl), path)


def refuse_full_without_go() -> None:
    if os.environ.get("NBA_GAME2_GO") != "1":
        raise SystemExit("--full refuses to run: set NBA_GAME2_GO=1 (the owner runs it after the "
                         "price data is refreshed).")


def coverage_text(pop: pd.DataFrame) -> str:
    """Counts only -- never a return."""
    if pop.empty:
        return "(no coverage rows)"
    keys = ["family", "point", "season", "market", "side", "axis_rule"]
    pop = pop.assign(axis_rule=pop["axis_rule"].fillna("-"))
    first = pop[pop["cut_index"] == 0].groupby(keys, dropna=False)[
        ["games", "games_decided", "games_priced", "games_with_model"]].first()
    bets = pop.pivot_table(index=keys, columns="cut", values="bets", aggfunc="first", dropna=False)
    bets.columns = [f"bets@{c:g}" for c in bets.columns]
    return first.join(bets).to_string()


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true", help="2020-21 only, plus synthetic checks")
    mode.add_argument("--full", action="store_true", help="every season (needs NBA_GAME2_GO=1)")
    ap.add_argument("--cache", type=Path, default=H.CACHE)
    ap.add_argument("--results", type=Path, default=RESULTS)
    # a smoke-run shortcut only; --full refuses it (placebo_runs)
    ap.add_argument("--placebo", type=int, default=None, help=argparse.SUPPRESS)
    return ap.parse_args(argv)


def placebo_runs(a: argparse.Namespace) -> int:
    """How many placebo runs a cell carries. Bar 10 (section 6.4, read as the
    2026-10-17 amendment "how each bar is read" fixes it) is the 95th
    percentile of 20 shuffles, so --full takes no override at all, not even
    --placebo 20; --smoke may ask for fewer."""
    if a.full and a.placebo is not None:
        raise SystemExit(f"--full runs exactly {N_PLACEBO} placebo runs (docs/nba_models_2026.md "
                         "section 6.4, bar 10); --placebo is for --smoke only.")
    return N_PLACEBO if a.placebo is None else int(a.placebo)


def main(argv=None) -> None:
    a = parse_args(argv)
    n_placebo = placebo_runs(a)
    if a.full:
        refuse_full_without_go()
    synthetic_checks()
    if not (a.cache / "nba_fetch_ledger.parquet").exists():
        raise SystemExit(f"{a.cache} has no nba_fetch_ledger.parquet: refresh the research cache "
                         "(python -m scripts.nba_research_cache --only lines) first.")
    out = a.results / "smoke_move" if a.smoke else a.results
    out.mkdir(parents=True, exist_ok=True)
    data = load_data(a.cache, full=a.full)
    print("load:", data.notes)
    close, sig = market_pricing(data)
    print("market pricing:", ", ".join(repr(sig[k]) for k in sorted(sig)))
    sched = schedule_features(a.cache)
    splits = load_splits(a.cache)
    print("public splits:", "absent (control emitted with no bets)" if splits is None else f"{len(splits):,} rows")
    f3, f3_pop = run_f3(data, close, sig, n_placebo)
    write_cells(f3, out / "cells_F3.parquet")
    f3_pop.to_parquet(out / "population_F3.parquet")
    ctl, ctl_pop = run_controls(data, close, sig, sched, splits, n_placebo)
    write_cells(ctl, out / "cells_controls.parquet")
    ctl_pop.to_parquet(out / "population_controls.parquet")
    print(f"wrote {len(f3)} F3 cells and {len(ctl)} control cells to {out}")
    pd.set_option("display.width", 250)
    print("\nF3 coverage (counts only)\n" + coverage_text(f3_pop))
    print("\ncontrol coverage (counts only)\n" + coverage_text(ctl_pop))


if __name__ == "__main__":
    main()

"""F6b: player points props summed per team, against the full-game total and spread.

docs/nba_models_2026.md section 6.3, family F6b, 12 cells: spread and total x
2 sides x decision point D x gap >= 2, 4, 6 points. Seasons 2023-24 on (labels
2024-2026, the seasons with props); cuts are chosen on 2024 and 2025
(choose_seasons=(2024, 2025), section 6.4's amendment), confirmed on 2026.
This lab BUILDS the cells; scripts/nba_game2_verdict.py judges them.

Every price, choice and grade goes through scripts/nba_game_harness (H): its
loaders, decision points, H.visible / H.offers, H.market_fair / H.fair_offers,
H.choose, H.grade and H.run_cells. Nothing here prices, chooses or grades.

THE MODEL NUMBER, PER GAME AT DECISION POINT D

  T          the game's per-game prop purchase, dated by the feed's own
             snapshot_at (fetch_at = snapshot_at), kept only when it falls
             45-75 minutes before tip: H.per_event_times(props, "D"). The
             full-game lines are what H.visible shows at the same T.
  PRICED     a player with a coherent main-line points quote (market
             player_points, implied sum 1.00-1.15 as H.COHERENT) visible at T
             (H.visible, the player keyed into `market`) from Pinnacle or a
             deciding book (H.BETTABLE). Bovada alone does not price a player.
  MEAN       each quote's no-vig over probability p (multiplicative, as
             H.market_fair and H.pinnacle_close) at that book's own line L is
             turned into the player's mean through the EMPIRICAL distribution
             of points around a player's own average:  mu = L - Q_e(1 - p),
             Q_e the quantile of the residuals e of the K_NEAREST = 4,000
             earlier-season player-games whose average was nearest L (K is a
             smoothing width), each residual spread over +-0.5 point (the
             continuity correction: P(points + U > k + .5) = P(points >= k + 1)
             exactly, and the quantile no longer snaps between whole numbers:
             without it the even-money offset at a 10.5 line moved from +0.66
             to +1.36 between two fit windows). p = 0.5 puts mu at L minus the
             residuals' median
             (the right skew the data shows); p above 0.5 puts mu above L. A
             whole-number line (none is stored: every points line held is .5)
             is read by the same continuity formula. The player's mean is
             Pinnacle's when it quotes coherently, else the median over the
             deciding books -- H.market_fair's rule for game lines, carried to
             the player. Quotes are combined per player id, so two spellings
             of one player across books are one player, counted once.
  SHAPE      the residuals e = points - m, m = the player's whole season
             average (not leave-one-out: that average falls after a big game,
             so a narrow band of it selects games by their score), over games
             PLAYED (a prop is void if he
             does not play) by player-seasons with >= 20 games played, on
             seasons strictly before the graded season S:
               2021 (smoke)  <- 2019-2020
               2024          <- 2019-2023
               2025          <- 2019-2024
               2026          <- 2019-2025
             WHY NOT A NEGATIVE BINOMIAL (measured 2026-10-17 on box scores
             2019-2023, no price read): around the season average, a single-
             dispersion NB2 (alpha 0.33 by maximum likelihood) gives 20-30 point
             scorers a standard deviation of 13-19 points (observed 7.7-9.5)
             and puts the mean 2.0-3.4 points above an even-money line; NB1
             (variance 4.1 x mean, the best of the three by likelihood) still
             puts it 1.2 above; Poisson's spread is far too narrow (sd 4.7 at
             22 points, observed 7.7). Observed mean minus median: +0.76 (5-10
             points), +0.53 (10-15), +0.25 (15-20), +0.03 (20-25), +0.31
             (25-30), -0.03 (30-40). Summed over ~14 priced players a family's
             skew error moves the implied total by 15-45 points, so the shape
             is read from the data instead of assumed.
             KNOWN LIMITATION, not tuned: the spread of points around a season
             average is wider than around the market's own expectation, so
             mu moves slightly too far from L at prices away from even money.
  ROSTER     for (game, team) at T: everyone in the box (played, did not play,
             or inactive) of the team's most recent game THIS SEASON that was
             final before T (tip at least FINAL_LAG = 4 hours before T), whose
             latest box appearance anywhere before that cutoff is with this
             team; plus everyone on the team's injury report as of T. The
             report wins: a player it lists for one team is not on the other.
  INJURIES   the team's latest SUBMITTED report for the game with printed
             time + 30 minutes <= T (section 6.1: a report is known 30
             minutes after its printed time), read as a whole report
             (models.nba_props.injury_asof). Report rows with no NBA id are
             matched by name within the team's roster, or dropped.
  BENCH      a roster player with no price, not Out, contributes his points
             per AVAILABLE team game over the team's last <= 10 games this
             season final before T: a game he played counts his points, a
             "DNP - Coach's Decision" counts 0, a game missed injured, resting,
             inactive or not with the team is skipped. No available game: 0.
             Doubtful and Questionable players without a price contribute
             (the rule names Out only).
  OUT        a priced player Out on the report as of T contributes 0 (the book
             would void his prop); counted in the population file.
  NAMES      a price finds its player by name within the two rosters of that
             game (models.nba_props.match_names): letters-only key, Jr/II
             stripped, nicknames, tokens in any order, initial + surname. A
             name two roster players share is REFUSED, never split (bar 13:
             two players sharing a name never share a price). If any priced
             name in a game is refused or unresolved, the game gets NO model
             number (an incomplete sum is a phantom gap); collisions are
             written out.
  REFUSED    also: a team with no final game this season before T (each team's
             opener), or a team with no priced player left.
  IMPLIED    team points = sum of priced means + bench; implied total = home +
             away; implied margin = home - away (the side-A quantity of the
             harness: spreads are the HOME number).
  GAP        per offer, in the bet side's favour against that offer's number:
               spread home: margin + spread_home      away: -(margin + spread_home)
               total over:  total - line              under: line - total
             A cell bets its side when gap >= g (g = 2, 4, 6), at the best
             offer under the market's own fair line among the offers clearing
             g (run_cells strength="gap").

POPULATION  the games this rule produced a model number for (refused games are
            not in it): the cell's own priced population, over which the
            harness takes bar 9's blind bet on each real side.
SIDES       every offer keeps its real side (home / away / over / under); no
            game is oriented, so the harness grades, shares and blinds by the
            real side.
GATE        the harness's 95% gate at D reads THIS lab's decision times (the
            per-game prop purchases, H.per_event_times), passed as times=.
MARKET      the market's fair line, the blind bet and closing value are
            priced through H.close_dist: the empirical spread of results
            around Pinnacle's close on seasons BEFORE the graded one. A prop
            season priced from its own results is refused (check_close_prior).
PLACEBO     20 runs: the model numbers (implied margin, implied total) shuffled
            between games on the same date in the same market
            (H.shuffle_within_date, rng seed = run number 0-19), the gap
            recomputed against each game's own offers, graded at the same cuts.
CLOSE       H.pinnacle_close / H.close_dist (reported only at D).

NO LOOK-AHEAD: prop quotes at or before T and within 60 minutes (H.visible);
box scores only from games whose tip is >= 4 hours before T; the injury report
only when printed >= 30 minutes before T; the schedule from the schedule;
the shape only from earlier seasons.

    PYTHONPATH=. python -m scripts.nba_game2_props --smoke
    NBA_GAME2_GO=1 PYTHONPATH=. python -m scripts.nba_game2_props --full
    PYTHONPATH=. python -m scripts.nba_game2_props --quality      # price-free, 2022-2025
    PYTHONPATH=. python -m scripts.nba_game2_props --names-check  # price-free, 2024-2025

Writes <results>/cells_F6b.parquet, population_F6b.parquet and
names_F6b.parquet; <results> is $NBA_GAME2_RESULTS (default
%TEMP%/nba_game_edge/results); --smoke writes to <results>/smoke. Nothing is
printed but counts and coverage.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402
from models.nba_props import base_key, injury_asof, match_names  # noqa: E402

FAMILY = "F6b"
POINT = "D"
CUTS = (2.0, 4.0, 6.0)
SIDES = {"spreads": ["home", "away"], "totals": ["over", "under"]}
CHOOSE_SEASONS = (2024, 2025)
PROP_SEASONS = (2024, 2025, 2026)     # the seasons with props: --full grades and fits shapes for these
# --full loads every PRICED season through 2025-26: the market's pricing for
# 2024 is fit on 2021-2023's closes. Named, not "every season", so 2026-27
# (untouched, section 6.5) never enters a graded run once its games are scored.
FULL_LOAD_SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
SMOKE_SEASONS = (2021,)
EXPECTED_CELLS = 12
PROP_MARKET = "player_points"
KEY_PREFIX = "pp|"                    # the player rides in H.visible's `market` column
FINAL_LAG = pd.Timedelta(hours=4)     # a box game is known at T only if it tipped 4 h before
REPORT_LAG = pd.Timedelta(minutes=30)  # section 6.1: a report is known 30 min after its stamp
WINDOW = 10                           # the team's last games this season for the bench rate
FIT_MIN_GAMES = 20                    # player-seasons in the shape
K_NEAREST = 4000                      # player-games whose residuals give the shape at one line
SHAPE_LINES = (10.5, 20.5, 30.5)      # the even-money offset reported per graded season
FIRST_BOX_SEASON = 2019
N_PLACEBO = 20
QUALITY_SEASONS = (2022, 2023, 2024, 2025)   # never 2026
NAMES_SEASONS = (2024, 2025)                 # never 2026
RESULTS = Path(os.environ.get("NBA_GAME2_RESULTS",
                              str(Path(os.environ.get("TEMP", "/tmp")) / "nba_game_edge" / "results")))


# ── props, dated by their own stamp ─────────────────────────────────────────

def props_frame(raw: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Points quotes in the harness's per-event shape: fetch_at = snapshot_at,
    pre-tip only, the player keyed into `market` so H.visible keeps one quote
    per (game, player, book)."""
    p = raw[(raw["market"] == PROP_MARKET) & (raw["snapshot_type"].astype(str) != "in_play")].copy()
    p = p.drop(columns=[c for c in ("game_date", "season", "tip") if c in p])
    p["snapshot_at"] = pd.to_datetime(p["snapshot_at"], utc=True, format="mixed")
    p = p.merge(games[["game_id", "season", "game_date", "tip"]], on="game_id")
    p = p[(p["snapshot_at"] < p["tip"]) & p["player_name"].notna() & p["line"].notna()
          & p["over_price"].notna() & p["under_price"].notna()]
    p = p.rename(columns={"bookmaker": "book"})
    p["fetch_at"] = p["snapshot_at"]
    p["price_a"], p["price_b"] = p["over_price"].astype(float), p["under_price"].astype(float)
    s = H.imp(p["price_a"]) + H.imp(p["price_b"])
    p["coherent"] = (s >= H.COHERENT[0]) & (s <= H.COHERENT[1])
    p["market"] = KEY_PREFIX + p["player_name"].astype(str)
    return p[["game_id", "season", "game_date", "tip", "market", "player_name", "book",
              "snapshot_at", "fetch_at", "line", "price_a", "price_b", "coherent"]].reset_index(drop=True)


def load_props(games: pd.DataFrame, cache: Path = H.CACHE) -> pd.DataFrame:
    raw = pd.read_parquet(cache / "nba_props.parquet",
                          columns=["game_id", "player_name", "market", "bookmaker", "snapshot_type",
                                   "snapshot_at", "line", "over_price", "under_price"])
    raw = raw[raw["game_id"].isin(games["game_id"])]
    return props_frame(raw, games)


# ── the shape: residuals from earlier seasons, the mean from a price ────────

@dataclass
class Shape:
    """Residuals of points around a player's own season average, sorted by
    that average. Fit on `seasons`, used for a later season."""
    m: np.ndarray
    e: np.ndarray
    seasons: tuple = ()


def fit_shape(app: pd.DataFrame, season: int) -> Shape:
    """The residuals of every game played, seasons [FIRST_BOX_SEASON, season),
    player-seasons with >= FIT_MIN_GAMES games played."""
    x = app[(app["season"] < season) & (app["season"] >= FIRST_BOX_SEASON)
            & app["played"] & app["points"].notna()]
    g = x.groupby(["player_id", "season"])["points"]
    n, tot = g.transform("size"), g.transform("sum")
    keep = n >= FIT_MIN_GAMES
    y = x.loc[keep, "points"].to_numpy(float)
    # the WHOLE player-season average, not the average without this game: a
    # leave-one-out average is lower after a big game, so a narrow band of them
    # selects big games for players just above the line and small ones just
    # below (measured: the even-money offset at 10.5 drifted +0.78 -> +1.49 as
    # seasons were added). The whole average selects player-seasons, not games.
    m = (tot[keep] / n[keep]).to_numpy(float)
    if len(y) == 0:
        raise ValueError(f"no box seasons before {season} to fit the shape on")
    o = np.argsort(m, kind="stable")
    return Shape(m=m[o], e=(y - m)[o], seasons=tuple(sorted(int(v) for v in x.loc[keep, "season"].unique())))


def nearest_residuals(shape: Shape, line: float, k: int = K_NEAREST) -> np.ndarray:
    """The residuals of the k player-games whose average is nearest `line`."""
    n = len(shape.m)
    if n <= k:
        return shape.e
    i = int(np.searchsorted(shape.m, line))
    lo, hi = max(0, i - k), min(n, i + k)
    d = np.abs(shape.m[lo:hi] - line)
    take = np.argpartition(d, k - 1)[:k] if hi - lo > k else np.arange(hi - lo)
    return shape.e[lo:hi][take]


GRID = np.arange(-60.0, 90.0 + 1e-9, 0.005)


def smooth_cdf(e: np.ndarray, x: np.ndarray = GRID) -> np.ndarray:
    """CDF of e + U(-0.5, 0.5): the continuity correction. Points are whole
    numbers, so P(points + U > k + 0.5) = P(points >= k + 1) exactly, and the
    residual distribution becomes continuous (no lattice for a quantile to snap to)."""
    es = np.sort(np.asarray(e, float))
    cs = np.concatenate([[0.0], np.cumsum(es)])
    a = np.searchsorted(es, x - 0.5, side="right")       # wholly below the kernel
    b = np.searchsorted(es, x + 0.5, side="left")        # inside it: partial mass
    mid = (b - a) * (x + 0.5) - (cs[b] - cs[a])
    return (a + mid) / len(es)


def mean_from_over(line, p_over, shape: Shape, k: int = K_NEAREST) -> np.ndarray:
    """mu = L - Q(1 - p): the mean at which P(points > L) = p under the shape,
    Q the quantile of the continuity-corrected residuals nearest L."""
    line = np.asarray(line, float)
    p = np.clip(np.asarray(p_over, float), 1e-4, 1 - 1e-4)
    out = np.full(line.shape, np.nan)
    for L in np.unique(line[np.isfinite(line)]):
        sel = line == L
        F = smooth_cdf(nearest_residuals(shape, float(L), k))
        lo, hi = np.searchsorted(F, 0.0, side="right") - 1, np.searchsorted(F, 1.0, side="left")
        Fi, Gi = F[max(lo, 0):hi + 1], GRID[max(lo, 0):hi + 1]
        out[sel] = L - np.interp(1.0 - p[sel], Fi, Gi)
    return out


def quote_means(vis: pd.DataFrame, shape_by_season: dict) -> pd.DataFrame:
    """One mean per visible coherent quote at Pinnacle or a deciding book."""
    v = vis[vis["coherent"] & vis["book"].isin((H.SHARP, *H.BETTABLE))].copy()
    if v.empty:
        return v.assign(p_over=[], mu=[])
    ia, ib = H.imp(v["price_a"]), H.imp(v["price_b"])
    v["p_over"] = ia / (ia + ib)
    v["mu"] = np.nan
    for s, idx in v.groupby("season").groups.items():
        x = v.loc[idx]
        v.loc[idx, "mu"] = mean_from_over(x["line"].to_numpy(), x["p_over"].to_numpy(), shape_by_season[int(s)])
    return v


def player_mean(qm: pd.DataFrame) -> pd.DataFrame:
    """Per (game, player_id): Pinnacle's mean when it quotes, else the median over
    the deciding books (H.market_fair's rule)."""
    if qm.empty:
        return pd.DataFrame(columns=["game_id", "player_id", "mu", "ref", "n_books"])
    sharp = qm[qm["book"] == H.SHARP].groupby(["game_id", "player_id"])["mu"].median()
    rest = qm[qm["book"].isin(H.BETTABLE)].groupby(["game_id", "player_id"])["mu"].agg(["median", "size"])
    out = rest.rename(columns={"median": "mu", "size": "n_books"}).assign(ref="consensus")
    out = out.reindex(out.index.union(sharp.index))
    has = out.index.isin(sharp.index)
    out.loc[has, "mu"] = sharp.reindex(out.index[has]).to_numpy()
    out.loc[has, "ref"] = "pinnacle"
    out["n_books"] = out["n_books"].fillna(0).astype(int)
    return out.reset_index()


# ── the box: who appeared, who was available, as of a cutoff ───────────────

def appearances(adv: pd.DataFrame, log: pd.DataFrame, ina: pd.DataFrame,
                games_all: pd.DataFrame) -> pd.DataFrame:
    """One row per (regular-season game, rostered player): played, did not play or
    inactive; `pts` = points if played, 0 for a coach's-decision DNP, NaN when
    he was not available (injury, rest, not with team, inactive)."""
    a = adv[adv["game_type"] == "regular"][["game_id", "player_id", "player_name", "team", "season",
                                            "played", "did_not_play_reason"]].copy()
    a = a.merge(log[["game_id", "player_id", "points"]].drop_duplicates(["game_id", "player_id"]),
                on=["game_id", "player_id"], how="left")
    i = ina[ina["game_type"] == "regular"][["game_id", "player_id", "player_name", "team", "season"]]
    i = i.dropna(subset=["player_id"])
    seen = pd.MultiIndex.from_frame(a[["game_id", "player_id"]])
    i = i[~pd.MultiIndex.from_frame(i[["game_id", "player_id"]]).isin(seen)]
    i = i.assign(played=False, did_not_play_reason="INACTIVE", points=np.nan)
    b = pd.concat([a, i], ignore_index=True)
    b["played"] = b["played"].fillna(False).astype(bool)
    b = b.merge(games_all[["game_id", "tip"]], on="game_id")
    coach = b["did_not_play_reason"].astype(str).str.contains("Coach", case=False, na=False)
    b["avail"] = b["played"] | (~b["played"] & coach)
    b["pts"] = np.where(b["played"], b["points"], np.where(b["avail"], 0.0, np.nan))
    b["season"] = b["season"].astype(int)
    return b.sort_values(["tip", "game_id"]).reset_index(drop=True)


def team_games(games_all: pd.DataFrame) -> pd.DataFrame:
    h = games_all[["game_id", "season", "tip", "home_team"]].rename(columns={"home_team": "team"})
    a = games_all[["game_id", "season", "tip", "away_team"]].rename(columns={"away_team": "team"})
    t = pd.concat([h, a], ignore_index=True).dropna(subset=["team"])
    t = t.sort_values(["team", "tip", "game_id"]).reset_index(drop=True)
    t["k"] = t.groupby("team").cumcount()
    return t


def targets_for(times: pd.DataFrame, games_all: pd.DataFrame) -> pd.DataFrame:
    """Two rows per decided game: (game_id, team, is_home, season, T, cutoff)."""
    g = times[["game_id", "T"]].merge(games_all[["game_id", "season", "home_team", "away_team"]],
                                      on="game_id")
    h = g.rename(columns={"home_team": "team"}).drop(columns="away_team").assign(is_home=True)
    a = g.rename(columns={"away_team": "team"}).drop(columns="home_team").assign(is_home=False)
    t = pd.concat([h, a], ignore_index=True)
    t["cutoff"] = t["T"] - FINAL_LAG
    return t.reset_index(drop=True)


def window_games(targets: pd.DataFrame, tg: pd.DataFrame) -> pd.DataFrame:
    """(game_id, team, prev_game_id, j): the team's last <= WINDOW games this season
    whose tip is at or before the cutoff; j = 0 is the most recent."""
    if targets.empty:
        return pd.DataFrame(columns=["game_id", "team", "prev_game_id", "j"])
    left = targets[["game_id", "team", "season", "cutoff"]].sort_values("cutoff")
    right = tg[["team", "tip", "k"]].sort_values("tip")
    m = pd.merge_asof(left, right, left_on="cutoff", right_on="tip", by="team",
                      direction="backward", allow_exact_matches=True)
    m = m.dropna(subset=["k"])
    m["k"] = m["k"].astype(int)
    w = m.loc[m.index.repeat(WINDOW)].copy()
    w["j"] = np.tile(np.arange(WINDOW), len(m))
    w["k"] = w["k"] - w["j"]
    w = w.merge(tg[["team", "k", "game_id", "season"]].rename(
        columns={"game_id": "prev_game_id", "season": "prev_season"}), on=["team", "k"])
    w = w[w["prev_season"] == w["season"]]
    return w[["game_id", "team", "prev_game_id", "j"]].reset_index(drop=True)


def latest_team(players: pd.DataFrame, app: pd.DataFrame) -> pd.Series:
    """Each (player_id, cutoff)'s team in his latest box appearance at or before the cutoff."""
    if players.empty:
        return pd.Series([], dtype=object)
    left = players[["player_id", "cutoff"]].reset_index().sort_values("cutoff")
    right = app[["player_id", "tip", "team"]].rename(columns={"team": "t_latest"}).sort_values("tip")
    m = pd.merge_asof(left, right, left_on="cutoff", right_on="tip", by="player_id",
                      direction="backward", allow_exact_matches=True)
    return m.set_index("index")["t_latest"].reindex(players.index)


def report_asof(inj: pd.DataFrame, times: pd.DataFrame) -> pd.DataFrame:
    """The latest submitted report per (game, team) printed >= 30 minutes before T."""
    if times.empty or inj is None or inj.empty:
        return pd.DataFrame(columns=["game_id", "team", "player_id", "player_name", "status"])
    dec = times[["game_id"]].assign(decision_ts=times["T"] - REPORT_LAG)
    i = inj.copy()
    i["report_ts"] = pd.to_datetime(i["report_ts"], utc=True)
    return injury_asof(i, dec)


def rosters(times: pd.DataFrame, games_all: pd.DataFrame, app: pd.DataFrame,
            inj: pd.DataFrame | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(roster, team_info). roster: game_id, team, player_id, player_name, status,
    proj, n_avail. team_info: game_id, team, is_home, has_final (a final game
    this season before T)."""
    tgt = targets_for(times, games_all)
    tg = team_games(games_all)
    win = window_games(tgt, tg)
    info = tgt[["game_id", "team", "is_home", "season", "T", "cutoff"]].copy()
    last = win[win["j"] == 0][["game_id", "team"]].drop_duplicates()
    info["has_final"] = pd.MultiIndex.from_frame(info[["game_id", "team"]]).isin(
        pd.MultiIndex.from_frame(last))
    cols = ["game_id", "team", "player_id", "player_name", "status", "proj", "n_avail"]
    if win.empty:
        return pd.DataFrame(columns=cols), info
    wa = win.merge(app[["game_id", "team", "player_id", "player_name", "pts"]].rename(
        columns={"game_id": "prev_game_id"}), on=["prev_game_id", "team"])
    # the bench rate: points per available team game over the window
    rate = wa.groupby(["game_id", "team", "player_id"])["pts"].agg(proj="mean", n_avail="count").reset_index()
    rate["proj"] = rate["proj"].fillna(0.0)
    # the roster: in the box of the team's most recent final game, latest appearance with this team
    r = wa[wa["j"] == 0][["game_id", "team", "player_id", "player_name"]].drop_duplicates(
        ["game_id", "team", "player_id"])
    r = r.merge(info[["game_id", "team", "cutoff"]], on=["game_id", "team"])
    r = r[latest_team(r, app).to_numpy() == r["team"].to_numpy()].drop(columns="cutoff")
    r = r.assign(src="box")
    rep = report_asof(inj, times)
    if len(rep):
        rep = rep[["game_id", "team", "player_id", "player_name", "status"]].copy()
        # a report row with no NBA id: the unique roster player of that team with the name
        miss = rep["player_id"].isna()
        if miss.any():
            known = pd.concat([r[["game_id", "team", "player_id", "player_name"]],
                               wa[["game_id", "team", "player_id", "player_name"]]]).drop_duplicates()
            known = known.assign(k=known["player_name"].map(base_key))
            uniq = known.groupby(["game_id", "team", "k"])["player_id"].agg(
                lambda s: s.iloc[0] if s.nunique() == 1 else None)
            keys = zip(rep.loc[miss, "game_id"], rep.loc[miss, "team"], rep.loc[miss, "player_name"].map(base_key))
            rep.loc[miss, "player_id"] = [uniq.get(k) for k in keys]
            rep = rep.dropna(subset=["player_id"])
        rep = rep.drop_duplicates(["game_id", "player_id"], keep="last")
        # the report wins: a player it lists for one team is not on the other team's roster
        listed = rep.set_index(["game_id", "player_id"])["team"]
        lt = listed.reindex(pd.MultiIndex.from_frame(r[["game_id", "player_id"]])).to_numpy()
        r = r[pd.isna(lt) | (lt == r["team"].to_numpy())]
        add = rep[~pd.MultiIndex.from_frame(rep[["game_id", "team", "player_id"]]).isin(
            pd.MultiIndex.from_frame(r[["game_id", "team", "player_id"]]))]
        r = pd.concat([r, add[["game_id", "team", "player_id", "player_name"]].assign(src="report")],
                      ignore_index=True)
        r = r.merge(rep[["game_id", "team", "player_id", "status"]], on=["game_id", "team", "player_id"],
                    how="left")
    else:
        r = r.assign(status=np.nan)
    r = r.merge(rate, on=["game_id", "team", "player_id"], how="left")
    r["proj"] = r["proj"].fillna(0.0)
    r["n_avail"] = r["n_avail"].fillna(0).astype(int)
    return r[cols + ["src"]].reset_index(drop=True), info


# ── names ───────────────────────────────────────────────────────────────────

# Book spelling -> box-score spelling, for names models.nba_props.match_names
# misses on the 2023-24 and 2024-25 props (measured 2026-10-17 from names only,
# no price read; each is one player: ids 1630527, 1630231, 1628970).
PROP_ALIASES = {"B.J. Boston Jr": "Brandon Boston", "Kenyon Martin Jr.": "KJ Martin",
                "Mil. Bridges": "Miles Bridges"}


def match_prop_names(priced: pd.DataFrame, roster: pd.DataFrame) -> pd.DataFrame:
    """match_names over the game's two rosters, the book's spelling first mapped
    through PROP_ALIASES. Returns the book's own name with player_id and how."""
    if priced.empty:
        return priced.assign(player_id=[], how=[])
    if roster.empty:                                  # nobody to be: every name unresolved
        return priced.assign(player_id=None, how="none")
    x = priced.assign(_n=priced["player_name"].map(lambda n: PROP_ALIASES.get(n, n)))
    m = match_names(x[["game_id", "_n"]].drop_duplicates().rename(columns={"_n": "player_name"}),
                    roster[["game_id", "player_id", "player_name"]])
    m = m.rename(columns={"player_name": "_n"})
    return x.merge(m, on=["game_id", "_n"], how="left").drop(columns="_n")


# ── the model number per game ───────────────────────────────────────────────

_TEAM_COLS = ["team_pts", "has_final", "n_priced", "n_priced_out", "n_bench", "bench_pts"]
PER_GAME_COLS = (["game_id", "T"] + [f"h_{c}" for c in _TEAM_COLS] + [f"a_{c}" for c in _TEAM_COLS]
                 + ["n_names", "n_shared", "n_none", "refused"])


def empty_times() -> pd.DataFrame:
    return pd.DataFrame({"game_id": pd.Series([], dtype=object),
                         "T": pd.Series([], dtype="datetime64[ns, UTC]"),
                         "lead_min": pd.Series([], dtype=float)})


def model_numbers(times: pd.DataFrame, props: pd.DataFrame, games_all: pd.DataFrame,
                  app: pd.DataFrame, inj: pd.DataFrame | None, shape_by_season: dict):
    """(model, per_game, names). model: game_id, market, mu (implied margin for
    spreads, implied total for totals). per_game: one row per decided game with
    the refusal reason (empty = has a model number) and the counts. names: every
    priced (game, name) with its resolution."""
    if times.empty or props.empty:
        return (pd.DataFrame(columns=["game_id", "market", "mu"]),
                pd.DataFrame(columns=PER_GAME_COLS),
                pd.DataFrame(columns=["game_id", "player_name", "player_id", "how", "team", "status"]))
    roster, info = rosters(times, games_all, app, inj)
    vis = H.visible(props, times)
    qm = quote_means(vis, shape_by_season)
    priced = qm[["game_id", "player_name"]].drop_duplicates()
    names = match_prop_names(priced, roster)
    names = names.merge(roster[["game_id", "player_id", "team", "status"]].drop_duplicates(
        ["game_id", "player_id"]), on=["game_id", "player_id"], how="left")
    ok_names = names[names["how"].isin(["key", "base", "alias", "tokens", "initial"])]
    qm = qm.merge(ok_names[["game_id", "player_name", "player_id"]], on=["game_id", "player_name"])
    pm = player_mean(qm).merge(roster[["game_id", "player_id", "team", "status"]].drop_duplicates(
        ["game_id", "player_id"]), on=["game_id", "player_id"], how="left")
    pm["out"] = pm["status"].eq("Out")
    priced_ids = pd.MultiIndex.from_frame(pm[["game_id", "player_id"]]) if len(pm) else \
        pd.MultiIndex.from_arrays([[], []])
    bench = roster[~pd.MultiIndex.from_frame(roster[["game_id", "player_id"]]).isin(priced_ids)
                   & ~roster["status"].eq("Out")] if len(roster) else roster
    tp = info[["game_id", "team", "is_home", "has_final"]].copy()
    agg_p = pm[~pm["out"]].groupby(["game_id", "team"])["mu"].agg(priced_pts="sum", n_priced="size")
    agg_o = pm[pm["out"]].groupby(["game_id", "team"]).size().rename("n_priced_out")
    agg_b = bench.groupby(["game_id", "team"])["proj"].agg(bench_pts="sum", n_bench="size")
    tp = tp.join(agg_p, on=["game_id", "team"]).join(agg_o, on=["game_id", "team"]).join(
        agg_b, on=["game_id", "team"])
    for c in ("priced_pts", "bench_pts"):
        tp[c] = tp[c].fillna(0.0)
    for c in ("n_priced", "n_priced_out", "n_bench"):
        tp[c] = tp[c].fillna(0).astype(int)
    tp["team_pts"] = tp["priced_pts"] + tp["bench_pts"]
    # one row per game, refusal reasons in a fixed order
    h, a = tp[tp["is_home"]].set_index("game_id"), tp[~tp["is_home"]].set_index("game_id")
    pg = times[["game_id", "T"]].set_index("game_id").join(
        h[_TEAM_COLS].add_prefix("h_")).join(a[_TEAM_COLS].add_prefix("a_"))
    nm = names.groupby("game_id")["how"].agg(
        n_names="size", n_shared=lambda s: int((s == "shared").sum()), n_none=lambda s: int((s == "none").sum()))
    pg = pg.join(nm)
    for c in ("n_names", "n_shared", "n_none"):
        pg[c] = pg[c].fillna(0).astype(int)
    reason = np.full(len(pg), "", dtype=object)
    no_final = ~(pg["h_has_final"].fillna(False).astype(bool) & pg["a_has_final"].fillna(False).astype(bool))
    no_price = pg["n_names"] == 0
    reason = np.where(reason == "", np.where(no_final, "no_final_game_this_season", ""), reason)
    reason = np.where(reason == "", np.where(no_price, "no_priced_player", ""), reason)
    reason = np.where(reason == "", np.where(pg["n_shared"] > 0, "name_collision", ""), reason)
    reason = np.where(reason == "", np.where(pg["n_none"] > 0, "unresolved_name", ""), reason)
    side_empty = (pg["h_n_priced"].fillna(0) == 0) | (pg["a_n_priced"].fillna(0) == 0)
    reason = np.where(reason == "", np.where(side_empty, "no_priced_player_on_a_side", ""), reason)
    pg["refused"] = reason
    pg = pg.reset_index()
    ok = pg[pg["refused"] == ""]
    model = pd.concat([
        pd.DataFrame({"game_id": ok["game_id"], "market": "spreads", "mu": ok["h_team_pts"] - ok["a_team_pts"]}),
        pd.DataFrame({"game_id": ok["game_id"], "market": "totals", "mu": ok["h_team_pts"] + ok["a_team_pts"]}),
    ], ignore_index=True)
    return model, pg, names


# ── the gap and the cells ───────────────────────────────────────────────────

def with_gap(neutral: pd.DataFrame, model: pd.DataFrame) -> pd.DataFrame:
    """Every market-fair offer, plus `gap` in the side's favour against the offer's
    own number (NaN where the game has no model number)."""
    x = neutral.merge(model[["game_id", "market", "mu"]].rename(columns={"mu": "model_mu"}),
                      on=["game_id", "market"], how="left")
    m, s, ln, mm = x["market"], x["side"], x["line"], x["model_mu"]
    gap = np.select([(m == "spreads") & (s == "home"), (m == "spreads") & (s == "away"),
                     (m == "totals") & (s == "over"), (m == "totals") & (s == "under")],
                    [mm + ln, -(mm + ln), mm - ln, ln - mm], default=np.nan)
    return x.assign(gap=gap)


def modelled(cand: pd.DataFrame) -> pd.DataFrame:
    """Only the offers of games the rule produced a number for: the cell's own
    priced population (section 6.4, second amendment), which run_cells reads
    from the games in `cand`."""
    return cand[cand["gap"].notna()].reset_index(drop=True)


def placebo_frames(neutral: pd.DataFrame, model: pd.DataFrame, games: pd.DataFrame,
                   n: int = N_PLACEBO) -> list[pd.DataFrame]:
    out = []
    for run in range(n):
        sh = H.shuffle_within_date(model, games, np.random.default_rng(run)) if len(model) else model
        out.append(modelled(with_gap(neutral, sh)))
    return out


def pick(c: pd.DataFrame, cut: float, side: str, market: str) -> pd.DataFrame:
    """The same choice run_cells makes for a strength cell (used for bet counts only)."""
    cm = c[(c["market"] == market) & (c["gap"] >= cut)]
    return H.choose(cm, -np.inf, sides=[side])


def offers_at(data: H.Data, times: pd.DataFrame, sig: dict):
    vis = H.visible(data.quotes, times)
    vis = vis[vis["market"].isin(list(SIDES))]
    off = H.offers(vis)
    fair = H.market_fair(vis, sig)
    return vis, H.fair_offers(off, fair)


def population(data: H.Data, times: pd.DataFrame, neutral: pd.DataFrame, cand: pd.DataFrame,
               per_game: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    """Per decision point and season: coverage, refusals, name resolution, bets per cell side."""
    g = data.games[["game_id", "season"]]
    rows = []
    for s in sorted(g["season"].unique()):
        ids = set(g.loc[g["season"] == s, "game_id"])
        r = {"family": FAMILY, "point": POINT, "season": int(s), "games": len(ids),
             "games_props_at_T": int(times["game_id"].isin(ids).sum())}
        dec = neutral[neutral["game_id"].isin(ids) & neutral["book"].isin(H.BETTABLE)
                      & (neutral["price"] >= H.PRICE_FLOOR)]
        for mk in SIDES:
            r[f"games_price_{mk}"] = int(dec.loc[dec["market"] == mk, "game_id"].nunique())
        pg = per_game[per_game["game_id"].isin(ids)]
        r["games_model"] = int((pg["refused"] == "").sum())
        for why in ("no_final_game_this_season", "no_priced_player", "name_collision", "unresolved_name",
                    "no_priced_player_on_a_side"):
            r[f"refused_{why}"] = int((pg["refused"] == why).sum())
        nm = names[names["game_id"].isin(ids)]
        r["priced_names"] = int(len(nm))
        for how in ("key", "base", "alias", "tokens", "initial", "shared", "none"):
            r[f"names_{how}"] = int((nm["how"] == how).sum())
        r["priced_out_at_T"] = int(pg["h_n_priced_out"].fillna(0).sum() + pg["a_n_priced_out"].fillna(0).sum())
        ok = pg[pg["refused"] == ""]
        r["mean_priced_per_team"] = float(pd.concat([ok["h_n_priced"], ok["a_n_priced"]]).mean()) if len(ok) else np.nan
        r["mean_bench_pts_per_team"] = float(pd.concat([ok["h_bench_pts"], ok["a_bench_pts"]]).mean()) if len(ok) else np.nan
        cs = cand[cand["game_id"].isin(ids)]
        for mk, sides in SIDES.items():
            for side in sides:
                for cut in CUTS:
                    r[f"bets_{mk}_{side}_g{int(cut)}"] = int(len(pick(cs, cut, side, mk))) if len(cs) else 0
        rows.append(r)
    return pd.DataFrame(rows)


# ── the run ─────────────────────────────────────────────────────────────────

def box_tables(cache: Path = H.CACHE) -> dict:
    return {
        "adv": pd.read_parquet(cache / "nba_player_game_adv.parquet",
                               columns=["game_id", "player_id", "player_name", "team", "season", "game_type",
                                        "played", "did_not_play_reason"]),
        "log": pd.read_parquet(cache / "nba_player_game_log.parquet", columns=["game_id", "player_id", "points"]),
        "ina": pd.read_parquet(cache / "nba_game_inactives.parquet",
                               columns=["game_id", "player_id", "player_name", "team", "season", "game_type"]),
        "inj": pd.read_parquet(cache / "nba_injury_report.parquet",
                               columns=["game_id", "team", "report_ts", "player_id", "player_name", "status"]),
    }


def build(data: H.Data, games_all: pd.DataFrame, props: pd.DataFrame, app: pd.DataFrame,
          inj: pd.DataFrame | None, shape_by_season: dict, sig: dict) -> dict:
    """Everything up to the cells: times, model numbers, market-fair offers with gap."""
    times = H.per_event_times(props, POINT) if len(props) else empty_times()
    times = times[times["game_id"].isin(data.games["game_id"])].reset_index(drop=True)
    model, per_game, names = model_numbers(times, props, games_all, app, inj, shape_by_season)
    _, neutral = offers_at(data, times, sig)
    cand = modelled(with_gap(neutral, model))
    return {"times": times, "model": model, "per_game": per_game, "names": names,
            "neutral": neutral, "cand": cand}


def check_close_prior(sig: dict, seasons) -> None:
    """Every graded prop season's market pricing must come from EARLIER
    seasons' results around Pinnacle's close. H.dist_by_season falls back to a
    season's own results when fewer than 300 earlier closes exist (meant for
    2020-21, never chosen on); for 2024-2026 that would price a season with its
    own outcomes, and a missing entry would price nothing. Either one stops the run."""
    for s in seasons:
        for m in SIDES:
            d = sig.get((int(s), m))
            if not isinstance(d, H.ResidDist) or not d.label.endswith("(prior)"):
                raise RuntimeError(f"{s} {m}: the market's pricing is {d!r}, not a distribution fit on "
                                   "earlier seasons; load every priced season before the graded ones")


def run(data: H.Data, games_all: pd.DataFrame, props: pd.DataFrame, app: pd.DataFrame,
        inj: pd.DataFrame | None, shape_by_season: dict, results: Path | None) -> dict:
    close = H.pinnacle_close(data)
    sig = H.close_dist(close, data.games)
    check_close_prior(sig, [s for s in PROP_SEASONS if s in set(data.games["season"].astype(int))])
    b = build(data, games_all, props, app, inj, shape_by_season, sig)
    placebo = placebo_frames(b["neutral"], b["model"], data.games)
    rows = H.run_cells(data, FAMILY, POINT, b["cand"], b["neutral"], cuts=list(CUTS),
                       sides_by_market=SIDES, close=close, sig=sig, placebo=placebo,
                       strength="gap", choose_seasons=CHOOSE_SEASONS, times=b["times"])
    assert len(rows) == EXPECTED_CELLS, f"F6b emits {EXPECTED_CELLS} cells, got {len(rows)}"
    cells = pd.DataFrame(rows)
    pop = population(data, b["times"], b["neutral"], b["cand"], b["per_game"], b["names"])
    for L in SHAPE_LINES:
        pop[f"shape_offset_{L:g}"] = pop["season"].map(
            lambda s: shape_offset(shape_by_season[int(s)], L) if int(s) in shape_by_season else np.nan)
    if results is not None:
        results.mkdir(parents=True, exist_ok=True)
        cells.to_parquet(results / f"cells_{FAMILY}.parquet")
        pop.to_parquet(results / f"population_{FAMILY}.parquet")
        nm = b["names"].merge(data.games[["game_id", "season"]], on="game_id", how="left")
        nm.to_parquet(results / f"names_{FAMILY}.parquet")
    return {"cells": cells, "population": pop, **b}


def shapes(app: pd.DataFrame, seasons) -> dict:
    return {int(s): fit_shape(app, int(s)) for s in seasons}


def shape_offset(shape: Shape, line: float, p: float = 0.5) -> float:
    """mu - L at an even-money (or p) line: what the shape does to a price."""
    return float(mean_from_over([line], [p], shape)[0] - line)


def load_all(seasons, cache: Path = H.CACHE, require_seasons=None):
    """`seasons`: what H.load keeps. The market's pricing for 2024-2026 is fit
    on the priced seasons before them (2020-21 on), so a graded run loads those
    too (FULL_LOAD_SEASONS). `require_seasons`: a graded run's seasons; H.load
    refuses a cache that prices too few of their games or whose rows match no
    purchase."""
    data = H.load(cache, seasons=seasons, require_seasons=require_seasons)
    games_all = H.load_games(cache)
    t = box_tables(cache)
    app = appearances(t["adv"], t["log"], t["ina"], games_all)
    props = load_props(data.games, cache)
    return data, games_all, app, t["inj"], props


# ── synthetic end-to-end check (also run by the tests) ─────────────────────

def symmetric_shape(n: int = 2001) -> Shape:
    """Residuals symmetric about zero (fewer than K_NEAREST, so every one is used):
    mu = L at p = 0.5."""
    assert n < K_NEAREST
    return Shape(m=np.full(n, 20.0), e=np.linspace(-12.0, 12.0, n), seasons=(0,))


PRIOR_GAMES = 300      # H.dist_by_season fits a season on earlier ones from 300 closes up


def prior_season(n: int = PRIOR_GAMES, season: int = 2023) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(games, quotes): n MIA v CHI games of an earlier season, each with one
    coherent Pinnacle spread (-4.5) and total (220.5) 70 minutes before tip and
    a deterministic score, so the market's pricing of the next season has
    earlier closes to be fit on."""
    tips = pd.Timestamp(f"{season - 1}-11-01T00:30:00Z") + pd.to_timedelta(np.arange(n), unit="D")
    i = np.arange(n)
    games = pd.DataFrame({"game_id": [f"Q{k}" for k in i], "season": season,
                          "game_date": [str((t - pd.Timedelta(hours=5)).date()) for t in tips],
                          "tip": tips, "home_team": "MIA", "away_team": "CHI",
                          "home_score": 98 + (i * 7) % 25, "away_score": 95 + (i * 11) % 21})
    q = []
    for gid, date, tip in zip(games["game_id"], games["game_date"], games["tip"]):
        fetch = tip - pd.Timedelta(minutes=70)
        for mk, ln in (("spreads", -4.5), ("totals", 220.5)):
            q.append({"game_id": gid, "season": season, "game_date": date, "tip": tip, "market": mk,
                      "book": "pinnacle", "line": ln, "snapshot_at": fetch - pd.Timedelta(minutes=2),
                      "fetch_at": fetch, "price_a": -105.0, "price_b": -105.0, "coherent": True})
    return games, pd.DataFrame(q)


def synthetic_case() -> dict:
    """BOS v NYK twice in 2024: P0 (final two days earlier, its box the roster)
    and G1 (decided at tip - 60 from its props), plus a 2023 season of MIA v
    CHI closes (prior_season) for the market's pricing. P0's props are bought
    too, so D reaches every 2024 game; P0 has no final game before it and gets
    no model number. Every number set by hand."""
    tip1 = pd.Timestamp("2024-01-16T00:30:00Z")
    tip0 = pd.Timestamp("2024-01-14T00:30:00Z")
    games = pd.DataFrame([
        {"game_id": "P0", "season": 2024, "game_date": "2024-01-13", "tip": tip0, "home_team": "BOS",
         "away_team": "NYK", "home_score": 100, "away_score": 90},
        {"game_id": "G1", "season": 2024, "game_date": "2024-01-15", "tip": tip1, "home_team": "BOS",
         "away_team": "NYK", "home_score": 120, "away_score": 100},
    ])
    T = tip1 - pd.Timedelta(minutes=60)
    # the box of P0: two players a side; B3 sat (coach), N3 inactive (injured)
    app = pd.DataFrame([
        ("P0", "b1", "Ann Bee", "BOS", True, 30.0), ("P0", "b2", "Cal Dee", "BOS", True, 12.0),
        ("P0", "b3", "Eve Eff", "BOS", False, np.nan),
        ("P0", "n1", "Gus Hay", "NYK", True, 25.0), ("P0", "n2", "Ivy Jay", "NYK", True, 8.0),
        ("P0", "n3", "Kim Lee", "NYK", False, np.nan),
    ], columns=["game_id", "player_id", "player_name", "team", "played", "points"])
    app["did_not_play_reason"] = np.where(app["player_id"] == "b3", "DNP - Coach's Decision",
                                          np.where(app["player_id"] == "n3", "INACTIVE", None))
    app["season"] = 2024
    app["tip"] = tip0
    coach = app["did_not_play_reason"].astype(str).str.contains("Coach")
    app["avail"] = app["played"] | coach
    app["pts"] = np.where(app["played"], app["points"], np.where(app["avail"], 0.0, np.nan))
    # props at T: b1 and n1 priced (fanduel and draftkings, even money no vig)
    rows = []
    for gid, at in (("G1", T), ("P0", tip0 - pd.Timedelta(minutes=60))):
        for name, line in (("Ann Bee", 27.5), ("Gus Hay", 22.5)):
            for book in ("fanduel", "draftkings"):
                rows.append({"game_id": gid, "player_name": name, "market": PROP_MARKET, "bookmaker": book,
                             "snapshot_type": "open", "snapshot_at": at.isoformat(), "line": line,
                             "over_price": -110.0, "under_price": -110.0})
    props = props_frame(pd.DataFrame(rows), games)
    inj = pd.DataFrame([{"game_id": "G1", "team": "NYK", "report_ts": T - pd.Timedelta(minutes=45),
                         "player_id": "n2", "player_name": "Ivy Jay", "status": "Out"}])
    # full-game quotes at a slate fetch 70 minutes before each tip, Pinnacle
    # among them; the 2023 closes are what the 2024 pricing is fit on
    parts = []
    for gid, date, tip, sp, tot in (("P0", "2024-01-13", tip0, -5.0, 200.0),
                                    ("G1", "2024-01-15", tip1, -3.5, 220.5)):
        fetch = tip - pd.Timedelta(minutes=70)
        for book, pa in (("fanduel", -110.0), ("draftkings", -110.0), ("pinnacle", -105.0)):
            for mk, ln in (("spreads", sp), ("totals", tot)):
                parts.append({"game_id": gid, "season": 2024, "game_date": date, "tip": tip,
                              "market": mk, "book": book, "line": ln,
                              "snapshot_at": fetch - pd.Timedelta(minutes=2), "fetch_at": fetch,
                              "price_a": pa, "price_b": pa, "coherent": True})
    pg, pq = prior_season()
    quotes = pd.concat([pd.DataFrame(parts), pq], ignore_index=True)
    fetches = quotes[["game_id", "tip", "fetch_at"]].drop_duplicates()
    fetches = fetches.assign(lead_min=(fetches["tip"] - fetches["fetch_at"]).dt.total_seconds() / 60)
    games = pd.concat([pg, games], ignore_index=True)
    data = H.Data(games=games, quotes=quotes, fetches=fetches)
    return {"games": games, "app": app, "props": props, "inj": inj, "data": data, "T": T,
            "shape": {2024: symmetric_shape()}}


def synthetic_check() -> dict:
    s = synthetic_case()
    sig = {(2024, "spreads"): 12.0, (2024, "totals"): 18.0}
    b = build(s["data"], s["games"], s["props"], s["app"], s["inj"], s["shape"], sig)
    pg = b["per_game"].set_index("game_id")
    assert pg.loc["G1", "refused"] == "", pg.loc["G1", "refused"]
    # a symmetric shape at even money puts each priced mean on his line
    home = 27.5 + 12.0 + 0.0           # Ann Bee's line; Cal Dee 12; Eve Eff DNP-coach 0
    away = 22.5 + 0.0                   # Gus Hay's line; Ivy Jay Out; Kim Lee inactive
    m = b["model"].set_index("market")["mu"]
    assert np.isclose(m["totals"], home + away), (m["totals"], home + away)
    assert np.isclose(m["spreads"], home - away), (m["spreads"], home - away)
    c = b["cand"]
    gh = c[(c["market"] == "spreads") & (c["side"] == "home")]["gap"].iloc[0]
    assert np.isclose(gh, (home - away) - 3.5)
    gu = c[(c["market"] == "totals") & (c["side"] == "under")]["gap"].iloc[0]
    assert np.isclose(gu, 220.5 - (home + away))
    return {"home": home, "away": away, "model": b["model"], "per_game": b["per_game"]}


# ── price-free checks ───────────────────────────────────────────────────────

def quality(app: pd.DataFrame, games_all: pd.DataFrame, inj: pd.DataFrame,
            seasons=QUALITY_SEASONS) -> pd.DataFrame:
    """The bench rule applied to the WHOLE roster (no prices) against the team's
    actual points, at T = tip - 60 minutes: bias and mean absolute error per season.
    Never 2026."""
    assert all(s <= 2025 for s in seasons), "never 2026"
    g = games_all[games_all["season"].isin(seasons)]
    times = g[["game_id"]].assign(T=g["tip"] - pd.Timedelta(minutes=60))
    roster, info = rosters(times, games_all, app, inj)
    proj = roster[~roster["status"].eq("Out")].groupby(["game_id", "team"])["proj"].sum()
    info = info[info["has_final"]].join(proj, on=["game_id", "team"])
    act = pd.concat([g[["game_id", "home_team", "home_score"]].rename(columns={"home_team": "team",
                                                                              "home_score": "pts"}),
                     g[["game_id", "away_team", "away_score"]].rename(columns={"away_team": "team",
                                                                              "away_score": "pts"})])
    x = info.merge(act, on=["game_id", "team"])
    x["err"] = x["proj"].fillna(0) - x["pts"]
    return x.groupby("season").agg(team_games=("err", "size"), bias=("err", "mean"),
                                   mae=("err", lambda e: e.abs().mean())).reset_index()


def names_check(cache: Path = H.CACHE, seasons=NAMES_SEASONS) -> pd.DataFrame:
    """Name resolution on the real prop names, reading NO line or price column."""
    assert all(s <= 2025 for s in seasons), "never 2026"
    games_all = H.load_games(cache)
    g = games_all[games_all["season"].isin(seasons)]
    raw = pd.read_parquet(cache / "nba_props.parquet",
                          columns=["game_id", "player_name", "market", "bookmaker", "snapshot_type", "snapshot_at"])
    raw = raw[raw["game_id"].isin(g["game_id"]) & (raw["market"] == PROP_MARKET)]
    raw = raw.assign(line=0.5, over_price=-110.0, under_price=-110.0)   # placeholders: no price is read
    props = props_frame(raw, g)
    times = H.per_event_times(props, POINT)
    t = box_tables(cache)
    app = appearances(t["adv"], t["log"], t["ina"], games_all)
    _, per_game, names = model_numbers(times, props, games_all, app, t["inj"],
                                       {int(s): symmetric_shape() for s in seasons})
    per_game = per_game.merge(g[["game_id", "season"]], on="game_id")
    out = per_game.groupby("season").agg(games_props_at_T=("game_id", "size"),
                                         games_model=("refused", lambda r: int((r == "").sum())))
    out = out.join(per_game.pivot_table(index="season", columns="refused", values="game_id",
                                        aggfunc="size", fill_value=0).drop(columns="", errors="ignore")
                   .add_prefix("refused_"))
    nm = names.merge(g[["game_id", "season"]], on="game_id")
    out = out.join(nm.pivot_table(index="season", columns="how", values="game_id", aggfunc="size",
                                  fill_value=0).add_prefix("names_"))
    return out.reset_index()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true", help="2020-21 only, plus the synthetic checks")
    mode.add_argument("--full", action="store_true",
                      help="grades 2023-24 to 2025-26 (needs NBA_GAME2_GO=1)")
    mode.add_argument("--quality", action="store_true", help="price-free bench check, 2022-2025")
    mode.add_argument("--names-check", action="store_true", help="price-free name resolution, 2024-2025")
    a = ap.parse_args()
    pd.set_option("display.width", 200)
    if a.quality:
        games_all = H.load_games()
        t = box_tables()
        app = appearances(t["adv"], t["log"], t["ina"], games_all)
        print(quality(app, games_all, t["inj"]).round(3).to_string(index=False))
        sh = shapes(app, (2021, 2024, 2025, 2026))
        print("shape: mean minus line at p = 0.5 / 0.55, by graded season (fit seasons in brackets):")
        for s_, v in sh.items():
            print(f"  {s_} {v.seasons}: " + ", ".join(
                f"L={L:g}: {shape_offset(v, L):+.2f} / {shape_offset(v, L, 0.55):+.2f}" for L in SHAPE_LINES))
        return
    if a.names_check:
        print(names_check().to_string(index=False))
        return
    if a.full and os.environ.get("NBA_GAME2_GO") != "1":
        sys.exit("--full is run by the owner after the price data is refreshed: set NBA_GAME2_GO=1")
    syn = synthetic_check()
    print(f"synthetic check passes: home {syn['home']:.3f}, away {syn['away']:.3f}")
    if a.smoke:
        data, games_all, app, inj, props = load_all(list(SMOKE_SEASONS))
        graded = SMOKE_SEASONS
    else:
        # every priced season loaded (the market's pricing reads the seasons
        # before 2024); the seasons with props are the ones graded and
        # required, and the only ones a shape is fit for (2019 has no box
        # season before it to fit on)
        data, games_all, app, inj, props = load_all(FULL_LOAD_SEASONS, require_seasons=PROP_SEASONS)
        graded = PROP_SEASONS
    results = RESULTS / "smoke" if a.smoke else RESULTS     # a smoke run never sits beside real cells
    out = run(data, games_all, props, app, inj, shapes(app, graded), results)
    cells, pop = out["cells"], out["population"]
    print(f"{len(cells)} cells written to {results} (family {FAMILY}, point {POINT})")
    print(pop.drop(columns=[c for c in pop.columns if c.startswith("bets_")]).to_string(index=False))
    bets = pop[["season"] + [c for c in pop.columns if c.startswith("bets_")]].set_index("season")
    print("bets per cell side and season (counts only):")
    print(bets.T.to_string())
    if a.smoke:
        assert (cells["n_choose"] == 0).all() and (cells["n_confirm"] == 0).all(), \
            "2020-21 holds no props: every cell must be empty"
        print("smoke: 12 cells, every cell empty on 2020-21 as expected (props start 2023-24)")
        print("price-free bench rule on the whole roster vs actual team points, 2020-21:")
        print(quality(app, games_all, inj, seasons=(2021,)).round(3).to_string(index=False))


if __name__ == "__main__":
    main()

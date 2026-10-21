"""F1, F1b and F5 of the second NBA game-market search: the player projection.

docs/nba_models_2026.md section 6.3. This lab EMITS cells through the shared
harness (scripts/nba_game_harness.py); scripts/nba_game2_verdict.py judges
them. These three families are graded ONCE, after the play-by-play lineup
segments (`nba_stints`) land, so --full refuses until they exist for every
season 2018-19 onward; until then the lab is built, tested and run on --smoke
and --quality only. --full also refuses a stale price cache
(H.load(require_seasons=...)).

THE PROJECTION (every input dated at or before the decision time T)
  ratings   each player's offensive and defensive impact in points per 100
            possessions, from two sources:
            (1) a box-score plus-minus: time-decayed per-100 box rates over the
                player's games final before T, shrunk toward the league mean
                by K pseudo-possessions, mapped to impact by coefficients fit on
                team efficiency (points per 100 possessions) in prior seasons'
                games -- the team-level fit of Basketball-Reference's BPM idea
                (Myers, "About Box Plus/Minus", 2020) with as-of rates and the
                minutes each player actually played;
            (2) adjusted plus-minus from lineup segments (`nba_stints`): a ridge
                regression whose penalty pulls each player toward his box
                rating instead of zero, the box-score prior of Engelmann's
                xRAPM / RPM and of EPM (Snarr, dunksandthrees.com methodology).
                The segment evidence is kept as a deviation from the prior and
                added to the box rating of the day. With no segments the rating
                is the box rating, the ridge's limit as its penalty grows.
  minutes   expected minutes = P(plays) x time-weighted minutes when he plays,
            each team rescaled to 240 with a per-player cap (practitioner
            minutes reallocation). P(plays): Out = 0; Doubtful, Questionable,
            Probable, Available and "not on the report" are rates fit on prior
            seasons' reports against who actually played, by status (or role)
            and hours to tip.
  game      pace = pace_home x pace_away / league pace and possessions-based
            efficiency (Oliver, Basketball on Paper, 2004); efficiency = league
            + own offence - opponent defence (+ home); margin and total through
            a linear calibration fit on prior seasons' walk-forward projections,
            with back-to-back terms read from the schedule.
  price     (F1) the projection's OWN empirical error distribution (section 6.5
            amendment, second): result minus the same projection at the same
            decision point, on seasons before S (H.dist_by_season), never the
            market's error. The harness re-centres it on zero (third
            amendment: the spread, not the average miss), so an earlier
            season's average miss never moves the centre a second time on
            top of the calibration. 2020-21 has no earlier priced season at a decision
            point, so it is priced on its own residuals (the harness's
            fallback): reported, never chosen on. The moneyline is the margin
            distribution's P(home margin > 0) with the tie mass removed.
            F1b and F5 are rule families measured in points; their offers keep
            the MARKET's fair pricing (H.close_dist), as closing-line value does.

FAMILIES (section 6.3; 228 cells)
  F1   spread, total, moneyline x 2 sides x A,B,C,D x EV >= 0,.01,.02,.03,.05,.08   144
  The CONSENSUS number at T (third amendment) is Pinnacle's number where it
  quotes, else the deciding books' median (consensus()). Every gap against
  the line below is measured against it, never against a book's own number.
  F1b  the projection predicting the consensus line's move: OLS of
       (closing consensus - decision consensus) on (projection - decision
       consensus), prior priced seasons, per market and decision point; the
       strength is the PREDICTED MOVE (predicted close - consensus at T) in the
       side's favour, the same for every book; a side is bet when it is >= k,
       at its best offer under the market's fair line:
       spread, total x 2 x A,B,C x k = 0.5, 1, 1.5, 2                                 48
  F5   absences valued beyond minutes: the F1 projection plus an OLS of its
       prior-season residual on tiered absences, starters out, Questionable /
       Doubtful exposure and first games back; the strength is the gap between
       that projection and the consensus number at T, the same for every book;
       a side is bet when it is >= the cut, at its best offer under the
       market's fair line: spread, total x 2 x B,C,D x gap >= 1,2,3                 36
  A cell's population is the games its projection produced a number for. The
  95% gate at D, the real-side shares and the blind bet per real side are the
  harness's (H.run_cells); every bet carries its real side.

WALK-FORWARD (season = ending year; nothing of season S is fit on season S)
  hyperparameters (rate half-life, shrinkage K, league and team-pace
      half-lives): fit on 2019..S-2, scored on S-1 (2020 and 2021 share the
      first possible fit, 2018-19 -> 2019-20); the minutes half-life is fit
      once on that first fit and kept, so P(plays) roles are one table.
  box coefficients: 2021 <- 2019-2020; 2022 <- 2019-2021; 2023 <- 2019-2022;
      2024 <- 2019-2023; 2025 <- 2019-2024; 2026 <- 2019-2025
      (2018-19 from 2018-12-15, once every player has some history).
  P(plays): the same seasons as the box coefficients.
  calibration and the F5 residual model: walk-forward projections of 2020..S-1
      (2021 <- 2020; 2022 <- 2020-2021; ... 2026 <- 2020-2025).
  adjusted plus-minus: refit every REFIT_DAYS on segments of games before the
      refit date (seasons S-1 and S, time-decayed); penalty by game-fold
      cross-validation on season S-1's segments.
  F1b move regression: 2022 <- 2021; 2023 <- 2021-2022; ... 2026 <- 2021-2025.
      2021 has no prior priced season, so F1b places no 2020-21 bet (its cells
      are still emitted, with n_2021 = 0).

LEAK GUARDS
  box scores   only games on an earlier date, and the latest such tip + FINAL_LAG
               must be <= T or the game gets no projection
  injuries     a report counts from its printed time + 30 minutes (section 6.1)
  schedule     back-to-backs from the schedule (dates only, never a result)
  prices       the harness's own visible(): fetch <= T, quote <= 60 minutes old

    PYTHONPATH=. python -m scripts.nba_game2_projection --smoke
    PYTHONPATH=. python -m scripts.nba_game2_projection --quality
    NBA_GAME2_GO=1 PYTHONPATH=. python -m scripts.nba_game2_projection --full
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402

# ── where things are ────────────────────────────────────────────────────────

RESULTS = Path(os.environ.get("NBA_GAME2_RESULTS",
                              "C:/Users/micha/AppData/Local/Temp/nba_game_edge/results"))
SMOKE_CACHE = Path(os.environ.get(
    "NBA_GAME2_SMOKE_CACHE",
    str(Path(os.environ.get("TEMP", "C:/Users/micha/AppData/Local/Temp"))
        / "nba_game_edge" / "projection_smoke_cache")))
STINTS_FILE = "nba_stints.parquet"
LEDGER_FILE = "nba_fetch_ledger.parquet"
GO_ENV = "NBA_GAME2_GO"

# ── seasons and the walk-forward ────────────────────────────────────────────

FIRST_BOX = 2019                 # 2018-19, the first box-score season held
FIRST_REF = 2020                 # the first season with a walk-forward projection
HYPER_FIT, HYPER_EVAL = 2019, 2020
TRAIN_FROM = "2018-12-15"
GRADED = (2021, 2022, 2023, 2024, 2025, 2026)
STINT_SEASONS = tuple(range(FIRST_BOX, max(GRADED) + 1))   # season S's ratings read S-1 and S
REGULAR_SEASON_TYPE = 2                                    # ESPN: 2 regular, 3 postseason, 5 play-in
SMOKE_SEASONS = (2021,)
QUALITY_SEASONS = (2022, 2023, 2024, 2025)   # never 2026: the confirmation season

# ── rules ───────────────────────────────────────────────────────────────────

FINAL_LAG = pd.Timedelta(hours=4)        # a game counts as final this long after tip
INJURY_LAG = pd.Timedelta(minutes=30)    # section 6.1: printed time + 30 minutes
REF_LEAD = pd.Timedelta(minutes=60)      # price-free reference decision time
ROSTER_GAMES = 10
TEAM_MINUTES = 240.0
ROLE_EDGES = (12.0, 24.0)
BUCKET_REF_H = {"far": 9.0, "mid": 4.5, "near": 1.0}
LISTED = ("Doubtful", "Questionable", "Probable", "Available")
STATS = ("pts", "fg2a", "fg3a", "fta", "oreb", "dreb", "ast", "stl", "blk", "tov", "pf")
FEATURES = STATS + ("mpg", "starter", "prior_share")
# Grids for the one hyperparameter fit (2018-19 -> 2019-20). The first grid
# (45-365 days, K 300-3000, minutes 3-24 games) chose its edges on that fit, so
# each was widened, still price-free; the rate half-life now ends at "no
# decay" and K near "no shrinkage", the natural bounds.
GRID_HL = (180.0, 365.0, 730.0, 1460.0, np.inf)  # days
GRID_K = (30.0, 100.0, 300.0, 1000.0)            # pseudo-possessions
GRID_HL_LG = (15.0, 30.0, 60.0, 120.0)         # days
GRID_MIN_HL = (1.5, 3.0, 6.0, 12.0)            # games played
GRID_HL_PACE = (15.0, 30.0, 60.0, 120.0, 240.0)  # days
RAPM_LAMBDAS = (250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0)
RAPM_FOLDS = 5
REFIT_DAYS = 7
TIER_RANKS = (2, 5)                           # rank <= 2 tier 1, <= 5 tier 2
ROTATION_MIN = 12.0
FIRST_BACK_MISSED = 3
F5_FEATURES = ("miss_t1", "miss_t2", "miss_t3", "starters_out", "q_exposure", "first_back")
MIN_FIT_ROWS = 100
N_PLACEBO = 20

SIDES2 = {"spreads": ("home", "away"), "totals": ("over", "under"), "h2h": ("home", "away")}
FAMILIES = {
    "F1": {"points": ("A", "B", "C", "D"), "markets": ("spreads", "totals", "h2h"),
           "cuts": (0.0, 0.01, 0.02, 0.03, 0.05, 0.08), "strength": "ev"},
    "F1b": {"points": ("A", "B", "C"), "markets": ("spreads", "totals"),
            "cuts": (0.5, 1.0, 1.5, 2.0), "strength": "strength"},
    "F5": {"points": ("B", "C", "D"), "markets": ("spreads", "totals"),
           "cuts": (1.0, 2.0, 3.0), "strength": "strength"},
}
EXPECTED_CELLS = {"F1": 144, "F1b": 48, "F5": 36}


def cell_specs(family: str | None = None) -> list[tuple]:
    """(family, point, market, side, cut_index, cut) for every cell section 6.3 lists."""
    out = []
    for fam, spec in FAMILIES.items():
        if family is not None and fam != family:
            continue
        for p in spec["points"]:
            for m in spec["markets"]:
                for s in SIDES2[m]:
                    for k, c in enumerate(spec["cuts"]):
                        out.append((fam, p, m, s, k, c))
    return out


def check_cell_count() -> None:
    for fam, n in EXPECTED_CELLS.items():
        assert len(cell_specs(fam)) == n, (fam, len(cell_specs(fam)), n)
    assert len(cell_specs()) == 228


check_cell_count()


# ── small helpers ───────────────────────────────────────────────────────────

def to_day(s) -> np.ndarray:
    """Calendar day number of an ISO date (or datetime) column."""
    return pd.to_datetime(pd.Series(s)).to_numpy().astype("datetime64[D]").astype(np.int64)


def ols(A, y, w=None, ridge: float = 1e-6) -> np.ndarray:
    """Weighted least squares; a tiny ridge (all but column 0) for conditioning."""
    A, y = np.asarray(A, float), np.asarray(y, float)
    w = np.ones(len(y)) if w is None else np.asarray(w, float)
    ok = np.isfinite(A).all(1) & np.isfinite(y) & np.isfinite(w) & (w > 0)
    A, y, w = A[ok], y[ok], w[ok]
    if len(y) < A.shape[1]:
        return np.full(A.shape[1], np.nan)
    G = (A.T * w) @ A
    pen = np.eye(A.shape[1]) * ridge * max(float(np.mean(np.diag(G))), 1e-12)
    pen[0, 0] = 0.0
    return np.linalg.solve(G + pen, (A.T * w) @ y)


class EW:
    """Time-decayed sums over each key's history rows dated STRICTLY before a
    query day: sum_j 0.5 ** ((day_q - day_j) / hl) * v_j."""

    def __init__(self, hist: pd.DataFrame, key: str, cols, hl: float):
        cols = list(cols)
        h = hist[[key, "day", *cols]].groupby([key, "day"], as_index=False)[cols].sum()
        h = h.sort_values([key, "day"]).reset_index(drop=True)
        self.lam = 0.0 if not np.isfinite(hl) else np.log(2.0) / hl
        base = h.groupby(key)["day"].transform("min").to_numpy(float)
        sc = np.exp(self.lam * (h["day"].to_numpy(float) - base))
        post = pd.DataFrame(h[cols].to_numpy(float) * sc[:, None], columns=cols).groupby(
            h[key].to_numpy()).cumsum()
        self.h = h[[key, "day"]].rename(columns={"day": "hday"}).assign(
            **{c: post[c].to_numpy() / sc for c in cols})
        self.key, self.cols = key, cols

    def asof(self, q: pd.DataFrame) -> pd.DataFrame:
        qq = q[[self.key, "day"]].reset_index(drop=True).assign(_i=np.arange(len(q)))
        qq["day"] = qq["day"].astype(np.int64)
        m = pd.merge_asof(qq.sort_values("day"), self.h.sort_values("hday"), left_on="day",
                          right_on="hday", by=self.key, allow_exact_matches=False)
        m = m.sort_values("_i")
        dec = np.exp(-self.lam * (m["day"].to_numpy(float) - m["hday"].to_numpy(float)))
        out = pd.DataFrame({c: np.nan_to_num(m[c].to_numpy(float) * dec) for c in self.cols})
        out["last_day"] = m["hday"].to_numpy(float)
        out.index = q.index
        return out


class Last:
    """The value a per-row series held after each key's last row dated STRICTLY before a query day."""

    def __init__(self, hist: pd.DataFrame, key: str, cols):
        self.cols = list(cols)
        self.key = key
        self.h = hist[[key, "day", *self.cols]].rename(columns={"day": "hday"}).sort_values("hday")

    def asof(self, q: pd.DataFrame) -> pd.DataFrame:
        qq = q[[self.key, "day"]].reset_index(drop=True).assign(_i=np.arange(len(q)))
        qq["day"] = qq["day"].astype(np.int64)
        m = pd.merge_asof(qq.sort_values("day"), self.h, left_on="day", right_on="hday",
                          by=self.key, allow_exact_matches=False).sort_values("_i")
        out = m[self.cols + ["hday"]].rename(columns={"hday": "last_day"}).reset_index(drop=True)
        out.index = q.index
        return out


# ── the world: box scores, games, injuries, segments ────────────────────────

@dataclass
class World:
    games: pd.DataFrame       # regular-season games with scores (H.load_games) + day
    panel: pd.DataFrame       # every (game, player) row: played, did not play, inactive
    inj: pd.DataFrame         # the official injury report, every row
    stints: pd.DataFrame | None = None
    tg: pd.DataFrame | None = None        # per (game, team) efficiency, pace, schedule
    seq: pd.DataFrame | None = None       # per (team, k): the team's k-th game
    notes: dict = field(default_factory=dict)


def build_panel(adv: pd.DataFrame, log: pd.DataFrame, ina: pd.DataFrame,
                games: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, player) on a regular-season roster; stats only where he played."""
    a = adv[adv["game_id"].isin(games["game_id"])].copy()
    a["player_id"] = a["player_id"].astype(str)
    lg = log.copy()
    lg["player_id"] = lg["player_id"].astype(str)
    a = a.merge(lg, on=["game_id", "player_id"], how="left")
    i = ina[ina["player_id"].notna() & ina["game_id"].isin(games["game_id"])][
        ["game_id", "team", "player_id"]].copy()
    i["player_id"] = i["player_id"].astype(str)
    have = pd.MultiIndex.from_frame(a[["game_id", "player_id"]])
    i = i[~pd.MultiIndex.from_frame(i[["game_id", "player_id"]]).isin(have)]
    p = pd.concat([a, i.assign(played=False)], ignore_index=True)
    p = p.drop(columns=[c for c in ("season", "game_date") if c in p]).merge(
        games[["game_id", "season", "day"]], on="game_id")
    p["played"] = p["played"].fillna(False).astype(bool)
    p["minutes"] = pd.to_numeric(p.get("minutes_exact"), errors="coerce").fillna(0.0).where(p["played"], 0.0)
    poss = pd.to_numeric(p.get("possessions"), errors="coerce")
    rate = float((poss / p["minutes"]).replace([np.inf, -np.inf], np.nan)[p["played"]].median()) \
        if p["played"].any() else 2.1
    p["poss"] = poss.where(poss.notna(), p["minutes"] * (rate if np.isfinite(rate) else 2.1)).where(p["played"], 0.0)
    num = lambda c: pd.to_numeric(p.get(c), errors="coerce")  # noqa: E731
    p["has_stats"] = p["played"] & num("points").notna() & (p["poss"] > 0)
    st = {"pts": num("points"), "fg2a": num("fg_att") - num("fg3_att"), "fg3a": num("fg3_att"),
          "fta": num("ft_att"), "oreb": num("offensive_reb"), "dreb": num("defensive_reb"),
          "ast": num("assists"), "stl": num("steals"), "blk": num("blocks"),
          "tov": num("turnovers"), "pf": num("fouls")}
    for c, v in st.items():
        p[c] = v.fillna(0.0).where(p["has_stats"], 0.0)
    p["is_starter"] = pd.to_numeric(p.get("is_starter"), errors="coerce").fillna(0.0)
    keep = ["game_id", "player_id", "team", "season", "day", "played", "minutes", "poss",
            "has_stats", "is_starter", *STATS]
    return p[keep].sort_values(["player_id", "day"]).reset_index(drop=True)


def team_table(games: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """Per (game, team): points, possessions, efficiency, pace, back-to-back."""
    pl = panel[panel["played"]]
    t = pl.groupby(["game_id", "team"], as_index=False).agg(poss5=("poss", "sum"), mins=("minutes", "sum"))
    t["poss"], t["gmin"] = t["poss5"] / 5.0, t["mins"] / 5.0
    g = games
    home = g.assign(team=g["home_team"], opp=g["away_team"], is_home=1.0, pts=g["home_score"],
                    opp_pts=g["away_score"])
    away = g.assign(team=g["away_team"], opp=g["home_team"], is_home=0.0, pts=g["away_score"],
                    opp_pts=g["home_score"])
    s = pd.concat([home, away], ignore_index=True)[
        ["game_id", "season", "day", "tip", "team", "opp", "is_home", "pts", "opp_pts"]]
    s = s.merge(t[["game_id", "team", "poss", "gmin"]], on=["game_id", "team"], how="left")
    o = t[["game_id", "team", "poss"]].rename(columns={"team": "opp", "poss": "opp_poss"})
    s = s.merge(o, on=["game_id", "opp"], how="left")
    s["game_poss"] = s[["poss", "opp_poss"]].mean(axis=1)
    s["eff"] = 100.0 * s["pts"] / s["game_poss"]
    s["pace"] = s["game_poss"] * 48.0 / s["gmin"]
    s = s.sort_values(["team", "day"]).reset_index(drop=True)
    prev = s.groupby("team")["day"].shift(1)
    s["b2b"] = ((s["day"] - prev) == 1).astype(float)
    s["k"] = s.groupby("team").cumcount()
    return s


def build_world(games: pd.DataFrame, adv: pd.DataFrame, log: pd.DataFrame, ina: pd.DataFrame,
                inj: pd.DataFrame, stints: pd.DataFrame | None = None) -> World:
    g = games.copy()
    g["season"] = g["season"].astype(int)
    g["day"] = to_day(g["game_date"])
    if "tip" not in g:
        g["tip"] = pd.to_datetime(g["commence_time"], utc=True)
    panel = build_panel(adv, log, ina, g)
    i = inj[inj["game_id"].isin(g["game_id"])].copy()
    i["report_ts"] = pd.to_datetime(i["report_ts"], utc=True)
    w = World(games=g.reset_index(drop=True), panel=panel, inj=i)
    w.tg = team_table(w.games, panel)
    w.seq = w.tg[["team", "k", "game_id", "day"]].copy()
    w.stints = normalize_stints(stints, w.games) if stints is not None else None
    return w


def load_world(cache: Path, max_season: int) -> World:
    """Everything the projection reads, every season after max_season dropped at the door."""
    games = H.load_games(cache)
    games = games[games["season"] <= max_season]
    adv = pd.read_parquet(cache / "nba_player_game_adv.parquet", columns=[
        "game_id", "player_id", "game_type", "team", "is_starter", "played", "minutes_exact",
        "possessions", "fouls", "season"])
    adv = adv[(adv["game_type"] == "regular") & (adv["season"].astype(int) <= max_season)]
    adv = adv.drop(columns=["game_type", "season"])
    log = pd.read_parquet(cache / "nba_player_game_log.parquet", columns=[
        "game_id", "player_id", "points", "offensive_reb", "defensive_reb", "assists", "steals",
        "blocks", "turnovers", "fg_att", "fg3_att", "ft_att", "season"])
    log = log[log["season"].astype(int) <= max_season].drop(columns="season")
    ina = pd.read_parquet(cache / "nba_game_inactives.parquet",
                          columns=["game_id", "team", "player_id", "game_type", "season"])
    ina = ina[(ina["game_type"] == "regular") & (ina["season"].astype(int) <= max_season)]
    inj = pd.read_parquet(cache / "nba_injury_report.parquet", columns=[
        "report_ts", "game_id", "team", "player_id", "player_name", "status", "season"])
    inj = inj[inj["season"].astype(int) <= max_season]
    st = None
    if (cache / STINTS_FILE).exists():
        st = pd.read_parquet(cache / STINTS_FILE)
        if "season" in st:
            st = st[st["season"].astype(int) <= max_season]
    return build_world(games, adv, log, ina, inj, st)


# ── lineup segments (nba_stints) ────────────────────────────────────────────

# The real table (Supabase `nba_stints`, written by data/ingestors/nba_pbp.py on
# branch nba-pbp-stints; columns read from information_schema on 2026-10-17)
# carries every column below. Its player ids are the NBA.com person ids every
# other NBA table uses, as TEXT[]; a player the id map lacks is 'espn:<id>' and
# is kept as his own player (no box history, so a league-mean prior). A side
# with other than five ids (n_home / n_away != 5: 18 of 37,132 regular-season
# rows in 2021-22) is dropped, as are garbage-time rows and every row whose
# season_type is not 2 (postseason 3 and play-in 5 are not in `games` either).
STINT_NEEDS = (
    "game_id (the games table key, e.g. NBA_2024-01-15_BOS_NYK); "
    "home_player_ids and away_player_ids (five nba.com person ids each, as text, the same "
    "ids as nba_player_game_adv.player_id; or columns home_p1..home_p5 / away_p1..away_p5); "
    "home_pts and away_pts scored in the segment; home_poss and away_poss, each team's "
    "offensive possessions ending in the segment (or one `possessions` column, split evenly); "
    "garbage_time (boolean, optional: those segments are dropped); season_type (optional: "
    "only 2, the regular season, is kept). A row without exactly five known ids per side is "
    "dropped.")


def _ids(s: pd.DataFrame, side: str) -> np.ndarray | None:
    lst = f"{side}_player_ids"
    if lst in s:
        # a list as written, a numpy array once it has been through parquet
        v = s[lst].map(lambda x: [str(i) for i in x] if isinstance(x, (list, tuple, np.ndarray)) else [])
        return np.array([(r + [None] * 5)[:5] if len(r) == 5 else [None] * 5 for r in v],
                        dtype=object).reshape(-1, 5)
    cols = [f"{side}_p{i}" for i in range(1, 6)]
    if all(c in s for c in cols):
        return s[cols].astype(object).to_numpy()
    return None


def _norm_id(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    t = str(v).strip()
    try:
        return str(int(float(t)))
    except ValueError:
        return t or None


def normalize_stints(s: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """The loader for <cache>/nba_stints.parquet (a cache of Supabase
    `nba_stints`); raises naming what is missing (STINT_NEEDS)."""
    if "season_type" in s:
        s = s[pd.to_numeric(s["season_type"], errors="coerce") == REGULAR_SEASON_TYPE]
    hi, ai = _ids(s, "home"), _ids(s, "away")
    if hi is None or ai is None or "game_id" not in s or not {"home_pts", "away_pts"} <= set(s):
        raise ValueError("nba_stints: missing columns. Needs: " + STINT_NEEDS)
    if {"home_poss", "away_poss"} <= set(s):
        hp, ap = s["home_poss"].to_numpy(float), s["away_poss"].to_numpy(float)
    elif "possessions" in s:
        hp = ap = s["possessions"].to_numpy(float) / 2.0
    else:
        raise ValueError("nba_stints: no possessions. Needs: " + STINT_NEEDS)
    out = pd.DataFrame({"game_id": s["game_id"].astype(str).to_numpy(),
                        "home_pts": s["home_pts"].to_numpy(float), "away_pts": s["away_pts"].to_numpy(float),
                        "home_poss": hp, "away_poss": ap,
                        "garbage": s["garbage_time"].fillna(False).astype(bool).to_numpy()
                        if "garbage_time" in s else False})
    norm = np.vectorize(_norm_id, otypes=[object])
    hi, ai = norm(hi), norm(ai)
    for j in range(5):
        out[f"h{j}"], out[f"a{j}"] = hi[:, j], ai[:, j]
    idc = [f"h{j}" for j in range(5)] + [f"a{j}" for j in range(5)]
    ok = out[idc].notna().all(axis=1) & ~out["garbage"]
    out = out[ok].merge(games[["game_id", "season", "day"]], on="game_id")
    return out.drop(columns="garbage").reset_index(drop=True)


def ridge_with_prior(home: np.ndarray, away: np.ndarray, y_home: np.ndarray, y_away: np.ndarray,
                     w_home: np.ndarray, w_away: np.ndarray, prior_o: np.ndarray,
                     prior_d: np.ndarray, lam: float) -> tuple[np.ndarray, np.ndarray]:
    """Offence / defence adjusted plus-minus, penalised toward a prior.

    home, away: (n, 5) integer player indices; y_*: offensive efficiency of that
    side net of league, intercept and home; minimises
        sum w (y - (sum O_offence - sum D_defence))^2 + lam |b - b_prior|^2.
    Returns (O, D) for every index."""
    from scipy import sparse
    n, P = len(home), len(prior_o)
    r = np.arange(n)
    rows = np.concatenate([np.repeat(r, 5), np.repeat(r, 5), np.repeat(r + n, 5), np.repeat(r + n, 5)])
    cols = np.concatenate([home.ravel(), P + away.ravel(), away.ravel(), P + home.ravel()])
    vals = np.concatenate([np.ones(5 * n), -np.ones(5 * n), np.ones(5 * n), -np.ones(5 * n)])
    X = sparse.csr_matrix((vals, (rows, cols)), shape=(2 * n, 2 * P))
    y = np.concatenate([y_home, y_away])
    w = np.concatenate([w_home, w_away])
    b0 = np.concatenate([prior_o, prior_d])
    resid = y - X @ b0
    Xw = X.multiply(w[:, None]).tocsr()
    A = (X.T @ Xw).toarray() + lam * np.eye(2 * P)
    delta = np.linalg.solve(A, Xw.T @ resid)
    b = b0 + delta
    return b[:P], b[P:]


# ── hyperparameters, state ──────────────────────────────────────────────────

@dataclass
class State:
    hp: dict
    rates: EW
    minutes: Last
    team_pace: EW
    league: EW
    lg_rates: dict


def league_rates(panel: pd.DataFrame) -> dict:
    """Per season S: league per-100 rates of season S-1 (S itself for the first season)."""
    pl = panel[panel["has_stats"]]
    by = pl.groupby("season")[[*STATS, "poss"]].sum()
    out = {}
    for s in by.index:
        src = by.loc[s - 1] if (s - 1) in by.index else by.loc[s]
        out[int(s)] = {c: 100.0 * src[c] / src["poss"] for c in STATS}
    return out


def minutes_history(panel: pd.DataFrame, min_hl: float) -> pd.DataFrame:
    """Per played row: the time-weighted minutes and starter share AFTER that game."""
    pl = panel[panel["played"]][["player_id", "day", "minutes", "is_starter"]].sort_values(["player_id", "day"])
    e = pl.groupby("player_id")[["minutes", "is_starter"]].ewm(halflife=min_hl).mean()
    e = e.reset_index(level=0, drop=True).reindex(pl.index)
    return pl[["player_id", "day"]].assign(m=e["minutes"].to_numpy(), starter=e["is_starter"].to_numpy())


def build_state(w: World, hp: dict) -> State:
    pl = w.panel[w.panel["has_stats"]]
    rates = EW(pl, "player_id", [*STATS, "poss"], hp["hl"])
    mins = Last(minutes_history(w.panel, hp["min_hl"]), "player_id", ["m", "starter"])
    tg = w.tg[w.tg["pace"].notna()]
    team_pace = EW(tg.assign(pw=tg["pace"], one=1.0), "team", ["pw", "one"], hp["hl_pace"])
    lg = w.tg[w.tg["game_poss"].notna()].assign(key="L", pw=lambda d: d["pace"], one=1.0)
    league = EW(lg, "key", ["pts", "game_poss", "pw", "one"], hp["hl_lg"])
    return State(hp=hp, rates=rates, minutes=mins, team_pace=team_pace, league=league,
                 lg_rates=league_rates(w.panel))


def league_asof(st: State, day) -> pd.DataFrame:
    q = pd.DataFrame({"key": "L", "day": np.asarray(day, np.int64)})
    e = st.league.asof(q)
    return pd.DataFrame({"L": 100.0 * e["pts"] / e["game_poss"].replace(0, np.nan),
                         "pace_lg": e["pw"] / e["one"].replace(0, np.nan)}, index=q.index)


def player_x(st: State, q: pd.DataFrame) -> pd.DataFrame:
    """As-of features (FEATURES) plus minutes state for (player_id, day, season)."""
    q = q.reset_index(drop=True)
    r = st.rates.asof(q)
    mm = st.minutes.asof(q)
    K = st.hp["k"]
    seasons = q["season"].astype(int).to_numpy()
    first = min(st.lg_rates)
    out = pd.DataFrame(index=q.index)
    for c in STATS:
        lr = pd.Series({s: v[c] for s, v in st.lg_rates.items()})
        m = lr.reindex(seasons).fillna(lr[first]).to_numpy()
        out[c] = 100.0 * (r[c].to_numpy() + K * m / 100.0) / (r["poss"].to_numpy() + K)
    out["mpg"] = mm["m"].fillna(0.0).to_numpy() / 48.0
    out["starter"] = mm["starter"].fillna(0.0).to_numpy()
    out["prior_share"] = K / (r["poss"].to_numpy() + K)
    out["m"] = mm["m"].fillna(0.0).to_numpy()
    out["last_played"] = mm["last_day"].to_numpy(float)
    return out


# ── the box-score plus-minus fit ────────────────────────────────────────────

def box_design(w: World, st: State, game_ids) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
    """Per (game, team): [1, home, sum share*x own, -sum share*x opp] and efficiency
    net of the as-of league, with the minutes each player actually played."""
    gid = set(game_ids)
    pl = w.panel[w.panel["played"] & w.panel["game_id"].isin(gid)][
        ["game_id", "team", "player_id", "day", "season", "minutes"]].reset_index(drop=True)
    x = player_x(st, pl)
    share = 5.0 * pl["minutes"] / pl.groupby(["game_id", "team"])["minutes"].transform("sum")
    X = pd.DataFrame(x[list(FEATURES)].to_numpy() * share.to_numpy()[:, None], columns=FEATURES)
    X[["game_id", "team"]] = pl[["game_id", "team"]]
    X = X.groupby(["game_id", "team"], as_index=False)[list(FEATURES)].sum()
    t = w.tg[w.tg["game_id"].isin(gid) & w.tg["eff"].notna()][
        ["game_id", "team", "opp", "is_home", "eff", "game_poss", "day", "season"]]
    t = t.merge(X, on=["game_id", "team"]).merge(
        X.rename(columns={"team": "opp", **{f: f + "_o" for f in FEATURES}}), on=["game_id", "opp"])
    t = t.reset_index(drop=True)
    L = league_asof(st, t["day"])["L"].to_numpy()
    A = np.column_stack([np.ones(len(t)), t["is_home"].to_numpy(float), t[list(FEATURES)].to_numpy(),
                         -t[[f + "_o" for f in FEATURES]].to_numpy()])
    return A, t["eff"].to_numpy() - L, t["game_poss"].to_numpy(float), t


def fit_box(w: World, st: State, seasons) -> dict:
    g = w.games[w.games["season"].isin(list(seasons)) & (w.games["game_date"] >= TRAIN_FROM)]
    A, y, wt, _ = box_design(w, st, g["game_id"])
    b = ols(A, y, wt, ridge=1e-3)
    F = len(FEATURES)
    return {"c": float(b[0]), "h": float(b[1]), "bo": b[2:2 + F], "bd": b[2 + F:2 + 2 * F],
            "n_sides": int(np.isfinite(y).sum()), "seasons": sorted(int(s) for s in seasons)}


def hyper_seasons(season: int) -> tuple[list[int], int]:
    """(fit seasons, scored season) for the hyperparameters a season uses:
    fit on 2018-19..S-2, scored on S-1; 2019-20 and 2020-21 share the first
    possible fit (2018-19 -> 2019-20). Never season S itself."""
    if season <= HYPER_EVAL + 1:
        return [HYPER_FIT], HYPER_EVAL
    return list(range(FIRST_BOX, season - 1)), season - 1


def fit_hyper(w: World, fit_seasons=(HYPER_FIT,), eval_season: int = HYPER_EVAL,
              min_hl: float | None = None) -> dict:
    """Decay and shrinkage fit on `fit_seasons`, scored on `eval_season` (price-free).
    `min_hl` given: the minutes half-life is held at it (P(plays) roles depend on it)."""
    fit_seasons = list(fit_seasons)
    assert eval_season not in fit_seasons
    ev = w.tg[(w.tg["season"] == eval_season) & w.tg["eff"].notna()]
    report = {}
    best = None
    for hl in GRID_HL_LG:
        lg = EW(w.tg[w.tg["game_poss"].notna()].assign(key="L", pw=w.tg["pace"], one=1.0),
                "key", ["pts", "game_poss", "pw", "one"], hl)
        e = lg.asof(pd.DataFrame({"key": "L", "day": ev["day"].to_numpy()}))
        L = 100.0 * e["pts"].to_numpy() / e["game_poss"].to_numpy()
        mse = float(np.average((ev["eff"].to_numpy() - L) ** 2, weights=ev["game_poss"]))
        report[f"hl_lg={hl}"] = mse
        best = (mse, hl) if best is None or mse < best[0] else best
    hl_lg = best[1]
    best = None
    lgp = EW(w.tg[w.tg["game_poss"].notna()].assign(key="L", pw=w.tg["pace"], one=1.0),
             "key", ["pw", "one"], hl_lg)
    evh = ev[ev["is_home"] == 1.0].merge(ev[["game_id", "team", "day"]].rename(
        columns={"team": "opp"}), on=["game_id", "opp", "day"])
    lp = lgp.asof(pd.DataFrame({"key": "L", "day": evh["day"].to_numpy()}))
    for hp_ in GRID_HL_PACE:
        tp = EW(w.tg[w.tg["pace"].notna()].assign(pw=w.tg["pace"], one=1.0), "team", ["pw", "one"], hp_)
        ph = tp.asof(evh[["team", "day"]])
        pa = tp.asof(evh[["opp", "day"]].rename(columns={"opp": "team"}))
        pred = (ph["pw"] / ph["one"]).to_numpy() * (pa["pw"] / pa["one"]).to_numpy() / (lp["pw"] / lp["one"]).to_numpy()
        ok = np.isfinite(pred) & evh["pace"].notna().to_numpy()
        mse = float(np.mean((evh["pace"].to_numpy()[ok] - pred[ok]) ** 2))
        report[f"hl_pace={hp_}"] = mse
        best = (mse, hp_) if best is None or mse < best[0] else best
    hl_pace = best[1]
    pl = w.panel[w.panel["played"] & (w.panel["season"] == eval_season)]
    best = None
    for mh in (GRID_MIN_HL if min_hl is None else (min_hl,)):
        m = Last(minutes_history(w.panel, mh), "player_id", ["m"]).asof(pl)["m"]
        ok = m.notna()
        mse = float(np.mean((pl["minutes"][ok] - m[ok]) ** 2))
        report[f"min_hl={mh}"] = mse
        best = (mse, mh) if best is None or mse < best[0] else best
    min_hl = best[1]
    best = None
    fit_ids = w.games[w.games["season"].isin(fit_seasons) & (w.games["game_date"] >= TRAIN_FROM)]["game_id"]
    ev_ids = w.games[w.games["season"] == eval_season]["game_id"]
    for hl in GRID_HL:
        for K in GRID_K:
            st = build_state(w, {"hl": hl, "k": K, "hl_lg": hl_lg, "min_hl": min_hl, "hl_pace": hl_pace})
            A, y, wt, _ = box_design(w, st, fit_ids)
            b = ols(A, y, wt, ridge=1e-3)
            A2, y2, wt2, _ = box_design(w, st, ev_ids)
            ok = np.isfinite(A2).all(1) & np.isfinite(y2)
            mse = float(np.average((y2[ok] - A2[ok] @ b) ** 2, weights=wt2[ok]))
            report[f"hl={hl},k={K}"] = mse
            best = (mse, hl, K) if best is None or mse < best[0] else best
    return {"hl": best[1], "k": best[2], "hl_lg": hl_lg, "min_hl": min_hl, "hl_pace": hl_pace,
            "fit": fit_seasons, "scored": eval_season, "mse": report}


# ── availability: roster, the injury report, P(plays) ───────────────────────

def lead_bucket(hours) -> np.ndarray:
    h = np.asarray(hours, float)
    return np.where(h > 6.0, "far", np.where(h > 3.0, "mid", "near"))


def role_of(m) -> np.ndarray:
    m = np.asarray(m, float)
    return np.where(m >= ROLE_EDGES[1], "core", np.where(m >= ROLE_EDGES[0], "rotation", "bench"))


def injury_at(inj: pd.DataFrame, times: pd.DataFrame) -> pd.DataFrame:
    """Each team's LATEST SUBMITTED report among those known by T, a report
    being known INJURY_LAG after its printed time. game_id, team, player_id, status."""
    r = inj[inj["game_id"].isin(times["game_id"])][["game_id", "team", "report_ts", "player_id", "status"]]
    r = r.merge(times[["game_id", "T"]].drop_duplicates("game_id"), on="game_id")
    r = r[r["report_ts"] + INJURY_LAG <= r["T"]]
    sub = r[r["status"] != "NOT YET SUBMITTED"].groupby(["game_id", "team"])["report_ts"].max()
    r = r.merge(sub.rename("use_ts").reset_index(), on=["game_id", "team"])
    r = r[(r["report_ts"] == r["use_ts"]) & r["status"].isin(("Out", *LISTED)) & r["player_id"].notna()]
    r = r.assign(player_id=r["player_id"].astype(str))
    return r[["game_id", "team", "player_id", "status"]].drop_duplicates(["game_id", "team", "player_id"])


def report_known(inj: pd.DataFrame, times: pd.DataFrame) -> pd.Series:
    """game_id -> True when any report for the game is known by T."""
    r = inj[inj["game_id"].isin(times["game_id"])][["game_id", "report_ts"]].merge(
        times[["game_id", "T"]].drop_duplicates("game_id"), on="game_id")
    seen = set(r.loc[r["report_ts"] + INJURY_LAG <= r["T"], "game_id"])
    return times["game_id"].isin(seen)


def sides_of(gm: pd.DataFrame) -> pd.DataFrame:
    h = gm.assign(team=gm["home_team"], opp=gm["away_team"], is_home=1.0)
    a = gm.assign(team=gm["away_team"], opp=gm["home_team"], is_home=0.0)
    return pd.concat([h, a], ignore_index=True)[
        ["game_id", "season", "day", "tip", "T", "team", "opp", "is_home"]]


def roster(w: World, sides: pd.DataFrame) -> pd.DataFrame:
    """(game_id, team, player_id): everyone with a row for the team in its last
    ROSTER_GAMES games before this one whose latest row anywhere is this team."""
    s = sides[["game_id", "team", "day"]].merge(w.seq[["game_id", "team", "k"]], on=["game_id", "team"])
    parts = []
    for j in range(1, ROSTER_GAMES + 1):
        parts.append(s.assign(k_prev=s["k"] - j))
    s = pd.concat(parts, ignore_index=True)
    s = s[s["k_prev"] >= 0].merge(
        w.seq.rename(columns={"k": "k_prev", "game_id": "prev_game", "day": "prev_day"}),
        on=["team", "k_prev"])
    s = s[s["prev_day"] < s["day"]]
    rows = w.panel[["game_id", "player_id", "team"]].rename(columns={"game_id": "prev_game"})
    c = s.merge(rows, on=["prev_game", "team"])[["game_id", "team", "day", "player_id"]]
    c = c.drop_duplicates(["game_id", "team", "player_id"]).reset_index(drop=True)
    last = Last(w.panel[["player_id", "day", "team"]].rename(columns={"team": "last_team"}),
                "player_id", ["last_team"]).asof(c)
    c = c[(last["last_team"] == c["team"]).to_numpy()]
    return c[["game_id", "team", "player_id"]].reset_index(drop=True)


def availability(w: World, st: State, sides: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team, player) on the as-of roster or the as-of report."""
    times = sides[["game_id", "T"]].drop_duplicates("game_id")
    ros = roster(w, sides)
    rep = injury_at(w.inj, times)
    rows = ros.merge(rep, on=["game_id", "team", "player_id"], how="outer")
    rows["status"] = rows["status"].fillna("unlisted")
    rows = rows.merge(sides, on=["game_id", "team"])
    known = report_known(w.inj, times)
    rows["covered"] = rows["game_id"].isin(set(times.loc[known.to_numpy(), "game_id"]))
    x = player_x(st, rows[["player_id", "day", "season"]])
    rows = pd.concat([rows.reset_index(drop=True), x.reset_index(drop=True)], axis=1)
    rows["bucket"] = lead_bucket((rows["tip"] - rows["T"]).dt.total_seconds() / 3600.0)
    rows["role"] = role_of(rows["m"])
    return rows


def play_prob(play: dict, status, role, bucket) -> np.ndarray:
    """P(plays): Out 0; listed statuses and unlisted roles from the fitted tables."""
    status, role, bucket = (np.asarray(v, dtype=object) for v in (status, role, bucket))
    out = np.empty(len(status))
    for i, (s, r, b) in enumerate(zip(status, role, bucket)):
        if s == "Out":
            out[i] = 0.0
        elif s == "unlisted":
            out[i] = play["unlisted"].get((r, b), play["unlisted_all"])
        else:
            out[i] = play["listed"].get((s, b), play["listed_status"].get(s, 0.5))
    return out


def played_flags(w: World, rows: pd.DataFrame) -> np.ndarray:
    k = w.panel.loc[w.panel["played"], ["game_id", "player_id"]].assign(_p=True)
    return rows[["game_id", "player_id"]].merge(k, on=["game_id", "player_id"], how="left")["_p"].fillna(False).to_numpy(bool)


def play_observations(w: World, st: State, seasons) -> pd.DataFrame:
    """Prior-season evidence for P(plays): the as-of report at tip - 9h / 4.5h / 1h
    against who actually played. Price-free (no fetch involved)."""
    out = []
    for s in seasons:
        g = w.games[w.games["season"] == s]
        if g.empty:
            continue
        for b, hrs in BUCKET_REF_H.items():
            gm = g.assign(T=g["tip"] - pd.Timedelta(hours=hrs))
            av = availability(w, st, sides_of(gm))
            av = av[av["covered"]]
            out.append(pd.DataFrame({"season": s, "bucket": b, "status": av["status"].to_numpy(),
                                     "role": av["role"].to_numpy(), "played": played_flags(w, av)}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(
        columns=["season", "bucket", "status", "role", "played"])


def fit_play(obs: pd.DataFrame, season: int) -> dict:
    o = obs[obs["season"] < season]
    rate = lambda d: float((d["played"].sum() + 1.0) / (len(d) + 2.0))  # noqa: E731
    lst = o[o["status"].isin(LISTED)]
    unl = o[o["status"] == "unlisted"]
    return {"listed": {k: rate(d) for k, d in lst.groupby(["status", "bucket"])},
            "listed_status": {k: rate(d) for k, d in lst.groupby("status")},
            "unlisted": {k: rate(d) for k, d in unl.groupby(["role", "bucket"])},
            "unlisted_all": rate(unl) if len(unl) else 0.9,
            "n": int(len(o)), "seasons": sorted(int(x) for x in o["season"].unique())}


def reallocate(df: pd.DataFrame, key, col: str, cap: float, total: float = TEAM_MINUTES,
               iters: int = 12) -> np.ndarray:
    """Expected minutes scaled so each team sums to `total`, nobody above `cap`."""
    e = df[col].to_numpy(float).copy()
    g = df.groupby(key, sort=False).ngroup().to_numpy()
    for _ in range(iters):
        capped = e >= cap - 1e-9
        fixed = np.bincount(g, weights=np.where(capped, e, 0.0))
        free = np.bincount(g, weights=np.where(capped, 0.0, e))
        scale = np.where(free > 0, (total - fixed) / np.where(free > 0, free, 1.0), 1.0)
        e = np.where(capped, e, e * scale[g])
        if (e <= cap + 1e-9).all():
            break
        e = np.minimum(e, cap)
    return e


def minutes_cap(w: World, season: int) -> float:
    """The 99th percentile of a player's minutes in regulation games before `season`."""
    p = w.panel[w.panel["played"] & (w.panel["season"] < season)]
    tm = p.groupby(["game_id", "team"])["minutes"].transform("sum")
    reg = p[(tm - TEAM_MINUTES).abs() < 1.0]
    return float(np.percentile(reg["minutes"], 99)) if len(reg) else 44.0


# ── adjusted plus-minus on segments ─────────────────────────────────────────

def box_rating(box: dict, x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    X = x[list(FEATURES)].to_numpy(float)
    return X @ box["bo"], X @ box["bd"]


def stint_targets(st: State, box: dict, s: pd.DataFrame) -> pd.DataFrame:
    L = league_asof(st, s["day"])["L"].to_numpy()
    yh = 100.0 * s["home_pts"].to_numpy() / s["home_poss"].replace(0, np.nan).to_numpy() - (L + box["c"] + box["h"])
    ya = 100.0 * s["away_pts"].to_numpy() / s["away_poss"].replace(0, np.nan).to_numpy() - (L + box["c"])
    return s.assign(yh=yh, ya=ya)


def rapm_solve(st: State, box: dict, s: pd.DataFrame, at_day: int, season: int, lam: float,
               decay: bool = True) -> pd.DataFrame:
    """Deviation of the segment rating from the box rating at `at_day`, per player.

    `lam` is the ridge penalty (rapm_lambda's cross-validated choice); the
    time-decay rate of the segment weights is a separate number, from the
    rate half-life. (The first build reused `lam` for the decay rate, so the
    chosen penalty never reached the ridge, and with no decay the penalty was
    0 and the solve singular.)"""
    ids = pd.unique(s[[f"h{j}" for j in range(5)] + [f"a{j}" for j in range(5)]].to_numpy().ravel())
    idx = {p: i for i, p in enumerate(ids)}
    q = pd.DataFrame({"player_id": ids, "day": at_day, "season": season})
    o0, d0 = box_rating(box, player_x(st, q))
    home = np.vectorize(idx.get)(s[[f"h{j}" for j in range(5)]].to_numpy())
    away = np.vectorize(idx.get)(s[[f"a{j}" for j in range(5)]].to_numpy())
    decay_rate = 0.0 if not np.isfinite(st.hp["hl"]) else np.log(2.0) / st.hp["hl"]
    dec = np.exp(-decay_rate * (at_day - s["day"].to_numpy(float))) if decay else 1.0
    wh = np.nan_to_num(s["home_poss"].to_numpy(float)) * dec
    wa = np.nan_to_num(s["away_poss"].to_numpy(float)) * dec
    yh = np.nan_to_num(s["yh"].to_numpy(float))
    ya = np.nan_to_num(s["ya"].to_numpy(float))
    o, d = ridge_with_prior(home, away, yh, ya, wh, wa, o0, d0, lam)
    return pd.DataFrame({"player_id": ids, "do": o - o0, "dd": d - d0})


def rapm_lambda(st: State, box: dict, w: World, season: int) -> tuple[float, dict]:
    """Penalty by game-fold cross-validation on season-1's segments."""
    s = w.stints[w.stints["season"] == season - 1]
    if len(s) < 1000:
        return 2000.0, {"note": "fewer than 1,000 prior segments: default 2000"}
    s = stint_targets(st, box, s)
    start = int(w.games.loc[w.games["season"] == season - 1, "day"].min())
    fold = pd.factorize(s["game_id"])[0] % RAPM_FOLDS
    scores = {}
    for lam in RAPM_LAMBDAS:
        err = num = 0.0
        for f in range(RAPM_FOLDS):
            tr, te = s[fold != f], s[fold == f]
            dev = rapm_solve(st, box, tr, start, season - 1, lam, decay=False).set_index("player_id")
            ids_all = pd.unique(te[[f"h{j}" for j in range(5)] + [f"a{j}" for j in range(5)]].to_numpy().ravel())
            q = pd.DataFrame({"player_id": ids_all, "day": start, "season": season - 1})
            o0, d0 = box_rating(box, player_x(st, q))
            o = pd.Series(o0 + dev["do"].reindex(ids_all).fillna(0).to_numpy(), index=ids_all)
            d = pd.Series(d0 + dev["dd"].reindex(ids_all).fillna(0).to_numpy(), index=ids_all)
            H5 = te[[f"h{j}" for j in range(5)]].to_numpy()
            A5 = te[[f"a{j}" for j in range(5)]].to_numpy()
            ph = o.reindex(H5.ravel()).to_numpy().reshape(H5.shape).sum(1) - d.reindex(A5.ravel()).to_numpy().reshape(A5.shape).sum(1)
            pa = o.reindex(A5.ravel()).to_numpy().reshape(A5.shape).sum(1) - d.reindex(H5.ravel()).to_numpy().reshape(H5.shape).sum(1)
            wh, wa = te["home_poss"].to_numpy(float), te["away_poss"].to_numpy(float)
            okh, oka = np.isfinite(te["yh"]) & (wh > 0), np.isfinite(te["ya"]) & (wa > 0)
            err += float(np.sum(wh[okh] * (te["yh"].to_numpy()[okh] - ph[okh]) ** 2)
                         + np.sum(wa[oka] * (te["ya"].to_numpy()[oka] - pa[oka]) ** 2))
            num += float(wh[okh].sum() + wa[oka].sum())
        scores[lam] = err / max(num, 1e-9)
    best = min(scores, key=scores.get)
    return best, {"cv_mse": scores}


def segments_before(s: pd.DataFrame, day: int) -> pd.DataFrame:
    """Segments of games dated strictly before `day` (a refit never sees its own date)."""
    return s[s["day"] < day]


def rapm_table(w: World, st: State, box: dict, season: int) -> tuple[pd.DataFrame | None, dict]:
    """(refit_day, player_id, do, dd) for every refit of `season`; refit R uses
    segments of games dated before R (seasons S-1 and S)."""
    if w.stints is None:
        return None, {"note": "no segments"}
    lam, info = rapm_lambda(st, box, w, season)
    days = w.games.loc[w.games["season"] == season, "day"]
    if days.empty:
        return None, info
    cur = stint_targets(st, box, w.stints[w.stints["season"].isin([season - 1, season])])
    out = []
    for R in range(int(days.min()), int(days.max()) + 1, REFIT_DAYS):
        sub = segments_before(cur, R)
        if len(sub) < 200:
            continue
        out.append(rapm_solve(st, box, sub, R, season, lam).assign(refit_day=R))
    info.update({"lambda": lam, "refits": len(out)})
    return (pd.concat(out, ignore_index=True) if out else None), info


# ── the projection ──────────────────────────────────────────────────────────

@dataclass
class Model:
    season: int
    box: dict
    play: dict
    cap: float
    rapm: pd.DataFrame | None = None
    calib: dict | None = None
    f5: dict | None = None
    st: State | None = None
    info: dict = field(default_factory=dict)


def box_guard(w: World, gm: pd.DataFrame) -> np.ndarray:
    """True where every game dated before this one tipped at least FINAL_LAG before T."""
    daily = w.games.groupby("day")["tip"].max().sort_index()
    prev_max = daily.cummax()
    d = prev_max.index.to_numpy()
    i = np.searchsorted(d, gm["day"].to_numpy(np.int64), side="left") - 1
    last = pd.Series(pd.NaT, index=gm.index, dtype="datetime64[ns, UTC]")
    ok = i >= 0
    last[ok] = prev_max.to_numpy()[i[ok]]
    return (last.isna() | (last + FINAL_LAG <= gm["T"])).to_numpy()


def project(w: World, st: State, model: Model, gm: pd.DataFrame) -> pd.DataFrame:
    """Per game at its decision time T: raw and calibrated margin and total, F5 terms.

    `gm`: game_id, season, day, tip, home_team, away_team, T. The model's own
    state (its season's half-lives and shrinkage) is used when it carries one."""
    st = model.st or st
    gm = gm.reset_index(drop=True)
    sides = sides_of(gm)
    av = availability(w, st, sides)
    o, d = box_rating(model.box, av)
    av["o"], av["d"] = o, d
    if model.rapm is not None and len(model.rapm):
        refits = np.sort(model.rapm["refit_day"].unique())
        j = np.searchsorted(refits, av["day"].to_numpy(np.int64), side="right") - 1
        av["refit_day"] = np.where(j >= 0, refits[np.maximum(j, 0)], -1)
        dev = av[["player_id", "refit_day"]].merge(model.rapm, on=["player_id", "refit_day"], how="left")
        av["o"] = av["o"] + dev["do"].fillna(0.0).to_numpy()
        av["d"] = av["d"] + dev["dd"].fillna(0.0).to_numpy()
    av["p_play"] = play_prob(model.play, av["status"], av["role"], av["bucket"])
    av["e_min"] = av["p_play"] * av["m"]
    av["min_proj"] = reallocate(av, ["game_id", "team"], "e_min", model.cap)
    av = f5_player_terms(w, av)
    av["wo"] = av["min_proj"] / 48.0 * av["o"]
    av["wd"] = av["min_proj"] / 48.0 * av["d"]
    agg = {"O": ("wo", "sum"), "D": ("wd", "sum"), "n_players": ("player_id", "size"),
           "minutes": ("min_proj", "sum"), "covered": ("covered", "max"),
           **{f: (f, "sum") for f in F5_FEATURES}}
    t = av.groupby(["game_id", "team"], as_index=False).agg(**agg)
    t = sides.merge(t, on=["game_id", "team"], how="left")
    t["pace_t"] = (lambda e: e["pw"] / e["one"].replace(0, np.nan))(st.team_pace.asof(t[["team", "day"]]))
    b2b = w.tg[["game_id", "team", "b2b"]]
    t = t.merge(b2b, on=["game_id", "team"], how="left")
    hcols = ["O", "D", "pace_t", "b2b", "n_players", "minutes", *F5_FEATURES]
    hm = t[t["is_home"] == 1.0][["game_id", "covered", *hcols]].rename(columns={c: c + "_h" for c in hcols})
    aw = t[t["is_home"] == 0.0][["game_id", *hcols]].rename(columns={c: c + "_a" for c in hcols})
    out = gm.merge(hm, on="game_id", how="left").merge(aw, on="game_id", how="left")
    lg = league_asof(st, out["day"])
    out["L"], out["pace_lg"] = lg["L"].to_numpy(), lg["pace_lg"].to_numpy()
    c, h = model.box["c"], model.box["h"]
    eff_h = out["L"] + c + h + out["O_h"] - out["D_a"]
    eff_a = out["L"] + c + out["O_a"] - out["D_h"]
    pace = out["pace_t_h"] * out["pace_t_a"] / out["pace_lg"]
    out["raw_margin"] = pace * (eff_h - eff_a) / 100.0
    out["raw_total"] = pace * (eff_h + eff_a) / 100.0
    out["box_ok"] = box_guard(w, out)
    bad = ~out["box_ok"] | (out["n_players_h"].fillna(0) == 0) | (out["n_players_a"].fillna(0) == 0)
    out.loc[bad, ["raw_margin", "raw_total"]] = np.nan
    return apply_models(out, model)


def f5_player_terms(w: World, av: pd.DataFrame) -> pd.DataFrame:
    """Per player: tier from the as-of rating, starter, Questionable exposure, first game back."""
    av = av.copy()
    rot = av["m"] >= ROTATION_MIN
    net = (av["o"] + av["d"]).where(rot, -np.inf)
    rank = net.groupby([av["game_id"], av["team"]]).rank(ascending=False, method="first")
    tier = np.where(~rot, 3, np.where(rank <= TIER_RANKS[0], 1, np.where(rank <= TIER_RANKS[1], 2, 3)))
    miss = (1.0 - av["p_play"]) * av["m"] / 48.0
    for t in (1, 2, 3):
        av[f"miss_t{t}"] = np.where(tier == t, miss, 0.0)
    av["starters_out"] = np.where(av["starter"] >= 0.5, 1.0 - av["p_play"], 0.0)
    av["q_exposure"] = np.where(av["status"].isin(["Questionable", "Doubtful"]), av["m"] / 48.0, 0.0)
    # team games since his last game played for this team
    k_now = av[["game_id", "team"]].merge(w.seq[["game_id", "team", "k"]], on=["game_id", "team"], how="left")["k"]
    lp = pd.DataFrame({"team": av["team"].to_numpy(), "day": av["last_played"].to_numpy()})
    k_last = lp.merge(w.seq[["team", "day", "k"]].assign(day=lambda d: d["day"].astype(float)),
                      on=["team", "day"], how="left")["k"]
    missed = k_now.to_numpy(float) - k_last.to_numpy(float) - 1.0
    back = (missed >= FIRST_BACK_MISSED) & (av["status"] != "Out").to_numpy() & (av["m"] > 0).to_numpy()
    av["first_back"] = np.where(back, av["p_play"] * av["m"] / 48.0, 0.0)
    return av


def calib_design(df: pd.DataFrame, kind: str) -> np.ndarray:
    """Margin: [1, raw margin, b2b home, b2b away]. Total: the same on the raw
    total's distance from the as-of league total (league pace x 2 x league
    efficiency), so a scoring level that drifts between seasons is carried by
    the as-of league numbers, not by an intercept fit on older seasons."""
    raw = df["raw_margin"] if kind == "margin" else df["raw_total"] - league_total(df)
    return np.column_stack([np.ones(len(df)), raw, df["b2b_h"].fillna(0), df["b2b_a"].fillna(0)])


def league_total(df: pd.DataFrame) -> pd.Series:
    return df["pace_lg"] * 2.0 * df["L"] / 100.0


def f5_design(df: pd.DataFrame, kind: str) -> np.ndarray:
    f = [df[c + "_h"].fillna(0) - df[c + "_a"].fillna(0) if kind == "margin"
         else df[c + "_h"].fillna(0) + df[c + "_a"].fillna(0) for c in F5_FEATURES]
    return np.column_stack([np.ones(len(df)), *f])


def actuals(w: World, df: pd.DataFrame) -> pd.DataFrame:
    g = w.games.set_index("game_id")
    return pd.DataFrame({"margin": (g["home_score"] - g["away_score"]).reindex(df["game_id"]).to_numpy(),
                         "total": (g["home_score"] + g["away_score"]).reindex(df["game_id"]).to_numpy()},
                        index=df.index)


def fit_calibration(w: World, refs: pd.DataFrame) -> dict:
    a = actuals(w, refs)
    return {"margin": ols(calib_design(refs, "margin"), a["margin"]),
            "total": ols(calib_design(refs, "total"), a["total"] - league_total(refs)),
            "n": int(refs["raw_margin"].notna().sum()),
            "seasons": sorted(int(s) for s in refs["season"].unique())}


def fit_f5(w: World, refs: pd.DataFrame, calib: dict) -> dict:
    a = actuals(w, refs)
    rm = a["margin"] - calib_design(refs, "margin") @ calib["margin"]
    rt = a["total"] - league_total(refs) - calib_design(refs, "total") @ calib["total"]
    return {"margin": ols(f5_design(refs, "margin"), rm), "total": ols(f5_design(refs, "total"), rt),
            "seasons": sorted(int(s) for s in refs["season"].unique())}


def apply_models(df: pd.DataFrame, model: Model) -> pd.DataFrame:
    out = df.copy()
    if model.calib is not None:
        out["margin"] = calib_design(out, "margin") @ model.calib["margin"]
        out["total"] = league_total(out) + calib_design(out, "total") @ model.calib["total"]
    else:
        out["margin"], out["total"] = out["raw_margin"], out["raw_total"]
    if model.f5 is not None and model.calib is not None:
        out["margin5"] = out["margin"] + f5_design(out, "margin") @ model.f5["margin"]
        out["total5"] = out["total"] + f5_design(out, "total") @ model.f5["total"]
    else:
        out["margin5"], out["total5"] = np.nan, np.nan
    return out


def ref_games(w: World, season: int) -> pd.DataFrame:
    g = w.games[w.games["season"] == season]
    return g.assign(T=g["tip"] - REF_LEAD)


def prior_refs(refs: dict, season: int) -> list:
    """The walk-forward reference projections of every season before `season`."""
    return [refs[x] for x in sorted(refs) if x < season]


def build_models(w: World, st: State, last_season: int, refs_for=None, log=print,
                 obs_seasons=()) -> tuple[dict, dict, pd.DataFrame]:
    """Walk-forward models for FIRST_REF..last_season, and the price-free
    reference projections (T = tip - 60 min) the calibration is fit on.
    `st` is the first state (2018-19 -> 2019-20); its minutes half-life is kept
    for every season so the P(plays) evidence (roles) is one table. Each season
    then gets its own rate, league and pace half-lives and shrinkage, fit on
    the seasons before it (hyper_seasons)."""
    obs = play_observations(w, st, sorted(set(range(FIRST_BOX, last_season)) | set(obs_seasons)))
    models, refs, hps = {}, {}, {}
    refs_for = set(range(FIRST_REF, last_season)) if refs_for is None else set(refs_for)
    for s in range(FIRST_REF, last_season + 1):
        t0 = time.time()
        fs, ev = hyper_seasons(s)
        key = (tuple(fs), ev)
        if key not in hps:
            first = (tuple(st.hp["fit"]), st.hp["scored"])
            hps[key] = st.hp if key == first else fit_hyper(w, fs, ev, min_hl=st.hp["min_hl"])
        hp = hps[key]
        st_s = st if hp is st.hp else build_state(w, hp)
        box = fit_box(w, st_s, range(FIRST_BOX, s))
        m = Model(season=s, box=box, play=fit_play(obs, s), cap=minutes_cap(w, s), st=st_s)
        if w.stints is not None:
            m.rapm, m.info["rapm"] = rapm_table(w, st_s, box, s)
        prior = prior_refs(refs, s)
        if prior:
            pr = pd.concat(prior, ignore_index=True)
            pr = pr[pr["raw_margin"].notna()]
            m.calib = fit_calibration(w, pr)
            m.f5 = fit_f5(w, pr, m.calib)
        models[s] = m
        if s in refs_for:
            refs[s] = project(w, st_s, raw_model(m), ref_games(w, s))
        log(f"  model {s}: hyperparameters fit {hp['fit']} scored {hp['scored']} (rate hl {hp['hl']}, "
            f"k {hp['k']}, league hl {hp['hl_lg']}, pace hl {hp['hl_pace']}); box fit {box['seasons']}; "
            f"P(plays) fit {m.play['seasons']}; calibration {m.calib['seasons'] if m.calib else 'none'} "
            f"({time.time() - t0:.0f}s)")
    return models, refs, obs


def raw_model(m: Model) -> Model:
    """The same season's model without calibration or F5 (the reference projection)."""
    return Model(season=m.season, box=m.box, play=m.play, cap=m.cap, rapm=m.rapm, st=m.st)


# ── pricing (the harness's own functions) ───────────────────────────────────

def projection_resid(games: pd.DataFrame, proj: pd.DataFrame, margin: str = "margin",
                     total: str = "total") -> pd.DataFrame:
    """(season, market, resid): the result minus the projection, side A (the
    home margin, the total), one row per projected game. No price is read."""
    x = proj[["game_id", "season", margin, total]].merge(
        games[["game_id", "home_score", "away_score"]], on="game_id")
    hm = (x["home_score"] - x["away_score"]).to_numpy(float)
    tt = (x["home_score"] + x["away_score"]).to_numpy(float)
    out = pd.concat([
        pd.DataFrame({"season": x["season"].astype(int), "market": "spreads", "resid": hm - x[margin]}),
        pd.DataFrame({"season": x["season"].astype(int), "market": "totals", "resid": tt - x[total]}),
    ], ignore_index=True)
    return out[np.isfinite(out["resid"].to_numpy(float))].reset_index(drop=True)


def projection_dist(games: pd.DataFrame, proj: pd.DataFrame, margin: str = "margin",
                    total: str = "total") -> dict:
    """(season, market) -> the projection's OWN empirical error distribution at
    this decision point (§6.5 amendment, second): residuals of the same
    projection at the same point on seasons BEFORE S (H.dist_by_season). The
    residuals are passed uncentred; H.ResidDist re-centres them on zero (§6.5
    amendment, third), so the price keeps their spread and not their average
    miss, which the calibration already corrects. The
    first priced season has no earlier one at the point, so 2020-21 is priced
    on its own residuals (the harness's fallback); it is reported, never
    chosen on."""
    r = projection_resid(games, proj, margin, total)
    return H.dist_by_season(r, sorted(r["season"].unique())) if len(r) else {}


def fair_frame(proj: pd.DataFrame, dist: dict, margin: str = "margin", total: str = "total") -> pd.DataFrame:
    """(game_id, market, mu, sigma, p_home) for spreads, totals and the moneyline.

    `dist`: (season, market) -> the projection's own H.ResidDist (projection_dist);
    `sigma` carries it, so the harness prices every number through the
    empirical distribution. The moneyline is P(home margin > 0) with the tie
    mass removed (no ties in the NBA)."""
    p = proj[["game_id", "season", margin, total]].dropna()
    s = p["season"].astype(int)
    dsp = np.array([dist.get((x, "spreads")) for x in s], dtype=object)
    dto = np.array([dist.get((x, "totals")) for x in s], dtype=object)
    w, _, l = H.probs_any(p[margin].to_numpy(), dsp, np.zeros(len(p)))
    ph = w / np.where(w + l > 0, w + l, np.nan)
    obj = lambda a: pd.Series(a, index=p.index, dtype=object)  # noqa: E731
    f = pd.concat([
        pd.DataFrame({"game_id": p["game_id"], "market": "spreads", "mu": p[margin], "sigma": obj(dsp), "p_home": np.nan}),
        pd.DataFrame({"game_id": p["game_id"], "market": "totals", "mu": p[total], "sigma": obj(dto), "p_home": np.nan}),
        pd.DataFrame({"game_id": p["game_id"], "market": "h2h", "mu": np.nan,
                      "sigma": obj([None] * len(p)), "p_home": ph}),
    ], ignore_index=True)
    ok = np.where(f["market"] == "h2h", f["p_home"].notna(), f["mu"].notna() & f["sigma"].notna())
    return f[ok].reset_index(drop=True)


def mu_frame(proj: pd.DataFrame, margin: str, total: str) -> pd.DataFrame:
    """The projection as (game_id, market, mu) for spreads and totals (home margin, total)."""
    p = proj[["game_id", margin, total]]
    f = pd.concat([pd.DataFrame({"game_id": p["game_id"], "market": "spreads", "mu": p[margin]}),
                   pd.DataFrame({"game_id": p["game_id"], "market": "totals", "mu": p[total]})],
                  ignore_index=True)
    return f[f["mu"].notna()].reset_index(drop=True)


def gap_strength(neutral: pd.DataFrame, mu: pd.DataFrame, cons: pd.DataFrame) -> pd.DataFrame:
    """F5 (§6.5 amendment, third): the gap, in points, between the projection
    and the CONSENSUS number at T (`cons`, from consensus(): Pinnacle's number,
    else the deciding books' median), from the side's view (a consensus home
    -6.5 with a projected home margin of 9: +2.5 for home, -2.5 for away).

    The offered number plays no part: every book's offer on a side carries the
    same gap, and the harness then takes that side's best offer under the
    MARKET's fair line (run_cells with strength="strength"). Measured against
    each book's own number, a soft book's off-consensus line raised the gap:
    the refuted outlier mechanism. A game with no consensus number has no gap."""
    x = neutral.merge(mu.rename(columns={"mu": "proj"}), on=["game_id", "market"], how="left")
    x = x.merge(cons[["game_id", "market", "cons"]], on=["game_id", "market"], how="left")
    side_a = x["side"].isin(["home", "over"]).to_numpy()
    a_gap = np.where(x["market"] == "spreads", x["proj"] + x["cons"], x["proj"] - x["cons"])
    return x.assign(strength=np.where(side_a, a_gap, -a_gap)).drop(columns=["proj", "cons"])


def consensus(vis: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, cons, ref): the consensus number at T for spreads and
    totals (§6.5 amendment, third): Pinnacle's coherent number where it quotes
    one (ref "pinnacle"), else the median of the deciding books' coherent
    numbers (ref "median"). Spreads carry the home number. Every gap against
    the line is measured against it: F5's gap, F1b's projection-minus-line and
    predicted move, and F1b's close (the same number at the last pre-tip fetch).
    The first build took the deciding books' median even where Pinnacle quoted."""
    v = vis[vis["coherent"] & vis["market"].isin(["spreads", "totals"])]
    pin = v[v["book"] == H.SHARP].drop_duplicates(["game_id", "market"])[["game_id", "market", "line"]]
    med = v[v["book"].isin(H.BETTABLE)].groupby(["game_id", "market"], as_index=False)["line"].median()
    med = med.merge(pin[["game_id", "market"]], on=["game_id", "market"], how="left", indicator=True)
    med = med[med["_merge"] == "left_only"].drop(columns="_merge")
    out = pd.concat([pin.assign(ref="pinnacle"), med.assign(ref="median")], ignore_index=True)
    return out.rename(columns={"line": "cons"})[["game_id", "market", "cons", "ref"]]


def close_times(data: H.Data) -> pd.DataFrame:
    f = data.fetches[data.fetches["lead_min"] > 0].sort_values(["game_id", "fetch_at"])
    f = f.drop_duplicates("game_id", keep="last")
    return f.rename(columns={"fetch_at": "T"})[["game_id", "T"]].reset_index(drop=True)


def move_rows(mu: pd.DataFrame, dec: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    """x = projection's stored-side number - decision consensus; y = close - decision."""
    x = mu.merge(dec, on=["game_id", "market"]).merge(
        close.rename(columns={"cons": "close"}), on=["game_id", "market"], how="left")
    num = np.where(x["market"] == "spreads", -x["mu"], x["mu"])
    return x.assign(x=num - x["cons"], y=x["close"] - x["cons"])


def fit_move(rows: pd.DataFrame) -> dict:
    """Per market: (a, b) of y = a + b x, or None with fewer than MIN_FIT_ROWS rows."""
    out = {}
    for m, r in rows.groupby("market"):
        r = r[np.isfinite(r["x"]) & np.isfinite(r["y"])]
        out[m] = None if len(r) < MIN_FIT_ROWS else tuple(ols(np.column_stack([np.ones(len(r)), r["x"]]), r["y"]))
    return out


def move_strength(neutral: pd.DataFrame, mu: pd.DataFrame, dec: pd.DataFrame, coef: dict) -> pd.DataFrame:
    """F1b (§6.5 amendment, second): the PREDICTED MOVE of the consensus number,
    M = C - cons = a + b (projection's number - cons), in the bettor's favour.
    Spreads carry the home number, so home gains when it is predicted to fall
    (-M) and away when it rises (+M); over gains when the total is predicted to
    rise (+M), under when it falls (-M).

    The offered number plays no part: every book's offer on a side carries the
    same strength, and the harness then takes that side's best offer under the
    MARKET's fair line (run_cells with strength="strength"). The first build
    used the offered number minus the predicted close, which scores a soft
    book's off-consensus number even when no move is predicted: the refuted
    outlier mechanism."""
    x = mu.merge(dec, on=["game_id", "market"])
    x["x"] = np.where(x["market"] == "spreads", -x["mu"], x["mu"]) - x["cons"]
    ab = x["market"].map(lambda m: coef.get(m))
    a = np.array([v[0] if v is not None else np.nan for v in ab], float)
    b = np.array([v[1] if v is not None else np.nan for v in ab], float)
    x["move"] = a + b * x["x"]
    o = neutral.merge(x[["game_id", "market", "move"]], on=["game_id", "market"], how="left")
    sp = (o["market"] == "spreads").to_numpy()
    side_a = o["side"].isin(["home", "over"]).to_numpy()
    fav_a = np.where(sp, -o["move"], o["move"])
    return o.assign(strength=np.where(side_a, fav_a, -fav_a)).drop(columns="move")


# ── one family, one decision point ──────────────────────────────────────────

@dataclass
class PointInputs:
    point: str
    times: pd.DataFrame
    off: pd.DataFrame
    vis: pd.DataFrame
    neutral: pd.DataFrame       # offers priced at the MARKET's fair line (H.close_dist)
    proj: pd.DataFrame          # per game: season, margin, total, margin5, total5
    dist: dict | None = None    # F1: the projection's own error distribution (projection_dist)


def scored_only(c: pd.DataFrame) -> pd.DataFrame:
    """A rule family's offers on games its projection produced a number for.
    The harness reads a cell's population (bar 9's blind sides) from the
    games in `cand`, so a game with no number must not be there."""
    return c[c["strength"].notna()].reset_index(drop=True)


def family_frames(fam: str, pi: PointInputs, games: pd.DataFrame, f1b_coef: dict | None,
                  n_placebo: int = N_PLACEBO) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    """(cand, placebo frames) for one family at one point. Placebo run r shuffles
    the projection between games on the same date (rng seed r) and re-prices.

    F1 prices the projection through ITS OWN error distribution (pi.dist), never
    the market's. F1b and F5 are rule families: their strength is in points and
    their offers keep the market's fair pricing (pi.neutral), so the harness
    takes a side's best offer under the market's fair line.
    f1b_coef: {season: {market: (a, b) or None}} for THIS point (F1b only)."""
    rng = lambda r: np.random.default_rng(r)  # noqa: E731
    if fam == "F1":
        if not pi.dist:
            raise ValueError("F1 is priced through the projection's own error distribution "
                             "(projection_dist); none was given for point " + pi.point)
        fair = fair_frame(pi.proj, pi.dist)
        cand = H.fair_offers(pi.off, fair)
        pl = [H.fair_offers(pi.off, H.shuffle_within_date(fair, games, rng(r))) for r in range(n_placebo)]
        return cand, pl
    if fam == "F5":
        mu = mu_frame(pi.proj, "margin5", "total5")
        dec = consensus(pi.vis)
        cand = scored_only(gap_strength(pi.neutral, mu, dec))
        pl = [scored_only(gap_strength(pi.neutral, H.shuffle_within_date(mu, games, rng(r)), dec))
              for r in range(n_placebo)]
        return cand, pl
    if fam == "F1b":
        mu = mu_frame(pi.proj, "margin", "total")
        dec = consensus(pi.vis)
        coef = f1b_coef or {}
        cand = scored_only(move_strength_by_season(pi.neutral, mu, dec, coef, pi.proj))
        pl = [scored_only(move_strength_by_season(pi.neutral, H.shuffle_within_date(mu, games, rng(r)),
                                                  dec, coef, pi.proj))
              for r in range(n_placebo)]
        return cand, pl
    raise ValueError(fam)


def move_strength_by_season(neutral, mu, dec, coef_by_season: dict, proj) -> pd.DataFrame:
    """F1b strength with each season's own walk-forward move coefficients."""
    season = proj.set_index("game_id")["season"]
    parts = []
    for s, coef in coef_by_season.items():
        ids = set(season[season == s].index)
        if not ids:
            continue
        parts.append(move_strength(neutral[neutral["game_id"].isin(ids)], mu[mu["game_id"].isin(ids)],
                                   dec[dec["game_id"].isin(ids)], coef))
    rest = neutral[~neutral["game_id"].isin(set(season[season.isin(list(coef_by_season))].index))]
    parts.append(rest.assign(strength=np.nan))
    return pd.concat(parts, ignore_index=True)


def emit_family(fam: str, data: H.Data, inputs: dict, market_sig: dict, close, f1b_coef: dict | None,
                n_placebo: int = N_PLACEBO) -> tuple[list[dict], pd.DataFrame]:
    """Every cell of one family (run_cells rows) and its population counts.
    `market_sig`: the market's own pricing (H.close_dist), for closing-line
    value. The 95% gate at D, the real-side shares and the blind bets per real
    side are the harness's (run_cells, given this point's decision times).
    f1b_coef: {point: {season: {market: (a, b)}}} (F1b only)."""
    spec = FAMILIES[fam]
    rows, pop = [], []
    for p in spec["points"]:
        pi = inputs[p]
        coef = (f1b_coef or {}).get(p) if fam == "F1b" else None
        cand, placebo = family_frames(fam, pi, data.games, coef, n_placebo)
        sides = {m: list(SIDES2[m]) for m in spec["markets"]}
        rows += H.run_cells(data, fam, p, cand, pi.neutral, list(spec["cuts"]), sides, close=close,
                            sig=market_sig, placebo=placebo, strength=spec["strength"],
                            times=pi.times)
        pop.append(population(fam, p, data, pi, cand))
    n = len(rows)
    assert n == EXPECTED_CELLS[fam], (fam, n)
    return rows, pd.concat(pop, ignore_index=True)


def population(fam: str, point: str, data: H.Data, pi: PointInputs, cand: pd.DataFrame) -> pd.DataFrame:
    """Per season and cell side: games, games with a decision time, with a price,
    with a model number, and bets per cut (the harness's own choose()). Counts only."""
    spec = FAMILIES[fam]
    season = data.games.set_index("game_id")["season"].astype(int)
    seasons = sorted(season.unique())
    count = lambda ids: pd.Series(season.reindex(pd.unique(ids)).value_counts()).reindex(seasons, fill_value=0)  # noqa: E731
    priced = pi.off[pi.off["book"].isin(H.BETTABLE)]
    strength = spec["strength"]
    model_ok = cand[cand[strength].notna()] if strength in cand else cand.iloc[0:0]
    n_games = count(season.index)
    n_time = count(pi.times["game_id"])
    out = []
    for m in spec["markets"]:
        n_priced = count(priced.loc[priced["market"] == m, "game_id"])
        n_model = count(model_ok.loc[model_ok["market"] == m, "game_id"])
        cm = cand[cand["market"] == m]
        for side in SIDES2[m]:
            for k, cut in enumerate(spec["cuts"]):
                if strength == "ev":
                    b = H.choose(cm, cut, sides=[side])
                else:
                    b = H.choose(cm[cm[strength] >= cut], -np.inf, sides=[side])
                n_bets = count(b["game_id"])
                for s in seasons:
                    out.append({"family": fam, "point": point, "season": int(s), "market": m,
                                "side": side, "cut_index": k, "cut": cut, "games": int(n_games[s]),
                                "games_with_time": int(n_time[s]), "games_priced": int(n_priced[s]),
                                "games_with_model": int(n_model[s]), "bets": int(n_bets[s])})
    return pd.DataFrame(out)


def point_inputs(data: H.Data, point: str, w: World, st: State, models: dict,
                 market_sig: dict) -> PointInputs:
    """Decision times, offers and the projection at one decision point, every
    season; the market's fair pricing (market_sig = H.close_dist) and the
    projection's own error distribution at this point (projection_dist)."""
    times, off = H.point_offers(data, point)
    vis = H.visible(data.quotes, times)
    neutral = H.fair_offers(off, H.market_fair(vis, market_sig))
    gm = data.games.merge(times[["game_id", "T"]], on="game_id")
    gm = gm.merge(w.games[["game_id", "day"]], on="game_id")
    parts = []
    for s, g in gm.groupby("season"):
        if int(s) in models and len(g):
            parts.append(project(w, st, models[int(s)], g))
    proj = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["game_id", "season", "margin", "total", "margin5", "total5"])
    dist = projection_dist(data.games, proj) if len(proj) else {}
    return PointInputs(point, times, off, vis, neutral, proj, dist)


def f1b_coefficients(data: H.Data, inputs: dict, seasons) -> dict:
    """{point: {season S: {market: (a, b) or None}}}, each fit on priced seasons before S."""
    close = consensus(H.visible(data.quotes, close_times(data)))
    out = {}
    for p in FAMILIES["F1b"]["points"]:
        pi = inputs[p]
        rows = move_rows(mu_frame(pi.proj, "margin", "total"), consensus(pi.vis), close)
        rows = rows.merge(pi.proj[["game_id", "season"]], on="game_id")
        out[p] = {int(s): fit_move(rows[rows["season"] < s]) for s in seasons}
    return out


# ── the synthetic check (no real data) ──────────────────────────────────────

def synthetic_market(seed: int = 0, seasons=(2021, 2022, 2023, 2024, 2025, 2026), per_season: int = 6):
    """A small priced world: every decision point reached, every market quoted."""
    rng = np.random.default_rng(seed)
    games, quotes = [], []
    for s in seasons:
        for i in range(per_season):
            day = pd.Timestamp(f"{s - 1}-12-{1 + i // 2:02d}")    # two games a date
            tip = day + pd.Timedelta(hours=24)            # 00:00Z the next UTC day = 7 pm ET
            gid = f"S{s}_{i}"
            hs, as_ = int(rng.integers(95, 125)), int(rng.integers(95, 125))
            games.append({"game_id": gid, "season": s, "game_date": day.strftime("%Y-%m-%d"),
                          "tip": tip.tz_localize("UTC"), "home_team": "AAA", "away_team": "BBB",
                          "home_score": hs, "away_score": as_})
            fetches = [tip - pd.Timedelta(hours=9)] + [tip - pd.Timedelta(minutes=m) for m in (240, 120, 60, 20)]
            for f in fetches:
                for book in ("fanduel", "draftkings", "betmgm", "pinnacle"):
                    sp = float(rng.choice([-5.5, -4.5, -3.5]))
                    tot = float(rng.choice([219.5, 220.5, 221.5]))
                    base = {"game_id": gid, "season": s, "game_date": day.strftime("%Y-%m-%d"),
                            "tip": tip.tz_localize("UTC"), "book": book,
                            "fetch_at": f.tz_localize("UTC"), "snapshot_at": (f - pd.Timedelta(minutes=5)).tz_localize("UTC"),
                            "coherent": True}
                    quotes += [{**base, "market": "spreads", "line": sp, "price_a": -110.0, "price_b": -110.0},
                               {**base, "market": "totals", "line": tot, "price_a": -110.0, "price_b": -110.0},
                               {**base, "market": "h2h", "line": np.nan, "price_a": -180.0, "price_b": 155.0}]
    g = pd.DataFrame(games)
    q = pd.DataFrame(quotes)
    f = q[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"])
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60.0)
    return H.Data(games=g, quotes=q, fetches=f.reset_index(drop=True))


def synthetic_cells_check(n_placebo: int = 2, seasons=(2021, 2022, 2023, 2024, 2025, 2026),
                          per_season: int = 6) -> dict:
    """Every family through run_cells on a synthetic priced world; returns row counts.
    Nothing here reads real prices."""
    data = synthetic_market(seasons=seasons, per_season=per_season)
    sig = {(s, m): 12.0 if m == "spreads" else 18.0 for s in data.games["season"].unique()
           for m in ("spreads", "totals")}
    rng = np.random.default_rng(1)
    # the projection's own error distribution, from synthetic residuals (a
    # handful of games a season is below the empirical table's floor of 50)
    by_market = {m: H.ResidDist(rng.normal(0.0, 13.0 if m == "spreads" else 19.0, 2000), f"synthetic {m}")
                 for m in ("spreads", "totals")}
    own = {(int(s), m): d for s in data.games["season"].unique() for m, d in by_market.items()}
    inputs = {}
    for p in ("A", "B", "C", "D"):
        times, off = H.point_offers(data, p)
        vis = H.visible(data.quotes, times)
        neutral = H.fair_offers(off, H.market_fair(vis, sig))
        g = data.games[data.games["game_id"].isin(times["game_id"])]
        proj = pd.DataFrame({"game_id": g["game_id"], "season": g["season"],
                             "margin": rng.normal(4, 6, len(g)), "total": rng.normal(220, 8, len(g))})
        proj["margin5"], proj["total5"] = proj["margin"] + 1.0, proj["total"] - 1.0
        inputs[p] = PointInputs(p, times, off, vis, neutral, proj, own)
    coef = {p: {int(s): {"spreads": (0.0, 0.5), "totals": (0.0, 0.5)} for s in data.games["season"].unique()}
            for p in FAMILIES["F1b"]["points"]}
    close = H.pinnacle_close(data)
    counts = {}
    for fam in FAMILIES:
        rows, pop = emit_family(fam, data, inputs, sig, close, coef, n_placebo=n_placebo)
        counts[fam] = len(rows)
        assert pop["bets"].sum() > 0, fam
    assert counts == EXPECTED_CELLS, counts
    assert sum(counts.values()) == 228
    return counts


# ── smoke: the 2020-21 prices when the shared cache has no fetch ledger ─────

PULL_HOURS_FULL = (0, 1, 2, 3, 4, 15, 16, 17, 18, 19, 20, 21, 22, 23)
EVENING = tuple(range(15, 24))
# odds_history_pulls, sport NBA, 2020-12-01..2021-07-31, read through the
# Supabase MCP on 2026-10-17: 1,963 pulls; every date 2020-12-23..2021-05-16
# carries PULL_HOURS_FULL except these (03-06..03-08 have none).
PULL_EXCEPT_2021 = {"2020-12-21": (22,), "2020-12-22": EVENING, "2020-12-24": (0, 1, 2, 3, 4, 22),
                    "2020-12-25": EVENING, "2021-03-05": (0, 1, 2, 3, 4), "2021-03-06": (),
                    "2021-03-07": (), "2021-03-08": (), "2021-03-09": (22,), "2021-03-10": EVENING,
                    "2021-05-17": (0, 1, 2, 3, 4)}


def ledger_2021() -> pd.DataFrame:
    """When each 2020-21 fetch was ASKED FOR (requested_at = date + hour, as
    scripts/nba_research_cache.py builds it). pulled_at is set to requested_at,
    so no row joins on created_at and every row is placed by the harness's own
    fallback: the first fetch at or after its snapshot_at."""
    days = pd.date_range("2020-12-21", "2021-05-17", freq="D").strftime("%Y-%m-%d")
    req = [pd.Timestamp(f"{d}T{h:02d}:00:00Z") for d in days
           for h in PULL_EXCEPT_2021.get(d, PULL_HOURS_FULL)]
    assert len(req) == 1963, len(req)
    led = pd.DataFrame({"requested_at": req})
    return led.assign(pulled_at=led["requested_at"], rows=0, why="hourly (smoke reconstruction)")


def smoke_price_cache(cache: Path) -> tuple[Path, str]:
    if (cache / LEDGER_FILE).exists():
        return cache, "fetch ledger read from the cache"
    out = SMOKE_CACHE.resolve()
    assert out != cache.resolve() and cache.resolve() not in out.parents, "never write into the shared cache"
    out.mkdir(parents=True, exist_ok=True)
    for f in ("nba_games.parquet", "nba_odds.parquet"):
        src, dst = cache / f, out / f
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
    ledger_2021().to_parquet(out / LEDGER_FILE)
    return out, ("the cache has no fetch ledger: a copy of games and odds in "
                 f"{out} with the 2020-21 fetch hours from odds_history_pulls; every quote "
                 "placed by its snapshot time (the harness's fallback), not joined on created_at")


# ── modes ───────────────────────────────────────────────────────────────────

def refuse_full(cache: Path) -> list[str]:
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full after the price data is refreshed")
    if not (cache / STINTS_FILE).exists():
        why.append(f"{cache / STINTS_FILE} does not exist: these families are graded once, after the "
                   "lineup segments land")
    if not (cache / LEDGER_FILE).exists():
        why.append(f"{cache / LEDGER_FILE} does not exist: refresh the cache "
                   "(python -m scripts.nba_research_cache --only lines)")
    return why


def run_projection_setup(w: World, last_season: int, log=print, obs_seasons=()):
    t0 = time.time()
    hp = fit_hyper(w)
    log(f"first hyperparameters (fit {HYPER_FIT}, scored {HYPER_EVAL}): rate hl={hp['hl']} days, "
        f"k={hp['k']}, league hl={hp['hl_lg']} days, team pace hl={hp['hl_pace']} days, "
        f"minutes hl={hp['min_hl']} games ({time.time() - t0:.0f}s)")
    st = build_state(w, hp)
    models, refs, obs = build_models(w, st, last_season, log=log, obs_seasons=obs_seasons)
    return hp, st, models, refs, obs


def smoke(cache: Path) -> dict:
    """2020-21 only: counts and coverage, and the synthetic checks. No cell table."""
    H.check()
    counts = synthetic_cells_check()
    print(f"synthetic: cells per family {counts} (228 expected); nothing written")
    w = load_world(cache, max_season=max(SMOKE_SEASONS))
    print(f"world: {len(w.games):,} games, {len(w.panel):,} player rows, {len(w.inj):,} report rows, "
          f"segments {'present' if w.stints is not None else 'absent (box ratings only)'}")
    hp, st, models, refs, _ = run_projection_setup(w, max(SMOKE_SEASONS))
    price_cache, note = smoke_price_cache(cache)
    print("prices:", note)
    data = H.load(price_cache, seasons=list(SMOKE_SEASONS))
    print("price rows:", data.notes)
    close = H.pinnacle_close(data)
    market_sig = H.close_dist(close, data.games)
    inputs = {p: point_inputs(data, p, w, st, models, market_sig) for p in H.POINTS}
    coef = f1b_coefficients(data, inputs, SMOKE_SEASONS)
    out_dir = RESULTS / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    # what each distribution was built from (count and source, not its spread)
    label = lambda d: {f"{s} {m}": {"n": v.n, "from": v.label} for (s, m), v in sorted(d.items())}  # noqa: E731
    summary = {"hyper": {k: v for k, v in hp.items() if k != "mse"}, "price_note": note,
               "ratings": ratings_used(w, models, list(SMOKE_SEASONS))["by_season"],
               "price_rows": data.notes, "market_pricing": label(market_sig), "points": {}}
    for fam in FAMILIES:
        pops = []
        for p in FAMILIES[fam]["points"]:
            pi = inputs[p]
            cand, _ = family_frames(fam, pi, data.games, coef.get(p) if fam == "F1b" else None,
                                    n_placebo=0)
            pops.append(population(fam, p, data, pi, cand))
        pop = pd.concat(pops, ignore_index=True)
        pop.to_parquet(out_dir / f"population_{fam}.parquet")
        summary[fam] = pop.groupby(["point", "market"]).agg(
            games=("games", "first"), with_time=("games_with_time", "first"),
            priced=("games_priced", "first"), with_model=("games_with_model", "first")).reset_index().to_dict("records")
    for p, pi in inputs.items():
        pr = pi.proj
        cov = H.point_coverage(data, p, pi.times)
        summary["points"][p] = {"games_with_time": int(len(pi.times)),
                                "coverage": {s: round(v, 4) for s, v in cov.items()},
                                "harness_gate_drops": H.gated_seasons(cov, SMOKE_SEASONS, p)[1],
                                "projected": int(pr["margin"].notna().sum()) if len(pr) else 0,
                                "box_guard_failed": int((~pr["box_ok"]).sum()) if len(pr) else 0,
                                "report_known": int(pr["covered"].fillna(False).sum()) if len(pr) else 0,
                                "own_pricing": label(pi.dist or {})}
    print(json.dumps(summary, indent=1, default=str))
    return summary


def pd_baseline(w: World, season_rows: pd.DataFrame) -> pd.DataFrame:
    """Plain point differential as of the game: season-to-date mean margin and
    game total per team (games before the date), else last season's."""
    t = w.tg.copy()
    t["mg"] = t["pts"] - t["opp_pts"]
    t["tt"] = t["pts"] + t["opp_pts"]
    t = t.sort_values(["team", "day"])
    grp = t.groupby(["team", "season"])
    t["pd_std"] = grp["mg"].transform(lambda s: s.shift(1).expanding().mean())
    t["tt_std"] = grp["tt"].transform(lambda s: s.shift(1).expanding().mean())
    fin = t.groupby(["team", "season"])[["mg", "tt"]].mean().reset_index()
    fin["season"] = fin["season"] + 1
    t = t.merge(fin.rename(columns={"mg": "pd_prev", "tt": "tt_prev"}), on=["team", "season"], how="left")
    t["pd"] = t["pd_std"].fillna(t["pd_prev"])
    t["tt_asof"] = t["tt_std"].fillna(t["tt_prev"])
    h = t[t["is_home"] == 1.0][["game_id", "pd", "tt_asof"]]
    a = t[t["is_home"] == 0.0][["game_id", "pd", "tt_asof"]]
    x = season_rows[["game_id", "season"]].merge(h, on="game_id").merge(a, on="game_id", suffixes=("_h", "_a"))
    return x.assign(pd_diff=x["pd_h"] - x["pd_a"], tt_mean=(x["tt_asof_h"] + x["tt_asof_a"]) / 2.0)


SEGMENTS_USED = "box-score prior plus adjusted plus-minus from lineup segments"
BOX_ONLY = "box-score only"


def ratings_used(w: World, models: dict, seasons) -> dict:
    """What each season's player ratings were actually built from, read from
    the world and the fitted models, never assumed: {"label": one line for
    the run, "by_season": {S: line}}. A season uses the segments when its
    model carries at least one adjusted plus-minus refit (rapm_table); the
    first build hard-coded "box-score only" whatever the cache held."""
    per = {}
    for S in seasons:
        m = models[S]
        info = (m.info or {}).get("rapm") or {}
        if w.stints is None:
            per[S] = f"{BOX_ONLY} (no lineup segment file in the cache)"
        elif m.rapm is not None and len(m.rapm):
            extra = f"; {info['note']}" if info.get("note") else ""
            per[S] = (f"{SEGMENTS_USED} ({info.get('refits', 'unknown')} refits, "
                      f"penalty {info.get('lambda', 'unknown')}{extra})")
        else:
            why = info.get("note") or f"{info.get('refits', 0)} refits had 200 or more segments"
            per[S] = f"{BOX_ONLY} (segment file present, but {why})"
    used = [S for S in seasons if per[S].startswith(SEGMENTS_USED)]
    if w.stints is None:
        label = per[seasons[0]] if len(seasons) else f"{BOX_ONLY} (no lineup segment file in the cache)"
    elif len(used) == len(seasons):
        label = f"{SEGMENTS_USED}, every season"
    elif not used:
        label = f"{BOX_ONLY} every season (segment file present, no season had a refit)"
    else:
        label = (f"{SEGMENTS_USED} in {', '.join(str(s) for s in used)}; {BOX_ONLY} in "
                 f"{', '.join(str(s) for s in seasons if s not in used)}")
    return {"label": label, "by_season": per}


def quality(cache: Path) -> dict:
    """Price-free accuracy, 2021-22..2024-25, every number walk-forward. Never 2025-26."""
    w = load_world(cache, max_season=max(QUALITY_SEASONS))
    assert w.games["season"].max() <= max(QUALITY_SEASONS) and 2026 not in set(w.panel["season"])
    hp, st, models, refs, obs = run_projection_setup(w, max(QUALITY_SEASONS), log=print,
                                                     obs_seasons=QUALITY_SEASONS)
    # the last season's reference projection (build_models makes refs for S < last)
    s_last = max(QUALITY_SEASONS)
    refs[s_last] = project(w, st, raw_model(models[s_last]), ref_games(w, s_last))
    base = pd_baseline(w, pd.concat([ref_games(w, s) for s in range(FIRST_REF, s_last + 1)]))
    used = ratings_used(w, models, list(QUALITY_SEASONS))
    res = {"hyper": {s: {k: v for k, v in models[s].st.hp.items() if k != "mse"} for s in QUALITY_SEASONS},
           "hyper_mse_first": hp["mse"],
           "ratings": used["label"], "seasons": {}}
    for S in QUALITY_SEASONS:
        m = models[S]
        r = apply_models(refs[S], m)
        a = actuals(w, r)
        ok = r["margin"].notna()
        pr = base[base["season"] < S]
        pa = actuals(w, pr)
        bm = ols(np.column_stack([np.ones(len(pr)), pr["pd_diff"]]), pa["margin"])
        bt = ols(np.column_stack([np.ones(len(pr)), pr["tt_mean"]]), pa["total"])
        bs = base[base["season"] == S].set_index("game_id").reindex(r["game_id"])
        b_m = bm[0] + bm[1] * bs["pd_diff"].to_numpy()
        b_t = bt[0] + bt[1] * bs["tt_mean"].to_numpy()
        both = ok.to_numpy() & np.isfinite(b_m) & np.isfinite(b_t)
        e = lambda x, y: {"rmse": float(np.sqrt(np.mean((x[both] - y[both]) ** 2))),  # noqa: E731
                          "mae": float(np.mean(np.abs(x[both] - y[both])))}
        res["seasons"][S] = {
            "games": int(both.sum()), "of": int(len(r)),
            "margin_projection": e(r["margin"].to_numpy(), a["margin"].to_numpy()),
            "margin_point_diff": e(b_m, a["margin"].to_numpy()),
            "total_projection": e(r["total"].to_numpy(), a["total"].to_numpy()),
            "total_point_diff": e(b_t, a["total"].to_numpy()),
            "fit": {"box": m.box["seasons"], "calibration": m.calib["seasons"] if m.calib else None,
                    "p_plays": m.play["seasons"], "hyperparameters": [m.st.hp["fit"], m.st.hp["scored"]],
                    "ratings": used["by_season"][S]}}
    cal = []
    for S in QUALITY_SEASONS:
        play = models[S].play
        o = obs[obs["season"] == S]
        o = o.assign(p=play_prob(play, o["status"], o["role"], o["bucket"]))
        for (status, bucket), d in o[o["status"].isin(LISTED)].groupby(["status", "bucket"]):
            cal.append({"season": S, "status": status, "bucket": bucket, "n": int(len(d)),
                        "predicted": float(d["p"].mean()), "played": float(d["played"].mean())})
        for (role, bucket), d in o[o["status"] == "unlisted"].groupby(["role", "bucket"]):
            cal.append({"season": S, "status": "unlisted:" + role, "bucket": bucket, "n": int(len(d)),
                        "predicted": float(d["p"].mean()), "played": float(d["played"].mean())})
        lo = o[o["status"] != "Out"]
        res["seasons"][S]["p_plays_brier"] = float(np.mean((lo["p"] - lo["played"].astype(float)) ** 2))
        res["seasons"][S]["out_played_share"] = float(o.loc[o["status"] == "Out", "played"].mean())
    res["p_plays_calibration"] = cal
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "quality_projection.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "p_plays_calibration"}, indent=1, default=str))
    print(pd.DataFrame(cal).round(3).to_string())
    return res


def stints_short(cache: Path, seasons=STINT_SEASONS, floor: float = H.MIN_PRICED_SHARE) -> dict:
    """season -> share of its regular-season games with any lineup segment, for
    every season below `floor` (the harness's own stale-cache share). A file
    exported while the play-by-play load is still running would otherwise run
    the early seasons with segment ratings and the later ones on box ratings
    alone, without a sound."""
    g = H.load_games(cache)
    cols = ["game_id", "season_type"]
    s = pd.read_parquet(cache / STINTS_FILE)
    s = s[[c for c in cols if c in s]]
    if "season_type" in s:
        s = s[s["season_type"].astype(int) == REGULAR_SEASON_TYPE]
    has = g["game_id"].isin(set(s["game_id"].astype(str)))
    share = has.groupby(g["season"]).mean()
    return {int(x): round(float(share.get(x, 0.0)), 4) for x in seasons
            if float(share.get(x, 0.0)) < floor}


def refuse(lines: list[str]) -> None:
    for x in lines:
        print("REFUSED:", x)
    raise SystemExit(2)


def full(cache: Path) -> None:
    """The graded run. Cheap refusals first, then the hour-long projection:
    the go flag and the files; a stale price cache (H.load with every graded
    season required); a lineup-segment file missing a season the ratings read
    (2018-19 onward: season S's adjusted plus-minus reads S-1 and S)."""
    why = refuse_full(cache)
    if why:
        refuse(why)
    try:
        data = H.load(cache, seasons=list(GRADED), require_seasons=GRADED)
    except RuntimeError as e:
        refuse([str(e)])
    print("price rows:", data.notes)
    short = stints_short(cache)
    if short:
        refuse([f"{cache / STINTS_FILE} has segments on too few regular-season games in {short} "
                f"(need {H.MIN_PRICED_SHARE:.0%}): the play-by-play load is not finished or the "
                "cache predates it"])
    w = load_world(cache, max_season=max(GRADED))
    hp, st, models, refs, _ = run_projection_setup(w, max(GRADED))
    close = H.pinnacle_close(data)
    market_sig = H.close_dist(close, data.games)
    inputs = {p: point_inputs(data, p, w, st, models, market_sig) for p in H.POINTS}
    coef = f1b_coefficients(data, inputs, GRADED)
    RESULTS.mkdir(parents=True, exist_ok=True)
    for fam in FAMILIES:
        rows, pop = emit_family(fam, data, inputs, market_sig, close, coef)
        pd.DataFrame(rows).to_parquet(RESULTS / f"cells_{fam}.parquet")
        pop.to_parquet(RESULTS / f"population_{fam}.parquet")
        print(f"{fam}: {len(rows)} cells written")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="2020-21 only, counts and coverage, synthetic checks")
    g.add_argument("--quality", action="store_true", help="price-free accuracy, 2021-22..2024-25")
    g.add_argument("--full", action="store_true", help=f"every season; needs {GO_ENV}=1 and the segments")
    a = ap.parse_args()
    cache = H.CACHE
    if a.smoke:
        smoke(cache)
    elif a.quality:
        quality(cache)
    else:
        full(cache)


if __name__ == "__main__":
    main()

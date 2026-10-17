"""NBA game markets, second search: F4 (shooting-luck-adjusted ratings) and F6c
(late-season motivation). docs/nba_models_2026.md section 6.3, 38 cells.

This lab EMITS cells; scripts/nba_game2_verdict.py judges them. Every quote,
decision time, fair line, choice and grade comes from scripts/nba_game_harness
(H): load, point_offers, visible, market_fair, fair_offers, run_cells (which
calls choose and grade), pinnacle_close, close_dist, shuffle_within_date.
Nothing here prices, chooses or grades a bet. No cut, constant or rule below
was chosen by looking at a betting result.

F4  SHOOTING-LUCK-ADJUSTED RATINGS -- 32 cells
    spread, total x 2 sides x decision points A, C x gap >= 1, 2, 3, 4 points.

  Hypothesis (the premise, not a filter): the line follows each team's RAW
  points per 100 possessions, and part of that rating is shooting luck that
  does not persist. Opponent three-point % barely persists (split-half r = 0.12,
  The Ringer 2021-02-12, "make or miss"; year-to-year r = 0.225, Paine 2009,
  basketball-reference blog p=3475); a defence has little control over opponent
  free-throw % (KenPom, kenpom.com/blog/?p=98; MetricGate's luck-adjusted
  plus-minus strips it). Only those two are adjusted, as section 6.3 registers
  ("opponent three-point and free-throw percentage replaced by their
  expectation"). A team's OWN shooting is left as played: a term that pulled
  its own 3P% toward the league came from the build instructions, not 6.3,
  and was removed before any priced season was graded (section 6.4, second
  amendment of 2026-10-17). No tolerance on how closely the line tracks the
  raw rating is applied: that would be a parameter section 6.3 does not
  register.

  Inputs for a game on Eastern date D (decision A = 15Z on D, C = 60-180 min
  before tip): box scores (nba_player_game_log summed to team and opponent) of
  the SAME season's games with game_date < D. Conservative for C: an afternoon
  game final before an evening decision on the same date is left out.
    poss   = 0.5 x [(FGA - OREB + TOV + 0.44 FTA) + the same for the opponent]
             (Dean Oliver's possession estimate with Hollinger's 0.44)
    ORtg   = 100 x PTS / poss       DRtg = 100 x OPP_PTS / poss   (season to date)
    lg3, lgFT = league 3P% and FT% over the same season's games before D
    adjusted: opponent 3P% -> lg3, opponent FT% -> lgFT (points only; the
              possession count is left as played). The team's own points are
              not touched, so ORtg adjusted = ORtg raw; only DRtg moves.
  Projection for home H, away A, pace = mean of the two teams' possessions per
  game, lg = league points per 100 (identical raw and adjusted: the
  adjustments sum to zero over the league):
    margin = pace/100 x [(ORtg_H - DRtg_H) - (ORtg_A - DRtg_A)]   (+ home court: cancels in the gap)
    total  = pace/100 x [ORtg_H + DRtg_A + ORtg_A + DRtg_H - 2 lg]
  gap = adjusted - raw, in points. strength(home) = gap_margin, (away) =
  -gap_margin, (over) = gap_total, (under) = -gap_total. A cell bets its side
  where strength >= g, at the best deciding offer under the market's own fair
  line (H.market_fair -> H.fair_offers; run_cells(strength="strength")).
  Population filter (not a cut): both teams have >= 10 games this season,
  the CLAUDE.md section 3 early-season rule.

F6c LATE-SEASON MOTIVATION -- 6 cells
    spread, against the team in the situation x A, C x 3 situations (axis_situation).
    The situation is a CATEGORICAL axis: the verdict gives its values no
    neighbours (section 6.4, second amendment), so bar 7 for an F6c cell is
    its own ROI on the choosing seasons above zero. Each cell carries one cut
    (the 0/1 flag, cut 1.0, cut_index 0).

  Krieger, Pace, Clarke & Girdner 2015 (Financial Services Review 24(4), NBA
  2004-2012): teams that had locked a seed failed to cover. As of game date D,
  from `games` results with game_date < D and each team's season length from
  the schedule (nba_schedule, regular games: 72 in 2020-21, 82 since):
    W = wins so far, maxW = W + games remaining.
    seed_locked  every other conference team either certainly finishes above
                 (its W > this team's maxW) or certainly below (its maxW <
                 this team's W), and the fixed rank is a seed (1-10: the
                 play-in seeds count).
    eliminated   at least 10 conference teams certainly finish above (W >
                 this team's maxW): it cannot reach the play-in.
    tanking      D after the season's trade deadline (Eastern date, strictly
                 later), and the team's win % is among the league's three
                 lowest (ties at third included).
  Tie-breakers are approximated conservatively: wherever two teams could
  finish level, neither "certainly above" nor "certainly below" holds, so a
  tie that a tie-breaker would settle never makes a seed locked or a team
  eliminated. Ignoring games between the other teams makes both tests
  conservative too (a flag is never wrong; it can be late).
  Games where BOTH teams are in the situation have no side and are not bet.
  Trade deadlines (3 p.m. ET): 2021-03-25 (CBS Sports, Hoops Rumors),
  2022-02-10 (ESPN/ABC7), 2023-02-09 (NBC Sports, NBA.com tracker),
  2024-02-08 (NBA.com), 2025-02-06 (NBA.com, NBC), 2026-02-05 (NBA.com tracker).

  "Against the team" is home in some games and away in others, so each cell
  bets the per-game label "against": every game with exactly one team in the
  situation carries side_pick = the REAL side against that team (away when
  the team is at home, home when it is away), and H.choose keeps the offer
  on that real side. The data is never rewritten: every bet carries its real
  side (home / away), its stored home number and its real price, so the
  harness grades it, reports its home/away and favourite/underdog shares and
  runs bar 9's blind bets on real sides.
  Bar 9's population is every game priced at the point: the rule gives each
  game a number (1 = one team in the situation, 0 = neither or both), as
  section 6.4's second amendment defines it ("the games its model or rule
  produced a number for"). The comparison is therefore "does betting against
  the team in the situation beat betting that real side (home, away,
  favourite, underdog) on every game". run_cells' own blind_roi_choose for the
  label "against" is the cell itself at no cut; the verdict does not read it.

PLACEBO: 20 runs, rng seed = run number. One row per (game, market) carrying
  the family's number (F4: the signed gap; F6c: the 0/1 flag and its per-game
  side, which move together) is shuffled within date and market by
  H.shuffle_within_date, then re-attached to the same market-fair offers. The
  market's fair price is never shuffled.

PRICING: the market's fair line, the blind bets and closing-line value use
  the EMPIRICAL distribution of results around Pinnacle's closing number on
  seasons before S (H.close_dist; 2020-21 has none before it and uses its own,
  the harness's fallback, and is reported, never chosen on). Neither family
  prices from a model of its own: F4's gap and F6c's flag only choose which
  market-fair offers are taken.

WALK-FORWARD AND WHERE EACH CONSTANT COMES FROM: neither family fits
  anything. For every graded season S (2021-2026) F4's ratings and league
  averages and F6c's standings use only season S's games before the game date.
    Registered in section 6.3: the gap cuts 1, 2, 3, 4 points; decision
      points A and C; the three situation names; "against the team".
    From a published source or a project rule:
      0.44        Dean Oliver's possession estimate, Hollinger's coefficient
      10 games    the early-season rule, CLAUDE.md section 3 (population, not a cut)
    Lab definitions that section 6.3 does NOT fix (F6c's are recorded as such
    in section 6.4's second amendment, so they are not read as registered):
      "expectation" = the league's 3P% / FT% over the same season's games
                      before the date (F4)
      seed_locked   = a fixed rank among seeds 1-10 (play-in seeds count)
      eliminated    = at least 10 conference teams certainly finish above
      tanking       = among the league's three lowest win %, ties included,
                      only on dates strictly after the trade deadline
      the deadline dates themselves (each date is cited to a source above;
      using the deadline as the start of tanking is the lab's choice)
      the conservative tie rule (a possible tie never locks or eliminates)

    PYTHONPATH=. python -m scripts.nba_game2_luck --smoke [--harness-cache DIR]
    NBA_GAME2_GO=1 PYTHONPATH=. python -m scripts.nba_game2_luck --full
    PYTHONPATH=. python -m scripts.nba_game2_luck --quality   # price-free, 2022-2025 only

--harness-cache: the folder H.load reads (games, odds, fetch ledger); default
NBA_RESEARCH_CACHE. Box scores and the schedule always come from
NBA_RESEARCH_CACHE. Output: <results>/cells_F4.parquet, cells_F6c.parquet,
population_F4.parquet, population_F6c.parquet, where <results> is
NBA_GAME2_RESULTS; --smoke writes to <results>/smoke/ so the verdict, which
globs <results>/cells_*.parquet, never reads a smoke cell.
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

RESULTS = Path(os.environ.get("NBA_GAME2_RESULTS",
                              "C:/Users/micha/AppData/Local/Temp/nba_game_edge/results"))
SMOKE_SEASONS = (2021,)
FULL_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)     # 2021-2026: every season --full grades
QUALITY_SEASONS = (2022, 2023, 2024, 2025)          # never 2026
N_PLACEBO = 20

# F4
FTA_POSS = 0.44              # Oliver / Hollinger possession estimate
MIN_GAMES = 10               # CLAUDE.md section 3 early-season rule
F4_POINTS = ("A", "C")
F4_CUTS = (1.0, 2.0, 3.0, 4.0)
F4_SIDES = {"spreads": ["home", "away"], "totals": ["over", "under"]}

# F6c
F6C_POINTS = ("A", "C")
SITUATIONS = ("seed_locked", "eliminated", "tanking")
PLAYIN_SEEDS = 10
TANK_BOTTOM = 3
F6C_CUTS = (1.0,)
F6C_SIDES = {"spreads": ["against"]}                 # per-game label: the real side is side_pick
TRADE_DEADLINE = {2019: "2019-02-07", 2020: "2020-02-06", 2021: "2021-03-25",
                  2022: "2022-02-10", 2023: "2023-02-09", 2024: "2024-02-08",
                  2025: "2025-02-06", 2026: "2026-02-05"}
EAST = frozenset("ATL BKN BOS CHA CHI CLE DET IND MIA MIL NYK ORL PHI TOR WAS".split())
WEST = frozenset("DAL DEN GSW HOU LAC LAL MEM MIN NOP OKC PHX POR SAC SAS UTA".split())
CONF = {**{t: "E" for t in EAST}, **{t: "W" for t in WEST}}

EXPECTED_CELLS = {
    "F4": len(F4_POINTS) * sum(len(s) for s in F4_SIDES.values()) * len(F4_CUTS),
    "F6c": len(F6C_POINTS) * len(SITUATIONS) * sum(len(s) for s in F6C_SIDES.values()) * len(F6C_CUTS),
}
assert EXPECTED_CELLS == {"F4": 32, "F6c": 6}, EXPECTED_CELLS


# ── F4: team box scores and as-of ratings ───────────────────────────────────

BOX_COLS = {"points": "pts", "fg_att": "fga", "fg3_made": "fg3m", "fg3_att": "fg3a",
            "ft_made": "ftm", "ft_att": "fta", "offensive_reb": "oreb", "turnovers": "tov"}
STATS = list(BOX_COLS.values())


def team_box(box: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team): its box totals, its opponent's (opp_*), and the
    game's possessions. Only games in `games` (regular season, final)."""
    b = box[box["team"].notna() & (box["team"] != "NaN")]
    t = b.groupby(["game_id", "team"], as_index=False)[list(BOX_COLS)].sum().rename(columns=BOX_COLS)
    t = t.merge(games[["game_id", "season", "game_date", "home_team", "away_team"]], on="game_id")
    t = t[(t["team"] == t["home_team"]) | (t["team"] == t["away_team"])].copy()
    t["opp"] = np.where(t["team"] == t["home_team"], t["away_team"], t["home_team"])
    o = t[["game_id", "team", *STATS]].rename(columns={"team": "opp", **{c: f"opp_{c}" for c in STATS}})
    t = t.merge(o, on=["game_id", "opp"])

    def one(p):
        return t[f"{p}fga"] - t[f"{p}oreb"] + t[f"{p}tov"] + FTA_POSS * t[f"{p}fta"]

    t["poss"] = 0.5 * (one("") + one("opp_"))
    return t.drop(columns=["home_team", "away_team"]).reset_index(drop=True)


TEAM_SUMS = ["pts", "opp_pts", "opp_fg3m", "opp_fg3a", "opp_ftm", "opp_fta", "poss"]
LEAGUE_SUMS = ["pts", "fg3m", "fg3a", "ftm", "fta", "poss"]


def _before(targets: pd.DataFrame, cum: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """For each target row the last cumulative row with game_date STRICTLY
    before the target's date (same `by` keys)."""
    t = targets.assign(_d=pd.to_datetime(targets["game_date"])).sort_values("_d")
    c = cum.assign(_d=pd.to_datetime(cum["game_date"])).drop(columns="game_date").sort_values("_d")
    out = pd.merge_asof(t, c, on="_d", by=by, allow_exact_matches=False)
    return out.drop(columns="_d")


def as_of_ratings(tb: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Raw and luck-adjusted ratings for (season, team, game_date) targets, from
    that team's games in the same season with game_date < the target's date,
    and league averages over the same season's games before that date. Only
    the opponents' 3P% and FT% are replaced (section 6.3): the offence is
    left as played, so ortg_adj equals ortg_raw."""
    team = tb.groupby(["season", "team", "game_date"], as_index=False)[TEAM_SUMS].sum()
    team["n"] = 1.0
    team = team.sort_values(["season", "team", "game_date"])
    team[TEAM_SUMS + ["n"]] = team.groupby(["season", "team"])[TEAM_SUMS + ["n"]].cumsum()
    lg = tb.groupby(["season", "game_date"], as_index=False)[LEAGUE_SUMS].sum().sort_values(
        ["season", "game_date"])
    lg[LEAGUE_SUMS] = lg.groupby("season")[LEAGUE_SUMS].cumsum()
    lg = lg.rename(columns={c: f"lg_{c}" for c in LEAGUE_SUMS})
    x = _before(targets[["season", "team", "game_date"]], team, ["season", "team"])
    x = _before(x, lg, ["season"])
    x["n"] = x["n"].fillna(0.0)
    lg3 = x["lg_fg3m"] / x["lg_fg3a"]
    lgft = x["lg_ftm"] / x["lg_fta"]
    adj_opp = (x["opp_pts"] + 3.0 * (x["opp_fg3a"] * lg3 - x["opp_fg3m"])
               + (x["opp_fta"] * lgft - x["opp_ftm"]))
    x["ortg_raw"] = 100.0 * x["pts"] / x["poss"]
    x["drtg_raw"] = 100.0 * x["opp_pts"] / x["poss"]
    x["ortg_adj"] = x["ortg_raw"]
    x["drtg_adj"] = 100.0 * adj_opp / x["poss"]
    x["pace"] = x["poss"] / x["n"]
    x["lg_rtg"] = 100.0 * x["lg_pts"] / x["lg_poss"]
    return x[["season", "team", "game_date", "n", "pace", "lg_rtg",
              "ortg_raw", "drtg_raw", "ortg_adj", "drtg_adj"]]


def f4_projections(games: pd.DataFrame, tb: pd.DataFrame) -> pd.DataFrame:
    """Per game: raw and adjusted projected margin (no home court) and total,
    and the gaps. Games where either team has < MIN_GAMES are dropped."""
    g = games[["game_id", "season", "game_date", "home_team", "away_team"]]
    tg = pd.concat([g[["season", "game_date", "home_team"]].rename(columns={"home_team": "team"}),
                    g[["season", "game_date", "away_team"]].rename(columns={"away_team": "team"})])
    r = as_of_ratings(tb, tg.drop_duplicates())
    cols = ["n", "pace", "lg_rtg", "ortg_raw", "drtg_raw", "ortg_adj", "drtg_adj"]
    h = r.rename(columns={"team": "home_team", **{c: f"h_{c}" for c in cols}})
    a = r.rename(columns={"team": "away_team", **{c: f"a_{c}" for c in cols}}).drop(columns="a_lg_rtg")
    x = g.merge(h, on=["season", "game_date", "home_team"]).merge(a, on=["season", "game_date", "away_team"])
    x = x[(x["h_n"] >= MIN_GAMES) & (x["a_n"] >= MIN_GAMES)].copy()
    pace = 0.5 * (x["h_pace"] + x["a_pace"]) / 100.0
    for k in ("raw", "adj"):
        x[f"margin_{k}"] = pace * ((x[f"h_ortg_{k}"] - x[f"h_drtg_{k}"]) - (x[f"a_ortg_{k}"] - x[f"a_drtg_{k}"]))
        x[f"total_{k}"] = pace * (x[f"h_ortg_{k}"] + x[f"a_drtg_{k}"] + x[f"a_ortg_{k}"]
                                  + x[f"h_drtg_{k}"] - 2.0 * x["h_lg_rtg"])
    x["gap_margin"] = x["margin_adj"] - x["margin_raw"]
    x["gap_total"] = x["total_adj"] - x["total_raw"]
    return x.dropna(subset=["gap_margin", "gap_total"]).reset_index(drop=True)


def f4_signal(proj: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, market): `strength` = the gap toward side A (home, over)."""
    s = proj[["game_id"]].assign(market="spreads", strength=proj["gap_margin"])
    t = proj[["game_id"]].assign(market="totals", strength=proj["gap_total"])
    return pd.concat([s, t], ignore_index=True)


def side_strength(off: pd.DataFrame, signal: pd.DataFrame) -> pd.DataFrame:
    """Offers carrying the family's number in THAT side's favour: +signal for
    home / over, -signal for away / under. Offers without a number are dropped."""
    x = off.drop(columns=[c for c in ("strength",) if c in off]).merge(
        signal[["game_id", "market", "strength"]], on=["game_id", "market"], how="inner")
    a = x["side"].isin(["home", "over"])
    return x.assign(strength=np.where(a, x["strength"], -x["strength"]))


# ── F6c: as-of standings and situations ─────────────────────────────────────

def season_lengths(sched: pd.DataFrame) -> pd.DataFrame:
    """(season, team, n_games): each team's regular-season length from the schedule."""
    r = sched[sched["game_type"] == "regular"]
    n = pd.concat([r[["season", "home_team"]].rename(columns={"home_team": "team"}),
                   r[["season", "away_team"]].rename(columns={"away_team": "team"})])
    return n.groupby(["season", "team"]).size().rename("n_games").reset_index()


def standings(games: pd.DataFrame, lengths: pd.DataFrame) -> pd.DataFrame:
    """(season, game_date, team, w, l, remaining) for every date with a game and
    every team, from results with game_date STRICTLY before that date."""
    g = games[games["home_score"].notna()]
    hw = (g["home_score"] > g["away_score"]).astype(float)
    res = pd.concat([
        g[["season", "game_date"]].assign(team=g["home_team"], w=hw, l=1.0 - hw),
        g[["season", "game_date"]].assign(team=g["away_team"], w=1.0 - hw, l=hw)])
    res = res.groupby(["season", "team", "game_date"], as_index=False)[["w", "l"]].sum()
    res = res.sort_values(["season", "team", "game_date"])
    res[["w", "l"]] = res.groupby(["season", "team"])[["w", "l"]].cumsum()
    dates = games[["season", "game_date"]].drop_duplicates()
    teams = lengths[lengths["team"].isin(CONF)]
    grid = dates.merge(teams, on="season")
    x = _before(grid, res, ["season", "team"])
    x[["w", "l"]] = x[["w", "l"]].fillna(0.0)
    x["remaining"] = x["n_games"] - x["w"] - x["l"]
    x["conf"] = x["team"].map(CONF)
    return x.sort_values(["season", "game_date", "team"]).reset_index(drop=True)


def situations(st: pd.DataFrame) -> pd.DataFrame:
    """Adds seed_locked, eliminated, tanking (bools) to standings rows."""
    out = []
    for (season, d, _conf), grp in st.groupby(["season", "game_date", "conf"], sort=False):
        w = grp["w"].to_numpy()
        mx = w + grp["remaining"].to_numpy()
        above = (w[None, :] > mx[:, None]).sum(1)          # teams certainly finishing above row i
        below = (mx[None, :] < w[:, None]).sum(1)          # teams certainly finishing below row i
        locked = (above + below) == (len(grp) - 1)
        out.append(grp.assign(seed_locked=locked & (above + 1 <= PLAYIN_SEEDS),
                              eliminated=above >= PLAYIN_SEEDS))
    x = pd.concat(out).sort_values(["season", "game_date", "team"])
    pct = x["w"] / (x["w"] + x["l"]).where(x["w"] + x["l"] > 0)
    third = pct.groupby([x["season"], x["game_date"]]).transform(
        lambda p: np.sort(p.dropna().to_numpy())[TANK_BOTTOM - 1] if p.notna().sum() >= TANK_BOTTOM else -1.0)
    deadline = x["season"].map(TRADE_DEADLINE)
    after = deadline.notna() & (x["game_date"] > deadline.fillna("9999"))
    x["tanking"] = after & pct.notna() & (pct <= third)
    return x.reset_index(drop=True)


def game_situations(games: pd.DataFrame, sit: pd.DataFrame) -> pd.DataFrame:
    """Per game and situation: which team (if exactly one) is in it."""
    g = games[["game_id", "season", "game_date", "home_team", "away_team"]]
    s = sit[["season", "game_date", "team", *SITUATIONS]]
    x = g.merge(s.rename(columns={"team": "home_team", **{k: f"h_{k}" for k in SITUATIONS}}),
                on=["season", "game_date", "home_team"], how="left")
    x = x.merge(s.rename(columns={"team": "away_team", **{k: f"a_{k}" for k in SITUATIONS}}),
                on=["season", "game_date", "away_team"], how="left")
    rows = []
    for k in SITUATIONS:
        h = x[f"h_{k}"].fillna(False).astype(bool)
        a = x[f"a_{k}"].fillna(False).astype(bool)
        rows.append(x[["game_id", "season", "game_date"]].assign(
            situation=k, home_in=h, away_in=a, single=h ^ a, both=h & a))
    return pd.concat(rows, ignore_index=True)


def f6c_signal(neutral: pd.DataFrame, gs: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, market) at the point. Where exactly one team is in
    the situation: strength 1 and side_pick = the REAL side against it (away
    when it is at home, home when it is away). Elsewhere (neither team, or
    both): strength 0 and no side."""
    s = neutral[["game_id", "market"]].drop_duplicates()
    team_at_home = gs.loc[gs["single"]].set_index("game_id")["home_in"].astype(bool)
    pick = s["game_id"].map(team_at_home.map({True: "away", False: "home"}))
    return s.assign(strength=pick.notna().astype(float), side_pick=pick).reset_index(drop=True)


def f6c_offers(neutral: pd.DataFrame, signal: pd.DataFrame) -> pd.DataFrame:
    """Market-fair offers with F6c's flag and per-game side merged on, UNSIGNED:
    both sides of a game carry the same strength and side_pick, and H.choose
    keeps the offer whose real side is side_pick. (side_strength would negate
    the flag on the away side and cut every bet that goes away.)"""
    cols = ("strength", "side_pick")
    base = neutral.drop(columns=[c for c in cols if c in neutral])
    return base.merge(signal[["game_id", "market", *cols]], on=["game_id", "market"], how="left")


# ── one decision point ──────────────────────────────────────────────────────

def market_offers(data: H.Data, point: str, sig: dict, markets) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(times, neutral): every offer at the point priced at the market's own fair line."""
    t, off = H.point_offers(data, point)
    fair = H.market_fair(H.visible(data.quotes, t), sig)
    neutral = H.fair_offers(off, fair)
    return t, neutral[neutral["market"].isin(list(markets))].reset_index(drop=True)


def placebo_frames(neutral: pd.DataFrame, signal: pd.DataFrame, games: pd.DataFrame,
                   attach=side_strength) -> list[pd.DataFrame]:
    """N_PLACEBO re-priced candidate frames: the per-game number (and F6c's
    per-game side with it) shuffled within date and market (seed = run
    number), re-attached to the same offers by the family's own `attach`."""
    cols = ["game_id", "market", *[c for c in ("strength", "side_pick") if c in signal]]
    out = []
    for run in range(N_PLACEBO):
        sh = H.shuffle_within_date(signal[cols], games, np.random.default_rng(run))
        out.append(attach(neutral, sh))
    return out


def run_f4(data: H.Data, tb: pd.DataFrame, close, sig) -> tuple[list[dict], pd.DataFrame]:
    proj = f4_projections(data.games, tb)
    signal = f4_signal(proj)
    rows, pop = [], []
    for point in F4_POINTS:
        _, neutral = market_offers(data, point, sig, F4_SIDES)
        sig_pt = signal.merge(neutral[["game_id", "market"]].drop_duplicates(), on=["game_id", "market"])
        cand = side_strength(neutral, sig_pt)
        pl = placebo_frames(neutral, sig_pt, data.games)
        got = H.run_cells(data, "F4", point, cand, neutral, F4_CUTS, F4_SIDES, close=close, sig=sig,
                          placebo=pl, strength="strength")
        rows += got
        pop.append(population(data.games, point, neutral, sig_pt, got))
    return rows, pd.concat(pop, ignore_index=True)


def run_f6c(data: H.Data, games_sit: pd.DataFrame, close, sig) -> tuple[list[dict], pd.DataFrame]:
    """The 6 F6c cells. `cand` (every priced game's offers, with the 0/1 flag
    and side_pick) is passed as run_cells' neutral frame too, because the
    per-game label "against" needs side_pick wherever the harness chooses."""
    rows, pop = [], []
    for point in F6C_POINTS:
        _, neutral = market_offers(data, point, sig, F6C_SIDES)
        for k in SITUATIONS:
            gs = games_sit[games_sit["situation"] == k]
            signal = f6c_signal(neutral, gs)
            cand = f6c_offers(neutral, signal)
            pl = placebo_frames(neutral, signal, data.games, attach=f6c_offers)
            got = H.run_cells(data, "F6c", point, cand, cand, F6C_CUTS, F6C_SIDES, close=close,
                              sig=sig, placebo=pl, strength="strength")
            for r in got:
                r["axis_situation"] = k
                r["bet_side_meaning"] = ("against the team in the situation; each bet carries "
                                         "its real side (home or away)")
            rows += got
            p = population(data.games, point, neutral, signal[signal["strength"] > 0], got)
            both = gs[gs["both"]].groupby("season").size()
            p["situation"] = k
            p["games_both_in_situation_not_bet"] = p["season"].map(both).fillna(0).astype(int)
            pop.append(p)
    return rows, pd.concat(pop, ignore_index=True)


def population(games: pd.DataFrame, point: str, neutral: pd.DataFrame, numbered: pd.DataFrame,
               cells: list[dict]) -> pd.DataFrame:
    """Per season and market at one point: games, games with a price, games with
    the family's number, and bets per cell side (counts only)."""
    gs = games.groupby("season").size().rename("games")
    out = []
    for c in cells:
        mk = c["market"]
        priced = neutral[neutral["market"] == mk].drop_duplicates("game_id").groupby("season").size()
        nm = numbered[numbered["market"] == mk].merge(games[["game_id", "season"]], on="game_id")
        nm = nm.drop_duplicates("game_id").groupby("season").size()
        for s in gs.index:
            bets = (c["n_2021"] if s == H.REGIME else c["n_confirm"] if s == H.CONFIRM
                    else c.get(f"n_{s}", 0))
            out.append({"point": point, "season": int(s), "market": mk, "side": c["side"],
                        "cut": c["cut"], "games": int(gs[s]), "games_priced": int(priced.get(s, 0)),
                        "games_with_number": int(nm.get(s, 0)), "bets": int(bets or 0)})
    return pd.DataFrame(out)


# ── price-free model quality (2022-2025 only) ───────────────────────────────

def quality(games: pd.DataFrame, tb: pd.DataFrame, seasons=QUALITY_SEASONS) -> pd.DataFrame:
    """Walk-forward accuracy of the raw and luck-adjusted projections against
    the result (no prices). Home court for season S = mean home margin over
    the seasons before S in `games`. Refuses 2026."""
    assert H.CONFIRM not in seasons, "2026 is never looked at"
    proj = f4_projections(games[games["season"].isin(seasons)], tb)
    proj = proj.merge(games[["game_id", "home_score", "away_score"]], on="game_id")
    margin = proj["home_score"] - proj["away_score"]
    total = proj["home_score"] + proj["away_score"]
    gm = games[games["season"] < max(seasons)]
    hca = {s: float((gm.loc[gm["season"] < s, "home_score"] - gm.loc[gm["season"] < s, "away_score"]).mean())
           for s in seasons}
    proj["hca"] = proj["season"].map(hca)
    rows = []
    for s, x in proj.assign(margin=margin, total=total).groupby("season"):
        r = {"season": int(s), "games": len(x), "hca_fit_on": f"<{s}", "hca": round(hca[s], 2)}
        for k in ("raw", "adj"):
            em = x["margin"] - (x[f"margin_{k}"] + x["hca"])
            et = x["total"] - x[f"total_{k}"]
            r[f"margin_mae_{k}"] = float(em.abs().mean())
            r[f"margin_rmse_{k}"] = float(np.sqrt((em ** 2).mean()))
            r[f"total_mae_{k}"] = float(et.abs().mean())
            r[f"total_rmse_{k}"] = float(np.sqrt((et ** 2).mean()))
        r["corr_gap_margin_vs_raw_miss"] = float(np.corrcoef(
            x["gap_margin"], x["margin"] - x["margin_raw"] - x["hca"])[0, 1])
        r["corr_gap_total_vs_raw_miss"] = float(np.corrcoef(x["gap_total"], x["total"] - x["total_raw"])[0, 1])
        rows.append(r)
    return pd.DataFrame(rows)


# ── synthetic checks (run by --smoke before any data is read) ────────────────

def synthetic_checks() -> None:
    """The spread-sign self-check and the F6c side rule, on one hand-built game.
    Run by --smoke and --full before any data is read."""
    H.check()
    tip = pd.Timestamp("2024-03-20T23:30:00Z")
    games = pd.DataFrame([{"game_id": "G", "season": 2024, "game_date": "2024-03-20", "tip": tip,
                           "home_team": "DET", "away_team": "BOS", "home_score": 100, "away_score": 110}])
    q = pd.DataFrame([{"game_id": "G", "season": 2024, "game_date": "2024-03-20", "tip": tip,
                       "market": "spreads", "book": "fanduel", "snapshot_at": tip - pd.Timedelta(minutes=70),
                       "fetch_at": tip - pd.Timedelta(minutes=60), "line": 6.5, "price_a": -105.0,
                       "price_b": -115.0, "coherent": True}])
    f = pd.DataFrame({"game_id": ["G"], "tip": [tip], "fetch_at": [tip - pd.Timedelta(minutes=60)],
                      "lead_min": [60.0]})
    d = H.Data(games=games, quotes=q, fetches=f)
    _, off = H.point_offers(d, "C")
    gs = pd.DataFrame({"game_id": ["G"], "home_in": [True], "away_in": [False],
                       "single": [True], "both": [False]})
    cand = f6c_offers(off.assign(p_win=0.5, p_push=0.0), f6c_signal(off, gs))
    b = H.grade(H.choose(cand[cand["strength"] >= 1.0], -np.inf, sides=F6C_SIDES["spreads"]), d.games)
    # DET (home, +6.5, in the situation) lost by 10: the bet against it is the
    # real AWAY side, BOS -6.5 at -115, stored at the home number +6.5; it covers
    assert b[["side", "line", "price", "result"]].values.tolist() == [["away", 6.5, -115.0, "W"]], b
    st = pd.DataFrame({"season": 2024, "game_date": "2024-04-01", "conf": "E",
                       "team": list("ABCDEFGHIJKLMNO"), "w": [60] + list(range(40, 26, -1)),
                       "l": 0.0, "remaining": 2.0})
    st["l"] = 80 - st["w"]
    s = situations(st).set_index("team")
    assert bool(s.loc["A", "seed_locked"]) and not bool(s.loc["B", "seed_locked"])
    assert bool(s.loc["O", "eliminated"]) and not bool(s.loc["K", "eliminated"])
    print("synthetic checks pass")


# ── main ────────────────────────────────────────────────────────────────────

def write_cells(rows: list[dict], path: Path) -> None:
    """The cell table as parquet, with placebo_rois typed list<double> so a
    placebo run with no bets on the choosing seasons (ROI NaN) reads back as
    NaN. Left to pandas, a column whose lists are all NaN is stored as
    list<null> and reads back as None, which the verdict's np.isfinite cannot
    take."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    df = pd.DataFrame(rows)
    t = pa.Table.from_pandas(df.drop(columns="placebo_rois"), preserve_index=False)
    pl = pa.array([[float(x) for x in v] for v in df["placebo_rois"]],
                  type=pa.list_(pa.float64()), from_pandas=False)
    pq.write_table(t.append_column("placebo_rois", pl), path)


def _load_box(cache: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    box = pd.read_parquet(cache / "nba_player_game_log.parquet",
                          columns=["game_id", "team", *BOX_COLS])
    sched = pd.read_parquet(cache / "nba_schedule.parquet",
                            columns=["season", "game_type", "home_team", "away_team"])
    return box, sched


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true", help="2020-21 only, plus synthetic checks")
    mode.add_argument("--full", action="store_true", help="every season (needs NBA_GAME2_GO=1)")
    mode.add_argument("--quality", action="store_true", help="price-free accuracy, 2022-2025")
    ap.add_argument("--harness-cache", type=Path, default=H.CACHE,
                    help="folder H.load reads: nba_games, nba_odds, nba_fetch_ledger")
    a = ap.parse_args(argv)
    if a.full and os.environ.get("NBA_GAME2_GO") != "1":
        raise SystemExit("--full refused: set NBA_GAME2_GO=1 (the owner runs it after the price "
                         "data is refreshed)")
    if not a.quality:
        synthetic_checks()                       # the spread-sign self-check, smoke AND full
    box, sched = _load_box(H.CACHE)
    if a.quality:
        games = H.load_games(H.CACHE)
        games = games[games["season"] < H.CONFIRM]
        print(quality(games, team_box(box, games)).round(3).to_string(index=False))
        return
    if not (a.harness_cache / "nba_fetch_ledger.parquet").exists():
        raise SystemExit(f"{a.harness_cache} has no nba_fetch_ledger.parquet: refresh the cache "
                         "(scripts/nba_research_cache.py writes it) or pass --harness-cache")
    out = RESULTS / "smoke" if a.smoke else RESULTS
    out.mkdir(parents=True, exist_ok=True)
    if a.smoke:
        data = H.load(a.harness_cache, seasons=SMOKE_SEASONS)
    else:
        # a graded run refuses a cache that prices too few games in any season
        # it grades, or whose rows match no purchase record (section 6.4)
        data = H.load(a.harness_cache, seasons=FULL_SEASONS, require_seasons=FULL_SEASONS)
    print("loaded", data.notes)
    close = H.pinnacle_close(data)
    sig = H.close_dist(close, data.games)          # the empirical distribution (section 6.4)
    tb = team_box(box, data.games)

    f4, pop4 = run_f4(data, tb, close, sig)
    assert len(f4) == EXPECTED_CELLS["F4"], len(f4)
    sit = situations(standings(data.games, season_lengths(sched)))
    f6, pop6 = run_f6c(data, game_situations(data.games, sit), close, sig)
    assert len(f6) == EXPECTED_CELLS["F6c"], len(f6)
    assert len(f4) + len(f6) == 38

    write_cells(f4, out / "cells_F4.parquet")
    write_cells(f6, out / "cells_F6c.parquet")
    pop4.to_parquet(out / "population_F4.parquet")
    pop6.to_parquet(out / "population_F6c.parquet")
    print(f"cells written to {out}: F4 {len(f4)}, F6c {len(f6)}")
    show = ["point", "season", "market", "side", "cut", "games", "games_priced", "games_with_number", "bets"]
    print(pop4[show].to_string(index=False))
    print(pop6[["situation", *show, "games_both_in_situation_not_bet"]].to_string(index=False))


if __name__ == "__main__":
    main()

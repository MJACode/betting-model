"""
NBA full-game totals, OVER only: the shooting-luck gap (`nba_total_luck`).

LIVE, real money (mike, 2026-10-17: "Find it ... edge like we have with other
sports"; CLAUDE.md section 2). The card that writes its picks is
scripts/nba_total_luck_card.py; the research it ships from is
docs/nba_models_2026.md sections 6.6 and 6.7.

THE IDEA. A team's points allowed per 100 possessions includes how well its
OPPONENTS happened to shoot threes and free throws, and a defence has little
control over either (opponent three-point % split-half r = 0.12, The Ringer
2021-02-12; year-to-year r = 0.225, Paine 2009; free throws: KenPom). The
market prices totals off the raw ratings. Replace those two percentages with
the league's rate so far this season and the projected total moves; when the
luck-adjusted projection is at least 3 points ABOVE the raw one, the over has
been underpriced.

THE EVIDENCE (family F4, decision point C, gap >= 3, the over; graded by
scripts/nba_game2_luck.py through scripts/nba_game_harness.py at bought
prices, every graded season pooled, the house standard of section 6.7):

    2021-22..2025-26   508 bets   +55.6 units   +10.1%   95% interval +2.0..+18.3
    seasons positive   5 of 5 (2020-21, never chosen on, lost 10.4% on 103)
    record             290-214-4
    prices             -115 to +100, median -110
    neighbours         gap >= 2 +5.9%, gap >= 4 +13.6% (210 bets)
    closing value      median -2.23% (the blind over at the same moment -2.41%)
    DraftKings alone   +8.2% on 425 bets (choosing seasons), +7.0% in 2025-26

It FAILED the stricter bars of section 6.4 (closing-line value; 2025-26 alone
has 82 bets here against the 200 a one-season confirmation needs), and only 6 of
422 cells cleared the 95% interval against about 10.6 expected by chance.
What makes it credible is its shape: the return rises with the gap at every
decision time, every graded season is positive, and the mechanism is
published. It is judged on its live record.

THE RULE, per regular-season game:
  1. RATINGS (the functions below, moved here from the lab so the lab and the
     live model share ONE copy): every final game of the SAME season with
     game_date before the game's Eastern date, summed from box scores.
       poss  = 0.5 x [(FGA - OREB + TOV + 0.44 FTA) + the same for the opponent]
       ORtg  = 100 x points / poss        DRtg = 100 x points allowed / poss
     Luck-adjusted DRtg replaces the opponents' made threes and made free
     throws with their attempts times the league's 3P% and FT% over the same
     season's games before the date. The offence is left as played.
     EVERY scheduled game of the season before the date must have its final
     score and both teams' box scores, and each team's box points must add up
     to its final score, as every game did in the lab; else the game is
     declined, 'score_missing', 'box_missing' or 'box_mismatch'
     (missing_inputs). Only regular-season games count, as in the lab: a game
     the schedule does not list counts only on a regular-season day with no
     other kind of game on it, so the NBA Cup final never does
     (regular_season).
  2. PROJECTION: pace = mean of the two teams' possessions per game;
       total = pace/100 x [ORtg_H + DRtg_A + ORtg_A + DRtg_H - 2 x league rating]
     gap = adjusted total - raw total, in points.
  3. BOTH TEAMS NEED 10+ GAMES this season (CLAUDE.md section 3). The first
     bets therefore come in mid-November.
  4. DECISION TIME (decision point C: "the newest fetch 60-180 minutes before
     tip"): the newest fetch, when it landed 60 to 66 minutes before tip and
     is at most 5 minutes old (timing below). A job of its own makes that
     fetch: scheduler.run_nba_total_luck_window runs every minute, 24x7, and
     when an undecided game is 61-66 minutes from tip it fetches the NBA board
     and runs the card (scripts/nba_total_luck_window.py). The first tick in
     the window decides, so a game on a whole-minute tip is decided on a fetch
     about 66 minutes out, and five more ticks follow if that one is skipped
     or fails. Until 2026-10-17 the card rode the refresh pass and decided
     only on the pass exactly 60 minutes out (73 or 103 minutes for afternoon
     tips), so a pass that never started lost the game: 27 of the 504 evening
     ticks over 2026-10-03..16 never started (production pipeline_runs, read
     2026-10-17). The lab's C fetch sat at exactly 60 minutes on 609 of
     611 bets; the same cell decided 45-75 minutes out (decision point D) made
     506 bets at +9.7% against C's +10.1% (docs/nba_models_2026.md 6.7), so a
     fetch 66 minutes out stays inside the graded effect. Each game is decided
     ONCE (the card's ledger); a later tick, a moved line or a better price
     writes nothing.
  5. THE OFFER (exactly the harness's): at decision time T, each book's newest
     quote from a fetch at or before T and no older than 60 minutes; the
     market's fair line is Pinnacle's no-vig total when Pinnacle quotes it
     coherently, else the median over the deciding books, priced through the
     EMPIRICAL distribution of final totals around Pinnacle's closing total on
     every earlier season (the artifact). Take the over at the book in
     config.BEST_LINE_BOOKMAKERS with the highest expected value under that
     fair line, at -200 or better (config.min_odds_for). A tie goes to the
     earlier book. The gap is the cut; the fair line only chooses the offer.
  6. BET when gap >= 3.0 (GAP_CUT). Overs only: the unders were mixed.

THE PROBABILITY (what model_probability holds): the market-fair probability
that the over WINS at the chosen line and price, PLUS the gap >= 3 bucket's
uplift, fitted walk-forward on seasons before the live one. Uplift =
(the bucket's realised win share) - (its mean market-fair win probability),
pushes counted in the denominator. For 2026-27 it is fitted on 2021-22 through
2025-26: 290 wins in 508 bets = 0.5709, against a mean fair probability of
0.5050, so the uplift is +0.0659 (scripts/nba_total_luck_build.py stores both
per season). The model decides on that number (config.MODELS_ON_OWN_PROBABILITY):
it has no record, so a promoted map would be the offset borrowed from other
models. Its EV floor (config.MODEL_OWN_EV_FLOOR, 0.00) is applied to the EV
WITH THE PUSH REFUNDED (p x decimal - 1 + P(push), the card's gate), because
the probability counts pushes in its denominator and a push on a whole-number
total returns the stake. On the 508 graded bets, at the 2026-27 uplift, that
EV is +0.011 at the smallest, +0.038 at the second smallest and +0.100 at the
median: the floor removes none of them. Counted the other way (a push as a
loss) one bet fell under zero, 2023-01-24 DEN at NOP, over 232.0 at -110:
-0.012 only because its 0.024 chance of a push was scored as a loss.

THE ARTIFACT (models/saved/, ARTIFACT_PATH): the residual sample (final total
minus Pinnacle's closing total, per season, 2020-21 to 2025-26) and the
per-season bucket counts. The live model and the replay of the lab read the
same rows, so they rank offers identically. It must be refitted before
2027-28: the card refuses a season the artifact does not end just before.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import config

MODEL_ID = "nba_total_luck"
SPORT = "NBA"
MARKET = "totals"
SIDE = "over"
GAP_CUT = 3.0
REFERENCE_BOOK = "draftkings"

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = "models/saved/nba_total_luck_20261017_090305.pkl"
ARTIFACT_KIND = "nba_total_luck"

# Decision point C is "the newest fetch 60-180 minutes before tip". Live, the
# game is decided on the newest fetch when it landed in [60, 66) minutes before
# tip, read at the rows' own created_at (the instant the fetch was stored, a few
# seconds after it was asked for, so the lead is never overstated). The window
# job (scripts/nba_total_luck_window.py) fetches when a game is 61-66 minutes
# out (a minute above the bottom, so a fetch that takes up to a minute to land
# still counts), so the first tick in the window decides and up to five more
# can. Pinned by tests/test_nba_total_luck.py against the job's own trigger:
# the window is at least two ticks wide.
DECISION_LEAD_MIN = (60.0, 66.0)
# A fetch older than this is not this tick's: the fetch step failed. Nothing is
# decided on it; the next tick fetches again.
STALE_FETCH_MAX_MIN = 5.0

# ── F4: team box scores and as-of ratings (moved from scripts/nba_game2_luck.py) ──

FTA_POSS = 0.44              # Oliver / Hollinger possession estimate
MIN_GAMES = 10               # CLAUDE.md section 3 early-season rule

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


# ── the artifact: the residual sample and the bucket's per-season counts ─────

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


def residual_frame(art: dict) -> pd.DataFrame:
    """(season, market, resid): final total minus Pinnacle's closing total."""
    r = pd.DataFrame(art["close_resid"], columns=["season", "resid"])
    return r.assign(season=r["season"].astype(int), market=MARKET)[["season", "market", "resid"]]


_DIST_CACHE: dict = {}


def pricing_dist(art: dict, season: int):
    """The empirical totals distribution the harness prices season `season`
    with: scripts.nba_game_harness.dist_by_season on the stored residuals,
    which uses the seasons BEFORE `season` (the lab's close_dist). Built once
    per artifact and season in a process (the table takes a few seconds)."""
    from scripts import nba_game_harness as H
    key = (art.get("built_at"), len(art["close_resid"]), int(season))
    if key not in _DIST_CACHE:
        d = H.dist_by_season(residual_frame(art), [int(season)]).get((int(season), MARKET))
        if d is None:
            raise ValueError(f"{MODEL_ID}: the artifact holds no residuals to price {season}")
        _DIST_CACHE[key] = d
    return _DIST_CACHE[key]


def uplift(art: dict, season: int) -> float:
    """The gap >= 3 bucket's realised win share minus its mean market-fair win
    probability, over the graded seasons before `season` (pushes in the
    denominator of both)."""
    rows = [v for s, v in art["bucket"].items() if int(s) < int(season)]
    n = sum(v["n"] for v in rows)
    if n == 0:
        raise ValueError(f"{MODEL_ID}: no graded bucket season before {season}")
    return (sum(v["wins"] for v in rows) - sum(v["sum_p_win"] for v in rows)) / n


def newest_season(art: dict) -> int:
    return int(max(int(s) for s, _ in art["close_resid"]))


# ── decision timing ──────────────────────────────────────────────────────────

def lead_minutes(tip: datetime, at: datetime) -> float:
    return (tip - at).total_seconds() / 60.0


def timing(tip: datetime, fetch_at: datetime, now: datetime) -> str:
    """Where a game stands on this run: 'decide', or why not. `fetch_at` is the
    game's newest stored fetch (odds.created_at).

    'too_late'    the fetch landed under 60 minutes before tip (or after it):
                  no decision is possible any more
    'too_early'   the fetch landed 66 or more minutes before tip: a later tick
                  fetches inside the window
    'stale_fetch' the fetch is more than 5 minutes old (the fetch step failed):
                  the next tick fetches again
    """
    lead = lead_minutes(tip, fetch_at)
    if lead < DECISION_LEAD_MIN[0] or fetch_at >= tip:
        return "too_late"
    if lead >= DECISION_LEAD_MIN[1]:
        return "too_early"
    if (now - fetch_at).total_seconds() / 60.0 > STALE_FETCH_MAX_MIN:
        return "stale_fetch"
    return "decide"


# ── the quotes ───────────────────────────────────────────────────────────────

QUOTE_ROW_COLS = ("game_id", "bookmaker", "market", "snapshot_type", "snapshot_at",
                  "created_at", "total_line", "over_price", "under_price", "over_link",
                  "under_link")


def quote_frame(rows: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Stored `odds` rows (QUOTE_ROW_COLS; the links may be absent) -> the
    harness's quote frame, through scripts.nba_game_harness.frame_quotes.

    The fetch instant is `created_at`: one odds fetch stores every book in
    one transaction, stamped with that transaction's start. In
    the archive the same instant comes from the purchase ledger, which the
    replay of the lab writes into created_at before calling this.
    Pre-game totals only ('open'); `games` carries season, game_date and tip.
    """
    from scripts import nba_game_harness as H
    o = rows[(rows["market"] == MARKET) & (rows["snapshot_type"] == "open")].copy()
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True, format="mixed")
    o["fetch_at"] = pd.to_datetime(o["created_at"], utc=True, format="mixed")
    for c in ("total_line", "over_price", "under_price"):
        o[c] = pd.to_numeric(o[c], errors="coerce")
    for c in ("spread_home", "home_price", "away_price"):
        o[c] = np.nan
    o["link_a"] = o["over_link"] if "over_link" in o else None
    o["link_b"] = o["under_link"] if "under_link" in o else None
    o = o.merge(games[["game_id", "season", "game_date", "tip"]], on="game_id")
    return H.frame_quotes(o, extra=("link_a", "link_b"))


# ── the decision ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TotalLuckBet:
    game_id: str
    season: int
    line: float                 # the total
    price: float                # the taken book's over price
    book: str
    gap: float                  # luck-adjusted minus raw projected total, points
    p_fair: float               # market-fair P(over wins) at this line
    p_push: float               # market-fair P(push) at this line
    ev_fair: float              # EV per unit risked under the market's fair line
    uplift: float               # the bucket's walk-forward uplift for the season
    p_model: float              # p_fair + uplift: model_probability
    fair_ref: str               # 'pinnacle' or 'consensus'
    fair_mu: float              # the market's fair centre for the total
    fetch_at: datetime          # T, the decision instant
    dk_price: float | None      # DraftKings' over at this number at T, else None
    link: str | None            # the taken book's betslip link
    dk_link: str | None


@dataclass(frozen=True)
class Decision:
    game_id: str
    fetch_at: datetime
    gap: float | None
    n_bets: int
    detail: str


DIAG_KEYS = ("games", "score_missing", "box_missing", "box_mismatch", "early_season",
             "gap_below_cut", "no_fair_line", "no_offer", "bets")

# ── completeness: the gap is the lab's only when every input game is present ─
#
# The gap reads TWO kinds of game: the two teams' own, and EVERY game of the
# season before the date (the league's 3P%, FT% and points per 100,
# as_of_ratings). The lab had all of them: in the research cache every
# regular-season game of 2018-19..2025-26 has a final score and a box score
# for both teams (measured 2026-10-17: 1,230 of 1,230 in each full season).
# Live, a game whose score or box has not landed simply drops out, and the gap
# moves with no sound: one other teams' box removed moved a 2025-26 gap from
# 2.992 (no bet) to 3.008 (a bet), and a missing previous night moved gaps by
# up to 0.68 points. So a game is decided only when, for EVERY scheduled
# regular-season game of its season before its Eastern date:
#   * the game has a final score (else 'score_missing'),
#   * a scored game has a box score for both teams (else 'box_missing'), and
#   * each team's box points add up to its final score (else 'box_mismatch').
#     A player-game stored twice (the results ingestor's 'espn:<id>' fallback
#     row and a later NBA.com row for the same player) or a box ESPN never
#     finished is summed into the team's possessions and ratings and into the
#     league's rates for the rest of the season. In the lab every team's box
#     added up: 19,038 of 19,038 team-games, 2018-19..2025-26 (research cache,
#     measured 2026-10-17), so this declines nothing the lab bet.
# A game ESPN reported postponed or cancelled (nba_schedule.status_text,
# written by data/ingestors/nba_results_ingestor.py or stats.nba.com's "PPD")
# was not played and is not owed. A game still unscored more than
# UNPLAYED_AFTER_DAYS before the date is presumed not played (a postponement
# nothing recorded): the results step retries every started unscored game all
# season, so a game played and still unscored after two weeks of passes has no
# score anywhere this system can read. It is counted in 'presumed_unplayed' and
# named in the card's log, so a gap computed without it is never silent.
# Placeholder rows (the NBA Cup knockout slots before their teams are known,
# home and away 'NaN') are not games.
UNPLAYED_AFTER_DAYS = 14
_POSTPONED = r"(?i)(?:ppd|postpon|cancel)"
_NOT_A_TEAM = {"", "NAN", "NONE", "NULL", "TBD"}


def _known_team(x) -> bool:
    return isinstance(x, str) and x.strip().upper() not in _NOT_A_TEAM


# ── the regular season: the lab's population, and nothing else ──────────────
#
# The lab's games are nba_games' regular-season rows: 1,230 a full season, the
# NBA Cup quarterfinals and semifinals included (they count in the standings),
# the Cup final never (it does not). Live, the `games` table also holds every
# event the odds feed quoted, under NBA_<date>_<away>_<home>, and nba_schedule
# (loaded by hand from a residential machine) lists the knockout games only as
# placeholders with no teams. For 2026-27 (production, read 2026-10-17):
# regular-season days 2026-10-20..2027-04-11, four quarterfinal and two
# semifinal placeholders typed 'regular' on 12-04, 12-05 and 12-08, and the
# final as 'cup_final' on 12-11. So a `games` row the schedule does not list
# counts as a regular-season game only when its date lies between the season's
# first and last regular-season days and no other kind of game is scheduled
# that day. No past date carried both (research cache, 2018-19..2026-27), so
# the rule drops no game the lab had; it drops the Cup final, and a preseason,
# play-in or playoff row the schedule has not caught up with.

def regular_season(rows: pd.DataFrame, days: pd.DataFrame) -> pd.DataFrame:
    """The rows of `games` that are regular-season games.

    rows  game_id, season, game_date and game_type: the type of the matching
          nba_schedule row, None when the schedule does not list the game
    days  season, game_date, game_type: the season's nba_schedule rows, of
          every type (placeholders included)
    A listed game counts when the schedule calls it 'regular'; an unlisted one
    as the comment above says. With no schedule for the season, nothing counts.
    """
    if rows is None or rows.empty:
        return rows
    d = days.assign(_d=days["game_date"].astype(str).str[:10],
                    season=pd.to_numeric(days["season"], errors="coerce"))
    reg = d[d["game_type"] == "regular"].groupby("season")["_d"].agg(["min", "max"])
    other = {(int(a), b) for a, b in
             d.loc[d["game_type"] != "regular", ["season", "_d"]].itertuples(index=False)}
    season = pd.to_numeric(rows["season"], errors="coerce")
    day = rows["game_date"].astype(str).str[:10]
    listed = rows["game_type"].notna()
    lo = season.map(reg["min"]).fillna("9999-12-31")
    hi = season.map(reg["max"]).fillna("0000-01-01")
    on_other = pd.Series([(int(a), b) in other if a == a else True
                          for a, b in zip(season, day)], index=rows.index, dtype=bool)
    keep = (listed & (rows["game_type"] == "regular")) | (
        ~listed & season.notna() & (day >= lo) & (day <= hi) & ~on_other)
    return rows[keep]


def scheduled_games(rows: pd.DataFrame) -> pd.DataFrame:
    """The season's scheduled regular-season games, one row per game_id:
    (game_id, game_date, postponed). `rows` may list a game twice (nba_schedule
    and games); a game is postponed when any row says so. Rows without two
    real teams are dropped."""
    cols = ["game_id", "game_date", "postponed"]
    if rows is None or rows.empty:
        return pd.DataFrame(columns=cols)
    r = rows[rows["home_team"].map(_known_team) & rows["away_team"].map(_known_team)].copy()
    st = r["status_text"] if "status_text" in r else pd.Series(None, index=r.index, dtype=object)
    r["postponed"] = st.fillna("").astype(str).str.contains(_POSTPONED, regex=True)
    r["game_date"] = r["game_date"].astype(str).str[:10]
    out = r.groupby("game_id", as_index=False).agg(game_date=("game_date", "min"),
                                                   postponed=("postponed", "any"))
    return out[cols]


def box_mismatches(final_games: pd.DataFrame, tb: pd.DataFrame) -> set[str]:
    """Boxed games where either team's summed box points differ from its final
    score (final_games' home_score / away_score)."""
    if tb.empty:
        return set()
    f = final_games[["game_id", "home_team", "away_team", "home_score", "away_score"]]
    m = tb[["game_id", "team", "pts"]].merge(f, on="game_id")
    score = pd.to_numeric(np.where(m["team"] == m["home_team"], m["home_score"],
                                   m["away_score"]), errors="coerce")
    bad = ~np.isclose(pd.to_numeric(m["pts"], errors="coerce"), score)
    return set(m.loc[bad, "game_id"])


def missing_inputs(targets: pd.DataFrame, scheduled: pd.DataFrame, final_games: pd.DataFrame,
                   tb: pd.DataFrame) -> dict[str, dict[str, list[str]]]:
    """game_id -> {'score_missing', 'box_missing', 'box_mismatch',
    'presumed_unplayed'}: the game ids of its season, before its Eastern date,
    that are owed and absent, or boxed wrong.

    scheduled    scheduled_games(...) for the season (every game, scored or not)
    final_games  the season's scored regular-season games, with their scores
    tb           team_box(box, final_games): a game is boxed only when both
                 teams' rows are there"""
    for c in ("home_score", "away_score"):
        if c not in final_games:
            raise ValueError(f"{MODEL_ID}: final_games needs {c} (the box-integrity check)")
    played = set(final_games["game_id"])
    boxed = set(tb["game_id"])
    wrong = box_mismatches(final_games, tb)
    sch = scheduled[~scheduled["game_id"].isin(played) & ~scheduled["postponed"]]
    sch_d = pd.to_datetime(sch["game_date"])
    # _d from the subset itself: assigning a Series to an EMPTY frame adopts the
    # Series' index (pandas 3), which filled this with the whole season as NaN.
    unboxed = final_games[~final_games["game_id"].isin(boxed)]
    unboxed = unboxed.assign(_d=unboxed["game_date"].astype(str).str[:10])
    mism = final_games[final_games["game_id"].isin(wrong)]
    mism = mism.assign(_d=mism["game_date"].astype(str).str[:10])
    out = {}
    for r in targets.itertuples(index=False):
        d = pd.Timestamp(str(r.game_date)[:10])
        before = sch[sch_d < d]
        old = pd.to_datetime(before["game_date"]) < d - pd.Timedelta(days=UNPLAYED_AFTER_DAYS)
        out[r.game_id] = {
            "score_missing": sorted(before.loc[~old, "game_id"]),
            "presumed_unplayed": sorted(before.loc[old, "game_id"]),
            "box_missing": sorted(unboxed.loc[unboxed["_d"] < str(d.date()), "game_id"]),
            "box_mismatch": sorted(mism.loc[mism["_d"] < str(d.date()), "game_id"]),
        }
    return out


def _named(ids: list[str], k: int = 3) -> str:
    more = f" +{len(ids) - k} more" if len(ids) > k else ""
    return f"{len(ids)} ({', '.join(ids[:k])}{more})"


def decide(targets: pd.DataFrame, quotes: pd.DataFrame, box: pd.DataFrame,
           final_games: pd.DataFrame, times: pd.DataFrame, art: dict, *,
           scheduled: pd.DataFrame,
           books=None, min_odds: float | None = None, gap_cut: float = GAP_CUT,
           bucket_uplift: float | None = None) -> tuple[list[TotalLuckBet], list[Decision], dict]:
    """The rule on frames. Pure given its inputs, so the card and the replay of
    the lab run the same code.

    targets      game_id, season, game_date, home_team, away_team (one season)
    quotes       the harness quote frame (scripts.nba_game_harness.frame_quotes),
                 totals, with link_a / link_b when the card has them
    box          nba_player_game_log rows (game_id, team and the BOX_COLS)
    final_games  the season's final regular-season games (game_id, season,
                 game_date, home_team, away_team, home_score, away_score)
    times        game_id, T: each game's decision instant
    scheduled    every scheduled regular-season game of the season, scored or
                 not (scheduled_games(...)): what the completeness check owes.
                 Required: without it nothing can tell a game that has not
                 landed from a game that was never played.
    bucket_uplift  the uplift to state the probability with; default the
                 artifact's, fitted on the seasons before this one. Only the
                 written probability depends on it, never which bet is taken.

    diag['presumed_unplayed'] lists the distinct games, over all targets, left
    out as presumed not played (UNPLAYED_AFTER_DAYS); the card logs them.
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
    gaps = dict(zip(proj["game_id"], proj["gap_total"]))
    missing = missing_inputs(targets, scheduled_games(scheduled), final_games, tb)

    t = times[times["game_id"].isin(set(targets["game_id"]))]
    q = quotes[(quotes["market"] == MARKET) & quotes["game_id"].isin(set(t["game_id"]))]
    vis = H.visible(q, t)
    off = H.offers(vis)
    fair = H.market_fair(vis, sig)
    neutral = H.fair_offers(off, fair)
    neutral = neutral[neutral["market"] == MARKET]
    cand = side_strength(neutral, f4_signal(proj))
    chosen = H.choose(cand[cand["strength"] >= gap_cut], -np.inf, books=books,
                      sides=[SIDE], floor=floor)
    by_game = {r.game_id: r for r in chosen.itertuples(index=False)}
    fair_by = {(r.game_id): r for r in fair[fair["market"] == MARKET].itertuples(index=False)}
    t_by = dict(zip(t["game_id"], t["T"]))

    bets, decisions = [], []
    presumed: set[str] = set()
    for g in targets.itertuples(index=False):
        gid = g.game_id
        if gid not in t_by:
            continue
        diag["games"] += 1
        T = t_by[gid]
        gap = gaps.get(gid)
        miss = missing[gid]
        presumed.update(miss["presumed_unplayed"])
        if miss["score_missing"]:
            diag["score_missing"] += 1
            decisions.append(Decision(gid, T, None, 0,
                                      f"score_missing:{_named(miss['score_missing'])}"))
            continue
        if miss["box_missing"]:
            diag["box_missing"] += 1
            decisions.append(Decision(gid, T, None, 0,
                                      f"box_missing:{_named(miss['box_missing'])}"))
            continue
        if miss["box_mismatch"]:
            diag["box_mismatch"] += 1
            decisions.append(Decision(gid, T, None, 0,
                                      f"box_mismatch:{_named(miss['box_mismatch'])}"))
            continue
        if gap is None:
            diag["early_season"] += 1
            decisions.append(Decision(gid, T, None, 0, "early_season: a team has under "
                                                         f"{MIN_GAMES} games"))
            continue
        if gap < gap_cut:
            diag["gap_below_cut"] += 1
            decisions.append(Decision(gid, T, float(gap), 0, f"gap_below_cut:{gap:.2f}"))
            continue
        if gid not in fair_by:
            diag["no_fair_line"] += 1
            decisions.append(Decision(gid, T, float(gap), 0, "no_fair_line"))
            continue
        c = by_game.get(gid)
        if c is None:
            diag["no_offer"] += 1
            decisions.append(Decision(gid, T, float(gap), 0, "no_offer"))
            continue
        dk = vis[(vis["game_id"] == gid) & (vis["book"] == REFERENCE_BOOK) & vis["coherent"]
                 & np.isclose(vis["line"], c.line)]
        dk_price = float(dk["price_a"].iloc[0]) if len(dk) else None
        dk_link = (dk["link_a"].iloc[0] if len(dk) and "link_a" in dk else None)
        fr = fair_by[gid]
        p_fair = float(c.p_win)
        bets.append(TotalLuckBet(
            game_id=gid, season=season, line=float(c.line), price=float(c.price), book=str(c.book),
            gap=float(gap), p_fair=p_fair, p_push=float(c.p_push), ev_fair=float(c.ev),
            uplift=float(up), p_model=float(p_fair + up), fair_ref=str(fr.ref),
            fair_mu=float(fr.mu), fetch_at=T, dk_price=dk_price,
            link=getattr(c, "link_a", None), dk_link=dk_link))
        diag["bets"] += 1
        decisions.append(Decision(gid, T, float(gap), 1, f"bet:{c.book} {c.line:g} {c.price:+.0f}"))
    diag["presumed_unplayed"] = sorted(presumed)
    return bets, decisions, diag

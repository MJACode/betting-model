"""
In-game NFL game lines, 2025: is any live full-game moneyline, spread or total
rule a bettable model?  (NFL edge search; the bought 2025 in-play lines.)

Run from the worktree root:
    PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_inplay_2025

No database, no network, no Odds API call. Reads the local cache only
(scripts/nfl_edge_lib.CACHE): inplay_2025.parquet, pbp_<season>.parquet,
nflverse_games.parquet, era5_kick_1999_2025.parquet, odds_hist_2020_2025.parquet.
Results are UNITS: one unit = one flat bet; a win at +150 pays +1.5u.

CONSTRUCTION - fixed before any 2025 price was compared with any outcome.

Data.  inplay_2025.parquet: full-game h2h / spreads / totals, one bulk
  historical call every 5 minutes from kickoff - 5 min to kickoff + 3h45m, all
  285 2025 games (272 REG + 13 POST). `snapshot_at` is the served snapshot; a
  quote is AS OF that time. spreads `point` = HOME handicap (home covers when
  home - away + point > 0); totals `point` = the live full-game total,
  price_home = over, price_away = under. VENUES (bettable): draftkings,
  fanduel, betmgm, williamhill_us, fanatics. bovada, mybookieag, betonlineag,
  lowvig, betus are offshore references and are never a venue.
  No per-book last_update was stored, so a quote's staleness is unknown and
  books suspend markets during plays: every result is an UPPER BOUND on what
  was bettable.

Game state at a snapshot.  The state after the LAST PLAY THAT ENDED at or before
  snapshot_at. A play's end = end_clock_time, else time_of_day + 5 s. A play
  never becomes known before an earlier play: known time = running max of the
  end times in game order (rows whose end time sits > 15 min off the centred
  rolling median of its neighbours are clock-entry errors and are dropped,
  counted). Only rows with a posteam (real plays) carry state.
  The state is built from that play's OWN row, post-play:
    score       total_home_score / total_away_score (post-play columns)
    clock       game_seconds_remaining of that play (its snap clock; the same
                definition is used in training, so the fitted models absorb
                the average run-off); the last play of a quarter -> the
                quarter boundary (2700 / 1800 / 900 / 0), since the quarter is
                then over
    possession  derived from the play's own outcome, never from a later row:
                TD -> the non-scoring team; PAT / 2-pt try, FG made, safety ->
                defteam (receives the kick); kickoff -> posteam (the receiver)
                unless fumble_lost; interception, fumble_lost, punt, FG missed
                or blocked, 4th down failed -> defteam; else posteam. The last
                play of the 2nd quarter -> the 2nd-half receiver (the team
                that did not receive the opening kickoff).
                Checked against the next play's posteam in training (printed).
  Snapshots with qtr > 4 (overtime) never open a bet; every bet is graded on
  the final result INCLUDING overtime (pushes return the stake; an NFL tie
  pushes a moneyline).

Best bettable price.  At one snapshot, across the five venues present:
  moneyline - the highest price for the side; spreads / totals - the best LINE
  first (most points for the side; lowest total for an over, highest for an
  under), then the best price at that line. DK cells use DraftKings only. The
  DK and best cells each find their own entries. No de-vig in any trigger:
  the implied probability includes the vig, because that is the price paid.

Training.  Every parameter below is fitted on 2016-2024 play-by-play
  (REG + POST, regulation plays only), final scores including overtime, and
  nflverse closing spread_line / total_line. 2025 never enters a fit.

H1  late-game leader underpricing (sportsbook version of the null Kalshi test).
  Empirical WP of the leader, smoothed: one logistic regression PER LEAD
  (4, 5, ..., 16 points) on every 2016-24 regulation state with <= 600 s left,
    logit P(leader wins) ~ 1 + t + ball + ball*t + fav + dog,  t = log(1 + secs)
  ball = leader has the ball; fav / dog = the LEADER's pregame band by the
  closing spread (favoured by >= 3.5 / underdog by >= 3.5; within 3.5 is the
  base). Target win 1 / tie 0.5 / loss 0 (fractional IRLS, ridge 1.0 on the
  slopes so 14-16 point leads with almost no losses stay finite).
  Second reference: nflverse vegas_home_wp + vegas_home_wpa (its post-play
  value). MEASURED after the run: on 48,486 2025 rows it equals the NEXT row's
  pre-snap vegas_home_wp exactly, i.e. it is a ONE-ROW LOOK-AHEAD (the next
  snap's clock, timeouts and field position). The ref=nflverse cells are kept
  for comparison with the Kalshi study but are not a clean test; the ref=pbp
  cells are.
  RULE: windows S in {600, 300} seconds left, leader up 4-16; edge = WP -
  implied(leader price); bet the leader at the FIRST snapshot with edge >= c,
  c in {0.02, 0.04, 0.06}; one bet per game per cell.

H2  live totals vs scoring pace.  OLS, fitted SEPARATELY for each window on the
  2016-24 states that window draws from:
    remaining = final total - points so far
      ~ 1 + f + TL*f + (pts - TL*(1-f))*f + |m|*f + |m| + Q2 + Q3 + Q4
  f = seconds left / 3600, TL = closing total_line, pts = points so far,
  m = score margin, Qk = quarter dummies (collinear terms inside one window are
  handled by least squares). Model final F = pts + fitted.
  Windows (one evaluation snapshot per game per window) and training states:
    endQ1 = first snapshot at/after the end of the last Q1 play
            (train: the last Q1 play, and Q2 states with >= 12:00 left)
    midQ2 = first snapshot whose state is in Q2 with <= 7:30 left in the half
            (train: Q2 states with 4:30-7:30 left)
    half  = first snapshot at/after the end of the last Q2 play AND before the
            first Q3 play's snap  (train: the last Q2 play)
    endQ3 = first snapshot at/after the end of the last Q3 play
            (train: the last Q3 play, and Q4 states with >= 12:00 left)
  RULE: bet OVER if F - line >= c, UNDER if line - F >= c, c in {2,3,4,5}
  points (the grid was fixed before grading; the 2016-24 residual SD at each
  window is printed for scale only). Combined over/under cell per window x cut.
  The pooled all-states fit is kept for H5 only.

H3  live spread vs a state model.  OLS per window, same training states:
    final margin - current margin (home - away)
      ~ 1 + f + SL*f + hb + hb*f + cm + cm*f + Q2 + Q3 + Q4
  SL = closing spread_line (home expected margin), hb = +1 home ball / -1 away,
  cm = current home margin. Model final M. Market's final margin = -point.
  RULE: bet HOME if M + point >= c, AWAY if -(M + point) >= c, c in {2,3,4},
  same four windows.

CHANGES AFTER THE FIRST RUN (made after it printed the 2016-24 TRAINING
  diagnostics and crashed in H4, and BEFORE any 2025 H1-H3 cell was read; that
  output file was overwritten unread):
  (1) H1 had been a binned table (exact lead x 60 s x ball x band, shrunk to
      coarser bins). 577 of its 780 cells had < 30 training games and the
      printed table was visibly non-monotone (lead 6 with the ball at 6:30
      left: 0.755; at 7:30: 0.865). Replaced by the per-lead logistic above.
  (2) H2/H3 had been ONE pooled OLS. Its 2016-24 residual at the halftime
      state averaged -2.64 points (it carried the end-of-half scoring burst
      into the break), against 2-5 point cuts. Replaced by per-window fits.
  (3) Snapshots at or after the end of the game's final play are excluded
      from every rule: 2.8% of venue quotes were served > 2 min after the
      final play, which a late-leader rule would otherwise bet as live.
  (4) A pandas index-alignment bug in the ERA5 join (fixed).
  (5) The clock of a quarter's last play is set to the quarter boundary: the
      per-window halftime fit had put +228 points per unit of f on the snap
      clock of the half's last play (a kneel at 0:40 vs a Hail Mary at 0:02),
      which is noise; at the break the time left is exactly 30:00.
  (6) Written AFTER the 2025 cells were read, as diagnostics only (no rule,
      no cut, nothing in the BH family): the price-asynchrony check on the H1
      best-price entries (async_check), the cross-venue dispersion table, the
      power block, and the renaming of ref=table to ref=pbp.

H4  in-play wind under.  Open-air games (roof outdoors/open). Wind = nflverse
  `wind` (<= 45 mph valid) and, separately, ERA5 10 m wind at the stadium in the
  kickoff hour (home-site games only; nfl_edge_halftime_oos construction).
  Windy: >= 12 / 15 / 18 mph. RULE: bet the UNDER on the live total at the
  endQ1 snapshot. Same games, the full-game UNDER at the last pre-kick
  snapshot in odds_hist_2020_2025 (median ~2h before kickoff; not a true
  close). PLACEBO: open-air games with wind < 8 mph by that source.

H5  non-offensive touchdowns.  A TD where return_touchdown = 1, or td_team !=
  posteam, or the play is a kickoff or punt; regulation only. Pre = the last
  snapshot before the TD play ended, post = the first at/after. Market move =
  live total(post) - live total(pre) (DK; and the venue median). Model move =
  F(post) - F(pre) from the H2 model on the two states. Clean = the score moved
  by the TD (+0/1/2 conversion) only between the two states; others dropped and
  counted. RULES at the post snapshot: UNDER every event; OVER every event;
  UNDER when market move - model move > 0; OVER when it is < 0.

H6  broad null control.  The first snapshot at/after commence_time + 30 min,
  every game: UNDER, OVER, spread FAVOURITE, spread DOG, moneyline FAVOURITE,
  moneyline DOG (favourite by DraftKings' line at that snapshot, else the
  venue median). Plus the measured live hold per book and market.

Inference.  Per cell: bets, units, ROI, 90% CI from a game-cluster bootstrap,
  win %, pushes, early (weeks 1-9) / late (weeks 10-22, the 13 playoff games
  folded into late) split. One-sided p = P(simulated units >= observed) when
  every non-push bet wins with probability = the implied probability of the
  price paid (a zero-EV null: generous to the rule, since the true null after
  vig is below break-even). Benjamini-Hochberg q = 0.10 over EVERY primary cell
  in H1-H6, controls and placebos included (the early/late halves are
  descriptive, not separate hypotheses; BH with them added is also printed).
  ROBUSTNESS, reported and NOT in the BH family: (a) the state lagged 60 s
  (state = last play ended at or before snapshot_at - 60 s: a quote that has
  not caught up with the last minute can no longer manufacture an edge);
  (b) quotes flagged stale removed (identical to that book's previous
  snapshot although the score changed in between).
  Clopper-Pearson 90% interval on wins mapped to ROI is printed for moneyline
  cells (late leaders rarely lose, which makes the bootstrap degenerate).

Cost of one more season: the purchase's own request plan (union over days of
  [kickoff - 5 min, kickoff + 3h45m], every 5 minutes, 30 credits per call)
  recomputed from the local schedule, validated against 2025's 5,490 calls.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
from scipy.stats import beta

from scripts.nfl_edge_lib import CACHE, am_to_dec, devig2, games, odds_hist

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 500)

VENUES = ["draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics"]
REFS = ["bovada", "mybookieag", "betonlineag", "lowvig", "betus"]
TRAIN = list(range(2016, 2025))
H1_WINDOWS = (600, 300)
H1_CUTS = (0.02, 0.04, 0.06)
H2_CUTS = (2, 3, 4, 5)
H3_CUTS = (2, 3, 4)
WINDOWS = ("endQ1", "midQ2", "half", "endQ3")
WIND_T = (12, 15, 18)
CALM_LT = 8
WIND_MAX_VALID = 45
K_SHRINK = 30
LAG_S = 60
SEC_EDGES = np.arange(0, 601, 60)
SEC_CENTRES = (SEC_EDGES[:-1] + SEC_EDGES[1:]) / 2
LEAD_GROUP = {4: 0, 5: 0, 6: 0, 7: 1, 8: 1, 9: 2, 10: 2, 11: 3, 12: 3, 13: 3, 14: 4, 15: 4, 16: 4}
CREDITS_PER_CALL = 30

PBP_COLS = ["game_id", "season_type", "qtr", "game_seconds_remaining", "posteam", "defteam",
            "home_team", "away_team", "total_home_score", "total_away_score", "touchdown",
            "td_team", "interception", "fumble_lost", "punt_attempt", "field_goal_result",
            "fourth_down_failed", "safety", "extra_point_attempt", "two_point_attempt",
            "kickoff_attempt", "play_type", "vegas_home_wp", "vegas_home_wpa",
            "return_touchdown", "order_sequence", "home_opening_kickoff"]
TIME_COLS = ["time_of_day", "end_clock_time"]

CELLS: list[dict] = []
ROBUST: list[dict] = []


# ─── grading ───────────────────────────────────────────────────────────────

def profit_of(v, dec):
    """v: 1 win, 0 loss, 0.5 push (stake back); dec: decimal price."""
    v = np.asarray(v, float)
    d = np.asarray(dec, float)
    return np.where(v == 1, d - 1, np.where(v == 0, -1.0, 0.0))


def boot(p, cl, n=4000, alpha=0.10, seed=7):
    p = np.asarray(p, float)
    if len(p) == 0:
        return np.nan, np.nan, np.nan
    u, inv = np.unique(np.asarray(cl), return_inverse=True)
    s = np.bincount(inv, weights=p)
    c = np.bincount(inv)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(u), size=(n, len(u)))
    r = s[idx].sum(1) / c[idx].sum(1)
    lo, hi = np.quantile(r, [alpha / 2, 1 - alpha / 2])
    return p.mean(), lo, hi


def p_null(v, dec, n=20000, seed=11):
    """P(units >= observed) if every non-push bet wins with prob = 1/dec."""
    v = np.asarray(v, float)
    d = np.asarray(dec, float)
    keep = v != 0.5
    v, d = v[keep], d[keep]
    if len(v) == 0:
        return np.nan
    obs = profit_of(v, d).sum()
    rng = np.random.default_rng(seed)
    u = rng.random((n, len(d)))
    sim = np.where(u < 1 / d, d - 1, -1.0).sum(1)
    return float((sim >= obs - 1e-9).mean())


def cp_roi(v, dec, alpha=0.10):
    v = np.asarray(v, float)
    d = np.asarray(dec, float)
    keep = v != 0.5
    v, d = v[keep], d[keep]
    n, k = len(v), v.sum()
    if n == 0:
        return np.nan, np.nan
    lo = 0.0 if k <= 0 else beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k >= n else beta.ppf(1 - alpha / 2, k + 1, n - k)
    c = (1 / d).sum()
    return n * lo / c - 1, n * hi / c - 1


def cell(b, hyp, label, venue, in_bh=True, ml=False, extra=None):
    """b: one row per bet with v, dec, game_id, week (and optional edge)."""
    r = {"hyp": hyp, "cell": label, "venue": venue, "in_bh": in_bh}
    if b is None or len(b) == 0:
        r.update({"bets": 0, "units": 0.0, "roi": np.nan, "lo": np.nan, "hi": np.nan,
                  "win": np.nan, "push": 0, "p": np.nan, "e_bets": 0, "e_units": 0.0,
                  "e_roi": np.nan, "l_bets": 0, "l_units": 0.0, "l_roi": np.nan,
                  "avg_dec": np.nan, "e_p": np.nan, "l_p": np.nan})
    else:
        pr = profit_of(b.v, b.dec)
        r["sd_bet"] = float(np.std(pr, ddof=1)) if len(pr) > 1 else np.nan
        roi, lo, hi = boot(pr, b.game_id)
        early = (b.week <= 9).values
        r.update({"bets": len(b), "units": round(pr.sum(), 2), "roi": round(100 * roi, 1),
                  "lo": round(100 * lo, 1), "hi": round(100 * hi, 1),
                  "win": round(100 * (b.v == 1).mean(), 1), "push": int((b.v == 0.5).sum()),
                  "p": round(p_null(b.v, b.dec), 4),
                  "e_bets": int(early.sum()), "e_units": round(pr[early].sum(), 2),
                  "e_roi": round(100 * pr[early].mean(), 1) if early.any() else np.nan,
                  "l_bets": int((~early).sum()), "l_units": round(pr[~early].sum(), 2),
                  "l_roi": round(100 * pr[~early].mean(), 1) if (~early).any() else np.nan,
                  "avg_dec": round(float(np.mean(b.dec)), 3),
                  "e_p": p_null(b.v[early], b.dec[early]) if early.any() else np.nan,
                  "l_p": p_null(b.v[~early], b.dec[~early]) if (~early).any() else np.nan})
        if ml:
            cl, ch = cp_roi(b.v, b.dec)
            r["cp_lo"], r["cp_hi"] = round(100 * cl, 1), round(100 * ch, 1)
        if "edge" in b:
            r["avg_edge"] = round(float(b.edge.mean()), 3)
    if extra:
        r.update(extra)
    (CELLS if in_bh else ROBUST).append(r)
    return r


SHOW = ["hyp", "cell", "venue", "bets", "units", "roi", "lo", "hi", "win", "push", "p",
        "e_bets", "e_units", "e_roi", "l_bets", "l_units", "l_roi", "avg_dec"]


def show(rows, title, extra_cols=()):
    t = pd.DataFrame(rows)
    if t.empty:
        print(f"\n{title}\n  (no cells)")
        return t
    t["lowN"] = np.where(t.bets < 30, "LOW-N", "")
    cols = [c for c in SHOW + list(extra_cols) if c in t.columns] + ["lowN"]
    print(f"\n{title}")
    print(t[cols].to_string(index=False))
    return t


def bh(p, q=0.10):
    p = np.asarray(p, float)
    ok = ~np.isnan(p)
    out = np.zeros(len(p), bool)
    pp = p[ok]
    if len(pp) == 0:
        return out
    o = np.argsort(pp)
    m = len(pp)
    passed = pp[o] <= q * np.arange(1, m + 1) / m
    k = np.max(np.where(passed)[0]) + 1 if passed.any() else 0
    rej = np.zeros(m, bool)
    rej[o[:k]] = True
    out[np.where(ok)[0]] = rej
    return out


# ─── play states ───────────────────────────────────────────────────────────

def post_ball_team(p: pd.DataFrame) -> np.ndarray:
    """Team with the ball after the play, from the play's own row only."""
    f = lambda c: p[c].fillna(0).values == 1                      # noqa: E731
    td = f("touchdown") & p.td_team.notna().values
    other_td = np.where(p.td_team.values == p.home_team.values, p.away_team.values,
                        p.home_team.values)
    conv = f("extra_point_attempt") | f("two_point_attempt")
    fgm = (p.field_goal_result == "made").values
    fgx = p.field_goal_result.isin(["missed", "blocked"]).values
    ko = f("kickoff_attempt")
    to = f("interception") | f("fumble_lost")
    conds = [td, conv, fgm | f("safety"), ko & f("fumble_lost"), ko,
             to | f("punt_attempt") | fgx | f("fourth_down_failed")]
    vals = [other_td, p.defteam.values, p.defteam.values, p.defteam.values,
            p.posteam.values, p.defteam.values]
    return np.select(conds, vals, default=p.posteam.values)


def play_states(seasons, timed=False) -> pd.DataFrame:
    parts = []
    for s in seasons:
        cols = PBP_COLS + (TIME_COLS if timed else [])
        p = pd.read_parquet(CACHE / f"pbp_{s}.parquet", columns=cols)
        p["season"] = s
        parts.append(p)
    p = pd.concat(parts, ignore_index=True)
    p = p.sort_values(["game_id", "order_sequence"], kind="stable")
    p = p[p.posteam.notna() & p.qtr.notna() & p.game_seconds_remaining.notna()].copy()
    team = post_ball_team(p)
    # last play of each quarter (in game order) -> flags; Q2's last -> 2nd-half receiver
    p["is_last_q"] = p.groupby(["game_id", "qtr"]).cumcount(ascending=False) == 0
    recv2 = np.where(p.home_opening_kickoff.fillna(0).values == 1, p.away_team.values,
                     p.home_team.values)
    team = np.where(p.is_last_q.values & (p.qtr.values == 2), recv2, team)
    p["ball_team"] = team
    p["home_ball"] = (team == p.home_team.values).astype(int)
    p["home_sc"] = p.total_home_score.astype(float)
    p["away_sc"] = p.total_away_score.astype(float)
    p["secs"] = np.where(p.is_last_q & (p.qtr <= 4), (4 - p.qtr) * 900.0,
                         p.game_seconds_remaining.astype(float))
    p["vwp_post"] = (p.vegas_home_wp + p.vegas_home_wpa.fillna(0)).clip(0, 1)
    p["nonoff_td"] = ((p.return_touchdown.fillna(0) == 1)
                      | ((p.touchdown.fillna(0) == 1) & p.td_team.notna() & (p.td_team != p.posteam))
                      | ((p.touchdown.fillna(0) == 1) & p.play_type.isin(["kickoff", "punt"])))
    if timed:
        te = pd.to_datetime(p.end_clock_time, utc=True, errors="coerce", format="mixed")
        ts = pd.to_datetime(p.time_of_day, utc=True, errors="coerce", format="mixed")
        p["t_snap"] = ts.astype("datetime64[ns, UTC]")
        p["t_end"] = te.fillna(ts + pd.Timedelta(seconds=5)).astype("datetime64[ns, UTC]")
    return p


def check_possession(p: pd.DataFrame):
    nxt = p.groupby("game_id").posteam.shift(-1)
    nq = p.groupby("game_id").qtr.shift(-1)
    nconv = (p.groupby("game_id").extra_point_attempt.shift(-1).fillna(0) == 1) | \
            (p.groupby("game_id").two_point_attempt.shift(-1).fillna(0) == 1)
    same_half = ((p.qtr <= 2) & (nq <= 2)) | ((p.qtr >= 3) & (nq >= 3))
    m = nxt.notna() & ~nconv & (same_half | (p.is_last_q & (p.qtr == 2)))
    agree = (p.ball_team[m] == nxt[m]).mean()
    print(f"possession check (derived post-play ball vs the next play's posteam, "
          f"excluding PAT-next rows): {m.sum():,} plays, agreement {100 * agree:.2f}%")


def attach_games(p: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    gg = g[["game_id", "week", "game_type", "home_score", "away_score", "result", "total",
            "spread_line", "total_line"]]
    return p.merge(gg, on="game_id", how="inner")


# ─── models (fit on 2016-2024) ─────────────────────────────────────────────

def leader_view(df):
    d = df.home_sc - df.away_sc
    lead_home = d > 0
    out = pd.DataFrame(index=df.index)
    out["lead"] = d.abs()
    out["lead_home"] = lead_home
    out["ball"] = np.where(lead_home, df.home_ball, 1 - df.home_ball)
    exp_m = np.where(lead_home, df.spread_line, -df.spread_line)
    out["band"] = np.where(exp_m >= 3.5, 0, np.where(exp_m <= -3.5, 2, 1))
    return out


def logit_irls(X, y, lam=1.0, iters=100):
    """Logistic regression with fractional targets; ridge lam on the slopes."""
    b = np.zeros(X.shape[1])
    R = lam * np.eye(X.shape[1])
    R[0, 0] = 0.0
    for _ in range(iters):
        eta = np.clip(X @ b, -30, 30)
        pr = 1 / (1 + np.exp(-eta))
        W = np.clip(pr * (1 - pr), 1e-9, None)
        step = np.linalg.solve(X.T @ (W[:, None] * X) + R, X.T @ (y - pr) - R @ b)
        b = b + step
        if np.abs(step).max() < 1e-9:
            break
    return b


def wp_design(secs, ball, band):
    t = np.log1p(np.asarray(secs, float))
    bl = np.asarray(ball, float)
    bd = np.asarray(band)
    return np.column_stack([np.ones(len(t)), t, bl, bl * t, bd == 0, bd == 2]).astype(float)


def fit_wp(tr: pd.DataFrame):
    x = tr[(tr.qtr <= 4) & tr.spread_line.notna()].copy()
    x = x.join(leader_view(x))
    x = x[(x.lead >= 4) & (x.lead <= 16) & (x.secs <= 600)].copy()
    fin = np.where(x.lead_home, x.result, -x.result)
    x["win"] = np.where(fin > 0, 1.0, np.where(fin < 0, 0.0, 0.5))
    coefs = np.zeros((13, 6))
    rows = []
    for L in range(4, 17):
        z = x[x.lead == L]
        X = wp_design(z.secs, z.ball, z.band)
        coefs[L - 4] = logit_irls(X, z.win.values)
        rows.append({"lead": L, "states": len(z), "games": z.game_id.nunique(),
                     "games_leader_lost": z[z.win == 0].game_id.nunique(),
                     **{n: round(v, 3) for n, v in zip(["const", "t", "ball", "ball*t", "fav", "dog"],
                                                       coefs[L - 4])}})
    x["fit"] = wp_lookup(coefs, x.lead, x.ball, x.band, x.secs)
    print(f"\nH1 WP model: per-lead logistic on {len(x):,} training states (2016-2024, lead 4-16, "
          f"<=600 s), {x.game_id.nunique():,} games")
    print(pd.DataFrame(rows).to_string(index=False))
    sl = pd.DataFrame({f"{int(c)}s": wp_lookup(coefs, np.arange(4, 17), np.ones(13), np.ones(13),
                                                np.full(13, c)) for c in SEC_CENTRES},
                      index=[f"lead {i}" for i in range(4, 17)]).round(3)
    print("fitted WP of the leader WITH the ball, pick-em band (columns: seconds left):")
    print(sl.to_string())
    x["fb"] = pd.cut(x.fit, [0, .7, .8, .85, .9, .95, .98, .99, 1.0])
    cal = x.groupby("fb", observed=True).agg(states=("win", "size"), fitted=("fit", "mean"),
                                             realised=("win", "mean")).round(4)
    print("in-sample calibration by fitted bucket (2016-2024):")
    print(cal.to_string())
    return coefs


def wp_lookup(coefs, lead, ball, band, secs):
    li = np.clip(np.asarray(lead, int) - 4, 0, 12)
    X = wp_design(secs, ball, band)
    eta = (X * coefs[li]).sum(1)
    return 1 / (1 + np.exp(-np.clip(eta, -30, 30)))


def x_total(df):
    f = df.secs.values / 3600
    tl = df.total_line.values
    pts = (df.home_sc + df.away_sc).values
    am = np.abs((df.home_sc - df.away_sc).values)
    q = df.qtr.values
    return np.column_stack([np.ones(len(df)), f, tl * f, (pts - tl * (1 - f)) * f, am * f, am,
                            q == 2, q == 3, q == 4]).astype(float)


def x_margin(df):
    f = df.secs.values / 3600
    sl = df.spread_line.values
    hb = 2 * df.home_ball.values - 1
    cm = (df.home_sc - df.away_sc).values
    q = df.qtr.values
    return np.column_stack([np.ones(len(df)), f, sl * f, hb, hb * f, cm, cm * f,
                            q == 2, q == 3, q == 4]).astype(float)


TOT_NAMES = ["const", "f", "TL*f", "pace*f", "|m|*f", "|m|", "Q2", "Q3", "Q4"]
MAR_NAMES = ["const", "f", "SL*f", "hb", "hb*f", "cm", "cm*f", "Q2", "Q3", "Q4"]


def ols(X, y):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return b


def train_windows(tr):
    """2016-24 states each window draws from (see the docstring)."""
    r = tr[tr.qtr <= 4]
    return {"endQ1": r[((r.qtr == 1) & r.is_last_q) | ((r.qtr == 2) & (r.secs >= 2520))],
            "midQ2": r[(r.qtr == 2) & (r.secs <= 2250) & (r.secs >= 2070)],
            "half": r[(r.qtr == 2) & r.is_last_q],
            "endQ3": r[((r.qtr == 3) & r.is_last_q) | ((r.qtr == 4) & (r.secs >= 720))]}


def fit_totals_margin(tr):
    r = tr[(tr.qtr <= 4) & tr.total_line.notna() & tr.spread_line.notna()].copy()
    yt = lambda z: (z.total - (z.home_sc + z.away_sc)).values             # noqa: E731
    ym = lambda z: (z.result - (z.home_sc - z.away_sc)).values            # noqa: E731
    bt = ols(x_total(r), yt(r))
    bm = ols(x_margin(r), ym(r))
    print(f"\nPOOLED OLS (all {len(r):,} regulation states; used by H5 only)")
    print("  totals: " + ", ".join(f"{n} {v:+.3f}" for n, v in zip(TOT_NAMES, bt)))
    print("  margin: " + ", ".join(f"{n} {v:+.3f}" for n, v in zip(MAR_NAMES, bm)))
    w = train_windows(r)
    btw, bmw, rows = {}, {}, []
    for k in WINDOWS:
        z = w[k]
        btw[k] = ols(x_total(z), yt(z))
        bmw[k] = ols(x_margin(z), ym(z))
        rt = yt(z) - x_total(z) @ btw[k]
        rm = ym(z) - x_margin(z) @ bmw[k]
        rp = yt(z) - x_total(z) @ bt
        rows.append({"window": k, "states": len(z), "games": z.game_id.nunique(),
                     "secs_med": z.secs.median(), "total_resid_sd": round(rt.std(), 2),
                     "pooled_total_resid_mean": round(rp.mean(), 2),
                     "margin_resid_sd": round(rm.std(), 2)})
        print(f"  {k} totals: " + ", ".join(f"{n} {v:+.3f}" for n, v in zip(TOT_NAMES, btw[k])))
        print(f"  {k} margin: " + ", ".join(f"{n} {v:+.3f}" for n, v in zip(MAR_NAMES, bmw[k])))
    print("Per-window fits, 2016-2024 (residual SD for scale; the cut grids were fixed "
          "beforehand; pooled_total_resid_mean = the pooled fit's bias there):")
    print(pd.DataFrame(rows).to_string(index=False))
    return bt, bm, btw, bmw


# ─── 2025 states and quotes ────────────────────────────────────────────────

def states_2025(g):
    p = play_states([2025], timed=True)
    p = attach_games(p, g)
    n0 = len(p)
    p = p[p.t_end.notna()].copy()
    n_nt = n0 - len(p)
    tn = (p.t_end - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
    med = tn.groupby(p.game_id).transform(lambda s: s.rolling(9, center=True, min_periods=1).median())
    bad = (tn - med).abs() > 900
    p = p[~bad].copy()
    p["t_known"] = p.groupby("game_id").t_end.cummax()
    print(f"\n2025 play states: {n0:,} plays with a posteam; {n_nt:,} with no time at all "
          f"(dropped; their score shows in the next timed play's post-play total); "
          f"{int(bad.sum())} clock-entry outliers dropped; {len(p):,} timed states, "
          f"{p.game_id.nunique()} games")
    return p


def attach_state(snaps, st, lag_s=0):
    cols = ["game_id", "t_known", "qtr", "secs", "home_sc", "away_sc", "home_ball",
            "vwp_post", "is_last_q"]
    s = st[cols].sort_values("t_known")
    x = snaps.copy()
    x["t_state"] = (x.snapshot_at - pd.Timedelta(seconds=lag_s)).astype("datetime64[ns, UTC]")
    x = x.sort_values("t_state")
    x = pd.merge_asof(x, s, left_on="t_state", right_on="t_known", by="game_id",
                      direction="backward", allow_exact_matches=True)
    return x.sort_values(["game_id", "snapshot_at"]).reset_index(drop=True)


def load_inplay(g):
    d = pd.read_parquet(CACHE / "inplay_2025.parquet")
    d["snapshot_at"] = d.snapshot_at.astype("datetime64[ns, UTC]")
    d["commence_time"] = d.commence_time.astype("datetime64[ns, UTC]")
    d = d[d.game_id.isin(g.game_id)]
    return d


def snapshot_frame(d, g, st, lag_s=0):
    snaps = d[["game_id", "snapshot_at", "commence_time"]].drop_duplicates(["game_id", "snapshot_at"])
    x = attach_state(snaps, st, lag_s)
    tf = st.groupby("game_id").t_known.max().rename("t_final")
    x = x.join(tf, on="game_id")
    x["over"] = (x.t_state >= x.t_final).fillna(False)
    gg = g[["game_id", "week", "game_type", "home_score", "away_score", "result", "total",
            "spread_line", "total_line", "roof", "wind", "home_team", "away_team"]]
    return x.merge(gg, on="game_id", how="left")


def venue_quotes(d, sf, stale_filter=False):
    q = d[d.bookmaker.isin(VENUES)].copy()
    q["dec_h"] = am_to_dec(q.price_home.values)
    q["dec_a"] = am_to_dec(q.price_away.values)
    q = q.merge(sf[["game_id", "snapshot_at", "home_sc", "away_sc"]], on=["game_id", "snapshot_at"],
                how="left")
    q = q.sort_values(["game_id", "bookmaker", "market", "snapshot_at"])
    grp = q.groupby(["game_id", "bookmaker", "market"])
    same_q = ((q.point.fillna(-999) == grp.point.shift(1).fillna(-999))
              & (q.price_home == grp.price_home.shift(1)) & (q.price_away == grp.price_away.shift(1)))
    score_moved = ((q.home_sc != grp.home_sc.shift(1)) | (q.away_sc != grp.away_sc.shift(1))) \
        & grp.home_sc.shift(1).notna() & q.home_sc.notna()
    q["stale"] = same_q & score_moved
    q["same_as_prev"] = same_q
    q["score_moved"] = score_moved
    if stale_filter:
        q = q[~q.stale]
    return q


def best_by(q, keys, line_col=None, line_high=True, dec_col="dec"):
    """One row per key: best line (if line_col) then best decimal price."""
    order = []
    asc = []
    if line_col is not None:
        order.append(line_col)
        asc.append(not line_high)
    order.append(dec_col)
    asc.append(False)
    return q.sort_values(list(keys) + order, ascending=[True] * len(keys) + asc) \
        .groupby(list(keys), as_index=False).head(1)


# ─── diagnostics ───────────────────────────────────────────────────────────

def diagnostics(d, sf, st, q, g):
    print("\n=== COVERAGE AND QUOTE-QUALITY DIAGNOSTICS (no outcomes) ===")
    print(f"in-play rows {len(d):,}, games {d.game_id.nunique()}, snapshots per game median "
          f"{d.groupby('game_id').snapshot_at.nunique().median():.0f}")
    cov = d[d.bookmaker.isin(VENUES)].groupby(["bookmaker", "market"]).size().unstack()
    print("venue rows by market:\n" + cov.to_string())
    ing = sf[sf.qtr.notna()]
    print(f"snapshots with a game state: {len(ing):,} of {len(sf):,}; in regulation (qtr<=4): "
          f"{int((ing.qtr <= 4).sum()):,}")
    # quotes after the final play ended
    last = st.groupby("game_id").t_known.max().rename("t_final")
    z = q.merge(last, on="game_id")
    post = z[z.snapshot_at > z.t_final + pd.Timedelta(minutes=2)]
    print("quotes served > 2 min after the final play ended (books still quoting a finished game), "
          "by book:", post.groupby("bookmaker").size().to_dict(),
          "| share of all venue rows:", round(len(post) / len(z), 4))
    # staleness proxy
    h = q[(q.market == "h2h") & q.score_moved]
    print("STALE PROXY (h2h): share of quotes identical to that book's previous snapshot although "
          "the score changed in between:",
          h.groupby("bookmaker").stale.mean().round(3).to_dict(), f"(n per book ~{len(h) // 5:,})")
    for m in ("spreads", "totals"):
        hh = q[(q.market == m) & q.score_moved]
        print(f"STALE PROXY ({m}):", hh.groupby("bookmaker").stale.mean().round(3).to_dict())
    # alignment: DK de-vigged home prob vs nflverse post-play WP of the state at lag -1/0/+1
    dk = q[(q.market == "h2h") & (q.bookmaker == "draftkings")][["game_id", "snapshot_at",
                                                                  "price_home", "price_away"]].copy()
    dk["p_home"], _ = devig2(dk.price_home.values, dk.price_away.values)
    a = sf[["game_id", "snapshot_at", "vwp_post", "qtr"]].copy()
    a["vwp_prev"] = a.groupby("game_id").vwp_post.shift(1)
    a["vwp_next"] = a.groupby("game_id").vwp_post.shift(-1)
    z = dk.merge(a, on=["game_id", "snapshot_at"]).dropna(subset=["vwp_post", "vwp_prev", "vwp_next"])
    z = z[z.qtr <= 4]
    print("\nALIGNMENT: DraftKings de-vigged home prob vs nflverse post-play vegas WP of the state "
          f"(n={len(z):,} snapshots; the aligned state should fit best)")
    for c, lab in (("vwp_prev", "state of the PREVIOUS snapshot"), ("vwp_post", "ALIGNED state"),
                   ("vwp_next", "state of the NEXT snapshot")):
        print(f"  {lab:32s} corr {np.corrcoef(z.p_home, z[c])[0, 1]:.4f}  "
              f"mean |diff| {np.abs(z.p_home - z[c]).mean():.4f}")
    # does the quote move across a touchdown, by how soon after it the snapshot came?
    td = st[(st.touchdown.fillna(0) == 1) & (st.qtr <= 4)][["game_id", "t_known"]].rename(
        columns={"t_known": "t_td"})
    s2 = dk.merge(sf[["game_id", "snapshot_at"]], on=["game_id", "snapshot_at"]).sort_values(
        ["game_id", "snapshot_at"])
    s2["prev_t"] = s2.groupby("game_id").snapshot_at.shift(1)
    s2["prev_p"] = s2.groupby("game_id").p_home.shift(1)
    s2["dp"] = (s2.p_home - s2.prev_p).abs()
    zz = td.merge(s2, on="game_id")
    zz = zz[(zz.t_td > zz.prev_t) & (zz.t_td <= zz.snapshot_at)].copy()
    zz["after_s"] = (zz.snapshot_at - zz.t_td).dt.total_seconds()
    zz["bucket"] = pd.cut(zz.after_s, [0, 30, 60, 120, 180, 300, 600])
    base = s2.dp.median()
    print("TOUCHDOWN TIMING: |change in DK de-vigged home prob| across the snapshot pair that "
          "straddles a TD, by seconds from the TD's end to the later snapshot "
          f"(median change over ALL consecutive pairs: {base:.4f})")
    print(zz.groupby("bucket", observed=True).dp.agg(["size", "mean", "median"]).round(4).to_string())


def hold_table(q, sf, h6_snaps):
    z = q.merge(sf[["game_id", "snapshot_at", "qtr"]], on=["game_id", "snapshot_at"])
    z = z[z.qtr <= 4].copy()
    z["over"] = 1 / z.dec_h + 1 / z.dec_a - 1
    t = z.groupby(["bookmaker", "market"]).over.mean().unstack().round(4)
    h = z.merge(h6_snaps[["game_id", "snapshot_at"]], on=["game_id", "snapshot_at"])
    t6 = h.groupby(["bookmaker", "market"]).over.mean().unstack().round(4)
    o = odds_hist(["h2h", "spreads", "totals"])
    o = o[(o.season == 2025) & o.bookmaker.isin(VENUES) & (o.lead_hours >= 0)]
    o = o.sort_values("snapshot_at").groupby(["game_id", "bookmaker", "market"]).tail(1)
    o["over"] = 1 / am_to_dec(o.price_home.values) + 1 / am_to_dec(o.price_away.values) - 1
    tp = o.groupby(["bookmaker", "market"]).over.mean().unstack().round(4)
    print("\nLIVE HOLD (mean overround = sum of implied probs - 1), every regulation in-play "
          "snapshot, by book x market:")
    print(t.to_string())
    print("LIVE HOLD at the H6 snapshot (kickoff + 30 min):")
    print(t6.to_string())
    print("PRE-GAME HOLD, last pre-kick snapshot (odds_hist 2025):")
    print(tp.to_string())


# ─── price asynchrony (diagnostic, not in BH) ─────────────────────────────

def async_check(e, h, label):
    """For best-price entries: was the best book an outlier against the other
    venues at the same snapshot? Re-grade the SAME bets at the venue-median and
    at DraftKings' price (h: venue quotes for the bet side, column dec)."""
    if len(e) == 0:
        return
    k = h.merge(e[["game_id", "snapshot_at"]], on=["game_id", "snapshot_at"])
    med = k.groupby(["game_id", "snapshot_at"]).dec.median().rename("med_dec")
    nb = k.groupby(["game_id", "snapshot_at"]).size().rename("n_books")
    dkp = k[k.bookmaker == "draftkings"].set_index(["game_id", "snapshot_at"]).dec.rename("dk_dec")
    z = e.join(med, on=["game_id", "snapshot_at"]).join(nb, on=["game_id", "snapshot_at"]) \
        .join(dkp, on=["game_id", "snapshot_at"])
    bk = k.sort_values("dec", ascending=False).groupby(["game_id", "snapshot_at"]).head(1)
    z = z.merge(bk[["game_id", "snapshot_at", "same_as_prev"]], on=["game_id", "snapshot_at"], how="left")
    z["gap"] = 1 / z.med_dec - 1 / z.dec
    pb = profit_of(z.v, z.dec)
    pm = profit_of(z.v, z.med_dec)
    zd = z.dropna(subset=["dk_dec"])
    pdk = profit_of(zd.v, zd.dk_dec)
    out = z.gap > 0.02
    print(f"  ASYNC {label}: bets {len(z)}; best book {e.bookmaker.value_counts().to_dict()}; "
          f"venues quoting median {z.n_books.median():.0f}; best-vs-median implied gap mean "
          f"{z.gap.mean():.4f}, > 0.02 in {int(out.sum())}; best book's quote unchanged since its "
          f"previous snapshot in {100 * z.same_as_prev.mean():.0f}%")
    print(f"     same bets at the BEST price {pb.sum():+.2f}u ({100 * pb.mean():+.1f}%), at the "
          f"VENUE MEDIAN {pm.sum():+.2f}u ({100 * pm.mean():+.1f}%), at DK where DK quoted "
          f"({len(zd)} bets) {pdk.sum():+.2f}u ({100 * pdk.mean():+.1f}%); best price when the "
          f"best book was NOT an outlier (gap <= 0.02, {int((~out).sum())} bets) "
          f"{pb[~out.values].sum():+.2f}u, when it was ({int(out.sum())}) {pb[out.values].sum():+.2f}u")


def dispersion(q, sf):
    z = q.merge(sf[["game_id", "snapshot_at", "qtr", "over"]], on=["game_id", "snapshot_at"])
    z = z[(z.qtr <= 4) & ~z.over]
    rows = []
    for m in ("h2h", "spreads", "totals"):
        y = z[z.market == m]
        if m != "h2h":
            # same line only: price dispersion at the modal line of the snapshot
            mode = y.groupby(["game_id", "snapshot_at"]).point.agg(lambda v: v.mode().iloc[0]).rename("mode")
            y = y.join(mode, on=["game_id", "snapshot_at"])
            y = y[y.point == y["mode"]]
        for side, col in (("home/over", "dec_h"), ("away/under", "dec_a")):
            g = y.groupby(["game_id", "snapshot_at"])[col]
            best, med, n = g.max(), g.median(), g.size()
            ok = n >= 3
            gap = (1 / med - 1 / best)[ok]
            rows.append({"market": m, "side": side, "snapshots": int(ok.sum()),
                         "best_vs_median_implied_gap_mean": round(gap.mean(), 4),
                         "gap_p90": round(gap.quantile(.9), 4)})
        if m != "h2h":
            ln = z[z.market == m].groupby(["game_id", "snapshot_at"]).point
            r = (ln.max() - ln.min())
            print(f"  {m}: venues disagree on the LINE at {100 * (r > 0).mean():.0f}% of snapshots; "
                  f"line range >= 1 point at {100 * (r >= 1).mean():.0f}%")
    print("PRICE DISPERSION across the five venues at one snapshot (>= 3 venues; spreads/totals "
          "at the modal line), implied-probability gap of the best price over the venue median:")
    print(pd.DataFrame(rows).to_string(index=False))


# ─── H1 ────────────────────────────────────────────────────────────────────

def h1(sf, q, est, tag="", in_bh=True):
    s0 = sf[(sf.qtr <= 4) & (sf.secs <= 600) & sf.spread_line.notna()]
    s = s0[~s0.over].copy()
    if not tag:
        print(f"H1: regulation snapshots with <= 600 s left {len(s0):,}; at/after the final play "
              f"(game over, excluded) {int(s0.over.sum()):,}")
    lv = leader_view(s)
    s = s.join(lv)
    s = s[(s.lead >= 4) & (s.lead <= 16)].copy()
    s["wp"] = wp_lookup(est, s.lead, s.ball, s.band, s.secs)
    s["vwp"] = np.where(s.lead_home, s.vwp_post, 1 - s.vwp_post)
    fin = np.where(s.lead_home, s.result, -s.result)
    s["v"] = np.where(fin > 0, 1.0, np.where(fin < 0, 0.0, 0.5))
    h = q[q.market == "h2h"].merge(s[["game_id", "snapshot_at", "lead_home"]], on=["game_id", "snapshot_at"])
    h["dec"] = np.where(h.lead_home, h.dec_h, h.dec_a)
    dk = h[h.bookmaker == "draftkings"][["game_id", "snapshot_at", "dec"]]
    bb = best_by(h, ["game_id", "snapshot_at"])[["game_id", "snapshot_at", "dec", "bookmaker"]]
    rows = []
    for venue, pq in (("DK", dk), ("best", bb)):
        x = s.merge(pq, on=["game_id", "snapshot_at"]).sort_values(["game_id", "snapshot_at"])
        x["imp"] = 1 / x.dec
        for ref in ("pbp", "nflverse"):
            x["edge"] = (x.wp if ref == "pbp" else x.vwp) - x.imp
            for S in H1_WINDOWS:
                for c in H1_CUTS:
                    e = x[(x.secs <= S) & (x.edge >= c)].groupby("game_id", as_index=False).head(1)
                    rows.append(cell(e, "H1", f"{tag}leader ref={ref} secs<={S} edge>={c:.2f}", venue,
                                     in_bh=in_bh, ml=True,
                                     extra={"ref": ref, "S": S, "cut": c}))
                    if venue == "best" and not tag and S == 600 and c in (0.02, 0.06):
                        async_check(e, h, f"H1 best ref={ref} secs<=600 edge>={c:.2f}")
    if not tag:
        # calibration at every window snapshot (no rule): table, nflverse, DK fair, realised
        x = s.merge(dk, on=["game_id", "snapshot_at"])
        hh = q[(q.market == "h2h") & (q.bookmaker == "draftkings")][["game_id", "snapshot_at",
                                                                    "price_home", "price_away"]]
        x = x.merge(hh, on=["game_id", "snapshot_at"])
        ph, pa = devig2(x.price_home.values, x.price_away.values)
        x["dk_fair"] = np.where(x.lead_home, ph, pa)
        x["imp"] = 1 / x.dec
        print("\nH1 CALIBRATION, every 2025 snapshot with <= 600 s left and the leader up 4-16 "
              "(DK quoted). Means; 'realised' = leader win share (tie 0.5); game-clustered CI on "
              "table - realised:")
        for lab, sub in (("<=600 s", x), ("<=300 s", x[x.secs <= 300])):
            gap = sub.wp - sub.v
            m, lo, hi = boot(gap, sub.game_id)
            print(f"  {lab}: snapshots {len(sub):,}, games {sub.game_id.nunique()}, table WP "
                  f"{sub.wp.mean():.4f}, nflverse {sub.vwp.mean():.4f}, DK fair {sub.dk_fair.mean():.4f}, "
                  f"DK implied (with vig) {sub.imp.mean():.4f}, realised {sub.v.mean():.4f}; "
                  f"table - realised {m:+.4f} [90% {lo:+.4f}, {hi:+.4f}]")
            for c in H1_CUTS:
                print(f"     share of snapshots with table WP - DK implied >= {c:.2f}: "
                      f"{100 * ((sub.wp - sub.imp) >= c).mean():.1f}%")
        for nm, col in (("table", "wp"), ("nflverse", "vwp"), ("DK fair", "dk_fair")):
            pp = np.clip(x[col].values, 1e-4, 1 - 1e-4)
            yv = x.v.values
            ll = -np.mean(yv * np.log(pp) + (1 - yv) * np.log(1 - pp))
            print(f"  {nm:9s} Brier {np.mean((pp - yv) ** 2):.5f}  log-loss {ll:.5f}")
    return rows


# ─── windows and H2 / H3 ───────────────────────────────────────────────────

def window_snaps(sf, st, lag_s=0):
    """{window: frame of one evaluation snapshot per game}."""
    t1 = st[st.qtr == 1].groupby("game_id").t_known.max().rename("t_q1")
    t2 = st[st.qtr == 2].groupby("game_id").t_known.max().rename("t_q2")
    t3 = st[st.qtr == 3].groupby("game_id").t_known.max().rename("t_q3")
    k3 = st[st.qtr == 3].sort_values("t_known").groupby("game_id").head(1).set_index("game_id")
    k3 = k3.t_snap.fillna(k3.t_end - pd.Timedelta(seconds=5)).rename("t_k3")
    x = sf.join(t1, on="game_id").join(t2, on="game_id").join(t3, on="game_id").join(k3, on="game_id")
    ts = x.snapshot_at - pd.Timedelta(seconds=lag_s)
    reg = (x.qtr <= 4) & ~x.over
    out = {"endQ1": x[reg & (ts >= x.t_q1)],
           "midQ2": x[reg & (x.qtr == 2) & (x.secs <= 2250)],
           "half": x[reg & (ts >= x.t_q2) & (x.snapshot_at < x.t_k3)],
           "endQ3": x[reg & (ts >= x.t_q3)]}
    return {k: v.sort_values(["game_id", "snapshot_at"]).groupby("game_id", as_index=False).head(1)
            for k, v in out.items()}


def line_quotes(q, market, keys_df):
    m = q[q.market == market].merge(keys_df[["game_id", "snapshot_at"]], on=["game_id", "snapshot_at"])
    return m


def grade_total(final, line, side):
    over = np.where(final > line, 1.0, np.where(final < line, 0.0, 0.5))
    return np.where(side == "over", over, np.where(over == 0.5, 0.5, 1 - over))


def grade_spread(result, point, side):
    h = result + point
    home = np.where(h > 0, 1.0, np.where(h < 0, 0.0, 0.5))
    return np.where(side == "home", home, np.where(home == 0.5, 0.5, 1 - home))


def total_offers(q, ws):
    """Per snapshot: DK line/prices; best over (lowest line) and best under (highest line)."""
    m = line_quotes(q, "totals", ws).dropna(subset=["point"])
    dk = m[m.bookmaker == "draftkings"][["game_id", "snapshot_at", "point", "dec_h", "dec_a"]]
    o = m.assign(dec=m.dec_h)
    bo = best_by(o, ["game_id", "snapshot_at"], "point", line_high=False)[["game_id", "snapshot_at", "point", "dec"]]
    u = m.assign(dec=m.dec_a)
    bu = best_by(u, ["game_id", "snapshot_at"], "point", line_high=True)[["game_id", "snapshot_at", "point", "dec"]]
    return dk, bo, bu, m


def spread_offers(q, ws):
    m = line_quotes(q, "spreads", ws).dropna(subset=["point"])
    dk = m[m.bookmaker == "draftkings"][["game_id", "snapshot_at", "point", "dec_h", "dec_a"]]
    hh = m.assign(dec=m.dec_h)
    bh_ = best_by(hh, ["game_id", "snapshot_at"], "point", line_high=True)[["game_id", "snapshot_at", "point", "dec"]]
    aa = m.assign(dec=m.dec_a)
    ba = best_by(aa, ["game_id", "snapshot_at"], "point", line_high=False)[["game_id", "snapshot_at", "point", "dec"]]
    return dk, bh_, ba, m


def two_sided_bets(ws, dk, bA, bB, edgeA, edgeB, sideA, sideB, cut, venue, grader):
    """Generic: A/B are the two sides; edge functions take (ws_row_frame, line)."""
    if venue == "DK":
        x = ws.merge(dk, on=["game_id", "snapshot_at"])
        x["eA"] = edgeA(x, x.point)
        x["eB"] = edgeB(x, x.point)
        x["lineA"] = x.point
        x["lineB"] = x.point
        x["decA"], x["decB"] = x.dec_h, x.dec_a
    else:
        a = bA.rename(columns={"point": "lineA", "dec": "decA"})
        b = bB.rename(columns={"point": "lineB", "dec": "decB"})
        x = ws.merge(a, on=["game_id", "snapshot_at"], how="inner").merge(
            b, on=["game_id", "snapshot_at"], how="inner")
        x["eA"] = edgeA(x, x.lineA)
        x["eB"] = edgeB(x, x.lineB)
    pickA = (x.eA >= cut) & (x.eA >= x.eB)
    pickB = (x.eB >= cut) & ~pickA
    b = x[pickA | pickB].copy()
    sA = pickA[pickA | pickB].values
    b["side"] = np.where(sA, sideA, sideB)
    b["line"] = np.where(sA, b.lineA, b.lineB)
    b["dec"] = np.where(sA, b.decA, b.decB)
    b["edge"] = np.where(sA, b.eA, b.eB)
    b["v"] = grader(b, b.line.values, b.side.values)
    return b


def h2(sf, st, q, btw, tag="", in_bh=True, lag_s=0):
    W = window_snaps(sf, st, lag_s)
    rows, keep = [], {}
    for w in WINDOWS:
        ws = W[w].dropna(subset=["total_line", "home_sc"]).copy()
        ws["F"] = ws.home_sc + ws.away_sc + x_total(ws) @ btw[w]
        dk, bo, bu, _ = total_offers(q, ws)
        keep[w] = (ws, dk, bo, bu)
        for venue in ("DK", "best"):
            for c in H2_CUTS:
                b = two_sided_bets(ws, dk, bo, bu,
                                   lambda x, L: x.F - L, lambda x, L: L - x.F, "over", "under", c,
                                   venue, lambda b, L, s: grade_total(b.total.values, L, s))
                r = cell(b, "H2", f"{tag}totals {w} |F-line|>={c}", venue, in_bh=in_bh,
                         extra={"window": w, "cut": c,
                                "overs": int((b.side == "over").sum()) if len(b) else 0})
                rows.append(r)
    return rows, keep


def h2_accuracy(keep):
    print("\nH2 ACCURACY at the window snapshots, 2025 (out of sample): final total minus "
          "the model's F and minus DK's live total")
    for w in WINDOWS:
        ws, dk, _, _ = keep[w]
        x = ws.merge(dk, on=["game_id", "snapshot_at"])
        em = x.total - x.F
        ek = x.total - x.point
        print(f"  {w}: games {len(x)}, model mean err {em.mean():+.2f} RMSE {np.sqrt((em ** 2).mean()):.2f}"
              f" | DK mean err {ek.mean():+.2f} RMSE {np.sqrt((ek ** 2).mean()):.2f} | "
              f"model - DK line: mean {(x.F - x.point).mean():+.2f}, SD {(x.F - x.point).std():.2f}, "
              f"|diff|>=3 in {int(((x.F - x.point).abs() >= 3).sum())} games")


def h3(sf, st, q, bmw, tag="", in_bh=True, lag_s=0):
    W = window_snaps(sf, st, lag_s)
    rows, keep = [], {}
    for w in WINDOWS:
        ws = W[w].dropna(subset=["spread_line", "home_sc"]).copy()
        ws["M"] = ws.home_sc - ws.away_sc + x_margin(ws) @ bmw[w]
        dk, bhm, ba, _ = spread_offers(q, ws)
        keep[w] = (ws, dk)
        for venue in ("DK", "best"):
            for c in H3_CUTS:
                b = two_sided_bets(ws, dk, bhm, ba,
                                   lambda x, P: x.M + P, lambda x, P: -(x.M + P), "home", "away", c,
                                   venue, lambda b, P, s: grade_spread(b.result.values, P, s))
                rows.append(cell(b, "H3", f"{tag}spread {w} |M+point|>={c}", venue, in_bh=in_bh,
                                 extra={"window": w, "cut": c}))
    return rows, keep


def h3_accuracy(keep):
    print("\nH3 ACCURACY at the window snapshots, 2025: final margin minus the model's M and "
          "minus DK's implied margin (-point)")
    for w in WINDOWS:
        ws, dk = keep[w]
        x = ws.merge(dk, on=["game_id", "snapshot_at"])
        em = x.result - x.M
        ek = x.result + x.point
        print(f"  {w}: games {len(x)}, model mean err {em.mean():+.2f} RMSE {np.sqrt((em ** 2).mean()):.2f}"
              f" | DK mean err {ek.mean():+.2f} RMSE {np.sqrt((ek ** 2).mean()):.2f} | "
              f"model - DK: mean {(x.M + x.point).mean():+.2f}, SD {(x.M + x.point).std():.2f}")


# ─── H4 ────────────────────────────────────────────────────────────────────

def wind_frame(g):
    from zoneinfo import ZoneInfo
    x = g[g.season == 2025].copy()
    out_roof = x.roof.isin(["outdoors", "open"])
    x["wind_nv"] = np.where(out_roof & (x.wind <= WIND_MAX_VALID), x.wind, np.nan)
    dt = pd.to_datetime(x.gameday + " " + x.gametime.fillna("13:00"), errors="coerce")
    x["hr"] = dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                nonexistent="shift_forward").dt.tz_convert("UTC").dt.floor("h")
    e = pd.read_parquet(CACHE / "era5_kick_1999_2025.parquet")
    e["ts"] = e.ts.astype("datetime64[us, UTC]")
    x["hr"] = x.hr.astype("datetime64[us, UTC]")
    x = x.merge(e[["stadium_id", "ts", "era5_wind"]].rename(columns={"ts": "hr"}),
                on=["stadium_id", "hr"], how="left")
    x["wind_era5"] = np.where(x.roof.isin(["outdoors", "open"]) & (x.location == "Home"),
                              x.era5_wind, np.nan)
    both = x[["wind_nv", "wind_era5"]].dropna()
    print(f"\nH4 wind: 2025 open-air games {int(out_roof.sum())}; nflverse wind {int(x.wind_nv.notna().sum())}, "
          f"ERA5 {int(x.wind_era5.notna().sum())}, both {len(both)}; corr {both.corr().iloc[0, 1]:.2f}; "
          f"mean nflverse {both.wind_nv.mean():.1f} vs ERA5 {both.wind_era5.mean():.1f} mph")
    for src in ("wind_nv", "wind_era5"):
        print(f"  {src}: games >= 12 {int((x[src] >= 12).sum())}, >= 15 {int((x[src] >= 15).sum())}, "
              f">= 18 {int((x[src] >= 18).sum())}, calm < {CALM_LT} {int((x[src] < CALM_LT).sum())}")
    return x[["game_id", "wind_nv", "wind_era5"]]


def pregame_totals(g):
    o = odds_hist(["totals"])
    o = o[(o.season == 2025) & o.bookmaker.isin(VENUES) & (o.lead_hours >= 0)].dropna(
        subset=["point", "price_home", "price_away"])
    o = o.sort_values("snapshot_at").groupby(["game_id", "bookmaker"]).tail(1).copy()
    o["dec_h"] = am_to_dec(o.price_home.values)
    o["dec_a"] = am_to_dec(o.price_away.values)
    o["dec"] = o.dec_a
    dk = o[o.bookmaker == "draftkings"][["game_id", "point", "dec"]]
    bu = best_by(o, ["game_id"], "point", line_high=True)[["game_id", "point", "dec"]]
    print(f"pre-game totals: games with a pre-kick venue quote {o.game_id.nunique()}; "
          f"lead hours of the last DK snapshot: "
          f"{o[o.bookmaker == 'draftkings'].lead_hours.quantile([.1, .5, .9]).round(2).to_dict()}")
    return dk, bu


def h4(keep2, g, wf):
    ws, dk, bo, bu = keep2["endQ1"]
    pdk, pbu = pregame_totals(g)
    base = g[g.season == 2025][["game_id", "week", "total"]].merge(wf, on="game_id")
    rows = []
    lv = {"DK": ws.merge(dk, on=["game_id", "snapshot_at"])[["game_id", "point", "dec_a", "F"]]
          .rename(columns={"dec_a": "dec"}),
          "best": ws.merge(bu, on=["game_id", "snapshot_at"])[["game_id", "point", "dec", "F"]]}
    pg = {"DK": pdk, "best": pbu}
    for src in ("wind_nv", "wind_era5"):
        sets = [(f">={T}", base[base[src] >= T]) for T in WIND_T] + \
               [(f"PLACEBO calm<{CALM_LT}", base[base[src] < CALM_LT])]
        for lab, gs in sets:
            for venue in ("DK", "best"):
                for when, src_tab in (("live endQ1", lv[venue]), ("pre-kick", pg[venue])):
                    b = gs.merge(src_tab, on="game_id")
                    b["v"] = grade_total(b.total.values, b.point.values, np.array(["under"] * len(b)))
                    rows.append(cell(b, "H4", f"{when} UNDER {src} {lab}", venue,
                                     extra={"src": src, "set": lab, "when": when}))
    # is the live line any different from the pre-game one in wind?
    x = base.merge(lv["DK"], on="game_id").merge(pdk.rename(columns={"point": "pre_pt", "dec": "pre_dec"}),
                                                 on="game_id")
    x["F_minus_live"] = x.F - x.point
    print("\nH4 context, DK, games with both a live endQ1 and a pre-kick total:")
    for src in ("wind_nv", "wind_era5"):
        for lab, m in ((">=15", x[src] >= 15), (">=12", x[src] >= 12), (f"<{CALM_LT}", x[src] < CALM_LT)):
            z = x[m]
            if len(z) == 0:
                continue
            print(f"  {src} {lab}: games {len(z)}, pre-kick total {z.pre_pt.mean():.1f}, live endQ1 "
                  f"total {z.point.mean():.1f}, final {z.total.mean():.1f}; final - pre-kick "
                  f"{(z.total - z.pre_pt).mean():+.1f}; final - live {(z.total - z.point).mean():+.1f}; "
                  f"windless H2 model F - live {z.F_minus_live.mean():+.2f}")
    return rows


# ─── H5 ────────────────────────────────────────────────────────────────────

def h5(sf, st, q, bt):
    ev = st[st.nonoff_td & (st.qtr <= 4)][["game_id", "t_known", "qtr", "play_type", "week"]].rename(
        columns={"t_known": "t_td"})
    s = sf[["game_id", "snapshot_at", "qtr", "secs", "home_sc", "away_sc", "home_ball", "total_line",
            "total", "week", "over"]].dropna(subset=["home_sc", "total_line"]).copy()
    s["F"] = s.home_sc + s.away_sc + x_total(s) @ bt
    s["pts"] = s.home_sc + s.away_sc
    tq = q[q.market == "totals"].dropna(subset=["point"])
    dkt = tq[tq.bookmaker == "draftkings"][["game_id", "snapshot_at", "point"]].rename(columns={"point": "dk_pt"})
    med = tq.groupby(["game_id", "snapshot_at"]).point.median().rename("med_pt").reset_index()
    s = s.merge(dkt, on=["game_id", "snapshot_at"], how="left").merge(med, on=["game_id", "snapshot_at"], how="left")
    rows_ev = []
    for r in ev.itertuples():
        z = s[s.game_id == r.game_id]
        pre = z[z.snapshot_at < r.t_td].tail(1)
        post = z[z.snapshot_at >= r.t_td].head(1)
        if len(pre) == 0 or len(post) == 0:
            continue
        a, b = pre.iloc[0], post.iloc[0]
        rows_ev.append({"game_id": r.game_id, "week": r.week, "play_type": r.play_type,
                        "snapshot_at": b.snapshot_at, "post_qtr": b.qtr, "post_over": b.over,
                        "dpts": b.pts - a.pts, "mkt_dk": b.dk_pt - a.dk_pt,
                        "mkt_med": b.med_pt - a.med_pt, "model": b.F - a.F,
                        "secs_after": (b.snapshot_at - r.t_td).total_seconds()})
    e = pd.DataFrame(rows_ev)
    n_all = len(ev)
    clean = e[(e.dpts - 6).isin([0, 1, 2]) & (e.post_qtr <= 4) & ~e.post_over.astype(bool)].copy()
    clean["excess_dk"] = clean.mkt_dk - clean.model
    print(f"\nH5: non-offensive TDs in 2025 regulation {n_all}; with a snapshot on both sides "
          f"{len(e)}; clean (only the TD and its try between the two states, post state in "
          f"regulation) {len(clean)}")
    if len(clean):
        print(f"  market move DK mean {clean.mkt_dk.mean():+.2f} (median {clean.mkt_dk.median():+.2f}), "
              f"venue-median line move {clean.mkt_med.mean():+.2f}; model move mean "
              f"{clean.model.mean():+.2f}; points on the board between the states {clean.dpts.mean():.2f}; "
              f"DK excess (market - model) mean {clean.excess_dk.mean():+.2f}, SD "
              f"{clean.excess_dk.std():.2f}, share > 0 {100 * (clean.excess_dk > 0).mean():.0f}%")
        m, lo, hi = boot(clean.excess_dk.dropna(), clean.dropna(subset=['excess_dk']).game_id)
        print(f"  DK excess game-clustered 90% CI [{lo:+.2f}, {hi:+.2f}]")
    ws = clean.merge(s[["game_id", "snapshot_at", "total"]], on=["game_id", "snapshot_at"])
    ws = ws.drop_duplicates(["game_id", "snapshot_at"])
    dk, bo, bu, _ = total_offers(q, ws)
    rows = []
    for venue in ("DK", "best"):
        if venue == "DK":
            xo = ws.merge(dk, on=["game_id", "snapshot_at"]).assign(dec=lambda d: d.dec_h)
            xu = ws.merge(dk, on=["game_id", "snapshot_at"]).assign(dec=lambda d: d.dec_a)
        else:
            xo = ws.merge(bo, on=["game_id", "snapshot_at"])
            xu = ws.merge(bu, on=["game_id", "snapshot_at"])
        for lab, x, side, m in (("UNDER every event", xu, "under", None),
                                ("OVER every event", xo, "over", None),
                                ("UNDER when market move > model move", xu, "under", "pos"),
                                ("OVER when market move < model move", xo, "over", "neg")):
            b = x.copy()
            if m == "pos":
                b = b[b.excess_dk > 0]
            elif m == "neg":
                b = b[b.excess_dk < 0]
            b["v"] = grade_total(b.total.values, b.point.values, np.array([side] * len(b)))
            rows.append(cell(b, "H5", lab, venue))
    return rows


# ─── H6 ────────────────────────────────────────────────────────────────────

def h6(sf, q):
    s = sf[sf.snapshot_at >= sf.commence_time + pd.Timedelta(minutes=30)]
    s = s.sort_values(["game_id", "snapshot_at"]).groupby("game_id", as_index=False).head(1)
    rows = []
    m = q.merge(s[["game_id", "snapshot_at", "total", "result"]], on=["game_id", "snapshot_at"])
    # favourite by DK, else venue median
    sp = m[m.market == "spreads"].dropna(subset=["point"])
    ref_pt = sp[sp.bookmaker == "draftkings"].set_index("game_id").point
    ref_pt = ref_pt.combine_first(sp.groupby("game_id").point.median())
    ml = m[m.market == "h2h"]
    ref_ml = (ml[ml.bookmaker == "draftkings"].set_index("game_id").eval("dec_h - dec_a"))
    ref_ml = ref_ml.combine_first(ml.groupby("game_id").apply(lambda z: (z.dec_h - z.dec_a).median(),
                                                               include_groups=False))
    tt = m[m.market == "totals"].dropna(subset=["point"])
    for venue in ("DK", "best"):
        src = (lambda z: z[z.bookmaker == "draftkings"]) if venue == "DK" else (lambda z: z)
        # totals
        for side in ("under", "over"):
            z = src(tt).assign(dec=lambda d: d.dec_a if side == "under" else d.dec_h)
            if venue == "best":
                z = best_by(z, ["game_id"], "point", line_high=(side == "under"))
            z = z.copy()
            z["v"] = grade_total(z.total.values, z.point.values, np.array([side] * len(z)))
            rows.append(cell(z, "H6", f"kick+30m totals {side.upper()}", venue))
        # spreads
        z = src(sp).copy()
        z["fav_home"] = z.game_id.map(ref_pt) < 0
        z = z[z.game_id.map(ref_pt) != 0]
        for who in ("FAV", "DOG"):
            home_side = z.fav_home if who == "FAV" else ~z.fav_home
            y = z.assign(side=np.where(home_side, "home", "away"),
                         dec=np.where(home_side, z.dec_h, z.dec_a),
                         line=np.where(home_side, z.point, -z.point))
            if venue == "best":
                y = best_by(y, ["game_id"], "line", line_high=True)
            y = y.copy()
            y["v"] = grade_spread(y.result.values, y.point.values, y.side.values)
            rows.append(cell(y, "H6", f"kick+30m spread {who}", venue))
        # moneyline
        z = src(ml).copy()
        z["fav_home"] = z.game_id.map(ref_ml) < 0
        z = z[z.game_id.map(ref_ml) != 0]
        for who in ("FAV", "DOG"):
            home_side = z.fav_home if who == "FAV" else ~z.fav_home
            y = z.assign(home=home_side, dec=np.where(home_side, z.dec_h, z.dec_a))
            if venue == "best":
                y = best_by(y, ["game_id"])
            y = y.copy()
            fin = np.where(y.home, y.result, -y.result)
            y["v"] = np.where(fin > 0, 1.0, np.where(fin < 0, 0.0, 0.5))
            rows.append(cell(y, "H6", f"kick+30m moneyline {who}", venue, ml=True))
    return rows, s


# ─── cost of one more season ───────────────────────────────────────────────

def request_plan(g, season):
    k = g[(g.season == season) & g.result.notna()].kick.dropna().sort_values()
    spans = sorted((t - timedelta(minutes=5), t + timedelta(hours=3, minutes=45)) for t in k)
    merged = []
    for lo, hi in spans:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    n = 0
    for lo, hi in merged:
        t = lo - timedelta(minutes=lo.minute % 5, seconds=lo.second, microseconds=lo.microsecond)
        while t <= hi:
            n += 1
            t += timedelta(minutes=5)
    return n


# ─── main ──────────────────────────────────────────────────────────────────

def main():
    g = games()
    print("=== TRAINING (2016-2024 play-by-play; no 2025 data) ===")
    tr = attach_games(play_states(TRAIN), g)
    check_possession(tr)
    est = fit_wp(tr)
    bt, bm, btw, bmw = fit_totals_margin(tr)
    del tr

    d = load_inplay(g)
    st = states_2025(g)
    sf = snapshot_frame(d, g, st, 0)
    sf_lag = snapshot_frame(d, g, st, LAG_S)
    q = venue_quotes(d, sf)
    q_fresh = venue_quotes(d, sf, stale_filter=True)
    diagnostics(d, sf, st, q, g)
    dispersion(q, sf)

    print("\n=== H1: late-game leader, live moneyline vs 2016-24 empirical WP ===")
    r1 = h1(sf, q, est)
    show(r1, "H1 cells (one bet per game per cell, first qualifying snapshot)",
         extra_cols=["cp_lo", "cp_hi", "avg_edge"])
    show(h1(sf_lag, q, est, tag="LAG60 ", in_bh=False) + h1(sf, q_fresh, est, tag="FRESH ", in_bh=False),
         "H1 ROBUSTNESS (not in BH): state lagged 60 s | stale quotes removed",
         extra_cols=["cp_lo", "cp_hi"])

    print("\n=== H2: live totals vs a 2016-24 remaining-points model ===")
    W = window_snaps(sf, st)
    print("2025 window snapshots (state only, no outcomes): seconds left in the state, q10/q50/q90")
    for k in WINDOWS:
        print(f"  {k}: games {len(W[k])}, secs {W[k].secs.quantile([.1, .5, .9]).round(0).tolist()}")
    r2, keep2 = h2(sf, st, q, btw)
    h2_accuracy(keep2)
    show(r2, "H2 cells (one evaluation snapshot per game per window)", extra_cols=["overs", "avg_edge"])
    rr = h2(sf_lag, st, q, btw, tag="LAG60 ", in_bh=False, lag_s=LAG_S)[0] + \
        h2(sf, st, q_fresh, btw, tag="FRESH ", in_bh=False)[0]
    show(rr, "H2 ROBUSTNESS (not in BH)")

    print("\n=== H3: live spread vs a 2016-24 margin model ===")
    r3, keep3 = h3(sf, st, q, bmw)
    h3_accuracy(keep3)
    show(r3, "H3 cells", extra_cols=["avg_edge"])
    rr = h3(sf_lag, st, q, bmw, tag="LAG60 ", in_bh=False, lag_s=LAG_S)[0] + \
        h3(sf, st, q_fresh, bmw, tag="FRESH ", in_bh=False)[0]
    show(rr, "H3 ROBUSTNESS (not in BH)")

    print("\n=== H4: in-play wind under ===")
    wf = wind_frame(g)
    r4 = h4(keep2, g, wf)
    show(r4, "H4 cells (live = the endQ1 snapshot; pre-kick = last odds_hist snapshot)")

    print("\n=== H5: non-offensive touchdowns ===")
    r5 = h5(sf, st, q, bt)
    show(r5, "H5 cells (bet at the first snapshot after the TD)")

    print("\n=== H6: broad null control ===")
    r6, s6 = h6(sf, q)
    show(r6, "H6 cells (first snapshot at/after kickoff + 30 min, every game)",
         extra_cols=["cp_lo", "cp_hi"])
    hold_table(q, sf, s6)

    print("\n=== MULTIPLE COMPARISONS ===")
    a = pd.DataFrame(CELLS)
    a["bh"] = bh(a.p.values)
    print(f"primary cells {len(a)} (H1 {sum(a.hyp == 'H1')}, H2 {sum(a.hyp == 'H2')}, "
          f"H3 {sum(a.hyp == 'H3')}, H4 {sum(a.hyp == 'H4')}, H5 {sum(a.hyp == 'H5')}, "
          f"H6 {sum(a.hyp == 'H6')}); with bets {int((a.bets > 0).sum())}; "
          f"one-sided p < 0.05: {int((a.p < 0.05).sum())}; p < 0.01: {int((a.p < 0.01).sum())}; "
          f"surviving BH q=0.10: {int(a.bh.sum())}")
    if a.bh.any():
        print(a[a.bh][["hyp", "cell", "venue", "bets", "units", "roi", "lo", "hi", "p"]].to_string(index=False))
    # BH with the early/late halves added as cells (descriptive family)
    allp = np.concatenate([a.p.values, a.e_p.values, a.l_p.values])
    print(f"BH q=0.10 with the early and late halves added ({len(allp)} p-values): "
          f"{int(bh(allp).sum())} rejected")
    print("smallest p per hypothesis:", a.groupby("hyp").p.min().round(4).to_dict())
    pos = a[(a.bets >= 30) & (a.lo > 0)]
    print(f"cells with >= 30 bets and the 90% CI lower bound above 0: {len(pos)}")
    if len(pos):
        print(pos[["hyp", "cell", "venue", "bets", "units", "roi", "lo", "hi", "p", "e_roi", "l_roi"]]
              .to_string(index=False))
    top = a[a.bets > 0].sort_values("p").head(12)
    print("\n12 lowest-p primary cells:")
    print(top[["hyp", "cell", "venue", "bets", "units", "roi", "lo", "hi", "p", "e_bets", "e_roi",
               "l_bets", "l_roi"]].to_string(index=False))
    print("\nunits summed over each hypothesis' cells is NOT a strategy (cells overlap); per-hyp "
          "share of cells with ROI > 0:",
          a[a.bets > 0].groupby("hyp").roi.apply(lambda s: round(100 * (s > 0).mean(), 0)).to_dict())

    print("\n=== WHAT MORE SEASONS WOULD BUY (power; per-bet SD measured on the 2025 cell) ===")
    print("bets needed so a 90% one-sided lower bound clears 0 at a true ROI of r: "
          "N = (1.645 * SD / r)^2; seasons = N / the cell's 2025 bets")
    pw = a[a.bets >= 30].copy()
    pick = pd.concat([pw[pw.hyp == h].sort_values("p").head(2) for h in ("H1", "H2", "H3", "H4", "H5", "H6")])
    for r_ in pick.itertuples():
        n3 = (1.645 * r_.sd_bet / 0.03) ** 2
        n5 = (1.645 * r_.sd_bet / 0.05) ** 2
        print(f"  {r_.hyp} {r_.cell} [{r_.venue}]: 2025 bets {r_.bets}, per-bet SD {r_.sd_bet:.3f}u; "
              f"N at +3% {n3:,.0f} ({n3 / r_.bets:.1f} seasons), at +5% {n5:,.0f} ({n5 / r_.bets:.1f} seasons)")

    print("\n=== COST OF ONE MORE SEASON (the purchase's own request plan, local schedule) ===")
    for s in (2025, 2024, 2023):
        n = request_plan(g, s)
        print(f"  {s}: {n:,} five-minute requests x {CREDITS_PER_CALL} = {n * CREDITS_PER_CALL:,} credits")
    print("  2025 purchase log: 5,490 calls, 164,700 credits")


if __name__ == "__main__":
    main()

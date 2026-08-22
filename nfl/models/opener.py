"""
Opener sharp-vs-soft: per-bet win probability and staking.

NOT THE LIVE PATH. The live opener is `scripts/daily_opener_card.py`, run by
the platform scheduler and published as `nfl_opener_spread`. That card uses a
FLAT win probability of 0.5818 for every qualifying bet.

This module is the proposed upgrade to that: a per-bet probability that varies
with how big the deviation actually is, plus Kelly-proportional sizing in the
same units the wind model uses. A 3-point deviation is worth far more than a
1-point one, and a flat probability cannot see the difference - it overstates
small deviations and understates large ones. Nothing imports this yet; wiring
it into the live card is a separate change with its own test updates.


WHAT THIS IS
------------
In the T-7 to T-2 day window, soft books carry numbers they posted days before
Pinnacle came online. Wherever a clean soft book's spread differs from
Pinnacle's by at least the threshold, bet the side Pinnacle favours, at the soft
book's number. One bet per game, at the FIRST qualifying moment.

Unlike the wind rule this IS a race. The edge is staleness, so it has to be bet
in the window; there is nothing left at the close.

EVIDENCE (scripts/backtest_opener.py, 2023-2025, 853 games, 29 clean books)
--------------------------------------------------------------------------
Threshold 1.0, one bet per game, priced at what the books actually quoted:

  n=593  win 58.18%  expected from the number bought 53.07%
  excess +5.11pp  95% CI [+1.1, +8.9]
  mean price -125.1  ROI +6.82%  95% CI [-0.6, +14.3]

The excess is what matters, not the win rate: most of 58.18% is simply the
value of the better number, and the books charge for that number almost exactly
what it is worth. Placebo with DraftKings as the reference gives +0.98pp
[-2.9, +4.9], so the effect is specific to Pinnacle.

WHAT DID NOT SURVIVE
--------------------
Totals and moneyline were scanned densely across 2023-2025 and both are null.
The totals placebo matches the totals signal at every threshold. Spreads only.

LIVE RISK, AND IT IS NOT SMALL
------------------------------
Season ROI at actual prices: 2023 +4.75%, 2024 +14.31%, 2025 +1.05%. Roughly
70% of three seasons of profit is 2024, and the most recent season is barely
above zero at a mean quoted price of -125. Either the edge is decaying as
early-week pricing tightens, or 2024 was a high draw. The staking below assumes
the pessimistic reading, and the monitoring rule in the runbook is a real stop,
not a formality.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

# Books carrying home/away sign flips. Screened on 1.4M quotes across 40 books;
# see scripts/screen_books.py. A defect in 0.4% of rows once supplied 15% of
# selected bets, and this rule selects on extremes, so the exclusion is binding.
DEFECTIVE_BOOKS = {"betanysports", "betsson", "nordicbet", "tipico_de"}

REFERENCE_BOOK = "pinnacle"

# The frozen rule.
DEV_THRESHOLD = 1.0            # points of deviation from Pinnacle
LEAD_LO_HOURS = 48.0           # T-2 days
LEAD_HI_HOURS = 168.0          # T-7 days
POLL_HOURS = 6.0               # the grid the rule was validated on

# Measured at threshold 1.0. `WIN_RATE` is the realised rate and already
# contains the value of the better number; `EXPECTED_FROM_LINE` is what the
# number alone was worth. The difference is the edge.
WIN_RATE = 0.5818
EXPECTED_FROM_LINE = 0.5307
EXCESS = WIN_RATE - EXPECTED_FROM_LINE
MEAN_PRICE = -125.1

# Share of the measured excess assumed to persist. 1.0 is the full-sample
# reading; the 2025 season alone would justify roughly 0.4. The default is
# deliberately below the full sample because the most recent season is the
# weakest and a decaying edge is the likelier of the two live readings.
EDGE_PERSISTENCE = 0.6

# Shared with the wind model so a unit means the same thing across the book.
UNIT_PCT = 0.01
REF_KELLY = 0.0911             # wind's reference bet, lead 3 / thr 11 / -110
MAX_UNITS = 2.0
DAY_UNIT_CAP = 4.0             # opener fires far more often than wind


def american_to_decimal(px: float) -> float:
    return 1.0 + (px / 100.0 if px > 0 else 100.0 / -px)


def american_to_prob(px: float) -> float:
    return 100.0 / (px + 100.0) if px > 0 else -px / (-px + 100.0)


def expected_from_number(clv_points: float, resid: np.ndarray) -> float:
    """
    P(cover) implied by the number bought alone, from the empirical
    margin-versus-close residual distribution. This is the benchmark the bet has
    to beat; beating 50% is not the bar.
    """
    e = resid + clv_points
    return float((e > 0).mean() + 0.5 * (e == 0).mean())


def model_win_prob(clv_points: float, resid: np.ndarray,
                   persistence: float = EDGE_PERSISTENCE) -> float:
    """
    P(win) for a qualifying bet: what the number is worth, plus the persisted
    share of the measured Pinnacle-direction excess.
    """
    return expected_from_number(clv_points, resid) + persistence * EXCESS


def kelly_fraction(p: float, px: float) -> float:
    b = american_to_decimal(px) - 1.0
    if b <= 0:
        return 0.0
    return max(0.0, (b * p - (1 - p)) / b)


def stake_units(p: float, px: float, ref_kelly: float = REF_KELLY,
                max_units: float = MAX_UNITS) -> float:
    """
    Units to stake. Same unit as the wind model - 1 unit is `UNIT_PCT` of
    bankroll - and the same Kelly-proportional scaling against the same
    reference, so the two models' stakes are directly comparable and can share
    one bankroll.
    """
    f = kelly_fraction(p, px)
    if f <= 0:
        return 0.0
    return float(min(f / ref_kelly, max_units))


@dataclass
class OpenerBet:
    game_id: str
    matchup: str
    kick_utc: str
    lead_h: float
    book: str
    side: str
    point: float
    price: int
    pin_point: float
    dev: float
    model_prob: float
    exp_from_number: float
    edge: float
    units: float
    stake_pct: float
    ev_pct: float

    def as_dict(self) -> dict:
        return asdict(self)


def select_bets(quotes: pd.DataFrame, resid: np.ndarray,
                threshold: float = DEV_THRESHOLD,
                persistence: float = EDGE_PERSISTENCE,
                bankroll: float = 1.0) -> pd.DataFrame:
    """
    Apply the frozen rule to a board.

    `quotes` is one row per (game, book) with the CURRENT spread, carrying:
      game_id, matchup, kick_utc, lead_h, book, point, px_home, px_away,
      pin_point.

    `point` is the HOME handicap, so a larger number is more points for the
    home side. dev > 0 means the soft book is offering the home side a better
    number than Pinnacle, and the bet is home.
    """
    q = quotes[~quotes.book.isin(DEFECTIVE_BOOKS) & (quotes.book != REFERENCE_BOOK)]
    q = q.dropna(subset=["point", "pin_point"]).copy()
    if q.empty:
        return pd.DataFrame(columns=[f.name for f in OpenerBet.__dataclass_fields__.values()])

    q["dev"] = q.point - q.pin_point
    q = q[q.dev.abs() >= threshold]
    if q.empty:
        return pd.DataFrame(columns=[f.name for f in OpenerBet.__dataclass_fields__.values()])

    rows = []
    for r in q.itertuples():
        bet_home = r.dev > 0
        px = r.px_home if bet_home else r.px_away
        if pd.isna(px):
            continue
        # CLV proxy at bet time: how much better the number is than Pinnacle's
        # current number. The backtest measured against Pinnacle's CLOSE, which
        # is not knowable live, and Pinnacle moves little in this window.
        clv = abs(r.dev)
        exp_n = expected_from_number(clv, resid)
        p = exp_n + persistence * EXCESS
        u = stake_units(p, int(px))
        dec = american_to_decimal(int(px))
        rows.append(OpenerBet(
            game_id=r.game_id, matchup=r.matchup, kick_utc=str(r.kick_utc),
            lead_h=round(float(r.lead_h), 1), book=r.book,
            side="home" if bet_home else "away",
            point=float(r.point) if bet_home else -float(r.point),
            price=int(px), pin_point=float(r.pin_point), dev=round(float(r.dev), 2),
            model_prob=round(p, 4), exp_from_number=round(exp_n, 4),
            edge=round(p - american_to_prob(int(px)), 4),
            units=round(u, 3), stake_pct=round(u * UNIT_PCT * 100, 3),
            ev_pct=round((p * (dec - 1) - (1 - p)) * 100, 2),
        ).as_dict())

    out = pd.DataFrame(rows)
    if not len(out):
        return out
    # One bet per game: the biggest deviation available right now.
    out = (out.sort_values(["game_id", "units", "dev"], ascending=[True, False, False])
           .groupby("game_id", as_index=False).first())
    if bankroll != 1.0:
        out["stake_amt"] = (out.stake_pct / 100 * bankroll).round(2)
    return out.sort_values("units", ascending=False).reset_index(drop=True)


def margin_residuals(games_csv: str = "data/games.csv") -> np.ndarray:
    g = pd.read_csv(games_csv)
    g = g[g.season.between(1999, 2025) & g.result.notna() & g.spread_line.notna()]
    return (g.result - g.spread_line).values

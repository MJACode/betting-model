"""
Opener sharp-vs-soft spread: the frozen rule, its per-bet win probability, and
the selection. Published by the platform as model `nfl_opener_spread`.

This is the MODEL. `scripts/daily_opener_card.py` is the live card that fetches
the board, calls `select_opener_bets`, and writes the CSV the publisher reads.
Keep the rule here and the plumbing there.

THE RULE (unchanged from the corrected backtest)
------------------------------------------------
In the T-7 to T-2 day window — Pinnacle posts around T-6.5, soft books still
carry the numbers they hung days earlier — wherever a clean soft book's HOME
spread deviates from Pinnacle's by at least `DEPLOY_THRESHOLD` points, bet the
side Pinnacle favours AT the soft book's stale number. One bet per game, taken
at the FIRST qualifying moment. The card runs daily, so "first qualifying
moment" is realised at daily resolution; the number corrects only ~4.8% a day,
so daily granularity loses little. LATER RUNS NEVER REPRICE A TAKEN BET — the
edge IS staleness, and waiting destroys it. The publisher enforces that lock.

Unlike the wind rule this is a race. There is nothing left at the close.

EVIDENCE (scripts/backtest_opener.py, 2020-2025, 1,675 games, 35 clean books)
--------------------------------------------------------------------------
RESTATED 2026-08-23 on SIX seasons. The original figure rested on 2023-2025,
which was all the densely-scanned data there was. A 27,300-credit scan added
2020-2022 at the same 6-hourly resolution, and the edge did not survive it.

  |dev| >= 1.0 : n=1,178, ATS 56.88% against 54.60% expected from the number
  bought, so +2.27pp excess [95% CI -0.6, +5.1]; ROI +1.34% [-3.9, +6.4] at
  the juice actually quoted. Both intervals span zero.

  Season ROI: 2020 -2.62%, 2021 -1.78%, 2022 -2.80%, 2023 +4.72%,
  2024 +10.86%, 2025 +0.32%. The three seasons that were added are ALL
  negative, and the DraftKings placebo now returns +0.95pp [-1.7, +3.7]
  against the model's +2.27pp — a gap too small to call.

  Raising the threshold does not rescue it: |dev| >= 2.0 over the same six
  seasons is +2.63% ROI [-6.3, +11.0] on n=356.

WHAT CHANGED, AND WHY THE OLD NUMBER WAS TOO HIGH
-------------------------------------------------
Two things, both corrections rather than new information:

  1. The backtest did not exclude EXCHANGES, but the live card always has.
     Matchbook quotes deep alternate lines that read as enormous "deviations"
     from Pinnacle's main number — in 2020 the selected bets averaged a price
     of about -2,000. Those were never openers, and the deployment would never
     have taken them. Excluding them, as the card does, lowers even the
     original 2023-2025 figure from +6.82% to +5.37%.
  2. Three more seasons of data, all of them worse.

WHAT DID NOT SURVIVE
--------------------
Totals and moneyline were scanned densely across 2023-2025 on the same
6-hourly grid and both are NULL; the totals placebo matches the totals signal
at every threshold. Spreads only.

LIVE, AND SIZED TO THE EVIDENCE
-------------------------------
Kept as a production model by explicit decision (2026-08-23) after the
six-season restatement above. That is a judgement call about an edge whose
interval spans zero, and the sizing is built to survive being wrong:

  * probabilities are the SIX-season ones, ~2.8pp below the three-season table
    they replace, so every stake is smaller at the same deviation;
  * the stake is Kelly-proportional per bet rather than flat, which matters
    enormously here. Over 2020-2025, 89% of picks carry a mean edge of
    +1.59pp and return -0.30%, while the 7% at +3.73pp return +17.13%. A flat
    stake bets those identically. Sizing takes the six-season return from
    +1.28% flat to +5.45% on units staked, risking 366u where flat risked 810u;
  * a quote whose juice has eaten the edge is staked at ZERO, not at 1u.

The honest caveat on that +5.45%: the tier boundaries came from this same
sample, so it is partly in-sample. The direction - bet more when the edge is
bigger - is not in doubt; the magnitude is not validated.

WHAT WOULD RETIRE IT: a 2026 season at or below flat. The profit across six
seasons is nearly all 2024, and 2025 was +0.32%. Watch the paper track, and do
not raise the unit on a good month.
"""

from __future__ import annotations

import pandas as pd

# Books carrying home/away sign flips in the Odds API feed. Screened across 40
# books on 1.4M quotes; see scripts/screen_books.py. This rule selects on
# extremes, so a defect present in 0.4% of rows once supplied 15% of selected
# bets — the exclusion is load-bearing, not hygiene.
DEFECTIVE_BOOKS = {"betanysports", "betsson", "nordicbet", "tipico_de"}

# Exchange prices are gross of ~2% commission and the platform's picks table
# has no way to express that, so the exchange is not bettable here. It was 1 of
# the 29 clean books in the backtest; excluding it is the conservative side.
EXCHANGES = {"matchbook"}

REFERENCE = "pinnacle"

DEPLOY_THRESHOLD = 1.0   # |soft_home_line - pinnacle_home_line|, points
LEAD_LO_DAYS = 2.0       # the validated window: T-7 to T-2
LEAD_HI_DAYS = 7.0

# Pooled validated ATS at the deployment threshold. Kept for reference and as
# the fallback: this is what the card used for EVERY bet until 2026-08-22.
POOLED_MODEL_PROB = 0.5688      # six-season pooled ATS (was 0.5818 on three)

# ---------------------------------------------------------------------------
# PER-BET WIN PROBABILITY BY DEVIATION SIZE
#
# A 3-point deviation is worth far more than a 1-point one, and a single pooled
# number cannot see the difference: it overstates the small deviations that
# make up most of the volume and understates the rare large ones.
#
# Two measured pieces go into this table, and the first is easy to miss.
#
# 1. THE DEVIATION SHRINKS BEFORE IT PAYS. The card sees |soft - pinnacle NOW|,
#    but a bet is worth its advantage against where Pinnacle CLOSES, and the
#    soft book moves most of the way to Pinnacle before then. Measured on the
#    593 selected bets, 2023-2025: mean |dev| 1.406 -> mean realised CLV 0.902,
#    a shrink of 0.641 overall and ~0.56 across the 1.0-2.0 band that carries
#    86% of the volume. Feeding raw |dev| into the win-probability curve would
#    overstate the pooled probability by 1.5pp: 59.67% against a realised
#    58.18%.
#    Six-season knots: |dev| 1.0/1.5/2.0/2.59/7.35 -> shrink
#    0.546/0.642/0.478/0.707/1.000.
# 2. WHAT THE SHRUNK NUMBER IS WORTH, from the empirical margin-versus-close
#    residual distribution (n=7,276, 1999-2025). That distribution carries the
#    key-number atoms, which is why this table has flat stretches rather than a
#    smooth curve. Plus the measured +5.11pp Pinnacle-direction excess.
#
# Sanity check on the whole construction: applied to the 1,178 backtested bets
# it gives a pooled 56.87% against a realised 56.88% - a 0.01pp gap. The
# average is preserved and only the distribution across deviation sizes moves.
# Regenerate with scripts/calibrate_opener.py --emit.
#
# Minimum modelled probability is now 0.5470 at |dev| 1.0, BELOW the min_prob
# 0.55 gate in config.py. That is intended: on six seasons a 1-point deviation
# is not worth betting, and the platform gate drops it without needing a
# separate rule. Only |dev| >= 2.0 clears the gate.
# ---------------------------------------------------------------------------
DEV_WIN_PROB = {
    1.0: 0.5470, 1.5: 0.5470, 2.0: 0.5557, 2.5: 0.5806, 3.0: 0.5987,
    3.5: 0.6116, 4.0: 0.6259, 4.5: 0.6408, 5.0: 0.6597, 5.5: 0.6711,
    6.0: 0.6975, 6.5: 0.7182, 7.0: 0.7311, 7.5: 0.7519, 8.0: 0.7641,
}

# Descriptive labels for the card and the alert, in probability points of edge
# over the price actually quoted. These COMMUNICATE the size of the predicted
# edge; they do not select. Boundaries sit near the quartiles of the backtested
# edge distribution (p25 +3.0pp, p75 +5.2pp).
EDGE_TIERS = ((3.0, "SMALL"), (5.5, "MEDIUM"), (float("inf"), "LARGE"))

# ---------------------------------------------------------------------------
# STAKING. Lives HERE, not in the publisher, so the card can print the number
# it is telling you to bet. The publisher reads `stake_pct` off the card CSV
# exactly as it already does for wind — one definition, one source of truth.
#
# Validated out-of-sample (walk-forward, calibrate on prior seasons only):
#   flat 1u                     601 bets  601u staked  +23.66u   +3.94%
#   Kelly x1, cap 2, no skip    601 bets  220u staked  +20.98u   +9.52%
#   Kelly x2, cap 4, skip 0.25  463 bets  424u staked  +41.08u   +9.68%
#
# The cap must move WITH the scale: at x2.7 with the cap left at 2, ROI fell to
# +7.58%, because the cap flattens exactly the big-edge bets sizing exists to
# find. Bets under MIN_UNITS are SKIPPED, not floored — a 0.5u floor tested
# out-of-sample added 132u of risk for -0.34u of profit.
# ---------------------------------------------------------------------------
UNIT_PCT = 0.01          # 1 unit = 1% of bankroll, same unit as the wind model
REF_KELLY = 0.0911       # wind's reference bet: lead 3, threshold 11, -110
STAKE_SCALE = 2.0
MAX_UNITS = 4.0          # must be >= 2 * STAKE_SCALE
MIN_UNITS = 0.25         # below this the bet is skipped entirely


def stake_units(model_prob: float, price: float) -> float:
    """
    Units to stake on one opener bet. Returns 0.0 when the bet is too small to
    want, which the caller must treat as "do not bet", not as "bet nothing".
    """
    b = (price / 100.0) if price > 0 else (100.0 / -price)
    if b <= 0:
        return 0.0
    kelly = max(0.0, (b * model_prob - (1 - model_prob)) / b)
    units = min(kelly / REF_KELLY * STAKE_SCALE, MAX_UNITS)
    return round(units, 3) if units >= MIN_UNITS else 0.0


def american_to_prob(px: float) -> float:
    return 100.0 / (px + 100.0) if px > 0 else -px / (-px + 100.0)


def model_prob_for_dev(dev: float) -> float:
    """
    P(win) for a bet taken at |dev| points off Pinnacle. Linear between the
    tabulated knots, clamped at both ends: below 1.0 nothing qualifies, and
    above 8.0 the table is already far outside the sample that fitted it.
    """
    d = abs(float(dev))
    keys = sorted(DEV_WIN_PROB)
    if d <= keys[0]:
        return DEV_WIN_PROB[keys[0]]
    if d >= keys[-1]:
        return DEV_WIN_PROB[keys[-1]]
    for lo, hi in zip(keys, keys[1:]):
        if lo <= d <= hi:
            w = (d - lo) / (hi - lo)
            return DEV_WIN_PROB[lo] + w * (DEV_WIN_PROB[hi] - DEV_WIN_PROB[lo])
    return POOLED_MODEL_PROB


def edge_tier(edge: float) -> str:
    """SMALL / MEDIUM / LARGE for an edge expressed as a probability fraction."""
    pp = float(edge) * 100.0
    for bound, label in EDGE_TIERS:
        if pp < bound:
            return label
    return EDGE_TIERS[-1][1]


def select_opener_bets(frame: pd.DataFrame, sched: pd.DataFrame,
                       threshold: float = DEPLOY_THRESHOLD) -> pd.DataFrame:
    """
    Pure selection: long snapshot frame (snapshot_to_frame shape: one row per
    event x book x market x side with home/away sides, price, point) + the
    window schedule -> one bet row per qualifying game.

    Mirrors backtest_opener's "first" variant at this snapshot: qualifying
    books ranked by |dev| descending, top one taken per game.
    """
    sp = frame[(frame.market == "spreads")
               & (~frame.book.isin(DEFECTIVE_BOOKS | EXCHANGES))].copy()
    if sp.empty:
        return pd.DataFrame()

    home = sp[sp.side == "home"][["event_id", "home", "away", "book", "price", "point"]]
    away = sp[sp.side == "away"][["event_id", "book", "price"]].rename(
        columns={"price": "px_away"})
    piv = home.rename(columns={"price": "px_home"}).merge(
        away, on=["event_id", "book"], how="inner")

    pin = (piv[piv.book == REFERENCE]
           .groupby(["home", "away"], as_index=False)
           .point.median().rename(columns={"point": "pin_home_line"}))
    if pin.empty:
        return pd.DataFrame()  # Pinnacle not live yet — nothing is decidable

    soft = piv[piv.book != REFERENCE].merge(pin, on=["home", "away"], how="inner")
    soft["dev"] = soft.point - soft.pin_home_line
    soft = soft[soft.dev.abs() >= threshold]
    if soft.empty:
        return pd.DataFrame()

    rows = []
    for r in soft.sort_values("dev", key=lambda s: s.abs(), ascending=False).itertuples():
        game = sched[(sched.home_team == r.home) & (sched.away_team == r.away)]
        if game.empty:
            continue
        game = game.iloc[0]
        bet_home = r.dev > 0            # soft gives home more points than the sharp line
        price = r.px_home if bet_home else r.px_away
        if pd.isna(price):
            continue
        side_line = r.point if bet_home else -r.point
        market_prob = american_to_prob(float(price))
        model_prob = model_prob_for_dev(r.dev)
        edge = model_prob - float(market_prob)
        units = stake_units(model_prob, int(price))
        if units <= 0:
            # Too small to want. Skipped rather than floored: the bets that
            # size tiny are the ones carrying almost no edge, and as a group
            # they lose money. The game is simply not locked yet, so a later
            # tick can still take it if the deviation grows.
            continue
        rows.append({
            "game_id": game.game_id,
            "matchup": game.matchup,
            "kick_utc": str(game.kick_utc),
            "lead_days": round(float(game.lead_days), 2),
            "side": "home" if bet_home else "away",
            "bet_team": r.home if bet_home else r.away,
            "book": r.book,
            "price": int(price),
            "side_line": float(side_line),
            "soft_home_line": float(r.point),
            "pin_home_line": float(r.pin_home_line),
            "dev": round(float(r.dev), 2),
            "model_prob": round(model_prob, 4),
            "market_prob": round(float(market_prob), 4),
            "edge": round(edge, 4),
            "edge_pp": round(edge * 100, 2),
            "edge_tier": edge_tier(edge),
            "units": units,
            "stake_pct": round(units * UNIT_PCT * 100, 3),
        })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    # One bet per game, largest |dev| first (the "first" variant's tie-break).
    return (out.sort_values("dev", key=lambda s: s.abs(), ascending=False)
            .groupby("game_id", as_index=False).first())


def evaluate_board(frame: pd.DataFrame, sched: pd.DataFrame,
                   threshold: float = DEPLOY_THRESHOLD) -> list[dict]:
    """
    Model's current view of EVERY scheduled game on the board, qualifying or
    not. Feeds the locked-pick history; it never selects anything.

    The distinction that matters here is between "no Pinnacle number yet" and
    "Pinnacle is up and the soft books agree with it". The first is the model
    waiting; the second is the model declining. A locked pick that reads
    "deviation gone" is a bet the market has since corrected — expected, and
    exactly what this is for.
    """
    from data_ingest.pick_eval import eval_row

    sp = frame[(frame.market == "spreads")
               & (~frame.book.isin(DEFECTIVE_BOOKS | EXCHANGES))].copy()

    out: list[dict] = []
    for g in sched.itertuples():
        lead_h = getattr(g, "lead_days", None)
        lead_h = None if lead_h is None else float(lead_h) * 24.0
        common = dict(game_id=g.game_id, model_id="nfl_opener_spread",
                      kick_utc=g.kick_utc, lead_hours=lead_h)

        rows = sp[(sp.home == g.home_team) & (sp.away == g.away_team)]
        if rows.empty:
            out.append(eval_row(qualifies=False, reason="no spread quotes on the board",
                                **common))
            continue

        pin = rows[(rows.book == REFERENCE) & (rows.side == "home")]
        if pin.empty:
            out.append(eval_row(qualifies=False,
                                reason="waiting on Pinnacle (posts ~T-6.5 days)",
                                **common))
            continue
        pin_line = float(pin.point.median())

        soft = rows[(rows.book != REFERENCE) & (rows.side == "home")].copy()
        if soft.empty:
            out.append(eval_row(qualifies=False, reason="no clean soft book quoting",
                                current_line=pin_line, **common))
            continue
        soft["dev"] = soft.point - pin_line
        best = soft.iloc[soft.dev.abs().values.argmax()]
        dev = float(best.dev)

        if abs(dev) < threshold:
            out.append(eval_row(
                qualifies=False,
                reason=f"deviation {dev:+.2f} below the {threshold} pt threshold",
                current_line=float(best.point), current_book=best.book,
                current_price=int(best.price), **common))
            continue

        prob = model_prob_for_dev(dev)
        edge = prob - american_to_prob(float(best.price))
        out.append(eval_row(
            qualifies=edge > 0,
            reason=(f"deviation {dev:+.2f} pts vs Pinnacle {pin_line:+.1f}"
                    if edge > 0 else
                    f"deviation {dev:+.2f} pts but the juice eats it ({edge*100:+.2f}pp)"),
            current_line=float(best.point), current_book=best.book,
            current_price=int(best.price), model_prob=round(prob, 4),
            edge=round(edge, 4), **common))
    return out

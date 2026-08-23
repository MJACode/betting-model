"""
Wind-suppressed totals: the frozen rule, its calibrated probability, and staking.

WHAT THIS IS
------------
A standing closing-line inefficiency, not a race. The market moves the total
about 2.6 points across the wind range while actual scoring falls about 6.2,
so it captures roughly 40% of the true wind effect. The bet is the UNDER on
outdoor games with high forecast wind, and it can be placed at any time up to
kickoff, including after the line has closed everywhere else.

WHAT IT IS NOT
--------------
It is not a spread play. Home cover rate is 48.8% / 49.4% / 48.9% in calm,
moderate and high wind. Totals only.

EVIDENCE
--------
Rule frozen on 1999-2015, tested on 2016-2025:
  nflverse observed wind >= 12 : 58.09% under, n=408
  ERA5 reanalysis    wind >= 12 : 59.32% under, n=354
The two sources agree on only 85.8% of flags, and the games where they
disagree hit at 62.1% (ERA5 only) and 59.0% (nflverse only). The effect is
physical wind, not a quirk of either data source.

Under MEASURED forecast error resampled onto 2016-2025:
  day-1 lead, threshold 12 : 57.63%  [52.6, 62.6]  P(beat vig) 0.980
  day-3 lead, threshold 12 : 57.09%  [52.4, 61.9]  P(beat vig) 0.975
  day-3 lead, threshold 11 : 56.71%  [52.3, 61.1]  P(beat vig) 0.972
  day-5 lead, threshold 12 : 56.17%  [51.0, 61.7]  P(beat vig) 0.916

Extended to every lead 1-7 at thresholds 11/12/13 by scripts/calibrate_lead.py,
which reproduces leads 1/3/5 to within 0.1pp. The edge decays about 0.41pp per
day of lead. Past lead 7 there is no measured forecast error, because
Open-Meteo's `previous_dayN` stops there.

STAKING
-------
1 unit = 1% of bankroll, sized Kelly-proportionally against a reference bet
(lead 3, threshold 11, -110), capped at 2 units, shaded on multi-game slates,
and zero past the calibrated lead range. Derived in scripts/stake_sizing.py.

LIVE RISK
---------
2024 and 2025 both lost on observed wind (-8.09u and +1.73u at -110 in ERA5
terms; -3.64u and -3.55u in the published nflverse terms). Two readings remain
live: ordinary variance at ~35 bets a season, or the market finally pricing
wind correctly. They cannot be separated yet. The unit stays at 1% and the
2-unit per-bet cap stays binding.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

# Calibrated under-rate by forecast lead, from resampling the measured
# forecast-error distribution onto the 2016-2025 outcome sample.
# Keyed by (lead_days, threshold_mph) on the Open-Meteo / ERA5 scale.
CALIBRATED_UNDER_RATE = {
    (0, 11): 0.6035, (0, 12): 0.5932, (0, 13): 0.5836,   # perfect knowledge, NOT LIVE
    (1, 11): 0.5735, (1, 12): 0.5763, (1, 13): 0.5758,
    (2, 11): 0.5700, (2, 12): 0.5735, (2, 13): 0.5745,   # interpolated between 1 and 3
    (3, 11): 0.5671, (3, 12): 0.5709, (3, 13): 0.5731,
    (4, 11): 0.5634, (4, 12): 0.5663, (4, 13): 0.5689,   # interpolated between 3 and 5
    (5, 11): 0.5596, (5, 12): 0.5617, (5, 13): 0.5647,
    # Leads 6-7 measured by scripts/calibrate_lead.py on the same method. That
    # run also reproduces leads 1/3/5 to within 0.1pp, which is the reason to
    # trust these two rows. `previous_dayN` stops at 7, so the table stops here.
    (6, 11): 0.5551, (6, 12): 0.5575, (6, 13): 0.5586,
    (7, 11): 0.5489, (7, 12): 0.5525, (7, 13): 0.5551,
}

# Empirical under rate by ERA5 wind bucket, 2016-2025, empirical-Bayes shrunk
# toward the 51.74% outdoor base rate with k=60. DIAGNOSTIC ONLY.
# Do not stake off these: the apparent fade above 15 mph rests on n=97 and
# n=64 and is not distinguishable from noise. Deployment uses the pooled rate.
BUCKET_DIAGNOSTIC = {
    "0-9": (1218, 0.4875), "9-11": (273, 0.5137), "11-13": (178, 0.6052),
    "13-15": (120, 0.6058), "15-18": (97, 0.5290), "18+": (64, 0.5246),
}

BREAKEVEN_110 = 0.5238
MIN_EDGE = 0.03          # project rule: 3% after vig
KELLY_FRACTION = 0.25    # project rule: 25% fractional Kelly
FLAT_CAP = 0.01          # 1% of bankroll. Keep this binding.

# ---------------------------------------------------------------------------
# STAKING
#
# Derived in scripts/stake_sizing.py; read that before changing any of these.
# The finding that matters: between 0.25% and 2% of bankroll the growth curve
# is still linear, because full Kelly on the measured edge is 9.1%. Median
# three-season return is 8.3-8.9x the stake at every size in that range, so
# nothing in the mathematics picks a number there. A drawdown budget does. The
# numbers below implement P(max drawdown > 35%) <= 5% and P(halving the roll)
# <= 2%, which puts the ceiling at 1.75% and the chosen unit at 1%.
#
# Sizing is Kelly-PROPORTIONAL: a bet is worth its own full-Kelly fraction
# divided by the reference bet's. That is scale-free, and it picks up price and
# forecast lead automatically, because full Kelly depends on the price and
# `model_under_prob` depends on the lead. Do not add a second lead multiplier.
#
# Note which "edge" does which job. The 3% MIN_EDGE gate is measured against the
# DE-VIGGED market probability, and that is the frozen rule; leave it alone. The
# sizing input is the Kelly edge, model probability against the raw price, which
# is what actually determines growth. They are different numbers and conflating
# them silently inflates every stake by roughly half a unit.
# ---------------------------------------------------------------------------
UNIT_PCT = 0.01          # 1 unit = 1% of bankroll
REF_KELLY = 0.0911       # full Kelly on the reference bet: lead 3, thr 11, -110
MAX_UNITS = 2.0          # hard per-bet cap
SLATE_UNIT_CAP = 3.0     # total units live on any one day
SLATE_RHO = 0.10         # within-slate outcome correlation, same weather system

# Longest forecast lead with a MEASURED error distribution. Open-Meteo's
# `previous_dayN` stops at 7, so leads beyond this have no calibration at all
# and are staked at zero rather than silently clipped to the lead-5 row.
MAX_CALIBRATED_LEAD = 7

# Shortest lead that is a MEASUREMENT. The lead-0 row is ERA5 truth, i.e. what
# the rule scores with perfect knowledge of the wind, and no forecast ever
# delivers it. Betting ten minutes before kickoff still gets a forecast, not the
# truth, so live probabilities floor at the lead-1 row. Using the lead-0 row
# there would inflate P(under) by 3pp and the stake by 0.7 units.
MIN_LIVE_LEAD = 1


def american_to_decimal(px: float) -> float:
    return 1.0 + (px / 100.0 if px > 0 else 100.0 / -px)


def american_to_prob(px: float) -> float:
    return 100.0 / (px + 100.0) if px > 0 else -px / (-px + 100.0)


def devig_two_way(px_a: float, px_b: float) -> tuple[float, float]:
    """
    Multiplicative de-vig. Adequate for a two-way total where the hold is
    small and roughly symmetric; do not reuse this on longshot markets where
    the favourite-longshot bias makes proportional de-vig badly wrong.
    """
    a, b = american_to_prob(px_a), american_to_prob(px_b)
    s = a + b
    if s <= 0:
        return float("nan"), float("nan")
    return a / s, b / s


def model_under_prob(lead_days: int, threshold: float = 11.0) -> float:
    """
    Calibrated P(under) for a qualifying game at a given forecast lead.

    Leads are floored at `MIN_LIVE_LEAD`, because the lead-0 row is a
    perfect-knowledge upper bound rather than anything a forecast delivers.
    Leads past `MAX_CALIBRATED_LEAD` clip to the last measured row, so the
    number returned there is an assumption rather than a measurement. Nothing
    should be staked on it: `stake_units` returns zero beyond that lead, and
    the card marks the row `calibrated_lead=False`.
    """
    lead = int(np.clip(round(lead_days), MIN_LIVE_LEAD, MAX_CALIBRATED_LEAD))
    thr = min(CALIBRATED_UNDER_RATE, key=lambda k: (k[0] != lead, abs(k[1] - threshold)))
    return CALIBRATED_UNDER_RATE[(lead, thr[1])]


def kelly_stake(p: float, px: float, fraction: float = KELLY_FRACTION,
                cap: float = FLAT_CAP) -> float:
    """
    Fractional Kelly as a share of bankroll, hard-capped.

    Kept as a diagnostic and for the older backtests. Deployment sizing goes
    through `stake_units`, which scales with the measured edge instead of with
    the model probability alone and which reports in units rather than percent.
    """
    b = american_to_decimal(px) - 1.0
    if b <= 0:
        return 0.0
    f = (b * p - (1 - p)) / b
    return float(max(0.0, min(f * fraction, cap)))


def slate_shade(k: int, rho: float = SLATE_RHO) -> float:
    """
    Per-bet multiplier that holds a k-game slate's risk equal to k independent
    bets. Wind games on one slate sit under the same synoptic system, so their
    outcomes correlate; k of them are worth k/(1+(k-1)rho) independent bets.
    """
    k = max(int(k), 1)
    return float(1.0 / np.sqrt(1.0 + (k - 1) * rho))


def stake_units(p_model: float, price: float, lead_days: float | None = None,
                slate_size: int = 1, ref_kelly: float = REF_KELLY,
                max_units: float = MAX_UNITS) -> float:
    """
    Units to stake on one bet. 1 unit is `UNIT_PCT` of bankroll.

    Kelly-proportional: this bet's full-Kelly fraction over the reference bet's.
    A reference bet (lead 3, threshold 11, -110) is 1.00 unit; -104 is 1.28
    units, -115 is 0.76, and a lead-7 bet at -110 is 0.58.

    Returns 0 beyond `MAX_CALIBRATED_LEAD`: there is no measured forecast-error
    distribution out there, so there is no probability to size against.
    """
    if p_model is None or price is None or not np.isfinite(p_model) or not np.isfinite(price):
        return 0.0
    if lead_days is not None and round(float(lead_days)) > MAX_CALIBRATED_LEAD:
        return 0.0
    b = american_to_decimal(price) - 1.0
    if b <= 0:
        return 0.0
    f = (b * p_model - (1 - p_model)) / b
    if f <= 0:
        return 0.0
    return float(min(f / ref_kelly, max_units) * slate_shade(slate_size))


def apply_slate_cap(bets: pd.DataFrame, cap: float = SLATE_UNIT_CAP) -> pd.DataFrame:
    """
    Scale a day's bets down proportionally if they exceed the daily unit cap.
    Grouping is by kickoff DATE, which is the unit a weather system acts on.
    """
    if bets.empty or "units" not in bets:
        return bets
    b = bets.copy()
    day = pd.to_datetime(b.kick_utc, utc=True, format="mixed").dt.date
    tot = b.groupby(day).units.transform("sum")
    b["units"] = np.where(tot > cap, b.units * cap / tot, b.units).round(3)
    b["stake_pct"] = (b.units * UNIT_PCT * 100).round(3)
    return b


@dataclass
class Bet:
    game_id: str
    matchup: str
    kick_utc: str
    stadium_id: str
    lead_days: float
    forecast_wind: float
    exp_true_wind: float
    total_line: float
    book: str
    price: int
    model_prob: float
    market_prob: float
    edge: float
    units: float
    stake_pct: float
    ev_pct: float
    calibrated_lead: bool

    def as_dict(self) -> dict:
        return asdict(self)


def select_bets(games: pd.DataFrame, threshold: float = 11.0,
                min_edge: float = MIN_EDGE, bankroll: float = 1.0) -> pd.DataFrame:
    """
    Apply the frozen rule to a slate.

    The threshold is applied to the RAW forecast, because that is exactly how
    the rule was validated. `expected_true_wind` is carried through for the card
    but never selects.

    `games` must carry, per game: game_id, matchup, kick_utc, stadium_id, roof,
    lead_days, forecast_wind, exp_true_wind, and the best available UNDER quote
    as best_book / best_total / best_under_px, plus best_over_px for de-vig.

    Indoor games are dropped before this is called; if any survive, they are
    dropped here too rather than silently scored.
    """
    from data_ingest.weather import INDOOR_ROOFS

    g = games[~games.roof.isin(INDOOR_ROOFS)].copy()
    g = g[g.forecast_wind >= threshold]
    if g.empty:
        return pd.DataFrame(columns=[f.name for f in Bet.__dataclass_fields__.values()])

    rows = []
    for r in g.itertuples():
        if pd.isna(r.best_under_px) or pd.isna(r.best_total):
            continue
        p_model = model_under_prob(r.lead_days, threshold)
        if pd.notna(getattr(r, "best_over_px", np.nan)):
            p_mkt, _ = devig_two_way(r.best_under_px, r.best_over_px)
        else:
            p_mkt = american_to_prob(r.best_under_px)
        edge = p_model - p_mkt
        if edge < min_edge:
            continue
        dec = american_to_decimal(r.best_under_px)
        rows.append(Bet(
            game_id=r.game_id, matchup=r.matchup, kick_utc=str(r.kick_utc),
            stadium_id=r.stadium_id, lead_days=round(float(r.lead_days), 2),
            forecast_wind=round(float(r.forecast_wind), 1),
            exp_true_wind=round(float(r.exp_true_wind), 1),
            total_line=float(r.best_total), book=r.best_book,
            price=int(r.best_under_px), model_prob=round(p_model, 4),
            market_prob=round(float(p_mkt), 4), edge=round(float(edge), 4),
            units=0.0, stake_pct=0.0,
            calibrated_lead=bool(round(float(r.lead_days)) <= MAX_CALIBRATED_LEAD),
            ev_pct=round((p_model * (dec - 1) - (1 - p_model)) * 100, 2),
        ).as_dict())

    out = pd.DataFrame(rows)
    if not len(out):
        return out

    # Slate size is counted over the bets that actually qualified, not over
    # every game that cleared the wind threshold, so it has to be a second pass.
    day = pd.to_datetime(out.kick_utc, utc=True, format="mixed").dt.date
    slate = day.map(day.value_counts())
    out["units"] = [round(stake_units(pm, px, ld, k), 3)
                    for pm, px, ld, k in zip(out.model_prob, out.price,
                                             out.lead_days, slate)]
    out["stake_pct"] = (out.units * UNIT_PCT * 100).round(3)
    out = apply_slate_cap(out)
    if bankroll != 1.0:
        out["stake_amt"] = (out.stake_pct / 100 * bankroll).round(2)
    return out.sort_values("edge", ascending=False).reset_index(drop=True)


def evaluate_board(games: pd.DataFrame, threshold: float = 11.0,
                   min_edge: float = MIN_EDGE) -> list[dict]:
    """
    Model's current view of EVERY outdoor game in the window, qualifying or
    not. Feeds the locked-pick history; it never selects anything.

    The reason string is the useful part on a locked pick. "forecast wind fell
    to 8.4 mph" is the case this whole mechanism exists for: the bet is already
    down at the locked total and cannot be retracted, but the condition that
    justified it is gone and that has to be visible rather than silently
    deleting the pick.
    """
    from data_ingest.pick_eval import eval_row
    from data_ingest.weather import INDOOR_ROOFS

    out: list[dict] = []
    for r in games.itertuples():
        lead_h = float(getattr(r, "lead_days", 0.0)) * 24.0
        common = dict(game_id=r.game_id, model_id="nfl_wind_totals",
                      kick_utc=r.kick_utc, lead_hours=lead_h)

        if getattr(r, "roof", None) in INDOOR_ROOFS:
            out.append(eval_row(qualifies=False, reason="indoor", **common))
            continue

        wind = getattr(r, "forecast_wind", None)
        if wind is None or pd.isna(wind):
            out.append(eval_row(qualifies=False, reason="no forecast available", **common))
            continue
        wind = float(wind)

        if wind < threshold:
            out.append(eval_row(
                qualifies=False,
                reason=f"forecast wind {wind:.1f} mph below the {threshold:.0f} mph threshold",
                **common))
            continue

        px = getattr(r, "best_under_px", None)
        total = getattr(r, "best_total", None)
        if px is None or pd.isna(px) or total is None or pd.isna(total):
            out.append(eval_row(qualifies=False,
                                reason=f"wind {wind:.1f} mph but no total quoted",
                                **common))
            continue

        lead_days = float(getattr(r, "lead_days", 0.0))
        p_model = model_under_prob(lead_days, threshold)
        over_px = getattr(r, "best_over_px", None)
        if over_px is not None and pd.notna(over_px):
            p_mkt, _ = devig_two_way(int(px), int(over_px))
        else:
            p_mkt = american_to_prob(int(px))
        edge = p_model - float(p_mkt)
        units = stake_units(p_model, int(px), lead_days)

        if round(lead_days) > MAX_CALIBRATED_LEAD:
            reason = (f"wind {wind:.1f} mph but lead {lead_days:.1f}d is beyond the "
                      f"{MAX_CALIBRATED_LEAD}-day calibration")
            qualifies = False
        elif edge < min_edge:
            reason = f"wind {wind:.1f} mph but edge {edge*100:+.2f}pp below {min_edge*100:.0f}pp"
            qualifies = False
        elif units <= 0:
            reason = f"wind {wind:.1f} mph but the model sizes this at zero units"
            qualifies = False
        else:
            reason = f"wind {wind:.1f} mph, edge {edge*100:+.2f}pp, {units:.2f} units"
            qualifies = True

        out.append(eval_row(
            qualifies=qualifies, reason=reason, current_line=float(total),
            current_price=int(px), current_book=getattr(r, "best_book", None),
            model_prob=round(p_model, 4), edge=round(float(edge), 4), **common))
    return out

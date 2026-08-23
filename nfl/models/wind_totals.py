"""
Wind-suppressed totals: the frozen rule, its calibrated probability, and staking.

(unchanged docstring ...)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

# Calibrated under-rate by forecast lead, from resampling the measured
# forecast-error distribution onto the 2016-2025 outcome sample.
# Keyed by (lead_days, threshold_mph) on the Open-Meteo / ERA5 scale.
CALIBRATED_UNDER_RATE = {
    (0, 11): 0.6035, (0, 12): 0.5932, (0, 13): 0.5836,   # perfect knowledge, upper bound
    (1, 11): 0.5735, (1, 12): 0.5763, (1, 13): 0.5758,
    (2, 11): 0.5700, (2, 12): 0.5735, (2, 13): 0.5745,   # interpolated between 1 and 3
    (3, 11): 0.5671, (3, 12): 0.5709, (3, 13): 0.5731,
    (4, 11): 0.5634, (4, 12): 0.5663, (4, 13): 0.5689,   # interpolated between 3 and 5
    (5, 11): 0.5596, (5, 12): 0.5617, (5, 13): 0.5647,
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

# Unit sizing for the poller / runbook: 1 unit == this fraction of bankroll.
UNIT_PCT = FLAT_CAP      # 1% by default; stake_sizing derives and recommends this.

# Maximum lead (in days) with a measured calibration. Leads beyond this are
# treated as uncalibrated / watch-only by the poller.
MAX_CALIBRATED_LEAD = 7


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
    """Calibrated P(under) for a qualifying game at a given forecast lead."""
    lead = int(np.clip(round(lead_days), 0, MAX_CALIBRATED_LEAD))
    thr = min(CALIBRATED_UNDER_RATE, key=lambda k: (k[0] != lead, abs(k[1] - threshold)))
    return CALIBRATED_UNDER_RATE[(lead, thr[1])]


def kelly_stake(p: float, px: float, fraction: float = KELLY_FRACTION,
                cap: float = FLAT_CAP) -> float:
    """Fractional Kelly as a share of bankroll, hard-capped."""
    b = american_to_decimal(px) - 1.0
    if b <= 0:
        return 0.0
    f = (b * p - (1 - p)) / b
    return float(max(0.0, min(f * fraction, cap)))


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
    stake_pct: float
    ev_pct: float

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
        stake = kelly_stake(p_model, r.best_under_px)
        dec = american_to_decimal(r.best_under_px)
        rows.append(Bet(
            game_id=r.game_id, matchup=r.matchup, kick_utc=str(r.kick_utc),
            stadium_id=r.stadium_id, lead_days=round(float(r.lead_days), 2),
            forecast_wind=round(float(r.forecast_wind), 1),
            exp_true_wind=round(float(r.exp_true_wind), 1),
            total_line=float(r.best_total), book=r.best_book,
            price=int(r.best_under_px), model_prob=round(p_model, 4),
            market_prob=round(float(p_mkt), 4), edge=round(float(edge), 4),
            stake_pct=round(stake * 100, 3),
            ev_pct=round((p_model * (dec - 1) - (1 - p_model)) * 100, 2),
        ).as_dict())

    out = pd.DataFrame(rows)
    return out.sort_values("edge", ascending=False).reset_index(drop=True) if len(out) else out
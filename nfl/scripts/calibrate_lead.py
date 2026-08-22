#!/usr/bin/env python3
"""
Extend the wind rule's calibration to long forecast leads (1..7 days).

WHY THIS EXISTS
---------------
`models/wind_totals.CALIBRATED_UNDER_RATE` stopped at lead 5, and
`model_under_prob` silently CLIPS anything longer to the lead-5 row. That was
harmless while the card was run Thursday-to-Sunday. It is not harmless once a
poller watches games 10 days out and fires on the first qualifying quote: a
lead-8 bet would then be staked off lead-5 probabilities.

Method is identical to `validate_wind_forecast.py --section sim`: take the
measured forecast-error distribution at lead N (Open-Meteo `previous_dayN`,
bucketed by true wind), resample it onto the 2016-2025 outcome sample, and read
the under rate off the games the noisy forecast would have selected.

`previous_dayN` exists for N in 1..7 only. Leads 8-10 cannot be measured with
this data and must be extrapolated; the fitted slope is printed for that.

    python scripts/calibrate_lead.py                 # leads 1-7, thresholds 11/12/13
    python scripts/calibrate_lead.py --draws 500     # faster, noisier

Costs zero Odds API credits. Weather pulls are cached under data/weather_cache
with their own keys, so this does not disturb the caches the other scripts use.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingest import weather as wx
from data_ingest.weather import STADIUM_COORDS, INDOOR_ROOFS

RNG = np.random.default_rng(20260817)
BINS = np.array([0, 4, 8, 10, 12, 14, 16, 18, 22, 99])
LEADS = (1, 2, 3, 4, 5, 6, 7)
FC_SPANS = [("2024-09-01", "2025-02-20"), ("2025-09-01", "2026-02-20")]
AR_SPANS = [("2016-09-01", "2019-02-20"), ("2019-09-01", "2022-02-20"),
            ("2022-09-01", "2024-02-20"), ("2024-09-01", "2026-02-20")]


def fetch_issued_all_leads(sid: str, start: str, end: str) -> pd.DataFrame:
    """
    Same call as weather.fetch_issued_forecasts but for every lead 1..7 and under
    its own cache key. The shipped helper keys its cache on (sid, start, end)
    only, so a file written for leads (1,3,5) would be replayed here without the
    extra columns.
    """
    lat, lon = STADIUM_COORDS[sid]
    hourly = ["wind_speed_10m"] + [f"wind_speed_10m_previous_day{i}" for i in LEADS]
    p = {"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
         "hourly": ",".join(hourly), "wind_speed_unit": "mph",
         "temperature_unit": "fahrenheit", "timezone": "UTC"}
    d = wx._get(wx.HISTFC_URL, p, f"issued_L17_{sid}_{start}_{end}")
    rename = {f"wind_speed_10m_previous_day{i}": f"fc_d{i}" for i in LEADS}
    return wx._frame(d, sid, rename)


def games() -> pd.DataFrame:
    g = pd.read_csv("data/games.csv")
    g = g[(g.season.between(2016, 2025)) & (~g.roof.isin(INDOOR_ROOFS))
          & g.stadium_id.isin(STADIUM_COORDS)].copy()
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                       nonexistent="shift_forward").dt.tz_convert("UTC"))
    return g


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    """D: games with ERA5 truth and the under outcome. H: hourly forecast/truth pairs."""
    g = games()
    sids = sorted(g.stadium_id.unique())
    print(f"loading weather for {len(sids)} stadiums ...", file=sys.stderr)

    ar = []
    for sid in sids:
        for s, e in AR_SPANS:
            try:
                ar.append(wx.fetch_era5(sid, s, e))
            except Exception as exc:                       # noqa: BLE001
                print(f"  skip era5 {sid} {s}: {exc}", file=sys.stderr)
    A = pd.concat(ar, ignore_index=True)

    fc = []
    for sid in sids:
        for s, e in FC_SPANS:
            try:
                fc.append(fetch_issued_all_leads(sid, s, e))
            except Exception as exc:                       # noqa: BLE001
                print(f"  skip issued {sid} {s}: {exc}", file=sys.stderr)
    F = pd.concat(fc, ignore_index=True)

    H = F.merge(A[["stadium_id", "ts", "era5_wind"]], on=["stadium_id", "ts"], how="inner")
    H = H.dropna(subset=["era5_wind"])

    g["hr"] = g.kick_utc.dt.floor("h")
    D = g.merge(A[["stadium_id", "ts", "era5_wind"]], left_on=["stadium_id", "hr"],
                right_on=["stadium_id", "ts"], how="left")
    # nflverse: `total` is the ACTUAL combined score, `total_line` is the number
    # the market hung. Comparing total against total against total is a push on
    # every row, which is exactly the silent failure this guard now catches.
    D["under"] = np.select([D.total < D.total_line, D.total == D.total_line], [1.0, 0.5], 0.0)
    D = D.dropna(subset=["total", "total_line", "era5_wind"])
    if (D.under != 0.5).sum() < 500:
        raise SystemExit("FATAL: almost every game graded as a push. Check the "
                         "total / total_line columns before trusting anything below.")
    return D, H


def resample(D: pd.DataFrame, H: pd.DataFrame, draws: int) -> pd.DataFrame:
    d = D[D.under != 0.5].copy()
    d["tb"] = np.digitize(d.era5_wind, BINS) - 1
    H = H.copy()
    H["tb"] = np.digitize(H.era5_wind, BINS) - 1
    truth, under, tb, n = d.era5_wind.values, d.under.values, d.tb.values, len(d)

    rows = []
    for lead in LEADS:
        col = f"fc_d{lead}"
        if col not in H or H[col].notna().sum() < 1000:
            print(f"  lead {lead}: no data, skipped", file=sys.stderr)
            continue
        err = H[col] - H.era5_wind
        pool = {}
        for b in H.tb.unique():
            v = err[H.tb == b].dropna().values
            if len(v) > 50:
                pool[b] = v
        allp = np.concatenate(list(pool.values()))
        for thr in (11, 12, 13):
            rates, vols = [], []
            for _ in range(draws):
                idx = RNG.integers(0, n, n)
                t, u, b = truth[idx], under[idx], tb[idx]
                noise = np.empty(n)
                for bb in np.unique(b):
                    m = b == bb
                    noise[m] = RNG.choice(pool.get(bb, allp), int(m.sum()), True)
                sel = (t + noise) >= thr
                if sel.sum() >= 5:
                    rates.append(u[sel].mean())
                    vols.append(int(sel.sum()))
            if len(rates) < 100:
                print(f"  lead {lead} thr {thr}: only {len(rates)} usable draws, skipped",
                      file=sys.stderr)
                continue
            r = np.array(rates)
            mu, ci = r.mean(), np.percentile(r, [2.5, 97.5])
            rows.append(dict(lead=lead, thr=thr,
                             n_hourly=int(H[col].notna().sum()),
                             err_sd=round(float(err.std()), 2),
                             bets_per_season=round(np.mean(vols) / 10, 1),
                             under=round(mu * 100, 2),
                             lo=round(ci[0] * 100, 1), hi=round(ci[1] * 100, 1),
                             roi110=round((mu * (100 / 110) - (1 - mu)) * 100, 2),
                             P_beat_vig=round(float((r > 0.5238).mean()), 3)))
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=2000)
    a = ap.parse_args()

    D, H = build()
    T = resample(D, H, a.draws)
    print("\n=== UNDER RATE BY FORECAST LEAD (measured error resampled onto 2016-2025) ===")
    print(T.to_string(index=False))

    print("\n=== DECAY OF THE EDGE WITH LEAD ===")
    for thr in (11, 12, 13):
        s = T[T.thr == thr]
        if len(s) < 3:
            continue
        slope, intercept = np.polyfit(s.lead, s.under, 1)
        ext = {L: round(intercept + slope * L, 2) for L in (8, 9, 10)}
        print(f"  thr {thr}: under = {intercept:.2f} {slope:+.3f} per day of lead   "
              f"extrapolated -> {ext}")
    print("\n  previous_dayN exists for N<=7 only. Leads 8-10 above are EXTRAPOLATION,")
    print("  not measurement, and the poller flags any bet fired at those leads.")

    out = "data/processed/lead_calibration.csv"
    T.to_csv(out, index=False)
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

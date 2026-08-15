#!/usr/bin/env python3
"""
Everything behind the wind rule's deployment numbers, in one runnable pass.

    python scripts/validate_wind_forecast.py            # all sections
    python scripts/validate_wind_forecast.py --section sim

Sections
  coverage   which Open-Meteo endpoints work, and when previous_dayN starts
  sources    Open-Meteo/ERA5 versus the nflverse wind column
  rule       the frozen rule on nflverse wind and on ERA5, 2016-2025
  error      measured forecast error by lead, unconditional and conditional
  sim        the powered validation: measured error resampled onto 2016-2025

Weather pulls are cached under data/weather_cache, so reruns are free and fast.
Odds are not touched, so this costs zero Odds API credits.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ingest.weather import (STADIUM_COORDS, INDOOR_ROOFS, ISSUED_FORECAST_START,
                                 fetch_era5, fetch_issued_forecasts, wind_at_kickoff)

RNG = np.random.default_rng(20260815)
BINS = np.array([0, 4, 8, 10, 12, 14, 16, 18, 22, 99])
FC_SPANS = [("2024-09-01", "2025-02-20"), ("2025-09-01", "2026-02-20")]
AR_SPANS = [("2016-09-01", "2019-02-20"), ("2019-09-01", "2022-02-20"),
            ("2022-09-01", "2024-02-20"), ("2024-09-01", "2026-02-20")]


def games() -> pd.DataFrame:
    g = pd.read_csv("data/games.csv")
    g = g[(g.season.between(2016, 2025)) & (~g.roof.isin(INDOOR_ROOFS))
          & g.stadium_id.isin(STADIUM_COORDS)].copy()
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                       nonexistent="shift_forward").dt.tz_convert("UTC"))
    return g


def hourly(kind: str, sids) -> pd.DataFrame:
    spans = FC_SPANS if kind == "fc" else AR_SPANS
    out = []
    for sid in sids:
        for s, e in spans:
            f = fetch_issued_forecasts if kind == "fc" else fetch_era5
            try:
                out.append(f(sid, s, e) if kind == "ar" else f(sid, s, e, leads=(1, 3, 5)))
            except Exception as exc:                      # noqa: BLE001
                print(f"  skip {kind} {sid} {s}: {exc}", file=sys.stderr)
    return pd.concat([d for d in out if len(d)], ignore_index=True)


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    g = games()
    sids = sorted(g.stadium_id.unique())
    print(f"loading weather for {len(sids)} stadiums ...", file=sys.stderr)
    fc, ar = hourly("fc", sids), hourly("ar", sids)
    H = fc.merge(ar, on=["stadium_id", "ts"], how="inner").dropna(subset=["era5_wind"])
    D = g.copy()
    for col, src in [("era5_wind", ar), ("om_analysis", fc),
                     ("fc_d1", fc), ("fc_d3", fc), ("fc_d5", fc)]:
        D[col] = wind_at_kickoff(src, D, col).reindex(D.game_id).values
    D["under"] = np.select([D.total < D.total_line, D.total == D.total_line], [1.0, 0.5], 0.0)
    return D, H


def sec_coverage(H):
    print("\n=== COVERAGE ===")
    print(f"  issued forecasts (previous_dayN) begin {ISSUED_FORECAST_START};"
          " before that only the assembled near-analysis series exists")
    print(f"  matched hourly forecast/ERA5 pairs: {len(H):,}")
    print("  previous-runs-api.open-meteo.com is NOT reachable from the project sandbox")


def sec_sources(D):
    print("\n=== SOURCE AGREEMENT: Open-Meteo vs nflverse `wind` ===")
    for c in ("era5_wind", "om_analysis"):
        s = D[D.wind.notna() & D[c].notna()]
        if len(s) < 50:
            continue
        print(f"  {c:12s} n={len(s):5d} corr={np.corrcoef(s.wind, s[c])[0,1]:.3f} "
              f"bias={(s[c]-s.wind).mean():+.2f} sd_diff={(s[c]-s.wind).std():.2f}")
    s = D[D.wind.notna() & D.era5_wind.notna()]
    a, b = s.era5_wind >= 12, s.wind >= 12
    print(f"  >=12 flag agreement {(a == b).mean()*100:.1f}%  "
          f"(nflverse {int(b.sum())}, ERA5 {int(a.sum())}, both {int((a & b).sum())})")
    for lab, m in [("both", a & b), ("ERA5 only", a & ~b), ("nflverse only", ~a & b)]:
        x = s[m & (s.under != 0.5)]
        if len(x):
            print(f"    {lab:14s} n={len(x):4d} under={x.under.mean()*100:5.1f}%")


def _rate(s):
    d = s[s.under != 0.5]
    wr = d.under.mean()
    bs = np.array([RNG.choice(d.under.values, len(d), True).mean() for _ in range(4000)])
    return len(d), wr, np.percentile(bs, [2.5, 97.5])


def sec_rule(D):
    print("\n=== FROZEN RULE, 2016-2025 (frozen on 1999-2015) ===")
    for lab, m in [("nflverse wind >= 12", D.wind >= 12), ("ERA5 wind >= 12", D.era5_wind >= 12)]:
        n, wr, ci = _rate(D[m])
        print(f"  {lab:22s} n={n:4d} under={wr*100:5.2f}% CI=[{ci[0]*100:.1f},{ci[1]*100:.1f}] "
              f"ROI@-110={(wr*(100/110)-(1-wr))*100:+.2f}%")


def sec_error(D, H):
    print("\n=== MEASURED FORECAST ERROR vs ERA5 ===")
    for lead in (1, 3, 5):
        e = H[f"fc_d{lead}"] - H.era5_wind
        print(f"  day-{lead}: n={e.notna().sum():,} bias={e.mean():+.2f} "
              f"sd={e.std():.2f} mae={e.abs().mean():.2f}")
    print("\n  E[true | forecast] - forecast, by forecast bucket (the live-valid correction):")
    for lead in (1, 3, 5):
        H["fb"] = np.digitize(H[f"fc_d{lead}"], BINS) - 1
        t = H.groupby("fb").agg(n=(f"fc_d{lead}", "size"), fc=(f"fc_d{lead}", "mean"),
                                truth=("era5_wind", "mean"))
        t["adj"] = (t.truth - t.fc).round(2)
        t.index = [f"{BINS[i]}-{BINS[i+1]}" for i in t.index]
        print(f"    lead {lead}: " + "  ".join(f"{k}:{v:+.2f}" for k, v in t.adj.items()))


def sec_sim(D, H):
    print("\n=== POWERED VALIDATION: measured error resampled onto 2016-2025 ===")
    d = D[D.under != 0.5].dropna(subset=["era5_wind"]).copy()
    d["tb"] = np.digitize(d.era5_wind, BINS) - 1
    H = H.copy(); H["tb"] = np.digitize(H.era5_wind, BINS) - 1
    truth, under, tb, n = d.era5_wind.values, d.under.values, d.tb.values, len(d)
    rows = []
    for lead in (1, 3, 5):
        pool = {b: v[~np.isnan(v)] for b, v in
                {b: (H.loc[H.tb == b, f"fc_d{lead}"].values - H.loc[H.tb == b, "era5_wind"].values)
                 for b in H.tb.unique()}.items() if (~np.isnan(v)).sum() > 50}
        allp = np.concatenate(list(pool.values()))
        for thr in (11, 12, 13):
            rates, vols = [], []
            for _ in range(2000):
                idx = RNG.integers(0, n, n)
                t, u, b = truth[idx], under[idx], tb[idx]
                noise = np.empty(n)
                for bb in np.unique(b):
                    m = b == bb
                    noise[m] = RNG.choice(pool.get(bb, allp), int(m.sum()), True)
                sel = (t + noise) >= thr
                if sel.sum() >= 5:
                    rates.append(u[sel].mean()); vols.append(int(sel.sum()))
            r = np.array(rates); mu = r.mean(); ci = np.percentile(r, [2.5, 97.5])
            rows.append(dict(lead=lead, thr=thr, bets_per_season=round(np.mean(vols) / 10, 1),
                             under=round(mu * 100, 2),
                             ci=f"[{ci[0]*100:.1f},{ci[1]*100:.1f}]",
                             roi110=round((mu * (100 / 110) - (1 - mu)) * 100, 2),
                             P_beat_vig=round(float((r > 0.5238).mean()), 3)))
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n  CIs bootstrap over games AND forecast noise jointly.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", choices=["coverage", "sources", "rule", "error", "sim", "all"],
                    default="all")
    a = ap.parse_args()
    D, H = build()
    run = {"coverage": [sec_coverage], "sources": [sec_sources], "rule": [sec_rule],
           "error": [sec_error], "sim": [sec_sim]}
    if a.section == "all":
        sec_coverage(H); sec_sources(D); sec_rule(D); sec_error(D, H); sec_sim(D, H)
    else:
        f = run[a.section][0]
        f(H) if a.section == "coverage" else (
            f(D) if a.section in ("sources", "rule") else f(D, H))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

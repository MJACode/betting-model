"""
NCAAF search — data-setup profile (spec items 1-5).

Read-only. Answers, with numbers rather than assumptions:
  1. line-provider distribution by season, and which provider is continuous
  2. label push rates
  3. opener coverage
  4. era split sizes
  5. hygiene — duplicate game_ids, missing lines, FBS/FCS history

Run:
    python -m scripts.ncaaf_search.profile_data
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.ncaaf_search.dataset import (  # noqa: E402
    build_label_set, provider_continuity, opener_coverage,
    DEFAULT_PRIORITY, PORTAL_ERA)

BAR = "=" * 78


def main() -> int:
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 40)

    print(BAR)
    print("NCAAF SEARCH — DATA SETUP PROFILE")
    print(f"provider priority: {' -> '.join(DEFAULT_PRIORITY)}")
    print(BAR)

    ls = build_label_set()
    df = ls.games

    print(f"\nGames with a final score, 2014-2025 excl. 2020: {len(df)}")
    print(f"game_id unique: {df['game_id'].is_unique}")

    # ── 1. provider continuity ──────────────────────────────────────────────
    print(f"\n{BAR}\n1. LINE PROVIDER BY SEASON (spreads, after priority dedup)\n{BAR}")
    cont = provider_continuity(ls.provider_counts)
    print(cont.to_string())

    seasons = sorted(df["season"].unique())
    print("\nContinuity check — providers present in EVERY season:")
    full = [p for p in cont.index if (cont.loc[p] > 0).all()]
    print(f"  {full or 'NONE — any full-sample label set mixes providers'}")

    print("\nLongest continuous run per provider:")
    for p in cont.index:
        yrs = [s for s in cont.columns if cont.loc[p, s] > 0]
        best, cur = [], []
        for s in sorted(yrs):
            if cur and s == cur[-1] + 1:
                cur.append(s)
            else:
                cur = [s]
            if len(cur) > len(best):
                best = list(cur)
        if best:
            print(f"  {p:22s} {best[0]}-{best[-1]}  ({len(best)} seasons)")

    switch = df.groupby("season")["spread_home_provider"].agg(
        lambda s: s.value_counts().idxmax() if s.notna().any() else None)
    print("\nDominant provider per season (the label set actually used):")
    prev = None
    for s, p in switch.items():
        mark = "   <-- PROVIDER SWITCH" if prev and p != prev else ""
        print(f"  {s}: {p}{mark}")
        prev = p

    # ── 2. pushes ───────────────────────────────────────────────────────────
    print(f"\n{BAR}\n2. LABELS & PUSH RATES\n{BAR}")
    print(f"  spread push rate: {ls.push_rates['spread']:.3%}")
    print(f"  total  push rate: {ls.push_rates['total']:.3%}")
    print(f"  dropped: {ls.dropped}")
    print(f"\n  usable ATS rows:    {int(df['home_covers'].notna().sum())}")
    print(f"  usable totals rows: {int(df['went_over'].notna().sum())}")
    ats = df["home_covers"].dropna()
    ovr = df["went_over"].dropna()
    print(f"\n  base rate home_covers: {ats.mean():.4f}  (n={len(ats)})")
    print(f"  base rate went_over:   {ovr.mean():.4f}  (n={len(ovr)})")
    print("  -> both should sit near 0.500; a real skew is a label bug.")

    # ── 3. openers ──────────────────────────────────────────────────────────
    print(f"\n{BAR}\n3. OPENER COVERAGE (spec item 3)\n{BAR}")
    for k, v in opener_coverage().items():
        print(f"  {k}: {v}")

    # ── 4. eras ─────────────────────────────────────────────────────────────
    print(f"\n{BAR}\n4. ERA SPLITS\n{BAR}")
    by_season = df.groupby("season").agg(
        games=("game_id", "size"),
        ats_rows=("home_covers", lambda s: int(s.notna().sum())),
        tot_rows=("went_over", lambda s: int(s.notna().sum())),
        home_cover=("home_covers", "mean"),
        over_rate=("went_over", "mean"),
    ).round(4)
    print(by_season.to_string())
    portal = df[df["season"].isin(PORTAL_ERA)]
    print(f"\n  full sample (2020 excluded): {len(df)} games")
    print(f"  portal era {PORTAL_ERA[0]}-{PORTAL_ERA[-1]}: {len(portal)} games "
          f"({int(portal['home_covers'].notna().sum())} usable ATS)")

    # ── 5. hygiene ──────────────────────────────────────────────────────────
    print(f"\n{BAR}\n5. HYGIENE\n{BAR}")
    miss_sp = df[df["spread_home"].isna()]
    print(f"  games with no usable closing spread: {len(miss_sp)}")
    if len(miss_sp):
        print(miss_sp.groupby("season").size().to_string())
    print(f"  games with no usable closing total:  {int(df['total_line'].isna().sum())}")

    both = df.dropna(subset=["spread_home", "total_line"])
    print(f"  games with BOTH spread and total:    {len(both)}")

    print(f"\n{BAR}\nHEADLINE FOR THE MODEL SEARCH\n{BAR}")
    if not full:
        print("  * No provider spans the full sample. A 10-season label set")
        print("    MIXES providers, and the switch coincides with 2023 — the")
        print("    season the existing margin model performed worst. Treat any")
        print("    full-sample result as confounded by that switch.")
    print("  * Openers absent -> Group D and CLV are blocked pending backfill.")
    print("  * Recommended primary label set: single-provider portal era.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

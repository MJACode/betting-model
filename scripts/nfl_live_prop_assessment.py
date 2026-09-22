"""
The standing assessment for `nfl_live_prop`: is there a live prop edge at all?

Reproduces every table in `docs/nfl_live_prop_assessment.md`. Zero Odds API
credits — the quotes were bought years ago and live in Supabase
(`nfl_live_prop_snapshots`, 5,333 checksum-verified files).

    python -m scripts.nfl_live_prop_assessment --restore   # pull the archive
    python -m scripts.nfl_live_prop_assessment             # every table
    python -m scripts.nfl_live_prop_assessment --section 3

WHY THIS EXISTS. The lane shipped on "DK's live pass-attempt line sits 2.33
attempts below the final". Re-measured on the same archive that number is
-0.12, CI (-0.42, +0.18). The model that priced it emitted a CONSTANT, so its
EV threshold was a pure price filter — which is why tightening it produced no
picks and loosening it produced the over on every game.

Sections:
    1  the output was a constant                   (production picks)
    2  the bias, at the correct unit of analysis   (clustered on game)
    3  graded at real prices, and why tightening hurts
    4  the market grid — every market, both sides
    5  can game state rescue it (needs play-by-play)
"""
from __future__ import annotations

import argparse
import glob
import os

import numpy as np
import pandas as pd

QUOTES = "nfl/data/live_model/_quotes_graded.parquet"
STATE = "nfl/data/live_model/_quotes_state.parquet"
MARKET_STAT = {
    "player_pass_attempts": "attempts",
    "player_pass_completions": "completions",
    "player_receptions": "receptions",
    "player_rush_attempts": "carries",
}
MIN_PRICE = -140.0
P_SHIPPED = 0.600344          # Phi(1.50 / 5.90), the constant the lane emitted


# ----------------------------------------------------------------- utilities
def american_b(a):
    """Decimal profit per unit staked."""
    a = np.asarray(a, dtype=float)
    return np.where(a > 0, a / 100.0, 100.0 / np.abs(np.where(a == 0, -100.0, a)))


def implied(a):
    a = np.asarray(a, dtype=float)
    return np.where(a < 0, -a / (-a + 100.0), 100.0 / (a + 100.0))


def cluster_se_mean(x, groups) -> float:
    """Cluster-robust SE of a sample mean. Snapshots of one game are not
    independent draws, and the naive SE understates by 1.4-1.8x here."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 2:
        return float("nan")
    s = pd.Series(x - x.mean()).groupby(np.asarray(groups)).sum().to_numpy()
    return float(np.sqrt((s ** 2).sum()) / n)


def boot_ci(prof, groups, draws: int = 4000, seed: int = 0):
    """Bootstrap a mean by resampling GAMES, not quotes."""
    rng = np.random.default_rng(seed)
    gs = [g.to_numpy() for _, g in pd.Series(np.asarray(prof, dtype=float))
          .groupby(np.asarray(groups))]
    if len(gs) < 3:
        return (float("nan"), float("nan"))
    idx = np.arange(len(gs))
    out = [np.concatenate([gs[i] for i in rng.choice(idx, len(gs), replace=True)]).mean()
           for _ in range(draws)]
    return tuple(np.percentile(out, [5, 95]) * 100)


# ------------------------------------------------------------------ the data
def restore_archive() -> None:
    from dotenv import load_dotenv
    load_dotenv()
    from nfl.live_model.backtest.backup_snaps import restore, _connect, SNAP_DIR
    conn = _connect()
    try:
        print(f"restored: {restore(conn, SNAP_DIR)} -> {SNAP_DIR}")
    finally:
        conn.close()


def build() -> pd.DataFrame:
    """Quotes joined to actual finals. One row per two-sided quote."""
    from dotenv import load_dotenv
    load_dotenv()
    from sqlalchemy import create_engine
    from nfl.live_model.backtest.flow_validate import load_snapshots, norm_name

    q = load_snapshots()
    q["ts"] = pd.to_datetime(q["ts"], utc=True, errors="coerce")
    q["commence_time"] = pd.to_datetime(q["commence_time"], utc=True, errors="coerce")
    q = q.dropna(subset=["ts", "commence_time"])
    # The game's EASTERN date: a 01:05 UTC kickoff is the previous evening, and
    # joining on the UTC date would miss every night game.
    q["game_date"] = q["commence_time"].dt.tz_convert(
        "America/New_York").dt.date.astype(str)
    q["join_name"] = q["player_name"].map(lambda n: norm_name(n).replace(" ", ""))
    q["stat"] = q["market"].map(MARKET_STAT)
    q = q.dropna(subset=["stat"])

    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
    log = pd.read_sql(
        "SELECT norm_name, game_date, season, game_id, attempts, completions, "
        "receptions, carries FROM nfl_player_game_log WHERE season BETWEEN 2023 AND 2025",
        create_engine(url))
    long = log.melt(id_vars=["norm_name", "game_date", "season", "game_id"],
                    value_vars=list(MARKET_STAT.values()),
                    var_name="stat", value_name="final").dropna(subset=["final"])

    m = q.merge(long, left_on=["join_name", "game_date", "stat"],
                right_on=["norm_name", "game_date", "stat"], how="left")
    m = m[m["final"].notna()].copy()
    m["final"] = m["final"].astype(float)
    m["err"] = m["line"] - m["final"]          # NEGATIVE = book posts LOW
    m["went_over"] = (m["final"] > m["line"]).astype(int)
    m["push"] = (m["final"] == m["line"]).astype(int)
    tot = implied(m["over_price"]) + implied(m["under_price"])
    m["imp_over"] = implied(m["over_price"]) / tot
    m["hold"] = tot - 1.0
    m["unit"] = m["game_id"].astype(str) + "|" + m["join_name"]
    m["season"] = pd.to_datetime(m["commence_time"], utc=True).dt.year.where(
        pd.to_datetime(m["commence_time"], utc=True).dt.month >= 3,
        pd.to_datetime(m["commence_time"], utc=True).dt.year - 1)
    os.makedirs(os.path.dirname(QUOTES), exist_ok=True)
    m.to_parquet(QUOTES, index=False)
    return m


def load() -> pd.DataFrame:
    if not os.path.exists(QUOTES):
        print("building the quote/final join (first run)...")
        return build()
    return pd.read_parquet(QUOTES)


# -------------------------------------------------------------- the sections
def section1() -> None:
    print("\n1. THE OUTPUT WAS A CONSTANT — every pick the lane ever wrote")
    print("   Phi(DEPLOY_BIAS/SIGMA) = Phi(1.50/5.90) = %.6f, for every quote."
          % P_SHIPPED)
    print(f"   At p={P_SHIPPED:.4f} the fair price is "
          f"{-100*P_SHIPPED/(1-P_SHIPPED):+.1f}, so the EV cut is a PRICE cut:")
    for ev in (0.06, 0.10):
        b = (ev + 1 - P_SHIPPED) / P_SHIPPED
        am = 100 * b if b >= 1 else -100 / b
        print(f"     EV >= {ev:.2f}  ->  bets anything priced better than {am:+.1f}")
    print("   Run this against production to see the two constants it emitted:")
    print("     SELECT model_probability, signal_type, COUNT(*) FROM picks")
    print("      WHERE model_id='nfl_live_prop' GROUP BY 1,2;")


def section2(d: pd.DataFrame) -> None:
    print("\n2. THE BIAS, AT THE CORRECT UNIT   (err = line - final; "
          "NEGATIVE = book posts low)")
    print(f"   {'market':17s}{'book':11s}{'quotes':>7s}{'units':>7s}{'games':>6s}"
          f"{'bias':>8s}{'SEnaive':>9s}{'SEclust':>9s}{'95% CI (clustered)':>24s}")
    for (mkt, book), g in d.groupby(["market", "book"]):
        if len(g) < 300:
            continue
        b = g["err"].mean()
        se_n = g["err"].std(ddof=1) / np.sqrt(len(g))
        se_c = cluster_se_mean(g["err"], g["game_id"])
        print(f"   {mkt.replace('player_',''):17s}{book:11s}{len(g):7,d}"
              f"{g['unit'].nunique():7,d}{g['game_id'].nunique():6d}{b:+8.2f}"
              f"{se_n:9.3f}{se_c:9.3f}"
              f"     ({b-1.96*se_c:+.2f}, {b+1.96*se_c:+.2f})")

    pa = d[(d.market == "player_pass_attempts") & (d.book == "draftkings")]
    print("\n   pass attempts @ DK, by season — no season supports -2.33:")
    print(f"   {'season':8s}{'quotes':>8s}{'bias':>8s}{'SEclust':>9s}{'t':>7s}"
          f"{'over rate':>11s}")
    for s, g in pa.groupby("season"):
        se_c = cluster_se_mean(g["err"], g["game_id"])
        print(f"   {int(s):<8d}{len(g):8,d}{g['err'].mean():+8.2f}{se_c:9.3f}"
              f"{g['err'].mean()/se_c:7.1f}{100*g['went_over'].mean():10.1f}%")
    print(f"\n   join sanity: corr(line, final)={np.corrcoef(pa['line'], pa['final'])[0,1]:.3f}"
          f"  mean line={pa['line'].mean():.1f}  mean final={pa['final'].mean():.1f}"
          f"  MAE={pa['err'].abs().mean():.2f}")
    print("   (the original reported MAE 4.72-4.97 — the SPREAD reproduces, "
          "only the CENTRE does not)")


def section3(d: pd.DataFrame) -> None:
    print("\n3. GRADED AT REAL PRICES — the shipped rule, and why tightening hurts")
    pa = d[(d.market == "player_pass_attempts") & (d.book == "draftkings")].copy()
    b = american_b(pa["over_price"])
    pa["prof"] = np.where(pa["push"] == 1, 0.0, np.where(pa["went_over"] == 1, b, -1.0))
    pa["ev"] = P_SHIPPED * b - (1 - P_SHIPPED)
    print(f"   {'arm':34s}{'bets':>7s}{'units':>9s}{'ROI':>9s}{'90% CI':>20s}")
    for name, sub in [("every over, no filter", pa)] + [
            (f"EV >= {ev:.2f}, price >= -140",
             pa[(pa.ev >= ev) & (pa.over_price >= MIN_PRICE)])
            for ev in (0.00, 0.06, 0.10)]:
        if sub.empty:
            continue
        lo, hi = boot_ci(sub["prof"], sub["game_id"])
        print(f"   {name:34s}{len(sub):7,d}{sub['prof'].sum():+9.1f}"
              f"{100*sub['prof'].mean():+8.2f}%   ({lo:+6.1f},{hi:+6.1f})")

    ship = pa[(pa.ev >= 0.06) & (pa.over_price >= MIN_PRICE)]
    print("\n   per season at the shipped cut:")
    for s, g in ship.groupby("season"):
        print(f"     {int(s)}  {len(g):5,d} bets  {g['prof'].sum():+8.1f}u  "
              f"{100*g['prof'].mean():+7.2f}%")

    slope = np.polyfit(pa["imp_over"], pa["went_over"], 1)[0]
    print(f"\n   the book's price IS informative: OLS slope of outcome on "
          f"de-vigged price = {slope:+.2f}")
    print("   (1.0 = perfectly calibrated, so the cheapest overs are the least likely)")
    print(f"   {'':22s}{'bets':>7s}{'mean de-vigged':>16s}{'actual over':>13s}")
    for nm, sub in (("kept by EV>=0.06", ship),
                    ("rejected", pa[~pa.index.isin(ship.index)])):
        print(f"   {nm:22s}{len(sub):7,d}{sub['imp_over'].mean():16.3f}"
              f"{sub['went_over'].mean():13.3f}")
    print(f"   the model asserted {P_SHIPPED:.4f} on every one of those rows.")


def section4(d: pd.DataFrame) -> None:
    print("\n4. THE MARKET GRID — every market, both sides, blind, at the posted price")
    print("   edge = actual hit rate minus the book's own de-vigged probability")
    print(f"   {'market':17s}{'book':11s}{'side':7s}{'quotes':>7s}{'units':>9s}"
          f"{'ROI':>9s}{'90% CI':>19s}{'edge':>7s}")
    for (mkt, book), g in d.groupby(["market", "book"]):
        if len(g) < 300:
            continue
        for side in ("over", "under"):
            bb = american_b(g[f"{side}_price"])
            won = ((g["went_over"] == 1) if side == "over"
                   else (g["went_over"] == 0)) & (g["push"] == 0)
            prof = np.where(g["push"] == 1, 0.0, np.where(won, bb, -1.0))
            devig = g["imp_over"] if side == "over" else 1 - g["imp_over"]
            lo, hi = boot_ci(prof, g["game_id"])
            print(f"   {mkt.replace('player_',''):17s}{book:11s}{side:7s}{len(g):7,d}"
                  f"{prof.sum():+9.1f}{100*prof.mean():+8.2f}%   ({lo:+6.1f},{hi:+6.1f})"
                  f"{100*(won.mean()-devig.mean()):+7.1f}")
    print("\n   The live market leans OVER exactly as the pre-game one does")
    print("   (docs/nfl_prop_over_lean.md). The shipped model bet the over.")
    print("   It is still not a bet: the hold is ~6.5% and the lean is 1-2.5pp.")


def section5() -> None:
    print("\n5. CAN GAME STATE RESCUE IT?")
    if not os.path.exists(STATE):
        print("   needs nflverse play-by-play and the state join:")
        print("     python -m nfl.live_model.backtest.pull_pbp --seasons 2023 2024 2025")
        print("   then see docs/nfl_live_prop_assessment.md section 5 for the result:")
        print("     in sample  chi2=16.13 df=6 p=0.013, and the book prices")
        print("                almost no state at all (R2=0.010)")
        print("     out of sample  log loss 0.6917 vs market 0.6917 — IDENTICAL")
        return
    import statsmodels.api as sm
    from scipy import stats
    m = pd.read_parquet(STATE)
    feats = ["trail", "secs", "accrued", "slack", "pace", "trail_x_sqrt_t"]
    d = m.dropna(subset=["imp_over"] + feats)
    y = d["went_over"].to_numpy(float)
    r0 = sm.Logit(y, sm.add_constant(d[["imp_over"]])).fit(disp=0)
    r1 = sm.Logit(y, sm.add_constant(d[["imp_over"] + feats])).fit(disp=0)
    lr = 2 * (r1.llf - r0.llf)
    print(f"   in sample: chi2={lr:.2f} df={len(feats)} "
          f"p={stats.chi2.sf(lr, len(feats)):.4f}  (n={len(d):,})")
    rs = sm.OLS(d["imp_over"].to_numpy(float), sm.add_constant(d[feats])).fit()
    print(f"   the book's own price on state: R2={rs.rsquared:.3f} "
          f"(it prices almost no state)")
    print("   out of sample (train 23-24, test 25): see the doc — it ties the market.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--restore", action="store_true",
                    help="pull the quote archive back out of Supabase first")
    ap.add_argument("--rebuild", action="store_true",
                    help="rebuild the quote/final join from the archive")
    ap.add_argument("--section", type=int, choices=[1, 2, 3, 4, 5], default=None)
    a = ap.parse_args()

    if a.restore:
        restore_archive()
    d = build() if a.rebuild else load()
    print(f"\n{len(d):,} graded two-sided quotes, "
          f"{d['game_id'].nunique():,} games, "
          f"{d['season'].min():.0f}-{d['season'].max():.0f}, "
          f"mean hold {100*d['hold'].mean():.1f}%")

    run = [a.section] if a.section else [1, 2, 3, 4, 5]
    for s in run:
        {1: lambda: section1(), 2: lambda: section2(d), 3: lambda: section3(d),
         4: lambda: section4(d), 5: lambda: section5()}[s]()


if __name__ == "__main__":
    main()

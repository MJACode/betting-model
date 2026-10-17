"""
Kalshi NFL game-winner markets: is there +EV a sportsbook does not offer?
(NFL edge search; data from scripts/nfl_edge_kalshi_fetch.py, which reads only
Kalshi's free no-login market-data API and caches the raw responses.)

CONSTRUCTION - written before any price or outcome was looked at.

Data.  KXNFLGAME (series "NFL Game", fee_type quadratic_with_maker_fees,
  multiplier 1). One market per team per game; we fetched only the HOME team's
  market, 1-minute candles, kickoff-8h .. kickoff+5h. Taker prices:
    buy HOME = home yes_ask (close of the 1-minute candle)
    buy AWAY = 1 - home yes_bid  (buying NO on the home market)
  The away team's own YES book can be tighter; ignoring it is conservative.
Fee.  Taker fee per contract = 0.07 * P * (1 - P) (Kalshi fee schedule, general
  trading fees; the PDF answered HTTP 429 here, the coefficient is from summaries
  of it). Kalshi rounds the ORDER's fee up to the cent; for a sized order (>=100
  contracts) that is negligible, so we use the unrounded per-contract fee. A
  single contract at 50c would pay a full 2c - shown once in the coverage block.
Units.  One unit = one flat bet. Buying at ask a with fee f, one unit buys
  1/(a+f) contracts:  win -> (1-a-f)/(a+f);  loss -> -1;  tie (Kalshi settles
  0.50 per side) -> 0.5/(a+f) - 1.  EV at probability p = p/(a+f) - 1.

(a) PRE-GAME, Kalshi vs Pinnacle.
  Decision time t = the latest Pinnacle h2h snapshot before kickoff in the
  2020-2025 Odds API archive (snapshots are every few hours, so t is usually
  2-6h before kickoff, not 1h). Pinnacle fair = proportional de-vig of that
  snapshot (fixed choice, not tuned). Kalshi price = the latest 1-minute candle
  ending at or before t; dropped if more than 5 minutes stale, or if t is more
  than 8h before kickoff (no candle). Both quotes are contemporaneous: no look-ahead.
  gap_side = Pinnacle fair(side) - Kalshi ask(side)   (fee NOT in the trigger)
  RULE: buy the side with gap >= X; X in {1..6} cents is a NEIGHBOURHOOD, not a
  fit. Graded at ask + fee. At most one side can qualify per game (gap_h + gap_a
  = bid - ask <= 0).  Sub-cell: t within 2h of kickoff.
  PLACEBO: buy the side with gap <= -X (Kalshi DEARER than Pinnacle): if Kalshi's
  deviations are noise around Pinnacle, this loses about fee + X.
  CONTROL: every game, home and away, at ask + fee (the cost floor).
  Seasons: Kalshi listed no NFL game markets before 2025 (probe), and the cache
  has no 2026 h2h (odds_2026 is spreads only), so this is 2025 REG only, with an
  early (weeks 1-9) / late (weeks 10-18) split. Nothing is fit on 2025.

(b) IN-PLAY, late leaders.
  Game state at candle end t = PRE-play state of the first play whose end time
  (pbp end_clock_time, else time_of_day) is AFTER t - i.e. the state after the
  last completed play. Scores from posteam_score/defteam_score (pre-play).
  Regulation only (qtr <= 4).
  RULE AS WORDED in the task (no exact rule retrieved from the cited research):
  the FIRST candle at which a team leads by >= L with <= S seconds left; buy the
  leader at that candle's ask + fee; one bet per game per rule.
    stated cells: L in {8, 9} x S in {600, 300}
    neighbourhood: L in {7,8,9,10,11,14,17} x S in {120,300,600,900}
  REFERENCE WP (fit on 2016-2024 pbp, REG+POST, every play): leader's final win
  rate (tie = 0.5) binned by lead x seconds-left x leader-has-ball. Graded seasons
  never enter the table. Second reference: nflverse vegas_wp (pre-game spread
  inside it) at the same play.
  CALIBRATION: mean(reference WP - cost) at the entry, game-clustered CI.
  SECOND RULE (pre-declared, not tuned): same entry window, but buy only at the
  first candle where reference WP - cost >= m, m in {0, 0.03}.
  PLACEBO: the same lead rule with 1200 < seconds left <= 1800 (third quarter);
  the late-game insurance story does not apply there.
  Execution delay robustness: price from the candle one minute later.
  Seasons graded: 2025 REG (hold-out 1, early/late split at week 9) and 2026
  weeks 1-4 plus the two week-5 games settled by 2026-10-11 (hold-out 2).

Executable prices only: Kalshi trades 1c-99c, and the candles' highest bid is
0.99 and lowest ask 0.01, so an ask of 1.00 (or a bid of 0.00) means that side
of the book was EMPTY. Such a candle has no buyable price for that side; a rule
fires at the first candle where its condition holds AND an offer exists.
(Added after the first run, which had treated 1.00 as a price - a bug, not a cut.)

Inference: 90% CI by game-cluster bootstrap (one bet per game per cell), plus a
Clopper-Pearson 90% interval on the win rate mapped to ROI (the bootstrap is
degenerate when a cell has no losses, which late-leader cells often do).
One-sided p under the null that every bet is priced at break-even: each bet wins
with probability = its cost (ask + fee); p = P(simulated units >= observed).
(The first run used the bootstrap share <= 0, which returns p = 0 for any cell
with no losing bet; replaced.) Benjamini-Hochberg over every graded season cell
(stated rules, neighbourhood, second rule, placebos), q = 0.10.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from scipy.stats import beta

from scripts.nfl_edge_lib import CACHE, devig2, games, odds_hist, pbp

KDIR = CACHE / "kalshi"
FEE = 0.07
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 400)


def fee(p):
    return FEE * p * (1 - p)


def profit(v, a):
    """v = settlement value of the side bought (1, 0, 0.5); a = ask paid."""
    c = a + fee(a)
    return v / c - 1


def boot(profit_arr, cluster, n=4000, alpha=0.10, seed=7):
    p = np.asarray(profit_arr, float)
    if len(p) == 0:
        return np.nan, np.nan, np.nan, np.nan
    uniq, inv = np.unique(np.asarray(cluster), return_inverse=True)
    s = np.bincount(inv, weights=p)
    c = np.bincount(inv)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(uniq), size=(n, len(uniq)))
    r = s[idx].sum(1) / c[idx].sum(1)
    lo, hi = np.quantile(r, [alpha / 2, 1 - alpha / 2])
    return p.mean(), lo, hi, float((r <= 0).mean())


def p_null(v, a, n=20000, seed=11):
    """P(units >= observed) if every bet wins with probability = its cost."""
    v = np.asarray(v, float)
    c = np.asarray(a, float) + fee(np.asarray(a, float))
    obs = (v / c - 1).sum()
    tie = v == 0.5
    rng = np.random.default_rng(seed)
    u = rng.random((n, len(c)))
    sim = np.where(u < c, 1 / c - 1, -1.0)
    sim[:, tie] = 0.5 / c[tie] - 1
    return float((sim.sum(1) >= obs - 1e-9).mean())


def cp_roi(v, a, alpha=0.10):
    """Clopper-Pearson interval on the number of wins (ties = half), mapped to ROI
    under a proportional model: true ROI r means each bet wins with probability
    cost_i * (1 + r), so expected wins = (1 + r) * sum(cost). Valid for any mix
    of costs (the first version used w*mean(1/c)-1, which is not)."""
    v = np.asarray(v, float)
    c = np.asarray(a, float) + fee(np.asarray(a, float))
    n, k = len(v), v.sum()
    lo = 0.0 if k <= 0 else beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k >= n else beta.ppf(1 - alpha / 2, k + 1, n - k)
    return n * lo / c.sum() - 1, n * hi / c.sum() - 1


def cell(df, label, col="profit", ask_col="ask", cluster="game_id"):
    if len(df) == 0:
        return {"cell": label, "bets": 0, "units": 0.0, "roi_pct": np.nan, "ci90_lo": np.nan,
                "ci90_hi": np.nan, "cp90_lo": np.nan, "cp90_hi": np.nan, "won_pct": np.nan,
                "losses": 0, "p_one_sided": np.nan}
    roi, lo, hi, _ = boot(df[col], df[cluster])
    cl, ch = cp_roi(df["v"], df[ask_col])
    return {"cell": label, "bets": len(df), "units": round(df[col].sum(), 2),
            "roi_pct": round(100 * roi, 2), "ci90_lo": round(100 * lo, 1),
            "ci90_hi": round(100 * hi, 1), "cp90_lo": round(100 * cl, 1),
            "cp90_hi": round(100 * ch, 1), "won_pct": round(100 * df["v"].mean(), 1),
            "losses": int((df["v"] == 0).sum()),
            "p_one_sided": round(p_null(df["v"], df[ask_col]), 4)}


def bh(pvals, q=0.10):
    p = np.asarray(pvals, float)
    ok = ~np.isnan(p)
    out = np.zeros(len(p), bool)
    pp = p[ok]
    if len(pp) == 0:
        return out
    order = np.argsort(pp)
    m = len(pp)
    thr = q * (np.arange(1, m + 1) / m)
    passed = pp[order] <= thr
    k = np.max(np.where(passed)[0]) + 1 if passed.any() else 0
    rej = np.zeros(m, bool)
    rej[order[:k]] = True
    out[np.where(ok)[0]] = rej
    return out


ALL_CELLS = []


def record(rows, family):
    for r in rows:
        r["family"] = family
        ALL_CELLS.append(r)


# ─── load ──────────────────────────────────────────────────────────────────

def load():
    g = games()
    g = g[g.season.isin([2025, 2026]) & (g.game_type == "REG")].copy()
    g["v_home"] = np.where(g.result > 0, 1.0, np.where(g.result < 0, 0.0, 0.5))
    cd = pd.read_parquet(KDIR / "candles_1m_nflgame.parquet")
    cd = cd.merge(g[["game_id", "season", "week", "kick", "home_team", "away_team",
                     "v_home", "result"]], on="game_id", how="inner")
    cd = cd.dropna(subset=["yes_bid_c", "yes_ask_c"]).sort_values(["game_id", "ts"])
    cd["ts"] = cd.ts.astype("datetime64[ns, UTC]")
    cd["mid"] = (cd.yes_bid_c + cd.yes_ask_c) / 2
    cd["spread_c"] = 100 * (cd.yes_ask_c - cd.yes_bid_c)
    mk = pd.read_parquet(KDIR / "markets_nfl.parquet")
    return g, cd, mk


def coverage(g, cd, mk):
    print("\n=== COVERAGE ===")
    gm = mk[(mk.series == "KXNFLGAME") & mk.game_id.notna()]
    for sea in (2025, 2026):
        x = gm[(gm.season == sea) & (gm.game_type == "REG")]
        print(f"{sea} REG: KXNFLGAME markets {len(x)}, games {x.game_id.nunique()}, "
              f"games w/ volume>0 {x[x.volume > 0].game_id.nunique()}, "
              f"median contracts traded per market {x.volume.median():,.0f}, "
              f"total {x.volume.sum():,.0f}")
    for s in ("KXNFLSPREAD", "KXNFLTOTAL"):
        x = mk[(mk.series == s) & mk.game_id.notna() & (mk.game_type == "REG")]
        for sea in (2025, 2026):
            y = x[x.season == sea]
            print(f"{s} {sea} REG: markets {len(y)} over {y.game_id.nunique()} games "
                  f"({len(y) / max(1, y.game_id.nunique()):.1f} strikes/game), median "
                  f"contracts per market {y.volume.median():,.0f}, per game "
                  f"{y.groupby('game_id').volume.sum().median():,.0f}")
    pg = cd.groupby("game_id").agg(season=("season", "first"), n=("ts", "size"))
    print("1-minute candles per game (window = 780 minutes):",
          pg.groupby("season").n.describe()[["count", "min", "50%", "max"]].round(0).to_dict("index"))
    print("games with candles by season:", pg.groupby("season").size().to_dict(),
          "| games in schedule:", g.groupby("season").game_id.nunique().to_dict())
    print("one-contract fee at 50c, rounded up to the cent: 2c "
          f"(unrounded 0.07*0.5*0.5 = {100 * fee(0.5):.2f}c)")


# ─── (a) pre-game ──────────────────────────────────────────────────────────

def pregame(g, cd):
    print("\n=== (a) PRE-GAME: Kalshi ask vs Pinnacle fair, contemporaneous ===")
    d = odds_hist(["h2h"])
    d = d[(d.season == 2025) & (d.bookmaker == "pinnacle")]
    d = d.drop(columns=["week"]).merge(g[["game_id", "kick", "week", "v_home"]], on="game_id")
    d = d[d.snapshot_at < d.kick].dropna(subset=["price_home", "price_away"])
    pin = d.sort_values("snapshot_at").groupby("game_id").tail(1).copy()
    pin["fair_h"], pin["fair_a"] = devig2(pin.price_home.values, pin.price_away.values)
    pin["lead_h"] = (pin.kick - pin.snapshot_at).dt.total_seconds() / 3600
    n0 = len(pin)
    pin = pin[pin.lead_h <= 8]
    print(f"2025 REG games with a pre-kick Pinnacle h2h snapshot: {n0}; "
          f"within 8h of kickoff (candle window): {len(pin)}")
    print("Pinnacle staleness (hours before kickoff of the decision time):",
          pin.lead_h.quantile([.1, .25, .5, .75, .9]).round(2).to_dict())
    k = cd[cd.season == 2025][["game_id", "ts", "yes_bid_c", "yes_ask_c", "mid", "spread_c",
                               "volume"]].sort_values("ts")
    pin = pin.sort_values("snapshot_at")
    pin["snapshot_at"] = pin.snapshot_at.astype("datetime64[ns, UTC]")
    k["ts"] = k.ts.astype("datetime64[ns, UTC]")
    x = pd.merge_asof(pin, k, left_on="snapshot_at", right_on="ts", by="game_id",
                      direction="backward", tolerance=pd.Timedelta("5min"))
    nd = x.yes_ask_c.isna().sum()
    x = x.dropna(subset=["yes_ask_c"]).copy()
    print(f"games with a Kalshi candle within 5 min before the Pinnacle snapshot: {len(x)} "
          f"(dropped {nd})")
    x["ask_h"] = x.yes_ask_c.where(x.yes_ask_c < 0.995)
    x["ask_a"] = (1 - x.yes_bid_c).where(x.yes_bid_c > 0.005)
    print("decision candles with an empty side (home ask 1.00 or bid 0.00):",
          int(x.ask_h.isna().sum() + x.ask_a.isna().sum()))
    x["gap_h"] = x.fair_h - x.ask_h
    x["gap_a"] = x.fair_a - x.ask_a
    x["mid_minus_fair_c"] = 100 * (x.mid - x.fair_h)
    print("Kalshi spread at decision (cents):", x.spread_c.describe()[["mean", "50%", "max"]].round(2).to_dict(),
          "| candle volume (contracts/min) median:", round(x.volume.median(), 0))
    print("Kalshi home mid - Pinnacle home fair (cents): ",
          x.mid_minus_fair_c.describe()[["mean", "std", "min", "50%", "max"]].round(2).to_dict())
    print("|mid - fair| >= 2c in", (x.mid_minus_fair_c.abs() >= 2).sum(), "games; >= 3c in",
          (x.mid_minus_fair_c.abs() >= 3).sum(), "; >= 5c in", (x.mid_minus_fair_c.abs() >= 5).sum())
    # forecast quality, same moment
    yv = x.v_home.values
    for nm, p in (("Kalshi mid", x.mid.values), ("Pinnacle fair", x.fair_h.values)):
        pc = np.clip(p, 1e-4, 1 - 1e-4)
        ll = -np.mean(yv * np.log(pc) + (1 - yv) * np.log(1 - pc))
        print(f"  {nm:14s} Brier {np.mean((p - yv) ** 2):.5f}  log-loss {ll:.5f}  (n={len(x)})")
    x["late"] = np.where(x.week <= 9, "early wk1-9", "late wk10-18")
    x["near2h"] = x.lead_h <= 2

    def bets(X, sign):
        rows = []
        for side in ("h", "a"):
            gap = x[f"gap_{side}"]
            sel = x[(gap >= X) if sign > 0 else (gap <= -X)].copy()
            sel["ask"] = sel[f"ask_{side}"]
            sel["v"] = sel.v_home if side == "h" else 1 - sel.v_home
            sel["side"] = side
            rows.append(sel.dropna(subset=["ask"]))
        b = pd.concat(rows)
        b["profit"] = profit(b.v.values, b.ask.values)
        return b

    out = []
    for X in (0.01, 0.02, 0.03, 0.04, 0.05, 0.06):
        b = bets(X, +1)
        out.append(cell(b, f"KALSHI CHEAP gap>={int(X * 100)}c all 2025"))
        for lab, sub in b.groupby("late"):
            out.append(cell(sub, f"KALSHI CHEAP gap>={int(X * 100)}c {lab}"))
        out.append(cell(b[b.near2h], f"KALSHI CHEAP gap>={int(X * 100)}c t<=2h pre-kick"))
    t = pd.DataFrame(out)
    t["low_vol"] = np.where(t.bets < 30, "LOW-N", "")
    print("\nRULE: buy the side whose Kalshi ask is below Pinnacle fair by >= X, at ask + fee")
    print(t.to_string(index=False))
    record([r for r in out if "all 2025" in r["cell"]], "pregame")
    pl = []
    for X in (0.01, 0.02, 0.03, 0.04, 0.05, 0.06):
        b = bets(X, -1)
        pl.append(cell(b, f"PLACEBO KALSHI DEAR gap<=-{int(X * 100)}c all 2025"))
    tp = pd.DataFrame(pl)
    print("\nPLACEBO: buy the side whose Kalshi ask is ABOVE Pinnacle fair by >= X")
    print(tp.to_string(index=False))
    record(pl, "pregame_placebo")
    ctl = pd.concat([x.assign(ask=x.ask_h, v=x.v_home),
                     x.assign(ask=x.ask_a, v=1 - x.v_home)]).dropna(subset=["ask"])
    ctl["profit"] = profit(ctl.v.values, ctl.ask.values)
    print("\nCONTROL (cost floor): every game, both sides, at ask + fee")
    print(pd.DataFrame([cell(ctl, "both sides every game")]).to_string(index=False))
    # expected ROI if Pinnacle fair were the truth (no outcomes involved)
    for X in (0.01, 0.03, 0.05):
        b = bets(X, +1)
        fair = np.where(b.side == "h", b.fair_h, b.fair_a)
        evp = fair / (b.ask + fee(b.ask)) - 1
        print(f"  gap>={int(X * 100)}c: bets {len(b)}, mean EV if Pinnacle fair is true "
              f"{100 * evp.mean():+.2f}%")
    return x


# ─── (b) in-play ───────────────────────────────────────────────────────────

LEAD_BINS = [0, 3, 6, 7, 8, 9, 10, 11, 13, 16, 20, 99]
SEC_BINS = [-1, 60, 120, 180, 300, 450, 600, 750, 900, 1200, 1500, 1800, 3600]


def bins(lead, secs, ball):
    lb = pd.cut(lead, LEAD_BINS, right=True, labels=False)
    sb = pd.cut(secs, SEC_BINS, right=True, labels=False)
    return lb.astype("float") * 100 + sb.astype("float") * 2 + ball.astype(float)


def wp_table():
    cols = ["game_id", "qtr", "game_seconds_remaining", "posteam", "posteam_score",
            "defteam_score", "home_team", "home_score", "away_score"]
    parts = []
    for s in range(2016, 2025):
        p = pd.read_parquet(CACHE / f"pbp_{s}.parquet", columns=cols)
        p = p[(p.qtr <= 4) & p.posteam.notna() & p.posteam_score.notna()]
        diff = p.posteam_score - p.defteam_score
        p = p[diff != 0]
        diff = diff[diff != 0]
        pos_home = p.posteam == p.home_team
        final_pos = np.where(pos_home, p.home_score - p.away_score, p.away_score - p.home_score)
        leader_final = np.where(diff > 0, final_pos, -final_pos)
        parts.append(pd.DataFrame({
            "game_id": p.game_id.values, "lead": diff.abs().values,
            "secs": p.game_seconds_remaining.values, "ball": (diff > 0).values.astype(int),
            "win": np.where(leader_final > 0, 1.0, np.where(leader_final < 0, 0.0, 0.5))}))
    t = pd.concat(parts, ignore_index=True)
    t["bin"] = bins(t.lead, t.secs, t.ball)
    tab = t.groupby("bin").agg(wp=("win", "mean"), plays=("win", "size"),
                               games=("game_id", "nunique")).reset_index()
    print(f"\nreference WP table: {len(t):,} plays from 2016-2024 regulation, "
          f"{tab.shape[0]} bins; bins with < 100 games: {(tab.games < 100).sum()}")
    return tab


def inplay_states(g, cd, seasons=(2025, 2026)):
    cols = ["game_id", "qtr", "game_seconds_remaining", "posteam", "posteam_score",
            "defteam_score", "home_team", "time_of_day", "end_clock_time", "vegas_home_wp",
            "touchdown", "play_type"]
    ps = pd.concat([pd.read_parquet(CACHE / f"pbp_{s}.parquet", columns=cols) for s in seasons],
                   ignore_index=True)
    ps = ps[ps.game_id.isin(g.game_id)]
    ps["t_end"] = pd.to_datetime(ps.end_clock_time, utc=True, errors="coerce", format="mixed")
    ps["t_snap"] = pd.to_datetime(ps.time_of_day, utc=True, errors="coerce", format="mixed")
    n_all = len(ps)
    # no end time (17% of 2025 rows, mostly PATs): snap + 10s, so a conversion's
    # result is never treated as known before the play could have ended
    ps["t_key"] = ps.t_end.fillna(ps.t_snap + pd.Timedelta(seconds=10))
    na = ps.t_key.isna().sum()
    sc_na = ps[ps.t_key.isna() & (ps.touchdown == 1)].shape[0]
    ps = ps[ps.posteam.notna() & ps.posteam_score.notna() & ps.t_key.notna()].copy()
    print(f"\npbp {seasons}: {n_all:,} rows; {na:,} with no end/snap time "
          f"({sc_na} of them touchdowns); usable state rows {len(ps):,}")
    ph = ps.posteam == ps.home_team
    ps["home_sc"] = np.where(ph, ps.posteam_score, ps.defteam_score)
    ps["away_sc"] = np.where(ph, ps.defteam_score, ps.posteam_score)
    ps["home_ball"] = ph.astype(int)
    ps = ps.sort_values(["game_id", "t_key"])
    return ps


def align_check(cd, ps):
    """Mean |change in Kalshi mid| by minute relative to touchdown end times."""
    td = ps[(ps.touchdown == 1) & (ps.qtr <= 4)][["game_id", "t_key"]].copy()
    k = cd[["game_id", "ts", "mid"]].copy()
    k["dmid"] = k.groupby("game_id").mid.diff().abs()
    td["m0"] = td.t_key.dt.ceil("min")
    rows = []
    for lag in range(-3, 4):
        z = td.assign(ts=td.m0 + pd.Timedelta(minutes=lag)).merge(k, on=["game_id", "ts"])
        rows.append({"lag_min": lag, "n": len(z), "mean_abs_dmid_c": round(100 * z.dmid.mean(), 2)})
    print("\nALIGNMENT CHECK: |minute change in Kalshi mid| around touchdown play-end times "
          "(lag 0 = the candle whose end first follows the play end)")
    print(pd.DataFrame(rows).to_string(index=False))


def inplay(g, cd, ps, tab):
    print("\n=== (b) IN-PLAY: late leaders ===")
    k = cd[(cd.ts > cd.kick)].copy()
    # state = pre-play state of first play ending AFTER t (strictly)
    k = k.sort_values("ts")
    s = ps[["game_id", "t_key", "qtr", "game_seconds_remaining", "home_sc", "away_sc",
            "home_ball", "vegas_home_wp"]].sort_values("t_key")
    s["t_key"] = s.t_key.astype("datetime64[ns, UTC]")
    k["ts"] = k.ts.astype("datetime64[ns, UTC]")
    x = pd.merge_asof(k, s, left_on="ts", right_on="t_key", by="game_id",
                      direction="forward", allow_exact_matches=False)
    x = x.dropna(subset=["home_sc", "game_seconds_remaining"])
    x = x[x.qtr <= 4].sort_values(["game_id", "ts"])
    # next-minute price for the execution-delay check
    x["ask1"] = x.groupby("game_id").yes_ask_c.shift(-1)
    x["bid1"] = x.groupby("game_id").yes_bid_c.shift(-1)
    diff = x.home_sc - x.away_sc
    x["lead"] = diff.abs()
    x["lead_home"] = diff > 0
    x["secs"] = x.game_seconds_remaining
    x["ball"] = np.where(x.lead_home, x.home_ball, 1 - x.home_ball)
    x["ask"] = np.where(x.lead_home, x.yes_ask_c, 1 - x.yes_bid_c)
    x["ask_d1"] = np.where(x.lead_home, x.ask1, 1 - x.bid1)
    n_empty = int((x.ask >= 0.995).sum())
    x.loc[x.ask >= 0.995, "ask"] = np.nan        # leader's side of the book empty
    x.loc[x.ask_d1 >= 0.995, "ask_d1"] = np.nan
    x["v"] = np.where(x.lead_home, x.v_home, 1 - x.v_home)
    x["vwp"] = np.where(x.lead_home, x.vegas_home_wp, 1 - x.vegas_home_wp)
    x = x[diff != 0].copy()
    x["bin"] = bins(x.lead, x.secs, x.ball)
    x = x.merge(tab[["bin", "wp", "games"]].rename(columns={"games": "ref_games"}), on="bin", how="left")
    x["cost"] = x.ask + fee(x.ask)
    x["gap_ref"] = x.wp - x.cost
    x["gap_vwp"] = x.vwp - x.cost
    x["profit"] = profit(x.v.values, x.ask.values)
    x["profit_d1"] = profit(x.v.values, x.ask_d1.values)
    x["half"] = np.where(x.season == 2026, "2026 wk1-5",
                         np.where(x.week <= 9, "2025 early wk1-9", "2025 late wk10-18"))
    x = x.sort_values(["game_id", "ts"])
    print(f"in-play candles with a regulation state: {len(x):,} over {x.game_id.nunique()} games "
          f"({x.groupby('season').game_id.nunique().to_dict()}); leader side empty (no offer) "
          f"in {n_empty:,} of them - not tradeable")
    x["tradeable"] = x.ask.notna()

    def first(L, lo, hi, extra=None):
        m = (x.lead >= L) & (x.secs <= hi) & (x.secs > lo) & x.tradeable
        if extra is not None:
            m &= extra
        return x[m].groupby("game_id", as_index=False).head(1)

    def block(L, S, lo=-1, extra=None, tag=""):
        e = first(L, lo, S, extra)
        rows = []
        for sea in (2025, 2026):
            rows.append(cell(e[e.season == sea], f"{tag}L>={L} secs<={S} {sea}"))
        rows.append(cell(e[(e.season == 2025) & e.ask_d1.notna()],
                         f"{tag}L>={L} secs<={S} 2025 delay+1m", col="profit_d1", ask_col="ask_d1"))
        for h in ("2025 early wk1-9", "2025 late wk10-18"):
            rows.append(cell(e[e.half == h], f"{tag}L>={L} secs<={S} {h}"))
        return e, rows

    print("\nRULE AS WORDED: first candle with lead >= L and <= S seconds left; buy the leader "
          "at ask + fee")
    stated = []
    for L in (8, 9):
        for S in (600, 300):
            e, rows = block(L, S)
            stated += rows
            for sea in (2025, 2026):
                es = e[e.season == sea]
                if len(es) == 0:
                    continue
                r_ref = boot(es.gap_ref, es.game_id)
                r_v = boot(es.gap_vwp.dropna(), es.dropna(subset=["gap_vwp"]).game_id)
                print(f"  L>={L} S<={S} {sea}: entries {len(es)}; cost median {es.cost.median():.3f}; "
                      f"ref WP - cost mean {100 * r_ref[0]:+.2f}c [90% {100 * r_ref[1]:+.2f}, "
                      f"{100 * r_ref[2]:+.2f}]; vegas_wp - cost {100 * r_v[0]:+.2f}c "
                      f"[{100 * r_v[1]:+.2f}, {100 * r_v[2]:+.2f}]; realised win "
                      f"{100 * es.v.mean():.1f}%; spread median {es.spread_c.median():.1f}c; "
                      f"candle volume median {es.volume.median():,.0f}; thin ref bins "
                      f"{(es.ref_games < 100).sum()}")
    t = pd.DataFrame(stated)
    t["low_vol"] = np.where(t.bets < 30, "LOW-N", "")
    print(t.to_string(index=False))
    record([r for r in stated if r["cell"].endswith(("2025", "2026"))], "inplay_stated")

    print("\nNEIGHBOURHOOD (2025 REG | 2026 wk1-5), first entry per game, leader at ask + fee")
    nb = []
    for L in (7, 8, 9, 10, 11, 14, 17):
        for S in (120, 300, 600, 900):
            e = first(L, -1, S)
            for sea in (2025, 2026):
                r = cell(e[e.season == sea], f"L>={L} secs<={S} {sea}")
                r["L"], r["S"], r["season"] = L, S, sea
                r["mean_cost"] = round(e[e.season == sea].cost.mean(), 3)
                r["ref_gap_c"] = round(100 * e[e.season == sea].gap_ref.mean(), 2)
                nb.append(r)
    tn = pd.DataFrame(nb)
    tn["low_vol"] = np.where(tn.bets < 30, "LOW-N", "")
    print(tn[["L", "S", "season", "bets", "units", "roi_pct", "ci90_lo", "ci90_hi", "cp90_lo",
              "cp90_hi", "won_pct", "losses", "mean_cost", "ref_gap_c", "p_one_sided",
              "low_vol"]].to_string(index=False))
    record([r for r in nb if not ((r["L"] in (8, 9)) and (r["S"] in (600, 300)))], "inplay_grid")

    print("\nSECOND RULE: in the window lead >= L, <= S seconds, buy at the first candle where "
          "reference WP - cost >= m")
    sr = []
    for L in (8, 9):
        for S in (600, 300):
            for m in (0.0, 0.03):
                e = first(L, -1, S, extra=(x.gap_ref >= m))
                for sea in (2025, 2026):
                    sr.append(cell(e[e.season == sea], f"L>={L} secs<={S} refgap>={m:.2f} {sea}"))
    ts_ = pd.DataFrame(sr)
    ts_["low_vol"] = np.where(ts_.bets < 30, "LOW-N", "")
    print(ts_.to_string(index=False))
    record(sr, "inplay_second_rule")

    print("\nPLACEBO: same lead rule in the third quarter (1200 < seconds left <= 1800)")
    pl = []
    for L in (8, 9):
        e = first(L, 1200, 1800)
        for sea in (2025, 2026):
            es = e[e.season == sea]
            r = cell(es, f"PLACEBO L>={L} 1200<secs<=1800 {sea}")
            r["ref_gap_c"] = round(100 * es.gap_ref.mean(), 2) if len(es) else np.nan
            r["vwp_gap_c"] = round(100 * es.gap_vwp.mean(), 2) if len(es) else np.nan
            pl.append(r)
    print(pd.DataFrame(pl).to_string(index=False))
    record(pl, "inplay_placebo")

    # calibration of the Kalshi leader mid across ALL late states (no rule)
    print("\nCALIBRATION, every in-play minute, regulation, by leader's price bucket "
          "(leader mid vs realised; game-clustered)")
    x["lmid"] = np.where(x.lead_home, x.mid, 1 - x.mid)
    x["late"] = np.where(x.secs <= 600, "<=10 min left", ">10 min left")
    x["pb"] = pd.cut(x.lmid, [0.5, 0.7, 0.8, 0.9, 0.95, 0.98, 1.0])
    cal = (x[x.tradeable].groupby(["season", "late", "pb"], observed=True)
             .apply(lambda z: pd.Series({"minutes": len(z), "games": z.game_id.nunique(),
                                         "mean_mid": round(z.lmid.mean(), 4),
                                         "realised": round(z.v.mean(), 4),
                                         "mean_cost_at_ask": round(z.cost.mean(), 4)}),
                    include_groups=False).reset_index())
    print(cal.to_string(index=False))
    return x


def main():
    g, cd, mk = load()
    coverage(g, cd, mk)
    pregame(g, cd)
    tab = wp_table()
    ps = inplay_states(g, cd)
    align_check(cd, ps)
    inplay(g, cd, ps, tab)
    a = pd.DataFrame(ALL_CELLS)
    a["bh_q10_reject"] = bh(a.p_one_sided.values)
    print(f"\n=== MULTIPLE COMPARISONS: {len(a)} graded cells, Benjamini-Hochberg q=0.10 ===")
    print(f"cells with one-sided p < 0.05: {(a.p_one_sided < 0.05).sum()}; "
          f"cells surviving BH: {a.bh_q10_reject.sum()}")
    if a.bh_q10_reject.any():
        print(a[a.bh_q10_reject][["family", "cell", "bets", "roi_pct", "ci90_lo", "ci90_hi",
                                  "p_one_sided"]].to_string(index=False))
    print("by family (cells, min p):", a.groupby("family").p_one_sided.agg(["size", "min"]).round(4)
          .to_dict("index"))


if __name__ == "__main__":
    main()

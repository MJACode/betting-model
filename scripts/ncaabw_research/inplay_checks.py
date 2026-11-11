"""Women's in-play second-half total and spread: the checks a first look needs
before it is anything more.

Reads the priced quotes scripts/ncaabw_research/inplay.py leaves in the cache
(inplay_priced_<season>.parquet: every in-play quote with the game-state
model's side, EV and grade; 2026 is walk-forward, 2025 a second look, 2027 the
season to date). The decision is that script's first-eligible rule: the first
snapshot of the second half holding an eligible quote decides the game, its
best-EV quote is bet at or above the cut.

  1. BLIND. At the same deciding snapshots, with no model: every over, every
     under, every favourite, every underdog; and the model's bets turned round.
  2. BANDS. Return by claimed-EV band, below the cut and above it. A real
     signal pays more the more it claims.
  3. PLACEBO. Each game takes ANOTHER game's decision (bet or not, and which
     side) and bets its own deciding quote on that side. This keeps the mix of
     sides and loses the link between the model and the game.
  4. STALE PRICES. By how old the quote was at its snapshot; by how long after
     the last score it was stamped; by book; against the two sharpest books on
     the board (BetOnline, LowVig) in the same snapshot; and the same side
     taken at the same book's NEXT snapshot, five minutes on.
  5. SPLITS. Third against fourth quarter, by month, by side.

With `halftime` it prints the rule restricted to the halftime break: nearly
every deciding quote sits there (the score is the halftime score and the
snapshot is before the third quarter's first play), so that is the rule a live
build would run.

    python -m scripts.ncaabw_research.inplay_checks [cut]              (default 0.05)
    python -m scripts.ncaabw_research.inplay_checks 0.05 halftime
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE  # noqa: E402
from scripts.ncaabw_research import inplay as ip  # noqa: E402

CUT = float(sys.argv[1]) if len(sys.argv) > 1 else 0.05
RULES = ("total_h2", "spread_h2")
SHARP = ("betonlineag", "lowvig")
FOLDS = ((2026, "2025-26 (walk-forward)"), (2025, "2024-25 (second look)"), (2027, "2026-27 to date"))


def line_of(b, label, extra=""):
    if not len(b):
        return f"  {label:44s}    0 bets"
    u, r = b["units"].values, b["risk"].values
    ud = pd.Series(u).groupby(b["game_date"].values).sum().values
    rd = pd.Series(r).groupby(b["game_date"].values).sum().values
    # its own seeded draw, so a line's interval does not depend on what was printed before it
    idx = np.random.default_rng(20261111).integers(0, len(ud), size=(3000, len(ud)))
    lo, hi = np.percentile(ud[idx].sum(axis=1) / rd[idx].sum(axis=1) * 100, [2.5, 97.5])
    return (f"  {label:44s} {len(b):5d} bets {int((u > 0).sum())}-{int((u < 0).sum())}  {u.sum():+8.2f}u "
            f"{u.sum() / r.sum() * 100:+6.2f}% [{lo:+5.1f}, {hi:+5.1f}]{extra}")


def regrade(q, side):
    """The quote graded on a given side ('over'/'under' or 'home'/'away')."""
    q = q.copy()
    is_sp = (q["market"] == "spreads").values
    first = np.isin(side, ("home", "over"))
    a = np.where(is_sp, np.where(first, q["home_price"], q["away_price"]),
                 np.where(first, q["over_price"], q["under_price"])).astype(float)
    d = np.where(a > 0, 1 + a / 100, 1 + 100 / np.abs(a))
    final = np.where(is_sp, q["final_m"].values + q["spread_home"].values, q["final_t"].values - q["total_line"].values)
    res = np.where(first, final, -final)
    risk = np.minimum(1 / (d - 1), 3.0)
    q["side"] = side; q["price"] = a; q["risk"] = risk
    q["units"] = np.where(res > 0, risk * (d - 1), np.where(res < 0, -risk, 0.0))
    return q


def deciding(Q, rule):
    """The deciding quote of each game for a rule: the best-EV eligible quote
    of the first second-half snapshot holding one."""
    E = Q[(Q["rule"] == rule) & Q["eligible"]].sort_values(
        ["game_id", "snapshot_ts", "ev"], ascending=[True, True, False])
    first_ts = E.groupby("game_id")["snapshot_ts"].transform("min")
    return E[E["snapshot_ts"] == first_ts].groupby("game_id").head(1).copy(), E[E["snapshot_ts"] == first_ts]


def blind(first_snap, rule):
    """At each game's deciding snapshot, one bet on a fixed side: the best
    price on that side among the eligible quotes."""
    out = {}
    sides = ("over", "under") if rule.startswith("total") else ("home", "away")
    for side in sides:
        g = regrade(first_snap, np.full(len(first_snap), side))
        g = g.sort_values(["game_id", "price"], ascending=[True, False]).groupby("game_id").head(1)
        out[side] = g
    if rule.startswith("spread"):
        fav_home = first_snap["prior_m"] > 0          # the pre-game favourite
        for name, pick in (("pre-game favourite", np.where(fav_home, "home", "away")),
                           ("pre-game underdog", np.where(fav_home, "away", "home")),
                           ("team ahead now", np.where(first_snap["cur_m"] > 0, "home", "away")),
                           ("team behind now", np.where(first_snap["cur_m"] > 0, "away", "home"))):
            g = regrade(first_snap, pick)
            out[name] = g.sort_values(["game_id", "price"], ascending=[True, False]).groupby("game_id").head(1)
    return out


def placebo(dec, n=200):
    """Each game takes another game's decision (EV and side) and bets its own
    deciding quote on that side when that other game's EV cleared the cut."""
    tot_u, tot_r, n_bets = [], [], []
    ev = dec["ev"].values; side = dec["side"].values
    rng = np.random.default_rng(20261111)
    for _ in range(n):
        perm = rng.permutation(len(dec))
        take = ev[perm] >= CUT
        g = regrade(dec[take], side[perm][take])
        tot_u.append(g["units"].sum()); tot_r.append(g["risk"].sum()); n_bets.append(int(take.sum()))
    roi = np.array(tot_u) / np.array(tot_r) * 100
    return float(np.mean(n_bets)), float(np.mean(tot_u)), float(roi.mean()), np.percentile(roi, [2.5, 97.5])


def add_since_score(Q, states):
    """Seconds from the last scoring play to the quote's own stamp."""
    lu = Q["last_update"].dt.as_unit("ns").astype("int64").values
    out = np.full(len(Q), np.nan)
    for gid, idx in Q.groupby("game_id").indices.items():
        st = states.get(gid)
        if st is None:
            continue
        sw = st["wall"][st["scored"]]
        if not len(sw):
            continue
        i = np.searchsorted(sw, lu[idx], side="right") - 1
        ok = i >= 0
        out[idx] = np.where(ok, (lu[idx] - sw[np.clip(i, 0, None)]) / 1e9, np.nan)
    Q = Q.copy(); Q["since_score_s"] = out
    return Q


def next_snapshot(bets, Q):
    """The same side at the same book's next snapshot (the next one holding
    that book's quote for the game and market, within 11 minutes)."""
    K = Q[["game_id", "market", "bookmaker", "snapshot_ts", "home_price", "away_price", "over_price",
           "under_price", "spread_home", "total_line", "final_m", "final_t", "game_date", "price",
           "gs"]].sort_values("snapshot_ts")
    rows = []
    for b in bets.itertuples(index=False):
        k = K[(K["game_id"] == b.game_id) & (K["market"] == b.market) & (K["bookmaker"] == b.bookmaker)
              & (K["snapshot_ts"] > b.snapshot_ts)
              & (K["snapshot_ts"] <= b.snapshot_ts + pd.Timedelta(minutes=11))]
        if len(k):
            rows.append((k.iloc[[0]], b.side))
    if not rows:
        return pd.DataFrame()
    nxt = pd.concat([r for r, _ in rows], ignore_index=True)
    return regrade(nxt, np.array([s for _, s in rows]))


def sharp_gap(bets, Q):
    """How the bet's line stands against the sharpest books' in the same
    snapshot: points better for the bet side (positive = our number is
    better than theirs)."""
    S = Q[Q["bookmaker"].isin(SHARP)].groupby(["game_id", "market", "snapshot_ts"])["line"].median().rename("sharp_line")
    b = bets.merge(S, on=["game_id", "market", "snapshot_ts"], how="left")
    is_sp = b["market"] == "spreads"
    # totals: an under wants a higher line, an over a lower one; spreads: the
    # home side wants a higher home number, the away side a lower one
    want_high = np.where(is_sp, b["side"] == "home", b["side"] == "under")
    b["gap"] = np.where(want_high, b["line"] - b["sharp_line"], b["sharp_line"] - b["line"])
    return b


def add_break(Q, states):
    """Mark the quotes that sit in the halftime break: the score is the
    halftime score (1,200 game seconds) and the snapshot is before the third
    quarter's first play. Also minutes from the end of the half to the stamp."""
    half_end = {gid: (st["wall"][np.searchsorted(st["gs"], 1200.0, side="left")]
                      if (st["gs"] >= 1200.0).any() else np.nan) for gid, st in states.items()}
    third = {gid: (st["wall"][np.searchsorted(st["gs"], 1200.0, side="right")]
                   if (st["gs"] > 1200.0).any() else np.nan) for gid, st in states.items()}
    Q = Q.copy()
    lu = Q["last_update"].dt.as_unit("ns").astype("int64")
    sn = pd.to_datetime(Q["snapshot_ts"], utc=True).dt.as_unit("ns").astype("int64")
    Q["in_break"] = (Q["gs"] == 1200.0) & (sn < Q["game_id"].map(third).fillna(np.inf))
    Q["min_into_break"] = (lu - Q["game_id"].map(half_end)) / 60e9
    return Q


def halftime(Qs, states):
    """The rule restricted to the break: where its deciding quotes sit, the
    grid by season and pooled, prices, volume, calibration, books, sides."""
    print("\n\n################ THE HALFTIME BREAK ONLY ################")
    decs = {}
    for season, label in FOLDS:
        if season not in Qs:
            continue
        Q = add_break(Qs[season], states)
        for rule in RULES:
            dec, _ = deciding(Q, rule)
            decs[(season, rule)] = dec[dec["in_break"]]
            m = dec.loc[dec["in_break"], "min_into_break"]
            n_snap = Q[(Q["rule"] == rule) & Q["eligible"] & Q["in_break"]].groupby("game_id")["snapshot_ts"].nunique()
            print(f"\n{rule}, {label}: {len(dec)} games decided, {int(dec['in_break'].sum())} in the break; "
                  f"quote stamped a median {m.median():.1f} min after the half ended (10% {m.quantile(0.1):.1f}, "
                  f"90% {m.quantile(0.9):.1f}); break snapshots a game: median {n_snap.median():.0f}")
            hb = decs[(season, rule)]
            for cut in (0.02, 0.03, 0.05, 0.08, 0.12):
                print(line_of(hb[hb["ev"] >= cut], f"break only, EV >= {cut:.2f}"))
            print(line_of(dec[~dec["in_break"] & (dec["ev"] >= CUT)], f"outside the break, EV >= {CUT}"))
    for rule in RULES:
        if (2025, rule) not in decs or (2026, rule) not in decs:
            continue
        both = pd.concat([decs[(2025, rule)], decs[(2026, rule)]])
        print(f"\n{rule}: 2025-26 (walk-forward) and 2024-25 (second look) together, break only, "
              f"{len(both)} games decided")
        for cut in (0.02, 0.03, 0.05, 0.08, 0.12):
            print(line_of(both[both["ev"] >= cut], f"EV >= {cut:.2f}"))
        b = both[both["ev"] >= CUT]
        print(f"  the bets' prices: min {b['price'].min():.0f}, 5% {b['price'].quantile(0.05):.0f}, median "
              f"{b['price'].median():.0f}, 95% {b['price'].quantile(0.95):.0f}, max {b['price'].max():.0f}; shorter "
              f"than -150: {int((b['price'] < -150).sum())}; plus money: {int((b['price'] > 100).sum())}")
        days = b.groupby("game_date").size()
        print(f"  game days with a bet {len(days)}; bets a day: median {days.median():.0f}, 90% "
              f"{days.quantile(0.9):.0f}, max {days.max()}")
        print("  claimed against won, every decided game:")
        for lo, hi in ((0.0, 0.52), (0.52, 0.55), (0.55, 0.58), (0.58, 0.62), (0.62, 0.70), (0.70, 1.01)):
            z = both[(both["prob"] >= lo) & (both["prob"] < hi) & (both["units"] != 0)]
            if len(z):
                print(f"    claimed {lo:.2f}-{hi:.2f}: n {len(z):4d}  claimed {z['prob'].mean():.3f}  "
                      f"won {(z['units'] > 0).mean():.3f}")
        for side, z in b.groupby("side"):
            print(line_of(z, f"side: {side}"))
        for book, z in b.groupby("bookmaker"):
            print(line_of(z, f"at {book}"))


if __name__ == "__main__":
    g = ip.load_games()
    pri = ip.priors()
    # the reading of the play list `inplay` was run with (NCAABW_INPLAY_STATE)
    Qs = {s: pd.read_parquet(CACHE / f"{ip.PRICED}_{s}.parquet") for s, _ in FOLDS
          if (CACHE / f"{ip.PRICED}_{s}.parquet").exists()}
    wanted = set().union(*[set(q["game_id"]) for q in Qs.values()])
    states = ip.load_states(g, wanted)
    print(f"cut: EV at or above {CUT}; games with a play-by-play {len(states):,}")
    if len(sys.argv) > 2 and sys.argv[2] == "halftime":
        halftime(Qs, states)
        sys.exit(0)
    for season, label in FOLDS:
        if season not in Qs:
            continue
        Q = add_since_score(Qs[season], states)
        Q["age_s"] = (pd.to_datetime(Q["snapshot_ts"], utc=True) - Q["last_update"]).dt.total_seconds()
        Q["month"] = pd.to_datetime(Q["game_date"]).dt.month
        for rule in RULES:
            dec, first_snap = deciding(Q, rule)
            bets = dec[dec["ev"] >= CUT]
            print(f"\n================ {rule}, {label}: {len(dec)} games decided ================")
            print(line_of(bets, f"the rule (EV >= {CUT})",
                          f"  prices {bets['price'].min():.0f}..{bets['price'].max():.0f}  claimed EV {bets['ev'].mean():.3f}"
                          if len(bets) else ""))
            if len(bets) < 10:
                continue
            print(" 1. blind, the same deciding snapshots, no model:")
            for name, z in blind(first_snap, rule).items():
                print(line_of(z, f"every {name}"))
            flip = {"over": "under", "under": "over", "home": "away", "away": "home"}
            print(line_of(regrade(bets, bets["side"].map(flip).values), "the rule's bets, turned round"))
            mix = bets["side"].value_counts().to_dict()
            print(f"    the rule's side mix: {mix}")
            print(" 2. by claimed EV (the deciding quote of every game):")
            for lo, hi in ((-1, 0.0), (0.0, 0.02), (0.02, 0.05), (0.05, 0.08), (0.08, 0.12), (0.12, 0.20), (0.20, 9)):
                z = dec[(dec["ev"] >= lo) & (dec["ev"] < hi)]
                extra = ""
                if len(z):
                    won = (z["units"] > 0).sum() / max(((z["units"] != 0).sum()), 1)
                    extra = f"  claimed win {z['prob'].mean():.3f} won {won:.3f}"
                print(line_of(z, f"EV {lo:+.2f} to {hi:+.2f}", extra))
            nb_, u_, roi_, ci = placebo(dec)
            print(f" 3. placebo (another game's decision, 200 shuffles): {nb_:.0f} bets on average, "
                  f"{u_:+.2f}u, {roi_:+.2f}% [{ci[0]:+.1f}, {ci[1]:+.1f}]")
            print(" 4. stale prices:")
            for lo, hi in ((0, 30), (30, 60), (60, 120), (120, 300), (300, 10 ** 6)):
                print(line_of(bets[(bets["age_s"] >= lo) & (bets["age_s"] < hi)], f"quote {lo}-{hi}s old at its snapshot"))
            for lo, hi in ((0, 20), (20, 45), (45, 90), (90, 10 ** 6)):
                print(line_of(bets[(bets["since_score_s"] >= lo) & (bets["since_score_s"] < hi)],
                              f"stamped {lo}-{hi}s after the last score"))
            for book, z in bets.groupby("bookmaker"):
                print(line_of(z, f"at {book}"))
            sg = sharp_gap(bets, Q)
            print(line_of(sg[sg["sharp_line"].isna()], "no sharp book in the snapshot"))
            print(line_of(sg[sg["gap"] >= 1.5], "our line 1.5+ better than the sharp books'"))
            print(line_of(sg[(sg["gap"] > 0) & (sg["gap"] < 1.5)], "our line better by under 1.5"))
            print(line_of(sg[sg["gap"] <= 0], "our line no better than the sharp books'"))
            nx = next_snapshot(bets, Q)
            print(line_of(nx, "same side, same book, NEXT snapshot",
                          f"  ({len(nx)} of {len(bets)} bets had one)" if len(nx) else ""))
            print(" 5. splits:")
            q4 = bets["gs"] >= 1800
            print(line_of(bets[~q4], "decided in the third quarter"))
            print(line_of(bets[q4], "decided in the fourth quarter"))
            for name, m in (("November-December", bets["month"].isin([11, 12])), ("January on", ~bets["month"].isin([11, 12]))):
                print(line_of(bets[m], name))
            for side, z in bets.groupby("side"):
                print(line_of(z, f"side: {side}"))

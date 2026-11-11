"""Tidy the NCAAF extract: scored games with closing lines, and pre-game quotes by pull.

Outputs (scratchpad/data):
  g.parquet        one row per scored game: margin, total, kickoff, ET date, closing spread/total
  q_hist.parquet   2023-2025 historical pulls: one row per (game, pull, book) with spread/total/ML
  q_2026.parquet   2026 live pre-game rows, same columns (pull_ts = the row's own stamp)
"""
from pathlib import Path

import numpy as np
import pandas as pd

from paths import CACHE as D  # noqa: E402
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 200)

NUM = ["home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"]


def main():
    g = pd.read_parquet(D / "ncaaf_games.parquet")
    for c in ("home_score", "away_score"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g["kick"] = pd.to_datetime(g.commence_time, utc=True, errors="coerce", format="mixed")
    g["margin"] = g.home_score - g.away_score
    g["total"] = g.home_score + g.away_score
    print("games", len(g), "scored", g.margin.notna().sum(), "with kickoff", g.kick.notna().sum())

    o = pd.read_parquet(D / "ncaaf_odds.parquet",
                        columns=["odds_id", "game_id", "market", "bookmaker", "snapshot_type", "snapshot_at",
                                 "created_at", "source"] + NUM)
    for c in NUM:
        o[c] = pd.to_numeric(o[c], errors="coerce")
    o["ts"] = pd.to_datetime(o.snapshot_at, utc=True, errors="coerce", format="mixed")
    o["src"] = o.source.fillna("").str.split("|").str[0]
    print(o[o.bookmaker.str.startswith("cfbd")].groupby(["bookmaker", "snapshot_type", "market"]).size().to_string())

    # ── closing lines for the distribution tables ────────────────────────────
    # CFBD's stored close per provider (2014-2025), in the repo's own priority.
    pri = ["cfbd_draftkings", "cfbd_bovada", "cfbd_consensus", "cfbd_teamrankings"]
    cf = o[o.bookmaker.isin(pri)].copy()
    print("cfbd snapshot types:", cf.snapshot_type.value_counts().to_dict())
    cf["rank"] = cf.bookmaker.map({b: i for i, b in enumerate(pri)})
    close_types = [t for t in cf.snapshot_type.unique() if "clos" in str(t).lower()]
    print("close types", close_types)
    cl = cf[cf.snapshot_type.isin(close_types)] if close_types else cf
    sp = (cl[(cl.market == "spreads") & cl.spread_home.notna()].sort_values(["game_id", "rank"])
          .drop_duplicates("game_id")[["game_id", "spread_home", "bookmaker"]]
          .rename(columns={"spread_home": "close_spread", "bookmaker": "close_spread_src"}))
    tt = (cl[(cl.market == "totals") & cl.total_line.notna()].sort_values(["game_id", "rank"])
          .drop_duplicates("game_id")[["game_id", "total_line", "bookmaker"]]
          .rename(columns={"total_line": "close_total", "bookmaker": "close_total_src"}))
    g = g.merge(sp, on="game_id", how="left").merge(tt, on="game_id", how="left")

    # ── an unscored odds row inherits its scored twin (same two teams, date within a day) ──
    g["d"] = pd.to_datetime(g.game_date)
    has_odds = set(o.game_id.unique())
    scored = g[g.margin.notna()]
    idx = {}
    for r in scored.itertuples(index=False):
        idx.setdefault((r.season, frozenset((r.home_team, r.away_team))), []).append(r)
    g["twin_of"] = None
    n_same = n_flip = n_none = n_amb = 0
    upd = {}
    for r in g[g.margin.isna() & g.game_id.isin(has_odds)].itertuples():
        cands = [c for c in idx.get((r.season, frozenset((r.home_team, r.away_team))), [])
                 if abs((c.d - r.d).days) <= 1]
        if len(cands) != 1:
            n_none += len(cands) == 0
            n_amb += len(cands) > 1
            continue
        c = cands[0]
        flip = c.home_team != r.home_team
        n_flip += flip
        n_same += not flip
        sgn = -1 if flip else 1
        upd[r.Index] = dict(
            home_score=c.away_score if flip else c.home_score, away_score=c.home_score if flip else c.away_score,
            margin=sgn * c.margin, total=c.total, twin_of=c.game_id, week=c.week, neutral_site=c.neutral_site,
            close_spread=(sgn * c.close_spread if pd.notna(c.close_spread) else np.nan),
            close_total=c.close_total, close_spread_src=c.close_spread_src, close_total_src=c.close_total_src)
    for i, u in upd.items():
        for k, v in u.items():
            g.at[i, k] = v
    print(f"unscored odds games matched to a scored twin: same orientation {n_same}, flipped {n_flip}, "
          f"no twin {n_none}, ambiguous {n_amb}")
    # a scored game that is somebody's twin must not ALSO be graded under its own id
    g["has_twin_child"] = g.game_id.isin({u["twin_of"] for u in upd.values()})

    # ── historical pulls (2023-2025) ─────────────────────────────────────────
    h = o[(o.src == "odds_api_historical") & (o.snapshot_type == "open")].copy()
    pull = h.groupby("created_at").ts.agg(["min", "max", "median", "size"])
    pull["span_min"] = (pull["max"] - pull["min"]).dt.total_seconds() / 60
    print("pulls", len(pull), "span minutes quantiles", pull.span_min.quantile([.5, .9, .99, 1]).round(1).to_dict())
    h["pull_ts"] = h.created_at.map(pull["max"])
    print("pull hour (UTC) counts:", h.drop_duplicates("created_at").pull_ts.dt.hour.value_counts().sort_index().to_dict())

    def wide(x, key):
        s = x[x.market == "spreads"][key + ["spread_home", "home_price", "away_price", "ts"]].rename(
            columns={"home_price": "sp_home", "away_price": "sp_away", "ts": "sp_ts"})
        t = x[x.market == "totals"][key + ["total_line", "over_price", "under_price", "ts"]].rename(columns={"ts": "tot_ts"})
        m = x[x.market == "h2h"][key + ["home_price", "away_price", "ts"]].rename(
            columns={"home_price": "ml_home", "away_price": "ml_away", "ts": "ml_ts"})
        s = s.drop_duplicates(key, keep="last")
        t = t.drop_duplicates(key, keep="last")
        m = m.drop_duplicates(key, keep="last")
        return s.merge(t, on=key, how="outer").merge(m, on=key, how="outer")

    h = h.sort_values("ts")
    qh = wide(h, ["game_id", "pull_ts", "bookmaker"])
    qh.to_parquet(D / "q_hist.parquet")
    print("q_hist", len(qh), "games", qh.game_id.nunique())

    # ── 2026 live pre-game rows ──────────────────────────────────────────────
    ids26 = set(g[g.season == 2026].game_id)
    l = o[o.game_id.isin(ids26) & (o.snapshot_type == "open") & (o.src == "")
          & o.market.isin(["spreads", "totals", "h2h"])].copy()
    l = l.merge(g[["game_id", "kick"]], on="game_id", how="left")
    l = l[l.ts < l.kick]
    l["pull_ts"] = l.ts
    l = l.sort_values("ts")
    keep = ["game_id", "pull_ts", "bookmaker", "market", "ts"] + NUM
    l[keep].to_parquet(D / "q_2026_long.parquet")
    print("2026 long rows", len(l), "games", l.game_id.nunique())

    # closing consensus from the last pre-kick historical pull (2023-25) for games CFBD has no close for
    hk = qh.merge(g[["game_id", "kick"]], on="game_id", how="left")
    hk = hk[hk.pull_ts < hk.kick]
    last = hk.groupby("game_id").pull_ts.transform("max")
    lastq = hk[hk.pull_ts == last]
    cons = lastq.groupby("game_id").agg(last_spread=("spread_home", "median"), last_total=("total_line", "median"),
                                        last_pull=("pull_ts", "first"), last_books=("bookmaker", "nunique"))
    pin = lastq[lastq.bookmaker == "pinnacle"].set_index("game_id")[["spread_home", "sp_home", "sp_away", "total_line",
                                                                     "over_price", "under_price", "ml_home", "ml_away"]].add_prefix("pin_close_")
    g = g.merge(cons, on="game_id", how="left").merge(pin, on="game_id", how="left")
    g["close_spread_any"] = g.close_spread.fillna(g.last_spread)
    g["close_total_any"] = g.close_total.fillna(g.last_total)
    g["et_date"] = g.kick.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    g.to_parquet(D / "g.parquet")

    sc = g[g.margin.notna()]
    print(sc.groupby("season").agg(games=("game_id", "size"), close_spread=("close_spread", "count"),
                                   close_any=("close_spread_any", "count"), close_total_any=("close_total_any", "count"),
                                   hist=("last_spread", "count")).to_string())
    # CFBD close vs last-pull consensus agreement where both exist
    b = sc[sc.close_spread.notna() & sc.last_spread.notna()]
    d = (b.close_spread - b.last_spread)
    print("cfbd close vs last-pull median: n", len(b), "mean abs diff", d.abs().mean().round(3), "share equal", (d == 0).mean().round(3),
          "share |d|>=3", (d.abs() >= 3).mean().round(4))
    # twin check: scored games sharing teams within a day
    sc2 = sc.assign(d=pd.to_datetime(sc.game_date))
    k = sc2.groupby(["season", "home_team", "away_team", "margin", "total"]).game_id.count()
    print("scored rows that repeat (season, home, away, margin, total):", int((k > 1).sum()), "of", len(k))
    # sanity: home cover / over rates vs close
    v = sc[sc.close_spread_any.notna()]
    cov = (v.margin + v.close_spread_any)
    print("home cover rate vs close (pushes out):", round((cov > 0).sum() / (cov != 0).sum(), 4), "n", int((cov != 0).sum()),
          "mean(margin+close)", round(cov.mean(), 3))
    v = sc[sc.close_total_any.notna()]
    ov = v.total - v.close_total_any
    print("over rate vs close:", round((ov > 0).sum() / (ov != 0).sum(), 4), "n", int((ov != 0).sum()), "mean(total-close)", round(ov.mean(), 3))


if __name__ == "__main__":
    main()

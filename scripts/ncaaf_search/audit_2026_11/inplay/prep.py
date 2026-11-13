"""NCAAF in-play port of the NCAAB game-state model: DATA PREP ONLY.

No model, no bets, no grades in this file. It turns the five local extracts
into the tables grid.py reads, and prints every count and every drop.

Outputs (this directory):
  games_2025.parquet     one row per CFBD play-by-play game (2025): final, block, prior
  train_states.parquet   2025 states, one per 30 s of regulation game clock
  tl_2025.parquet        2025 wallclock timeline per ODDS game_id (trusted plays)
  ev_2025.parquet        2025 score-change events per ODDS game_id (t_lo, t_hi)
  st_2026.parquet        2026 logged states per game_id (the live loop's log)
  ginfo.parquet          per odds game_id: season, slate date, final, prior, Pinnacle prior
  quotes.parquet         DraftKings in-play h2h / totals quotes, both seasons
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402

import bisect
import sys
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(str(CACHE))
OUT = WORK / "inplay"
REG_S, GRID_STEP = 3600.0, 30
TRAIN_SECS = (60, 3540)            # game seconds gone, regulation


def ts(s):
    return pd.to_datetime(s, utc=True, errors="coerce", format="ISO8601")


def lnds_mask(a: np.ndarray) -> np.ndarray:
    """A longest non-decreasing subsequence of `a` (NaN never kept)."""
    n = len(a)
    tails, tails_idx, prev = [], [], np.full(n, -1)
    for i, v in enumerate(a):
        if np.isnan(v):
            continue
        k = bisect.bisect_right(tails, v)
        if k == len(tails):
            tails.append(v); tails_idx.append(i)
        else:
            tails[k] = v; tails_idx[k] = i
        prev[i] = tails_idx[k - 1] if k > 0 else -1
    m = np.zeros(n, bool)
    i = tails_idx[-1] if tails_idx else -1
    while i >= 0:
        m[i] = True
        i = prev[i]
    return m


def by_game_lnds(df: pd.DataFrame, key: str, col: str) -> np.ndarray:
    v = df[col].to_numpy(float)
    m = np.zeros(len(df), bool)
    for _, idx in df.groupby(key, sort=False).indices.items():
        m[idx] = lnds_mask(v[idx])
    return m


# ── games ────────────────────────────────────────────────────────────────────
g = pd.read_parquet(D / "ncaaf_games.parquet")
g["hs"] = pd.to_numeric(g["home_score"], errors="coerce")
g["as_"] = pd.to_numeric(g["away_score"], errors="coerce")
g["kick"] = ts(g["commence_time"])
g["gdate"] = pd.to_datetime(g["game_date"])
g = g[g["season"].isin([2025, 2026])].reset_index(drop=True)
g["pair"] = [" | ".join(sorted([h, a])) for h, a in zip(g["home_team"], g["away_team"])]
print(f"games rows 2025: {(g.season == 2025).sum()}, 2026: {(g.season == 2026).sum()}")


def twins(row) -> pd.DataFrame:
    """Rows that are the same game: same season, same two teams, within a day."""
    c = g[(g["season"] == row["season"]) & (g["pair"] == row["pair"])]
    return c[(c["gdate"] - row["gdate"]).abs() <= pd.Timedelta(days=1)]


by_pair = {k: v for k, v in g.groupby(["season", "pair"])}


def final_for(row):
    """(home, away) final in THIS row's orientation: its own, else a twin's
    (flipped when the twin lists the teams the other way round). Conflicting
    twins give none."""
    if pd.notna(row["hs"]) and pd.notna(row["as_"]):
        return row["hs"], row["as_"], "own"
    c = by_pair[(row["season"], row["pair"])]
    c = c[((c["gdate"] - row["gdate"]).abs() <= pd.Timedelta(days=1)) & c["hs"].notna()]
    outs = set()
    for _, t in c.iterrows():
        outs.add((t["hs"], t["as_"]) if t["home_team"] == row["home_team"] else (t["as_"], t["hs"]))
    if len(outs) == 1:
        h, a = outs.pop()
        return h, a, "twin"
    return np.nan, np.nan, "none"


# ── odds ─────────────────────────────────────────────────────────────────────
ocols = ["odds_id", "game_id", "market", "bookmaker", "snapshot_type", "snapshot_at", "created_at",
         "source", "home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"]
o = pd.read_parquet(D / "ncaaf_odds.parquet", columns=ocols)
o = o[o["game_id"].isin(set(g["game_id"]))]
for c in ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"):
    o[c] = pd.to_numeric(o[c], errors="coerce").astype(float)

# pre-game closes: each book's LAST row at or before its game row's kickoff
pre = o[(o["snapshot_type"] != "in_play") & o["market"].isin(["spreads", "totals"])].copy()
pre["snap"] = ts(pre["snapshot_at"])
pre = pre.merge(g[["game_id", "kick"]], on="game_id")
n0 = len(pre)
pre = pre[pre["snap"].notna() & (pre["snap"] <= pre["kick"])]
print(f"pre-game spread/total rows (2025-26 games): {n0:,}; at or before kickoff: {len(pre):,}")
pre["num"] = np.where(pre["market"] == "spreads", pre["spread_home"], pre["total_line"])
pre = pre.dropna(subset=["num"]).sort_values("snap", kind="stable")
close = pre.drop_duplicates(["game_id", "market", "bookmaker"], keep="last")
close = close.pivot_table(index="game_id", columns=["bookmaker", "market"], values="num", aggfunc="last")

PRIOR_ORDER = ("draftkings", "cfbd_draftkings", "cfbd_bovada")


def prior_own(gid: str):
    """(home spread, total, source) from the game row's own closes: DraftKings'
    last pre-kick row, else CFBD's DraftKings close, else CFBD's Bovada close.
    Both numbers come from the same source."""
    if gid not in close.index:
        return np.nan, np.nan, "none"
    r = close.loc[gid]
    for b in PRIOR_ORDER:
        sp, to = r.get((b, "spreads"), np.nan), r.get((b, "totals"), np.nan)
        if pd.notna(sp) and pd.notna(to):
            return float(sp), float(to), b
    return np.nan, np.nan, "none"


def prior_for(row):
    """The row's own prior, else a twin's (home number flipped when the twin
    lists the teams the other way round), walking PRIOR_ORDER across all of
    them so a DraftKings pre-kick row on any twin beats a CFBD close."""
    c = by_pair[(row["season"], row["pair"])]
    c = c[(c["gdate"] - row["gdate"]).abs() <= pd.Timedelta(days=1)]
    best = (np.nan, np.nan, "none", 99)
    for _, t in c.iterrows():
        sp, to, src = prior_own(t["game_id"])
        if src == "none":
            continue
        rank = PRIOR_ORDER.index(src) * 2 + (0 if t["game_id"] == row["game_id"] else 1)
        if rank < best[3]:
            best = (sp if t["home_team"] == row["home_team"] else -sp, to, src, rank)
    return best[:3]


def pin_for(gid: str):
    if gid not in close.index:
        return np.nan, np.nan
    r = close.loc[gid]
    return r.get(("pinnacle", "spreads"), np.nan), r.get(("pinnacle", "totals"), np.nan)


# ── in-play quotes ───────────────────────────────────────────────────────────
ip = o[(o["snapshot_type"] == "in_play") & (o["bookmaker"] == "draftkings")
       & o["market"].isin(["h2h", "totals"])].copy()
src = ip["source"].fillna("")
rep = ip[src.str.startswith("historical_inplay")].copy()
ex = rep["source"].str.extract(r"req=([^|]*)\|served=([^|]*)\|lu=([^|]*)")
rep["stamp"], rep["fetch"] = ts(ex[2]), ts(ex[1])
rep["season"] = 2025
live = ip[(src == "")].copy()
live["stamp"], live["fetch"] = ts(live["snapshot_at"]), ts(live["created_at"])
live["own_clock"] = live["snapshot_at"].str.len() > 20      # stamped with OUR clock, not the book's
live = live[live["stamp"] >= pd.Timestamp("2026-08-01", tz="UTC")]
live["season"] = 2026
print(f"2025 replay DraftKings rows: {len(rep):,} ({rep.game_id.nunique()} games); "
      f"2026 live DraftKings rows: {len(live):,} ({live.game_id.nunique()} games)")
print(f"  2026 rows stamped with our own clock (no book timestamp): {int(live['own_clock'].sum()):,}"
      f" on dates {sorted(live.loc[live['own_clock'], 'game_id'].str.slice(6, 16).unique())}")
live = live[~live["own_clock"]]
q = pd.concat([rep, live], ignore_index=True)
vals = ["home_price", "away_price", "total_line", "over_price", "under_price"]
n0 = len(q)
q = q.sort_values(["season", "game_id", "market", "fetch", "odds_id"], kind="stable")
samefetch = q.duplicated(["season", "game_id", "market", "fetch"], keep=False)
differ = q[samefetch].groupby(["season", "game_id", "market", "fetch"])[vals].nunique().max(axis=1)
print(f"  rows sharing (game, market, fetch): {int(samefetch.sum()):,}; of those groups, "
      f"{int((differ > 1).sum())} hold different numbers (of {len(differ):,})")
q = q.drop_duplicates(["season", "game_id", "market", "fetch"] + vals, keep="first")
print(f"  exact duplicate rows dropped: {n0 - len(q):,}; quotes kept: {len(q):,}")
age = (q["fetch"] - q["stamp"]).dt.total_seconds()
print("  fetch - stamp seconds by season:\n", age.groupby(q["season"]).quantile([0, .5, .9, .99, 1]).unstack().round(1).to_string())
q["age"] = age
q[["season", "game_id", "market", "stamp", "fetch", "age", "odds_id"] + vals].to_parquet(OUT / "quotes.parquet", index=False)

# ── ginfo: every game row that carries a quote or a logged state ─────────────
s26 = pd.read_parquet(D / "ncaaf_live_states.parquet")
need = set(q["game_id"]) | set(s26["game_id"])
gi = g[g["game_id"].isin(need)].copy()
fin = gi.apply(final_for, axis=1, result_type="expand")
gi["fh"], gi["fa"], gi["final_src"] = fin[0], fin[1], fin[2]
pri = gi.apply(prior_for, axis=1, result_type="expand")
gi["sp_pre"], gi["T_pre"], gi["prior_src"] = pri[0], pri[1], pri[2]
pin = gi["game_id"].map(pin_for)
gi["pin_sp"], gi["pin_T"] = [x[0] for x in pin], [x[1] for x in pin]
gi["slate"] = gi["game_id"].str.slice(6, 16)
print("\nginfo (games with a DraftKings in-play quote or a logged state):")
print(gi.groupby("season").agg(games=("game_id", "size"), final=("fh", lambda x: x.notna().sum()),
                               prior=("T_pre", lambda x: x.notna().sum())).to_string())
print(gi.groupby(["season", "final_src"]).size().to_string())
print(gi.groupby(["season", "prior_src"]).size().to_string())
both = gi.dropna(subset=["pin_sp", "sp_pre"])
print(f"Pinnacle pre-kick close present on {gi['pin_T'].notna().sum()} of {len(gi)} games; where both: "
      f"mean |DK - Pinnacle| spread {np.abs(both.sp_pre - both.pin_sp).mean():.3f}, "
      f"total {np.abs(both.T_pre - both.pin_T).mean():.3f}; within a point on both "
      f"{((np.abs(both.sp_pre - both.pin_sp) <= 1) & (np.abs(both.T_pre - both.pin_T) <= 1)).mean():.3f}")
gi[["game_id", "season", "slate", "home_team", "away_team", "kick", "fh", "fa", "final_src",
    "sp_pre", "T_pre", "prior_src", "pin_sp", "pin_T", "week"]].to_parquet(OUT / "ginfo.parquet", index=False)

# ── 2025 plays ───────────────────────────────────────────────────────────────
p = pd.read_parquet(D / "ncaaf_plays.parquet")
for c in ("drive_id", "play_number", "period", "clock_minutes", "clock_seconds", "offense_score",
          "defense_score", "week"):
    p[c] = pd.to_numeric(p[c], errors="coerce")
p = p.rename(columns={"game_id_cfbd": "cfbd"})
# CFBD's negative drive ids do not sort into play order with the positive
# ones; those games are left out rather than ordered by a guess
neg_games = set(p.loc[p["drive_id"] < 0, "cfbd"])
print(f"\n2025 play-by-play games with a negative drive id (dropped, order unknowable): {len(neg_games)} "
      f"of {p.cfbd.nunique()}")
p = p[~p["cfbd"].isin(neg_games)]
p = p.sort_values(["cfbd", "drive_id", "play_number"], kind="mergesort").reset_index(drop=True)
p["ord"] = p.groupby("cfbd").cumcount()
hb = p["offense"] == p["home"]
p["h_raw"] = np.where(hb, p["offense_score"], p["defense_score"]).astype(float)
p["a_raw"] = np.where(hb, p["defense_score"], p["offense_score"]).astype(float)
# a lone glitch row (0-0 after a field goal, the two scores swapped) is removed
# by a 5-play centred median; the cumulative maximum then makes the series a step
def med5(x: pd.Series) -> pd.Series:
    """Centred 5-play median, the ends padded with the end values (so a
    median is always one of the five scores, never a half point)."""
    v = x.to_numpy(float)
    pad = np.concatenate([[v[0]] * 2, v, [v[-1]] * 2])
    win = np.lib.stride_tricks.sliding_window_view(pad, 5)
    return pd.Series(np.median(win, axis=1), index=x.index)


for c in ("h", "a"):
    med = p.groupby("cfbd")[f"{c}_raw"].transform(med5)
    p[f"{c}_s"] = med.groupby(p["cfbd"]).cummax()
reg = p["period"] <= 4
p["secs_left"] = np.where(reg, p["clock_minutes"] * 60 + p["clock_seconds"] + 900 * (4 - p["period"]), 0.0)
p["elapsed"] = np.where(reg, REG_S - p["secs_left"], REG_S + (p["period"] - 4))
p["clock_ok"] = by_game_lnds(p, "cfbd", "elapsed")
w = ts(p["wallclock"])
med = w.groupby(p["cfbd"]).transform("median")
off = ((w - med).dt.total_seconds() / 86400.0).round()
p["w"] = w - pd.to_timedelta(off.fillna(0), unit="D")
p["wsec"] = (p["w"] - pd.Timestamp("2025-01-01", tz="UTC")).dt.total_seconds()
p["wall_ok"] = by_game_lnds(p, "cfbd", "wsec")
print(f"\n2025 plays: {len(p):,} in {p.cfbd.nunique()} games; clock in order on {p.clock_ok.mean():.4f}, "
      f"wallclock parsed {w.notna().mean():.4f}, shifted a whole day {(off.abs() >= 1).mean():.4f}, "
      f"wallclock in order {p.wall_ok.mean():.4f}")

# one row per play-by-play game, matched to the games table
pg = p.groupby("cfbd").agg(home=("home", "first"), away=("away", "first"), week=("week", "first"),
                           stype=("season_type", "first"), wmed=("w", "median"), n=("ord", "size"),
                           h_end=("h_s", "last"), a_end=("a_s", "last"), maxp=("period", "max"),
                           wall_ok=("wall_ok", "mean")).reset_index()
pg["pair"] = [" | ".join(sorted([h, a])) for h, a in zip(pg["home"], pg["away"])]
g25 = g[g["season"] == 2025]
rows = []
for _, r in pg.iterrows():
    c = g25[g25["pair"] == r["pair"]]
    if pd.notna(r["wmed"]):
        d0 = r["wmed"].tz_convert(None).normalize()
        c = c[(c["gdate"] - d0).abs() <= pd.Timedelta(days=2)]
    else:
        c = c.iloc[:0]
    fh = fa = sp = to = np.nan
    psrc = "none"
    finals, best = set(), 99
    for _, t in c.iterrows():
        same = t["home_team"] == r["home"]
        if pd.notna(t["hs"]):
            finals.add((t["hs"], t["as_"]) if same else (t["as_"], t["hs"]))
        s_, t_, src_ = prior_own(t["game_id"])
        if src_ != "none" and PRIOR_ORDER.index(src_) < best:
            best, sp, to, psrc = PRIOR_ORDER.index(src_), (s_ if same else -s_), t_, src_
    if len(finals) == 1:
        fh, fa = finals.pop()
    rows.append({"cfbd": r["cfbd"], "n_rows": len(c), "game_ids": "|".join(c["game_id"]),
                 "fh": fh, "fa": fa, "sp_pre": sp, "T_pre": to, "prior_src": psrc})
pg = pg.merge(pd.DataFrame(rows), on="cfbd")
pg["block"] = np.where((pg["stype"] == "regular") & (pg["week"] <= 7), "early", "late")
pg["final_ok"] = (pg["h_end"] == pg["fh"]) & (pg["a_end"] == pg["fa"])
print(f"play-by-play games: {len(pg)}; matched to a games row: {(pg.n_rows > 0).sum()}; with a final: "
      f"{pg.fh.notna().sum()}; play-by-play ends on that final: {pg.final_ok.sum()}; with a prior: "
      f"{pg.T_pre.notna().sum()}")
# every score step must be a football score (1, 2, 3, 6, 7, 8)
p = p.merge(pg[["cfbd", "final_ok", "block", "fh", "fa", "sp_pre", "T_pre", "prior_src"]], on="cfbd")
tot = p["h_s"] + p["a_s"]
step = tot - tot.groupby(p["cfbd"]).shift(1).fillna(0)
bad_step = set(p.loc[~step.isin([0, 1, 2, 3, 6, 7, 8]), "cfbd"])
pg["steps_ok"] = ~pg["cfbd"].isin(bad_step)
pg["clean"] = pg["final_ok"] & pg["steps_ok"]
pg["train_ok"] = pg["clean"] & pg["T_pre"].notna()
print(f"  a score step that is not 1/2/3/6/7/8: {len(bad_step)} games; clean (final matches, steps real): "
      f"{pg.clean.sum()}; clean with a prior (the training set): {pg.train_ok.sum()}")
print(pg[pg.train_ok].groupby(["block", "prior_src"]).size().to_string())
print("  training games by block:", pg[pg.train_ok].groupby("block").size().to_dict(),
      "| early = regular-season weeks 1-7, late = weeks 8+ and the postseason")
pg.to_parquet(OUT / "games_2025.parquet", index=False)

# training states: every 30 s of regulation clock, the last in-order play at or before it
tr = p[p["cfbd"].isin(set(pg.loc[pg.train_ok, "cfbd"])) & p["clock_ok"] & reg].copy()
tr = tr.sort_values(["elapsed", "ord"], kind="stable")
grid = np.arange(TRAIN_SECS[0], TRAIN_SECS[1] + 1, GRID_STEP, dtype=float)
ids = tr["cfbd"].unique()
left = pd.DataFrame({"cfbd": np.repeat(ids, len(grid)), "g": np.tile(grid, len(ids))}).sort_values("g", kind="stable")
st = pd.merge_asof(left, tr[["cfbd", "elapsed", "ord", "period", "h_s", "a_s", "block", "fh", "fa",
                             "sp_pre", "T_pre", "prior_src", "week"]],
                   left_on="g", right_on="elapsed", by="cfbd", direction="backward").dropna(subset=["period"])
st["secs_left"] = REG_S - st["g"]
st["f"] = st["secs_left"] / REG_S
st["m"], st["t"] = st["h_s"] - st["a_s"], st["h_s"] + st["a_s"]
st["mu_pre"] = -st["sp_pre"]
st["final_margin"], st["final_total"] = st["fh"] - st["fa"], st["fh"] + st["fa"]
print(f"training states: {len(st):,} from {st.cfbd.nunique()} games ({len(grid)} grid points a game)")
neg = ((st["final_total"] - st["t"]) < 0).sum()
print(f"  states with more points on the board than the final: {int(neg)}")
st.to_parquet(OUT / "train_states.parquet", index=False)

# 2025 wallclock timeline per ODDS game row (its own home/away orientation)
gid_map = []
for _, r in pg[pg.clean].iterrows():
    for gid in filter(None, r["game_ids"].split("|")):
        gid_map.append((gid, r["cfbd"]))
gid_map = pd.DataFrame(gid_map, columns=["game_id", "cfbd"])
gid_map = gid_map[gid_map["game_id"].isin(set(q.loc[q.season == 2025, "game_id"]))]
gid_map = gid_map.merge(g[["game_id", "home_team"]], on="game_id")
print(f"\n2025 replay games: {q.loc[q.season == 2025, 'game_id'].nunique()}; with a clean play-by-play game: "
      f"{gid_map.game_id.nunique()}")
p["secs_ok"] = np.where(p["clock_ok"], p["secs_left"], np.nan)
p["secs_ff"] = p.groupby("cfbd")["secs_ok"].ffill()
p["per_ok"] = np.where(p["clock_ok"], p["period"], np.nan)
p["per_ff"] = p.groupby("cfbd")["per_ok"].ffill()
tl = p[p["wall_ok"]].merge(gid_map, on="cfbd")
same = tl["home"] == tl["home_team"]
tl["hs"] = np.where(same, tl["h_s"], tl["a_s"])
tl["as_"] = np.where(same, tl["a_s"], tl["h_s"])
tl = tl.rename(columns={"w": "t"})[["game_id", "cfbd", "block", "ord", "t", "per_ff", "secs_ff", "hs", "as_"]]
tl.to_parquet(OUT / "tl_2025.parquet", index=False)
# score-change events with the bracket the true time sits in
p["w_ok"] = p["w"].where(p["wall_ok"])
p["t_hi"] = p.groupby("cfbd")["w_ok"].bfill()
p["t_lo"] = p.groupby("cfbd")["w_ok"].ffill().groupby(p["cfbd"]).shift(1)
ev = p[step > 0].merge(gid_map[["game_id", "cfbd"]], on="cfbd")[["game_id", "cfbd", "ord", "t_lo", "t_hi"]]
d = (ev["t_hi"] - ev["t_lo"]).dt.total_seconds()
print(f"2025 score changes on those games: {len(ev):,}; bracket (previous in-order wallclock to the "
      f"wallclock the score is first seen at) seconds: "
      f"{d.quantile([.25, .5, .75, .9, .95]).round(0).to_dict()}; no upper stamp: {int(ev.t_hi.isna().sum())}")
ev.to_parquet(OUT / "ev_2025.parquet", index=False)

# ── 2026 logged states ───────────────────────────────────────────────────────
s26["seen"] = ts(s26["seen_at"])
s26 = s26.sort_values(["game_id", "seen", "state_id"], kind="stable")
s26["secs_left"] = np.where(s26["period"].between(1, 4), s26["clock_seconds"] + 900 * (4 - s26["period"]),
                            np.where(s26["period"] == 0, REG_S, 0.0))
print(f"\n2026 logged states: {len(s26):,} on {s26.game_id.nunique()} games, "
      f"{s26.seen.min()} .. {s26.seen.max()}")
chg = (s26.groupby("game_id")["home_score"].diff().fillna(0) != 0) | (s26.groupby("game_id")["away_score"].diff().fillna(0) != 0)
down = (s26.groupby("game_id")["home_score"].diff().fillna(0) < 0) | (s26.groupby("game_id")["away_score"].diff().fillna(0) < 0)
s26["score_chg"] = chg
print(f"  score changes logged: {int(chg.sum()):,}, of which a score going DOWN: {int(down.sum())} "
      f"on {s26.loc[down, 'game_id'].nunique()} games")
last = s26.groupby("game_id").tail(1).merge(gi[["game_id", "fh", "fa"]], on="game_id")
print(f"  last logged score equals the final: {((last.home_score == last.fh) & (last.away_score == last.fa)).sum()} "
      f"of {len(last)}; last logged score above the final: {((last.home_score > last.fh) | (last.away_score > last.fa)).sum()}")
s26[["game_id", "seen", "period", "clock_seconds", "secs_left", "home_score", "away_score", "score_chg"]].to_parquet(OUT / "st_2026.parquet", index=False)

# how far the book leads the logged state: DraftKings' first total move of >= 2.5
# points within 5 minutes either side of each logged score change
tq = q[(q.season == 2026) & (q.market == "totals")].sort_values(["game_id", "stamp"])
tq["jump"] = tq.groupby("game_id")["total_line"].diff()
jm = tq[tq["jump"].abs() >= 2.5][["game_id", "stamp", "jump"]]
sc = s26[s26["score_chg"]][["game_id", "seen"]]
m = sc.merge(jm, on="game_id")
m["lag"] = (m["seen"] - m["stamp"]).dt.total_seconds()
m = m[m["lag"].abs() <= 300]
m = m.loc[m.groupby(["game_id", "seen"])["lag"].apply(lambda x: x.abs().idxmin())]
print(f"  logged score change minus DraftKings' nearest total move >= 2.5 pts (seconds; positive = the "
      f"book moved first), n={len(m)}: {m.lag.quantile([.05, .25, .5, .75, .9, .95]).round(0).to_dict()}")
print("done")

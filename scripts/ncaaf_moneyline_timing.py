"""When should the NCAAF moneyline model decide? Replay its live decision at
every hour and grade each timing out of sample.

mike, 2026-11-14: when a model decides is a per-model parameter, chosen by
out-of-sample expected units (CLAUDE.md §1c). This replays
`ncaaf_moneyline_market` (models/ncaaf_moneyline_market.py) at every hourly
instant of the 2023-2025 seasons, through the card's own read and decision
(`quotes_at` -> `decide`, unchanged), with each season's final-margin table
and offset fitted on the seasons before it (the build's `table_for`).

THE PANEL. For every scored game and every whole UTC hour T from the game's
first stored quote to five minutes before kickoff: the decision the card
would make at T, reading each book's newest complete row stamped in the 60
minutes up to T (the card's window, as live). Only the stored historical
pulls are read (source odds_api_historical, the build's PULL_SOURCE).

THE CANDIDATE TIMINGS, fixed before any result was read (the family BH-FDR
divides by):
  * `h00` .. `h23`: once, at that whole UTC hour on the game's Eastern date
    (`h14` is the live card). A game kicking off less than five minutes after
    the hour, or before it, is out of that timing's scope.
  * `first_bet`: every hour from the game's first stored quote until it bets;
    the first BET locks (CLAUDE.md §1c). A game that never bets is not bet.
  * `last_read`: once, at the last whole hour at least five minutes before
    kickoff.

THE TEST. Each timing is graded on 2023-2024 (the selection seasons) and on
2025 (the confirmation season). The timing is chosen on 2023-2024 by units;
BH-FDR runs over all 26 candidates on their 2023-2024 one-sided bootstrap
p-values; the chosen timing is then read on 2025 alone. Reported per timing:
games in scope, games with a consensus, games priced, bets, units by season,
return with a 95% interval (dates resampled), the chance of a positive season
(a season's worth of bet dates resampled from the timing's own dates), and
CLV against Pinnacle's close (power de-vig, `tracking/clv_math`), each bet's
own price.

    python -m scripts.ncaaf_moneyline_timing --cache DIR [--out PATH]
        [--panel-out PATH] [--hours 14,23] [--check-bets PKL ...]

DIR holds ncaaf_games.parquet and ncaaf_odds.parquet, every NCAAF row of
`games` and `odds` (scripts/ncaaf_search/audit_2026_11/extract_ncaaf.py, or
scripts/ncaaf_hourly_extract.py for the hourly purchase). Every row is in
Supabase; nothing else is read.

--hours restricts the panel to those whole UTC hours on each game's Eastern
date (the fixed timings only), which is how the replay is checked against the
build: `--hours 14 --check-bets bets_D0_AM_C.pkl` must hold the research's 311
bets game for game.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.ncaaf_moneyline_market as mm  # noqa: E402
import scripts.ncaaf_moneyline_market_build as build  # noqa: E402
from tracking.clv_math import market_edge_clv  # noqa: E402

SEASONS = (2023, 2024, 2025)
SELECT = (2023, 2024)
CONFIRM = (2025,)
BOOTSTRAP = 4000
FDR_Q = 0.10
CANDIDATES = [f"h{h:02d}" for h in range(24)] + ["first_bet", "last_read"]
PANEL_COLS = ["game_id", "season", "instant", "status", "bookmaker", "side", "price", "edge",
              "prob", "cons", "n_ok", "ml_books"]


# ── the rows ──────────────────────────────────────────────────────────────────

def pull_rows(g: pd.DataFrame, o: pd.DataFrame, seasons) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(h2h rows, spreads rows, games) of every stored historical pull for the
    scored games of `seasons`, as the card's read takes them, one odds id per
    real game (the build's choice: the id with more stored quotes)."""
    h = o[(o["source"].fillna("").str.split("|").str[0] == build.PULL_SOURCE)
          & (o["snapshot_type"] == "open")].copy()
    h["ts"] = pd.to_datetime(h["snapshot_at"], utc=True, errors="coerce", format="mixed")
    h["pull_ts"] = h["created_at"].map(h.groupby("created_at")["ts"].max())
    h = h[h["bookmaker"].isin(mm.CONS_BOOKS) & h["market"].isin(["spreads", "totals", "h2h"])]
    gg = g[g["margin"].notna() & g["season"].isin(list(seasons)) & g["kick"].notna()]
    h = h.merge(gg[["game_id", "kick", "et_date", "season", "twin_of"]], on="game_id", how="inner")
    h = h[h["pull_ts"] < h["kick"] - mm.MIN_LEAD]
    per = h.drop_duplicates(["game_id", "pull_ts", "bookmaker"])
    n = per.assign(canon=per["twin_of"].fillna(per["game_id"])).groupby(
        ["canon", "game_id"]).size().reset_index(name="n")
    n = n.sort_values(["canon", "n", "game_id"], ascending=[True, False, True], kind="mergesort")
    h = h[h["game_id"].isin(set(n.drop_duplicates("canon")["game_id"]))]
    h = h[h["market"].isin(["h2h", "spreads"]) & h["ts"].notna()]
    h["tip"] = h["kick"]
    for c in ("home_price", "away_price", "spread_home"):
        h[c] = pd.to_numeric(h[c], errors="coerce").astype(float)
    h = h.rename(columns={"home_price": "p1", "away_price": "p2", "spread_home": "line"})
    cols = ["game_id", "bookmaker", "ts", "line", "p1", "p2", "order", "tip"]
    games = h.drop_duplicates("game_id")[["game_id", "season", "et_date", "kick"]]
    h = h.sort_values("ts", kind="mergesort")
    return (h[h["market"] == "h2h"][cols].reset_index(drop=True),
            h[h["market"] == "spreads"][cols].reset_index(drop=True),
            games.reset_index(drop=True))


def _window(rows: pd.DataFrame, ts: np.ndarray, t: pd.Timestamp) -> pd.DataFrame:
    """Rows stamped in the card's window up to t. rows sorted by ts; ts their
    stamps as UTC datetime64 (rows["ts"].values)."""
    lo = np.searchsorted(ts, np.datetime64((t - timedelta(minutes=mm.WINDOW_MIN)).tz_convert(None)), "left")
    hi = np.searchsorted(ts, np.datetime64(t.tz_convert(None)), "right")
    return rows.iloc[lo:hi]


def instants(games: pd.DataFrame, ml: pd.DataFrame, hours) -> list[pd.Timestamp]:
    """Every whole UTC hour the panel decides at. hours=None: every hour from
    the season's first stored quote to its last kickoff."""
    if hours is not None:
        out = set()
        for d in games["et_date"].unique():
            day = pd.Timestamp(str(d)[:10], tz="UTC")
            out.update(day + pd.Timedelta(hours=int(h)) for h in hours)
        return sorted(out)
    t0 = ml["ts"].min().floor("h") + pd.Timedelta(hours=1)
    t1 = games["kick"].max().floor("h")
    return list(pd.date_range(t0, t1, freq="h"))


def panel(rows: tuple, tables: dict, hours=None, log_every: int = 200) -> pd.DataFrame:
    """The card's decision for every game at every instant it is in scope."""
    ml, sp, games = rows
    kick = games.set_index("game_id")["kick"]
    season_of = games.set_index("game_id")["season"]
    et_of = games.set_index("game_id")["et_date"].astype(str).str[:10]
    out = []
    t0 = time.time()
    for season in sorted(games["season"].unique()):
        table, offset, _ = tables[int(season)]
        gs = games[games["season"] == season]
        ids_s = set(gs["game_id"])
        ml_s = ml[ml["game_id"].isin(ids_s)].reset_index(drop=True)
        sp_s = sp[sp["game_id"].isin(ids_s)].reset_index(drop=True)
        ml_ts, sp_ts = ml_s["ts"].values, sp_s["ts"].values
        ts_list = instants(gs, ml_s, hours)
        for i, t in enumerate(ts_list):
            m = _window(ml_s, ml_ts, t)
            s = _window(sp_s, sp_ts, t)
            # In scope at t: still to kick off at least five minutes after t,
            # and on t's Eastern date when the panel is the fixed hours only.
            ids = {gid for gid in set(m["game_id"]) | set(s["game_id"])
                   if not mm.too_close(kick[gid], t)}
            if hours is not None:
                day = t.strftime("%Y-%m-%d")
                ids = {gid for gid in ids if et_of[gid] == day}
            if not ids:
                continue
            m = m[m["game_id"].isin(ids)].assign(instant=t)
            s = s[s["game_id"].isin(ids)].assign(instant=t)
            q = mm.quotes_at(m, s)
            nml = (q[q["bookmaker"].isin(mm.DECIDING_BOOKS) & q["ml_home"].notna()
                     & q["ml_away"].notna()].groupby("game_id").size())
            for d in mm.decide(sorted(ids), q, table, offset):
                b = d.best or {}
                out.append((d.game_id, int(season_of[d.game_id]), t, d.status, b.get("bookmaker"),
                            b.get("side"), b.get("price"), b.get("edge"), b.get("prob"),
                            b.get("cons"), b.get("n_ok"), int(nml.get(d.game_id, 0))))
            if log_every and i % log_every == 0:
                print(f"  season {season}: instant {i + 1}/{len(ts_list)} {t:%Y-%m-%d %H}Z, "
                      f"{len(out)} decisions ({time.time() - t0:.0f}s)", flush=True)
    return pd.DataFrame(out, columns=PANEL_COLS)


# ── the timings ───────────────────────────────────────────────────────────────

def timing_rows(p: pd.DataFrame, games: pd.DataFrame, name: str) -> pd.DataFrame:
    """The one decision each game gets under timing `name` (one row a game in
    that timing's scope)."""
    if name.startswith("h"):
        hour = int(name[1:])
        inst = {r.game_id: pd.Timestamp(str(r.et_date)[:10], tz="UTC") + pd.Timedelta(hours=hour)
                for r in games.itertuples(index=False)}
        x = p[p["instant"] == p["game_id"].map(inst)]
        return x.drop_duplicates("game_id")
    if name == "first_bet":
        b = p[p["status"] == "bets"].sort_values(["game_id", "instant"], kind="mergesort")
        first = b.drop_duplicates("game_id")
        rest = p[~p["game_id"].isin(set(first["game_id"]))]
        last = rest.sort_values(["game_id", "instant"], kind="mergesort").drop_duplicates(
            "game_id", keep="last")
        return pd.concat([first, last], ignore_index=True)
    if name == "last_read":
        return p.sort_values(["game_id", "instant"], kind="mergesort").drop_duplicates(
            "game_id", keep="last")
    raise ValueError(name)


def pinnacle_close(ml: pd.DataFrame) -> pd.DataFrame:
    """Pinnacle's last stored moneyline stamped before kickoff, per game."""
    x = ml[(ml["bookmaker"] == "pinnacle") & (ml["ts"] <= ml["tip"])
           & ml["p1"].notna() & ml["p2"].notna()]
    x = x.sort_values(["game_id", "ts", "order"], kind="mergesort").drop_duplicates("game_id", keep="last")
    return x.set_index("game_id")[["p1", "p2", "ts"]].rename(
        columns={"p1": "pin_home", "p2": "pin_away", "ts": "pin_ts"})


def with_clv(b: pd.DataFrame, pin: pd.DataFrame) -> pd.DataFrame:
    b = b.join(pin, on="game_id")
    clv = []
    for r in b.itertuples(index=False):
        if pd.isna(r.pin_home) or pd.isna(r.pin_away):
            clv.append(np.nan)
            continue
        side, other = ((r.pin_home, r.pin_away) if r.side == "home" else (r.pin_away, r.pin_home))
        pct, _, _ = market_edge_clv(r.price, side, [other])
        clv.append(np.nan if pct is None else pct)
    b["clv_pct"] = clv
    return b


def _boot(b: pd.DataFrame, rng) -> dict:
    """Return, its 95% interval, the one-sided p of a return at or below zero,
    and the chance of a positive season, all over bet dates."""
    if not len(b):
        return {"roi_ci95": None, "p_le_zero": 1.0, "p_positive_season": None}
    dd = b.groupby("et_date").agg(u=("units", "sum"), r=("risk", "sum"))
    u, r = dd["u"].to_numpy(), dd["r"].to_numpy()
    j = rng.integers(0, len(dd), size=(BOOTSTRAP, len(dd)))
    roi = u[j].sum(1) / r[j].sum(1) * 100
    lo, hi = np.percentile(roi, [2.5, 97.5])
    n_season = max(1, int(round(len(dd) / max(1, b["season"].nunique()))))
    k = rng.integers(0, len(dd), size=(BOOTSTRAP, n_season))
    return {"roi_ci95": [round(float(lo), 1), round(float(hi), 1)],
            "p_le_zero": round(float((roi <= 0).mean()), 4),
            "p_positive_season": round(float((u[k].sum(1) > 0).mean()), 3)}


def grade_timing(dec: pd.DataFrame, g: pd.DataFrame, pin: pd.DataFrame, seasons, rng) -> dict:
    x = dec[dec["season"].isin(list(seasons))]
    bets = x[x["status"] == "bets"].merge(g[["game_id", "margin", "et_date"]], on="game_id", how="left")
    bets = build.grade(bets.copy())
    bets = with_clv(bets, pin) if len(bets) else bets
    out = {"games_in_scope": int(len(x)),
           "with_consensus": int((x["n_ok"].fillna(0) > 0).sum()),
           "priced": int(x["edge"].notna().sum()),
           "bets": int(len(bets))}
    if not len(bets):
        return {**out, "units": 0.0, "roi_pct": None, "units_by_season": {}}
    out.update({
        "record": f"{int((bets.result == 'W').sum())}-{int((bets.result == 'L').sum())}",
        "units": round(float(bets["units"].sum()), 2),
        "risked": round(float(bets["risk"].sum()), 2),
        "roi_pct": round(float(bets["units"].sum() / bets["risk"].sum() * 100), 2),
        "units_by_season": {str(s): round(float(bets.loc[bets["season"] == s, "units"].sum()), 2)
                            for s in seasons},
        "bets_by_season": {str(s): int((bets["season"] == s).sum()) for s in seasons},
        "price_min": float(bets["price"].min()), "price_median": float(bets["price"].median()),
        "price_max": float(bets["price"].max()),
        "road_teams": int((bets["side"] == "away").sum()),
        "clv_n": int(bets["clv_pct"].notna().sum()),
        "clv_mean_pct": (round(float(bets["clv_pct"].mean()), 2)
                         if bets["clv_pct"].notna().any() else None),
        "clv_beat_share": (round(float((bets["clv_pct"] > 0).sum() / bets["clv_pct"].notna().sum()), 3)
                           if bets["clv_pct"].notna().any() else None),
    })
    out.update(_boot(bets, rng))
    return out


def bh(pvals: dict, q: float) -> set:
    """Benjamini-Hochberg: the names whose p-values are rejected at FDR q."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    k = 0
    for i, (_, p) in enumerate(items, 1):
        if p <= q * i / m:
            k = i
    return {name for name, _ in items[:k]}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--panel-out", type=Path, default=None)
    ap.add_argument("--panel-in", type=Path, default=None,
                    help="read a panel written by --panel-out instead of rebuilding it")
    ap.add_argument("--hours", type=str, default=None,
                    help="comma-separated whole UTC hours: the fixed timings only")
    ap.add_argument("--check-bets", type=str, nargs="*", default=[],
                    help="HOUR=PKL pairs: compare that fixed hour's bets with a research pickle")
    a = ap.parse_args(argv)
    t0 = time.time()
    g, o = build.history(a.cache)
    tables = {s: build.table_for(g, s) for s in SEASONS}
    for s, (_, c, n) in tables.items():
        print(f"season {s}: margin table on {n} games, offset {c:+.3f}", flush=True)
    rows = pull_rows(g, o, SEASONS)
    del o
    ml, sp, games = rows
    print(f"rows: {len(ml)} moneyline, {len(sp)} spread, {len(games)} games "
          f"({time.time() - t0:.0f}s)", flush=True)
    hours = [int(h) for h in a.hours.split(",")] if a.hours else None
    if a.panel_in:
        p = pd.read_parquet(a.panel_in)
    else:
        p = panel(rows, tables, hours)
        if a.panel_out:
            p.to_parquet(a.panel_out)
    print(f"panel: {len(p)} decisions over {p['instant'].nunique()} instants, "
          f"{p['game_id'].nunique()} games ({time.time() - t0:.0f}s)", flush=True)

    names = [f"h{h:02d}" for h in hours] if hours else CANDIDATES
    pin = pinnacle_close(ml)
    rng = np.random.default_rng(7)
    res = {}
    for name in names:
        dec = timing_rows(p, games, name)
        res[name] = {"all": grade_timing(dec, g, pin, SEASONS, rng),
                     "select_2023_2024": grade_timing(dec, g, pin, SELECT, rng),
                     "confirm_2025": grade_timing(dec, g, pin, CONFIRM, rng)}
        r = res[name]["all"]
        print(f"{name:>10}: {r['bets']:4d} bets, {r.get('units', 0):+8.2f} units, "
              f"return {r.get('roi_pct')}%, by season {r.get('units_by_season')}", flush=True)

    checks = {}
    for spec in a.check_bets:
        hour, pkl = spec.split("=", 1)
        dec = timing_rows(p, games, f"h{int(hour):02d}")
        bets = dec[dec["status"] == "bets"][["game_id", "bookmaker", "side", "price", "edge"]]
        checks[f"h{int(hour):02d}"] = build.check_bets(bets, Path(pkl), mm.CUT)
        print(f"check h{int(hour):02d} against {Path(pkl).name}: {checks[f'h{int(hour):02d}']}", flush=True)

    summary = {"candidates": names, "fdr_q": FDR_Q, "results": res, "checks": checks}
    if not hours:
        sel = {n: res[n]["select_2023_2024"] for n in names}
        pvals = {n: (sel[n]["p_le_zero"] if sel[n]["bets"] else 1.0) for n in names}
        passed = bh(pvals, FDR_Q)
        chosen = max(names, key=lambda n: sel[n].get("units", 0.0))
        summary.update({
            "chosen_on_2023_2024": chosen,
            "chosen_units_2023_2024": sel[chosen].get("units"),
            "chosen_p_2023_2024": pvals[chosen],
            "bh_fdr_survivors_2023_2024": sorted(passed),
            "chosen_confirm_2025": res[chosen]["confirm_2025"],
            "live_h14": {"select_2023_2024": res["h14"]["select_2023_2024"],
                         "confirm_2025": res["h14"]["confirm_2025"]},
        })
        print(f"chosen on 2023-2024: {chosen} ({sel[chosen].get('units')} units, "
              f"p {pvals[chosen]}); BH-FDR survivors at q={FDR_Q}: {sorted(passed) or 'none'}; "
              f"on 2025: {res[chosen]['confirm_2025'].get('units')} units, "
              f"return {res[chosen]['confirm_2025'].get('roi_pct')}% "
              f"{res[chosen]['confirm_2025'].get('roi_ci95')}", flush=True)
    if a.out:
        a.out.write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
        print(f"wrote {a.out}", flush=True)


if __name__ == "__main__":
    main()

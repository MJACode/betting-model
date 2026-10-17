"""
NFL edge search: does the PLAYER-PROP market price WIND?

Hypothesis. The full-game totals market prices only part of the wind effect
(docs/nfl_wind_lead_evidence.md). Nobody has checked props. High wind should
suppress passing volume and efficiency, so QB passing and WR/TE receiving
props should go UNDER more often in windy open-air games, and rushing volume
should go OVER. The question is not "do unders win" (prop lines lean over
everywhere, docs/nfl_prop_over_lean.md) but whether they win MORE in wind than
in the identical selection on calm open-air games and on domes.

CONSTRUCTION (written before any outcome was read; not changed afterwards)
-------------------------------------------------------------------------
Population. Main-line (non-alternate) props, seasons 2023-2025, in eight
markets. Mechanism side per market, fixed in advance:
    group P (bet UNDER): player_pass_yds, player_pass_completions,
        player_pass_attempts, player_pass_tds, player_reception_yds,
        player_receptions
    group R (bet OVER):  player_rush_attempts, player_rush_yds
One bet per proposition = (game, player, market).

Decision time. Three variants, each graded separately:
    latest  the latest snapshot strictly before kickoff (lead > 0h)
    T24     the latest snapshot at least 24h before kickoff
    T48     the latest snapshot at least 48h before kickoff (line-move table,
            and the 3-day-forecast bet)
For each proposition, the decision snapshot is the latest snapshot_at meeting
the bound, and only quotes AT that snapshot are used, so every book in the
consensus is observed at the same moment. No quote after the decision time is
read. No feature is derived from the outcome.

Line and price. Only BETTABLE books (scripts/nfl_edge_lib.BETTABLE), EXCLUDED
books dropped. At least two bettable books must quote the player at the
decision snapshot. The line is the MODAL line among those books (ties: the line
nearest their median, then the lower line). The bet is graded at the BEST
bettable price for the mechanism side AT THAT LINE. Fair probability of the
under = mean over books at that line with both prices of the proportional
no-vig split (lib.devig2). Pushes return the stake.

Grading. Actual stat from the nflverse player log (lib.player_log), joined on
(game, normalised name). A player missing from the stat log but present in the
snap-count log with offense_pct > 0 played and recorded nothing: actual = 0.
A player in neither did not play: the prop is void and dropped (counted).
BUG FIXED AFTER THE FIRST RUN: the stat log has NO rows for the 2023 and 2024
postseasons (26 games), so the zero-fill turned every prop in them into 0
(Mahomes 0 passing yards in the Jan-2024 Miami wild card). The zero-fill now
applies only to games the stat log covers; props in those 26 games are void.

Wind. Game environment from nflverse roof: outdoor = 'outdoors' or 'open';
dome = 'dome' or 'closed'; blank roof = excluded from both.
    obs     nflverse `wind` (recorded at the game; NOT knowable at bet time;
            the mechanism test). Outdoor only. 2023-2025.
    fc_d1   Open-Meteo forecast for the kickoff hour as ISSUED one day earlier
            (stadium_weather_hourly). Outdoor only. 2024-2025. Bettable with
            the 'latest' quote; with the T24 quote it is roughly simultaneous.
    fc_d3   the same, issued three days earlier. Bettable at every decision.
    era5    ERA5 reanalysis wind at the stadium's coordinates, kickoff hour,
            fetched free from archive-api.open-meteo.com and cached. Defined
            for DOMES too: the placebo.
Windy = wind >= T for T in {10, 12, 15, 18} mph. Calm = wind < 10 mph (one
fixed control for every T; the 10-T band is excluded at T > 10).

Comparisons (every one a cluster bootstrap by game, 90% interval):
    W - C    ROI of the mechanism side, windy open-air minus calm open-air
    DiD      (W - C) - (Dome_W - Dome_C): Dome_W is the dome ROI reweighted
             to the WEEK mix of the windy bets and Dome_C to the week mix of
             the calm bets. Wind is a late-season phenomenon; this removes
             whatever the calendar does to prop outcomes on its own.
Price-free view: mechanism-side hit rate minus the no-vig fair probability,
and mean (actual - line), windy vs calm vs dome.

Fit / hold-out.
    obs:      fit 2023-2024, hold-out 2025.
    forecast: fit 2024 (the issued-forecast archive starts 2024-01-18),
              hold-out 2025.
    A PRIORI primary cell (declared here, not chosen): fc_d1, latest quote,
        group P, T = 12 mph (the repo's nflverse totals threshold).
    FIT-CHOSEN cell: among bettable cells (fc_d1/fc_d3 x decision x group P/R
        x T), the largest 2024 W - C ROI difference with >= 25 windy bets in
        2024. Its 2025 numbers are then read once.
    obs mechanism: the T with the largest 2023-24 W - C for group P with >= 50
        windy bets; its 2025 numbers read once.

Placebos that must NOT work if the mechanism is real:
    1. Domes in ambient wind (era5 >= T): the roof removes the wind, so the
       dome W - C must be ~0 while the open-air one is not.
    2. Wind shuffled across open-air games WITHIN the same season-week
       (1,000 permutations): the observed W - C must sit in the tail.

ADDED AFTER THE FIRST RUN (inference only; no selection rule changed). The
first run showed the dome placebo's raw W - C was NOT ~0, and that unders win
more late in the season in every roof type. Table [7b] therefore adds a
CALENDAR-MATCHED W - C: windy minus calm bets in the SAME season-week only,
weighted by windy bets (weeks with no calm game drop out and are counted),
same stratified game bootstrap. It is applied identically to the open-air
cells and to the dome placebo. Table [6b] adds the per-season and early/late
split for the QB passing-yards-only cells, and the grid gains a win% column.
Table [6c] (added after the second run) lists every game in the forecast
>= 15 mph cell, because that cell rests on 25 games.

Season splits: every season separately; early (weeks 1-9) vs late (10+).
2026 Week 1: the prop cache holds only ~3-4-day-out quotes for 16 games; it is
an appendix row, never part of the fit or the hold-out.

Units: 1 unit = one flat bet (CLAUDE.md §4). No database, no Odds API.

    python -m scripts.nfl_edge_prop_wind
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import urllib.request

import numpy as np
import pandas as pd

from nfl.data_ingest.weather import STADIUM_COORDS
from scripts.nfl_edge_lib import (BETTABLE, CACHE, EXCLUDED, am_to_dec, boot_ci,
                                  devig2, games, player_log, profit_units,
                                  props_market)

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 500)

MARKETS = {  # market -> (stat column, mechanism side, group)
    "player_pass_yds": ("passing_yards", "under", "P"),
    "player_pass_completions": ("completions", "under", "P"),
    "player_pass_attempts": ("attempts", "under", "P"),
    "player_pass_tds": ("passing_tds", "under", "P"),
    "player_reception_yds": ("receiving_yards", "under", "P"),
    "player_receptions": ("receptions", "under", "P"),
    "player_rush_yds": ("rushing_yards", "over", "R"),
    "player_rush_attempts": ("carries", "over", "R"),
}
SHORT = {"player_pass_yds": "pass_yds", "player_pass_completions": "pass_cmp",
         "player_pass_attempts": "pass_att", "player_pass_tds": "pass_tds",
         "player_reception_yds": "rec_yds", "player_receptions": "receptions",
         "player_rush_yds": "rush_yds", "player_rush_attempts": "rush_att"}
THRESHOLDS = [10, 12, 15, 18]
CALM = 10.0
DECISIONS = {"latest": 0.0, "T24": 24.0, "T48": 48.0}
SEASONS = [2023, 2024, 2025]
FIT_OBS, FIT_FC, HOLD = [2023, 2024], [2024], 2025
NBOOT = 2000
ERA5_FILE = CACHE / "era5_wind_stadiums_2023_2026.parquet"
LOWVOL = 40  # windy bets per season at or below which a cell is "low volume"


# ─── names ─────────────────────────────────────────────────────────────────

_SUF = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


def norm(s) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower().replace(".", " ")
    s = _SUF.sub(" ", s)
    return re.sub(r"[^a-z]", "", s)


def norm_series(x: pd.Series) -> pd.Series:
    u = pd.Series(x.dropna().unique())
    m = dict(zip(u, u.map(norm)))
    return x.map(m)


# ─── games and wind ────────────────────────────────────────────────────────

def load_games() -> pd.DataFrame:
    g = games()
    g = g[g.season.between(2023, 2026)].copy()
    roof = g.roof.fillna("").astype(str).str.strip()
    g["env"] = np.where(roof.isin(["outdoors", "open"]), "outdoor",
                        np.where(roof.isin(["dome", "closed"]), "dome", "unknown"))
    g["gid"] = "NFL_" + g.game_id
    g["hr"] = g.kick.dt.floor("h").astype("datetime64[ns, UTC]")
    g["obs"] = np.where(g.env == "outdoor", g.wind, np.nan)
    # issued forecasts, kickoff hour
    w = pd.read_parquet(CACHE / "stadium_weather_hourly.parquet",
                        columns=["stadium_id", "ts", "fc_d1_mph", "fc_d3_mph"])
    for c in ("fc_d1_mph", "fc_d3_mph"):
        w[c] = pd.to_numeric(w[c], errors="coerce").astype(float)
    w["ts"] = w.ts.astype("datetime64[ns, UTC]")
    w = w.drop_duplicates(["stadium_id", "ts"])
    g = g.merge(w, left_on=["stadium_id", "hr"], right_on=["stadium_id", "ts"], how="left")
    g["fc_d1"] = np.where(g.env == "outdoor", g.fc_d1_mph, np.nan)
    g["fc_d3"] = np.where(g.env == "outdoor", g.fc_d3_mph, np.nan)
    # ERA5 ambient wind, all stadiums incl. domes
    e = era5(sorted(set(g.stadium_id.dropna()) & set(STADIUM_COORDS)))
    e["ts_e"] = e.ts_e.astype("datetime64[ns, UTC]")
    g = g.merge(e, left_on=["stadium_id", "hr"], right_on=["stadium_id", "ts_e"], how="left")
    g["era5"] = np.where(g.env.isin(["outdoor", "dome"]), g.era5_mph, np.nan)
    return g[["gid", "season", "week", "game_type", "kick", "env", "stadium_id",
              "obs", "fc_d1", "fc_d3", "era5", "roof"]]


def era5(stadiums) -> pd.DataFrame:
    """ERA5 kickoff-hour wind per stadium, 2023-08 .. 2026-09. Free, cached."""
    if ERA5_FILE.exists():
        e = pd.read_parquet(ERA5_FILE)
        if set(stadiums) <= set(e.stadium_id):
            return e
    frames = []
    for sid in stadiums:
        lat, lon = STADIUM_COORDS[sid]
        url = ("https://archive-api.open-meteo.com/v1/archive?"
               f"latitude={lat}&longitude={lon}&start_date=2023-08-01&end_date=2026-09-30"
               "&hourly=wind_speed_10m&wind_speed_unit=mph&timezone=UTC")
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=120) as r:
                    j = json.loads(r.read().decode("utf-8"))
                break
            except Exception as exc:  # noqa: BLE001 - retry then fail loudly
                if attempt == 4:
                    raise SystemExit(f"ERA5 fetch failed for {sid}: {exc}")
                time.sleep(5 * (attempt + 1))
        h = j["hourly"]
        frames.append(pd.DataFrame({"stadium_id": sid,
                                    "ts_e": pd.to_datetime(h["time"]).tz_localize("UTC"),
                                    "era5_mph": pd.to_numeric(h["wind_speed_10m"], errors="coerce")}))
        time.sleep(0.5)
    e = pd.concat(frames, ignore_index=True)
    e.to_parquet(ERA5_FILE, index=False)
    return e


# ─── actuals ───────────────────────────────────────────────────────────────

def load_actuals():
    L = player_log()
    L = L[L.season >= 2023].copy()
    L["key"] = norm_series(L.player_name)
    stats = sorted({v[0] for v in MARKETS.values()})
    for c in stats:
        L[c] = pd.to_numeric(L[c], errors="coerce").astype(float)
    L = L[["game_id", "key"] + stats]
    dup = L.duplicated(["game_id", "key"], keep=False)
    L = L[~dup]
    s = pd.read_parquet(CACHE / "local_nfl_snap_counts.parquet",
                        columns=["game_id", "norm_name", "offense_pct"])
    s = s[s.game_id.str[4:8].astype(int) >= 2023]
    s = s[pd.to_numeric(s.offense_pct, errors="coerce") > 0]
    s["key"] = s.norm_name.astype(str).str.replace(r"(jr|sr|iii|ii|iv)$", "", regex=True)
    # Zero-fill is only valid for a game the stat log COVERS. The 2023 and 2024
    # postseasons (26 games) have snap counts but no stat rows at all; filling
    # those with 0 turned every prop in them into a fake under win (first run).
    covered = set(L.game_id)
    snaps = {k for k in zip(s.game_id, s.key) if k[0] in covered}
    return L, snaps, int(dup.sum())


# ─── props -> one decision per proposition ─────────────────────────────────

def decisions(market: str, g: pd.DataFrame, L: pd.DataFrame, snaps: set) -> dict:
    stat, side, grp = MARKETS[market]
    p = props_market(market)
    p = p[["game_id", "player_name", "line", "over_price", "under_price",
           "bookmaker", "snapshot_at"]].copy()
    p["bookmaker"] = p.bookmaker.astype(str)
    p = p[~p.bookmaker.isin(EXCLUDED) & p.bookmaker.isin(BETTABLE)]
    p = p.rename(columns={"game_id": "gid"})
    p = p.merge(g[["gid", "kick"]], on="gid", how="inner")
    p["lead_h"] = (p.kick - p.snapshot_at).dt.total_seconds() / 3600
    p = p[p.lead_h > 0]                                   # strictly pre-kickoff
    p["key"] = norm_series(p.player_name)
    p = p.drop_duplicates(["gid", "key", "bookmaker", "snapshot_at"])
    out = {}
    for dec, lead in DECISIONS.items():
        x = p[p.lead_h >= lead]
        last = x.groupby(["gid", "key"]).snapshot_at.transform("max")
        x = x[x.snapshot_at == last]
        nb = x.groupby(["gid", "key"]).bookmaker.nunique().rename("n_books")
        x = x.join(nb, on=["gid", "key"])
        x = x[x.n_books >= 2]
        cnt = x.groupby(["gid", "key", "line"]).size().rename("n").reset_index()
        med = x.groupby(["gid", "key"]).line.median().rename("med")
        cnt = cnt.join(med, on=["gid", "key"])
        cnt["dist"] = (cnt.line - cnt.med).abs()
        cnt = cnt.sort_values(["gid", "key", "n", "dist", "line"],
                              ascending=[True, True, False, True, True])
        cons = cnt.drop_duplicates(["gid", "key"])[["gid", "key", "line", "n"]]
        at = x.merge(cons, on=["gid", "key", "line"])
        col = f"{side}_price"
        a = at.dropna(subset=[col]).copy()
        a["dec_p"] = am_to_dec(a[col])
        best = a.loc[a.groupby(["gid", "key"]).dec_p.idxmax(),
                     ["gid", "key", "line", col, "lead_h", "n_books", "n"]]
        best = best.rename(columns={col: "price", "n": "n_at_line"})
        both = at.dropna(subset=["over_price", "under_price"])
        _, pu = devig2(both.over_price.values, both.under_price.values)
        fair = pd.Series(pu, index=both.index).groupby([both.gid, both.key]).mean().rename("fair_under")
        best = best.join(fair, on=["gid", "key"])
        # grade
        best = best.merge(L[["game_id", "key", stat]], left_on=["gid", "key"],
                          right_on=["game_id", "key"], how="left").drop(columns="game_id")
        played0 = best[stat].isna() & pd.Series(
            [k in snaps for k in zip(best.gid, best.key)], index=best.index)
        best.loc[played0, stat] = 0.0
        n_void = int(best[stat].isna().sum())
        best = best.dropna(subset=[stat]).rename(columns={stat: "actual"})
        best["push"] = (best.actual == best.line).astype(int)
        best["under_hit"] = (best.actual < best.line).astype(int)
        won = best.under_hit if side == "under" else (best.actual > best.line).astype(int)
        best["won"] = won
        best["profit"] = profit_units(won.values, best.price.values, best.push.values)
        best["fair_side"] = best.fair_under if side == "under" else 1 - best.fair_under
        best["market"], best["side"], best["grp"], best["dec"] = market, side, grp, dec
        best["n_void"] = n_void
        best["n_zero_fill"] = int(played0.sum())
        out[dec] = best
    return out


# ─── bootstrap: W - C and the dome-week-reweighted DiD ─────────────────────

def did_boot(df: pd.DataFrame, n: int = NBOOT, seed: int = 11) -> dict:
    """df: profit, gid, grp in {W,C,D}, wk. Stratified cluster bootstrap by game."""
    if (df.grp == "W").sum() == 0 or (df.grp == "C").sum() == 0:
        return {}
    gcode, guniq = pd.factorize(df.gid)
    wcode, wuniq = pd.factorize(df.wk)
    gg = pd.Series(df.grp.values, index=gcode).groupby(level=0).first()
    strata = {k: gg.index[gg.values == k].values for k in ("W", "C", "D")}
    y = df.profit.values.astype(float)
    isW, isC, isD = (df.grp.values == "W"), (df.grp.values == "C"), (df.grp.values == "D")
    nw = len(wuniq)

    def stats(w):
        W = (w * y)[isW].sum() / w[isW].sum()
        C = (w * y)[isC].sum() / w[isC].sum()
        out = {"W": W, "C": C, "WC": W - C}
        if isD.any():
            dsum = np.bincount(wcode[isD], weights=(w * y)[isD], minlength=nw)
            dcnt = np.bincount(wcode[isD], weights=w[isD], minlength=nw)
            ok = dcnt > 0
            m = np.where(ok, dsum / np.where(ok, dcnt, 1), 0.0)
            wW = np.bincount(wcode[isW], weights=w[isW], minlength=nw) * ok
            wC = np.bincount(wcode[isC], weights=w[isC], minlength=nw) * ok
            dW = (wW * m).sum() / wW.sum() if wW.sum() > 0 else np.nan
            dC = (wC * m).sum() / wC.sum() if wC.sum() > 0 else np.nan
            out.update({"D": (w * y)[isD].sum() / w[isD].sum(), "DiD": (W - C) - (dW - dC)})
        return out

    point = stats(np.ones(len(y)))
    rng = np.random.default_rng(seed)
    draws = []
    ng = len(guniq)
    for _ in range(n):
        cnt = np.zeros(ng)
        for k, idx in strata.items():
            if len(idx):
                np.add.at(cnt, idx[rng.integers(0, len(idx), len(idx))], 1)
        draws.append(stats(cnt[gcode]))
    dr = pd.DataFrame(draws)
    res = {}
    for k, v in point.items():
        lo, hi = np.nanquantile(dr[k], [0.05, 0.95])
        res[k] = (v, lo, hi)
    return res


def week_matched(df: pd.DataFrame, n: int = NBOOT, seed: int = 5) -> dict:
    """Calendar-matched W - C: within each season-week, mean(W) - mean(C),
    averaged with weights = windy bets. df: profit, gid, grp in {W,C}, wk."""
    df = df[df.grp.isin(["W", "C"])]
    if (df.grp == "W").sum() == 0 or (df.grp == "C").sum() == 0:
        return {}
    gcode, guniq = pd.factorize(df.gid)
    wcode, wuniq = pd.factorize(df.wk)
    gg = pd.Series(df.grp.values, index=gcode).groupby(level=0).first()
    strata = {k: gg.index[gg.values == k].values for k in ("W", "C")}
    y = df.profit.values.astype(float)
    isW = df.grp.values == "W"
    nw = len(wuniq)

    def est(w):
        sW = np.bincount(wcode[isW], weights=(w * y)[isW], minlength=nw)
        nW = np.bincount(wcode[isW], weights=w[isW], minlength=nw)
        sC = np.bincount(wcode[~isW], weights=(w * y)[~isW], minlength=nw)
        nC = np.bincount(wcode[~isW], weights=w[~isW], minlength=nw)
        ok = (nW > 0) & (nC > 0)
        if not ok.any():
            return np.nan
        d = sW[ok] / nW[ok] - sC[ok] / nC[ok]
        return (nW[ok] * d).sum() / nW[ok].sum()

    one = np.ones(len(y))
    sWk = np.bincount(wcode[isW], minlength=nw)
    sCk = np.bincount(wcode[~isW], minlength=nw)
    kept = sWk[(sCk > 0)].sum() / sWk.sum()
    point = est(one)
    rng = np.random.default_rng(seed)
    ng = len(guniq)
    dr = []
    for _ in range(n):
        cnt = np.zeros(ng)
        for idx in strata.values():
            np.add.at(cnt, idx[rng.integers(0, len(idx), len(idx))], 1)
        dr.append(est(cnt[gcode]))
    lo, hi = np.nanquantile(dr, [0.05, 0.95])
    return {"WCwk": (point, lo, hi), "kept": kept}


def fmt(t, pct=True):
    if not t:
        return ""
    v, lo, hi = t
    f = 100 if pct else 1
    return f"{f*v:+.1f} ({f*lo:+.1f},{f*hi:+.1f})"


def roi_ci(x: pd.DataFrame):
    if len(x) == 0:
        return np.nan, np.nan, np.nan
    r, (lo, hi) = boot_ci(x.profit.values, x.gid.values, n=NBOOT)
    return 100 * r, 100 * lo, 100 * hi


# ─── the grid ──────────────────────────────────────────────────────────────

def frame_for(bets: pd.DataFrame, g: pd.DataFrame, src: str, T: float, seasons) -> pd.DataFrame:
    b = bets[bets.season.isin(seasons)]
    w = b[src]
    if src == "era5":
        envmask = b.env.isin(["outdoor"])
    else:
        envmask = b.env == "outdoor"
    grp = np.where(envmask & (w >= T), "W",
                   np.where(envmask & (w < CALM), "C",
                            np.where(b.env == "dome", "D", "")))
    f = b.assign(grp=grp)
    return f[f.grp != ""]


def grid_row(f: pd.DataFrame, nseas: int, label: dict) -> dict:
    W = f[f.grp == "W"]
    r = did_boot(f[["profit", "gid", "grp", "wk"]])
    roi, lo, hi = roi_ci(W)
    row = dict(label)
    row.update({
        "wind_games": W.gid.nunique(),
        "bets": len(W), "bets/szn": round(len(W) / nseas, 1),
        "units": round(W.profit.sum(), 1),
        "ROI%": round(roi, 1), "ci90": f"({lo:+.1f},{hi:+.1f})",
        "hit-fair": round(100 * (W.won - W.fair_side).mean(), 1) if len(W) else np.nan,
        "calm_ROI": round(100 * f[f.grp == "C"].profit.mean(), 1),
        "dome_ROI": round(100 * f[f.grp == "D"].profit.mean(), 1) if (f.grp == "D").any() else np.nan,
        "win%": round(100 * W.won.mean(), 1) if len(W) else np.nan,
        "W-C": fmt(r.get("WC")), "DiD": fmt(r.get("DiD")),
    })
    for s in sorted(f.season.unique()):
        Ws = W[W.season == s]
        row[f"{s}"] = f"{100*Ws.profit.mean():+.1f}/{len(Ws)}" if len(Ws) else "-"
    row["flag"] = "LOW-VOL" if len(W) / nseas <= LOWVOL else ""
    return row


def main():
    t0 = time.time()
    g = load_games()
    L, snaps, ndup = load_actuals()
    g["wk"] = g.season.astype(str) + "-" + g.week.astype(str).str.zfill(2)
    allb = {d: [] for d in DECISIONS}
    cov = []
    for m in MARKETS:
        res = decisions(m, g, L, snaps)
        for d, b in res.items():
            allb[d].append(b)
        b = res["latest"]
        cov.append({"market": SHORT[m], "graded(latest)": len(b), "void_dropped": int(b.n_void.iloc[0]),
                    "zero_filled": int(b.n_zero_fill.iloc[0]),
                    "med_lead_h_latest": round(b.lead_h.median(), 1),
                    "med_lead_h_T24": round(res["T24"].lead_h.median(), 1),
                    "med_lead_h_T48": round(res["T48"].lead_h.median(), 1),
                    "med_books": res["latest"].n_books.median()})
        print(f"  loaded {m} ({time.time()-t0:.0f}s)", file=sys.stderr)
    gcols = ["gid", "season", "week", "wk", "env", "obs", "fc_d1", "fc_d3", "era5"]
    B = {d: pd.concat(v, ignore_index=True).merge(g[gcols], on="gid", how="left")
         for d, v in allb.items()}
    for d in B:
        B[d]["late"] = B[d].week >= 10
        B[d]["mkt"] = B[d].market.map(SHORT)

    lat = B["latest"]
    main_ = lat[lat.season.isin(SEASONS)]
    print("=" * 100)
    print("NFL PROP x WIND  (python -m scripts.nfl_edge_prop_wind)")
    print("=" * 100)
    print(f"\n[0] COVERAGE  (2023-2026 rows; log name collisions dropped: {ndup})")
    print(pd.DataFrame(cov).to_string(index=False))
    print("\nbets per season x environment (latest decision, all 8 markets):")
    print(main_.groupby(["season", "env"]).size().unstack().to_string())

    # volume of windy games
    print("\n[1] WINDY GAMES PER SEASON (open-air games with the wind measure; calm = <10 mph)")
    gg = g[g.season.isin(SEASONS) & (g.env == "outdoor")]
    rows = []
    for src in ("obs", "fc_d1", "fc_d3", "era5"):
        for s in SEASONS:
            x = gg[gg.season == s][src]
            if x.notna().sum() == 0:
                continue
            r = {"src": src, "season": s, "open-air games w/ measure": int(x.notna().sum()),
                 "calm<10": int((x < CALM).sum())}
            for T in THRESHOLDS:
                r[f">={T}"] = int((x >= T).sum())
            rows.append(r)
    dg = g[g.season.isin(SEASONS) & (g.env == "dome")]
    for s in SEASONS:
        x = dg[dg.season == s].era5
        r = {"src": "era5 DOME", "season": s, "open-air games w/ measure": int(x.notna().sum()),
             "calm<10": int((x < CALM).sum())}
        for T in THRESHOLDS:
            r[f">={T}"] = int((x >= T).sum())
        rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))
    c = gg[["obs", "fc_d1", "fc_d3", "era5"]].corr().round(2)
    print("\ncorrelation of the wind measures across open-air games 2023-25:")
    print(c.to_string())

    # [2] price-free mechanism, per market, observed wind
    print("\n[2] MECHANISM, PRICE-FREE - observed nflverse wind, latest pre-kick line, 2023-25 pooled")
    print("    mean(actual-line) and mechanism-side hit rate minus no-vig fair probability (pp).")
    print("    side: under for passing/receiving, over for rushing. W = wind >= T, C = open-air <10 mph.")
    rows = []
    for m in MARKETS:
        x = main_[main_.market == m]
        o = x[x.env == "outdoor"]
        r = {"market": SHORT[m], "side": MARKETS[m][1]}
        for lab, sel in (("C", o[o.obs < CALM]), ("W12", o[o.obs >= 12]), ("W15", o[o.obs >= 15]),
                         ("dome", x[x.env == "dome"])):
            r[f"n_{lab}"] = len(sel)
            r[f"a-l_{lab}"] = round((sel.actual - sel.line).mean(), 2)
            r[f"hit-fair_{lab}"] = round(100 * (sel.won - sel.fair_side).mean(), 1)
        rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))

    # [3] main grid: groups, every source x decision x T
    print("\n[3] GRID - pooled groups (P = passing/receiving UNDERS, R = rushing OVERS).")
    print("    bets/ROI/CI are the WINDY cell at the best bettable price; W-C and DiD are ROI pp with 90% CI")
    print("    (cluster bootstrap by game, stratified). Season columns: ROI%/bets.")
    print("    obs: fit 2023-24, hold-out 2025 (NOT bettable: recorded at the game).")
    print("    fc_d1/fc_d3: fit 2024, hold-out 2025.  LOW-VOL = <= 40 windy bets per season.")
    plan = [("obs", "latest", SEASONS), ("obs", "T24", SEASONS),
            ("fc_d1", "latest", [2024, 2025]), ("fc_d1", "T24", [2024, 2025]),
            ("fc_d3", "latest", [2024, 2025]), ("fc_d3", "T24", [2024, 2025]),
            ("fc_d3", "T48", [2024, 2025])]
    grid = []
    for src, dec, seas in plan:
        bets = B[dec]
        for grp in ("P", "R"):
            bb = bets[bets.grp == grp]
            for T in THRESHOLDS:
                f = frame_for(bb, g, src, T, seas)
                grid.append(grid_row(f, len(seas), {"src": src, "dec": dec, "grp": grp, "T": T}))
    G = pd.DataFrame(grid)
    print(G.to_string(index=False))

    # [4] per-market neighbourhood at the bettable decision and observed wind
    print("\n[4] GRID - per market (one row per market x T). Strict low-volume cells live here.")
    for src, dec, seas in (("obs", "latest", SEASONS), ("fc_d1", "latest", [2024, 2025]),
                           ("fc_d3", "T24", [2024, 2025])):
        rows = []
        bets = B[dec]
        for m in MARKETS:
            bb = bets[bets.market == m]
            for T in THRESHOLDS:
                f = frame_for(bb, g, src, T, seas)
                rows.append(grid_row(f, len(seas), {"market": SHORT[m], "side": MARKETS[m][1], "T": T}))
        print(f"\n  source={src}  decision={dec}  seasons={seas}")
        print(pd.DataFrame(rows).to_string(index=False))

    # [5] fit-chosen and a-priori cells, then the hold-out read
    print("\n[5] SELECTION ON FIT SEASONS, THEN THE HOLD-OUT (2025) READ ONCE")
    sel = []
    for src in ("fc_d1", "fc_d3"):
        for dec in (("latest", "T24") if src == "fc_d1" else ("latest", "T24", "T48")):
            for grp in ("P", "R"):
                bb = B[dec][B[dec].grp == grp]
                for T in THRESHOLDS:
                    f = frame_for(bb, g, src, T, FIT_FC)
                    nW = (f.grp == "W").sum()
                    if nW == 0:
                        continue
                    wc = f[f.grp == "W"].profit.mean() - f[f.grp == "C"].profit.mean()
                    sel.append({"src": src, "dec": dec, "grp": grp, "T": T, "fit_W_bets": nW,
                                "fit_W_ROI": round(100 * f[f.grp == "W"].profit.mean(), 1),
                                "fit_W-C": round(100 * wc, 1)})
    S = pd.DataFrame(sel)
    elig = S[S.fit_W_bets >= 25].sort_values("fit_W-C", ascending=False)
    print("fit-season (2024) ranking of bettable cells, >= 25 windy bets (top 8):")
    print(elig.head(8).to_string(index=False))
    chosen = elig.iloc[0]
    cells = [("A PRIORI", "fc_d1", "latest", "P", 12),
             ("FIT-CHOSEN", chosen.src, chosen.dec, chosen.grp, int(chosen["T"]))]
    # obs mechanism threshold
    ob = []
    for T in THRESHOLDS:
        f = frame_for(lat[lat.grp == "P"], g, "obs", T, FIT_OBS)
        nW = (f.grp == "W").sum()
        ob.append({"T": T, "fit_W_bets": nW, "fit_W-C": 100 * (f[f.grp == "W"].profit.mean() - f[f.grp == "C"].profit.mean())})
    ob = pd.DataFrame(ob)
    tob = int(ob[ob.fit_W_bets >= 50].sort_values("fit_W-C", ascending=False).iloc[0]["T"])
    print("\nobs mechanism, fit 2023-24, group P latest:")
    print(ob.round(1).to_string(index=False))
    cells.append(("OBS-FIT", "obs", "latest", "P", tob))
    rows = []
    for name, src, dec, grp, T in cells:
        bb = B[dec][B[dec].grp == grp]
        fit = FIT_OBS if src == "obs" else FIT_FC
        for lab, seas in (("fit", fit), ("HOLD-OUT 2025", [HOLD])):
            f = frame_for(bb, g, src, T, seas)
            r = grid_row(f, len(seas), {"cell": name, "src": src, "dec": dec, "grp": grp, "T": T, "part": lab})
            rows.append({k: r[k] for k in ("cell", "src", "dec", "grp", "T", "part", "bets", "units", "ROI%",
                                            "ci90", "calm_ROI", "dome_ROI", "W-C", "DiD")})
    print("\n" + pd.DataFrame(rows).to_string(index=False))

    # [6] seasons and early/late for the key cells
    print("\n[6] EVERY SEASON, AND EARLY (wk 1-9) vs LATE (wk 10+), key cells")
    key = [("obs", "latest", "P", 12, SEASONS), ("obs", "latest", "P", 15, SEASONS),
           ("fc_d1", "latest", "P", 12, [2024, 2025]), ("fc_d1", "latest", "P", 15, [2024, 2025]),
           (chosen.src, chosen.dec, chosen.grp, int(chosen["T"]), [2024, 2025])]
    rows = []
    for src, dec, grp, T, seas in key:
        bb = B[dec][B[dec].grp == grp]
        f = frame_for(bb, g, src, T, seas)
        for part, ff in [(str(s), f[f.season == s]) for s in seas] + \
                        [("early", f[~f.late]), ("late", f[f.late])]:
            W = ff[ff.grp == "W"]
            roi, lo, hi = roi_ci(W)
            r = did_boot(ff[["profit", "gid", "grp", "wk"]], n=1000)
            rows.append({"src": src, "dec": dec, "grp": grp, "T": T, "part": part,
                         "W_games": W.gid.nunique(), "W_bets": len(W),
                         "W_ROI": f"{roi:+.1f} ({lo:+.1f},{hi:+.1f})" if len(W) else "-",
                         "C_ROI": round(100 * ff[ff.grp == "C"].profit.mean(), 1),
                         "D_ROI": round(100 * ff[ff.grp == "D"].profit.mean(), 1),
                         "W-C": fmt(r.get("WC"))})
    print(pd.DataFrame(rows).to_string(index=False))

    # [7] placebo 1: ERA5 ambient wind, open-air vs dome
    print("\n[7] PLACEBO 1 - ERA5 ambient wind at the stadium. Domes must show NOTHING.")
    print("    latest decision, 2023-25. W = era5 >= T, C = era5 < 10, within the stated roof type.")
    rows = []
    for grp in ("P", "R"):
        bb = lat[(lat.grp == grp) & lat.season.isin(SEASONS)]
        for env in ("outdoor", "dome"):
            for T in THRESHOLDS:
                x = bb[bb.env == env]
                w = x.era5
                f = x.assign(grp=np.where(w >= T, "W", np.where(w < CALM, "C", "")))
                f = f[f.grp != ""]
                r = did_boot(f[["profit", "gid", "grp", "wk"]], n=1000)
                W = f[f.grp == "W"]
                rows.append({"grp": grp, "roof": env, "T": T, "W_games": W.gid.nunique(), "W_bets": len(W),
                             "W_ROI": round(100 * W.profit.mean(), 1) if len(W) else np.nan,
                             "C_ROI": round(100 * f[f.grp == "C"].profit.mean(), 1),
                             "W-C": fmt(r.get("WC"))})
    print(pd.DataFrame(rows).to_string(index=False))

    # [6b] QB passing yards only - the low-volume cells, every season and early/late
    print()
    print("[6b] QB PASSING YARDS UNDER ONLY (2 bets per windy game) - every season, early vs late")
    rows = []
    for src, dec, T, seas in (("obs", "latest", 15, SEASONS), ("obs", "latest", 18, SEASONS),
                              ("fc_d1", "latest", 15, [2024, 2025]), ("fc_d3", "T24", 15, [2024, 2025]),
                              ("fc_d3", "T48", 15, [2024, 2025])):
        bb = B[dec][B[dec].market == "player_pass_yds"]
        f = frame_for(bb, g, src, T, seas)
        for part, ff in [(str(s_), f[f.season == s_]) for s_ in seas] + [("early", f[~f.late]), ("late", f[f.late])]:
            W = ff[ff.grp == "W"]
            roi, lo, hi = roi_ci(W)
            rows.append({"src": src, "dec": dec, "T": T, "part": part, "W_games": W.gid.nunique(),
                         "W_bets": len(W), "win%": round(100 * W.won.mean(), 1) if len(W) else np.nan,
                         "units": round(W.profit.sum(), 1),
                         "W_ROI": f"{roi:+.1f} ({lo:+.1f},{hi:+.1f})" if len(W) else "-",
                         "mean(actual-line)": round((W.actual - W.line).mean(), 1) if len(W) else np.nan,
                         "C_ROI": round(100 * ff[ff.grp == "C"].profit.mean(), 1)})
    print(pd.DataFrame(rows).to_string(index=False))

    # [6c] concentration: every game in the forecast >= 15 mph cell
    print()
    print("[6c] EVERY GAME IN THE fc_d1 >= 15 mph CELL (latest decision): group P and QB pass yds only")
    f = B["latest"]
    f = f[(f.env == "outdoor") & (f.fc_d1 >= 15) & f.season.isin([2024, 2025])]
    per = f.groupby("gid").agg(season=("season", "first"), week=("week", "first"),
                               fc_d1=("fc_d1", "first"), obs=("obs", "first"))
    pg = f[f.grp == "P"].groupby("gid").profit.agg(P_bets="count", P_units="sum")
    py = f[f.market == "player_pass_yds"].groupby("gid").profit.agg(qb_bets="count", qb_units="sum")
    per = per.join(pg).join(py).sort_values(["season", "week"])
    per["P_ROI%"] = (100 * per.P_units / per.P_bets).round(1)
    print(per.round(2).to_string())
    u = per.P_units.dropna().sort_values(ascending=False)
    print(f"    games {len(per)}, P units positive in {int((per.P_units > 0).sum())}; "
          f"top-3 games carry {u.head(3).sum():.1f} of {u.sum():.1f} units; "
          f"ROI without the top 3 games: {100 * (u.iloc[3:].sum()) / per.P_bets[u.index[3:]].sum():+.1f}%")

    # [7b] calendar-matched W - C, open-air cells and the dome placebo side by side
    print()
    print("[7b] CALENDAR-MATCHED W - C (same season-week only; added after the first run, see docstring)")
    print("     latest decision. 'kept' = share of windy bets whose week also has a calm game.")
    rows = []
    specs = []
    for T in (12, 15, 18):
        specs += [("P", "obs", "outdoor", T, SEASONS), ("P", "fc_d1", "outdoor", T, [2024, 2025]),
                  ("P", "era5", "outdoor", T, SEASONS), ("P", "era5", "dome", T, SEASONS)]
    for T in (12, 15):
        specs += [("pass_yds", "obs", "outdoor", T, SEASONS), ("pass_yds", "fc_d1", "outdoor", T, [2024, 2025]),
                  ("pass_yds", "era5", "outdoor", T, SEASONS), ("pass_yds", "era5", "dome", T, SEASONS)]
    for who, src, env, T, seas in specs:
        bb = lat[lat.season.isin(seas) & (lat.env == env)]
        bb = bb[bb.grp == "P"] if who == "P" else bb[bb.mkt == who]
        w = bb[src]
        f = bb.assign(grp=np.where(w >= T, "W", np.where(w < CALM, "C", "")))
        f = f[f.grp != ""]
        r = week_matched(f[["profit", "gid", "grp", "wk"]])
        W = f[f.grp == "W"]
        rows.append({"bets": who, "src": src, "roof": env, "T": T, "W_games": W.gid.nunique(), "W_bets": len(W),
                     "raw W-C": round(100 * (W.profit.mean() - f[f.grp == "C"].profit.mean()), 1),
                     "week-matched W-C (90% CI)": fmt(r.get("WCwk")),
                     "kept": round(r.get("kept", np.nan), 2)})
    print(pd.DataFrame(rows).to_string(index=False))

    # [8] placebo 2: within-week permutation of observed wind
    print("\n[8] PLACEBO 2 - observed wind shuffled across open-air games within season-week, 1000 perms")
    rng = np.random.default_rng(3)
    rows = []
    for grp, T in (("P", 12), ("P", 15), ("R", 12), ("R", 15)):
        bb = lat[(lat.grp == grp) & lat.season.isin(SEASONS) & (lat.env == "outdoor") & lat.obs.notna()]
        gw = bb.drop_duplicates("gid")[["gid", "wk", "obs"]].reset_index(drop=True)
        gsum = bb.groupby("gid").profit.agg(["sum", "count"])
        gw = gw.join(gsum, on="gid")

        def wc(wind):
            Wm, Cm = wind >= T, wind < CALM
            return gw["sum"][Wm].sum() / gw["count"][Wm].sum() - gw["sum"][Cm].sum() / gw["count"][Cm].sum()

        obs_v = wc(gw.obs.values)
        perm = []
        wk_idx = [np.flatnonzero(gw.wk.values == k) for k in gw.wk.unique()]
        for _ in range(1000):
            wnd = gw.obs.values.copy()
            for ix in wk_idx:
                wnd[ix] = wnd[rng.permutation(ix)]
            perm.append(wc(wnd))
        perm = np.array(perm)
        rows.append({"grp": grp, "T": T, "observed W-C pp": round(100 * obs_v, 1),
                     "perm mean": round(100 * perm.mean(), 1),
                     "perm 5%": round(100 * np.quantile(perm, .05), 1),
                     "perm 95%": round(100 * np.quantile(perm, .95), 1),
                     "one-sided p": round((perm >= obs_v).mean(), 3)})
    print(pd.DataFrame(rows).to_string(index=False))

    # [9] do books move prop lines for wind?
    print("\n[9] LINE MOVEMENT - consensus line at the latest pre-kick snapshot minus at T-48h, same proposition.")
    print("    Negative = line moved DOWN. W/C by observed wind (and fc_d1 for 2024-25).")
    m48 = B["T48"][["gid", "key", "market", "line"]].rename(columns={"line": "line48"})
    mv = lat.merge(m48, on=["gid", "key", "market"])
    mv["move"] = mv.line - mv.line48
    mv = mv[mv.season.isin(SEASONS)]
    rows = []
    for m in MARKETS:
        x = mv[mv.market == m]
        o = x[x.env == "outdoor"]
        r = {"market": SHORT[m], "n": len(x)}
        for lab, sel in (("calm", o[o.obs < CALM]), ("obs>=12", o[o.obs >= 12]), ("obs>=15", o[o.obs >= 15]),
                         ("dome", x[x.env == "dome"]), ("fc1>=12", o[o.fc_d1 >= 12]),
                         ("fc1_calm", o[o.fc_d1 < CALM])):
            r[lab] = round(sel.move.mean(), 2)
        Wd = o[o.obs >= 12].assign(grp="W", profit=lambda d: d.move)
        Cd = o[o.obs < CALM].assign(grp="C", profit=lambda d: d.move)
        rr = did_boot(pd.concat([Wd, Cd])[["profit", "gid", "grp", "wk"]], n=1000)
        r["W12-C (90% CI)"] = fmt(rr.get("WC"), pct=False)
        rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"    props with both snapshots: {len(mv)}; median lead at the two ends: "
          f"{lat.lead_h.median():.1f}h vs {B['T48'].lead_h.median():.1f}h")

    # [10] 2026 week 1 appendix
    print("\n[10] APPENDIX - 2026 Week 1 (16 games in the prop cache, quotes ~3-4 days out; observed wind)")
    a = lat[(lat.season == 2026)]
    if len(a):
        print(f"    graded props {len(a)}, median lead {a.lead_h.median():.0f}h, games {a.gid.nunique()}")
        for grp in ("P", "R"):
            x = a[a.grp == grp]
            o = x[x.env == "outdoor"]
            for lab, sel in (("obs>=12", o[o.obs >= 12]), ("calm<10", o[o.obs < CALM]), ("dome", x[x.env == "dome"])):
                print(f"    {grp} {lab:8s} games {sel.gid.nunique():3d} bets {len(sel):4d} "
                      f"ROI {100*sel.profit.mean():+.1f}%" if len(sel) else f"    {grp} {lab:8s} none")
    print(f"\n(done in {time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()

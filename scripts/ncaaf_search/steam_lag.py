"""
Steam lag: Pinnacle moved between two stored snapshots and DraftKings' line
had not — bet DraftKings' stale number the way Pinnacle went.

Session 252 (2026-09-08, Matt: "surprising you cannot find edge. go harder").
PR #581 compared Pinnacle's de-vigged number with DraftKings' AT THE SAME
INSTANT and found NCAAF negative on h2h and spreads, flat on totals. This is
a different shape: not "DK sits off Pinnacle" but "Pinnacle MOVED and DK has
not caught up yet", which is the bettable event a line-shopper actually sees.
The 13-book backfill carries it by construction: every row's `snapshot_at`
is that book's own last_update, so at a pull a Pinnacle row stamped 22:50
beside a DK row stamped 20:00 is a lag.

DEFINITIONS (fixed before any number)
- Pulls: the 14:00Z and 23:00Z pull instants in `odds_history_pulls` for
  NCAAF (324 dates, 2023-08-24 .. 2025-12-06). A book's line AS OF a pull is
  its latest row with snapshot_at <= the pull instant; pre-game rows only
  (snapshot_at < commence_time). The line's own snapshot_at is its age.
- Event (k in 0.5, 1.0, 1.5 points): between consecutive pulls T1 < T2, both
  before kickoff, Pinnacle's line moved by >= k, AND DraftKings' moved by
  < k/2 over the same interval, AND DK's line at T2 is older than Pinnacle's
  (a lag, not a disagreement). One event per (game, market, T2, k).
- Bet: DK's line at T2, on the side Pinnacle moved toward. Totals: up ->
  over. Spreads: `spread_home` down (home more favoured at Pinnacle) -> home.
- Grade: at that DK line, from the final score; pushes excluded.
  Home covers iff (home - away) + spread_home > 0 (scored_line is the HOME
  number, CLAUDE.md section 4). Over wins iff actual > line.
- CLV: DK's last pre-kick line minus DK's T2 line, signed toward the bet, in
  points. Positive = DK later moved the way Pinnacle had.
- CONTROL "followed": same Pinnacle move, but DK ALSO moved >= k/2 the same
  way by T2 — graded at DK's moved line. Separates "lag" from "follow steam",
  which line_move_spots.py already found null at the close.
- Join to scores: odds ids are ET-dated; scores may sit on a UTC-dated alias
  row. Matched on (season, home, away) with game_date within one day.
- Per season, Wilson 95% vs 0.5238, time split (first/second half of each
  season by kickoff date), and the k-neighbourhood, not a peak.

POWER, stated up front: two pulls a day see only the moves that straddle a
pull, so events are hundreds, not thousands. A CI on 300 bets is ~ +/-5.6pp.

WHAT THIS CANNOT MEASURE: how long DK stays stale in production. Two pulls a
day cannot see a lag window; a rule that survives here still needs the live
feed to say the window is real before it is shipped.

    python scripts/ncaaf_search/steam_lag.py
"""
from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BREAKEVEN = 0.5238
KS = (0.5, 1.0, 1.5)
SEASONS = (2023, 2024, 2025)


def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    ph = w / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


# ---------------------------------------------------------------------- load
def load(conn):
    pulls = conn.execute("""
        SELECT snapshot_date, hour_utc FROM odds_history_pulls
        WHERE sport = 'NCAAF' ORDER BY 1, 2""").fetchall()
    pulls = sorted({pd.Timestamp(f"{d}T{h:02d}:00:00Z") for d, h in pulls})
    ph = ",".join(["%s"] * len(SEASONS))
    odds = conn.execute(f"""
        SELECT o.game_id, g.season, g.home_team, g.away_team, g.game_date,
               g.commence_time::timestamptz, o.bookmaker, o.market,
               o.snapshot_at::timestamptz, o.spread_home, o.total_line
        FROM odds o JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'NCAAF' AND g.season IN ({ph})
          AND o.source = 'odds_api_historical'
          AND o.bookmaker IN ('pinnacle', 'draftkings')
          AND o.market IN ('spreads', 'totals')
          AND COALESCE(o.snapshot_type, 'open') <> 'in_play'
          AND o.snapshot_at::timestamptz < g.commence_time::timestamptz
    """, SEASONS).fetchall()
    odds = pd.DataFrame(odds, columns=["game_id", "season", "home_team", "away_team",
                                       "game_date", "commence_time", "bookmaker",
                                       "market", "snapshot_at", "spread_home", "total_line"])
    odds["snapshot_at"] = pd.to_datetime(odds["snapshot_at"], utc=True)
    odds["commence_time"] = pd.to_datetime(odds["commence_time"], utc=True)
    odds["line"] = np.where(odds["market"] == "spreads",
                            odds["spread_home"].astype(float),
                            odds["total_line"].astype(float))
    odds = odds.dropna(subset=["line"])
    scores = conn.execute(f"""
        SELECT season, home_team, away_team, game_date, home_score, away_score
        FROM games WHERE sport = 'NCAAF' AND season IN ({ph})
          AND home_score IS NOT NULL""", SEASONS).fetchall()
    scores = pd.DataFrame(scores, columns=["season", "home_team", "away_team",
                                           "game_date", "hs", "as"])
    return pulls, odds, scores


def attach_scores(games: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    cand = games.merge(scores, on=["season", "home_team", "away_team"], how="left",
                       suffixes=("", "_s"))
    cand["_dd"] = (pd.to_datetime(cand["game_date_s"]) - pd.to_datetime(cand["game_date"])).dt.days.abs()
    cand = cand[cand["_dd"].le(1)]
    cand = cand.sort_values("_dd").drop_duplicates("game_id", keep="first")
    return cand[["game_id", "hs", "as"]]


# ------------------------------------------------------------------- lines
def lines_at_pulls(odds: pd.DataFrame, pulls: list[pd.Timestamp]) -> pd.DataFrame:
    """One row per (game, market, book, pull): the line as of the pull and
    its age (the row's own snapshot_at)."""
    out = []
    pulls_arr = np.array([p.value for p in pulls], dtype="int64")
    for (gid, mkt, book), grp in odds.groupby(["game_id", "market", "bookmaker"]):
        grp = grp.sort_values("snapshot_at")
        snaps = grp["snapshot_at"].values.astype("datetime64[ns]").astype("int64")
        lines = grp["line"].values
        kick = grp["commence_time"].iloc[0].value
        # pulls strictly before kickoff and at/after the first stored row
        sel = pulls_arr[(pulls_arr < kick) & (pulls_arr >= snaps[0])]
        if len(sel) == 0:
            continue
        idx = np.searchsorted(snaps, sel, side="right") - 1
        for p, i in zip(sel, idx):
            out.append((gid, mkt, book, p, lines[i], snaps[i]))
    t = pd.DataFrame(out, columns=["game_id", "market", "bookmaker", "pull", "line", "age"])
    return t


def build_events(lines: pd.DataFrame) -> pd.DataFrame:
    wide = lines.pivot_table(index=["game_id", "market", "pull"], columns="bookmaker",
                             values=["line", "age"], aggfunc="first")
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.dropna(subset=["line_pinnacle", "line_draftkings"]).reset_index()
    wide = wide.sort_values(["game_id", "market", "pull"])
    g = wide.groupby(["game_id", "market"])
    wide["pin_prev"] = g["line_pinnacle"].shift(1)
    wide["dk_prev"] = g["line_draftkings"].shift(1)
    wide["pull_prev"] = g["pull"].shift(1)
    ev = wide.dropna(subset=["pin_prev", "dk_prev"]).copy()
    ev["pin_move"] = ev["line_pinnacle"] - ev["pin_prev"]
    ev["dk_move"] = ev["line_draftkings"] - ev["dk_prev"]
    ev["dk_stale"] = ev["age_draftkings"] < ev["age_pinnacle"]
    return ev


def grade(ev: pd.DataFrame, closes: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    ev = ev.merge(closes, on=["game_id", "market"], how="left")
    ev = ev.merge(scores, on="game_id", how="inner")
    ev["dir"] = np.sign(ev["pin_move"])                    # +1 up, -1 down
    # bet side: totals up -> over (+1); spreads home number down -> home (+1)
    ev["side"] = np.where(ev["market"] == "totals", ev["dir"], -ev["dir"])
    line = ev["line_draftkings"]
    tot = ev["hs"] + ev["as"]
    marg = ev["hs"] - ev["as"]
    res_tot = np.sign(tot - line)                           # +1 over, -1 under, 0 push
    res_spr = np.sign(marg + line)                          # +1 home covers
    ev["res"] = np.where(ev["market"] == "totals", res_tot, res_spr)
    ev["win"] = (ev["res"] == ev["side"]).astype(int)
    ev["push"] = (ev["res"] == 0).astype(int)
    # CLV: DK close minus DK T2 line, signed toward the bet
    clv_tot = (ev["dk_close"] - line) * ev["side"]
    clv_spr = (line - ev["dk_close"]) * ev["side"]          # home wants spread_home to fall
    ev["clv"] = np.where(ev["market"] == "totals", clv_tot, clv_spr)
    return ev


def summarise(sub: pd.DataFrame) -> dict:
    dec = sub[sub["push"] == 0]
    n = len(dec); w = int(dec["win"].sum())
    lo, hi = wilson(w, n)
    return dict(n=n, w=w, wr=(w / n) if n else float("nan"), lo=lo, hi=hi,
                clv=float(sub["clv"].mean()) if len(sub) else float("nan"))


def fmt(d: dict) -> str:
    if not d["n"]:
        return f"{0:5d}   n/a"
    flag = " +" if d["lo"] > BREAKEVEN else ("  " if d["hi"] > BREAKEVEN else " -")
    return f"{d['n']:5d} {d['wr']:.3f} [{d['lo']:.3f},{d['hi']:.3f}]{flag} clv {d['clv']:+.2f}"


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from data.db import get_connection

    conn = get_connection()
    try:
        pulls, odds, scores = load(conn)
    finally:
        conn.close()
    print(f"pulls {len(pulls)}, odds rows {len(odds)}, games {odds['game_id'].nunique()}")

    games = odds[["game_id", "season", "home_team", "away_team", "game_date"]].drop_duplicates("game_id")
    sc = attach_scores(games, scores)
    print(f"games with a score: {len(sc)} of {len(games)}")

    lines = lines_at_pulls(odds, pulls)
    closes = (odds[odds["bookmaker"] == "draftkings"].sort_values("snapshot_at")
              .groupby(["game_id", "market"])["line"].last().rename("dk_close").reset_index())
    ev = build_events(lines)
    ev = grade(ev, closes, sc)
    ev = ev.merge(games[["game_id", "season", "game_date"]], on="game_id")
    print(f"consecutive-pull pairs with both books priced: {len(ev)}")

    # time split marker
    mids = {}
    for s in SEASONS:
        ds = sorted(ev.loc[ev["season"] == s, "game_date"].unique())
        if ds:
            mids[s] = ds[len(ds) // 2]
    ev["half"] = np.where(ev["game_date"] < ev["season"].map(mids), "early", "late")

    for mkt in ("totals", "spreads"):
        m = ev[ev["market"] == mkt]
        print(f"\n=== {mkt.upper()} — Pinnacle moved >= k, DK moved < k/2 and DK's line is OLDER than Pinnacle's (LAG) ===")
        print(f"{'k':>4} {'bets':>5} {'win%':>5} {'Wilson 95%':>15}   clv(pts) | control: DK FOLLOWED (moved >= k/2 same way)")
        for k in KS:
            moved = m[m["pin_move"].abs() >= k]
            lag = moved[(moved["dk_move"].abs() < k / 2) & moved["dk_stale"]]
            followed = moved[(np.sign(moved["dk_move"]) == np.sign(moved["pin_move"])) & (moved["dk_move"].abs() >= k / 2)]
            print(f"{k:>4} " + fmt(summarise(lag)) + "   | " + fmt(summarise(followed)))
            for s in SEASONS:
                print(f"{'':>4}   {s}  " + fmt(summarise(lag[lag['season'] == s])))
            for h in ("early", "late"):
                print(f"{'':>4}   {h:<5} " + fmt(summarise(lag[lag['half'] == h])))
        # direction split at k=1
        lag1 = m[(m["pin_move"].abs() >= 1.0) & (m["dk_move"].abs() < 0.5) & m["dk_stale"]]
        for name, sub in (("bet over / home", lag1[lag1["side"] > 0]), ("bet under / away", lag1[lag1["side"] < 0])):
            print(f"{'':>4}   k=1 {name:<17} " + fmt(summarise(sub)))
        # how often DK later moved toward Pinnacle at all (the lag closed)
        if len(lag1):
            print(f"{'':>4}   k=1 lag events where DK's close moved toward Pinnacle: "
                  f"{100 * (lag1['clv'] > 0).mean():.0f}%  (away: {100 * (lag1['clv'] < 0).mean():.0f}%)")


if __name__ == "__main__":
    main()

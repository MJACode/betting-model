"""Build the NCAAB spread model's frozen numbers (models/ncaab_spread_market.py)
and replay its card walk-forward.

Writes models/saved/ncaab_spread_market_<season>.json: the eight books, the
check hour and window, the cut and the minimum of other books, the mean offset
c per phase, and the final-margin table (models/ncaab_margin_dist.py) fitted on
2012 through the last finished season. It then REPLAYS the card's own decision
path (models.ncaab_book_quotes.snapshot -> models.ncaab_spread_market.decide)
on every 2021..last season at the 15:00 UTC instant of each game, with the
margin table fitted on the seasons before each one, grades every bet, and
prints bets, units and ROI by season with and without the three-other-books
minimum.

    python -m scripts.ncaab_spread_market_build --cache DIR [--last-season 2026]
        [--out PATH] [--check-tables PKL] [--check-bets CSV] [--bets-out PATH]

DIR is a read-only copy of three Supabase reads, as parquet:
  games.parquet                SELECT game_id, season, game_date, commence_time, home_score,
                               away_score FROM games WHERE sport = 'NCAAB'
  ncaab_archive_lines.parquet  SELECT row_key, source, game_id, flipped, open_spread_home,
                               close_spread_home, systems::text AS systems
                               FROM ncaab_archive_lines
  odds_parts/*.parquet         SELECT game_id, market, bookmaker, snapshot_at, home_price,
                               away_price, spread_home FROM odds WHERE game_id = ANY(<the
                               2021-2026 NCAAB games, 300 at a time>) AND market = 'spreads'
                               AND snapshot_type IS DISTINCT FROM 'in_play'
                               (more columns and markets may be present; the parts are
                               read in name order, and that order breaks a tie between
                               two rows of one book with the same stamp)
Every row is in Supabase; the copy only saves re-reading 1.2M odds rows. The
2026-11-02 build read the copy taken for the research (scratch
ncaab_model/cache, 2026-10-26 to 10-30).

--check-tables compares the walk-forward margin tables with a pickle of the
research's ({season: {"pmf", "ge"}}); --check-bets compares the replayed bets,
game by game, with the research's (game_id, side 1/2, line, price,
bookmaker). Reads nothing else and writes only the JSON (and --bets-out).
"""
from __future__ import annotations

import argparse
import glob
import json
import pickle
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.ncaab_book_quotes as bq  # noqa: E402
import models.ncaab_margin_dist as md  # noqa: E402
import models.ncaab_spread_market as sm  # noqa: E402

TABLE_FIRST = 2012           # the margin table trains from here
C_SEASONS = (2012, 2020)     # c: the archive seasons, never refit
PAID_FIRST = 2021            # the first season with bought sportsbook spreads
CUT = 0.03
BOOTSTRAP = 2000


# ── loading ──────────────────────────────────────────────────────────────────

def load_games(cache: Path) -> pd.DataFrame:
    g = pd.read_parquet(cache / "games.parquet",
                        columns=["game_id", "season", "game_date", "commence_time",
                                 "home_score", "away_score"])
    g["game_date"] = g["game_date"].astype(str).str[:10]
    g["tip"] = pd.to_datetime(g["commence_time"], utc=True, format="mixed")
    return g


def load_spread_rows(cache: Path, game_ids: set) -> pd.DataFrame:
    parts = []
    files = sorted(glob.glob(str(cache / "odds_parts" / "*.parquet")))
    if not files:
        raise SystemExit(f"{cache}/odds_parts/*.parquet: no odds parts")
    for f in files:
        d = pd.read_parquet(f, columns=["game_id", "market", "bookmaker", "snapshot_at",
                                        "home_price", "away_price", "spread_home"])
        d = d[(d["market"] == "spreads") & d["bookmaker"].isin(bq.BOOKS) & d["game_id"].isin(game_ids)]
        parts.append(d.drop(columns="market"))
    o = pd.concat(parts, ignore_index=True)
    o["order"] = np.arange(len(o), dtype="int64")      # file order breaks a same-stamp tie
    o["ts"] = pd.to_datetime(o["snapshot_at"], utc=True, format="mixed")
    o = o.rename(columns={"spread_home": "line", "home_price": "p1", "away_price": "p2"})
    for c in ("line", "p1", "p2"):
        o[c] = pd.to_numeric(o[c], errors="coerce").astype(float)
    return o.drop(columns="snapshot_at")


def archive_lines(cache: Path) -> pd.DataFrame:
    """Per ESPN game: the Prediction Tracker opener and close and SBRO's
    close, in ESPN's orientation (the home number), each dropped where it
    disagrees with Prediction Tracker's own systems average by more than 10
    points (0.0 placeholders and sign flips); the opener also when it is a
    decimal-shifted value. The research's build_lines.archive_lines, unchanged."""
    a = pd.read_parquet(cache / "ncaab_archive_lines.parquet",
                        columns=["source", "game_id", "flipped", "open_spread_home",
                                 "close_spread_home", "systems"])
    a = a[a["game_id"].notna()].copy()
    sgn = np.where(a["flipped"] == True, -1.0, 1.0)  # noqa: E712
    for col in ("open_spread_home", "close_spread_home"):
        a[col] = a[col].astype(float) * sgn
    sysd = a["systems"].map(lambda s: json.loads(s) if isinstance(s, str) else {})
    a["sys_lineavg"] = sysd.map(lambda d: d.get("lineavg")).astype(float) * sgn
    pt = a[a["source"] == "prediction_tracker"].drop_duplicates("game_id")
    sb = a[a["source"] == "sbro"].drop_duplicates("game_id")
    pt = pt.rename(columns={"open_spread_home": "pt_open", "close_spread_home": "pt_close"})
    bad_open = (((pt["pt_open"] + pt["sys_lineavg"]).abs() > 10)
                | ((pt["pt_open"].abs() < 1) & (pt["sys_lineavg"].abs() > 5)))
    pt.loc[bad_open, "pt_open"] = np.nan
    pt = pt[["game_id", "pt_open", "pt_close", "sys_lineavg"]]
    sb = sb.rename(columns={"close_spread_home": "sb_close"})[["game_id", "sb_close"]]
    out = pt.merge(sb, on="game_id", how="outer")
    for col in ("pt_close", "sb_close"):
        bad = (out[col] + out["sys_lineavg"]).abs() > 10
        out.loc[bad, col] = np.nan
    return out[["game_id", "pt_open", "pt_close", "sb_close"]]


def close_consensus(rows: pd.DataFrame, games: pd.DataFrame) -> pd.Series:
    """Per game, the median over the bettable books of each book's last
    pre-tip spread (the research's spreads_c_cons)."""
    o = rows[["game_id", "bookmaker", "ts", "line", "order"]].merge(
        games[["game_id", "tip"]], on="game_id", how="inner")
    o = o[(o["ts"] <= o["tip"]) & o["line"].notna()]
    o = o.sort_values(["game_id", "bookmaker", "ts", "order"], kind="mergesort")
    last = o.drop_duplicates(["game_id", "bookmaker"], keep="last")
    return last.groupby("game_id")["line"].median()


def history(games: pd.DataFrame, arch: pd.DataFrame, close_cons: pd.Series, last: int) -> pd.DataFrame:
    """Every scored game through `last`, ordered by date then game id, with its
    margin, phase, the archive lines and the line its mean is read from."""
    h = games[games["home_score"].notna() & (games["season"] <= last)].copy()
    h["margin"] = h["home_score"].astype(float) - h["away_score"].astype(float)
    h = h.sort_values(["game_date", "game_id"], kind="mergesort").reset_index(drop=True)
    h = h.merge(arch, on="game_id", how="left")
    h["cons_close"] = h["game_id"].map(close_cons)
    h["phase"] = [sm.phase_of(d) for d in h["game_date"]]
    h["mu_close"] = np.where(h["season"] <= C_SEASONS[1], -(h["sb_close"].fillna(h["pt_close"])),
                             -h["cons_close"])
    return h


def c_by_phase(h: pd.DataFrame) -> tuple[dict, dict]:
    tr = h[(h["season"] >= C_SEASONS[0]) & (h["season"] <= C_SEASONS[1])].dropna(subset=["margin", "pt_open"])
    x = tr["margin"] + tr["pt_open"]
    return ({k: float(v) for k, v in x.groupby(tr["phase"]).mean().items()},
            {k: int(v) for k, v in x.groupby(tr["phase"]).size().items()})


def table_for(h: pd.DataFrame, season: int) -> tuple[dict, int]:
    tr = h[(h["season"] >= TABLE_FIRST) & (h["season"] < season) & h["mu_close"].notna()
           & h["margin"].notna()]
    return md.fit(tr["margin"].values, tr["mu_close"].values), int(len(tr))


# ── the replay ───────────────────────────────────────────────────────────────

def replay_season(rows: pd.DataFrame, games: pd.DataFrame, c: dict, table: dict,
                  cut: float) -> list[sm.Decision]:
    """The card's decision path over one season's games at their 15:00 UTC
    instants: snapshot, then decide."""
    g = games.copy()
    g["instant"] = [pd.Timestamp(bq.check_instant(d)) for d in g["game_date"]]
    r = rows.merge(g[["game_id", "instant", "tip"]], on="game_id", how="inner")
    snap = sm.snapshot_for(r, dict(zip(g["game_id"], g["game_date"])))
    return sm.decide(list(g["game_id"]), snap, c, table, cut)


def grade(b: pd.DataFrame) -> pd.DataFrame:
    b = b.copy()
    dd = sm.dec(b["price"])
    res = np.where(b["side"] == 1, b["margin"] + b["line"], -(b["margin"] + b["line"]))
    b["risk"] = np.minimum(1 / (dd - 1), 3.0)
    b["units"] = np.select([res > 0, res < 0], [b["risk"] * (dd - 1), -b["risk"]], 0.0)
    b["result"] = np.select([res > 0, res < 0], ["W", "L"], "P")
    return b


def summarize(b: pd.DataFrame) -> dict:
    if not len(b):
        return {"bets": 0}
    rng = np.random.default_rng(7)
    dd = b.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    j = rng.integers(0, len(dd), size=(BOOTSTRAP, len(dd)))
    lo, hi = np.percentile(dd["u"].values[j].sum(1) / dd["r"].values[j].sum(1) * 100, [2.5, 97.5])
    return {"bets": int(len(b)),
            "record": f"{int((b.result == 'W').sum())}-{int((b.result == 'L').sum())}-"
                      f"{int((b.result == 'P').sum())}",
            "units": round(float(b["units"].sum()), 2),
            "roi_pct": round(float(b["units"].sum() / b["risk"].sum() * 100), 2),
            "ci95_dates": [round(float(lo), 1), round(float(hi), 1)],
            "price_min": float(b["price"].min()), "price_max": float(b["price"].max()),
            "price_median": float(b["price"].median())}


def table_rows(bets: pd.DataFrame, last: int) -> dict:
    out = {}
    for name, x in (("without the 3-other-books minimum", bets),
                    ("live: 3+ other books", bets[bets["status"] == "bets"])):
        per = {str(s): summarize(x[x["season"] == s]) for s in sorted(x["season"].unique())}
        per[f"{PAID_FIRST}-{last - 1}"] = summarize(x[x["season"] <= last - 1])
        per[str(last)] = summarize(x[x["season"] == last])
        out[name] = per
    return out


def check_tables(tables: dict, path: Path) -> dict:
    ref = pickle.load(open(path, "rb"))
    out = {}
    for s, t in tables.items():
        if s in ref:
            out[int(s)] = {"pmf": float(np.abs(t["pmf"] - ref[s]["pmf"]).max()),
                           "ge": float(np.abs(t["ge"] - ref[s]["ge"]).max())}
    return out


def check_bets(bets: pd.DataFrame, path: Path) -> dict:
    r = pd.read_csv(path)
    m = bets.merge(r[["game_id", "side", "line", "price", "bookmaker"]], on="game_id", how="outer",
                   suffixes=("", "_res"), indicator=True)
    both = m[m["_merge"] == "both"]
    same = both[(both["side"] == both["side_res"]) & np.isclose(both["line"], both["line_res"])
                & np.isclose(both["price"], both["price_res"])]
    return {"replay_bets": int(len(bets)), "research_bets": int(len(r)),
            "both": int(len(both)), "replay_only": m.loc[m["_merge"] == "left_only", "game_id"].tolist()[:20],
            "research_only": m.loc[m["_merge"] == "right_only", "game_id"].tolist()[:20],
            "same_game_side_line_price": int(len(same)),
            "same_book_too": int((same["bookmaker"] == same["bookmaker_res"]).sum()),
            "other_book_same_line_price": int((same["bookmaker"] != same["bookmaker_res"]).sum())}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--last-season", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--check-tables", type=Path, default=None)
    ap.add_argument("--check-bets", type=Path, default=None)
    ap.add_argument("--bets-out", type=Path, default=None)
    a = ap.parse_args(argv)
    t0 = time.time()
    last = a.last_season
    games = load_games(a.cache)
    arch = archive_lines(a.cache)
    paid = games[(games["season"] >= PAID_FIRST) & (games["season"] <= last)]
    rows = load_spread_rows(a.cache, set(paid["game_id"]))
    print(f"games {len(games)}; spread rows of the 8 books on {PAID_FIRST}-{last} games {len(rows)} "
          f"({time.time() - t0:.0f}s)", flush=True)
    h = history(games, arch, close_consensus(rows, games), last)
    c, c_n = c_by_phase(h)
    print(f"c (mean final margin + PT opener, {C_SEASONS[0]}-{C_SEASONS[1]}): "
          f"{ {k: round(v, 4) for k, v in c.items()} } games {c_n}", flush=True)
    tables, sizes = {}, {}
    for s in range(PAID_FIRST, last + 2):
        tables[s], sizes[s] = table_for(h, s)
    print(f"margin tables fitted ({time.time() - t0:.0f}s): training games {sizes}", flush=True)
    if a.check_tables:
        print("table check against", a.check_tables, json.dumps(check_tables(tables, a.check_tables)))

    scored = h[(h["season"] >= PAID_FIRST)]
    dec_rows = []
    for s in range(PAID_FIRST, last + 1):
        gs = scored[scored["season"] == s][["game_id", "game_date", "tip", "season", "margin"]]
        for d in replay_season(rows, gs, c, tables[s], CUT):
            if d.status in ("bets", "too_few_books", "book_not_bettable") or d.best is not None:
                b = d.best or {}
                dec_rows.append({"game_id": d.game_id, "season": s, "status": d.status,
                                 **{k: b.get(k) for k in ("bookmaker", "side", "line", "price", "edge",
                                                          "prob", "cons", "n_ok", "mu")}})
        print(f"  replayed {s} ({time.time() - t0:.0f}s)", flush=True)
    dz = pd.DataFrame(dec_rows).merge(scored[["game_id", "game_date", "margin"]], on="game_id")
    bets = grade(dz[dz["edge"] > CUT].copy())
    tab = table_rows(bets, last)
    live = bets[bets["status"] == "bets"]
    min_ev = float((live["prob"] * sm.dec(live["price"]) - 1).min())
    summary = {"cut": CUT, "rule": "15:00 UTC, every bettable book, consensus incl. the bet book, "
                                  "best quote per game, no games-played wait",
               "priced_games": int(len(dz)), "by_season": tab,
               "min_ev_live": round(min_ev, 4),
               "min_prob_live": round(float(live["prob"].min()), 4)}
    print("replay:", json.dumps(summary, indent=1))
    if a.check_bets:
        print("bet check against", a.check_bets, json.dumps(check_bets(bets, a.check_bets), indent=1))
    if a.bets_out:
        bets.to_parquet(a.bets_out, index=False)
    out = a.out or (sm.ROOT / f"models/saved/ncaab_spread_market_{last + 1}.json")
    art = {
        "kind": sm.ARTIFACT_KIND, "model_id": sm.MODEL_ID,
        "season": last + 1, "prior_season": last,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": f"python -m scripts.ncaab_spread_market_build --cache <copy of the three reads> "
                   f"--last-season {last}",
        "books": list(bq.BOOKS), "check_hour_utc": bq.CHECK_HOUR_UTC, "window_min": bq.WINDOW_MIN,
        "cut": CUT, "min_other_books": sm.MIN_OTHER_BOOKS,
        "c_by_phase": c, "c_games": c_n,
        "c_note": f"mean(final margin + Prediction Tracker opener) over the {C_SEASONS[0]}-{C_SEASONS[1]} "
                  "archive games, by phase; the evidence used these for every season and never refit them",
        "table_train_seasons": [TABLE_FIRST, last], "table_train_games": sizes[last + 1],
        "margin_table": md.to_json(tables[last + 1]),
        "replay": summary,
    }
    out.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

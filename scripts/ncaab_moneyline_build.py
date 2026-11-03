"""Build the NCAAB moneyline model's frozen numbers
(models/ncaab_moneyline_own_spread.py) and replay its card walk-forward.

Writes models/saved/ncaab_moneyline_own_spread_<season>.json: the books, the
check hour and window, the cut, the price floor, the flag limits, and WHICH
final-margin table the card prices with. The table is not copied: it is the
spread model's (models/saved/ncaab_spread_market_<season>.json, fitted on 2012
through the last finished season), and this build refits it with the spread
build's own functions and refuses to write unless the two are identical; the
artifact pins the table's SHA-256 so a later rebuild of the spread artifact
cannot silently change this model.

It then REPLAYS the card's own decision path
(models.ncaab_moneyline_own_spread.read -> decide) on every 2021..last season
at the 15:00 UTC instant of each game, with the margin table fitted on the
seasons before each one, grades every bet (a moneyline, overtime included),
prints bets, units and ROI by season, and compares the bets game by game with
the research's.

    python -m scripts.ncaab_moneyline_build --cache DIR [--last-season 2026]
        [--out PATH] [--check-tables PKL] [--check-bets PARQUET] [--bets-out PATH]

DIR is the same read-only copy scripts/ncaab_spread_market_build.py reads
(games.parquet, ncaab_archive_lines.parquet, odds_parts/*.parquet); the odds
parts must carry the h2h rows of the eight books and of Pinnacle and Bovada as
well as the spreads (the 2026-11-02 build read the copy taken for the research,
scratch ncaab_model/cache, 2026-10-26 to 10-30). Every row is in Supabase.

--check-tables compares the walk-forward margin tables with a pickle of the
research's ({season: {"pmf", "ge"}}); --check-bets compares the replayed bets,
game by game, with the research's (game_id, side 'home'/'away', bookmaker,
price). Reads nothing else and writes only the JSON (and --bets-out).
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
import models.ncaab_moneyline_own_spread as om  # noqa: E402
import scripts.ncaab_spread_market_build as sb  # noqa: E402

PAID_FIRST = sb.PAID_FIRST
BOOTSTRAP = 2000


def load_h2h_rows(cache: Path, game_ids: set) -> pd.DataFrame:
    """Every stored moneyline row of REF_BOOKS for these games, file order kept
    (it breaks a tie between two rows of one book with the same stamp)."""
    parts = []
    files = sorted(glob.glob(str(cache / "odds_parts" / "*.parquet")))
    if not files:
        raise SystemExit(f"{cache}/odds_parts/*.parquet: no odds parts")
    for f in files:
        d = pd.read_parquet(f, columns=["game_id", "market", "bookmaker", "snapshot_at",
                                        "home_price", "away_price"])
        d = d[(d["market"] == "h2h") & d["bookmaker"].isin(om.REF_BOOKS) & d["game_id"].isin(game_ids)]
        parts.append(d.drop(columns="market"))
    o = pd.concat(parts, ignore_index=True)
    o["order"] = np.arange(len(o), dtype="int64")
    o["ts"] = pd.to_datetime(o["snapshot_at"], utc=True, format="mixed")
    o = o.rename(columns={"home_price": "p1", "away_price": "p2"})
    for c in ("p1", "p2"):
        o[c] = pd.to_numeric(o[c], errors="coerce").astype(float)
    o["line"] = np.nan
    return o.drop(columns="snapshot_at")


def replay_season(ml_rows: pd.DataFrame, sp_rows: pd.DataFrame, games: pd.DataFrame,
                  table: dict, cut: float) -> list[om.Decision]:
    """The card's decision path over one season's games at their 15:00 UTC
    instants: read, then decide. Games without a tip, or tipping less than
    five minutes after 15:00 UTC, are not priced (as on the card)."""
    g = games[games["tip"].notna()].copy()
    g["instant"] = [pd.Timestamp(bq.check_instant(d)) for d in g["game_date"]]
    g = g[[not om.too_close(t, i) for t, i in zip(g["tip"], g["instant"])]]
    key = g[["game_id", "instant", "tip"]]
    ml, sp = om.read(ml_rows.merge(key, on="game_id", how="inner"),
                     sp_rows.merge(key, on="game_id", how="inner"), table)
    return om.decide(list(g["game_id"]), ml, sp, cut)


def grade(b: pd.DataFrame) -> pd.DataFrame:
    """A moneyline: the side wins when its team's final margin (overtime
    included) is positive. A game with no margin, or a 0 margin, is not graded."""
    b = b[b["margin"].notna() & (b["margin"] != 0)].copy()
    dd = om.dec(b["price"])
    win = np.where(b["side"] == "home", b["margin"] > 0, b["margin"] < 0)
    b["risk"] = np.minimum(1 / (dd - 1), 3.0)
    b["units"] = np.where(win, b["risk"] * (dd - 1), -b["risk"])
    b["result"] = np.where(win, "W", "L")
    return b


def summarize(b: pd.DataFrame) -> dict:
    if not len(b):
        return {"bets": 0}
    out = sb.summarize(b)
    du = b.groupby("game_date")["units"].sum().sort_values(ascending=False)
    out["record"] = f"{int((b.result == 'W').sum())}-{int((b.result == 'L').sum())}"
    out["units_without_10_best_dates"] = round(float(du.iloc[10:].sum()), 2)
    ev = b["prob"] * om.dec(b["price"]) - 1
    out["ev_min"] = round(float(ev.min()), 4)
    out["ev_median"] = round(float(ev.median()), 4)
    return out


def check_tables(tables: dict, path: Path) -> dict:
    return sb.check_tables(tables, path)


def check_bets(bets: pd.DataFrame, path: Path) -> dict:
    r = pd.read_parquet(path, columns=["game_id", "side", "bookmaker", "price", "edge_own"])
    m = bets.merge(r, on="game_id", how="outer", suffixes=("", "_res"), indicator=True)
    both = m[m["_merge"] == "both"]
    same = both[(both["side"] == both["side_res"]) & np.isclose(both["price"], both["price_res"])]
    other = same[same["bookmaker"] != same["bookmaker_res"]]
    return {"replay_bets": int(len(bets)), "research_bets": int(len(r)),
            "both": int(len(both)),
            "replay_only": m.loc[m["_merge"] == "left_only", "game_id"].tolist()[:20],
            "research_only": m.loc[m["_merge"] == "right_only", "game_id"].tolist()[:20],
            "same_game_side_price": int(len(same)),
            "same_book_too": int((same["bookmaker"] == same["bookmaker_res"]).sum()),
            "other_book_same_side_price": int(len(other)),
            "other_book_edge_equal": int(np.isclose(other["edge"], other["edge_own"], rtol=0,
                                                    atol=1e-12).sum()),
            "max_abs_edge_diff": float((same["edge"] - same["edge_own"]).abs().max()) if len(same) else None}


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
    games = sb.load_games(a.cache)
    arch = sb.archive_lines(a.cache)
    paid = games[(games["season"] >= PAID_FIRST) & (games["season"] <= last)]
    sp_rows = sb.load_spread_rows(a.cache, set(paid["game_id"]))
    ml_rows = load_h2h_rows(a.cache, set(paid["game_id"]))
    print(f"games {len(games)}; {PAID_FIRST}-{last} rows: spreads {len(sp_rows)}, moneylines "
          f"{len(ml_rows)} ({time.time() - t0:.0f}s)", flush=True)
    h = sb.history(games, arch, sb.close_consensus(sp_rows, games), last)
    tables, sizes = {}, {}
    for s in range(PAID_FIRST, last + 2):
        tables[s], sizes[s] = sb.table_for(h, s)
    print(f"margin tables fitted ({time.time() - t0:.0f}s): training games {sizes}", flush=True)
    if a.check_tables:
        print("table check against", a.check_tables, json.dumps(check_tables(tables, a.check_tables)))

    # The live table is the spread model's: refuse to write unless they are identical.
    spread_art_rel = f"models/saved/ncaab_spread_market_{last + 1}.json"
    spread_art = json.loads((om.ROOT / spread_art_rel).read_text(encoding="utf-8"))
    theirs = md.from_json(spread_art["margin_table"])
    mine = tables[last + 1]
    diff = {k: float(np.abs(mine[k] - theirs[k]).max()) for k in ("pmf", "ge")}
    print(f"table {last + 1} against {spread_art_rel}: largest difference {diff}", flush=True)
    if any(v != 0.0 for v in diff.values()) or int(spread_art["season"]) != last + 1:
        raise SystemExit(f"{spread_art_rel} does not hold the table this build fits; not written")

    scored = h[h["season"] >= PAID_FIRST]
    rows = []
    for s in range(PAID_FIRST, last + 1):
        gs = games[games["season"] == s][["game_id", "game_date", "tip", "season"]]
        for d in replay_season(ml_rows, sp_rows, gs, tables[s], om.CUT):
            if d.best is not None:
                b = d.best
                rows.append({"game_id": d.game_id, "season": s, "status": d.status,
                             **{k: b.get(k) for k in ("bookmaker", "side", "price", "edge", "prob",
                                                      "own_line", "mu")}})
        print(f"  replayed {s} ({time.time() - t0:.0f}s)", flush=True)
    dz = pd.DataFrame(rows).merge(scored[["game_id", "game_date", "margin"]], on="game_id", how="left")
    bets = grade(dz[dz["edge"] > om.CUT].copy())
    per = {str(s): summarize(bets[bets["season"] == s]) for s in sorted(bets["season"].unique())}
    per[f"{PAID_FIRST}-{last - 1}"] = summarize(bets[bets["season"] <= last - 1])
    per[str(last)] = summarize(bets[bets["season"] == last])
    neighbours = {}
    for c in (0.005, 0.015):
        x = grade(dz[dz["edge"] > c].copy())
        neighbours[str(c)] = {f"{PAID_FIRST}-{last - 1}": summarize(x[x["season"] <= last - 1]),
                              str(last): summarize(x[x["season"] == last])}
    min_ev = float((bets["prob"] * om.dec(bets["price"]) - 1).min())
    summary = {"cut": om.CUT, "min_price": om.MIN_PRICE,
               "rule": "15:00 UTC, every bettable book's moneyline priced off its own spread, flagged "
                       "quotes out, sides shorter than -200 out before the pick, best side per game, "
                       "no games-played wait",
               "priced_games": int(len(dz)), "by_season": per, "neighbour_cuts": neighbours,
               "min_ev": round(min_ev, 4),
               "min_prob": round(float(bets["prob"].min()), 4)}
    print("replay:", json.dumps(summary, indent=1))
    check = None
    if a.check_bets:
        check = check_bets(bets, a.check_bets)
        print("bet check against", a.check_bets, json.dumps(check, indent=1))
    if a.bets_out:
        bets.to_parquet(a.bets_out, index=False)
    out = a.out or (om.ROOT / f"models/saved/ncaab_moneyline_own_spread_{last + 1}.json")
    art = {
        "kind": om.ARTIFACT_KIND, "model_id": om.MODEL_ID,
        "season": last + 1, "prior_season": last,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": f"python -m scripts.ncaab_moneyline_build --cache <copy of the three reads> "
                   f"--last-season {last}",
        "books": list(bq.BOOKS), "ref_books": list(om.REF_BOOKS),
        "check_hour_utc": bq.CHECK_HOUR_UTC, "window_min": bq.WINDOW_MIN,
        "min_lead_min": int(om.MIN_LEAD.total_seconds() // 60),
        "cut": om.CUT, "min_price": om.MIN_PRICE,
        "isum_range": [om.ISUM_LO, om.ISUM_HI], "disagree_line": om.DISAGREE_LINE,
        "margin_table_from": spread_art_rel,
        "margin_table_sha256": om.table_digest(spread_art["margin_table"]),
        "table_train_seasons": [sb.TABLE_FIRST, last], "table_train_games": sizes[last + 1],
        "replay": summary, "research_check": check,
    }
    out.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

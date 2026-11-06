"""Re-grade the three live NBA in-play rules on the archive's HOURLY purchases
only, under the rule the live loop runs, through the house standard of record
9.1 (scripts/nba_game2_verdict.py --house5: bands, 200 placebo runs).

WHY (independent review, 2026-11-04). IG-2's graded cells (record 7.3) read
every archive purchase: the hourly ones (ledger why='hourly', requested on the
hour, the market as served about 264 s before it; 553 s in 2020-21, 549 s in 2021-22)
AND the 'gap_fill' purchases at :30 (53.5% exactly 30 minutes before a listed
tip, 19.4% at one). The live loop can only reproduce the hourly ones: it
fetches at every hour minus 264 s and never builds a fetch time from a tip
(games.commence_time in 2026-27 holds the actual start). So the rule that
ships is graded here on the hourly purchases alone.

THE RULE GRADED is the shipping one (models/nba_live_ig2.py), applied to the
held seasons 2020-21 .. 2025-26:
  quotes      the research cache's archive rows (nba_odds, source
              odds_api_historical), each placed in its purchase by the ledger
              exactly as scripts/nba_ingame_data.load_quotes places it, then
              ONLY the hourly purchases kept, and only then the same-stamp
              dedupe (so a quote first served at a :30 purchase and again at
              the next hour counts at the hour);
  served      the purchase minus the season's grid offset (load_quotes);
  state       the held play-by-play pull (nba_pbp, scripts/nba_s_ingame27
              --pull-held) through L.in_play_state: the stable state join;
  rules       1 (price), 3-4 (far from Pinnacle), 5 (early clock), 6 (clock
              jump), and record 7.1's freshness, as L applies them;
  model       IG-2's walk-forward state models (2020-21 in-sample, 2021-22 ..
              2025-26 each fit on the seasons before it), the held prior;
  decision    the first eligible hourly purchase per game, market and phase.
Cells: quarters 1-2 spread, quarter-3 moneyline, quarter-3 spread, each at EV
>= 0.02 / 0.05 / 0.08 (the bands need the neighbours), family
IG2_hourly_live. Pooled 2021-22 .. 2025-26, chosen on 2021-22 .. 2024-25.

    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_live_ig2_regrade --out <folder>
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5

Read-only inputs, all caches of Supabase rows; writes to --out only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_ingame_data as D  # noqa: E402
from scripts import nba_ingame_ig2 as G  # noqa: E402
from scripts import nba_s_ingame27 as L  # noqa: E402
from scripts.nba_game_market_lab import imp  # noqa: E402

FAMILY = "IG2_hourly_live"
RULE_CELLS = {"Q1-Q2": ("spreads",), "Q3": ("h2h", "spreads")}
HOURLY_WHY = "hourly"


def hourly_quotes(cache: Path, games: pd.DataFrame, seasons, all_purchases: bool = False) -> tuple[pd.DataFrame, dict]:
    """D.load_quotes with the ledger's non-hourly purchases removed BEFORE the
    same-stamp dedupe. Every other line is load_quotes'."""
    o = pd.read_parquet(cache / "nba_odds.parquet")
    o = o[o["market"].isin(("h2h", "spreads")) & (o["source"] == "odds_api_historical")].copy()
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True)
    o = o.merge(games[["game_id", "season", "game_date", "tip"]], on="game_id")
    led = pd.read_parquet(cache / "nba_fetch_ledger.parquet")
    led["requested_at"] = pd.to_datetime(led["requested_at"], utc=True)
    # The seventh search's 5-minute news-window purchases (2026-10-24, after the
    # graded table was built) are left out with the quotes they bought, as
    # H.load leaves them out: otherwise they would place rows the graded table
    # never held.
    news = led["why"] == H.NEWS_WINDOW_WHY
    news_pulls = set(pd.to_datetime(led.loc[news, "pulled_at"], utc=True))
    o = o[~pd.to_datetime(o["created_at"], utc=True, format="mixed").isin(news_pulls)].copy()
    led = led[~news]
    o, notes = H.attach_fetch(o, led)
    hourly = set(led.loc[led["why"] == HOURLY_WHY, "requested_at"])
    notes["rows_before_hourly_filter"] = int(len(o))
    # the served offset is measured on the fetches load_quotes measured it on
    newest = o.groupby("fetch_at")["snapshot_at"].max().rename("served_newest")
    o = o.merge(newest.reset_index(), on="fetch_at", how="left")
    per_fetch = o[["season", "fetch_at", "served_newest"]].drop_duplicates("fetch_at")
    gap = (per_fetch["fetch_at"] - per_fetch["served_newest"]).dt.total_seconds()
    offset = gap.groupby(per_fetch["season"]).quantile(D.GRID_Q)
    notes["grid_offset_s"] = {int(k): float(v) for k, v in offset.items()}
    on_grid = o["fetch_at"] - pd.to_timedelta(o["season"].map(offset), unit="s")
    o["served_at"] = on_grid.where(on_grid > o["served_newest"], o["served_newest"])
    if not all_purchases:
        o = o[o["fetch_at"].isin(hourly)].copy()
    notes["rows_hourly"] = int(len(o))
    o = o[o["season"].isin(list(seasons))
          & (o["snapshot_at"] >= o["tip"] - pd.Timedelta(minutes=D.PREFILTER_MIN))].copy()
    o = o.rename(columns={"bookmaker": "book", "snapshot_at": "stamp", "snapshot_type": "label"})
    k = ["game_id", "market", "book", "stamp", "fetch_at"]
    o = o.drop_duplicates(k)
    k2 = ["game_id", "market", "book", "stamp"]
    o = o.sort_values([*k2, "fetch_at"])
    notes["rows_same_stamp_later_fetch"] = int(o.duplicated(k2).sum())
    o = o.drop_duplicates(k2, keep="first")
    o["line"] = np.where(o["market"] == "spreads", o["spread_home"], np.nan)
    o["price_a"], o["price_b"] = o["home_price"], o["away_price"]
    o = o[o["price_a"].notna() & o["price_b"].notna()].copy()
    bad = L.impossible_price(o["price_a"]) | L.impossible_price(o["price_b"])
    notes["rule1_dropped"] = int(bad.sum())
    o = o[~bad].copy()
    ia, ib = imp(o["price_a"]), imp(o["price_b"])
    o["implied_sum"] = ia + ib
    o["coherent"] = (o["implied_sum"] >= H.COHERENT[0]) & (o["implied_sum"] <= H.COHERENT[1])
    o["fa"] = ia / (ia + ib)
    keep = ["game_id", "season", "game_date", "tip", "market", "book", "label", "stamp", "fetch_at",
            "served_at", "served_newest", "line", "price_a", "price_b", "implied_sum", "coherent", "fa"]
    return o[keep].reset_index(drop=True), notes


def held_table(cache: Path, all_purchases: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """The hourly in-play table under the shipping rule: (qt for G.eligible, games, notes)."""
    games = H.load_games(cache)
    games = games[games["season"].isin(L.HELD_SEASONS)].reset_index(drop=True)
    q, notes = hourly_quotes(cache, games, L.HELD_SEASONS, all_purchases)
    pbp = pd.read_parquet(L.SCRATCH / L.HELD_PULL["pbp"])
    pbp = pbp[pbp["season_type"] == 2]
    box = pd.read_parquet(L.SCRATCH / L.HELD_PULL["box"])
    prior_min = L.box_prior_minutes(L.all_box())
    jumps = L.jump_games(pbp)
    notes["games_wallclock_jump"] = len(jumps)
    out = []
    for s in L.HELD_SEASONS:
        t0 = time.time()
        plays, wild = L.live_plays(pbp[pbp["season"] == s])
        top = L.box_top_players(box[(box["season"] == s) & box["game_id"].isin(set(plays["game_id"]))], prior_min)
        qs = q[q["season"] == s]
        qs, _tl, n = L.in_play_state(qs, plays, top, games)
        out.append(qs)
        print(f"season {s}: {len(qs):,} in-play quotes ({time.time() - t0:.0f}s)", flush=True)
    qa = pd.concat(out, ignore_index=True)
    qa, early = L.drop_early_clocks(qa)
    notes["games_first_play_before_listed_tip"] = early
    qa = qa[~qa["game_id"].isin(set(jumps))].reset_index(drop=True)
    qa, d34 = L.apply_bad_rows(qa)
    notes["rule34_dropped"] = int(len(d34))
    return L.step1_table(qa), games, notes


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--all-purchases", action="store_true",
                    help="the comparator: hourly AND gap-fill purchases, the same rule")
    ap.add_argument("--table", type=Path, default=None,
                    help="the built in-play table: written by --build-table, read otherwise")
    ap.add_argument("--build-table", action="store_true", help="build the table, save it, stop")
    ap.add_argument("--cell", default=None,
                    help="one family only, 'Q1-Q2:spreads' / 'Q3:h2h' / 'Q3:spreads' (parallel runs)")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NBA_GAME2_BETS", str(a.out / "bets"))
    H.check()
    t0 = time.time()
    if a.table is not None and a.table.exists() and not a.build_table:
        qt = pd.read_parquet(a.table)
        notes = json.loads(a.table.with_suffix(".json").read_text(encoding="utf-8"))
    else:
        qt, _games, notes = held_table(H.CACHE, a.all_purchases)
        if a.table is not None:
            qt.to_parquet(a.table, index=False)
            a.table.with_suffix(".json").write_text(json.dumps(notes, indent=1, default=str), encoding="utf-8")
        if a.build_table:
            print(f"table built: {len(qt):,} rows ({time.time() - t0:.0f}s)")
            return
    train = pd.read_parquet(G.TRAIN_CACHE)
    models = G.models_by_season(train, G.FEATURES)
    prior = pd.read_parquet(G.PRIOR_CACHE)
    dec_all = L.phase_decisions(qt, prior, models, step=1)
    data = L.empty_data(H.load_games(H.CACHE))
    rows = []
    cells_wanted = RULE_CELLS
    if a.cell:
        ph_, mk_ = a.cell.split(":")
        cells_wanted = {ph_: (mk_,)}
    for ph, markets in cells_wanted.items():
        dec = dec_all[(dec_all["phase_ig2"] == ph) & dec_all["market"].isin(markets)]
        fr = L.step1_frames(dec, models, data.games)
        r = L.emit(data, FAMILY, ph, fr, {mk: ["model"] for mk in markets}, L.PLACEBO_SEEDS, H.CHOOSE,
                   L.HELD_GRADED)
        for x in r:
            b = L.beside(fr, x, data.games, L.HELD_GRADED, None)
            x.update({k: v for k, v in b.items() if not isinstance(v, dict)})
        rows += r
        print(f"{ph}: {len(r)} cells ({time.time() - t0:.0f}s)", flush=True)
    cells = pd.DataFrame(rows)
    if a.all_purchases:
        cells["family"] = FAMILY.replace("hourly", "allpurchases")
    tag = "" if not a.cell else "_" + a.cell.replace(":", "_").replace("-", "")
    cells.to_parquet(a.out / f"cells_{cells['family'].iloc[0]}{tag}.parquet", index=False)
    notes["decisions"] = {f"{p}|{m}": int(n) for (p, m), n in
                          dec_all.drop_duplicates(["game_id", "market", "phase_ig2"])
                          .groupby(["phase_ig2", "market"]).size().items()}
    (a.out / "notes.json").write_text(json.dumps(notes, indent=1, default=str), encoding="utf-8")
    cols = ["point", "market", "cut", "pool_n", "pool_units", "pool_roi", "pool_ci95_lo", "pool_ci95_hi",
            "pool_seasons_counted", "pool_seasons_positive", "roi_choose", "roi_confirm", "n_confirm"]
    print(cells[[c for c in cols if c in cells]].round(4).to_string(index=False))
    print(f"done in {time.time() - t0:.0f}s; notes {json.dumps({k: v for k, v in notes.items() if not isinstance(v, dict)})}")


if __name__ == "__main__":
    main()

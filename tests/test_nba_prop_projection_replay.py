"""The NBA projection model's LIVE code, replayed on the graded seasons.

Two checks that the code which bets is the code that was graded
(docs/nba_models_2026.md section 5):

  * find_bets, the live selection, on a month of 2025-26's archived quotes and
    the stored walk-forward means, returns the graded card's bets, bet for bet:
    same propositions, side, line, book and price.
  * project_core, the live projection, on one 2025-26 night from the research
    cache, gives the graded walk-forward means and projects every player the
    graded card bet.

They need the research cache (data/local/nba, scripts/nba_research_cache.py)
and the research work folders under the build machine's temp directory, so
they SKIP anywhere those are absent. On the build machine they run with the
suite: the replay of 2026-01-15 takes about a minute.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.nba_prop_projection as pj  # noqa: E402
import models.nba_props as nb  # noqa: E402
from models.nba_prop_market import parse_ts  # noqa: E402

RESEARCH = Path(os.environ.get("NBA_RESEARCH_DIR", "C:/Users/micha/AppData/Local/Temp/nba_rebuild"))
CACHE = Path(__file__).parent.parent / "data" / "local" / "nba"
NEEDS = [RESEARCH / "verify_model/work/quotes.parquet", RESEARCH / "verify_model/work/pred_wk_2026.parquet",
         RESEARCH / "verify_model/work/alphas_wk.json", RESEARCH / "verify_model/work/models_wk_2026.pkl",
         RESEARCH / "proj/work/calib_maps.parquet", RESEARCH / "proj/bets_card_best.parquet",
         RESEARCH / "results/props_market_bets_sharp_ALL_under_prop_0.00.parquet",
         CACHE / "nba_games.parquet"]
pytestmark = pytest.mark.skipif(not all(p.exists() for p in NEEDS),
                                reason="the NBA research cache and work folders are not on this machine")
SEASON = 2026
KEY = ["game_id", "player_id", "market"]


def _means(pred: pd.DataFrame) -> pd.DataFrame:
    proj = pred[["game_id", "player_id", "status"]].copy()
    for m in pj.MARKETS:
        proj[f"mu_{m}"] = np.clip(sum(pred[f"mu2_{s}"].values for s in nb.BY_MARKET[m].parts), pj.MU_FLOOR, None)
    return proj.drop_duplicates(["game_id", "player_id"])


def test_the_live_selection_returns_the_graded_bets_for_a_month(monkeypatch):
    # the research decided inside 45-70 on the archive's one snapshot; only SELECTION is compared here
    monkeypatch.setattr(pj, "DECISION_WINDOW_MIN", (45, 70))
    books = nb.books()
    W = RESEARCH / "verify_model/work"
    q = pd.read_parquet(W / "quotes.parquet")
    q = q[(q.season == SEASON) & q.market.isin(pj.MARKETS) & q.bookmaker.isin(books)
          & (pd.to_datetime(q.game_date) >= "2026-01-01") & (pd.to_datetime(q.game_date) < "2026-02-01")].copy()
    q["player_id"] = q.player_id.astype(str)
    pred = pd.read_parquet(W / f"pred_wk_{SEASON}.parquet")
    pred["player_id"] = pred.player_id.astype(str)
    proj = _means(pred)
    al = json.loads((W / "alphas_wk.json").read_text(encoding="utf-8"))
    maps = pd.read_parquet(RESEARCH / "proj/work/calib_maps.parquet")
    art = {"alphas": {m: al[f"two_stage|{m}|{SEASON}"] for m in pj.MARKETS},
           "calibration": {m: tuple(maps[(maps.season == SEASON) & (maps.market == m)][["a", "b"]].iloc[0])
                           for m in pj.MARKETS}}
    rule = pd.read_parquet(RESEARCH / "results/props_market_bets_sharp_ALL_under_prop_0.00.parquet",
                           columns=KEY)
    rule_keys = set(zip(rule.game_id, rule.player_id.astype(str), rule.market))
    g = pd.read_parquet(CACHE / "nba_games.parquet", columns=["game_id", "commence_time", "game_date"])
    g = g.set_index("game_id")
    tips = nb._utc(g.commence_time)
    recs = q[["game_id", "player_name", "player_id", "market", "bookmaker", "line", "over_price", "under_price",
              "snapshot_at"]].rename(columns={"player_name": "player", "bookmaker": "book"}).to_dict("records")
    by_game: dict[str, list[dict]] = {}
    for r in recs:
        for k in ("line", "over_price", "under_price"):
            v = r[k]
            r[k] = None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)
        r["over_link"] = r["under_link"] = r["book_last_update"] = None
        by_game.setdefault(r["game_id"], []).append(r)
    bets = []
    for gid, rows in by_game.items():
        now = max(parse_ts(r["snapshot_at"]) for r in rows) + timedelta(seconds=1)
        games = {gid: {"tip": tips[gid].to_pydatetime(), "game_date": str(g.game_date[gid])[:10]}}
        b, _, _ = pj.find_bets(rows, proj[proj.game_id == gid], games, now, art, rule_keys, set(), {gid},
                               books, price_floor=-200.0)
        bets += b
    live = pd.DataFrame([b.__dict__ for b in bets])
    graded = pd.read_parquet(RESEARCH / "proj/bets_card_best.parquet")
    graded = graded[(graded.season == SEASON) & graded.market.isin(pj.MARKETS)
                    & graded.game_id.isin(set(by_game))].copy()
    graded["player_id"] = graded.player_id.astype(str)
    assert len(graded) > 1000, "a month of 2025-26 holds thousands of graded bets"
    m = graded.merge(live, on=KEY, how="outer", suffixes=("_g", "_l"), indicator=True)
    assert (m._merge == "both").all(), m._merge.value_counts().to_dict()
    for c in ("side", "line", "book", "price"):
        assert (m[f"{c}_g"] == m[f"{c}_l"]).all(), c


def test_the_live_projection_gives_the_graded_means_for_one_night():
    import scripts.nba_prop_projection_card as card
    W = RESEARCH / "verify_model/work"
    fm = pd.read_pickle(W / "models_wk_2026.pkl")
    art = {"minutes": fm["minutes"], "rates": {s: fm[f"rate_{s}"] for s in pj.STATS}}
    pred = pd.read_parquet(W / "pred_wk_2026.parquet")
    pred["player_id"] = pred.player_id.astype(str)
    raw = nb.load_cache(CACHE, with_props=True, with_lines=False)
    props = raw["nba_props"]
    dec = nb.decisions_for(raw, props[props.game_date < "2026-10-20"])
    report = pj.compact_report(pj.collapse_official(raw["nba_injury_report"]), dec)
    games = raw["nba_games"][["game_id", "season", "game_date", "home_team", "away_team", "commence_time"]].copy()
    games = games[games.season >= nb.FIRST_TRAIN_SEASON]
    games["season"] = games.season.astype(int)
    log = raw["nba_player_game_log"].copy()
    log["player_id"] = log.player_id.astype(str)
    day, tip = "2026-01-15", pd.Timestamp("2026-01-16T00:30:00Z")          # two games tip at 7:30pm ET
    gids = [gid for gid, t in nb._utc(games.set_index("game_id").commence_time).items()
            if t == tip and str(games.set_index("game_id").game_date[gid])[:10] == day]
    assert len(gids) == 2
    now = dec.set_index("game_id").decision_ts.reindex(gids).max().to_pydatetime()
    hist = {"games": games, "schedule": raw["nba_schedule"][["game_id", "game_type", "commence_time"]],
            "log": log[pd.to_datetime(log.game_date) < pd.Timestamp(day)],
            "asof": report[~report.game_id.isin(gids)].assign(source="official")}
    priced = props[props.game_id.isin(gids) & props.market.isin(pj.MARKETS)][["game_id", "player_name"]]
    rows, _ = card.project_core(hist, report[report.game_id.isin(gids)], gids, now, priced.drop_duplicates(), art)
    m = rows.merge(pred, on=["game_id", "player_id"])
    assert len(m) == len(rows) > 40
    for mk in pj.MARKETS:
        want = np.clip(sum(m[f"mu2_{s}"].values for s in nb.BY_MARKET[mk].parts), pj.MU_FLOOR, None)
        assert np.allclose(m[f"mu_{mk}"].values, want, rtol=1e-9), mk
    graded = pd.read_parquet(RESEARCH / "proj/bets_card_best.parquet")
    graded = graded[graded.game_id.isin(gids) & graded.market.isin(pj.MARKETS)]
    have = set(zip(rows.game_id, rows.player_id))
    assert graded.size and all((g_, str(p)) in have for g_, p in zip(graded.game_id, graded.player_id))

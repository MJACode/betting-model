"""Replay the LIVE `nba_total_luck` code on the research cache, against the lab.

The live model (models/nba_total_luck.decide) is run on the archived seasons at
the lab's own decision instants (decision point C: the newest fetch 60-180
minutes before tip, scripts.nba_game_harness.decision_times), with:

  quotes   the archived odds rows, shaped by the LIVE shaping
           (models.nba_total_luck.quote_frame) after their fetch instant is
           read from the purchase ledger (the live odds table carries it in
           created_at; the archive's created_at is the purchase time)
  box      nba_player_game_log, and the season's final games from nba_games
  schedule nba_schedule's regular-season rows: what the completeness check
           (models.nba_total_luck.missing_inputs) owes before each date
  pricing  the committed artifact (models.nba_total_luck.ARTIFACT_PATH)

and compared, game by game, with what the lab graded:

  gaps     the lab's own projection (scripts.nba_game2_luck: team_box +
           f4_projections over every graded season at once)
  bets     the lab's bet file for the shipped cell (F4, C, totals, over, 3.0)

    NBA_RESEARCH_CACHE=... python -m scripts.nba_total_luck_replay [--seasons 2026 ...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import models.nba_total_luck as tl  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

BETS = Path("C:/Users/micha/AppData/Local/Temp/nba_game_edge/results/house/bets/"
            "bets_F4_C_totals_0004.parquet")
LAB_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)        # the lab's --full load


def lab_bets(path: Path = BETS) -> pd.DataFrame:
    b = pd.read_parquet(path)
    return b[(b["family"] == "F4") & (b["point"] == "C") & (b["market"] == tl.MARKET)
             & (b["cell_side"] == tl.SIDE) & (b["cut"] == tl.GAP_CUT)].reset_index(drop=True)


def load(cache: Path = H.CACHE, seasons=LAB_SEASONS) -> dict:
    """Everything the replay reads, loaded once."""
    data = H.load(cache, seasons=LAB_SEASONS)              # the lab's own load
    o = pd.read_parquet(cache / "nba_odds.parquet")
    o = o[(o["market"] == tl.MARKET) & (o["source"] == "odds_api_historical")
          & (o["snapshot_type"] != "in_play")].copy()
    o = o[o["game_id"].isin(set(data.games["game_id"]))]
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True)
    led = pd.read_parquet(cache / "nba_fetch_ledger.parquet")
    o, _ = H.attach_fetch(o, led)
    o["created_at"] = o["fetch_at"]                          # the live table's meaning
    box = pd.read_parquet(cache / "nba_player_game_log.parquet",
                          columns=["game_id", "team", *tl.BOX_COLS])
    sched = pd.read_parquet(cache / "nba_schedule.parquet",
                            columns=["game_id", "season", "game_type", "game_date",
                                     "home_team", "away_team", "status_text"])
    sched = sched[sched["game_type"] == "regular"]
    return {"data": data, "rows": o.drop(columns="fetch_at"), "box": box,
            "schedule": sched, "seasons": tuple(seasons)}


def lab_gaps(data: H.Data, box: pd.DataFrame) -> pd.Series:
    """The lab's gap per game, computed the lab's way: one call over every
    graded season (scripts.nba_game2_luck.run_f4)."""
    from scripts import nba_game2_luck as L
    proj = L.f4_projections(data.games, L.team_box(box, data.games))
    return proj.set_index("game_id")["gap_total"]


def replay(ld: dict, season: int, art: dict | None = None) -> dict:
    data, box = ld["data"], ld["box"]
    art = art or tl.load_artifact()
    games = data.games[data.games["season"] == season]
    times = H.decision_times(data.fetches, data.games, "C")
    times = times[times["game_id"].isin(set(games["game_id"]))]
    quotes = tl.quote_frame(ld["rows"], games)
    targets = games[games["game_id"].isin(set(times["game_id"]))][
        ["game_id", "season", "game_date", "home_team", "away_team"]]
    final = games[["game_id", "season", "game_date", "home_team", "away_team"]]
    # 2020-21 and 2021-22 have no graded season before them to fit an uplift on;
    # it moves only the written probability, never the bet, so 0 is used there.
    prior = [s for s in art["bucket"] if int(s) < season]
    sched = ld["schedule"]
    sched = sched[sched["season"].astype(int) == season]
    bets, decisions, diag = tl.decide(targets, quotes, box, final, times, art,
                                      scheduled=sched,
                                      bucket_uplift=None if prior else 0.0)

    lab_gap = lab_gaps(data, box)
    live_gap = {d.game_id: d.gap for d in decisions if d.gap is not None}
    common = sorted(set(live_gap) & set(lab_gap.index[lab_gap.index.isin(targets["game_id"])]))
    diff = np.array([abs(live_gap[g] - lab_gap[g]) for g in common])
    only_lab = sorted(set(lab_gap.index) & set(targets["game_id"]) - set(live_gap))
    only_live = sorted(set(live_gap) - set(lab_gap.index))

    lb = lab_bets()
    lb = lb[lb["season"] == season]
    key = ["game_id", "book", "line", "price"]
    live = pd.DataFrame([{"game_id": b.game_id, "book": b.book, "line": b.line, "price": b.price,
                          "T": b.fetch_at, "gap": b.gap, "p_fair": b.p_fair} for b in bets],
                        columns=key + ["T", "gap", "p_fair"])
    m = lb[key + ["T", "p_win"]].merge(live, on=key, how="outer", indicator=True)
    same_t = m[m["_merge"] == "both"]
    t_ok = bool((pd.to_datetime(same_t["T_x"], utc=True) == pd.to_datetime(same_t["T_y"], utc=True)).all())
    p_ok = bool(np.allclose(same_t["p_win"], same_t["p_fair"], atol=1e-9)) if len(same_t) else True
    return {
        "season": season, "games_decided": int(diag["games"]), "diag": diag,
        "gap_compared": len(common), "gap_max_abs_diff": float(diff.max()) if len(diff) else 0.0,
        "gap_only_lab": only_lab, "gap_only_live": only_live,
        "lab_bets": int(len(lb)), "live_bets": int(len(live)),
        "bets_matched": int((m["_merge"] == "both").sum()),
        "lab_only": m[m["_merge"] == "left_only"][key].to_dict("records"),
        "live_only": m[m["_merge"] == "right_only"][key].to_dict("records"),
        "decision_time_identical": t_ok, "fair_probability_identical": p_ok,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", type=int, nargs="+", default=list(LAB_SEASONS))
    a = ap.parse_args()
    ld = load()
    for s in a.seasons:
        r = replay(ld, s)
        print({k: v for k, v in r.items()})


if __name__ == "__main__":
    main()

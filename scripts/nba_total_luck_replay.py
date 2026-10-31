"""Replay the LIVE `nba_total_luck` code on the research cache, against the lab.

The live model (models/nba_total_luck.decide) is run on the archived seasons at
the lab's own decision instants (decision point C: the newest fetch 60-180
minutes before tip, scripts.nba_game_harness.decision_times), with:

  quotes   the archived odds rows, shaped by the LIVE shaping
           (models.nba_total_luck.quote_frame) after their fetch instant is
           read from the purchase ledger (the live odds table carries it in
           created_at; the archive's created_at is the purchase time)
  games    the season's final games, box scores and owed games read by the
           CARD'S OWN load (scripts.nba_total_luck_card.load_season), its SQL
           answered from the cache's nba_games, nba_schedule and
           nba_player_game_log (FrameConn): the regular-season rule, the
           scores for the box-integrity check and the owed set are the live
           ones
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
    # the injury-report windows (docs/nba_models_2026.md section 11) stay out, as H.load
    # leaves them out: the lab this replays was graded before they were bought
    if "why" in led:
        news = led["why"].astype(str) == H.NEWS_WINDOW_WHY
        if news.any():
            pulled = set(pd.to_datetime(led.loc[news, "pulled_at"], utc=True))
            o = o[~pd.to_datetime(o["created_at"], utc=True, format="mixed").isin(pulled)]
            led = led[~news]
    o, _ = H.attach_fetch(o, led)
    o["created_at"] = o["fetch_at"]                          # the live table's meaning
    box = pd.read_parquet(cache / "nba_player_game_log.parquet",
                          columns=["game_id", "team", *tl.BOX_COLS])
    sched = pd.read_parquet(cache / "nba_schedule.parquet",
                            columns=["game_id", "season", "game_type", "game_date",
                                     "home_team", "away_team", "status_text"])
    games = pd.read_parquet(cache / "nba_games.parquet",
                            columns=["game_id", "season", "game_date", "home_team", "away_team",
                                     "home_score", "away_score"])
    return {"data": data, "rows": o.drop(columns="fetch_at"), "box": box,
            "schedule": sched, "games": games, "seasons": tuple(seasons)}


class FrameConn:
    """The four reads scripts.nba_total_luck_card.load_season makes, answered
    from frames shaped like the production tables (games, nba_schedule,
    nba_player_game_log), the way Postgres answers them. Anything else is
    refused, so a new read cannot slip past the replay unanswered."""

    def __init__(self, games: pd.DataFrame, schedule: pd.DataFrame, box: pd.DataFrame):
        g = games.copy()
        g["game_date"] = g["game_date"].astype(str).str[:10]
        sc = schedule.copy()
        sc["game_date"] = sc["game_date"].astype(str).str[:10]
        self.games, self.schedule, self.box = g, sc, box

    def execute(self, sql, params=None):
        q = " ".join(sql.split())
        if q.startswith("SELECT g.game_id, g.season, g.game_date"):
            season, before = params
            g = self.games[(self.games["season"].astype(int) == season)
                           & (self.games["game_date"] < before)]
            m = g.merge(self.schedule[["game_id", "game_type"]], on="game_id", how="left")
            m["game_type"] = m["game_type"].astype(object).where(m["game_type"].notna(), None)
            rows = m[["game_id", "season", "game_date", "home_team", "away_team",
                      "home_score", "away_score", "game_type"]].itertuples(index=False)
        elif q.startswith("SELECT DISTINCT season, game_date, game_type FROM nba_schedule"):
            sc = self.schedule[self.schedule["season"].astype(int).isin(params[0])]
            rows = sc[["season", "game_date", "game_type"]].drop_duplicates().itertuples(index=False)
        elif q.startswith("SELECT s.game_id, s.game_date"):
            season, before = params
            sc = self.schedule[(self.schedule["season"].astype(int) == season)
                               & (self.schedule["game_type"] == "regular")
                               & (self.schedule["game_date"] < before)]
            rows = sc[["game_id", "game_date", "home_team", "away_team",
                       "status_text"]].itertuples(index=False)
        elif "FROM nba_player_game_log" in q:
            bx = self.box[self.box["game_id"].isin(params[0])]
            rows = bx[["game_id", "team", *tl.BOX_COLS]].itertuples(index=False)
        else:
            raise AssertionError(f"FrameConn: unexpected read: {q[:80]}")
        out = [tuple(r) for r in rows]
        return type("R", (), {"fetchall": lambda self_: out})()


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
    # The card's own load of the season, every game before the season's end.
    from scripts.nba_total_luck_card import load_season
    final, season_box, sched = load_season(FrameConn(ld["games"], ld["schedule"], box),
                                           season, "9999-12-31")
    lab_final = games[["game_id", "home_score", "away_score"]].sort_values("game_id")
    live_final = final[["game_id", "home_score", "away_score"]].sort_values("game_id")
    same_population = (lab_final["game_id"].tolist() == live_final["game_id"].tolist()
                       and np.allclose(lab_final[["home_score", "away_score"]].to_numpy(float),
                                       live_final[["home_score", "away_score"]].to_numpy(float)))
    # 2020-21 and 2021-22 have no graded season before them to fit an uplift on;
    # it moves only the written probability, never the bet, so 0 is used there.
    prior = [s for s in art["bucket"] if int(s) < season]
    bets, decisions, diag = tl.decide(targets, quotes, season_box, final, times, art,
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
        "load_season_is_the_lab_population": bool(same_population),
        "load_season_games": int(len(final)), "lab_games": int(len(lab_final)),
        "gap_compared": len(common), "gap_max_abs_diff": float(diff.max()) if len(diff) else 0.0,
        "gap_only_lab": only_lab, "gap_only_live": only_live,
        "lab_bets": int(len(lb)), "live_bets": int(len(live)),
        "bets_matched": int((m["_merge"] == "both").sum()),
        "lab_only": m[m["_merge"] == "left_only"][key].to_dict("records"),
        "live_only": m[m["_merge"] == "right_only"][key].to_dict("records"),
        "decision_time_identical": t_ok, "fair_probability_identical": p_ok,
    }


def grade_window(ld: dict, season: int, lo: float, hi: float, art: dict | None = None) -> dict:
    """The shipped rule, decided on the newest fetch lo-hi minutes before tip,
    graded on the final scores: how the edge holds at decision times other
    than the lab's C (whose fetches sit at 60 minutes)."""
    data, box = ld["data"], ld["box"]
    art = art or tl.load_artifact()
    games = data.games[data.games["season"] == season]
    f = data.fetches[(data.fetches["lead_min"] >= lo) & (data.fetches["lead_min"] <= hi)]
    times = (f.sort_values(["game_id", "fetch_at"]).drop_duplicates("game_id", keep="last")
              .rename(columns={"fetch_at": "T"})[["game_id", "T", "lead_min"]])
    times = times[times["game_id"].isin(set(games["game_id"]))]
    quotes = tl.quote_frame(ld["rows"], games)
    targets = games[games["game_id"].isin(set(times["game_id"]))][
        ["game_id", "season", "game_date", "home_team", "away_team"]]
    from scripts.nba_total_luck_card import load_season
    final, season_box, sched = load_season(FrameConn(ld["games"], ld["schedule"], box),
                                           season, "9999-12-31")
    prior = [s for s in art["bucket"] if int(s) < season]
    bets, _, _ = tl.decide(targets, quotes, season_box, final, times, art, scheduled=sched,
                           bucket_uplift=None if prior else 0.0)
    tips = games.set_index("game_id")["tip"]
    b = pd.DataFrame([{"game_id": x.game_id, "season": season, "game_date": None,
                       "market": tl.MARKET, "side": tl.SIDE, "line": x.line, "price": x.price,
                       "book": x.book,
                       "lead_min": (tips[x.game_id] - x.fetch_at).total_seconds() / 60.0}
                      for x in bets])
    if b.empty:
        return {"season": season, "bets": 0}
    b["game_date"] = b["game_id"].map(games.set_index("game_id")["game_date"])
    g = H.grade(b, data.games)
    return {"season": season, "bets": int(len(g)), "units": round(float(g["units"].sum()), 2),
            "risk": round(float(g["risk"].sum()), 2), "roi": round(H.roi(g), 4),
            "median_lead_min": float(g["lead_min"].median())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", type=int, nargs="+", default=list(LAB_SEASONS))
    ap.add_argument("--window", type=float, nargs=2, metavar=("LO", "HI"),
                    help="grade the shipped rule on the newest fetch LO-HI minutes before tip")
    a = ap.parse_args()
    ld = load()
    if a.window:
        rows = [grade_window(ld, s, *a.window) for s in a.seasons]
        for r in rows:
            print(r)
        graded = [r for r in rows if r.get("bets") and r["season"] != H.REGIME]
        n = sum(r["bets"] for r in graded)
        u = sum(r["units"] for r in graded)
        risk = sum(r["risk"] for r in graded)
        print(f"pooled 2021-22..2025-26: {n} bets, {u:+.1f} units, {100 * u / risk:+.1f}%, "
              f"{sum(1 for r in graded if r['units'] > 0)} of {len(graded)} seasons positive")
        return
    for s in a.seasons:
        r = replay(ld, s)
        print({k: v for k, v in r.items()})


if __name__ == "__main__":
    main()

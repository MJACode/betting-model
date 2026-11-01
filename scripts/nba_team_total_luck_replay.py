"""Replay the LIVE `nba_team_total_luck` code on the research cache, against the lab.

The live model (models/nba_team_total_luck.decide) is run on 2023-24, 2024-25
and 2025-26 at the lab's own decision instants (decision point D: each game's
per-game purchase 45-75 minutes before tip, scripts.nba_game_harness.
per_event_times on the lab's own load), with:

  quotes   the archived per-game purchase rows (both team-total markets), their
           created_at set to snapshot_at (the purchase's feed time IS its fetch
           instant; the archive's created_at is the day the rows were bought),
           passed through the LIVE write-time split
           (models.nba_book_numbers.split_main_rungs: one fetch at a time, each
           book's main rung kept under its market, the rest renamed
           _alternate), then shaped by the LIVE shaping
           (models.nba_team_total_luck.quote_frame). So the match below is
           proven on the shape the live fetch stores.
  games    the season's final games, box scores and owed games read by the
           totals card's own load (scripts.nba_total_luck_card.load_season,
           its SQL answered from the cache by
           scripts.nba_total_luck_replay.FrameConn)
  pricing  the committed artifact (models.nba_team_total_luck.ARTIFACT_PATH)

and compared, game by game, with what the lab graded:

  home parts  the lab's own (scripts.nba_game4_p3.f4_signal on
              scripts.nba_game2_luck's projection over every graded season).
              On this branch nba_game2_luck's projection IS models/
              nba_total_luck's, so this comparison checks the inputs and the
              home-part formula, not the ratings code; the replay test pins
              the parts against the fourth search's own copy as well
              (tests/test_nba_team_total_luck_replay.py, LAB_HOME_PARTS_SHA256)
  bets        the lab's bet file for the shipped cell (P3_F4, D,
              team_totals_home, under, cut 2.0): game, book, line, price, T
              and the market-fair probability
  pricing     the lab's own team_total_dist for each season (same rows, same
              probabilities)

It also states, on the matched bets, the decision lead (each must be a
'decide' under the live timing) and the EV floor at the 2026-27 uplift
(models.honest_ev.gate, as the card applies it: p_model x decimal - 1 against
config.MODEL_OWN_EV_FLOOR, a push scored as a loss), and grades the live bets
on the home team's final score (scripts.nba_game_harness.grade).

    NBA_RESEARCH_CACHE=... python -m scripts.nba_team_total_luck_replay [--seasons 2026 ...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import models.nba_team_total_luck as tt  # noqa: E402
from models import nba_book_numbers as NB  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_team_total_luck_build import BETS, cell_bets  # noqa: E402
from scripts.nba_total_luck_replay import FrameConn  # noqa: E402

LAB_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)        # the lab's full-game load (P3 --full)
REPLAY_SEASONS = (2024, 2025, 2026)
TT_MARKETS = ("team_totals_home", "team_totals_away")


def lab_bets(path: Path = BETS) -> pd.DataFrame:
    return cell_bets(path)


def split_archive(rows: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """The archived rows through the live write-time split, one fetch (one
    purchase instant) at a time. -> (rows as stored live, counts)."""
    main, alt = [], []
    for _, grp in rows.groupby("created_at", sort=True):
        m, a = NB.split_main_rungs(grp.to_dict("records"))
        main += m
        alt += a
    out = pd.DataFrame(main + alt, columns=rows.columns)
    counts = {"rows": int(len(rows)), "main": len(main), "alternate": len(alt),
              "by_market": out["market"].value_counts().to_dict()}
    return out, counts


def load(cache: Path = H.CACHE) -> dict:
    """Everything the replay reads, loaded once."""
    from scripts import nba_game4_p3 as P3
    data = H.load(cache, seasons=LAB_SEASONS, require_seasons=LAB_SEASONS)   # the lab's own load
    games_p = H.with_periods(data.games, cache)
    pe, graded = P3.load_derivatives(games_p, cache)
    times = H.per_event_times(pe, P3.POINT)
    o = pd.read_parquet(cache / "nba_odds.parquet")
    o = o[(o["source"] == H.PER_EVENT_SOURCE) & (o["snapshot_type"] != "in_play")
          & o["market"].isin(TT_MARKETS) & o["game_id"].isin(set(data.games["game_id"]))].copy()
    o["created_at"] = o["snapshot_at"]                     # the live table's meaning
    for c in ("over_link", "under_link"):
        o[c] = None                                       # the purchase kept no links
    rows, split = split_archive(o[list(tt.QUOTE_ROW_COLS)])
    box = pd.read_parquet(cache / "nba_player_game_log.parquet",
                          columns=["game_id", "team", *tt.BOX_COLS])
    sched = pd.read_parquet(cache / "nba_schedule.parquet",
                            columns=["game_id", "season", "game_type", "game_date",
                                     "home_team", "away_team", "status_text"])
    games = pd.read_parquet(cache / "nba_games.parquet",
                            columns=["game_id", "season", "game_date", "home_team", "away_team",
                                     "home_score", "away_score"])
    return {"data": data, "games_p": games_p, "pe": pe, "graded": graded, "times": times,
            "rows": rows, "split": split, "box": box, "schedule": sched, "games": games}


def lab_home_parts(ld: dict) -> pd.Series:
    """The lab's home part per game, computed the lab's way: one projection
    over every graded season (scripts.nba_game4_p3.full)."""
    from scripts import nba_game2_luck as L
    from scripts import nba_game4_p3 as P3
    data = ld["data"]
    graded_games = data.games[data.games["season"].isin(ld["graded"])]
    proj = L.f4_projections(graded_games, L.team_box(ld["box"], data.games))
    s = P3.f4_signal(proj)
    return s[s["market"] == tt.MARKET].set_index("game_id")["strength"]


def pricing_matches(ld: dict, art: dict, seasons) -> dict:
    """The artifact's distribution against the lab's own team_total_dist."""
    from scripts.nba_game2_market import team_total_dist
    lab = team_total_dist(H.pinnacle_close(ld["data"]), ld["games_p"])
    out = {}
    for s in seasons:
        a, b = tt.pricing_dist(art, s), lab[(int(s), tt.MARKET)]
        out[int(s)] = bool(a.n == b.n and np.array_equal(a.win_whole, b.win_whole)
                           and np.array_equal(a.push_whole, b.push_whole)
                           and np.array_equal(a.win_half, b.win_half))
    return out


def main_rungs_match(ld: dict, season: int) -> bool:
    """The rows the live split stores under team_totals_home are exactly the
    lab's main rungs (models.nba_book_numbers.main_rungs on its own load)."""
    games = ld["data"].games[ld["data"].games["season"] == season]
    pe = ld["pe"]
    lab = NB.main_rungs(pe[(pe["market"] == tt.MARKET) & pe["game_id"].isin(set(games["game_id"]))])
    live = tt.quote_frame(ld["rows"], games)
    key = ["game_id", "book", "fetch_at", "line", "price_a", "price_b", "coherent"]
    a = lab[key].sort_values(key).reset_index(drop=True)
    b = live[key].sort_values(key).reset_index(drop=True)
    return bool(len(a) == len(b) and a.equals(b))


def replay(ld: dict, season: int, art: dict | None = None) -> dict:
    data, box = ld["data"], ld["box"]
    art = art or tt.load_artifact()
    games = data.games[data.games["season"] == season]
    times = ld["times"][ld["times"]["game_id"].isin(set(games["game_id"]))]
    quotes = tt.quote_frame(ld["rows"], games)
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
    # 2023-24 has no graded season before it to fit an uplift on; it moves only
    # the written probability, never the bet, so 0 is used there.
    prior = [s for s in art["bucket"] if int(s) < season]
    bets, decisions, diag = tt.decide(targets, quotes, season_box, final, times, art,
                                      scheduled=sched,
                                      bucket_uplift=None if prior else 0.0)

    lab_part = ld.get("lab_parts")
    if lab_part is None:
        lab_part = ld["lab_parts"] = lab_home_parts(ld)
    live_part = {d.game_id: d.home_part for d in decisions if d.home_part is not None}
    in_t = lab_part[lab_part.index.isin(targets["game_id"])]
    common = sorted(set(live_part) & set(in_t.index))
    diff = np.array([abs(live_part[g] - in_t[g]) for g in common])
    only_lab = sorted(set(in_t.index) - set(live_part))
    only_live = sorted(set(live_part) - set(lab_part.index))

    lb = lab_bets()
    lb = lb[lb["season"] == season]
    key = ["game_id", "book", "line", "price"]
    live = pd.DataFrame([{"game_id": b.game_id, "book": b.book, "line": b.line, "price": b.price,
                          "T": b.fetch_at, "p_fair": b.p_fair, "home_part": b.home_part}
                         for b in bets], columns=key + ["T", "p_fair", "home_part"])
    m = lb[key + ["T", "p_win"]].merge(live, on=key, how="outer", indicator=True)
    both = m[m["_merge"] == "both"]
    t_ok = bool((pd.to_datetime(both["T_x"], utc=True)
                 == pd.to_datetime(both["T_y"], utc=True)).all())
    p_ok = bool(np.allclose(both["p_win"], both["p_fair"], atol=1e-9)) if len(both) else True

    tips = games.set_index("game_id")["tip"]
    leads = [tt.lead_minutes(tips[b.game_id], b.fetch_at) for b in bets]
    timing = [tt.timing(tips[b.game_id], b.fetch_at, b.fetch_at) for b in bets]
    # The card's EV floor (models.honest_ev.gate, as scripts/nba_total_luck_card.py
    # applies it) on each bet's probability at the 2026-27 uplift.
    from models.honest_ev import gate
    u27 = tt.uplift(art, 2027)
    gates = [(b, gate(tt.MODEL_ID, b.p_fair + u27, b.price)) for b in bets]
    below = [{"game_id": b.game_id, "book": b.book, "line": b.line, "price": b.price,
              "ev": round(g.ev, 4), "floor": g.floor} for b, g in gates if not g.clears]
    graded = H.grade(pd.DataFrame([{"game_id": b.game_id, "season": season,
                                    "market": tt.MARKET, "side": tt.SIDE, "line": b.line,
                                    "price": b.price, "book": b.book} for b in bets],
                                  columns=["game_id", "season", "market", "side", "line",
                                           "price", "book"]), games)
    return {
        "season": season, "games_decided": int(diag["games"]), "diag": diag,
        "decisions": len(decisions),
        "decisions_with_an_offer": sum(1 for d in decisions if d.book is not None),
        "load_season_is_the_lab_population": bool(same_population),
        "load_season_games": int(len(final)), "lab_games": int(len(lab_final)),
        "home_part_compared": len(common),
        "home_part_max_abs_diff": float(diff.max()) if len(diff) else 0.0,
        "home_part_only_lab": only_lab, "home_part_only_live": only_live,
        "live_home_parts": {g: float(v) for g, v in live_part.items()},
        "lab_bets": int(len(lb)), "live_bets": int(len(live)),
        "bets_matched": int((m["_merge"] == "both").sum()),
        "lab_only": m[m["_merge"] == "left_only"][key].to_dict("records"),
        "live_only": m[m["_merge"] == "right_only"][key].to_dict("records"),
        "decision_time_identical": t_ok, "fair_probability_identical": p_ok,
        "lead_min": (round(min(leads), 1), round(float(np.median(leads)), 1),
                     round(max(leads), 1)) if leads else None,
        "every_bet_decides_under_live_timing": all(x == "decide" for x in timing),
        "below_ev_floor_at_2026_27_uplift": below,
        "record": graded["result"].value_counts().to_dict(),
        "units": round(float(graded["units"].sum()), 2),
        "risk": round(float(graded["risk"].sum()), 2),
        "main_rungs_are_the_labs": main_rungs_match(ld, season),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", type=int, nargs="+", default=list(REPLAY_SEASONS))
    a = ap.parse_args()
    ld = load()
    art = tt.load_artifact()
    print("split:", ld["split"])
    print("pricing equals the lab's team_total_dist:", pricing_matches(ld, art, a.seasons))
    tot = {"lab_bets": 0, "live_bets": 0, "bets_matched": 0, "units": 0.0, "risk": 0.0}
    below = []
    for s in a.seasons:
        r = replay(ld, s, art)
        print({k: v for k, v in r.items() if k != "live_home_parts"})
        for k in tot:
            tot[k] += r[k]
        below += r["below_ev_floor_at_2026_27_uplift"]
    tot["units"], tot["risk"] = round(tot["units"], 2), round(tot["risk"], 2)
    roi = 100.0 * tot["units"] / tot["risk"] if tot["risk"] else float("nan")
    print(f"pooled: {tot} ({roi:+.1f}%) | below the EV floor at the 2026-27 uplift: {below}")


if __name__ == "__main__":
    main()

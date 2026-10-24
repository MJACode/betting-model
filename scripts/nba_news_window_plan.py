"""The 5-minute fetch plan around NBA injury-report changes (docs/nba_models_2026.md section 11).

An EVENT is a change between two consecutive submitted injury reports of one team for one
game that moves the team's expected minutes (sum over listed players of P(plays) x his
minutes per game, as of the game) enough that the implied spread move, 2.26 points per 48
minutes (section 4.1), summed over both teams at that report, is at least MIN_MOVE points.
Around each event's printed report time R the plan asks for the whole slate at
R-5, R, R+5, ..., R+25 minutes (the feed's snapshot spacing), dropping instants within 15
minutes of that game's tip and instants already bought. The worker's purchase
(data/ingestors/nba_odds_history.py --instants) reads the file this writes and buys each
instant once (_buy_snapshot re-checks both ledgers).

    PYTHONPATH=. python -m scripts.nba_news_window_plan --seasons 2025 2026 \\
        --out jobs/nba_news_windows_2025_2026.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

K_PTS_PER_MIN = 2.26 / 48.0
P_PLAY = {"Out": 0.0, "Doubtful": 0.1, "Questionable": 0.5, "Probable": 0.95, "Available": 1.0}
MIN_MOVE = 0.5
OFFSETS_MIN = (-5, 0, 5, 10, 15, 20, 25)
TIP_MARGIN_MIN = 15
CACHE = Path(os.environ.get("NBA_RESEARCH_CACHE", str(ROOT / "data" / "local" / "nba")))


def player_minutes(adv: pd.DataFrame) -> pd.DataFrame:
    """(player_id, season, game_date, mpg): mean minutes over the player's last 10 played
    games of the season BEFORE this game; fewer than 3 such games -> last season's mean."""
    a = adv[adv["game_type"].eq("regular") | adv["game_type"].isna()].copy()
    a["player_id"] = a["player_id"].astype(str)
    a["min"] = np.where(a["played"].fillna(False).astype(bool), a["minutes_exact"].astype(float), np.nan)
    a = a.sort_values(["player_id", "season", "game_date"])
    g = a.groupby(["player_id", "season"])["min"]
    a["n_prev"] = g.transform(lambda s: s.notna().cumsum().shift(1).fillna(0))
    a["m10"] = g.transform(lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    prior = a.groupby(["player_id", "season"])["min"].mean().rename("prior_mean").reset_index()
    prior["season"] = prior["season"] + 1
    a = a.merge(prior, on=["player_id", "season"], how="left")
    a["mpg"] = np.where(a["n_prev"] >= 3, a["m10"], a["prior_mean"])
    return a[["player_id", "season", "game_date", "mpg"]]


def asof_mpg(players: pd.DataFrame, mins: pd.DataFrame) -> np.ndarray:
    """mpg for (player_id, season, game_date) rows: the player's row on or before game_date
    (that row's value is built from games strictly before it)."""
    m = mins.dropna(subset=["mpg"]).copy()
    m["gd"] = pd.to_datetime(m["game_date"])
    m = m.sort_values("gd")
    p = players.copy()
    p["_k"] = np.arange(len(p))
    p["gd"] = pd.to_datetime(p["game_date"])
    out = pd.merge_asof(p.sort_values("gd"), m[["player_id", "season", "gd", "mpg"]],
                        on="gd", by=["player_id", "season"], direction="backward")
    return out.set_index("_k")["mpg"].reindex(p["_k"]).to_numpy()


def team_changes(ir: pd.DataFrame, mins: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """(game_id, team, report_ts, d_min): the change in expected minutes between consecutive
    SUBMITTED reports of one team for one game. A player absent from a submitted report is
    available; a team marked NOT YET SUBMITTED contributes no report at that time."""
    ir = ir[ir["game_id"].isin(set(games["game_id"]))].copy()
    ir["report_ts"] = pd.to_datetime(ir["report_ts"], utc=True)
    nys = ir["status"].eq("NOT YET SUBMITTED")
    submitted = ir.loc[~nys, ["game_id", "team", "report_ts"]].drop_duplicates()
    rows = ir[~nys & ir["player_id"].notna() & ir["status"].isin(P_PLAY)].copy()
    rows["player_id"] = rows["player_id"].astype(str)
    rows["p"] = rows["status"].map(P_PLAY)
    gd = games.set_index("game_id")["game_date"].astype(str)
    plist = rows[["game_id", "team", "player_id", "season"]].drop_duplicates()
    plist["game_date"] = plist["game_id"].map(gd)
    plist["mpg"] = np.nan_to_num(asof_mpg(plist[["player_id", "season", "game_date"]], mins), nan=0.0)
    grid = submitted.merge(plist, on=["game_id", "team"])
    grid = grid.merge(rows[["game_id", "team", "player_id", "report_ts", "p"]],
                      on=["game_id", "team", "player_id", "report_ts"], how="left")
    grid["p"] = grid["p"].fillna(1.0)
    grid["e_min"] = grid["p"] * grid["mpg"]
    tr = grid.groupby(["game_id", "team", "report_ts"]).agg(e_min=("e_min", "sum")).reset_index()
    tr = tr.sort_values(["game_id", "team", "report_ts"])
    tr["d_min"] = tr.groupby(["game_id", "team"])["e_min"].diff()
    return tr.dropna(subset=["d_min"])


def events(ir: pd.DataFrame, adv: pd.DataFrame, games: pd.DataFrame,
           min_move: float = MIN_MOVE) -> pd.DataFrame:
    """(game_id, report_ts, s, tip, season): s = the implied change in the HOME margin, both
    teams' changes at that report summed; kept when |s| >= min_move and the report is
    printed at least 30 minutes before tip."""
    tc = team_changes(ir, player_minutes(adv), games)
    g = games.set_index("game_id")
    home = tc["team"].to_numpy() == g.loc[tc["game_id"], "home_team"].to_numpy()
    tc["s"] = np.where(home, 1.0, -1.0) * tc["d_min"] * K_PTS_PER_MIN
    e = tc.groupby(["game_id", "report_ts"]).agg(s=("s", "sum")).reset_index()
    e["tip"] = e["game_id"].map(g["tip"])
    e["season"] = e["game_id"].map(g["season"]).astype(int)
    keep = (e["s"].abs() >= min_move - 1e-12) & (e["report_ts"] < e["tip"] - pd.Timedelta(minutes=30))
    return e[keep].reset_index(drop=True)


def instants(ev: pd.DataFrame, held=()) -> list[pd.Timestamp]:
    """Every R + offset (5-minute grid) before its game's tip - TIP_MARGIN_MIN, none held."""
    want = set()
    for r in ev.itertuples(index=False):
        for k in OFFSETS_MIN:
            t = (r.report_ts + pd.Timedelta(minutes=k)).floor("5min")
            if t < r.tip - pd.Timedelta(minutes=TIP_MARGIN_MIN):
                want.add(t)
    held = {pd.Timestamp(h).tz_convert("UTC") if pd.Timestamp(h).tzinfo else pd.Timestamp(h, tz="UTC")
            for h in held}
    return sorted(want - held)


def load_cache(cache: Path, seasons) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, set]:
    g = pd.read_parquet(cache / "nba_games.parquet")
    g = g[g["home_score"].notna() & g["commence_time"].notna() & g["season"].isin(list(seasons))].copy()
    g["tip"] = pd.to_datetime(g["commence_time"], utc=True)
    ir = pd.read_parquet(cache / "nba_injury_report.parquet")
    ir = ir[ir["season"].isin(list(seasons))]
    adv = pd.read_parquet(cache / "nba_player_game_adv.parquet",
                          columns=["player_id", "season", "game_date", "team", "game_type",
                                   "played", "minutes_exact"])
    led = pd.read_parquet(cache / "nba_fetch_ledger.parquet") if (cache / "nba_fetch_ledger.parquet").exists() \
        else pd.DataFrame({"requested_at": []})
    held = set(pd.to_datetime(led["requested_at"], utc=True))
    return g, ir, adv, held


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", nargs=2, type=int, required=True, metavar=("FIRST", "LAST"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    seasons = list(range(a.seasons[0], a.seasons[1] + 1))
    g, ir, adv, held = load_cache(CACHE, seasons)
    ev = events(ir, adv, g)
    plan = instants(ev, held)
    body = {
        "what": "NBA slate fetches around injury-report changes, docs/nba_models_2026.md section 11",
        "seasons": seasons, "min_move_points": MIN_MOVE, "offsets_min": list(OFFSETS_MIN),
        "events": int(len(ev)), "events_by_season": {str(k): int(v) for k, v in ev.groupby("season").size().items()},
        "credits_per_instant": 30, "instants": [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in plan],
    }
    a.out.write_text(json.dumps(body, indent=0) + "\n", encoding="utf-8")
    print(f"{len(ev)} events, {len(plan)} instants (~{30 * len(plan):,} credits) -> {a.out}")


if __name__ == "__main__":
    main()

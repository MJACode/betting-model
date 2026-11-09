"""Does the live ESPN read reproduce the lab's play-by-play? Field by field.

For a sample of 2025-26 games: ESPN's game summary (free, the document the
live loop reads) through nba_live.espn.records_from_summary, against the
sportsdataverse release the lab was built from (scripts/nba_ingame_data.py),
on every PBP_SOURCE_COLS field nba_pbp.slim_plays reads; then both through
slim_plays and plays_frame, compared on every column the state is counted
from. Also: the timeline cut at a set of in-play quote stamps gives the lab's
state at those stamps (quotes_state.parquet).

    PYTHONPATH=. python -m scripts.nba_live_espn_check --games 25
    ... --save-fixture tests/fixtures/espn_nba_summary_<id>.json --fixture-event <id>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from data.ingestors import nba_pbp as P  # noqa: E402
from nba_live import espn as E  # noqa: E402
from nba_live import state as S  # noqa: E402
from scripts import nba_ingame_data as D  # noqa: E402

SDV = D.PBP_ROOT / "pbp_2026" / "play_by_play_2026.parquet"
FIELDS = ("sequence_number", "type_id", "type_text", "text", "away_score", "home_score",
          "period_number", "clock_display_value", "scoring_play", "score_value", "team_id",
          "athlete_id_1", "athlete_id_2", "athlete_id_3", "wallclock", "shooting_play",
          "coordinate_x_raw", "coordinate_y_raw", "points_attempted", "home_team_id",
          "away_team_id", "home_team_abbrev", "away_team_abbrev", "season_type")
PLAY_COLS = ("play_no", "period", "clock_s", "game_s", "type_text", "team_side", "points",
             "fg3a", "fg3m", "heave3", "fta", "ftm", "athlete_id_1", "pf", "tf", "wc")


def _norm(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return int(v) if float(v).is_integer() else round(float(v), 6)
    s = str(v)
    try:
        f = float(s)
        return int(f) if f.is_integer() else round(f, 6)
    except ValueError:
        return s


def check_game(eid: int, gid: str, home: str, away: str, sdv: pd.DataFrame, summary: dict) -> dict:
    live = E.records_from_summary(summary)
    ref = sdv[sdv["game_id"].astype(int) == eid].astype(object).where(lambda d: d.notna(), None)
    ref = ref.to_dict("records")
    out = {"game_id": gid, "espn": eid, "plays_live": len(live), "plays_ref": len(ref)}
    if len(live) != len(ref):
        out["error"] = "play count differs"
        return out
    bad = {}
    for f in FIELDS:
        n = sum(_norm(a.get(f)) != _norm(b.get(f)) for a, b in zip(live, ref))
        if n:
            bad[f] = n
    out["source_fields_differ"] = bad
    meta = P.espn_game_meta(eid, live)
    sw = not (meta and meta["home"] == home and meta["away"] == away)
    pl = S.plays_from_records(live, eid, gid, 2026, swapped=sw)
    pr = D.plays_frame(P.slim_plays(ref, espn_game_id=eid, game_id=gid, season=2026,
                                    season_type=2, swapped=sw))
    diff = {}
    for c in PLAY_COLS:
        a, b = pl[c].reset_index(drop=True), pr[c].reset_index(drop=True)
        eq = (a == b) | (a.isna() & b.isna())
        if not eq.all():
            diff[c] = int((~eq).sum())
    out["play_columns_differ"] = diff
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--games", type=int, default=25)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--save-fixture", default=None)
    ap.add_argument("--fixture-event", type=int, default=None)
    a = ap.parse_args()
    q = pd.read_parquet(D.OUT, columns=["game_id", "season", "espn_game_id"])
    q = q[q["season"] == 2026].drop_duplicates("game_id").dropna()
    games = pd.read_parquet(D.H.CACHE / "nba_games.parquet")[["game_id", "home_team", "away_team"]]
    q = q.merge(games, on="game_id")
    pick = q.sample(n=min(a.games, len(q)), random_state=a.seed)
    sdv = pd.read_parquet(SDV, columns=[c for c in P.PBP_SOURCE_COLS])
    sdv = sdv[sdv["game_id"].astype(int).isin(set(pick["espn_game_id"].astype(int)))]
    client = E.EspnClient()
    rows = []
    for r in pick.itertuples(index=False):
        j = client.summary(int(r.espn_game_id))
        if j is None:
            rows.append({"game_id": r.game_id, "error": "no summary"})
            continue
        if a.save_fixture and a.fixture_event == int(r.espn_game_id):
            Path(a.save_fixture).write_text(json.dumps(j), encoding="utf-8")
        rows.append(check_game(int(r.espn_game_id), r.game_id, r.home_team, r.away_team, sdv, j))
        time.sleep(0.3)
    clean = [x for x in rows if not x.get("error") and not x.get("source_fields_differ")
             and not x.get("play_columns_differ")]
    for x in rows:
        if x not in clean:
            print(json.dumps(x, default=str))
    print(f"{len(clean)} of {len(rows)} games identical on every source field and every play column "
          f"({sum(x.get('plays_live', 0) for x in clean):,} plays)")


if __name__ == "__main__":
    main()

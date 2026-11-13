"""The research cache: one read of the stored women's schedule and results, and
NCAA's team box scores parsed by the importer's own function. Everything here
is a copy of what Supabase holds (games, ncaabw_events) or is being imported
into it (ncaabw_team_game_stats), read once so the research never leans on the
production database again.

    python -m scripts.ncaabw_research.cache            
"""
import os
import sys
from pathlib import Path

import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE, SPOOL  # noqa: E402,F401

from data.db import get_connection  # noqa: E402
from data.ingestors import ncaabw_sdv_import as sdv  # noqa: E402

OUT = CACHE

with get_connection() as conn:
    rows = conn.execute("""
        SELECT g.game_id, g.season, g.game_date, g.commence_time, g.home_team, g.away_team,
               g.home_score, g.away_score, g.neutral_site, g.conference_game, g.went_to_ot,
               e.espn_event_id, e.home_espn_id, e.away_espn_id, e.status, e.season_type
          FROM games g JOIN ncaabw_events e ON e.game_id = g.game_id
         WHERE g.sport = 'NCAABW'
    """).fetchall()
    teams = conn.execute("SELECT espn_id, school, mascot, display_name, is_d1 FROM ncaabw_teams").fetchall()
cols = ["game_id", "season", "game_date", "commence_time", "home_team", "away_team", "home_score",
        "away_score", "neutral_site", "conference_game", "went_to_ot", "espn_event_id",
        "home_espn_id", "away_espn_id", "status", "season_type"]
g = pd.DataFrame([tuple(r) for r in rows], columns=cols)
g.to_parquet(OUT / "games.parquet", index=False)
pd.DataFrame([tuple(r) for r in teams],
             columns=["espn_id", "school", "mascot", "display_name", "is_d1"]).to_parquet(
    OUT / "teams.parquet", index=False)
print("games", len(g), g.groupby("season").size().to_dict())
print("scored", int(g["home_score"].notna().sum()), "| d1 teams", sum(1 for t in teams if t[4]))

parts = []
for season in range(2010, 2028):
    df = sdv._fetch_parquet(sdv.TEAM_BOX_URL.format(season=season))
    if df is None:
        print(season, "no team box file")
        continue
    sched = sdv._fetch_parquet(sdv.SCHEDULE_URL.format(season=season))
    dates = sdv.schedule_dates(sched) if sched is not None else None
    x = pd.DataFrame(sdv.team_rows(df, season, dates))
    parts.append(x)
    print(season, "box rows", len(x), "contests", x["contest_id"].nunique(),
          "espn_game_id", round(float(x["espn_game_id"].notna().mean()), 3),
          "team id", round(float(x["team_espn_id"].notna().mean()), 3))
box = pd.concat(parts, ignore_index=True)
box.to_parquet(OUT / "box.parquet", index=False)
print("box rows", len(box), "columns", list(box.columns))

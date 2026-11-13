"""This season's box coverage, read the way the totals card reads it.

For each final of the season: does a box (two rows) sit on it after
models.ncaabw_total_blend.place_box, and from which source? Then, per team,
how many finals have none, since the card holds a team that is missing two.

    python -m scripts.ncaabw_research.box_coverage [season]      (reads only)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import scripts.ncaabw_total_card as card  # noqa: E402
from data.db import get_connection  # noqa: E402

season = int(sys.argv[1]) if len(sys.argv) > 1 else 2027
with get_connection() as conn:
    games_df, box_df = card.load_season(conn, season)
    misses = pd.DataFrame(conn.execute(
        "SELECT game_id, reason FROM ncaabw_box_misses").fetchall(), columns=["game_id", "reason"])
print(f"season {season}: games {len(games_df)}, stored box rows {len(box_df)} "
      f"({box_df.groupby('source').size().to_dict()})")
sg, box = card.prepare_season(games_df, box_df)
placed = box[box["game_id"].notna()]
print(f"rows kept after one-source-per-game: {len(box)} ({box.groupby('source').size().to_dict()}); "
      f"on a stored game: {len(placed)}; on none: {len(box) - len(placed)} "
      f"({box[box['game_id'].isna()].groupby('source').size().to_dict()})")
rows = placed.groupby("game_id").size()
src = placed.groupby("game_id")["source"].first()
fin = sg[sg["home_score"].notna()].copy()
fin["box_rows"] = fin["game_id"].map(rows).fillna(0).astype(int)
fin["source"] = fin["game_id"].map(src)
print(f"finals {len(fin)}: with a box {int((fin['box_rows'] >= 2).sum())} "
      f"({fin[fin['box_rows'] >= 2].groupby('source').size().to_dict()}), "
      f"one row only {int((fin['box_rows'] == 1).sum())}, none {int((fin['box_rows'] == 0).sum())}; "
      f"with possessions {int(fin['poss'].notna().sum())}")
both = box_df.copy()
print("games both sources hold:", int((box.groupby("_key")["source"].nunique() > 1).sum()),
      "(must be 0 after place_box)")
no = fin[fin["box_rows"] < 2]
teams = pd.concat([no["home_espn_id"], no["away_espn_id"]]).dropna().astype(int).value_counts()
print(f"teams missing 1: {int((teams == 1).sum())}, 2+: {int((teams >= 2).sum())}"
      + (f" {teams[teams >= 2].to_dict()}" if (teams >= 2).any() else ""))
big = no[(no["n_sched_home"] >= 10) & (no["n_sched_away"] >= 10)]
print(f"finals without a box between two teams with 10+ scheduled games: {len(big)}")
for r in no.merge(misses, on="game_id", how="left").itertuples(index=False):
    print(f"  {r.game_id} ({r.game_date}) rows {r.box_rows} sched {r.n_sched_home}/{r.n_sched_away}: "
          f"{r.reason if isinstance(r.reason, str) else 'no ESPN miss recorded'}")
# ESPN's refused games that NCAA's rows cover
ref = misses[misses["game_id"].isin(set(fin["game_id"]))]
cov = ref.merge(fin[["game_id", "box_rows", "source"]], on="game_id")
print(f"ESPN refused {len(ref)} of this season's finals; NCAA's rows hold "
      f"{int((cov['box_rows'] >= 2).sum())} of them")

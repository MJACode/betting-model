"""The shot charts in the research cache, and the halftime window they give.

  shots.parquet     euroleague_shots, read once by game id
  halftime.parquet  one row a game: the UTC time of the last shot of the
                    second quarter (minute <= 20) and of the first shot of the
                    third (minute >= 21), the half-time score from the
                    quarter scores, and the gap between the two shots. A
                    halftime decision is read from the in-play snapshots that
                    fall inside that window.

    python -m scripts.euroleague_research.cache_shots
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.euroleague_research._paths import CACHE  # noqa: E402

from data.db import get_connection  # noqa: E402

BATCH = 100
COLS = ["game_id", "num_anot", "team", "action", "points", "minute", "console",
        "points_home", "points_away", "shot_utc"]


def main() -> None:
    with get_connection() as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT game_id FROM euroleague_shot_fetches WHERE status = 'ok'").fetchall()]
        conn.commit()
        rows = []
        for i in range(0, len(ids), BATCH):
            rows += [tuple(r) for r in conn.execute(
                f"SELECT {', '.join(COLS)} FROM euroleague_shots WHERE game_id = ANY(%s)",
                (ids[i:i + BATCH],)).fetchall()]
            conn.commit()
    s = pd.DataFrame(rows, columns=COLS)
    s["shot_utc"] = pd.to_datetime(s["shot_utc"], utc=True)
    s.to_parquet(CACHE / "shots.parquet", index=False)
    q2 = s[s["minute"] <= 20].groupby("game_id")["shot_utc"].max().rename("last_q2_shot")
    q3 = s[s["minute"] >= 21].groupby("game_id")["shot_utc"].min().rename("first_q3_shot")
    ht = pd.concat([q2, q3], axis=1).reset_index()
    p = pd.read_parquet(CACHE / "periods.parquet")
    h1 = (p[p["period"] <= 2].groupby("game_id")[["home_points", "away_points"]].sum()
          .rename(columns={"home_points": "ht_home", "away_points": "ht_away"}).reset_index())
    ht = ht.merge(h1, on="game_id", how="left")
    ht["break_minutes"] = (ht["first_q3_shot"] - ht["last_q2_shot"]).dt.total_seconds() / 60
    ht.to_parquet(CACHE / "halftime.parquet", index=False)
    print("shots", len(s), "games", s["game_id"].nunique())
    print("halftime rows", len(ht), "| both shots", int(ht[["last_q2_shot", "first_q3_shot"]].notna().all(axis=1).sum()))
    print("break minutes:", ht["break_minutes"].describe().round(1).to_dict())


if __name__ == "__main__":
    main()

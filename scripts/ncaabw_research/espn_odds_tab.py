"""ESPN's own odds, tabulated: for each season read, how many games carry a
line from a sportsbook provider (not the projection provider), by month, and
how that line did against the final (as a check that it is a market line)."""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE, SPOOL  # noqa: E402,F401

g = pd.read_parquet(CACHE / "games.parquet")
g = g[g["home_score"].notna()].copy()
g["margin"] = g["home_score"].astype(float) - g["away_score"].astype(float)
g["total"] = g["home_score"].astype(float) + g["away_score"].astype(float)
g["month"] = g["game_date"].astype(str).str[:7]
gi = g.set_index("espn_event_id")
PROJECTION = {"accuscore", "numberfire", "teamrankings", "consensus"}
PRIORITY = ["ESPN BET", "DraftKings", "BetfairSportsbook", "Caesars Sportsbook", "MGM",
            "Caesars Sportsbook (New Jersey)", "SugarHouse", "Unibet", "Westgate"]

rows = []
prov_all = Counter()
for season in [int(a) for a in sys.argv[1:]]:
    f = CACHE / f"espn_odds_{season}.jsonl"
    if not f.exists():
        continue
    for line in open(f, encoding="utf-8"):
        rec = json.loads(line)
        items = {(it.get("provider") or {}).get("name"): it for it in rec["items"]}
        for name in items:
            prov_all[(season, name)] += 1
        pick = next((items[p] for p in PRIORITY if p in items), None)
        if pick is None or rec["event"] not in gi.index:
            continue
        h = pick.get("homeTeamOdds") or {}
        a = pick.get("awayTeamOdds") or {}
        spread = pick.get("spread")
        fav_home = h.get("favorite")
        home_line = None
        if spread is not None and fav_home is not None:
            home_line = -abs(float(spread)) if fav_home else abs(float(spread))
        rows.append({"event": rec["event"], "season": season,
                     "provider": (pick.get("provider") or {}).get("name"),
                     "home_line": home_line, "total_line": pick.get("overUnder"),
                     "home_ml": h.get("moneyLine"), "away_ml": a.get("moneyLine")})
E = pd.DataFrame(rows).merge(g[["espn_event_id", "month", "margin", "total"]],
                             left_on="event", right_on="espn_event_id")
for season, n in sorted(Counter(k[0] for k in prov_all.elements()).items()):
    print(season, "provider rows:", {k[1]: v for k, v in prov_all.items() if k[0] == season})
games_by_month = g.groupby("month").size()
tab = E.groupby("month").agg(with_book=("event", "size"), spread=("home_line", "count"),
                             total=("total_line", "count"), ml=("home_ml", "count"))
tab["games"] = games_by_month.reindex(tab.index)
print(tab[["games", "with_book", "spread", "total", "ml"]].to_string())
for season, x in E.groupby("season"):
    s = x.dropna(subset=["home_line"]); t = x.dropna(subset=["total_line"])
    e = s["margin"] + s["home_line"]
    et = t["total"] - t["total_line"].astype(float)
    print(f"{season}: spread on {len(s)} games: mean error {e.mean():+.2f}, MAE {e.abs().mean():.2f}, "
          f"home covers {(e > 0).mean():.3f} | total on {len(t)}: mean error {et.mean():+.2f}, "
          f"MAE {et.abs().mean():.2f}, over {(et > 0).mean():.3f} | by provider "
          f"{x['provider'].value_counts().to_dict()}")
E.to_parquet(CACHE / "espn_lines.parquet", index=False)

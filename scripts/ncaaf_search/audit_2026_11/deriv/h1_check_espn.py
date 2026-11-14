"""Check the play-by-play half-time scores against ESPN's quarter scores on a sample of dates.

A CHECK, not a data source: a handful of Saturdays per season from ESPN's public scoreboard (no key),
matched to our games on the ET date and the final score, then compared on the half-time score.
Nothing is kept beyond the printed agreement.

    python h1_check_espn.py 2025-09-06 2025-10-11 ...
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CACHE  # noqa: E402

URL = ("https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
       "?dates={d}&groups={grp}&limit=400")


def board(date: str) -> list[dict]:
    out = {}
    for grp in (80, 81):          # FBS, FCS
        req = urllib.request.Request(URL.format(d=date.replace("-", ""), grp=grp),
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            js = json.load(r)
        for e in js.get("events", []):
            c = e["competitions"][0]
            if not c.get("status", {}).get("type", {}).get("completed"):
                continue
            side = {t["homeAway"]: t for t in c["competitors"]}
            try:
                ls_h = [int(float(x["value"])) for x in side["home"].get("linescores", [])]
                ls_a = [int(float(x["value"])) for x in side["away"].get("linescores", [])]
                out[e["id"]] = dict(home=side["home"]["team"].get("location"), away=side["away"]["team"].get("location"),
                                    fh=int(side["home"]["score"]), fa=int(side["away"]["score"]),
                                    h1h=sum(ls_h[:2]), h1a=sum(ls_a[:2]), q=len(ls_h))
            except (KeyError, ValueError):
                continue
        time.sleep(0.4)
    return list(out.values())


def main():
    dates = sys.argv[1:]
    h = pd.read_parquet(CACHE / "h1_scores.parquet")
    g = pd.read_parquet(CACHE / "g.parquet")[["game_id", "et_date", "game_date", "home_team", "away_team"]]
    h = h.merge(g, on="game_id", how="left")
    tot = dict(espn=0, ours=0, both=0, agree=0)
    bad = []
    for d in dates:
        ev = board(d)
        mine = h[(h.et_date == d) | (h.game_date == d)]
        key = {}
        for e in ev:
            key.setdefault((e["fh"], e["fa"]), []).append(e)
        n_both = n_ok = 0
        for r in mine.itertuples(index=False):
            c = key.get((int(r.fin_home), int(r.fin_away)), [])
            if len(c) != 1:
                continue
            e = c[0]
            n_both += 1
            if (e["h1h"], e["h1a"]) == (int(r.h1_home), int(r.h1_away)):
                n_ok += 1
            else:
                bad.append((d, r.home_team, r.away_team, f"ours {int(r.h1_home)}-{int(r.h1_away)}",
                            f"espn {e['h1h']}-{e['h1a']}", f"final {e['fh']}-{e['fa']}"))
        print(f"{d}: espn finals {len(ev)}, ours with a half-time score {len(mine)}, matched on the final {n_both}, "
              f"half-time equal {n_ok}")
        tot["espn"] += len(ev)
        tot["ours"] += len(mine)
        tot["both"] += n_both
        tot["agree"] += n_ok
    print("TOTAL", tot, "| agreement", round(tot["agree"] / max(tot["both"], 1), 4))
    for b in bad[:25]:
        print("  differs:", b)


if __name__ == "__main__":
    main()

"""ESPN's own odds for the women's games of 2022-23 and 2023-24: one free call a
game to ESPN's core API. Saves every answer raw (cache/espn_odds_<season>.jsonl,
one line a game) and stops at the first 403 or 429, which a re-run resumes
after. Gentle: four requests in flight, each followed by a short pause.

    python -m scripts.ncaabw_research.espn_odds 2023 2024
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE, SPOOL  # noqa: E402,F401

URL = ("https://sports.core.api.espn.com/v2/sports/basketball/leagues/"
       "womens-college-basketball/events/{e}/competitions/{e}/odds")
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0"
stop = {"why": None}


def one(eid):
    if stop["why"]:
        return eid, None, None
    for attempt in range(3):
        try:
            r = S.get(URL.format(e=eid), params={"limit": 30}, timeout=30)
        except requests.RequestException:
            time.sleep(1 + attempt)
            continue
        if r.status_code in (403, 429):
            stop["why"] = f"HTTP {r.status_code}"
            return eid, r.status_code, None
        time.sleep(0.12)
        if r.status_code == 200:
            return eid, 200, r.json().get("items", [])
        return eid, r.status_code, None
    return eid, None, None


g = pd.read_parquet(CACHE / "games.parquet")
for season in [int(a) for a in sys.argv[1:]]:
    out = CACHE / f"espn_odds_{season}.jsonl"
    have = set()
    if out.exists():
        with open(out, encoding="utf-8") as f:
            have = {json.loads(line)["event"] for line in f}
    ids = [int(e) for e in g[(g["season"] == season) & g["home_score"].notna()]["espn_event_id"]
           if int(e) not in have]
    print(f"season {season}: {len(have)} held, {len(ids)} to ask", flush=True)
    n = 0
    with open(out, "a", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=4) as ex:
        for eid, status, items in ex.map(one, ids):
            if status in (200, 404):
                f.write(json.dumps({"event": eid, "status": status, "items": items or []}) + "\n")
                n += 1
                if n % 500 == 0:
                    f.flush()
                    print(f"  {season}: {n} asked", flush=True)
    print(f"season {season}: asked {n}; stopped: {stop['why']}", flush=True)
    if stop["why"]:
        break

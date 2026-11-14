"""How often would the card see a NON-UFC fight it could bet? The feed's MMA
key carries every promotion. The card keeps a fight whose two fighters both
resolve to a ufcstats record; a bout between two of them in another
promotion would never be settled by the UFC results feed.

On the bought spool: every event at least a week out that Pinnacle and a
deciding book priced, whose two names are both in the fighters table, split
by whether it was a UFC fight (placed on ufc_fight_log) or not.

    python non_ufc_events.py <spool dir>      (run from the study folder)
"""
import gzip
import json
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))
from data.ingestors import ufc_odds_history as H  # noqa: E402

spool = Path(sys.argv[1])
F = pd.read_parquet("fights.parquet")
FT = pd.read_parquet("fighters.parquet")
known = set(FT.slug.dropna()) | {H.slugify(n) for n in FT.name.dropna()}
index = H.FightIndex([(r.game_id, str(r.date)[:10], r.a_name, r.b_name) for r in F.itertuples()])
DEC = {"draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers", "hardrockbet"}
seen = {}
for p in sorted((spool / "daily").glob("*.json.gz")):
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        body = json.load(fh)
    served = H._utc(body.get("timestamp"))
    for ev in body.get("data") or []:
        ct = H._utc(ev.get("commence_time"))
        if ct is None or served is None or ct - served < timedelta(days=7):
            continue
        books = {b["key"] for b in ev.get("bookmakers") or [] if any(m["key"] == "h2h" for m in b.get("markets") or [])}
        if "pinnacle" not in books or not (books & DEC):
            continue
        h, a = ev.get("home_team") or "", ev.get("away_team") or ""
        if H.feed_slug(h) not in known or H.feed_slug(a) not in known:
            continue
        seen[ev["id"]] = (ct.year, index(h, a, ct) is not None, h, a, ct.date())
D = pd.DataFrame(seen.values(), columns=["year", "ufc", "home", "away", "date"])
print(D.groupby(["year", "ufc"]).size().unstack(fill_value=0).rename(columns={True: "UFC", False: "not UFC"}))
print(D[~D.ufc].sort_values("date").tail(15).to_string(index=False))

# Is there a logged UFC card within a day of each event that was not a UFC
# fight? If so the settlement can tell it did not happen on that card.
cards = sorted(set(pd.to_datetime(F.date).dt.date))
import bisect
def near_card(d):
    i = bisect.bisect_left(cards, d - timedelta(days=1))
    return i < len(cards) and cards[i] <= d + timedelta(days=1)
D["card_near"] = D.date.map(near_card)
N = D[~D.ufc]
print(f"not-UFC events {len(N)}: with a logged UFC card within a day {N.card_near.sum()} "
      f"({N.card_near.mean():.0%}), without {(~N.card_near).sum()}")
print(N[~N.card_near].groupby("year").size().to_dict())
print(N[~N.card_near].sort_values("date").tail(12).to_string(index=False))

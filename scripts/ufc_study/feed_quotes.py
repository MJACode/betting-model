"""The bought feed history (data/ingestors/ufc_odds_history.py) as one row per
UFC fight, book, market and pull, prices oriented to fighter A (the smaller
slug, as fights.parquet). Reads the purchase's spool, which is a cache of
ufc_odds_history: every snapshot in full, so the price at any pull is a
lookup, not a reconstruction. Writes feed_quotes.parquet in the working
directory.

    python feed_quotes.py <spool dir>
"""
import gzip
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))
from data.ingestors import ufc_odds_history as H  # noqa: E402

spool = Path(sys.argv[1])
F = pd.read_parquet("fights.parquet")
index = H.FightIndex([(r.game_id, str(r.date)[:10], r.a_name, r.b_name) for r in F.itertuples()])
a_slug = {r.game_id: H.slugify(r.a_name) for r in F.itertuples()}

rows = []
for stage in H.STAGES:
    for p in sorted((spool / stage).glob("*.json.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            body = json.load(fh)
        for r in H.quote_rows(body, index):
            if not r["game_id"]:
                continue
            a_home = H.feed_slug(r["home_name"]) == a_slug[r["game_id"]]
            rows.append(dict(
                game_id=r["game_id"], event_id=r["event_id"], stage=stage,
                served_at=r["served_at"], commence=r["commence_time"], book=r["bookmaker"],
                market=r["market"],
                pa=r["home_price"] if a_home else r["away_price"],
                pb=r["away_price"] if a_home else r["home_price"],
                line=r["total_line"], over=r["over_price"], under=r["under_price"]))
Q = pd.DataFrame(rows)
Q.to_parquet("feed_quotes.parquet")
print(len(Q), "quote rows,", Q.game_id.nunique(), "UFC fights,",
      Q.served_at.nunique(), "pulls;", Q.groupby("market").game_id.nunique().to_dict())

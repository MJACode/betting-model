"""Historical UFC moneyline prices (BestFightOdds via fight-canon-db), joined to
our own fight table. Output: ml_hist.parquet, one row per fight, oriented as
fights.parquet (A = smaller slug)."""
import re, sqlite3, unicodedata
import numpy as np
import pandas as pd

from _paths import CANON_DB
DB = "file:" + CANON_DB.replace("\\", "/") + "?mode=ro"
c = sqlite3.connect(DB, uri=True)
q = """
SELECT f.fight_id, e.date, e.name AS event, e.promotion, f.weight_class, f.method, f.end_round,
       f.end_time, f.scheduled_rounds, fp.fighter_id, fp.corner, fr.name, o.open, o.close_low, o.close_high,
       fp.result
FROM fights f JOIN events e USING(event_id)
JOIN fight_participants fp USING(fight_id)
JOIN fighters fr ON fr.fighter_id = fp.fighter_id
LEFT JOIN odds o ON o.fight_id = f.fight_id AND o.fighter_id = fp.fighter_id AND o.book = 'all'
WHERE e.promotion = 'UFC'
"""
try:
    D = pd.read_sql(q, c)
except Exception as exc:
    print("query failed:", exc)
    print(pd.read_sql("select sql from sqlite_master where name='fight_participants'", c).iloc[0, 0])
    raise
print(D.head(3).T); print(len(D), D.fight_id.nunique())


def slugify(n):
    n = unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


D["slug"] = D.name.map(slugify)
W = []
for fid, g in D.groupby("fight_id"):
    if len(g) != 2:
        continue
    g = g.sort_values("slug")
    a, b = g.iloc[0], g.iloc[1]
    W.append(dict(cfid=fid, date=a.date, event=a.event, a_slug=a.slug, b_slug=b.slug,
                  a_open=a.open, b_open=b.open, a_close_lo=a.close_low, a_close_hi=a.close_high,
                  b_close_lo=b.close_low, b_close_hi=b.close_high, c_result_a=a.result))
W = pd.DataFrame(W)
W["date"] = pd.to_datetime(W.date)
print("UFC fights in canon", len(W), "with open both sides", (W.a_open.notna() & W.b_open.notna()).sum(),
      "with close both", (W.a_close_lo.notna() & W.b_close_lo.notna()).sum())

F = pd.read_parquet("fights.parquet")
F["a_slug"] = F.a_name.map(slugify); F["b_slug"] = F.b_name.map(slugify)
key = lambda s: s.a_slug + "|" + s.b_slug
F["k"] = key(F); W["k"] = key(W)
M = F.merge(W.drop(columns=["a_slug", "b_slug"]), on="k", suffixes=("", "_c"))
M = M[(M.date - M.date_c).dt.days.abs() <= 2]
M = M.drop_duplicates("game_id")
print("joined to our fights", len(M), "of", len(F))
print(M.groupby(M.date.dt.year).agg(n=("game_id", "size"), open=("a_open", lambda s: s.notna().sum()),
                                     close=("a_close_lo", lambda s: s.notna().sum())).to_string())
# result agreement check
M["a_won"] = M.result_a == "win"
agree = (M.c_result_a.str.lower().str[0] == M.result_a.str[0]).mean()
print("result agreement with canon", round(agree, 4))
M.to_parquet("ml_hist.parquet")

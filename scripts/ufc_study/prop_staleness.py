"""How old is a BestFightOdds "last recorded price"? For every price history
the chart stage has stored (ufc_prop_history_ticks, a seeded sample of the
priced method, distance and round props at the five books a pick may name):
does its last price equal the page's, how long before the fight did it last
change, and did any change land after the fight started. The start is the
odds feed's latest commence time for the fight (ufc_odds_history, to
2026-06-13), else the games table's. Run from
the study folder after prop_load.py; reads the local mirror."""
import glob
import os

import pandas as pd
import pyarrow.dataset as ds

from _paths import MIRROR


def mirror(t):
    files = glob.glob(os.path.join(MIRROR, f"public.{t}", "*.parquet"))
    return ds.dataset(files, format="parquet").to_table().to_pandas()


T = mirror("ufc_prop_history_ticks")
P = mirror("ufc_prop_history")
F = mirror("ufc_prop_history_fights").set_index("matchup_id")
O = mirror("ufc_odds_history")
G = mirror("games")
G = G[G.sport == "UFC"].set_index("game_id")
start = pd.to_datetime(O[O.game_id.notna()].groupby("game_id").commence_time.max(), utc=True)
start = start.combine_first(pd.to_datetime(G.commence_time, utc=True, errors="coerce"))

key = ["matchup_id", "book_id", "prop_type", "team", "side"]
T = T.sort_values("quoted_at")
last = T.groupby(key).agg(last_at=("quoted_at", "last"), last_price=("price", "last"),
                          first_at=("quoted_at", "first"), first_price=("price", "first"),
                          changes=("price", "size")).reset_index()
last = last.merge(P[key + ["price", "bookmaker"]], on=key, how="left")
last["game_id"] = F.game_id.reindex(last.matchup_id).to_numpy()
last["start"] = start.reindex(last.game_id).to_numpy()
last["start"] = pd.to_datetime(last.start, utc=True)
last["hours_before"] = (last.start - pd.to_datetime(last.last_at, utc=True)).dt.total_seconds() / 3600
last["open_days"] = (last.start - pd.to_datetime(last.first_at, utc=True)).dt.total_seconds() / 86400
last["same_as_page"] = last.last_price == last.price
s = last[last.start.notna()]
print(f"{len(last):,} histories with at least one price; {len(s):,} on fights with a start time")
print(f"last price equals the page's: {last.same_as_page.mean():.1%}")
bands = pd.cut(s.hours_before, [-1e9, 0, 1, 6, 24, 72, 168, 1e9],
               labels=["after the start", "0-1 h", "1-6 h", "6-24 h", "1-3 days", "3-7 days", "over 7 days"])
print("\nlast change, before the fight's start:")
print((bands.value_counts(normalize=True).sort_index() * 100).round(1).to_string())
print("\nby book (median hours before the start; share over 24 h):")
print(s.groupby("bookmaker").agg(histories=("hours_before", "size"),
                                 median_h=("hours_before", "median"),
                                 over_24h=("hours_before", lambda x: (x > 24).mean())).round(2).to_string())
print(f"\nfirst price, days before the start: median {s.open_days.median():.1f}, "
      f"quartiles {s.open_days.quantile(.25):.1f}-{s.open_days.quantile(.75):.1f}; "
      f"price changes per history: median {last.changes.median():.0f}, mean {last.changes.mean():.1f}")

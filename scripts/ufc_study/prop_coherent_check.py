"""The fight-winner-coherent decision rule (mechanism 3 of prop_grade.py) taken
apart at the price an hour before each fight: the cut neighbourhood, each
year, each book, the winners it rests on, and the prices it takes. The rule
has no fitted parameter (it rescales each fighter's no-vig method prices to
the fight-winner no-vig chance), so there is no training window to leak
from; what can fool it is a cut picked after seeing the result and a handful
of long-priced winners.

Run from the study folder after `prop_leads.py tables` (needs the price
histories of the rule's bets stored and mirrored):

    python prop_coherent_check.py
"""
import glob
import os
import re
import unicodedata
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
# the last guard is prop_leads' own; an earlier one sits inside its own split
_src = (HERE / "prop_leads.py").read_text(encoding="utf-8").rsplit('if __name__ == "__main__":', 1)[0]
exec(compile(_src, str(HERE / "prop_leads.py"), "exec"))
from _paths import MIRROR  # noqa: E402


def mirror(t):
    return pd.concat(pd.read_parquet(f) for f in glob.glob(os.path.join(MIRROR, f"public.{t}", "*.parquet")))


def starts():
    """Each fight's start, as prop_leads.retime finds it."""
    O = mirror("ufc_odds_history")
    G = mirror("games")
    G = G[G.sport == "UFC"]
    start = pd.to_datetime(O[O.game_id.notna()].groupby("game_id").commence_time.max(), utc=True)
    start = start.combine_first(pd.to_datetime(G.set_index("game_id").commence_time, utc=True, errors="coerce"))
    last = lambda n: re.sub(r"[^a-z]+", " ", unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore")
                            .decode().lower()).split()[-1:] or [""]
    O["ct"] = pd.to_datetime(O.commence_time, utc=True)
    by_names = {}
    for h, w, ct in zip(O.home_name, O.away_name, O.ct):
        if pd.notna(ct):
            k = (ct.date(), frozenset(last(h) + last(w)))
            by_names[k] = max(by_names.get(k, ct), ct)
    for gid in set(X.index) - set(start.dropna().index):
        d = pd.Timestamp(X.loc[gid, "date"]).date()
        names = frozenset(last(X.loc[gid, "a_name"]) + last(X.loc[gid, "b_name"]))
        hits = [by_names[(d + timedelta(days=k), names)] for k in (0, 1, -1)
                if (d + timedelta(days=k), names) in by_names]
        if hits:
            start[gid] = max(hits)
    return start


def main():
    T = mirror("ufc_prop_history_ticks")
    T["quoted_at"] = pd.to_datetime(T.quoted_at, utc=True)
    T = T.sort_values("quoted_at")
    by = {k: g for k, g in T.groupby(["book_id", "matchup_id", "prop_type", "team", "side"])}
    start = starts()

    name = "Decision by fighter"
    rows = outcome_rows(name).reset_index(drop=True)
    p = pd.Series(coherent(rows, name), index=rows.index)
    pool = bets(rows, p, 0.02).copy()
    pool["p"] = p.reindex(pool.index)
    h1 = []
    for x in pool.itertuples():
        g = by.get((x.book_id, x.src_matchup, x.prop_type, x.src_team, x.src_side))
        st = start.get(x.game_id, pd.NaT)
        if g is None or pd.isna(st):
            h1.append(np.nan)
            continue
        g = g[g.quoted_at <= st - pd.Timedelta(hours=1)]
        h1.append(g.price_decimal.iloc[-1] if len(g) else np.nan)
    pool["h1"] = h1
    ok = pool[pool.h1.notna()].copy()
    print(f"{name}, coherent rule: {len(pool)} bets at EV >= 0.02 on the page's price, "
          f"{len(ok)} with a price an hour before the fight")

    print("\ncut neighbourhood (EV at the page's price; graded at the page's price, then an hour before):")
    nb = []
    for c in [0.00] + CUTS:
        at_page = rows.assign(p=p)[(p * rows.dec - 1 >= c) & rows.won.notna() & rows.year.isin(TEST_YEARS)]
        sub = ok[ok.p * ok.dec - 1 >= c]
        nb.append({"cut": c, "page": f"{summary(at_page)['bets']} {summary(at_page)['ret']:+.1f}%",
                   "1h before": f"{len(sub)} {summary(sub.assign(dec=sub.h1))['ret']:+.1f}%"
                   if c >= 0.02 else "histories not fetched"})
    print(pd.DataFrame(nb).to_string(index=False))

    s = ok.assign(dec=ok.h1)
    print("\nan hour before, by year:")
    print(pd.DataFrame([summary(s[s.year == y], y) for y in TEST_YEARS]).to_string(index=False))
    print("\nan hour before, by book:")
    print(pd.DataFrame([summary(s[s.bookmaker == b], b) for b in sorted(s.bookmaker.unique())]).to_string(index=False))
    am = np.where(s.dec >= 2, (s.dec - 1) * 100, -100 / (s.dec - 1))
    u, r = units(s.dec.to_numpy(), s.won.to_numpy())
    w = s.won.astype(bool).to_numpy()
    print(f"\nprices an hour before: median {np.median(am):+.0f}, shortest {am.min():+.0f}, longest {am.max():+.0f}")
    print(f"won {w.sum()} of {len(s)}; units {u.sum():+.2f} on {r.sum():.2f} risked; "
          f"units without the single biggest winner {u.sum() - u[w].max():+.2f}, "
          f"without the three biggest {u.sum() - np.sort(u[w])[-3:].sum():+.2f}")
    print(f"model's chance at the bet: mean {s.p.mean():.3f}; price's implied chance: mean {(1 / s.dec).mean():.3f}; "
          f"won {w.mean():.3f}")


if __name__ == "__main__":
    main()

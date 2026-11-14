"""The two prop leads prop_grade.py found, taken apart (docs/ufc_market_audit.md
section 5f): goes the distance and decision by fighter, the market-anchored
model (mechanism 2) and the recalibrated market alone (2r). Run from the
study folder after prop_load.py.

  python prop_leads.py tables     # per year, by book, the cut and ridge
                                  # neighbourhood, 50 placebos; writes
                                  # prop_lead_jobs.txt, the price histories
                                  # the bets need (book's own cell, and for
                                  # goes the distance the other side too)
  python prop_leads.py retime     # once those histories are stored: each
                                  # bet re-graded at the price standing 1 h
                                  # and 24 h before the start (also the
                                  # fight-winner-coherent decision bets,
                                  # prop_lead_bets_mldecision.parquet)
"""
import glob
import os
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
_src = (HERE / "prop_grade.py").read_text(encoding="utf-8").split('if __name__ == "__main__":')[0]
exec(compile(_src, str(HERE / "prop_grade.py"), "exec"))

LEADS = ("Goes the distance", "Decision by fighter")
PLACEBOS = 50


def lead_bets(name, cut=MAIN_CUT, ridge=None, no_inputs=False):
    rows = outcome_rows(name).reset_index(drop=True)
    two_way = name in TWO_WAY
    if ridge is not None:
        global fit_offset
        base_fit = fit_offset
        fit_offset = lambda Z, U, off, y, ridge_=ridge: base_fit(Z, U, off, y, ridge_)  # noqa: E731
        try:
            p = walk_forward(rows, FAMILIES[name][1], two_way, no_inputs=no_inputs)
        finally:
            fit_offset = base_fit
    else:
        p = walk_forward(rows, FAMILIES[name][1], two_way, no_inputs=no_inputs)
    b = bets(rows, p, cut).copy()
    b["p"] = p.reindex(b.index)
    return rows, p, b


def tables():
    jobs = set()
    for name in LEADS:
        rows, p, b = lead_bets(name)
        print(f"\n== {name}, the anchored model at EV >= {MAIN_CUT}: {summary(b)}")
        yr = [summary(b[b.year == y], y) for y in TEST_YEARS]
        print(pd.DataFrame(yr).drop(columns="years_pos").to_string(index=False))
        _, _, r2 = lead_bets(name, no_inputs=True)
        print("  the recalibrated market alone (no fighter inputs), same cut, by year:")
        print(pd.DataFrame([summary(r2, "all")] + [summary(r2[r2.year == y], y) for y in TEST_YEARS])
              .drop(columns="years_pos").to_string(index=False))
        blind = best_of_five(family_rows(name))
        blind = blind[blind.year.isin(TEST_YEARS)]
        print("  blind, every price at the best of five, by year and side (the bar):")
        print(pd.DataFrame([summary(blind[(blind.year == y) & (blind.side == 1)], f"{y} side 1")
                            for y in TEST_YEARS]).drop(columns="years_pos").to_string(index=False))
        print("  ridge neighbourhood at the cut:")
        print(pd.DataFrame([summary(lead_bets(name, ridge=rg)[2], f"ridge {rg}") for rg in (10, 30, 100, 300)])
              .to_string(index=False))
        print("  graded at one book only (the model's bet wherever that book had a price, EV at its own price):")
        one = []
        for bk in BOOKS:
            s = family_rows(name)
            s = s[s.bookmaker == bk].join(rows.set_index(["matchup_id", "prop_type", "team", "side"])[["fair"]]
                                          .assign(p=p.to_numpy()), on=["matchup_id", "prop_type", "team", "side"])
            s = s[s.p.notna()]
            s = s[(s.p * s.dec - 1 >= MAIN_CUT) & s.won.notna() & s.year.isin(TEST_YEARS)]
            one.append(summary(s, bk))
        print(pd.DataFrame(one).to_string(index=False))
        pl = []
        for _ in range(PLACEBOS):
            pp = walk_forward(rows, FAMILIES[name][1], name in TWO_WAY, placebo=True)
            pl.append(summary(bets(rows, pp, MAIN_CUT))["ret"])
        pl = np.array(pl, float)
        real = summary(b)["ret"]
        print(f"  placebo, {PLACEBOS} runs: median {np.nanmedian(pl):+.1f}%, 90th percentile "
              f"{np.nanpercentile(pl, 90):+.1f}%, {np.mean(pl >= real):.0%} at or above the real {real:+.1f}%")
        for x in b.itertuples():
            jobs.add((x.book_id, x.src_matchup, x.prop_type, x.src_team, x.src_side))
            if name == "Goes the distance":
                jobs.add((x.book_id, x.src_matchup, x.prop_type, x.src_team, 3 - x.src_side))
        b.assign(lead=name).to_parquet(f"prop_lead_bets_{name.split()[0].lower()}.parquet")
    # goes the distance down to EV >= 0.02, for the cut neighbourhood at the earlier prices
    rows, p, b = lead_bets("Goes the distance", cut=0.02)
    b.to_parquet("prop_lead_bets_goes02.parquet")
    for x in b.itertuples():
        jobs.add((x.book_id, x.src_matchup, x.prop_type, x.src_team, x.src_side))
    # the fight-winner-coherent decision bets (mechanism 3), at EV >= 0.02
    name = "Decision by fighter"
    rows = outcome_rows(name).reset_index(drop=True)
    p = pd.Series(coherent(rows, name), index=rows.index)
    b = bets(rows, p, 0.02).copy()
    b["p"] = p.reindex(b.index)
    print(f"\n== {name}, the fight-winner-coherent rule at EV >= 0.02: {summary(b)}; "
          f"best price at {b.groupby('bookmaker').size().to_dict()}")
    b.assign(lead="ml decision").to_parquet("prop_lead_bets_mldecision.parquet")
    for x in b.itertuples():
        jobs.add((x.book_id, x.src_matchup, x.prop_type, x.src_team, x.src_side))
    Path("prop_lead_jobs.txt").write_text("".join(f"{','.join(map(str, j))}\n" for j in sorted(jobs)),
                                          encoding="utf-8")
    print(f"\n{len(jobs):,} price histories listed in prop_lead_jobs.txt")


def _american(dec):
    dec = np.asarray(dec, float)
    return np.where(dec >= 2, (dec - 1) * 100, -100 / (dec - 1))


def retime():
    """Each lead's bets at the price its own history shows 1 h and 24 h
    before the fight's start: the start is the odds feed's latest commence
    time for the fight (ufc_odds_history, to 2026-06-13), else the games
    table's."""
    from _paths import MIRROR

    def mirror(t):
        return pd.concat(pd.read_parquet(f) for f in glob.glob(os.path.join(MIRROR, f"public.{t}", "*.parquet")))

    T = mirror("ufc_prop_history_ticks")
    T["quoted_at"] = pd.to_datetime(T.quoted_at, utc=True)
    T = T.sort_values("quoted_at")
    O = mirror("ufc_odds_history")
    G = mirror("games")
    G = G[G.sport == "UFC"]
    start = pd.to_datetime(O[O.game_id.notna()].groupby("game_id").commence_time.max(), utc=True)
    start = start.combine_first(pd.to_datetime(G.set_index("game_id").commence_time, utc=True, errors="coerce"))
    # A fight the odds history did not place on our id (the feed spells a
    # fighter differently: "Sergey" Pavlovich) is found there by the two
    # surnames within a day of the fight.
    last = lambda n: re.sub(r"[^a-z]+", " ", unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore")
                            .decode().lower()).split()[-1:] or [""]
    O["ct"] = pd.to_datetime(O.commence_time, utc=True)
    by_names = {}
    for h, w, ct in zip(O.home_name, O.away_name, O.ct):
        if pd.notna(ct):
            k = (ct.date(), frozenset(last(h) + last(w)))
            by_names[k] = max(by_names.get(k, ct), ct)
    from datetime import timedelta
    for gid in set(X.index) - set(start.dropna().index):
        d = pd.Timestamp(X.loc[gid, "date"]).date()
        names = frozenset(last(X.loc[gid, "a_name"]) + last(X.loc[gid, "b_name"]))
        hits = [by_names[(d + timedelta(days=k), names)] for k in (0, 1, -1)
                if (d + timedelta(days=k), names) in by_names]
        if hits:
            start[gid] = max(hits)
    by = {k: g for k, g in T.groupby(["book_id", "matchup_id", "prop_type", "team", "side"])}

    def at(b, hrs):
        out = []
        for x in b.itertuples():
            g = by.get((x.book_id, x.src_matchup, x.prop_type, x.src_team, x.src_side))
            st = start.get(x.game_id, pd.NaT)
            if g is None or pd.isna(st):
                out.append(np.nan)
                continue
            g = g[g.quoted_at <= st - pd.Timedelta(hours=hrs)]
            out.append(g.price_decimal.iloc[-1] if len(g) else np.nan)
        return np.array(out)

    sets = [("Goes the distance, anchored, EV >= 0.08", "prop_lead_bets_goes.parquet", MAIN_CUT),
            ("Decision by fighter, anchored, EV >= 0.08", "prop_lead_bets_decision.parquet", MAIN_CUT),
            ("Decision by fighter, the fight-winner-coherent rule, EV >= 0.02",
             "prop_lead_bets_mldecision.parquet", 0.02)]
    for name, path, cut in sets:
        b = pd.read_parquet(path)
        h1, h24 = at(b, 1), at(b, 24)
        print(f"\n== {name}: {len(b)} bets; a price an hour before the start for {np.isfinite(h1).sum()}, "
              f"a day before for {np.isfinite(h24).sum()}")
        rows = []
        ok = np.isfinite(h1)
        rows.append({"graded": "last recorded price, the bets with an hour-before price", **summary(b[ok])})
        for label, dec in (("price 1 h before the start", h1), ("price 24 h before the start", h24)):
            m = np.isfinite(dec)
            s = b[m].assign(dec=dec[m])
            rows.append({"graded": label, **summary(s)})
            rows.append({"graded": label + ", only if EV still >= the cut", **summary(s[s.p * s.dec - 1 >= cut])})
        print(pd.DataFrame(rows).to_string(index=False))
        same = np.isclose(h1[ok], b.dec.to_numpy()[ok], atol=0.005)
        print(f"  last recorded price equal to the price an hour before: {same.mean():.0%}; by book "
              f"{pd.Series(same).groupby(b.bookmaker.to_numpy()[ok]).mean().round(2).to_dict()}")
        better = h1[ok] > b.dec.to_numpy()[ok] + 0.005
        print(f"  price an hour before longer than the last recorded: {better.mean():.0%}; shorter: "
              f"{(h1[ok] < b.dec.to_numpy()[ok] - 0.005).mean():.0%}")
        if not name.startswith("Goes the distance"):
            continue
        s1 = b[ok].assign(dec=h1[ok])
        print("  at the price 1 h before, by year:")
        print(pd.DataFrame([summary(s1[s1.year == y], y) for y in TEST_YEARS]).drop(columns="years_pos")
              .to_string(index=False))
        print("  at the price 1 h before, by book:")
        print(pd.DataFrame([summary(s1[s1.bookmaker == bk], bk) for bk in BOOKS if (s1.bookmaker == bk).any()])
              .to_string(index=False))
        print("  at the price 1 h before, by side:")
        print(pd.DataFrame([summary(s1[s1.side == sd], "yes" if sd == 1 else "no") for sd in (1, 2)])
              .to_string(index=False))
        am = _american(s1.dec)
        print(f"  prices taken an hour before: median {np.median(am):+.0f}, shortest {am.min():+.0f}, "
              f"longest {am.max():+.0f}, shorter than -300: {(am < -300).mean():.1%}")
        pool = pd.read_parquet("prop_lead_bets_goes02.parquet")
        q1 = at(pool, 1)
        m = np.isfinite(q1)
        pool = pool[m].assign(dec_last=pool.dec[m], dec=q1[m])
        print(f"  cut neighbourhood, on the {m.sum()} of {len(m)} bets down to EV 0.02 with an hour-before price:")
        nb = []
        for c in CUTS:
            at_page = pool[pool.p * pool.dec_last - 1 >= c]
            nb.append({"cut": c, "rule": "decided and graded at the page's price",
                       **summary(at_page.assign(dec=at_page.dec_last))})
            nb.append({"cut": c, "rule": "decided at the page's price, graded an hour before", **summary(at_page)})
            nb.append({"cut": c, "rule": "decided and graded an hour before", **summary(pool[pool.p * pool.dec - 1 >= c])})
        print(pd.DataFrame(nb).to_string(index=False))


if __name__ == "__main__":
    {"tables": tables, "retime": retime}[sys.argv[1]]()

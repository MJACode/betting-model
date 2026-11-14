"""Tennis match winner, round 1: the baselines, and the decidable books'
prices against Pinnacle's no-vig price at the same moment, with DraftKings'
retirement option. Reads the local cache (scripts/tennis_cache.py) and the
spooled match archive; writes nothing but its own report.

FIXED BEFORE ANY RESULT WAS READ (docs/sports/tennis.md, "Mechanisms to test"):
  population  every feed event linked to its ESPN result (two players' names
              within 60 hours), pre-match quotes only: snapshot and last update
              10+ minutes before the earlier of ESPN's start and the feed's last
              listed start
  decisions   first (each book's first quote), t12 (latest 12+ hours before the
              listed start), close (latest pre-match)
  books       DraftKings, FanDuel, BetMGM, Caesars, Fanatics, BetRivers, Hard Rock
  reference   Pinnacle's two prices standing at the decidable quote's snapshot,
              de-vigged multiplicatively, no older than 6 hours; the Betfair
              exchange the same way as a second reference
  EV          p_ref x decimal - 1, plus, at DraftKings only, the side's chance
              of retiring after set one (voided, not lost): the per-side rate by
              tour and best-of, read off the archive's 2015-2019 tour matches,
              before any priced season
  one bet     per event and decision: the best EV quote across books and sides
  grade       each book's own retirement rule (models/tennis_common.py); units
              at the published stake (risk to win 1, risk capped at 3)
  cuts        EV >= 0.00, 0.01, 0.02, 0.03, 0.05, 0.08

    python -m scripts.tennis_shop_study --cache C:/Users/micha/tennis_research/cache \\
        --spool C:/Users/micha/tennis_research/spool
"""
from __future__ import annotations

import argparse
import glob
import math
from pathlib import Path

import numpy as np
import pandas as pd

from models import tennis_common as tc
from scripts import tennis_market_study as st

CUTS = (0.0, 0.01, 0.02, 0.03, 0.05, 0.08)
REF_MAX_AGE = pd.Timedelta(hours=6)


def retire_rates(spool: str) -> dict:
    """Per-side chance of a retirement after set one, by (tour, best_of), from
    the archive's tour-level matches of 2015-2019 (walkovers out)."""
    out = {}
    for tour, pre, lv in (("ATP", "atp", {"G", "M", "A", "F"}), ("WTA", "wta", {"G", "PM", "P", "I", "F"})):
        fs = [f for f in glob.glob(f"{spool}/sackmann__{pre}__{pre}_matches_20*.csv")
              if 2015 <= int(f[-8:-4]) <= 2019]
        d = pd.concat([pd.read_csv(f, dtype={"tourney_level": str}, low_memory=False) for f in fs])
        d = d[d.tourney_level.isin(lv)]
        res = d.score.astype(str).map(tc.from_archive_score)
        ok = [r is not None and r.status != "walkover" for r in res]
        d, res = d[ok], [r for r in res if r is not None and r.status != "walkover"]
        ret1 = np.array([r.status == "retired" and r.first_set_complete for r in res])
        for bo, g in d.assign(r=ret1).groupby("best_of"):
            out[(tour, int(bo))] = float(g.r.mean() / 2)
    return out


def load(cache: Path):
    q = pd.read_parquet(cache / "tennis_odds_quotes.parquet")
    for c in ("commence_time", "last_update", "snapshot_ts"):
        q[c] = pd.to_datetime(q[c], utc=True)
    res = pd.read_parquet(cache / "tennis_espn_matches.parquet")
    res["start_time"] = pd.to_datetime(res["start_time"], utc=True)
    res = res.rename(columns={"p1_tiebreaks": "p1_tb", "p2_tiebreaks": "p2_tb"})
    return q, res


def candidates(q: pd.DataFrame, lk: pd.DataFrame, res: pd.DataFrame, rr: dict) -> pd.DataFrame:
    """Every decidable quote, both sides, at each decision, with its reference
    probability, EV, the DraftKings retirement term, and its grade."""
    pm = st.pre_match(q, lk, res)
    h = pm[pm.market == "h2h"].dropna(subset=["home_price", "away_price"])
    refs = {b: h[h.bookmaker == b].sort_values("snapshot_ts") for b in ("pinnacle", "betfair_ex_eu")}
    res_by = res.set_index("comp_id")
    lki = lk.dropna(subset=["comp_id"]).set_index("event_id")
    out = []
    for dec in st.DECISIONS:
        dq = st.decision_quotes(h, dec)
        dq = dq[dq.bookmaker.isin(st.DECIDABLE)]
        for ref_book, rq in refs.items():
            m = pd.merge_asof(dq.sort_values("snapshot_ts"), rq[["event_id", "snapshot_ts", "home_price", "away_price"]]
                              .rename(columns={"snapshot_ts": "ref_ts", "home_price": "r_home", "away_price": "r_away"}),
                              left_on="snapshot_ts", right_on="ref_ts", by="event_id", direction="backward")
            m = m.dropna(subset=["r_home", "r_away"])
            m = m[(m.snapshot_ts - m.ref_ts) <= REF_MAX_AGE]
            for r in m.itertuples(index=False):
                if r.event_id not in lki.index:
                    continue
                link = lki.loc[r.event_id]
                espn = res_by.loc[link.comp_id]
                result = st.espn_result(espn, a_is_p1=bool(link.home_is_p1))
                if result is None or result.status == "walkover":
                    continue
                ph, pa = tc.no_vig_pair(r.r_home, r.r_away)
                tour = "ATP" if "tennis_atp" in r.sport_key else "WTA"
                p_ret = rr.get((tour, int(espn.best_of or 3)), 0.0)
                for side, price, p in (("a", r.home_price, ph), ("b", r.away_price, pa)):
                    d = tc.american_to_decimal(price)
                    opt = p_ret if r.bookmaker == "draftkings" else 0.0
                    g = tc.grade_moneyline(result, side, r.bookmaker)
                    out.append({"decision": dec, "ref": ref_book, "event_id": r.event_id,
                                "tour": tour, "book": r.bookmaker, "side": side, "price": int(price),
                                "p_ref": p, "ev": p * d - 1 + opt, "opt": opt,
                                "ts": r.snapshot_ts, "ref_ts": r.ref_ts,
                                "r_side": int(r.r_home if side == "a" else r.r_away),
                                "r_other": int(r.r_away if side == "a" else r.r_home),
                                "start": espn.start_time,
                                "season": int(espn.season), "grade": g,
                                "units": tc.units(g, price), "risk": min(1 / (d - 1), 3.0)})
    return pd.DataFrame(out)


def ci(units: np.ndarray, risk: np.ndarray, z: float = 1.645) -> tuple:
    if len(units) < 2 or risk.sum() == 0:
        return (math.nan, math.nan)
    m = units.sum() / risk.sum()
    se = (units / risk).std(ddof=1) / math.sqrt(len(units))
    return (m - z * se, m + z * se)


def table(b: pd.DataFrame) -> dict:
    graded = b[b.grade.isin([tc.WIN, tc.LOSS])]
    u, r = b.units.values, b.risk.values
    lo, hi = ci(u, r)
    return {"bets": len(b), "graded": len(graded), "won": int((b.grade == tc.WIN).sum()),
            "void": int((b.grade == tc.VOID).sum()), "units": round(u.sum(), 2),
            "roi": round(u.sum() / r.sum(), 4) if r.sum() else math.nan,
            "ci90": (round(lo, 4), round(hi, 4))}


def best_per_event(c: pd.DataFrame, cut: float) -> pd.DataFrame:
    x = c[c.ev >= cut].sort_values("ev", ascending=False)
    return x.drop_duplicates(["decision", "ref", "event_id"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--spool", required=True)
    ap.add_argument("--save", type=Path)
    a = ap.parse_args(argv)
    rr = retire_rates(a.spool)
    print("retirement after set one, per side, 2015-2019 tour matches:", {k: round(v, 4) for k, v in rr.items()})
    q, res = load(a.cache)
    lk = st.link(q, res)
    print(f"feed events {len(lk):,}, linked to ESPN {lk.comp_id.notna().sum():,}")
    c = candidates(q, lk, res, rr)
    if a.save:
        c.to_parquet(a.save, index=False)
    print(f"candidate quotes (both sides, every book, three decisions, two references): {len(c):,}")

    # Baseline: every decidable quote both ways, Pinnacle reference rows only (one per quote).
    base = c[c.ref == "pinnacle"]
    print("\nBASELINE: every quote both ways, at each book's own grading")
    for (dec, book), g in base.groupby(["decision", "book"]):
        t = table(g)
        print(f"  {dec:5s} {book:15s} quotes {t['bets']:6,}  roi {t['roi']:+.4f}  median EV {g.ev.median():+.4f}")
    print("\nBLIND FAVOURITE / DOG at the close, DraftKings and FanDuel, by price band")
    cl = base[(base.decision == "close") & base.book.isin(["draftkings", "fanduel"])].copy()
    cl["band"] = pd.cut(cl.price, [-100000, -400, -200, -130, 100, 150, 250, 100000],
                        labels=["<-400", "-400..-200", "-200..-130", "-130..+100", "+100..+150", "+150..+250", ">+250"])
    for (book, band), g in cl.groupby(["book", "band"], observed=True):
        t = table(g)
        print(f"  {book:12s} {band!s:12s} quotes {t['bets']:5,}  roi {t['roi']:+.4f}")

    print("\nSHOP AGAINST THE SHARP REFERENCE: one bet per event and decision, best EV across books and sides")
    for ref in ("pinnacle", "betfair_ex_eu"):
        for dec in st.DECISIONS:
            for cut in CUTS:
                b = best_per_event(c[(c.ref == ref) & (c.decision == dec)], cut)
                if len(b) == 0:
                    continue
                t = table(b)
                print(f"  ref {ref:13s} {dec:5s} EV>={cut:.2f}  bets {t['bets']:5,} won {t['won']:5,} void {t['void']:3}  "
                      f"units {t['units']:+8.2f}  roi {t['roi']:+.4f}  ci90 {t['ci90']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

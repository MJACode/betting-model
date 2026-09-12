#!/usr/bin/env python3
"""The market's over-lean, bet at the BEST BETTABLE PRICE. No projection is consulted.

    python -m scripts.nfl_prop_over_lean
    python -m scripts.nfl_prop_over_lean --train 2023 2024 --test 2025
    python -m scripts.nfl_prop_over_lean --min-books 4 --shop-line

WHAT THIS IS, AND HOW IT DIFFERS FROM scripts/nfl_prop_under_bias.py.

That script (2026-09-07) measured the same observation -- the book's de-vigged
P(over) sits above the realised over rate on most NFL prop markets -- and graded
it at DRAFTKINGS' OWN UNDER PRICE. Two days later the repo stopped deciding at
DraftKings (CLAUDE.md §6, 2026-09-09, mike: "we want best lines for us
regardless"): a pre-game pick is now decided, sized and settled at the best
price across `config.BETTABLE_BOOKS`.

That matters more here than anywhere else in the repo. Every book holds 6-7% on
a two-way prop, so a single book's price needs the lean to exceed ~3.2pp before
a blind under pays. The SAME BET at the best of seven books needs far less,
because the shopping recovers most of one book's hold. The 09-07 measurement was
therefore run against a bar the production system no longer has to clear.

THE BET. One per proposition (game, player, market): the UNDER at the book
offering the best price, at the SAME LINE. No model, no projection, no feature.
The only inputs are which market it is and what the books are quoting.

WHY EQUAL-LINE BY DEFAULT. Taking the best (line, price) pair across books mixes
two effects -- price shopping, which is free, and line shopping, which can be
adverse selection (the book with the friendliest line may be the one that has
not seen the injury). `--shop-line` reports that variant; the headline is
equal-line at the consensus line, which is conservative and is the only arm
whose numbers are quoted anywhere.

THE DISCIPLINE. Markets are chosen on TRAIN seasons only and applied blind to a
TEST season, because choosing them after seeing which ones showed a lean is the
in-sample selection CLAUDE.md §7 keeps warning about. Reported alongside:

  * blind OVER at the best over price -- the control. If the lean is real this
    must lose, and lose by more than the unders win.
  * per season, with a game-clustered bootstrap interval.
  * the realised over rate against the number of books quoting, so a "best
    price" that comes from one thin book is visible.

Pushes (actual == line) return the stake and are excluded from win rate and ROI
the same way the rest of the repo treats them.

Zero credits: everything is in data/local.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import config
from data import local_store
from data.ingestors.nfl_props_data_ingestor import norm_player_name

MARKET_STAT = {
    "player_pass_yds": "passing_yards",
    "player_pass_attempts": "attempts",
    "player_pass_completions": "completions",
    "player_pass_tds": "passing_tds",
    "player_rush_yds": "rushing_yards",
    "player_rush_attempts": "carries",
    "player_reception_yds": "receiving_yards",
    "player_receptions": "receptions",
}


def implied(a: float) -> float:
    a = float(a)
    return 100.0 / (a + 100.0) if a > 0 else abs(a) / (abs(a) + 100.0)


def profit(price: float, won: bool) -> float:
    p = float(price)
    return (p / 100.0 if p > 0 else 100.0 / abs(p)) if won else -1.0


def load() -> pd.DataFrame:
    """One row per (game, player, market, line, book): the latest pre-game quote."""
    local_store.activate()
    o = local_store.read_table("nfl_prop_odds")
    o = o[(o.snapshot_type == "open") & o.market.isin(MARKET_STAT)
          & (~o.game_id.astype(str).str.startswith("NFL_2026"))].copy()
    bettable = {b.strip().lower() for b in config.BETTABLE_BOOKS}
    o = o[o.bookmaker.isin(bettable)]
    ko = (local_store.read_table("nfl_team_game_stats", columns=["game_id", "commence_time"])
          .dropna(subset=["commence_time"]).drop_duplicates("game_id"))
    ko["kick"] = pd.to_datetime(ko.commence_time, utc=True)
    o = o.merge(ko[["game_id", "kick"]], on="game_id", how="inner")
    o["ts"] = pd.to_datetime(o.snapshot_at, utc=True, format="mixed")
    o = o[o.ts <= o.kick]                       # compared as timestamps, never as text
    o["norm"] = o.player_name.map(norm_player_name)
    o = o.sort_values("ts").groupby(
        ["game_id", "norm", "market", "line", "bookmaker"], as_index=False).last()
    return o


def build(shop_line: bool, min_books: int) -> pd.DataFrame:
    o = load()
    log = local_store.read_table("nfl_player_game_log")
    cols = sorted(set(MARKET_STAT.values()))
    act = {(r.norm_name, r.game_id): {c: getattr(r, c) for c in cols}
           for r in log.itertuples(index=False)}

    rows = []
    for (gid, norm, market), g in o.groupby(["game_id", "norm", "market"], sort=False):
        a = (act.get((norm, gid)) or {}).get(MARKET_STAT[market])
        if a is None or (isinstance(a, float) and np.isnan(a)):
            continue
        actual = float(a)
        season = int(str(gid).split("_")[1])
        # THE CONSENSUS LINE: the one the most books quote (ties -> the lower,
        # which is the harder under, i.e. the conservative side).
        counts = g.groupby("line").size()
        main_line = float(counts[counts == counts.max()].index.min())
        cand = g if shop_line else g[g.line == main_line]
        cand = cand[cand.under_price.notna() & cand.over_price.notna()]
        if cand.empty:
            continue
        n_books = int(cand.bookmaker.nunique())
        if n_books < min_books:
            continue
        # RANK THE BET, NOT THE PAYOUT. The first version of --shop-line ranked
        # on payout alone, which for an under picks the LONGEST price -- i.e.
        # the hardest line -- and is the opposite of line shopping. An under
        # wants the HIGHEST line it can get, and the best price among books
        # offering it; an over wants the lowest line. On the equal-line path
        # every row shares one line, so this reduces to best price there.
        cand = cand.assign(u_pay=cand.under_price.map(lambda p: profit(p, True)),
                           o_pay=cand.over_price.map(lambda p: profit(p, True)))
        bu = cand.sort_values(["line", "u_pay"], ascending=[False, False]).iloc[0]
        bo = cand.sort_values(["line", "o_pay"], ascending=[True, False]).iloc[0]
        dk = g[(g.bookmaker == "draftkings") & (g.line == main_line)]
        dk_under = float(dk.under_price.iloc[0]) if len(dk) and pd.notna(
            dk.under_price.iloc[0]) else np.nan
        # the consensus de-vigged P(over) at the main line, across books
        at_main = g[(g.line == main_line) & g.over_price.notna() & g.under_price.notna()]
        if len(at_main):
            io = at_main.over_price.map(implied).values
            iu = at_main.under_price.map(implied).values
            cons_over = float(np.mean(io / (io + iu)))
            hold = float(np.mean(io + iu) - 1.0)
        else:
            cons_over, hold = np.nan, np.nan
        rows.append(dict(
            season=season, game_id=gid, player=norm, market=market,
            line=main_line, n_books=n_books, cons_over=cons_over, hold=hold,
            under_line=float(bu.line), under_price=float(bu.under_price),
            under_book=bu.bookmaker,
            over_line=float(bo.line), over_price=float(bo.over_price),
            over_book=bo.bookmaker,
            dk_under=dk_under, actual=actual,
        ))
    df = pd.DataFrame(rows)
    df["under_won"] = df.actual < df.under_line
    df["under_push"] = df.actual == df.under_line
    df["over_won"] = df.actual > df.over_line
    df["over_push"] = df.actual == df.over_line
    df["main_over"] = df.actual > df.line
    df["main_push"] = df.actual == df.line
    return df


def boot(prof: np.ndarray, games: np.ndarray, rng, n: int = 8000) -> tuple[float, float]:
    """Game-clustered bootstrap: props in one game share a game script."""
    uniq = np.unique(games)
    idx = {g: np.where(games == g)[0] for g in uniq}
    out = []
    for _ in range(n):
        pick = rng.choice(uniq, len(uniq), replace=True)
        out.append(prof[np.concatenate([idx[g] for g in pick])].mean())
    return float(np.percentile(out, 5) * 100), float(np.percentile(out, 95) * 100)


def grade(df: pd.DataFrame, side: str, rng, label: str = "") -> tuple[int, float]:
    price = df[f"{side}_price"].values
    won = df[f"{side}_won"].values
    push = df[f"{side}_push"].values
    keep = ~push
    prof = np.array([profit(p, w) for p, w in zip(price[keep], won[keep])])
    if len(prof) < 30:
        print(f"  {label:34s} {len(prof):>6}   (thin)")
        return len(prof), float("nan")
    lo, hi = boot(prof, df.game_id.values[keep], rng)
    print(f"  {label:34s} {len(prof):>6} {100*(prof > 0).mean():>6.1f}% "
          f"{prof.sum():>+9.2f} {100*prof.mean():>+7.2f}% "
          f"{'('+format(lo,'+.1f')+', '+format(hi,'+.1f')+')':>17}")
    return len(prof), float(prof.mean() * 100)


def lean_table(df: pd.DataFrame, title: str) -> list[str]:
    """market -> realised over rate vs the consensus de-vigged fair. Chooses markets."""
    print(f"\n{title}")
    print(f"  {'market':26s} {'props':>6} {'cons P(over)':>12} {'realised':>9} "
          f"{'lean':>8} {'hold':>7} {'need':>7}  verdict")
    print("  " + "-" * 92)
    chosen = []
    for m, g in sorted(df.groupby("market"), key=lambda kv: kv[0]):
        g = g[~g.main_push]
        if len(g) < 200:
            continue
        real = float(g.main_over.mean())
        cons = float(g.cons_over.mean())
        hold = float(g.hold.mean())
        lean = cons - real
        # the bar: at the BEST price the shopping recovers part of the hold, so
        # the honest bar is the cost of the bet actually taken. Measured, not
        # assumed: the mean implied probability of the best under price minus
        # the fair under probability.
        best_imp = float(g.under_price.map(implied).mean())
        need = best_imp - (1.0 - cons)
        ok = lean > need
        if ok:
            chosen.append(m)
        print(f"  {m:26s} {len(g):>6} {100*cons:>11.1f}% {100*real:>8.1f}% "
              f"{100*lean:>+7.1f}pp {100*hold:>6.2f}% {100*need:>6.2f}pp  "
              f"{'BET UNDER' if ok else '-'}")
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", nargs="+", type=int, default=[2023, 2024])
    ap.add_argument("--test", nargs="+", type=int, default=[2025])
    ap.add_argument("--min-books", type=int, default=3)
    ap.add_argument("--shop-line", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rng = np.random.default_rng(20260912)

    df = build(a.shop_line, a.min_books)
    if a.out:
        df.to_csv(a.out, index=False)
    print(f"\nNFL prop over-lean, best bettable price, {'LINE-SHOPPED' if a.shop_line else 'equal-line'}, "
          f">= {a.min_books} books")
    print(f"{len(df):,} propositions "
          f"{df.groupby('season').size().to_dict()}, "
          f"mean books quoting {df.n_books.mean():.1f}")
    print(f"best under book: {df.under_book.value_counts().head(5).to_dict()}")

    train = df[df.season.isin(a.train)]
    test = df[df.season.isin(a.test)]
    chosen = lean_table(train, f"TRAIN {a.train} — is the lean bigger than what the best price costs?")
    print(f"\n  chosen on TRAIN only: {', '.join(chosen) if chosen else '(none)'}")
    lean_table(test, f"TEST {a.test} — the same table, for reference only (never used to choose)")

    if not chosen:
        print("\nNo market clears on the training seasons.")
        return

    print(f"\nTEST {a.test} — blind unders at the best price, markets fixed on TRAIN")
    print(f"  {'selection':34s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} {'90% CI':>17}")
    print("  " + "-" * 92)
    sel = test[test.market.isin(chosen)]
    for m in chosen:
        grade(sel[sel.market == m], "under", rng, m)
    grade(sel, "under", rng, "POOLED (best price)")
    dk = sel[sel.dk_under.notna()].copy()
    dk["under_price"] = dk.dk_under
    dk["under_line"] = dk.line
    dk["under_won"] = dk.actual < dk.line
    dk["under_push"] = dk.main_push
    grade(dk, "under", rng, "POOLED at DraftKings' price")
    print("\n  CONTROL — blind OVERS at the best over price (must lose if the lean is real):")
    grade(sel, "over", rng, "POOLED overs")

    print(f"\nALL SEASONS pooled on the TRAIN-chosen markets, for the season split:")
    print(f"  {'season':34s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} {'90% CI':>17}")
    print("  " + "-" * 92)
    allsel = df[df.market.isin(chosen)]
    for s in sorted(allsel.season.unique()):
        grade(allsel[allsel.season == s], "under", rng, f"{s} unders")


if __name__ == "__main__":
    main()

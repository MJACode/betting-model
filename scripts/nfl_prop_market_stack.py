"""Anchor the eleven NFL prop models on the market, and measure what that buys.

WHY THIS EXISTS. `docs/nfl_prop_information_test.md` settled that the player
and context features behind the eleven distributional models hold less
information than the DraftKings line. The one thing in this repo that has
demonstrably beaten that line is OTHER BOOKS' PRICES: `models/nfl_prop_market`
bets a soft book against a de-vigged sharp quote at the same line and measures
+10.19% over 623 bets, sharp-specific under placebo. So "the features that
make a distributional model win" almost certainly start with the market.

WHAT THIS DOES. For every DraftKings-quoted row the backtest dumped
(`nfl_prop_backtest --all --seasons 2023 2024 2025 --dump`), build MARKET
features from the odds board as it stood AT OR BEFORE the DK row's own
snapshot -- never a later price:

  - the sharp books (pinnacle, betonlineag), each separately: main line, fair
    P(over) at that line, and fair P(over) at DK's line where they quote it;
  - a consensus of every other book: median main line, mean fair at DK's line,
    how many books quote it;
  - DK's own movement: its line and fair at t72 and t48 against the row priced;
  - the book's adjustment against the naive projection: line minus rolling-8.

Then a SECOND STAGE, kept deliberately small so two test seasons cannot be
mined: a ridge logistic per market on those features plus the model's own
P(over), fitted walk-forward (2023 -> 2024, 2023-24 -> 2025) and graded on the
§5c bar -- Brier against DK and against a sharp-only stack, ROI at a FIXED cut
grid against the DK price with an interval, per season, the shipped rule on
the same rows, and a placebo with a retail book standing in as the sharp.

    python -m scripts.nfl_prop_market_stack --rows <dump dir>
    python -m scripts.nfl_prop_market_stack --rows <dump dir> --placebo fanduel
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
from models.market_relative import devig, implied
import models.nfl_prop_market as mk
from scripts.nfl_prop_information_test import fit_logistic, grade, logit, profit, sigmoid

SHARP = ("pinnacle", "betonlineag")
CUTS = (0.02, 0.03, 0.04, 0.05, 0.06)


def _nn(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _book_quotes(rows: pd.DataFrame) -> dict[float, tuple[float, float]]:
    """Newest two-sided quote per line for one book, {line: (over, under)}."""
    out: dict = {}
    for r in rows.sort_values("ts").itertuples(index=False):
        op, up = _nn(r.over_price), _nn(r.under_price)
        if op is None or up is None:
            continue
        out[float(r.line)] = (op, up)           # later rows overwrite
    return out


def _main_line(quotes: dict) -> tuple[float, float] | None:
    """(line, fair_over) at the book's tightest two-way line."""
    best = None
    for line, (op, up) in quotes.items():
        io, iu = implied(op), implied(up)
        if io is None or iu is None:
            continue
        fo, _ = devig(op, up)
        if fo is None:
            continue
        vig = io + iu
        if best is None or vig < best[2]:
            best = (line, fo, vig)
    return None if best is None else (best[0], best[1])


def _context(g: pd.DataFrame, ts, sharp) -> dict:
    """Everything the board says about one proposition at or before `ts`:
    per-book two-sided quotes at the open, and DK's t72/t48 main lines.
    Built once per (proposition, timestamp) because a soft-book row set has
    six or seven rows per proposition that all read the same board."""
    g = g[g.ts <= ts]
    opn = g[g.snapshot_type == "open"]
    ctx = {"books": {}, "dk_prev": {}}
    for b, gb in opn.groupby("bookmaker"):
        ctx["books"][b] = _book_quotes(gb)
    for st in ("t72", "t48"):
        q = _book_quotes(g[(g.snapshot_type == st) & (g.bookmaker == "draftkings")])
        ml = _main_line(q)
        if ml is not None:
            ctx["dk_prev"][st] = ml
    return ctx


def _features_from(ctx: dict, line: float, sharp, exclude: str) -> dict:
    f: dict = {}
    for b in sharp:
        q = ctx["books"].get(b, {})
        ml = _main_line(q)
        if ml is not None:
            f[f"{b}_line"], f[f"{b}_fair_own"] = ml
        if line in q:
            fo, _ = devig(*q[line])
            if fo is not None:
                f[f"{b}_fair_dk"] = fo
    lines, fairs = [], []
    for b, q in ctx["books"].items():
        if b in sharp or b == exclude:
            continue
        ml = _main_line(q)
        if ml is not None:
            lines.append(ml[0])
        if line in q:
            fo, _ = devig(*q[line])
            if fo is not None:
                fairs.append(fo)
    if lines:
        f["cons_line"], f["cons_n"] = float(np.median(lines)), len(lines)
    if fairs:
        f["cons_fair_dk"], f["cons_n_same"] = float(np.mean(fairs)), len(fairs)
    for st, ml in ctx["dk_prev"].items():
        f[f"dk_line_{st}"], f[f"dk_fair_{st}"] = ml
    return f


def _board(rows: pd.DataFrame, odds: pd.DataFrame):
    market_of = {mid: config.PROP_MODELS[mid][1] for mid in rows.model_id.unique()}
    o = odds[odds.market.isin(set(market_of.values()))
             & odds.snapshot_type.isin(("open", "t48", "t72"))].copy()
    o["norm"] = o.player_name.map(norm_player_name)
    o["ts"] = pd.to_datetime(o.snapshot_at, utc=True, format="mixed")
    return market_of, {k: g for k, g in o.groupby(["game_id", "norm", "market"], sort=False)}


def market_features(rows: pd.DataFrame, odds: pd.DataFrame, sharp=SHARP,
                    book_col: str | None = None) -> pd.DataFrame:
    """One row per input row, market features bounded at the row's snapshot.
    `book_col` names the column holding the row's own book (excluded from the
    consensus); None means the rows are DraftKings'."""
    market_of, groups = _board(rows, odds)
    rows = rows.copy()
    rows["market"] = rows.model_id.map(market_of)
    rows["norm"] = rows.player.map(norm_player_name)
    rows["dk_ts"] = pd.to_datetime(rows.snapshot_at, utc=True, format="mixed")
    cache: dict = {}
    feats = []
    for r in rows.itertuples(index=False):
        key = (r.game_id, r.norm, r.market)
        g = groups.get(key)
        if g is None:
            feats.append({})
            continue
        ck = (key, r.dk_ts)
        if ck not in cache:
            cache[ck] = _context(g, r.dk_ts, sharp)
        own = getattr(r, book_col) if book_col else "draftkings"
        feats.append(_features_from(cache[ck], float(r.line), sharp, own))
    return pd.concat([rows.reset_index(drop=True), pd.DataFrame(feats)], axis=1)


def soft_rows(rows: pd.DataFrame, odds: pd.DataFrame, soft_books) -> pd.DataFrame:
    """The SOFT-BOOK version of the dump: one row per (proposition, soft book)
    at that book's newest two-sided open quote before kickoff, carrying the
    model's projection from the DK row of the same proposition. This is the
    row set the shipped rule bets on; the DK rows are the one book that
    prices flat and so shows nothing."""
    market_of, groups = _board(rows, odds)
    rows = rows.copy()
    rows["market"] = rows.model_id.map(market_of)
    rows["norm"] = rows.player.map(norm_player_name)
    rows["dk_ts"] = pd.to_datetime(rows.snapshot_at, utc=True, format="mixed")
    out = []
    for r in rows.itertuples(index=False):
        g = groups.get((r.game_id, r.norm, r.market))
        if g is None:
            continue
        g = g[(g.ts <= r.dk_ts) & (g.snapshot_type == "open") & g.bookmaker.isin(soft_books)]
        for b, gb in g.groupby("bookmaker"):
            q = _book_quotes(gb)
            ml = _main_line(q)
            if ml is None:
                continue
            line, fo = ml
            op, up = q[line]
            out.append({"model_id": r.model_id, "season": r.season, "game_id": r.game_id,
                        "player": r.player, "book": b, "line": line, "pred": r.pred,
                        "p_over": r.p_over, "fair_over": fo, "over_price": op,
                        "under_price": up, "snapshot_at": r.snapshot_at,
                        "roll8": r.roll8, "actual": r.actual})
    return pd.DataFrame(out)


# --- the second stage ------------------------------------------------------

def _design(df: pd.DataFrame, sd_line: float, sd_pred: float, sharp=SHARP,
            which: str = "full") -> np.ndarray:
    """Difference features that are ZERO when a book is missing. No presence
    flags: a flag that is almost always 1 in the training season standardises
    to -28 in a test season where the book is absent, and one such row was
    enough to put P(over) at 0.004. The row's own fair is not here either --
    it enters the fit as an OFFSET with coefficient one (see `_fit`), so the
    stack can only move away from the book's price where a feature earns it."""
    def diff(a, b):
        v = (df[a] - df[b]) if (a in df and b in df) else pd.Series(np.nan, index=df.index)
        return v.fillna(0.0).values

    cols = []
    if which in ("sharp", "full"):
        for b_ in sharp:
            cols += [diff(f"{b_}_fair_dk", "fair_over"),
                     diff(f"{b_}_line", "line") / sd_line,
                     diff(f"{b_}_fair_own", "fair_over")]
    if which == "full":
        z = ((df.pred - df.line) / sd_pred).fillna(0.0).values
        adj = ((df.line - df.roll8) / sd_line).fillna(0.0).values
        cols += [z, diff("cons_fair_dk", "fair_over"), diff("cons_line", "line") / sd_line,
                 diff("line", "dk_line_t72") / sd_line, diff("fair_over", "dk_fair_t72"),
                 diff("line", "dk_line_t48") / sd_line, diff("fair_over", "dk_fair_t48"), adj]
    return np.column_stack(cols)


def _fit(X: np.ndarray, y: np.ndarray, offset: np.ndarray, l2: float = 1.0):
    """Ridge logistic with an OFFSET: logit p = offset + X w, no intercept.
    The offset is the book's own logit(fair), so w measures what the features
    add to the price; w = 0 reproduces the book exactly."""
    n, k = X.shape
    w = np.zeros(k)
    for _ in range(100):
        p = sigmoid(offset + X @ w)
        g = X.T @ (p - y) + l2 * w
        H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(k)
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-9:
            break
    return w


def _bets(p: np.ndarray, te: pd.DataFrame, cut: float) -> list[float]:
    """ONE BET PER (proposition, side): with several books per proposition the
    same opinion would otherwise be counted six times, inflating the count and
    correlating the outcomes. The book with the largest edge is the bet."""
    best: dict = {}
    per_book = "book" in te.columns
    for pb, r in zip(p, te.itertuples(index=False)):
        if pb < 0:
            continue                              # no reference on this row
        for side, pp, price in (("over", pb, r.over_price), ("under", 1 - pb, r.under_price)):
            if price is None or not np.isfinite(float(price)):
                continue
            edge = pp - implied(price)
            if edge >= cut:
                won = (r.actual > r.line) if side == "over" else (r.actual < r.line)
                k = (r.game_id, r.player, side) if per_book else (r.game_id, r.player, r.line, side)
                if k not in best or edge > best[k][0]:
                    best[k] = (edge, profit(price, won))
    return [v for _e, v in best.values()]


def _rule_bets(te: pd.DataFrame, cut: float, sharp=SHARP) -> list[float]:
    """The shipped rule, exactly: a sharp's de-vigged fair against the row's
    OWN de-vigged fair (fair-vs-fair, `scripts/nfl_prop_two_sharps`), any one
    reference clearing the cut qualifies, one bet per (proposition, side) at
    the best disagreement, graded at the price actually paid. Note the scale:
    5pp fair-vs-fair is roughly 2pp against the price, so this column and the
    stack's price-based cuts are not the same ruler."""
    cols = [f"{b}_fair_dk" for b in sharp if f"{b}_fair_dk" in te.columns]
    if not cols:
        return []
    best: dict = {}
    for r in te.itertuples(index=False):
        refs = [getattr(r, c) for c in cols if pd.notna(getattr(r, c))]
        if not refs:
            continue
        for side, own, price in (("over", r.fair_over, r.over_price),
                                 ("under", 1 - r.fair_over, r.under_price)):
            if price is None or not np.isfinite(float(price)):
                continue
            edge = max((f if side == "over" else 1 - f) - own for f in refs)
            if edge >= cut:
                won = (r.actual > r.line) if side == "over" else (r.actual < r.line)
                k = (r.game_id, r.player, side)
                if k not in best or edge > best[k][0]:
                    best[k] = (edge, profit(price, won))
    return [v for _e, v in best.values()]


def evaluate(df: pd.DataFrame, rng, sharp=SHARP, label: str = "") -> None:
    df = df.dropna(subset=["fair_over", "p_over", "pred", "line", "actual"]).copy()
    df = df[df.actual != df.line]
    df["y"] = (df.actual > df.line).astype(float)
    has_same = pd.Series(False, index=df.index)
    for b in sharp:
        if f"{b}_fair_dk" in df:
            has_same |= df[f"{b}_fair_dk"].notna()
    df["has_same"] = has_same

    for test in (2023, 2024, 2025):
        # 2023 is read BACKWARDS -- fitted on 2024-25 -- because no market
        # history exists before it. A third out-of-sample season, not a
        # walk-forward one; the two are labelled apart in the output.
        tr = df[df.season < test] if test > 2023 else df[df.season > test]
        te = df[df.season == test]
        if len(tr) < 150 or len(te) < 150:
            print(f"  {label} {test}: thin ({len(tr)} / {len(te)})")
            continue
        sd_line = float(tr.line.std() or 1.0)
        sd_pred = float((tr.pred - tr.line).std() or 1.0)
        y = te.y.values
        out = {"n": len(te), "brier_dk": float(np.mean((te.fair_over - y) ** 2))}
        preds = {}
        tr_brier = {}
        off_tr, off_te = logit(tr.fair_over), logit(te.fair_over)
        for which in ("sharp", "full"):
            from sklearn.preprocessing import StandardScaler
            X = _design(tr, sd_line, sd_pred, sharp, which)
            sc = StandardScaler().fit(X)
            Xs = np.clip(sc.transform(X), -4, 4)
            w = _fit(Xs, tr.y.values, off_tr)
            tr_brier[which] = float(np.mean((sigmoid(off_tr + Xs @ w) - tr.y.values) ** 2))
            Xt = np.clip(sc.transform(_design(te, sd_line, sd_pred, sharp, which)), -4, 4)
            p = sigmoid(off_te + Xt @ w)
            preds[which] = p
            out[f"brier_{which}"] = float(np.mean((p - y) ** 2))
        out["brier_book_tr"] = float(np.mean((tr.fair_over - tr.y) ** 2))
        print(f"  {label} {test}{' (fitted on 2024-25, read backwards)' if test == 2023 else ''}: "
              f"n={out['n']}  Brier book {out['brier_dk']:.4f} | "
              f"sharp-stack {out['brier_sharp']:.4f} | full-stack {out['brier_full']:.4f} | "
              f"rows with same-line sharp {100*te.has_same.mean():.0f}%  "
              f"[train: book {out['brier_book_tr']:.4f} sharp {tr_brier['sharp']:.4f} "
              f"full {tr_brier['full']:.4f}]")
        print(f"    {'construction':22s} {'cut':>4} {'bets':>5} {'win%':>6} {'units':>9} {'ROI':>8}  90% CI")
        for cut in CUTS:
            rows_ = [("rule 5pp fair-vs-fair", _rule_bets(te, 0.05, sharp)),
                     ("sharp-stack", _bets(preds["sharp"], te, cut)),
                     ("full-stack", _bets(preds["full"], te, cut))]
            # The stack on rows the RULE cannot see: no same-line sharp quote.
            mask = ~te.has_same.values
            rows_.append(("full-stack, no-same-line",
                          _bets(preds["full"][mask], te[mask], cut)))
            for name, prof in rows_:
                print(f"    {name:22s} {cut:>4.0%} {grade(np.array(prof), rng) if prof else '    0'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--placebo", default=None,
                    help="a retail book to stand in for BOTH sharp slots")
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--cache", default=None, help="parquet of built features to reuse")
    ap.add_argument("--soft", action="store_true",
                    help="evaluate on the SOFT-BOOK rows (the rule's venue) instead of DK's")
    a = ap.parse_args()
    rng = np.random.default_rng(42)
    sharp = (a.placebo, a.placebo) if a.placebo else SHARP
    if a.placebo:
        sharp = (a.placebo,)

    local_store.activate()
    odds = local_store.read_table("nfl_prop_odds")
    files = sorted(Path(a.rows).glob("nfl_prop_*.csv"))
    for f in files:
        mid = f.stem
        if a.models and mid not in a.models:
            continue
        rows = pd.read_csv(f)
        tag = f"{mid}{'_' + a.placebo if a.placebo else ''}{'_soft' if a.soft else ''}"
        cached = (Path(a.cache) / f"{tag}.parquet") if a.cache else None
        if cached is not None and cached.exists():
            feats = pd.read_parquet(cached)      # minutes per market otherwise
        else:
            if a.soft:
                soft_books = tuple(b for b in mk.SOFT_BOOKS if b not in sharp)
                rows = soft_rows(rows, odds, soft_books)
                feats = market_features(rows, odds, sharp, book_col="book")
            else:
                feats = market_features(rows, odds, sharp)
            if cached is not None:
                cached.parent.mkdir(parents=True, exist_ok=True)
                feats.to_parquet(cached)
        print(f"\n{mid}  (sharp = {sharp})")
        evaluate(feats, rng, sharp, mid.replace("nfl_prop_", ""))


if __name__ == "__main__":
    main()

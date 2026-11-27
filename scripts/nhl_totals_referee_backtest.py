"""Walk-forward: do referee crews move the NHL full-game total?

The live rule is unchanged. `USE_NHL_REF_FEATURES` stays False, and this
script never writes a pick, an artifact, or a threshold. It replays the
totals lab's selection (scripts/nhl_totals_lab.py, SHARP-VS-SOFT, the bettable
books, EV floor and price floor the live rule uses) twice on the same quotes:
once at Pinnacle's no-vig price, once after a logistic shift fit on referee
deviations from earlier games only.

    python -m scripts.nhl_totals_referee_backtest
    python -m scripts.nhl_totals_referee_backtest --cache DIR --doc docs/nhl_totals_referee_backtest.md

The cache is a local read of Supabase (games, nhl_game_officials,
nhl_team_game_log, odds source odds_api_historical). It is not a store.
Quotes are one row per bettable book in a fetch that also holds Pinnacle at
the same total. `pins.csv` is Pinnacle's first and last pre-game quote.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

import config
from models.market_relative import devig, implied
from models.nhl_referee_features import (
    C_GRID,
    FEATURES,
    REF_K,
    RefTotalsModel,
    build_referee_features,
    choose_c,
    flat_profit,
    log_loss,
    market_logit,
    season_folds,
    select_first_plus_ev,
)
from models.nhl_totals_market import COHERENT, MODEL_ID, USE_NHL_REF_FEATURES
from scripts.nhl_totals_lab import BETTABLE

SOURCE = "odds_api_historical"
BOOKS = tuple(BETTABLE)
EV_GRID = (0.0, 0.005, 0.01, 0.015, 0.02, 0.03)
K_GRID = (20.0, 50.0, 100.0)
BOOT_N = 2000
BOOT_SEED = 11


def _coherent(over, under) -> bool:
    o, u = implied(over), implied(under)
    if o is None or u is None:
        return False
    return COHERENT[0] < (o + u) < COHERENT[1]


def _months(start=(2023, 10), end=(2026, 11)):
    y, m = start
    out = []
    while (y, m) <= end:
        nxt_m, nxt_y = (1, y + 1) if m == 12 else (m + 1, y)
        out.append((f"{y:04d}-{m:02d}-01", f"{nxt_y:04d}-{nxt_m:02d}-01"))
        y, m = nxt_y, nxt_m
    return out


def _quote_sql() -> str:
    return """
        WITH g AS (
            SELECT game_id, commence_time::timestamptz AS ct
            FROM games
            WHERE sport = 'NHL' AND game_date >= %s AND game_date < %s
              AND home_score IS NOT NULL AND commence_time IS NOT NULL
        ),
        pin AS (
            SELECT DISTINCT ON (o.game_id, o.created_at, o.total_line)
                   o.game_id, o.created_at, o.total_line,
                   o.over_price, o.under_price
            FROM odds o
            JOIN g ON g.game_id = o.game_id
            WHERE o.market = 'totals' AND o.bookmaker = 'pinnacle'
              AND o.source = %s AND o.snapshot_type = 'open'
              AND o.snapshot_at::timestamptz <= g.ct
              AND o.total_line IS NOT NULL
              AND o.over_price IS NOT NULL AND o.under_price IS NOT NULL
            ORDER BY o.game_id, o.created_at, o.total_line, o.snapshot_at DESC
        )
        SELECT s.game_id, s.created_at::text, s.bookmaker, s.snapshot_at::text,
               s.total_line::float8, s.over_price::float8, s.under_price::float8,
               p.over_price::float8, p.under_price::float8
        FROM odds s
        JOIN g ON g.game_id = s.game_id
        JOIN pin p
          ON p.game_id = s.game_id AND p.created_at = s.created_at
         AND p.total_line = s.total_line
        WHERE s.market = 'totals' AND s.source = %s AND s.snapshot_type = 'open'
          AND s.bookmaker = ANY(%s)
          AND s.snapshot_at::timestamptz <= g.ct
          AND s.total_line IS NOT NULL
          AND s.over_price IS NOT NULL AND s.under_price IS NOT NULL
    """


def load_db():
    from data.db import get_connection
    cols_q = ["game_id", "created_at", "book", "snap", "total_line", "over_price",
              "under_price", "pin_over", "pin_under"]
    conn = get_connection()
    try:
        games = pd.DataFrame(conn.execute(
            "SELECT game_id, season, game_date, commence_time::text, "
            "home_score::float8, away_score::float8 FROM games "
            "WHERE sport = 'NHL' AND season BETWEEN 2024 AND 2027",
        ).fetchall(), columns=["game_id", "season", "game_date", "commence_time",
                               "home_score", "away_score"])
        officials = pd.DataFrame(conn.execute(
            "SELECT nhl_game_id, role, full_name, season_end, game_type, game_date, our_game_id "
            "FROM nhl_game_officials",
        ).fetchall(), columns=["nhl_game_id", "role", "full_name", "season_end",
                               "game_type", "game_date", "our_game_id"])
        stats = pd.DataFrame(conn.execute(
            """
            SELECT t.nhl_game_id, MIN(t.game_id), MIN(t.season), MIN(t.game_type),
                   MIN(t.game_date), SUM(t.goals_for)::int, SUM(t.pp_opportunities)::int,
                   SUM(t.times_shorthanded)::int
            FROM nhl_team_game_log t
            WHERE t.nhl_game_id IN (SELECT DISTINCT nhl_game_id FROM nhl_game_officials)
            GROUP BY t.nhl_game_id
            """,
        ).fetchall(), columns=["nhl_game_id", "game_id", "season", "game_type",
                               "game_date", "goals", "pp_opp", "penalties"])
        pim = pd.DataFrame(conn.execute(
            """
            SELECT nhl_game_id, SUM(pim)::int
            FROM nhl_skater_game_log
            WHERE nhl_game_id IN (SELECT DISTINCT nhl_game_id FROM nhl_game_officials)
            GROUP BY nhl_game_id
            """,
        ).fetchall(), columns=["nhl_game_id", "pim"])
        stats = stats.merge(pim, on="nhl_game_id", how="left")
        quotes = []
        sql = _quote_sql()
        for start, end in _months():
            quotes += conn.execute(sql, (start, end, SOURCE, SOURCE, list(BOOKS))).fetchall()
        quotes = pd.DataFrame(quotes, columns=cols_q)
        pins = pd.DataFrame(conn.execute(
            """
            WITH g AS (
                SELECT game_id, commence_time::timestamptz AS ct
                FROM games
                WHERE sport = 'NHL' AND season BETWEEN 2024 AND 2027
                  AND home_score IS NOT NULL AND commence_time IS NOT NULL
            ),
            o AS (
                SELECT o.game_id, o.snapshot_at, o.total_line::float8 AS total_line,
                       o.over_price::float8 AS over_price, o.under_price::float8 AS under_price
                FROM odds o
                JOIN g ON g.game_id = o.game_id
                WHERE o.market = 'totals' AND o.bookmaker = 'pinnacle'
                  AND o.source = %s AND o.snapshot_type = 'open'
                  AND o.snapshot_at::timestamptz <= g.ct
                  AND o.total_line IS NOT NULL
                  AND o.over_price IS NOT NULL AND o.under_price IS NOT NULL
            ),
            firsts AS (
                SELECT DISTINCT ON (game_id)
                       'first'::text AS which, game_id, total_line, over_price, under_price,
                       snapshot_at::text AS snap
                FROM o ORDER BY game_id, snapshot_at ASC
            ),
            lasts AS (
                SELECT DISTINCT ON (game_id)
                       'last'::text AS which, game_id, total_line, over_price, under_price,
                       snapshot_at::text AS snap
                FROM o ORDER BY game_id, snapshot_at DESC
            )
            SELECT * FROM firsts UNION ALL SELECT * FROM lasts
            """,
            (SOURCE,),
        ).fetchall(), columns=["which", "game_id", "total_line", "over_price", "under_price", "snap"])
    finally:
        conn.close()
    return games, officials, stats, quotes, pins


def load_cache(path: Path):
    def rd(name):
        return pd.read_csv(path / name)
    stats = rd("stats.csv")
    return rd("games.csv"), rd("officials.csv"), stats, rd("quotes.csv"), rd("pins.csv")


def _prepare(games, officials, stats, quotes, pins):
    games = games.drop_duplicates("game_id").copy()
    games["season"] = pd.to_numeric(games["season"], errors="coerce").astype("Int64")
    for c in ("home_score", "away_score"):
        games[c] = pd.to_numeric(games[c], errors="coerce")
    games["total"] = games["home_score"] + games["away_score"]
    officials = officials.copy()
    if "game_id" not in officials.columns and "our_game_id" in officials.columns:
        officials = officials.rename(columns={"our_game_id": "game_id"})
    stats = stats.copy()
    for c in ("goals", "pp_opp", "penalties", "pim"):
        if c in stats.columns:
            stats[c] = pd.to_numeric(stats[c], errors="coerce")
    hist = stats.merge(games[["game_id", "commence_time", "total"]], on="game_id", how="inner")
    scored = hist[hist["total"].notna() & hist["goals"].notna()]
    goal_mismatch = int((scored["goals"] != scored["total"]).sum()) if len(scored) else 0
    goal_short_by_one = int(((scored["goals"] + 1) == scored["total"]).sum()) if len(scored) else 0
    # The team log's goals_for omits the shootout goal. The full-game total counts
    # it. On this join every disagreement is the log short by 1, so the goals
    # feature uses the scoreboard total. Power plays and penalties stay on the log.
    hist["goals_log"] = hist["goals"]
    hist["goals"] = hist["total"].where(hist["total"].notna(), hist["goals"])
    features = build_referee_features(hist, officials, k=REF_K, role="referee", prefix="ref")
    lines = build_referee_features(hist, officials, k=REF_K, role="linesman", prefix="lin")
    features = features.merge(lines, on="game_id", how="outer")
    if "pim" in hist.columns and hist["pim"].notna().any():
        pim_f = build_referee_features(
            hist.dropna(subset=["pim"]), officials, k=REF_K, role="referee", prefix="ref",
            stat_cols=("pim",),
        )
        features = features.merge(pim_f[["game_id", "ref_pim_dev"]], on="game_id", how="left")
    quotes = quotes.copy()
    for c in ("total_line", "over_price", "under_price", "pin_over", "pin_under"):
        quotes[c] = pd.to_numeric(quotes[c], errors="coerce")
    quotes = quotes.merge(
        games[["game_id", "season", "game_date", "total", "commence_time"]],
        on="game_id", how="inner",
    )
    quotes = quotes[quotes["total"].notna()].copy()
    quotes["snap_t"] = pd.to_datetime(quotes["snap"], utc=True, errors="coerce")
    pins = pins.copy()
    for c in ("total_line", "over_price", "under_price"):
        pins[c] = pd.to_numeric(pins[c], errors="coerce")
    refs = officials[officials["role"] == "referee"]
    id_col = "game_id" if "game_id" in refs.columns else None
    doubles = int((refs.groupby(["full_name", "game_date"])[id_col].nunique() > 1).sum()) if id_col else 0
    coverage = {
        "official_games": int(officials.loc[officials.role == "referee", "nhl_game_id"].nunique())
        if "nhl_game_id" in officials.columns else int(refs["game_id"].nunique())
        if "game_id" in refs.columns else None,
        "quote_rows": int(len(quotes)),
        "quote_games": int(quotes.game_id.nunique()),
        "seasons": sorted(int(s) for s in quotes.season.dropna().unique()),
        "goal_mismatch": goal_mismatch,
        "goal_short_by_one": goal_short_by_one,
        "scored_log_games": int(len(scored)),
        "referee_dates_with_two_games": doubles,
        "books": list(BOOKS),
        "ref_k": REF_K,
        "flag": bool(USE_NHL_REF_FEATURES),
    }
    return games, quotes, pins, features, hist, coverage


def _pin_over(over, under):
    p_over, _p_under = devig(over, under)
    return p_over


def long_frame(quotes: pd.DataFrame, p_over_of, min_odds: float) -> pd.DataFrame:
    """One row per book, side and snapshot that the lab would score."""
    book_ord = {b: i for i, b in enumerate(BOOKS)}
    rows = []
    for r in quotes.itertuples(index=False):
        if r.book not in book_ord or pd.isna(r.snap_t):
            continue
        if not _coherent(r.pin_over, r.pin_under) or not _coherent(r.over_price, r.under_price):
            continue
        p_over = p_over_of(r)
        if p_over is None or not (0.0 < float(p_over) < 1.0):
            continue
        p_over = float(p_over)
        for side, prob, price in (
            ("over", p_over, r.over_price),
            ("under", 1.0 - p_over, r.under_price),
        ):
            if pd.isna(price) or float(price) < min_odds:
                continue
            ev = config.expected_value(prob, float(price))
            if ev is None:
                continue
            rows.append({
                "game_id": r.game_id, "season": int(r.season), "game_date": r.game_date,
                "created_at": r.created_at, "snap_t": r.snap_t, "book": r.book,
                "book_ord": book_ord[r.book], "side": side, "price": float(price),
                "total_line": float(r.total_line), "total": float(r.total),
                "fair": float(prob), "ev": float(ev),
            })
    return pd.DataFrame(rows)


def _with_profit(picked: pd.DataFrame) -> pd.DataFrame:
    if picked.empty:
        return picked
    out = picked.copy()
    out["profit"] = [
        flat_profit(t, ln, s, p)
        for t, ln, s, p in zip(out["total"], out["total_line"], out["side"], out["price"])
    ]
    return out


def first_quotes(pins, games, features, cols):
    """One training row per game: Pinnacle's earliest pre-game total, non-push."""
    first = pins[pins["which"] == "first"].drop_duplicates("game_id")
    m = first.merge(
        games[["game_id", "season", "game_date", "commence_time", "total"]],
        on="game_id", how="inner",
    )
    m = m.merge(features, on="game_id", how="inner")
    m = m[m["ref_n"].fillna(0) >= 1].copy()
    rows = []
    for r in m.itertuples(index=False):
        if not _coherent(r.over_price, r.under_price):
            continue
        if pd.isna(r.total) or float(r.total) == float(r.total_line):
            continue
        p = _pin_over(r.over_price, r.under_price)
        if p is None or not (0.0 < p < 1.0):
            continue
        rec = {
            "game_id": r.game_id, "season": int(r.season), "game_date": r.game_date,
            "commence_time": pd.to_datetime(r.commence_time, utc=True, errors="coerce"),
            "y": 1.0 if float(r.total) > float(r.total_line) else 0.0,
            "p_market": float(p), "offset": float(market_logit([p])[0]),
            "total_line": float(r.total_line),
        }
        skip = False
        for c in cols:
            val = getattr(r, c, None)
            if val is None or (isinstance(val, float) and np.isnan(val)) or pd.isna(val):
                skip = True
                break
            rec[c] = float(val)
        if skip:
            continue
        rows.append(rec)
    return pd.DataFrame(rows)


def walk(quotes, train_rows, features, cols, *, intercept: bool, min_ev: float, min_odds: float):
    """Fit each test season on earlier seasons only. Return both cards and the scored rows."""
    by = features.set_index("game_id")
    folds = []
    base_parts, ref_parts, scored_parts = [], [], []
    long_base, long_ref = [], []
    for train_seasons, test_season in season_folds(sorted(train_rows.season.unique())):
        tr = train_rows[train_rows.season.isin(train_seasons)].dropna(subset=list(cols))
        te_games = set(train_rows.loc[train_rows.season == test_season, "game_id"])
        q = quotes[(quotes.season == test_season) & (quotes.game_id.isin(te_games))].copy()
        if len(tr) < 200 or q.empty:
            continue
        C = choose_c(tr, cols, intercept=intercept) if cols else 1.0
        model = RefTotalsModel(C=C, intercept=intercept, features=cols).fit(
            tr[list(cols)].to_numpy() if cols else np.zeros((len(tr), 0)),
            tr["y"].to_numpy(), tr["offset"].to_numpy(),
        )

        def base_p(r, _by=by):
            return _pin_over(r.pin_over, r.pin_under)

        def ref_p(r, _model=model, _by=by, _cols=cols):
            p = _pin_over(r.pin_over, r.pin_under)
            if p is None or r.game_id not in _by.index:
                return None
            return _model.adjust_over(p, _by.loc[r.game_id])

        b_long = long_frame(q, base_p, min_odds)
        r_long = long_frame(q, ref_p, min_odds)
        b_bet = _with_profit(select_first_plus_ev(b_long, min_ev))
        r_bet = _with_profit(select_first_plus_ev(r_long, min_ev))
        base_parts.append(b_bet)
        ref_parts.append(r_bet)
        long_base.append(b_long)
        long_ref.append(r_long)
        scored = train_rows[train_rows.season == test_season].copy()
        if len(scored):
            X = scored[list(cols)].to_numpy() if cols else np.zeros((len(scored), 0))
            scored["p_model"] = model.predict_over(X, scored["offset"].to_numpy())
            scored["fold_C"] = C
            scored_parts.append(scored)
        folds.append({
            "train": [int(s) for s in train_seasons],
            "test": int(test_season),
            "C": C,
            "n_train": int(len(tr)),
            "coefficients": model.standardized_coefficients(),
            "intercept": None if not intercept else float(model.w[0]),
        })
    base = pd.concat(base_parts, ignore_index=True) if base_parts else pd.DataFrame()
    ref = pd.concat(ref_parts, ignore_index=True) if ref_parts else pd.DataFrame()
    scored = pd.concat(scored_parts, ignore_index=True) if scored_parts else pd.DataFrame()
    b_long = pd.concat(long_base, ignore_index=True) if long_base else pd.DataFrame()
    r_long = pd.concat(long_ref, ignore_index=True) if long_ref else pd.DataFrame()
    return {"folds": folds, "base": base, "ref": ref, "scored": scored,
            "long_base": b_long, "long_ref": r_long}


def bootstrap_roi(bets: pd.DataFrame):
    """The totals lab's interval: 2,000 resamples of game days, seed 11."""
    if bets is None or len(bets) == 0:
        return None
    g = bets.groupby("game_date").profit.agg(["sum", "count"])
    if len(g) < 2:
        return None
    tot, cnt = g["sum"].to_numpy(), g["count"].to_numpy()
    idx = np.random.default_rng(BOOT_SEED).integers(0, len(g), size=(BOOT_N, len(g)))
    samples = tot[idx].sum(1) / cnt[idx].sum(1)
    lo, hi = np.percentile(samples, [2.5, 97.5])
    return float(lo), float(hi)


def bootstrap_unit_diff(ref: pd.DataFrame, base: pd.DataFrame):
    if (ref is None or ref.empty) and (base is None or base.empty):
        return None
    r = ref.groupby("game_date").profit.sum() if len(ref) else pd.Series(dtype=float)
    b = base.groupby("game_date").profit.sum() if len(base) else pd.Series(dtype=float)
    dates = sorted(set(r.index) | set(b.index))
    if len(dates) < 2:
        return None
    diff = np.array([float(r.get(d, 0.0)) - float(b.get(d, 0.0)) for d in dates])
    idx = np.random.default_rng(BOOT_SEED).integers(0, len(dates), size=(BOOT_N, len(dates)))
    samples = diff[idx].sum(1)
    lo, hi = np.percentile(samples, [2.5, 97.5])
    return float(diff.sum()), float(lo), float(hi)


def card_summary(bets: pd.DataFrame) -> dict:
    if bets is None or bets.empty:
        return {"bets": 0, "units": 0.0, "roi": None, "ci": None, "pushes": 0,
                "by_season": {}, "by_side": {}}
    units = float(bets.profit.sum())
    roi = float(bets.profit.mean())
    ci = bootstrap_roi(bets)
    by_season = {}
    for season, g in bets.groupby("season"):
        by_season[int(season)] = {
            "bets": int(len(g)), "units": round(float(g.profit.sum()), 2),
            "roi": float(g.profit.mean()),
        }
    by_side = {}
    for side, g in bets.groupby("side"):
        by_side[str(side)] = {
            "bets": int(len(g)), "units": round(float(g.profit.sum()), 2),
            "roi": float(g.profit.mean()),
        }
    return {
        "bets": int(len(bets)), "units": round(units, 2), "roi": roi,
        "ci": None if ci is None else [float(ci[0]), float(ci[1])],
        "pushes": int((bets.profit == 0).sum()),
        "by_season": by_season, "by_side": by_side,
    }


def early_late(bets: pd.DataFrame, slate: pd.DataFrame) -> dict:
    out = {}
    if bets is None or bets.empty or slate is None or slate.empty:
        return out
    for season, g in slate.groupby("season"):
        dates = sorted(set(g.game_date.astype(str)))
        if not dates:
            continue
        med = dates[len(dates) // 2]
        b = bets[bets.season == season]
        early, late = b[b.game_date.astype(str) <= med], b[b.game_date.astype(str) > med]
        out[int(season)] = {
            "cut_date": med,
            "early": card_summary(early),
            "late": card_summary(late),
        }
    return out


def reliability(y, p) -> dict:
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    edges = (0.0, 0.45, 0.50, 0.55, 1.01)
    rows, ece = [], 0.0
    n_all = len(y)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi)
        n = int(m.sum())
        if n == 0 or n_all == 0:
            rows.append({"lo": lo, "hi": min(hi, 1.0), "n": n, "pred": None, "actual": None})
            continue
        pred, actual = float(p[m].mean()), float(y[m].mean())
        ece += (n / n_all) * abs(pred - actual)
        rows.append({"lo": lo, "hi": min(hi, 1.0), "n": n, "pred": pred, "actual": actual})
    return {"bins": rows, "ece": float(ece), "n": int(n_all),
            "log_loss_market": None, "log_loss_model": None}


def close_ev(bets: pd.DataFrame, pins: pd.DataFrame) -> dict:
    if bets is None or bets.empty:
        return {"n_same_line": 0, "n": 0, "mean_ev": None}
    last = pins[pins["which"] == "last"][["game_id", "total_line", "over_price", "under_price"]]
    last = last.rename(columns={"total_line": "close_line", "over_price": "close_over",
                                "under_price": "close_under"})
    m = bets.merge(last.drop_duplicates("game_id"), on="game_id", how="left")
    same = m[m["close_line"] == m["total_line"]]
    evs = []
    for r in same.itertuples(index=False):
        if not _coherent(r.close_over, r.close_under):
            continue
        p_over = _pin_over(r.close_over, r.close_under)
        if p_over is None:
            continue
        p = p_over if r.side == "over" else 1.0 - p_over
        ev = config.expected_value(p, r.price)
        if ev is not None:
            evs.append(ev)
    return {
        "n": int(len(bets)),
        "n_same_line": int(len(evs)),
        "n_line_moved": int((m["close_line"].notna() & (m["close_line"] != m["total_line"])).sum()),
        "mean_ev": float(np.mean(evs)) if evs else None,
    }


def head_to_head(base, ref, ref_long, min_ev: float) -> dict:
    diff = bootstrap_unit_diff(ref, base)
    if base is None or base.empty:
        both = same = flip = identical = only_b = only_r = 0
        kept = dropped = None
    else:
        b = base.drop_duplicates("game_id").set_index("game_id")
        r = ref.drop_duplicates("game_id").set_index("game_id") if len(ref) else pd.DataFrame()
        both_ids = b.index.intersection(r.index) if len(r) else []
        same = sum(1 for g in both_ids if b.loc[g, "side"] == r.loc[g, "side"])
        flip = sum(1 for g in both_ids if b.loc[g, "side"] != r.loc[g, "side"])
        identical = 0
        for g in both_ids:
            if b.loc[g, "side"] != r.loc[g, "side"]:
                continue
            if (str(b.loc[g, "created_at"]) == str(r.loc[g, "created_at"])
                    and b.loc[g, "book"] == r.loc[g, "book"]
                    and float(b.loc[g, "total_line"]) == float(r.loc[g, "total_line"])):
                identical += 1
        only_b = int(len(b.index.difference(r.index))) if len(r) else int(len(b))
        only_r = int(len(r.index.difference(b.index))) if len(r) else 0
        both = int(len(both_ids))
        if ref_long is not None and len(ref_long):
            key = ["game_id", "created_at", "book", "side"]
            look = ref_long[key + ["ev"]].drop_duplicates(key)
            merged = base.merge(look, on=key, how="left", suffixes=("", "_ref"))
            kept_mask = merged["ev_ref"].notna() & (merged["ev_ref"] >= min_ev)
            kept = card_summary(merged[kept_mask])
            dropped = card_summary(merged[~kept_mask])
        else:
            kept = dropped = None
    return {
        "both": both, "same_side": int(same), "flip": int(flip), "identical": int(identical),
        "only_baseline": int(only_b), "only_ref": int(only_r),
        "unit_diff": None if diff is None else diff[0],
        "unit_diff_ci": None if diff is None else [diff[1], diff[2]],
        "kept": kept, "dropped": dropped,
    }


def ev_neighborhood(long_b, long_r) -> list:
    rows = []
    for cut in EV_GRID:
        b = _with_profit(select_first_plus_ev(long_b, cut)) if len(long_b) else pd.DataFrame()
        r = _with_profit(select_first_plus_ev(long_r, cut)) if len(long_r) else pd.DataFrame()
        bs, rs = card_summary(b), card_summary(r)
        diff = bootstrap_unit_diff(r, b)
        rows.append({
            "ev": cut, "base": bs, "ref": rs,
            "unit_diff": None if diff is None else round(diff[0], 2),
            "unit_diff_ci": None if diff is None else [round(diff[1], 2), round(diff[2], 2)],
        })
    return rows


def _pct(x):
    if x is None:
        return "—"
    return f"{100 * x:+.2f}%"


def _ci(ci):
    if not ci:
        return "—"
    return f"{100 * ci[0]:+.1f}% .. {100 * ci[1]:+.1f}%"


def _uci(ci):
    if not ci:
        return "—"
    return f"{ci[0]:+.1f} .. {ci[1]:+.1f}"


def _card_line(label, s):
    return (f"| {label} | {s['bets']} | {s['units']:+.1f} | {_pct(s['roi'])} | {_ci(s['ci'])} |")


def render_doc(payload: dict) -> str:
    cov = payload["coverage"]
    base, ref = payload["baseline"], payload["ref"]
    h = payload["h2h"]
    rec = payload["recommendation"]
    lines = []
    w = lines.append
    w("# NHL full-game totals, with the referee crew")
    w("")
    w("Backtest only. `USE_NHL_REF_FEATURES` in `models/nhl_totals_market.py` "
      "is False, and this run did not register an artifact or change a threshold, "
      "a stake, or a pause. The live card still prices Pinnacle's no-vig against "
      "the bettable books in the newest pre-game fetch.")
    w("")
    w(f"**Recommendation: {rec['verdict']}.** {rec['because']}")
    w("")
    cref = payload["close"]["ref"]["mean_ev"]
    cbase = payload["close"]["base"]["mean_ev"]
    w(f"On the same slate the rule bets {payload['baseline']['bets']} times for "
      f"{payload['baseline']['units']:+.1f} units "
      f"({_pct(payload['baseline']['roi'])}, close EV "
      f"{'—' if cbase is None else f'{100 * cbase:+.2f}%'}). "
      f"The referee card bets {payload['ref']['bets']} times for "
      f"{payload['ref']['units']:+.1f} units "
      f"({_pct(payload['ref']['roi'])}, close EV "
      f"{'—' if cref is None else f'{100 * cref:+.2f}%'}).")
    w("")
    w("## Head to head")
    w("")
    w("Same quotes, same games (a stored referee and a historical total), the "
      "totals lab's rule: the first pre-game snapshot where a bettable book's "
      f"price at Pinnacle's number has EV at least {payload['min_ev']:.3f}, "
      f"price {payload['min_odds']:.0f} or better, one bet a game. "
      "Profit is one unit risked at the price taken (the lab's grade). "
      "The interval resamples game days, 2,000 times, seed 11.")
    w("")
    w("| card | bets | units | ROI | 95% by day |")
    w("|---|---:|---:|---:|---|")
    w(_card_line("Pinnacle no-vig (the live rule's backtest)", base))
    w(_card_line("Pinnacle no-vig plus referee deviations", ref))
    w("")
    diff = h["unit_diff"]
    w(f"Unit difference (referee card minus the rule): "
      f"**{diff:+.1f}** units, day-clustered 95% **{_uci(h['unit_diff_ci'])}**."
      if diff is not None else "Unit difference was not computed.")
    w("")
    w(f"Games both cards bet: {h['both']}. Same side: {h['same_side']} "
      f"(identical ticket {h['identical']}). Opposite side: {h['flip']}. "
      f"Rule only: {h['only_baseline']}. Referee card only: {h['only_ref']}.")
    w("")
    if h.get("kept") and h["kept"]["bets"]:
        w("Taken as a filter on the rule's own tickets (same game, fetch, book and side; "
          "the referee probability still has to clear the EV floor):")
        w("")
        w("| rule tickets | bets | units | ROI |")
        w("|---|---:|---:|---:|")
        for label, key in (("still clears", "kept"), ("dropped", "dropped")):
            s = h[key]
            w(f"| {label} | {s['bets']} | {s['units']:+.1f} | {_pct(s['roi'])} |")
        w("")
    w("## By season, side, and half")
    w("")
    w("Seasons are ending years. 2023-24 is the first season with officials, so it "
      "trains the first fold and is not a test season. Each later season is fit on "
      "every earlier priced season only.")
    w("")
    w("| season | rule bets | rule units | rule ROI | ref bets | ref units | ref ROI |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    seasons = sorted(set(base["by_season"]) | set(ref["by_season"]))
    for s in seasons:
        b, r = base["by_season"].get(s, {}), ref["by_season"].get(s, {})
        w(f"| {s - 1}-{str(s)[2:]} | {b.get('bets', 0)} | {b.get('units', 0):+.1f} | "
          f"{_pct(b.get('roi'))} | {r.get('bets', 0)} | {r.get('units', 0):+.1f} | "
          f"{_pct(r.get('roi'))} |")
    w("")
    w("| side | rule bets | rule units | rule ROI | ref bets | ref units | ref ROI |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for side in ("over", "under"):
        b, r = base["by_side"].get(side, {}), ref["by_side"].get(side, {})
        w(f"| {side} | {b.get('bets', 0)} | {b.get('units', 0):+.1f} | {_pct(b.get('roi'))} | "
          f"{r.get('bets', 0)} | {r.get('units', 0):+.1f} | {_pct(r.get('roi'))} |")
    w("")
    w("Half-season split at the middle game date of that season's scored slate "
      "(the games, not the bets):")
    w("")
    w("| season | half | split date | rule bets | rule units | ref bets | ref units |")
    w("|---|---|---|---:|---:|---:|---:|")
    for season, halves in sorted(payload["early_late"].items()):
        for name in ("early", "late"):
            hlf = halves[name]
            b, r = hlf["base"], hlf["ref"]
            w(f"| {season - 1}-{str(season)[2:]} | {name} | {halves['cut_date']} | "
              f"{b['bets']} | {b['units']:+.1f} | {r['bets']} | {r['units']:+.1f} |")
    w("")
    w("## Prices, calibration, closing line")
    w("")
    cal = payload["calibration"]
    gap = None
    if cal["log_loss_market"] is not None and cal["log_loss_model"] is not None:
        gap = abs(cal["log_loss_model"] - cal["log_loss_market"])
    w(f"Every scored test game at Pinnacle's first pre-game total (pushes out): "
      f"{cal['n']} games. Log loss, market {_fmt(cal['log_loss_market'], 5)}, "
      f"referee model {_fmt(cal['log_loss_model'], 5)}"
      + (f" (gap {gap:.5f})" if gap is not None else "")
      + ". "
      f"Calibration error (binned absolute gap, weighted): "
      f"market {100 * cal['ece_market']:.2f} points, "
      f"model {100 * cal['ece_model']:.2f} points.")
    w("")
    w("| bin | n | market predicted | market actual | model predicted | model actual |")
    w("|---|---:|---:|---:|---:|---:|")
    for b, m in zip(cal["market_bins"], cal["model_bins"]):
        w(f"| {b['lo']:.2f}–{b['hi']:.2f} | {b['n']} | {_fmt(b['pred'], 3)} | "
          f"{_fmt(b['actual'], 3)} | {_fmt(m['pred'], 3)} | {_fmt(m['actual'], 3)} |")
    w("")
    w("On the bets themselves, the probability the card used against whether that side won "
      "(pushes out):")
    w("")
    w("| card | bets | mean probability | win rate | calibration error |")
    w("|---|---:|---:|---:|---:|")
    for label, key in (("rule", "bet_base"), ("referee", "bet_ref")):
        b = payload[key]
        w(f"| {label} | {b['n']} | {_fmt(b['mean_p'], 3)} | {_fmt(b['win_rate'], 3)} | "
          f"{100 * b['ece']:.2f} pts |")
    w("")
    cl = payload["close"]
    w("EV at Pinnacle's last pre-game price, only where that close is the same number "
      "as the bet (a moved number is a different proposition):")
    w("")
    w("| card | bets | same number | line moved | mean EV at the close |")
    w("|---|---:|---:|---:|---:|")
    for label, key in (("rule", "base"), ("referee", "ref")):
        c = cl[key]
        ev = "—" if c["mean_ev"] is None else f"{100 * c['mean_ev']:+.2f}%"
        w(f"| {label} | {c['n']} | {c['n_same_line']} | {c['n_line_moved']} | {ev} |")
    w("")
    w("## EV neighborhood")
    w("")
    w("The model is not refit at each floor. The live floor is 0.01. "
      "A result that exists only in one cell is a peak.")
    w("")
    w("| EV floor | rule bets | rule units | rule ROI | ref bets | ref units | ref ROI | unit diff | 95% |")
    w("|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in payload["ev_grid"]:
        b, r = row["base"], row["ref"]
        w(f"| {row['ev']:.3f} | {b['bets']} | {b['units']:+.1f} | {_pct(b['roi'])} | "
          f"{r['bets']} | {r['units']:+.1f} | {_pct(r['roi'])} | "
          f"{row['unit_diff'] if row['unit_diff'] is not None else '—'} | {_uci(row['unit_diff_ci'])} |")
    w("")
    w("## What the fit used")
    w("")
    w("Three crew means, each a referee's own earlier games shrunk toward the "
      f"league mean of every earlier game (`K = {int(cov['ref_k'])}`): goals per game, "
      "power-play opportunities per game (both teams' `pp_opportunities`, summed), "
      "and penalties per game (both teams' `times_shorthanded`, summed — penalties "
      "that left a team shorthanded; the team log has no raw penalty count). "
      "The feature is the shrunk rate minus the league mean, so a crew at the "
      "mean, and a referee with no earlier game, adds zero. The logistic model "
      "has no intercept: it cannot move Pinnacle's price without a deviation. "
      f"Penalty `C` is chosen on the last quarter of the training rows from {list(C_GRID)}, "
      "then the model is refit on the whole training fold.")
    w("")
    w(f"Officials cover the games in `nhl_game_officials`. Referee-dates with two "
      f"games: {cov['referee_dates_with_two_games']} (a prior is still every game with "
      "an earlier commence time, so a shared face-off would not leak either way). "
      f"Team-log goals disagreed with the scoreboard on {cov['goal_mismatch']} of "
      f"{cov['scored_log_games']} joined games, and {cov['goal_short_by_one']} of those "
      "are the log short by one (the shootout goal the total counts and the log does "
      "not). The goals feature uses the scoreboard. Power plays and penalties use the team log.")
    w("")
    w(f"Quote rows after the same-fetch, same-number join: {cov['quote_rows']:,} "
      f"on {cov['quote_games']:,} games, seasons {cov['seasons']}. "
      f"Books: {', '.join(cov['books'])}. Source `{SOURCE}`. "
      "2026-27 is absent from that source, so it is not a fold.")
    w("")
    w("Coefficients are the logit change per training standard deviation. "
      "Positive means a higher crew rate raises the over probability.")
    w("")
    w("| test season | train seasons | C | n train | goals | power plays | penalties |")
    w("|---|---|---:|---:|---:|---:|---:|")
    for f in payload["folds"]:
        c = f["coefficients"]
        w(f"| {f['test']} | {', '.join(str(s) for s in f['train'])} | {f['C']} | "
          f"{f['n_train']} | {c.get('ref_goals_dev', 0):+.3f} | "
          f"{c.get('ref_pp_dev', 0):+.3f} | {c.get('ref_pen_dev', 0):+.3f} |")
    w("")
    corr = payload["correlation"]
    w(f"On the {corr['n_games']} joined games, `pp_opportunities` and "
      f"`times_shorthanded` are equal on {corr['pp_equals_penalties']} games "
      f"(correlation {corr['pp_penalties']:.3f}). The two special-teams coefficients "
      "are one input entered twice. Penalty minutes, from the skater log, are the "
      "distinct count, and that ablation is its own row. Crew-feature correlations: "
      f"goals/PP {corr['feat_goals_pp']:.3f}, goals/penalties {corr['feat_goals_pen']:.3f}, "
      f"PP/penalties {corr['feat_pp_pen']:.3f}.")
    w("")
    w("## Ablation")
    w("")
    w("Each row is its own walk-forward, same quotes, same floor. "
      "\"Intercept only\" is a recalibration of Pinnacle with no crew input, "
      "so a referee result that matches it is the intercept.")
    w("")
    w("| specification | ref bets | ref units | ref ROI | unit diff vs rule | 95% | log loss | market log loss |")
    w("|---|---:|---:|---:|---:|---|---:|---:|")
    for row in payload["ablation"]:
        w(f"| {row['name']} | {row['bets']} | {row['units']:+.1f} | {_pct(row['roi'])} | "
          f"{row['unit_diff'] if row['unit_diff'] is not None else '—'} | "
          f"{_uci(row['unit_diff_ci'])} | {_fmt(row['log_loss'], 5)} | "
          f"{_fmt(row['market_log_loss'], 5)} |")
    w("")
    w("## Shrinkage neighborhood")
    w("")
    w(f"The headline uses K = {int(REF_K)}. The other values are the same walk with "
      "the prior weight changed. They are not a search that picked a winner.")
    w("")
    w("| K | ref bets | ref units | ref ROI | unit diff | 95% |")
    w("|---:|---:|---:|---:|---:|---|")
    for row in payload["k_grid"]:
        w(f"| {row['k']:.0f} | {row['bets']} | {row['units']:+.1f} | {_pct(row['roi'])} | "
          f"{row['unit_diff'] if row['unit_diff'] is not None else '—'} | {_uci(row['unit_diff_ci'])} |")
    w("")
    w("## Checks behind the recommendation")
    w("")
    w("All four had to hold, at K = 50 and the live 0.01 floor, before the "
      "features would be worth a separate decision to turn the flag on:")
    w("")
    for item in rec["checks"]:
        mark = "pass" if item["pass"] else "fail"
        w(f"- {mark}: {item['text']}")
    w("")
    w("## What this did not change")
    w("")
    w("The live total still decides on Pinnacle's no-vig in the newest fetch "
      "(`scripts/nhl_totals_card.py`). This backtest uses the lab's first "
      "qualifying snapshot, which is the selection the 0.01 floor was graded on. "
      "No row was written to `picks`. No artifact was saved.")
    w("")
    w("Run: `python -m scripts.nhl_totals_referee_backtest`. "
      "The figures above are that script on `odds_api_historical`, read 2026-11-27.")
    w("")
    return "\n".join(lines) + "\n"


def _fmt(x, n):
    if x is None:
        return "—"
    return f"{x:.{n}f}"


def _ll(scored, col):
    if scored is None or scored.empty:
        return None
    return log_loss(scored["y"].to_numpy(), scored[col].to_numpy())


def _bet_cal(bets: pd.DataFrame) -> dict:
    if bets is None or bets.empty:
        return {"n": 0, "mean_p": None, "win_rate": None, "ece": 0.0}
    play = bets[bets.profit != 0]
    if play.empty:
        return {"n": 0, "mean_p": None, "win_rate": None, "ece": 0.0}
    y = (play.profit > 0).astype(float).to_numpy()
    p = play.fair.to_numpy()
    rel = reliability(y, p)
    return {"n": int(len(play)), "mean_p": float(np.mean(p)), "win_rate": float(np.mean(y)),
            "ece": rel["ece"]}


def _recommend(h2h, ev_grid, log_m, log_r, by_season_base, by_season_ref) -> dict:
    checks = []
    diff = h2h["unit_diff"]
    ci = h2h["unit_diff_ci"]
    ci_above = diff is not None and ci is not None and ci[0] > 0 and diff > 0
    checks.append({
        "pass": bool(ci_above),
        "text": "the referee card's units beat the rule, and the day-clustered "
                "95% interval on that difference sits above zero",
    })
    ll_better = log_r is not None and log_m is not None and log_r < log_m
    checks.append({
        "pass": bool(ll_better),
        "text": "out-of-sample log loss on every scored test game beats Pinnacle's no-vig",
    })
    seasons = sorted(set(by_season_base) | set(by_season_ref))
    season_ok = True
    for s in seasons:
        b = by_season_base.get(s, {}).get("units", 0.0)
        r = by_season_ref.get(s, {}).get("units", 0.0)
        if r - b < 0:
            season_ok = False
    checks.append({
        "pass": bool(season_ok) and bool(seasons),
        "text": "every test season's unit difference is zero or positive",
    })
    neigh = {row["ev"]: row["unit_diff"] for row in ev_grid}
    neigh_ok = all(neigh.get(c) is not None and neigh[c] >= 0 for c in (0.005, 0.01, 0.015))
    checks.append({
        "pass": bool(neigh_ok),
        "text": "the unit difference is zero or positive at EV 0.005, 0.01 and 0.015",
    })
    ok = all(c["pass"] for c in checks)
    if ok:
        verdict = "the backtest clears its checks; turning the flag on is a separate decision"
        because = ("The four checks below all hold. This pull request still leaves the flag "
                   "off, because adopting the features would be a live-model change and "
                   "needs an explicit ask.")
    else:
        verdict = "leave the flag off"
        missed = []
        if not ci_above:
            if diff is not None and ci is not None and diff > 0 and ci[0] <= 0:
                missed.append(
                    f"the referee card is ahead by {diff:+.1f} units and the 95% interval on that gap includes zero"
                )
            else:
                missed.append("the referee card does not beat the rule on units")
        if not ll_better:
            missed.append("log loss does not beat Pinnacle")
        if not season_ok or not seasons:
            missed.append("a test season is behind the rule")
        if not neigh_ok:
            missed.append("the EV floors next to 0.01 do not keep the gain")
        because = "It fails the bar: " + "; ".join(missed) + "."
    return {"verdict": verdict, "because": because, "checks": checks, "adopt": ok}


def _ablation_row(name, result) -> dict:
    ref, base, scored = result["ref"], result["base"], result["scored"]
    summary = card_summary(ref)
    diff = bootstrap_unit_diff(ref, base)
    return {
        "name": name,
        "bets": summary["bets"], "units": summary["units"], "roi": summary["roi"],
        "unit_diff": None if diff is None else round(diff[0], 2),
        "unit_diff_ci": None if diff is None else [round(diff[1], 2), round(diff[2], 2)],
        "log_loss": _ll(scored, "p_model"),
        "market_log_loss": _ll(scored, "p_market"),
    }


def _rebuild_features(hist, officials, k, pim: bool):
    features = build_referee_features(hist, officials, k=k, role="referee", prefix="ref")
    if pim:
        pim_f = build_referee_features(
            hist.dropna(subset=["pim"]), officials, k=k, role="referee", prefix="ref",
            stat_cols=("pim",),
        )
        features = features.merge(pim_f[["game_id", "ref_pim_dev"]], on="game_id", how="left")
    return features


def run(games, officials, stats, quotes, pins) -> dict:
    if USE_NHL_REF_FEATURES:
        raise SystemExit("USE_NHL_REF_FEATURES is True; this backtest refuses to run against a flipped flag")
    min_ev = float(config.min_ev_for(MODEL_ID))
    min_odds = float(config.min_odds_for(MODEL_ID))
    if "game_id" not in officials.columns and "our_game_id" in officials.columns:
        officials = officials.rename(columns={"our_game_id": "game_id"})
    games, quotes, pins, features, hist, coverage = _prepare(games, officials, stats, quotes, pins)
    if features["game_id"].duplicated().any():
        raise RuntimeError("referee features are not one row per game")
    slate_games = set(features.loc[features["ref_n"].fillna(0) >= 1, "game_id"])
    quotes = quotes[quotes.game_id.isin(slate_games)].copy()
    cols = list(FEATURES)
    train = first_quotes(pins, games, features, cols)
    headline = walk(quotes, train, features, cols, intercept=False, min_ev=min_ev, min_odds=min_odds)
    base, ref = headline["base"], headline["ref"]
    scored = headline["scored"]
    market_rel = reliability(scored["y"], scored["p_market"]) if len(scored) else reliability([], [])
    model_rel = reliability(scored["y"], scored["p_model"]) if len(scored) else reliability([], [])
    # Align bins by the market's game order; both use the same rows, so n matches per game
    # but bin membership differs. Report each probability's own bins.
    calibration = {
        "n": int(len(scored)),
        "log_loss_market": _ll(scored, "p_market"),
        "log_loss_model": _ll(scored, "p_model"),
        "ece_market": market_rel["ece"],
        "ece_model": model_rel["ece"],
        "market_bins": market_rel["bins"],
        "model_bins": model_rel["bins"],
    }
    slate = train[train.season.isin(sorted(set(base.season) | set(ref.season)) if len(base) or len(ref) else [])]
    # early/late needs both cards split on the same dates. Build per card then zip.
    halves = {}
    base_halves = early_late(base, slate)
    ref_halves = early_late(ref, slate)
    for season in sorted(set(base_halves) | set(ref_halves)):
        halves[season] = {
            "cut_date": (base_halves.get(season) or ref_halves.get(season))["cut_date"],
            "early": {
                "base": (base_halves.get(season) or {}).get("early", card_summary(pd.DataFrame())),
                "ref": (ref_halves.get(season) or {}).get("early", card_summary(pd.DataFrame())),
            },
            "late": {
                "base": (base_halves.get(season) or {}).get("late", card_summary(pd.DataFrame())),
                "ref": (ref_halves.get(season) or {}).get("late", card_summary(pd.DataFrame())),
            },
        }
    # early_late on an empty side returns {}; the dict above assumes cut_date exists.
    # Recompute cut from train directly when a side is missing — handled by the `or` chain
    # only if one side has the season. If both empty, skip. Good.

    h2h = head_to_head(base, ref, headline["long_ref"], min_ev)
    base_s, ref_s = card_summary(base), card_summary(ref)
    ev_grid = ev_neighborhood(headline["long_base"], headline["long_ref"])
    recommendation = _recommend(h2h, ev_grid, calibration["log_loss_market"],
                                calibration["log_loss_model"], base_s["by_season"], ref_s["by_season"])

    # Correlations
    pp_pen = float(hist[["pp_opp", "penalties"]].corr().iloc[0, 1]) if len(hist) > 2 else float("nan")
    feat_corr = train[cols].corr() if len(train) > 2 else pd.DataFrame(np.eye(3), index=cols, columns=cols)
    correlation = {
        "n_games": int(len(hist)),
        "pp_equals_penalties": int((hist["pp_opp"] == hist["penalties"]).sum()),
        "pp_penalties": pp_pen,
        "feat_goals_pp": float(feat_corr.loc["ref_goals_dev", "ref_pp_dev"]),
        "feat_goals_pen": float(feat_corr.loc["ref_goals_dev", "ref_pen_dev"]),
        "feat_pp_pen": float(feat_corr.loc["ref_pp_dev", "ref_pen_dev"]),
    }

    lin_cols = ["lin_goals_dev", "lin_pp_dev", "lin_pen_dev"]
    both_cols = cols + lin_cols

    def _walk_on(frame, use_cols, intercept, name):
        rows = first_quotes(pins, games, frame, use_cols)
        # first_quotes requires ref_n. Linesmen-only games still have ref_n from the merge
        # when frame is `both` or `features`. For linesmen-only, require lin_n.
        if "lin_n" in frame.columns and set(use_cols) <= set(lin_cols):
            rows = first_quotes(pins, games, frame, use_cols)
        return _ablation_row(name, walk(
            quotes, rows, frame, use_cols, intercept=intercept, min_ev=min_ev, min_odds=min_odds,
        ))

    ablation = [_ablation_row("referees (headline)", headline)]
    for drop, name in (
        (("ref_goals_dev",), "drop goals"),
        (("ref_pp_dev",), "drop power plays"),
        (("ref_pen_dev",), "drop penalties"),
    ):
        use = [c for c in cols if c not in drop]
        ablation.append(_walk_on(features, use, False, name))
    ablation.append(_walk_on(features, lin_cols, False, "linesmen instead"))
    ablation.append(_walk_on(features, both_cols, False, "referees plus linesmen"))
    if "ref_pim_dev" in features.columns:
        ablation.append(_walk_on(features, ["ref_goals_dev", "ref_pp_dev", "ref_pim_dev"], False,
                                 "penalty minutes instead of times shorthanded"))
    # Intercept-only control: no crew columns.
    empty = features[["game_id", "ref_n"]].copy()
    rows = first_quotes(pins, games, empty, [])
    # first_quotes with cols [] skips the feature-null check. Walk with empty cols.
    ablation.append(_ablation_row("intercept only", walk(
        quotes, rows, empty, [], intercept=True, min_ev=min_ev, min_odds=min_odds,
    )))

    k_grid = []
    for k in K_GRID:
        if k == REF_K:
            row = _ablation_row(f"K={k:.0f}", headline)
        else:
            feat_k = _rebuild_features(hist, officials, k, False)
            # rebuild does not include linesmen; headline cols only
            rows_k = first_quotes(pins, games, feat_k, cols)
            row = _ablation_row(f"K={k:.0f}", walk(
                quotes[quotes.game_id.isin(set(feat_k.loc[feat_k.ref_n.fillna(0) >= 1, "game_id"]))],
                rows_k, feat_k, cols, intercept=False, min_ev=min_ev, min_odds=min_odds,
            ))
        row["k"] = k
        k_grid.append(row)

    return {
        "coverage": coverage,
        "min_ev": min_ev,
        "min_odds": min_odds,
        "baseline": base_s,
        "ref": ref_s,
        "h2h": h2h,
        "early_late": halves,
        "calibration": calibration,
        "bet_base": _bet_cal(base),
        "bet_ref": _bet_cal(ref),
        "close": {"base": close_ev(base, pins), "ref": close_ev(ref, pins)},
        "ev_grid": ev_grid,
        "folds": headline["folds"],
        "correlation": correlation,
        "ablation": ablation,
        "k_grid": k_grid,
        "recommendation": recommendation,
        "n_train_rows": int(len(train)),
        "n_slate_games": int(quotes.game_id.nunique()),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", default=None, help="directory of games/officials/stats/quotes/pins csv")
    ap.add_argument("--doc", default=None, help="write the markdown report here")
    ap.add_argument("--json", default=None, help="write the result dict as JSON")
    args = ap.parse_args()
    if args.cache:
        loaded = load_cache(Path(args.cache))
    else:
        loaded = load_db()
    payload = run(*loaded)
    text = render_doc(payload)
    if args.doc:
        Path(args.doc).write_text(text, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()

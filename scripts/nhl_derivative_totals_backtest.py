"""Walk-forward grade of the NHL derivative totals, on the bought prices.

The production module is models/nhl_derivative_totals.py. This script only
loads the prices and prints the table. A side is registered only when
`neighbour_clears` is true; this script does not edit config and does not
write a pick.

Prices are `odds` rows with source `odds_api_nhl_totals_history` (one pre-game
snapshot a game). One bet per game — per team, for a team total — at the line
with the best expected value. The blind rows are every game at the line whose
over is closest to -110, which is the number a bettor would call the main one.

    python -m scripts.nhl_derivative_totals_backtest
    python -m scripts.nhl_derivative_totals_backtest --cache /tmp/nhl_deriv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import models.nhl_derivative_totals as dt  # noqa: E402

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 200)

NON_BETTABLE = {"pinnacle", "bovada", "espnbet"}
SOURCE = "odds_api_nhl_totals_history"


def _csv(path: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(path / name)


def load(cache: str | None):
    if cache:
        c = Path(cache)
        return (_csv(c, "team_log.csv"), _csv(c, "periods.csv"),
                _csv(c, "games.csv"), _csv(c, "prices.csv"))
    from data.db import get_connection
    conn = get_connection()
    try:
        team = pd.DataFrame(conn.execute(
            "SELECT nhl_game_id, game_id, team, opponent, season, game_date, is_home, "
            "goals_for, goals_against, shots_for, shots_against, game_type "
            "FROM nhl_team_game_log").fetchall(),
            columns=["nhl_game_id", "game_id", "team", "opponent", "season", "game_date",
                     "is_home", "goals_for", "goals_against", "shots_for", "shots_against", "game_type"])
        periods = pd.DataFrame(conn.execute(
            "SELECT game_id, season, game_date, home_p1, away_p1, home_p2, away_p2, home_p3, away_p3, source "
            "FROM nhl_period_scores").fetchall(),
            columns=["game_id", "season", "game_date", "home_p1", "away_p1", "home_p2", "away_p2",
                     "home_p3", "away_p3", "source"])
        games = pd.DataFrame(conn.execute(
            "SELECT game_id, season, game_date, home_team, away_team, home_score, away_score, commence_time "
            "FROM games WHERE sport = 'NHL' AND season BETWEEN 2024 AND 2026 AND home_score IS NOT NULL"
        ).fetchall(), columns=["game_id", "season", "game_date", "home_team", "away_team",
                               "home_score", "away_score", "commence_time"])
        ids = games.game_id.tolist()
        rows = []
        for i in range(0, len(ids), 200):
            rows += conn.execute(
                "SELECT game_id, market, bookmaker, total_line, over_price, under_price, snapshot_at "
                "FROM odds WHERE game_id = ANY(%s) AND source = %s AND snapshot_type = 'open' "
                "AND market = ANY(%s)",
                (ids[i:i + 200], SOURCE,
                 ["alternate_totals", "totals_p1", "team_totals_home", "team_totals_away"])).fetchall()
        prices = pd.DataFrame(rows, columns=["game_id", "market", "bookmaker", "total_line",
                                             "over_price", "under_price", "snapshot_at"])
        return team, periods, games, prices
    finally:
        conn.close()


def regulation(periods: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    p = periods.copy()
    p["rank"] = np.where(p["source"].eq("nhl_api_score"), 0, 1)
    p = p.sort_values("rank").drop_duplicates("game_id", keep="first")
    g = games.merge(p[["game_id", "home_p1", "away_p1", "home_p2", "away_p2", "home_p3", "away_p3"]],
                    on="game_id", how="left")
    for c in ("home_p1", "away_p1", "home_p2", "away_p2", "home_p3", "away_p3", "home_score", "away_score"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g["reg_home"] = g.home_p1 + g.home_p2 + g.home_p3
    g["reg_away"] = g.away_p1 + g.away_p2 + g.away_p3
    g["total"] = g.home_score + g.away_score
    g["p1_total"] = g.home_p1 + g.away_p1
    return g


def pregame(prices: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    px = prices.merge(games, on="game_id", how="inner")
    px["snap"] = pd.to_datetime(px.snapshot_at, utc=True, format="mixed")
    px["start"] = pd.to_datetime(px.commence_time, utc=True, format="mixed")
    px = px[px.snap.notna() & px.start.notna() & (px.snap <= px.start)].copy()
    for c in ("total_line", "over_price", "under_price"):
        px[c] = pd.to_numeric(px[c], errors="coerce")
    return px.drop_duplicates(["game_id", "market", "bookmaker", "total_line"])


def _line(label: dict, b: pd.DataFrame) -> dict:
    if len(b) < 30:
        return {**label, "bets": len(b), "clears": False}
    lo, hi = dt.day_interval(b)
    r = {**label, "bets": len(b), "units": round(float(b.profit.sum()), 1),
         "roi%": round(float(b.profit.mean()) * 100, 2),
         "95% by day": f"{lo * 100:+.1f}..{hi * 100:+.1f}",
         "clears": dt.publishable(b)}
    ordered = b.sort_values("game_date")
    half = len(ordered) // 2
    r["early"] = round(float(ordered.profit.iloc[:half].mean()) * 100, 1)
    r["late"] = round(float(ordered.profit.iloc[half:].mean()) * 100, 1)
    for season in dt.TEST_SEASONS:
        q = b[b.season == season].profit
        r[f"{season - 1}-{str(season)[2:]}"] = (f"{q.mean() * 100:+.1f}% ({len(q)})" if len(q) >= 30
                                                else f"({len(q)})")
    return r


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    if rows:
        print(pd.DataFrame(rows).to_string(index=False))
    else:
        print("(no rows)")


def even_money(px: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """The line whose over is closest to -110, one per key. That is the main number."""
    d = px[px.over_price.notna()].copy()
    d["dist"] = (d.over_price + 110).abs()
    return d.sort_values("dist", kind="mergesort").drop_duplicates(keys)


def blind_rows(px: pd.DataFrame, actual: str, keys: list[str], seasons_col: str = "season") -> list[dict]:
    q = even_money(px, keys)
    rows = []
    for side, col in (("over", "over_price"), ("under", "under_price")):
        b = q[q[col].notna()].copy()
        b["profit"] = dt.profit(b[actual], b.total_line, b[col], side)
        b = b[b.profit.notna()]
        b["season"] = b[seasons_col]
        rows.append(_line({"side": side, "line": "closest to -110"}, b))
    return rows


def model_rows(sides: pd.DataFrame, keys: list[str], floor: float | None) -> list[dict]:
    rows = []
    by_side: dict[str, dict] = {}
    for side in ("over", "under"):
        by_cut = {}
        for cut in dt.EV_CUTS:
            b = dt.select_bets(sides, side=side, cut=cut, floor=floor, keys=keys)
            by_cut[cut] = b
            rows.append(_line({"side": side, "EV>=": cut, "floor": floor if floor is not None else "none"}, b))
        by_side[side] = by_cut
        ok = dt.neighbour_clears(by_cut)
        rows.append({"side": side, "EV>=": f"plateau {dt.PUBLISH_CUT}", "floor": floor, "clears": ok,
                     "bets": len(by_cut.get(dt.PUBLISH_CUT, []))})
    return rows


def team_sides(px: pd.DataFrame, pred: pd.DataFrame, actual_col: str) -> pd.DataFrame:
    """Team-total quotes joined to that team's mean. `actual_col` is already on `px`."""
    parts = []
    for market, home in (("team_totals_home", True), ("team_totals_away", False)):
        block = pred[pred.is_home.astype(float) == (1.0 if home else 0.0)][
            ["game_id", "team", "mu", "dispersion"]]
        q = px[px.market == market].merge(block, on="game_id", how="inner")
        q = q[q[actual_col].notna() & q["mu"].notna()]
        if q.empty:
            continue
        disp = float(np.nanmedian(q.dispersion)) if q.dispersion.notna().any() else 0.0
        parts.append(dt.side_frame(q, q["mu"].values, q.total_line.values, q.over_price.values,
                                   q.under_price.values, q[actual_col].values, disp))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def game_sides(px: pd.DataFrame, means: pd.DataFrame, market: str, mu_col: str,
               actual_col: str, dispersion: float) -> pd.DataFrame:
    q = px[px.market == market].merge(means[["game_id", mu_col]], on="game_id", how="inner")
    q = q[q[mu_col].notna() & q[actual_col].notna()]
    if q.empty:
        return q
    return dt.side_frame(q, q[mu_col].values, q.total_line.values, q.over_price.values,
                         q.under_price.values, q[actual_col].values, dispersion)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", default=None)
    a = ap.parse_args()
    team, periods, games, prices = load(a.cache)
    games = regulation(periods, games)
    px = pregame(prices, games)
    print(f"{len(px):,} pre-game derivative quotes, {px.game_id.nunique():,} games, "
          f"books {sorted(px.bookmaker.unique())}")

    frame = dt.build_team_frame(team)
    p1 = dt.build_p1_frame(periods, games)
    pred = dt.walk_forward(frame, p1)
    means = dt.game_means(pred)
    means = means.merge(games[["game_id", "total", "p1_total", "reg_home", "reg_away",
                               "home_score", "away_score"]], on="game_id", how="left")
    print(f"walk-forward team-games {len(pred):,}; games with both means {len(means):,}; "
          f"goal dispersion {pred.dispersion.iloc[0]:.3f}")

    bettable = sorted(b for b in px.bookmaker.unique() if b not in NON_BETTABLE)
    dk = px[px.bookmaker == "draftkings"]

    # ── blind, the market's own margin ──────────────────────────────────────
    show("BLIND alternate totals, DraftKings, the line closest to -110",
         blind_rows(dk[dk.market == "alternate_totals"], "total", ["game_id"]))
    show("BLIND 1st-period total, DraftKings, the line closest to -110",
         blind_rows(dk[dk.market == "totals_p1"], "p1_total", ["game_id"]))

    tt = px[px.market.isin(["team_totals_home", "team_totals_away"])].copy()
    tt["reg_side"] = np.where(tt.market.eq("team_totals_home"), tt.reg_home, tt.reg_away)
    tt["full_side"] = np.where(tt.market.eq("team_totals_home"), tt.home_score, tt.away_score)
    show("BLIND team total, FanDuel, regulation goals (3 periods)",
         blind_rows(tt[tt.bookmaker == "fanduel"], "reg_side", ["game_id", "market"]))
    show("BLIND team total, FanDuel, full-game goals (overtime included)",
         blind_rows(tt[tt.bookmaker == "fanduel"], "full_side", ["game_id", "market"]))

    # ── model ───────────────────────────────────────────────────────────────
    disp = float(pred.dispersion.median())
    p1_disp = float(pred.p1_dispersion.dropna().median()) if "p1_dispersion" in pred.columns else 0.0

    def report(title: str, sides: pd.DataFrame, keys: list[str]) -> None:
        if sides.empty:
            show(title, [])
            return
        show(title + " — price floor -200", model_rows(sides, keys, dt.PRICE_FLOOR))
        show(title + " — no price floor", model_rows(sides, keys, None))

    alt_dk = game_sides(dk, means, "alternate_totals", "mu_total", "total", disp)
    alt_bt = game_sides(px[px.bookmaker.isin(bettable)], means, "alternate_totals", "mu_total", "total", disp)
    report("MODEL alternate total, DraftKings", alt_dk, ["game_id"])
    report("MODEL alternate total, best bettable price", alt_bt, ["game_id"])

    p1_dk = game_sides(dk, means, "totals_p1", "mu_p1", "p1_total", p1_disp)
    p1_bt = game_sides(px[px.bookmaker.isin(bettable)], means, "totals_p1", "mu_p1", "p1_total", p1_disp)
    report("MODEL 1st-period total, DraftKings", p1_dk, ["game_id"])
    report("MODEL 1st-period total, best bettable price", p1_bt, ["game_id"])

    tt_reg = team_sides(tt[tt.bookmaker.isin(bettable)], pred, "reg_side")
    tt_full = team_sides(tt[tt.bookmaker.isin(bettable)], pred, "full_side")
    report("MODEL team total, best bettable price, REGULATION settlement", tt_reg, ["game_id", "team"])
    report("MODEL team total, best bettable price, FULL-GAME settlement", tt_full, ["game_id", "team"])

    # Ablation at the publish cut, best bettable, regulation / game total, floor -200.
    ablate = []
    for name, feats in (("no shots", [f for f in dt.GOAL_FEATURES if f not in dt.SHOT_FEATURES]),
                        ("no rest", [f for f in dt.GOAL_FEATURES if f not in dt.REST_FEATURES])):
        pred_a = dt.walk_forward(frame, p1, goal_features=feats)
        means_a = dt.game_means(pred_a).merge(games[["game_id", "total"]], on="game_id", how="left")
        sides = game_sides(px[px.bookmaker.isin(bettable)], means_a, "alternate_totals", "mu_total", "total",
                           float(pred_a.dispersion.median()))
        b = dt.select_bets(sides, side="under", cut=dt.PUBLISH_CUT, floor=dt.PRICE_FLOOR, keys=["game_id"])
        ablate.append(_line({"features": name, "market": "alternate", "side": "under"}, b))
        b = dt.select_bets(sides, side="over", cut=dt.PUBLISH_CUT, floor=dt.PRICE_FLOOR, keys=["game_id"])
        ablate.append(_line({"features": name, "market": "alternate", "side": "over"}, b))
    show(f"ABLATION alternate total, best bettable, EV>={dt.PUBLISH_CUT}, floor -200", ablate)

    print("\nPUBLISHED =", dt.PUBLISHED or "()  — nothing cleared, not publishing")


if __name__ == "__main__":
    main()

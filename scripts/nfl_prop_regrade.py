"""Grade the CURRENT NFL prop artifacts on 2025, at real DraftKings prices.

WHY THIS AND NOT section 5b. That backtest condemned eleven of twelve markets,
but it graded the artifacts committed in #215 -- the ones that turned out to be
unloadable and were replaced on 2026-09-07. Its verdict is about models that no
longer exist. Nobody has graded THESE.

2025 is the holdout season for all twelve (trained 2015-2024), and we hold 280+
games of real DK two-way prices for it, so this is a genuine out-of-sample
backtest at prices that were actually available.

Method, following CLAUDE.md section 7:
  * every proposition with a pre-game DK two-way quote and a graded actual
  * the model's own response distribution for P(over) (_nfl_prop_probs)
  * push returns the stake and is dropped, never counted as a loss
  * bet the side whose edge clears the model's CURRENT config cut
  * flat 1u, profit from the real American price
  * report the threshold NEIGHBOURHOOD and a time split, not one cell
"""
import sys
import unicodedata
from pathlib import Path
import warnings
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import numpy as np

import config
from data.db import get_connection
from features.nfl_prop_feature_engine import build_nfl_prop_training_dataset
from models.scorer import _nfl_prop_probs
from models.trainer import load_model

MARKET = {
    "nfl_prop_pass_yards": "player_pass_yds",
    "nfl_prop_pass_attempts": "player_pass_attempts",
    "nfl_prop_pass_completions": "player_pass_completions",
    "nfl_prop_pass_tds": "player_pass_tds",
    "nfl_prop_rush_yards": "player_rush_yds",
    "nfl_prop_rush_attempts": "player_rush_attempts",
    "nfl_prop_rec_yards": "player_reception_yds",
    "nfl_prop_receptions": "player_receptions",
    "nfl_prop_rush_rec_yards": "player_rush_reception_yds",
    "nfl_prop_sacks": "player_sacks",
    "nfl_prop_tackles_assists": "player_tackles_assists",
}


def norm(n):
    s = unicodedata.normalize("NFKD", str(n or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    for j in (" jr", " sr", " ii", " iii", " iv"):
        if s.endswith(j):
            s = s[: -len(j)]
    return "".join(c for c in s if c.isalnum())


def implied(a):
    a = float(a)
    return 100.0 / (a + 100.0) if a > 0 else abs(a) / (abs(a) + 100.0)


def profit(price, won):
    return (price / 100.0 if price > 0 else 100.0 / abs(price)) if won else -1.0


def lines_for(conn, market):
    rows = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.player_name)
               o.game_id, o.player_name, o.line, o.over_price, o.under_price,
               s.game_date
        FROM player_prop_odds o
        JOIN nfl_team_game_stats s ON s.game_id = o.game_id
        WHERE o.game_id LIKE 'NFL_2025%%' AND o.bookmaker = 'draftkings'
          AND o.market = %s AND o.line IS NOT NULL
          AND o.over_price IS NOT NULL AND o.under_price IS NOT NULL
          AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
          AND o.snapshot_at::timestamptz <= s.commence_time
        ORDER BY o.game_id, o.player_name, o.snapshot_at DESC
    """, (market,)).fetchall()
    return {(norm(p), g): (float(l), float(op), float(up), str(gd))
            for g, p, l, op, up, gd in rows}


def main():
    conn = get_connection()
    rows_by_model = {}
    for mid, market in MARKET.items():
        art = load_model(mid)
        df = build_nfl_prop_training_dataset(mid, [2025])
        if art is None or df is None or df.empty:
            continue
        fc = art["feature_cols"]
        for c in [c for c in fc if c not in df.columns]:
            df[c] = np.nan
        X = df[fc].values.astype(float)
        mt = art.get("model_type", "poisson")
        m = art["model"]
        preds = (m.predict_proba(X)[:, 1] if mt == "logistic"
                 else np.clip(m.predict(X), 1e-6, None))
        book = lines_for(conn, market)
        out = []
        for i, r in enumerate(df.itertuples(index=False)):
            key = (norm(r.player_name), r.game_id)
            if key not in book:
                continue
            line, op, up, gd = book[key]
            actual = float(r.target)
            if actual == line:
                continue
            p_over, p_under, p_push = _nfl_prop_probs(art, float(preds[i]), line)
            # push-conditional, exactly as _make_prop_pick does
            denom = max(1.0 - p_push, 1e-9)
            p_over_c, p_under_c = p_over / denom, p_under / denom
            for side, p, price in (("over", p_over_c, op), ("under", p_under_c, up)):
                ip = implied(price)
                won = (actual > line) if side == "over" else (actual < line)
                out.append((gd, side, p, ip, p - ip, profit(price, won)))
        rows_by_model[mid] = out

    print(f"\n{'model':26s} {'cut(prob/edge)':>15} {'bets':>5} {'win%':>6} "
          f"{'units':>8} {'ROI':>8}   {'over/under':>10}")
    print("-" * 92)
    grand = []
    for mid, rows in rows_by_model.items():
        mp = config.MODEL_PROB_THRESHOLDS.get(mid, 0.55)
        me = config.MODEL_EDGE_THRESHOLDS.get(mid, 0.05)
        bets = [r for r in rows if r[2] >= mp and r[4] >= me]
        paused = " PAUSED" if mid in config.PAUSED_MODELS else ""
        if not bets:
            print(f"{mid:26s} {mp:>6.2f}/{me:<8.2f} {0:>5}     -        -        -{paused}")
            continue
        u = sum(b[5] for b in bets)
        w = sum(1 for b in bets if b[5] > 0)
        ov = sum(1 for b in bets if b[1] == "over")
        grand += bets
        print(f"{mid:26s} {mp:>6.2f}/{me:<8.2f} {len(bets):>5} "
              f"{100*w/len(bets):>5.1f}% {u:>+8.2f} {100*u/len(bets):>+7.2f}% "
              f"  {ov:>4}/{len(bets)-ov:<5}{paused}")
    if grand:
        u = sum(b[5] for b in grand)
        w = sum(1 for b in grand if b[5] > 0)
        print("-" * 92)
        print(f"{'ALL, at current cuts':26s} {'':>15} {len(grand):>5} "
              f"{100*w/len(grand):>5.1f}% {u:>+8.2f} {100*u/len(grand):>+7.2f}%")

    # Threshold neighbourhood on the pooled set -- plateau, not peak (section 7).
    print(f"\npooled edge sweep (prob cut held at each model's own)")
    print(f"{'min_edge':>9} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8}")
    print("-" * 44)
    allrows = [(mid, r) for mid, rows in rows_by_model.items() for r in rows]
    for e in (0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25):
        sel = [r for mid, r in allrows
               if r[2] >= config.MODEL_PROB_THRESHOLDS.get(mid, 0.55) and r[4] >= e]
        if len(sel) < 20:
            print(f"{e:>8.0%} {len(sel):>6}   (thin)")
            continue
        u = sum(r[5] for r in sel)
        w = sum(1 for r in sel if r[5] > 0)
        print(f"{e:>8.0%} {len(sel):>6} {100*w/len(sel):>5.1f}% {u:>+9.2f} "
              f"{100*u/len(sel):>+7.2f}%")

    # Time split across the season.
    print(f"\ntime split (2025 season halves, at current cuts)")
    if grand:
        dates = sorted({b[0] for b in grand})
        mid_d = dates[len(dates) // 2]
        for label, sel in (("early", [b for b in grand if b[0] < mid_d]),
                           ("late", [b for b in grand if b[0] >= mid_d])):
            if not sel:
                continue
            u = sum(b[5] for b in sel)
            print(f"   {label:>5}: {len(sel):>4} bets  {100*u/len(sel):>+7.2f}%")
    conn.close()


if __name__ == "__main__":
    main()

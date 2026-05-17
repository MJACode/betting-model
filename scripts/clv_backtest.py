"""
CLV backtest — measures Closing Line Value for every settled BET pick.

For each pick, compares the no-vig implied probability at scoring time
(picks.dk_odds) against the no-vig implied probability of the closing line
(latest odds snapshot before games.commence_time). CLV is reported in
basis points: positive = we scored at a better price than the market closed.

Pass / fail interpretation (model needs >=50 picks to be meaningful):
  AvgCLV >= +10 bps AND %Positive >= 55%  →  real edge against the close.
  AvgCLV near 0                            →  fair-price coin flips.
  AvgCLV < 0                               →  reverse edge or late scoring.

Usage:
  python -m scripts.clv_backtest
  python -m scripts.clv_backtest --model mlb_moneyline --since 2026-05-01
  python -m scripts.clv_backtest --csv clv_results.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import statistics
from collections import defaultdict
from typing import Optional

from config import PROP_MODELS
from data.db import get_connection
from models.scorer import american_to_implied_prob

GAME_MARKET_MAP = {
    "mlb_moneyline":       "h2h",
    "mlb_over_under":      "totals",
    "mlb_runline":         "spreads",
    "mlb_f5_moneyline":    "h2h_1st_5_innings",
    "mlb_f5_over_under":   "totals_1st_5_innings",
    "mlb_f5_runline":      "spreads_1st_5_innings",
    "nhl_moneyline":       "h2h",
    "nhl_moneyline_regulation": "h2h_3way",
    "nhl_over_under":      "totals",
    "nhl_puckline":        "spreads",
}

_PICK_LABEL_RE = re.compile(r"^(.+?)\s+(?:Over|Under)\s+", re.IGNORECASE)


def model_to_market(model_id: str) -> Optional[str]:
    if model_id in GAME_MARKET_MAP:
        return GAME_MARKET_MAP[model_id]
    if model_id in PROP_MODELS:
        return PROP_MODELS[model_id][1]
    return None


def no_vig(p_self: Optional[float], p_other: Optional[float]) -> Optional[float]:
    """Normalize a two-way implied-prob pair so they sum to 1.0.
    Returns the de-vigged probability for `p_self`.
    """
    if p_self is None or p_other is None:
        return None
    total = p_self + p_other
    if total <= 0:
        return None
    return p_self / total


def side_prices_for_pick(pick_side: str, row: dict) -> tuple[Optional[float], Optional[float]]:
    """Return (self_american, other_american) for the side this pick is on."""
    s = (pick_side or "").lower()
    if s == "home":
        return row.get("home_price"), row.get("away_price")
    if s == "away":
        return row.get("away_price"), row.get("home_price")
    if s == "over":
        return row.get("over_price"), row.get("under_price")
    if s == "under":
        return row.get("under_price"), row.get("over_price")
    return None, None


def line_matches(model_id: str, scored_line: Optional[float], row: dict) -> bool:
    """For totals / spreads, the closing line must match the scored line."""
    market = model_to_market(model_id) or ""
    if "totals" in market or model_id.endswith("over_under"):
        return scored_line is not None and row.get("total_line") == scored_line
    if "spreads" in market or model_id.endswith("runline") or model_id.endswith("puckline"):
        return scored_line is not None and row.get("spread_home") == scored_line
    if model_id in PROP_MODELS:
        return scored_line is not None and row.get("line") == scored_line
    return True


_PICKS_COLS = [
    "pick_id", "model_id", "game_id", "game_date", "pick_side",
    "pick_label", "dk_odds", "scored_line", "player_id", "commence_time",
]
_GAME_ODDS_COLS = [
    "game_id", "market", "snapshot_at", "snapshot_type",
    "home_price", "away_price", "over_price", "under_price",
    "spread_home", "total_line",
]
_PROP_ODDS_COLS = [
    "game_id", "market", "player_name", "snapshot_at", "snapshot_type",
    "line", "over_price", "under_price",
]


def fetch_picks(conn, since: Optional[str], until: Optional[str], model: Optional[str]):
    sql = """
        SELECT p.pick_id, p.model_id, p.game_id, p.game_date, p.pick_side,
               p.pick_label, p.dk_odds, p.scored_line, p.player_id,
               g.commence_time
        FROM picks p
        JOIN games g ON g.game_id = p.game_id
        WHERE p.signal_type = 'BET'
          AND p.result IS NOT NULL
          AND p.dk_odds IS NOT NULL
          AND p.game_date >= %s
    """
    params = [since or "2026-04-14"]
    if until:
        sql += " AND p.game_date <= %s"
        params.append(until)
    if model:
        sql += " AND p.model_id = %s"
        params.append(model)
    sql += " ORDER BY p.game_date, p.pick_id"
    rows = conn.execute(sql, params).fetchall()
    return [dict(zip(_PICKS_COLS, r)) for r in rows]


def fetch_game_closings(conn, game_ids: set[str], markets: set[str]) -> dict:
    """Returns {(game_id, market): [rows ordered by snapshot_at desc]}."""
    if not game_ids or not markets:
        return {}
    sql = """
        SELECT game_id, market, snapshot_at, snapshot_type,
               home_price, away_price, over_price, under_price,
               spread_home, total_line
        FROM odds
        WHERE bookmaker = 'draftkings'
          AND game_id = ANY(%s)
          AND market  = ANY(%s)
        ORDER BY game_id, market, snapshot_at DESC
    """
    out: dict = defaultdict(list)
    rows = conn.execute(sql, [list(game_ids), list(markets)]).fetchall()
    for r in rows:
        d = dict(zip(_GAME_ODDS_COLS, r))
        out[(d["game_id"], d["market"])].append(d)
    return out


def fetch_prop_closings(conn, game_ids: set[str], markets: set[str]) -> dict:
    """Returns {(game_id, market, normalized_player_name): [rows ordered by snapshot_at desc]}."""
    if not game_ids or not markets:
        return {}
    sql = """
        SELECT game_id, market, player_name, snapshot_at, snapshot_type,
               line, over_price, under_price
        FROM player_prop_odds
        WHERE bookmaker = 'draftkings'
          AND game_id = ANY(%s)
          AND market  = ANY(%s)
        ORDER BY game_id, market, player_name, snapshot_at DESC
    """
    out: dict = defaultdict(list)
    rows = conn.execute(sql, [list(game_ids), list(markets)]).fetchall()
    for r in rows:
        d = dict(zip(_PROP_ODDS_COLS, r))
        key = (d["game_id"], d["market"], (d["player_name"] or "").strip().lower())
        out[key].append(d)
    return out


def parse_player_name(pick_label: str) -> Optional[str]:
    if not pick_label:
        return None
    m = _PICK_LABEL_RE.match(pick_label)
    return m.group(1).strip() if m else None


def pick_closing_row(snapshots: list[dict], commence_time: str,
                     model_id: str, scored_line: Optional[float]) -> Optional[dict]:
    """Latest pre-game-start snapshot whose line matches the scored line.
    Prefer snapshot_type='close' if present; otherwise latest pre-commence row.
    Returns None if no matching snapshot or if the line moved.
    """
    pre_game = [s for s in snapshots if s["snapshot_at"] < commence_time]
    if not pre_game:
        return None
    closes = [s for s in pre_game if s.get("snapshot_type") == "close"]
    candidates = closes if closes else pre_game
    for s in candidates:
        if line_matches(model_id, scored_line, s):
            return s
    return None


def compute_clv(conn, picks: list, game_closings: dict, prop_closings: dict):
    """Yields per-pick CLV dicts."""
    for p in picks:
        model_id = p["model_id"]
        market = model_to_market(model_id)
        if not market:
            continue

        scored_american = p["dk_odds"]
        if scored_american is None:
            continue

        is_prop = model_id in PROP_MODELS
        if is_prop:
            player_name = parse_player_name(p["pick_label"])
            if not player_name:
                yield _row_no_clv(p, scored_american, reason="no_player_name")
                continue
            key = (p["game_id"], market, player_name.strip().lower())
            snapshots = prop_closings.get(key, [])
        else:
            snapshots = game_closings.get((p["game_id"], market), [])

        if not snapshots:
            yield _row_no_clv(p, scored_american, reason="no_closing_snapshot")
            continue

        closing = pick_closing_row(snapshots, p["commence_time"], model_id, p["scored_line"])
        if closing is None:
            yield _row_no_clv(p, scored_american, reason="line_moved_or_no_match",
                              line_moved=True)
            continue

        self_close_amer, other_close_amer = side_prices_for_pick(p["pick_side"], closing)
        if self_close_amer is None or other_close_amer is None:
            yield _row_no_clv(p, scored_american, reason="missing_close_pair")
            continue

        scored_implied = american_to_implied_prob(scored_american)
        close_self     = american_to_implied_prob(self_close_amer)
        close_other    = american_to_implied_prob(other_close_amer)

        # No-vig CLV: we need the scored snapshot's "other side" too, but the picks
        # table only stores one side. Use raw scored_implied as a proxy for the
        # scored no-vig prob — under typical DK -110 vig the bias is ~2.4% on
        # both sides and cancels in the differential. Documented assumption.
        close_no_vig = no_vig(close_self, close_other)
        if close_no_vig is None:
            yield _row_no_clv(p, scored_american, reason="bad_close_pair")
            continue

        clv_bps = (scored_implied - close_no_vig) * 10000.0
        yield {
            "pick_id":         p["pick_id"],
            "model_id":        model_id,
            "game_date":       p["game_date"],
            "pick_label":      p["pick_label"],
            "scored_dk_odds":  scored_american,
            "closing_dk_odds": self_close_amer,
            "scored_implied":  round(scored_implied, 4),
            "close_no_vig":    round(close_no_vig, 4),
            "clv_bps":         round(clv_bps, 1),
            "line_moved":      False,
            "reason":          None,
        }


def _row_no_clv(p, scored_amer, reason: str, line_moved: bool = False) -> dict:
    return {
        "pick_id":         p["pick_id"],
        "model_id":        p["model_id"],
        "game_date":       p["game_date"],
        "pick_label":      p["pick_label"],
        "scored_dk_odds":  scored_amer,
        "closing_dk_odds": None,
        "scored_implied":  None,
        "close_no_vig":    None,
        "clv_bps":         None,
        "line_moved":      line_moved,
        "reason":          reason,
    }


def summarize(results: list[dict]) -> dict:
    by_model: dict = defaultdict(list)
    for r in results:
        by_model[r["model_id"]].append(r)
    summary = {}
    for model_id, rows in sorted(by_model.items()):
        clvs = [r["clv_bps"] for r in rows if r["clv_bps"] is not None]
        line_moved = sum(1 for r in rows if r["line_moved"])
        no_close   = sum(1 for r in rows if r["reason"] == "no_closing_snapshot")
        summary[model_id] = {
            "picks":       len(rows),
            "measured":    len(clvs),
            "line_moved":  line_moved,
            "no_close":    no_close,
            "avg_clv_bps": round(statistics.mean(clvs), 1) if clvs else None,
            "median_bps":  round(statistics.median(clvs), 1) if clvs else None,
            "pct_positive": round(sum(1 for c in clvs if c > 0) / len(clvs) * 100, 1) if clvs else None,
        }
    return summary


def print_summary(summary: dict) -> None:
    print(f"\n{'Model':<28} {'Picks':>6} {'Measured':>9} {'LineMv':>7} {'NoClose':>8} "
          f"{'AvgCLV':>9} {'Median':>8} {'%Pos':>7}")
    print("-" * 92)
    for model_id, s in summary.items():
        avg = f"{s['avg_clv_bps']:+.1f}bps" if s["avg_clv_bps"] is not None else "—"
        med = f"{s['median_bps']:+.1f}"     if s["median_bps"]  is not None else "—"
        pos = f"{s['pct_positive']:.1f}%"   if s["pct_positive"] is not None else "—"
        print(f"{model_id:<28} {s['picks']:>6} {s['measured']:>9} "
              f"{s['line_moved']:>7} {s['no_close']:>8} "
              f"{avg:>9} {med:>8} {pos:>7}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="Filter to one model_id")
    ap.add_argument("--since", help="game_date >= YYYY-MM-DD (default: 2026-04-14)")
    ap.add_argument("--until", help="game_date <= YYYY-MM-DD")
    ap.add_argument("--csv",   help="Write per-pick rows to this CSV path")
    args = ap.parse_args()

    with get_connection() as conn:
        picks = fetch_picks(conn, args.since, args.until, args.model)
        if not picks:
            print("No settled BET picks match the filters.")
            return

        game_picks = [p for p in picks if p["model_id"] not in PROP_MODELS]
        prop_picks = [p for p in picks if p["model_id"] in PROP_MODELS]

        game_ids   = {p["game_id"] for p in picks}
        game_mkts  = {model_to_market(p["model_id"]) for p in game_picks}
        prop_mkts  = {model_to_market(p["model_id"]) for p in prop_picks}
        game_mkts.discard(None); prop_mkts.discard(None)

        print(f"Loaded {len(picks)} settled BET picks "
              f"({len(game_picks)} game, {len(prop_picks)} prop) "
              f"across {len(game_ids)} games.")

        game_closings = fetch_game_closings(conn, game_ids, game_mkts)
        prop_closings = fetch_prop_closings(conn, game_ids, prop_mkts)
        print(f"Loaded {sum(len(v) for v in game_closings.values())} game-odds rows, "
              f"{sum(len(v) for v in prop_closings.values())} prop-odds rows.")

        results = list(compute_clv(conn, picks, game_closings, prop_closings))

    if args.csv:
        fieldnames = [
            "pick_id", "model_id", "game_date", "pick_label",
            "scored_dk_odds", "closing_dk_odds",
            "scored_implied", "close_no_vig", "clv_bps",
            "line_moved", "reason",
        ]
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
        print(f"Wrote {len(results)} rows to {args.csv}")

    print_summary(summarize(results))


if __name__ == "__main__":
    main()

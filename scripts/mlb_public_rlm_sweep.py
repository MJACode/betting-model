"""Leak-bounded 2026 public RLM / steam grader. Measure only.

`public_betting` is UNIQUE(game_id, market, side, book) — last upsert wins.
Most stored snapshots sit after first pitch, so a naive last-row read is a
post-start split. This sweep keeps a row only when
`features.feature_engine._is_pregame_snapshot` says so (timestamptz + trusted
first pitch when present). Prices are the latest DraftKings OPEN quote with
`snapshot_at <= games.commence_time`.

Public splits exist from 2026-05-31. They cannot train 2019–2025. August 2026
honest pregame coverage is empty because last-upsert already overwrote it.

Does not publish, pause, or unpause. Does not write `picks`.

    python -m scripts.mlb_public_rlm_sweep
    python -m scripts.mlb_public_rlm_sweep --steam --by-month
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import get_connection
from features.feature_engine import _is_pregame_snapshot
from scripts.game_line_market_sweep import (
    _by_month,
    _print_table,
    _split_halves,
    _summarize,
    grade,
    iter_months,
)


BOOK = "draftkings"
FADE_OVER_TIX = (65, 70, 75, 80)
RLM_GAPS = (10, 15, 20)
STEAM_PTS = (0.5, 1.0)


def _f(x):
    return None if x is None else float(x)


def load_public_rows(conn, date_from: str, date_to: str) -> list[dict]:
    """One dict per (game, market) with both sides, DK price, and the score."""
    raw = conn.execute("""
        SELECT pb.game_id, pb.game_date::text, pb.market, pb.side,
               pb.public_bet_pct, pb.public_money_pct, pb.snapshot_at,
               g.commence_time, g.first_pitch_at,
               g.home_score, g.away_score
        FROM public_betting pb
        JOIN games g ON g.game_id = pb.game_id
        WHERE g.sport = 'MLB'
          AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
          AND g.game_date >= %s AND g.game_date < %s
          AND pb.snapshot_at::timestamptz <= g.commence_time::timestamptz
        ORDER BY pb.game_id, pb.market, pb.side, pb.snapshot_at DESC
    """, (date_from, date_to)).fetchall()
    latest: dict[tuple, dict] = {}
    for (gid, gd, market, side, tix, money, snap, commence, fp,
         hs, as_) in raw:
        if not _is_pregame_snapshot(snap, commence, fp):
            continue
        key = (gid, market, side)
        if key in latest:
            continue
        latest[key] = dict(
            game_id=gid, game_date=str(gd)[:10], market=market, side=side,
            tix=_f(tix), money=_f(money), home_score=float(hs),
            away_score=float(as_),
        )
    by_gm: dict[tuple, dict] = {}
    for row in latest.values():
        k = (row["game_id"], row["market"])
        slot = by_gm.setdefault(k, {
            "game_id": row["game_id"], "game_date": row["game_date"],
            "market": row["market"],
            "home_score": row["home_score"], "away_score": row["away_score"],
            "tix_home": None, "money_home": None,
            "tix_away": None, "money_away": None,
            "tix_over": None, "money_over": None,
            "tix_under": None, "money_under": None,
        })
        side = row["side"]
        if side in ("home", "away", "over", "under"):
            slot[f"tix_{side}"] = row["tix"]
            slot[f"money_{side}"] = row["money"]
    rows = list(by_gm.values())
    if not rows:
        return []
    ids = list({r["game_id"] for r in rows})
    dk = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.market)
               o.game_id, o.market, o.home_price, o.away_price,
               o.spread_home, o.total_line, o.over_price, o.under_price
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE o.sport = 'MLB' AND o.bookmaker = 'draftkings'
          AND o.snapshot_type = 'open'
          AND o.market IN ('h2h', 'spreads', 'totals')
          AND o.game_id = ANY(%s)
          AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
        ORDER BY o.game_id, o.market, o.snapshot_at DESC
    """, (ids,)).fetchall()
    pin = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.market)
               o.game_id, o.market, o.home_price, o.away_price,
               o.spread_home, o.total_line, o.over_price, o.under_price
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE o.sport = 'MLB' AND o.bookmaker = 'pinnacle'
          AND o.snapshot_type = 'open'
          AND o.market IN ('h2h', 'spreads', 'totals')
          AND o.game_id = ANY(%s)
          AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
        ORDER BY o.game_id, o.market, o.snapshot_at DESC
    """, (ids,)).fetchall()
    dk_map = {(r[0], r[1]): r for r in dk}
    pin_map = {(r[0], r[1]): r for r in pin}
    out = []
    for row in rows:
        q = dk_map.get((row["game_id"], row["market"]))
        if not q:
            continue
        row["home_price"] = _f(q[2])
        row["away_price"] = _f(q[3])
        row["spread_home"] = _f(q[4])
        row["total_line"] = _f(q[5])
        row["over_price"] = _f(q[6])
        row["under_price"] = _f(q[7])
        p = pin_map.get((row["game_id"], row["market"]))
        if p:
            row["pin_home"] = _f(p[2])
            row["pin_away"] = _f(p[3])
            row["pin_spread"] = _f(p[4])
            row["pin_total"] = _f(p[5])
            row["pin_over"] = _f(p[6])
            row["pin_under"] = _f(p[7])
        else:
            row["pin_home"] = row["pin_away"] = None
            row["pin_spread"] = row["pin_total"] = None
            row["pin_over"] = row["pin_under"] = None
        out.append(row)
    return out


def _pick(row, side, price, line) -> tuple | None:
    if price is None:
        return None
    won = grade(row["market"], side,
                (row["home_score"], row["away_score"], row["game_date"]),
                line)
    return (row["game_date"], 1.0, float(price), won, BOOK)


def _pin_leans(row, side: str) -> bool | None:
    """True when Pinnacle's no-vig prefers `side`. None if unpriceable / unequal line."""
    from scripts.game_line_market_sweep import devig
    m = row["market"]
    if m == "totals":
        if row["pin_total"] is None or row["total_line"] is None:
            return None
        if float(row["pin_total"]) != float(row["total_line"]):
            return None
        over, under = devig(row["pin_over"], row["pin_under"])
        if over is None:
            return None
        return (over >= under) if side == "over" else (under > over)
    if m == "spreads":
        if row["pin_spread"] is None or row["spread_home"] is None:
            return None
        if float(row["pin_spread"]) != float(row["spread_home"]):
            return None
        home, away = devig(row["pin_home"], row["pin_away"])
        if home is None:
            return None
        return (home >= away) if side == "home" else (away > home)
    home, away = devig(row["pin_home"], row["pin_away"])
    if home is None:
        return None
    return (home >= away) if side == "home" else (away > home)


def collect_public_strategies(rows: list[dict]) -> dict[str, list]:
    """Named strategy → list of (date, edge, price, won, book) for _summarize."""
    out: dict[str, list] = defaultdict(list)
    totals = [r for r in rows if r["market"] == "totals"]
    spreads = [r for r in rows if r["market"] == "spreads"]
    h2h = [r for r in rows if r["market"] == "h2h"]

    for r in totals:
        p = _pick(r, "under", r["under_price"], r["total_line"])
        if p:
            out["control_always_under"].append(p)
        p = _pick(r, "over", r["over_price"], r["total_line"])
        if p:
            out["control_always_over"].append(p)
        tix = r["tix_over"]
        for thr in FADE_OVER_TIX:
            if tix is not None and tix >= thr:
                p = _pick(r, "under", r["under_price"], r["total_line"])
                if p:
                    out[f"fade_public_over_tix_{thr}"].append(p)
                if thr == 70 and _pin_leans(r, "under") is True:
                    p = _pick(r, "under", r["under_price"], r["total_line"])
                    if p:
                        out["hybrid_fade_over_70_pin_lean_under"].append(p)
        if r["tix_over"] is not None and r["money_over"] is not None:
            rlm = r["money_over"] - r["tix_over"]
            for gap in RLM_GAPS:
                if abs(rlm) < gap:
                    continue
                side = "over" if rlm > 0 else "under"
                price = r["over_price"] if side == "over" else r["under_price"]
                p = _pick(r, side, price, r["total_line"])
                if p:
                    out[f"totals_follow_rlm_{gap}"].append(p)

    for r in spreads:
        sh = r["spread_home"]
        if sh is None:
            continue
        fav_side = "home" if sh < 0 else ("away" if sh > 0 else None)
        if fav_side:
            tix = r[f"tix_{fav_side}"]
            money = r[f"money_{fav_side}"]
            dog = "away" if fav_side == "home" else "home"
            dog_price = r["away_price"] if dog == "away" else r["home_price"]
            if tix is not None and money is not None:
                if tix >= 70 and money <= 45:
                    p = _pick(r, dog, dog_price, sh)
                    if p:
                        out["fade_public_fav_rl_tix70_money45"].append(p)
                if tix >= 65 and money <= 50:
                    p = _pick(r, dog, dog_price, sh)
                    if p:
                        out["fade_public_fav_rl_tix65_money50"].append(p)
        if r["tix_home"] is not None and r["money_home"] is not None:
            rlm = r["money_home"] - r["tix_home"]
            for gap in RLM_GAPS:
                if abs(rlm) < gap:
                    continue
                side = "home" if rlm > 0 else "away"
                price = r["home_price"] if side == "home" else r["away_price"]
                p = _pick(r, side, price, sh)
                if p:
                    out[f"spreads_follow_rlm_{gap}"].append(p)

    from scripts.game_line_market_sweep import implied
    for r in h2h:
        if r["tix_home"] is not None and r["money_home"] is not None:
            rlm = r["money_home"] - r["tix_home"]
            for gap in RLM_GAPS:
                if abs(rlm) < gap:
                    continue
                side = "home" if rlm > 0 else "away"
                price = r["home_price"] if side == "home" else r["away_price"]
                p = _pick(r, side, price, None)
                if p:
                    out[f"h2h_follow_rlm_{gap}"].append(p)
        hp, ap = r["home_price"], r["away_price"]
        if hp is None or ap is None:
            continue
        home_fav = implied(hp) > implied(ap)
        tix_fav = r["tix_home"] if home_fav else r["tix_away"]
        for thr in (70, 75):
            if tix_fav is None or tix_fav < thr:
                continue
            side = "away" if home_fav else "home"
            price = r["away_price"] if home_fav else r["home_price"]
            p = _pick(r, side, price, None)
            if p:
                out[f"fade_public_ml_fav_tix_{thr}"].append(p)
    return dict(out)


def load_steam_moves(conn, date_from: str, date_to: str) -> list[dict]:
    """Earliest vs latest leak-bounded DK OPEN total, month-chunked."""
    out = []
    for start, stop in iter_months(date_from, date_to):
        pad = (date.fromisoformat(start) - timedelta(days=14)).isoformat()
        rows = conn.execute("""
            SELECT o.game_id, o.total_line, o.over_price, o.under_price,
                   o.snapshot_at, g.commence_time, g.first_pitch_at,
                   g.home_score, g.away_score, g.game_date::text
            FROM odds o
            JOIN games g ON g.game_id = o.game_id
            WHERE o.sport = 'MLB' AND o.market = 'totals'
              AND o.bookmaker = 'draftkings' AND o.snapshot_type = 'open'
              AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
              AND g.game_date >= %s AND g.game_date < %s
              AND o.snapshot_at >= %s AND o.snapshot_at < %s
              AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
            ORDER BY o.game_id, o.snapshot_at ASC
        """, (start, stop, pad, stop)).fetchall()
        first: dict = {}
        last: dict = {}
        for (gid, line, op, up, snap, commence, fp, hs, as_, gd) in rows:
            if not _is_pregame_snapshot(snap, commence, fp):
                continue
            rec = dict(line=_f(line), over=_f(op), under=_f(up),
                       hs=float(hs), as_=float(as_), gd=str(gd)[:10])
            first.setdefault(gid, rec)
            last[gid] = rec
        for gid, a in first.items():
            b = last.get(gid)
            if not b or a["line"] is None or b["line"] is None:
                continue
            move = b["line"] - a["line"]
            out.append({
                "game_id": gid, "game_date": b["gd"], "move": move,
                "line": b["line"], "over_price": b["over"],
                "under_price": b["under"],
                "home_score": b["hs"], "away_score": b["as_"],
            })
    return out


def collect_steam(rows: list[dict]) -> dict[str, list]:
    out: dict[str, list] = defaultdict(list)
    for r in rows:
        move = r["move"]
        for pts in STEAM_PTS:
            if abs(move) < pts:
                continue
            follow = "over" if move > 0 else "under"
            fade = "under" if move > 0 else "over"
            for name, side in ((f"steam_follow_{pts}", follow),
                               (f"steam_fade_{pts}", fade)):
                price = r["over_price"] if side == "over" else r["under_price"]
                if price is None:
                    continue
                won = grade("totals", side,
                            (r["home_score"], r["away_score"], r["game_date"]),
                            r["line"])
                out[name].append((r["game_date"], 1.0, float(price), won, BOOK))
    return dict(out)


def _block(picks, by_month: bool) -> dict:
    pooled = _summarize(picks, [1.0])
    row = pooled[0] if pooled else {"n": 0}
    block = {"n": row.get("n", 0), "pooled": row}
    if by_month:
        block["by_month"] = {
            m: (_summarize(v, [1.0])[0] if v else {"n": 0})
            for m, v in _by_month(picks, [1.0]).items()
        }
        block["halves"] = _split_halves(picks, [1.0])
    return block


def run(date_from: str | None = "2026-05-31", date_to: str | None = None,
        steam: bool = False, by_month: bool = True) -> dict:
    if date_to is None:
        date_to = (date.today() + timedelta(days=1)).isoformat()
    conn = get_connection()
    try:
        rows = load_public_rows(conn, date_from, date_to)
        strategies = collect_public_strategies(rows)
        out = {
            "date_from": date_from,
            "date_to": date_to,
            "n_games": len({r["game_id"] for r in rows}),
            "n_rows": len(rows),
            "strategies": {},
        }
        print(f"\n=== MLB public RLM  {date_from}..{date_to}  "
              f"{out['n_games']} games / {out['n_rows']} market-rows")
        for name, picks in sorted(strategies.items()):
            out["strategies"][name] = _block(picks, by_month)
            legacy = [(1.0, out["strategies"][name]["pooled"].get("n", 0),
                       out["strategies"][name]["pooled"].get("win_pct"),
                       out["strategies"][name]["pooled"].get("roi_pct"),
                       tuple(out["strategies"][name]["pooled"]["ci90"])
                       if out["strategies"][name]["pooled"].get("ci90")
                       else None)]
            print(f"  -- {name}")
            _print_table(legacy)
        if steam:
            steam_rows = load_steam_moves(conn, "2026-03-20", date_to)
            steam_strats = collect_steam(steam_rows)
            out["steam_n_games"] = len(steam_rows)
            out["steam"] = {}
            print(f"\n=== DK totals steam (first vs last OPEN)  "
                  f"{out['steam_n_games']} games")
            for name, picks in sorted(steam_strats.items()):
                out["steam"][name] = _block(picks, by_month)
                b = out["steam"][name]["pooled"]
                legacy = [(1.0, b.get("n", 0), b.get("win_pct"),
                           b.get("roi_pct"),
                           tuple(b["ci90"]) if b.get("ci90") else None)]
                print(f"  -- {name}")
                _print_table(legacy)
        return out
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", default="2026-05-31")
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--steam", action="store_true")
    ap.add_argument("--by-month", action="store_true")
    a = ap.parse_args()
    run(date_from=a.date_from, date_to=a.date_to,
        steam=a.steam, by_month=a.by_month or True)


if __name__ == "__main__":
    main()

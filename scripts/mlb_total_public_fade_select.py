"""Replicate / stress the mlb_total_public_fade selection cells.

WHY THIS EXISTS
---------------
The blunt t70 fade fires on ~80% of the honest 2026 public window and
wrote UNDER on 12/12 games on 2026-09-19. This script grades the
selective candidates (public steam, juice floor, slate cap, top-1)
against the same shop the card uses, with month holdout and bootstrap.

It writes nothing to `picks`. PUBLISH stays 0.

    python -m scripts.mlb_total_public_fade_select
    python -m scripts.mlb_total_public_fade_select --date-from 2026-05-31 --date-to 2026-09-20

Run where the DB is reachable (Railway worker or Matt's machine). MCP
unbounded odds scans time out — this month-chunks like
`scripts/game_line_market_sweep.py`.
"""
from __future__ import annotations

import argparse
import random
from datetime import date, timedelta
from pathlib import Path
import sys

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.mlb_game_market as mk
import models.mlb_total_public_fade as fade

SNAPSHOT_PAD_DAYS = 14
BOOTSTRAP_N = 5000
BOOTSTRAP_SEED = 19


def bootstrap_roi(units: list[float], n: int = BOOTSTRAP_N,
                  seed: int = BOOTSTRAP_SEED
                  ) -> tuple[float, float, float, float] | None:
    """Mean / 2.5% / 97.5% / P(roi>0) of a flat-bet ROI resample."""
    if not units:
        return None
    rng = random.Random(seed)
    k = len(units)
    rois = []
    for _ in range(n):
        sample = [units[rng.randrange(k)] for _ in range(k)]
        rois.append(sum(sample) / k)
    rois.sort()
    mean = sum(rois) / n
    lo = rois[int(0.025 * n)]
    hi = rois[min(n - 1, int(0.975 * n))]
    ppos = sum(1 for r in rois if r > 0) / n
    return mean, lo, hi, ppos


def month_holdout(rows: list[dict]) -> list[dict]:
    """Leave-one-month-out on graded rows with a `month` and `units`."""
    months = sorted({r["month"] for r in rows})
    out = []
    for m in months:
        train = [r for r in rows if r["month"] != m]
        test = [r for r in rows if r["month"] == m]
        out.append({
            "hold": m,
            "train": _cell(train),
            "test": _cell(test),
        })
    return out


def _cell(rows: list[dict]) -> dict:
    action = [r for r in rows if r.get("result") in ("WIN", "LOSS")]
    n = len(action)
    units = sum(r["units"] for r in action)
    wins = sum(1 for r in action if r["result"] == "WIN")
    losses = n - wins
    roi = (units / n) if n else None
    return {"n": n, "wins": wins, "losses": losses, "units": units, "roi": roi}


def _fmt(cell: dict) -> str:
    if not cell["n"]:
        return "n=0"
    roi = cell["roi"]
    return (f"n={cell['n']:3d}  {cell['wins']}-{cell['losses']}  "
            f"u={cell['units']:+.2f}  roi={roi*100:+.1f}%")


def load_public_window(conn, date_from: str, date_to: str):
    rows = conn.execute("""
        SELECT pb.game_id, pb.public_bet_pct, pb.public_money_pct,
               pb.snapshot_at, g.commence_time, g.game_date,
               g.home_score, g.away_score
        FROM public_betting pb
        JOIN games g ON g.game_id = pb.game_id
        WHERE pb.market = 'totals'
          AND pb.side = 'over'
          AND pb.book = 'consensus'
          AND g.sport = 'MLB'
          AND g.game_date >= %s AND g.game_date < %s
    """, (date_from, date_to)).fetchall()
    parsed = []
    scores = {}
    for r in rows:
        parsed.append({
            "game_id": r[0],
            "public_bet_pct": r[1],
            "public_money_pct": r[2],
            "snapshot_at": r[3],
            "commence_time": r[4],
            "ticket": r[1],
            "over_money_pct": r[2],
            "game_date": None if r[5] is None else str(r[5])[:10],
        })
        scores[r[0]] = (r[6], r[7], None if r[5] is None else str(r[5])[:10])
    splits = fade.select_latest_pre_commence_over(parsed)
    return splits, scores


def iter_months(date_from: str, date_to: str):
    start = date.fromisoformat(date_from[:10])
    end = date.fromisoformat(date_to[:10])
    d = start.replace(day=1)
    while d < end:
        nxt = date(d.year + (d.month == 12),
                   1 if d.month == 12 else d.month + 1, 1)
        a = max(d, start).isoformat()
        b = min(nxt, end).isoformat()
        if a < b:
            yield a, b
        d = nxt


def load_quotes_chunked(conn, game_ids: list[str],
                        date_from: str, date_to: str) -> dict:
    quotes = {}
    for start, stop in iter_months(date_from, date_to):
        pad = (date.fromisoformat(start) - timedelta(days=SNAPSHOT_PAD_DAYS)
               ).isoformat()
        month_ids = [gid for gid in game_ids
                     if len(gid) >= 14 and start <= gid[4:14] < stop]
        if not month_ids:
            continue
        quotes.update(mk.load_latest_quotes(conn, fade.SPORT, fade.MARKET,
                                            month_ids))
        logger.info(f"quotes {start}→{stop}: {len(month_ids)} games")
    return quotes


def grade_bets(bets, scores) -> list[dict]:
    rows = []
    for b in bets:
        hs, as_, gdate = scores.get(b.game_id, (None, None, b.game_date))
        month = (gdate or b.game_date or "")[:7]
        rec = {
            "game_id": b.game_id,
            "date": gdate or b.game_date,
            "month": month,
            "tix": b.over_ticket_pct,
            "money": b.over_money_pct,
            "price": b.price,
            "line": b.line,
            "book": b.book,
            "steam": fade.is_public_steam(b.over_ticket_pct, b.over_money_pct),
            "juice115": fade.juice_ok(b.price, -115),
        }
        if hs is None or as_ is None:
            rec.update(result=None, units=None, settled=False)
            rows.append(rec)
            continue
        result, units = fade.grade_under(float(hs) + float(as_), b.line, b.price)
        rec.update(result=result, units=units, settled=True)
        rows.append(rec)
    return rows


def report(name: str, rows: list[dict]) -> dict:
    cell = _cell(rows)
    logger.info(f"{name:42s} {_fmt(cell)}")
    return {"name": name, **cell, "rows": rows}


def run(date_from: str, date_to: str) -> dict:
    from data.db import get_connection

    conn = get_connection()
    try:
        splits, scores = load_public_window(conn, date_from, date_to)
        gids = list(splits)
        quotes = load_quotes_chunked(conn, gids, date_from, date_to)
    finally:
        conn.close()

    # Priced universe: blunt cut 0 so every shoppable under is a row.
    universe, diag = fade.find_fade_bets(splits, quotes, min_over_tickets=0)
    logger.info(f"honest public {len(splits)}  priced {len(universe)}  "
                f"diag={diag}")
    graded = grade_bets(universe, scores)
    settled = [r for r in graded if r.get("settled")]

    cells = []
    cells.append(report("priced universe (blind under)", settled))
    cells.append(report("blunt t70", [r for r in settled if r["tix"] >= 70]))
    steam = [r for r in settled if r["tix"] >= 75 and r["steam"]]
    cells.append(report("steam75 money>=tix", steam))
    steam_j = [r for r in steam if r["juice115"]]
    cells.append(report("steam75 + juice>=-115", steam_j))
    cells.append(report("t80 + juice>=-115",
                        [r for r in settled if r["tix"] >= 80 and r["juice115"]]))

    # Slate-capped steam via the finder (same ranking as production).
    steam_bets, _ = fade.select_fade_bets(
        splits, quotes, rule=fade.RULE_STEAM, min_under_price=None)
    steam_capped = grade_bets(steam_bets, scores)
    cells.append(report("steam75 cap2 (finder)",
                        [r for r in steam_capped if r.get("settled")]))

    juice_bets, _ = fade.select_fade_bets(
        splits, quotes, rule=fade.RULE_STEAM, min_under_price=-115)
    cells.append(report("steam75 + juice>=-115 cap2",
                        [r for r in grade_bets(juice_bets, scores)
                         if r.get("settled")]))

    logger.info("month holdout — steam75 (no juice, no cap)")
    for h in month_holdout(steam):
        logger.info(f"  hold {h['hold']}: train {_fmt(h['train'])}  "
                    f"test {_fmt(h['test'])}")
    logger.info("month holdout — steam75 cap2")
    for h in month_holdout([r for r in steam_capped if r.get("settled")]):
        logger.info(f"  hold {h['hold']}: train {_fmt(h['train'])}  "
                    f"test {_fmt(h['test'])}")

    logger.info(f"bootstrap {BOOTSTRAP_N} seed={BOOTSTRAP_SEED}")
    for name, rows in (
        ("steam75", steam),
        ("steam75 + juice>=-115", steam_j),
        ("steam75 cap2", [r for r in steam_capped if r.get("settled")]),
        ("blunt t70", [r for r in settled if r["tix"] >= 70]),
    ):
        units = [r["units"] for r in rows if r.get("result") in ("WIN", "LOSS")]
        boot = bootstrap_roi(units)
        if boot:
            mean, lo, hi, ppos = boot
            logger.info(
                f"  {name:28s} mean {mean*100:+.1f}%  "
                f"CI [{lo*100:+.1f},{hi*100:+.1f}]  P+={ppos:.2f}")
    return {"cells": [{k: v for k, v in c.items() if k != "rows"}
                      for c in cells]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--date-from", default="2026-05-31")
    ap.add_argument("--date-to", default=None)
    a = ap.parse_args()
    date_to = a.date_to
    if date_to is None:
        import config
        date_to = (config.today_et() + timedelta(days=1)).isoformat()
    run(a.date_from, date_to)


if __name__ == "__main__":
    main()

"""
What moment does Action Network's archived split describe?

The NBA archive (data/ingestors/nba_public_splits_ingestor.py) is one undated
number per side. The only place we can date it is MLB: `public_betting` holds
Action Network consensus splits that OUR ingestor fetched before first pitch
(snapshot_at, refused after the start), 2026-05-31 on. This script re-reads
the archive for those same games today and compares, per (game, market, side):

* exact match rate of tickets % and money %;
* the same, by how long before the listed start our capture was taken.

If the archive equals our last pre-start capture whatever the lead, the split
stopped moving before our capture (or the archive is a pre-start freeze). If
the match rate falls as the lead grows, the archive kept moving after our
capture -- i.e. it is a value from closer to (or after) the start.

Read-only. No paid calls: Action Network's free scoreboard only.

    python -m scripts.action_network_archive_timing --cache-dir <temp dir>
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

MLB_V2 = "https://api.actionnetwork.com/web/v2/scoreboard/mlb"
# Minutes our capture was taken BEFORE the listed start (negative = after it;
# rows written before the post-start guard existed are in the table).
LEAD_BUCKETS = [(-100000, -180), (-180, -60), (-60, -15), (-15, 0),
                (0, 15), (15, 60), (60, 180), (180, 100000)]


def lead_bucket(minutes: float) -> str:
    for lo, hi in LEAD_BUCKETS:
        if lo <= minutes < hi:
            if lo == -100000:
                return f"after start >{-hi}m"
            if hi <= 0:
                return f"after start {-hi}-{-lo}m"
            return f"before start {lo}-{hi}m" if hi < 100000 else f"before start >{lo}m"
    return "unbucketed"


def archive_by_game(data: dict) -> dict:
    """{game_id: {(market, side): {tickets, money}}} for an MLB v2 payload,
    with game ids built exactly as public_betting_ingestor builds them."""
    from data.ingestors.nba_public_splits_ingestor import (
        et_game_date, parse_v2_sides, validate_sides)
    from data.ingestors.odds_ingestor import _normalize_team, _build_game_id

    out = {}
    for g in data.get("games") or []:
        teams = {t.get("id"): t for t in g.get("teams") or []}
        home = teams.get(g.get("home_team_id")) or {}
        away = teams.get(g.get("away_team_id")) or {}
        hn = home.get("full_name") or home.get("display_name")
        an = away.get("full_name") or away.get("display_name")
        if not hn or not an:
            continue
        gid = _build_game_id("MLB", et_game_date(g.get("start_time")),
                             _normalize_team(an, "MLB"), _normalize_team(hn, "MLB"))
        out[gid] = {"sides": validate_sides(parse_v2_sides(g)),
                    "status": g.get("status"), "num_bets": g.get("num_bets")}
    return out


def fetch(day: str, cache_dir: Path) -> dict:
    import requests
    from data.ingestors.nba_public_splits_ingestor import _HEADERS
    p = cache_dir / f"mlb_v2_{day.replace('-', '')}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    r = requests.get(MLB_V2, params={"bookIds": 15, "date": day.replace("-", ""),
                                      "periods": "event"},
                     headers=_HEADERS, timeout=25)
    r.raise_for_status()
    p.write_text(r.text, encoding="utf-8")
    time.sleep(1.0)
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--out", help="write the JSON result here")
    args = ap.parse_args()
    cache = Path(args.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)

    from data.db import get_connection
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT pb.game_id, pb.game_date, pb.market, pb.side,
               pb.public_bet_pct, pb.public_money_pct, pb.snapshot_at,
               g.commence_time
        FROM public_betting pb
        JOIN games g ON g.game_id = pb.game_id
        WHERE pb.source = 'action_network' AND left(pb.game_id, 4) = 'MLB_'
        """
    ).fetchall()
    conn.close()

    by_date = defaultdict(list)
    for r in rows:
        by_date[r[1]].append(r)

    stats = defaultdict(lambda: {"n": 0, "tickets_eq": 0, "money_eq": 0,
                                 "tickets_absdiff": [], "money_absdiff": []})
    no_archive = 0
    for day in sorted(by_date):
        try:
            arch = archive_by_game(fetch(day, cache))
        except Exception as exc:                                  # noqa: BLE001
            print(f"{day}: fetch failed {exc}")
            continue
        for gid, _d, market, side, bet, money, snap, ct in by_date[day]:
            a = (arch.get(gid) or {}).get("sides", {}).get((market, side))
            if not a or (a["tickets"] is None and a["money"] is None):
                no_archive += 1
                continue
            try:
                lead = (datetime.fromisoformat(str(ct).replace("Z", "+00:00"))
                        - datetime.fromisoformat(str(snap))).total_seconds() / 60
            except ValueError:
                continue
            for key in ("all", lead_bucket(lead)):
                s = stats[key]
                s["n"] += 1
                if bet is not None and a["tickets"] is not None:
                    d = abs(float(a["tickets"]) - float(bet))
                    s["tickets_eq"] += d == 0
                    s["tickets_absdiff"].append(d)
                if money is not None and a["money"] is not None:
                    d = abs(float(a["money"]) - float(money))
                    s["money_eq"] += d == 0
                    s["money_absdiff"].append(d)

    result = {"public_betting_rows": len(rows), "dates": len(by_date),
              "rows_without_archive_value": no_archive, "by_lead": {}}
    for key, s in stats.items():
        td, md = sorted(s["tickets_absdiff"]), sorted(s["money_absdiff"])
        result["by_lead"][key] = {
            "n": s["n"],
            "tickets_exact": round(s["tickets_eq"] / max(len(td), 1), 4),
            "money_exact": round(s["money_eq"] / max(len(md), 1), 4),
            "tickets_median_absdiff": td[len(td) // 2] if td else None,
            "tickets_p90_absdiff": td[int(len(td) * 0.9)] if td else None,
            "money_median_absdiff": md[len(md) // 2] if md else None,
            "money_p90_absdiff": md[int(len(md) * 0.9)] if md else None,
        }
    text = json.dumps(result, indent=1)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

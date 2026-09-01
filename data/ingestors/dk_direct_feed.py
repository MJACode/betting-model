"""DraftKings' own in-play feed, written into `odds` as a first-class source.

mike, 2026-08-30: "build the dk direct live feed."

WHAT THIS BUYS, MEASURED RATHER THAN ASSUMED. On 2026-08-30 DK's own feed and
The Odds API were recorded side by side for two hours across 11 live MLB games:

    distinct in-play quotes    DK direct 1,890   aggregator 654
    DK line changes we saw     100%              29.7%
    age of the price we act on ~5s (poll rate)   28.6s median, 50.8s p90
    wrong line at that moment  --                11.8%

The aggregator is not lying to us -- it publishes an honest snapshot every ~67s
and we poll it 147 times per snapshot. It is simply too COARSE to price a book
that reprices every 15-25s. This closes that gap at the source.

HOW IT STAYS SAFE FOR THE DECISION PATH. Rows are written as
`bookmaker='draftkings', snapshot_type='in_play'` -- the same book, the same
market vocabulary -- so `_get_live_dk_odds` and `_best_live_price` pick them up
with no change, and CLAUDE.md section 6's invariant (the models only ever DECIDE
on DraftKings) is preserved exactly. What distinguishes them is a new `source`
column: 'odds_api' for the aggregator, 'dk_direct' here.

That column is not decoration. Without it the freshness comparison that
justified this work becomes circular -- you cannot measure the aggregator's lag
against DK once both are the same rows in the same table. It is also the
rollback: `DELETE FROM odds WHERE source='dk_direct'` is a complete undo.

SNAPSHOT_AT MEANS SOMETHING DIFFERENT HERE, AND THAT IS DELIBERATE. For
aggregator rows `snapshot_at` is the market's own `last_update` -- the book's
publish clock, which is what LIVE_ODDS_MAX_AGE_SEC bounds. DK's league feed
carries no per-market publish stamp, so for direct rows it is OUR clock at the
moment we read it. At a 5s cadence that trivially clears the 30s gate, which is
correct rather than a loophole: we watched the number arrive, so it is on offer
now by observation instead of by the book's assertion. `source` is what lets
anyone reading these columns later tell the two meanings apart.

FIRST-SEEN, NOT EVERY-POLL. A quote is written once, when it first appears. At
5s polling a per-poll write would be ~12 identical rows a minute per market for
a number that has not moved -- that is not data, it is the same fact 12 times,
and it would bury the change we actually care about.

OFF BY DEFAULT. `RUN_DK_DIRECT_FEED` gates it, so merging this changes nothing
until someone turns it on. DraftKings' terms forbid automated access however the
request is shaped; mike has made that call explicitly and more than once, and it
is recorded here rather than re-argued.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger

from data.db import DBConnection, get_connection
from scripts.dk_direct_probe import CANDIDATES, HEADERS, _session
from data.ingestors.book_team_map import resolve_game_id
from scripts.dk_freshness_compare import parse_dk_payload

# The column that keeps the two feeds distinguishable. Added idempotently on
# every start rather than in a migration, matching probability_calibration's
# DDL convention -- this table is written by several processes and none of them
# should fail because a column landed in a different deploy order.
DDL = [
    "ALTER TABLE odds ADD COLUMN IF NOT EXISTS source TEXT",
    "CREATE INDEX IF NOT EXISTS idx_odds_source_inplay "
    "ON odds (source, game_id, market) WHERE snapshot_type = 'in_play'",
]

POLL_SEC = float(os.environ.get("DK_DIRECT_POLL_SEC", "5"))


def _ensure_schema(conn: DBConnection) -> None:
    for stmt in DDL:
        try:
            conn.execute(stmt)
            conn.commit()
        except Exception as exc:                          # noqa: BLE001
            # A concurrent writer may have added it between our check and ours.
            conn.rollback()
            logger.debug(f"dk_direct schema: {stmt[:40]}... -> {exc}")


# The team map lives in book_team_map.py, shared with the bovada feed. It was a
# private copy here until 2026-08-31, and two bugs had already been found in it
# (prefix matching collapsing "NY Yankees"/"NY Mets", then ATH vs the games
# table's OAK) -- exactly the shape section 1b warns about, where a fix lands in
# one feed and not the other.
def _game_id_for(conn: DBConnection, sport: str, event_name: str,
                 cache: dict) -> str | None:
    """Our game_id for a DK event name, or None when it is not unique."""
    return resolve_game_id(conn, sport, event_name, _slate_dates(), cache)


def _slate_dates() -> list[str]:
    from config import live_slate_dates
    return live_slate_dates()


_COLS = ("game_id", "sport", "market", "bookmaker", "snapshot_type",
         "snapshot_at", "total_line", "spread_home", "over_price",
         "under_price", "home_price", "away_price", "created_at", "source")


def _row_for(rec: dict, game_id: str, sport: str, now: str) -> dict | None:
    """One parsed DK market -> one `odds` row, in this repo's column vocabulary.

    parse_dk_payload orders sides deterministically (Over/Home first), so side_a
    is always the over/home price. Anything that is not a two-way game market we
    understand is dropped rather than guessed at.
    """
    base = {c: None for c in _COLS}
    base.update({"game_id": game_id, "sport": sport, "market": rec["market"],
                 "bookmaker": "draftkings", "snapshot_type": "in_play",
                 "snapshot_at": now, "created_at": now, "source": "dk_direct"})
    if rec["market"] == "totals":
        if rec["line"] is None:
            return None
        base.update({"total_line": rec["line"], "over_price": rec["price_a"],
                     "under_price": rec["price_b"]})
    elif rec["market"] == "spreads":
        if rec["line"] is None:
            return None
        # DK's `points` on the HOME side. scored_line is always the home number
        # in this repo (CLAUDE.md section 4), so it maps straight across.
        base.update({"spread_home": rec["line"], "home_price": rec["price_a"],
                     "away_price": rec["price_b"]})
    elif rec["market"] == "h2h":
        base.update({"home_price": rec["price_a"], "away_price": rec["price_b"]})
    else:
        return None
    return base


def _seen_key(row: dict) -> tuple:
    """What counts as 'the same quote'. Excludes the clock, so an unchanged
    number is a no-op however many times we poll it."""
    return (row["game_id"], row["market"], row["total_line"],
            row["spread_home"], row["over_price"], row["under_price"],
            row["home_price"], row["away_price"])


def poll_once(conn: DBConnection, sport: str, sess, seen: set,
              game_cache: dict, dry_run: bool = False) -> dict:
    """One read of DK's league feed. Returns counters, never raises upward."""
    out = {"quotes": 0, "written": 0, "unmatched": 0, "errors": 0}
    moved: set[str] = set()
    for url in CANDIDATES.get(sport, []):
        try:
            body = sess.get(url, headers=HEADERS, timeout=15).json()
        except Exception as exc:                          # noqa: BLE001
            logger.debug(f"dk_direct {sport}: {type(exc).__name__} on {url[:60]}")
            out["errors"] += 1
            continue

        now = datetime.now(timezone.utc).isoformat()
        recs = parse_dk_payload(body, sport, live_only=True)
        out["quotes"] += len(recs)
        rows = []
        for rec in recs:
            game_id = _game_id_for(conn, sport, rec.get("event_name") or "",
                                   game_cache)
            if not game_id:
                out["unmatched"] += 1
                continue
            row = _row_for(rec, game_id, sport, now)
            if row is None:
                continue
            key = _seen_key(row)
            if key in seen:
                continue
            seen.add(key)
            moved.add(game_id)
            rows.append(row)

        if rows and not dry_run:
            sql = (f"INSERT INTO odds ({', '.join(_COLS)}) VALUES "
                   f"({', '.join('%(' + c + ')s' for c in _COLS)})")
            for r in rows:
                try:
                    conn.execute(sql, r)
                except Exception as exc:                  # noqa: BLE001
                    # Roll back per row: a failed statement poisons the
                    # connection and every later write in this pass would fail
                    # silently behind it (the backfill_pbp lesson, 2026-08-30).
                    conn.rollback()
                    out["errors"] += 1
                    logger.debug(f"dk_direct insert failed: {exc}")
            conn.commit()
        out["written"] += len(rows)
        out["moved"] = moved
        return out          # first URL that answered is the one we use
    out["moved"] = moved
    return out


def run(sports: list[str], minutes: float, dry_run: bool = False,
        score: bool = False) -> dict:
    """Poll DK, write what moved, and -- with `score` -- price it immediately.

    THE POINT OF `score`. Measured 2026-08-31 on the four live picks that fired
    that day, the pipeline is ALREADY fast once it sees a qualifying quote:

        DK publishes -> we hold the price   2.4 - 5.8 s
        price -> pick row written           0.8 - 1.0 s
        pick -> push and Discord sent       1.1 - 2.2 s
        ---------------------------------------------
        DK publishes -> in your hand        4.6 - 8.7 s

    So latency was never the problem. COVERAGE was: the aggregator shows us
    29.7% of DK's line changes, so seven moves in ten never produce a pick at
    all, and a pick that is never made cannot be fast.

    This closes that gap. The feed already knows the exact moment a quote is new
    -- that is what the `seen` set is -- so it scores those games in the same
    tick instead of waiting for the next pass to notice. Same scorer, same
    first-signal lock, same daily caps, same notifier: nothing about the
    DECISION changes, only when it happens and how many moves reach it.

    Budget at the default 5s poll: 5 (poll) + ~0.5 (write) + ~1 (score) + ~2
    (notify) = about 8.5s worst case and ~5s typical, on ~100% of DK's moves
    rather than 30%.

    EXPECTED CONSEQUENCE, stated so a jump is not misread as drift: going from
    30% to 100% of DK's moves means more first-crossings, caught earlier. Live
    volume will rise and tracking/live_calibration.py re-derives every cut from
    the RECENT regime, so its bets/week projections move with it. That is the
    machinery working -- the same lesson as 2026-08-29, when the meaning of a
    cut moved without anyone changing it.
    """
    conn = get_connection()
    sess = _session("chrome124", bootstrap=True)
    seen: set = set()
    game_cache: dict = {}
    totals = {"quotes": 0, "written": 0, "unmatched": 0, "errors": 0,
              "passes": 0, "scored": 0, "bets": 0}
    try:
        _ensure_schema(conn)
        deadline = time.time() + minutes * 60
        while time.time() < deadline:
            tick_started = time.time()
            moved: set[str] = set()
            for sport in sports:
                c = poll_once(conn, sport, sess, seen, game_cache, dry_run)
                moved |= c.pop("moved", set())
                for k, v in c.items():
                    totals[k] += v
            totals["passes"] += 1

            if score and moved:
                t0 = time.time()
                try:
                    from models.live_scorer import run_live_scorer
                    summary = run_live_scorer(game_ids=moved, dry_run=dry_run)
                    totals["scored"] += 1
                    totals["bets"] += summary.get("bets", 0)
                    logger.info(
                        f"dk_direct: {len(moved)} game(s) moved -> scored in "
                        f"{time.time() - t0:.1f}s, {summary.get('bets', 0)} BET")
                except Exception as exc:                  # noqa: BLE001
                    # Scoring must never kill the feed. A dead feed loses every
                    # future move; a failed score loses one tick, and the
                    # Railway loop is still running as the backstop.
                    totals["errors"] += 1
                    logger.error(f"dk_direct: scoring failed (non-fatal): {exc}")

            # Sleep the REMAINDER of the interval, not a flat POLL_SEC.
            #
            # Measured before this: fetch ~0.2s + score ~2.3s + sleep 5s gave a
            # 7.5s cadence, so a move landing just after a poll waited 7.5s to
            # be seen and the worst case came to ~11.8s end to end -- over the
            # 10s budget, purely because the loop counted its own work as if it
            # were idle time. Holding a true 5s cadence puts the worst case at
            # 5 + 2.3 + 2 = ~9.3s.
            elapsed = time.time() - tick_started
            time.sleep(max(0.0, POLL_SEC - elapsed))
    finally:
        conn.close()
    level = "info" if totals["written"] or dry_run else "warning"
    getattr(logger, level)(
        f"dk_direct: {totals['passes']} passes, {totals['quotes']} quotes, "
        f"{totals['written']} written, {totals['scored']} scoring runs, "
        f"{totals['bets']} BET, {totals['unmatched']} unmatched, "
        f"{totals['errors']} errors")
    return totals


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sports", nargs="*", default=["MLB"])
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--score", action="store_true",
                    help="price each move in the same tick (the sub-10s path)")
    a = ap.parse_args()
    run([s for s in a.sports if s in CANDIDATES], a.minutes, a.dry_run,
        score=a.score)


if __name__ == "__main__":
    main()

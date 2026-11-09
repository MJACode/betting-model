"""Historical NCAAB in-play prices from The Odds API: the market the NCAAB in-play
model is graded against.

WHY. Every hour of six NCAAB seasons was bought by the game-lines purchase
(data/ingestors/ncaab_odds_history.py, `odds_history_pulls`: 744 hours in each
January), and every snapshot carried the games then in progress (40 of 114
events at 2026-02-07 21:55:37Z, measured 2026-11-07). Its keeper drops every
in-play row by design (`QuoteKeeper.wanted`: the purchase was approved for
pre-game models), so no past NCAAB in-game price is stored: zero after-tip rows
on the 155 games of 2026-02-07. This module re-buys the in-play instants and
keeps ONLY the in-play rows.

WHAT IS BOUGHT. The bulk /historical/sports/basketball_ncaab/odds snapshot,
h2h + spreads + totals at the ten fetched books (config.LINE_SHOP_BOOKMAKERS),
30 credits a snapshot (x-requests-last, 19 calls on 2026-11-07), at every grid
instant on the clock (every `--step` minutes) at which a game is in progress:
listed tip + 2 minutes < instant < listed tip + IN_PLAY_WINDOW_MIN (160: 10.6% of
games end past tip + 135, the 99th percentile near 160, 2020-21 .. 2022-23). The feed
serves the market as it stood some seconds before the instant asked for: 300 s
in 2020-21 and 2021-22, 261-263 s from 2022-23 on (measured 2026-11-07, three
instants a season). `snapshot_ts` in the ledger is what it served.

WHAT IS STORED. Each snapshot's rows whose quote (`last_update`) is after the
game's listed tip, stamped `snapshot_type = 'in_play'` by
odds_ingestor._mark_in_play, land in `odds` with source SOURCE (protected from
retention in data/prune_odds.PROTECTED_SOURCES). A quote last updated before the
tip is a pre-game quote already stored by the lines purchase and is counted, not
stored. Started events the resolver cannot match are kept raw in
`ncaab_odds_unmatched` under SOURCE. Every snapshot is ledgered in
`ncaab_inplay_fetches` (its own table: the shared `odds_history_pulls` already
holds every hour, so `buy_lines` would skip them all) in the same transaction as
its rows, so a re-run never buys an instant twice.

CREDITS. A dry run prints the plan and its cost and spends nothing. `--apply`
needs `--max-credits` (the number mike approved) and stops before the balance
falls under `--floor`. mike's approval in chat comes first (CLAUDE.md 1b).

    python -m data.ingestors.ncaab_inplay_history --seasons 2021 2026 --step 60
    python -m data.ingestors.ncaab_inplay_history --seasons 2021 2026 --step 30 \\
        --apply --max-credits 481410 --floor 100000
    python -m data.ingestors.ncaab_inplay_history --import-probe DIR   (paid probe payloads)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.db import get_connection
from data.ingestors.nba_odds_history import _write_with_retry
from data.ingestors.ncaab_odds_history import (BASE, BOOKS, LINE_MARKETS, LINE_SNAPSHOT_COST,
                                               PoolMeter, _paid_calls,
                                               _parse_snapshot, _resolver, _season_games,
                                               _stamp, _utc, check_precondition)
from data.ingestors.odds_ingestor import _insert_odds
from data.ingestors.odds_quota import latest_remaining, persist_quota

SPORT = "NCAAB"
SOURCE = "odds_api_ncaab_inplay_history"
LEDGER = "ncaab_inplay_fetches"
IN_PLAY_START_MIN = 2
IN_PLAY_WINDOW_MIN = 160         # 99th percentile of the last play, tip + 158-161 min (2021-23)
STEPS = (60, 30, 15, 10, 5)
DEFAULT_CONCURRENCY = 6
LEDGER_COLS = ("requested_at", "snapshot_ts", "step_min", "events", "events_in_play",
               "rows", "pre_tip_rows", "unmatched", "credits", "pulled_at")
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_inplay_fetches (
    requested_at    TIMESTAMPTZ PRIMARY KEY,
    snapshot_ts     TIMESTAMPTZ,
    step_min        SMALLINT,
    events          INTEGER,
    events_in_play  INTEGER,
    rows            INTEGER,
    pre_tip_rows    INTEGER,
    unmatched       INTEGER,
    credits         INTEGER,
    pulled_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
_UNMATCHED_INSERT = """
    INSERT INTO ncaab_odds_unmatched
           (snapshot_at, event_id, home_name, away_name, commence_time, payload, source)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (event_id, snapshot_at, source) DO NOTHING
"""


def ensure_tables(conn) -> None:
    """The ledger, once, locked down (ncaab_odds_unmatched is the lines
    purchase's table and is created there)."""
    if not schema_is_current(conn, LEDGER, columns=LEDGER_COLS, rls=True,
                             revoked_from=API_ROLES):
        conn.execute(LEDGER_DDL)
        lock_down(conn, LEDGER)
        conn.commit()


# ── the plan ─────────────────────────────────────────────────────────────────

def inplay_instants(games: list[dict], step_min: int) -> list[datetime]:
    """Every instant on the `step_min` clock grid at which a listed game is in
    progress (tip + 2 min < instant < tip + IN_PLAY_WINDOW_MIN), newest first,
    each once. Pure, so the plan is testable."""
    if step_min not in STEPS:
        raise ValueError(f"step must be one of {STEPS}, got {step_min}")
    want: set[datetime] = set()
    for g in games:
        tip = _utc(g.get("commence_time"))
        if tip is None:
            continue
        lo = tip + timedelta(minutes=IN_PLAY_START_MIN)
        hi = tip + timedelta(minutes=IN_PLAY_WINDOW_MIN)
        t = tip.replace(minute=0, second=0, microsecond=0)
        while t < hi:
            if t > lo:
                want.add(t)
            t += timedelta(minutes=step_min)
    return sorted(want, reverse=True)


def held_instants(conn) -> set[datetime]:
    if conn.execute("SELECT to_regclass('public.ncaab_inplay_fetches')").fetchone()[0] is None:
        conn.commit()
        return set()
    out = {_utc(r[0]) for r in conn.execute(
        "SELECT requested_at FROM ncaab_inplay_fetches").fetchall()}
    conn.commit()
    return out


class LedgerMismatch(RuntimeError):
    """`odds` holds rows under SOURCE that the ledger does not account for."""


def stored_rows(conn) -> int:
    """Rows already in `odds` under this purchase's source marker (through
    idx_odds_source_inplay: every stored row is in_play)."""
    n = conn.execute("SELECT COUNT(*) FROM odds WHERE source = %s AND snapshot_type = 'in_play'",
                     (SOURCE,)).fetchone()[0]
    conn.commit()
    return int(n)


def check_resume(conn) -> tuple[int, int]:
    """(rows stored under SOURCE, rows the ledger says were stored). The resume
    skips every ledgered instant; it is only honest while the ledger accounts
    for what `odds` holds under the marker. Rows and ledger row are written in
    one transaction, so the two agree; if the ledger was lost or cleared, a
    re-run would re-buy and store every row twice, so this REFUSES instead."""
    have = stored_rows(conn)
    if conn.execute("SELECT to_regclass('public.ncaab_inplay_fetches')").fetchone()[0] is None:
        conn.commit()
        ledgered = 0
    else:
        ledgered = int(conn.execute(
            "SELECT COALESCE(SUM(rows), 0) FROM ncaab_inplay_fetches").fetchone()[0])
        conn.commit()
    if have > ledgered:
        raise LedgerMismatch(f"odds holds {have:,} rows under {SOURCE} but the ledger accounts "
                             f"for {ledgered:,}: a re-run would buy them again")
    return have, ledgered


def played_ids(conn, first: int, last: int) -> set[str]:
    """Games with a final score: a postponed or cancelled game was never in play."""
    out = {r[0] for r in conn.execute(
        "SELECT game_id FROM games WHERE sport = 'NCAAB' AND season BETWEEN %s AND %s "
        "AND home_score IS NOT NULL", (first, last)).fetchall()}
    conn.commit()
    return out


def plan(conn, first: int, last: int, step_min: int):
    played = played_ids(conn, first, last)
    games = [g for g in _season_games(conn, first, last) if g["game_id"] in played]
    instants = inplay_instants(games, step_min)
    held = held_instants(conn)
    todo = [w for w in instants if w not in held]
    by_season: dict[int, int] = defaultdict(int)
    for w in todo:
        by_season[w.year + (1 if w.month >= 8 else 0)] += 1
    return games, instants, todo, dict(sorted(by_season.items()))


# ── one snapshot ─────────────────────────────────────────────────────────────

def split_snapshot(body: dict, when: datetime, resolver, tips: dict[str, str]) -> dict:
    """One bought snapshot -> what is stored. Pure apart from the resolver."""
    events = body.get("data") or []
    served = _utc(body.get("timestamp")) or when
    hits, unmatched, odds_rows, dropped, _ = _parse_snapshot(events, when, resolver, tips)
    keep, pre_tip = [], 0
    for r in odds_rows:
        if r.get("snapshot_type") == "in_play":
            r["source"] = SOURCE
            keep.append(r)
        else:
            pre_tip += 1
    started = [ev for ev in unmatched + dropped
               if (_utc(ev.get("commence_time")) or served) < served]
    in_play = sum(1 for ev in events if (_utc(ev.get("commence_time")) or served) < served)
    return {"served": served, "rows": keep, "pre_tip_rows": pre_tip, "lost": started,
            "events": len(events), "events_in_play": in_play}


def store_snapshot(conn, when: datetime, body: dict, resolver, tips: dict[str, str],
                   step_min: int | None, credits: int, stats: dict) -> bool:
    part = split_snapshot(body, when, resolver, tips)
    lost = [(_stamp(part["served"]), str(ev.get("id")), ev.get("home_team"),
             ev.get("away_team"), ev.get("commence_time"), json.dumps(ev), SOURCE)
            for ev in part["lost"]]

    def _write():
        if part["rows"]:
            _insert_odds(conn, part["rows"])
        if lost:
            conn.executemany(_UNMATCHED_INSERT, lost)
        conn.execute("""
            INSERT INTO ncaab_inplay_fetches (requested_at, snapshot_ts, step_min, events,
                   events_in_play, rows, pre_tip_rows, unmatched, credits, pulled_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (requested_at) DO NOTHING
        """, (when, part["served"], step_min, part["events"], part["events_in_play"],
              len(part["rows"]), part["pre_tip_rows"], len(lost), credits))
        conn.commit()

    if not _write_with_retry(conn, _write, f"inplay {_stamp(when)}"):
        stats["errors"] += 1
        return False
    stats["snapshots"] += 1
    stats["rows"] += len(part["rows"])
    stats["pre_tip_rows"] += part["pre_tip_rows"]
    stats["unmatched"] += len(lost)
    stats["events_in_play"] += part["events_in_play"]
    return True


def _params(when: datetime) -> dict:
    return {"date": _stamp(when), "markets": ",".join(LINE_MARKETS), "bookmakers": BOOKS,
            "oddsFormat": "american"}


def buy(conn, meter: PoolMeter, first: int, last: int, step_min: int) -> dict:
    check_precondition(conn, list(range(first, last + 1)))
    ensure_tables(conn)
    check_resume(conn)
    games, instants, todo, _ = plan(conn, first, last, step_min)
    resolver = _resolver(conn, games)
    tips = {g["game_id"]: g.get("commence_time") for g in games}
    stats: dict = defaultdict(int)
    logger.info(f"inplay: {len(instants):,} instants, {len(todo):,} to buy "
                f"(~{LINE_SNAPSHOT_COST * len(todo):,} credits)")

    def jobs():
        for w in todo:
            yield w, f"{BASE}/odds", _params(w)

    def consume(when, r):
        if r is None or r.status_code != 200:
            stats["http_errors"] += 1
            logger.warning(f"inplay {_stamp(when)}: HTTP {getattr(r, 'status_code', 'network')}")
            return
        billed = int(float(r.headers.get("x-requests-last") or 0))
        store_snapshot(conn, when, r.json(), resolver, tips, step_min, billed, stats)
        if stats["snapshots"] % 200 == 0:
            logger.info(f"inplay {_stamp(when)}: {stats['snapshots']:,} stored, "
                        f"{stats['rows']:,} rows, spent {meter.spent:,}, balance {meter.remaining}")

    stop = _paid_calls(meter, jobs(), LINE_SNAPSHOT_COST, consume)
    if stop:
        stats["stopped"] = stop
    return dict(stats)


def import_probe(conn, folder: Path) -> dict:
    """Store paid probe payloads (hist_<YYYYMMDDTHHMMSSZ>.json, the body the feed
    sent) through the same path, so the credits they cost are not lost and the
    instants are not bought again."""
    ensure_tables(conn)
    files = sorted(folder.glob("hist_*.json"))
    whens = [datetime.strptime(f.stem.split("_", 1)[1], "%Y%m%dT%H%M%SZ")
             .replace(tzinfo=timezone.utc) for f in files]
    if not files:
        return {"files": 0}
    seasons = sorted({w.year + (1 if w.month >= 8 else 0) for w in whens})
    games = [g for g in _season_games(conn, seasons[0], seasons[-1])]
    resolver = _resolver(conn, games)
    tips = {g["game_id"]: g.get("commence_time") for g in games}
    held = held_instants(conn)
    stats: dict = defaultdict(int)
    for f, w in zip(files, whens):
        if w in held:
            stats["already"] += 1
            continue
        body = json.loads(f.read_text(encoding="utf-8"))
        store_snapshot(conn, w, body, resolver, tips, None, LINE_SNAPSHOT_COST, stats)
    return dict(stats)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"))
    ap.add_argument("--step", type=int, choices=STEPS, help="minutes between instants")
    ap.add_argument("--apply", action="store_true", help="spend; without it, a dry run")
    ap.add_argument("--max-credits", type=int, help="the approved ceiling (required with --apply)")
    ap.add_argument("--floor", type=int, help="stop before the balance falls below this")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--import-probe", type=Path, metavar="DIR",
                    help="store paid probe payloads from DIR; no paid call")
    a = ap.parse_args(argv)
    conn = get_connection()
    try:
        if a.import_probe:
            print("probe import:", import_probe(conn, a.import_probe))
            return 0
        if not a.seasons or not a.step:
            ap.error("--seasons and --step are required")
        first, last = a.seasons
        games, instants, todo, by_season = plan(conn, first, last, a.step)
        print(f"plan: every {a.step} min, seasons {first}-{last}: {len(instants):,} instants, "
              f"{len(instants) - len(todo):,} held, {len(todo):,} to buy = "
              f"{len(todo) * LINE_SNAPSHOT_COST:,} credits at {LINE_SNAPSHOT_COST} each")
        print("  to buy by season:", by_season)
        print("  balance on record:", latest_remaining(conn))
        if not a.apply:
            return 0
        if not a.max_credits or a.floor is None:
            ap.error("--apply needs --max-credits and --floor")
        meter = PoolMeter(ceiling=a.max_credits, floor=a.floor, workers=a.concurrency)
        print("bought:", buy(conn, meter, first, last, a.step))
        print(f"spent {meter.spent:,}; balance {meter.remaining}; 429s {meter.rate_limited}")
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

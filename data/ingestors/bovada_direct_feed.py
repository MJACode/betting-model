"""Bovada's own in-play feed — the second live source, and the one that runs.

mike, 2026-08-31: "bovada as the second source."

WHY BOVADA AND NOT THE OTHERS. Probed from the Railway worker on 2026-08-31,
bovada was the ONLY book of seven that answered: 200, 802 KB, parseable JSON,
no key and no browser impersonation needed. DraftKings, BetMGM, Pinnacle and
Caesars all refused the datacentre outright (403/401) -- DK does so even with
the exact Chrome fingerprint and cookie bootstrap that runs for hours from a
residential address, in 10-40ms, which is an edge refusal rather than a rate
limit. So DK direct runs on mike's machine and this runs on the worker.

WHAT IT IS FOR, AND WHAT IT IS NOT. This is a BEST-LINE source, not a decision
source. CLAUDE.md section 6: the models only ever DECIDE on DraftKings, because
every threshold was swept on DK-implied edge and best-of-N runs ~2pp cheaper in
implied probability. Bovada rows are written as bookmaker='bovada', so
`_best_live_price` can shop them and `_get_live_dk_odds` can never see them.
That separation is structural rather than a convention someone has to remember.

SNAPSHOT_AT IS THE BOOK'S OWN CLOCK HERE, which makes three different meanings
now live in that column and they are worth stating together:

    aggregator rows  snapshot_type='in_play', source NULL/'odds_api'
                     -> the market's `last_update`, the book's publish clock
    dk_direct rows   -> OUR clock at read time; DK's league feed carries no
                        per-market publish stamp
    bovada rows      -> the event's `lastModified`, the book's publish clock

So bovada is strictly better instrumented than DK direct for freshness, and
LIVE_ODDS_MAX_AGE_SEC means the same thing for it as for the aggregator.

RATE. One coupon call returns every MLB event at once (~35 KB pre-game, ~800 KB
with live markets), so this is ONE request per poll for the whole league rather
than one per game. At the default 5s that is 12 requests a minute against a
public, unauthenticated page.

OFF BY DEFAULT. `RUN_BOVADA_FEED` gates the scheduler job.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from loguru import logger

from data.db import DBConnection, get_connection
from data.ingestors.book_team_map import resolve_game_id

COUPON_URL = os.environ.get(
    "BOVADA_MLB_URL",
    "https://www.bovada.lv/services/sports/event/coupon/events/A/description"
    "/baseball/mlb?marketFilterId=def&preMatchOnly=false&lang=en")

# A plain browser UA is enough -- unlike DK this needs no TLS impersonation.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Bovada's market vocabulary -> ours. Verified against a live payload rather
# than assumed: the only three main game markets it publishes are these.
MARKET_MAP = {"Moneyline": "h2h", "Total": "totals", "Runline": "spreads"}

POLL_SEC = float(os.environ.get("BOVADA_POLL_SEC", "5"))

_COLS = ("game_id", "sport", "market", "bookmaker", "snapshot_type",
         "snapshot_at", "total_line", "spread_home", "over_price",
         "under_price", "home_price", "away_price", "created_at", "source")


def _american(price: dict | None) -> int | None:
    """Bovada writes "+250" and "-350" as ASCII strings.

    The leading '+' is why this cannot be a bare int(): int("+250") happens to
    work in Python, but the decimal fallback matters when american is absent,
    and being explicit here is what stopped DK's UNICODE minus becoming a silent
    None in the sibling feed.
    """
    if not price:
        return None
    raw = price.get("american")
    if isinstance(raw, str):
        cleaned = raw.replace("−", "-").replace("+", "").strip()
        try:
            return int(cleaned)
        except ValueError:
            pass
    try:
        dec = float(price.get("decimal"))
    except (TypeError, ValueError):
        return None
    if dec <= 1.0:
        return None
    return round((dec - 1) * 100) if dec >= 2.0 else round(-100 / (dec - 1))


def _stamp(ms) -> str | None:
    """lastModified is epoch MILLISECONDS. Treating it as seconds would date
    every row to 1970 and make every quote look infinitely stale."""
    try:
        return datetime.fromtimestamp(int(ms) / 1000.0,
                                      tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def parse_coupon(body, live_only: bool = True) -> list[dict]:
    """Bovada's coupon payload -> one record per main game market.

    Pure: no clock, no network, no database. Everything about this payload that
    could change shape is isolated here.

    LIVE requires BOTH the event and the market period to say so. The event flag
    alone stays true while bovada also publishes the pre-game market for the
    same game, and taking that would write a pre-game number as an in-play one.
    """
    out: list[dict] = []
    for node in body or []:
        for ev in node.get("events") or []:
            ev_live = bool(ev.get("live"))
            if live_only and not ev_live:
                continue
            name = ev.get("description") or ""
            published = _stamp(ev.get("lastModified"))
            for dg in ev.get("displayGroups") or []:
                for mk in dg.get("markets") or []:
                    market = MARKET_MAP.get(mk.get("description") or "")
                    if not market:
                        continue
                    period = mk.get("period") or {}
                    if live_only and not period.get("live"):
                        continue
                    if mk.get("status") not in (None, "O"):
                        continue        # suspended market is not on offer
                    by_type = {o.get("type"): o for o in mk.get("outcomes") or []
                               if o.get("status") in (None, "O")}
                    rec = {"event_name": name, "market": market,
                           "published_at": published, "line": None,
                           "home_price": None, "away_price": None,
                           "over_price": None, "under_price": None}
                    if market == "h2h":
                        if not {"H", "A"} <= by_type.keys():
                            continue
                        rec["home_price"] = _american(by_type["H"].get("price"))
                        rec["away_price"] = _american(by_type["A"].get("price"))
                    elif market == "totals":
                        if not {"O", "U"} <= by_type.keys():
                            continue
                        rec["over_price"] = _american(by_type["O"].get("price"))
                        rec["under_price"] = _american(by_type["U"].get("price"))
                        rec["line"] = _num((by_type["O"].get("price") or {}
                                            ).get("handicap"))
                    else:                                    # spreads
                        if not {"H", "A"} <= by_type.keys():
                            continue
                        rec["home_price"] = _american(by_type["H"].get("price"))
                        rec["away_price"] = _american(by_type["A"].get("price"))
                        # The HOME number. Bovada carries the handicap per
                        # outcome with opposite signs (away -2.5 / home +2.5),
                        # and scored_line is always the home figure in this repo
                        # (CLAUDE.md section 4) -- taking the away one would
                        # flip the sign on every spread, which has produced a
                        # wrong threshold twice before.
                        rec["line"] = _num((by_type["H"].get("price") or {}
                                            ).get("handicap"))
                    if _complete(rec):
                        out.append(rec)
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _complete(rec: dict) -> bool:
    if rec["market"] == "h2h":
        return rec["home_price"] is not None and rec["away_price"] is not None
    if rec["market"] == "totals":
        return (rec["line"] is not None and rec["over_price"] is not None
                and rec["under_price"] is not None)
    return (rec["line"] is not None and rec["home_price"] is not None
            and rec["away_price"] is not None)


def _row_for(rec: dict, game_id: str, now: str) -> dict:
    base = {c: None for c in _COLS}
    base.update({
        "game_id": game_id, "sport": "MLB", "market": rec["market"],
        "bookmaker": "bovada", "snapshot_type": "in_play",
        # The book's own publish clock when it gave us one; ours only as a
        # fallback, so a missing stamp never makes a stale quote look fresh by
        # accident -- it makes it look exactly as fresh as our read.
        "snapshot_at": rec.get("published_at") or now,
        "created_at": now, "source": "bovada_direct",
        "home_price": rec["home_price"], "away_price": rec["away_price"],
        "over_price": rec["over_price"], "under_price": rec["under_price"],
    })
    if rec["market"] == "totals":
        base["total_line"] = rec["line"]
    elif rec["market"] == "spreads":
        base["spread_home"] = rec["line"]
    return base


def _seen_key(row: dict) -> tuple:
    """First-seen semantics: the clock is excluded, so an unchanged number is a
    no-op however many times we poll it."""
    return (row["game_id"], row["market"], row["total_line"],
            row["spread_home"], row["over_price"], row["under_price"],
            row["home_price"], row["away_price"])


def poll_once(conn: DBConnection, sess, seen: set, game_cache: dict,
              dry_run: bool = False) -> dict:
    from config import live_slate_dates
    out = {"quotes": 0, "written": 0, "unmatched": 0, "errors": 0}
    try:
        body = sess.get(COUPON_URL, headers=HEADERS, timeout=15).json()
    except Exception as exc:                              # noqa: BLE001
        logger.debug(f"bovada: {type(exc).__name__} on coupon")
        out["errors"] += 1
        return out

    now = datetime.now(timezone.utc).isoformat()
    dates = live_slate_dates()
    rows = []
    for rec in parse_coupon(body, live_only=True):
        out["quotes"] += 1
        game_id = resolve_game_id(conn, "MLB", rec["event_name"], dates,
                                  game_cache)
        if not game_id:
            out["unmatched"] += 1
            continue
        row = _row_for(rec, game_id, now)
        key = _seen_key(row)
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    if rows and not dry_run:
        sql = (f"INSERT INTO odds ({', '.join(_COLS)}) VALUES "
               f"({', '.join('%(' + c + ')s' for c in _COLS)})")
        for r in rows:
            try:
                conn.execute(sql, r)
            except Exception as exc:                      # noqa: BLE001
                # Per row: a failed statement poisons the connection and every
                # later write in the pass fails silently behind it.
                conn.rollback()
                out["errors"] += 1
                logger.debug(f"bovada insert failed: {exc}")
        conn.commit()
    out["written"] += len(rows)
    return out


def run(minutes: float, dry_run: bool = False) -> dict:
    from data.ingestors.dk_direct_feed import _ensure_schema
    conn = get_connection()
    sess = requests.Session()
    seen: set = set()
    game_cache: dict = {}
    totals = {"quotes": 0, "written": 0, "unmatched": 0, "errors": 0,
              "passes": 0}
    try:
        _ensure_schema(conn)          # shares the `source` column with DK direct
        deadline = time.time() + minutes * 60
        while time.time() < deadline:
            c = poll_once(conn, sess, seen, game_cache, dry_run)
            for k, v in c.items():
                totals[k] += v
            totals["passes"] += 1
            time.sleep(POLL_SEC)
    finally:
        conn.close()
    # Passes with no writes is the shape of a silent failure, so it is reported
    # rather than logged as a success.
    level = "info" if totals["written"] or dry_run else "warning"
    getattr(logger, level)(
        f"bovada: {totals['passes']} passes, {totals['quotes']} quotes, "
        f"{totals['written']} written, {totals['unmatched']} unmatched, "
        f"{totals['errors']} errors")
    return totals


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.minutes, a.dry_run)


if __name__ == "__main__":
    main()

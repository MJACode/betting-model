"""Correct the closing-line value of every published pre-game bet (issue #1470).

mike, 2026-11-19: *"yes I want it to be accurate please correct"*. In-play
bets stay unmeasured by design. The rule is tracking/clv_close.py.

Two eras, because the odds prune deleted later rows of settled games until
2026-11-14 (docs/data_archive.md):

  recent    games from clv_close.STORED_FROM: every pull is still stored, so
            the close is measured from our own rows. Free.
  history   older games: the bet book's quotes are bought from the feed's
            history at the start (main market and its alternate ladder), into
            clv_close_quotes, then measured from those plus whatever stored
            rows survived.

Commands (dry run unless --apply; nothing is bought without `buy`):

  python -m scripts.clv_close_history recent [--apply]
  python -m scripts.clv_close_history plan
  python -m scripts.clv_close_history buy [--limit N]
  python -m scripts.clv_close_history history [--apply]
  python -m scripts.clv_close_history remeasure-none [--apply]
            every bet measured with no closing price, measured again from
            stored rows and bought quotes (after a fix to the rule)

WHAT ONE CALL COSTS, measured 2026-11-19 on NHL_2026-11-05_VAN_WPG: an event
list is 1 credit (x-requests-last); one game's odds at one book is 10 credits
per market the book returns (two asked, one returned: 10). A (game, book) is
bought once: an ok ledger row in clv_close_purchases is never bought again.
Before any paid call the run refuses when the balance is under RESERVE_DAYS of
the platform's median daily burn (odds_quota.daily_burn), so the live feeds
never run dry (the September 2026 outage).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
from loguru import logger  # noqa: E402

import config  # noqa: E402
from data.db import ConnectionLost, get_connection  # noqa: E402
from tracking import clv_close as cc  # noqa: E402

RESERVE_DAYS = 3

from data.ingestors.clv_closing_pull import (  # noqa: E402
    SOURCE_HISTORY as SOURCE, api_markets, ledger, parse_book, store_quotes)

PUBLISHED_PREGAME = """
    p.pick_id IN (SELECT pick_id FROM public.v_model_health_bets WHERE status <> 'in_play')
"""


# ── planning ─────────────────────────────────────────────────────────────────

def history_targets(conn) -> list[cc.Bet]:
    return cc.load_bets(conn, PUBLISHED_PREGAME + """
        AND g.commence_time::timestamptz < %s::timestamptz ORDER BY p.pick_id""", (cc.STORED_FROM,))


def plan(conn, bets: list[cc.Bet]) -> dict:
    """{(sport, eastern date): {(game_id, book): {"bound": t, "markets": set, "props": set}}}"""
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    out: dict = defaultdict(dict)
    for b in bets:
        if b.bound is None or not b.market:
            continue
        sport = b.game_id.split("_", 1)[0]
        day = b.bound.astimezone(et).date().isoformat()
        slot = out[(sport, day)].setdefault((b.game_id, b.bet_book),
                                            {"bound": b.bound, "markets": set(), "props": set()})
        slot["bound"] = min(slot["bound"], b.bound)
        for k in api_markets(b):
            slot["markets"].add(k)
            if b.kind == "prop":
                slot["props"].add(k)
    return out


def bought(conn) -> set[tuple[str, str]]:
    rows = conn.execute("SELECT DISTINCT game_id, bookmaker FROM public.clv_close_purchases WHERE ok AND kind = 'history'").fetchall()
    conn.commit()
    return {(r[0], r[1]) for r in rows}


# ── buying ───────────────────────────────────────────────────────────────────

class Feed:
    def __init__(self):
        self.key = os.environ["ODDS_API_KEY"]
        self.base = config.ODDS_API_BASE
        self.s = requests.Session()
        self.spent = 0
        self.remaining = None

    def get(self, path: str, params: dict):
        r = self.s.get(f"{self.base}{path}", params={"apiKey": self.key, **params}, timeout=45)
        last = r.headers.get("x-requests-last")
        rem = r.headers.get("x-requests-remaining")
        if last is not None:
            self.spent += int(float(last))
        if rem is not None:
            self.remaining = int(float(rem))
        try:
            from data.ingestors import odds_quota
            odds_quota.record_quota_headers(r)
        except Exception:                                      # noqa: BLE001
            pass
        return r, (int(float(last)) if last is not None else None)


def _z(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def refuse_reason(conn) -> str | None:
    from data.ingestors import odds_quota
    remaining = odds_quota.latest_remaining(conn)
    burn = odds_quota.daily_burn(conn)
    conn.commit()
    if remaining is None or not burn:
        return f"cannot measure the balance or the daily burn (remaining={remaining}, burn={burn})"
    burn_v = burn[0] if isinstance(burn, tuple) else burn
    floor = RESERVE_DAYS * float(burn_v)
    if float(remaining) < floor:
        return f"balance {remaining} is under {RESERVE_DAYS} days of median burn ({floor:.0f})"
    return None


def buy(conn, limit: int | None = None) -> dict:
    from data.ingestors.alt_game_lines import game_for_event
    from data.ingestors.odds_ingestor import SPORT_KEYS, _schedule_resolver
    reason = refuse_reason(conn)
    if reason:
        logger.error(f"Refusing to buy: {reason}")
        return {"refused": reason}
    feed = Feed()
    done = bought(conn)
    p = plan(conn, history_targets(conn))
    stats = Counter()
    calls = 0
    for (sport, day), slots in sorted(p.items()):
        todo = {k: v for k, v in slots.items() if k not in done}
        if not todo:
            continue
        if limit is not None and calls >= limit:
            break
        key = SPORT_KEYS.get(sport)
        if not key:
            stats["no_sport_key"] += len(todo)
            continue
        earliest = min(v["bound"] for v in todo.values())
        r, _ = feed.get(f"/historical/sports/{key}/events", {"date": _z(earliest - timedelta(hours=1))})
        if r.status_code != 200:
            logger.warning(f"{sport} {day}: events HTTP {r.status_code} {r.text[:200]}")
            stats["events_failed"] += 1
            continue
        resolver = _schedule_resolver(sport, conn, day)
        conn.commit()
        events = {}
        for ev in (r.json().get("data") or []):
            hit = game_for_event(sport, ev, resolver)
            if hit:
                events[hit[0]] = (ev, hit[1])
        for (game_id, book), slot in sorted(todo.items()):
            if limit is not None and calls >= limit:
                break
            if game_id not in events:
                stats["unmatched_game"] += 1
                _ledger(conn, game_id, book, slot, None, None, False, 0, 0, "no feed event matched")
                continue
            ev, home_name = events[game_id]
            markets = sorted(slot["markets"])
            params = {"date": _z(slot["bound"]), "regions": "us", "markets": ",".join(markets),
                      "bookmakers": book, "oddsFormat": "american"}
            r2, billed = feed.get(f"/historical/sports/{key}/events/{ev['id']}/odds", params)
            calls += 1
            if r2.status_code == 422 and len(markets) > 1:
                # A ladder the feed does not carry for this sport: main only.
                markets = [m for m in markets if not m.startswith("alternate_") and not m.endswith("_alternate")]
                params["markets"] = ",".join(markets)
                r2, billed2 = feed.get(f"/historical/sports/{key}/events/{ev['id']}/odds", params)
                billed = (billed or 0) + (billed2 or 0)
                calls += 1
            if r2.status_code != 200:
                stats["odds_failed"] += 1
                _ledger(conn, game_id, book, slot, ev["id"], None, False, billed, 0,
                        f"HTTP {r2.status_code} {r2.text[:200]}")
                continue
            body = r2.json()
            snap = cc._utc(body.get("timestamp"))
            rows = []
            for bk in ((body.get("data") or {}).get("bookmakers") or []):
                if bk.get("key") == book:
                    rows += parse_book(game_id, bk, home_name, snap, ev["id"], slot["props"])
            # The session pooler drops a long-lived connection now and then
            # (2026-11-19: twice in 300 calls, "server closed the connection
            # unexpectedly"). The quotes are already fetched and paid for, so
            # store them again on the reconnected connection, not re-buy.
            for attempt in range(3):
                try:
                    n = store_quotes(conn, rows, SOURCE)
                    _ledger(conn, game_id, book, slot, ev["id"], snap, True, billed, n, None, markets)
                    break
                except ConnectionLost:
                    logger.warning(f"{game_id} {book}: connection lost while storing; retrying ({attempt + 1})")
                    try:
                        conn.rollback()
                    except Exception:                          # noqa: BLE001
                        pass
            else:
                raise RuntimeError(f"{game_id} {book}: could not store the bought quotes")
            stats["bought"] += 1
            stats["quotes"] += n
            time.sleep(0.15)
    try:
        from data.ingestors import odds_quota
        odds_quota.persist_quota(conn)
    except Exception:                                          # noqa: BLE001
        pass
    stats["credits"] = feed.spent
    stats["remaining"] = feed.remaining or 0
    return dict(stats)


def _ledger(conn, game_id, book, slot, event_id, snap, ok, credits, quotes, error, markets=None):
    ledger(conn, game_id, book, slot["bound"], markets or sorted(slot["markets"]), event_id, snap,
           ok, credits, quotes, error, "history")


# ── measuring ────────────────────────────────────────────────────────────────

def run_measure(conn, bets: list[cc.Bet], history: bool, apply: bool) -> dict:
    stats = Counter()
    by_model = defaultdict(Counter)
    changes = []
    for b in bets:
        quotes = cc.feed_quotes(conn, b) + (cc.history_quotes(conn, b) if history else [])
        close = cc.choose_close(b, quotes)
        m = cc.measure(b, close)
        state = "priced" if m["clv_pct"] is not None else ("polled" if close.last_poll else "no_pull")
        stats[state] += 1
        if close.note:
            stats[f"via {close.note}"] += 1
        by_model[b.model_id][state] += 1
        old = b.before.get("clv_pct")
        changes.append((b.pick_id, b.model_id, old, m["clv_pct"], close.note))
        if apply:
            cc.write(conn, b, close)
    return {"stats": dict(stats), "by_model": {k: dict(v) for k, v in by_model.items()},
            "changed": sum(1 for c in changes if (c[2] is None) != (c[3] is None)
                           or (c[2] is not None and c[3] is not None and abs(float(c[2]) - float(c[3])) > 0.005)),
            "sample": changes[:15]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["recent", "plan", "buy", "history", "remeasure-none"])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only-bought", action="store_true",
                    help="history: measure only bets whose game and book were bought")
    a = ap.parse_args(argv)
    conn = get_connection()
    if a.command == "recent":
        bets = cc.load_bets(conn, PUBLISHED_PREGAME + """
            AND g.commence_time::timestamptz >= %s::timestamptz ORDER BY p.pick_id""", (cc.STORED_FROM,))
        print(json.dumps(run_measure(conn, bets, False, a.apply), indent=1, default=str))
    elif a.command == "plan":
        bets = history_targets(conn)
        p = plan(conn, bets)
        done = bought(conn)
        slots = [(k, s) for day in p.values() for k, s in day.items()]
        todo = [s for k, s in slots if k not in done]
        est = sum(10 * len(s["markets"]) for s in todo) + len(p)
        print(json.dumps({"bets": len(bets), "sport_days": len(p), "game_books": len(slots),
                          "to_buy": len(todo), "max_credits": est,
                          "unbounded": sum(1 for b in bets if b.bound is None)}, indent=1))
    elif a.command == "buy":
        print(json.dumps(buy(conn, a.limit), indent=1, default=str))
    elif a.command == "history":
        bets = history_targets(conn)
        if a.apply and not a.only_bought:
            # The older games' stored rows were pruned: without a purchase the
            # rule finds no pull and would write "no close" over a close that
            # was right. Apply only where the history has been bought.
            print("history --apply needs --only-bought: a bet whose game and book were "
                  "not bought would be measured from pruned rows alone.")
            return 2
        if a.only_bought:
            done = bought(conn)
            bets = [b for b in bets if (b.game_id, b.bet_book) in done]
        print(json.dumps(run_measure(conn, bets, True, a.apply), indent=1, default=str))
    elif a.command == "remeasure-none":
        bets = cc.load_bets(conn, """
            p.pick_id IN (SELECT pick_id FROM public.clv_close_measurements WHERE source = 'none')
            ORDER BY p.pick_id""")
        print(json.dumps(run_measure(conn, bets, True, a.apply), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The closing pull: the bet book's price at the start, for every pre-game bet (issue #1470).

Every minute (scheduler.run_clv_closing_pull), for each game with a pre-game BET
that starts in the next PULL_LEAD_MAX, one call to the feed's event endpoint
for that game: the bet books, the bet markets and their alternate ladders. The
quotes go to `clv_close_quotes`, stamped with the instant they were pulled, and
tracking/clv_close.py reads them with our own stored rows when it measures the
close.

WHY. The regular passes stop pulling a book about ten minutes before the start
for many markets, and most of them never pull the alternate ladder. Measured on
the 145 published bets of 2026-11-15..18: 10 were placed after the book's last
pull before the start (so had no close at all), and 24 had a last pull whose
main line had left our number with no alternate at our number stored.

WHAT ONE CALL COSTS. The live event endpoint bills one credit per market
returned per region; a bookmakers list of up to ten counts as one region
(odds_ingestor._get_event_odds, measured on the NBA and NCAAB live feeds). A
game with one moneyline bet is one credit; a spread bet two (the line and its
ladder); a prop bet two per market.

A game is pulled once per bet that came before the pull (the ledger,
clv_close_purchases with kind 'closing'): a bet placed after the game's last
closing pull gets another on the next tick, while the game is still inside
the window. NHL moneylines are decided about four minutes before the start,
which is after the first closing pull (measured on 2026-11-11..16 bets). A
failed call is tried again on the next tick the same way. No call within PULL_LEAD_MIN of the start: the answer could land
after it.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from loguru import logger

PULL_LEAD_MAX = timedelta(minutes=4)
PULL_LEAD_MIN = timedelta(seconds=40)
SOURCE_LIVE = "odds_api_live_clv_close"
SOURCE_HISTORY = "odds_api_history_clv_close"

# Stored market name -> the feed's key, and the feed's alternate key.
_API_MAIN = {"team_totals_home": "team_totals", "team_totals_away": "team_totals",
             "h2h_3way": "h2h_3_way"}
_API_ALT = {"spreads": "alternate_spreads", "totals": "alternate_totals",
            "team_totals_home": "alternate_team_totals", "team_totals_away": "alternate_team_totals"}


def api_markets(bet) -> list[str]:
    """The feed's keys for a bet's market and its alternate ladder."""
    out = []
    if bet.market:
        out.append(_API_MAIN.get(bet.market, bet.market))
        if bet.alt:
            if bet.kind == "prop":
                out.append(bet.alt)                         # player_points_alternate
            elif bet.market in _API_ALT:
                out.append(_API_ALT[bet.market])
            else:
                out.append(f"alternate_{bet.market}")       # alternate_spreads_h1
    return out


def stored_market(api_key: str, home: bool | None = None) -> str:
    if api_key == "team_totals":
        return "team_totals_home" if home else "team_totals_away"
    if api_key == "alternate_team_totals":
        return "team_totals_home_alternate" if home else "team_totals_away_alternate"
    if api_key == "h2h_3_way":
        return "h2h_3way"
    if api_key in ("alternate_spreads", "alternate_totals"):
        return api_key
    if api_key.startswith("alternate_"):
        return f"{api_key[len('alternate_'):]}_alternate"   # spreads_h1_alternate
    return api_key


def parse_book(game_id: str, book: dict, home_name: str, fetched_at: datetime,
               event_id: str, prop_markets: set[str]) -> list[dict]:
    """One bookmaker's markets from a feed answer as clv_close_quotes rows,
    HOME-relative (spread_home is the home number)."""
    rows = []
    for m in book.get("markets", []):
        key = m.get("key") or ""
        outs = m.get("outcomes") or []
        base = {"game_id": game_id, "bookmaker": book.get("key"), "fetched_at": fetched_at,
                "book_last_update": m.get("last_update"), "event_id": event_id}
        if key in prop_markets:
            by = defaultdict(dict)
            for o in outs:
                side = (o.get("name") or "").lower()
                if side in ("over", "under") and o.get("point") is not None:
                    by[(o.get("description"), float(o["point"]))][side] = o.get("price")
            for (player, line), px in by.items():
                rows.append({**base, "market": key, "player_name": player, "line": line,
                             "over_price": px.get("over"), "under_price": px.get("under")})
        elif "team_totals" in key:
            by = defaultdict(dict)
            for o in outs:
                side = (o.get("name") or "").lower()
                if side in ("over", "under") and o.get("point") is not None:
                    by[(o.get("description") == home_name, float(o["point"]))][side] = o.get("price")
            for (is_home, line), px in by.items():
                rows.append({**base, "market": stored_market(key, is_home), "total_line": line,
                             "over_price": px.get("over"), "under_price": px.get("under")})
        elif "spreads" in key:
            home_px, away_px = {}, {}
            for o in outs:
                if o.get("point") is None:
                    continue
                if o.get("name") == home_name:
                    home_px[float(o["point"])] = o.get("price")
                else:
                    away_px[float(o["point"])] = o.get("price")
            for pt in set(home_px) | {-p for p in away_px}:
                rows.append({**base, "market": stored_market(key), "spread_home": pt,
                             "home_price": home_px.get(pt), "away_price": away_px.get(-pt)})
        elif "totals" in key:
            by = defaultdict(dict)
            for o in outs:
                side = (o.get("name") or "").lower()
                if side in ("over", "under") and o.get("point") is not None:
                    by[float(o["point"])][side] = o.get("price")
            for line, px in by.items():
                rows.append({**base, "market": stored_market(key), "total_line": line,
                             "over_price": px.get("over"), "under_price": px.get("under")})
        elif key.startswith("h2h"):
            row = {**base, "market": stored_market(key)}
            for o in outs:
                if o.get("name") == home_name:
                    row["home_price"] = o.get("price")
                elif (o.get("name") or "").lower() == "draw":
                    row["draw_price"] = o.get("price")
                else:
                    row["away_price"] = o.get("price")
            rows.append(row)
    return rows


_QCOLS = ("game_id", "bookmaker", "market", "player_name", "spread_home", "total_line", "line",
          "home_price", "away_price", "draw_price", "over_price", "under_price", "fetched_at",
          "book_last_update", "event_id")


def store_quotes(conn, rows: list[dict], source: str) -> int:
    n = 0
    for r in rows:
        cur = conn.execute(f"""
            INSERT INTO public.clv_close_quotes ({", ".join(_QCOLS)}, source)
            VALUES ({", ".join(["%s"] * len(_QCOLS))}, %s)
            ON CONFLICT DO NOTHING
        """, tuple(r.get(c) for c in _QCOLS) + (source,))
        n += max(cur.rowcount, 0)
    return n


def ledger(conn, game_id, book, asked_for, markets, event_id, snapshot, ok, credits, quotes,
           error, kind):
    conn.execute("""
        INSERT INTO public.clv_close_purchases
               (game_id, bookmaker, asked_for, markets, event_id, snapshot_at, ok, credits,
                quotes, error, kind)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (game_id, book, asked_for, ",".join(markets), event_id, snapshot, ok, credits, quotes,
          error, kind))
    conn.commit()


# ── the live closing pull ────────────────────────────────────────────────────

def due(conn, now: datetime) -> dict:
    """{game_id: {"bound": t, "books": {...}, "markets": {...}, "props": {...}}}
    for pre-game bets starting in (now + PULL_LEAD_MIN, now + PULL_LEAD_MAX]
    whose game has no ok closing pull yet."""
    from tracking import clv_close as cc
    lo, hi = now + PULL_LEAD_MIN, now + PULL_LEAD_MAX
    bets = cc.load_bets(conn, """
            p.signal_type = 'BET' AND p.is_live IS NOT TRUE
        AND COALESCE(p.decision_odds, p.dk_odds) IS NOT NULL
        AND p.game_date BETWEEN %s AND %s
        AND g.commence_time IS NOT NULL
        AND g.commence_time::timestamptz > %s::timestamptz
        AND g.commence_time::timestamptz <= %s::timestamptz + interval '15 minutes'
        AND NOT EXISTS (SELECT 1 FROM public.clv_close_purchases c
                         WHERE c.game_id = p.game_id AND c.kind = 'closing' AND c.ok
                           AND c.snapshot_at > p.created_at::timestamptz)
    """, ((now - timedelta(days=1)).date().isoformat(), (now + timedelta(days=1)).date().isoformat(),
          lo.isoformat(), hi.isoformat()))
    out: dict = {}
    for b in bets:
        if b.bound is None or not (lo < b.bound <= hi) or not b.market:
            continue
        slot = out.setdefault(b.game_id, {"bound": b.bound, "books": set(), "markets": set(),
                                          "props": set()})
        slot["bound"] = min(slot["bound"], b.bound)
        slot["books"].add(b.bet_book)
        for k in api_markets(b):
            slot["markets"].add(k)
            if b.kind == "prop":
                slot["props"].add(k)
    return out


def pull(conn=None, now: datetime | None = None, http=None) -> dict:
    """One tick. Returns counts; never raises on a feed error (logged, ledgered)."""
    from data.db import get_connection
    from data.ingestors.alt_game_lines import game_for_event
    from data.ingestors.odds_ingestor import SPORT_KEYS, _schedule_resolver
    import config
    if os.environ.get("RUN_CLV_CLOSING_PULL", "1") == "0":
        return {"skipped": "RUN_CLV_CLOSING_PULL=0"}
    own = conn is None
    conn = conn or get_connection()
    now = now or datetime.now(timezone.utc)
    stats = defaultdict(int)
    try:
        row = conn.execute("SELECT to_regclass('public.clv_close_purchases') IS NOT NULL").fetchone()
        conn.commit()
        if not (row and row[0]):
            return {"skipped": "clv_close tables not created yet"}
        games = due(conn, now)
        if not games:
            return {}
        if http is None:
            import requests
            http = requests.Session()
        key = os.environ.get("ODDS_API_KEY")
        if not key:
            return {"skipped": "no ODDS_API_KEY"}
        by_sport = defaultdict(dict)
        for gid, slot in games.items():
            by_sport[gid.split("_", 1)[0]][gid] = slot
        for sport, slots in by_sport.items():
            sport_key = SPORT_KEYS.get(sport)
            if not sport_key:
                stats["no_sport_key"] += len(slots)
                continue
            r = http.get(f"{config.ODDS_API_BASE}/sports/{sport_key}/events",
                         params={"apiKey": key}, timeout=30)
            if r.status_code != 200:
                stats["events_failed"] += 1
                logger.warning(f"CLV closing pull {sport}: events HTTP {r.status_code}")
                continue
            day = min(s["bound"] for s in slots.values()).date().isoformat()
            resolver = _schedule_resolver(sport, conn, day)
            conn.commit()
            events = {}
            for ev in r.json() or []:
                hit = game_for_event(sport, ev, resolver)
                if hit:
                    events[hit[0]] = (ev, hit[1])
            for gid, slot in sorted(slots.items()):
                books = sorted(slot["books"])
                markets = sorted(slot["markets"])
                if gid not in events:
                    stats["unmatched_game"] += 1
                    for b in books:
                        ledger(conn, gid, b, slot["bound"], markets, None, None, False, 0, 0,
                               "no feed event matched", "closing")
                    continue
                ev, home_name = events[gid]
                params = {"apiKey": key, "regions": "us", "markets": ",".join(markets),
                          "bookmakers": ",".join(books), "oddsFormat": "american"}
                url = f"{config.ODDS_API_BASE}/sports/{sport_key}/events/{ev['id']}/odds"
                resp = http.get(url, params=params, timeout=30)
                billed = _billed(resp)
                if resp.status_code == 422 and any(m.startswith("alternate_") or m.endswith("_alternate")
                                                   for m in markets):
                    markets = [m for m in markets
                               if not m.startswith("alternate_") and not m.endswith("_alternate")]
                    params["markets"] = ",".join(markets)
                    resp = http.get(url, params=params, timeout=30)
                    billed = (billed or 0) + (_billed(resp) or 0)
                fetched = datetime.now(timezone.utc)
                if resp.status_code != 200:
                    stats["odds_failed"] += 1
                    for b in books:
                        ledger(conn, gid, b, slot["bound"], markets, ev["id"], None, False, billed, 0,
                               f"HTTP {resp.status_code}", "closing")
                    continue
                body = resp.json() or {}
                n_total = 0
                for bk in body.get("bookmakers") or []:
                    if bk.get("key") in slot["books"]:
                        n = store_quotes(conn, parse_book(gid, bk, home_name, fetched, ev["id"],
                                                          slot["props"]), SOURCE_LIVE)
                        n_total += n
                conn.commit()
                for b in books:
                    ledger(conn, gid, b, slot["bound"], markets, ev["id"], fetched, True,
                           billed, n_total, None, "closing")
                    billed = 0               # the call's bill on its first ledger row only
                stats["pulled"] += 1
                stats["quotes"] += n_total
        try:
            from data.ingestors import odds_quota
            odds_quota.persist_quota(conn)
        except Exception:                                      # noqa: BLE001
            pass
        if stats:
            logger.info(f"CLV closing pull: {dict(stats)}")
        return dict(stats)
    finally:
        if own:
            try:
                conn.close()
            except Exception:                                  # noqa: BLE001
                pass


def _billed(resp) -> int | None:
    try:
        from data.ingestors import odds_quota
        odds_quota.record_quota_headers(resp)
    except Exception:                                          # noqa: BLE001
        pass
    last = resp.headers.get("x-requests-last") if hasattr(resp, "headers") else None
    try:
        return int(float(last)) if last is not None else None
    except (TypeError, ValueError):
        return None

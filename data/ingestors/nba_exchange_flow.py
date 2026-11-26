"""Real-money order flow on NBA game-winner markets at two exchanges, before tip.

WHY (mike, 2026-11-26: "it doesn't take weeks why can't we get historical data
somewhere", about handle / money data). Sportsbook splits have no history anyone
sells with observation times (docs/nba_data_sources_and_handle_2026_11.md). Exchange
trades do: every trade is timestamped, priced, sized and signed by the side that took
liquidity, and both exchanges serve them for free:

  Kalshi      KXNBAGAME, one YES contract per team, settled events from 2025-04-15
              (research probe, 2026-11-26). Trades: /markets/trades, and
              /historical/trades for anything before the exchange's historical cutoff.
              Each trade carries taker_side, yes_price_dollars, count_fp, created_time.
  Polymarket  NBA game events from 2024-04 (play-in) and every regular-season month
              from 2024-10; trades from data-api /v2/trades?conditionId=..., each with
              side (BUY / SELL), outcome, price, size and a unix timestamp.

WHAT IS STORED. Only trades BEFORE the game's listed start (`games.commence_time`),
folded into 15-minute buckets per team: how many contracts were bought on that team
(the taker's side, Kalshi; the trade's side, Polymarket), what they cost, the
volume-weighted price, and the team's implied price at the bucket's last trade. A
January 2026 game carried 29,064 trades on one Kalshi market alone, so trade-level rows
for every game would run to tens of millions; the buckets keep the timing and the
direction, which is what the test needs. Rows land in `nba_exchange_flow`; the ledger
`nba_exchange_flow_fetches` holds one row per (source, game) read, so a re-run reads
nothing twice. An event that does not match a `games` row is logged and NOT ledgered,
so fixing the match and re-running picks it up.

Worker-only tables (RLS on, anon revoked). Nothing live reads them.

    python -m data.ingestors.nba_exchange_flow --source kalshi --apply
    python -m data.ingestors.nba_exchange_flow --source polymarket --apply --limit 20
    python -m data.ingestors.nba_exchange_flow --source both            # dry run: counts only
"""
from __future__ import annotations

import argparse
import json
import re
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests
from loguru import logger

import config

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"
PDATA = "https://data-api.polymarket.com"
KALSHI_SERIES = "KXNBAGAME"
BUCKET_MIN = 15
FLOW_TABLE = "nba_exchange_flow"
LEDGER = "nba_exchange_flow_fetches"
FLOW_DDL = f"""
CREATE TABLE IF NOT EXISTS {FLOW_TABLE} (
    source         TEXT NOT NULL,
    game_id        TEXT NOT NULL,
    team           TEXT NOT NULL,
    bucket_start   TIMESTAMPTZ NOT NULL,
    minutes_to_tip INTEGER NOT NULL,
    n_trades       INTEGER NOT NULL,
    buy_contracts  DOUBLE PRECISION NOT NULL,
    buy_notional   DOUBLE PRECISION NOT NULL,
    vwap           DOUBLE PRECISION,
    last_price     DOUBLE PRECISION,
    last_trade_at  TIMESTAMPTZ,
    PRIMARY KEY (source, game_id, team, bucket_start)
)
"""
LEDGER_DDL = f"""
CREATE TABLE IF NOT EXISTS {LEDGER} (
    source          TEXT NOT NULL,
    game_id         TEXT NOT NULL,
    market_ids      TEXT NOT NULL,
    tip             TIMESTAMPTZ NOT NULL,
    trades_read     INTEGER NOT NULL,
    pre_tip_trades  INTEGER NOT NULL,
    pre_tip_notional DOUBLE PRECISION NOT NULL,
    note            TEXT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source, game_id)
)
"""
UA = {"User-Agent": "Mozilla/5.0 (research; betting-model)", "Accept": "application/json"}

# Standard alternate NBA codes, applied only to a code that is not one of ours, and
# only kept when the pair then matches a `games` row on that date.
CODE_ALIAS = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "PHO": "PHX", "BRK": "BKN",
              "WSH": "WAS", "CHO": "CHA", "UTAH": "UTA", "NJ": "BKN", "LA": "LAL"}
_MON = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
_KEVENT = re.compile(r"^KXNBAGAME-(\d{2})([A-Z]{3})(\d{2})([A-Z]+)$")
_PSLUG = re.compile(r"^nba-([a-z]{2,4})-([a-z]{2,4})-(\d{4}-\d{2}-\d{2})$")


# ── pure pieces (tested) ─────────────────────────────────────────────────────

def our_code(code: str, ours: set[str]) -> str | None:
    c = (code or "").upper()
    if c in ours:
        return c
    a = CODE_ALIAS.get(c)
    return a if a in ours else None


def kalshi_event(ticker: str) -> tuple[str, str] | None:
    """'KXNBAGAME-26JAN01UTALAC' -> ('2026-01-01', 'UTALAC')."""
    m = _KEVENT.match(ticker or "")
    if not m or m.group(2) not in _MON:
        return None
    return f"20{m.group(1)}-{_MON[m.group(2)]:02d}-{m.group(3)}", m.group(4)


def nickname_map() -> dict[str, str]:
    """'Pelicans' / 'Trail Blazers' / 'Clippers' -> our code, from the full names we map."""
    out: dict[str, str] = {}
    for full, code in config.NBA_ODDS_API_MAP.items():
        words = full.split()
        for k in range(1, len(words)):
            out[" ".join(words[k:]).lower()] = code
        out[full.lower()] = code
    out["76ers"] = "PHI"
    out["sixers"] = "PHI"
    return out


def team_for_outcome(outcome: str, nick: dict[str, str]) -> str | None:
    return nick.get((outcome or "").strip().lower())


def kalshi_leg(trade: dict, market_team: str, other_team: str) -> tuple[str, float, float, datetime] | None:
    """One Kalshi trade on the market that pays if `market_team` wins, as
    (team the taker bought, that team's price, contracts, time)."""
    try:
        p = float(trade.get("yes_price_dollars"))
        c = float(trade.get("count_fp") if trade.get("count_fp") is not None else trade.get("count"))
        ts = datetime.fromisoformat(trade["created_time"].replace("Z", "+00:00"))
    except (TypeError, ValueError, KeyError):
        return None
    side = trade.get("taker_side")
    if side == "yes":
        return market_team, p, c, ts
    if side == "no":
        return other_team, round(1.0 - p, 6), c, ts
    return None


def poly_leg(trade: dict, team: str, other_team: str) -> tuple[str, float, float, datetime] | None:
    """One Polymarket trade on the outcome `team`: BUY buys it, SELL sells it (buys the other)."""
    try:
        p = float(trade.get("price"))
        c = float(trade.get("size"))
        ts = datetime.fromtimestamp(int(trade["timestamp"]), tz=timezone.utc)
    except (TypeError, ValueError, KeyError):
        return None
    side = (trade.get("side") or "").upper()
    if side == "BUY":
        return team, p, c, ts
    if side == "SELL":
        return other_team, round(1.0 - p, 6), c, ts
    return None


def bucket_rows(source: str, game_id: str, tip: datetime,
                legs: list[tuple[str, float, float, datetime]], teams: tuple[str, str]) -> list[dict]:
    """Pre-tip legs folded into BUCKET_MIN buckets per team. `last_price` is each team's
    implied price at the bucket's last trade, whichever team that trade bought."""
    pre = sorted((l for l in legs if l[3] < tip), key=lambda l: l[3])
    agg: dict[tuple[str, datetime], dict] = {}
    last_in_bucket: dict[datetime, tuple[str, float, datetime]] = {}
    for team, price, c, ts in pre:
        b = ts.replace(second=0, microsecond=0) - timedelta(minutes=ts.minute % BUCKET_MIN)
        a = agg.setdefault((team, b), {"n": 0, "c": 0.0, "notional": 0.0})
        a["n"] += 1
        a["c"] += c
        a["notional"] += c * price
        last_in_bucket[b] = (team, price, ts)
    rows = []
    for b, (lt, lp, lts) in last_in_bucket.items():
        for team in teams:
            a = agg.get((team, b), {"n": 0, "c": 0.0, "notional": 0.0})
            implied = lp if team == lt else round(1.0 - lp, 6)
            rows.append({"source": source, "game_id": game_id, "team": team, "bucket_start": b,
                         "minutes_to_tip": int((tip - b).total_seconds() // 60),
                         "n_trades": a["n"], "buy_contracts": round(a["c"], 4),
                         "buy_notional": round(a["notional"], 4),
                         "vwap": round(a["notional"] / a["c"], 6) if a["c"] else None,
                         "last_price": implied, "last_trade_at": lts})
    return rows


# ── HTTP ─────────────────────────────────────────────────────────────────────

class Pace:
    """At most `per_sec` requests a second across threads."""

    def __init__(self, per_sec: float):
        self.gap, self.lock, self.next = 1.0 / per_sec, threading.Lock(), 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        time.sleep(max(0.0, t - now))


def _get(pace: Pace, url: str, params: dict) -> requests.Response | None:
    for attempt in range(5):
        pace.wait()
        try:
            r = requests.get(url, params=params, headers=UA, timeout=60)
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(3 * (attempt + 1))
            continue
        return r
    return None


# ── Kalshi ───────────────────────────────────────────────────────────────────

def _kpages(pace, path, params, key, pages=200):
    out, cursor = [], None
    for _ in range(pages):
        p = dict(params)
        if cursor:
            p["cursor"] = cursor
        r = _get(pace, f"{KALSHI}{path}", p)
        if r is None or r.status_code != 200:
            return out, getattr(r, "status_code", None)
        body = r.json()
        out += body.get(key) or []
        cursor = body.get("cursor")
        if not cursor:
            break
    return out, 200


def kalshi_trades(pace: Pace, ticker: str, tip: datetime) -> list[dict]:
    """Every trade before `tip`: the live endpoint, else the historical one. `max_ts` is
    sent; if an endpoint refuses it the trades are read whole and filtered after."""
    max_ts = int(tip.timestamp())
    for path in ("/markets/trades", "/historical/trades"):
        tr, code = _kpages(pace, path, {"ticker": ticker, "limit": 1000, "max_ts": max_ts}, "trades")
        if code == 400:
            tr, code = _kpages(pace, path, {"ticker": ticker, "limit": 1000}, "trades")
        if tr:
            return tr
    return []


def kalshi_games(pace: Pace) -> list[dict]:
    evs, code = _kpages(pace, "/events", {"series_ticker": KALSHI_SERIES, "status": "settled",
                                          "limit": 200}, "events")
    logger.info(f"kalshi {KALSHI_SERIES}: {len(evs)} settled events (HTTP {code})")
    return evs


def kalshi_one(pace: Pace, ev: dict, games_by_date: dict, ours: set[str],
               done: set | frozenset = frozenset()) -> dict:
    """Read one event. Returns {'game': ..., 'rows': [...], 'ledger': {...}} or {'unmatched': why}."""
    et = ev.get("event_ticker", "")
    parsed = kalshi_event(et)
    if not parsed:
        return {"unmatched": f"{et}: ticker not parsed"}
    d, codes = parsed
    mk, _ = _kpages(pace, "/markets", {"event_ticker": et, "limit": 100}, "markets", pages=1)
    if not mk:
        mk, _ = _kpages(pace, "/historical/markets", {"event_ticker": et, "limit": 100}, "markets", pages=1)
    sfx = {m["ticker"].rsplit("-", 1)[-1]: m["ticker"] for m in mk if m.get("ticker")}
    mapped = {our_code(s, ours): t for s, t in sfx.items()}
    mapped.pop(None, None)
    if len(mapped) != 2:
        return {"unmatched": f"{et}: market codes {sorted(sfx)}"}
    pair = set(mapped)
    game = None
    for day in (d, (datetime.fromisoformat(d) - timedelta(days=1)).date().isoformat(),
                (datetime.fromisoformat(d) + timedelta(days=1)).date().isoformat()):
        hits = [g for g in games_by_date.get(day, []) if {g["home"], g["away"]} == pair]
        if len(hits) == 1:
            game = hits[0]
            break
    if game is None:
        return {"unmatched": f"{et}: no games row for {sorted(pair)} near {d}"}
    if ("kalshi", game["game_id"]) in done:
        return {"already": game["game_id"]}
    tip = game["tip"]
    legs, read = [], 0
    for team, ticker in mapped.items():
        other = (pair - {team}).pop()
        tr = kalshi_trades(pace, ticker, tip)
        read += len(tr)
        legs += [l for l in (kalshi_leg(t, team, other) for t in tr) if l]
    rows = bucket_rows("kalshi", game["game_id"], tip, legs, (game["home"], game["away"]))
    pre = [l for l in legs if l[3] < tip]
    return {"game": game, "rows": rows,
            "ledger": {"source": "kalshi", "game_id": game["game_id"],
                       "market_ids": ",".join(sorted(mapped.values())), "tip": tip,
                       "trades_read": read, "pre_tip_trades": len(pre),
                       "pre_tip_notional": round(sum(c * p for _, p, c, _ in pre), 2), "note": None}}


# ── Polymarket ───────────────────────────────────────────────────────────────

def poly_events(pace: Pace) -> list[dict]:
    r = _get(pace, f"{GAMMA}/tags/slug/nba", {})
    tag = r.json().get("id") if r is not None and r.status_code == 200 else None
    if not tag:
        logger.warning("polymarket: no nba tag")
        return []
    out, seen, cursor = [], set(), None
    for _ in range(400):
        params = {"tag_id": tag, "closed": "true", "limit": 500}
        if cursor:
            params["next_cursor"] = cursor
        r = _get(pace, f"{GAMMA}/events/keyset", params)
        if r is None or r.status_code != 200:
            logger.warning(f"polymarket keyset HTTP {getattr(r, 'status_code', None)}")
            break
        body = r.json()
        new = [e for e in body.get("events") or [] if e.get("id") not in seen]
        if not new:
            break
        for e in new:
            seen.add(e.get("id"))
        out += new
        cursor = body.get("next_cursor")
        if not cursor:
            break
    games = [e for e in out if _PSLUG.match(e.get("slug") or "")]
    logger.info(f"polymarket nba: {len(out)} closed events, {len(games)} game slugs")
    return games


def _moneyline_market(ev: dict) -> dict | None:
    mk = ev.get("markets") or []
    for m in mk:
        if (m.get("slug") or "") == ev.get("slug"):
            return m
    for m in mk:
        if (m.get("question") or "").strip() == (ev.get("title") or "").strip():
            return m
    return mk[0] if len(mk) == 1 else None


_POLY_TAKER_PARAM: list = []


def poly_trades(pace: Pace, cid: str) -> list[dict]:
    """Every trade on one condition. The first call learns whether the API takes a
    taker-only flag (an unknown parameter answers 400 on this API)."""
    if not _POLY_TAKER_PARAM:
        for cand in ({"takerOnly": "true"}, {"taker_only": "true"}, {}):
            r = _get(pace, f"{PDATA}/v2/trades", {"conditionId": cid, "limit": 1, **cand})
            if r is not None and r.status_code == 200:
                _POLY_TAKER_PARAM.append(cand)
                logger.info(f"polymarket trades: taker flag {cand or 'none accepted'}")
                break
        else:
            _POLY_TAKER_PARAM.append({})
    extra = _POLY_TAKER_PARAM[0]
    out, cursor, offset = [], None, 0
    for _ in range(400):
        params = {"conditionId": cid, "limit": 500, **extra}
        if cursor:
            params["next_cursor"] = cursor
        elif offset:
            params["offset"] = offset
        r = _get(pace, f"{PDATA}/v2/trades", params)
        if r is None or r.status_code != 200:
            break
        body = r.json()
        data = body.get("data") if isinstance(body, dict) else body
        if not data:
            break
        out += data
        cursor = body.get("next_cursor") if isinstance(body, dict) else None
        if not cursor:
            if len(data) < 500:
                break
            offset += len(data)
    return out


def poly_one(pace: Pace, ev: dict, games_by_date: dict, nick: dict,
             done: set | frozenset = frozenset()) -> dict:
    slug = ev.get("slug", "")
    m = _PSLUG.match(slug)
    mk = _moneyline_market(ev)
    if not m or mk is None:
        return {"unmatched": f"{slug}: no moneyline market"}
    try:
        outcomes = json.loads(mk.get("outcomes") or "[]")
    except ValueError:
        outcomes = []
    teams = [team_for_outcome(o, nick) for o in outcomes]
    if len(teams) != 2 or None in teams or teams[0] == teams[1]:
        return {"unmatched": f"{slug}: outcomes {outcomes}"}
    pair = set(teams)
    d = m.group(3)
    game = None
    for day in (d, (datetime.fromisoformat(d) - timedelta(days=1)).date().isoformat(),
                (datetime.fromisoformat(d) + timedelta(days=1)).date().isoformat()):
        hits = [g for g in games_by_date.get(day, []) if {g["home"], g["away"]} == pair]
        if len(hits) == 1:
            game = hits[0]
            break
    if game is None:
        return {"unmatched": f"{slug}: no games row for {sorted(pair)} near {d}"}
    if ("polymarket", game["game_id"]) in done:
        return {"already": game["game_id"]}
    tip = game["tip"]
    tr = poly_trades(pace, mk.get("conditionId"))
    by_name = dict(zip(outcomes, teams))
    legs = []
    for t in tr:
        team = by_name.get(t.get("outcome"))
        if team is None:
            continue
        leg = poly_leg(t, team, (pair - {team}).pop())
        if leg:
            legs.append(leg)
    rows = bucket_rows("polymarket", game["game_id"], tip, legs, (game["home"], game["away"]))
    pre = [l for l in legs if l[3] < tip]
    sides = defaultdict(float)
    for t in tr:
        sides[(t.get("side") or "?").upper()] += float(t.get("size") or 0)
    return {"game": game, "rows": rows,
            "ledger": {"source": "polymarket", "game_id": game["game_id"],
                       "market_ids": mk.get("conditionId"), "tip": tip, "trades_read": len(tr),
                       "pre_tip_trades": len(pre),
                       "pre_tip_notional": round(sum(c * p for _, p, c, _ in pre), 2),
                       "note": json.dumps({"taker_flag": _POLY_TAKER_PARAM[0] if _POLY_TAKER_PARAM else None,
                                           "size_by_side": {k: round(v, 2) for k, v in sides.items()}})}}


# ── database ─────────────────────────────────────────────────────────────────

def _games_by_date(conn) -> tuple[dict, set[str]]:
    rows = conn.execute(
        "SELECT game_id, game_date::text, home_team, away_team, commence_time FROM games "
        "WHERE sport = 'NBA' AND season >= 2024 AND commence_time IS NOT NULL "
        "AND home_team <> 'NaN'").fetchall()
    by: dict[str, list] = defaultdict(list)
    ours: set[str] = set()
    for gid, d, h, a, ct in rows:
        tip = datetime.fromisoformat(str(ct).replace("Z", "+00:00"))
        if tip.tzinfo is None:
            tip = tip.replace(tzinfo=timezone.utc)
        by[d].append({"game_id": gid, "home": h, "away": a, "tip": tip})
        ours |= {h, a}
    return by, ours


def _ensure(conn) -> None:
    from data.anon_readable import lock_down
    from data.ddl_guard import schema_is_current
    if not schema_is_current(conn, FLOW_TABLE):
        conn.execute(FLOW_DDL)
    if not schema_is_current(conn, LEDGER):
        conn.execute(LEDGER_DDL)
    lock_down(conn, FLOW_TABLE)
    lock_down(conn, LEDGER)
    conn.commit()


def _store(conn, out: dict) -> None:
    if out["rows"]:
        conn.executemany(f"""
            INSERT INTO {FLOW_TABLE} (source, game_id, team, bucket_start, minutes_to_tip, n_trades,
                buy_contracts, buy_notional, vwap, last_price, last_trade_at)
            VALUES (%(source)s, %(game_id)s, %(team)s, %(bucket_start)s, %(minutes_to_tip)s,
                %(n_trades)s, %(buy_contracts)s, %(buy_notional)s, %(vwap)s, %(last_price)s,
                %(last_trade_at)s)
            ON CONFLICT DO NOTHING""", out["rows"])
    conn.execute(f"""
        INSERT INTO {LEDGER} (source, game_id, market_ids, tip, trades_read, pre_tip_trades,
            pre_tip_notional, note)
        VALUES (%(source)s, %(game_id)s, %(market_ids)s, %(tip)s, %(trades_read)s,
            %(pre_tip_trades)s, %(pre_tip_notional)s, %(note)s)
        ON CONFLICT DO NOTHING""", out["ledger"])
    conn.commit()


def run(source: str, apply: bool, limit: int | None, workers: int = 4) -> dict:
    from data.db import get_connection
    conn = get_connection()
    stats = defaultdict(int)
    try:
        if apply:
            _ensure(conn)
        by_date, ours = _games_by_date(conn)
        done = set()
        if apply:
            done = {(s, g) for s, g in conn.execute(f"SELECT source, game_id FROM {LEDGER}").fetchall()}
        nick = nickname_map()
        jobs = []
        if source in ("kalshi", "both"):
            kp = Pace(8.0)
            jobs += [("kalshi", ev, kp) for ev in kalshi_games(kp)]
        if source in ("polymarket", "both"):
            pp = Pace(8.0)
            jobs += [("polymarket", ev, pp) for ev in poly_events(pp)]
        if limit:
            jobs = jobs[:limit]
        logger.info(f"exchange flow: {len(jobs)} events to read, {len(done)} games already ledgered")

        def one(job):
            src, ev, pace = job
            try:
                if src == "kalshi":
                    return src, kalshi_one(pace, ev, by_date, ours, done)
                return src, poly_one(pace, ev, by_date, nick, done)
            except Exception as exc:  # noqa: BLE001 — one event's failure must not stop the run
                return src, {"unmatched": f"{ev.get('event_ticker') or ev.get('slug')}: "
                                          f"{type(exc).__name__}: {exc}"[:300]}

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for i, (src, out) in enumerate(pool.map(one, jobs), 1):
                if "unmatched" in out:
                    stats[f"{src}_unmatched"] += 1
                    if stats[f"{src}_unmatched"] <= 40:
                        logger.warning(f"unmatched {src}: {out['unmatched']}")
                    continue
                if "already" in out:
                    stats[f"{src}_already"] += 1
                    continue
                key = (src, out["game"]["game_id"])
                if key in done:
                    stats[f"{src}_duplicate_event"] += 1
                    continue
                stats[f"{src}_games"] += 1
                stats[f"{src}_rows"] += len(out["rows"])
                stats[f"{src}_pre_tip_trades"] += out["ledger"]["pre_tip_trades"]
                if apply:
                    _store(conn, out)
                    done.add(key)
                if i % 100 == 0:
                    logger.info(f"exchange flow: {i}/{len(jobs)} read | {dict(stats)}")
        logger.info(f"exchange flow done: {dict(stats)}")
        return dict(stats)
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", choices=("kalshi", "polymarket", "both"), default="both")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    print(run(a.source, a.apply, a.limit, a.workers))


if __name__ == "__main__":
    main()

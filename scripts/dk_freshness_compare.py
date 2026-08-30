"""
Collect DraftKings' OWN in-play lines, so the aggregator's lag can be measured.

THE QUESTION THIS EXISTS TO ANSWER. We know The Odds API serves one cached
in-play snapshot for ~45 seconds (136 snapshots over 2.5 hours, ~7 of our polls
per snapshot). What we do NOT know is whether that cache is merely COARSE or
also BEHIND -- a 45s-old-but-accurate snapshot and a snapshot that is itself a
minute stale look identical from our side, and the difference decides whether
there is anything to fix at all:

    coarse only  -> nothing to buy. The edge band + disclosure already shipped
                    ARE the fix.
    also behind  -> it is a source problem, and the source has to change.

Answering it needs a second, independent read of DraftKings' line. As of
2026-08-30 we have one: DK's own league feed answers a request carrying a real
browser TLS fingerprint (see scripts/dk_direct_probe.py).

WHY THIS COSTS NOTHING. It does NOT poll The Odds API. The live loop already
writes in-play rows into `odds` with `snapshot_at` = the feed's own publish
stamp and `created_at` = our clock, so the aggregator's half of the comparison
is already accruing in the database. This collector only has to record DK's
side; the join happens afterwards, offline, in SQL (see ANALYSIS below).

That also means the comparison measures what we ACTUALLY HAVE rather than a
parallel fetch made under better conditions -- which is the number that matters.

WHAT IT RECORDS. One row per DISTINCT quote, not one per poll. `quote_key` is
unique, so re-seeing the same line and price is a no-op and `observed_at` stays
the FIRST moment DK showed it. That is the whole measurement: first-seen here
versus first-seen in `odds`.

STATUS: SPIKE. Read-only, ~1 request per 5s, on a public unauthenticated page.
It writes to its own table and nothing in the pipeline reads it. DraftKings'
terms forbid automated access however the request is shaped, so this stays a
measurement and does not become a feed without a separate decision.

ANALYSIS (run after a session, against the same database):

    -- how far behind the aggregator was, per line change
    SELECT d.event_name, d.market, d.line,
           d.observed_at                       AS dk_first_seen,
           MIN(o.created_at::timestamptz)      AS aggregator_first_seen,
           EXTRACT(EPOCH FROM MIN(o.created_at::timestamptz) - d.observed_at) AS lag_sec
      FROM dk_line_observations d
      JOIN games g   ON g.game_date = CURRENT_DATE AND g.sport = 'MLB'
      JOIN odds  o   ON o.game_id = g.game_id
                    AND o.snapshot_type = 'in_play'
                    AND o.bookmaker = 'draftkings'
                    AND o.market = d.market
                    AND o.total_line = d.line
                    AND o.created_at::timestamptz >= d.observed_at
     WHERE d.market = 'totals'
     GROUP BY 1,2,3,4
     ORDER BY lag_sec DESC;

  A lag clustering near half the ~45s cache window is the COARSE case -- we are
  landing at a random point inside a stale bucket. A lag consistently ABOVE the
  window is the BEHIND case, and is the finding that would justify changing
  source.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.dk_direct_probe import CANDIDATES, HEADERS, _session   # noqa: E402

# DK's own market names, mapped onto the market vocabulary the rest of this
# repo uses, so the join in ANALYSIS above needs no translation layer.
MARKET_MAP = {
    "Moneyline": "h2h",
    "Total": "totals",
    "Total Points": "totals",
    "Total Runs": "totals",
    "Run Line": "spreads",
    "Spread": "spreads",
    "Point Spread": "spreads",
}

DDL = """
CREATE TABLE IF NOT EXISTS dk_line_observations (
    obs_id       BIGSERIAL PRIMARY KEY,
    observed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    quote_key    TEXT UNIQUE NOT NULL,
    sport        TEXT,
    dk_event_id  TEXT,
    event_name   TEXT,
    event_status TEXT,
    period       TEXT,
    market       TEXT,
    line         NUMERIC,
    side_a       TEXT,
    price_a      INTEGER,
    side_b       TEXT,
    price_b      INTEGER
)
"""


def _american(sel: dict) -> int | None:
    """DK writes American odds with a UNICODE minus (U+2212), not ASCII '-', so
    int() on the raw string raises. Decimal is the safer field and is used as
    the fallback; both are read because a missing decimal is likelier than a
    missing display string."""
    disp = (sel.get("displayOdds") or {}).get("american")
    if isinstance(disp, str):
        cleaned = disp.replace("−", "-").replace("+", "+").strip()
        try:
            return int(cleaned)
        except ValueError:
            pass
    dec = sel.get("decimal") or (sel.get("displayOdds") or {}).get("decimal")
    try:
        d = float(dec)
    except (TypeError, ValueError):
        return None
    if d <= 1.0:
        return None
    return round((d - 1) * 100) if d >= 2.0 else round(-100 / (d - 1))


def parse_dk_payload(body: dict, sport: str, live_only: bool = True) -> list[dict]:
    """DK's league feed -> one record per main market of each event.

    Pure: no clock, no network, no database. Everything about this payload that
    could change shape is isolated here."""
    events = {str(e.get("id")): e for e in body.get("events") or []}
    markets = [m for m in body.get("markets") or [] if m.get("main")]
    by_market: dict[str, list[dict]] = {}
    for sel in body.get("selections") or []:
        by_market.setdefault(str(sel.get("marketId")), []).append(sel)

    out: list[dict] = []
    for mk in markets:
        ev = events.get(str(mk.get("eventId")))
        if not ev:
            continue
        status = ev.get("status") or ""
        if live_only and status != "STARTED":
            continue
        market = MARKET_MAP.get(mk.get("name") or "")
        if not market:
            continue
        sels = [s for s in by_market.get(str(mk.get("id")), []) if s.get("main") is not False]
        if len(sels) != 2:
            continue
        # Order deterministically so the same quote always builds the same key:
        # Over/Home first, whatever the payload's ordering happens to be.
        pref = {"Over": 0, "Home": 0, "Under": 1, "Away": 1}
        sels.sort(key=lambda s: pref.get(s.get("outcomeType") or "", 9))
        a, b = sels
        line = a.get("points")
        if line is None:
            line = b.get("points")
        try:
            line = float(line) if line is not None else None
        except (TypeError, ValueError):
            line = None
        rec = {
            "sport": sport,
            "dk_event_id": str(ev.get("id")),
            "event_name": ev.get("name"),
            "event_status": status,
            "period": ((ev.get("liveGameState") or {}).get("period")),
            "market": market,
            "line": line,
            "side_a": a.get("label"),
            "price_a": _american(a),
            "side_b": b.get("label"),
            "price_b": _american(b),
        }
        if rec["price_a"] is None or rec["price_b"] is None:
            continue
        rec["quote_key"] = "|".join(str(rec[k]) for k in
                                    ("dk_event_id", "market", "line",
                                     "price_a", "price_b"))
        out.append(rec)
    return out


def _store(conn, rows: list[dict]) -> int:
    """First-seen semantics: the unique quote_key means a repeat is a no-op and
    observed_at keeps pointing at the moment DK FIRST showed this number."""
    if not rows:
        return 0
    cols = ("quote_key", "sport", "dk_event_id", "event_name", "event_status",
            "period", "market", "line", "side_a", "price_a", "side_b", "price_b")
    sql = (f"INSERT INTO dk_line_observations ({', '.join(cols)}) VALUES "
           f"({', '.join('%(' + c + ')s' for c in cols)}) "
           "ON CONFLICT (quote_key) DO NOTHING")
    n = 0
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(sql, r)
            n += cur.rowcount or 0
    conn.commit()
    return n


def run(sports: list[str], minutes: float, interval: float,
        impersonate: str, dry_run: bool) -> None:
    sess = _session(impersonate, bootstrap=False)
    conn = None
    if not dry_run:
        from data.db import get_connection
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()

    deadline = time.time() + minutes * 60
    polls = new_quotes = 0
    while time.time() < deadline:
        started = time.time()
        for sport in sports:
            url = CANDIDATES[sport][0]
            try:
                body = sess.get(url, headers=HEADERS, timeout=15).json()
            except Exception as exc:                          # noqa: BLE001
                print(f"  {sport} fetch failed: {type(exc).__name__}: {exc}",
                      flush=True)
                continue
            rows = parse_dk_payload(body, sport)
            polls += 1
            if dry_run:
                for r in rows[:6]:
                    print(f"  {r['event_name']:<34} {r['market']:<8} "
                          f"{r['line']}  {r['price_a']}/{r['price_b']}  "
                          f"({r['period']})", flush=True)
                print(f"  -- {sport}: {len(rows)} live main markets", flush=True)
            else:
                added = _store(conn, rows)
                new_quotes += added
                if added:
                    print(f"{datetime.now(timezone.utc):%H:%M:%S} {sport}: "
                          f"+{added} new quote(s) of {len(rows)} live",
                          flush=True)
        if dry_run:
            break
        # Deadline-based, not a flat sleep: at a 5s cadence the fetch time is a
        # large share of the interval and a flat sleep silently runs slower
        # than it reads (the ncaaf_live/gameday lesson).
        time.sleep(max(0.0, interval - (time.time() - started)))

    print(f"\npolls={polls} new_quotes={new_quotes}", flush=True)
    if conn is not None:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sports", nargs="*", default=["MLB"])
    ap.add_argument("--minutes", type=float, default=90.0)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--impersonate", default="chrome124")
    ap.add_argument("--dry-run", action="store_true",
                    help="one poll, print what was parsed, touch no database")
    a = ap.parse_args()
    print(f"dk-freshness-compare @ {datetime.now(timezone.utc).isoformat()} "
          f"sports={a.sports} every {a.interval}s for {a.minutes}m",
          flush=True)
    run([s for s in a.sports if s in CANDIDATES], a.minutes, a.interval,
        a.impersonate, a.dry_run)

"""NBA quarter and half lines before tip, for members asking the AI assistant (Matt, 2026-11-26).

WHY. A member asked the Signal Base connector for tonight's NBA 1Q totals at 5:48 PM ET and got nothing. Measured
2026-11-25: before tip, the only NBA period prices stored were the 1Q spread and moneyline (the nba_q1_trend models'
own call, about an hour before tip) and the 1H total (nba_first_half_total_luck's). The 1Q total and every Q2-Q4 line
were bought the MORNING AFTER each game (odds_api_nba_period_close_history), which is a record, not a price anyone
can still take. Matt approved the credits on 2026-11-26 ("Yes to additional credits", ~128 a day quoted).

WHAT IT BUYS. Per NBA game, at most two per-event calls, at every line-shop book:
  * EARLY, once a game is within EARLY_LEAD of tip: all twelve PERIOD_MARKETS.
  * PRETIP, once within PRETIP_LEAD: the nine not already bought before tip by a model's own call
    (PRETIP_MARKETS = PERIOD_MARKETS minus spreads_q1, h2h_q1 and totals_h1).
A game first seen inside PRETIP_LEAD gets one call with all twelve, recorded as stage 'both'.
The per-event endpoint bills per market returned (measured on nba_first_quarter_odds: 2.00 credits a 2-market call
over 51 calls, 2026-11-18..25), so a game costs at most 12 + 9 = 21 credits.

WHAT IT MUST NOT TOUCH. Real-money models decide on these markets, so every row carries its own SOURCE and
snapshot_type 'open':
  * nba_q1_trend / nba_q1_trend_ml read odds WHERE source = their LIVE_SOURCE (scripts/nba_q1_trend_card._quote_rows);
  * nba_first_half_total_luck reads WHERE source = nba_first_half_odds.SOURCE;
  * their CLV reads 'close' rows only (tracking/paper_tracker._close_rows_only);
  * team_period_results grades on the newest pre-tip row, which stays the next-morning purchase at tip-5.
Never a 'close' row, never a model's source. tests/test_nba_period_lines_live.py pins all of it.

MAIN LINE. A book can quote several numbers for one period. Each (book, market) keeps one main number under the
market's own name, the rest under '<market>_alternate': only a two-sided number can be main, the one whose two prices
are closest to even, ties to the lower number (models/nba_book_numbers.split_main_rungs's rule, which accepts only
its own markets). Spreads are keyed on the HOME number (CLAUDE.md section 4): home at p pairs with away at -p.

THE LEDGER (nba_period_line_fetches, worker-only): one row per call, with its stage. A failed call is not a fetch
and the next pass tries again; a 200 with nothing quoted is a fetch.

    python run_pipeline.py --step nba-period-lines     # what the refresh pass runs
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from loguru import logger

from config import LINE_SHOP_BOOKMAKERS
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.ingestors import odds_quota
from data.ingestors.nba_odds_history import _ODDS_KEYS
from data.ingestors.nba_team_total_odds import EVENT_ODDS, EVENTS, SPORT, SPORT_KEY, _when, _z, event_ids
from data.ingestors.odds_ingestor import _get_event_odds, _insert_odds, _list_events
from data.ingestors.odds_quota import persist_quota

SOURCE = "odds_api_nba_period_lines_live"
PERIOD_MARKETS = ("spreads_h1", "totals_h1", "h2h_h1",
                  "spreads_q1", "totals_q1", "h2h_q1",
                  "spreads_q2", "totals_q2", "spreads_q3", "totals_q3", "spreads_q4", "totals_q4")
# Already bought before tip by a model's own call, so not bought again near tip.
MODEL_FETCHED = ("spreads_q1", "h2h_q1", "totals_h1")
PRETIP_MARKETS = tuple(m for m in PERIOD_MARKETS if m not in MODEL_FETCHED)
EARLY_LEAD = timedelta(hours=7)
PRETIP_LEAD = timedelta(minutes=75)
STAGES = ("early", "pretip", "both")
# Members bet at the line-shop books; the MCP shows its seven. betPARX is fetched, never named (config section 6).
READ_BOOKS = tuple(LINE_SHOP_BOOKMAKERS)

# ── the ledger ───────────────────────────────────────────────────────────────
LEDGER_TABLE = "nba_period_line_fetches"
LEDGER_COLS = ("requested_at", "fetch_at", "endpoint", "stage", "game_id", "event_id", "ok",
               "markets", "rows_stored", "main_rows", "books", "credits_last", "detail")
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS nba_period_line_fetches (
    requested_at  TIMESTAMPTZ NOT NULL,
    fetch_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint      TEXT NOT NULL,
    stage         TEXT,
    game_id       TEXT,
    event_id      TEXT,
    ok            BOOLEAN NOT NULL,
    markets       TEXT,
    rows_stored   INTEGER NOT NULL DEFAULT 0,
    main_rows     INTEGER NOT NULL DEFAULT 0,
    books         TEXT,
    credits_last  REAL,
    detail        TEXT
)
"""
_INSERT_LEDGER = (
    "INSERT INTO nba_period_line_fetches (requested_at, endpoint, stage, game_id, event_id, ok, markets, "
    "rows_stored, main_rows, books, credits_last, detail) VALUES (%(requested_at)s, %(endpoint)s, %(stage)s, "
    "%(game_id)s, %(event_id)s, %(ok)s, %(markets)s, %(rows_stored)s, %(main_rows)s, %(books)s, "
    "%(credits_last)s, %(detail)s)")


def ensure_ledger(conn) -> None:
    if schema_is_current(conn, LEDGER_TABLE, columns=LEDGER_COLS, rls=True, revoked_from=API_ROLES):
        return
    conn.execute(LEDGER_DDL)
    lock_down(conn, LEDGER_TABLE)
    conn.commit()


def _ledger_row(conn, requested_at: datetime, endpoint: str, *, stage: str | None = None,
                game_id: str | None = None, event_id: str | None = None, ok: bool, markets=(),
                rows_stored: int = 0, main_rows: int = 0, books=(), credits: float | None = None,
                detail: str | None = None) -> None:
    conn.execute(_INSERT_LEDGER, {
        "requested_at": requested_at, "endpoint": endpoint, "stage": stage, "game_id": game_id,
        "event_id": event_id, "ok": ok, "markets": ",".join(markets) or None, "rows_stored": rows_stored,
        "main_rows": main_rows, "books": ",".join(sorted(books)) or None, "credits_last": credits,
        "detail": (detail or None) and detail[:500]})


def stages_done(conn, game_ids: list[str]) -> dict[str, set[str]]:
    """{game_id: stages with an ok event call}. 'both' counts as early and pretip."""
    if not game_ids:
        return {}
    rows = conn.execute(
        f"SELECT game_id, stage FROM {LEDGER_TABLE} WHERE game_id = ANY(%s) AND endpoint = %s AND ok",
        (list(game_ids), EVENT_ODDS)).fetchall()
    out: dict[str, set[str]] = {}
    for gid, stage in rows:
        out.setdefault(gid, set()).update(("early", "pretip") if stage == "both" else (stage,))
    return out


# ── what is due ──────────────────────────────────────────────────────────────

def due(games: dict[str, datetime], done: dict[str, set[str]], now: datetime) -> dict[str, str]:
    """{game_id: stage} for games not yet started. EARLY inside EARLY_LEAD, PRETIP inside PRETIP_LEAD; a game
    that needs both at once gets one 'both' call."""
    out = {}
    for gid, tip in games.items():
        left = tip - now
        if left <= timedelta(0):
            continue
        have = done.get(gid, set())
        want_early = left <= EARLY_LEAD and "early" not in have
        want_pre = left <= PRETIP_LEAD and "pretip" not in have
        if want_early and want_pre:
            out[gid] = "both"
        elif want_pre:
            out[gid] = "pretip"
        elif want_early:
            out[gid] = "early"
    return out


def markets_for(stage: str) -> tuple[str, ...]:
    return PRETIP_MARKETS if stage == "pretip" else PERIOD_MARKETS


# ── parsing ──────────────────────────────────────────────────────────────────

def _implied(price) -> float | None:
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p >= 100:
        return 100.0 / (p + 100.0)
    if p <= -100:
        return -p / (-p + 100.0)
    return None


def book_rows(book_markets: list[dict], home_name: str, away_name: str) -> list[dict]:
    """One book's markets -> one odds-row dict per (market, number): spreads keyed on the HOME number, totals on
    the line, moneylines one pair. Only PERIOD_MARKETS; one-sided quotes kept (never main)."""
    out: list[dict] = []
    for m in book_markets:
        key = m.get("key")
        if key not in PERIOD_MARKETS:
            continue
        outs = m.get("outcomes") or []
        if key.startswith("h2h_"):
            row: dict = {}
            for o in outs:
                name = o.get("name") or ""
                if name == home_name:
                    row.update(home_price=o.get("price"), home_link=o.get("link"), home_sid=o.get("sid"))
                elif name == away_name:
                    row.update(away_price=o.get("price"), away_link=o.get("link"), away_sid=o.get("sid"))
            if row:
                out.append({"market": key, **row})
            continue
        slots: dict[float, dict] = {}
        for o in outs:
            name, pt = o.get("name") or "", o.get("point")
            if pt is None:
                continue
            if key.startswith("spreads_"):
                if name == home_name:
                    slots.setdefault(float(pt), {}).update(
                        home_price=o.get("price"), home_link=o.get("link"), home_sid=o.get("sid"))
                elif name == away_name:
                    slots.setdefault(-float(pt), {}).update(
                        away_price=o.get("price"), away_link=o.get("link"), away_sid=o.get("sid"))
            elif name in ("Over", "Under"):
                side = name.lower()
                slots.setdefault(float(pt), {}).update(
                    {f"{side}_price": o.get("price"), f"{side}_link": o.get("link"), f"{side}_sid": o.get("sid")})
        col = "spread_home" if key.startswith("spreads_") else "total_line"
        out += [{"market": key, col: pt, **s} for pt, s in sorted(slots.items())]
    return out


def split_main(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Per (book, market): one main number keeps the market name, the rest become '<market>_alternate'.
    Moneylines are always main. Main = two-sided, prices closest to even, ties to the lower number."""
    groups: dict[tuple, list[dict]] = {}
    main, alt = [], []
    for r in rows:
        if r["market"].startswith("h2h_"):
            main.append(r)
        else:
            groups.setdefault((r.get("bookmaker"), r["market"]), []).append(r)
    for (_, market), rs in groups.items():
        a, b = (("home_price", "away_price") if market.startswith("spreads_") else ("over_price", "under_price"))
        num = "spread_home" if market.startswith("spreads_") else "total_line"

        def gap(r):
            pa, pb = _implied(r.get(a)), _implied(r.get(b))
            return None if pa is None or pb is None else abs(pa - pb)
        two_sided = [r for r in rs if gap(r) is not None]
        pick = min(two_sided, key=lambda r: (gap(r), float(r[num]))) if two_sided else None
        for r in rs:
            if r is pick:
                main.append(r)
            else:
                alt.append({**r, "market": f"{market}_alternate"})
    return main, alt


def event_rows(body: dict | None, game_id: str, fetched_at: datetime) -> tuple[list[dict], list[dict]]:
    """One event response -> (main rows, alternate rows), every odds column, snapshot_type 'open', SOURCE."""
    body = body or {}
    home_name, away_name = body.get("home_team") or "", body.get("away_team") or ""
    rows: list[dict] = []
    for book in body.get("bookmakers") or []:
        key = book.get("key")
        if key not in READ_BOOKS:
            continue
        markets = book.get("markets") or []
        stamps = {m.get("key"): m.get("last_update") for m in markets}
        for p in book_rows(markets, home_name, away_name):
            row = dict.fromkeys(_ODDS_KEYS)
            row.update(p)
            row.update({"game_id": game_id, "sport": SPORT, "bookmaker": key, "snapshot_type": "open",
                        "snapshot_at": stamps.get(p["market"]) or book.get("last_update") or _z(fetched_at),
                        "source": SOURCE})
            rows.append(row)
    return split_main(rows)


# ── the run ──────────────────────────────────────────────────────────────────

def _upcoming(conn, now: datetime) -> dict[str, datetime]:
    rows = conn.execute(
        "SELECT game_id, home_team, away_team, commence_time FROM games WHERE sport = %s "
        "AND commence_time IS NOT NULL AND commence_time <> '' "
        "AND commence_time::timestamptz > %s AND commence_time::timestamptz <= %s",
        (SPORT, now, now + EARLY_LEAD)).fetchall()
    out = {}
    for gid, _h, _a, ct in rows:
        t = ct if isinstance(ct, datetime) else _when(ct)
        if t is not None:
            out[gid] = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    return out


def _billed(before: dict | None) -> float | None:
    after = odds_quota.latest()
    if after is None or after is before:
        return None
    return after.get("last")


def run(conn=None, now: datetime | None = None) -> dict:
    """Buy whatever is due this pass. -> a summary; `failed` names games whose call failed."""
    from data.ingestors.odds_quota import plan_credit_budget
    import config
    now = now or datetime.now(timezone.utc)
    out = {"due": {}, "fetched": [], "failed": [], "rows": 0, "credits": {}}
    if not config.ODDS_API_KEY:
        out["skipped"] = "no ODDS_API_KEY"
        return out
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    try:
        ensure_ledger(conn)
        games = _upcoming(conn, now)
        todo = due(games, stages_done(conn, list(games)), now)
        out["due"] = todo
        conn.rollback()          # no transaction across a call: created_at must be the fetch instant
        if not todo:
            return out
        planned = sum(len(markets_for(s)) for s in todo.values())
        _, problems = plan_credit_budget(conn, shard_calls=1, total_calls=1, credits_per_call=planned)
        if problems:
            out["skipped"] = problems
            logger.warning(f"NBA period lines: not started: {problems}")
            return out
        asked = datetime.now(timezone.utc)
        before = odds_quota.latest()
        try:
            events, why = _list_events(SPORT_KEY), None
        except Exception as exc:  # noqa: BLE001 - recorded, every game fails below
            events, why = [], f"event list failed: {exc!r}"
        _ledger_row(conn, asked, EVENTS, ok=why is None, rows_stored=len(events),
                    credits=_billed(before), detail=why or f"{len(events)} events listed")
        conn.commit()
        teams = {gid: {} for gid in todo}
        for gid, home, away in conn.execute(
                "SELECT game_id, home_team, away_team FROM games WHERE game_id = ANY(%s)", (list(todo),)).fetchall():
            teams[gid] = {"home": home, "away": away}
        conn.rollback()
        by_game = event_ids(events, teams)
        for gid, stage in sorted(todo.items()):
            markets = markets_for(stage)
            ev = by_game.get(gid)
            asked = datetime.now(timezone.utc)
            if ev is None:
                _ledger_row(conn, asked, EVENT_ODDS, stage=stage, game_id=gid, ok=False, markets=markets,
                            detail=why or "not in the feed's event list")
                conn.commit()
                out["failed"].append(gid)
                continue
            before = odds_quota.latest()
            try:
                body = _get_event_odds(SPORT_KEY, ev, list(markets))
            except Exception as exc:  # noqa: BLE001 - one game's failure is its own
                _ledger_row(conn, asked, EVENT_ODDS, stage=stage, game_id=gid, event_id=ev, ok=False,
                            markets=markets, credits=_billed(before), detail=f"call failed: {exc!r}")
                conn.commit()
                out["failed"].append(gid)
                continue
            credits = _billed(before)
            out["credits"][gid] = credits
            if body is None:
                _ledger_row(conn, asked, EVENT_ODDS, stage=stage, game_id=gid, event_id=ev, ok=False,
                            markets=markets, credits=credits, detail="HTTP 404 or 422: no body")
                conn.commit()
                out["failed"].append(gid)
                continue
            main, alt = event_rows(body, gid, datetime.now(timezone.utc))
            rows = main + alt
            try:
                if rows:
                    _insert_odds(conn, rows)
                _ledger_row(conn, asked, EVENT_ODDS, stage=stage, game_id=gid, event_id=ev, ok=True,
                            markets=markets, rows_stored=len(rows), main_rows=len(main),
                            books={r["bookmaker"] for r in rows}, credits=credits)
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                _ledger_row(conn, asked, EVENT_ODDS, stage=stage, game_id=gid, event_id=ev, ok=False,
                            markets=markets, credits=credits, detail=f"store failed: {exc!r}")
                conn.commit()
                out["failed"].append(gid)
                continue
            out["fetched"].append(gid)
            out["rows"] += len(rows)
            logger.info(f"  {gid}: {stage} period lines, {len(main)} main + {len(alt)} alternate rows, "
                        f"x-requests-last {credits}")
        return out
    finally:
        try:
            persist_quota(conn)
        finally:
            if own:
                conn.close()

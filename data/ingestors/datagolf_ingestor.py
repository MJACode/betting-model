"""
DataGolf ingestor — the single data source for GOLF (PGA Tour).

One API key (Scratch Plus) unlocks everything golf needs:
  • /get-player-list                    → golf_players (dg_id ↔ name ↔ slug)
  • /historical-raw-data/event-list     → the event catalog (id, date, name)
  • /historical-raw-data/rounds         → round-level scoring + strokes gained
  • /field-updates                      → the current week's field + tee times
  • /betting-tools/outrights            → LIVE DraftKings odds (win/top_N/make_cut)
  • /betting-tools/matchups             → LIVE DraftKings tournament matchup odds

Each tournament maps to ONE `games` row (game_id = GOLF_{start_date}_{event_slug},
home_team = event name, away_team = 'FIELD', scores stay NULL). Per-player picks FK
to that row and carry picks.player_id = str(dg_id). Round-level results land in
`golf_rounds`; live DK odds snapshots land in `golf_odds`.

────────────────────────────────────────────────────────────────────────────────
ASSUMED RESPONSE SHAPES — verify with scripts/verify_datagolf.py before trusting.
All parsers are pure and tolerant (.get with fallbacks) so a field-name correction
is a one-line change here, not a pipeline rewrite. Names below are DataGolf's
documented fields as of 2026-06; confirm against a real key.

  player-list rows : {dg_id, player_name "Last, First", country, amateur}
  event-list rows  : {event_id, calendar_year, date "YYYY-MM-DD", event_name, tour}
  rounds payload   : {event_id, event_name, year, scores: [
                       {dg_id, player_name, fin_text "T10"/"CUT"/"WD",
                        round_1: {score, sg_ott, sg_app, sg_arg, sg_putt, sg_t2g,
                                  sg_total, course_num, driving_dist, driving_acc,
                                  gir, scrambling}, round_2: {...}, ...}]}
  field-updates    : {event_name, current_round, event_id?, field: [{dg_id, player_name}]}
  outrights payload: {event_name, market, odds: [
                       {dg_id, player_name, datagolf: {baseline, baseline_history_fit},
                        draftkings "+450", fanduel, ...}]}
  matchups payload : {event_name, market, match_list: [
                       {p1_dg_id, p1_player_name, p2_dg_id, p2_player_name,
                        p3_dg_id?, ties, draftkings: {p1, p2, tie}, datagolf: {p1,p2,tie}}]}
────────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import argparse
import sqlite3  # noqa: F401  (lazy-annotation parity with sibling ingestors on py3.12)
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from loguru import logger

import config
from data.db import get_connection, DBConnection

DG_BASE = config.DATAGOLF_BASE_URL
DG_KEY = config.DATAGOLF_API_KEY

# Outright markets we ingest (DataGolf market keys). top_5/frl are collected for
# context even though only win/top_10/top_20/make_cut have models.
OUTRIGHT_MARKETS = ["win", "top_5", "top_10", "top_20", "make_cut"]

# Polite pause between historical API calls during backfill.
_BACKFILL_SLEEP_SEC = 0.4


# ══════════════════════════════════════════════════════════════════════════════
# Pure helpers (fixture-testable — no network, no DB)
# ══════════════════════════════════════════════════════════════════════════════

def normalize_dg_name(name: str) -> str:
    """
    DataGolf sends names as "Last, First" (e.g. "Scheffler, Scottie").
    Convert to display order "First Last". Names already in display order, single
    names, and trailing suffixes ("McIlroy, Rory" / "Jr.") are handled.
    """
    if not name:
        return ""
    name = name.strip()
    if "," in name:
        parts = [p.strip() for p in name.split(",")]
        if len(parts) == 2 and parts[1]:
            # "Last, First" → "First Last" ("Woods, Tiger" → "Tiger Woods")
            return f"{parts[1]} {parts[0]}".strip()
    return name


def slugify_golfer(name: str) -> str:
    """Lowercase, strip accents/punctuation, collapse to hyphens. Matches odds
    names to stats names (the UFC slugify_fighter analog)."""
    if not name:
        return ""
    name = normalize_dg_name(name)
    # strip accents
    name = "".join(
        c for c in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(c)
    )
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-")


def event_slug(event_name: str) -> str:
    """Slug for the tournament half of a game_id. Drops 'the ' prefixes and
    common noise so the same event slugs identically year to year."""
    if not event_name:
        return "event"
    name = event_name.lower().strip()
    name = re.sub(r"^the\s+", "", name)
    name = "".join(
        c for c in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(c)
    )
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-") or "event"


def build_game_id(start_date: str, event_name: str) -> str:
    """GOLF_{YYYY-MM-DD}_{event_slug}."""
    return f"GOLF_{start_date}_{event_slug(event_name)}"


def is_team_event(event_name: str) -> bool:
    """Team formats (Zurich Classic etc.) have no individual finish — exclude."""
    if not event_name:
        return False
    low = event_name.lower()
    return any(marker in low for marker in config.GOLF_TEAM_EVENT_MARKERS)


_CUT_TOKENS = {"cut", "mc", "missed cut", "missedcut"}
_VOID_TOKENS = {"wd", "w/d", "dq", "dsq", "dns", "wdn", "ret"}


def parse_finish(fin_text) -> tuple[int | None, int | None]:
    """
    Map a DataGolf fin_text to (finish_pos, made_cut_hint).

      "1" / "T10"      → (10, 1)   numeric finish, made the cut
      "CUT" / "MC"     → (None, 0) missed the cut
      "WD"/"DQ"/"DNS"  → (None, None)  ambiguous — caller refines from rounds played
      blank/unknown    → (None, None)

    made_cut_hint is a hint only — parse_event_rounds refines WD/DQ rows using the
    actual number of rounds the player completed (3+ rounds ⇒ they made the cut).
    """
    if fin_text is None:
        return None, None
    s = str(fin_text).strip().lower()
    if not s:
        return None, None
    if s in _CUT_TOKENS:
        return None, 0
    if s in _VOID_TOKENS:
        return None, None
    # strip a leading 'T' (tie) then any non-digits
    digits = re.sub(r"[^0-9]", "", s)
    if digits:
        return int(digits), 1
    return None, None


_ROUND_KEYS = [f"round_{i}" for i in range(1, 6)]  # support up to 5 (rare)


def _num(v):
    """Coerce to float, tolerating strings / None / empty."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _american(v):
    """Coerce an American-odds value ('+450', '-130', 450) to float. None when
    the book doesn't price this selection."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("+", "")
    try:
        return float(s)
    except ValueError:
        return None


# ── Parsers: raw JSON → list[dict] ────────────────────────────────────────────

def parse_player_list(raw) -> list[dict]:
    rows = raw.get("players", raw) if isinstance(raw, dict) else raw
    out = []
    for p in rows or []:
        dg_id = p.get("dg_id")
        if dg_id is None:
            continue
        name = normalize_dg_name(p.get("player_name", ""))
        out.append({
            "dg_id":       int(dg_id),
            "player_name": name,
            "slug":        slugify_golfer(name),
            "country":     p.get("country") or p.get("country_code"),
            "amateur":     int(p.get("amateur") or 0),
        })
    return out


def parse_event_list(raw, tour: str = "pga") -> list[dict]:
    rows = raw.get("events", raw) if isinstance(raw, dict) else raw
    out = []
    for e in rows or []:
        eid = e.get("event_id")
        season = e.get("calendar_year") or e.get("year") or e.get("season")
        if eid is None or season is None:
            continue
        if (e.get("tour") or tour) != tour:
            continue
        name = e.get("event_name", "")
        if is_team_event(name):
            continue
        out.append({
            "dg_event_id": int(eid),
            "season":      int(season),
            "event_name":  name,
            "start_date":  e.get("date") or e.get("start_date"),
            "tour":        e.get("tour") or tour,
        })
    return out


def parse_event_rounds(raw, dg_event_id: int, season: int,
                       game_id: str, start_date: str) -> list[dict]:
    """
    Reshape a /historical-raw-data/rounds payload into one row per player per
    round, with the event-level finish (finish_pos / finish_text / made_cut)
    duplicated on each of that player's rows.
    """
    scores = raw.get("scores", []) if isinstance(raw, dict) else (raw or [])
    out = []
    for sc in scores:
        dg_id = sc.get("dg_id")
        if dg_id is None:
            continue
        name = normalize_dg_name(sc.get("player_name", ""))
        fin_text = sc.get("fin_text") or sc.get("finish")
        pos, made_cut = parse_finish(fin_text)

        # gather present rounds
        round_objs = []
        for rk in _ROUND_KEYS:
            ro = sc.get(rk)
            if isinstance(ro, dict) and (ro.get("score") is not None or ro.get("sg_total") is not None):
                round_objs.append((int(rk.split("_")[1]), ro))

        rounds_played = len(round_objs)
        # Refine ambiguous WD/DQ: 3+ completed rounds ⇒ player did make the cut.
        if made_cut is None and pos is None:
            if rounds_played >= 3:
                made_cut = 1
            elif rounds_played > 0 and str(fin_text or "").strip().lower() in _VOID_TOKENS:
                made_cut = None  # withdrew early — settlement voids make_cut picks

        for rnum, ro in round_objs:
            out.append({
                "dg_id":       int(dg_id),
                "player_name": name,
                "game_id":     game_id,
                "dg_event_id": int(dg_event_id),
                "season":      int(season),
                "game_date":   start_date,
                "round_num":   rnum,
                "course_num":  ro.get("course_num"),
                "score":       ro.get("score"),
                "sg_ott":      _num(ro.get("sg_ott")),
                "sg_app":      _num(ro.get("sg_app")),
                "sg_arg":      _num(ro.get("sg_arg")),
                "sg_putt":     _num(ro.get("sg_putt")),
                "sg_t2g":      _num(ro.get("sg_t2g")),
                "sg_total":    _num(ro.get("sg_total")),
                "driving_dist": _num(ro.get("driving_dist")),
                "driving_acc":  _num(ro.get("driving_acc")),
                "gir":          _num(ro.get("gir")),
                "scrambling":   _num(ro.get("scrambling")),
                "finish_pos":  pos,
                "finish_text": fin_text,
                "made_cut":    made_cut,
            })
    return out


# DataGolf /field-updates carries per-player round-1 tee times. The exact field
# name is PROVISIONAL — we try a few candidates so this is a one-line fix if it
# differs from what the live feed returns.
_TEE_TIME_KEYS = ("r1_teetime", "teetime", "tee_time", "start_time")
# Most PGA Tour events run on US Eastern; a clock-only tee time is localized here
# before being stored as a proper UTC ISO. International events (e.g. The Open)
# may be off by their offset — acceptable v1; the tournament date is unaffected.
_GOLF_TZ = ZoneInfo("America/New_York")


def _tee_time_to_utc(raw, start_date: str):
    """
    Best-effort parse of a DataGolf tee time → tz-aware UTC datetime, or None.
    Handles full ISO datetimes (used as-is; naive → assumed ET) and clock-only
    strings ('7:50am', '07:50', '1:20 PM') combined with the tournament date.
    """
    if not raw:
        return None
    s = str(raw).strip()
    try:                                            # full ISO datetime
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_GOLF_TZ)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    try:
        d = datetime.fromisoformat(start_date).date()
    except (ValueError, TypeError):
        return None
    clk = s.upper().replace(" ", "")                # clock-only ('7:50AM' / '07:50')
    for fmt in ("%I:%M%p", "%H:%M"):
        try:
            t = datetime.strptime(clk, fmt).time()
        except ValueError:
            continue
        return datetime.combine(d, t, tzinfo=_GOLF_TZ).astimezone(timezone.utc)
    return None


def _earliest_commence_iso(teetimes, start_date: str) -> str | None:
    """Earliest round-1 tee time across the field as a UTC ISO string, or None."""
    dts = [dt for raw in teetimes if (dt := _tee_time_to_utc(raw, start_date))]
    return min(dts).isoformat() if dts else None


def parse_field_update(raw) -> dict:
    """{event_name, current_round, dg_event_id?, players: [...], r1_teetimes: [...]}."""
    field = raw.get("field", []) if isinstance(raw, dict) else []
    players = []
    r1_teetimes = []
    for p in field:
        dg_id = p.get("dg_id")
        if dg_id is None:
            continue
        players.append({
            "dg_id":       int(dg_id),
            "player_name": normalize_dg_name(p.get("player_name", "")),
        })
        for k in _TEE_TIME_KEYS:                     # first matching key wins
            v = p.get(k)
            if v:
                r1_teetimes.append(str(v).strip())
                break
    return {
        "event_name":   raw.get("event_name", "") if isinstance(raw, dict) else "",
        "current_round": raw.get("current_round") if isinstance(raw, dict) else None,
        "dg_event_id":  raw.get("event_id") if isinstance(raw, dict) else None,
        "players":      players,
        "r1_teetimes":  r1_teetimes,
    }


def parse_outright_odds(raw, market: str, book: str = "draftkings") -> list[dict]:
    """Extract the chosen book's price + DataGolf's model prob per player. Players
    the book doesn't price (price None) are still emitted (datagolf_prob may exist)."""
    odds = raw.get("odds", []) if isinstance(raw, dict) else []
    out = []
    for o in odds:
        dg_id = o.get("dg_id")
        if dg_id is None:
            continue
        dg = o.get("datagolf") or {}
        dg_prob = dg.get("baseline_history_fit")
        if dg_prob is None:
            dg_prob = dg.get("baseline")
        out.append({
            "dg_id":         int(dg_id),
            "player_name":   normalize_dg_name(o.get("player_name", "")),
            "market":        market,
            "price":         _american(o.get(book)),
            "datagolf_prob": _num(dg_prob),
        })
    return out


def parse_matchup_odds(raw, book: str = "draftkings") -> list[dict]:
    """
    Tournament matchups → one row per (favorite-agnostic) pair. We store p1 as the
    'player' and p2 as the opponent with both American prices. 3-balls (p3 present)
    are skipped v1. A "no matchups" string match_list yields [].
    """
    match_list = raw.get("match_list") if isinstance(raw, dict) else None
    if not isinstance(match_list, list):
        return []
    out = []
    for m in match_list:
        if m.get("p3_dg_id") is not None or m.get("p3_player_name"):
            continue  # skip 3-balls v1
        p1, p2 = m.get("p1_dg_id"), m.get("p2_dg_id")
        if p1 is None or p2 is None:
            continue
        bk = m.get(book) or {}
        dg = m.get("datagolf") or {}
        out.append({
            "dg_id":           int(p1),
            "player_name":     normalize_dg_name(m.get("p1_player_name", "")),
            "opp_dg_id":       int(p2),
            "opp_player_name": normalize_dg_name(m.get("p2_player_name", "")),
            "market":          "matchup_tournament",
            "price":           _american(bk.get("p1")),
            "opp_price":       _american(bk.get("p2")),
            "datagolf_prob":   _num(dg.get("p1")),
            "ties":            m.get("ties"),
        })
    return out


# ══════════════════════════════════════════════════════════════════════════════
# I/O
# ══════════════════════════════════════════════════════════════════════════════

def _dg_get(path: str, **params):
    """GET feeds.datagolf.com/{path} with the API key + json file_format."""
    if not DG_KEY:
        raise RuntimeError("DATAGOLF_API_KEY is not set — cannot call DataGolf.")
    params.setdefault("file_format", "json")
    params["key"] = DG_KEY
    url = f"{DG_BASE}/{path.lstrip('/')}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_games_tournament(conn: DBConnection, *, game_id: str, season: int,
                             start_date: str, end_date: str | None,
                             event_name: str, dg_event_id: int, tour: str,
                             course_name: str | None, field_size: int | None,
                             has_cut: int, status: str,
                             commence_time: str | None = None) -> None:
    """Idempotently create/update the one games row + golf_tournaments row.

    commence_time is the earliest round-1 tee time (UTC ISO) when available,
    falling back to the tournament start_date (date-only). game_date stays the
    start_date — only commence_time carries the precise start.
    """
    commence_time = commence_time or start_date
    conn.execute("""
        INSERT INTO games (game_id, sport, season, game_date, home_team, away_team,
                           data_source, commence_time)
        VALUES (%(gid)s, 'GOLF', %(season)s, %(date)s, %(event)s, 'FIELD',
                'datagolf', %(commence)s)
        ON CONFLICT (game_id) DO UPDATE SET
            home_team = EXCLUDED.home_team,
            commence_time = EXCLUDED.commence_time,
            updated_at = NOW()::TEXT
    """, {"gid": game_id, "season": season, "date": start_date,
          "event": event_name, "commence": commence_time})

    conn.execute("""
        INSERT INTO golf_tournaments (game_id, tour, dg_event_id, season, event_name,
                                      course_name, start_date, end_date, field_size,
                                      has_cut, status)
        VALUES (%(gid)s, %(tour)s, %(eid)s, %(season)s, %(event)s,
                %(course)s, %(start)s, %(end)s, %(fsize)s, %(cut)s, %(status)s)
        ON CONFLICT (dg_event_id, season) DO UPDATE SET
            field_size = COALESCE(EXCLUDED.field_size, golf_tournaments.field_size),
            course_name = COALESCE(EXCLUDED.course_name, golf_tournaments.course_name),
            status = EXCLUDED.status
    """, {"gid": game_id, "tour": tour, "eid": dg_event_id, "season": season,
          "event": event_name, "course": course_name, "start": start_date,
          "end": end_date, "fsize": field_size, "cut": has_cut, "status": status})


def _insert_rounds(conn: DBConnection, rows: list[dict]) -> int:
    """Upsert round rows (idempotent on the natural key)."""
    if not rows:
        return 0
    sql = """
        INSERT INTO golf_rounds (
            dg_id, player_name, game_id, dg_event_id, season, game_date,
            round_num, course_num, score,
            sg_ott, sg_app, sg_arg, sg_putt, sg_t2g, sg_total,
            driving_dist, driving_acc, gir, scrambling,
            finish_pos, finish_text, made_cut
        ) VALUES (
            %(dg_id)s, %(player_name)s, %(game_id)s, %(dg_event_id)s, %(season)s, %(game_date)s,
            %(round_num)s, %(course_num)s, %(score)s,
            %(sg_ott)s, %(sg_app)s, %(sg_arg)s, %(sg_putt)s, %(sg_t2g)s, %(sg_total)s,
            %(driving_dist)s, %(driving_acc)s, %(gir)s, %(scrambling)s,
            %(finish_pos)s, %(finish_text)s, %(made_cut)s
        )
        ON CONFLICT (dg_id, dg_event_id, season, round_num) DO UPDATE SET
            score = EXCLUDED.score, sg_total = EXCLUDED.sg_total,
            finish_pos = EXCLUDED.finish_pos, finish_text = EXCLUDED.finish_text,
            made_cut = EXCLUDED.made_cut
    """
    conn.executemany(sql, rows)
    return len(rows)


def _insert_golf_odds(conn: DBConnection, rows: list[dict]) -> int:
    """Append odds snapshots (no dedup — history is the point)."""
    if not rows:
        return 0
    sql = """
        INSERT INTO golf_odds (
            game_id, game_date, dg_id, player_name, market,
            bookmaker, snapshot_type, snapshot_at, price, datagolf_prob,
            opp_dg_id, opp_player_name, opp_price
        ) VALUES (
            %(game_id)s, %(game_date)s, %(dg_id)s, %(player_name)s, %(market)s,
            'draftkings', %(snapshot_type)s, %(snapshot_at)s, %(price)s, %(datagolf_prob)s,
            %(opp_dg_id)s, %(opp_player_name)s, %(opp_price)s
        )
    """
    conn.executemany(sql, rows)
    return len(rows)


def _upsert_players(conn: DBConnection, rows: list[dict]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO golf_players (dg_id, player_name, slug, country, amateur, updated_at)
        VALUES (%(dg_id)s, %(player_name)s, %(slug)s, %(country)s, %(amateur)s, NOW()::TEXT)
        ON CONFLICT (dg_id) DO UPDATE SET
            player_name = EXCLUDED.player_name, slug = EXCLUDED.slug,
            country = EXCLUDED.country, amateur = EXCLUDED.amateur, updated_at = NOW()::TEXT
    """
    conn.executemany(sql, rows)
    return len(rows)


# ── Entry points ──────────────────────────────────────────────────────────────

def ingest_player_list(conn: DBConnection | None = None) -> int:
    """Refresh golf_players from /get-player-list."""
    own = conn is None
    conn = conn or get_connection()
    try:
        raw = _dg_get("get-player-list")
        rows = parse_player_list(raw)
        n = _upsert_players(conn, rows)
        if own:
            conn.commit()
        logger.info(f"golf player list: {n} players")
        return n
    finally:
        if own:
            conn.close()


def _event_meta_lookup(conn: DBConnection):
    """All (dg_event_id, season) already fully ingested (used to skip in backfill)."""
    done = conn.execute(
        "SELECT DISTINCT dg_event_id, season FROM golf_rounds"
    ).fetchall()
    return {(int(r[0]), int(r[1])) for r in done}


def backfill_golf_rounds(start_year: int, end_year: int, force: bool = False) -> int:
    """
    Walk the event-list and pull round-level scoring for every PGA event in the
    range. Idempotent — skips (event, year) pairs already present unless force.
    """
    conn = get_connection()
    total = 0
    try:
        ingest_player_list(conn)
        raw_events = _dg_get("historical-raw-data/event-list")
        events = parse_event_list(raw_events)
        events = [e for e in events if start_year <= e["season"] <= end_year]
        done = set() if force else _event_meta_lookup(conn)
        logger.info(f"golf backfill: {len(events)} events {start_year}-{end_year}")

        for e in events:
            key = (e["dg_event_id"], e["season"])
            if key in done:
                continue
            start_date = e["start_date"]
            if not start_date:
                logger.warning(f"  skip {e['event_name']} {e['season']} — no date")
                continue
            game_id = build_game_id(start_date, e["event_name"])
            try:
                raw = _dg_get("historical-raw-data/rounds",
                              tour=e["tour"], event_id=e["dg_event_id"], year=e["season"])
            except requests.HTTPError as exc:
                logger.warning(f"  {e['event_name']} {e['season']}: {exc}")
                continue
            rows = parse_event_rounds(raw, e["dg_event_id"], e["season"], game_id, start_date)
            if not rows:
                continue
            field_size = len({r["dg_id"] for r in rows})
            has_cut = 1 if any(r["made_cut"] == 0 for r in rows) else 0
            _upsert_games_tournament(
                conn, game_id=game_id, season=e["season"], start_date=start_date,
                end_date=None, event_name=e["event_name"], dg_event_id=e["dg_event_id"],
                tour=e["tour"], course_name=raw.get("course_name") if isinstance(raw, dict) else None,
                field_size=field_size, has_cut=has_cut, status="completed")
            n = _insert_rounds(conn, rows)
            total += n
            conn.commit()
            logger.info(f"  {e['season']} {e['event_name']}: {n} round rows ({field_size} players)")
            time.sleep(_BACKFILL_SLEEP_SEC)
        logger.success(f"golf backfill complete: {total} round rows")
        return total
    finally:
        conn.close()


def ingest_golf_field(run_date: str | None = None, conn: DBConnection | None = None) -> int:
    """
    Create/refresh the upcoming tournament's games + golf_tournaments rows from
    /field-updates (+ /get-schedule for the date/course). No-op when no PGA event
    is in the field. Returns the field size.
    """
    own = conn is None
    conn = conn or get_connection()
    try:
        raw = _dg_get("field-updates", tour="pga")
        fu = parse_field_update(raw)
        if not fu["event_name"] or not fu["players"]:
            logger.info("golf field: no active PGA event")
            return 0
        if is_team_event(fu["event_name"]):
            logger.info(f"golf field: {fu['event_name']} is a team event — skipping")
            return 0

        sched = _resolve_schedule_event(fu["event_name"], fu.get("dg_event_id"))
        if not sched:
            logger.warning(f"golf field: could not resolve schedule for '{fu['event_name']}'")
            return 0
        game_id = build_game_id(sched["start_date"], fu["event_name"])
        # earliest round-1 tee time → precise commence_time (falls back to date)
        commence_time = _earliest_commence_iso(
            fu.get("r1_teetimes", []), sched["start_date"])
        _upsert_games_tournament(
            conn, game_id=game_id, season=sched["season"], start_date=sched["start_date"],
            end_date=sched.get("end_date"), event_name=fu["event_name"],
            dg_event_id=sched["dg_event_id"], tour="pga", course_name=sched.get("course_name"),
            field_size=len(fu["players"]), has_cut=sched.get("has_cut", 1),
            status="scheduled", commence_time=commence_time)
        # keep the player registry fresh for these names
        _upsert_players(conn, [{
            "dg_id": p["dg_id"], "player_name": p["player_name"],
            "slug": slugify_golfer(p["player_name"]), "country": None, "amateur": 0,
        } for p in fu["players"]])
        if own:
            conn.commit()
        logger.info(f"golf field: {fu['event_name']} — {len(fu['players'])} players")
        return len(fu["players"])
    finally:
        if own:
            conn.close()


def _resolve_schedule_event(event_name: str, dg_event_id: int | None) -> dict | None:
    """Resolve start_date/season/event_id for the named event from /get-schedule.
    Falls back to today's date when the schedule can't be read (field still ingests)."""
    try:
        raw = _dg_get("get-schedule", tour="pga")
    except requests.HTTPError:
        raw = None
    rows = (raw.get("schedule", raw) if isinstance(raw, dict) else raw) or []
    target = event_name.lower().strip()
    for ev in rows:
        if str(ev.get("event_name", "")).lower().strip() == target or (
            dg_event_id is not None and ev.get("event_id") == dg_event_id):
            start = ev.get("start_date") or ev.get("date")
            if not start:
                continue
            season = int(ev.get("calendar_year") or ev.get("year") or start[:4])
            return {
                "dg_event_id": int(ev.get("event_id") or dg_event_id or 0),
                "season":      season,
                "start_date":  start,
                "end_date":    ev.get("end_date"),
                "course_name": ev.get("course") or ev.get("course_name"),
                "has_cut":     1,
            }
    # Fallback: no schedule match — anchor on today so picks still surface.
    if dg_event_id is not None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {"dg_event_id": int(dg_event_id), "season": int(today[:4]),
                "start_date": today, "end_date": None, "course_name": None, "has_cut": 1}
    return None


def ingest_golf_results(run_date: str | None = None, lookback_days: int = 10) -> int:
    """
    Pull round-level results for any tournament whose start_date is within the
    trailing window and that isn't yet marked completed. Self-healing — a Monday
    run finishes Sunday's event; a missed day is caught the next day. Runs before
    settlement.
    """
    conn = get_connection()
    total = 0
    try:
        run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cutoff = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=lookback_days)
                  ).strftime("%Y-%m-%d")
        pending = conn.execute("""
            SELECT game_id, dg_event_id, season, event_name, start_date, tour
            FROM golf_tournaments
            WHERE start_date >= %s AND start_date <= %s
              AND COALESCE(status, '') <> 'completed'
        """, (cutoff, run_date)).fetchall()
        for game_id, dg_event_id, season, event_name, start_date, tour in pending:
            try:
                raw = _dg_get("historical-raw-data/rounds",
                              tour=tour or "pga", event_id=dg_event_id, year=season)
            except requests.HTTPError as exc:
                logger.warning(f"  results {event_name} {season}: {exc}")
                continue
            rows = parse_event_rounds(raw, dg_event_id, season, game_id, start_date)
            if not rows:
                continue
            n = _insert_rounds(conn, rows)
            total += n
            # mark completed once final-round finish positions are present
            has_finish = any(r["finish_pos"] is not None for r in rows)
            max_round = max((r["round_num"] for r in rows), default=0)
            if has_finish and max_round >= 3:
                conn.execute(
                    "UPDATE golf_tournaments SET status = 'completed' WHERE game_id = %s",
                    (game_id,))
            conn.commit()
            logger.info(f"  results {season} {event_name}: {n} round rows")
        if total == 0:
            logger.info("golf results: nothing to settle in window")
        return total
    finally:
        conn.close()


def ingest_golf_odds(snapshot_type: str = "live", include_matchups: bool = False,
                     conn: DBConnection | None = None) -> int:
    """
    Snapshot live DK odds for the current event across the outright markets
    (and tournament matchups when include_matchups). Maps the odds onto the
    tournament's games row via the matching golf_tournaments entry. No-op off-weeks.
    """
    own = conn is None
    conn = conn or get_connection()
    snap_at = _now_iso()
    total = 0
    try:
        # Identify the active/upcoming tournament games row (the soonest scheduled).
        row = conn.execute("""
            SELECT game_id, game_date, event_name FROM golf_tournaments
            WHERE COALESCE(status,'') <> 'completed'
            ORDER BY start_date ASC LIMIT 1
        """).fetchone()
        if not row:
            logger.info("golf odds: no scheduled tournament")
            return 0
        game_id, game_date, event_name = row[0], row[1], row[2]

        for market in OUTRIGHT_MARKETS:
            try:
                raw = _dg_get("betting-tools/outrights", tour="pga",
                              market=market, odds_format="american")
            except requests.HTTPError as exc:
                logger.warning(f"  odds {market}: {exc}")
                continue
            parsed = parse_outright_odds(raw, market)
            rows = [{
                "game_id": game_id, "game_date": game_date,
                "dg_id": r["dg_id"], "player_name": r["player_name"],
                "market": market, "snapshot_type": snapshot_type, "snapshot_at": snap_at,
                "price": r["price"], "datagolf_prob": r["datagolf_prob"],
                "opp_dg_id": None, "opp_player_name": None, "opp_price": None,
            } for r in parsed]
            total += _insert_golf_odds(conn, rows)

        if include_matchups:
            try:
                raw = _dg_get("betting-tools/matchups", tour="pga",
                              market="tournament_matchups", odds_format="american")
                parsed = parse_matchup_odds(raw)
                rows = [{
                    "game_id": game_id, "game_date": game_date,
                    "dg_id": r["dg_id"], "player_name": r["player_name"],
                    "market": r["market"], "snapshot_type": snapshot_type, "snapshot_at": snap_at,
                    "price": r["price"], "datagolf_prob": r["datagolf_prob"],
                    "opp_dg_id": r["opp_dg_id"], "opp_player_name": r["opp_player_name"],
                    "opp_price": r["opp_price"],
                } for r in parsed]
                total += _insert_golf_odds(conn, rows)
            except requests.HTTPError as exc:
                logger.warning(f"  matchups: {exc}")

        if own:
            conn.commit()
        logger.info(f"golf odds: {total} snapshots for {event_name}")
        return total
    finally:
        if own:
            conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="DataGolf ingestor (GOLF / PGA Tour)")
    ap.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                    help="Backfill round-level history for the year range")
    ap.add_argument("--force", action="store_true", help="Re-ingest events already present")
    ap.add_argument("--players", action="store_true", help="Refresh the player list only")
    ap.add_argument("--field", action="store_true", help="Ingest the current week's field")
    ap.add_argument("--results", action="store_true", help="Ingest recent completed results")
    ap.add_argument("--odds", action="store_true", help="Snapshot live DK outright odds")
    ap.add_argument("--matchups", action="store_true", help="Include matchup odds with --odds")
    args = ap.parse_args()

    if args.backfill:
        backfill_golf_rounds(args.backfill[0], args.backfill[1], force=args.force)
    elif args.players:
        ingest_player_list()
    elif args.field:
        ingest_golf_field()
    elif args.results:
        ingest_golf_results()
    elif args.odds:
        ingest_golf_odds(include_matchups=args.matchups)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

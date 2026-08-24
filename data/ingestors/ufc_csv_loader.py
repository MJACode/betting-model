"""
UFC historical loader — CSV path (primary).

ufcstats.com moved behind a browser-level Cloudflare challenge that cloudscraper
can't solve (see ufc_stats_ingestor._get). This loader gets the identical data
from the Greco1899/scrape_ufc_stats GitHub mirror — a maintained repo whose own
scheduled scraper keeps 1:1 CSV exports of ufcstats.com (the CSVs even preserve
the ufcstats fight/fighter ids in their URL columns), updated weekly after each
card.

It does NOT re-implement any DB logic. It rebuilds the exact dict shapes the
pure parsers (`parse_event_page` / `parse_fight_page`) emit, then hands them to
`ufc_stats_ingestor._ingest_event(ev=..., detail_lookup=...)`, so home/away
assignment, games/ufc_fight_log writes, idempotency and the settlement contract
are all shared with the scraper. Fighter profiles (height/reach/stance/dob),
which the scraper fetched per-page over HTTP, are loaded from fighter_tott.csv.

CSV files used (from UFC_CSV_DIR if set, else fetched from UFC_CSV_BASE_URL):
    ufc_event_details.csv   EVENT, URL(event id), DATE, LOCATION
    ufc_fight_results.csv   EVENT, BOUT, OUTCOME, WEIGHTCLASS, METHOD, ROUND,
                            TIME, TIME FORMAT, REFEREE, DETAILS, URL(fight id)
    ufc_fight_stats.csv     EVENT, BOUT, ROUND, FIGHTER, KD, SIG.STR., ... (per round)
    ufc_fighter_tott.csv    FIGHTER, HEIGHT, WEIGHT, REACH, STANCE, DOB, URL(fighter id)

Usage:
    python -m data.ingestors.ufc_csv_loader --backfill 2010 2025
    python -m data.ingestors.ufc_csv_loader --fighters        # profiles only
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import UFC_CSV_BASE_URL, UFC_CSV_DIR
from data.db import get_connection, DBConnection
from data.ingestors.ufc_stats_ingestor import (
    _id_from_url, _int_or_none, _mmss_to_sec, _of_pair, _parse_event_date,
    _parse_dob, _height_to_inches, _reach_to_inches, _ingest_event,
    slugify_fighter,
)

_FILES = {
    "events":   "ufc_event_details.csv",
    "results":  "ufc_fight_results.csv",
    "stats":    "ufc_fight_stats.csv",
    "tott":     "ufc_fighter_tott.csv",
}


# ── CSV access ────────────────────────────────────────────────────────────────

# The mirror is ~9.8 MB across the four CSVs and is fetched unconditionally on
# every call, which is fine once a day and abusive of a volunteer's free repo
# once an hour. raw.githubusercontent serves no Last-Modified but does serve an
# ETag (a content hash) and honours If-None-Match with a bodyless 304, so a poll
# costs one HEAD when nothing has changed.
#
# The cache lives on disk and the worker's disk is ephemeral: losing it costs
# exactly one extra download after a redeploy, so no schema change is warranted.
_ETAG_CACHE = Path(os.environ.get(
    "UFC_CSV_ETAG_CACHE",
    Path(tempfile.gettempdir()) / "ufc_mirror_etag.json"))


def _mirror_etag() -> str | None:
    """Current ETag of the fight-results CSV, or None if it can't be read."""
    if UFC_CSV_DIR:
        return None                       # local files: nothing to poll
    try:
        url = f"{UFC_CSV_BASE_URL.rstrip('/')}/{_FILES['results']}"
        resp = requests.head(url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        return resp.headers.get("ETag")
    except Exception as exc:
        logger.debug(f"UFC mirror HEAD failed ({exc}) — will fetch in full")
        return None


def _cached_etag() -> str | None:
    try:
        return json.loads(_ETAG_CACHE.read_text()).get("results")
    except Exception:
        return None


def _store_etag(etag: str | None) -> None:
    if not etag:
        return
    try:
        _ETAG_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _ETAG_CACHE.write_text(json.dumps({"results": etag}))
    except Exception as exc:
        logger.debug(f"could not cache UFC mirror etag: {exc}")


def mirror_unchanged() -> bool:
    """True when the mirror is byte-identical to the copy we last ingested.

    Conservative: any doubt (HEAD failed, nothing cached, local dir in use)
    returns False so the caller fetches rather than silently skipping a card.
    """
    current = _mirror_etag()
    return bool(current) and current == _cached_etag()


def _read_csv(key: str) -> list[dict]:
    """Load one CSV as a list of dict rows, from UFC_CSV_DIR or the GitHub mirror."""
    fname = _FILES[key]
    if UFC_CSV_DIR:
        path = Path(UFC_CSV_DIR) / fname
        text = path.read_text(encoding="utf-8")
    else:
        url = f"{UFC_CSV_BASE_URL.rstrip('/')}/{fname}"
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        text = resp.text
    return list(csv.DictReader(io.StringIO(text)))


# ── Pure transforms (CSV rows → parser-shaped dicts) ───────────────────────────

def _kd_int(text: str) -> int | None:
    """KD/REV cells arrive as floats in the CSV ('1.0'); coerce to int."""
    t = (text or "").strip()
    if not t or t == "--":
        return None
    try:
        return int(float(t))
    except ValueError:
        return None


def _split_bout(bout: str) -> tuple[str, str] | None:
    """'Arnold Allen vs. Melquizael Costa' → ('Arnold Allen', 'Melquizael Costa')."""
    parts = (bout or "").split(" vs. ")
    if len(parts) != 2:
        return None
    return parts[0].strip(), parts[1].strip()


def _scheduled_rounds(time_format: str) -> int | None:
    """'3 Rnd (5-5-5)' → 3; 'No Time Limit' → None."""
    import re
    m = re.match(r"^\s*(\d+)\s*Rnd", (time_format or "").strip())
    return int(m.group(1)) if m else None


def build_fighter_index(tott_rows: list[dict]) -> dict[str, str]:
    """
    Map fighter display name → ufcstats fighter id (from the URL column).
    Seven names are shared by two fighters in the dataset; we keep the first
    occurrence and warn — acceptable for v1 (the min-3-fights gate and rolling
    career stats are robust to a rare id collision).
    """
    index: dict[str, str] = {}
    collisions: list[str] = []
    for r in tott_rows:
        name = (r.get("FIGHTER") or "").strip()
        fid = _id_from_url(r.get("URL", ""), "fighter")
        if not name or not fid:
            continue
        if name in index and index[name] != fid:
            collisions.append(name)
            continue
        index[name] = fid
    if collisions:
        logger.warning(f"{len(collisions)} duplicate fighter names kept first id: "
                       f"{sorted(set(collisions))}")
    return index


def _aggregate_stats(stat_rows: list[dict]) -> dict[tuple[str, str], dict[str, dict]]:
    """
    Sum per-round stat rows into per-(EVENT, BOUT) → {fighter_name: totals}.
    Totals mirror parse_fight_page's per-fighter values:
      kd, sig_landed, sig_attempted, total_landed, td_landed, td_attempted,
      sub_attempts, reversals, control_sec.
    """
    agg: dict[tuple[str, str], dict[str, dict]] = defaultdict(lambda: defaultdict(
        lambda: {"kd": 0, "sig_landed": 0, "sig_attempted": 0,
                 "total_landed": 0, "td_landed": 0, "td_attempted": 0,
                 "sub_attempts": 0, "reversals": 0, "control_sec": 0}))
    for r in stat_rows:
        key = ((r.get("EVENT") or "").strip(), (r.get("BOUT") or "").strip())
        fighter = (r.get("FIGHTER") or "").strip()
        if not fighter:
            continue
        t = agg[key][fighter]
        t["kd"] += _kd_int(r.get("KD")) or 0
        sl, sa = _of_pair(r.get("SIG.STR.", ""))
        t["sig_landed"] += sl or 0
        t["sig_attempted"] += sa or 0
        tl, _ = _of_pair(r.get("TOTAL STR.", ""))
        t["total_landed"] += tl or 0
        tdl, tda = _of_pair(r.get("TD", ""))
        t["td_landed"] += tdl or 0
        t["td_attempted"] += tda or 0
        t["sub_attempts"] += _kd_int(r.get("SUB.ATT")) or 0
        t["reversals"] += _kd_int(r.get("REV.")) or 0
        t["control_sec"] += _mmss_to_sec((r.get("CTRL") or "").strip()) or 0
    return agg


def build_events(results_rows, stat_rows, fighter_index,
                 event_meta_by_name) -> dict[str, dict]:
    """
    Group fight-results rows by event into the dict shape parse_event_page
    returns, plus a parallel detail map (fight_id → parse_fight_page shape).

    Returns: {event_id: {"name", "date", "fights": [...], "_details": {...}}}
    Winner is always placed first (names[0]) for decisive bouts, matching the
    'first_won' convention _ingest_event relies on.
    """
    stat_agg = _aggregate_stats(stat_rows)
    events: dict[str, dict] = {}

    for r in results_rows:
        event_name = (r.get("EVENT") or "").strip()
        bout = (r.get("BOUT") or "").strip()
        pair = _split_bout(bout)
        meta = event_meta_by_name.get(event_name)
        if not pair or not meta:
            continue
        event_id, event_date = meta
        fight_id = _id_from_url(r.get("URL", ""), "fight")
        if not fight_id:
            continue

        a, b = pair
        outcome_raw = (r.get("OUTCOME") or "").strip().upper()
        if outcome_raw == "W/L":            # first listed won
            names = [a, b]; outcome = "first_won"
        elif outcome_raw == "L/W":          # second listed won → put winner first
            names = [b, a]; outcome = "first_won"
        elif outcome_raw.startswith("D"):
            names = [a, b]; outcome = "draw"
        else:                               # NC/NC or anything else
            names = [a, b]; outcome = "nc"

        ids = [fighter_index.get(n) for n in names]
        per_fighter = stat_agg.get((event_name, bout), {})
        ordered = [per_fighter.get(n, {}) for n in names]

        method_raw = (r.get("METHOD") or "").strip()
        end_round = _int_or_none(r.get("ROUND", ""))
        end_time_sec = _mmss_to_sec((r.get("TIME") or "").strip())
        weight_class = (r.get("WEIGHTCLASS") or "").strip()
        is_title = 1 if "title" in weight_class.lower() else 0

        fight = {
            "fight_id":       fight_id,
            "fighter_ids":    ids,
            "fighter_names":  names,
            "outcome":        outcome,
            "weight_class":   weight_class,
            "is_title_fight": is_title,
            "method_raw":     method_raw,
            "end_round":      end_round,
            "end_time_sec":   end_time_sec,
            "kd":             [t.get("kd") for t in ordered],
            "sig_landed":     [t.get("sig_landed") for t in ordered],
            "td_landed":      [t.get("td_landed") for t in ordered],
            "sub_attempts":   [t.get("sub_attempts") for t in ordered],
        }
        detail = {
            "scheduled_rounds": _scheduled_rounds(r.get("TIME FORMAT", "")),
            "is_title_fight":   is_title,
            "method_raw":       method_raw,
            "end_round":        end_round,
            "end_time_sec":     end_time_sec,
            "totals": {
                "kd":            [t.get("kd") for t in ordered],
                "sig_landed":    [t.get("sig_landed") for t in ordered],
                "sig_attempted": [t.get("sig_attempted") for t in ordered],
                "total_landed":  [t.get("total_landed") for t in ordered],
                "td_landed":     [t.get("td_landed") for t in ordered],
                "td_attempted":  [t.get("td_attempted") for t in ordered],
                "sub_attempts":  [t.get("sub_attempts") for t in ordered],
                "reversals":     [t.get("reversals") for t in ordered],
                "control_sec":   [t.get("control_sec") for t in ordered],
            },
        }

        ev = events.setdefault(event_id, {
            "name": event_name, "date": event_date,
            "fights": [], "_details": {}})
        ev["fights"].append(fight)
        ev["_details"][fight_id] = detail

    return events


# ── DB writes ─────────────────────────────────────────────────────────────────

def load_fighter_profiles_from_csv(conn: DBConnection, tott_rows: list[dict]) -> int:
    """
    Upsert height/reach/stance/dob for every fighter in tott.csv. Replaces the
    scraper's per-page HTTP profile fetch (refresh_fighter_profiles), which is
    blocked behind Cloudflare.
    """
    updated = 0
    for r in tott_rows:
        name = (r.get("FIGHTER") or "").strip()
        fid = _id_from_url(r.get("URL", ""), "fighter")
        if not name or not fid:
            continue
        height = _height_to_inches((r.get("HEIGHT") or "").strip())
        reach = _reach_to_inches((r.get("REACH") or "").replace('"', '').strip())
        stance = (r.get("STANCE") or "").strip() or None
        dob = _parse_dob((r.get("DOB") or "").strip())
        conn.execute("""
            INSERT INTO fighters (fighter_id, name, slug, height_in, reach_in,
                                  stance, dob)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fighter_id) DO UPDATE SET
                name = EXCLUDED.name, slug = EXCLUDED.slug,
                height_in = COALESCE(EXCLUDED.height_in, fighters.height_in),
                reach_in  = COALESCE(EXCLUDED.reach_in, fighters.reach_in),
                stance    = COALESCE(EXCLUDED.stance, fighters.stance),
                dob       = COALESCE(EXCLUDED.dob, fighters.dob),
                updated_at = NOW()::TEXT
        """, (fid, name, slugify_fighter(name), height, reach, stance, dob))
        updated += 1
    conn.commit()
    logger.success(f"Fighter profiles loaded from CSV: {updated}")
    return updated


# ── Entry points ────────────────────────────────────────────────────────────

def backfill_ufc_csv(start_year: int, end_year: int, force: bool = False) -> dict:
    """
    Historical backfill from the CSV mirror. Same DB effect as
    ufc_stats_ingestor.backfill_ufc_stats, minus the Cloudflare problem.
    Idempotent — already-ingested events are skipped by _ingest_event.
    """
    logger.info(f"Loading UFC CSVs (dir={UFC_CSV_DIR or UFC_CSV_BASE_URL}) ...")
    event_rows = _read_csv("events")
    results_rows = _read_csv("results")
    stat_rows = _read_csv("stats")
    tott_rows = _read_csv("tott")

    today = datetime.now().strftime("%Y-%m-%d")
    event_meta_by_name: dict[str, tuple[str, str]] = {}
    for r in event_rows:
        name = (r.get("EVENT") or "").strip()
        date = _parse_event_date((r.get("DATE") or "").strip())
        eid = _id_from_url(r.get("URL", ""), "event")
        if name and date and eid and start_year <= int(date[:4]) <= end_year \
                and date <= today:
            event_meta_by_name[name] = (eid, date)

    fighter_index = build_fighter_index(tott_rows)
    events = build_events(results_rows, stat_rows, fighter_index, event_meta_by_name)
    ordered = sorted(events.items(), key=lambda kv: kv[1]["date"])
    logger.info(f"UFC CSV backfill {start_year}–{end_year}: {len(ordered)} events")

    conn = get_connection()
    total_fights = 0
    try:
        load_fighter_profiles_from_csv(conn, tott_rows)
        for i, (event_id, ev) in enumerate(ordered, 1):
            try:
                result = _ingest_event(
                    conn, event_id, {"name": ev["name"], "date": ev["date"]},
                    force=force, ev=ev,
                    detail_lookup=lambda fid, _d=ev["_details"]: _d.get(fid))
                total_fights += result["fights"]
            except Exception as exc:
                logger.error(f"Event {ev['name']} ({ev['date']}) failed: {exc}")
                conn.rollback()
            if i % 50 == 0:
                logger.info(f"  ... {i}/{len(ordered)} events done")
    finally:
        conn.close()

    logger.success(f"CSV backfill done: {len(ordered)} events, {total_fights} fights")
    return {"events": len(ordered), "fights": total_fights}


def _heal_window_lo(conn: DBConnection, run_date: str, lookback_days: int,
                    max_heal_days: int) -> str:
    """
    Self-healing lower bound for the daily ingest window.

    The mirror's update cadence is irregular and can lag a card by well over a
    week (observed Jun–Jul 2026: events absent 8+ days after the card), so a
    fixed trailing window silently drops events that appear in the CSV only
    after they've slid out of it. Anchor the window to the last event actually
    ingested (MAX(ufc_fight_log.game_date)) so anything the mirror publishes
    late is still picked up, bounded by max_heal_days. Re-ingesting an already
    -done event is a cheap idempotent skip.
    """
    from datetime import timedelta
    d = datetime.strptime(run_date, "%Y-%m-%d")
    lo = (d - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    floor = (d - timedelta(days=max_heal_days)).strftime("%Y-%m-%d")

    row = conn.execute("SELECT MAX(game_date) FROM ufc_fight_log").fetchone()
    if row and row[0]:
        # -1 day so the boundary event is re-checked (idempotent)
        heal = (datetime.strptime(str(row[0])[:10], "%Y-%m-%d")
                - timedelta(days=1)).strftime("%Y-%m-%d")
        lo = min(lo, heal)
    else:
        lo = floor
    return max(lo, floor)


def ingest_ufc_results_for_date_csv(run_date: str | None = None,
                                    lookback_days: int = 8,
                                    max_heal_days: int = 365) -> dict:
    """
    Daily pipeline step (CSV path). Ingests any event from the CSV mirror
    between the self-healing lower bound (see _heal_window_lo — everything
    since the last ingested event, capped at max_heal_days) and run_date.
    Must run before settlement. No-ops cleanly when the mirror has nothing
    new in the window (non-event days).
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    etag = _mirror_etag()          # captured BEFORE the download it describes
    try:
        event_rows = _read_csv("events")
        results_rows = _read_csv("results")
        stat_rows = _read_csv("stats")
        tott_rows = _read_csv("tott")
    except Exception as exc:
        logger.error(f"UFC CSV fetch failed: {exc}")
        return {"events": 0, "fights": 0, "error": str(exc)}

    conn = get_connection()
    total = 0
    try:
        lo = _heal_window_lo(conn, run_date, lookback_days, max_heal_days)

        meta = {}
        for r in event_rows:
            n = (r.get("EVENT") or "").strip()
            d = _parse_event_date((r.get("DATE") or "").strip())
            e = _id_from_url(r.get("URL", ""), "event")
            if n and d and e and lo <= d <= run_date:
                meta[n] = (e, d)
        if not meta:
            logger.info(f"UFC results: no events in {lo}..{run_date}")
            return {"events": 0, "fights": 0}

        events = build_events(results_rows, stat_rows,
                              build_fighter_index(tott_rows), meta)
        logger.info(f"UFC results: {len(events)} event(s) in {lo}..{run_date}")
        load_fighter_profiles_from_csv(conn, tott_rows)
        for event_id, ev in events.items():
            try:
                result = _ingest_event(
                    conn, event_id, {"name": ev["name"], "date": ev["date"]},
                    ev=ev,
                    detail_lookup=lambda fid, _d=ev["_details"]: _d.get(fid))
                total += result["fights"]
            except Exception as exc:
                logger.error(f"Event {ev['name']} failed: {exc}")
                conn.rollback()
    finally:
        conn.close()
    # Only after a clean ingest: a failed run must re-fetch rather than record
    # the mirror as already consumed.
    _store_etag(etag)
    return {"events": len(events), "fights": total}


def refresh_fighter_profiles_from_csv() -> dict:
    """Load only the fighter profile table from the CSV mirror."""
    conn = get_connection()
    try:
        return {"profiles": load_fighter_profiles_from_csv(conn, _read_csv("tott"))}
    finally:
        conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UFC CSV-mirror loader")
    parser.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill events from START to END year (e.g. 2010 2025)")
    parser.add_argument("--fighters", action="store_true",
                        help="Load fighter profiles only")
    parser.add_argument("--force", action="store_true",
                        help="Re-ingest events even if already present")
    args = parser.parse_args()

    if args.fighters:
        result = refresh_fighter_profiles_from_csv()
    elif args.backfill:
        result = backfill_ufc_csv(args.backfill[0], args.backfill[1], force=args.force)
    else:
        parser.error("specify --backfill START END or --fighters")

    logger.info(f"Done: {result}")

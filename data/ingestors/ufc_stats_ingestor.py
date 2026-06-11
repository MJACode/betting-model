"""
ufc_stats_ingestor.py — ufcstats.com scraper: events, fight results, fighters.

UFC has no official free stats API. ufcstats.com is the canonical public
record (every UFC fight back to 1993) and is a static, unauthenticated site.
This ingestor is the UFC analog of wnba_stats_ingestor:

  • backfill_ufc_stats(start, end)     — historical backfill (~700 events,
                                         ~8K fights since 2010, ~1 hr polite)
  • ingest_ufc_results_for_date(date)  — daily step; ingests any completed
                                         event in the trailing week that isn't
                                         fully ingested yet (Sunday 7am run
                                         catches Saturday cards; self-heals)
  • refresh_fighter_profiles()         — fills height/reach/stance/dob for
                                         fighters missing profile data

Writes:
  • fighters       — identity registry (ufcstats fighter_id, name, slug,
                     height/reach/stance/dob)
  • ufc_fight_log  — one row per fighter per fight (two rows per fight)
  • games          — sport='UFC' rows. Pre-fight rows are created by the odds
                     ingestor (home/away = The Odds API assignment); this
                     ingestor matches them by slug-pair + date (±1 day) and
                     fills home_score/away_score/home_win. Historical fights
                     with no odds row get a deterministic assignment:
                     home = lexicographically smaller slug (random w.r.t.
                     outcome — never winner-first, which would leak the label).

All HTML parsers are pure functions over markup strings so they can be
fixture-tested without network access. Markup changes localize here.

Usage:
    python -m data.ingestors.ufc_stats_ingestor --backfill 2010 2025
    python -m data.ingestors.ufc_stats_ingestor --date 2026-06-13
    python -m data.ingestors.ufc_stats_ingestor --event-id 39f68882def7a507
    python -m data.ingestors.ufc_stats_ingestor --fighters     # profile refresh
"""

import argparse
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import UFCSTATS_BASE_URL, UFC_NAME_ALIASES
from data.db import get_connection, DBConnection

REQUEST_SLEEP = 0.3   # polite inter-request pause (static site, but be kind)
_HEADERS = {"User-Agent": "Mozilla/5.0 (betting-model research; contact: personal project)"}


# ── Pure helpers ──────────────────────────────────────────────────────────────

def slugify_fighter(name: str) -> str:
    """
    Normalize a fighter name to a join key: lowercase, accents stripped,
    punctuation removed, spaces → hyphens. 'José Aldo Jr.' → 'jose-aldo-jr'.
    Applied to both Odds API names and ufcstats names so the two sources meet.
    """
    if not name:
        return ""
    # Apply explicit alias first (Odds API name → ufcstats name)
    name = UFC_NAME_ALIASES.get(name, name)
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def normalize_method(raw: str) -> str:
    """Map a ufcstats method string to our canonical method classes."""
    if not raw:
        return "other"
    m = raw.strip().lower()
    if "ko" in m or "tko" in m:          # 'KO/TKO', "TKO - Doctor's Stoppage"
        return "ko_tko"
    if "submission" in m:
        return "submission"
    if "decision" in m:                  # Unanimous / Split / Majority
        return "decision"
    if "dq" in m or "disqualification" in m:
        return "dq"
    return "other"                       # Overturned / Could Not Continue / etc.


def _mmss_to_sec(mmss: str) -> int | None:
    """'3:14' → 194 seconds."""
    if not mmss:
        return None
    m = re.match(r"^\s*(\d+):(\d{2})\s*$", mmss)
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def _parse_event_date(text: str) -> str | None:
    """'April 13, 2024' → '2024-04-13'."""
    try:
        return datetime.strptime(text.strip(), "%B %d, %Y").strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def rounds_completed(end_round: int | None, end_time_sec: int | None,
                     scheduled_rounds: int | None) -> float | None:
    """
    Fractional rounds completed at the fight's end — the 'total' that round
    O/U lines settle against (Over 2.5 = the fight passes 2:30 of round 3).
    A 5-minute UFC round is the unit; a decision = exactly scheduled_rounds.
    """
    if end_round is None or end_time_sec is None:
        return None
    if scheduled_rounds is not None and end_round >= scheduled_rounds and end_time_sec >= 300:
        return float(scheduled_rounds)   # went the distance
    return round((end_round - 1) + min(end_time_sec, 300) / 300.0, 3)


def _id_from_url(url: str, kind: str) -> str | None:
    """Extract the hex token from a ufcstats details URL."""
    if not url:
        return None
    m = re.search(rf"{kind}-details/([0-9a-f]+)", url)
    return m.group(1) if m else None


def _height_to_inches(text: str) -> float | None:
    """ufcstats height `6' 4"` → 76.0."""
    if not text:
        return None
    m = re.match(r"""^\s*(\d+)'\s*(\d+)"\s*$""", text.strip())
    if not m:
        return None
    return float(m.group(1)) * 12 + float(m.group(2))


def _reach_to_inches(text: str) -> float | None:
    """ufcstats reach `76"` → 76.0."""
    if not text:
        return None
    m = re.match(r'^\s*(\d+(?:\.\d+)?)"?\s*$', text.strip())
    return float(m.group(1)) if m else None


def _parse_dob(text: str) -> str | None:
    """'Jul 19, 1987' → '1987-07-19'."""
    try:
        return datetime.strptime(text.strip(), "%b %d, %Y").strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def _of_pair(text: str) -> tuple[int | None, int | None]:
    """ufcstats 'landed of attempted' cell: '116 of 199' → (116, 199)."""
    if not text:
        return None, None
    m = re.match(r"^\s*(\d+)\s+of\s+(\d+)\s*$", text.strip())
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _int_or_none(text: str) -> int | None:
    try:
        return int(text.strip())
    except (ValueError, TypeError, AttributeError):
        return None


# ── HTML Parsers (pure — fixture-testable) ────────────────────────────────────

def parse_event_list(html: str) -> list[dict]:
    """
    Parse the completed-events index (statistics/events/completed?page=all).
    Returns [{event_id, name, date, location}] for rows that carry a date.
    The 'next event' header row (no completed flag) is included — callers
    filter by date <= today.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for row in soup.select("tr.b-statistics__table-row"):
        link = row.select_one("a[href*='event-details/']")
        date_el = row.select_one("span.b-statistics__date")
        if not link or not date_el:
            continue
        event_id = _id_from_url(link.get("href", ""), "event")
        date_iso = _parse_event_date(date_el.get_text())
        if not event_id or not date_iso:
            continue
        cols = row.select("td")
        location = cols[1].get_text(strip=True) if len(cols) > 1 else None
        events.append({
            "event_id": event_id,
            "name":     link.get_text(strip=True),
            "date":     date_iso,
            "location": location,
        })
    return events


def parse_event_page(html: str) -> dict:
    """
    Parse an event-details page into event metadata + its fight rows.

    Returns:
        {
          "name": str, "date": "YYYY-MM-DD" | None,
          "fights": [{
              fight_id, fighter_ids: [id1, id2], fighter_names: [n1, n2],
              outcome: 'first_won' | 'draw' | 'nc',
              weight_class, is_title_fight,
              method_raw, end_round, end_time_sec,
              kd: [int, int], sig_landed: [int, int],
              td_landed: [int, int], sub_attempts: [int, int],
          }]
        }
    The first listed fighter in a row is the winner when outcome='first_won'.
    """
    soup = BeautifulSoup(html, "html.parser")

    name_el = soup.select_one("span.b-content__title-highlight")
    event_name = name_el.get_text(strip=True) if name_el else None

    event_date = None
    for li in soup.select("li.b-list__box-list-item"):
        txt = li.get_text(" ", strip=True)
        if txt.lower().startswith("date:"):
            event_date = _parse_event_date(txt[5:].strip())
            break

    fights = []
    for row in soup.select("tr.b-fight-details__table-row[data-link]"):
        fight_id = _id_from_url(row.get("data-link", ""), "fight")
        if not fight_id:
            continue

        cols = row.select("td")
        if len(cols) < 10:
            continue

        # Outcome flags (one per fighter for draw/nc; single 'win' for a winner)
        flags = [f.get_text(strip=True).lower()
                 for f in cols[0].select("i.b-flag__text")]
        if "win" in flags:
            outcome = "first_won"
        elif "draw" in flags:
            outcome = "draw"
        else:
            outcome = "nc"

        fighter_links = cols[1].select("a[href*='fighter-details/']")
        if len(fighter_links) < 2:
            continue
        fighter_ids = [_id_from_url(a.get("href", ""), "fighter")
                       for a in fighter_links[:2]]
        fighter_names = [a.get_text(strip=True) for a in fighter_links[:2]]

        def _two_ints(col):
            ps = col.select("p")
            return [_int_or_none(p.get_text()) for p in ps[:2]] if len(ps) >= 2 else [None, None]

        kd          = _two_ints(cols[2])
        sig_landed  = _two_ints(cols[3])
        td_landed   = _two_ints(cols[4])
        sub_att     = _two_ints(cols[5])

        wc_ps = cols[6].select("p")
        weight_class = wc_ps[0].get_text(strip=True) if wc_ps else None
        is_title = 1 if cols[6].select_one("img[src*='belt']") else 0

        method_ps = cols[7].select("p")
        method_raw = " ".join(p.get_text(strip=True) for p in method_ps if p.get_text(strip=True))

        end_round = _int_or_none(cols[8].get_text())
        end_time_sec = _mmss_to_sec(cols[9].get_text(strip=True))

        fights.append({
            "fight_id":       fight_id,
            "fighter_ids":    fighter_ids,
            "fighter_names":  fighter_names,
            "outcome":        outcome,
            "weight_class":   weight_class,
            "is_title_fight": is_title,
            "method_raw":     method_raw,
            "end_round":      end_round,
            "end_time_sec":   end_time_sec,
            "kd":             kd,
            "sig_landed":     sig_landed,
            "td_landed":      td_landed,
            "sub_attempts":   sub_att,
        })

    return {"name": event_name, "date": event_date, "fights": fights}


def parse_fight_page(html: str) -> dict:
    """
    Parse a fight-details page for the data the event row doesn't carry:
    scheduled rounds (time format), title-bout flag, and full per-fighter
    totals (attempted strikes, total strikes, takedown attempts, reversals,
    control time). Per-fighter values are returned in page order — the same
    fighter order as the event row.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: dict = {
        "scheduled_rounds": None,
        "is_title_fight":   0,
        "method_raw":       None,
        "end_round":        None,
        "end_time_sec":     None,
        "totals":           None,
    }

    title_el = soup.select_one("i.b-fight-details__fight-title")
    if title_el and "title bout" in title_el.get_text(" ", strip=True).lower():
        out["is_title_fight"] = 1

    for item in soup.select("i.b-fight-details__text-item, i.b-fight-details__text-item_first"):
        label_el = item.select_one("i.b-fight-details__label")
        if not label_el:
            continue
        label = label_el.get_text(strip=True).rstrip(":").lower()
        value = item.get_text(" ", strip=True)
        value = re.sub(rf"^{re.escape(label_el.get_text(strip=True))}\s*", "", value).strip()
        if label == "method":
            out["method_raw"] = value
        elif label == "round":
            out["end_round"] = _int_or_none(value)
        elif label == "time":
            out["end_time_sec"] = _mmss_to_sec(value)
        elif label == "time format":
            m = re.match(r"^\s*(\d+)\s*Rnd", value)
            out["scheduled_rounds"] = int(m.group(1)) if m else None

    # Totals table — first .js-fight-section table. Columns:
    # Fighter | KD | Sig. str. | Sig. str. % | Total str. | Td | Td % | Sub. att | Rev. | Ctrl
    section = soup.select_one("section.b-fight-details__section.js-fight-section table")
    if section:
        body_row = section.select_one("tbody tr")
        if body_row:
            cols = body_row.select("td")
            if len(cols) >= 10:
                def _pair(col_idx, parser):
                    ps = cols[col_idx].select("p")
                    if len(ps) < 2:
                        return [None, None]
                    return [parser(ps[0].get_text(strip=True)),
                            parser(ps[1].get_text(strip=True))]

                kd = _pair(1, _int_or_none)
                sig = _pair(2, _of_pair)
                tot = _pair(4, _of_pair)
                td  = _pair(5, _of_pair)
                sub = _pair(7, _int_or_none)
                rev = _pair(8, _int_or_none)
                ctrl = _pair(9, _mmss_to_sec)

                out["totals"] = {
                    "kd":             kd,
                    "sig_landed":     [sig[0][0] if sig[0] else None, sig[1][0] if sig[1] else None],
                    "sig_attempted":  [sig[0][1] if sig[0] else None, sig[1][1] if sig[1] else None],
                    "total_landed":   [tot[0][0] if tot[0] else None, tot[1][0] if tot[1] else None],
                    "td_landed":      [td[0][0] if td[0] else None, td[1][0] if td[1] else None],
                    "td_attempted":   [td[0][1] if td[0] else None, td[1][1] if td[1] else None],
                    "sub_attempts":   sub,
                    "reversals":      rev,
                    "control_sec":    ctrl,
                }

    return out


def parse_fighter_page(html: str) -> dict:
    """Parse a fighter-details page → {name, height_in, reach_in, stance, dob}."""
    soup = BeautifulSoup(html, "html.parser")
    name_el = soup.select_one("span.b-content__title-highlight")
    out = {
        "name":      name_el.get_text(strip=True) if name_el else None,
        "height_in": None,
        "reach_in":  None,
        "stance":    None,
        "dob":       None,
    }
    for li in soup.select("li.b-list__box-list-item"):
        title_el = li.select_one("i.b-list__box-item-title")
        if not title_el:
            continue
        label = title_el.get_text(strip=True).rstrip(":").lower()
        value = li.get_text(" ", strip=True)
        value = re.sub(rf"^{re.escape(title_el.get_text(strip=True))}\s*", "", value).strip()
        if value == "--":
            continue
        if label == "height":
            out["height_in"] = _height_to_inches(value)
        elif label == "reach":
            out["reach_in"] = _reach_to_inches(value)
        elif label == "stance":
            out["stance"] = value
        elif label == "dob":
            out["dob"] = _parse_dob(value)
    return out


# ── HTTP fetchers ─────────────────────────────────────────────────────────────

def _get(url: str) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    time.sleep(REQUEST_SLEEP)
    return resp.text


def _fetch_event_list(all_pages: bool = True) -> list[dict]:
    page = "all" if all_pages else "1"
    url = f"{UFCSTATS_BASE_URL}/statistics/events/completed?page={page}"
    return parse_event_list(_get(url))


def _fetch_event(event_id: str) -> dict:
    return parse_event_page(_get(f"{UFCSTATS_BASE_URL}/event-details/{event_id}"))


def _fetch_fight(fight_id: str) -> dict:
    return parse_fight_page(_get(f"{UFCSTATS_BASE_URL}/fight-details/{fight_id}"))


def _fetch_fighter(fighter_id: str) -> dict:
    return parse_fighter_page(_get(f"{UFCSTATS_BASE_URL}/fighter-details/{fighter_id}"))


# ── DB helpers ────────────────────────────────────────────────────────────────

def _build_ufc_game_id(game_date: str, away_slug: str, home_slug: str) -> str:
    """Mirror of odds_ingestor._build_game_id for sport='UFC'."""
    return f"UFC_{game_date}_{away_slug}_{home_slug}"


def _resolve_game_row(conn: DBConnection, game_date: str,
                      slug_a: str, slug_b: str) -> tuple[str, str, str] | None:
    """
    Find an existing UFC games row matching this fighter pair within ±1 day of
    game_date (Odds API ET-converted dates can differ from the ufcstats event
    date for late cards / international events).

    Returns (game_id, home_team_name, away_team_name) or None.
    """
    d = datetime.strptime(game_date, "%Y-%m-%d")
    lo = (d - timedelta(days=1)).strftime("%Y-%m-%d")
    hi = (d + timedelta(days=1)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT game_id, home_team, away_team FROM games
        WHERE sport = 'UFC' AND game_date BETWEEN %s AND %s
    """, (lo, hi)).fetchall()

    want = {slug_a, slug_b}
    for game_id, home_team, away_team in rows:
        if {slugify_fighter(home_team), slugify_fighter(away_team)} == want:
            return game_id, home_team, away_team
    return None


def _upsert_fighter_stub(conn: DBConnection, fighter_id: str, name: str) -> None:
    """Register a fighter id/name/slug; profile fields filled later."""
    conn.execute("""
        INSERT INTO fighters (fighter_id, name, slug)
        VALUES (%s, %s, %s)
        ON CONFLICT (fighter_id) DO UPDATE SET
            name = EXCLUDED.name,
            slug = EXCLUDED.slug,
            updated_at = NOW()::TEXT
    """, (fighter_id, name, slugify_fighter(name)))


def _upsert_fight_log(conn: DBConnection, row: dict) -> None:
    cols = [
        "fighter_id", "fighter_name", "opponent_id", "opponent_name",
        "game_id", "game_date", "season", "event_name", "weight_class",
        "is_title_fight", "scheduled_rounds", "result", "method",
        "method_detail", "end_round", "end_time_sec", "knockdowns",
        "sig_strikes_landed", "sig_strikes_attempted", "sig_strikes_absorbed",
        "total_strikes_landed", "takedowns_landed", "takedowns_attempted",
        "sub_attempts", "reversals", "control_time_sec",
    ]
    placeholders = ", ".join(f"%({c})s" for c in cols)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols
                        if c not in ("fighter_id", "game_id"))
    conn.execute(f"""
        INSERT INTO ufc_fight_log ({', '.join(cols)})
        VALUES ({placeholders})
        ON CONFLICT (fighter_id, game_id) DO UPDATE SET {updates}
    """, {c: row.get(c) for c in cols})


def _ingest_event(conn: DBConnection, event_id: str, event_meta: dict | None = None,
                  force: bool = False) -> dict:
    """
    Ingest one completed event: fight log rows for every fight + games rows
    (matched to pre-fight odds rows when they exist, created otherwise).
    Idempotent — skips fights whose game already has scores unless force.
    """
    ev = _fetch_event(event_id)
    event_name = ev.get("name") or (event_meta or {}).get("name")
    event_date = ev.get("date") or (event_meta or {}).get("date")
    if not event_date:
        logger.warning(f"Event {event_id}: no date parsed — skipping")
        return {"fights": 0, "skipped": 0}

    season = int(event_date[:4])
    n_ingested = n_skipped = 0

    for fight in ev["fights"]:
        ids   = fight["fighter_ids"]
        names = fight["fighter_names"]
        if None in ids or len(ids) < 2:
            logger.warning(f"  Fight {fight['fight_id']}: missing fighter ids — skipped")
            n_skipped += 1
            continue

        slugs = [slugify_fighter(n) for n in names]

        # ── Resolve / create the games row ─────────────────────────────────
        resolved = _resolve_game_row(conn, event_date, slugs[0], slugs[1])
        if resolved:
            game_id, home_name, away_name = resolved
            game_date_row = game_id.split("_")[1]
        else:
            # No pre-fight odds row (historical backfill). Deterministic
            # assignment: home = smaller slug. NEVER winner-first — that
            # would make home_win constant and leak the label.
            if slugs[0] <= slugs[1]:
                home_idx, away_idx = 0, 1
            else:
                home_idx, away_idx = 1, 0
            home_name, away_name = names[home_idx], names[away_idx]
            game_date_row = event_date
            game_id = _build_ufc_game_id(event_date, slugs[away_idx], slugs[home_idx])
            conn.execute("""
                INSERT INTO games (game_id, sport, season, game_date,
                                   home_team, away_team, data_source)
                VALUES (%s, 'UFC', %s, %s, %s, %s, 'ufcstats')
                ON CONFLICT (game_id) DO NOTHING
            """, (game_id, season, event_date, home_name, away_name))

        if not force:
            done = conn.execute(
                "SELECT 1 FROM games WHERE game_id = %s AND home_score IS NOT NULL",
                (game_id,)).fetchone()
            already_logged = conn.execute(
                "SELECT COUNT(*) FROM ufc_fight_log WHERE game_id = %s",
                (game_id,)).fetchone()
            if done and already_logged and already_logged[0] >= 2:
                n_skipped += 1
                continue

        # ── Fight-details page (scheduled rounds, title flag, full totals) ──
        detail = {}
        try:
            detail = _fetch_fight(fight["fight_id"])
        except Exception as exc:
            logger.warning(f"  Fight page {fight['fight_id']} fetch failed "
                           f"(using event-row data only): {exc}")

        method_raw = detail.get("method_raw") or fight["method_raw"]
        method = normalize_method(method_raw)
        end_round = detail.get("end_round") or fight["end_round"]
        end_time_sec = (detail.get("end_time_sec")
                        if detail.get("end_time_sec") is not None
                        else fight["end_time_sec"])
        scheduled = detail.get("scheduled_rounds")
        is_title = max(fight["is_title_fight"], detail.get("is_title_fight", 0))
        totals = detail.get("totals") or {}

        # ── games outcome (home/away convention of the resolved row) ───────
        home_slug = slugify_fighter(home_name)
        winner_slug = None
        if fight["outcome"] == "first_won":
            winner_slug = slugs[0]

        if fight["outcome"] in ("draw", "nc"):
            home_score, away_score, home_win = 0.5, 0.5, None
        elif winner_slug == home_slug:
            home_score, away_score, home_win = 1, 0, 1
        else:
            home_score, away_score, home_win = 0, 1, 0

        conn.execute("""
            UPDATE games
            SET home_score = %s, away_score = %s, home_win = %s,
                updated_at = NOW()::TEXT
            WHERE game_id = %s
        """, (home_score, away_score, home_win, game_id))

        # ── fighters + fight log (one row per fighter) ──────────────────────
        for i in (0, 1):
            _upsert_fighter_stub(conn, ids[i], names[i])

        sig_landed = totals.get("sig_landed") or fight["sig_landed"]
        for i, j in ((0, 1), (1, 0)):
            if fight["outcome"] == "draw":
                result = "draw"
            elif fight["outcome"] == "nc":
                result = "nc"
            else:
                result = "win" if i == 0 else "loss"

            _upsert_fight_log(conn, {
                "fighter_id":            ids[i],
                "fighter_name":          names[i],
                "opponent_id":           ids[j],
                "opponent_name":         names[j],
                "game_id":               game_id,
                "game_date":             game_date_row,
                "season":                season,
                "event_name":            event_name,
                "weight_class":          fight["weight_class"],
                "is_title_fight":        is_title,
                "scheduled_rounds":      scheduled,
                "result":                result,
                "method":                method,
                "method_detail":         method_raw,
                "end_round":             end_round,
                "end_time_sec":          end_time_sec,
                "knockdowns":            (totals.get("kd") or fight["kd"])[i],
                "sig_strikes_landed":    sig_landed[i],
                "sig_strikes_attempted": (totals.get("sig_attempted") or [None, None])[i],
                "sig_strikes_absorbed":  sig_landed[j],
                "total_strikes_landed":  (totals.get("total_landed") or [None, None])[i],
                "takedowns_landed":      (totals.get("td_landed") or fight["td_landed"])[i],
                "takedowns_attempted":   (totals.get("td_attempted") or [None, None])[i],
                "sub_attempts":          (totals.get("sub_attempts") or fight["sub_attempts"])[i],
                "reversals":             (totals.get("reversals") or [None, None])[i],
                "control_time_sec":      (totals.get("control_sec") or [None, None])[i],
            })

        n_ingested += 1

    conn.commit()
    logger.info(f"  {event_name} ({event_date}): {n_ingested} fights ingested, "
                f"{n_skipped} skipped")
    return {"fights": n_ingested, "skipped": n_skipped}


# ── Entry points ──────────────────────────────────────────────────────────────

def backfill_ufc_stats(start_year: int, end_year: int, force: bool = False) -> dict:
    """
    Historical backfill: every completed UFC event with start_year <= year <=
    end_year. Idempotent — already-ingested events are skipped quickly.
    ~700 events / ~8K fights for 2010–2025 at 300ms per request ≈ 1 hour.
    Run refresh_fighter_profiles() afterwards to fill height/reach/stance/dob.
    """
    events = _fetch_event_list(all_pages=True)
    today = datetime.now().strftime("%Y-%m-%d")
    targets = [e for e in events
               if start_year <= int(e["date"][:4]) <= end_year and e["date"] <= today]
    targets.sort(key=lambda e: e["date"])
    logger.info(f"UFC backfill {start_year}–{end_year}: {len(targets)} events")

    conn = get_connection()
    total_fights = 0
    try:
        for i, ev in enumerate(targets, 1):
            try:
                result = _ingest_event(conn, ev["event_id"], ev, force=force)
                total_fights += result["fights"]
            except Exception as exc:
                logger.error(f"Event {ev['name']} ({ev['date']}) failed: {exc}")
                conn.rollback()
            if i % 25 == 0:
                logger.info(f"  ... {i}/{len(targets)} events done")
    finally:
        conn.close()

    profile_result = refresh_fighter_profiles()
    return {"events": len(targets), "fights": total_fights, **profile_result}


def ingest_ufc_results_for_date(run_date: str | None = None) -> dict:
    """
    Daily pipeline step. Looks at the first page of completed events and
    ingests any event dated within the trailing 7 days of run_date that isn't
    fully ingested. No-ops cleanly on non-event days. The Sunday 7am run
    catches Saturday cards; the window self-heals missed runs.
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")
    lo = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")

    try:
        events = _fetch_event_list(all_pages=False)
    except Exception as exc:
        logger.error(f"ufcstats event list fetch failed: {exc}")
        return {"events": 0, "fights": 0, "error": str(exc)}

    targets = [e for e in events if lo <= e["date"] <= run_date]
    if not targets:
        logger.info(f"UFC results: no completed events in {lo}..{run_date}")
        return {"events": 0, "fights": 0}

    conn = get_connection()
    total = 0
    try:
        for ev in targets:
            try:
                result = _ingest_event(conn, ev["event_id"], ev)
                total += result["fights"]
            except Exception as exc:
                logger.error(f"Event {ev['name']} failed: {exc}")
                conn.rollback()
    finally:
        conn.close()

    if total:
        refresh_fighter_profiles()
    return {"events": len(targets), "fights": total}


def refresh_fighter_profiles(limit: int | None = None) -> dict:
    """
    Fetch fighter-details pages for fighters whose profile fields are all NULL
    (newly registered by fight ingestion). Idempotent and resumable.
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT fighter_id, name FROM fighters
            WHERE height_in IS NULL AND reach_in IS NULL
              AND stance IS NULL AND dob IS NULL
            ORDER BY fighter_id
        """).fetchall()
        if limit:
            rows = rows[:limit]
        if not rows:
            return {"profiles": 0}

        logger.info(f"Fetching {len(rows)} fighter profiles...")
        updated = 0
        for i, (fighter_id, name) in enumerate(rows, 1):
            try:
                profile = _fetch_fighter(fighter_id)
            except Exception as exc:
                logger.warning(f"  Profile fetch failed for {name}: {exc}")
                continue
            if not any(profile.get(k) for k in ("height_in", "reach_in", "stance", "dob")):
                continue
            conn.execute("""
                UPDATE fighters
                SET height_in = %s, reach_in = %s, stance = %s, dob = %s,
                    updated_at = NOW()::TEXT
                WHERE fighter_id = %s
            """, (profile["height_in"], profile["reach_in"],
                  profile["stance"], profile["dob"], fighter_id))
            updated += 1
            if i % 100 == 0:
                conn.commit()
                logger.info(f"  ... {i}/{len(rows)} profiles done")
        conn.commit()
        logger.success(f"Fighter profiles updated: {updated}/{len(rows)}")
        return {"profiles": updated}
    finally:
        conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ufcstats.com ingestor")
    parser.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill events from START to END year (e.g. 2010 2025)")
    parser.add_argument("--date", help="Ingest results around a date (default: today)")
    parser.add_argument("--event-id", help="Ingest a single event by ufcstats id")
    parser.add_argument("--fighters", action="store_true",
                        help="Refresh missing fighter profiles only")
    parser.add_argument("--force", action="store_true",
                        help="Re-ingest events even if already present")
    args = parser.parse_args()

    if args.backfill:
        result = backfill_ufc_stats(args.backfill[0], args.backfill[1], force=args.force)
    elif args.event_id:
        _conn = get_connection()
        try:
            result = _ingest_event(_conn, args.event_id, force=args.force)
        finally:
            _conn.close()
    elif args.fighters:
        result = refresh_fighter_profiles()
    else:
        result = ingest_ufc_results_for_date(args.date)

    logger.info(f"Done: {result}")

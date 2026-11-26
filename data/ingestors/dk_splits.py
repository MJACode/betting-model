"""DraftKings' own % of bets and % of handle, for the app's Scoreboard.

Matt, 2026-11-16, comparing PIT @ CIN against a competitor that shows
DraftKings' splits: ours read PIT +3.5 49% bets / 55% money, theirs a very
different handle share. Ours was Action Network's CONSENSUS pseudo-book (id
15), a blend of books, not DraftKings. Same finding on 2026-11-03 (CHI @ SEA).

SOURCE. DraftKings publishes the split itself on DK Network:
``https://dknetwork.draftkings.com/draftkings-sportsbook-betting-splits/``.
The worker probe of 2026-11-03 (worker_jobs 936774,
scripts/splits_source_probe.py) measured that page as HTTP 200, 345 KB, the
numbers in the server-rendered HTML (no iframe, no table: 120 percent cells in
div markup), laid out per game as

    JAX Jaguars @ BAL Ravens Thu 11/5 · 8:15 PM ET Selection Odds Handle Bets
    Moneyline BAL Ravens +350 22% 10% JAX Jaguars −455 78% 90%
    Spread JAX Jaguars -8.5 −115 86% 82% BAL Ravens +8.5 −105 14% 18%
    Total Over 42.5 −105 50% 50% Under 42.5 −115 50% 50%

once its tags are stripped. The parser reads that text, not the div
structure, which the probe did not record. tests/test_dk_splits.py carries the
probe's text verbatim.

WHAT IS AND IS NOT MEASURED. Only the NFL page (event group 88808, the
page's default) has been seen. Which other sports the page serves, and their
event-group ids, are read from the page's own links each pass
(`discover_event_groups`); a sport with no link found is not fetched. NCAAF
team names on DK Network have never been seen, so NCAAF matching may miss.
Each pass returns per-sport counts (games parsed, matched, unmatched), so the
first worker pass is the measurement.

WRITES. `scoreboard_splits` (one row per game/market/side, the latest
pre-start DK split, plus the first DK split seen as open_*), and every changed
split appended to `scoreboard_splits_history`. Never public_betting, which the
scorer copies onto every pick. No API key, no Odds API credits.
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

from loguru import logger

from data.ingestors.nba_public_splits_ingestor import validate_sides
from data.ingestors.scoreboard_splits import _parse_ts, append_history

SOURCE = "dk_network"
DK_URL = "https://dknetwork.draftkings.com/draftkings-sportsbook-betting-splits/"
REQUEST_TIMEOUT = 25
MAX_PAGES = 8
# Measured 2026-11-03 (worker_jobs 936774): NFL is the page's default and its
# links carry tb_eg=88808. Every other id comes from discover_event_groups.
# NBA, NHL and NCAAF measured 2026-11-26 (scripts/research_probe_2026_11_26.py dk2): the page
# asked for each id directly parsed 5 NBA, 7 NHL and 10 NCAAF games with Handle % and Bets %,
# teams of the right league. The page's own links carry only the NFL id, so discovery alone
# never found them. NBA / NCAAF are DraftKings' ids in dk_live_board.LEAGUES.
KNOWN_EVENT_GROUPS: dict[str, str] = {"NFL": "88808", "NBA": "42648", "NHL": "42133",
                                      "NCAAF": "87637"}
SPORTS: tuple[str, ...] = ("NFL", "NCAAF", "NBA", "NHL", "MLB")
# The sport names as the page's sport list prints them (the probe's text:
# "Sports NFL NBA NHL MLB WNBA UFC UFL NCAA Football NCAA Basketball ...").
_SPORT_LABELS = {"NFL": "NFL", "NBA": "NBA", "NHL": "NHL", "MLB": "MLB",
                 "NCAA Football": "NCAAF"}

_ET = ZoneInfo("America/New_York")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

_HEADER = "Selection Odds Handle Bets"
_ODDS = r"(?:[+\-−]\d{3,5}|EVEN|EV)"
_PCT = r"(\d{1,3})% (\d{1,3})%"
_ML_ROW = re.compile(rf"(\S.*?) ({_ODDS}) {_PCT}")
_SPREAD_ROW = re.compile(rf"(\S.*?) ([+\-−]?\d+(?:\.\d+)?|PK|pk|Pick|pick) ({_ODDS}) {_PCT}")
_TOTAL_ROW = re.compile(rf"(Over|Under) (\d+(?:\.\d+)?) ({_ODDS}) {_PCT}")
_SECTION = re.compile(r"\b(Moneyline|Spread|Total)\b (.*?)(?=\b(?:Moneyline|Spread|Total)\b |$)")
_WHEN = re.compile(
    r"@ (?P<home>.+?) (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) (?P<md>\d{1,2}/\d{1,2})"
    r" · (?P<time>\d{1,2}:\d{2} [AP]M) ET\s*$")


# ── page text ────────────────────────────────────────────────────────────────

def page_text(html: str) -> str:
    """The page's visible text, one space between tokens (the probe's own
    stripping, so the fixture and the live page read the same way)."""
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    text = unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def _odds(s: str) -> int | None:
    s = s.replace("−", "-")
    if s.upper() in ("EVEN", "EV"):
        return 100
    try:
        return int(s)
    except ValueError:
        return None


def _line(s: str) -> float | None:
    s = s.replace("−", "-")
    if s.lower() in ("pk", "pick"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def _game_date(md: str, now: datetime) -> str | None:
    """'11/5' -> the ET date in the year that puts it nearest `now`."""
    try:
        month, day = (int(x) for x in md.split("/"))
    except ValueError:
        return None
    today = now.astimezone(_ET).date()
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    return best.isoformat() if best else None


def parse_page(text: str, now: datetime) -> list[dict]:
    """Every game on one page: {home, away, date, sides}. `sides` is
    {(market, side): {tickets, money, value, odds}} in our orientation
    (home/away, over/under). tickets = DK's Bets %, money = DK's Handle %."""
    chunks = text.split(_HEADER)
    out = []
    for i in range(1, len(chunks)):
        head = chunks[i - 1]
        at = head.rfind(" @ ")
        m = _WHEN.search(head[at:]) if at >= 0 else None
        if not m:
            continue
        home = m.group("home").strip()
        body = chunks[i]
        sides: dict = {}
        names: set[str] = set()
        for sec in _SECTION.finditer(body):
            kind, rest = sec.group(1), sec.group(2)
            if kind == "Total":
                for r in list(_TOTAL_ROW.finditer(rest))[:2]:
                    side = r.group(1).lower()
                    sides[("totals", side)] = {
                        "value": _line(r.group(2)), "odds": _odds(r.group(3)),
                        "money": float(r.group(4)), "tickets": float(r.group(5))}
                continue
            pat = _ML_ROW if kind == "Moneyline" else _SPREAD_ROW
            market = "h2h" if kind == "Moneyline" else "spreads"
            for r in list(pat.finditer(rest))[:2]:
                name = r.group(1).strip()
                names.add(name)
                side = "home" if name == home else "away"
                if market == "h2h":
                    v = {"value": None, "odds": _odds(r.group(2)),
                         "money": float(r.group(3)), "tickets": float(r.group(4))}
                else:
                    v = {"value": _line(r.group(2)), "odds": _odds(r.group(3)),
                         "money": float(r.group(4)), "tickets": float(r.group(5))}
                sides[(market, side)] = v
        away = sorted(n for n in names if n != home)
        if len(away) != 1:
            continue
        sides = validate_sides(sides)
        sides = {k: v for k, v in sides.items()
                 if v.get("tickets") is not None or v.get("money") is not None}
        if sides:
            out.append({"home": home, "away": away[0],
                        "date": _game_date(m.group("md"), now), "sides": sides})
    return out


def discover_event_groups(html: str) -> dict[str, str]:
    """{sport: event-group id} from the page's own sport links. Only links
    whose visible text is one of _SPORT_LABELS count."""
    found: dict[str, str] = {}
    for href, label in re.findall(
            r"<a\b[^>]*href=[\"']([^\"']*tb_eg=\d+[^\"']*)[\"'][^>]*>(.*?)</a>",
            html, flags=re.S | re.I):
        name = page_text(label)
        sport = _SPORT_LABELS.get(name)
        eg = re.search(r"tb_eg=(\d+)", unescape(href))
        if sport and eg and sport not in found:
            found[sport] = eg.group(1)
    return found


# ── matching ─────────────────────────────────────────────────────────────────

def _full_names(sport: str) -> dict[str, list[str]]:
    """{our abbr: [full names]} from the odds feed's own maps."""
    if sport == "NFL":
        from config import NFL_ODDS_API_MAP as m
    elif sport == "NBA":
        from config import NBA_ODDS_API_MAP as m
    elif sport == "MLB":
        from data.ingestors.odds_ingestor import MLB_ODDS_API_MAP as m
    elif sport == "NHL":
        from data.ingestors.odds_ingestor import NHL_ODDS_API_MAP as m
    else:
        return {}
    out: dict[str, list[str]] = {}
    for full, abbr in m.items():
        out.setdefault(abbr, []).append(full)
    return out


def team_matches(sport: str, dk_name: str, our_id: str,
                 names: dict[str, list[str]] | None = None) -> bool:
    """Does DK Network's 'JAX Jaguars' name our team id? Pro sports: DK
    prints a short city then the nickname, so the nickname (everything after
    the first word) must end one of our full names for that id. 'LA Rams' and
    'LA Chargers' share the city word, which is why the city is not used.
    NCAAF: the odds feed's school resolver, which strips a mascot."""
    if sport == "NCAAF":
        try:
            from data.ingestors.cfbd_ingestor import resolve_odds_api_school
            return resolve_odds_api_school(dk_name) == our_id
        except Exception:                                     # noqa: BLE001
            return dk_name == our_id
    parts = dk_name.split(" ", 1)
    if len(parts) != 2:
        return False
    nick = parts[1].strip().lower()
    names = names if names is not None else _full_names(sport)
    return any(f.lower().endswith(" " + nick) for f in names.get(our_id, []))


def match(sport: str, parsed: dict, games: Iterable[dict],
          names: dict[str, list[str]] | None = None) -> dict | None:
    """The one slate game with both teams, nearest DK's printed date (within a
    day: DK prints the ET date, a late start can sit on our next date)."""
    hits = [g for g in games
            if team_matches(sport, parsed["home"], g.get("home_team") or "", names)
            and team_matches(sport, parsed["away"], g.get("away_team") or "", names)]
    if not hits:
        return None
    if parsed.get("date"):
        want = date.fromisoformat(parsed["date"])
        near = [g for g in hits
                if abs((date.fromisoformat(g["game_date"]) - want).days) <= 1]
        exact = [g for g in near if g["game_date"] == parsed["date"]]
        if len(exact) == 1:
            return exact[0]
        return near[0] if len(near) == 1 else None
    return hits[0] if len(hits) == 1 else None


def build_rows(sport: str, parsed_games: list[dict], games: list[dict],
               now: datetime, counts: dict | None = None) -> list[dict]:
    """Rows for scoreboard_splits from one sport's parsed games. Started games
    are skipped so the stored row stays the last pre-start split."""
    counts = counts if counts is not None else {}
    names = _full_names(sport)
    rows: list[dict] = []
    stamp = now.isoformat()
    seen: set[str] = set()
    for p in parsed_games:
        g = match(sport, p, games, names)
        if g is None:
            counts["unmatched"] = counts.get("unmatched", 0) + 1
            continue
        if g["game_id"] in seen:
            continue
        seen.add(g["game_id"])
        start = _parse_ts(g.get("commence_time"))
        if start is None or start <= now:
            counts["started"] = counts.get("started", 0) + 1
            continue
        counts["games"] = counts.get("games", 0) + 1
        for (market, side), v in sorted(p["sides"].items()):
            rows.append({
                "game_id": g["game_id"], "sport": sport, "game_date": g["game_date"],
                "market": market, "side": side,
                "bet_pct": v.get("tickets"), "money_pct": v.get("money"),
                "line_value": v.get("value"), "odds": v.get("odds"),
                "snapshot_at": stamp,
            })
    return rows


# ── fetch and write ──────────────────────────────────────────────────────────

def _default_get(params: dict | None) -> str | None:
    import requests
    try:
        r = requests.get(DK_URL, params=params or None, timeout=REQUEST_TIMEOUT,
                         headers={"User-Agent": _UA, "Accept": "text/html"})
    except Exception as exc:                                  # noqa: BLE001
        logger.warning(f"dk_splits {params}: fetch failed: {exc}")
        return None
    if r.status_code != 200:
        logger.warning(f"dk_splits {params}: HTTP {r.status_code}")
        return None
    return r.text


def fetch_sport(get: Callable[[dict | None], str | None], eg: str,
                now: datetime) -> list[dict]:
    """Every page of one event group for the next 7 days, until a page adds
    no new game."""
    out: list[dict] = []
    seen: set[tuple] = set()
    for page in range(1, MAX_PAGES + 1):
        html = get({"tb_eg": eg, "tb_edate": "n7days", "tb_emt": "0", "tb_page": str(page)})
        if not html:
            break
        new = [p for p in parse_page(page_text(html), now)
               if (p["home"], p["away"], p["date"]) not in seen]
        if not new:
            break
        for p in new:
            seen.add((p["home"], p["away"], p["date"]))
        out.extend(new)
        time.sleep(0.5)
    return out


UPSERT_SQL = """
INSERT INTO public.scoreboard_splits
    (game_id, sport, game_date, market, side, bet_pct, money_pct,
     line_value, snapshot_at, source, open_bet_pct, open_money_pct,
     open_snapshot_at, open_line_value)
VALUES
    (%(game_id)s, %(sport)s, %(game_date)s, %(market)s, %(side)s,
     %(bet_pct)s, %(money_pct)s, %(line_value)s, %(snapshot_at)s,
     'dk_network', %(bet_pct)s, %(money_pct)s, %(snapshot_at)s, %(line_value)s)
ON CONFLICT (game_id, market, side) DO UPDATE SET
    bet_pct = EXCLUDED.bet_pct,
    money_pct = EXCLUDED.money_pct,
    line_value = EXCLUDED.line_value,
    snapshot_at = EXCLUDED.snapshot_at,
    source = 'dk_network',
    -- The opening split is the first DraftKings one. A row an earlier
    -- source wrote (Action Network consensus, before 2026-11-16) is not it.
    open_bet_pct = CASE WHEN scoreboard_splits.source = 'dk_network'
                         AND scoreboard_splits.open_snapshot_at IS NOT NULL
                        THEN scoreboard_splits.open_bet_pct ELSE EXCLUDED.bet_pct END,
    open_money_pct = CASE WHEN scoreboard_splits.source = 'dk_network'
                           AND scoreboard_splits.open_snapshot_at IS NOT NULL
                          THEN scoreboard_splits.open_money_pct ELSE EXCLUDED.money_pct END,
    open_snapshot_at = CASE WHEN scoreboard_splits.source = 'dk_network'
                             AND scoreboard_splits.open_snapshot_at IS NOT NULL
                            THEN scoreboard_splits.open_snapshot_at ELSE EXCLUDED.snapshot_at END,
    open_line_value = CASE WHEN scoreboard_splits.source = 'dk_network'
                            AND scoreboard_splits.open_snapshot_at IS NOT NULL
                           THEN scoreboard_splits.open_line_value ELSE EXCLUDED.line_value END
"""


def run(conn=None, *, now: datetime | None = None,
        get: Callable[[dict | None], str | None] | None = None) -> dict:
    """One pass. Returns {'event_groups': {...}, sport: {parsed, games, rows,
    history, unmatched, started}}."""
    now = now or datetime.now(timezone.utc)
    get = get or _default_get
    today = now.astimezone(_ET).date()
    days = [(today + timedelta(days=i)).isoformat() for i in range(8)]
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    try:
        if conn.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' "
            "AND table_name = 'scoreboard_splits' AND column_name = 'open_line_value'"
        ).fetchone() is None:
            logger.info("dk_splits: scoreboard_splits migration not applied yet; nothing written")
            return {}
        landing = get(None)
        groups = dict(KNOWN_EVENT_GROUPS)
        if landing:
            groups.update(discover_event_groups(landing))
        cols = ("game_id", "sport", "game_date", "home_team", "away_team", "commence_time")
        games = [dict(zip(cols, r)) for r in conn.execute(
            "SELECT game_id, sport, game_date::text, home_team, away_team, "
            "commence_time::text FROM public.games "
            "WHERE sport = ANY(%(sports)s) AND game_date::text = ANY(%(days)s)",
            {"sports": list(SPORTS), "days": days},
        ).fetchall()]
        out: dict = {"event_groups": groups}
        for sport in SPORTS:
            eg = groups.get(sport)
            slate = [g for g in games if g["sport"] == sport]
            if not eg or not any((_parse_ts(g["commence_time"]) or now) > now for g in slate):
                continue
            parsed = fetch_sport(get, eg, now)
            counts: dict = {"parsed": len(parsed)}
            rows = build_rows(sport, parsed, slate, now, counts)
            if rows:
                conn.executemany(UPSERT_SQL, [{k: v for k, v in r.items() if k != "odds"}
                                              for r in rows])
                conn.commit()
            counts["rows"] = len(rows)
            counts["history"] = append_history(conn, rows, SOURCE)
            out[sport] = counts
        logger.info(f"dk_splits: {out}")
        return out
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    print(run())

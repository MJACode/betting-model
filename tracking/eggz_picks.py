"""Read Eggz's posts in #eggz-picks, grade them, and recap that channel only.

The model record stays in `picks`. These rows live in `capper_messages` and
`capper_picks`. A line that cannot be parsed or matched is `needs_review`.
It is stored and logged. It is not dropped, and it is not given a result.

The Oct 18 and Oct 20 posts are the grammar the tests pin: a sport/date
header, `All 1U` as the message stake, and `60 Minute ML` as `h2h_3way`.
Anything else is needs_review.

Env, all optional. Any one missing and that half no-ops:
    DISCORD_BOT_TOKEN          existing bot token (monitoring/discord_stats.py)
    DISCORD_EGGZ_CHANNEL_ID    #eggz-picks channel id
    DISCORD_EGGZ_AUTHOR_ID     his user id (username jack_mehoff123,
                               display name Dr. Eggz)
    DISCORD_WEBHOOK_EGGZ       recaps only. Never #results, never X.

The bot needs View Channel, Read Message History, and the Message Content
intent. Without that intent Discord returns an empty body.
"""

from __future__ import annotations

import difflib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

import config
from data.ingestors.book_team_map import MLB_NICKNAMES
from tracking.clv_math import same_book_clv
from tracking.discord_notifier import (
    ET,
    _post,
    _tally,
    _tally_line,
    clv_line,
    period_heading,
    recap_periods_due,
    in_daily_recap_window,
    in_period_recap_window,
    sport_in_progress,
)
from tracking.paper_tracker import (
    _closing_odds,
    _closing_prop_odds,
    _compute_result,
    _ip_to_outs,
)

logger = logging.getLogger(__name__)

API = "https://discord.com/api/v10"
_PAGE = 100
_BACKFILL_PAGES = 20
_PROP_STATS = {
    "hits": ("batter", "hits", "batter_hits"),
    "hit": ("batter", "hits", "batter_hits"),
    "home runs": ("batter", "home_runs", "batter_home_runs"),
    "home run": ("batter", "home_runs", "batter_home_runs"),
    "hrs": ("batter", "home_runs", "batter_home_runs"),
    "hr": ("batter", "home_runs", "batter_home_runs"),
    "rbis": ("batter", "rbi", "batter_rbis"),
    "rbi": ("batter", "rbi", "batter_rbis"),
    "runs": ("batter", "runs", "batter_runs_scored"),
    "total bases": ("batter", "total_bases", "batter_total_bases"),
    "stolen bases": ("batter", "stolen_bases", "batter_stolen_bases"),
    "sb": ("batter", "stolen_bases", "batter_stolen_bases"),
    "strikeouts": ("pitcher", "p_strikeouts", "pitcher_strikeouts"),
    "ks": ("pitcher", "p_strikeouts", "pitcher_strikeouts"),
    "k": ("pitcher", "p_strikeouts", "pitcher_strikeouts"),
    "earned runs": ("pitcher", "p_earned_runs", "pitcher_earned_runs"),
    "outs": ("pitcher", "COMPUTE_OUTS", "pitcher_outs"),
    "walks": ("batter", "walks", "batter_walks"),
    "pitcher walks": ("pitcher", "p_walks", "pitcher_walks"),
}
_STAT_ALT = "|".join(sorted(_PROP_STATS, key=len, reverse=True))
_PRICE_RE = re.compile(r"(?<![\d.])([+-]\d{3,})(?!\d)")
_STAKE_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*u(?:nits?)?\b", re.I)
_SPREAD_RE = re.compile(r"(?<![\d.])([+-]\d{1,2}(?:\.\d+)?)(?!\d)")
_LINE_NUM_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)(?!\d)")
_EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D✅❌✔✖]+")
_ALL_STAKE_RE = re.compile(r"^all\s+(\d+(?:\.\d+)?)\s*u(?:nits?)?$", re.I)
_REG_RE = re.compile(
    r"\b(?:60\s*min(?:ute)?s?\s*ml|reg(?:ulation)?\s*ml|3\s*[- ]?way(?:\s*ml)?)\b",
    re.I)
_SLATE_RE = re.compile(
    r"^(?P<sport>nhl|nfl|mlb|nba|wnba|ncaaf|ufc)\b"
    r"(?:\s+(?P<weekday>[A-Za-z]+day))?"
    r"(?:\s+(?P<mon>[A-Za-z]+)\.?\s+(?P<day>\d{1,2}))?"
    r"\s*$",
    re.I)
_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_FUZZY_CUTOFF = 0.88


def _token() -> str:
    return os.environ.get("DISCORD_BOT_TOKEN", "").strip()


def configured_to_read() -> bool:
    return bool(_token() and config.DISCORD_EGGZ_CHANNEL_ID
                and config.DISCORD_EGGZ_AUTHOR_ID)


def configured_to_post() -> bool:
    return bool(config.DISCORD_WEBHOOK_EGGZ)


_SKIP_LAST = {"team", "fc", "club"}


def _add_last(add, full: str, sport: str, abbr: str) -> None:
    last = full.split()[-1]
    if last.lower() in _SKIP_LAST:
        return
    add(last, sport, abbr)


def _aliases() -> dict[str, list[tuple[str, str]]]:
    """Lowercase token -> [(sport, abbrev), ...]. Built once."""
    if getattr(_aliases, "cache", None) is not None:
        return _aliases.cache
    out: dict[str, list[tuple[str, str]]] = {}

    def add(token: str, sport: str, abbr: str) -> None:
        key = " ".join(token.lower().replace(".", " ").split())
        if not key:
            return
        pair = (sport, abbr.upper())
        bucket = out.setdefault(key, [])
        if pair not in bucket:
            bucket.append(pair)

    for nick, abbr in MLB_NICKNAMES.items():
        add(nick, "MLB", abbr)
        add(abbr, "MLB", abbr)
    for full, abbr in config.NFL_ODDS_API_MAP.items():
        add(full, "NFL", abbr)
        add(abbr, "NFL", abbr)
        _add_last(add, full, "NFL", abbr)
    for full, abbr in config.NBA_ODDS_API_MAP.items():
        add(full, "NBA", abbr)
        add(abbr, "NBA", abbr)
        _add_last(add, full, "NBA", abbr)
    for full, abbr in config.WNBA_ODDS_API_MAP.items():
        add(full, "WNBA", abbr)
        add(abbr, "WNBA", abbr)
        _add_last(add, full, "WNBA", abbr)
    from tracking.x_teams import _NHL
    for abbr, nick in _NHL.items():
        spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", nick).lower()
        add(abbr, "NHL", abbr)
        add(spaced, "NHL", abbr)
        add(nick, "NHL", abbr)
    # His spelling of Canadiens, on the Oct 20 slate.
    add("canadians", "NHL", "MTL")
    _aliases.cache = out
    return out


def _teams_in(text: str) -> list[tuple[str, str, str]]:
    """Longest alias first. Returns (token, sport, abbrev) without overlap."""
    aliases = _aliases()
    keys = sorted(aliases, key=len, reverse=True)
    low = " ".join(text.lower().replace(".", " ").split())
    found: list[tuple[int, str, str, str]] = []
    occupied = [False] * (len(low) + 1)
    for key in keys:
        start = 0
        while True:
            i = low.find(key, start)
            if i < 0:
                break
            end = i + len(key)
            bounded = (
                (i == 0 or not low[i - 1].isalnum())
                and (end == len(low) or not low[end].isalnum())
            )
            if bounded and not any(occupied[i:end]):
                for sport, abbr in aliases[key]:
                    found.append((i, key, sport, abbr))
                for j in range(i, end):
                    occupied[j] = True
                break
            start = i + 1
    found.sort()
    return [(key, sport, abbr) for _i, key, sport, abbr in found]


def _strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text or "")


def _price_and_stake(text: str, default_stake: float = 1.0
                     ) -> tuple[str, float | None, float]:
    stake = default_stake
    m = _STAKE_RE.search(text)
    if m:
        stake = float(m.group(1))
        text = (text[:m.start()] + text[m.end():]).strip()
    price = None
    pm = _PRICE_RE.search(text)
    if pm:
        price = float(pm.group(1))
        text = (text[:pm.start()] + " " + text[pm.end():]).strip()
    text = text.replace("(", " ").replace(")", " ")
    text = " ".join(text.split())
    return text, price, stake


def _slate_date(month: int, day: int, posted: datetime | None) -> str | None:
    year = posted.year if posted else datetime.now(timezone.utc).year
    try:
        slate = datetime(year, month, day).date()
    except ValueError:
        return None
    if posted:
        delta = (slate - posted.date()).days
        if delta > 180:
            slate = slate.replace(year=year - 1)
        elif delta < -180:
            slate = slate.replace(year=year + 1)
    return slate.isoformat()


def _slate_header(text: str, posted: datetime | None) -> dict | None:
    """'NHL Sunday Oct. 18' is the sport and the slate date, not a bet."""
    m = _SLATE_RE.match(text.strip())
    if not m:
        return None
    out = {"sport": m.group("sport").upper()}
    if not m.group("mon"):
        return out
    month = _MONTHS.get(m.group("mon").lower())
    if not month:
        return None
    slate = _slate_date(month, int(m.group("day")), posted)
    if not slate:
        return None
    out["slate_date"] = slate
    return out


def _fuzzy_one(text: str, sport: str) -> str | None:
    """One nickname in `sport` within one edit, or None when it is not unique."""
    aliases = _aliases()
    low = " ".join(text.lower().replace(".", " ").split())
    phrases = {low}
    phrases.update(w for w in low.split() if w.isalpha() and len(w) >= 4)
    scored: list[tuple[float, str]] = []
    for key, pairs in aliases.items():
        if not any(s == sport for s, _abbr in pairs):
            continue
        if len(key) < 5:
            continue
        for phrase in phrases:
            if abs(len(phrase) - len(key)) > 2:
                continue
            ratio = difflib.SequenceMatcher(None, phrase, key).ratio()
            if ratio >= _FUZZY_CUTOFF:
                for s, abbr in pairs:
                    if s == sport:
                        scored.append((ratio, abbr))
    if not scored:
        return None
    scored.sort(reverse=True)
    top = scored[0][0]
    close = {abbr for ratio, abbr in scored if top - ratio <= 0.05}
    if len(close) != 1:
        return None
    return close.pop()


def _spread_number(text: str) -> tuple[str, float | None]:
    m = _SPREAD_RE.search(text)
    if not m:
        return text, None
    return (text[:m.start()] + " " + text[m.end():]).strip(), float(m.group(1))


def parse_message(body: str, posted_at: datetime | None = None
                  ) -> tuple[list[dict], list[dict]]:
    """(legs, reviews). A review is a line that was not turned into a bet.

    A matchup line (`NYY @ BOS`) sets the game for the lines under it.
    A sport/date line (`NHL Sunday Oct. 18`) sets the sport and the slate
    date. `All 1U` sets the stake for the lines that do not name their own.
    Neither of those is a bet. Stake defaults to 1 unit to win. A missing
    price stays missing.
    """
    legs: list[dict] = []
    reviews: list[dict] = []
    context: dict | None = None
    default_stake = 1.0
    lines = [_strip_emoji(ln).strip() for ln in (body or "").splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("#")]
    if not lines:
        reviews.append({"line_no": 1, "raw": body or "", "reason": "empty"})
        return legs, reviews
    for n, raw in enumerate(lines, start=1):
        slate = _slate_header(raw, posted_at)
        if slate:
            context = dict(context or {})
            context.update(slate)
            continue
        all_stake = _ALL_STAKE_RE.match(raw.strip())
        if all_stake:
            default_stake = float(all_stake.group(1))
            continue
        stripped, price, stake = _price_and_stake(raw, default_stake)
        header = _matchup_header(stripped)
        if header and price is None and not _STAKE_RE.search(raw):
            context = dict(context or {})
            context.update(header)
            continue
        leg = _parse_line(stripped, price, stake, context, raw)
        if leg is None:
            reviews.append({"line_no": n, "raw": raw, "reason": "unparsed"})
            continue
        leg["line_no"] = n
        leg["sport_hint"] = (context or {}).get("sport")
        leg["slate_date"] = (context or {}).get("slate_date")
        legs.append(leg)
    return legs, reviews


def _matchup_header(text: str) -> dict | None:
    m = re.match(r"^(?P<a>.+?)\s+(?:@|vs\.?|at)\s+(?P<b>.+)$", text, re.I)
    if not m:
        return None
    a, b = m.group("a").strip(), m.group("b").strip()
    if _teams_in(a) and _teams_in(b) and not re.search(r"\b(over|under|ml)\b", text, re.I):
        return {"away_text": a, "home_text": b, "raw": text}
    return None


def _parse_line(text: str, price, stake, context, raw: str) -> dict | None:
    prop = re.match(
        rf"^(?P<player>.+?)\s+(?P<side>over|under|o|u)\s+"
        rf"(?P<line>\d+(?:\.\d+)?)\s+(?P<stat>{_STAT_ALT})\b",
        text, re.I)
    if prop:
        stat = prop.group("stat").lower()
        kind, col, market = _PROP_STATS[stat]
        side = prop.group("side").lower()
        side = {"o": "over", "u": "under"}.get(side, side)
        return {
            "market": "prop", "side": side, "line": float(prop.group("line")),
            "price": price, "stake_units": stake,
            "player_name": prop.group("player").strip(" -"),
            "prop_stat": col, "prop_kind": kind, "prop_market": market,
            "team_text": None, "away_text": (context or {}).get("away_text"),
            "home_text": (context or {}).get("home_text"), "raw": raw,
        }
    ou = re.match(
        r"^(?:(?P<pre>.+?)\s+)?(?P<side>over|under|o|u)\s+(?P<line>\d+(?:\.\d+)?)\b\s*(?P<post>.*)$",
        text, re.I)
    if ou:
        side = ou.group("side").lower()
        side = {"o": "over", "u": "under"}.get(side, side)
        rest = " ".join(p for p in (ou.group("pre"), ou.group("post")) if p).strip()
        away, home = _split_sides(rest, context)
        return {
            "market": "totals", "side": side, "line": float(ou.group("line")),
            "price": price, "stake_units": stake, "player_name": None,
            "prop_stat": None, "prop_kind": None, "prop_market": None,
            "team_text": None, "away_text": away, "home_text": home, "raw": raw,
        }
    reg = _REG_RE.search(text)
    if reg:
        team = (text[:reg.start()] + " " + text[reg.end():])
        team = " ".join(team.split())
        return {
            "market": "h2h_3way", "side": None, "line": None, "price": price,
            "stake_units": stake, "player_name": None, "prop_stat": None,
            "prop_kind": None, "prop_market": None, "team_text": team,
            "away_text": (context or {}).get("away_text"),
            "home_text": (context or {}).get("home_text"), "raw": raw,
        }
    if re.search(r"\b(ml|moneyline)\b", text, re.I):
        team = re.sub(r"\b(ml|moneyline)\b", " ", text, flags=re.I)
        team = " ".join(team.split())
        return {
            "market": "h2h", "side": None, "line": None, "price": price,
            "stake_units": stake, "player_name": None, "prop_stat": None,
            "prop_kind": None, "prop_market": None, "team_text": team,
            "away_text": (context or {}).get("away_text"),
            "home_text": (context or {}).get("home_text"), "raw": raw,
        }
    rest, spread = _spread_number(text)
    if spread is not None and abs(spread) < 100:
        return {
            "market": "spreads", "side": None, "line": spread, "price": price,
            "stake_units": stake, "player_name": None, "prop_stat": None,
            "prop_kind": None, "prop_market": None, "team_text": rest,
            "away_text": (context or {}).get("away_text"),
            "home_text": (context or {}).get("home_text"), "raw": raw,
        }
    return None


def _split_sides(rest: str, context) -> tuple[str | None, str | None]:
    if rest:
        m = re.match(r"^(?P<a>.+?)\s+(?:@|vs\.?|at)\s+(?P<b>.+)$", rest, re.I)
        if m:
            return m.group("a").strip(), m.group("b").strip()
    if context:
        return context.get("away_text"), context.get("home_text")
    return None, None


def choose_game(candidates: list[dict], posted_at: datetime) -> tuple[dict | None, str | None]:
    """The soonest game that has not started, or a review reason.

    Two sports in the window, or two games within 18 hours, are not a guess.
    A post after every candidate has started is posted_after_start.
    """
    future = [c for c in candidates if c["commence"] > posted_at]
    if not future:
        if candidates:
            return None, "posted_after_start"
        return None, "no_game"
    sports = {c["sport"] for c in future}
    if len(sports) > 1:
        return None, "ambiguous_team"
    future.sort(key=lambda c: c["commence"])
    nxt = [c for c in future[1:]
           if c["commence"] - future[0]["commence"] <= timedelta(hours=18)]
    if nxt:
        return None, "ambiguous_game"
    return future[0], None


def _parse_ts(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        ts = value
    else:
        try:
            ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def units_for_result(stake_units, price, result: str) -> tuple[float, float]:
    """(profit, risked). 1u is 1 unit to win. A missing price is the bare stake.

    No -110 is filled in. A push and a NO_ACTION laid nothing.
    """
    from tracking.discord_notifier import _decimal_or_none
    try:
        u = float(stake_units)
    except (TypeError, ValueError):
        u = 1.0
    if u <= 0:
        u = 1.0
    if result not in ("WIN", "LOSS"):
        return 0.0, 0.0
    dec = _decimal_or_none(price)
    if dec is None or dec <= 1.0:
        return (u, u) if result == "WIN" else (-u, u)
    risk = u / (dec - 1.0)
    return (u, risk) if result == "WIN" else (-risk, risk)


def fetch_channel_messages(channel_id: str, *, after: str | None = None,
                           before: str | None = None) -> list[dict] | None:
    """One Discord page. None means the call failed and the cursor must stay."""
    params: dict[str, str | int] = {"limit": _PAGE}
    if after:
        params["after"] = after
    if before:
        params["before"] = before
    try:
        r = requests.get(
            f"{API}/channels/{channel_id}/messages",
            params=params,
            headers={"Authorization": f"Bot {_token()}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.error(f"Eggz read failed: {exc}")
        return None
    if r.status_code == 429:
        logger.error("Eggz read rate-limited (429); cursor left where it was")
        return None
    if r.status_code in (401, 403, 404):
        logger.error(f"Eggz read refused ({r.status_code})")
        return None
    if r.status_code >= 300:
        logger.error(f"Eggz read HTTP {r.status_code}")
        return None
    body = r.json()
    if not isinstance(body, list):
        logger.error("Eggz read returned a non-list")
        return None
    return body


def _snow(message_id: str) -> int:
    try:
        return int(message_id)
    except (TypeError, ValueError):
        return 0


def ingest_messages(conn, fetch=fetch_channel_messages) -> int:
    """Store new messages from the configured author. Returns rows written.

    The cursor is the newest snowflake examined, including other authors,
    so the next poll asks Discord for messages after that id. The first
    runs walk backward until a short page, then forward.
    """
    if not configured_to_read():
        return 0
    channel = config.DISCORD_EGGZ_CHANNEL_ID
    author = config.DISCORD_EGGZ_AUTHOR_ID
    cur = conn.execute(
        "SELECT newest_id, oldest_id, backfill_done FROM capper_ingest_cursor "
        "WHERE channel_id = %s", (channel,)).fetchone()
    newest, oldest, done = (cur if cur else (None, None, False))
    written = 0
    if not done:
        pages = 0
        while pages < _BACKFILL_PAGES:
            batch = fetch(channel, before=oldest)
            if batch is None:
                return written
            if not batch:
                done = True
                break
            batch_ids = [str(m.get("id")) for m in batch if m.get("id")]
            if not batch_ids:
                logger.error("Eggz page had no message ids; cursor left where it was")
                conn.commit()
                return written
            written += _store_batch(conn, batch, channel, author)
            oldest = min(batch_ids, key=_snow)
            newest = max([newest, max(batch_ids, key=_snow)], key=lambda x: _snow(x or "0"))
            pages += 1
            if len(batch) < _PAGE:
                done = True
            _save_cursor(conn, channel, newest, oldest, done)
            if done or pages >= _BACKFILL_PAGES:
                break
        if not done:
            conn.commit()
            return written
    batch = fetch(channel, after=newest)
    if batch is None:
        conn.commit()
        return written
    if batch:
        batch_ids = [str(m.get("id")) for m in batch if m.get("id")]
        if not batch_ids:
            logger.error("Eggz page had no message ids; cursor left where it was")
        else:
            written += _store_batch(conn, batch, channel, author)
            newest = max(batch_ids, key=_snow)
            _save_cursor(conn, channel, newest, oldest, True)
    _refresh_edits(conn, fetch, channel, author)
    conn.commit()
    return written


def _save_cursor(conn, channel, newest, oldest, done) -> None:
    conn.execute(
        "INSERT INTO capper_ingest_cursor "
        "(channel_id, newest_id, oldest_id, backfill_done, updated_at) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (channel_id) DO UPDATE SET "
        "newest_id = EXCLUDED.newest_id, oldest_id = EXCLUDED.oldest_id, "
        "backfill_done = EXCLUDED.backfill_done, updated_at = EXCLUDED.updated_at",
        (channel, newest, oldest, bool(done), datetime.now(timezone.utc).isoformat()),
    )


def _store_batch(conn, batch: list[dict], channel: str, author: str) -> int:
    n = 0
    for msg in batch:
        if str((msg.get("author") or {}).get("id")) != str(author):
            continue
        if _upsert_message(conn, msg, channel):
            n += 1
    return n


def _upsert_message(conn, msg: dict, channel: str) -> bool:
    mid = str(msg.get("id") or "")
    if not mid:
        return False
    author = msg.get("author") or {}
    body = msg.get("content") or ""
    posted = _parse_ts(msg.get("timestamp"))
    edited = _parse_ts(msg.get("edited_timestamp"))
    if posted is None:
        _flag_message(conn, mid, channel, author, body or "", datetime.now(timezone.utc),
                      "needs_review", "no timestamp")
        return True
    existing = conn.execute(
        "SELECT body, edited_at FROM capper_messages WHERE message_id = %s",
        (mid,)).fetchone()
    if existing and existing[0] == body and _parse_ts(existing[1]) == edited:
        return False
    graded = conn.execute(
        "SELECT 1 FROM capper_picks WHERE message_id = %s AND status = 'graded' LIMIT 1",
        (mid,)).fetchone()
    conn.execute(
        "INSERT INTO capper_messages (message_id, channel_id, author_id, "
        "author_username, author_display, body, posted_at, edited, edited_at, "
        "parse_status, parse_note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (message_id) DO UPDATE SET body = EXCLUDED.body, "
        "edited = EXCLUDED.edited, edited_at = EXCLUDED.edited_at, "
        "author_username = EXCLUDED.author_username, "
        "author_display = EXCLUDED.author_display",
        (mid, channel, str(author.get("id") or ""),
         author.get("username"), author.get("global_name") or author.get("username"),
         body, posted.isoformat(), edited is not None,
         edited.isoformat() if edited else None,
         "parsed", None),
    )
    if graded:
        return True
    _replace_legs(conn, mid, body, posted)
    return True


def _flag_message(conn, mid, channel, author, body, posted, status, note) -> None:
    conn.execute(
        "INSERT INTO capper_messages (message_id, channel_id, author_id, "
        "author_username, author_display, body, posted_at, edited, parse_status, "
        "parse_note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (message_id) DO NOTHING",
        (mid, channel, str((author or {}).get("id") or ""),
         (author or {}).get("username"),
         (author or {}).get("global_name"),
         body, posted.isoformat(), False, status, note),
    )
    _surface_review(conn, mid, note)


def _replace_legs(conn, message_id: str, body: str, posted: datetime) -> None:
    prev = conn.execute(
        "SELECT parse_note FROM capper_messages WHERE message_id = %s",
        (message_id,)).fetchone()
    old_note = prev[0] if prev else None
    conn.execute(
        "DELETE FROM capper_picks WHERE message_id = %s AND status <> 'graded'",
        (message_id,))
    legs, reviews = parse_message(body, posted)
    note_parts = []
    for leg in legs:
        game, reason = _match_leg(conn, leg, posted)
        if reason:
            _insert_pick(conn, message_id, leg, posted, "needs_review", reason, game)
            note_parts.append(f"line {leg['line_no']}: {reason}")
        else:
            _insert_pick(conn, message_id, leg, posted, "pending", None, game)
    for rev in reviews:
        _insert_review(conn, message_id, rev, posted)
        note_parts.append(f"line {rev['line_no']}: {rev['reason']}")
    status = "needs_review" if note_parts else "parsed"
    note = "; ".join(note_parts)[:500] or None
    conn.execute(
        "UPDATE capper_messages SET parse_status = %s, parse_note = %s "
        "WHERE message_id = %s", (status, note, message_id))
    if note_parts and note != old_note:
        _surface_review(conn, message_id, note)


def _insert_review(conn, message_id, rev, posted) -> None:
    conn.execute(
        "INSERT INTO capper_picks (message_id, line_no, status, review_reason, "
        "stake_units, posted_at) VALUES (%s,%s,'needs_review',%s,1,%s) "
        "ON CONFLICT (message_id, line_no) DO NOTHING",
        (message_id, rev["line_no"], f"{rev['reason']}: {rev['raw'][:240]}",
         posted.isoformat()),
    )


def _insert_pick(conn, message_id, leg, posted, status, reason, game) -> None:
    g = game or {}
    conn.execute(
        "INSERT INTO capper_picks (message_id, line_no, status, review_reason, "
        "sport, game_id, game_date, home_team, away_team, commence_time, market, "
        "side, line, price, stake_units, player_name, prop_stat, prop_market, "
        "posted_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (message_id, line_no) DO UPDATE SET status = EXCLUDED.status, "
        "review_reason = EXCLUDED.review_reason, sport = EXCLUDED.sport, "
        "game_id = EXCLUDED.game_id, game_date = EXCLUDED.game_date, "
        "home_team = EXCLUDED.home_team, away_team = EXCLUDED.away_team, "
        "commence_time = EXCLUDED.commence_time, market = EXCLUDED.market, "
        "side = EXCLUDED.side, line = EXCLUDED.line, price = EXCLUDED.price, "
        "stake_units = EXCLUDED.stake_units, player_name = EXCLUDED.player_name, "
        "prop_stat = EXCLUDED.prop_stat, prop_market = EXCLUDED.prop_market",
        (message_id, leg["line_no"], status, reason, g.get("sport"), g.get("game_id"),
         g.get("game_date"), g.get("home_team"), g.get("away_team"),
         g.get("commence_time"), leg["market"], g.get("side") or leg.get("side"),
         leg.get("line"), leg.get("price"), leg.get("stake_units") or 1,
         leg.get("player_name"), leg.get("prop_stat"), leg.get("prop_market"),
         posted.isoformat()),
    )


def _match_leg(conn, leg: dict, posted: datetime) -> tuple[dict | None, str | None]:
    away_text, home_text = leg.get("away_text"), leg.get("home_text")
    team_text = leg.get("team_text")
    if leg["market"] in ("h2h", "h2h_3way", "spreads") and not (team_text or "").strip():
        return None, "no_team"
    if leg["market"] == "totals" and not (away_text and home_text):
        return None, "no_matchup"
    if leg["market"] == "prop" and not (away_text and home_text):
        return None, "no_matchup"
    candidates = _candidate_games(conn, leg, posted)
    if candidates and candidates[0].get("ambiguous"):
        return None, "ambiguous_team"
    chosen, reason = choose_game(candidates, posted)
    if reason or chosen is None:
        return None, reason or "no_game"
    side = _side_for(leg, chosen)
    if side is None:
        return None, "team_not_in_game"
    chosen = dict(chosen)
    chosen["side"] = side
    if leg["market"] == "spreads":
        # The number in the post is that team's spread. Settlement wants the
        # HOME number (CLAUDE.md §4).
        team_line = float(leg["line"])
        chosen_line = team_line if side == "home" else -team_line
        leg["line"] = chosen_line
    return chosen, None


def _side_for(leg, game) -> str | None:
    if leg["market"] in ("totals", "prop"):
        return leg.get("side")
    hits = _teams_in(leg.get("team_text") or "")
    if not hits:
        return None
    abbrs = {abbr for _tok, _sport, abbr in hits if _sport == game["sport"]}
    if not abbrs:
        abbrs = {abbr for _tok, _sport, abbr in hits}
    if game["home_team"] in abbrs and game["away_team"] not in abbrs:
        return "home"
    if game["away_team"] in abbrs and game["home_team"] not in abbrs:
        return "away"
    return None


def _candidate_games(conn, leg, posted: datetime) -> list[dict]:
    start = (posted - timedelta(hours=6)).isoformat()
    end = (posted + timedelta(days=7)).isoformat()
    away_text, home_text = leg.get("away_text"), leg.get("home_text")
    if away_text and home_text:
        pairs = _pair_teams(away_text, home_text)
        if leg.get("sport_hint"):
            pairs = [p for p in pairs if p[0] == leg["sport_hint"]]
        if not pairs:
            return []
        rows = []
        for sport, away, home in pairs:
            rows.extend(conn.execute(
                "SELECT game_id, sport, game_date, home_team, away_team, "
                "commence_time, home_score, away_score, home_win, home_win_reg, "
                "went_to_ot FROM games WHERE sport = %s AND home_team = %s "
                "AND away_team = %s AND commence_time::timestamptz BETWEEN %s::timestamptz "
                "AND %s::timestamptz",
                (sport, home, away, start, end)).fetchall())
        return [_game_dict(r) for r in rows]
    hits = _teams_in(leg.get("team_text") or "")
    sport_hint = leg.get("sport_hint")
    if sport_hint:
        hits = [h for h in hits if h[1] == sport_hint]
        if not hits:
            abbr = _fuzzy_one(leg.get("team_text") or "", sport_hint)
            if abbr:
                hits = [(leg.get("team_text") or "", sport_hint, abbr)]
        if len({h[2] for h in hits}) > 1:
            return [{"ambiguous": True}]
    if not hits:
        return []
    slate = leg.get("slate_date")
    rows = []
    seen = set()
    for _tok, sport, abbr in hits:
        sql = (
            "SELECT game_id, sport, game_date, home_team, away_team, "
            "commence_time, home_score, away_score, home_win, home_win_reg, "
            "went_to_ot FROM games WHERE sport = %s AND (home_team = %s OR "
            "away_team = %s) AND commence_time::timestamptz BETWEEN %s::timestamptz "
            "AND %s::timestamptz"
        )
        params: list = [sport, abbr, abbr, start, end]
        if slate:
            sql += " AND game_date = %s"
            params.append(slate)
        found = conn.execute(sql, tuple(params)).fetchall()
        for row in found:
            if row[0] not in seen:
                seen.add(row[0])
                rows.append(row)
    return [_game_dict(r) for r in rows]


def _pair_teams(away_text, home_text) -> list[tuple[str, str, str]]:
    aways = _teams_in(away_text)
    homes = _teams_in(home_text)
    pairs = []
    for _a, sa, aa in aways:
        for _b, sb, bb in homes:
            if sa == sb:
                pairs.append((sa, aa, bb))
    return pairs


def _game_dict(row) -> dict:
    (game_id, sport, game_date, home, away, commence,
     home_score, away_score, home_win, home_win_reg, went_to_ot) = row
    ts = _parse_ts(commence)
    return {
        "game_id": game_id, "sport": sport, "game_date": game_date,
        "home_team": home, "away_team": away, "commence_time": commence,
        "commence": ts or datetime.max.replace(tzinfo=timezone.utc),
        "home_score": home_score, "away_score": away_score,
        "home_win": home_win, "home_win_reg": home_win_reg,
        "went_to_ot": went_to_ot or 0,
    }


def _refresh_edits(conn, fetch, channel, author) -> None:
    """The newest page, so an edit of a recent post is stored.

    Graded legs are left alone. The cursor does not move backward.
    """
    batch = fetch(channel)
    if not batch:
        return
    _store_batch(conn, batch, channel, author)


def _surface_review(conn, message_id: str, note: str) -> None:
    logger.error(f"Eggz message {message_id} needs review: {note}")
    url = config.DISCORD_WEBHOOK_OPS
    if not url:
        return
    kind = "eggz_review"
    if conn.execute(
        "SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = %s",
        (message_id, kind)).fetchone():
        return
    posted = _post(url, {"content": f"Eggz pick needs review ({message_id}): {note[:1500]}"})
    if not posted:
        return
    conn.execute(
        "INSERT INTO push_sent (lock_key, kind, sent_at, message_id) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT (lock_key, kind) DO NOTHING",
        (message_id, kind, datetime.now(ET).isoformat(), posted),
    )


def reparse_stored(conn) -> int:
    """Re-read stored messages whose parse was needs_review.

    A graded leg is left as it was. A message that already parsed is left
    as it was, so a later grade is not wiped on the next poll.
    """
    rows = conn.execute(
        "SELECT message_id, body, posted_at, parse_status FROM capper_messages"
    ).fetchall()
    n = 0
    for mid, body, posted, status in rows:
        if status != "needs_review":
            continue
        graded = conn.execute(
            "SELECT 1 FROM capper_picks WHERE message_id = %s AND status = 'graded' "
            "LIMIT 1", (mid,)).fetchone()
        if graded:
            continue
        ts = _parse_ts(posted)
        if ts is None or body is None:
            continue
        _replace_legs(conn, mid, body, ts)
        n += 1
    if n:
        conn.commit()
    return n


def grade_pending(conn) -> int:
    """Grade pending legs whose game is final. Returns how many settled.

    Stored messages that are still needs_review are reparsed first, so a
    parser fix reaches rows already in capper_messages.

    Game markets use `_compute_result` and the DraftKings pre-start close
    (`_closing_odds`, `same_book_clv`). MLB props use the same player_game_log
    columns the prop settler reads. A final with no grade becomes
    needs_review, so the recap is not held open by a leg that cannot settle.
    """
    reparse_stored(conn)
    rows = conn.execute(
        "SELECT id, game_id, market, side, line, price, stake_units, "
        "player_name, prop_stat, prop_market, commence_time, sport "
        "FROM capper_picks WHERE game_id IS NOT NULL AND ("
        "status = 'pending' OR (status = 'needs_review' AND "
        "review_reason = 'no_regulation_score'))"
    ).fetchall()
    n = 0
    for row in rows:
        if _grade_one(conn, row):
            n += 1
    if n:
        conn.commit()
    return n


def _grade_one(conn, row) -> bool:
    (pid, game_id, market, side, line, price, stake, player, prop_stat,
     prop_market, commence, sport) = row
    prop_kind = "pitcher" if prop_stat in {
        "p_strikeouts", "p_walks", "p_hits_allowed", "p_earned_runs",
        "COMPUTE_OUTS"} else "batter"
    game = conn.execute(
        "SELECT home_score, away_score, home_win, home_win_reg, went_to_ot, "
        "commence_time, game_date FROM games WHERE game_id = %s",
        (game_id,)).fetchone()
    if not game or game[0] is None or game[1] is None:
        return False
    home_score, away_score, home_win, home_win_reg, went_to_ot, commence_db, _gd = game
    if market == "prop":
        return _grade_prop(conn, pid, game_id, side, line, price, stake, player,
                           prop_stat, prop_kind, prop_market, commence or commence_db,
                           sport)
    if market == "h2h_3way":
        return _grade_regulation(conn, pid, game_id, side, price, stake,
                                 commence or commence_db, home_win_reg, went_to_ot)
    if home_win is None and home_score is not None and away_score is not None:
        if float(home_score) > float(away_score):
            home_win = 1
        elif float(home_score) < float(away_score):
            home_win = 0
    spread_home = float(line) if market == "spreads" and line is not None else None
    total_line = float(line) if market == "totals" and line is not None else None
    result, _flat, _kelly = _compute_result(
        side or "", market, float(home_score), float(away_score),
        home_win, home_win_reg, int(went_to_ot or 0),
        price, spread_home, total_line, 0.0)
    if result == "NO_ACTION":
        _mark_review(conn, pid, "ungraded")
        return True
    profit, risked = units_for_result(stake, price, result)
    clv, close_px, beat = _game_clv(
        conn, game_id, market, side, line, price, commence or commence_db)
    _write_grade(conn, pid, result, profit, risked, clv, close_px, beat)
    return True


def _regulation_from_game(side, home_win_reg, went_to_ot) -> str | None:
    """60-minute result from a final's `went_to_ot` and `home_win_reg`.

    `went_to_ot = 1` is a regulation tie, so both sides lose. `went_to_ot = 0`
    follows `home_win_reg` (1 home won in regulation, 0 the away side did).
    A missing field returns None and the caller leaves the leg needs_review.
    """
    if side not in ("home", "away") or home_win_reg is None or went_to_ot is None:
        return None
    try:
        ot = int(went_to_ot)
        reg = int(home_win_reg)
    except (TypeError, ValueError):
        return None
    if ot == 1:
        return "LOSS"
    if ot != 0 or reg not in (0, 1):
        return None
    won = (reg == 1) if side == "home" else (reg == 0)
    return "WIN" if won else "LOSS"


def _grade_regulation(conn, pid, game_id, side, price, stake, commence,
                      home_win_reg, went_to_ot) -> bool:
    """60-minute ML. A regulation tie, including OT/SO, is a loss for either side.

    Period rows win when any exist: the score is the sum of the three period
    columns, and a tie is a loss. A final with no period row uses `went_to_ot`
    and `home_win_reg` when both are present. Otherwise the leg is
    needs_review. The full-game moneyline result is not used. The caller has
    already required a final (both scores present).
    """
    rows = conn.execute(
        "SELECT home_p1, home_p2, home_p3, away_p1, away_p2, away_p3 "
        "FROM nhl_period_scores WHERE game_id = %s",
        (game_id,)).fetchall()
    if not rows:
        result = _regulation_from_game(side, home_win_reg, went_to_ot)
        if result is None:
            return _mark_review(conn, pid, "no_regulation_score")
        profit, risked = units_for_result(stake, price, result)
        clv, close_px, beat = _game_clv(
            conn, game_id, "h2h_3way", side, None, price, commence)
        _write_grade(conn, pid, result, profit, risked, clv, close_px, beat)
        return True
    sums = []
    for home_p1, home_p2, home_p3, away_p1, away_p2, away_p3 in rows:
        try:
            sums.append((
                int(home_p1) + int(home_p2) + int(home_p3),
                int(away_p1) + int(away_p2) + int(away_p3),
            ))
        except (TypeError, ValueError):
            _mark_review(conn, pid, "no_regulation_score")
            return True
    if len(set(sums)) != 1:
        _mark_review(conn, pid, "regulation_scores_disagree")
        return True
    reg_home, reg_away = sums[0]
    if reg_home == reg_away:
        result = "LOSS"
    elif (reg_home > reg_away) == (side == "home"):
        result = "WIN"
    else:
        result = "LOSS"
    profit, risked = units_for_result(stake, price, result)
    clv, close_px, beat = _game_clv(
        conn, game_id, "h2h_3way", side, None, price, commence)
    _write_grade(conn, pid, result, profit, risked, clv, close_px, beat)
    return True


def _grade_prop(conn, pid, game_id, side, line, price, stake, player,
                prop_stat, prop_kind, prop_market, commence, sport) -> bool:
    if prop_kind not in ("batter", "pitcher") or not prop_stat or line is None:
        _mark_review(conn, pid, "prop_not_graded")
        return True
    rows = conn.execute(
        "SELECT player_name, player_type, innings_pitched, p_strikeouts, "
        "p_walks, p_hits_allowed, p_earned_runs, hits, total_bases, home_runs, "
        "rbi, runs, stolen_bases, walks FROM player_game_log WHERE game_id = %s",
        (game_id,)).fetchall()
    if not rows:
        # MLB logs arrive after the final. Another sport has no row in this
        # table, so leaving it pending would hold the recap open.
        if sport == "MLB":
            return False
        _mark_review(conn, pid, "prop_not_graded")
        return True
    cols = ["player_name", "player_type", "innings_pitched", "p_strikeouts",
            "p_walks", "p_hits_allowed", "p_earned_runs", "hits", "total_bases",
            "home_runs", "rbi", "runs", "stolen_bases", "walks"]
    want = "pitcher" if prop_kind == "pitcher" else "batter"
    target = " ".join(str(player or "").lower().split())
    actual = None
    found = False
    for raw in rows:
        d = dict(zip(cols, raw))
        if d["player_type"] != want:
            continue
        name = " ".join(str(d["player_name"] or "").lower().split())
        if name != target:
            continue
        found = True
        if prop_stat == "COMPUTE_OUTS":
            actual = _ip_to_outs(d.get("innings_pitched"))
        else:
            actual = d.get(prop_stat)
        break
    if not found or actual is None:
        conn.execute(
            "UPDATE capper_picks SET status = 'graded', result = 'NO_ACTION', "
            "units = 0, risked = 0, graded_at = %s, review_reason = %s "
            "WHERE id = %s",
            (datetime.now(timezone.utc).isoformat(), "player_not_in_log", pid))
        return True
    if float(actual) == float(line):
        result = "PUSH"
    elif (float(actual) > float(line)) == (side == "over"):
        result = "WIN"
    else:
        result = "LOSS"
    profit, risked = units_for_result(stake, price, result)
    clv = close_px = beat = None
    if prop_market and player and commence and price is not None:
        snap = _closing_prop_odds(conn, game_id, player, prop_market, commence)
        if snap:
            close_px = snap.get("over_price") if side == "over" else snap.get("under_price")
            if snap.get("line") is not None and float(snap["line"]) == float(line):
                pct, _pp = same_book_clv(price, close_px)
                clv = pct
                beat = (pct > 0) if pct is not None else None
    _write_grade(conn, pid, result, profit, risked, clv, close_px, beat)
    return True


def _game_clv(conn, game_id, market, side, line, price, commence):
    if price is None or not commence or not side:
        return None, None, None
    match = None
    if market == "spreads":
        match = line
    elif market == "totals":
        match = line
    snap = _closing_odds(conn, game_id, market, commence, "draftkings",
                         match_line=match)
    if not snap:
        return None, None, None
    col = {"home": "home_price", "away": "away_price", "over": "over_price",
           "under": "under_price"}.get(side)
    close_px = snap.get(col) if col else None
    close_line = snap.get("spread_home") if market == "spreads" else snap.get("total_line")
    if market != "h2h" and line is not None and close_line is not None:
        if float(close_line) != float(line):
            return None, close_px, None
    pct, _pp = same_book_clv(price, close_px)
    beat = (pct > 0) if pct is not None else None
    return pct, close_px, beat


def _write_grade(conn, pid, result, profit, risked, clv, close_px, beat) -> None:
    conn.execute(
        "UPDATE capper_picks SET status = 'graded', result = %s, units = %s, "
        "risked = %s, clv_pct = %s, closing_price = %s, clv_beat_close = %s, "
        "graded_at = %s, review_reason = NULL "
        "WHERE id = %s AND status IN ('pending', 'needs_review')",
        (result, profit, risked, clv, close_px, beat,
         datetime.now(timezone.utc).isoformat(), pid))


def _mark_review(conn, pid, reason: str) -> bool:
    changed = conn.execute(
        "UPDATE capper_picks SET status = 'needs_review', review_reason = %s "
        "WHERE id = %s AND status = 'pending' RETURNING id",
        (reason, pid)).fetchone()
    if changed:
        logger.error(f"Eggz pick {pid} needs review: {reason}")
    return bool(changed)


def _window_rows(conn, start: str, end: str) -> list[tuple]:
    return conn.execute(
        "SELECT sport, 'eggz', result, NULL, price, "
        "CASE WHEN clv_pct IS NOT NULL THEN clv_pct END, FALSE, units, risked "
        "FROM capper_picks WHERE status = 'graded' AND result IN ('WIN','LOSS','PUSH') "
        "AND game_date BETWEEN %s AND %s",
        (start, end)).fetchall()


def _pending_in(conn, start: str, end: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM capper_picks WHERE status = 'pending' "
        "AND game_date BETWEEN %s AND %s",
        (start, end)).fetchone()
    return int(row[0]) if row else 0


def _slate_unfinished(conn, start: str, end: str) -> bool:
    """A game on a slate date in this window has no final score.

    The slate dates are the dates he has a pick. Every game of that sport
    on that date has to be final, so a finished leg does not recap a night
    that is still being played. A connection with no execute is not live.
    """
    execute = getattr(conn, "execute", None)
    if execute is None:
        return False
    row = execute(
        "SELECT 1 FROM games g "
        "WHERE g.game_date BETWEEN %s AND %s "
        "AND (g.home_score IS NULL OR g.away_score IS NULL) "
        "AND EXISTS (SELECT 1 FROM capper_picks c "
        "WHERE c.game_date = g.game_date AND c.sport = g.sport "
        "AND c.game_date BETWEEN %s AND %s) "
        "LIMIT 1",
        (start, end, start, end)).fetchone()
    return row is not None


def eggz_embed(heading: str, rows: list[tuple], pending: int) -> dict | None:
    """The Discord embed, or None when the window is not ready to post."""
    if pending:
        return None
    if not rows:
        return None
    overall = _tally(rows)
    if overall["w"] + overall["l"] + overall["p"] == 0:
        return None
    by_sport: dict[str, list] = {}
    for row in rows:
        by_sport.setdefault(row[0] or "?", []).append(row)
    fields = [{
        "name": sport,
        "value": _tally_line(_tally(group), with_clv=True),
        "inline": False,
    } for sport, group in sorted(by_sport.items())]
    color = 0x3BA55D if overall["units"] > 0 else 0xED4245 if overall["units"] < 0 else 0x4F545C
    return {
        "title": f"\U0001F4CA Eggz — {heading}",
        "description": (
            f"**{_tally_line(overall, with_clv=True)}**  ·  {len(rows)} settled"
        ),
        "color": color,
        "fields": fields,
        "clv": clv_line(overall),
    }


def _post_window(conn, span: str, start: str, end: str, heading: str,
                 dry_run: bool = False, now: datetime | None = None) -> int:
    if not configured_to_post():
        return 0
    kind = f"discord_eggz_results_{span}"
    lock = f"{kind}:{start}"
    if conn.execute(
        "SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = %s",
        (lock, kind)).fetchone():
        return 0
    pending = _pending_in(conn, start, end)
    if pending or _slate_unfinished(conn, start, end):
        return 0
    rows = _window_rows(conn, start, end)
    sports = tuple({r[0] for r in rows if r[0]})
    if sport_in_progress(conn, sports, now):
        logger.info(f"Eggz {span} waits, a game of that sport is in progress")
        return 0
    embed = eggz_embed(heading, rows, 0)
    if embed is None:
        return 0
    embed.pop("clv", None)
    if dry_run:
        logger.info(f"[dry-run] eggz {span} {heading}")
        return 0
    message_id = _post(config.DISCORD_WEBHOOK_EGGZ, {"embeds": [embed]})
    if not message_id:
        logger.error(f"Eggz {span} recap not confirmed")
        return 0
    conn.execute(
        "INSERT INTO push_sent (lock_key, kind, sent_at, message_id) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT (lock_key, kind) DO NOTHING",
        (lock, kind, datetime.now(ET).isoformat(), message_id))
    conn.commit()
    logger.info(f"Eggz {span} recap posted: {heading}")
    return 1


def _as_et(now: datetime | None) -> datetime:
    """The clock in America/New_York. A UTC instant is converted, not relabeled."""
    now = now or datetime.now(ET)
    if now.tzinfo is None:
        return now.replace(tzinfo=ET)
    return now.astimezone(ET)


def post_eggz_recaps(now: datetime | None = None, dry_run: bool = False) -> int:
    """Daily from 6:00am ET, week and month from 7:30am ET, all through noon.

    Skips when DISCORD_WEBHOOK_EGGZ is unset. Does not post to X or #results.
    The day is yesterday in America/New_York. A pending leg, a slate date
    that is not final, or a game of that sport in progress is left
    unledgered. After noon the miss waits for the next morning.
    """
    if not configured_to_post():
        return 0
    from data.db import get_connection
    now = _as_et(now)
    conn = get_connection()
    try:
        try:
            ingest_messages(conn)
        except Exception as exc:                              # noqa: BLE001
            logger.error(f"Eggz ingest before recap failed: {exc}")
        try:
            grade_pending(conn)
        except Exception as exc:                              # noqa: BLE001
            logger.error(f"Eggz grade before recap failed: {exc}")
        posted = 0
        if in_daily_recap_window(now):
            day = (now.date() - timedelta(days=1)).isoformat()
            posted += _post_window(
                conn, "day", day, day, _day_heading(day), dry_run, now)
        if in_period_recap_window(now):
            for window in recap_periods_due(now):
                posted += _post_window(
                    conn, window["span"], window["start"].isoformat(),
                    window["end"].isoformat(), window["heading"], dry_run, now)
        return posted
    finally:
        conn.close()


def _day_heading(day: str) -> str:
    return datetime.fromisoformat(day).strftime("%b %d").replace(" 0", " ")


def run_eggz_ingest() -> None:
    """Poll, parse, and grade. Recaps stay on the daily and Monday jobs."""
    if not configured_to_read():
        return
    from data.db import get_connection
    conn = get_connection()
    try:
        n = ingest_messages(conn)
        g = grade_pending(conn)
        if n or g:
            logger.info(f"Eggz ingest stored {n}, graded {g}")
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"Eggz ingest failed: {exc}")
    finally:
        conn.close()


def period_heading_for(span: str, start, end) -> str:
    return period_heading(span, start, end)

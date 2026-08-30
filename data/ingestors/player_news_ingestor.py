"""
player_news_ingestor.py — recent per-player news notes, one row per (item, player).

WHY. A player prop is a bet on ONE person, and the thing that moves it most
often is not a number we model — it is a sentence: "on a 75-pitch limit",
"scratched with hamstring tightness", "moved up to leadoff". The pick card
showed the line, the edge and the form chart, and none of that. This feeds the
"Recent News" sheet the prop screens open from their top-right newspaper icon.

PROVIDER IS A SETTING (config.PLAYER_NEWS_PROVIDER), NOT A HARD-CODE.

  espn (default)  free, no key, the same hidden API the injury ingestor already
                  reads. Returns ARTICLES — headline + summary + link — with the
                  players they are about named in each article's `categories`.
                  Coverage is good for anyone with a storyline and thin for a
                  middle reliever: ~10 items per league feed, ~10 more per team.

  A licensed fantasy-notes feed (RotoWire, RotoBaller, SportsDataIO) is what the
  screenshot this was copied from is running: one note per player per event,
  with a separate ANALYSIS paragraph. `player_news.analysis` and the provider
  registry below exist so that drops in behind the same table and the same
  sheet — write a fetch function returning NewsItems and name it in PROVIDERS.

ESPN CALL BUDGET. ESPN has IP-blocked this worker twice (sessions 112, 115), so
this is deliberately frugal: one league feed per sport per run, plus at most
config.PLAYER_NEWS_MAX_TEAM_FETCHES team feeds spent on the teams that actually
have a player-prop pick today. The refresh-pass entry point is gated on a MAX
AGE (config.REFRESH_PLAYER_NEWS_MAX_AGE_MIN), not a cadence, so ~42 passes a day
cannot become 42 sweeps.

NAME RESOLUTION. Every row carries `player_key` — normalize_player_name(name),
the same fold the prop odds path uses — and `player_id` when that name resolves
against the sport's game log. The id is the join the app prefers; the key is why
an accented name still finds its news (see data/name_match.py for what that gap
cost on the odds side). An ambiguous name (two players folding alike) resolves
to no id rather than the wrong one, and is still readable by key.

Usage:
    python -m data.ingestors.player_news_ingestor                # all sports
    python -m data.ingestors.player_news_ingestor --sport MLB
    python -m data.ingestors.player_news_ingestor --max-age-min 60
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import config
from data.db import get_connection
from data.name_match import normalize_player_name

# ── Constants ─────────────────────────────────────────────────────────────────

ESPN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

ESPN_NEWS_URL = "https://site.api.espn.com/apis/site/v2/sports/{path}/news"

# Per-sport game log the name index is built from. Same tables the player detail
# screen charts, so a player the app can open is a player news can resolve.
LOG_TABLES: dict[str, str] = {
    "MLB":  "player_game_log",
    "WNBA": "wnba_player_game_log",
    "NBA":  "nba_player_game_log",
    "NFL":  "nfl_player_game_log",
}

# ESPN numeric team ids, for the team-scoped feeds. Sports with no map get the
# league feed only — a missing map must never be an error.
ESPN_TEAM_IDS: dict[str, dict] = {
    "MLB":  getattr(config, "ESPN_MLB_TEAM_IDS", {}),
    "NBA":  getattr(config, "ESPN_NBA_TEAM_IDS", {}),
    "WNBA": getattr(config, "ESPN_WNBA_TEAM_IDS", {}),
}

REQUEST_TIMEOUT = 15


# ── The provider contract ─────────────────────────────────────────────────────

@dataclass
class NewsPlayer:
    """A player an item is about, as the feed names them."""
    name: str
    team: str | None = None


@dataclass
class NewsItem:
    """One note/article, plus every player it is about.

    A feed that writes one note per player yields items with a single player; an
    article feed like ESPN's yields items with several. Storage is per (item,
    player) either way, so both shapes read identically out of the table.
    """
    source: str
    source_item_id: str
    published_at: datetime
    headline: str
    body: str | None = None
    # The fantasy-note ANALYSIS paragraph. None for feeds that carry none.
    analysis: str | None = None
    url: str | None = None
    players: list[NewsPlayer] = field(default_factory=list)


# ── ESPN provider ─────────────────────────────────────────────────────────────

def _parse_published(raw: object) -> datetime | None:
    """ESPN publishes ISO-8601 with a Z suffix. Parse before comparing — these
    are compared and stored as timestamps, and a string compare on mixed shapes
    silently mis-orders them (the §7 trap)."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _athletes_in(article: dict) -> list[NewsPlayer]:
    """Players an ESPN article is about.

    They arrive in `categories`, one entry per tagged entity:
        {"type": "athlete", "athlete": {"id": ..., "description": "Shota Imanaga"}}
    `description` is the display name; some payloads put it on the category
    itself instead, so both are read.
    """
    out: list[NewsPlayer] = []
    seen: set[str] = set()
    for cat in article.get("categories") or []:
        if not isinstance(cat, dict) or cat.get("type") != "athlete":
            continue
        athlete = cat.get("athlete") if isinstance(cat.get("athlete"), dict) else {}
        name = athlete.get("description") or athlete.get("displayName") or cat.get("description")
        if not isinstance(name, str) or not name.strip():
            continue
        key = normalize_player_name(name)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(NewsPlayer(name=name.strip()))
    return out


def _article_url(article: dict) -> str | None:
    links = article.get("links")
    if not isinstance(links, dict):
        return None
    web = links.get("web")
    if isinstance(web, dict) and isinstance(web.get("href"), str):
        return web["href"]
    return None


def _to_item(article: dict) -> NewsItem | None:
    """One ESPN article → a NewsItem, or None when it names no player."""
    if not isinstance(article, dict):
        return None
    headline = article.get("headline") or article.get("title")
    published = _parse_published(article.get("published") or article.get("lastModified"))
    item_id = article.get("id") or article.get("dataSourceIdentifier") or _article_url(article)
    if not isinstance(headline, str) or not headline.strip() or published is None or item_id is None:
        return None
    players = _athletes_in(article)
    if not players:
        # An article about nobody in particular has nowhere to appear — the
        # sheet is per player. Dropping it here keeps the table to news we
        # can actually surface.
        return None
    return NewsItem(
        source="espn",
        source_item_id=str(item_id),
        published_at=published,
        headline=headline.strip(),
        body=(article.get("description") or "").strip() or None,
        analysis=None,
        url=_article_url(article),
        players=players,
    )


def _fetch_espn(url: str, params: dict, fetch=None) -> list[dict]:
    """One ESPN news feed → its articles. Never raises: a dead feed is a quiet
    zero, not a failed pipeline step."""
    getter = fetch or (lambda u, **kw: requests.get(u, **kw))
    try:
        resp = getter(url, params=params, headers=ESPN_HEADERS, timeout=REQUEST_TIMEOUT)
        if getattr(resp, "status_code", 200) != 200:
            logger.warning(f"ESPN news {params} → HTTP {resp.status_code}")
            return []
        payload = resp.json()
    except Exception as exc:
        logger.warning(f"ESPN news {params} failed: {exc}")
        return []
    articles = payload.get("articles") if isinstance(payload, dict) else None
    return [a for a in (articles or []) if isinstance(a, dict)]


def fetch_espn_news(sport: str, teams: list[str] | None = None, fetch=None) -> list[NewsItem]:
    """League feed for `sport`, plus a bounded set of team feeds.

    Team feeds are the only way a bench bat or a fifth starter shows up at all —
    the league feed is the ~10 biggest stories. They are capped at
    config.PLAYER_NEWS_MAX_TEAM_FETCHES and spent on teams passed in by the
    caller (the ones with a prop pick today).
    """
    path = config.ESPN_NEWS_PATHS.get(sport)
    if not path:
        logger.warning(f"No ESPN news path for {sport} — skipping")
        return []
    url = ESPN_NEWS_URL.format(path=path)

    items: dict[tuple[str, str], NewsItem] = {}

    def absorb(articles: list[dict]) -> None:
        for article in articles:
            item = _to_item(article)
            if item is not None:
                items.setdefault((item.source, item.source_item_id), item)

    absorb(_fetch_espn(url, {"limit": 50}, fetch))

    team_ids = ESPN_TEAM_IDS.get(sport) or {}
    budget = max(0, config.PLAYER_NEWS_MAX_TEAM_FETCHES)
    for team in (teams or [])[:budget]:
        espn_id = team_ids.get(team)
        if espn_id is None:
            continue
        absorb(_fetch_espn(url, {"limit": 20, "team": espn_id}, fetch))

    return list(items.values())


PROVIDERS = {
    "espn": fetch_espn_news,
}


# ── Resolution against our own players ────────────────────────────────────────

def build_name_index(conn, sport: str, lookback_days: int = 400) -> dict[str, str | None]:
    """{normalized name: our player_id} for players logged recently.

    A name two players share folds to one key; that entry maps to None so the
    row stores no id rather than the wrong one. Both are still readable by key,
    which is the whole reason the key column exists.
    """
    table = LOG_TABLES.get(sport)
    if not table:
        return {}
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    try:
        rows = conn.execute(
            f"SELECT DISTINCT player_id, player_name FROM {table} WHERE game_date >= %s",
            (cutoff,),
        ).fetchall()
    except Exception as exc:
        logger.warning(f"{sport}: could not read {table} for name resolution: {exc}")
        return {}

    index: dict[str, str | None] = {}
    ambiguous: set[str] = set()
    for row in rows:
        player_id, player_name = row[0], row[1]
        key = normalize_player_name(player_name)
        if not key or player_id is None:
            continue
        if key in ambiguous:
            continue
        existing = index.get(key, "\0")
        if existing == "\0":
            index[key] = str(player_id)
        elif existing != str(player_id):
            index[key] = None
            ambiguous.add(key)
    if ambiguous:
        logger.debug(f"{sport}: {len(ambiguous)} ambiguous player names stored by key only")
    return index


def teams_with_props_today(conn, sport: str, run_date: str | None = None) -> list[str]:
    """Teams playing today that carry a player-prop pick — where a team-scoped
    ESPN call is worth spending."""
    day = run_date or date.today().isoformat()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT g.home_team, g.away_team
            FROM picks p
            JOIN games g ON g.game_id = p.game_id
            WHERE p.game_date = %s AND p.sport = %s AND p.player_id IS NOT NULL
            """,
            (day, sport),
        ).fetchall()
    except Exception as exc:
        logger.warning(f"{sport}: could not read today's prop teams: {exc}")
        return []
    teams: list[str] = []
    for home, away in rows:
        for team in (home, away):
            if team and team not in teams:
                teams.append(team)
    return teams


# ── Storage ───────────────────────────────────────────────────────────────────

UPSERT = """
INSERT INTO player_news (
    sport, player_id, player_name, player_key, team,
    source, source_item_id, published_at, headline, body, analysis, url, ingested_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (source, source_item_id, player_key) DO UPDATE SET
    sport       = EXCLUDED.sport,
    player_id   = COALESCE(EXCLUDED.player_id, player_news.player_id),
    player_name = EXCLUDED.player_name,
    team        = COALESCE(EXCLUDED.team, player_news.team),
    published_at= EXCLUDED.published_at,
    headline    = EXCLUDED.headline,
    body        = EXCLUDED.body,
    analysis    = EXCLUDED.analysis,
    url         = EXCLUDED.url,
    ingested_at = NOW()
"""


def store_items(conn, sport: str, items: list[NewsItem], index: dict[str, str | None]) -> int:
    """Write one row per (item, player). Returns rows written."""
    written = 0
    for item in items:
        for player in item.players:
            key = normalize_player_name(player.name)
            if not key:
                continue
            conn.execute(
                UPSERT,
                (
                    sport,
                    index.get(key),
                    player.name,
                    key,
                    player.team,
                    item.source,
                    item.source_item_id,
                    item.published_at,
                    item.headline,
                    item.body,
                    item.analysis,
                    item.url,
                ),
            )
            written += 1
    return written


def prune_old(conn, retention_days: int | None = None) -> int:
    """Drop notes past the retention window. This table is a cache of a feed we
    can re-read — nothing here is irreplaceable."""
    days = retention_days if retention_days is not None else config.PLAYER_NEWS_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = conn.execute("DELETE FROM player_news WHERE published_at < %s", (cutoff,))
    return getattr(result, "rowcount", 0) or 0


def _minutes_since_last_ingest(conn) -> float | None:
    """Age of the freshest row, in minutes. None when the table is empty or
    unreadable — which must read as "stale", never as "fresh"."""
    try:
        row = conn.execute("SELECT MAX(ingested_at) FROM player_news").fetchone()
    except Exception:
        return None
    if not row or row[0] is None:
        return None
    stamp = row[0]
    if isinstance(stamp, str):
        stamp = _parse_published(stamp)
        if stamp is None:
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - stamp).total_seconds() / 60.0


# ── Entry point ───────────────────────────────────────────────────────────────

def ingest_player_news(
    sports: list[str] | None = None,
    conn=None,
    max_age_min: int | None = None,
    run_date: str | None = None,
    fetch=None,
) -> dict:
    """Fetch and store recent news for each sport. Returns a per-sport summary.

    `max_age_min` makes this a no-op when the table was refreshed that recently —
    the same self-limiting shape as the injury and weather refresh steps, so the
    refresh pass can call it on every pass without sweeping ESPN every pass.
    """
    provider_name = config.PLAYER_NEWS_PROVIDER
    provider = PROVIDERS.get(provider_name)
    if provider is None:
        logger.error(
            f"Unknown PLAYER_NEWS_PROVIDER '{provider_name}' — known: {sorted(PROVIDERS)}"
        )
        return {"skipped": "unknown_provider"}

    targets = [s.upper() for s in (sports or config.PLAYER_NEWS_SPORTS)]
    owns = conn is None
    conn = conn or get_connection()
    summary: dict = {}
    try:
        if max_age_min is not None:
            age = _minutes_since_last_ingest(conn)
            if age is not None and age < max_age_min:
                logger.info(f"Player news is {age:.0f} min old (< {max_age_min}) — skipping")
                return {"skipped": "fresh", "age_min": round(age, 1)}

        for sport in targets:
            teams = teams_with_props_today(conn, sport, run_date)
            items = provider(sport, teams, fetch) if fetch else provider(sport, teams)
            index = build_name_index(conn, sport)
            written = store_items(conn, sport, items, index)
            conn.commit()
            resolved = sum(
                1
                for item in items
                for p in item.players
                if index.get(normalize_player_name(p.name))
            )
            summary[sport] = {"items": len(items), "rows": written, "resolved": resolved}
            logger.info(
                f"{sport}: {len(items)} news items → {written} player rows "
                f"({resolved} matched to a player id)"
            )

        pruned = prune_old(conn)
        conn.commit()
        if pruned:
            logger.info(f"Pruned {pruned} news rows past retention")
        summary["pruned"] = pruned
    finally:
        if owns:
            conn.close()
    return summary


def run_player_news_ingestor(max_age_min: int | None = None, run_date: str | None = None) -> dict:
    """run_pipeline entry point."""
    return ingest_player_news(max_age_min=max_age_min, run_date=run_date)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent player news")
    parser.add_argument("--sport", action="append", help="Sport to fetch (repeatable)")
    parser.add_argument("--max-age-min", type=int, default=None,
                        help="Skip entirely when the table is fresher than this")
    parser.add_argument("--date", default=None, help="Run date (YYYY-MM-DD) for today's prop teams")
    args = parser.parse_args()
    result = ingest_player_news(
        sports=args.sport, max_age_min=args.max_age_min, run_date=args.date
    )
    logger.info(f"Player news: {result}")


if __name__ == "__main__":
    main()

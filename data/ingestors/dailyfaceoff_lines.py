"""Daily Faceoff line combinations and special-teams units.

Personal, non-commercial. Not a pick input. The page is the same site as
the starting-goalie scraper and sits behind the same Cloudflare wall, so a
team that does not answer is one warning and the run carries on. A run
that reads no team on a game day fails, so a blocked morning is visible.

Each run inserts a new snapshot. Nothing is updated in place.

The page is Next.js. Measured on the Boston page archived 2026-03-03
(and the same shape on 2024-08-12 and 2025-12-10): `__NEXT_DATA__` →
`props.pageProps.combinations.players[]`, with `groupIdentifier` f1–f4,
d1–d3, g, pp1, pp2, pk1, pk2, and ir. Utah's slug `utah-mammoth` was
archived 2025-10-09.

    python -m data.ingestors.dailyfaceoff_lines --daily
    python -m data.ingestors.dailyfaceoff_lines --daily --apply
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from loguru import logger

from data.db import ConnectionLost, get_connection
from data.ingestors.nhl_stats_ingestor import _norm_nhl

SOURCE = "dailyfaceoff"
PAGE = "https://www.dailyfaceoff.com/teams/{slug}/line-combinations"
TIMEOUT_S = 20
PAUSE_S = 0.8
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml",
}
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

# Slugs are the path on that site. Boston was read from the 2026-03-03
# archive; Utah from the 2025-10-09 archive. The rest are the same
# /teams/{slug}/line-combinations path.
TEAM_SLUGS = {
    "ANA": "anaheim-ducks",
    "BOS": "boston-bruins",
    "BUF": "buffalo-sabres",
    "CGY": "calgary-flames",
    "CAR": "carolina-hurricanes",
    "CHI": "chicago-blackhawks",
    "COL": "colorado-avalanche",
    "CBJ": "columbus-blue-jackets",
    "DAL": "dallas-stars",
    "DET": "detroit-red-wings",
    "EDM": "edmonton-oilers",
    "FLA": "florida-panthers",
    "LAK": "los-angeles-kings",
    "MIN": "minnesota-wild",
    "MTL": "montreal-canadiens",
    "NSH": "nashville-predators",
    "NJD": "new-jersey-devils",
    "NYI": "new-york-islanders",
    "NYR": "new-york-rangers",
    "OTT": "ottawa-senators",
    "PHI": "philadelphia-flyers",
    "PIT": "pittsburgh-penguins",
    "SJS": "san-jose-sharks",
    "SEA": "seattle-kraken",
    "STL": "st-louis-blues",
    "TBL": "tampa-bay-lightning",
    "TOR": "toronto-maple-leafs",
    "UTA": "utah-mammoth",
    "VAN": "vancouver-canucks",
    "VGK": "vegas-golden-knights",
    "WSH": "washington-capitals",
    "WPG": "winnipeg-jets",
}

COLS = (
    "snapshot_at", "game_date", "team_abbr", "team_slug", "source_name",
    "source_updated_at", "category", "group_id", "group_name",
    "player_id", "player_name", "position_id", "position_name",
    "jersey_number", "source",
)
# A retry of the same snapshot does not replace a row. A later run has a
# new snapshot_at and inserts beside it.
INSERT_SQL = (
    f"INSERT INTO dailyfaceoff_line_snapshots ({', '.join(COLS)}) "
    f"VALUES ({', '.join(f'%({c})s' for c in COLS)}) "
    f"ON CONFLICT (snapshot_at, team_abbr, category, group_id, player_id) DO NOTHING"
)


def parse_line_page(html: str) -> dict:
    """pageProps. Raises ValueError when the Next.js payload is not there."""
    match = _NEXT_DATA.search(html or "")
    if not match:
        raise ValueError("no __NEXT_DATA__ on the DailyFaceoff line page")
    return json.loads(match.group(1))["props"]["pageProps"]


def line_rows(page: dict, game_date: str, snapshot_at: str) -> list[dict]:
    """One row per player on a unit. A player repeated in one unit is kept once."""
    comb = (page or {}).get("combinations") or {}
    team = _norm_nhl(str(comb.get("teamAbbreviation") or ""))
    if not team:
        return []
    slug = comb.get("teamSlug")
    source_name = comb.get("sourceName") or comb.get("source")
    updated = comb.get("updatedAt")
    out = []
    seen = set()
    for player in comb.get("players") or []:
        pid = player.get("playerId")
        group = player.get("groupIdentifier")
        category = player.get("categoryIdentifier")
        if pid is None or not group or not category:
            continue
        key = (team, str(category), str(group), int(pid))
        if key in seen:
            continue
        seen.add(key)
        jersey = player.get("jerseyNumber")
        out.append({
            "snapshot_at": snapshot_at,
            "game_date": game_date,
            "team_abbr": team,
            "team_slug": slug,
            "source_name": source_name,
            "source_updated_at": updated,
            "category": str(category),
            "group_id": str(group),
            "group_name": player.get("groupName"),
            "player_id": int(pid),
            "player_name": player.get("name"),
            "position_id": player.get("positionIdentifier"),
            "position_name": player.get("positionName"),
            "jersey_number": int(jersey) if jersey is not None else None,
            "source": SOURCE,
        })
    return out


def fetch_team(slug: str, fetch_html=None) -> dict | None:
    """One team's page, parsed. None, and one warning, on any failure."""
    url = PAGE.format(slug=slug)
    try:
        if fetch_html is None:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_S)
            resp.raise_for_status()
            html = resp.text
        else:
            html = fetch_html(url)
        return parse_line_page(html)
    except Exception as exc:                                  # noqa: BLE001 - fail open
        logger.warning(f"DailyFaceoff lines {slug}: not read ({exc!r}); the other teams still run")
        return None


def nhl_games_on(conn, game_date: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM games WHERE sport = 'NHL' AND game_date = ?",
        (game_date,),
    ).fetchone()
    conn.commit()
    return int(row[0] or 0)


def _write(conn, rows: list[dict]) -> None:
    def once():
        conn.executemany(INSERT_SQL, rows)
        conn.commit()

    try:
        once()
    except ConnectionLost:
        logger.warning("connection lost — re-running the snapshot")
        once()


def daily(run_date: str, apply: bool, pause_s: float = PAUSE_S,
          fetch_html=None, games: int | None = None) -> dict:
    """Scrape every team when `run_date` has an NHL game. Otherwise do nothing.

    `games` lets a test skip the schedule read. `fetch_html(url)` lets a
    test skip the network.
    """
    import time
    conn = get_connection() if (apply or games is None) else None
    try:
        n_games = games if games is not None else nhl_games_on(conn, run_date)
        if n_games <= 0:
            logger.info(f"DailyFaceoff lines {run_date}: no NHL games, nothing fetched")
            return {"ok": True, "written": 0, "teams": 0, "missed": [],
                    "reason": "no NHL games", "game_date": run_date}
        snapshot_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows: list[dict] = []
        missed = []
        read = 0
        for abbr, slug in TEAM_SLUGS.items():
            page = fetch_team(slug, fetch_html=fetch_html)
            if page is None:
                missed.append(abbr)
            else:
                team_rows = line_rows(page, run_date, snapshot_at)
                if not team_rows:
                    missed.append(abbr)
                    logger.warning(f"DailyFaceoff lines {slug}: page had no players")
                else:
                    rows.extend(team_rows)
                    read += 1
            if pause_s and fetch_html is None:
                time.sleep(pause_s)
        if read == 0:
            raise RuntimeError(
                f"DailyFaceoff lines {run_date}: 0 of {len(TEAM_SLUGS)} teams read")
        if apply and rows:
            _write(conn, rows)
        logger.success(
            f"DailyFaceoff lines {run_date}: {read} teams, {len(rows)} players"
            + ("" if apply else " (dry run)")
            + (f", missed {missed}" if missed else ""))
        return {"ok": True, "written": len(rows) if apply else 0,
                "teams": read, "missed": missed, "game_date": run_date,
                "snapshot_at": snapshot_at}
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daily", action="store_true", required=True)
    ap.add_argument("--date", default=None, help="YYYY-MM-DD, default today ET")
    ap.add_argument("--apply", action="store_true", help="write to Supabase")
    args = ap.parse_args()
    if args.date:
        run_date = args.date
    else:
        run_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    daily(run_date, args.apply)

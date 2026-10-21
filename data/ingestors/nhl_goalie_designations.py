"""Who ESPN and DailyFaceoff say will start in goal, stored as it changes.

WHY (mike, 2026-10-20): "We should absolutely always know the goalie matchup
before making a bet as well." No NHL model bets until both starting goalies
are confirmed (models/nhl_goalie_gate.py), and the gate can only read what is
stored. Until this module, the only goalie record was `nhl_goalie_stats`: one
row per team per game, written once at ~10:06Z from ESPN's probable starter,
with ESPN's own 'expected' / 'confirmed' flag thrown away. The 6am goalie did
not start in 65 of 251 team-games 2026-10-01..10-19 (22 of 70, 31%, for
10-14..10-19); on 2026-10-20 MTL (Fowler -> Dobes) and SEA (Daccord ->
Grubauer) changed after the write.

WHAT A RUN DOES, for the NHL games on the asked ET dates that have not started
(from `games`; a started game is never touched):

  1. ESPN core: each team's probableStartingGoalie and its status
     (data/ingestors/espn_probables.fetch_espn_nhl_designations). The listing
     plus one event document a game; an athlete document only when ESPN names
     someone new or changes his status.
  2. DailyFaceoff's starting-goalies page for the date: per team, the name and
     "Confirmed" / "Likely" / unconfirmed, from the page's Next.js
     __NEXT_DATA__ JSON. It sits behind Cloudflare, and whether it answers
     the Railway worker has not been tested, so it FAILS OPEN: one warning, and
     the run carries on with ESPN alone (the gate treats a team DailyFaceoff
     has never named as no disagreement, and a stored DailyFaceoff name no
     poll has read for config.NHL_GOALIE_READ_MAX_AGE_MIN the same way).
  3. A row in `nhl_goalie_designations` for each (game, team, source) whose
     (player_name, status) differs from the latest stored row. Append-only:
     the table is the timeline of who was named and when. A row the source
     still shows unchanged gets `last_seen_at` = this poll instead: the gate
     refuses an ESPN confirmation no poll has read for
     config.NHL_GOALIE_READ_MAX_AGE_MIN, so a poll that reads nothing (ESPN
     blocking the worker) cannot leave an old confirmation standing all day.
  4. For every game dated TODAY (ET) whose latest ESPN designation is
     'confirmed' for someone other than the goalie on the game's
     `nhl_goalie_stats` row: that row is deleted and the confirmed goalie's row
     is written in its place, built by the same function the 6am write uses
     (nhl_stats_ingestor.goalie_row: his as-of line from the per-game log). It
     only ever REWRITES a row the 6am run wrote; it never creates one, because
     the as-of line is built from logs that hold last night's games only after
     that morning's top-up (~10:05Z). That is also why no game can be known
     before its own game day.

Idempotent: a second run on the same state stores no row (it only moves
`last_seen_at`). Steps 3 and 4 run in one transaction.

A RUN THAT CANNOT READ ESPN FAILS. When ESPN's listing for a date with
unstarted games cannot be read, or names none of them, whatever DailyFaceoff
said is still stored, and then the run raises: the step shows as failed in
the refresh pass and the window's heartbeat, instead of reporting success on
a poll that saw nothing.

ESPN LOAD. The worker has been IP-blocked by ESPN twice (scripts/
refresh_pass.sh). A poll of an unchanged ~11-game slate is 12 ESPN calls. The
five-minute NHL job polls today only (`--today-only`); tomorrow is polled by
the hourly refresh passes and the 6am run, where it is history only (a
tomorrow game cannot be known today: step 4).

    python -m data.ingestors.nhl_goalie_designations                # today and tomorrow
    python -m data.ingestors.nhl_goalie_designations --today-only
    python -m data.ingestors.nhl_goalie_designations --dry-run      # read and say, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import config  # noqa: E402
from data.ingestors.odds_ingestor import NHL_ODDS_API_MAP  # noqa: E402
from models.nhl_goalie_gate import (  # noqa: E402
    CONFIRMED,
    NO_STARTER,
    SOURCE_DAILYFACEOFF,
    SOURCE_ESPN,
    _fold,
    same_goalie,
)

ET = ZoneInfo("America/New_York")
DAILYFACEOFF_URL = "https://www.dailyfaceoff.com/starting-goalies/{date}"
DAILYFACEOFF_TIMEOUT_S = 8
DAILYFACEOFF_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml",
}
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
# DailyFaceoff's NewsStrengthId, used only when the name is missing. Measured on
# the 2026-10-20 page: 2 Confirmed, 3 Likely; tomorrow's games carry none.
_DF_STRENGTH = {2: "confirmed", 3: "likely"}
# Team names folded to letters only, so "St Louis Blues" (DailyFaceoff) and
# "St. Louis Blues" (the odds feed) are one key.
_TEAM_BY_FOLDED_NAME = {_fold(name): abbrev for name, abbrev in NHL_ODDS_API_MAP.items()}

_INSERT = """
    INSERT INTO nhl_goalie_designations
        (game_id, team, player_id, player_name, source, status, source_player_id, observed_at,
         last_seen_at)
    VALUES (%(game_id)s, %(team)s, %(player_id)s, %(player_name)s, %(source)s,
            %(status)s, %(source_player_id)s, %(observed_at)s, %(last_seen_at)s)
"""
_SEEN = "UPDATE nhl_goalie_designations SET last_seen_at = %s WHERE designation_id = ANY(%s)"
_LATEST_SQL = """
    SELECT DISTINCT ON (game_id, team, source)
           game_id, team, source, player_id, player_name, status, source_player_id, observed_at,
           designation_id
    FROM nhl_goalie_designations
    WHERE game_id = ANY(%s)
    ORDER BY game_id, team, source, observed_at DESC
"""


def normalize_status(raw) -> str:
    """Lower case; a missing status is 'unconfirmed'."""
    s = str(raw or "").strip().lower()
    return s or "unconfirmed"


def team_from_name(name: str | None) -> str | None:
    return _TEAM_BY_FOLDED_NAME.get(_fold(name))


# ── DailyFaceoff, pure ───────────────────────────────────────────────────────

def parse_dailyfaceoff_page(html: str) -> dict:
    """The page's Next.js pageProps. Raises ValueError when it is not there."""
    m = _NEXT_DATA.search(html or "")
    if not m:
        raise ValueError("no __NEXT_DATA__ on the DailyFaceoff page")
    return json.loads(m.group(1))["props"]["pageProps"]


def parse_dailyfaceoff(page_props: dict) -> list[dict]:
    """One row per team the page lists: {team, player_name, source_player_id,
    status}. A team whose name is not ours is skipped. A team with no goalie
    named is status 'none'."""
    out = []
    for g in (page_props or {}).get("data") or []:
        for side in ("home", "away"):
            team = team_from_name(g.get(f"{side}TeamName"))
            if not team:
                continue
            name = g.get(f"{side}GoalieName")
            raw = g.get(f"{side}NewsStrengthName")
            if raw is None:
                raw = _DF_STRENGTH.get(g.get(f"{side}NewsStrengthId"))
            gid = g.get(f"{side}GoalieId")
            out.append({"team": team, "player_name": name or None,
                        "source_player_id": str(gid) if gid not in (None, "") else None,
                        "status": normalize_status(raw) if name else NO_STARTER})
    return out


def fetch_dailyfaceoff(game_date: str, fetch_html=None) -> list[dict] | None:
    """The page for one ET date, parsed; None (and one warning) on any failure."""
    url = DAILYFACEOFF_URL.format(date=game_date)
    try:
        if fetch_html is None:
            resp = requests.get(url, headers=DAILYFACEOFF_HEADERS, timeout=DAILYFACEOFF_TIMEOUT_S)
            resp.raise_for_status()
            html = resp.text
        else:
            html = fetch_html(url)
        return parse_dailyfaceoff(parse_dailyfaceoff_page(html))
    except Exception as exc:                                  # noqa: BLE001 - fail open
        logger.warning(f"DailyFaceoff {game_date}: not read ({exc!r}); its last stored names "
                       f"still veto for {config.NHL_GOALIE_READ_MAX_AGE_MIN} minutes after they "
                       f"were last read, then the goalie gate runs on ESPN alone")
        return None


# ── the change, pure ─────────────────────────────────────────────────────────

def changes(latest: dict, observed: list[dict]) -> list[dict]:
    """The observed rows to store: those whose (player_name, status) differs
    from the latest stored row for the same (game_id, team, source), or that
    have none. `latest` is {(game_id, team, source): row}."""
    out, seen = [], set()
    for r in observed:
        key = (r["game_id"], r["team"], r["source"])
        if key in seen:
            continue
        seen.add(key)
        held = latest.get(key)
        if held and (held.get("player_name") or None) == (r.get("player_name") or None) \
                and held.get("status") == r.get("status"):
            continue
        out.append(r)
    return out


def swaps_needed(latest: dict, stats: dict, game_ids) -> list[tuple[str, str, dict]]:
    """(game_id, team, ESPN row) for every goalie row that names someone other
    than the goalie ESPN has CONFIRMED. A team with no goalie row is not here:
    a swap rewrites, it never creates. Pure."""
    out = []
    for (gid, team, source), row in sorted(latest.items()):
        if source != SOURCE_ESPN or gid not in game_ids:
            continue
        if row.get("status") != CONFIRMED or not row.get("player_name"):
            continue
        held = stats.get((gid, team))
        if held is None:
            continue
        if same_goalie(held.get("player_id"), held.get("player_name"),
                       row.get("player_id"), row.get("player_name")):
            continue
        out.append((gid, team, row))
    return out


# ── the run ──────────────────────────────────────────────────────────────────

def _unstarted_games(conn, game_date: str, now: datetime) -> dict[str, dict]:
    """{game_id: {home, away, game_date}} for the date's games not yet started."""
    from scripts.nhl_prop_card import slate
    return {g: {**v, "game_date": game_date} for g, v in slate(conn, game_date, now).items()}


def _latest(conn, game_ids: list[str]) -> dict:
    if not game_ids:
        return {}
    rows = conn.execute(_LATEST_SQL, (game_ids,)).fetchall()
    return {(r[0], r[1], r[2]): {"player_id": r[3], "player_name": r[4], "status": r[5],
                                 "source_player_id": r[6], "observed_at": r[7],
                                 "designation_id": r[8] if len(r) > 8 else None} for r in rows}


def _stats_rows(conn, game_ids: list[str]) -> dict:
    if not game_ids:
        return {}
    out: dict = {}
    for gid, team, pid, name in conn.execute(
            "SELECT game_id, team, player_id, player_name FROM nhl_goalie_stats "
            "WHERE game_id = ANY(%s) ORDER BY created_at DESC", (game_ids,)).fetchall():
        out.setdefault((gid, team), {"player_id": pid, "player_name": name})
    return out


class _Resolver:
    """Puts an NHL id to a goalie's name, the way the 6am write does; the
    summary and the log are read once a run, and only if a name needs it."""

    def __init__(self, conn, game_date: str):
        self.conn, self.game_date, self._loaded = conn, game_date, False
        self.season = None
        self.summary: list[dict] = []
        self.book = None

    def _load(self):
        if self._loaded:
            return
        from data.ingestors.nhl_stats_ingestor import _fetch_goalie_season_stats, _goalie_book
        from data.season_labels import nhl_season_label
        self.season = nhl_season_label(self.game_date)
        self.summary = _fetch_goalie_season_stats(self.season)
        self.book = _goalie_book(self.conn, self.season)
        self._loaded = True

    def player_id(self, name: str | None) -> str | None:
        if not name:
            return None
        self._load()
        from data.ingestors.nhl_stats_ingestor import resolve_goalie_id
        return resolve_goalie_id(name, self.summary, self.book, self.season, self.game_date) or None

    def row(self, team: str, name: str, player_id: str | None, game_id: str) -> dict:
        self._load()
        from data.ingestors.nhl_stats_ingestor import goalie_row
        return goalie_row(name, player_id or "", team, self.season, self.game_date, game_id,
                          self.summary, self.book)


def _observe_date(conn, game_date: str, games: dict, latest: dict, espn_fetch,
                  df_fetch) -> tuple[list, bool, bool]:
    """ESPN and DailyFaceoff rows for one date's unstarted games, keyed to our
    game ids. Returns (rows, whether DailyFaceoff answered, whether ESPN was
    read: its listing answered and named at least one of these games)."""
    from data.ingestors.espn_probables import fetch_espn_nhl_designations
    by_team = {}
    for gid, g in games.items():
        by_team[g["home"]] = gid
        by_team[g["away"]] = gid
    wanted = {(g["home"], g["away"]) for g in games.values()}
    # Every game on the date, started ones included, so a started game is
    # recognised from its short name and skipped without another call.
    pairs = {(h, a) for h, a in conn.execute(
        "SELECT home_team, away_team FROM games WHERE sport = 'NHL' AND game_date = %s",
        (game_date,)).fetchall()} | wanted
    known = {team: {"espn_athlete_id": row.get("source_player_id"), "designation": row.get("status"),
                    "player_name": row.get("player_name")}
             for (gid, team, source), row in latest.items()
             if source == SOURCE_ESPN and gid in games}
    rows = []
    try:
        espn = fetch_espn_nhl_designations(game_date, fetch=espn_fetch, known=known,
                                           teams_ok=lambda h, a: (h, a) in pairs,
                                           skip_game=lambda h, a: (h, a) not in wanted,
                                           strict=True)
    except Exception as exc:                                  # noqa: BLE001 - reported by run()
        logger.error(f"NHL goalies {game_date}: ESPN not read ({exc!r})")
        espn = []
    espn_ok = any(by_team.get(d["team"]) is not None for d in espn)
    for d in espn:
        gid = by_team.get(d["team"])
        if gid is None:
            continue
        rows.append({"game_id": gid, "team": d["team"], "source": SOURCE_ESPN,
                     "player_name": d.get("player_name"), "status": normalize_status(d.get("designation")),
                     "source_player_id": d.get("espn_athlete_id")})
    df = fetch_dailyfaceoff(game_date, fetch_html=df_fetch)
    for d in df or []:
        gid = by_team.get(d["team"])
        if gid is None:
            continue
        rows.append({"game_id": gid, "source": SOURCE_DAILYFACEOFF, **d})
    return rows, df is not None, espn_ok


def run(dates: list[str] | None = None, now: datetime | None = None, *, today_only: bool = False,
        dry_run: bool = False, conn=None, espn_fetch=None, df_fetch=None) -> dict:
    """Poll, store what changed, rewrite the goalie rows ESPN's confirmations
    contradict. `conn`, `espn_fetch`, `df_fetch` exist for the tests."""
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ET).date()
    if dates is None:
        dates = [today.isoformat()] + ([] if today_only else [(today + timedelta(days=1)).isoformat()])
    out = {"dates": dates, "games": 0, "observed": 0, "stored": 0, "seen": 0, "swapped": [],
           "dailyfaceoff": {}, "espn": {}}
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    try:
        stored_rows, swaps, seen_ids = [], [], []
        for d in dates:
            games = _unstarted_games(conn, d, now)
            out["games"] += len(games)
            if not games:
                continue
            ids = sorted(games)
            latest = _latest(conn, ids)
            observed, df_ok, espn_ok = _observe_date(conn, d, games, latest, espn_fetch, df_fetch)
            out["observed"] += len(observed)
            out["dailyfaceoff"][d] = "ok" if df_ok else "not read"
            out["espn"][d] = "ok" if espn_ok else "not read"
            new = changes(latest, observed)
            # The rows still standing as stored: this read is their last_seen_at.
            new_keys = {(r["game_id"], r["team"], r["source"]) for r in new}
            for key in {(r["game_id"], r["team"], r["source"]) for r in observed} - new_keys:
                if latest.get(key, {}).get("designation_id") is not None:
                    seen_ids.append(latest[key]["designation_id"])
            resolver = _Resolver(conn, d)
            for r in new:
                r["player_id"] = resolver.player_id(r.get("player_name"))
                r["observed_at"] = now
                r["last_seen_at"] = now
                latest[(r["game_id"], r["team"], r["source"])] = r
            stored_rows += new
            # Rewrites are for TODAY's games only: tomorrow's rows do not exist
            # yet, and a past game is never touched.
            if d == today.isoformat():
                for gid, team, row in swaps_needed(latest, _stats_rows(conn, ids), set(ids)):
                    swaps.append((gid, team, row, resolver))
        out["stored"] = len(stored_rows)
        out["seen"] = len(seen_ids)
        for r in stored_rows:
            logger.info(f"NHL goalies: {r['game_id']} {r['team']} {r['source']}: "
                        f"{r.get('player_name')} ({r['status']})")
        if dry_run:
            out["swapped"] = [f"{g} {t} -> {row['player_name']}" for g, t, row, _ in swaps]
            conn.rollback()
            return out
        if stored_rows:
            conn.executemany(_INSERT, [{k: r.get(k) for k in (
                "game_id", "team", "player_id", "player_name", "source", "status",
                "source_player_id", "observed_at", "last_seen_at")} for r in stored_rows])
        if seen_ids:
            conn.execute(_SEEN, (now, sorted(seen_ids)))
        if swaps:
            from data.ingestors.nhl_stats_ingestor import _upsert_goalie_stats
            for gid, team, row, resolver in swaps:
                new_row = resolver.row(team, row["player_name"], row.get("player_id"), gid)
                conn.execute("DELETE FROM nhl_goalie_stats WHERE game_id = %s AND team = %s", (gid, team))
                _upsert_goalie_stats(conn, [new_row])
                logger.warning(f"NHL goalies: {gid} {team} goalie row rewritten to the "
                               f"ESPN-confirmed starter {row['player_name']}")
                out["swapped"].append(f"{gid} {team} -> {row['player_name']}")
        conn.commit()
        logger.info(f"NHL goalie designations: {out}")
        blind = sorted(d for d, v in out["espn"].items() if v != "ok")
        if blind:
            raise RuntimeError(
                f"ESPN not read for {', '.join(blind)}: a stored confirmation counts only "
                f"until {config.NHL_GOALIE_READ_MAX_AGE_MIN} minutes after a poll last read it "
                f"(config.NHL_GOALIE_READ_MAX_AGE_MIN)")
        return out
    except Exception:
        try:
            conn.rollback()
        except Exception:                                     # noqa: BLE001
            pass
        raise
    finally:
        if own:
            conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--today-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(run(today_only=a.today_only, dry_run=a.dry_run))


if __name__ == "__main__":
    main()

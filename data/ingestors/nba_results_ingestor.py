"""nba_results_ingestor.py -- NBA final scores and player box scores on the worker.

WHY THIS EXISTS. Until 2026-10-15 nothing on the Railway worker wrote NBA final
scores: they came only from nba_stats_ingestor (nba_api / stats.nba.com, which
blocks datacenter IPs), run by hand on Matt's machine, last on 2026-08-30. With
no score, no NBA game pick can settle, and with no box score no NBA prop can.
This step reads ESPN's site API, which the worker reaches (the WNBA results step
read it every hour on 2026-10-15), so every NBA pick of 2026-27 can settle
without Matt's machine. It is the NBA analog of wnba_results_ingestor.

WHAT IT WRITES, for ET dates [run_date - N .. run_date] (N = 3), plus a
14-day self-heal reach for any started game still missing a score or a box
(a worker outage longer than three days is caught up on the first pass back):
  * games               -- home_score, away_score, home_win, went_to_ot (ESPN's
                           period count > 4) for every FINAL game that already
                           has a `games` row, or that `nba_schedule` lists as a
                           regular-season game (then the row is inserted).
                           Preseason is ignored (ESPN season type 1, and no
                           `games` row). Play-in and playoff games are written
                           only when `games` already has them.
                           A score already stored is never overwritten: a
                           different ESPN score is logged as a WARNING and
                           counted (`score_conflicts`), because a final that
                           changes after its picks graded would break the
                           settled record (CLAUDE.md section 1c).
  * nba_player_game_log -- every player who played, for a final game that has no
                           log rows yet. A game is never skipped because one
                           player's id could not be found (that is how rookies'
                           games went unlogged under the old fill_missing).
  * nba_player_dnp      -- (created on demand) ESPN's did-not-play list for the
                           same game, with ESPN's reason ("COACH'S DECISION",
                           an injury note), plus players ESPN lists with '--'
                           minutes and no stats (reason NO MINUTES). Inactive
                           players are not in ESPN's box and so not here. A
                           --recheck run over past dates adds the list for
                           games already logged, once; it never touches their
                           box or score rows.

PLAYER IDS (load-bearing). nba_player_game_log keys players on the NBA.com
PERSON_ID, and a prop pick settles on (player_id, game_id). ESPN has its own
athlete ids. Resolution order, first hit wins:
  1. player_positions crosswalk -- source_athlete_id (ESPN) -> player_id
     (NBA.com), sport = 'NBA'.
  2. exact normalised name, same team, in nba_player_game_log over the last
     400 days -- only when exactly one id matches.
  3. exact normalised name anywhere in that log -- only when exactly one id
     matches (a traded player the crosswalk has not caught up with).
  4. FALLBACK 'espn:<athleteId>', so the row is never dropped. NBA.com ids are
     all digits, so the prefix can never collide with one. A rookie's later
     games resolve to the same fallback id (step 2 finds it in the log), so his
     own record stays on one id and his props settle against it.
Steps 2 and 3 never take an id the crosswalk gives to a DIFFERENT ESPN athlete,
nor another athlete's fallback id; and two box rows of one game never share an
id (the second falls back, with a warning).

KNOWN CONSEQUENCE OF THE FALLBACK. If the local nba_api job is later run over
the same 2026-27 dates, it writes the rookie again under his numeric id: two
rows for one player-game. Nothing reconciles them today.

WHY A SETTLED-LOOKING GAME CAN STILL BE WRONG, AND THE GUARD. Settlement treats
"game logged, player absent" as a DNP and voids the prop. So a box is written
only when it is complete: the players' points must add up to the final score of
each team, and the box must not be empty. A box ESPN has not finished filling is
left for the next pass.

COST. It self-limits: a date is fetched only when a game on it has started and
still lacks a score or a box. An idle pass makes no ESPN call at all. A busy one
makes one scoreboard call per such date and one summary call per final game
not yet logged.

Usage:
    python -m data.ingestors.nba_results_ingestor                     # trailing window
    python -m data.ingestors.nba_results_ingestor --date 2026-10-21
    python -m data.ingestors.nba_results_ingestor --start 2026-04-01 --end 2026-04-12 --dry-run --recheck
"""
from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from loguru import logger

from data.db import call_in_savepoint, get_connection, statement_timeout
from data.ingestors.nba_espn_box import (
    ESPN_NBA_SCOREBOARD_URL, ESPN_NBA_SUMMARY_URL, SEASON_TYPE_PRESEASON,
    parse_nba_box, parse_nba_dnp, parse_nba_scoreboard,
)
from data.ingestors.nba_stats_ingestor import _nba_season_for_date, _upsert_player_log
from data.ingestors.wnba_results_ingestor import norm_player_name

LOOKBACK_DAYS = 3
HEAL_DAYS = 14               # a started game still unscored/unlogged this far back
NAME_HISTORY_DAYS = 400
SUMMARY_SLEEP = 0.4          # between per-game summary calls
FALLBACK_PREFIX = "espn:"

_ET = ZoneInfo("America/New_York")

DNP_TABLE = "nba_player_dnp"
DNP_COLUMNS = ("game_id", "espn_athlete_id", "player_id", "player_name", "team",
               "game_date", "season", "reason", "created_at")
DNP_DDL = """
CREATE TABLE IF NOT EXISTS nba_player_dnp (
    game_id          TEXT NOT NULL,
    espn_athlete_id  TEXT NOT NULL,
    player_id        TEXT,
    player_name      TEXT NOT NULL,
    team             TEXT NOT NULL,
    game_date        TEXT NOT NULL,
    season           INTEGER NOT NULL,
    reason           TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, espn_athlete_id)
)
"""


# ── player ids ───────────────────────────────────────────────────────────────

def fallback_id(espn_id: str | None, name: str | None) -> str:
    """'espn:<athleteId>'; with no ESPN id, 'espn:name:<normalised-name>'."""
    espn_id = str(espn_id or "").strip()
    if espn_id:
        return f"{FALLBACK_PREFIX}{espn_id}"
    return f"{FALLBACK_PREFIX}name:{norm_player_name(name).replace(' ', '-')}"


class PlayerResolver:
    """ESPN athlete -> our player_id, in the order the module docstring gives.

    `crosswalk` is {espn_athlete_id: player_id}; `log_names` is an iterable of
    (player_id, player_name, team) from nba_player_game_log.
    """

    def __init__(self, crosswalk: dict, log_names):
        self.crosswalk = {str(k): str(v) for k, v in (crosswalk or {}).items() if k and v}
        self._claimed: dict[str, set[str]] = {}
        for espn_id, pid in self.crosswalk.items():
            self._claimed.setdefault(pid, set()).add(espn_id)
        self._by_team: dict[tuple, set[str]] = {}
        self._by_name: dict[str, set[str]] = {}
        for pid, name, team in log_names or ():
            key = norm_player_name(name)
            if not key or pid is None:
                continue
            pid = str(pid)
            self._by_team.setdefault((team, key), set()).add(pid)
            self._by_name.setdefault(key, set()).add(pid)

    def _free(self, pid: str, espn_id: str, name: str) -> bool:
        """A name match may not take an id that belongs to another ESPN athlete."""
        owners = self._claimed.get(pid)
        if owners and espn_id not in owners:
            return False
        if pid.startswith(FALLBACK_PREFIX) and pid != fallback_id(espn_id, name):
            return False
        return True

    def resolve(self, espn_id, name, team) -> tuple[str, str]:
        """(player_id, how) -- how is crosswalk | name_team | name_league | fallback."""
        espn_id = str(espn_id or "").strip()
        if espn_id and espn_id in self.crosswalk:
            return self.crosswalk[espn_id], "crosswalk"
        key = norm_player_name(name)
        if key:
            team_hits = {p for p in self._by_team.get((team, key), ())
                         if self._free(p, espn_id, name)}
            if len(team_hits) == 1:
                return next(iter(team_hits)), "name_team"
            if not team_hits:
                league_hits = {p for p in self._by_name.get(key, ())
                               if self._free(p, espn_id, name)}
                if len(league_hits) == 1:
                    return next(iter(league_hits)), "name_league"
        return fallback_id(espn_id, name), "fallback"


def build_log_rows(players: list[dict], resolver: PlayerResolver, game: dict,
                   tally: dict | None = None) -> tuple[list[dict], list[dict]]:
    """nba_player_game_log rows for every player in the box, and the players
    that took a fallback id. No player is dropped for want of an id. `tally`,
    when given, counts how each id was found."""
    rows: list[dict] = []
    fallbacks: list[dict] = []
    used: set[str] = set()
    for p in players:
        pid, how = resolver.resolve(p.get("espn_id"), p["name"], p["team"])
        if tally is not None:
            tally[how] = tally.get(how, 0) + 1
        if pid in used:
            logger.warning(f"NBA results: {p['name']} ({p['team']}) resolved to "
                           f"{pid}, already used in {game['game_id']}; falling back")
            pid, how = fallback_id(p.get("espn_id"), p["name"]), "fallback_duplicate"
            if pid in used:
                logger.warning(f"NBA results: {p['name']} appears twice in the "
                               f"{game['game_id']} box; second row dropped")
                continue
        used.add(pid)
        if how.startswith("fallback"):
            fallbacks.append({"game_id": game["game_id"], "player_id": pid,
                              "name": p["name"], "team": p["team"], "how": how})
        rows.append({
            "player_id": pid,
            "player_name": p["name"],
            "team": p["team"],
            "game_id": game["game_id"],
            "game_date": game["game_date"],
            "season": game["season"],
            "minutes": p["minutes"],
            # The column is INTEGER and Postgres refuses bool -> int implicitly
            # (the 2026-07-11 WNBA outage).
            "is_starter": 1 if p["starter"] else 0,
            "points": p["points"],
            "rebounds": p["rebounds"],
            "offensive_reb": p["offensive_reb"],
            "defensive_reb": p["defensive_reb"],
            "assists": p["assists"],
            "steals": p["steals"],
            "blocks": p["blocks"],
            "turnovers": p["turnovers"],
            "fg_made": p["fg_made"], "fg_att": p["fg_att"],
            "fg3_made": p["fg3_made"], "fg3_att": p["fg3_att"],
            "ft_made": p["ft_made"], "ft_att": p["ft_att"],
        })
    return rows, fallbacks


def build_dnp_rows(dnps: list[dict], resolver: PlayerResolver, game: dict) -> list[dict]:
    out = []
    for d in dnps:
        if not d.get("espn_id"):
            continue                       # the key; ESPN has always sent it
        pid, _how = resolver.resolve(d["espn_id"], d["name"], d["team"])
        out.append({"game_id": game["game_id"], "espn_athlete_id": d["espn_id"],
                    "player_id": pid, "player_name": d["name"], "team": d["team"],
                    "game_date": game["game_date"], "season": game["season"],
                    "reason": d.get("reason")})
    return out


def box_is_complete(rows: list[dict], game: dict, ev: dict) -> bool:
    """Players' points add up to each team's final score."""
    if not rows:
        return False
    want = {game["home"]: ev["home_score"], game["away"]: ev["away_score"]}
    got: dict[str, int] = {}
    for r in rows:
        if r["points"] is None:
            return False
        got[r["team"]] = got.get(r["team"], 0) + r["points"]
    return got == want


# ── matching ESPN events to our games ────────────────────────────────────────

def match_game(ev: dict, known: dict[str, dict]) -> dict | None:
    """Our game for an ESPN final: the same game_id, else the only game with the
    same home and away teams within a day (a `games` row before a schedule one)."""
    exact = known.get(ev["game_id"])
    if exact is not None and exact["source"] == "games":
        return exact
    d = date.fromisoformat(ev["game_date"])
    near = [g for g in known.values()
            if g["home"] == ev["home"] and g["away"] == ev["away"]
            and abs((date.fromisoformat(g["game_date"]) - d).days) <= 1]
    in_games = [g for g in near if g["source"] == "games"]
    if in_games:
        return in_games[0] if len(in_games) == 1 else None
    if exact is not None:
        return exact
    return near[0] if len(near) == 1 else None


def score_action(game: dict, ev: dict) -> dict | None:
    """What to write to `games` for this final, or None.

    kind: insert   -- a regular-season game only nba_schedule had
          fill     -- the stored score is missing
          ot       -- the score matches; went_to_ot is wrong or missing
          conflict -- a different score is stored; NOT written
    """
    hs, as_ = ev.get("home_score"), ev.get("away_score")
    if hs is None or as_ is None:
        return None
    base = {"game_id": game["game_id"], "home_score": hs, "away_score": as_,
            "home_win": 1 if hs > as_ else 0, "went_to_ot": ev.get("went_to_ot")}
    if game["source"] == "schedule":
        return {"kind": "insert", **base}
    cur_h, cur_a = game.get("home_score"), game.get("away_score")
    if cur_h is None or cur_a is None:
        return {"kind": "fill", **base}
    if (int(cur_h), int(cur_a)) == (hs, as_):
        ot = ev.get("went_to_ot")
        if ot is not None and game.get("went_to_ot") != ot:
            return {"kind": "ot", **base}
        return None
    return {"kind": "conflict", **base, "stored": (int(cur_h), int(cur_a))}


def _parse_ts(ts) -> datetime | None:
    s = str(ts or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def needs_work(game: dict, now: datetime) -> bool:
    """Started, and still missing a score or a box."""
    start = _parse_ts(game.get("commence_time"))
    if start is not None:
        started = start <= now
    else:
        started = game["game_date"] <= now.astimezone(_ET).strftime("%Y-%m-%d")
    if not started:
        return False
    return game.get("home_score") is None or not game.get("logged")


# ── database ─────────────────────────────────────────────────────────────────

class PgStore:
    """Every read and write this module makes, against data.db's connection."""

    def __init__(self, conn):
        self.conn = conn
        self._dnp_ready = False

    def _read(self, name, fn):
        return call_in_savepoint(self.conn, name, fn)

    def window_games(self, start: str, end: str) -> dict[str, dict]:
        def _games():
            return self.conn.execute("""
                SELECT g.game_id, g.game_date, g.season, g.home_team, g.away_team,
                       g.home_score, g.away_score, g.went_to_ot, g.commence_time,
                       EXISTS (SELECT 1 FROM nba_player_game_log l
                                WHERE l.game_id = g.game_id) AS logged
                  FROM games g
                 WHERE g.sport = 'NBA' AND g.game_date >= %s AND g.game_date <= %s
            """, (start, end)).fetchall()

        known: dict[str, dict] = {}
        for gid, gdate, season, home, away, hs, as_, ot, ct, logged in self._read(
                "nba_results_games", _games):
            known[gid] = {"game_id": gid, "game_date": str(gdate)[:10],
                          "season": int(season) if season is not None
                          else _nba_season_for_date(str(gdate)[:10]),
                          "home": home, "away": away, "home_score": hs,
                          "away_score": as_, "went_to_ot": ot, "commence_time": ct,
                          "logged": bool(logged), "source": "games"}

        def _schedule():
            return self.conn.execute("""
                SELECT s.game_id, s.game_date, s.season, s.home_team, s.away_team,
                       s.commence_time
                  FROM nba_schedule s
                 WHERE s.game_type = 'regular'
                   AND s.game_date >= %s AND s.game_date <= %s
                   AND NOT EXISTS (SELECT 1 FROM games g WHERE g.game_id = s.game_id)
            """, (start, end)).fetchall()

        try:
            sched = self._read("nba_results_sched", _schedule)
        except Exception as exc:                      # noqa: BLE001
            # nba_schedule is loaded by a local job; its absence only means a
            # game `games` lacks cannot be added here.
            logger.info(f"NBA results: nba_schedule not read ({str(exc)[:80]})")
            sched = []
        for gid, gdate, season, home, away, ct in sched:
            if gid in known:
                continue
            known[gid] = {"game_id": gid, "game_date": str(gdate)[:10],
                          "season": int(season), "home": home, "away": away,
                          "home_score": None, "away_score": None, "went_to_ot": None,
                          "commence_time": ct, "logged": False, "source": "schedule"}
        return known

    def resolver(self, since: str) -> PlayerResolver:
        def _xwalk():
            return self.conn.execute("""
                SELECT source_athlete_id, player_id FROM player_positions
                 WHERE sport = 'NBA' AND source_athlete_id IS NOT NULL
            """).fetchall()

        def _names():
            return self.conn.execute("""
                SELECT DISTINCT player_id, player_name, team FROM nba_player_game_log
                 WHERE game_date >= %s
            """, (since,)).fetchall()

        xwalk = {str(e): str(p) for e, p in self._read("nba_results_xwalk", _xwalk)}
        names = self._read("nba_results_names", _names)
        return PlayerResolver(xwalk, names)

    def is_logged(self, game_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM nba_player_game_log WHERE game_id = %s LIMIT 1",
            (game_id,)).fetchone() is not None

    def write_score(self, action: dict, game: dict) -> int:
        kind = action["kind"]
        if kind == "fill":
            cur = self.conn.execute("""
                UPDATE games SET home_score = %s, away_score = %s, home_win = %s,
                       went_to_ot = COALESCE(%s, went_to_ot), updated_at = NOW()::TEXT
                 WHERE game_id = %s AND sport = 'NBA'
                   AND (home_score IS NULL OR away_score IS NULL)
            """, (action["home_score"], action["away_score"], action["home_win"],
                  action["went_to_ot"], action["game_id"]))
            return cur.rowcount or 0
        if kind == "ot":
            cur = self.conn.execute("""
                UPDATE games SET went_to_ot = %s, updated_at = NOW()::TEXT
                 WHERE game_id = %s AND sport = 'NBA'
                   AND home_score = %s AND away_score = %s
            """, (action["went_to_ot"], action["game_id"],
                  action["home_score"], action["away_score"]))
            return cur.rowcount or 0
        if kind == "insert":
            cur = self.conn.execute("""
                INSERT INTO games (game_id, sport, season, game_date, home_team,
                    away_team, home_score, away_score, home_win, went_to_ot,
                    commence_time, data_source, created_at, updated_at)
                VALUES (%s, 'NBA', %s, %s, %s, %s, %s, %s, %s, %s, %s, 'espn',
                        NOW()::TEXT, NOW()::TEXT)
                ON CONFLICT (game_id) DO NOTHING
            """, (action["game_id"], game["season"], game["game_date"], game["home"],
                  game["away"], action["home_score"], action["away_score"],
                  action["home_win"], action["went_to_ot"] or 0, game.get("commence_time")))
            return cur.rowcount or 0
        return 0

    def upsert_log(self, rows: list[dict]) -> int:
        return _upsert_player_log(self.conn, rows)

    def ensure_dnp_table(self) -> None:
        """Create nba_player_dnp once. Gated on the catalog: CREATE TABLE IF NOT
        EXISTS is real DDL and fires PostgREST's schema reload (data/ddl_guard.py)."""
        if self._dnp_ready:
            return
        from data.anon_readable import API_ROLES, lock_down
        from data.ddl_guard import schema_is_current
        if not schema_is_current(self.conn, DNP_TABLE, columns=DNP_COLUMNS,
                                 rls=True, revoked_from=API_ROLES):
            self.conn.execute(DNP_DDL)
            lock_down(self.conn, DNP_TABLE)
            self.conn.commit()
        self._dnp_ready = True

    def has_dnp(self, game_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM nba_player_dnp WHERE game_id = %s LIMIT 1",
            (game_id,)).fetchone() is not None

    def upsert_dnp(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        self.conn.executemany("""
            INSERT INTO nba_player_dnp (game_id, espn_athlete_id, player_id,
                player_name, team, game_date, season, reason)
            VALUES (%(game_id)s, %(espn_athlete_id)s, %(player_id)s, %(player_name)s,
                    %(team)s, %(game_date)s, %(season)s, %(reason)s)
            ON CONFLICT (game_id, espn_athlete_id) DO NOTHING
        """, rows)
        return len(rows)


# ── ESPN ─────────────────────────────────────────────────────────────────────

def _http_get_json(url: str, params: dict) -> dict:
    """GET with one retry on a timeout, a dropped connection or a 5xx. A 4xx
    (ESPN's 403 IP block) is not retried: it raises at once."""
    import requests
    from data.ingestors.injury_ingestor import ESPN_HEADERS

    last: Exception | None = None
    for attempt in range(2):
        try:
            resp = requests.get(url, params=params, headers=ESPN_HEADERS, timeout=20)
            if resp.status_code < 500:
                resp.raise_for_status()
                return resp.json()
            last = requests.HTTPError(f"{resp.status_code} from {url}")
        except requests.HTTPError:
            raise
        except requests.RequestException as exc:
            last = exc
        time.sleep(2.0 * (attempt + 1))
    raise last  # type: ignore[misc]


# ── the step ─────────────────────────────────────────────────────────────────

def _shift(d: str, days: int) -> str:
    return (date.fromisoformat(d) + timedelta(days=days)).isoformat()


def _new_totals() -> dict:
    return {"dates_checked": 0, "dates_fetched": 0, "finals": 0, "preseason": 0,
            "not_in_games": 0, "scores_filled": 0, "games_inserted": 0,
            "ot_fixed": 0, "score_conflicts": 0, "box_games": 0, "box_rows": 0,
            "dnp_rows": 0, "box_incomplete": 0, "fallback_players": [],
            "resolved_by": {},
            "errors": 0, "failed": [], "planned_scores": [], "planned_box": []}


def ingest_nba_results(run_date: str | None = None, lookback_days: int = LOOKBACK_DAYS,
                       dates: list[str] | None = None, *, dry_run: bool = False,
                       recheck: bool = False, get_json=None, connect=None,
                       now: datetime | None = None, raise_on_error: bool = True,
                       sleep: float = SUMMARY_SLEEP, store=None,
                       heal_days: int = HEAL_DAYS) -> dict:
    """Scores and box scores for the window (or `dates`). Returns counts.

    Default window: run_date and the `lookback_days` before it, plus a
    self-heal reach of `heal_days` -- every date in it is gated the same way
    (a started game still missing a score or a box), so a worker outage longer
    than the lookback is caught up on the first pass back, at no cost when
    nothing is missing.

    dry_run  -- read everything, fetch everything, write nothing; the rows that
                would be written are returned in planned_scores / planned_box.
    recheck  -- ignore the self-limiting gate and parse every final's box, even
                one already logged (dry-run reconciliation). A live recheck still
                never rewrites a logged game.
    One game is one savepoint and one commit. A failed date or game is counted
    and the rest still run; with raise_on_error the call then raises, so the
    pipeline step goes red instead of silently green.
    """
    now = now or datetime.now(timezone.utc)
    if dates is None:
        run_date = run_date or now.astimezone(_ET).strftime("%Y-%m-%d")
        anchor = date.fromisoformat(run_date)
        reach = max(lookback_days, heal_days)
        dates = [(anchor - timedelta(days=i)).isoformat()
                 for i in range(reach, -1, -1)]
    dates = sorted(set(dates))
    if not dates:
        return _new_totals()
    get_json = get_json or _http_get_json
    if store is not None:                 # tests: an in-memory store
        own, conn = False, store.conn
    else:
        own = connect is None
        conn = (connect or get_connection)()
        store = PgStore(conn)
    totals = _new_totals()
    totals["dates_checked"] = len(dates)
    try:
        known = store.window_games(_shift(dates[0], -1), _shift(dates[-1], 1))
        # End the read transaction before any HTTP: no snapshot held open
        # while ESPN answers.
        conn.rollback()
        if recheck:
            targets = dates
        else:
            busy = {g["game_date"] for g in known.values() if needs_work(g, now)}
            targets = [d for d in dates if d in busy]
        totals["dates_fetched"] = len(targets)
        if not targets:
            logger.info(f"NBA results: nothing pending {dates[0]}..{dates[-1]} "
                        f"(no ESPN call)")
        resolver = None
        for d in targets:
            try:
                board = get_json(ESPN_NBA_SCOREBOARD_URL, {"dates": d.replace("-", "")})
            except Exception as exc:                  # noqa: BLE001
                logger.warning(f"NBA results: scoreboard {d} failed: {exc}")
                totals["errors"] += 1
                totals["failed"].append(d)
                continue
            for ev in parse_nba_scoreboard(board, d):
                if ev["game_date"] != d:
                    continue                          # the neighbouring date owns it
                totals["finals"] += 1
                if ev["season_type"] == SEASON_TYPE_PRESEASON:
                    totals["preseason"] += 1
                    continue
                game = match_game(ev, known)
                if game is None:
                    totals["not_in_games"] += 1
                    logger.info(f"NBA results: {ev['game_id']} is in neither games "
                                f"nor the regular-season schedule; ignored")
                    continue
                if resolver is None and (recheck or not game["logged"]):
                    resolver = store.resolver(_shift(dates[0], -NAME_HISTORY_DAYS))
                    conn.rollback()
                _one_game(ev, game, store, resolver, totals, get_json=get_json,
                          dry_run=dry_run, recheck=recheck, sleep=sleep)
    finally:
        if own:
            conn.close()

    fb = totals["fallback_players"]
    if fb:
        logger.warning(f"NBA results: {len(fb)} player(s) took a fallback id: "
                       f"{[(f['name'], f['team'], f['player_id']) for f in fb[:10]]}")
    summary = {k: v for k, v in totals.items()
               if k not in ("planned_scores", "planned_box", "fallback_players")}
    summary["fallback_players"] = len(fb)
    logger.info(f"NBA results{' (DRY RUN)' if dry_run else ''}: {summary}")
    if totals["failed"] and raise_on_error:
        raise RuntimeError(f"NBA results: {len(totals['failed'])} failure(s) "
                           f"({', '.join(totals['failed'])}); committed so far: {summary}")
    return totals


def _one_game(ev, game, store: PgStore, resolver, totals, *, get_json, dry_run,
              recheck, sleep) -> None:
    conn = store.conn
    action = score_action(game, ev)
    if action and action["kind"] == "conflict":
        totals["score_conflicts"] += 1
        logger.warning(f"NBA results: {game['game_id']} stored "
                       f"{action['stored'][0]}-{action['stored'][1]} (home-away), "
                       f"ESPN says {ev['home_score']}-{ev['away_score']}; NOT overwritten")
        action = None

    rows: list[dict] = []
    dnp: list[dict] = []
    if recheck or not game["logged"]:
        try:
            summary = get_json(ESPN_NBA_SUMMARY_URL, {"event": ev["event_id"]})
        except Exception as exc:                      # noqa: BLE001
            logger.warning(f"NBA results: summary for {game['game_id']} "
                           f"(event {ev['event_id']}) failed: {exc}")
            totals["errors"] += 1
            totals["failed"].append(game["game_id"])
            summary = None
        if sleep:
            time.sleep(sleep)
        if summary is not None:
            rows, fallbacks = build_log_rows(parse_nba_box(summary), resolver, game,
                                             tally=totals["resolved_by"])
            if box_is_complete(rows, game, ev):
                dnp = build_dnp_rows(parse_nba_dnp(summary), resolver, game)
                totals["fallback_players"].extend(fallbacks)
                for f in fallbacks:
                    logger.info(f"NBA results: {f['name']} ({f['team']}) in "
                                f"{f['game_id']} has no NBA.com id; stored as "
                                f"{f['player_id']}")
            else:
                totals["box_incomplete"] += 1
                logger.warning(f"NBA results: {game['game_id']} box incomplete "
                               f"({len(rows)} rows; points do not add up to "
                               f"{ev['home_score']}-{ev['away_score']}); next pass")
                rows = []

    if dry_run:
        if action:
            totals["planned_scores"].append(action)
        if rows:
            totals["planned_box"].append({"game_id": game["game_id"], "rows": rows,
                                          "dnp": dnp, "logged": game["logged"]})
        return

    if recheck and game["logged"]:
        # Never rewrite a logged game's box. Its did-not-play list is new data
        # nothing else stores, so a recheck over past dates adds it once.
        rows = []
    if not action and not rows and not dnp:
        return

    try:
        if dnp:
            store.ensure_dnp_table()

        def _write():
            out = {"score": 0, "box": 0, "dnp": 0}
            if action:
                out["score"] = store.write_score(action, game)
            if rows and not store.is_logged(game["game_id"]):
                out["box"] = store.upsert_log(rows)
            if dnp and (out["box"] or game["logged"]) \
                    and not store.has_dnp(game["game_id"]):
                out["dnp"] = store.upsert_dnp(dnp)
            return out

        out = call_in_savepoint(conn, "nba_results_game", _write)
        conn.commit()
    except Exception as exc:                          # noqa: BLE001
        if statement_timeout(exc):
            logger.warning(f"NBA results: {game['game_id']} timed out; next pass")
        else:
            logger.warning(f"NBA results: {game['game_id']} write failed: {exc}")
        totals["errors"] += 1
        totals["failed"].append(game["game_id"])
        try:
            conn.rollback()
        except Exception:                             # noqa: BLE001
            pass
        return

    if action and out["score"]:
        key = {"fill": "scores_filled", "insert": "games_inserted", "ot": "ot_fixed"}
        totals[key[action["kind"]]] += 1
    totals["dnp_rows"] += out["dnp"]
    if out["box"]:
        totals["box_games"] += 1
        totals["box_rows"] += out["box"]
        game["logged"] = True
    if action and action["kind"] in ("fill", "insert") and out["score"]:
        game["home_score"], game["away_score"] = action["home_score"], action["away_score"]
        game["source"] = "games"


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="NBA finals + box scores from ESPN")
    ap.add_argument("--date", help="one ET date YYYY-MM-DD")
    ap.add_argument("--start", help="first ET date of a range")
    ap.add_argument("--end", help="last ET date of a range")
    ap.add_argument("--run-date", help="anchor of the trailing window (default: today ET)")
    ap.add_argument("--lookback", type=int, default=LOOKBACK_DAYS)
    ap.add_argument("--dry-run", action="store_true", help="write nothing")
    ap.add_argument("--recheck", action="store_true",
                    help="ignore the pending gate; parse every final's box")
    a = ap.parse_args()
    dates = None
    if a.date:
        dates = [a.date]
    elif a.start and a.end:
        d, end, dates = date.fromisoformat(a.start), date.fromisoformat(a.end), []
        while d <= end:
            dates.append(d.isoformat())
            d += timedelta(days=1)
    ingest_nba_results(run_date=a.run_date, lookback_days=a.lookback, dates=dates,
                       dry_run=a.dry_run, recheck=a.recheck)


if __name__ == "__main__":
    main()

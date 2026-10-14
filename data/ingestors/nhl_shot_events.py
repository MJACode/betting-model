"""Every NHL shot attempt since 2018-19, from the league's free play-by-play feed.

Table and the reason it exists: data/migrations/add_nhl_shot_events.sql.

WHAT IS PULLED. `api-web.nhle.com/v1/gamecenter/<nhl_game_id>/play-by-play`, one
call per game (measured 2026-10-13: HTTP 200 in ~0.35 s, 120-160 KB). Every shot
on goal, missed shot, blocked shot and goal becomes one row. No key, no credits.

THE GAME LIST is nhl_team_game_log (2 = regular season, 3 = playoffs), read ONCE
at the start of a run, so a top-up landing mid-run cannot shift it. A game whose
feed is not final (`gameState` OFF / FINAL) is skipped and listed, never stored.

EVERYTHING LANDS IN SUPABASE IN THE RUN THAT FETCHES IT. Rows go in batches of
about 2,000 that never split a game, committed per batch, so a run that dies
leaves every game either whole or absent; the key is (nhl_game_id, event_id)
with ON CONFLICT DO NOTHING, and a game already stored is not fetched again. The
raw JSON is kept gzipped in a DISPOSABLE cache outside the repo
(%TEMP%/nhl_pbp_cache, or $NHL_PBP_CACHE_DIR) so a resumed run does not
re-download; deleting it loses nothing.

THE DATABASE IS LIVE. A short pause after every batch, and before every tenth
batch the run reads pg_stat_activity: more than 5 active queries, or one running
over 60 s, and it waits 2 minutes and looks again, naming what was busy.

DECODING. Each of these was checked against the feed, not assumed
(scripts/nhl_shot_events_verify.py re-runs the checks):

  * `situationCode` is four digits: away goalie in net, away skaters, home
    skaters, home goalie in net. "1451" on a home goal is the league's own
    "pp"; "0651" on a home goal is its "empty-net"; "1010" / "0101" is a penalty
    shot or a shootout attempt.
  * The shooting team is the SHOOTER's team on the game roster (`rosterSpots`),
    falling back to `eventOwnerTeamId` only when the shooter is not listed. A
    blocked shot's owner has been reported to be the blocking team; the roster
    makes that question moot, and the verify script measures it.
  * A blocked shot's coordinates are where it was BLOCKED and its zoneCode is
    the BLOCKING team's zone, so blocked shots never vote on which end a team
    attacks, and the xG model leaves them out.
  * The end each team attacks is decided per period from the events
    themselves: an event's zoneCode is its owner's zone, so an owner's event in
    its offensive zone at x > 0 means it attacks the +89 net. The feed's
    `homeTeamDefendingSide` is absent for all of 2018-19; where it exists it is
    stored as given and compared. Decisive votes win (they are what the
    coordinates were recorded against), then the feed, then the opposite of an
    adjacent period. `side_source` says which.

    python -m data.ingestors.nhl_shot_events --seasons 2019 2027 --limit 20   # dry run
    python -m data.ingestors.nhl_shot_events --seasons 2019 2027 --apply
    python -m data.ingestors.nhl_shot_events --games 2023020001 --apply
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import random
import tempfile
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

import requests
from loguru import logger

from data.db import ConnectionLost, DBConnection, get_connection
from data.ingestors.nhl_stats_ingestor import NHL_API_BASE, NHL_HEADERS, _norm_nhl

SOURCE = "nhl_api_pbp"
PBP_URL = NHL_API_BASE + "/gamecenter/{gid}/play-by-play"
SHOT_EVENTS = ("shot-on-goal", "missed-shot", "blocked-shot", "goal")
UNBLOCKED = ("shot-on-goal", "missed-shot", "goal")
FINAL_STATES = ("OFF", "FINAL")
GAME_TYPES = (2, 3)

NET_X = 89                 # goal lines at x = +/-89 ft
BLUE_LINE_X = 25           # blue lines at x = +/-25 ft
SIDE_MIN_VOTES = 3         # events needed before the derived end is trusted
SIDE_MIN_SHARE = 0.8       # ... and the share of them that must agree
FEED_SIDE = {"left": 1, "right": -1}   # home defends left -> home attacks +89

IN_FLIGHT = 4
MAX_ATTEMPTS = 5
HTTP_TIMEOUT = 30
WRITE_BATCH = 2_000
BATCH_PAUSE = 0.5
LOAD_CHECK_EVERY = 10
LOAD_MAX_ACTIVE = 5
LOAD_MAX_SECONDS = 60
LOAD_WAIT_SECONDS = 120

CACHE_DIR = Path(os.environ.get("NHL_PBP_CACHE_DIR")
                 or Path(tempfile.gettempdir()) / "nhl_pbp_cache")

SIT_KEYS = ("away_goalie_in_net", "away_skaters", "home_skaters", "home_goalie_in_net")
VIEW_KEYS = ("shooting_skaters", "defending_skaters", "empty_net",
             "shooting_goalie_pulled", "strength", "strength_state")

COLUMNS = (
    "nhl_game_id", "event_id", "game_id", "season", "game_type", "game_date",
    "sort_order", "period", "period_type", "period_seconds", "game_seconds",
    "event_type", "shot_type", "reason", "x", "y", "zone_code",
    "home_defending_side", "attacking_net_x", "side_source", "x_norm", "y_norm",
    "situation_code", *SIT_KEYS, *VIEW_KEYS,
    "shooting_team", "is_home", "event_owner_team", "shooter_id", "goalie_id",
    "blocker_id", "home_score_before", "away_score_before",
    "prev_event_type", "prev_team", "prev_zone_code", "prev_x", "prev_y",
    "prev_seconds_since", "source",
)
INSERT_SQL = (f"INSERT INTO nhl_shot_events ({', '.join(COLUMNS)}) "
              f"VALUES ({', '.join(f'%({c})s' for c in COLUMNS)}) "
              "ON CONFLICT (nhl_game_id, event_id) DO NOTHING")

LOAD_SQL = ("SELECT count(*) FILTER (WHERE state='active'), "
            "max(now()-query_start) FILTER (WHERE state='active') "
            "FROM pg_stat_activity WHERE datname=current_database()")
BUSY_SQL = ("SELECT pid, backend_type, round(extract(epoch FROM now()-query_start)), "
            "left(query, 80) FROM pg_stat_activity "
            "WHERE datname=current_database() AND state='active' "
            "ORDER BY query_start LIMIT 8")


@dataclass(frozen=True)
class GameMeta:
    nhl_game_id: int
    game_id: str
    season: int
    game_type: int
    game_date: str
    home: str
    away: str


class FetchFailed(RuntimeError):
    pass


# ── decoding (pure: tested without a network or a database) ─────────────────

def decode_situation(code) -> dict | None:
    """'1451' -> away goalie in net 1, away skaters 4, home skaters 5, home goalie 1."""
    if not isinstance(code, str) or len(code) != 4 or not code.isdigit():
        return None
    return dict(zip(SIT_KEYS, (int(c) for c in code)))


def shooter_view(sit: dict | None, is_home: bool, shootout: bool = False) -> dict:
    """The strength columns from the SHOOTING team's side.

    `strength` compares the skaters each side would have with its goalie in
    net, so an extra attacker is not a power play: 6v5 with the shooter's own
    net empty is EV, 6v4 is PP -- the league's own labelling.
    """
    out = dict.fromkeys(VIEW_KEYS)
    if sit is None:
        if shootout:
            out["strength"] = "SO"
        return out
    if is_home:
        shoot_sk, def_sk = sit["home_skaters"], sit["away_skaters"]
        shoot_g, def_g = sit["home_goalie_in_net"], sit["away_goalie_in_net"]
    else:
        shoot_sk, def_sk = sit["away_skaters"], sit["home_skaters"]
        shoot_g, def_g = sit["away_goalie_in_net"], sit["home_goalie_in_net"]
    out.update(shooting_skaters=shoot_sk, defending_skaters=def_sk,
               empty_net=int(def_g == 0), shooting_goalie_pulled=int(shoot_g == 0),
               strength_state=f"{shoot_sk}v{def_sk}")
    if shootout:
        out["strength"] = "SO"
    elif shoot_sk == 1 and def_sk == 0:
        out["strength"] = "PS"
    else:
        own = shoot_sk - (1 if shoot_g == 0 else 0)
        opp = def_sk - (1 if def_g == 0 else 0)
        out["strength"] = "PP" if own > opp else "SH" if own < opp else "EV"
    return out


def _sign(v) -> int:
    return 1 if v > 0 else -1 if v < 0 else 0


def _clock(s) -> int | None:
    """'MM:SS' -> seconds."""
    if not isinstance(s, str) or ":" not in s:
        return None
    m, sec = s.split(":", 1)
    try:
        return int(m) * 60 + int(sec)
    except ValueError:
        return None


def _period(p: dict) -> tuple[int | None, str | None]:
    pd_ = p.get("periodDescriptor") or {}
    return pd_.get("number"), pd_.get("periodType")


def period_sides(plays: list[dict], home_id, away_id) -> tuple[dict, dict]:
    """Which way the HOME team attacks in each non-shootout period (+1 = the net
    at x = +89) and how that was decided, plus the evidence for each period.

    Votes come from every non-blocked event with coordinates and an O / D zone:
    zoneCode is the event OWNER's zone, so an owner's event in its offensive
    zone at x > 0 means the owner attacks +89. Blocked shots do not vote (their
    zoneCode is the blocker's).
    """
    votes: dict[int, Counter] = defaultdict(Counter)
    feed: dict[int, Counter] = defaultdict(Counter)
    periods: set[int] = set()
    for p in plays:
        per, ptype = _period(p)
        if per is None or ptype == "SO":
            continue
        periods.add(per)
        fs = FEED_SIDE.get(p.get("homeTeamDefendingSide"))
        if fs:
            feed[per][fs] += 1
        if p.get("typeDescKey") == "blocked-shot":
            continue
        d = p.get("details") or {}
        x, zone, owner = d.get("xCoord"), d.get("zoneCode"), d.get("eventOwnerTeamId")
        if (x is None or zone not in ("O", "D") or owner not in (home_id, away_id)
                or abs(x) < BLUE_LINE_X):
            continue
        owner_sign = _sign(x) if zone == "O" else -_sign(x)
        votes[per][owner_sign if owner == home_id else -owner_sign] += 1

    chosen: dict[int, tuple[int, str]] = {}
    evidence: dict[int, dict] = {}
    for per in sorted(periods):
        v, n = votes[per], sum(votes[per].values())
        top, k = v.most_common(1)[0] if n else (None, 0)
        fs = feed[per].most_common(1)[0][0] if feed[per] else None
        evidence[per] = {"votes": n, "derived": top, "share": (k / n) if n else None,
                         "feed": fs}
        if n >= SIDE_MIN_VOTES and k / n >= SIDE_MIN_SHARE:
            chosen[per] = (top, "derived")
        elif fs:
            chosen[per] = (fs, "feed")
    for per in sorted(periods):            # teams switch ends every period
        if per not in chosen:
            for adj in (per - 1, per + 1):
                if adj in chosen and chosen[adj][1] != "adjacent":
                    chosen[per] = (-chosen[adj][0], "adjacent")
                    break
    for per, (sign, how) in chosen.items():
        evidence[per]["chosen"], evidence[per]["how"] = sign, how
    return chosen, evidence


def _shooter(p: dict):
    d = p.get("details") or {}
    return d.get("scoringPlayerId") if p.get("typeDescKey") == "goal" else d.get("shootingPlayerId")


def _event_team_id(p: dict, roster: dict):
    """A shot belongs to the shooter's team; anything else to its owner."""
    if p.get("typeDescKey") in SHOT_EVENTS:
        t = roster.get(_shooter(p))
        if t is not None:
            return t
    return (p.get("details") or {}).get("eventOwnerTeamId")


def parse_game(pbp: dict, meta: GameMeta, source: str = SOURCE) -> tuple[list[dict], dict]:
    """Rows for nhl_shot_events, plus the game's diagnostics.

    Raises ValueError when the feed's teams are not the game the log names --
    a game stored under the wrong teams is worse than one not stored.
    """
    home, away = pbp.get("homeTeam") or {}, pbp.get("awayTeam") or {}
    home_id, away_id = home.get("id"), away.get("id")
    feed_home, feed_away = _norm_nhl(home.get("abbrev") or ""), _norm_nhl(away.get("abbrev") or "")
    if (feed_home, feed_away) != (meta.home, meta.away):
        raise ValueError(f"teams {feed_away}@{feed_home} in the feed, "
                         f"{meta.away}@{meta.home} in nhl_team_game_log")
    abbrev = {home_id: meta.home, away_id: meta.away}
    roster = {r.get("playerId"): r.get("teamId") for r in pbp.get("rosterSpots") or []
              if r.get("playerId")}

    # CHRONOLOGICAL order: period, then the clock, then sortOrder within a
    # second. sortOrder alone is not chronological -- in 2018-19 an event
    # entered late gets a late sortOrder (2018020001 has a 5:38 blocked shot
    # sorted after a 7:14 miss), which would hand a shot the wrong previous
    # event and could put a goal into the wrong score state.
    diag: Counter = Counter()
    by_sort = sorted(pbp.get("plays") or [],
                     key=lambda p: (p.get("sortOrder") is None, p.get("sortOrder") or 0))
    last: dict = {}
    for p in by_sort:
        per, secs = _period(p)[0], _clock(p.get("timeInPeriod"))
        if per is not None and secs is not None:
            if per in last and secs < last[per]:
                diag["sortorder_not_chronological"] += 1
            last[per] = max(secs, last.get(per, secs))
    plays = sorted(by_sort, key=lambda p: (_period(p)[0] or 0,
                                           _clock(p.get("timeInPeriod")) or 0,
                                           p.get("sortOrder") or 0))
    seen: set = set()
    deduped = []
    for p in plays:
        eid = p.get("eventId")
        if eid is not None and eid in seen:
            diag["dup_event_ids"] += 1
            continue
        seen.add(eid)
        deduped.append(p)
    plays = deduped

    sides, side_evidence = period_sides(plays, home_id, away_id)
    meta_mismatch = {
        "game_type": pbp.get("gameType") != meta.game_type,
        "season": str(pbp.get("season")) != f"{meta.season - 1}{meta.season}",
        "game_date": pbp.get("gameDate") != meta.game_date,
    }

    def as_int(v):
        if v is None:
            return None
        if v != int(v):
            diag["nonint_coord"] += 1
        return int(round(v))

    rows: list[dict] = []
    home_goals = away_goals = 0
    sog = Counter()
    prev = None
    for p in plays:
        per, ptype = _period(p)
        kind = p.get("typeDescKey")
        if kind in SHOT_EVENTS and per is not None and p.get("eventId") is not None:
            d = p.get("details") or {}
            shooter = _shooter(p)
            team_id = _event_team_id(p, roster)
            if team_id not in (home_id, away_id):
                diag["unknown_team"] += 1
                prev = p
                continue
            is_home = team_id == home_id
            shootout = ptype == "SO"
            if roster.get(shooter) is None:
                diag["roster_miss"] += 1
            if kind == "blocked-shot":
                owner, blocker_team = d.get("eventOwnerTeamId"), roster.get(d.get("blockingPlayerId"))
                diag["blocked"] += 1
                diag["block_owner_not_shooter_team"] += int(owner != team_id)
                diag["block_owner_is_blocker_team"] += int(blocker_team is not None
                                                           and owner == blocker_team
                                                           and blocker_team != team_id)
                diag["teammate_block"] += int(blocker_team == team_id)
            sit = decode_situation(p.get("situationCode"))
            if sit is None:
                diag["missing_sitcode"] += 1
            view = shooter_view(sit, is_home, shootout)
            x, y = d.get("xCoord"), d.get("yCoord")
            if x is None or y is None:
                diag["missing_xy"] += 1
            if shootout:
                sign, how = (_sign(x), "shot") if x else (None, None)
            elif per in sides:
                hs, how = sides[per]
                sign = hs if is_home else -hs
            else:
                sign, how = None, None
                diag["no_side"] += 1
            secs = _clock(p.get("timeInPeriod"))
            same = prev is not None and _period(prev)[0] == per
            pv = (prev.get("details") or {}) if same else {}
            prev_secs = _clock(prev.get("timeInPeriod")) if same else None
            prev_team_id = _event_team_id(prev, roster) if same else None
            if kind in UNBLOCKED and not shootout and sit is not None:
                diag["goalie_digit_mismatch"] += int((d.get("goalieInNetId") is None)
                                                     != (view["empty_net"] == 1))
            row = {
                "nhl_game_id": meta.nhl_game_id, "event_id": int(p["eventId"]),
                "game_id": meta.game_id, "season": meta.season,
                "game_type": meta.game_type, "game_date": meta.game_date,
                "sort_order": p.get("sortOrder"), "period": per, "period_type": ptype,
                "period_seconds": secs,
                "game_seconds": (None if shootout or secs is None
                                 else (per - 1) * 1200 + secs),
                "event_type": kind, "shot_type": d.get("shotType"),
                "reason": d.get("reason"),
                "x": as_int(x), "y": as_int(y), "zone_code": d.get("zoneCode"),
                "home_defending_side": p.get("homeTeamDefendingSide"),
                "attacking_net_x": NET_X * sign if sign else None,
                "side_source": how if sign else None,
                "x_norm": as_int(x * sign) if sign and x is not None else None,
                "y_norm": as_int(y * sign) if sign and y is not None else None,
                "situation_code": p.get("situationCode"),
                **(sit or dict.fromkeys(SIT_KEYS)), **view,
                "shooting_team": abbrev[team_id], "is_home": int(is_home),
                "event_owner_team": abbrev.get(d.get("eventOwnerTeamId")),
                "shooter_id": shooter, "goalie_id": d.get("goalieInNetId"),
                "blocker_id": d.get("blockingPlayerId"),
                "home_score_before": home_goals, "away_score_before": away_goals,
                "prev_event_type": prev.get("typeDescKey") if same else None,
                "prev_team": abbrev.get(prev_team_id) if same else None,
                "prev_zone_code": pv.get("zoneCode"),
                "prev_x": as_int(pv.get("xCoord")), "prev_y": as_int(pv.get("yCoord")),
                "prev_seconds_since": (secs - prev_secs
                                       if secs is not None and prev_secs is not None
                                       else None),
                "source": source,
            }
            rows.append(row)
            if kind in ("shot-on-goal", "goal") and not shootout:
                sog["home" if is_home else "away"] += 1
            if kind == "goal" and not shootout:
                if is_home:
                    home_goals += 1
                else:
                    away_goals += 1
                if "homeScore" in d and (d.get("homeScore"), d.get("awayScore")) != (home_goals, away_goals):
                    diag["score_mismatch"] += 1
        prev = p

    diag["rows"] = len(rows)
    return rows, {
        "counts": diag,
        "sog_feed": (home.get("sog"), away.get("sog")),
        "sog_counted": (sog["home"], sog["away"]),
        "meta_mismatch": meta_mismatch,
        "feed_game_type": pbp.get("gameType"),
        "sides": side_evidence,
    }


# ── transport ────────────────────────────────────────────────────────────────

_local = threading.local()


def _session() -> requests.Session:
    s = getattr(_local, "session", None)
    if s is None:
        s = _local.session = requests.Session()
        s.headers.update(NHL_HEADERS)
    return s


def _cache_path(gid: int) -> Path:
    return CACHE_DIR / f"{gid}.json.gz"


def _write_cache(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{threading.get_ident()}")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def fetch_pbp(gid: int) -> dict:
    """One game's feed: the disposable cache if it holds it, else the API with
    retries and backoff. Only a FINAL feed is cached."""
    path = _cache_path(gid)
    if path.exists():
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError, EOFError):
            path.unlink(missing_ok=True)        # a torn cache file is re-fetched
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = _session().get(PBP_URL.format(gid=gid), timeout=HTTP_TIMEOUT)
            if r.status_code == 200:
                body = r.json()
                if body.get("gameState") in FINAL_STATES:
                    _write_cache(path, r.text)
                return body
            last = f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError) as exc:
            last = f"{type(exc).__name__}: {str(exc)[:120]}"
        if attempt < MAX_ATTEMPTS:
            time.sleep(min(2 ** attempt, 30) + random.uniform(0, 1))
    raise FetchFailed(f"{MAX_ATTEMPTS} attempts, last: {last}")


def process_game(meta: GameMeta) -> tuple[GameMeta, list[dict] | None, dict | None, str | None]:
    """Fetch and parse one game, in a worker thread. Never raises: a failure is
    returned, listed at the end, and the game is simply not stored."""
    try:
        pbp = fetch_pbp(meta.nhl_game_id)
    except FetchFailed as exc:
        return meta, None, None, f"fetch failed: {exc}"
    state = pbp.get("gameState")
    if state not in FINAL_STATES:
        return meta, None, None, f"not final (gameState={state})"
    try:
        rows, diag = parse_game(pbp, meta)
    except Exception as exc:                                  # noqa: BLE001
        logger.exception(f"{meta.nhl_game_id}: parse failed")
        return meta, None, None, f"parse failed: {type(exc).__name__}: {exc}"
    return meta, rows, diag, None


# ── database ─────────────────────────────────────────────────────────────────

def game_list(conn: DBConnection, first: int, last: int,
              only: list[int] | None = None) -> tuple[list[GameMeta], list[int]]:
    """Every played game in nhl_team_game_log for seasons first..last, one row
    each, with the home and away team. Returns the games and the ids whose log
    rows do not make exactly one home and one away team."""
    rows = conn.execute(
        "SELECT nhl_game_id, min(game_id), max(game_id), min(season), min(game_type), "
        "       min(game_date), max(CASE WHEN is_home = 1 THEN team END), "
        "       max(CASE WHEN is_home = 0 THEN team END), count(*), sum(is_home) "
        "FROM nhl_team_game_log WHERE season BETWEEN ? AND ? AND game_type IN (2, 3) "
        "GROUP BY nhl_game_id ORDER BY nhl_game_id", (first, last)).fetchall()
    conn.commit()
    games, odd = [], []
    for gid, gmin, gmax, season, gtype, gdate, home, away, n, n_home in rows:
        if only and gid not in only:
            continue
        if n != 2 or n_home != 1 or gmin != gmax or not home or not away:
            odd.append(gid)
            continue
        games.append(GameMeta(int(gid), gmin, int(season), int(gtype), gdate, home, away))
    return games, odd


def stored_game_ids(conn: DBConnection) -> set[int]:
    ids = {r[0] for r in conn.execute(
        "SELECT DISTINCT nhl_game_id FROM nhl_shot_events WHERE source = ?",
        (SOURCE,)).fetchall()}
    conn.commit()
    return ids


def wait_for_quiet_db(conn: DBConnection) -> tuple[int, float]:
    """Block until the database is quiet: at most LOAD_MAX_ACTIVE active
    queries and none running longer than LOAD_MAX_SECONDS."""
    waited = 0
    while True:
        conn.commit()            # a fresh transaction, so now() is this moment
        active, longest = conn.execute(LOAD_SQL).fetchone()
        conn.commit()
        secs = longest.total_seconds() if longest is not None else 0.0
        if active <= LOAD_MAX_ACTIVE and secs <= LOAD_MAX_SECONDS:
            logger.info(f"load check: {active} active, longest {secs:.1f}s"
                        + (f" (after waiting {waited}s)" if waited else ""))
            return active, secs
        busy = conn.execute(BUSY_SQL).fetchall()
        conn.commit()
        logger.warning(
            f"database busy: {active} active, longest {secs:.0f}s -- waiting "
            f"{LOAD_WAIT_SECONDS}s. " + " | ".join(
                f"pid {pid} {bt} {age}s {q!r}" for pid, bt, age, q in busy))
        time.sleep(LOAD_WAIT_SECONDS)
        waited += LOAD_WAIT_SECONDS


def insert_rows(conn: DBConnection, rows: list[dict]) -> None:
    """One batch, one transaction. A batch that loses its connection is re-run
    once on the reconnected handle; ON CONFLICT DO NOTHING makes that safe."""
    try:
        conn.executemany(INSERT_SQL, rows)
        conn.commit()
    except ConnectionLost:
        logger.warning("connection lost mid-batch -- re-running the batch")
        conn.executemany(INSERT_SQL, rows)
        conn.commit()


class BatchWriter:
    """Accumulates whole games and writes them ~WRITE_BATCH rows at a time."""

    def __init__(self, conn: DBConnection | None, apply: bool):
        self.conn, self.apply = conn, apply
        self.buf: list[dict] = []
        self.games_in_buf: list[int] = []
        self.batches = self.rows_written = self.games_written = 0

    def add(self, gid: int, rows: list[dict]) -> None:
        self.buf.extend(rows)
        self.games_in_buf.append(gid)
        if len(self.buf) >= WRITE_BATCH:
            self.flush()

    def flush(self) -> None:
        if not self.buf:
            return
        if self.apply:
            if self.batches % LOAD_CHECK_EVERY == 0:
                wait_for_quiet_db(self.conn)
            insert_rows(self.conn, self.buf)
            time.sleep(BATCH_PAUSE)
        self.batches += 1
        self.rows_written += len(self.buf)
        self.games_written += len(self.games_in_buf)
        if self.batches % 25 == 0:
            logger.info(f"{self.batches} batches, {self.games_written:,} games, "
                        f"{self.rows_written:,} rows" + ("" if self.apply else " (dry run)"))
        self.buf, self.games_in_buf = [], []


# ── the run ──────────────────────────────────────────────────────────────────

def run(first: int, last: int, apply: bool, only: list[int] | None = None,
        limit: int | None = None) -> dict:
    conn = get_connection()
    try:
        games, odd = game_list(conn, first, last, only)
        stored = stored_game_ids(conn) if apply else set()
        todo = [g for g in games if g.nhl_game_id not in stored]
        if limit:
            todo = todo[:limit]
        expected = Counter(g.season for g in games)
        logger.info(f"{len(games):,} games in nhl_team_game_log for {first}-{last} "
                    f"({dict(sorted(expected.items()))}); {len(stored):,} already "
                    f"stored; {len(todo):,} to do; {len(odd)} with odd log rows {odd[:10]}")
        if apply:
            wait_for_quiet_db(conn)

        writer = BatchWriter(conn, apply)
        failed: dict[int, str] = {}
        totals: dict[int, Counter] = defaultdict(Counter)
        sog_off: list[tuple] = []
        meta_off: list[tuple] = []
        empty: list[int] = []
        t0 = time.time()
        with ThreadPoolExecutor(IN_FLIGHT) as ex:
            it = iter(todo)
            pending: set = set()

            def top_up():
                while len(pending) < IN_FLIGHT * 2:
                    m = next(it, None)
                    if m is None:
                        return
                    pending.add(ex.submit(process_game, m))

            top_up()
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for fut in done:
                    pending.discard(fut)
                    meta, rows, diag, err = fut.result()
                    if err:
                        failed[meta.nhl_game_id] = err
                        logger.warning(f"{meta.nhl_game_id} ({meta.game_id}): {err}")
                        continue
                    totals[meta.season].update(diag["counts"])
                    totals[meta.season]["games"] += 1
                    if diag["sog_feed"] != diag["sog_counted"]:
                        sog_off.append((meta.nhl_game_id, diag["sog_feed"], diag["sog_counted"]))
                    if any(diag["meta_mismatch"].values()):
                        meta_off.append((meta.nhl_game_id, meta.game_id, diag["feed_game_type"],
                                         {k for k, v in diag["meta_mismatch"].items() if v}))
                    if not rows:
                        empty.append(meta.nhl_game_id)
                        continue
                    writer.add(meta.nhl_game_id, rows)
                top_up()
        writer.flush()
        mins = (time.time() - t0) / 60
        logger.success(f"done in {mins:.1f} min: {writer.games_written:,} games, "
                       f"{writer.rows_written:,} rows in {writer.batches} batches"
                       + ("" if apply else " (dry run: nothing written)"))
        for season in sorted(totals):
            logger.info(f"season {season}: {dict(totals[season])}")
        logger.info(f"feed sog != counted sog (non-shootout): {len(sog_off)} games "
                    f"{sog_off[:15]}")
        logger.info(f"feed metadata != nhl_team_game_log: {len(meta_off)} games {meta_off[:15]}")
        logger.info(f"games with no shot events: {len(empty)} {empty[:20]}")
        if failed:
            logger.warning(f"{len(failed)} games NOT stored:")
            for gid, err in sorted(failed.items()):
                logger.warning(f"  {gid}: {err}")
        return {"games": writer.games_written, "rows": writer.rows_written,
                "failed": failed, "sog_off": sog_off, "meta_off": meta_off, "empty": empty}
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"),
                    default=(2019, 2027), help="ENDING years, inclusive")
    ap.add_argument("--games", nargs="+", type=int, help="only these nhl_game_ids")
    ap.add_argument("--limit", type=int, help="at most this many games (a trial run)")
    ap.add_argument("--apply", action="store_true", help="write to Supabase")
    a = ap.parse_args()
    run(a.seasons[0], a.seasons[1], a.apply, only=a.games, limit=a.limit)

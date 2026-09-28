"""
One MLB game_id per PHYSICAL game, doubleheaders included.

WHY THIS EXISTS
---------------
Every MLB ingestor used to mint `MLB_<date>_<away>_<home>` on its own, so both
games of a doubleheader collapsed into one id (docs/followups.md, "Doubleheaders
collide under one game_id"). On 2026-09-25 BAL@NYY game 1's in-play prices and
final score landed on the same `games` row as game 2's pre-game board: a +3300
live NYY price read as a pre-game edge, and a game-2 pick settled on game 1's
box score before game 2 had started.

THE RULE
--------
Game 1 -- and every single game, which the Stats API numbers 1 -- keeps the id
it always had. Game 2 gets `_G2`. Nothing already stored for a single game or a
game 1 changes id, so every existing join keeps working.

The game number comes from the MLB Stats API (`gameNumber`, or `game_num` in the
statsapi wrapper), which is the only feed that knows it. A sportsbook feed (The
Odds API, Action Network) carries a start time instead, and `game_number_for_start`
maps that start onto the Stats API schedule for the same matchup and date.

What happens when the schedule cannot be read: the last good read is kept
(refetch after a minute). With none at all, a lone event for a matchup keeps
the old base id, while two or more events are matched against the base /
`_G2` rows already in `games` -- and DROPPED, at ERROR, when there is nothing
to match, rather than collapsed onto one row. Settlement fails closed on such
a day (tracking/paper_tracker._mlb_settle_holds).

A sportsbook event, once assigned on a doubleheader day, keeps its game_id
(`MlbEventBatch`, `mlb_event_game_map`), so a book moving a start later never
moves the event to the other game.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from loguru import logger

_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date}"

# A traditional doubleheader's game 2 is listed with startTimeTBD and a
# placeholder gameDate FIVE MINUTES after game 1 (measured on the 2026 schedule:
# BAL@NYY 09-25 is 20:05Z / 20:10Z, HOU@BAL 04-30 16:35Z / 16:40Z). Matching a
# book's start time against that placeholder would hand game 1 to game 2 on any
# book that lists game 1 a few minutes late. Game 2 of a traditional
# doubleheader starts after game 1 ends, so its effective start is game 1's
# plus a typical game and the break between them.
TBD_GAME_GAP = timedelta(hours=3)

# The schedule for a date changes (a rainout becomes tomorrow's doubleheader),
# so it is re-read at most this often. The live odds loop runs every few
# minutes and must not call the Stats API on every pass.
_SCHEDULE_TTL_S = 15 * 60
# After a FAILED read, retry this soon -- and meanwhile keep serving the last
# good schedule. One failed fetch used to cache "no games" over a good schedule
# for the whole 15 minutes, which sent game 2's odds back to the base row.
_SCHEDULE_RETRY_S = 60
_schedule_cache: dict[str, tuple[float, list[dict]]] = {}      # last GOOD read
_schedule_failed: dict[str, float] = {}                        # last failed read


def mlb_game_id(game_date: str, away: str, home: str,
                game_number: int | None = 1) -> str:
    """`MLB_<date>_<away>_<home>`, plus `_G<n>` for the second game of a day."""
    base = f"MLB_{game_date}_{away}_{home}"
    try:
        n = int(game_number or 1)
    except (TypeError, ValueError):
        n = 1
    return base if n < 2 else f"{base}_G{n}"


def parse_mlb_game_id(game_id: str) -> tuple[str, str, str, int] | None:
    """(date, away, home, game_number) from an MLB game_id, `_G<n>` included.
    None for anything that is not one."""
    parts = (game_id or "").split("_")
    if len(parts) < 4 or parts[0] != "MLB":
        return None
    n = 1
    if len(parts) == 5 and parts[4].startswith("G") and parts[4][1:].isdigit():
        n = int(parts[4][1:])
    elif len(parts) != 4:
        return None
    return parts[1], parts[2], parts[3], n


def game_number(game: dict) -> int:
    """The Stats API game number from either the raw schedule (`gameNumber`)
    or the statsapi wrapper (`game_num`). 1 when absent or unreadable."""
    raw = game.get("game_num", game.get("gameNumber"))
    try:
        return max(int(raw), 1)
    except (TypeError, ValueError):
        return 1


def _ts(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fetch_schedule(game_date: str) -> list[dict]:
    """Raw Stats API schedule games for one date. Raises on failure.
    Isolated so tests replace it (tests/conftest.py stubs it to [])."""
    import requests
    resp = requests.get(_SCHEDULE_URL.format(date=game_date), timeout=15)
    resp.raise_for_status()
    return [g for d in resp.json().get("dates", []) for g in d.get("games", [])]


def _schedule_games(game_date: str) -> list[dict] | None:
    """The raw schedule for a date: fresh, or the last GOOD read while a
    refetch is failing, or None when no read has ever succeeded (unknown --
    NOT the same as a day with no games)."""
    now = time.monotonic()
    good = _schedule_cache.get(game_date)
    if good and now - good[0] < _SCHEDULE_TTL_S:
        return good[1]
    failed = _schedule_failed.get(game_date)
    if failed is not None and now - failed < _SCHEDULE_RETRY_S:
        return good[1] if good else None
    try:
        games = _fetch_schedule(game_date)
    except Exception as exc:                                # noqa: BLE001
        _schedule_failed[game_date] = now
        if good:
            logger.warning(f"MLB schedule {game_date} refetch failed ({exc}); "
                           f"keeping the last good read, retry in "
                           f"{_SCHEDULE_RETRY_S}s")
            return good[1]
        logger.error(f"MLB schedule {game_date} unavailable ({exc}) and never "
                     f"read: doubleheader ids cannot be verified this pass")
        return None
    _schedule_failed.pop(game_date, None)
    _schedule_cache[game_date] = (now, games)
    return games


def schedule_state(game_date: str) -> dict[tuple[str, str], list[tuple[int, datetime]]] | None:
    """{(away, home): [(game_number, effective_start_utc), ...]} for one date,
    or None when the schedule has never been read (fail closed on that).

    A suspended game resumed on this date is listed on it too, under its
    ORIGINAL officialDate and game number (SF@ATL gamePk 824912: suspended
    06-16, resumed 06-17 18:00Z, listed on 06-17 beside that day's 824913,
    both gameNumber 1). It belongs to its original date's id, so it is left
    out: it is not this date's game, and not a doubleheader."""
    games = _schedule_games(game_date)
    if games is None:
        return None
    from data.ingestors.mlb_stats_ingestor import STATSAPI_TEAM_IDS
    out: dict[tuple[str, str], list[tuple[int, datetime, bool]]] = {}
    for g in games:
        if g.get("officialDate") and g["officialDate"] != game_date:
            continue                              # resumed from an earlier date
        teams = g.get("teams", {})
        away = STATSAPI_TEAM_IDS.get(teams.get("away", {}).get("team", {}).get("id"))
        home = STATSAPI_TEAM_IDS.get(teams.get("home", {}).get("team", {}).get("id"))
        start = _ts(g.get("gameDate"))
        if not away or not home or start is None:
            continue
        out.setdefault((away, home), []).append(
            (game_number(g), start, bool(g.get("status", {}).get("startTimeTBD"))))

    resolved: dict[tuple[str, str], list[tuple[int, datetime]]] = {}
    for key, rows in out.items():
        rows.sort(key=lambda r: r[0])
        eff: list[tuple[int, datetime]] = []
        for n, start, tbd in rows:
            if tbd and eff:
                _tbd_placeholder[(game_date, *key, n)] = start
                start = max(start, eff[-1][1] + TBD_GAME_GAP)
            eff.append((n, start))
        resolved[key] = eff
    return resolved


# MLB's placeholder start for a TBD game 2 (game 1 + 5 min), kept beside the
# effective start: a book may list game 2 AT the placeholder, so an event near
# it is not evidence of game 1.
_tbd_placeholder: dict[tuple[str, str, str, int], datetime] = {}

# How close a lone event's start must be to a scheduled game to be placed on
# it by time alone. Near no game is ambiguous (a game 1 delayed 91+ minutes).
MATCH_WINDOW = timedelta(minutes=60)

# Near TWO games, the closer one wins unless the two distances are within
# TIE_TOLERANCE of each other. Why 2 minutes: book start times are minute
# precision and are seen a minute off MLB's (CIN@CWS 2026-08-13 was listed
# 17:11Z for a 17:10Z first pitch), and a 1-minute offset in the event's start
# moves the DIFFERENCE between its two distances by up to 2 minutes. Closer
# than that, which game the book meant is noise. The tightest real case is a
# traditional doubleheader: game 1 at 20:05Z, game 2's TBD placeholder at
# 20:10Z. A book listing game 1 at 20:05-20:06 gets game 1, a book listing
# game 2 at the placeholder (20:09-20:10) gets game 2, and 20:07-20:08 is a
# tie and refused. An event keeps its first assignment (`_EventMap`), so
# game 2's event arriving later goes to the one game left, never onto game 1.
TIE_TOLERANCE = timedelta(minutes=2)


def unambiguous_game_number(game_date: str, away: str, home: str,
                            candidates: list[tuple[int, datetime]] | None,
                            start, *, closest: bool = True) -> int | None:
    """The scheduled game this start belongs to by time alone, or None.

    Near = within MATCH_WINDOW of the effective start or, for a TBD game, of
    its placeholder; a game's distance is the smaller of the two. Near no game
    is None (a game 1 delayed 91+ minutes is 89 minutes from game 2's
    effective start). Near one game is that game. Near several: the closest,
    unless the best two are within TIE_TOLERANCE (None). `closest=False` keeps
    the strict rule -- near several is None -- for settlement's check 2, which
    only ever HOLDS on a positive answer and is left as reviewed."""
    ct = _ts(start)
    if not candidates or ct is None:
        return None
    near: dict[int, timedelta] = {}
    for n, eff in candidates:
        times = [t for t in (eff, _tbd_placeholder.get((game_date, away, home, n)))
                 if t is not None]
        d = min((abs(t - ct) for t in times), default=None)
        if d is not None and d <= MATCH_WINDOW:
            near[n] = d
    if len(near) == 1:
        return next(iter(near))
    if not near or not closest:
        return None
    (n1, d1), (_n2, d2) = sorted(near.items(), key=lambda kv: (kv[1], kv[0]))[:2]
    return n1 if d2 - d1 > TIE_TOLERANCE else None


def schedule_starts(game_date: str) -> dict[tuple[str, str], list[tuple[int, datetime]]]:
    """schedule_state, with an unknown schedule as {} (every game is game 1)."""
    return schedule_state(game_date) or {}


def game_number_for_start(candidates: list[tuple[int, datetime]] | None,
                          commence_time) -> int:
    """The scheduled game whose start is nearest a book's start time.

    Used for ONE event seen on its own. Two or more events for the matchup in
    one batch are assigned by start order instead (`MlbEventBatch`), and an
    event already assigned keeps its id (`_EventMap`). Ties go to the lower
    game number. No candidates, or no parseable start, is game 1."""
    ct = _ts(commence_time)
    if not candidates or ct is None:
        return 1
    return min(candidates,
               key=lambda c: (abs((c[1] - ct).total_seconds()), c[0]))[0]


# ── event id -> game_id, assigned once ───────────────────────────────────────
#
# Nearest-start matching alone can swap or collapse the two games when a book
# moves one: a game 1 delayed 91+ minutes sits nearer game 2's effective start,
# and a game 2 listed at MLB's placeholder (game 1 + 5 min) sits nearer game 1.
# So the FIRST assignment of a sportsbook event is recorded and never redone:
# in memory for the process, and in `mlb_event_game_map`
# (data/migrations/mlb_event_game_map_2026_09_28.sql, UNAPPLIED) across
# restarts. Until that table exists the map is memory-only and says so once.
# One game_id holds one event per source: a second event that resolves to an
# already-claimed game_id is logged at ERROR and its rows are dropped.

_EVENT_MAP_DB = True                 # tests/conftest.py turns the DB side off
_DB_RETRY_S = 15 * 60


class _EventMap:
    def __init__(self):
        self.by_event: dict[tuple[str, str], str] = {}
        self.by_game: dict[tuple[str, str], str] = {}
        self._db_off_until = 0.0

    def clear(self):
        self.by_event.clear()
        self.by_game.clear()
        self._db_off_until = 0.0

    # The DB side. Every failure (table missing, connection) degrades to the
    # memory map; a missing table is the expected state until the migration.
    def _db(self):
        if not _EVENT_MAP_DB or time.monotonic() < self._db_off_until:
            return None
        try:
            from data.db import get_connection
            return get_connection()
        except Exception as exc:                            # noqa: BLE001
            self._db_disable(exc)
            return None

    def _db_disable(self, exc):
        self._db_off_until = time.monotonic() + _DB_RETRY_S
        logger.warning(f"mlb_event_game_map unavailable ({exc}); event ids are "
                       f"remembered in memory only for {_DB_RETRY_S // 60} min")

    def load(self, source: str, game_date: str, away: str, home: str) -> None:
        """Pull this matchup's recorded assignments into memory."""
        conn = self._db()
        if conn is None:
            return
        try:
            rows = conn.execute(
                "SELECT event_id, game_id FROM mlb_event_game_map "
                "WHERE source = %s AND game_date = %s AND away_team = %s "
                "AND home_team = %s", (source, game_date, away, home)).fetchall()
            for event_id, game_id in rows:
                self.by_event[(source, str(event_id))] = game_id
                self.by_game.setdefault((source, game_id), str(event_id))
        except Exception as exc:                            # noqa: BLE001
            self._db_disable(exc)
        finally:
            _close(conn)

    def claim(self, source: str, event_id: str, game_id: str, game_date: str,
              away: str, home: str, commence) -> str | None:
        """Record event -> game_id. Returns the game_id when this event holds
        it, None when another event already does (the caller drops it)."""
        held_by = self.by_game.get((source, game_id))
        if held_by is not None and held_by != event_id:
            return None
        conn = self._db()
        if conn is not None:
            try:
                conn.execute(
                    "INSERT INTO mlb_event_game_map (source, event_id, game_id, "
                    "game_date, away_team, home_team, commence_time) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (source, event_id, game_id, game_date, away, home,
                     _ts(commence).isoformat() if _ts(commence) else None))
                conn.commit()
                row = conn.execute(
                    "SELECT event_id FROM mlb_event_game_map "
                    "WHERE source = %s AND game_id = %s",
                    (source, game_id)).fetchone()
                if row and str(row[0]) != event_id:
                    self.by_game[(source, game_id)] = str(row[0])
                    return None
                row = conn.execute(
                    "SELECT game_id FROM mlb_event_game_map "
                    "WHERE source = %s AND event_id = %s",
                    (source, event_id)).fetchone()
                if row and row[0] != game_id:        # another process got here
                    self.by_event[(source, event_id)] = row[0]
                    self.by_game[(source, row[0])] = event_id
                    return row[0]
            except Exception as exc:                        # noqa: BLE001
                self._db_disable(exc)
            finally:
                _close(conn)
        self.by_event[(source, event_id)] = game_id
        self.by_game[(source, game_id)] = event_id
        return game_id

    def existing_rows(self, game_date: str, away: str, home: str) -> dict[int, datetime]:
        """{game_number: commence_time} of the base / _G2 games rows already
        stored for the matchup. The cold-failure fallback matches on these."""
        conn = self._db()
        if conn is None:
            return {}
        base = mlb_game_id(game_date, away, home)
        try:
            rows = conn.execute(
                "SELECT game_id, commence_time FROM games WHERE game_id IN (%s, %s)",
                (base, base + "_G2")).fetchall()
        except Exception as exc:                            # noqa: BLE001
            logger.warning(f"games lookup for {base} failed ({exc})")
            return {}
        finally:
            _close(conn)
        out = {}
        for gid, ct in rows:
            parsed = parse_mlb_game_id(gid)
            if parsed and _ts(ct):
                out[parsed[3]] = _ts(ct)
        return out


def _close(conn) -> None:
    try:
        conn.close()
    except Exception:                                       # noqa: BLE001
        pass


_event_map = _EventMap()


class MlbEventBatch:
    """Resolve every event of one ingest pass together.

    `add()` each MLB event first, then `game_id()` per event. Per matchup:
      0. a matchup the schedule lists once is a single game: base id, as
         before, nothing recorded;
      1. an event already assigned (this process or mlb_event_game_map) keeps
         its game_id, whatever its start says now;
      2. two or more NEW events are assigned by START ORDER to the scheduled
         games not already claimed (game numbers ascending);
      3. one new event goes to the one unclaimed game left, or by time to the
         scheduled game it is near (MATCH_WINDOW) -- the closest when near
         two, e.g. game 1 at its listed start vs game 2's TBD placeholder
         five minutes later; near none, or a tie (TIE_TOLERANCE), is DROPPED
         at ERROR, never guessed;
      4. schedule never read (cold Stats API failure): match against the
         base / _G2 rows already in `games`; with nothing to match, a lone
         event gets the base id (a single game, as before) and two or more
         are DROPPED -- the base id would collapse them;
      5. a result that would put a second event id on a claimed game_id is
         logged at ERROR and dropped (None).
    None means: do not write this event's rows this pass."""

    def __init__(self, source: str = "odds_api"):
        self.source = source
        self._events: dict[tuple[str, str, str], list[tuple[str | None, object]]] = {}
        self._done: dict[tuple[str, str, str], dict] = {}

    def add(self, game_date: str, away: str, home: str, event_id, commence) -> None:
        key = (game_date, away, home)
        ev = (str(event_id) if event_id else None, commence)
        lst = self._events.setdefault(key, [])
        if ev not in lst:
            lst.append(ev)
        self._done.pop(key, None)

    def game_id(self, game_date: str, away: str, home: str, event_id, commence) -> str | None:
        key = (game_date, away, home)
        eid = str(event_id) if event_id else None
        if (eid, commence) not in self._events.get(key, []):
            self.add(game_date, away, home, eid, commence)
        if key not in self._done:
            self._done[key] = self._resolve(game_date, away, home)
        return self._done[key].get((eid, str(commence)))

    def _resolve(self, game_date, away, home) -> dict:
        src, emap = self.source, _event_map
        events = self._events[(game_date, away, home)]
        out: dict[tuple, str | None] = {}
        base = mlb_game_id(game_date, away, home)
        sched = schedule_state(game_date)
        cands = (sched.get((away, home)) or []) if sched is not None else None

        # A matchup the schedule lists ONCE (or not at all) is a single game:
        # the base id, as always, with nothing recorded or refused. Only a
        # doubleheader -- or a day whose schedule cannot be read -- needs the
        # event map. (A book re-issuing a single game's event id must not have
        # its new id refused.)
        if cands is not None and len(cands) <= 1:
            n = cands[0][0] if cands else 1
            for e, ct in events:
                out[(e, str(ct))] = mlb_game_id(game_date, away, home, n)
            return out

        if any(e for e, _ in events if e and (src, e) not in emap.by_event):
            emap.load(src, game_date, away, home)
        claimed: dict[int, str] = {}                  # game number -> event id
        for (s, gid), e in emap.by_game.items():
            p = parse_mlb_game_id(gid)
            if s == src and p and p[:3] == (game_date, away, home):
                claimed[p[3]] = e
        new = []
        for e, ct in events:
            if e and (src, e) in emap.by_event:
                out[(e, str(ct))] = emap.by_event[(src, e)]
            else:
                new.append((e, ct))
        if not new:
            return out
        new.sort(key=lambda x: (_ts(x[1]) or datetime.max.replace(tzinfo=timezone.utc),
                                x[0] or ""))

        if cands is None:                              # schedule never read
            rows = emap.existing_rows(game_date, away, home)
            if 2 in rows:
                cands = sorted(rows.items())
            elif len(new) >= 2:
                for e, ct in new:
                    logger.error(
                        f"MLB {away}@{home} {game_date}: {len(new)} events and no "
                        f"schedule to tell the games apart; event {e} ({ct}) "
                        f"DROPPED this pass rather than collapsed onto {base}")
                    out[(e, str(ct))] = None
                return out
            else:
                e, ct = new[0]
                if claimed.get(1) not in (None, e):
                    logger.error(f"MLB {away}@{home} {game_date}: event {e} "
                                 f"would collapse onto {base} (held by event "
                                 f"{claimed[1]}) with no schedule; DROPPED")
                    out[(e, str(ct))] = None
                    return out
                logger.warning(f"MLB {away}@{home} {game_date}: schedule unavailable; "
                               f"lone event {e} filed under {base} unverified")
                out[(e, str(ct))] = base
                return out                             # unverified: not recorded

        free = sorted((c for c in cands if c[0] not in claimed), key=lambda c: c[0])
        picks: list[tuple[tuple, int]] = []
        starts = [_ts(ct) for _e, ct in new]
        if len(new) >= 2 and len(set(starts)) < len(starts):
            for e, ct in new:
                logger.error(f"MLB {away}@{home} {game_date}: two events share "
                             f"start {ct}; start order cannot tell them apart; "
                             f"event {e} DROPPED")
                out[(e, str(ct))] = None
        elif len(new) >= 2:
            picks = [(ev, c[0]) for ev, c in zip(new, free)]
            for e, ct in new[len(picks):]:
                logger.error(f"MLB {away}@{home} {game_date}: more events than "
                             f"unassigned games; event {e} ({ct}) DROPPED")
                out[(e, str(ct))] = None
        elif len(free) == 1 and claimed:
            # Every other game already has its event: this is the one left.
            picks = [(new[0], free[0][0])]
        elif free:
            e, ct = new[0]
            n = (unambiguous_game_number(game_date, away, home, free, ct)
                 if all(c[1] is not None for c in free) else free[0][0])
            if n is None:
                logger.error(f"MLB {away}@{home} {game_date}: event {e} ({ct}) is "
                             f"near no scheduled game, or equally near two "
                             f"({', '.join(f'G{c[0]} {c[1]:%H:%MZ}' for c in free)}); "
                             f"DROPPED until it is listed beside the other game "
                             f"or matches one")
                out[(e, str(ct))] = None
            else:
                picks = [((e, ct), n)]
        else:
            e, ct = new[0]
            logger.error(f"MLB {away}@{home} {game_date}: every scheduled game "
                         f"already has an event; event {e} ({ct}) DROPPED")
            out[(e, str(ct))] = None

        for (e, ct), n in picks:
            gid = mlb_game_id(game_date, away, home, n)
            if e:
                got = emap.claim(src, e, gid, game_date, away, home, ct)
                if got is None:
                    logger.error(f"MLB {away}@{home} {game_date}: event {e} resolved "
                                 f"to {gid}, already held by event "
                                 f"{emap.by_game.get((src, gid))}; rows DROPPED")
                gid = got
            out[(e, str(ct))] = gid
        return out


def mlb_event_game_id(game_date: str, away: str, home: str, commence_time,
                      event_id=None, source: str = "odds_api") -> str | None:
    """The game_id for ONE sportsbook event, doubleheader-aware. None = drop.
    A pass that sees several events should use MlbEventBatch."""
    b = MlbEventBatch(source)
    return b.game_id(game_date, away, home, event_id, commence_time)


def clear_cache() -> None:
    _schedule_cache.clear()
    _schedule_failed.clear()
    _tbd_placeholder.clear()
    _event_map.clear()


# ── snapshot_type, per snapshot ──────────────────────────────────────────────

def snapshot_type_for(requested: str, snapshot_at, commence_time) -> str:
    """The label ONE odds row earns from its own timestamp against ITS game's
    start -- not the label the caller stamped on the whole batch.

    * A pre-game label ('open' / 'close') on a snapshot taken after this
      event's start becomes 'in_play'. Same rule as odds_ingestor._mark_in_play:
      the evening refresh keeps writing rows after first pitch, and a live price
      wearing a pre-game label is the §7 leak.
    * An 'in_play' label on a snapshot taken more than
      first_pitch.SUSPICIOUS_EARLY_MINUTES before this event's start becomes
      'open'. No real game has gone live that early (the measured range ends at
      -36 minutes), so such a row is a pre-game quote -- on 2026-09-25 those
      were game 2's -115/-104 board labelled in_play because game 1 was live.
      Inside that window the caller's 'in_play' stands: games genuinely go live
      up to ~36 minutes before the listed start, and demoting those rows would
      manufacture the permissive leak.
    * Anything unparseable keeps the requested label (fail open, as before).
    """
    from data.first_pitch import SUSPICIOUS_EARLY_MINUTES
    snap, start = _ts(snapshot_at), _ts(commence_time)
    if snap is None or start is None:
        return requested
    if requested in ("open", "close") and snap > start:
        return "in_play"
    if requested == "in_play" and snap < start - timedelta(minutes=SUSPICIOUS_EARLY_MINUTES):
        return "open"
    return requested

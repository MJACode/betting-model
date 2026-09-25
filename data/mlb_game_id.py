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

Fails CLOSED to the old id: if the schedule cannot be fetched, every game is
game 1, which is exactly the behaviour before this module existed. That keeps a
Stats API outage from inventing ids, at the cost of the old collision on a
doubleheader day -- and the settlement guard in tracking/paper_tracker.py is
what stops that collision from grading a pick on the wrong game.
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
_schedule_cache: dict[str, tuple[float, list[dict]]] = {}


def mlb_game_id(game_date: str, away: str, home: str,
                game_number: int | None = 1) -> str:
    """`MLB_<date>_<away>_<home>`, plus `_G<n>` for the second game of a day."""
    base = f"MLB_{game_date}_{away}_{home}"
    try:
        n = int(game_number or 1)
    except (TypeError, ValueError):
        n = 1
    return base if n < 2 else f"{base}_G{n}"


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


def schedule_starts(game_date: str) -> dict[tuple[str, str], list[tuple[int, datetime]]]:
    """{(away, home): [(game_number, effective_start_utc), ...]} for one date.

    Empty on any failure: the caller then treats every game as game 1."""
    now = time.monotonic()
    hit = _schedule_cache.get(game_date)
    if hit and now - hit[0] < _SCHEDULE_TTL_S:
        games = hit[1]
    else:
        try:
            games = _fetch_schedule(game_date)
        except Exception as exc:                            # noqa: BLE001
            logger.warning(f"MLB schedule {game_date} unavailable ({exc}); "
                           f"doubleheader game 2s keep the game-1 id this pass")
            games = []
        _schedule_cache[game_date] = (now, games)

    from data.ingestors.mlb_stats_ingestor import STATSAPI_TEAM_IDS
    out: dict[tuple[str, str], list[tuple[int, datetime, bool]]] = {}
    for g in games:
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
                start = max(start, eff[-1][1] + TBD_GAME_GAP)
            eff.append((n, start))
        resolved[key] = eff
    return resolved


def game_number_for_start(candidates: list[tuple[int, datetime]] | None,
                          commence_time) -> int:
    """The scheduled game whose start is nearest a book's start time.

    Deterministic per event -- the bulk, per-event, props and live paths all see
    the same commence_time for one event, so they all land on the same id.
    Ties go to the lower game number. No candidates, or no parseable start,
    is game 1: the pre-existing id."""
    ct = _ts(commence_time)
    if not candidates or ct is None:
        return 1
    return min(candidates,
               key=lambda c: (abs((c[1] - ct).total_seconds()), c[0]))[0]


def mlb_event_game_id(game_date: str, away: str, home: str, commence_time) -> str:
    """The game_id for a sportsbook event, doubleheader-aware."""
    cands = schedule_starts(game_date).get((away, home))
    return mlb_game_id(game_date, away, home,
                       game_number_for_start(cands, commence_time))


def clear_cache() -> None:
    _schedule_cache.clear()


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

"""
The stored schedule, read one way for every sport: what a team has played,
what it still has to play before a game, and whether a model may decide it yet.

mike, 2026-10-20: "The repo/models should look ahead schedules for all markets
and sports and models."

WHY
---
Several pre-game models decide days before kickoff, and every one of them read
a team's recent history from games ALREADY PLAYED. A game the team still had
to play before this one was invisible, so it looked like a bye. Measured on
production (read-only, 2026-10-20; summarised in docs/sessions/2026-10.md and
the sport docs):

  * ncaaf_over_under decided 9 of its 77 kept BETs before one of the two teams
    played an intermediate game. On all 8 graded ones the rest read 12-21 days
    where the true rest was 6-8, and games played, the early-season flag and
    every team stat were one game stale. Those 8 went 3-5, -2.31 units, against
    36-25, +7.48 units on the other 61.
  * wnba_moneyline bet the opening price of game N+1 1.6 to 61.6 seconds after
    the odds feed listed it, while game N was still being played (5 postseason
    BETs; 11 of 40 BETs were written before a team's previous game was in the
    database).
  * The NFL opener spread model evaluated CAR @ GB (10-29) on 10-20, before both
    teams' week-7 games.
  * mlb_f5_moneyline wrote 14 of its 119 BETs since 2026-07-05 before the
    morning run had logged a team's previous game (-5.54 units on those 14,
    -1.42 on the other 91). MLB is live through the World Series (game 1
    2026-10-23) and scores 7 days ahead.

THE RULE. A pre-game model never decides while either team still has an earlier
game that is not played, being played, or played but not yet in the logs that
model's inputs read. Its number is still written, as NONE, with the reason
("waiting for Wisconsin's 2026-10-17 game to be played and logged"): an empty
board and a broken pipeline look the same. NONE never locks (the game lock is
BET-only), so the first pass after the game is logged decides it.

WHAT COUNTS AS ONE GAME. The stored schedule holds several rows for one game.
These are the repo's existing rules, not new ones:

  * UFC, NCAAF and NFL (tracking.record_duplicates.NO_SERIES_SPORTS): a team or
    fighter never plays twice inside two days, so every row for that team
    within a day of another is the same event. This also catches the NCAAF
    night-game stub (the odds feed's ET-dated row beside CFBD's UTC-dated one)
    and the opponent spelled two ways ('LIU Sharks' beside 'Long Island
    University'), which an opponent-name match cannot: measured 2026-10-20, all
    10 past unscored NCAAF odds-feed rows since May with a price had a scored
    row for one of their two teams, under the same name, within a day; the
    alias rule (cfbd_ingestor._slug_extends) matches none of them, which is
    why they are still unscored.
  * Every other sport plays series, so two rows are one game only when they
    share both teams, are dated at most a day apart AND start within
    SERIES_WINDOW_HOURS, and two different finals are two games.
  * A row the odds feed wrote that no book has ever priced is not a listing
    (needs_price). Measured 2026-10-20: the 3 past unscored WNBA rows since May
    have 0 odds rows each, and sit 17 to 42 hours from the real game, outside the
    series window; without this they would hold their teams' next games. UFC
    uses the scorer's own "this fight is real" signal, a DraftKings h2h row
    (models/scorer.run_scorer).

A PAST GAME THAT NEVER GETS A RESULT stops holding decisions after
`lookback_days` (a data gap or a cancelled game, not a game to wait for), and is
reported. It does not count as a previous game either: the training rows read
only games that were played.

REST AS OF KICKOFF (`rest_days_as_of_kickoff`). The days from the team's
previous game to this one, where "previous" includes a game that has not been
played YET: by kickoff it will have been. That is what the training rows saw,
because every game in history is played. For the dates: an event dated on two
days takes its LATER date, which is what training reads (in 2015-2025 the
odds-feed twins are unscored, so a night game counts at CFBD's UTC date).

NHL keeps its own two-day check (models/nhl_moneyline_anchored.stale_teams),
built on `games_between` and `teams_missing_from_logs` below with its exact
behaviour: every row, no de-duplication, no price filter.

Read-only. Nothing here writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from loguru import logger

from tracking.record_duplicates import NO_SERIES_SPORTS, SERIES_WINDOW_HOURS


@dataclass(frozen=True)
class Rules:
    """How one sport's schedule is read.

    lookback_days    How long after its start a game with no result (or not
                     yet in the logs) still holds a decision. Past that it is a
                     data gap: reported, and neither waited for nor counted.
    needs_price      An unscored row counts only when a book has priced it.
    played_from_log  The log, not a score in `games`, says the game happened
                     (UFC: 367 of the odds feed's 579 fight rows have no
                     score; results land on the mirror's own rows).
    log              Which log the inputs read; None means the score in
                     `games` is what they read.
    price_book       needs_price reads this book's h2h row only (None: any row).
    word             "game" or "fight", for the reason.
    result_lookback_hours
                     How long after its start a game with NO RESULT still
                     holds, when that is shorter than lookback_days (MLB: a
                     postponed game keeps its priced row and never gets a
                     score). A game with a result still waits for the log for
                     the full lookback_days. None: lookback_days for both.
    """
    sport: str
    lookback_days: int
    needs_price: bool = False
    played_from_log: bool = False
    log: str | None = None
    price_book: str | None = None
    word: str = "game"
    result_lookback_hours: int | None = None


# lookback_days, each sport:
#   NCAAF 10: the results step self-heals 10 days back
#             (cfbd_ingestor.ingest_ncaaf_results_for_date, heal_days=10).
#   NFL   10: one week plus the measured log lag (Sunday games reached the
#             player log 4.2-20.5h after kickoff, 2026 weeks 1-6).
#   WNBA   4: the 2026 regular-season BETs written on a missing result had a
#             previous game 2 to 4 days old.
#   UFC  400: a fighter's previous fight is months back. Safe this long only
#             because a fight counts as done once its CARD is in the log
#             (a cancelled bout never is), and every past DraftKings-priced
#             card date since 2026-06-13 is in ufc_fight_log (25 of 25,
#             measured 2026-10-20).
#   MLB  2 days for the log, 12 hours for the result. Measured 2026-10-20:
#             October finals were scored within 3.9h of first pitch, and the
#             morning run logged them at 10:05-10:07Z the next day. The log
#             can be late (30 of 1,955 team-games since 07-10 were logged
#             after the team's next first pitch): that next game is held,
#             not decided on a stale bullpen. A game with no result 12h on
#             is a postponement or a results gap: MLB_2026-10-16_TB_CLE kept
#             3,328 odds rows and no score, 22.3h before the two teams' next
#             game, so one 2-day horizon would have held that game to its
#             first pitch.
RULES: dict[str, Rules] = {
    "NCAAF": Rules("NCAAF", lookback_days=10, log="ncaaf"),
    "NFL":   Rules("NFL", lookback_days=10),
    "WNBA":  Rules("WNBA", lookback_days=4, needs_price=True),
    "UFC":   Rules("UFC", lookback_days=400, needs_price=True, played_from_log=True,
                   log="ufc", price_book="draftkings", word="fight"),
    "MLB":   Rules("MLB", lookback_days=2, needs_price=True, log="mlb",
                   result_lookback_hours=12),
}

# The sports the generic pre-game scorer gates (models/scorer.run_scorer).
# NFL's pre-game models are cards, gated where their BETs are written
# (scripts/nfl_wind_publisher). NHL's side models decide on game day only,
# 16:00Z-18:00Z, behind their own check (models/nhl_moneyline_anchored.
# stale_teams). MLB's results gap (146 of 2,385 odds-feed rows for 2026 with
# no result, docs/sports/mlb.md) costs at most 12 hours per missing result,
# under result_lookback_hours, not days.
SCORER_GATED_SPORTS: tuple[str, ...] = ("NCAAF", "WNBA", "UFC", "MLB")

# The reason every gate writes when the schedule itself cannot be read: the
# gates fail CLOSED (no decision this pass), and say so.
SCHEDULE_UNREADABLE = "schedule check failed; not deciding this pass"

# A team-day window this wide around a game's date is the game itself.
_SAME_EVENT_DAYS = 1


# ── rows and events ──────────────────────────────────────────────────────────

def parse_start(value) -> datetime | None:
    """A stored commence_time (two ISO shapes, '...Z' and '...+00:00', and
    sometimes a space for the T) as an aware UTC datetime, or None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip().replace(" ", "T").replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class GameRow:
    """One `games` row. `priced` is None when nobody looked (a scored row and a
    sport without needs_price never need to)."""
    game_id: str
    game_date: str
    home: str
    away: str
    start: datetime | None = None
    home_score: float | None = None
    away_score: float | None = None
    priced: bool | None = None

    @property
    def day(self) -> date | None:
        return _day(self.game_date)

    @property
    def scored(self) -> bool:
        return self.home_score is not None


def ufc_slugs(game_id: str) -> tuple[str, str] | None:
    """(away_slug, home_slug) from UFC_{date}_{away}_{home}. Fighter slugs hold
    hyphens, never underscores (models/scorer._sibling_ufc_game_id)."""
    parts = str(game_id).split("_")
    if len(parts) != 4 or parts[0] != "UFC":
        return None
    return parts[2], parts[3]


def participants(row: GameRow, sport: str) -> tuple[str, str]:
    """Who plays in the row. A UFC fighter is his slug in the id: the display
    name on the row is spelled however the book spelled it."""
    if sport == "UFC":
        slugs = ufc_slugs(row.game_id)
        if slugs:
            return slugs
    return row.away, row.home


@dataclass
class Event:
    """Every stored row of one real game."""
    rows: list[GameRow] = field(default_factory=list)

    @property
    def ids(self) -> set[str]:
        return {r.game_id for r in self.rows}

    @property
    def days(self) -> list[date]:
        return sorted(d for d in (r.day for r in self.rows) if d is not None)

    @property
    def first_day(self) -> date | None:
        d = self.days
        return d[0] if d else None

    @property
    def last_day(self) -> date | None:
        d = self.days
        return d[-1] if d else None

    @property
    def start(self) -> datetime | None:
        starts = [r.start for r in self.rows if r.start is not None]
        return min(starts) if starts else None

    @property
    def scored(self) -> bool:
        return any(r.scored for r in self.rows)


def _final(row: GameRow) -> tuple | None:
    if row.home_score is None or row.away_score is None:
        return None
    return tuple(sorted((float(row.home_score), float(row.away_score))))


def _same_series_game(a: GameRow, b: GameRow, sport: str) -> bool:
    """tracking.record_duplicates' rule for a sport that plays series."""
    if frozenset(participants(a, sport)) != frozenset(participants(b, sport)):
        return False
    if a.day is None or b.day is None or abs((a.day - b.day).days) > _SAME_EVENT_DAYS:
        return False
    if a.start is None or b.start is None:
        return False
    if abs((a.start - b.start).total_seconds()) >= SERIES_WINDOW_HOURS * 3600:
        return False
    fa, fb = _final(a), _final(b)
    return not (fa is not None and fb is not None and fa != fb)


def _joins(event: Event, row: GameRow, sport: str) -> bool:
    if row.game_id in event.ids:
        return True
    if sport in NO_SERIES_SPORTS:
        # One team's rows only (team_view filters first): within a day of any
        # of them is the same game.
        return row.day is not None and any(
            abs((row.day - d).days) <= _SAME_EVENT_DAYS for d in event.days)
    return any(_same_series_game(row, r, sport) for r in event.rows)


def collapse(rows: list[GameRow], sport: str) -> list[Event]:
    """One team's rows -> its games, in date order."""
    ordered = sorted(rows, key=lambda r: (r.day or date.min,
                                          r.start or datetime.min.replace(tzinfo=timezone.utc)))
    events: list[Event] = []
    for r in ordered:
        for ev in events:
            if _joins(ev, r, sport):
                ev.rows.append(r)
                break
        else:
            events.append(Event([r]))
    return events


def _is_listing(row: GameRow, rules: Rules) -> bool:
    """A row the odds feed wrote for a game no book has priced is not a game."""
    if not rules.needs_price or row.scored:
        return True
    return row.priced is not False


def _before(ev: Event, target: Event) -> bool:
    a, b = ev.first_day, target.first_day
    if a is None or b is None:
        return False
    if a != b:
        return a < b
    return ev.start is not None and target.start is not None and ev.start < target.start


def _clock(ev: Event) -> datetime | None:
    """When the game is (or was) on: its start, else the end of its last day."""
    if ev.start is not None:
        return ev.start
    d = ev.last_day
    return (datetime.combine(d, datetime.max.time()).replace(tzinfo=timezone.utc)
            if d else None)


# ── one team's view of the schedule ─────────────────────────────────────────

UNPLAYED, UNSCORED, UNLOGGED = "not played yet", "no result yet", "not in the logs yet"


@dataclass
class TeamView:
    """One team's schedule around one game, as of `now`."""
    team: str
    target: Event
    earlier: list[Event]
    pending: list[tuple[Event, str]]
    gaps: list[Event]
    previous: Event | None
    later: list[Event]

    @property
    def next_game(self) -> Event | None:
        return self.later[0] if self.later else None

    @property
    def rest_days(self) -> int | None:
        """Days from the previous game's (later) date to this game's date."""
        if self.previous is None or self.previous.last_day is None:
            return None
        here = self.target.first_day
        return (here - self.previous.last_day).days if here else None

    @property
    def back_to_back(self) -> bool:
        return self.rest_days == 1

    def games_in_last(self, days: int) -> int:
        """Games (played or still to be played) in the `days` before this one."""
        here = self.target.first_day
        if here is None:
            return 0
        lo = here - timedelta(days=days)
        return sum(1 for ev in self.earlier
                   if ev not in self.gaps and ev.last_day and ev.last_day >= lo)


def team_view(rows: list[GameRow], rules: Rules, team: str, target: GameRow,
              now: datetime, logged=None) -> TeamView:
    """`rows` are stored games rows (any team; this filters). `logged(team,
    event) -> bool` says whether the event is in the logs the inputs read;
    None means the score in `games` is the log."""
    sport = rules.sport
    mine = [r for r in rows if team in participants(r, sport) and _is_listing(r, rules)]
    if target.game_id not in {r.game_id for r in mine}:
        mine.append(target)
    events = collapse(mine, sport)
    here = next(ev for ev in events if target.game_id in ev.ids)
    horizon = now - timedelta(days=rules.lookback_days)
    result_horizon = (now - timedelta(hours=rules.result_lookback_hours)
                      if rules.result_lookback_hours is not None else horizon)

    earlier, later, pending, gaps = [], [], [], []
    for ev in events:
        if ev is here:
            continue
        if not _before(ev, here):
            later.append(ev)
            continue
        earlier.append(ev)
        on = _clock(ev)
        future = on is not None and on > now
        stale = on is not None and on < horizon
        no_result_long = on is not None and on < result_horizon
        happened = logged(team, ev) if rules.played_from_log else ev.scored
        if happened:
            if rules.played_from_log or logged is None or logged(team, ev) or stale:
                continue                     # done (or a log gap past the lookback)
            pending.append((ev, UNLOGGED))
        elif future:
            pending.append((ev, UNPLAYED))
        elif no_result_long:
            gaps.append(ev)                  # never got a result: not waited for
        else:
            pending.append((ev, UNLOGGED if rules.played_from_log else UNSCORED))

    # The previous game, for rest: anything earlier that has been or will be
    # played. A game that never got a result inside the lookback is not one.
    counted = [ev for ev in earlier if ev not in gaps]
    previous = max(counted, key=lambda e: (e.last_day, _clock(e)), default=None)
    return TeamView(team=team, target=here, earlier=earlier, pending=pending,
                    gaps=gaps, previous=previous, later=later)


def pending_reason(views: list[tuple[str, TeamView]], word: str = "game") -> str | None:
    """The persisted reason, naming every team still waiting, or None.
    `views` is [(display name, view)]."""
    parts = []
    for name, view in views:
        for ev, _state in sorted(view.pending, key=lambda p: p[0].first_day or date.min):
            parts.append(f"{name}'s {ev.first_day.isoformat() if ev.first_day else '?'} {word}")
    if not parts:
        return None
    return f"waiting for {' and '.join(parts)} to be played and logged"


# ── loading from the database ────────────────────────────────────────────────

_ROW_COLS = "game_id, game_date, home_team, away_team, commence_time, home_score, away_score"


def _rows(raw) -> list[GameRow]:
    out = []
    for gid, gdate, home, away, start, hs, as_ in raw:
        out.append(GameRow(str(gid), str(gdate)[:10], home, away, parse_start(start),
                           None if hs is None else float(hs),
                           None if as_ is None else float(as_)))
    return out


def _with_prices(conn, rows: list[GameRow], rules: Rules,
                 skip: frozenset = frozenset()) -> list[GameRow]:
    """Fill `priced` on the unscored rows: one indexed read, for those only.
    `skip`: ids that need no answer -- only ever the one game being asked
    about, which team_view puts back in whatever its row says. NOT the games a
    scoring pass is about to score: run_scorer builds that list before its
    price pre-filters drop the games no book has priced, so an unpriced row
    dated inside the window would be taken for a game and hold the real one
    behind it (WNBA_2026-10-22_GSV_ATL, 0 odds rows, in the Finals)."""
    if not rules.needs_price:
        return rows
    ids = sorted({r.game_id for r in rows if not r.scored and r.game_id not in skip})
    if not ids:
        return rows
    # An IN list, not = ANY(...): the same statement runs on Postgres and on
    # the sqlite the tests use. EXISTS, not DISTINCT over odds: it stops at
    # each game's first odds row. Measured on production 2026-10-20 over 88
    # MLB games (about 37,000 odds rows each): DISTINCT read 3.3 million index
    # entries in 1,780 ms, EXISTS 88 in 17 ms.
    marks = ",".join("?" * len(ids))
    book = " AND o.market = 'h2h' AND o.bookmaker = ?" if rules.price_book else ""
    hit = {r[0] for r in conn.execute(
        f"SELECT s.game_id FROM games s WHERE s.game_id IN ({marks}) AND EXISTS "
        f"(SELECT 1 FROM odds o WHERE o.game_id = s.game_id{book})",
        (*ids, rules.price_book) if rules.price_book else tuple(ids)).fetchall()}
    return [r if r.scored else GameRow(r.game_id, r.game_date, r.home, r.away, r.start,
                                       r.home_score, r.away_score, r.game_id in hit)
            for r in rows]


def _log_check(conn, rules: Rules, lo: str, hi: str, teams=()):
    """`logged(team, event)` for the sport's log, or None (the score is the log).
    `teams`: whose log to read, where the read is per team (MLB)."""
    if rules.log == "ncaaf":
        seen: dict[str, set] = {}
        ids: set[tuple[str, str]] = set()
        for team, gdate, gid in conn.execute(
                "SELECT team, game_date, game_id FROM ncaaf_team_game_log "
                "WHERE game_date >= ? AND game_date <= ?", (lo, hi)).fetchall():
            d = _day(gdate)
            if d is not None:
                seen.setdefault(team, set()).add(d)
            ids.add((team, str(gid)))

        def logged(team: str, ev: Event) -> bool:
            if any((team, gid) in ids for gid in ev.ids):
                return True
            have = seen.get(team, set())
            return any(abs((d - x).days) <= _SAME_EVENT_DAYS for d in ev.days for x in have)
        return logged
    if rules.log == "ufc":
        cards = {d for d in (_day(r[0]) for r in conn.execute(
            "SELECT DISTINCT game_date FROM ufc_fight_log WHERE game_date >= ?",
            (lo,)).fetchall()) if d is not None}

        def logged(team: str, ev: Event) -> bool:
            # The whole card lands at once (ufc_csv_loader). A card in the log
            # with this fighter missing is a bout that did not happen.
            return any(abs((d - x).days) <= _SAME_EVENT_DAYS for d in ev.days for x in cards)
        return logged
    if rules.log == "mlb":
        # The morning run's footprint: a team-stats row dated AFTER the game.
        # The mlb_stats step writes one per team every morning, in the same
        # run as (and before the scoring step, like) the bullpen rows the game
        # models read (bullpen_ip_last1/3, where no row reads as an off day).
        # Not the bullpen rows themselves: a team whose starter went the
        # distance has none. Since 07-10, 41 of 1,996 team-games had no
        # bullpen row, 1,996 of 1,996 had a later team-stats row, and the two
        # never landed more than an hour apart. In the postseason the team
        # stats stay at 162 games; the bullpen rows are what the run changes.
        teams = sorted({t for t in teams if t})
        if not teams:
            return lambda team, ev: False
        marks = ",".join("?" * len(teams))
        latest = {t: _day(d) for t, d in conn.execute(
            f"SELECT team, MAX(as_of_date) FROM mlb_team_stats "
            f"WHERE team IN ({marks}) AND as_of_date >= ? GROUP BY team",
            (*teams, lo)).fetchall()}

        def logged(team: str, ev: Event) -> bool:
            last, d = latest.get(team), ev.last_day
            return last is not None and d is not None and last > d
        return logged
    return None


@dataclass
class ScheduleBook:
    """One sport's stored schedule around a set of games, loaded once per
    scoring pass (three indexed reads at most)."""
    rules: Rules
    rows: list[GameRow]
    logged: object = None

    @classmethod
    def load(cls, conn, sport: str, targets) -> "ScheduleBook":
        """`targets`: the (game_id, game_date) pairs this pass will score."""
        rules = RULES[sport]
        targets = list(targets)
        days = sorted(d for d in (_day(t[1]) for t in targets) if d is not None)
        if not days:
            return cls(rules, [], None)
        lo = (days[0] - timedelta(days=rules.lookback_days + 2)).isoformat()
        hi = (days[-1] + timedelta(days=_SAME_EVENT_DAYS)).isoformat()
        rows = _rows(conn.execute(
            f"SELECT {_ROW_COLS} FROM games WHERE sport = ? "
            f"AND game_date >= ? AND game_date <= ?", (sport, lo, hi)).fetchall())
        rows = _with_prices(conn, rows, rules)
        teams = {t for r in rows for t in (r.home, r.away)}
        return cls(rules, rows, _log_check(conn, rules, lo, hi, teams))

    def views(self, game_id: str, game_date: str, home: str, away: str,
              commence_time, now: datetime) -> list[tuple[str, TeamView]]:
        target = GameRow(game_id, str(game_date)[:10], home, away, parse_start(commence_time))
        out = []
        sides = participants(target, self.rules.sport)          # (away, home)
        for name, team in ((away, sides[0]), (home, sides[1])):
            out.append((name, team_view(self.rows, self.rules, team, target, now, self.logged)))
        return out

    def pending_reason(self, game_id: str, game_date: str, home: str, away: str,
                       commence_time, now: datetime) -> str | None:
        views = self.views(game_id, game_date, home, away, commence_time, now)
        hours = self.rules.result_lookback_hours
        after = f"{hours}+ hours" if hours is not None else f"{self.rules.lookback_days}+ days"
        for name, v in views:
            for ev in v.gaps:
                logger.info(f"  {game_id}: {name}'s {ev.first_day} {self.rules.word} "
                            f"({', '.join(sorted(ev.ids))}) has no result "
                            f"{after} on -- not waited for")
        return pending_reason(views, self.rules.word)


def rest_days_as_of_kickoff(conn, sport: str, team: str, game_id: str,
                            game_date: str, now: datetime | None = None) -> int | None:
    """Days of rest `team` will have at kickoff of `game_id`, from the stored
    schedule: its previous game, played or still to be played. None when the
    team has no earlier game stored (the callers' existing default applies).

    Replaces the live feature paths' read of PLAYED games only, which made an
    unplayed intermediate game invisible. Same history depth as before (no
    season bound), so a season opener still reads the days since the team's
    last game of the previous season, on both paths."""
    rules = RULES[sport]
    now = now or datetime.now(timezone.utc)
    d = _day(game_date)
    if d is None:
        return None
    # '?' placeholders: DBConnection turns them into psycopg2's, and the
    # feature engines' sqlite tests can run this read as written.
    raw = conn.execute(
        f"SELECT {_ROW_COLS} FROM games WHERE sport = ? "
        f"AND (home_team = ? OR away_team = ?) AND game_date <= ? "
        f"ORDER BY game_date DESC LIMIT 15",
        (sport, team, team, (d + timedelta(days=_SAME_EVENT_DAYS)).isoformat())).fetchall()
    rows = _with_prices(conn, _rows(raw), rules, skip=frozenset({game_id}))
    target = next((r for r in rows if r.game_id == game_id), None) or GameRow(
        game_id, d.isoformat(), team, "", None)
    prev = team_view(rows, rules, team, target, now).previous
    # Measured to THIS row's date, as the played-games read was: the row being
    # scored can be either twin of a night game.
    return (d - prev.last_day).days if prev is not None and prev.last_day else None


# ── the NHL check's primitives (its behaviour, unchanged) ───────────────────

def games_between(conn, sport: str, lo: str, hi: str) -> list[tuple]:
    """(game_id, home_team, away_team) for every row dated lo <= d < hi, scored
    or not, duplicates and all."""
    return conn.execute(
        "SELECT game_id, home_team, away_team FROM games WHERE sport = ? "
        "AND game_date >= ? AND game_date < ?", (sport, lo, hi)).fetchall()


def teams_missing_from_logs(rows, logged_ids) -> set:
    """Both teams of every row whose game_id the log does not hold."""
    return {t for gid, h, a in rows if gid not in logged_ids for t in (h, a)}

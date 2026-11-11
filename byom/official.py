"""The official pick for a Build Your Own Model leg: the first match.

No database. A builder model's bet becomes official at the first
DraftKings quote, at or before kickoff, where the leg fits the model's
rules and the side carries an American price (Matt, 2026-11-04: "it's
all about when a line becomes an official pick"). That quote's line and
price are the bet of record. A later move does not change it. The
closing-line result stays in byom_game_facts and byom_prop_facts beside
it.

The rules that can change with the quote are the role (favorite,
underdog, pick'em, from the DraftKings HOME spread in force) and the
line, price, team-spread, and game-total bands. The builder stores one
candidate per pre-kickoff snapshot where those numbers changed
(`game_lock_candidates`, `prop_lock_candidates`, `match_role` 'any',
`context_at_lock` true). The lock is the earliest candidate that fits
the role and the bands together (`first_fit`, and the same search in
`byom_legs`). A band is not applied to a quote that was already locked.

Side, week, rest, primetime, market and over/under do not move, so they
stay filters on the locked row. A total has no role. A role with no
spread yet in force is unknown and matches only a model that asks for
any role.

`point` is the HOME spread on a spread leg, the same sign convention as
`byom_game_facts.dk_spread_home` (CLAUDE.md §4). The label the app shows
is built in SQL by `byom_leg_label`, one place, so no screen rebuilds a
number.

`game_official_legs` and `prop_official_legs` are the no-band case: one
row per role, the first candidate that fits that role. The builders do
not write those rows. They write the candidates.
"""
from __future__ import annotations

from bisect import bisect_right
from decimal import Decimal

from byom.game_facts import (
    _rank,
    american_odds,
    grade_ats,
    grade_ml,
    grade_total,
    roles,
)
from byom.prop_facts import _capture_rank, grade_ou

MATCH_ROLES = ("any", "favorite", "underdog", "pickem")

# Sports whose builders write official candidates. NBA joined 2026-11-04
# (Matt: "do the same as what I said for nfl").
OFFICIAL_SPORTS = ("NFL", "NBA", "NHL")

# (market, leg_side, price field on the quote). price_home is the over
# on a total, price_away the under: the same mapping as byom/load.py.
GAME_LEGS = (
    ("h2h", "home", "price_home"),
    ("h2h", "away", "price_away"),
    ("spreads", "home", "price_home"),
    ("spreads", "away", "price_away"),
    ("totals", "over", "price_home"),
    ("totals", "under", "price_away"),
)

OFFICIAL_COLUMNS = (
    "canonical_key", "sport", "season", "market", "leg_side",
    "player_key", "match_role", "leg_role", "team", "locked_at",
    "point", "price", "result", "team_spread", "game_total",
    "context_at_lock",
)

_STATE = ("point", "price", "leg_role", "team_spread", "game_total")


class RoleClock:
    """The home role and home spread in force at any moment.

    At each snapshot the spread is the best-ranked quote with a point,
    the same rank the closing line uses. Between snapshots the last one
    holds. Before the first spread the role and the point are unknown
    (None).
    """

    def __init__(self, spreads: list[dict]):
        best: dict = {}
        for quote in spreads:
            if quote.get("lead_hours", 0) < 0:
                continue
            if quote.get("point") is None or quote.get("point") == "":
                continue
            snap = quote["snapshot_at"]
            if snap not in best or _rank(quote) > _rank(best[snap]):
                best[snap] = quote
        self._times = sorted(best)
        self._home = [roles(best[t]["point"])[0] for t in self._times]
        self._points = [_num(best[t]["point"]) for t in self._times]

    def home_role(self, at):
        i = bisect_right(self._times, at)
        if i == 0:
            return None
        return self._home[i - 1]

    def home_point(self, at):
        i = bisect_right(self._times, at)
        if i == 0:
            return None
        return self._points[i - 1]


class PointClock:
    """A market's point in force at a time. None before the first point.

    Totals use this so a game-total band reads the total at the quote,
    not the closing total. `rank` is the quote rank for that market.
    """

    def __init__(self, quotes: list[dict], rank):
        best: dict = {}
        for quote in quotes:
            if quote.get("lead_hours", 0) < 0 or not _has_point(quote):
                continue
            snap = quote["snapshot_at"]
            if snap not in best or rank(quote) > rank(best[snap]):
                best[snap] = quote
        self._times = sorted(best)
        self._points = [_num(best[t].get("point")) for t in self._times]

    def point_at(self, at):
        i = bisect_right(self._times, at)
        if i == 0:
            return None
        return self._points[i - 1]


_FLIP = {"favorite": "underdog", "underdog": "favorite", "pickem": "pickem"}


def side_role(home_role, side: str | None):
    """This side's role given the home role. A side that is neither is None."""
    if home_role is None:
        return None
    if side == "home":
        return home_role
    if side == "away":
        return _FLIP[home_role]
    return None


def _team_spread(home_point, side: str | None):
    """This side's spread. Positive is an underdog. None when unknown."""
    if home_point is None or side not in ("home", "away"):
        return None
    return home_point if side == "home" else -home_point


def _fits(match_role: str, leg_role) -> bool:
    return match_role == "any" or leg_role == match_role


def _in_band(value, lo, hi) -> bool:
    """Inclusive. A missing number is outside a band that was set."""
    if lo is None and hi is None:
        return True
    if value is None:
        return False
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    if lo is not None and number < Decimal(str(lo)):
        return False
    if hi is not None and number > Decimal(str(hi)):
        return False
    return True


def first_fit(candidates, *, role=None, min_line=None, max_line=None,
              min_price=None, max_price=None, min_spread=None, max_spread=None,
              min_total=None, max_total=None):
    """The earliest candidate that fits the role and the four bands.

    `role` None is any role. A line band is the prop line (`player_key`
    set). A game leg has no prop line, so a line band does not fit it.
    Team spread and game total are the numbers in force at that quote.
    """
    for row in sorted(candidates, key=lambda item: item["locked_at"]):
        if role is not None and row.get("leg_role") != role:
            continue
        if not _in_band(row.get("price"), min_price, max_price):
            continue
        if min_line is not None or max_line is not None:
            if not row.get("player_key"):
                continue
            if not _in_band(row.get("point"), min_line, max_line):
                continue
        if not _in_band(row.get("team_spread"), min_spread, max_spread):
            continue
        if not _in_band(row.get("game_total"), min_total, max_total):
            continue
        return row
    return None


def _first(quotes, accept, rank):
    """The earliest snapshot with an accepted quote, and its best-ranked one."""
    chosen = _best_by_snapshot(quotes, accept, rank)
    if not chosen:
        return None
    return chosen[0]


def _best_by_snapshot(quotes, accept, rank) -> list[dict]:
    """Best-ranked accepted quote at each snapshot, earliest snapshot first."""
    by_snap: dict = {}
    for quote in quotes:
        if not accept(quote):
            continue
        snap = quote["snapshot_at"]
        if snap not in by_snap or rank(quote) > rank(by_snap[snap]):
            by_snap[snap] = quote
    return [by_snap[snap] for snap in sorted(by_snap)]


def _has_point(quote) -> bool:
    return quote.get("point") is not None and quote.get("point") != ""


def _num(value):
    if value is None or value == "":
        return None
    return Decimal(str(value))


# A prop is filtered on its own line and price only (Matt, 2026-11-04:
# favorite/underdog, team spread and game total are team bets), so a
# snapshot where only the game moved is not a new prop candidate. That
# keeps the NBA prop history, about 108 props a game, inside the app's
# read limit.
_PROP_STATE = ("point", "price")


def _keep_changes(rows: list[dict], state: tuple = None) -> list[dict]:
    """Drop a snapshot that repeats the previous candidate's lock state.

    The earliest quote that enters a band is unchanged: a later quote
    with the same point, price, role, team spread and game total cannot
    be the first one that fits.
    """
    kept = []
    prev = None
    for row in rows:
        keys = _STATE if state is None else state
        if prev is not None and all(prev[key] == row[key] for key in keys):
            continue
        kept.append(row)
        prev = row
    return kept


def _game_result(market, side, home_score, away_score, point):
    if market == "h2h":
        pair = grade_ml(home_score, away_score)
    elif market == "spreads":
        pair = grade_ats(home_score, away_score, point)
    else:
        pair = grade_total(home_score, away_score, point)
    if pair is None:
        return None
    return pair[0] if side in ("home", "over") else pair[1]


def _candidate(fact, market, side, team, quote, point, price, leg_role,
               team_spread, game_total, result, player_key=""):
    return {
        "canonical_key": fact["canonical_key"],
        "sport": fact["sport"],
        "season": fact["season"],
        "market": market,
        "leg_side": side,
        "player_key": player_key,
        "match_role": "any",
        "leg_role": leg_role,
        "team": team,
        "locked_at": quote["snapshot_at"],
        "point": point,
        "price": price,
        "result": result,
        "team_spread": team_spread,
        "game_total": game_total,
        "context_at_lock": True,
    }


def game_lock_candidates(fact: dict, moneylines: list[dict],
                         spreads: list[dict], totals: list[dict]) -> list[dict]:
    """Every pre-kickoff candidate for one game's six legs.

    One row per snapshot where the lock state changed, best-ranked quote
    at that snapshot. `match_role` is 'any'. `leg_role`, `team_spread`
    and `game_total` are the numbers in force then, so a later read can
    pick the first row that fits a model's bands. A quote after kickoff
    is not a candidate.
    """
    clock = RoleClock(spreads)
    total_clock = PointClock(totals, _rank)
    pools = {"h2h": moneylines, "spreads": spreads, "totals": totals}
    home_score, away_score = fact.get("home_score"), fact.get("away_score")
    out = []
    for market, side, field in GAME_LEGS:
        team = {"home": fact.get("home_team"),
                "away": fact.get("away_team")}.get(side)

        def accept(q, market=market, field=field):
            if q.get("lead_hours", -1) < 0:
                return False
            if american_odds(q.get(field)) is None:
                return False
            if market != "h2h" and not _has_point(q):
                return False
            return True

        rows = []
        for quote in _best_by_snapshot(pools[market], accept, _rank):
            point = None if market == "h2h" else _num(quote.get("point"))
            if market == "spreads":
                home_point = point
            else:
                home_point = clock.home_point(quote["snapshot_at"])
            leg_role = None if market == "totals" else side_role(
                clock.home_role(quote["snapshot_at"]), side)
            game_total = point if market == "totals" else total_clock.point_at(
                quote["snapshot_at"])
            rows.append(_candidate(
                fact, market, side, team, quote, point,
                american_odds(quote.get(field)), leg_role,
                None if market == "totals" else _team_spread(home_point, side),
                game_total,
                _game_result(market, side, home_score, away_score, point),
            ))
        out.extend(_keep_changes(rows))
    return out


def game_official_legs(fact: dict, moneylines: list[dict],
                       spreads: list[dict], totals: list[dict]) -> list[dict]:
    """One row per role: the first candidate that fits that role. No bands.

    The builders write `game_lock_candidates` instead. This is the
    role-only lock, so a reader that does not pass bands agrees with
    `first_fit`.
    """
    grouped: dict = {}
    for row in game_lock_candidates(fact, moneylines, spreads, totals):
        grouped.setdefault((row["market"], row["leg_side"]), []).append(row)
    out = []
    for market, side, _field in GAME_LEGS:
        wanted = ("any",) if market == "totals" else MATCH_ROLES
        for match_role in wanted:
            chosen = first_fit(
                grouped.get((market, side), []),
                role=None if match_role == "any" else match_role)
            if chosen is None:
                continue
            locked = dict(chosen)
            locked["match_role"] = match_role
            out.append(locked)
    return out


def prop_lock_candidates(fact: dict, pool: list[dict], clock: RoleClock,
                         home_team: str | None, away_team: str | None,
                         total_clock: PointClock | None = None) -> list[dict]:
    """Every pre-kickoff candidate for one prop's over and under.

    The role and the team spread are the player's team at the quote.
    A player with no team has no role and no team spread, so only a
    model that asks for any role and no spread band can match. The
    line band reads this quote's point. Graded at that point with the
    same actual the closing fact used. A player who did not play stays
    ungraded.
    """
    team = fact.get("team")
    if team and team == home_team:
        team_side = "home"
    elif team and team == away_team:
        team_side = "away"
    else:
        team_side = None
    actual = fact.get("actual") if fact.get("log_status") == "logged" else None
    out = []
    for side, field in (("over", "over_price"), ("under", "under_price")):
        def accept(q, field=field):
            if q.get("lead_hours", -1) < 0 or not _has_point(q):
                return False
            return american_odds(q.get(field)) is not None

        rows = []
        for quote in _best_by_snapshot(pool, accept, _capture_rank):
            point = _num(quote.get("point"))
            graded = grade_ou(actual, point) if actual is not None else None
            home_point = clock.home_point(quote["snapshot_at"])
            rows.append(_candidate(
                fact, fact["market"], side, team, quote, point,
                american_odds(quote.get(field)),
                side_role(clock.home_role(quote["snapshot_at"]), team_side),
                _team_spread(home_point, team_side),
                None if total_clock is None else total_clock.point_at(
                    quote["snapshot_at"]),
                None if graded is None else (
                    graded[0] if side == "over" else graded[1]),
                player_key=fact["player_key"],
            ))
        out.extend(_keep_changes(rows, _PROP_STATE))
    return out


def prop_official_legs(fact: dict, pool: list[dict], clock: RoleClock,
                       home_team: str | None, away_team: str | None,
                       total_clock: PointClock | None = None) -> list[dict]:
    """One row per role: the first candidate that fits that role. No bands."""
    grouped: dict = {}
    for row in prop_lock_candidates(
            fact, pool, clock, home_team, away_team, total_clock):
        grouped.setdefault(row["leg_side"], []).append(row)
    out = []
    for side in ("over", "under"):
        for match_role in MATCH_ROLES:
            chosen = first_fit(
                grouped.get(side, []),
                role=None if match_role == "any" else match_role)
            if chosen is None:
                continue
            locked = dict(chosen)
            locked["match_role"] = match_role
            out.append(locked)
    return out

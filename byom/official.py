"""The official pick for a Build Your Own Model leg: the first match.

No database. A builder model's bet becomes official at the first
DraftKings quote, at or before kickoff, where the leg fits the model's
rules and the side carries an American price (Matt, 2026-11-04: "it's
all about when a line becomes an official pick"). That quote's line and
price are the bet of record. A later move does not change it. The
closing-line result stays in byom_game_facts and byom_prop_facts beside
it.

Which rules can change with the line? Only the role: favorite, underdog
or pick'em, read off the DraftKings HOME spread in force at that moment.
Side, week, rest, primetime, market and over/under do not move, so a
leg needs one official row for each role a model can ask for:

    any       the first priced quote for this leg, whatever the role
    favorite  the first priced quote while this leg's team is favored
    underdog  the first priced quote while this leg's team is the dog
    pickem    the first priced quote while the spread is 0

A leg that never fits a role has no row for it, so a model that asks
for that role has no bet on that game. A total has no role, so it has
only `any`. A role with no spread yet in force is unknown and matches
only `any`.

`point` is the HOME spread on a spread leg, the same sign convention as
`byom_game_facts.dk_spread_home` (CLAUDE.md §4). The label the app shows
is built in SQL by `byom_leg_label`, one place, so no screen rebuilds a
number.
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
    "point", "price", "result",
)


class RoleClock:
    """The home role in force at any moment, from DraftKings spreads.

    At each snapshot the spread is the best-ranked quote with a point,
    the same rank the closing line uses. Between snapshots the last one
    holds. Before the first spread the role is unknown (None).
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

    def home_role(self, at):
        i = bisect_right(self._times, at)
        if i == 0:
            return None
        return self._home[i - 1]


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


def _fits(match_role: str, leg_role) -> bool:
    return match_role == "any" or leg_role == match_role


def _first(quotes, accept, rank):
    """The earliest snapshot with an accepted quote, and its best-ranked one."""
    by_snap: dict = {}
    for quote in quotes:
        if not accept(quote):
            continue
        snap = quote["snapshot_at"]
        if snap not in by_snap or rank(quote) > rank(by_snap[snap]):
            by_snap[snap] = quote
    if not by_snap:
        return None
    return by_snap[min(by_snap)]


def _has_point(quote) -> bool:
    return quote.get("point") is not None and quote.get("point") != ""


def _num(value):
    if value is None or value == "":
        return None
    return Decimal(str(value))


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


def game_official_legs(fact: dict, moneylines: list[dict],
                       spreads: list[dict], totals: list[dict]) -> list[dict]:
    """Official rows for one game's six legs.

    `fact` is the assembled byom_game_facts dict (identity and scores).
    The quote lists are DraftKings pre-start quotes from
    `game_facts._pre_start`: `snapshot_at` parsed, `lead_hours` set. A
    quote after kickoff is never official.
    """
    clock = RoleClock(spreads)
    pools = {"h2h": moneylines, "spreads": spreads, "totals": totals}
    home_score, away_score = fact.get("home_score"), fact.get("away_score")
    out = []
    for market, side, field in GAME_LEGS:
        pool = pools[market]
        wanted = ("any",) if market == "totals" else MATCH_ROLES
        team = {"home": fact.get("home_team"),
                "away": fact.get("away_team")}.get(side)
        for match_role in wanted:
            def accept(q, match_role=match_role, market=market, side=side,
                       field=field):
                if q.get("lead_hours", -1) < 0:
                    return False
                if american_odds(q.get(field)) is None:
                    return False
                if market != "h2h" and not _has_point(q):
                    return False
                if market == "totals":
                    return True
                role = side_role(clock.home_role(q["snapshot_at"]), side)
                return _fits(match_role, role)

            quote = _first(pool, accept, _rank)
            if quote is None:
                continue
            point = None if market == "h2h" else _num(quote.get("point"))
            leg_role = (None if market == "totals"
                        else side_role(clock.home_role(quote["snapshot_at"]), side))
            out.append({
                "canonical_key": fact["canonical_key"],
                "sport": fact["sport"],
                "season": fact["season"],
                "market": market,
                "leg_side": side,
                "player_key": "",
                "match_role": match_role,
                "leg_role": leg_role,
                "team": team,
                "locked_at": quote["snapshot_at"],
                "point": point,
                "price": american_odds(quote.get(field)),
                "result": _game_result(market, side, home_score, away_score, point),
            })
    return out


def prop_official_legs(fact: dict, pool: list[dict], clock: RoleClock,
                       home_team: str | None, away_team: str | None) -> list[dict]:
    """Official rows for one prop fact's over and under.

    `fact` is the closing prop fact (who, which market, the actual stat).
    `pool` is that player's DraftKings pre-start quotes for the market,
    from `prop_facts._pre_start`. The role is the player's team's role
    at the quote's snapshot. A player with no team has no role, so only
    `any` can match. Graded at the official line with the same actual
    the closing fact used. A player who did not play stays ungraded.
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
        for match_role in MATCH_ROLES:
            def accept(q, match_role=match_role, field=field):
                if q.get("lead_hours", -1) < 0 or not _has_point(q):
                    return False
                if american_odds(q.get(field)) is None:
                    return False
                role = side_role(clock.home_role(q["snapshot_at"]), team_side)
                return _fits(match_role, role)

            quote = _first(pool, accept, _capture_rank)
            if quote is None:
                continue
            point = _num(quote.get("point"))
            graded = grade_ou(actual, point) if actual is not None else None
            out.append({
                "canonical_key": fact["canonical_key"],
                "sport": fact["sport"],
                "season": fact["season"],
                "market": fact["market"],
                "leg_side": side,
                "player_key": fact["player_key"],
                "match_role": match_role,
                "leg_role": side_role(clock.home_role(quote["snapshot_at"]), team_side),
                "team": team,
                "locked_at": quote["snapshot_at"],
                "point": point,
                "price": american_odds(quote.get(field)),
                "result": None if graded is None else (
                    graded[0] if side == "over" else graded[1]),
            })
    return out

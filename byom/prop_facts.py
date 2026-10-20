"""Grade one NFL player prop into a byom_prop_facts row.

No database. The line is the last DraftKings snapshot at or before
game start. A missing line is not a prop. There is no price and no
unit. Standard markets only. A key ending in `_alternate` is an alt
ladder and is not a fact.

Thin data, recorded on the row as log_status. Only `logged` is graded.
A player who did not play is left ungraded: no actual, no result, and
the row is excluded from the record, the success stats, and the totals.
A quote with no posted line is not a row. The backtest skips it.

- logged: the game has a log and this player's normalised name matches
  one row. actual is that row's stat.
- non_participant: the game has a log and this name matches nobody.
  The player did not play, or the row never landed. actual and both
  results stay NULL. The status stays so the row can be told apart.
- missing_log: the game has been played and the log has zero rows. The
  ingest has not arrived. actual and both results stay NULL. A missing
  file is not a loss and is not in the record.
- unplayed: the game has no final score. Results stay NULL.
- ambiguous: two log rows normalise to the same name and the quote's
  team does not pick exactly one of them. No guess. Results stay NULL.

Anytime TD is rushing_tds + receiving_tds. Passing TDs are a different
market. A return or defensive score is not in nfl_player_game_log, so a
touchdown that is only a return grades as a loss. That is the file's
limit, not a zero we invented.

Tackles are solo + assists. That sum runs short of the number some books
grade. The row stores the sum we have.

Name match is data.name_match.normalize_player_name: case, accents,
punctuation, and a trailing suffix. It does not expand nicknames
(Josh/Joshua). A nickname miss on a logged game is non_participant
and stays ungraded.
"""
from __future__ import annotations

from decimal import Decimal

from data.name_match import normalize_player_name

from byom.constants import LINE_BASIS, SPORT
from byom.game_facts import lead_hours, parse_game_id, parse_ts

# Odds API market -> nfl_player_game_log columns summed into actual.
# Alternates are absent on purpose.
MARKET_COLUMNS: dict[str, tuple[str, ...]] = {
    "player_pass_yds": ("passing_yards",),
    "player_pass_attempts": ("attempts",),
    "player_pass_completions": ("completions",),
    "player_pass_tds": ("passing_tds",),
    "player_rush_yds": ("rushing_yards",),
    "player_rush_attempts": ("carries",),
    "player_reception_yds": ("receiving_yards",),
    "player_receptions": ("receptions",),
    "player_rush_reception_yds": ("rushing_yards", "receiving_yards"),
    "player_anytime_td": ("rushing_tds", "receiving_tds"),
    "player_tackles_assists": ("def_tackles_solo", "def_tackle_assists"),
    "player_sacks": ("def_sacks",),
}

ANYTIME_TD_MARKET = "player_anytime_td"
# Yes/No anytime rows are stored at 0.5 when the feed omits a point.
ANYTIME_TD_LINE = Decimal("0.5")
_LINE = Decimal("0.001")


def is_standard_market(market: str | None) -> bool:
    """True for a main line. An alt ladder key is false."""
    if not market or market.endswith("_alternate"):
        return False
    return market in MARKET_COLUMNS


def player_key(name: str | None) -> str:
    return normalize_player_name(name)


def _num(value) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def same_line(left, right) -> bool:
    if left is None or right is None:
        return False
    return abs(Decimal(str(left)) - Decimal(str(right))) <= _LINE


def actual_from_log(row: dict, market: str) -> Decimal:
    """Sum the columns this market grades. A NULL column counts as 0
    once the row itself matched. Passing TDs are not in anytime TD."""
    total = Decimal(0)
    for col in MARKET_COLUMNS[market]:
        value = _num(row.get(col))
        if value is not None:
            total += value
    return total


def grade_ou(actual, line) -> tuple[str, str] | None:
    """(over, under). Push when actual equals the line."""
    if actual is None or line is None:
        return None
    diff = Decimal(str(actual)) - Decimal(str(line))
    if diff > 0:
        return "win", "loss"
    if diff < 0:
        return "loss", "win"
    return "push", "push"


def log_status(played: bool, game_row_count: int, matches: int) -> str:
    if not played:
        return "unplayed"
    if game_row_count <= 0:
        return "missing_log"
    if matches > 1:
        return "ambiguous"
    if matches == 0:
        # Diagnostic only. A player who did not play is not graded as 0.
        return "non_participant"
    return "logged"


_RESULTS = frozenset({"win", "loss", "push"})


def in_backtest(fact: dict) -> bool:
    """True when this row is scored.

    The line has to be one that was posted, and the player has to have
    logged the game. A missing line is skipped. A player who did not
    play, a missing log, an unplayed game, and an ambiguous name are
    outside the record, the success stats, and the totals.
    """
    if fact.get("line") is None:
        return False
    if fact.get("log_status") != "logged":
        return False
    return (
        fact.get("over_result") in _RESULTS
        and fact.get("under_result") in _RESULTS
    )


def backtest(facts: list[dict]) -> dict:
    """Record, success, and totals for the rows that count.

    Success is wins among decided rows. A push is in the total and out
    of the rate. Over and under are both counted, so an Anytime TD 'No'
    on a player who did not play cannot become an under win.
    """
    over_wins = over_losses = under_wins = under_losses = pushes = 0
    total_actual = Decimal(0)
    for fact in facts:
        if not in_backtest(fact):
            continue
        over = fact["over_result"]
        under = fact["under_result"]
        if over == "win":
            over_wins += 1
        elif over == "loss":
            over_losses += 1
        if under == "win":
            under_wins += 1
        elif under == "loss":
            under_losses += 1
        if over == "push":
            pushes += 1
        actual = fact.get("actual")
        if actual is not None:
            total_actual += Decimal(str(actual))
    over_decided = over_wins + over_losses
    under_decided = under_wins + under_losses
    return {
        "record_over": f"{over_wins}-{over_losses}-{pushes}",
        "record_under": f"{under_wins}-{under_losses}-{pushes}",
        "over_wins": over_wins,
        "over_losses": over_losses,
        "under_wins": under_wins,
        "under_losses": under_losses,
        "pushes": pushes,
        "totals": over_wins + over_losses + pushes,
        "total_actual": total_actual,
        "over_success": (over_wins / over_decided) if over_decided else None,
        "under_success": (under_wins / under_decided) if under_decided else None,
    }


def _line_of(quote: dict, market: str):
    raw = quote.get("point")
    if raw is None:
        raw = quote.get("line")
    line = _num(raw)
    if line is None and market == ANYTIME_TD_MARKET:
        return ANYTIME_TD_LINE
    return line


def line_key(line) -> str:
    """One text for a line. 220.50 and 220.5 are the same prop."""
    text = format(Decimal(str(line)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _rows_for_player(log_rows: list[dict], key: str, team: str | None = None) -> list[dict]:
    """Name matches. When more than one remains, the quote's team breaks
    the tie if it matches exactly one log row."""
    matches = [row for row in log_rows if player_key(row.get("player_name")) == key]
    if len(matches) <= 1 or not team:
        return matches
    wanted = str(team).strip().upper()
    sided = [
        row for row in matches
        if str(row.get("team") or "").strip().upper() == wanted
    ]
    if len(sided) == 1:
        return sided
    return matches


def _pre_start(quote: dict) -> dict | None:
    """One DraftKings quote at or before kickoff, or None."""
    market = quote.get("market")
    if (quote.get("bookmaker") or "").lower() != "draftkings":
        return None
    if not is_standard_market(market):
        return None
    key = player_key(quote.get("player_name"))
    if not key:
        return None
    lead = lead_hours(quote.get("snapshot_at"), quote.get("commence_time"))
    if lead is None or lead < 0:
        return None
    snap = parse_ts(quote.get("snapshot_at"))
    if snap is None:
        return None
    row = dict(quote)
    row["player_key"] = key
    row["market"] = market
    row["lead_hours"] = lead
    row["snapshot_at"] = snap
    row["point"] = _line_of(row, market)
    return row


def facts_for_game(game: dict, quotes: list[dict],
                   log_rows: list[dict]) -> list[dict]:
    """Prop facts for one game.

    Empty when the id does not parse or no DraftKings standard market has
    a snapshot at or before kickoff. The line is the latest such snapshot.
    An earlier number is not a second fact.
    """
    parsed = parse_game_id(game.get("game_id") or "")
    if parsed is None:
        return []
    canonical, season, week, _away, _home = parsed
    played = game.get("home_score") is not None and game.get("away_score") is not None
    grouped: dict[tuple, list[dict]] = {}
    for quote in quotes:
        row = _pre_start(quote)
        # No posted line: skip. Do not grade it, and do not invent a number.
        # Anytime TD has already filled 0.5 when the feed omitted the point.
        if row is None or row.get("point") is None:
            continue
        grouped.setdefault((row["player_key"], row["market"]), []).append(row)
    game_rows = len(log_rows)
    out = []
    for (key, market), pool in grouped.items():
        latest = max(quote["snapshot_at"] for quote in pool)
        at_line = [quote for quote in pool if quote["snapshot_at"] == latest]
        seen: list = []
        lines = []
        for quote in at_line:
            line = quote.get("point")
            if line is None or any(same_line(line, prev) for prev in seen):
                continue
            seen.append(line)
            lines.append((line, quote))
        for line, quote in lines:
            matches = _rows_for_player(log_rows, key, quote.get("team"))
            status = log_status(played, game_rows, len(matches) if played else 0)
            out.append(_one(
                canonical, season, week, key, market, line, quote,
                status, matches,
            ))
    return out


def _one(canonical, season, week, key, market, line, quote,
         status, matches) -> dict:
    actual = None
    graded = None
    # Anyone who did not play, and any row still missing a line, stays
    # ungraded. actual 0 would book the under, and Anytime TD 'No', as a win.
    if status == "logged" and matches and line is not None:
        actual = actual_from_log(matches[0], market)
        graded = grade_ou(actual, line)
    over_result = under_result = None
    if graded is not None:
        over_result, under_result = graded
    return {
        "prop_key": f"{canonical}|{market}|{key}|{line_key(line)}",
        "canonical_key": canonical,
        "sport": SPORT,
        "season": season,
        "week": week,
        "player_name": quote.get("player_name") or key,
        "player_key": key,
        "team": quote.get("team"),
        "market": market,
        "line": line,
        "line_basis": LINE_BASIS,
        "actual": actual,
        "over_result": over_result,
        "under_result": under_result,
        "log_status": status,
    }

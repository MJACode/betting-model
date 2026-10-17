"""Pure grading for one NFL game's Build Your Own Model fact.

No database. The line is the last DraftKings snapshot at or before
game start. A missing line does not skip the game. Moneyline is the
score only. There is no price and no unit.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from byom.constants import DK_HISTORY_START_SEASON, LINE_BASIS

_KEY = re.compile(r"^(?:NFL_)?(\d{4})_(\d{2})_([A-Z]{2,3})_([A-Z]{2,3})$")
_ET = ZoneInfo("America/New_York")


def parse_ts(value):
    """Timezone-aware UTC, or None. Naive stamps are UTC. Text with Z works."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_game_id(game_id: str) -> tuple[str, int, int, str, str] | None:
    """(canonical_key, season, week, away, home) or None.

    Week comes from the id. games.week is NULL for every NFL season, so it
    is not an input.
    """
    match = _KEY.fullmatch(str(game_id or "").strip())
    if not match:
        return None
    season_s, week_s, away, home = match.groups()
    season, week = int(season_s), int(week_s)
    return f"{season_s}_{week_s}_{away}_{home}", season, week, away, home


def lead_hours(snapshot_at, commence) -> float | None:
    snap = parse_ts(snapshot_at)
    kick = parse_ts(commence)
    if snap is None or kick is None:
        return None
    return (kick - snap).total_seconds() / 3600.0


def _pre_start(quotes, market: str) -> list[dict]:
    """DraftKings quotes for one market, with a known lead. Other books out."""
    out = []
    for quote in quotes:
        if quote.get("market") != market:
            continue
        if (quote.get("bookmaker") or "").lower() != "draftkings":
            continue
        lead = lead_hours(quote.get("snapshot_at"), quote.get("commence_time"))
        if lead is None:
            continue
        out.append({**quote, "lead_hours": lead, "snapshot_at": parse_ts(quote["snapshot_at"])})
    return out


def line_at_start(quotes) -> dict | None:
    """Latest snapshot at or before game start.

    In-play (negative lead) is not the line. There is no hour window:
    an older pre-start snapshot is the line when it is the latest one.
    """
    chosen = None
    for quote in quotes:
        if quote["lead_hours"] < 0:
            continue
        if chosen is None or quote["snapshot_at"] > chosen["snapshot_at"]:
            chosen = quote
    return chosen


def is_primetime(commence) -> bool | None:
    """Thursday and Monday kickoffs, and any kickoff at 7pm ET or later.

    A Sunday 1pm or 4pm ET kickoff is not primetime. Missing commence is
    None, not a guess.
    """
    kick = parse_ts(commence)
    if kick is None:
        return None
    local = kick.astimezone(_ET)
    if local.weekday() in (0, 3):
        return True
    return local.hour >= 19


def rest_days(team: str, game_day: date | None, played: dict[str, list[date]]) -> int | None:
    """Days since this team's previous game in the same schedule. None when
    this is the first date we have for them."""
    if game_day is None:
        return None
    prior = [d for d in played.get(team, ()) if d < game_day]
    if not prior:
        return None
    return (game_day - max(prior)).days


def roles(spread_home) -> tuple[str | None, str | None]:
    """(home_role, away_role) from the HOME spread. 0 is a pick'em."""
    if spread_home is None:
        return None, None
    spread = Decimal(str(spread_home))
    if spread < 0:
        return "favorite", "underdog"
    if spread > 0:
        return "underdog", "favorite"
    return "pickem", "pickem"


def grade_ats(home_score, away_score, spread_home) -> tuple[str, str] | None:
    """(home, away). Home covers when (home - away) + home_spread > 0."""
    if home_score is None or away_score is None or spread_home is None:
        return None
    adjusted = (Decimal(str(home_score)) - Decimal(str(away_score))
                + Decimal(str(spread_home)))
    if adjusted > 0:
        return "win", "loss"
    if adjusted < 0:
        return "loss", "win"
    return "push", "push"


def grade_ml(home_score, away_score) -> tuple[str, str] | None:
    if home_score is None or away_score is None:
        return None
    home = Decimal(str(home_score))
    away = Decimal(str(away_score))
    if home > away:
        return "win", "loss"
    if home < away:
        return "loss", "win"
    return "tie", "tie"


def grade_total(home_score, away_score, line) -> tuple[str, str] | None:
    """(over, under)."""
    if home_score is None or away_score is None or line is None:
        return None
    adjusted = (Decimal(str(home_score)) + Decimal(str(away_score))
                - Decimal(str(line)))
    if adjusted > 0:
        return "win", "loss"
    if adjusted < 0:
        return "loss", "win"
    return "push", "push"


def _num(value):
    if value is None:
        return None
    return Decimal(str(value))


def _side(pair, index: int):
    if pair is None:
        return None
    return pair[index]


def assemble_game(game: dict, quotes: list[dict],
                  played: dict[str, list[date]]) -> dict | None:
    """One facts dict, or None when this game is not built.

    Not built: the id does not parse, or the season in the id is before
    DraftKings history. A missing line is not a reason to skip. A large
    spread is not a reason to skip. Moneyline uses the score only.
    """
    parsed = parse_game_id(game.get("game_id") or "")
    if parsed is None:
        return None
    key, season, week, away, home = parsed
    if season < DK_HISTORY_START_SEASON:
        return None

    spread = line_at_start(_pre_start(quotes, "spreads"))
    total = line_at_start(_pre_start(quotes, "totals"))
    dk_spread = None if spread is None else spread.get("point")
    dk_total = None if total is None else total.get("point")

    home_score = game.get("home_score")
    away_score = game.get("away_score")
    ats = grade_ats(home_score, away_score, dk_spread)
    ml = grade_ml(home_score, away_score)
    ou = grade_total(home_score, away_score, dk_total)
    home_role, away_role = roles(dk_spread)
    game_day = parse_date(game.get("game_date"))
    commence = game.get("commence_time")
    if parse_ts(commence) is None:
        for slot in (spread, total):
            if slot is not None and parse_ts(slot.get("commence_time")) is not None:
                commence = slot.get("commence_time")
                break

    return {
        "canonical_key": key,
        "sport": "NFL",
        "season": season,
        "week": week,
        "away_team": away,
        "home_team": home,
        "game_date": game_day,
        "commence_time": parse_ts(commence),
        "home_score": _num(home_score),
        "away_score": _num(away_score),
        "line_basis": LINE_BASIS,
        "dk_spread_home": _num(dk_spread),
        "dk_total": _num(dk_total),
        "ats_home_result": _side(ats, 0),
        "ats_away_result": _side(ats, 1),
        "ml_home_result": _side(ml, 0),
        "ml_away_result": _side(ml, 1),
        "ou_over_result": _side(ou, 0),
        "ou_under_result": _side(ou, 1),
        "home_rest_days": rest_days(home, game_day, played),
        "away_rest_days": rest_days(away, game_day, played),
        "is_primetime": is_primetime(commence),
        "home_role": home_role,
        "away_role": away_role,
    }

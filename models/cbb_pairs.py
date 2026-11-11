"""A total UNDER and a spread bet on a big favourite are not held on one
college basketball game, men's or women's.

mike, 2026-11-11: "half time unders should not be taken along with big
favorite spreads, like I have seen some men picks where you pick half time
under and a -14, these have a low chance of hitting together, ensure we
account for that in mens and womens models."

WHAT HE SAW. From 2026-11-03 to 11-10 ten men's games carried a first-half
under AND a first-half spread bet on a favourite laying 13.5 to 19.5. Both
won in 2 of the 10 (the under 2-8, the favourite 8-2).

WHAT THE HISTORY SAYS (the local copy of the database, 17,117 men's games of
2023-24 to 2026-27 with a pre-game first-half spread, total and score; no
model). When the favourite lays 6 to 15 points in the half, its cover and the
under come in together in 21 to 22 games in 100, against 23 to 24 if the two
were unrelated: the under hits 44 to 47% of the time the favourite covers and
50 to 55% when it does not. Under 3 points there is no relation. On the full
game the same shows from 20 points up, men's and women's (men's 20 to 30: both
22.1% against 24.1%; women's 30 and up: 22.9% against 25.5%).

THE RULE. Two bets on one game are the pair when one is a total UNDER and the
other is a spread bet on the FAVOURITE laying BIG_FAVOURITE points or more: 12
on a first-half spread, 20 on a full-game spread (a first-half number runs
about 0.58 of the full-game number). The second of the two to be decided is
not bet. The standing bet keeps the game and is never touched (CLAUDE.md
section 1c), the same way two bets that cannot both win are handled.

WHERE. Every college basketball writer asks before it bets: the five cards
through `hold_back` (the bet becomes a priced, unstaked NONE row, the way a
bet under the price floor does), the two in-play loops through `clash` and
`pair` (a `declined` decision). Women's college basketball has no spread model
today, so nothing can trip it there yet; the check is in place for the day
one exists.

THE FIRST-HALF UNDER HAS ITS OWN, EARLIER RULE (models/ncaab_first_half_total.
UNDER_BIG_FAVOURITE): that model decides fifty minutes before the first-half
spread model does, so a pair check alone would keep the under and drop the
favourite, the leg that pays. docs/sports/ncaab.md, "An under beside a big
favourite".
"""
from __future__ import annotations

# Spread models and what their number is a spread on.
SPREADS = {
    "ncaab_spread_market": "full",
    "ncaab_first_half_spread": "first_half",
    "ncaab_live_spread_h1": "full",          # bet in the first half, on the full game
    "ncaab_live_spread_h2": "full",
}
# Total models: any of their UNDER bets is half of the pair.
TOTALS = (
    "ncaab_total_blend", "ncaab_first_half_total", "ncaab_live_total_h2",
    "ncaabw_total_blend", "ncaabw_live_total_ht",
)
# Points the favourite lays at or above which it is "big", by the spread's scope.
BIG_FAVOURITE = {"full": 20.0, "first_half": 12.0}


def points_laid(side: str, home_line: float) -> float:
    """Points the picked side lays (positive: it is the favourite). `home_line`
    is the HOME number, as scored_line stores every spread (CLAUDE.md section 4)."""
    return -float(home_line) if side == "home" else float(home_line)


def big_favourite(model_id: str, side, line) -> bool:
    """Is this a spread bet on a favourite laying big points?"""
    scope = SPREADS.get(model_id)
    if scope is None or side not in ("home", "away") or line is None:
        return False
    return points_laid(side, line) >= BIG_FAVOURITE[scope]


def under(model_id: str, side) -> bool:
    return model_id in TOTALS and side == "under"


def pair(a: dict, b: dict) -> bool:
    """Are these two bets the pair? Each dict: model_id, side, line (the HOME
    number for a spread)."""
    return ((under(a["model_id"], a["side"]) and big_favourite(b["model_id"], b["side"], b["line"]))
            or (under(b["model_id"], b["side"]) and big_favourite(a["model_id"], a["side"], a["line"])))


_STANDING_SQL = """
    SELECT model_id, pick_side, scored_line, pick_label
      FROM picks
     WHERE game_id = %s AND signal_type = 'BET' AND model_id = ANY(%s)
       AND (condition_status IS NULL OR condition_status <> 'VOID')
     ORDER BY pick_id
"""


def clash(conn, game_id: str, model_id: str, side, line) -> str | None:
    """Why a bet of `model_id` on `side` at `line` would make the pair with a
    bet the game already holds, or None. One indexed read of `picks`, and none
    at all for a bet that is neither an under nor a big favourite."""
    mine = {"model_id": model_id, "side": side, "line": line}
    if under(model_id, side):
        others = list(SPREADS)
    elif big_favourite(model_id, side, line):
        others = list(TOTALS)
    else:
        return None
    for m, s, ln, label in conn.execute(_STANDING_SQL, (game_id, others)).fetchall():
        if pair(mine, {"model_id": m, "side": s, "line": None if ln is None else float(ln)}):
            what = "a big favourite's spread" if under(model_id, side) else "an under"
            return f"paired_with:{label or m} ({what} on the same game)"
    return None


def hold_back(conn, rows: list[dict], refused: dict) -> int:
    """A card's BET rows that would make the pair become NONE rows (priced, no
    stake), in place, with the reason in `refused` under the game id. Returns
    how many. Rows are picks rows: game_id, model_id, pick_side, scored_line."""
    n = 0
    for r in rows:
        if r.get("signal_type") != "BET":
            continue
        why = clash(conn, r["game_id"], r["model_id"], r.get("pick_side"), r.get("scored_line"))
        if why:
            r["signal_type"] = "NONE"
            r["kelly_fraction"], r["recommended_bet"] = 0.0, 0.0
            refused[r["game_id"]] = why
            n += 1
    return n

"""Tennis: what a match result means for a bet, at each book.

SETTLEMENT IS THE TRAP IN TENNIS. A match can end three ways besides a
completed final point: a walkover (never started), a retirement or
disqualification before the first set is complete, and one after it. Books
grade the last case differently, and the player who retires is far more often
the one who was losing, so a grader that treats every book alike manufactures
an edge on one side.

THE RULES, as each book states them:

  draftkings   moneyline: void if the retirement comes before the first set is
               complete; after it, the player who advances is the winner AND
               "Moneyline bets placed on the retiring or disqualified player or
               pairing will be void" (DraftKings house rules, Massachusetts
               edition dated 8.1.24, p. 47, read 2026-11-13). ITF matches: void
               on any retirement. Games spread and total games: graded on lines
               already decided once one set is complete (total games at the
               fewest games the match could have finished in), the rest void
               (p. 47-48). A tiebreak and a super tiebreak each count as one game.
  pinnacle     moneyline has action once one set is complete (the retiring
               player loses); every other market is void unless its period was
               finished (pinnacle.com betting rules, read by the scout 2026-11-13).
  fanduel,     one set completed for action (Action Network's book-by-book
  betmgm       table, updated 2026-05-04): the retiring player loses.
  williamhill_us  (Caesars) the full match must be completed, else void
               (the same table).
  everyone else  not read: graded as void on any retirement, and counted, so a
               result never rests on a rule nobody has checked.

    RULE_RETIREE_VOID   the retiring player's bets are void, the opponent's win
    RULE_ONE_SET        the retiring player's bets lose, the opponent's win
    RULE_FULL_MATCH     void
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

RULE_RETIREE_VOID = "retiree_void"
RULE_ONE_SET = "one_set"
RULE_FULL_MATCH = "full_match"

MONEYLINE_RULE = {
    "draftkings": RULE_RETIREE_VOID,
    "pinnacle": RULE_ONE_SET,
    "fanduel": RULE_ONE_SET,
    "betmgm": RULE_ONE_SET,
    "williamhill_us": RULE_FULL_MATCH,
}
DEFAULT_MONEYLINE_RULE = RULE_FULL_MATCH

WIN, LOSS, PUSH, VOID = "WIN", "LOSS", "PUSH", "VOID"


def fold(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ø", "o").replace("ß", "ss").replace("ł", "l").replace("đ", "d")
    return re.sub(r"[^a-z ]", " ", s.lower().replace("-", " ").replace("'", ""))


def name_key(name: str) -> frozenset:
    """A player's name as a set of folded tokens: 'Sun Fajing' and 'Fajing Sun'
    are one key, and so are 'Alex de Minaur' and 'Alex De Minaur'."""
    return frozenset(t for t in fold(name).split() if t)


# ── the result of one match ──────────────────────────────────────────────────

@dataclass
class Result:
    """One match, from the side of player A against player B."""
    a_games: list            # games won by A in each set played (a super tiebreak is one game)
    b_games: list
    a_advanced: bool         # A goes through (won, or B retired / was disqualified / gave a walkover)
    status: str              # "complete", "retired", "walkover"
    retired_side: str | None = None      # "a" or "b" when status is "retired"
    sets_complete: int = 0               # sets finished before the match ended
    best_of: int = 3
    super_tb_last: bool = field(default=False)

    @property
    def first_set_complete(self) -> bool:
        return self.sets_complete >= 1

    @property
    def total_games(self) -> int:
        return sum(self.a_games) + sum(self.b_games)


def _set_done(a: int, b: int, final_super: bool = False) -> bool:
    if final_super:
        return True
    hi, lo = max(a, b), min(a, b)
    return (hi >= 6 and hi - lo >= 2) or (hi == 7 and lo == 6) or (hi == 7 and lo == 5)


_SET = re.compile(r"^(\d+)-(\d+)(?:\((\d+)\))?$")
_SUPER = re.compile(r"^\[(\d+)-(\d+)\]$")


def from_archive_score(score: str, best_of: int = 3) -> Result | None:
    """The archive lists the WINNER first, and the retiring player is always
    the loser, so A is the winner. 'W/O' is a walkover; 'RET' and 'DEF' end a
    match early. Returns None for a score it cannot read."""
    s = str(score or "").strip()
    if not s:
        return None
    up = s.upper()
    if "W/O" in up or "WALKOVER" in up:
        return Result([], [], True, "walkover", best_of=best_of)
    retired = any(tok in up for tok in ("RET", "DEF", "ABD", "ABN"))
    a_g, b_g, done, sup = [], [], 0, False
    for tok in s.split():
        m = _SET.match(tok)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            a_g.append(a)
            b_g.append(b)
            if _set_done(a, b):
                done += 1
            continue
        m = _SUPER.match(tok)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            a_g.append(1 if a > b else 0)
            b_g.append(1 if b > a else 0)
            done += 1
            sup = True
            continue
        if tok.upper() in ("RET", "RET.", "DEF", "DEF.", "ABD", "ABN"):
            continue
        return None
    if not a_g:
        return Result([], [], True, "walkover" if not retired else "retired",
                      retired_side="b" if retired else None, best_of=best_of)
    return Result(a_g, b_g, True, "retired" if retired else "complete",
                  retired_side="b" if retired else None, sets_complete=done,
                  best_of=best_of, super_tb_last=sup)


# ── grading ──────────────────────────────────────────────────────────────────

def grade_moneyline(res: Result, side: str, book: str, *, itf: bool = False) -> str:
    """WIN/LOSS/VOID for a moneyline bet on `side` ("a" or "b") at `book`."""
    if res.status == "walkover":
        return VOID
    won = res.a_advanced if side == "a" else not res.a_advanced
    if res.status == "complete":
        return WIN if won else LOSS
    if not res.first_set_complete:
        return VOID
    rule = MONEYLINE_RULE.get(book, DEFAULT_MONEYLINE_RULE)
    if book == "draftkings" and itf:
        return VOID
    if rule == RULE_FULL_MATCH:
        return VOID
    if rule == RULE_RETIREE_VOID and side == res.retired_side:
        return VOID
    return WIN if won else LOSS


def grade_total(res: Result, line: float, over: bool) -> str:
    """Total games. Completed matches only; any retirement or walkover is VOID
    here (DraftKings settles lines already decided, Pinnacle voids: the
    stricter reading is used until a book's own rule is applied per book)."""
    if res.status != "complete":
        return VOID
    t = res.total_games
    if t == line:
        return PUSH
    return WIN if (t > line) == over else LOSS


def grade_games_spread(res: Result, side: str, point: float) -> str:
    """Games handicap on `side` with its own `point` (e.g. -3.5)."""
    if res.status != "complete":
        return VOID
    margin = sum(res.a_games) - sum(res.b_games)
    if side == "b":
        margin = -margin
    v = margin + point
    if v == 0:
        return PUSH
    return WIN if v > 0 else LOSS


# ── prices ───────────────────────────────────────────────────────────────────

def american_to_decimal(p: float) -> float:
    p = float(p)
    return 1 + (p / 100 if p > 0 else 100 / -p)


def implied(p: float) -> float:
    return 1 / american_to_decimal(p)


def no_vig_pair(p_a: float, p_b: float) -> tuple[float, float]:
    """Multiplicative de-vig of a two-way American pair."""
    ia, ib = implied(p_a), implied(p_b)
    s = ia + ib
    return ia / s, ib / s


def units(result: str, price: float) -> float:
    """Profit in units at the published stake: risk enough to win 1 unit, risk
    capped at 3 (tracking/discord_notifier.stake_for; +200 risks 0.5)."""
    d = american_to_decimal(price)
    risk = min(1.0 / (d - 1), 3.0)
    if result == WIN:
        return risk * (d - 1)
    if result == LOSS:
        return -risk
    return 0.0

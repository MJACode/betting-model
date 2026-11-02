"""
A pick is published only if its WORDS agree with its NUMBERS.

mike, 2026-09-12: *"I want error checking ... You must check every pick that
goes out."* A reply told him BUF @ HOU was "Bills -1". The pick was Bills +1,
and it went to his followers as -1.

What happened: `picks.scored_line` is the HOME number (CLAUDE.md §4) -- the
opener stores Houston's -1 for a Bills +1 bet. The label was right, the row was
right, Discord posted the label. The number was rebuilt from `scored_line`
without the flip, which §4 had already warned about twice.

So this checks the two halves of a pick against each other before any surface
sends it: the label a person reads, and the side and line the pick settles on.
They are written by the same code at the same moment, so they can only
disagree if something is broken -- and when they do, neither can be trusted,
so the pick is REFUSED and logged, never sent. It is not ledgered either, so it
retries every pass and the refusal stays loud until someone fixes the row.

Measured before this shipped (2026-09-12, every BET ever written): 83 spread
labels, 4,042 over/under labels and 412 moneyline labels, zero disagreements.
The check exists so the next one cannot reach a follower.

THE STAT CHECK WAS ADDED 2026-09-21, after the one it would have caught. The
live NFL prop model changed market from pass attempts to rushing attempts, one
display string was left behind, and "Blake Corum Under 11.5 Pass Attempts" went
to the live channel -- a running back on a passing line, with a correct bet
underneath it. Side and line both agreed with the row, so everything above
passed. What disagreed was the STAT, and nothing was looking at it.

It is deliberately a NEGATIVE check: a pick is refused only when its label names
a market that is not the one it stores. A label whose wording merely differs
from the platform's own ("Rec" against "Recs") is NOT refused, because a
publishing check that is stricter than it needs to be is an outage waiting for
the first model that words a label differently.

Checked:
  * spreads    -- the signed number in the label equals the SIDE's line
                  (the home number, negated for an away pick), and the label
                  names the side's team, not the other one.
  * over/under -- the label says the pick's side, at the stored line.
  * home/away  -- the label does not name the other team.
  * the STAT   -- a player prop's label does not name a DIFFERENT market from
                  the one the pick stores and settles on.
  * team total -- a pick that settles on ONE team's points (its model's market
                  is team_totals_home / team_totals_away) says "Team Total",
                  so it cannot be read as the full-game total, and does not
                  name the other team as the one whose points it is. Keyed on
                  the model's market, so no other model's verdict changes.
  * first half -- a pick that settles on Q1 + Q2 points (its model's market is
                  totals_h1) says "First Half", so it cannot be read as the
                  full-game total. Keyed on the model's market too.

A producer that does not supply `side` and `line` cannot be checked, so its
picks are refused too. A check that dead code can satisfy is not a check (§1b).
"""

from __future__ import annotations

import re

from loguru import logger

_SPREAD_HINTS = ("spread", "runline", "puckline")

# A signed number not glued to a word or a decimal: "+1", "-1.5", not "F5".
_SIGNED = re.compile(r"(?<![\w.])([+-]\d+(?:\.\d+)?)")
_OU_WORD = re.compile(r"\b(over|under)\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_OU_LETTER = re.compile(r"(?<![\w.])([ou])\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
# The words a label may legitimately use for each NFL prop market. Aliases and
# not a single name, because the platform, the app and the live model have each
# spelled these differently and the point is to catch a WRONG market rather than
# an unusual spelling. A market absent here is never checked.
_NFL_STAT_ALIASES: dict[str, tuple[str, ...]] = {
    "player_pass_attempts":      ("pass attempts", "pass att", "passing attempts"),
    "player_pass_completions":   ("completions", "pass comp", "comp"),
    "player_pass_yds":           ("pass yds", "pass yards", "passing yards"),
    "player_pass_tds":           ("pass tds", "pass td", "passing tds"),
    "player_rush_attempts":      ("carries", "rush attempts", "rush att",
                                  "rushing attempts"),
    "player_rush_yds":           ("rush yds", "rush yards", "rushing yards"),
    "player_receptions":         ("receptions", "recs", "rec"),
    "player_reception_yds":      ("rec yds", "receiving yards", "reception yards"),
    "player_rush_reception_yds": ("ru+re yds", "rush+rec yds", "rush + rec yds"),
    "player_anytime_td":         ("anytime td",),
    "player_tackles_assists":    ("tkl+ast", "tackles+assists", "tackles + assists"),
    "player_sacks":              ("sacks", "sack"),
}
# Longest first, so "receptions" is matched before the "rec" inside it and
# "pass attempts" before a bare "attempts" could ever be considered.
_STAT_BY_ALIAS: tuple[tuple[str, str], ...] = tuple(sorted(
    ((alias, market) for market, aliases in _NFL_STAT_ALIASES.items()
     for alias in aliases),
    key=lambda pair: -len(pair[0])))


def _stat_problem(label: str, prop_market: str | None) -> str | None:
    """The market this label NAMES, when that is not the market it stores."""
    if not prop_market or prop_market not in _NFL_STAT_ALIASES:
        return None
    text = label.lower()
    for alias, market in _STAT_BY_ALIAS:
        if re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", text):
            if market != prop_market:
                return (f"the label says {alias!r}, but the pick is on "
                        f"{prop_market} and settles against it")
            return None
    return None


_PICKEM = re.compile(r"\bPK\b|pick\s*'?\s*em|(?<![\w.+-])0(?:\.0)?(?![\w.])",
                     re.IGNORECASE)


def _market(model_id: str | None) -> str:
    """The market the pick settles on, or "" when it cannot be read."""
    try:
        # Lazy: paper_tracker imports config and the notifiers import this.
        from tracking.paper_tracker import _market_for_pick
        return _market_for_pick(model_id or "")
    except Exception:
        return ""


def _is_spread(model_id: str | None) -> bool:
    mid = model_id or ""
    return _market(mid).startswith("spreads") or any(h in mid for h in _SPREAD_HINTS)


_TEAM_TOTAL = re.compile(r"\bteam[\s-]*total\b", re.IGNORECASE)


def _team_total_problem(label: str, model_id: str | None,
                        home: str | None, away: str | None) -> str | None:
    """A team-total pick whose label reads as the game total or names the
    other team. None for every model whose market is not a team total."""
    market = _market(model_id)
    if market not in ("team_totals_home", "team_totals_away"):
        return None
    mine, theirs = (home, away) if market == "team_totals_home" else (away, home)
    if not _TEAM_TOTAL.search(label):
        return ("the label does not say Team Total, so it reads as the "
                "full-game total; the pick settles on one team's points"
                + (f" ({mine})" if mine else ""))
    tail = _tail(label)
    if _names(tail, theirs) and not _names(tail, mine):
        return (f"the label names {theirs}, but the pick is on {mine}'s "
                f"team total")
    return None


_FIRST_HALF = re.compile(r"\bfirst[\s-]*half\b", re.IGNORECASE)


def _first_half_problem(label: str, model_id: str | None) -> str | None:
    """A first-half pick whose label reads as the game total. None for every
    model whose market is not the first half's total."""
    if _market(model_id) != "totals_h1":
        return None
    if not _FIRST_HALF.search(label):
        return ("the label does not say First Half, so it reads as the "
                "full-game total; the pick settles on the first half's points")
    return None


def _tail(label: str) -> str:
    """The bet itself: the opener writes "BUF @ HOU — BUF +1 (...)"."""
    return label.rsplit("— ", 1)[-1].strip()


def _names(text: str, team: str | None) -> bool:
    return bool(team) and (text == team or text.startswith(f"{team} "))


def pick_problems(label, side, line, model_id, home=None, away=None,
                  prop_market=None) -> list[str]:
    """Every way this pick's label disagrees with its side and line. Empty = OK."""
    if label is None or not str(label).strip():
        return ["the pick has no label"]
    label = str(label)
    tail = _tail(label)
    side = (side or "").lower()
    problems: list[str] = []

    if side in ("home", "away"):
        mine, theirs = (home, away) if side == "home" else (away, home)
        if _names(tail, theirs) and not _names(tail, mine):
            problems.append(f"the label names {theirs}, but the pick is on the "
                            f"{side} side ({mine})")
        if line is not None and _is_spread(model_id):
            expected = -float(line) if side == "away" else float(line)
            m = _SIGNED.search(tail)
            if m is None:
                if not (expected == 0 and _PICKEM.search(tail)):
                    problems.append(f"the label carries no spread; the {side} "
                                    f"side's line is {expected:+g}")
            elif abs(float(m.group(1)) - expected) > 1e-9:
                problems.append(f"the label says {m.group(1)}, but the stored "
                                f"line for the {side} side is {expected:+g}")

    elif side in ("over", "under") and line is not None:
        m = _OU_WORD.search(label) or _OU_LETTER.search(label)
        if m is None:
            problems.append(f"the label carries no total; the stored line is "
                            f"{float(line):g}")
        else:
            if m.group(1).lower()[0] != side[0]:
                problems.append(f"the label says {m.group(1)}, but the pick is "
                                f"the {side}")
            if abs(float(m.group(2)) - float(line)) > 1e-9:
                problems.append(f"the label says {m.group(2)}, but the stored "
                                f"line is {float(line):g}")

    stat = _stat_problem(label, prop_market)
    if stat:
        problems.append(stat)
    team_total = _team_total_problem(label, model_id, home, away)
    if team_total:
        problems.append(team_total)
    first_half = _first_half_problem(label, model_id)
    if first_half:
        problems.append(first_half)
    return problems


def refuse_mismatched(signals: list[dict], surface: str) -> list[dict]:
    """The signals that are safe to send. Each refused one is logged at ERROR.

    Every producer dict must carry `side` and `line` (None is a valid line for a
    moneyline); a dict without them is refused rather than waved through.
    """
    kept: list[dict] = []
    for s in signals:
        if "side" not in s or "line" not in s:
            problems = ["the producer did not supply side and line, so the "
                        "label cannot be checked"]
        else:
            problems = pick_problems(s.get("label"), s.get("side"), s.get("line"),
                                     s.get("model_id"), s.get("home"), s.get("away"),
                                     s.get("prop_market"))
        if problems:
            logger.error(f"{surface}: REFUSED to publish {s.get('lock_key')} "
                         f"{s.get('label')!r}: {'; '.join(problems)}")
            continue
        kept.append(s)
    return kept

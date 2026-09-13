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

Checked:
  * spreads    -- the signed number in the label equals the SIDE's line
                  (the home number, negated for an away pick), and the label
                  names the side's team, not the other one.
  * over/under -- the label says the pick's side, at the stored line.
  * home/away  -- the label does not name the other team.

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
_PICKEM = re.compile(r"\bPK\b|pick\s*'?\s*em|(?<![\w.+-])0(?:\.0)?(?![\w.])",
                     re.IGNORECASE)


def _is_spread(model_id: str | None) -> bool:
    mid = model_id or ""
    try:
        # Lazy: paper_tracker imports config and the notifiers import this.
        from tracking.paper_tracker import _market_for_pick
        market = _market_for_pick(mid)
    except Exception:
        market = ""
    return market.startswith("spreads") or any(h in mid for h in _SPREAD_HINTS)


def _tail(label: str) -> str:
    """The bet itself: the opener writes "BUF @ HOU — BUF +1 (...)"."""
    return label.rsplit("— ", 1)[-1].strip()


def _names(text: str, team: str | None) -> bool:
    return bool(team) and (text == team or text.startswith(f"{team} "))


def pick_problems(label, side, line, model_id, home=None, away=None) -> list[str]:
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
                                     s.get("model_id"), s.get("home"), s.get("away"))
        if problems:
            logger.error(f"{surface}: REFUSED to publish {s.get('lock_key')} "
                         f"{s.get('label')!r}: {'; '.join(problems)}")
            continue
        kept.append(s)
    return kept

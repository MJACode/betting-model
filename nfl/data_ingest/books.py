"""Which books a bet can ACTUALLY BE PLACED AT.

One definition, because there are two NFL cards and they must not disagree
about it. The opener got this filter on 2026-09-06 after mike looked at the
Week-1 board and found the two largest edges sitting at onexbet (+7.32pp) and
betus (+5.92pp) — books with no US licence. The wind card had exactly the same
hole and kept it for another few hours: its five locked Week-1 picks name
gtbets, lowvig and onexbet.

mike: "no can't bet on these remove them."

A pick naming an unplaceable book is worse than no pick. §1c makes it
permanent, so nothing can retract it, and it enters the track record as a bet
that was never available — inflating the record with returns nobody could have
collected.

THE CANONICAL LIST IS `config.BETTABLE_BOOKS`, derived there from
LINE_SHOP_BOOKMAKERS (the list mike curated as the books the app quotes a price
at) minus the two entries carried for analysis rather than placement: pinnacle,
the sharp reference the opener measures against, and bovada, offshore.

THE LITERAL BELOW IS A FALLBACK, not a second opinion. This package runs
standalone — backtests, replay harnesses and one-off scripts execute with the
nfl/ root on sys.path and no repo root, where `import config` finds nothing at
all. tests/test_nfl_opener.py pins the fallback against config.BETTABLE_BOOKS,
so the copy cannot drift unnoticed.

WHEN IN DOUBT, LEAVE A BOOK OUT. The failure modes are not symmetric: too
narrow loses a bet we could have had, which is recoverable and shows up as a
missing row, while too wide locks an unplaceable pick forever.
"""

from __future__ import annotations

import os

BETTABLE_FALLBACK = ("draftkings,fanduel,betmgm,williamhill_us,espnbet,"
                     "fanatics,betrivers,hardrockbet,ballybet,betparx,rebet")


def bettable_books() -> set[str]:
    """The placement venues.

    Read fresh on every call rather than captured at import, so an env override
    applies to the process that sets it — the cards are long-lived under the
    scheduler and a value frozen at import would ignore a Railway change until
    the next deploy.
    """
    env = os.environ.get("BETTABLE_BOOKS")
    if env:
        return {b.strip().lower() for b in env.split(",") if b.strip()}
    try:
        from config import BETTABLE_BOOKS as _cfg
        return {b.strip().lower() for b in _cfg}
    except Exception:                                          # noqa: BLE001
        return {b.strip().lower() for b in BETTABLE_FALLBACK.split(",")}

"""A restatement must publish the same card as the post it corrects.

Found 2026-09-03 by rendering the 2026-09-02 slate through the real producers
to answer "what would have gone to Discord?" — CLAUDE.md §7's rule that a
hand-written fixture drifts from the producer exactly as the renderer did.

`notify_discord_signals` reads `_new_signals`, which selects best_book/best_odds.
`notify_discord_restate` reads `_locked_signals`, which did not. Both render
through `_signal_field` → `better_price_note`, so a restatement silently dropped
the "also `-120` @ BetMGM" line from every pick that had one — a correction
telling the reader a WORSE place to bet than the post it was correcting.

On that slate 11 of 22 picks carried a better non-DK price, so half the card
changed. Same family as the session-171 X/Discord divergence: two paths
publishing one pick, only one of them complete (§1b).
"""

from __future__ import annotations

import re

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import discord_notifier as dn  # noqa: E402

SRC = (Path(__file__).parent.parent / "tracking"
       / "discord_notifier.py").read_text(encoding="utf-8")


def _producer(name: str) -> str:
    start = SRC.index(f"def {name}(")
    end = SRC.index("\ndef ", start + 1)
    return SRC[start:end]


def test_both_signal_producers_select_the_better_price():
    """Whichever path publishes a pick, it publishes the same price options.

    Asserted on the OUTER select list (`pk.best_book`), not on the substring
    "best_book" anywhere in the function: both producers mention the columns in
    their LATERAL join, so a looser check passes while the outer SELECT — the
    part that actually reaches the renderer — is missing them. That weaker
    version was written first and survived the mutation.
    """
    # Adjacent pair in the select list, either alias. `_new_signals` reads
    # `picks` as its base table since 2026-09-05 and so projects `p.`, while
    # `_locked_signals` still reaches it through a LATERAL and projects `pk.`.
    # The alias was never the property; the projection reaching the renderer is.
    for name in ("_new_signals", "_locked_signals"):
        body = _producer(name)
        assert re.search(r"\bpk?\.best_book,\s*pk?\.best_odds", body), (
            f"{name} does not project the better price out to the renderer, so "
            f"anything rendered through it drops the 'also @ Book' line")


def test_the_locked_producer_maps_the_columns_into_the_dict():
    """Selecting them is not enough — better_price_note reads dict keys."""
    body = _producer("_locked_signals")
    assert '"best_book": r[' in body and '"best_odds": r[' in body


def test_a_restated_pick_still_names_the_cheaper_book():
    """End to end through the real renderer, not a source grep."""
    signal = {
        "label": "Tomoyuki Sugano Under 6.5 Hits", "sport": "MLB",
        "model_id": "mlb_prop_pitcher_hits", "dk_odds": -139.0,
        "kelly": 0.02, "home": "COL", "away": "BAL", "commence": None,
        "posted_at": None, "best_book": "betmgm", "best_odds": -120.0,
    }
    field = dn._signal_field(signal)
    assert "-120" in field["value"] and "BetMGM" in field["value"], (
        "the restated card lost the better price")


def test_a_worse_price_elsewhere_never_replaces_draftkings():
    """Publishing a worse price as though it were an upgrade is the one failure
    mode worse than publishing DraftKings'. (Was written against
    better_price_note, which became publish_price on 2026-09-03 when the best
    book moved from a footnote to the headline.)"""
    same = dict(dk_odds=-110.0, best_book="draftkings", best_odds=-110.0)
    worse = dict(dk_odds=-110.0, best_book="betmgm", best_odds=-125.0)
    assert dn.publish_price(same) == (-110.0, "DraftKings")
    assert dn.publish_price(worse) == (-110.0, "DraftKings")

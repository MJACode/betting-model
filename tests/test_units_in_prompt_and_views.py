"""The Claude-mobile picks prompt speaks in units, never dollars.

mike, 2026-11-03: *"everything must be units"*. CLAUDE.md §4: one unit is one
flat bet, and a dollar figure invents a stake size nobody chose.

Until this file existed the prompt pasted into the Claude-mobile project asked
for a bankroll, sized every pick as ``kelly_fraction * bankroll``, printed a
``Bet ($)`` column and a dollar exposure line. Every other surface (Discord,
push, the Record tab, the website) publishes the flat unit stake from
``tracking.discord_notifier.stake_for``: one unit to win at
``COALESCE(decision_odds, dk_odds)``, risk capped at 3 units, a bare 1 unit
when the pick has no price. So the prompt quoted a different bet from the one
the channel posted for the same pick.

The stake comes from the database function that the published record is
built on (``published_pick_stake``), so it cannot drift from the channel.
``tests/test_record_units_agree.py`` pins that function's SQL body to
``stake_for``. Since 2026-11-04 there is no prompt to paste: the open picks are
the ``public.open_picks`` view, and this file pins that the view uses that
function and quotes no money, and that the doc reads records in units.
"""
from __future__ import annotations

import re
from pathlib import Path

from tracking.discord_notifier import fmt_stake, stake_for

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "docs" / "mobile_picks_prompt.md").read_text(encoding="utf-8")

# The query a Claude chat reads: the open_picks view body.
_MIG = (ROOT / "data" / "migrations" / "open_picks_view_2026_11_04.sql").read_text(encoding="utf-8")
BLOCK = re.search(r"\$view\$(.*?)\$view\$", _MIG, re.S).group(1)

STAKE_PRICE = "COALESCE(p.decision_odds, p.dk_odds)"


def test_the_prompt_quotes_no_dollar_amount():
    """No dollar sign anywhere in what Claude is told to print or compute."""
    hits = [line.strip() for line in BLOCK.splitlines() if "$" in line]
    assert not hits, f"dollar signs in the open picks view: {hits}"
    assert "$" not in DOC.replace("$view$", ""), "a dollar sign in the doc"


def test_the_prompt_never_sizes_a_pick_off_a_bankroll():
    """A bankroll-sized stake is a dollar stake, and kelly_fraction is not the
    published stake (it is FLAT 1u to win, conviction_for)."""
    assert "my_bankroll" not in BLOCK
    assert "Ask me for my current bankroll" not in BLOCK
    assert not re.search(r"kelly_fraction\s*[*x×]", BLOCK), (
        "the prompt still multiplies kelly_fraction into a stake")
    assert "Kelly %" not in BLOCK, "a Kelly % column is a stake as a share of a bankroll"
    assert "scaled to the bankroll" not in DOC


def test_the_stake_comes_from_the_published_stake_function():
    """The same function v_public_track_record and Discord #results book, at
    the price the pick was decided at."""
    assert f"public.published_pick_stake({STAKE_PRICE}) s" in BLOCK
    for col in ("ROUND(s.risk, 2) AS risk_units", "ROUND(s.win, 2) AS to_win_units",
                "END AS stake"):
        assert col in BLOCK, f"the view lost the unit stake: {col}"


def test_the_stake_examples_match_the_channel_format():
    """The view writes the stake as text. It must read the way fmt_stake prints
    it: two decimals, half up, zeros trimmed, a bare 1u with no price. The SQL
    was compared with fmt_stake on production for 21 prices on 2026-11-04."""
    examples = {-110: "1.1u to win 1u", 150: "0.67u to win 1u", -350: "3u to win 0.86u",
                -115: "1.15u to win 1u"}
    for price, text in examples.items():
        assert fmt_stake(stake_for(None, price)) == text, (price, fmt_stake(stake_for(None, price)))
    assert "1.15u to win 1u" in DOC
    assert "trim_scale(ROUND(s.risk, 2))::text || 'u to win '" in BLOCK
    # Unpriced: the bare conviction, never a made-up -110 price.
    assert fmt_stake(stake_for(None, None)) == "1u"
    assert "THEN '1u'" in BLOCK


def test_records_are_read_in_units():
    """A follow-up like "how did yesterday go?" must not be answered by
    summing profit_flat and quoting it as money."""
    assert "v_public_track_record" in DOC
    assert "units and risked" in DOC
    assert "profit_flat / 100.0" in DOC

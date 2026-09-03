"""The free pick names the cheaper book, on both public surfaces.

mike, 2026-09-03: "Yes @ book line."

The paid sport channels have named a cheaper book since 2026-08-30. The free
Discord card and the tweet did not — the same pick reached three surfaces
carrying three different amounts of information, and the two PUBLIC ones
carried the least. Same family as the session-171 X/Discord recap divergence
and the session-176 restate bug: one pick, several paths, only some complete.

Also pins the book list (mike, same day: "do the extra books") — every book
that can be OFFERED must render with a human name on both surfaces, or a
members' channel prints "hardrockbet".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from tracking import discord_notifier as dn  # noqa: E402
from tracking import x_publisher as xp  # noqa: E402

DN_SRC = (Path(__file__).parent.parent / "tracking"
          / "discord_notifier.py").read_text(encoding="utf-8")


def _pick(**kw):
    base = {"sport": "MLB", "label": "KC vs MIA Under 8.5", "dk_odds": -102.0,
            "kelly": 0.02, "home": "KC", "away": "MIA", "commence": None,
            "posted_at": None, "best_book": "espnbet", "best_odds": 100.0}
    base.update(kw)
    return base


# ── the tweet ────────────────────────────────────────────────────────────────

def test_the_tweet_names_the_cheaper_book():
    """The cheaper book is the HEADLINE as of 2026-09-03, not a footnote after
    the DraftKings price — mike, "it just needs to post the best book and
    price". The earlier assertion here expected both prices in the tweet."""
    t = xp.render_free_pick(_pick(), "2026-09-02")
    assert "+100 at ESPN BET" in t
    assert "-102" not in t, "the DK price is no longer the published one"


def test_the_tweet_still_has_no_link():
    """A book name is not a URL, and the 13x link rate must not be reachable
    through this clause."""
    xp._assert_no_link(xp.render_free_pick(_pick(), "2026-09-02"))


def test_the_tweet_says_draftkings_when_draftkings_is_best():
    t = xp.render_free_pick(_pick(best_book="draftkings", best_odds=-102.0),
                            "2026-09-02")
    assert "-102 at DraftKings" in t


@pytest.mark.parametrize("worse", [-130.0, -102.0])
def test_the_tweet_never_publishes_a_worse_price_than_draftkings(worse):
    t = xp.render_free_pick(_pick(best_book="betmgm", best_odds=worse),
                            "2026-09-02")
    assert "BetMGM" not in t
    assert "-102 at DraftKings" in t


def test_the_good_to_clause_is_dropped_not_truncated_when_it_will_not_fit():
    """A half-written price is worse than none. The hashtags earn their place
    (+21% engagement) and the pick itself is the post.

    The label length is chosen so the tweet fits WITHOUT the "good to" clause
    and overflows WITH it — the only case this branch decides. A longer label
    overflows on its own and hits the pre-existing `[:MAX_TWEET]` truncation,
    which is a different (and already tested) behaviour.
    """
    label = "X" * 200
    base = xp.render_free_pick(_pick(label=label), "2026-09-02")
    assert len(base) <= xp.MAX_TWEET, "fixture no longer fits without the clause"

    t = xp.render_free_pick(_pick(label=label, good_to=-115), "2026-09-02")
    assert len(t) <= xp.MAX_TWEET
    assert "Good to" not in t, "the clause was added and then truncated"
    assert t.endswith(xp.hashtags_for("MLB")), "the tags were pushed off the end"


def test_the_tweet_publishes_the_good_to_bound_when_it_fits():
    t = xp.render_free_pick(_pick(good_to=-115), "2026-09-02")
    assert "Good to -115." in t


def test_a_pick_with_no_alternative_falls_back_to_draftkings():
    assert xp._publish_price({"dk_odds": -110, "best_book": None,
                              "best_odds": None}) == (-110, "DraftKings")
    assert xp._publish_price({"dk_odds": None, "best_book": None,
                              "best_odds": None}) == (None, None)


# ── the free Discord card ────────────────────────────────────────────────────

def test_the_free_card_names_the_cheaper_book():
    embed = dn._free_pick_embed(_pick(), "2026-09-02")
    value = embed["fields"][0]["value"]
    assert "+100 @ ESPN BET" in value
    assert "-102" not in value, "the DK price is no longer the published one"


def test_the_free_card_query_reads_the_columns_it_renders():
    """Selecting them is the half that was missing; rendering them is useless
    without it."""
    start = DN_SRC.index("def _free_pick_candidates(")
    body = DN_SRC[start:DN_SRC.index("\ndef ", start + 1)]
    assert "pk.best_book" in body and "pk.best_odds" in body
    assert '"best_book": r[' in body and '"best_odds": r[' in body


# ── the book list ────────────────────────────────────────────────────────────

def test_the_extra_books_are_offered():
    for book in ("betrivers", "hardrockbet", "ballybet", "betparx", "rebet"):
        assert book in config.BEST_LINE_BOOKMAKERS, f"{book} is not shoppable"
        assert book in config.ODDS_API_BOOKMAKERS_PARAM, f"{book} is not fetched"


def test_every_offerable_book_has_a_human_name_on_both_surfaces():
    """A key with no display entry renders as its raw feed name, and
    "hardrockbet" in a channel members pay for reads like a bug."""
    for book in config.BEST_LINE_BOOKMAKERS:
        assert book in dn._BOOK_NAMES, f"{book} has no Discord display name"
        assert book in xp._BOOK_DISPLAY, f"{book} has no X display name"


def test_the_us2_credit_cost_is_written_down_where_the_list_is():
    """These five span a second Odds API region, which DOUBLES the bill on
    every fetch that uses this param — measured 3 -> 6 credits on one bulk MLB
    call. The next person editing this list needs that in front of them (§1b)."""
    src = (Path(__file__).parent.parent / "config.py").read_text(encoding="utf-8")
    assert "us2" in src and "6 credits" in src

"""Discord publishes the best price for the bettor — without moving the decision.

mike, 2026-08-30: "the bet should pick the best line for the bettor, across the
main books, not just DK."
mike, 2026-09-03: "it just needs to post the best book and price and for bonus,
post a 'good to xx odds'."

The first version of this shipped as a FOOTNOTE — the card led with DraftKings
and appended "also `-120` @ BetMGM". That buried the number the reader is meant
to act on behind the number the MODEL happens to decide on, and on the
2026-09-02 slate it did that on half the card. The best bettable price is now
the headline; DraftKings appears only when it is the best.

THE DISTINCTION THIS FILE EXISTS TO PROTECT, UNCHANGED. The models DECIDE on
DraftKings (CLAUDE.md §6): every threshold was swept on DK-implied edge, and a
best-of-N price is systematically cheaper in implied probability, so adopting it
as the QUALIFYING price would loosen every cut with nobody deciding to. This
changes where a reader PLACES the bet, never whether the bet exists — and a
future edit that quietly starts gating on best_odds is the regression to catch.
"""

from __future__ import annotations

import re

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.discord_notifier import _signal_field, publish_price  # noqa: E402

_SRC = (Path(__file__).parent.parent / "tracking"
        / "discord_notifier.py").read_text(encoding="utf-8")


def _sig(**kw):
    base = {"label": "Tomoyuki Sugano Under 6.5 Hits", "sport": "MLB",
            "model_id": "mlb_prop_pitcher_hits", "dk_odds": -139.0,
            "kelly": 0.02, "home": "COL", "away": "BAL", "commence": None,
            "posted_at": None, "best_book": "betmgm", "best_odds": -120.0}
    base.update(kw)
    return base


# ── the headline price ───────────────────────────────────────────────────────

def test_a_strictly_better_book_becomes_the_headline():
    odds, book = publish_price(_sig())
    assert odds == -120.0 and book == "BetMGM"


def test_it_works_on_plus_money_too():
    odds, book = publish_price(_sig(dk_odds=-102.0, best_book="espnbet",
                                    best_odds=100.0))
    assert odds == 100.0 and book == "ESPN BET"


@pytest.mark.parametrize("best", [-139.0, -150.0])
def test_an_equal_or_worse_price_never_replaces_draftkings(best):
    """Publishing a worse price as though it were an upgrade is the one failure
    mode worse than publishing DraftKings'."""
    odds, book = publish_price(_sig(best_odds=best))
    assert odds == -139.0 and book == "DraftKings"


def test_draftkings_winning_its_own_shop_is_published_as_draftkings():
    odds, book = publish_price(_sig(best_book="draftkings", best_odds=-139.0))
    assert odds == -139.0 and book == "DraftKings"


@pytest.mark.parametrize("missing", [{"best_book": None}, {"best_odds": None},
                                     {"best_book": "", "best_odds": None}])
def test_missing_data_falls_back_rather_than_breaking(missing):
    odds, book = publish_price(_sig(**missing))
    assert odds == -139.0 and book == "DraftKings"


def test_the_headline_reaches_the_rendered_line():
    value = _signal_field(_sig())["value"]
    assert "-120 @ BetMGM" in value
    assert "-139" not in value, "the DK price is no longer the published one"


def test_the_stake_is_grossed_up_by_the_published_price():
    """Telling a reader to risk 1.39u at -139 while pointing them at BetMGM's
    -120 would have them lay 16% more than the bet needs."""
    at_best = _signal_field(_sig())["value"]
    at_dk = _signal_field(_sig(best_book=None, best_odds=None))["value"]
    assert "1.2u" in at_best, at_best
    assert "1.39u" in at_dk, at_dk


# ── the "good to" bound ──────────────────────────────────────────────────────

def test_good_to_is_published_when_the_producer_supplies_it():
    value = _signal_field(_sig(good_to=-125))["value"]
    assert "good to `-125`" in value


def test_good_to_is_simply_absent_when_it_cannot_be_computed():
    assert "good to" not in _signal_field(_sig())["value"]


@pytest.mark.parametrize("fn", ["_new_signals", "_locked_signals",
                                "_free_pick_candidates"])
def test_every_pre_game_producer_computes_good_to(fn):
    """It was live-only until 2026-09-03. All three pre-game producers read the
    gates from the SAME model_action_thresholds row the scorer's cut comes from,
    so the published range and the applied cut cannot drift apart."""
    i = _SRC.index(f"def {fn}(")
    body = _SRC[i:_SRC.index("\ndef ", i + 10)]
    assert "price_bound(" in body, f"{fn} publishes no good-to bound"
    assert "t.min_edge" in body and "t.min_odds" in body


# ── the guards that must not move ────────────────────────────────────────────

def test_best_odds_never_reaches_the_qualifying_gate():
    """
    §6's tripwire. The threshold join in _new_signals gates on os.* and t.*
    columns; best_odds is read from the picks row for DISPLAY and must never
    appear in a WHERE clause.
    """
    i = _SRC.index("def _new_signals(")
    j = _SRC.index("\ndef ", i + 10)
    fn = _SRC[i:j]
    # The SQL only. A first version sliced to the end of the function and
    # tripped on the row dict, where "best_odds" is a legitimate output key —
    # a test that fails on correct code teaches people to delete tests.
    sql_start = fn.index('conn.execute("""') + len('conn.execute("""')
    sql = fn[sql_start:fn.index('"""', sql_start)]
    where = sql[sql.index("WHERE"):]
    assert "best_odds" not in where, (
        "best_odds appears in the signal query's WHERE — the BET decision must "
        "stay on DraftKings (§6)")
    # ...and it IS projected out to the caller, or the display half was never
    # wired. Checked against the OUTER select list and the row dict's indices,
    # not against "is the string anywhere before the first WHERE" — that first
    # WHERE belongs to the LATERAL subquery, so the loose version stayed true
    # with the outer projection deleted and a mutation sailed through it.
    # The ADJACENT PAIR in a select list is what makes this mutation-resistant:
    # a bare "best_book somewhere in the function" check passed while the outer
    # projection was deleted, because the old LATERAL mentioned the columns too.
    # The alias is not the point and stopped being "pk." on 2026-09-05, when the
    # producer began reading `picks` as its base table -- so match either.
    assert re.search(r"\bpk?\.best_book,\s*pk?\.best_odds", sql), (
        "the outer SELECT must project the best price")
    assert '"best_book": r[14], "best_odds": r[15],' in fn, (
        "the row dict must read the projected columns")


def test_the_live_path_is_untouched():
    """
    Live picks carry no multi-book best price, and the live lane has its own
    staleness story. Publishing a shopped price there would advertise a number
    we never measured in-play.
    """
    i = _SRC.index("def _new_live_signals(")
    j = _SRC.index("\ndef ", i + 10)
    assert "best_odds" not in _SRC[i:j]

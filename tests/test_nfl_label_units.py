"""NFL pick labels carry no unit figure. The stake is the posted one, shown
beside the label on every surface.

mike, 2026-11-04: "everything must be units", on one basis: the posted stake,
1u to win at COALESCE(decision_odds, dk_odds), risk capped at 3u (stake_for /
published_pick_stake, CLAUDE.md §2 and §4). On production that day the open
picks view and Discord showed one row with two unit numbers that disagreed:

    pick  "DAL @ IND — IND +7.5 · 0.79u · NEW 0m"   stake "1.17u to win 1u"
    pick  "LA @ WAS Under 47.5 · 0.87u"             stake "1.1u to win 1u"

The label's figure was the model's own sizing (kelly_fraction / 1%), written
into pick_label by scripts/nfl_wind_publisher.py. No other sport's label
carries a unit figure, so new NFL labels drop it. The sizing stays on the row
as kelly_fraction.

Stored labels are never rewritten (CLAUDE.md §1c). The surfaces that show an
old label beside the posted stake drop only that token, on display. The bet
itself (team, side, number), the age tag and any parenthetical stay word for
word (CLAUDE.md §00).

Nothing here posts, writes, or grades a live pick.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from scripts.nfl_wind_publisher import build_opener_rows, build_rows  # noqa: E402
from tracking import discord_notifier as dn  # noqa: E402
from tracking import paper_tracker as pt  # noqa: E402
from tracking import push_notifier as push  # noqa: E402
from tracking import x_publisher as xp  # noqa: E402
from tracking.pick_integrity import label_without_stake, pick_problems  # noqa: E402

# Three generations of each card's label. Only the last is written now.
OPENER_ANNOTATED = "TEN @ NYG — NYG -1 (Opener +2 vs Pinnacle, MGM) · 1.96u · NEW 0m"
OPENER_STAKED = "TEN @ NYG — NYG -1 · 1.96u · NEW 0m"
OPENER_BARE = "TEN @ NYG — NYG -1 · NEW 0m"
WIND_ANNOTATED = "NYJ @ MIA Under 43.5 (Wind 14 mph, FD) · 1.00u"
WIND_STAKED = "NYJ @ MIA Under 43.5 · 1.00u"
WIND_BARE = "NYJ @ MIA Under 43.5"

# The production rows that showed the problem (picks 4197557, 4197610).
PROD_OPENER = "DAL @ IND — IND +7.5 · 0.79u · NEW 0m"
PROD_WIND = "LA @ WAS Under 47.5 · 0.87u"


def _wind_card_row(**over):
    row = {
        "game_id": "2026_02_NYJ_MIA", "matchup": "NYJ @ MIA",
        "kick_utc": "2026-09-20 17:00:00+00:00", "stadium_id": "MIA00",
        "lead_days": "3.1", "forecast_wind": "14.2", "exp_true_wind": "12.1",
        "total_line": "43.5", "book": "fanduel", "price": "-105",
        "model_prob": "0.5671", "market_prob": "0.5122", "edge": "0.0549",
        "stake_pct": "0.87", "ev_pct": "5.9", "stake_units": "87.0",
    }
    row.update(over)
    return row


def _opener_card_row(**over):
    row = dict(game_id="2026_03_TEN_NYG", matchup="TEN @ NYG",
               kick_utc="2026-09-27 17:00:00+00:00", side="home", bet_team="NYG",
               side_line="-1.0", soft_home_line="-1.0", price="-105",
               model_prob="0.5557", market_prob="0.5122", edge="0.0435",
               dev="2.0", book="betmgm", stake_pct="1.958")
    row.update(over)
    return row


_UNIT_FIGURE = re.compile(r"\d+(?:\.\d+)?u\b")


# ── New labels ───────────────────────────────────────────────────────────────

def test_a_new_wind_label_is_the_bet_only():
    _, picks = build_rows([_wind_card_row()], bankroll=1000.0)
    assert picks[0]["pick_label"] == WIND_BARE
    # The model's sizing is still on the row, where it always was.
    assert picks[0]["kelly_fraction"] == 0.0087


def test_a_new_opener_label_keeps_the_age_and_drops_the_unit_figure():
    cases = (("0.0", OPENER_BARE),
             ("", "TEN @ NYG — NYG -1 · age unknown"),
             ("1500", "TEN @ NYG — NYG -1 · up 25h"))
    for held, want in cases:
        _, picks = build_opener_rows([_opener_card_row(held_min=held)], 1000.0)
        assert picks[0]["pick_label"] == want
        assert not _UNIT_FIGURE.search(picks[0]["pick_label"])
        assert picks[0]["kelly_fraction"] == 0.01958
    # A card written before the age column existed: the bet alone.
    _, picks = build_opener_rows([_opener_card_row()], 1000.0)
    assert picks[0]["pick_label"] == "TEN @ NYG — NYG -1"


def test_a_new_label_reads_like_every_other_sports_label():
    """No other model writes a unit figure into pick_label (production,
    2026-11-04: the 61 labels with one are all nfl_wind_totals and
    nfl_opener_spread BETs)."""
    _, wind = build_rows([_wind_card_row()], bankroll=1000.0)
    _, opener = build_opener_rows([_opener_card_row(held_min="0.0")], 1000.0)
    for p in wind + opener:
        assert not _UNIT_FIGURE.search(p["pick_label"]), p["pick_label"]


# ── Every reader handles all three generations ───────────────────────────────

def test_the_line_check_passes_on_every_generation():
    for label in (OPENER_ANNOTATED, OPENER_STAKED, OPENER_BARE):
        assert pick_problems(label, "home", -1.0, "nfl_opener_spread",
                             home="NYG", away="TEN") == [], label
        assert pick_problems(label_without_stake(label), "home", -1.0,
                             "nfl_opener_spread", home="NYG", away="TEN") == []
    for label in (WIND_ANNOTATED, WIND_STAKED, WIND_BARE):
        assert pick_problems(label, "under", 43.5, "nfl_wind_totals",
                             home="MIA", away="NYJ") == [], label
        assert pick_problems(label_without_stake(label), "under", 43.5,
                             "nfl_wind_totals", home="MIA", away="NYJ") == []
    # And a wrong line is still refused on the new shape.
    assert pick_problems(OPENER_BARE, "home", -2.0, "nfl_opener_spread",
                         home="NYG", away="TEN")
    assert pick_problems(WIND_BARE, "under", 44.5, "nfl_wind_totals",
                         home="MIA", away="NYJ")


def test_grading_finds_the_book_on_every_generation():
    for label in (OPENER_ANNOTATED, OPENER_STAKED, OPENER_BARE):
        want = "betmgm"
        got = pt._bet_price_and_book("nfl_opener_spread", -105.0, None, None,
                                     label)
        if "(" in label:
            assert got == (-105.0, want)
        else:
            assert got == (-105.0, "draftkings")
        assert pt._bet_price_and_book("nfl_opener_spread", -105.0, -105.0,
                                      want, label) == (-105.0, want)
    assert pt._bet_price_and_book("nfl_wind_totals", -110.0, None, None,
                                  WIND_ANNOTATED) == (-110.0, "fanduel")
    assert pt._bet_price_and_book("nfl_wind_totals", -110.0, -110.0, "fanduel",
                                  WIND_BARE) == (-110.0, "fanduel")


def test_the_old_label_still_names_its_book_on_discord():
    sig = {"model_id": "nfl_opener_spread", "label": OPENER_ANNOTATED,
           "dk_odds": -105.0}
    assert dn.book_for_pick(sig) == "BetMGM"


# ── The display helper ───────────────────────────────────────────────────────

def test_only_the_unit_figure_leaves_an_old_label():
    assert label_without_stake(OPENER_ANNOTATED) == \
        "TEN @ NYG — NYG -1 (Opener +2 vs Pinnacle, MGM) · NEW 0m"
    assert label_without_stake(OPENER_STAKED) == OPENER_BARE
    assert label_without_stake(WIND_ANNOTATED) == "NYJ @ MIA Under 43.5 (Wind 14 mph, FD)"
    assert label_without_stake(WIND_STAKED) == WIND_BARE
    assert label_without_stake(PROD_OPENER) == "DAL @ IND — IND +7.5 · NEW 0m"
    assert label_without_stake(PROD_WIND) == "LA @ WAS Under 47.5"
    assert label_without_stake("TEN @ CIN — CIN -11 · 1.27u · up 12h") == \
        "TEN @ CIN — CIN -11 · up 12h"
    # Either order of the two tags.
    assert label_without_stake("CHI @ ATL — CHI +0.5 · NEW 0m · 0.98u") == \
        "CHI @ ATL — CHI +0.5 · NEW 0m"


def test_a_label_with_no_unit_figure_is_returned_as_stored():
    for label in (OPENER_BARE, WIND_BARE, "Boston Bruins (Regulation)",
                  "NYY ML (F5)", "Aaron Judge Over 0.5 HR",
                  "BOS @ MIL — MIL Team Total Under 115.5",
                  "Duke @ Kansas — First Half Duke +3.5",
                  "Jadarian Price Over 1.5 Rec (FD)",
                  "Islam Makhachev Under 2.5 Rounds"):
        assert label_without_stake(label) == label
    assert label_without_stake(None) == ""
    assert label_without_stake("") == ""


# ── The surfaces that show a label beside the posted stake ──────────────────

def _sig(label, **kw):
    base = {"sport": "NFL", "model_id": "nfl_opener_spread", "label": label,
            "dk_odds": -105.0, "kelly": 0.0196, "home": "NYG", "away": "TEN",
            "commence": None, "posted_at": None, "best_book": None,
            "best_odds": None, "decision_book": "betmgm",
            "decision_odds_raw": -105.0, "side": "home", "line": -1.0,
            "game_date": "2026-09-27"}
    base.update(kw)
    return base


def test_discord_shows_one_unit_number_per_pick():
    for label in (OPENER_ANNOTATED, OPENER_STAKED, OPENER_BARE):
        field = dn._signal_field(_sig(label))
        assert "1.96u" not in field["name"], field["name"]
        assert field["name"].startswith("TEN @ NYG — NYG -1")
        assert field["name"].endswith("· NEW 0m")
        # The posted stake: 1u to win at -105.
        assert "1.05u to win 1u" in field["value"]
        assert len(_UNIT_FIGURE.findall(field["name"] + field["value"])) == 2


def test_the_free_pick_shows_one_unit_number():
    embed = dn._free_pick_embed(_sig(PROD_OPENER, home="IND", away="DAL",
                                     dk_odds=-117.0, decision_odds_raw=-117.0,
                                     decision_book="betrivers", line=-7.5,
                                     side="home"), "2026-11-08")
    name = embed["fields"][0]["name"]
    assert name == "DAL @ IND — IND +7.5 · NEW 0m"
    assert "1.17u to win 1u" in embed["fields"][0]["value"]


def test_x_and_push_drop_the_old_figure():
    tweet = xp.render_pick(_sig(WIND_STAKED, model_id="nfl_wind_totals",
                                home="MIA", away="NYJ", dk_odds=-110.0,
                                decision_book="fanduel",
                                decision_odds_raw=-110.0))
    assert WIND_BARE in tweet and "1.00u" not in tweet
    body = push._summary_body([PROD_OPENER, PROD_WIND])
    assert "0.79u" not in body and "0.87u" not in body
    assert "DAL @ IND — IND +7.5 · NEW 0m" in body and "LA @ WAS Under 47.5" in body


def test_a_void_notice_quotes_the_message_it_voids():
    """The void notice names the pick members were sent, word for word, and
    carries no stake, so it keeps the stored label."""
    field = dn._void_field(_sig(OPENER_STAKED), None)
    assert field["name"] == OPENER_STAKED


# ── The open picks view ──────────────────────────────────────────────────────

def test_open_picks_strips_the_same_token_and_nothing_else():
    sql = (ROOT / "data" / "migrations" / "open_picks_view_2026_11_04.sql"
           ).read_text(encoding="utf-8")
    body = re.search(r"\$view\$(.*?)\$view\$", sql, re.S).group(1)
    code = "\n".join(line.split("--", 1)[0] for line in body.splitlines())
    m = re.search(r"regexp_replace\(p\.pick_label,\s*'([^']+)',\s*'',\s*'g'\)\s+AS pick\b",
                  code)
    assert m, "the pick column is the stored label minus the unit figure"
    # The SQL pattern and the Python helper are the same expression.
    from tracking import pick_integrity
    assert m.group(1) == pick_integrity._STAKE_TOKEN.pattern

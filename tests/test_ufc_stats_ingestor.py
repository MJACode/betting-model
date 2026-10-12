"""
test_ufc_stats_ingestor.py — Pure-function tests for the ufcstats.com parsers.

Uses synthetic HTML fixtures shaped like real ufcstats markup — no network.
If ufcstats changes its markup, these tests localize the fix to the parsers.
"""

import pytest

from data.ingestors.ufc_stats_ingestor import (
    _height_to_inches,
    _mmss_to_sec,
    _of_pair,
    _parse_dob,
    _parse_event_date,
    _reach_to_inches,
    normalize_method,
    parse_event_list,
    parse_event_page,
    parse_fight_page,
    parse_fighter_page,
    rounds_completed,
    slugify_fighter,
)


# ── slugify ───────────────────────────────────────────────────────────────────

def test_slugify_basic():
    assert slugify_fighter("Jon Jones") == "jon-jones"


def test_slugify_accents_and_punctuation():
    assert slugify_fighter("José Aldo Jr.") == "jose-aldo-jr"
    assert slugify_fighter("Khabib Nurmagomedov") == "khabib-nurmagomedov"
    assert slugify_fighter("  Ciryl   Gane ") == "ciryl-gane"


def test_slugify_empty():
    assert slugify_fighter("") == ""
    assert slugify_fighter(None) == ""


# ── method normalization ──────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("KO/TKO Punch", "ko_tko"),
    ("KO/TKO", "ko_tko"),
    ("TKO - Doctor's Stoppage", "ko_tko"),
    ("Submission Rear Naked Choke", "submission"),
    ("Decision - Unanimous", "decision"),
    ("Decision - Split", "decision"),
    ("Decision - Majority", "decision"),
    ("DQ", "dq"),
    ("Overturned", "other"),
    ("Could Not Continue", "other"),
    ("", "other"),
])
def test_normalize_method(raw, expected):
    assert normalize_method(raw) == expected


# ── scalar parsers ────────────────────────────────────────────────────────────

def test_mmss_to_sec():
    assert _mmss_to_sec("3:14") == 194
    assert _mmss_to_sec("5:00") == 300
    assert _mmss_to_sec("0:00") == 0
    assert _mmss_to_sec("--") is None
    assert _mmss_to_sec("") is None


def test_event_date():
    assert _parse_event_date("April 13, 2024") == "2024-04-13"
    assert _parse_event_date("garbage") is None


def test_height_reach_dob():
    assert _height_to_inches("6' 4\"") == 76.0
    assert _height_to_inches("--") is None
    assert _reach_to_inches('76"') == 76.0
    assert _reach_to_inches("--") is None
    assert _parse_dob("Jul 19, 1987") == "1987-07-19"
    assert _parse_dob("--") is None


def test_of_pair():
    assert _of_pair("116 of 199") == (116, 199)
    assert _of_pair("0 of 0") == (0, 0)
    assert _of_pair("---") == (None, None)


# ── rounds_completed (round-total settlement math) ────────────────────────────

def test_rounds_completed_finish():
    # Stoppage at 3:14 of round 1 → 0 + 194/300
    assert rounds_completed(1, 194, 3) == pytest.approx(0.647, abs=1e-3)
    # Stoppage at 2:30 of round 3 → exactly 2.5 (the push point on O/U 2.5)
    assert rounds_completed(3, 150, 3) == 2.5


def test_rounds_completed_distance():
    # Decision in a 3-rounder → exactly 3.0
    assert rounds_completed(3, 300, 3) == 3.0
    # Decision in a 5-rounder → exactly 5.0
    assert rounds_completed(5, 300, 5) == 5.0


def test_rounds_completed_missing():
    assert rounds_completed(None, 100, 3) is None
    assert rounds_completed(2, None, 3) is None


# ── HTML fixtures ─────────────────────────────────────────────────────────────

EVENT_LIST_HTML = """
<table class="b-statistics__table-events"><tbody>
<tr class="b-statistics__table-row">
  <td class="b-statistics__table-col">
    <i class="b-statistics__table-content">
      <a href="http://ufcstats.com/event-details/aaa111bbb222cc33" class="b-link b-link_style_black">UFC 300: Pereira vs. Hill</a>
      <span class="b-statistics__date">April 13, 2024</span>
    </i>
  </td>
  <td class="b-statistics__table-col b-statistics__table-col_style_big-top-padding">Las Vegas, Nevada, USA</td>
</tr>
<tr class="b-statistics__table-row">
  <td class="b-statistics__table-col">
    <i class="b-statistics__table-content">
      <a href="http://ufcstats.com/event-details/dd44ee55ff66aa77" class="b-link b-link_style_black">UFC Fight Night: Allen vs. Curtis</a>
      <span class="b-statistics__date">April 6, 2024</span>
    </i>
  </td>
  <td class="b-statistics__table-col b-statistics__table-col_style_big-top-padding">Las Vegas, Nevada, USA</td>
</tr>
</tbody></table>
"""


def test_parse_event_list():
    events = parse_event_list(EVENT_LIST_HTML)
    assert len(events) == 2
    assert events[0]["event_id"] == "aaa111bbb222cc33"
    assert events[0]["name"] == "UFC 300: Pereira vs. Hill"
    assert events[0]["date"] == "2024-04-13"
    assert events[0]["location"] == "Las Vegas, Nevada, USA"
    assert events[1]["date"] == "2024-04-06"


EVENT_PAGE_HTML = """
<h2 class="b-content__title">
  <span class="b-content__title-highlight">UFC 300: Pereira vs. Hill</span>
</h2>
<ul class="b-list__box-list">
  <li class="b-list__box-list-item"><i class="b-list__box-item-title">Date:</i> April 13, 2024</li>
  <li class="b-list__box-list-item"><i class="b-list__box-item-title">Location:</i> Las Vegas, Nevada, USA</li>
</ul>
<table><tbody>
<tr class="b-fight-details__table-row b-fight-details__table-row__hover js-fight-details-click"
    data-link="http://ufcstats.com/fight-details/f1f1f1f1f1f1f1f1">
  <td class="b-fight-details__table-col">
    <p class="b-fight-details__table-text">
      <a class="b-flag b-flag_style_green" href="#"><i class="b-flag__inner"><i class="b-flag__text">win</i></i></a>
    </p>
  </td>
  <td class="b-fight-details__table-col">
    <p class="b-fight-details__table-text"><a href="http://ufcstats.com/fighter-details/1111111111111111" class="b-link">Alex Pereira</a></p>
    <p class="b-fight-details__table-text"><a href="http://ufcstats.com/fighter-details/2222222222222222" class="b-link">Jamahal Hill</a></p>
  </td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">1</p><p class="b-fight-details__table-text">0</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">11</p><p class="b-fight-details__table-text">7</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">0</p><p class="b-fight-details__table-text">0</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">0</p><p class="b-fight-details__table-text">0</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">Light Heavyweight</p><img src="/belt.png"></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">KO/TKO</p><p class="b-fight-details__table-text">Punch</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">1</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">3:14</p></td>
</tr>
<tr class="b-fight-details__table-row b-fight-details__table-row__hover js-fight-details-click"
    data-link="http://ufcstats.com/fight-details/f2f2f2f2f2f2f2f2">
  <td class="b-fight-details__table-col">
    <p class="b-fight-details__table-text">
      <a class="b-flag b-flag_style_gray" href="#"><i class="b-flag__inner"><i class="b-flag__text">draw</i></i></a>
    </p>
    <p class="b-fight-details__table-text">
      <a class="b-flag b-flag_style_gray" href="#"><i class="b-flag__inner"><i class="b-flag__text">draw</i></i></a>
    </p>
  </td>
  <td class="b-fight-details__table-col">
    <p class="b-fight-details__table-text"><a href="http://ufcstats.com/fighter-details/3333333333333333" class="b-link">Fighter One</a></p>
    <p class="b-fight-details__table-text"><a href="http://ufcstats.com/fighter-details/4444444444444444" class="b-link">Fighter Two</a></p>
  </td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">0</p><p class="b-fight-details__table-text">0</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">88</p><p class="b-fight-details__table-text">92</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">2</p><p class="b-fight-details__table-text">1</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">0</p><p class="b-fight-details__table-text">1</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">Welterweight</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">Decision - Split</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">3</p></td>
  <td class="b-fight-details__table-col"><p class="b-fight-details__table-text">5:00</p></td>
</tr>
</tbody></table>
"""


def test_parse_event_page_metadata():
    ev = parse_event_page(EVENT_PAGE_HTML)
    assert ev["name"] == "UFC 300: Pereira vs. Hill"
    assert ev["date"] == "2024-04-13"
    assert len(ev["fights"]) == 2


def test_parse_event_page_winner_fight():
    fight = parse_event_page(EVENT_PAGE_HTML)["fights"][0]
    assert fight["fight_id"] == "f1f1f1f1f1f1f1f1"
    assert fight["outcome"] == "first_won"
    assert fight["fighter_names"] == ["Alex Pereira", "Jamahal Hill"]
    assert fight["fighter_ids"] == ["1111111111111111", "2222222222222222"]
    assert fight["weight_class"] == "Light Heavyweight"
    assert fight["is_title_fight"] == 1
    assert fight["method_raw"] == "KO/TKO Punch"
    assert fight["end_round"] == 1
    assert fight["end_time_sec"] == 194
    assert fight["kd"] == [1, 0]
    assert fight["sig_landed"] == [11, 7]


def test_parse_event_page_draw_fight():
    fight = parse_event_page(EVENT_PAGE_HTML)["fights"][1]
    assert fight["outcome"] == "draw"
    assert fight["is_title_fight"] == 0
    assert fight["method_raw"] == "Decision - Split"
    assert fight["end_round"] == 3
    assert fight["end_time_sec"] == 300


FIGHT_PAGE_HTML = """
<div class="b-fight-details">
  <div class="b-fight-details__fight-head">
    <i class="b-fight-details__fight-title">UFC Light Heavyweight Title Bout</i>
  </div>
  <div class="b-fight-details__content">
    <p class="b-fight-details__text">
      <i class="b-fight-details__text-item_first"><i class="b-fight-details__label">Method:</i> KO/TKO</i>
      <i class="b-fight-details__text-item"><i class="b-fight-details__label">Round:</i> 1</i>
      <i class="b-fight-details__text-item"><i class="b-fight-details__label">Time:</i> 3:14</i>
      <i class="b-fight-details__text-item"><i class="b-fight-details__label">Time format:</i> 5 Rnd (5-5-5-5-5)</i>
      <i class="b-fight-details__text-item"><i class="b-fight-details__label">Referee:</i> Herb Dean</i>
    </p>
  </div>
  <section class="b-fight-details__section js-fight-section">
    <table>
      <thead><tr><th>Fighter</th><th>KD</th><th>Sig. str.</th><th>Sig. str. %</th><th>Total str.</th><th>Td</th><th>Td %</th><th>Sub. att</th><th>Rev.</th><th>Ctrl</th></tr></thead>
      <tbody><tr>
        <td><p>Alex Pereira</p><p>Jamahal Hill</p></td>
        <td><p>1</p><p>0</p></td>
        <td><p>11 of 14</p><p>7 of 15</p></td>
        <td><p>78%</p><p>46%</p></td>
        <td><p>13 of 16</p><p>9 of 17</p></td>
        <td><p>0 of 0</p><p>0 of 1</p></td>
        <td><p>---</p><p>0%</p></td>
        <td><p>0</p><p>0</p></td>
        <td><p>0</p><p>0</p></td>
        <td><p>0:09</p><p>0:00</p></td>
      </tr></tbody>
    </table>
  </section>
</div>
"""


def test_parse_fight_page():
    detail = parse_fight_page(FIGHT_PAGE_HTML)
    assert detail["is_title_fight"] == 1
    assert detail["scheduled_rounds"] == 5
    assert detail["method_raw"] == "KO/TKO"
    assert detail["end_round"] == 1
    assert detail["end_time_sec"] == 194
    totals = detail["totals"]
    assert totals["kd"] == [1, 0]
    assert totals["sig_landed"] == [11, 7]
    assert totals["sig_attempted"] == [14, 15]
    assert totals["total_landed"] == [13, 9]
    assert totals["td_landed"] == [0, 0]
    assert totals["td_attempted"] == [0, 1]
    assert totals["sub_attempts"] == [0, 0]
    assert totals["control_sec"] == [9, 0]


FIGHTER_PAGE_HTML = """
<h2 class="b-content__title">
  <span class="b-content__title-highlight">Alex Pereira</span>
</h2>
<ul class="b-list__box-list">
  <li class="b-list__box-list-item b-list__box-list-item_type_block">
    <i class="b-list__box-item-title b-list__box-item-title_type_width">Height:</i> 6' 4"
  </li>
  <li class="b-list__box-list-item b-list__box-list-item_type_block">
    <i class="b-list__box-item-title b-list__box-item-title_type_width">Weight:</i> 205 lbs.
  </li>
  <li class="b-list__box-list-item b-list__box-list-item_type_block">
    <i class="b-list__box-item-title b-list__box-item-title_type_width">Reach:</i> 79"
  </li>
  <li class="b-list__box-list-item b-list__box-list-item_type_block">
    <i class="b-list__box-item-title b-list__box-item-title_type_width">STANCE:</i> Orthodox
  </li>
  <li class="b-list__box-list-item b-list__box-list-item_type_block">
    <i class="b-list__box-item-title b-list__box-item-title_type_width">DOB:</i> Jul 7, 1987
  </li>
</ul>
"""


def test_parse_fighter_page():
    profile = parse_fighter_page(FIGHTER_PAGE_HTML)
    assert profile["name"] == "Alex Pereira"
    assert profile["height_in"] == 76.0
    assert profile["reach_in"] == 79.0
    assert profile["stance"] == "Orthodox"
    assert profile["dob"] == "1987-07-07"


def test_parse_fighter_page_missing_fields():
    html = """
    <span class="b-content__title-highlight">Debut Fighter</span>
    <li class="b-list__box-list-item"><i class="b-list__box-item-title">Height:</i> --</li>
    <li class="b-list__box-list-item"><i class="b-list__box-item-title">Reach:</i> --</li>
    """
    profile = parse_fighter_page(html)
    assert profile["name"] == "Debut Fighter"
    assert profile["height_in"] is None
    assert profile["reach_in"] is None


# ── Name variants: aliases + the anchor-rule fallback ─────────────────────────
# The Odds API and ufcstats spell some fighters differently. Unmapped, the two
# sources slugify apart, the odds feed's `games` row never receives a score,
# and every pick on it is stuck unsettled forever (the Ian Garry case).

def test_alias_makes_both_sources_agree():
    """An alias must collapse the two spellings onto ONE slug — that's what
    makes odds and ufcstats build the same game_id, so no duplicate row."""
    assert slugify_fighter("Ian Garry") == slugify_fighter("Ian Machado Garry")
    assert slugify_fighter("Ian Garry") == "ian-machado-garry"


@pytest.mark.parametrize("odds_name,ufcstats_name", [
    ("Ian Garry", "Ian Machado Garry"),
    ("Sergey Spivak", "Serghei Spivac"),
    ("Billy Goff", "Billy Ray Goff"),
    ("Carlos Diego Ferreira", "Diego Ferreira"),
    ("Giovanna Canuto", "Gigi Canuto"),
    ("Yadier DelValle", "Yadier del Valle"),
    ("L'udovit Klein", "Ludovit Klein"),
    ("Seok Hyun Ko", "Seokhyeon Ko"),
    ("Asu Almabaev", "Asu Almabayev"),
    ("Abdulrakhman Yakhyaev", "Abdul Rakhman Yakhyaev"),
    ("Abusupyian Magomedov", "Abus Magomedov"),
    ("Beatriz Mesquita", "Bia Mesquita"),
    ("Nursultan Ruziboev", "Nursulton Ruziboev"),
    ("Javier Reyes Rugeles", "Javier Reyes"),
    ("Steve Garcia Jr.", "Steve Garcia"),
])
def test_confirmed_aliases_resolve_to_ufcstats_slug(odds_name, ufcstats_name):
    assert slugify_fighter(odds_name) == slugify_fighter(ufcstats_name)


def test_aliases_do_not_touch_unmapped_names():
    """The alias table must never rewrite a name it doesn't know."""
    assert slugify_fighter("Islam Makhachev") == "islam-makhachev"
    assert slugify_fighter("Charles Johnson") == "charles-johnson"


class _FakeConn:
    """Minimal DBConnection stand-in: one canned games result set."""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        self._last = (sql, params)
        return self

    def fetchall(self):
        return self._rows


def _resolve(rows, slug_a, slug_b, date="2026-08-15"):
    from data.ingestors.ufc_stats_ingestor import _resolve_game_rows
    return _resolve_game_rows(_FakeConn(rows), date, slug_a, slug_b)


def test_resolve_exact_pair_wins():
    rows = [("UFC_2026-08-15_a_b", "Islam Makhachev", "Ian Machado Garry")]
    got = _resolve(rows, "islam-makhachev", "ian-machado-garry")
    assert [g[0] for g in got] == ["UFC_2026-08-15_a_b"]


def test_resolve_returns_every_duplicate_orientation():
    """Picks can sit on swapped/duplicated rows; all need scores."""
    rows = [
        ("UFC_2026-08-15_x_y", "Islam Makhachev", "Ian Machado Garry"),
        ("UFC_2026-08-15_y_x", "Ian Machado Garry", "Islam Makhachev"),
    ]
    got = _resolve(rows, "islam-makhachev", "ian-machado-garry")
    assert len(got) == 2


def test_resolve_anchor_rescues_unmapped_variant():
    """One fighter matching on the same date identifies the bout — this is the
    safety net for a name variant nobody has aliased yet."""
    rows = [("UFC_2026-08-15_odds", "Islam Makhachev", "Ian Garry")]
    got = _resolve(rows, "islam-makhachev", "ian-machado-garry")
    assert [g[0] for g in got] == ["UFC_2026-08-15_odds"]


def test_resolve_anchor_declines_when_opponent_changed():
    """Charles Johnson was listed vs Ochoa AND vs Henrique but fought Chapolin.
    Two rows share a fighter → the matchup changed. A replaced opponent is a
    DIFFERENT proposition, so this must NOT auto-resolve."""
    rows = [
        ("UFC_2026-08-15_ochoa", "Charles Johnson", "Jose Ochoa"),
        ("UFC_2026-08-15_henrique", "Charles Johnson", "Eduardo Henrique"),
    ]
    got = _resolve(rows, "charles-johnson", "eduardo-chapolin")
    assert got == []


def test_resolve_ignores_unrelated_fights():
    rows = [("UFC_2026-08-15_other", "Neil Magny", "Ramiz Brahimaj")]
    assert _resolve(rows, "islam-makhachev", "ian-machado-garry") == []


def test_resolve_anchor_returns_a_fight_stored_twice_but_not_beside_a_changed_opponent():
    """The odds feed stored one fight twice, home/away swapped, under a
    spelling ufcstats does not use (Pereira vs Zheleznyakova, 2026-10-10:
    ufcstats spells her Daria Zhelezniakova). Both rows are the SAME two
    fighters, so this is not a changed matchup: every row is returned and
    each is scored in its own orientation. Declining here left both odds rows
    unscored and created a third, ufcstats-only row instead.

    The rule is "every row is the same two fighters", not "several rows":
    the same duplicate pair beside a row naming a different opponent is
    still ambiguous and still declines."""
    rows = [
        ("UFC_2026-10-10_alice-pereira_darya-zheleznyakova",
         "Darya Zheleznyakova", "Alice Pereira"),
        ("UFC_2026-10-10_darya-zheleznyakova_alice-pereira",
         "Alice Pereira", "Darya Zheleznyakova"),
    ]
    got = _resolve(rows, "alice-pereira", "daria-zhelezniakova", date="2026-10-10")
    assert sorted(g[0] for g in got) == sorted(r[0] for r in rows)

    rows_with_a_changed_opponent = rows + [
        ("UFC_2026-10-10_alice-pereira_tracy-cortez",
         "Tracy Cortez", "Alice Pereira"),
    ]
    assert _resolve(rows_with_a_changed_opponent, "alice-pereira",
                    "daria-zhelezniakova", date="2026-10-10") == []


def _warnings_while(fn):
    """Run fn() and return (its result, every WARNING message logged)."""
    from loguru import logger
    messages = []
    sink = logger.add(lambda m: messages.append(str(m)), level="WARNING")
    try:
        return fn(), messages
    finally:
        logger.remove(sink)


@pytest.mark.parametrize("rows", [
    # booked once: the odds feed has only the original matchup
    [("UFC_2026-08-15_charles-johnson_jose-ochoa", "Jose Ochoa", "Charles Johnson")],
    # booked twice, home/away swapped — the same two fighters on both rows
    [("UFC_2026-08-15_charles-johnson_jose-ochoa", "Jose Ochoa", "Charles Johnson"),
     ("UFC_2026-08-15_jose-ochoa_charles-johnson", "Charles Johnson", "Jose Ochoa")],
], ids=["one row", "stored twice"])
def test_resolve_anchor_refuses_a_late_replacement(rows):
    """Charles Johnson was booked against Jose Ochoa and fought Eduardo
    Chapolin. If the odds feed only ever listed the Ochoa booking, every row
    shares exactly one fighter (Johnson) with the result, and every row is
    the same two fighters — so "same pair on every row" alone accepts it, and
    a moneyline pick on Ochoa would be graded on the Chapolin fight (a
    sportsbook voids that bet). Ochoa does not resemble Chapolin, so this is
    a different fight: nothing is matched, and the refusal is logged."""
    got, warnings = _warnings_while(
        lambda: _resolve(rows, "charles-johnson", "eduardo-chapolin"))
    assert got == []
    refusals = [m for m in warnings if "does not resemble" in m]
    assert len(refusals) == 1, warnings
    assert "jose-ochoa" in refusals[0] and "eduardo-chapolin" in refusals[0]


# Every name-variant match the results ingest has met since 2025-01-01: a
# read-only replay of every ufcstats fight in ufc_fight_log from 2025-01-01 to
# 2026-10-10 against the odds-feed games rows within a day of it. The odds
# feed's games rows start on 2026-06-13, so all of them are from then on. Each
# row is as stored (both orientations where the fight was stored twice). The
# feed's spelling and the ufcstats spelling of the misspelled fighter differ
# in every one of these; each must still be matched.
_GENUINE_NAME_VARIANTS = [
    # (ufcstats winner, ufcstats loser, date, odds-feed rows: (game_id, home, away))
    ("Kai Asakura", "Aoriqileng", "2026-08-29", [
        ("UFC_2026-08-29_aori-qileng_kai-asakura", "Kai Asakura", "Aori Qileng"),
        ("UFC_2026-08-29_kai-asakura_aori-qileng", "Aori Qileng", "Kai Asakura"),
    ]),
    ("Sumudaerji", "Alex Perez", "2026-08-29", [
        ("UFC_2026-08-29_alex-perez_su-mudaerji", "Su Mudaerji", "Alex Perez"),
        ("UFC_2026-08-29_su-mudaerji_alex-perez", "Alex Perez", "Su Mudaerji"),
    ]),
    ("Julia Polastri", "Xiong Jingnan", "2026-08-29", [
        ("UFC_2026-08-29_jingnan-xiong_julia-polastri", "Julia Polastri", "Jingnan Xiong"),
        ("UFC_2026-08-29_julia-polastri_jingnan-xiong", "Jingnan Xiong", "Julia Polastri"),
    ]),
    ("Losene Keita", "Muhammad Naimov", "2026-09-05", [
        ("UFC_2026-09-05_losene-keita_muhammadjon-naimov", "Muhammadjon Naimov", "Losene Keita"),
        ("UFC_2026-09-05_muhammadjon-naimov_losene-keita", "Losene Keita", "Muhammadjon Naimov"),
    ]),
    ("Nora Cornolle", "Klaudia Sygula", "2026-09-05", [
        ("UFC_2026-09-05_klaudia-sygu-a_nora-cornolle", "Nora Cornolle", "Klaudia Syguła"),
        ("UFC_2026-09-05_nora-cornolle_klaudia-sygu-a", "Klaudia Syguła", "Nora Cornolle"),
    ]),
    ("Tommy Gantt", "Drakkar Klose", "2026-09-12", [
        ("UFC_2026-09-12_drakkar-klose_thomas-gantt", "Thomas Gantt", "Drakkar Klose"),
        ("UFC_2026-09-12_thomas-gantt_drakkar-klose", "Drakkar Klose", "Thomas Gantt"),
    ]),
    ("Rongzhu", "Rafa Garcia", "2026-09-12", [
        ("UFC_2026-09-12_zhu-rong_rafa-garcia", "Rafa Garcia", "Zhu Rong"),
    ]),
    ("Elves Brener", "Josiah Harrell", "2026-09-26", [
        ("UFC_2026-09-26_elves-brenner_josiah-harrell", "Josiah Harrell", "Elves Brenner"),
    ]),
    ("Alatengheili", "John Castaneda", "2026-09-26", [
        ("UFC_2026-09-26_heili-alateng_john-castaneda", "John Castaneda", "Heili Alateng"),
        ("UFC_2026-09-26_john-castaneda_heili-alateng", "Heili Alateng", "John Castaneda"),
    ]),
    ("Alexander Hernandez", "Rafael Dos Anjos", "2026-10-03", [
        ("UFC_2026-10-03_alex-hernandez_rafael-dos-anjos", "Rafael dos Anjos", "Alex Hernandez"),
    ]),
    ("Johnny Walker", "Mick Parkin", "2026-10-03", [
        ("UFC_2026-10-03_michael-parkin_johnny-walker", "Johnny Walker", "Michael Parkin"),
    ]),
    ("Alice Pereira", "Daria Zhelezniakova", "2026-10-10", [
        ("UFC_2026-10-10_alice-pereira_darya-zheleznyakova", "Darya Zheleznyakova", "Alice Pereira"),
        ("UFC_2026-10-10_darya-zheleznyakova_alice-pereira", "Alice Pereira", "Darya Zheleznyakova"),
    ]),
    ("Loopy Godinez", "Ketlen Souza", "2026-10-10", [
        ("UFC_2026-10-10_ketlen-souza_lupita-godinez", "Lupita Godinez", "Ketlen Souza"),
    ]),
]


@pytest.mark.parametrize("winner,loser,date,rows", _GENUINE_NAME_VARIANTS,
                         ids=[f"{w} v {l}" for w, l, _d, _r in _GENUINE_NAME_VARIANTS])
def test_resolve_anchor_matches_every_real_name_variant(winner, loser, date, rows):
    got = _resolve(rows, slugify_fighter(winner), slugify_fighter(loser), date=date)
    assert sorted(g[0] for g in got) == sorted(r[0] for r in rows)


# The same replay found these fights where the odds feed ALSO kept a row for
# an opponent the fighter did not end up facing (a changed booking). Each
# fight was matched through its correct row, which the feed had too. Had the
# feed never listed the real matchup, the stale row would be the only one
# sharing a fighter — and "same pair on every row" alone accepted every one of
# them. None of the stale opponents resembles the real one.
_STALE_BOOKINGS = [
    # (ufcstats winner, ufcstats loser, date, the stale odds-feed rows)
    ("Farid Basharat", "John Garza", "2026-07-11", [
        ("UFC_2026-07-11_ethyn-ewing_farid-basharat", "Farid Basharat", "Ethyn Ewing"),
    ]),
    ("Magomed Ankalaev", "Bogdan Guskov", "2026-07-25", [
        ("UFC_2026-07-25_khalil-rountree_magomed-ankalaev", "Magomed Ankalaev", "Khalil Rountree"),
    ]),
    ("Borislav Nikolic", "Mark Vologdin", "2026-08-01", [
        ("UFC_2026-08-01_josias-musasa_mark-vologdin", "Mark Vologdin", "Josias Musasa"),
    ]),
    ("Miles Johns", "Gianni Vazquez", "2026-08-08", [
        ("UFC_2026-08-08_jessie-rosas_miles-johns", "Miles Johns", "Jessie Rosas"),
        ("UFC_2026-08-08_miles-johns_jessie-rosas", "Jessie Rosas", "Miles Johns"),
    ]),
    ("Pavel Andrusca", "Nathaniel Wood", "2026-09-05", [
        ("UFC_2026-09-05_mairon-santos_nathaniel-wood", "Nathaniel Wood", "Mairon Santos"),
    ]),
    ("Jean Silva", "Jose Delgado", "2026-09-12", [
        ("UFC_2026-09-12_jean-silva_yair-rodriguez", "Yair Rodriguez", "Jean Silva"),
        ("UFC_2026-09-12_yair-rodriguez_jean-silva", "Jean Silva", "Yair Rodriguez"),
    ]),
    ("Luis Hernandez", "Sedriques Dumas", "2026-09-26", [
        ("UFC_2026-09-26_mickey-gall_sedriques-dumas", "Sedriques Dumas", "Mickey Gall"),
        ("UFC_2026-09-26_sedriques-dumas_mickey-gall", "Mickey Gall", "Sedriques Dumas"),
    ]),
    ("Marcus McGhee", "Anthony Romero", "2026-10-03", [
        ("UFC_2026-10-03_benardo-sopaj_marcus-mcghee", "Marcus McGhee", "Benardo Sopaj"),
    ]),
    ("Natalia Silva", "Wang Cong", "2026-10-03", [
        ("UFC_2026-10-03_natalia-silva_valentina-shevchenko", "Valentina Shevchenko", "Natalia Silva"),
    ]),
]


@pytest.mark.parametrize("winner,loser,date,rows", _STALE_BOOKINGS,
                         ids=[f"{w} v {l}" for w, l, _d, _r in _STALE_BOOKINGS])
def test_resolve_anchor_refuses_every_real_stale_booking_on_its_own(winner, loser, date, rows):
    assert _resolve(rows, slugify_fighter(winner), slugify_fighter(loser), date=date) == []


# ── Scoring a matched row: which side won ─────────────────────────────────────
# The results ingest writes home_score/away_score/home_win onto each matched
# games row. Settlement grades UFC moneyline picks from games.home_win, so a
# wrong side here grades a winning pick as a loss.

class _IngestConn:
    """DBConnection stand-in for _ingest_event: serves the games rows near the
    event date, reports no existing fight-log rows, and records every score
    written to games."""

    def __init__(self, games_rows):
        self._games_rows = games_rows
        self._result = []
        self.scores = []          # (home_score, away_score, home_win, game_id)
        self.inserted_games = []

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if text.startswith("SELECT game_id, home_team, away_team FROM games"):
            self._result = list(self._games_rows)
        elif text.startswith("UPDATE games"):
            self.scores.append(tuple(params))
            self._result = []
        elif text.startswith("INSERT INTO games"):
            self.inserted_games.append(tuple(params))
            self._result = []
        elif text.startswith("SELECT COUNT(*)"):
            self._result = [(0,)]
        else:                     # fight-log lookups and upserts, fighter upserts
            self._result = []
        return self

    def fetchall(self):
        return self._result

    def fetchone(self):
        return self._result[0] if self._result else None

    def commit(self):
        pass


def _one_fight_event(winner, loser, date, outcome="first_won"):
    """A parse_event_page-shaped event with one fight; winner listed first."""
    return {
        "name": "UFC Fight Night",
        "date": date,
        "fights": [{
            "fight_id": "f0f0f0f0f0f0f0f0",
            "fighter_ids": ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"],
            "fighter_names": [winner, loser],
            "outcome": outcome,
            "weight_class": "Flyweight",
            "is_title_fight": 0,
            "method_raw": "Decision - Unanimous",
            "end_round": 3,
            "end_time_sec": 300,
            "kd": [0, 0],
            "sig_landed": [40, 30],
            "td_landed": [1, 0],
            "sub_attempts": [0, 0],
        }],
    }


def _ingest(games_rows, winner, loser, date, outcome="first_won"):
    from data.ingestors.ufc_stats_ingestor import _ingest_event
    conn = _IngestConn(games_rows)
    _ingest_event(conn, "evt", ev=_one_fight_event(winner, loser, date, outcome),
                  detail_lookup=lambda _fight_id: {}, force=True)
    return conn


def test_a_misspelled_fighter_is_scored_for_the_side_they_fought_on():
    """Godinez vs Souza, 2026-10-10: the odds feed has 'Lupita Godinez' at
    home, ufcstats has 'Loopy Godinez', and she won. Her row is matched by
    the anchor rule (Souza is spelled the same in both). Comparing only the
    winner's name with the home name credited Souza (home_win=0); checking
    the loser's name too places the win at home.

    Every combination of side and result is checked, plus both orientations
    of a correctly spelled row, so the fix for the one broken case cannot
    break the others: (home name, away name, winner, loser, expected scores).
    """
    cases = [
        # misspelled fighter at home, wins: the case that was scored backwards
        ("Lupita Godinez", "Ketlen Souza", "Loopy Godinez", "Ketlen Souza", (1, 0, 1)),
        # misspelled fighter at home, loses
        ("Lupita Godinez", "Ketlen Souza", "Ketlen Souza", "Loopy Godinez", (0, 1, 0)),
        # misspelled fighter away, wins
        ("Ketlen Souza", "Lupita Godinez", "Loopy Godinez", "Ketlen Souza", (0, 1, 0)),
        # misspelled fighter away, loses
        ("Ketlen Souza", "Lupita Godinez", "Ketlen Souza", "Loopy Godinez", (1, 0, 1)),
        # both spelled alike in both sources: unchanged, either orientation
        ("Islam Makhachev", "Ian Machado Garry", "Ian Machado Garry", "Islam Makhachev", (0, 1, 0)),
        ("Ian Machado Garry", "Islam Makhachev", "Ian Machado Garry", "Islam Makhachev", (1, 0, 1)),
    ]
    got = []
    for home, away, winner, loser, _expected in cases:
        gid = f"UFC_2026-10-10_{slugify_fighter(away)}_{slugify_fighter(home)}"
        conn = _ingest([(gid, home, away)], winner=winner, loser=loser,
                       date="2026-10-10")
        assert conn.inserted_games == []      # matched the odds row, made none
        got.append(conn.scores)
    assert got == [
        [(*expected, f"UFC_2026-10-10_{slugify_fighter(away)}_{slugify_fighter(home)}")]
        for home, away, _w, _l, expected in cases
    ]


def test_the_same_fight_stored_twice_is_scored_on_both_rows_each_way_round():
    """Pereira beat Zheleznyakova (ufcstats: Daria Zhelezniakova); the odds
    feed stored the fight twice, home/away swapped. Both rows are scored, each
    with its own orientation (Pereira at home wins, Pereira away wins) and
    no third row is created."""
    away_pereira = "UFC_2026-10-10_alice-pereira_darya-zheleznyakova"
    home_pereira = "UFC_2026-10-10_darya-zheleznyakova_alice-pereira"
    conn = _ingest([
        (away_pereira, "Darya Zheleznyakova", "Alice Pereira"),
        (home_pereira, "Alice Pereira", "Darya Zheleznyakova"),
    ], winner="Alice Pereira", loser="Daria Zhelezniakova", date="2026-10-10")
    assert conn.inserted_games == []
    assert sorted(conn.scores, key=lambda s: s[3]) == [
        (0, 1, 0, away_pereira),
        (1, 0, 1, home_pereira),
    ]


def test_a_row_naming_neither_fighter_is_left_unscored(monkeypatch):
    """If a matched row names neither fighter the way ufcstats does, nothing
    says which side won. The old rule scored it as an away win by default;
    it must be left unscored (and logged) rather than guessed. The resolver
    never produces such a row today, so it is injected here directly."""
    import data.ingestors.ufc_stats_ingestor as ingestor
    gid = "UFC_2026-10-10_ketlyn-sousa_lupita-godinez"
    monkeypatch.setattr(ingestor, "_resolve_game_rows",
                        lambda *_a, **_k: [(gid, "Lupita Godinez", "Ketlyn Sousa")])
    conn = _ingest([], winner="Loopy Godinez", loser="Ketlen Souza",
                   date="2026-10-10")
    assert conn.inserted_games == []
    assert conn.scores == []


def test_a_late_replacement_is_not_scored_on_the_original_booking():
    """End to end: the odds feed has Johnson v Ochoa stored twice; ufcstats
    has Johnson beating Chapolin. Neither Ochoa row may receive a score
    (that would grade an Ochoa pick on someone else's fight); the result goes
    on a new ufcstats-only row instead, as it did before name variants were
    matched at all."""
    ochoa_home = "UFC_2026-08-15_charles-johnson_jose-ochoa"
    ochoa_away = "UFC_2026-08-15_jose-ochoa_charles-johnson"
    conn = _ingest([
        (ochoa_home, "Jose Ochoa", "Charles Johnson"),
        (ochoa_away, "Charles Johnson", "Jose Ochoa"),
    ], winner="Charles Johnson", loser="Eduardo Chapolin", date="2026-08-15")
    scored = {s[3] for s in conn.scores}
    assert ochoa_home not in scored and ochoa_away not in scored
    assert [g[0] for g in conn.inserted_games] == [
        "UFC_2026-08-15_eduardo-chapolin_charles-johnson"]
    assert scored == {"UFC_2026-08-15_eduardo-chapolin_charles-johnson"}

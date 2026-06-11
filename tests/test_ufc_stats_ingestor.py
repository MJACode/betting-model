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

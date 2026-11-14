"""TennisExplorer's results page: two rows a match, the header above them,
the level from the tournament's name. The fixture is a copy of the markup read
on 2026-11-12 (Stockholm) and 2025-08-31 (an unlinked ITF header)."""
from data.ingestors import tennis_explorer as te

PAGE = """
<table class="result" cellspacing="0"><tbody>
<tr class="head flags">
  <td class="t-name" colspan="2"><a href="/stockholm/2026/atp-men/"><span class="fl fl-se">&nbsp;</span><span class="type-men2">&nbsp;</span>Stockholm</a></td>
  <td class="score">S</td><td class="course">H</td><td class="course">A</td>
</tr>
<tr id="r10" class="one fRow bott">
  <td class="first time" rowspan="2">20:30</td>
  <td class="t-name"><a href="/player/musetti/">Musetti L.</a> (3)</td>
  <td class="result">2</td>
  <td class="score">7</td><td class="score">3</td><td class="score">6</td><td class="score">&nbsp;</td><td class="score">&nbsp;</td>
  <td class="coursew" rowspan="2">1.48</td><td class="course" rowspan="2">2.62</td>
  <td class="alone-icons" rowspan="2">&nbsp;</td>
  <td rowspan="2"><a href="/match-detail/?id=3377083" title="Click for match detail">info</a></td>
</tr>
<tr id="r10b" class="one">
  <td class="t-name"><a href="/player/humbert-e2553/">Humbert U.</a> (7)</td>
  <td class="result">1</td>
  <td class="score">6<sup>5</sup></td><td class="score">6</td><td class="score">4</td><td class="score">&nbsp;</td><td class="score">&nbsp;</td>
</tr>
<tr class="head flags">
  <td class="t-name" colspan="2"><span class="fl fl-all">&nbsp;</span><span class="type-men2">&nbsp;</span>Futures 2025</td>
  <td class="score">S</td>
</tr>
<tr id="r11" class="two bott">
  <td class="first time" rowspan="2">10:00</td>
  <td class="t-name"><a href="/player/doe-1/">Doe J.</a></td>
  <td class="result">1</td>
  <td class="score">6</td><td class="score">2</td><td class="score">&nbsp;</td>
  <td class="course" rowspan="2">&nbsp;</td><td class="course" rowspan="2">&nbsp;</td>
  <td rowspan="2"><a href="/match-detail/?id=999" title="Click for match detail">info</a></td>
</tr>
<tr id="r11b" class="two">
  <td class="t-name"><a href="/player/roe-2/">Roe K.</a></td>
  <td class="result">0</td>
  <td class="score">3</td><td class="score">0</td><td class="score">&nbsp;</td>
</tr>
</tbody></table>
"""


def test_two_rows_make_one_match_with_its_header_tiebreak_and_prices():
    ms = te.parse_results_page(PAGE)
    assert len(ms) == 2
    m = ms[0]
    assert (m.tournament, m.tournament_path, m.match_id) == ("Stockholm", "/stockholm/2026/atp-men/", "3377083")
    assert (m.p1_slug, m.p2_slug) == ("/player/musetti/", "/player/humbert-e2553/")
    assert m.p1_games == [7, 3, 6] and m.p2_games == [6, 6, 4]
    assert m.p2_tiebreaks == [5, None, None]
    assert (m.p1_price, m.p2_price, m.winner_marked) == (1.48, 2.62, 1)


def test_an_unlinked_itf_header_and_an_unpriced_retirement():
    m = te.parse_results_page(PAGE)[1]
    assert m.tournament == "Futures 2025" and m.tournament_path is None
    assert te.level_of(m.tournament, m.tournament_path) == "itf"
    assert (m.p1_sets, m.p2_sets) == (1, 0) and m.p1_games == [6, 2]   # stopped in set two
    assert m.p1_price is None and m.p2_price is None


def test_levels_from_names_and_paths():
    assert te.level_of("Bytom ITF", "/bytom-itf/2025/wta-women/") == "itf"
    assert te.level_of("Changsha WTA", "/changsha-wta/2025/wta-women/") == "125"
    assert te.level_of("Como challenger", "/como-challenger/2025/atp-men/") == "challenger"
    assert te.level_of("UTR Pro Tennis Series 3", "/utr-pro-tennis-series-3/2025/atp-men/") == "other"
    assert te.level_of("Austrian Bundesliga", "/austrian-bundesliga/2025/atp-men/") == "other"
    assert te.level_of("US Open", "/us-open/2025/atp-men/") == "tour"


def test_rows_for_drops_other_levels():
    page = PAGE.replace("Stockholm</a>", "UTR Pro Tennis Series 3</a>").replace(
        "/stockholm/2026/atp-men/", "/utr-pro-tennis-series-3/2026/atp-men/")
    from datetime import date
    rows = te.rows_for(page, "atp-single", date(2025, 8, 31))
    assert [r[3] for r in rows] == ["itf"]

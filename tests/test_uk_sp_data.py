"""The UK and Ireland starting-price loader: the year filter, the SP strings and the
each-way terms. No data files: the CSV is written into a temp folder.

scripts/horse/uk_sp_data.py feeds docs/horse_racing_market_audit.md section 8. A wrong SP
parse or wrong each-way terms would change every table there, so these are pinned.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.horse import uk_sp_data as uk


def _row(date, race_id, horse, pos, sp):
    vals = dict.fromkeys(uk.HEADER, "")
    vals.update(date=date, course="Ascot", race_id=race_id, off="2:05", race_name="Maiden",
                type="Flat", ran="2", pos=pos, horse=horse, age="3", sp=sp,
                jockey="A Rider", trainer="B Trainer", sire="S", dam="D")
    return ",".join(vals[c] for c in uk.HEADER)


def test_the_year_filter_works_on_a_file_that_repeats_its_header(tmp_path, monkeypatch):
    # 1988-2004.csv repeats its header inside the file. The dropped header rows left
    # "date" as a category, and the year filter raised int("date") before this was fixed.
    lines = [",".join(uk.HEADER),
             _row("2003-06-01", "1", "Alpha", "1", "2/1"),
             ",".join(uk.HEADER),
             _row("2004-06-01", "2", "Beta", "1", "Evens")]
    (tmp_path / "old.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(uk, "FILES", {"1988-2004": ("old.csv", 1988, 2004)})
    out = uk.read_raw(years=[2004], root=tmp_path)
    assert out["date"].astype(str).tolist() == ["2004-06-01"]
    assert not any(c in set(out[c].astype(str)) for c in out.columns if c != "file")


def test_starting_prices_parse_to_decimal_odds_and_the_favourite_marker_comes_off():
    dec, mark, stat, lad = uk.parse_sp(pd.Series(["2/1", "EvensF", "Evs", "100/30", "10/3J",
                                                  "16/5", "", "F"]))
    assert dec[:6].tolist() == pytest.approx([3.0, 2.0, 2.0, 13 / 3, 13 / 3, 4.2])
    assert list(mark[:6]) == ["", "F", "", "", "J", ""]
    assert list(stat) == ["ok"] * 6 + ["missing", "unparsed"]
    assert np.isnan(dec[6]) and np.isnan(dec[7])
    assert bool(lad[3]) and not bool(lad[5])          # 100/30 is on the SP ladder, 16/5 is not


@pytest.mark.parametrize("ran, handicap, places, frac", [
    (4, False, 1, 0.0), (5, False, 2, 0.25), (7, True, 2, 0.25), (8, False, 3, 0.2),
    (15, False, 3, 0.2), (12, True, 3, 0.25), (16, True, 4, 0.25), (16, False, 3, 0.2)])
def test_each_way_terms_follow_the_field_size_and_handicap(ran, handicap, places, frac):
    p, f = uk.place_terms([ran], [handicap])
    assert (int(p[0]), float(f[0])) == (places, frac)


def test_a_dead_heat_for_the_last_place_pays_half():
    # 3 places paid; two horses dead-heat for 3rd, the 5th horse gets nothing
    share = uk.position_share([1, 2, 3, 3, 5], [1, 1, 2, 2, 1], [3] * 5)
    assert share.tolist() == pytest.approx([1.0, 1.0, 0.5, 0.5, 0.0])

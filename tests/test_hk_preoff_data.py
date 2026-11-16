"""The Hong Kong pre-race pool loader: the clock, the snapshot a decision may
use, and the grading. No network and no data files (the snapshots are faked).

scripts/horse/hk_preoff_data.py feeds docs/horse_racing_market_audit.md §7.
A wrong clock or a snapshot from after the lead would turn every table there
into hindsight, so these are pinned.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.horse import hk_preoff_data as hk


def test_capture_time_is_utc_and_the_start_is_hong_kong_time():
    # Measured on the files (audit §7): with +8 h the pools freeze after the
    # listed start in every race; with any other whole hour they do not.
    assert hk.CAPTURE_TO_HK == pd.Timedelta(hours=8)


def test_hong_kong_seasons_start_in_september():
    assert hk.season_of(["2017-06-21", "2017-09-03", "2018-06-27"]).tolist() == [2016, 2017, 2017]
    assert hk.season_label(2016) == "2016/2017"


def test_a_pool_bet_is_sized_at_the_screen_price_and_paid_at_the_dividend():
    # backed at 5.0 on the screen: risk 0.25 to win 1; the dividend paid 4.0
    profit, risk = hk.pool_bet_units([5.0, 5.0, 5.0], [4.0, np.nan, 4.0], [1, 0, 1],
                                     refund=[False, False, True])
    assert risk.tolist() == pytest.approx([0.25, 0.25, 0.0])
    assert profit.tolist() == pytest.approx([0.75, -0.25, 0.0])


def _fake_snapshots():
    rows = []
    # race 1: captures 40, 13, 7 and 1.5 minutes before the start, two runners
    for snap_no, lead in enumerate([40.0, 13.0, 7.0, 1.5]):
        for horse in (1, 2):
            rows.append((1, snap_no, lead, horse, 4.0 + snap_no + horse))
    # race 2: only a capture 30 minutes out
    for horse in (1, 2):
        rows.append((2, 0, 30.0, horse, 6.0))
    df = pd.DataFrame(rows, columns=["race_id", "snap_no", "minutes_before_start", "horse_no", "win_disp"])
    for c in ("status", "pla_disp", "field_priced", "book_win", "book_win_mid", "book_pla"):
        df[c] = 0
    return df


@pytest.mark.parametrize("lead, want_snap_lead", [(10, 13.0), (5, 7.0), (2, 7.0)])
def test_the_decision_uses_the_last_capture_at_or_before_the_lead(monkeypatch, lead, want_snap_lead):
    monkeypatch.setattr(hk, "_snapshots", _fake_snapshots)
    out = hk.snapshot_at(lead)
    r1 = out[out.race_id == 1]
    assert set(r1.snap_lead) == {want_snap_lead}     # never the 1.5-minute capture
    assert (out.snap_lead >= lead).all()


def test_a_race_whose_last_capture_is_stale_is_dropped(monkeypatch):
    monkeypatch.setattr(hk, "_snapshots", _fake_snapshots)
    out = hk.snapshot_at(5)
    assert 2 not in set(out.race_id)                  # 30 minutes out is 25 minutes stale
    with pytest.raises(ValueError):
        hk.snapshot_at(0)

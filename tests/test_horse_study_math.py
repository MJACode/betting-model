"""The arithmetic the horse racing studies grade with. No network, no database.

scripts/horse/anz_study.py and scripts/horse/hk_study.py produce the tables in
docs/horse_racing_market_audit.md. These pin the pieces whose mistake would
move every number there: the published stake, dead heats, commission, the
de-vig, the place probabilities, the day-first date in one Betfair file, and
which files the Supabase store takes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.horse.anz_study import commission_schedule, devig, harville_top, stake_units
from scripts.horse.store_files import REL_PREFIX, SOURCE_PREFIX, files, kind_for


def test_the_stake_is_one_unit_to_win_with_risk_capped_at_three():
    profit, risk = stake_units(np.array([5.0, 2.0, 1.25]), np.array([1.0, 1.0, 1.0]), 0.0)
    assert risk.tolist() == pytest.approx([0.25, 1.0, 3.0])
    # at 1.25 the cap binds: 3 units risked win 0.75, not 1
    assert profit.tolist() == pytest.approx([1.0, 1.0, 0.75])
    lost, risk = stake_units(np.array([5.0]), np.array([0.0]), 0.0)
    assert lost.tolist() == pytest.approx([-0.25])


def test_a_dead_heat_pays_half_the_stake_at_full_odds_and_loses_the_other_half():
    profit, risk = stake_units(np.array([5.0]), np.array([0.5]), 0.0)
    # 0.25 risked: half (0.125) wins 4x = 0.5, half loses 0.125
    assert profit.tolist() == pytest.approx([0.5 - 0.125])
    assert risk.tolist() == pytest.approx([0.25])


def test_commission_is_charged_on_a_net_win_only():
    win, _ = stake_units(np.array([3.0]), np.array([1.0]), 0.10)
    loss, _ = stake_units(np.array([3.0]), np.array([0.0]), 0.10)
    assert win.tolist() == pytest.approx([0.9])
    assert loss.tolist() == pytest.approx([-0.5])


def test_commission_follows_the_state_and_the_march_2025_change():
    df = pd.DataFrame({
        "STATE_CODE": ["NSW", "ACT", "VIC", "VIC", "NZ", "NZ"],
        "date": pd.to_datetime(["2024-01-01", "2026-01-01", "2025-03-24", "2025-03-25",
                                "2024-06-01", "2025-06-01"]),
    })
    assert commission_schedule(df).tolist() == pytest.approx([0.10, 0.10, 0.07, 0.08, 0.05, 0.06])


@pytest.mark.parametrize("method", ["prop", "power"])
def test_devig_sums_to_one(method):
    q = 1.0 / np.array([1.8, 3.5, 7.0, 15.0, 40.0])
    p = devig(q, method)
    assert p.sum() == pytest.approx(1.0)
    assert np.all(np.diff(p) < 0)


def test_power_devig_takes_more_margin_off_the_longshot():
    q = 1.0 / np.array([1.4, 3.0, 8.0])     # a book of 1.17, over 100%
    prop, power = devig(q, "prop"), devig(q, "power")
    assert power[-1] < prop[-1] and power[0] > prop[0]


@pytest.mark.parametrize("k", [1, 2, 3])
def test_place_probabilities_sum_to_the_number_of_places(k):
    p = np.array([0.35, 0.25, 0.15, 0.1, 0.08, 0.04, 0.03])
    for lam in (1.0, 0.76):
        top = harville_top(p, k, lam)
        assert top.sum() == pytest.approx(float(k), abs=1e-9)
        assert np.all(top <= 1.0) and np.all(np.diff(top) <= 1e-12)


def test_harville_second_place_matches_the_formula_by_hand():
    p = np.array([0.5, 0.3, 0.2])
    # P(runner 2 in the first two) = .3 + .5*.3/.5 + .2*.3/.8
    assert harville_top(p, 2)[1] == pytest.approx(0.3 + 0.3 + 0.075)


def test_one_betfair_file_writes_its_dates_day_first(tmp_path):
    """ANZ_Thoroughbreds_2025_04.csv writes 1/04/2025; read as month-first it
    would put April's races in January. The loader reads both shapes and
    refuses a row outside its file's month."""
    from scripts.horse.anz_study import load
    cols = ("LOCAL_MEETING_DATE,WIN_MARKET_ID,SELECTION_ID,STATE_CODE,WIN_RESULT,PLACE_RESULT,"
            "WIN_BSP,PLACE_BSP,BEST_AVAIL_BACK_AT_SCHEDULED_OFF,BEST_AVAIL_LAY_AT_SCHEDULED_OFF,"
            "BACK_MARKET_PERCENTAGE_AT_SCHEDULED_OFF,LAY_MARKET_PERCENTAGE_AT_SCHEDULED_OFF,"
            "WIN_BSP_VOLUME,WIN_PREPLAY_VOLUME,DISTANCE\n")
    d = tmp_path / "betfair-x"
    d.mkdir()
    (d / "ANZ_Thoroughbreds_2025_04.csv").write_text(
        cols + "1/04/2025,1,10,VIC,WINNER,WINNER,2,1.2,2,2.1,1,1,1,1,1200\n"
               "1/04/2025,1,11,VIC,LOSER,LOSER,3,1.5,3,3.1,1,1,1,1,1200\n", encoding="utf-8")
    (d / "ANZ_Thoroughbreds_2025_05.csv").write_text(
        cols + "2025-05-02,2,12,NSW,WINNER,WINNER,2,1.2,2,2.1,1,1,1,1,1200\n", encoding="utf-8")
    df = load(tmp_path)
    assert sorted(df["date"].dt.strftime("%Y-%m-%d").unique()) == ["2025-04-01", "2025-05-02"]
    (d / "ANZ_Thoroughbreds_2025_06.csv").write_text(
        cols + "2025-07-02,3,13,NSW,WINNER,WINNER,2,1.2,2,2.1,1,1,1,1,1200\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="outside their file's month"):
        load(tmp_path)


def test_the_store_takes_csvs_not_zips_and_marks_whose_file_it_is(tmp_path):
    (tmp_path / "betfair-ANZ_Thoroughbreds_2020.zip").mkdir()
    (tmp_path / "betfair-ANZ_Thoroughbreds_2020.zip" / "ANZ_Thoroughbreds_2020.zip").write_bytes(b"zip")
    (tmp_path / "betfair-ANZ_Thoroughbreds_2020.zip" / "ANZ_Thoroughbreds_2020_01.csv").write_text("a\n")
    (tmp_path / "gdaley-hkracing").mkdir()
    (tmp_path / "gdaley-hkracing" / "runs.csv").write_text("a\n")
    rels = [rel for rel, _ in files(tmp_path)]
    assert rels == ["betfair-ANZ_Thoroughbreds_2020.zip/ANZ_Thoroughbreds_2020_01.csv",
                    "gdaley-hkracing/runs.csv"]
    assert [kind_for(r) for r in rels] == ["betfair_anz_thoroughbreds", "gdaley_hkracing"]
    # the shared table's rel_path is unique: racing rows must not collide with NFL ones
    assert REL_PREFIX == "horse/" and SOURCE_PREFIX == "horse_racing|"

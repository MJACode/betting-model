"""A card run that finds no bets must not leave an earlier run's card on disk.

WHY THIS FILE EXISTS

Measured 2026-09-20. The 15:40 UTC wind run forecast MIN @ CHI at 13.3 mph and
wrote data/cards/wind_card_2026-09-20.csv (Under 47.5 at -114). From 15:50 the
forecast was 10.0 mph and every run printed "No qualifying bets" -- and returned
without touching the file, so scripts/nfl_wind_publisher.py re-read the 15:40
row every ten minutes until kickoff. Nothing was bet only because the EV floor
dropped it. The opener card had the same exit.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
NFL_ROOT = REPO / "nfl"


@pytest.fixture()
def nfl_path():
    sys.path.insert(0, str(NFL_ROOT))
    try:
        yield
    finally:
        sys.path.remove(str(NFL_ROOT))


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(
        f"_nfl_script_{name}", NFL_ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_clear_card_removes_todays_file_and_only_that(nfl_path, tmp_path, monkeypatch):
    from data_ingest.cards import card_path, clear_card
    monkeypatch.chdir(tmp_path)
    now = datetime(2026, 9, 20, 15, 50, tzinfo=timezone.utc)
    today = card_path("wind_card", now)
    today.parent.mkdir(parents=True)
    today.write_text("game_id\n2026_02_MIN_CHI\n", encoding="utf-8")
    other = today.parent / "wind_card_2026-09-19.csv"
    other.write_text("game_id\n", encoding="utf-8")
    opener = card_path("opener_card", now)
    opener.write_text("game_id\n", encoding="utf-8")

    assert clear_card("wind_card", now) is True
    assert not today.exists()
    assert other.exists() and opener.exists()
    assert clear_card("wind_card", now) is False


def test_the_path_cleared_is_the_path_the_publisher_reads(nfl_path):
    from data_ingest.cards import card_path
    from scripts import nfl_wind_publisher as pub
    now = datetime(2026, 9, 20, 15, 50, tzinfo=timezone.utc)
    src = (REPO / "scripts" / "nfl_wind_publisher.py").read_text(encoding="utf-8")
    for prefix in ("wind_card", "opener_card"):
        assert f'CARDS_DIR / f"{prefix}_{{run_date}}.csv"' in src
        assert (card_path(prefix, now).name
                == (pub.CARDS_DIR / f"{prefix}_2026-09-20.csv").name)
    assert pub.CARDS_DIR.name == "cards" and pub.CARDS_DIR.parent.name == "data"


def _windless_run(monkeypatch, tmp_path, argv):
    """Run the wind card's main() with a slate that qualifies nothing."""
    card = _load_script("weekly_wind_card")
    slate = pd.DataFrame([{
        "matchup": "MIN @ CHI", "stadium_id": "CHI98", "lead_days": 0.0,
        "forecast_wind": 10.0, "exp_true_wind": 8.9, "gust": 17.9, "temp": 65.9,
    }])
    monkeypatch.setattr(card, "load_schedule", lambda days: slate)
    monkeypatch.setattr(card, "attach_forecast", lambda sched: slate)
    monkeypatch.setattr(card, "attach_odds", lambda g, regions, dry: g)
    monkeypatch.setattr(card, "select_bets", lambda g, **kw: pd.DataFrame())
    monkeypatch.setattr(card, "open_air_mask",
                        lambda s: pd.Series([True] * len(s)))
    monkeypatch.setattr(sys, "argv", ["weekly_wind_card.py", *argv])
    monkeypatch.chdir(tmp_path)
    stale = tmp_path / "data" / "cards" / (
        f"wind_card_{datetime.now(timezone.utc):%Y-%m-%d}.csv")
    stale.parent.mkdir(parents=True)
    stale.write_text("game_id\n2026_02_MIN_CHI\n", encoding="utf-8")
    assert card.main() == 0
    return stale


def test_a_priced_wind_run_with_no_bets_removes_the_earlier_card(
        nfl_path, monkeypatch, tmp_path):
    stale = _windless_run(monkeypatch, tmp_path, [])
    assert not stale.exists()


def test_a_dry_run_leaves_the_card_alone(nfl_path, monkeypatch, tmp_path):
    # A dry run prices nothing, so "no bets" says nothing about the card.
    stale = _windless_run(monkeypatch, tmp_path, ["--dry-run"])
    assert stale.exists()


def test_the_opener_card_clears_on_its_no_bets_exit():
    src = (NFL_ROOT / "scripts" / "daily_opener_card.py").read_text(encoding="utf-8")
    exit_block = src.split("No qualifying opener bets", 1)[1].split("return 0", 1)[0]
    assert 'clear_card("opener_card")' in exit_block

"""MoneyPuck.com is a supplemental NHL source. Credit MoneyPuck.com.

The files on their data page, one download per file per day, keyed so they
join to our games. Not a pick input.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from data.ingestors import moneypuck_nhl as mp
from data.ingestors.moneypuck_columns import SOURCE, TABLES, columns

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = "moneypuck_nhl_2026_11_26.sql"


def test_a_shot_uses_the_league_game_id_not_the_file_number():
    # shots_2026.csv game 20001 is FLA at CAR, which the team log stores as
    # 2026020001. The file's shotID is not unique, so it is not the key.
    record = mp.shot_record({
        "season": "2026", "game_id": "20001", "id": "25",
        "teamCode": "FLA", "homeTeamCode": "CAR", "awayTeamCode": "FLA",
        "shotID": "0", "xGoal": "0.12",
    })
    assert record["nhl_game_id"] == 2026020001
    assert record["event_id"] == 25
    assert record["mp_game_number"] == 20001
    assert record["season_start"] == 2026
    assert record["season_end"] == 2027
    assert record["team_abbr"] == "FLA"
    assert record["home_abbr"] == "CAR"
    assert record["x_goal"] == pytest.approx(0.12)
    assert record["source"] == SOURCE
    assert mp.nhl_game_id_from_shot(2024, 30001) == 2024030001


def test_team_abbrevs_match_ours_and_the_date_is_iso():
    assert mp.team_abbr("ARI") == "UTA"
    assert mp.team_abbr("L.A") == "LAK"
    assert mp.team_abbr("T.B") == "TBL"
    assert mp.team_abbr("N.J") == "NJD"
    assert mp.team_abbr("S.J") == "SJS"
    assert mp.iso_date("20081004") == "2008-10-04"
    record = mp.team_record({
        "season": "2008", "gameId": "2008020001", "playerTeam": "ARI",
        "opposingTeam": "L.A", "situation": "5on5", "gameDate": "20081004",
        "xGoalsFor": "1.5",
    })
    assert record["team_abbr"] == "UTA"
    assert record["opp_abbr"] == "LAK"
    assert record["nhl_game_id"] == 2008020001
    assert record["game_date"] == "2008-10-04"
    assert record["x_goals_for"] == pytest.approx(1.5)


def test_a_forward_line_id_stays_text():
    line_id = "848344584841538485400"  # 21 digits, past bigint
    record = mp.line_record({
        "season": "2026", "gameId": "2026020328", "lineId": line_id,
        "playerTeam": "ANA", "opposingTeam": "CGY", "situation": "5on5",
        "gameDate": "20261115", "position": "line", "name": "A-B-C",
    })
    assert record["line_id"] == line_id
    assert isinstance(record["line_id"], str)
    assert record["position"] == "line"


def test_a_row_with_no_team_is_not_stored():
    assert mp.team_record({
        "season": "2026", "gameId": "2026020001", "playerTeam": "",
        "opposingTeam": "FLA", "situation": "all", "gameDate": "20261004",
    }) is None


def test_daily_plan_is_one_download_per_file_for_the_current_season():
    plan = mp.daily_plan("2026-11-26")
    urls = [item["url"] for item in plan]
    assert len(urls) == len(set(urls)) == 6
    assert urls[0].endswith("/shots_2026.zip")
    assert urls[1].endswith("/all_teams.csv")
    kinds = [item["kind"] for item in plan]
    assert kinds == ["shots", "teams", "skaters", "goalies", "lines", "bios"]
    # June is still the previous season. File year is the starting year.
    june = [item["url"] for item in mp.daily_plan("2026-06-01")]
    assert any(url.endswith("/shots_2025.zip") for url in june)
    assert mp.file_year("2026-11-26") == 2026
    assert mp.file_year("2026-09-29") == 2026


def test_backfill_keeps_the_history_that_fits_and_leaves_the_rest():
    urls = [item["url"] for item in mp.backfill_plan("2026-11-26")]
    assert len(urls) == len(set(urls))
    assert any(url.endswith("/shots_2018.zip") for url in urls)
    assert any(url.endswith("/shots_2026.zip") for url in urls)
    assert not any("shots_2017" in url for url in urls)
    assert not any("shots_2007-2025" in url for url in urls)
    assert any(url.endswith("/lines/2008_to_2024.zip") for url in urls)
    assert any(url.endswith("/goalies/2008_to_2024.zip") for url in urls)
    assert not any("skaters/2008_to_2024" in url for url in urls)
    skater_years = [url for url in urls if "/skaters/" in url]
    assert len(skater_years) == 2026 - 2018 + 1
    assert not any(url.endswith("/lines/2018.zip") for url in urls)
    assert any(url.endswith("/lines/2025.zip") for url in urls)
    assert any(url.endswith("/all_teams.csv") for url in urls)


def test_a_plan_that_names_one_file_twice_is_refused():
    item = mp.daily_plan("2026-11-26")[0]
    with pytest.raises(RuntimeError, match="twice"):
        mp.run_plan([item, item], "2026-11-26", apply=False)


def test_load_upserts_on_the_key_and_counts_without_a_database(tmp_path):
    path = tmp_path / "teams.csv"
    path.write_text(
        "season,gameId,playerTeam,opposingTeam,situation,gameDate,xGoalsFor\n"
        "2026,2026020001,ARI,FLA,5on5,20261004,1.2\n"
        "2026,2026020001,ARI,FLA,5on5,20261004,1.4\n"
        "2025,2025020001,BOS,NYR,all,20251004,0.4\n",
        encoding="utf-8",
    )
    stats = mp.load_file(path, "teams", 2026, apply=False, conn=None)
    assert stats["seen"] == 3
    assert stats["kept"] == 2
    assert stats["written"] == 1  # the two 2026 rows are one key; last wins
    sql = mp._insert_sql("moneypuck_team_games", ("nhl_game_id", "team_abbr", "situation"),
                         ("nhl_game_id", "team_abbr", "situation"))
    assert "ON CONFLICT (nhl_game_id, team_abbr, situation) DO UPDATE" in sql
    assert "fetched_at = NOW()" in sql


def test_migration_enables_rls_and_credits_moneypuck():
    from data.view_migrations import ACTIVE_MIGRATIONS
    sql = (ROOT / "data" / "migrations" / MIGRATION).read_text(encoding="utf-8")
    assert MIGRATION in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    assert "MoneyPuck.com" in sql
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 6
    assert sql.count("REVOKE ALL ON public.moneypuck_") == 6
    assert "anon, authenticated" in sql
    for name in ("moneypuck_shots", "moneypuck_team_games", "moneypuck_skater_games",
                 "moneypuck_goalie_games", "moneypuck_line_games", "moneypuck_players"):
        assert f"public.{name}" in sql
    assert "shooter_player_id" in sql
    assert "line_id" in sql and "TEXT NOT NULL" in sql
    # The worker applies one statement. Comments then a single DO block.
    body = "\n".join(line for line in sql.splitlines() if not line.startswith("--")).strip()
    assert body.startswith("DO $$")
    assert body.endswith("END $$;")
    for key, table in TABLES.items():
        for col in columns(table):
            assert col in sql, (key, col)


def test_no_pick_model_reads_moneypuck():
    """Live scoring does not read MoneyPuck.

    models/nhl_props.py may name the tables for a points and assists backtest
    whose flag defaults off. The card scores the live spec and does not call
    that path.
    """
    allowed = {(ROOT / "models" / "nhl_props.py").resolve()}
    for path in (ROOT / "models").rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        if path.resolve() in allowed:
            continue
        assert "moneypuck" not in text, path
    assert "moneypuck" not in (ROOT / "config.py").read_text(encoding="utf-8").lower()
    props = (ROOT / "models" / "nhl_props.py").read_text(encoding="utf-8")
    assert "USE_MONEYPUCK_POINTS = False" in props
    card = (ROOT / "scripts" / "nhl_props_card.py").read_text(encoding="utf-8")
    assert "add_points_features" not in card
    assert "points_spec" not in card
    assert "assists_spec" not in card
    assert "moneypuck" not in card.lower()


def test_the_module_credits_moneypuck():
    text = (ROOT / "data" / "ingestors" / "moneypuck_nhl.py").read_text(encoding="utf-8")
    assert "MoneyPuck.com" in text
    assert "https://moneypuck.com/data.htm" in text


def test_cache_path_keeps_same_named_files_apart():
    from data.ingestors.moneypuck_nhl import _cache_path
    base = "https://peter-tanner.com/moneypuck/downloads/seasonPlayersSummary"
    paths = {
        _cache_path("2026-11-26", f"{base}/{kind}/{name}")
        for kind in ("skaters", "goalies", "lines")
        for name in ("2025.zip", "2008_to_2024.zip")
    }
    assert len(paths) == 6


def test_int_takes_float_formatted_ids():
    from data.ingestors.moneypuck_nhl import _int
    assert _int("8475883.0") == 8475883
    assert _int("8475883") == 8475883

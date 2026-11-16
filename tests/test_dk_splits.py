"""DraftKings' own splits (data/ingestors/dk_splits.py).

FIXTURE is DK Network's page text exactly as the worker probe captured it on
2026-11-03 (worker_jobs 936774, `handle_window`), U+2212 minus signs and the
U+00B7 dot included. No network, no database.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from data.ingestors import dk_splits as dk
from data.ingestors import scoreboard_splits as ss

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = (
    "Sports NFL NBA NHL MLB WNBA UFC UFL NCAA Football NCAA Basketball Today Tomorrow "
    "Next 7 Days Next 30 Days Search All Moneyline Spread Total --> Matchup Odds % Handle "
    "% Bets --> JAX Jaguars @ BAL Ravens Thu 11/5 · 8:15 PM ET Selection Odds Handle Bets "
    "Moneyline BAL Ravens +350 22% 10% JAX Jaguars −455 78% 90% "
    "Spread JAX Jaguars -8.5 −115 86% 82% BAL Ravens +8.5 −105 14% 18% "
    "Total Over 42.5 −105 50% 50% Under 42.5 −115 50% 50% "
    "CIN Bengals @ ATL Falcons Sun 11/8 · 9:30 AM ET Selection Odds Handle Bets "
    "Moneyline ATL Falcons +136 17% 16% CIN Bengals −162 83% 84% "
    "Spread CIN Bengals -3 −115 50% 81% ATL Falcons +3 −105 50% 19% "
    "Total Over 52.5 −102 100% 100% Under 52.5 −118 0% 0% "
    "NY Jets @ KC Chiefs Sun 11/8 · 1:00 PM ET Selection Odds Handle Bets "
    "Moneyline KC Chiefs −485 89% 93% NY Jets +370 11% 7% "
    "Spread KC Chiefs -9.5 −112 36% 63% NY Jets +9.5 −108 64% 37% "
    "Total Over 46.5 −110 0% 0% Under 46.5 −110 100% 100% Advertisement "
    "DET Lions @ MIA Dolphins Sun 11/8 · 1:00 PM ET Selection Odds Handle Bets "
    "Moneyline MIA Dolphins +285 3% 9% DET Lions −360 97% 91% "
    "Spread DET Lions -7 −108 85% 89% MIA Dolphins +7 −112 15% 11% "
    "Total Over 50.5 −105 100% 100% Under 50"
)
NOW = datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)


def _games():
    return dk.parse_page(FIXTURE, NOW)


def test_parses_every_complete_game_with_handle_as_money_and_bets_as_tickets():
    games = _games()
    assert [(g["away"], g["home"], g["date"]) for g in games] == [
        ("JAX Jaguars", "BAL Ravens", "2026-11-05"),
        ("CIN Bengals", "ATL Falcons", "2026-11-08"),
        ("NY Jets", "KC Chiefs", "2026-11-08"),
        ("DET Lions", "MIA Dolphins", "2026-11-08"),
    ]
    s = games[1]["sides"]
    # "Spread CIN Bengals -3 −115 50% 81%": Handle 50, Bets 81.
    assert s[("spreads", "away")] == {"value": -3.0, "odds": -115, "money": 50.0, "tickets": 81.0}
    assert s[("spreads", "home")] == {"value": 3.0, "odds": -105, "money": 50.0, "tickets": 19.0}
    assert s[("h2h", "home")]["odds"] == 136 and s[("h2h", "home")]["value"] is None
    assert s[("totals", "over")]["value"] == 52.5


def test_a_zero_zero_side_reads_as_zero_when_its_pair_sums_to_100():
    s = _games()[2]["sides"]
    assert s[("totals", "over")]["money"] == 0.0 and s[("totals", "under")]["money"] == 100.0


def test_a_truncated_last_game_keeps_only_the_complete_markets():
    s = _games()[3]["sides"]
    assert ("spreads", "home") in s and ("h2h", "away") in s
    # "Total Over 50.5 −105 100% 100% Under 50" was cut mid-row: the lone
    # Over is kept as served (clean_pair 'one_side'), no Under is invented.
    assert ("totals", "under") not in s


def test_page_text_reads_html_the_way_the_probe_did():
    html = ("<div><span>JAX Jaguars</span> @ <span>BAL Ravens</span> <time>Thu 11/5 &middot; "
            "8:15 PM ET</time></div><div>Selection</div><div>Odds</div><div>Handle</div>"
            "<div>Bets</div><div>Spread</div><div>JAX Jaguars</div><div>-8.5</div>"
            "<div>&minus;115</div><div>86%</div><div>82%</div><div>BAL Ravens</div>"
            "<div>+8.5</div><div>&minus;105</div><div>14%</div><div>18%</div>")
    g = dk.parse_page(dk.page_text(html), NOW)
    assert g[0]["sides"][("spreads", "away")]["money"] == 86.0


NAMES = {"CIN": ["Cincinnati Bengals"], "ATL": ["Atlanta Falcons"],
         "LA": ["Los Angeles Rams"], "LAC": ["Los Angeles Chargers"],
         "NYJ": ["New York Jets"], "NYG": ["New York Giants"], "SF": ["San Francisco 49ers"]}


def test_nickname_not_city_names_the_team():
    assert dk.team_matches("NFL", "LA Rams", "LA", NAMES)
    assert not dk.team_matches("NFL", "LA Rams", "LAC", NAMES)
    # Our Rams id is "LA": the city word must not hand it the Chargers.
    assert not dk.team_matches("NFL", "LA Chargers", "LA", NAMES)
    assert dk.team_matches("NFL", "LA Chargers", "LAC", NAMES)
    assert dk.team_matches("NFL", "NY Jets", "NYJ", NAMES)
    assert not dk.team_matches("NFL", "NY Jets", "NYG", NAMES)
    assert dk.team_matches("NFL", "SF 49ers", "SF", NAMES)


def test_every_nfl_team_name_resolves_to_exactly_one_id():
    # DK prints '<city> <nickname>'; the nickname must pick one of our ids.
    from config import NFL_ODDS_API_MAP
    names = dk._full_names("NFL")
    for full, abbr in NFL_ODDS_API_MAP.items():
        dk_name = "XX " + full.split(" ")[-1]
        hits = {a for a in names if dk.team_matches("NFL", dk_name, a, names)}
        assert hits == {abbr}, (full, hits)


GAME = {"game_id": "NFL_2026_10_CIN_ATL", "sport": "NFL", "game_date": "2026-11-08",
        "home_team": "ATL", "away_team": "CIN", "commence_time": "2026-11-08T14:30:00+00:00"}


def test_rows_land_on_our_game_id_and_skip_started_games():
    counts: dict = {}
    rows = dk.build_rows("NFL", _games(), [GAME], NOW, counts)
    assert {r["game_id"] for r in rows} == {"NFL_2026_10_CIN_ATL"}
    away = next(r for r in rows if r["market"] == "spreads" and r["side"] == "away")
    assert (away["bet_pct"], away["money_pct"], away["line_value"]) == (81.0, 50.0, -3.0)
    assert counts["games"] == 1 and counts["unmatched"] == 3
    later = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
    assert dk.build_rows("NFL", _games(), [GAME], later, {}) == []


def test_upsert_keeps_the_first_dk_split_as_the_opening():
    sql = dk.UPSERT_SQL
    assert "'dk_network', %(bet_pct)s, %(money_pct)s, %(snapshot_at)s" in sql
    assert "THEN scoreboard_splits.open_money_pct ELSE EXCLUDED.money_pct" in sql
    # An Action Network row is never the opening.
    assert sql.count("scoreboard_splits.source = 'dk_network'") == 4
    assert "THEN scoreboard_splits.open_line_value ELSE EXCLUDED.line_value" in sql


def test_discovers_event_groups_from_sport_links_only():
    html = ('<a href="?tb_eg=88808&amp;tb_edate=n7days">NFL</a>'
            '<a href="?tb_eg=42648">NBA</a><a href="?tb_eg=1&tb_page=2">2</a>'
            '<a href="?tb_eg=87637"><span>NCAA Football</span></a>')
    assert dk.discover_event_groups(html) == {"NFL": "88808", "NBA": "42648", "NCAAF": "87637"}


def test_history_appends_only_changed_splits():
    rows = [{"game_id": "g", "market": "spreads", "side": "home", "bet_pct": 50.0,
             "money_pct": 40.0, "line_value": -3.0},
            {"game_id": "g", "market": "spreads", "side": "away", "bet_pct": 50.0,
             "money_pct": 60.0, "line_value": 3.0}]
    latest = {("g", "spreads", "home"): {"bet_pct": 50, "money_pct": 40, "line_value": -3},
              ("g", "spreads", "away"): {"bet_pct": 50, "money_pct": 55, "line_value": 3}}
    assert [r["side"] for r in ss.changed_rows(rows, latest)] == ["away"]
    assert len(ss.changed_rows(rows, {})) == 2


def test_never_written_to_public_betting_and_wired_into_refresh_and_migrations():
    src = (ROOT / "data" / "ingestors" / "dk_splits.py").read_text(encoding="utf-8")
    assert "public_betting" not in src.split('"""', 2)[2]
    sh = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
    assert "par scoreboard-splits" in sh
    rp = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    assert "from data.ingestors.dk_splits import run" in rp
    mig = (ROOT / "data" / "view_migrations.py").read_text(encoding="utf-8")
    assert mig.index("add_scoreboard_splits_2026_10_29.sql") < mig.index(
        "scoreboard_splits_dk_history_2026_11_16.sql")
    sql = (ROOT / "data" / "migrations" / "scoreboard_splits_dk_history_2026_11_16.sql"
           ).read_text(encoding="utf-8")
    assert sql.index("RETURN;") < sql.index("ALTER TABLE")
    assert "REVOKE ALL ON public.scoreboard_splits_history FROM anon, authenticated" in sql

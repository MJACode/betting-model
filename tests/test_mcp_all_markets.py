"""AI assistant (MCP): every stored game market, EuroLeague / NBL, and the missing props.

Matt, 2026-11-25 ("Yes to everything ... include Euro and NBL"). A member asked
the connector for tonight's NBA first-quarter totals and was told it has no
quarter markets: mcp_stats.game_prices kept only h2h / spreads / totals while
latest_odds held every NBA quarter and half, NCAAB halves, team totals,
alternates, NHL 3-way and first period, and EuroLeague / NBL lines.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from data.view_migrations import ACTIVE_MIGRATIONS
from tests._node import NODE, node_strips_types

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "data" / "migrations"
NEW = "mcp_stats_all_markets_2026_11_25.sql"
BASE = "mcp_stats_views_2026_11_21.sql"
SERVER = ROOT / "supabase" / "functions" / "mcp" / "index.ts"

# Every distinct market key in latest_odds over the 7 days to 2026-11-25
# (read-only query, this session), with the period it must map to.
MEASURED_PERIODS = {
    "alternate_spreads": "game", "alternate_team_totals_away": "game",
    "alternate_team_totals_home": "game", "alternate_totals": "game", "h2h": "game",
    "h2h_3_way_h1": "1H", "h2h_3_way_q1": "1Q", "h2h_3way": "game", "h2h_h1": "1H",
    "h2h_q1": "1Q", "spreads": "game", "spreads_h1": "1H", "spreads_q1": "1Q",
    "spreads_q2": "2Q", "spreads_q3": "3Q", "spreads_q4": "4Q", "team_totals_away": "game",
    "team_totals_away_alternate": "game", "team_totals_h1_away": "1H",
    "team_totals_h1_away_alternate": "1H", "team_totals_h1_home": "1H",
    "team_totals_h1_home_alternate": "1H", "team_totals_home": "game",
    "team_totals_home_alternate": "game", "totals": "game", "totals_h1": "1H",
    "totals_p1": "1P", "totals_q1": "1Q", "totals_q2": "2Q", "totals_q3": "3Q",
    "totals_q4": "4Q",
}
EXPECTED_KIND = {
    "h2h": "moneyline", "h2h_h1": "moneyline", "h2h_q1": "moneyline",
    "h2h_3way": "moneyline_3way", "h2h_3_way_h1": "moneyline_3way", "h2h_3_way_q1": "moneyline_3way",
    "spreads": "spread", "spreads_q3": "spread", "alternate_spreads": "spread",
    "totals": "total", "totals_p1": "total", "alternate_totals": "total",
    "team_totals_home": "team_total_home", "team_totals_h1_home_alternate": "team_total_home",
    "alternate_team_totals_home": "team_total_home",
    "team_totals_away": "team_total_away", "team_totals_h1_away": "team_total_away",
    "alternate_team_totals_away": "team_total_away",
}
ALTERNATE = {m for m in MEASURED_PERIODS if m.startswith("alternate_") or m.endswith("_alternate")}


def _body(name: str) -> str:
    sql = (MIGRATIONS / name).read_text(encoding="utf-8")
    return "\n".join(ln for ln in sql.splitlines() if not ln.strip().startswith("--"))


def _view(body: str, name: str) -> str:
    start = body.index(f"CREATE OR REPLACE VIEW mcp_stats.{name} AS")
    return body[start:body.index(";\n", start)]


def test_listed_after_the_views_it_replaces():
    i = ACTIVE_MIGRATIONS.index
    assert NEW in ACTIVE_MIGRATIONS
    for earlier in (BASE, "mcp_stats_alt_lines_2026_11_21.sql", "mcp_stats_context_2026_11_22.sql"):
        assert i(earlier) < i(NEW), earlier


def test_guard_is_the_property_not_the_text():
    body = _body(NEW)
    assert body.strip().startswith("DO $markets$") and body.strip().endswith("$markets$;")
    assert "attname = 'period'" in body
    assert "WHERE stat = 'anytime_td'" in body
    assert "pg_get_viewdef" not in body
    assert not re.search(r"GRANT[^;]*\b(anon|authenticated)\b", body)
    assert "TO mcp_reader" in body


def test_base_file_cannot_rerun_over_this_one():
    """The base file re-runs only while 'mcp_stats v1' is missing from this comment."""
    body = _body(NEW)
    comment = body[body.index("COMMENT ON VIEW mcp_stats.player_games"):]
    assert "mcp_stats v1" in comment.split(";")[0]


def test_both_files_carry_the_same_three_views():
    for name in ("game_prices", "prop_markets", "player_games"):
        assert _view(_body(BASE), name) == _view(_body(NEW), name), name


def test_game_prices_has_no_market_filter_and_keeps_the_pregame_bound():
    view = _view(_body(NEW), "game_prices")
    assert "o.market IN" not in view and "market = ANY" not in view
    assert view.rstrip().endswith("WHERE (g.commence_time IS NULL OR o.snapshot_at <= g.commence_time)")
    select = view.split("FROM public.latest_odds")[0].rstrip()
    # Appended after the original twelve columns: CREATE OR REPLACE can only append.
    cols = select.index("o.over_price, o.under_price, o.snapshot_at")
    assert select.index("AS period") > cols
    assert select.index("AS kind") > select.index("AS period")
    assert select.endswith("AS is_alternate")


def _sql_regex(view: str, label: str) -> str:
    m = re.search(r"substring\(o\.market FROM '([^']+)'\)", view)
    assert m, label
    return m.group(1)


def test_period_mapping_on_every_measured_market():
    pat = re.compile(_sql_regex(_view(_body(NEW), "game_prices"), "period"))
    for market, want in MEASURED_PERIODS.items():
        m = pat.search(market)
        got = (m.group(1)[1] + m.group(1)[0].upper()) if m else "game"
        assert got == want, market


def test_kind_mapping_follows_the_case_order():
    view = _view(_body(NEW), "game_prices")
    whens = re.findall(r"WHEN o\.market ~ '([^']+)' THEN '([^']+)'", view)
    assert [k for _, k in whens] == ["moneyline_3way", "moneyline", "spread",
                                     "team_total_home", "team_total_away", "total"]
    for market, want in EXPECTED_KIND.items():
        got = next((k for pat, k in whens if re.search(pat, market)), market)
        assert got == want, market


def test_alternate_flag_on_every_measured_market():
    m = re.search(r"\(o\.market ~ '([^']+)'\) AS is_alternate", _view(_body(NEW), "game_prices"))
    assert m
    for market in MEASURED_PERIODS:
        assert bool(re.search(m.group(1), market)) == (market in ALTERNATE), market


NEW_PROPS = {
    ("NBA", "rebounds_assists", "player_rebounds_assists"), ("NBA", "blocks_steals", "player_blocks_steals"),
    ("NBA", "double_double", "player_double_double"), ("NBA", "first_basket", "player_first_basket"),
    ("NBA", "first_team_basket", "player_first_team_basket"),
    ("NFL", "anytime_td", "player_anytime_td"), ("NFL", "sacks", "player_sacks"),
    ("NFL", "tackles_assists", "player_tackles_assists"), ("NCAAF", "anytime_td", "player_anytime_td"),
    ("NHL", "goals", "player_goal_scorer_anytime"),
}


def _prop_rows() -> set[tuple[str, str, str]]:
    return set(re.findall(r"\('(\w+)','(\w+)','(\w+)'\)", _view(_body(NEW), "prop_markets")))


def test_prop_markets_maps_the_missing_props():
    assert NEW_PROPS <= _prop_rows()


def test_every_new_stat_with_history_is_in_player_games():
    games = _view(_body(NEW), "player_games")
    for stat in ("rebounds_assists", "blocks_steals", "double_double", "anytime_td", "sacks", "tackles_assists"):
        assert f"('{stat}'," in games, stat


def _server() -> str:
    return SERVER.read_text(encoding="utf-8")


def test_server_offers_every_mapped_stat_and_the_new_leagues():
    src = _server()
    sports = re.search(r"const SPORTS = \[([^\]]+)\]", src).group(1)
    assert '"EUROLEAGUE"' in sports and '"NBL"' in sports
    stats_block = src[src.index("const STATS: Record<Sport, string[]> = {"):src.index("const ALL_STATS")]
    per_sport = {m.group(1): set(re.findall(r'"(\w+)"', m.group(2)))
                 for m in re.finditer(r"\n  (\w+): \[([^\]]*)\]", stats_block)}
    assert per_sport["EUROLEAGUE"] == set() and per_sport["NBL"] == set()
    # A prop the view maps but the tool refuses is the bug this file fixes.
    for sport, stat, _ in _prop_rows():
        assert stat in per_sport[sport], (sport, stat)


# ── The real get_game_lines body, run in node on measured rows ───────────────
# BOS @ WAS, 2026-11-24, latest_odds (read-only query this session), the seven
# mcp books only. 1Q total: 56.5 x2, 57.5 x2, 60.5 x1 (Hard Rock at +175).
def _r(book, kind, alt=False, **kw):
    base = dict(kind=kind, is_alternate=alt, book=book, home_price=None, away_price=None, draw_price=None,
                spread_home=None, total_line=None, over_price=None, under_price=None,
                away_team="BOS", home_team="WAS", starts_at="2026-11-25T00:00:00Z",
                periods=["game", "1H", "1Q", "2Q", "3Q", "4Q"])
    base.update(kw)
    return base


Q1_TOTALS = [
    _r("BetMGM", "total", total_line=56.5, over_price=-115, under_price=-105),
    _r("BetRivers", "total", total_line=56.5, over_price=-129, under_price=-106),
    _r("DraftKings", "total", total_line=57.5, over_price=100, under_price=-120),
    _r("FanDuel", "total", total_line=57.5, over_price=-102, under_price=-125),
    _r("Hard Rock Bet", "total", total_line=60.5, over_price=175, under_price=-220),
]


def _run(rows, period="1Q", home_spread=None, total=None):
    if not node_strips_types():
        pytest.skip("node >= 22.6 not available")
    src = _server()
    case = src[src.index('case "get_game_lines": {'):src.index('case "get_injuries": {')]
    body = case[case.index("      const available ="):case.index("      return { data, rows: n ? 1 : 0 };")]
    script = (
        'const PERIODS = ["game", "1H", "2H", "1Q", "2Q", "3Q", "4Q", "1P", "2P", "3P"] as const;\n'
        f"const rows: any[] = {json.dumps(rows)};\n"
        f"const period = {json.dumps(period)};\nconst books: string | null = null;\n"
        f"const homeSpread: number | null = {json.dumps(home_spread)};\n"
        f"const totalAt: number | null = {json.dumps(total)};\n"
        + body + "\nconsole.log(JSON.stringify(data));\n")
    out = subprocess.run([NODE, "--experimental-strip-types", "--no-warnings", "--input-type=module-typescript"],
                         input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_tied_main_number_breaks_to_the_median_and_off_numbers_are_not_the_headline():
    d = _run(Q1_TOTALS)
    t = d["total"]
    assert t["line"] == 57.5 and t["books"] == 2
    assert t["over"] == {"price": 100, "book": "DraftKings"}
    assert t["under"] == {"price": -120, "book": "DraftKings"}
    # Hard Rock's +175 is a price on 60.5, never on the headline number.
    others = {o["line"]: o for o in t["other_lines"]}
    assert set(others) == {56.5, 60.5}
    assert others[60.5]["over"] == {"price": 175, "book": "Hard Rock Bet"}
    assert d["available_periods"] == ["game", "1H", "1Q", "2Q", "3Q", "4Q"]
    assert d["period"] == "1Q"


def test_tie_goes_to_the_median_not_the_bigger_number():
    """Same 2-2 tie with the off number BELOW: the median is now 56.5."""
    rows = Q1_TOTALS[:4] + [_r("Hard Rock Bet", "total", total_line=52.5, over_price=-300, under_price=220)]
    assert _run(rows)["total"]["line"] == 56.5


def test_exact_number_asks_reach_alternate_rows():
    rows = [
        _r("DraftKings", "spread", spread_home=10.5, home_price=-110, away_price=-110),
        _r("FanDuel", "spread", spread_home=10.5, home_price=-108, away_price=-112),
        _r("DraftKings", "spread", alt=True, spread_home=5.5, home_price=250, away_price=-350),
        _r("FanDuel", "spread", alt=True, spread_home=5.5, home_price=240, away_price=-330),
        _r("BetMGM", "spread", alt=True, spread_home=5.5, home_price=230, away_price=-320),
    ]
    d = _run(rows, period="game", home_spread=5.5, total=230.5)
    assert d["spread"]["home_line"] == 10.5          # alternates never set the main number
    assert d["spread_at"] == {"home_line": 5.5, "home": {"price": 250, "book": "DraftKings"},
                              "away": {"price": -320, "book": "BetMGM"}}
    assert d["total_at"] == {"line": 230.5, "coverage": "none"}


def test_a_period_with_no_prices_says_so_and_lists_what_exists():
    empty = [{**_r(None, None), "kind": None, "book": None}]
    d = _run(empty, period="3P")
    assert d["coverage"] == "none"
    assert d["moneyline"] is None and d["spread"] is None and d["total"] is None
    assert d["available_periods"] == ["game", "1H", "1Q", "2Q", "3Q", "4Q"]

"""The team page off the Stats tab's Teams board (2026-09-20).

Matt: "you should be able to click in a team and see useful stats to help a
user make a bet -- public bet vs sharp, home vs away, record against that
team". The page is screens/TeamStatsScreen.tsx, fed by hooks/useTeamDetail.ts
and lib/teamDetail.ts. There is no node on the machines that run this suite,
so what a TypeScript test would pin is pinned here structurally, from the
source -- the same shape as test_mobile_sport_filter.py.

Three things this guards, each of which is a silent failure if it drifts:

1. THE ROUTE IS WIRED END TO END. The board row navigates to 'TeamStats',
   the param list declares it, and App.tsx registers the screen. A missing
   registration is a runtime "The action 'NAVIGATE' ... was not handled"
   warning and a dead tap -- nothing at build time says so.

2. THE PAGE'S READS ARE ANON-READABLE AND SIZED. public_betting held the
   grant but no RLS policy, which is deny-all: the app would have received
   zero rows and no error. The policy migration exists and the manifest
   names both new relations (test_anon_readable.py checks the manifest
   against every `.from()`; this checks the migration exists at all).

3. THE RECORD FILTER IS ON THE SERVER AND IS THE RECORD FILTER. The "our
   picks on this team" read counts what a pick WAS -- `signal_type = 'BET'`,
   a real result, game-level -- and never joins the threshold table
   (CLAUDE.md §1c). Measured 2026-09-20: 2,840 pick rows in one MLB team's
   last 25 games, 13 of them settled game-level BETs; the phone must see 13.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
SCREEN = MOBILE / "src" / "screens" / "TeamStatsScreen.tsx"
HOOK = MOBILE / "src" / "hooks" / "useTeamDetail.ts"
LIB = MOBILE / "src" / "lib" / "teamDetail.ts"
BOARD = MOBILE / "src" / "components" / "TeamsBoard.tsx"
STATS = MOBILE / "src" / "screens" / "StatsScreen.tsx"
QUERIES = MOBILE / "src" / "lib" / "queries.ts"
TYPES = MOBILE / "src" / "types" / "index.ts"
APP = MOBILE / "App.tsx"
MIGRATION = ROOT / "data" / "migrations" / "anon_read_public_betting_2026_09_20.sql"


def _read(p: Path) -> str:
    # Explicit encoding: this repo runs on Windows (CLAUDE.md §7).
    return p.read_text(encoding="utf-8")


# ── 1. the route ───────────────────────────────────────────────────────────


def test_the_board_row_opens_the_team_page():
    board = _read(BOARD)
    assert "onOpenTeam" in board, "TeamsBoard lost its onOpenTeam prop"
    # The tap target is the name/record block, a labelled button, and the
    # LINE pill keeps its own press -- both Pressables must be present.
    assert re.search(r"accessibilityLabel=\{\s*onOpen\s*\?\s*`\$\{row\.team\}", board), (
        "the team row's Pressable must carry an accessibilityLabel naming the team"
    )
    stats = _read(STATS)
    assert "navigation.navigate('TeamStats'" in stats, (
        "StatsScreen no longer navigates the board's onOpenTeam to the TeamStats route"
    )


def test_the_route_is_declared_and_registered():
    types = _read(TYPES)
    assert re.search(r"TeamStats:\s*\{", types), "RootStackParamList has no TeamStats entry"
    app = _read(APP)
    assert 'name="TeamStats"' in app, "App.tsx does not register the TeamStats screen"
    assert "TeamStatsScreen" in app
    assert SCREEN.exists()


def test_the_screen_is_pushed_not_focus_aware():
    """The app-root rule (.claude/rules/frontend.md): plain effects only."""
    for p in (SCREEN, HOOK):
        # The CALL, not the word: the hook's header names the rule it follows.
        assert "useFocusEffect(" not in _read(p), f"{p.name} must not call useFocusEffect"


# ── 2. the reads ───────────────────────────────────────────────────────────


def test_public_betting_policy_migration_exists_and_is_select_only():
    assert MIGRATION.exists(), "the public_betting anon-read policy migration is missing"
    sql = _read(MIGRATION)
    assert re.search(r"CREATE POLICY .* ON public\.public_betting", sql)
    assert "FOR SELECT" in sql
    assert not re.search(r"FOR (INSERT|UPDATE|DELETE|ALL)", sql), (
        "public_betting is display data: the app may read it, never write it"
    )


def test_the_new_relations_are_in_the_manifest():
    from data.anon_readable import ANON_READABLE

    assert "public_betting" in ANON_READABLE
    assert "nfl_team_game_stats" in ANON_READABLE


def test_every_team_page_read_names_its_relation_literally():
    """The tripwire in test_anon_readable.py only sees literal `.from('x')`."""
    q = _read(QUERIES)
    for fn, rel in (
        ("fetchTeamRecentGamesForSport", "games"),
        ("fetchHeadToHead", "games"),
        ("fetchOpeningLine", "odds"),
        ("fetchGameLineRowsAllMarkets", "v_latest_odds_all_books"),
        ("fetchPublicSplits", "public_betting"),
        ("fetchNflTeamGameStats", "nfl_team_game_stats"),
        ("fetchSettledGamePicksForGames", "picks"),
    ):
        m = re.search(rf"export async function {fn}\(.*?\n\}}\n", q, re.S)
        assert m, f"{fn} is missing from queries.ts"
        assert f".from('{rel}')" in m.group(0), f"{fn} must read '{rel}' by literal name"


def test_recent_games_are_scoped_by_sport():
    """'BUF' is Buffalo in the NFL and the NHL; the form strip must not mix them."""
    q = _read(QUERIES)
    m = re.search(r"export async function fetchTeamRecentGamesForSport\(.*?\n\}\n", q, re.S)
    assert m
    assert ".eq('sport', sport)" in m.group(0)


# ── 3. the record filter ───────────────────────────────────────────────────


def test_the_pick_record_read_is_the_record_filter_on_the_server():
    q = _read(QUERIES)
    m = re.search(r"export async function fetchSettledGamePicksForGames\(.*?\n\}\n", q, re.S)
    assert m, "fetchSettledGamePicksForGames is missing"
    body = m.group(0)
    assert ".eq('signal_type', 'BET')" in body, "the record is BET rows, filtered server-side"
    assert ".in('result', ['WIN', 'LOSS', 'PUSH'])" in body, "the record is settled rows"
    assert ".is('player_id', null)" in body, "props are bets on players, not on the team"
    assert "model_action_thresholds" not in body, (
        "a record query never joins the threshold table (CLAUDE.md §1c)"
    )


def test_units_never_price_an_unpriced_pick():
    """profit_flat fabricates -110 for a pick with no price (CLAUDE.md §6), and
    the priced-line rule is read through lib/decisionPrice, never the columns."""
    lib = _read(LIB)
    m = re.search(r"function addPick\(.*?\n\}\n", lib, re.S)
    assert m
    body = m.group(0)
    assert "hasPricedLine(p)" in body
    assert "unpriced" in body


def test_results_are_units_never_dollars():
    """CLAUDE.md §4: results are always in units."""
    for p in (SCREEN, LIB, HOOK):
        src = _read(p)
        assert "formatCurrency" not in src, f"{p.name} formats a result as money"
        assert not re.search(r"\$\d", src), f"{p.name} prints a dollar figure"


def test_no_paper_trading_copy():
    """CLAUDE.md §2 / .claude/rules/frontend.md: the platform is live."""
    for p in (SCREEN, HOOK, LIB):
        assert "paper" not in _read(p).lower(), f"{p.name} mentions paper trading"


def test_the_nfl_spread_sign_is_normalised_the_way_the_board_does_it():
    """nflverse spread_line is positive when HOME is favoured -- the opposite of
    odds.spread_home. The board SQL verified the sign (favourites win 78%, not
    32%); the page's cover mark has to use the same normalisation."""
    lib = _read(LIB)
    m = re.search(r"export function nflCoverMarks\(.*?\n\}\n", lib, re.S)
    assert m
    assert "r.is_home ? -spreadLine : spreadLine" in m.group(0)
    assert "margin + teamSpread" in m.group(0)

"""The NBA game matchup page (Matt, 2026-11-23).

Matt: "we don't have a nice match up view with games to figure out who to
bet". The existing game screen (screens/ScoreboardGameScreen.tsx) becomes the
matchup page for the sports in lib/gameMatchup MATCHUP_SPORTS (NBA first), and
three places open it: the Stats tab's Teams row game line, the Picks
scoreboard (already), and a pick's detail page.

What is pinned:

1. THE PURE HALF (lib/gameMatchup.ts), run under node: the side that ranks
   better gets the edge (Def Rtg is better LOW, so the bigger number must not
   win), the last-10 ATS / O-U counts, rest days, the under shop at one number,
   and the pick filter — open picks by the action test, graded ones by the
   record test, other games' picks never.
2. "NO PICK" IS THE SIGNALS BOARD'S ANSWER, NOT A LEAN. The page shows the
   Signals board's own cards for this game through the same filters
   (passesActionFilter / passesRecordFilter / isUnlockedPreview), or "No pick"
   (Matt: "No pick, just stats in their matchup"). It never reads an edge off
   a NONE row.
3. THE THREE WAYS IN ARE WIRED.
4. lib/matchup.ts (the PLAYER grade) is untouched: the game helpers live in
   their own file.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests._node import NODE, node_strips_types

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile" / "src"
LIB = SRC / "lib" / "gameMatchup.ts"
SCREEN = SRC / "screens" / "ScoreboardGameScreen.tsx"
HOOK = SRC / "hooks" / "useMatchup.ts"
SECTIONS = SRC / "components" / "MatchupSections.tsx"
BOARD = SRC / "components" / "TeamsBoard.tsx"
STATS = SRC / "screens" / "StatsScreen.tsx"
DETAIL = SRC / "screens" / "PickDetailScreen.tsx"
QUERIES = SRC / "lib" / "queries.ts"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _run(tmp_path: Path, body: str):
    (tmp_path / "gameMatchup.ts").write_text(_read(LIB), encoding="utf-8")
    script = "import * as m from './gameMatchup.ts';" + body
    r = subprocess.run(
        [NODE, "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


needs_node = pytest.mark.skipif(not node_strips_types(), reason="needs node >= 22.6")


# ── 1. the pure half ───────────────────────────────────────────────────────

@needs_node
def test_the_edge_goes_to_the_better_rank_not_the_bigger_number(tmp_path):
    out = _run(tmp_path, """
      const d = (key, better) => ({ key, label: key, better });
      const away = [
        { def: d('net_rating', 'high'), value: 9.4, rank: 3 },
        { def: d('def_rating', 'low'), value: 117.1, rank: 28 },
        { def: d('pace', null), value: 101.4, rank: null },
        { def: d('ats_pct', 'high'), value: 0.5, rank: 12 },
      ];
      const home = [
        { def: d('net_rating', 'high'), value: -7.8, rank: 27 },
        { def: d('def_rating', 'low'), value: 102.4, rank: 1 },
        { def: d('pace', null), value: 102.7, rank: null },
        { def: d('ats_pct', 'high'), value: 0.5, rank: 12 },
      ];
      console.log(JSON.stringify(m.pairRanks(away, home).map((p) => [p.key, p.edge])));
    """)
    assert out == [
        ["net_rating", "away"],
        # 117.1 is the bigger number, and the WORSE defence: home has the edge.
        ["def_rating", "home"],
        # No direction, no edge.
        ["pace", None],
        # A tie is no edge.
        ["ats_pct", None],
    ]


@needs_node
def test_cover_summary_counts_the_newest_n_and_only_games_with_a_line(tmp_path):
    out = _run(tmp_path, """
      const r = (d, ats, ou) => ({ game_id: d, game_date: d, is_home: true, ats, ou });
      const rows = [
        r('2026-11-01', 'L', 'U'),   // oldest: outside a last-3 window
        r('2026-11-05', 'W', 'O'),
        r('2026-11-03', null, null), // no stored line
        r('2026-11-07', 'P', 'P'),
      ];
      const s = m.coverSummary(rows, 3);
      console.log(JSON.stringify([s.games, s.atsGames, s.atsW, s.atsL, s.atsP, m.formatAts(s), m.formatOu(s),
        m.formatAts(m.coverSummary([], 10))]));
    """)
    assert out == [3, 2, 1, 0, 1, "1-0-1", "1o-0u-1p", "—"]


@needs_node
def test_rest_days_count_the_days_off(tmp_path):
    out = _run(tmp_path, """
      console.log(JSON.stringify([
        m.restDays('2026-11-22', '2026-11-23'),
        m.restDays('2026-11-20', '2026-11-23'),
        m.restDays(null, '2026-11-23'),
        m.restDays('2026-11-23', '2026-11-23'),
        m.restText(0), m.restText(1), m.restText(2),
      ]));
    """)
    assert out == [0, 2, None, None, "Back-to-back", "1 day rest", "2 days rest"]


@needs_node
def test_the_under_shops_only_at_the_anchor_number(tmp_path):
    out = _run(tmp_path, """
      const t = (book, line, under) => ({ game_id: 'G', market: 'totals', bookmaker: book, total_line: line, under_price: under });
      const rows = [
        t('fanduel', 224.5, -105),
        t('draftkings', 225.5, -110),   // the member's first book: the anchor
        t('betmgm', 225.5, -102),       // same number, better price: wins
        t('caesars', 224.5, +100),      // better price at ANOTHER number: a different bet
        t('pinnacle', 225.5, +120),     // not one of the member's books
        { ...t('betmgm', 225.5, -101), game_id: 'OTHER' },
      ];
      const b = m.bestUnder(rows, 'G', ['draftkings', 'fanduel', 'betmgm', 'caesars']);
      console.log(JSON.stringify([b.row.bookmaker, b.price, b.line, m.bestUnder(rows, 'G', ['bet365'])]));
    """)
    assert out == ["betmgm", -102, 225.5, None]


@needs_node
def test_game_picks_are_the_signals_board_s_picks_for_this_game(tmp_path):
    out = _run(tmp_path, """
      const p = (id, game_id, result, passes, record) => ({ id, pick: { game_id, result }, passes, record });
      const open = [
        p('open-bet', 'G', null, true, false),
        p('open-none', 'G', null, false, false),     // below the bar: not shown, no lean
        p('other-game', 'H', null, true, true),
      ];
      const finished = [
        p('graded-in-record', 'G', 'WIN', false, true),
        p('graded-not-in-record', 'G', 'LOSS', true, false),
        p('finished-ungraded', 'G', null, true, false),
      ];
      const out = m.gamePicks('G', open, finished, { action: (d) => d.passes, record: (d) => d.record });
      console.log(JSON.stringify(out.map((d) => d.id)));
    """)
    assert out == ["open-bet", "graded-in-record", "finished-ungraded"]


@needs_node
def test_injuries_sort_worst_status_first(tmp_path):
    out = _run(tmp_path, """
      const rows = [
        { team: 'MIN', status: 'Day-To-Day', player_name: 'A' },
        { team: 'BKN', status: 'Out', player_name: 'Z' },
        { team: 'MIN', status: 'Out', player_name: 'C' },
        { team: 'MIN', status: 'Out', player_name: 'B' },
      ];
      console.log(JSON.stringify(m.teamInjuries(rows, 'MIN').map((r) => r.player_name)));
    """)
    assert out == ["B", "C", "A"]


def test_the_pure_half_imports_nothing_from_the_app():
    # node --experimental-strip-types cannot resolve '@/': one import and every
    # test above stops running.
    assert "from '@/" not in _read(LIB)


# ── 2. "No pick" is the Signals board's answer ─────────────────────────────

def test_the_page_uses_the_signals_board_filters_and_cards():
    s = _read(SCREEN)
    assert "useTodayPicks(game?.game_date)" in s
    assert "passesActionFilter(d.pick) && !isUnlockedPreview(d.pick)" in s
    assert "passesRecordFilter(d.pick) && !isUnlockedPreview(d.pick)" in s
    assert "<PickCard" in s and 'layout="signals"' in s
    assert "No pick from our models on this game." in s
    # Never a lean below the bar: the page reads no edge of its own.
    assert "decisionEdge" not in s and ".edge" not in s


def test_the_page_is_not_focus_aware_beyond_its_own_poll():
    # The sections load through useSection (plain useEffect), like the team page.
    h = _read(HOOK)
    assert "import { useFocusEffect" not in h and "useFocusEffect(" not in h
    assert "useSection" in h


def test_the_new_read_is_scoped_bounded_and_names_its_relation():
    q = _read(QUERIES)
    i = q.index("export async function fetchTeamFullGameCovers")
    body = q[i:q.index("\n}\n", i)]
    assert ".from('team_period_results')" in body
    for clause in (".eq('sport', sport)", ".eq('team', team)", ".eq('period', 'FG')", ".lt('game_date', beforeDate)", ".limit(limit)"):
        assert clause in body, clause


# ── 3. the three ways in ───────────────────────────────────────────────────

def test_the_teams_row_game_line_opens_the_matchup():
    b = _read(BOARD)
    assert "onOpenGame(slateGame.game.game_id)" in b
    s = _read(STATS)
    assert "onOpenGame={hasMatchupView(sport) ? (gameId) => navigation.navigate('ScoreboardGame', { gameId })" in s


def test_the_pick_detail_page_links_to_the_matchup():
    d = _read(DETAIL)
    assert "hasMatchupView(game.sport)" in d
    assert "navigation.navigate('ScoreboardGame', { gameId: game.game_id }, { pop: true })" in d


def test_the_picks_scoreboard_still_opens_the_game():
    assert "navigation.navigate('ScoreboardGame', { gameId })" in _read(SRC / "screens" / "PicksHomeScreen.tsx")


# ── 4. the player grade is untouched ───────────────────────────────────────

def test_the_player_matchup_module_still_exports_its_grade():
    m = _read(SRC / "lib" / "matchup.ts")
    for name in ("gradeOpponentDefence", "matchupStrengthSpoken", "normalCdf"):
        assert name in m, name

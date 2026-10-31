"""The app reads a first-half total as the first two quarters' points
(nba_first_half_total_luck).

The model bets the first half's over, and its picks settle on Q1 + Q2. The odds
table stores those prices under 'totals_h1', with the number in total_line, the
same column a game total uses. Each place the app turns a model id or a market into
prices or a line has to know that:

  * lib/markets.ts gameMarketForModel: 'totals_h1'. The id has none of the
    substrings the mapping looks for, so without its own case it fell to 'h2h'.
  * lib/teamDetail.ts teamPickRecords: a first-half total is neither side of the
    game nor its total. Filed under "Overs" it would put a different bet on a number
    about half the size into the game-total record on BOTH teams' pages.
  * lib/markets.ts splitPickTitle: the card's bold line is the bet after the
    label's dash; movement is read at the deciding book's own number.
  * lib/markets.ts pickRowTitle and pickRowMatchup, components/PickRowTitle.tsx: a
    row on a model's page or the tracked list titles the bet and clips its middle,
    with the matchup on its own line. The whole label on one line lost the side
    and number first at larger text.
  * lib/signalsCard.ts signalsBetHeadline: "First Half Over 112.5", never a bare
    "Over 112.5", which reads as the game total.
  * lib/queries.ts MAIN_GAME_ODDS_MARKETS: the prices are read, the alternate rung
    is not.
  * lib/modelMeta.ts: its own chip and name, no picker slot, a probability note, and
    a page that says it posts about an hour before tip.

These run the real modules under node's type stripping, like
tests/test_mobile_team_total.py; mobile/scripts/verify_preferred_book.ts,
verify_pick_timing.ts, verify_paused_catalog.ts and verify_pick_card.ts carry the
same cases for `npx tsx`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_mobile_team_total import (MARKETS_FILES, META_FILES, TEAM_FILES,  # noqa: F401
                                          VIEW_FILES, _run, node)

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "mobile" / "src" / "lib"

H1 = """
const H1_LABEL = 'BOS @ MIL — First Half Over 112.5';
const H1_PICK = { ...PICK, model_id: 'nba_first_half_total_luck', pick_side: 'over',
  pick_label: H1_LABEL, scored_line: 112.5, dk_odds: -110, decision_odds: -105 };
"""


@node
def test_the_pick_reads_the_first_half_market_and_its_number(tmp_path):
    _run(tmp_path, MARKETS_FILES, H1 + """
import { gameMarketForModel, marketClassForModel, lineFromSnapshot, splitPickTitle, pickRowTitle, pickRowMatchup, rowIsSameBet } from './markets.ts';
eq(gameMarketForModel('nba_first_half_total_luck'), 'totals_h1', 'market');
eq(marketClassForModel('nba_first_half_total_luck'), 'game_total', 'parlay class');
const fd = { bookmaker: 'fanduel', total_line: 112.5, over_price: -108, under_price: -112 };
eq(lineFromSnapshot(fd, 'totals_h1'), 112.5, 'first-half line');
eq(rowIsSameBet(H1_PICK, fd, 'totals_h1'), true, 'the same number is the same bet');
eq(rowIsSameBet(H1_PICK, { ...fd, total_line: 113.5 }, 'totals_h1'), false, 'another number is not');
eq(splitPickTitle(H1_PICK), { primary: 'First Half Over 112.5', secondary: null }, 'the card');
// A row's title is the bet, so the number survives larger text. The bet alone
// names no team, so the matchup is quoted onto its own caption line.
eq(pickRowTitle(H1_PICK), 'First Half Over 112.5', 'the row');
eq(pickRowMatchup(H1_PICK), 'BOS @ MIL', 'the row caption');
// The team total's own behaviour has not moved.
eq(splitPickTitle(PICK), { primary: 'MIL Team Total Under 115.5', secondary: null }, 'team total card');
eq(pickRowTitle(PICK), 'MIL Team Total Under 115.5', 'team total row');
eq(pickRowMatchup(PICK), null, 'a team total names its team, so no caption');
// An NFL opener's "TB @ CAR — CAR -3" is neither.
eq(pickRowTitle({ pick_label: 'TB @ CAR — CAR -3' }), 'TB @ CAR — CAR -3', 'opener row');
eq(pickRowMatchup({ pick_label: 'TB @ CAR — CAR -3' }), null, 'opener has no caption');
eq(pickRowMatchup({ pick_label: 'Roquan Smith Under 9.5 Tackles' }), null, 'a prop has no caption');
""")


@node
def test_the_line_movement_card_shows_the_first_half_line(tmp_path):
    """Over 112.5 at FanDuel, then 113.5: the card lists both numbers and calls the
    rise against the over, as it does for a game total."""
    _run(tmp_path, VIEW_FILES, H1 + """
import { lineMovementView } from './lineMovementView.ts';
import { sincePick, HISTORY_ROWS } from './lineHistory.ts';
const P = { ...H1_PICK, dk_odds: null, line_book: 'fanduel' };
const tot = (snapshot_at, total_line, over_price, under_price) => ({ snapshot_at, total_line, over_price, under_price });
const rows = [tot('2026-11-01T22:34:00Z', 112.5, -105, -115), tot('2026-11-01T22:50:00Z', 113.5, -110, -110)];
const win = sincePick(rows, P.created_at, P.game_time, HISTORY_ROWS, Date.parse('2026-11-01T23:00:00Z'));
const v = lineMovementView(P, win, 'totals_h1', false);
eq(v.showLineCol, true, 'line column');
eq(v.rows.map((r) => r.lineText), ['112.5', '113.5'], 'rows, the price at the pick first');
eq([v.verdict.tone, v.verdict.label], ['against', 'Line moved 112.5 → 113.5 against you'], 'verdict');
""")


@node
def test_the_team_page_leaves_the_first_half_out_of_every_tile(tmp_path):
    _run(tmp_path, TEAM_FILES, H1 + """
import { teamPickRecords } from './teamDetail.ts';
const games = [{ game_id: PICK.game_id, game_date: PICK.game_date, home_team: 'MIL', away_team: 'BOS' }];
const bet = { ...H1_PICK, result: 'WIN', profit_flat: 95, decision_odds: -105 };
for (const team of ['MIL', 'BOS']) {
  const r = teamPickRecords([bet], games, team);
  eq([r.settled, r.firstHalves, r.teamTotals, r.over.wins, r.under.wins, r.on.wins, r.against.wins],
     [1, 1, 0, 0, 0, 0, 0], `${team}'s page`);
}
// A full-game over stays in the Overs tile.
const full = { ...bet, model_id: 'nba_total_luck', pick_label: 'MIL vs BOS Over 225.5', scored_line: 225.5 };
const r = teamPickRecords([full], games, 'MIL');
eq([r.settled, r.firstHalves, r.over.wins], [1, 0, 1], 'a full-game over');
""")


@node
def test_the_model_has_its_own_chip_and_no_picker_slot(tmp_path):
    _run(tmp_path, META_FILES, """
import { MODEL_META, betSlotForModel, modelLong, modelPageTiming, modelProbabilityNote } from './modelMeta.ts';
import { pickTimingInfo } from './markets.ts';
const m = MODEL_META.nba_first_half_total_luck;
eq([m.type, m.shortLabel, m.statKey, m.statLabel], ['game', '1H O/U', null, ''], 'entry');
eq(modelLong('nba_first_half_total_luck'), 'NBA First Half Totals', 'long name');
eq(betSlotForModel('nba_first_half_total_luck', 'game'), null, 'not a picker slot');
const note = modelProbabilityNote('nba_first_half_total_luck');
eq([note.includes('upper bound'), note.includes('about 6 percentage')], [true, true], note);
const t = modelPageTiming('nba_first_half_total_luck');
eq([t.title, t.empty.includes('about an hour before tip-off')], ['Checked once per game', true], 'page');
const info = pickTimingInfo({ ...PICK, model_id: 'nba_first_half_total_luck', pick_side: 'over',
  pick_label: 'BOS @ MIL — First Half Over 112.5', scored_line: 112.5 });
eq([info.kind, info.note.startsWith('Posted once and never re-priced'), info.note.includes('Void')],
   ['posted', true, false], 'timing');
""")


@node
def test_the_signals_card_says_first_half(tmp_path):
    _run(tmp_path, MARKETS_FILES + ["signalsCard.ts"], """
import { signalsBetHeadline } from './signalsCard.ts';
eq(signalsBetHeadline({ side: 'over', line: 112.5, market: 'totals_h1', homeTeam: 'MIL', awayTeam: 'BOS' }),
   'First Half Over 112.5', 'the first half');
eq(signalsBetHeadline({ side: 'over', line: 225.5, market: 'totals', homeTeam: 'MIL', awayTeam: 'BOS' }),
   'Over 225.5', 'the game total is unchanged');
""")


def test_every_pick_row_titles_through_the_component_that_keeps_the_number():
    """The JSX cannot run under node's type stripping, so this reads the source. Only
    a first half clips its middle: an opener's number sits in the middle of its label.
    """
    comp = (ROOT / "mobile/src/components/PickRowTitle.tsx").read_text(encoding="utf-8")
    assert "numberOfLines={1} ellipsizeMode={matchup ? 'middle' : 'tail'}" in comp
    assert "{matchup ? <Text style={matchupStyle}>{matchup}</Text> : null}" in comp
    for screen, rows in (("BuiltInModelDetailScreen.tsx", 2), ("PerformanceScreen.tsx", 1)):
        src = (ROOT / "mobile/src/screens" / screen).read_text(encoding="utf-8")
        assert src.count("<PickRowTitle pick=") == rows, screen
        assert "pickRowTitle(" not in src, screen


def test_the_first_half_is_read_with_the_main_game_markets_and_its_alternates_are_not():
    src = (LIB / "queries.ts").read_text(encoding="utf-8")
    i = src.index("const MAIN_GAME_ODDS_MARKETS = [")
    block = src[i:src.index("] as const;", i)]
    assert "'totals_h1'," in block
    assert "alternate" not in block


def test_the_mobile_threshold_is_generated_from_config():
    src = (LIB / "thresholds.generated.ts").read_text(encoding="utf-8")
    assert "nba_first_half_total_luck: { min_prob: 0, min_edge: 0, min_odds: -200 }," in src


@pytest.mark.parametrize("path", ["mobile/src/lib/modelMeta.ts", "mobile/src/lib/markets.ts",
                                  "mobile/src/lib/signalsCard.ts", "mobile/src/lib/teamDetail.ts",
                                  "models/nba_first_half_total_luck.py",
                                  "scripts/nba_first_half_total_luck_card.py"])
def test_nothing_of_this_model_writes_a_first_quarter(path):
    """Its copy says first half; a first-quarter label would be another bet."""
    assert "1Q" not in (ROOT / path).read_text(encoding="utf-8")

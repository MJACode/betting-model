"""The app reads a team total as ONE team's points (nba_team_total_luck).

nba_team_total_luck bets the HOME team's own points, under, and its picks
settle on the home team's final score (tracking/paper_tracker). The odds table
stores those prices under 'team_totals_home', with the number in total_line,
the same column a game total uses. Each place the app turns a model id or a
market into prices or a line has to know that:

  * lib/markets.ts gameMarketForModel: 'team_totals_home'. The id has none of
    the substrings the mapping looks for, so without its own case it fell to
    'h2h' and every price, line-shop and movement read took moneyline rows.
  * lineFromSnapshot: total_line for a team total. It read `line` (the prop
    column), which is empty on these rows, so no other book's row was ever
    the same bet and the movement card had no line.
  * lib/lineMovementView.ts: the line column shows for a team total.
  * lib/teamDetail.ts teamPickRecords: a team-total pick is neither side of
    the game nor its total. Filed under "Unders" it would put a different bet
    on a different number into the game-total record on BOTH teams' pages,
    so it stays out of all four tiles. It is still a posted bet in the team's
    games, so it counts in the page's bet total (`settled`, `teamTotals`).
  * lib/markets.ts splitPickTitle: the card's bold line is the bet after the
    label's dash; movement is read at the deciding book's own number.
  * lib/modelMeta.ts: its own chip and name, no picker slot, a probability
    note, and a page that says it posts about an hour before tip.

These run the real modules under node's type stripping, like
tests/test_mobile_line_movement.py; mobile/scripts/verify_preferred_book.ts,
verify_pick_timing.ts and verify_paused_catalog.ts carry the same cases for
`npx tsx`.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "mobile" / "src" / "lib"

from tests._node import NODE, node_strips_types  # noqa: E402

# markets.ts and everything it imports at run time; type-only imports are erased.
MARKETS_FILES = ["markets.ts", "format.ts", "thresholds.ts", "thresholds.generated.ts",
                 "decisionPrice.ts", "discordPublish.ts", "clvBet.ts"]
VIEW_FILES = MARKETS_FILES + ["lineMovementView.ts", "lineHistory.ts"]
TEAM_FILES = MARKETS_FILES + ["teamDetail.ts", "teamStatCatalog.ts", "teamBoard.ts"]
META_FILES = MARKETS_FILES + ["modelMeta.ts"]

PRELUDE = """
const eq = (got, want, what) => {
  if (JSON.stringify(got) !== JSON.stringify(want)) throw new Error(`${what}: ${JSON.stringify(got)} !== ${JSON.stringify(want)}`);
};
const LABEL = 'BOS @ MIL — MIL Team Total Under 115.5';
const PICK = {
  pick_id: 1, game_id: 'NBA_2026-11-01_BOS_MIL', model_id: 'nba_team_total_luck', sport: 'NBA',
  game_date: '2026-11-01', pick_side: 'under', signal_type: 'BET', is_live: false, pick_label: LABEL,
  dk_odds: -115, scored_line: 115.5, decision_odds: -112, decision_edge: 0.1, decision_book: 'fanduel',
  line_book: null, player_id: null, created_at: '2026-11-01 22:35:10.5+00', game_time: '2026-11-01T23:30:00+00:00',
};
"""

node = pytest.mark.skipif(not node_strips_types(), reason="node >= 22.6 not available")


def _run(tmp_path: Path, files: list[str], script: str) -> None:
    """Copy lib modules with node-resolvable imports ('./x' and '@/lib/x'
    become './x.ts'), then run `script`."""
    for name in files:
        src = (LIB / name).read_text(encoding="utf-8")
        src = re.sub(r"from '\./([\w.]+)';", r"from './\1.ts';", src)
        src = re.sub(r"from '@/lib/([\w.]+)';", r"from './\1.ts';", src)
        (tmp_path / name).write_text(src, encoding="utf-8")
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "--input-type=module", "-e", PRELUDE + script],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr


@node
def test_the_pick_reads_the_home_team_total_market_and_its_number(tmp_path):
    _run(tmp_path, MARKETS_FILES, """
import { gameMarketForModel, marketClassForModel, lineFromSnapshot, splitPickTitle, rowIsSameBet } from './markets.ts';
eq(gameMarketForModel('nba_team_total_luck'), 'team_totals_home', 'market');
eq(marketClassForModel('nba_team_total_luck'), 'game_total', 'parlay class');
const fd = { bookmaker: 'fanduel', total_line: 115.5, over_price: -108, under_price: -112 };
eq(lineFromSnapshot(fd, 'team_totals_home'), 115.5, 'home team total line');
eq(lineFromSnapshot({ total_line: 104.5 }, 'team_totals_away'), 104.5, 'away team total line');
eq(rowIsSameBet(PICK, fd, 'team_totals_home'), true, 'the same number is the same bet');
eq(rowIsSameBet(PICK, { ...fd, total_line: 114.5 }, 'team_totals_home'), false, 'another number is not');
// One line on the card, not a player-prop caption "MIL Team Total" over "Under 115.5";
// and the bet, word for word from the label, not the matchup the card's header
// already shows (on a phone the whole label clipped "MIL Team Total" away).
eq(splitPickTitle({ pick_label: LABEL }), { primary: 'MIL Team Total Under 115.5', secondary: null }, 'title');
eq(splitPickTitle({ pick_label: 'MIL vs BOS Over 225.5' }), { primary: 'MIL vs BOS Over 225.5', secondary: null }, 'a game total stays whole');
eq(splitPickTitle({ pick_label: 'HOU @ TEN — TEN +9.5 (Opener +2 vs Pinnacle, BR)' }).primary, 'HOU @ TEN — TEN +9.5 (Opener +2 vs Pinnacle, BR)', 'another dashed label stays whole');
""")


@node
def test_the_line_movement_card_shows_the_team_total_line(tmp_path):
    """Under 115.5 at FanDuel, then 114.5: the card lists both numbers and
    calls the drop against the under, as it does for a game total. (The
    number is FanDuel's own: DraftKings did not hang 115.5, so the card wrote
    line_book, as scripts/nba_total_luck_card.py does.)"""
    _run(tmp_path, VIEW_FILES, """
import { lineMovementView } from './lineMovementView.ts';
import { sincePick, HISTORY_ROWS } from './lineHistory.ts';
const P = { ...PICK, dk_odds: null, line_book: 'fanduel' };
const tot = (snapshot_at, total_line, over_price, under_price) => ({ snapshot_at, total_line, over_price, under_price });
const rows = [tot('2026-11-01T22:34:00Z', 115.5, -108, -112), tot('2026-11-01T22:50:00Z', 114.5, -110, -110)];
const win = sincePick(rows, P.created_at, P.game_time, HISTORY_ROWS, Date.parse('2026-11-01T23:00:00Z'));
const v = lineMovementView(P, win, 'team_totals_home', false);
eq(v.showLineCol, true, 'line column');
eq(v.rows.map((r) => r.lineText), ['115.5', '114.5'], 'rows, the price at the pick first');
eq([v.verdict.tone, v.verdict.label], ['against', 'Line moved 115.5 → 114.5 against you'], 'verdict');
""")


@node
def test_the_team_page_leaves_the_team_total_out_of_every_tile(tmp_path):
    """MIL's under (the team total) won; the full-game over on the same game
    lost. On both teams' pages only the full-game over is in a tile; the team
    total is still a posted bet in the team's games, so it counts in the bet
    total and is named as left out. A page whose only bet is a team total
    does not read "No posted picks". Watched failing when it was dropped."""
    _run(tmp_path, TEAM_FILES, """
import { teamPickRecords } from './teamDetail.ts';
const games = [{ game_id: PICK.game_id, home_team: 'MIL', away_team: 'BOS' }];
const settled = { result: 'WIN', profit_flat: 89.29, condition_status: null, downgrade_reason: null };
const picks = [
  { ...PICK, ...settled },
  { ...PICK, ...settled, pick_id: 2, model_id: 'nba_total_luck', pick_side: 'over', scored_line: 225.5,
    pick_label: 'MIL vs BOS Over 225.5', result: 'LOSS', profit_flat: -100 },
];
for (const team of ['MIL', 'BOS']) {
  const r = teamPickRecords(picks, games, team);
  eq([r.settled, r.teamTotals, r.under.wins, r.under.losses, r.over.losses, r.on.wins, r.against.wins],
     [2, 1, 0, 0, 1, 0, 0], `${team}'s page`);
  const only = teamPickRecords([picks[0]], games, team);
  eq([only.settled, only.teamTotals, only.under.wins, only.over.losses], [1, 1, 0, 0], `${team}'s page, team total only`);
}
const unread = teamPickRecords([{ ...picks[0], discordPublish: 'unknown' }], games, 'MIL');
eq(unread.ledgerUnread, true, 'an unread ledger stamp on a team total is still reported');
""")


@node
def test_the_model_has_its_own_chip_and_no_picker_slot(tmp_path):
    _run(tmp_path, META_FILES, """
import { MODEL_META, betSlotForModel, modelLong, modelPageTiming, modelProbabilityNote } from './modelMeta.ts';
const m = MODEL_META.nba_team_total_luck;
eq([m.type, m.shortLabel, m.statKey, m.statLabel], ['game', 'TT Luck', null, ''], 'entry');
eq(modelLong('nba_team_total_luck'), 'Home Team Total (Unders)', 'long name');
eq(betSlotForModel('nba_team_total_luck', 'game'), null, 'not a picker slot');
// The probability is the graded seasons' own win rate: the note says to plan on less.
const note = modelProbabilityNote('nba_team_total_luck');
eq([note.includes('upper bound'), note.includes('nearer 8%')], [true, true], note);
// Its page says when it fills: each game is checked once, about an hour before
// tip, and only some games get a bet; not the morning run.
for (const id of ['nba_team_total_luck', 'nba_total_luck', 'nba_prop_market', 'nba_prop_projection']) {
  const t = modelPageTiming(id);
  eq([t.title, t.empty.includes('about an hour before tip-off'), t.empty.includes('only some'),
      t.body.includes('hourly'), t.note],
     ['Checked once per game', true, true, false, 'Posted about an hour before tip-off and never re-priced.'], id);
}
eq([modelPageTiming('mlb_over_under').title, modelPageTiming('mlb_over_under').note],
   ['Picks lock for the day', "Locked for the day once scored — won't change again until the game ends."],
   'every other model keeps its copy');
""")


@node
def test_a_move_off_the_deciding_book_s_number_is_against_the_bet(tmp_path):
    """FanDuel decided Under 115.5 at -112 while DraftKings also hung 115.5,
    so the card left line_book empty. FanDuel then moved to 114.5 at -105:
    a point against the under. The stored line is the deciding book's own
    number (both NBA totals cards), so the move is read at that book: a red
    'skip', never a green price move in the bettor's favour. The full-game
    overs card writes the same row. Watched failing ('good') before both ids
    were added to BET_BOOK_LINE_MODELS."""
    _run(tmp_path, MARKETS_FILES, """
import { movementFromLatest, movementFromSameBookHistory } from './markets.ts';
const cases = [
  [{ ...PICK }, 'team_totals_home', { bookmaker: 'fanduel', total_line: 114.5, over_price: -115, under_price: -105 }],
  [{ ...PICK, model_id: 'nba_total_luck', pick_side: 'over', scored_line: 225.5,
     pick_label: 'MIL vs BOS Over 225.5', dk_odds: -108, decision_odds: -110 },
   'totals', { bookmaker: 'fanduel', total_line: 226.5, over_price: -105, under_price: -115 }],
];
for (const [pick, market, now] of cases) {
  const dk = { market, total_line: pick.scored_line, over_price: -110, under_price: -110 };
  for (const [what, m] of [['card chip', movementFromLatest(pick, dk, [now])],
                           ['detail card', movementFromSameBookHistory(pick, now, market)]]) {
    eq([m && m.severity, m && m.lineMovedAgainst], ['skip', true], `${pick.model_id} ${what}`);
  }
}
""")

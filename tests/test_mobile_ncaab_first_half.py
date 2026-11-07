"""The app reads an NCAAB first-half spread as the first half's margin
(ncaab_first_half_spread).

The model bets one side of the first half's spread, and its picks settle on the
first half's score. The odds table stores those prices under 'spreads_h1', with
the HOME number in spread_home, the column a game spread uses. Each place the
app turns a model id or a market into prices or a line has to know that:

  * lib/markets.ts gameMarketForModel: 'spreads_h1'. The id contains 'spread',
    so without its own case it read the full-game spread rows, a number about
    twice as big.
  * lib/signalsCard.ts signalsBetHeadline: "First Half Duke +3.5", never a bare
    "Duke +3.5", which reads as the game's spread.
  * lib/teamDetail.ts teamPickRecords: a first-half spread is neither side of
    the game in the game record: it is counted with the first halves.
  * lib/markets.ts splitPickTitle / pickRowTitle / pickRowMatchup: the label
    "Duke @ Kansas — First Half Duke +3.5" titles the bet, with the matchup on
    its own line, as the NBA first half's does.
  * lib/queries.ts MAIN_GAME_ODDS_MARKETS: its prices are read; its alternate
    rungs are not.
  * lib/modelMeta.ts: its own chip and name, no picker slot, and a page that
    says it posts five to ten minutes before tip.

These run the real modules under node's type stripping, like
tests/test_mobile_first_half.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_mobile_team_total import (MARKETS_FILES, META_FILES, TEAM_FILES,  # noqa: F401
                                          _run, node)

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "mobile" / "src" / "lib"

SP = """
const SP_LABEL = 'Duke @ Kansas — First Half Duke +3.5';
const SP_PICK = { ...PICK, game_id: 'NCAAB_2026-11-10_duke_kansas', sport: 'NCAAB',
  model_id: 'ncaab_first_half_spread', pick_side: 'away', pick_label: SP_LABEL,
  scored_line: -3.5, dk_odds: -110, decision_odds: -105, decision_book: 'fanduel' };
"""


@node
def test_the_pick_reads_the_first_half_spread_market_and_its_number(tmp_path):
    _run(tmp_path, MARKETS_FILES, SP + """
import { gameMarketForModel, marketClassForModel, lineFromSnapshot, splitPickTitle, pickRowTitle, pickRowMatchup, rowIsSameBet, pickTimingInfo } from './markets.ts';
eq(gameMarketForModel('ncaab_first_half_spread'), 'spreads_h1', 'market');
eq(gameMarketForModel('nfl_opener_spread'), 'spreads', 'a game spread is unchanged');
eq(marketClassForModel('ncaab_first_half_spread'), 'game_spread', 'parlay class');
const fd = { bookmaker: 'fanduel', spread_home: -3.5, home_price: -115, away_price: -105 };
eq(lineFromSnapshot(fd, 'spreads_h1'), -3.5, 'the home number');
eq(rowIsSameBet(SP_PICK, fd, 'spreads_h1'), true, 'the same number is the same bet');
eq(rowIsSameBet(SP_PICK, { ...fd, spread_home: -4.5 }, 'spreads_h1'), false, 'another number is not');
eq(splitPickTitle(SP_PICK), { primary: 'First Half Duke +3.5', secondary: null }, 'the card');
eq(pickRowTitle(SP_PICK), 'First Half Duke +3.5', 'the row');
eq(pickRowMatchup(SP_PICK), 'Duke @ Kansas', 'the row caption');
const info = pickTimingInfo(SP_PICK);
eq([info.kind, info.note.startsWith('Posted once and never re-priced'), info.note.includes('Void')],
   ['posted', true, false], 'timing');
""")


@node
def test_the_signals_card_says_first_half(tmp_path):
    _run(tmp_path, MARKETS_FILES + ["signalsCard.ts"], """
import { signalsBetHeadline } from './signalsCard.ts';
eq(signalsBetHeadline({ side: 'away', line: -3.5, market: 'spreads_h1', team: 'Duke', homeTeam: 'Kansas', awayTeam: 'Duke' }),
   'First Half Duke +3.5', 'the away side, its own number');
eq(signalsBetHeadline({ side: 'home', line: -3.5, market: 'spreads_h1', team: 'Kansas', homeTeam: 'Kansas', awayTeam: 'Duke' }),
   'First Half Kansas \\u22123.5', 'the home side');
eq(signalsBetHeadline({ side: 'away', line: -3.5, market: 'spreads', team: 'Duke', homeTeam: 'Kansas', awayTeam: 'Duke' }),
   'Duke +3.5', 'the game spread is unchanged');
""")


@node
def test_the_team_page_counts_it_with_the_first_halves(tmp_path):
    _run(tmp_path, TEAM_FILES, SP + """
import { teamPickRecords } from './teamDetail.ts';
const games = [{ game_id: SP_PICK.game_id, game_date: SP_PICK.game_date, home_team: 'Kansas', away_team: 'Duke' }];
const bet = { ...SP_PICK, result: 'WIN', profit_flat: 95 };
for (const team of ['Kansas', 'Duke']) {
  const r = teamPickRecords([bet], games, team);
  eq([r.settled, r.firstHalves, r.on.wins, r.against.wins], [1, 1, 0, 0], `${team}'s page`);
}
""")


@node
def test_the_model_has_its_own_chip_and_says_when_it_posts(tmp_path):
    _run(tmp_path, META_FILES, """
import { MODEL_META, betSlotForModel, modelLong, modelPageTiming } from './modelMeta.ts';
const m = MODEL_META.ncaab_first_half_spread;
eq([m.type, m.shortLabel, m.statKey, m.statLabel], ['game', '1H Spread', null, ''], 'entry');
eq(modelLong('ncaab_first_half_spread'), 'NCAAB First Half Spreads', 'long name');
eq(betSlotForModel('ncaab_first_half_spread', 'game'), null, 'not a picker slot');
const t = modelPageTiming('ncaab_first_half_spread');
eq([t.title, t.empty.includes('five to ten minutes before tip-off'), t.note.includes('five to ten minutes')],
   ['Checked once per game', true, true], 'page');
""")


def test_its_prices_are_read_with_the_main_game_markets():
    src = (LIB / "queries.ts").read_text(encoding="utf-8")
    i = src.index("const MAIN_GAME_ODDS_MARKETS = [")
    block = src[i:src.index("] as const;", i)]
    assert "'spreads_h1'," in block and "alternate" not in block


def test_the_mobile_threshold_is_generated_from_config():
    src = (LIB / "thresholds.generated.ts").read_text(encoding="utf-8")
    # 0.025 from 2026-11-07 (mike); the mirror is regenerated from config.
    assert "ncaab_first_half_spread: { min_prob: 0, min_edge: 0.025, min_odds: -200 }," in src


# ── the NCAAB first half's total (ncaab_first_half_total) ────────────────────
# Stored under 'totals_h1' like the NBA first half's total; its id holds
# neither 'over_under' nor 'spread', so without its own case it read the
# moneyline rows.

TO = """
const TO_LABEL = 'Duke @ Kansas — First Half Under 70.5';
const TO_PICK = { ...PICK, game_id: 'NCAAB_2026-11-10_duke_kansas', sport: 'NCAAB',
  model_id: 'ncaab_first_half_total', pick_side: 'under', pick_label: TO_LABEL,
  scored_line: 70.5, dk_odds: -115, decision_odds: -110, decision_book: 'fanduel' };
"""


@node
def test_the_first_half_total_reads_its_own_market_and_number(tmp_path):
    _run(tmp_path, MARKETS_FILES, TO + """
import { gameMarketForModel, marketClassForModel, lineFromSnapshot, splitPickTitle, pickRowTitle, pickRowMatchup, rowIsSameBet, pickTimingInfo } from './markets.ts';
eq(gameMarketForModel('ncaab_first_half_total'), 'totals_h1', 'market');
eq(gameMarketForModel('ncaab_total_blend'), 'totals', 'the game total is unchanged');
eq(marketClassForModel('ncaab_first_half_total'), 'game_total', 'parlay class');
const fd = { bookmaker: 'fanduel', total_line: 70.5, over_price: -110, under_price: -110 };
eq(lineFromSnapshot(fd, 'totals_h1'), 70.5, 'the first half total');
eq(rowIsSameBet(TO_PICK, fd, 'totals_h1'), true, 'the same number is the same bet');
eq(rowIsSameBet(TO_PICK, { ...fd, total_line: 71.5 }, 'totals_h1'), false, 'another number is not');
eq(pickRowTitle(TO_PICK), 'First Half Under 70.5', 'the row');
eq(pickRowMatchup(TO_PICK), 'Duke @ Kansas', 'the row caption');
const info = pickTimingInfo(TO_PICK);
eq([info.kind, info.note.startsWith('Posted once and never re-priced'), info.note.includes('Void')],
   ['posted', true, false], 'timing');
""")


@node
def test_the_team_page_counts_a_first_half_total_with_the_first_halves(tmp_path):
    _run(tmp_path, TEAM_FILES, TO + """
import { teamPickRecords } from './teamDetail.ts';
const games = [{ game_id: TO_PICK.game_id, game_date: TO_PICK.game_date, home_team: 'Kansas', away_team: 'Duke' }];
const bet = { ...TO_PICK, result: 'WIN', profit_flat: 90.9 };
const r = teamPickRecords([bet], games, 'Kansas');
eq([r.settled, r.firstHalves], [1, 1], 'counted with the first halves, in no tile');
""")


@node
def test_the_first_half_total_has_its_own_chip_and_says_it_posts_an_hour_out(tmp_path):
    _run(tmp_path, META_FILES, """
import { MODEL_META, betSlotForModel, modelLong, modelPageTiming, modelProbabilityNote } from './modelMeta.ts';
const m = MODEL_META.ncaab_first_half_total;
eq([m.type, m.shortLabel, m.statKey, m.statLabel], ['game', '1H O/U', null, ''], 'entry');
eq(modelLong('ncaab_first_half_total'), 'NCAAB First Half Totals', 'long name');
eq(betSlotForModel('ncaab_first_half_total', 'game'), null, 'not a picker slot');
const t = modelPageTiming('ncaab_first_half_total');
eq([t.title, t.empty.includes('about an hour before tip-off'), t.note.includes('about an hour')],
   ['Checked once per game', true, true], 'page');
eq(modelProbabilityNote('ncaab_first_half_total').includes('first half'), true, 'its own note');
""")


def test_the_first_half_total_threshold_is_generated_from_config():
    src = (LIB / "thresholds.generated.ts").read_text(encoding="utf-8")
    # The bar moved 0.02 -> 0.025 on 2026-11-06 (mike); the mirror is regenerated from config.
    assert "ncaab_first_half_total: { min_prob: 0, min_edge: 0.025, min_odds: -200 }," in src

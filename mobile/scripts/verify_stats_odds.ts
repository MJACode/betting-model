/**
 * Standalone verification for the Stats tab's ODDS column (src/lib/statsOdds.ts).
 * Run with:
 *
 *   npx tsx scripts/verify_stats_odds.ts
 *
 * The column used to read only `picks`, so a player DraftKings priced but no
 * model had scored showed a dash. Rows below are the REAL 2026-09-03 MLB slate
 * (v_latest_prop_odds_all_books, batter_hits, DraftKings) — the eight players
 * from Matt's screenshot, every one of them priced, none of them holding a
 * pick at the time.
 *
 * Pins:
 *  - a DK-priced player with no pick gets a quote, not a dash;
 *  - the quote is at the line the RULER is on, never the model's own line;
 *  - a pick scored at that line wins the cell (edge/EV/betslip survive);
 *  - a pick scored at a DIFFERENT line does not (it is a different bet);
 *  - names that fold together are refused on both sides of the join;
 *  - the sport bound holds (player_points is NBA and WNBA both).
 */

import { allBookPricesForPick, MODEL_BOOK } from '../src/lib/markets';
import {
  ambiguousKeys,
  buildPickIndex,
  buildQuoteIndex,
  sameLine,
  statsOddsCell,
} from '../src/lib/statsOdds';
import type { EnrichedPick, PropOddsByBookRow } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// ── Fixtures: the real slate, prices as stored (numerics come back as strings) ──

const row = (
  player: string,
  game: string,
  line: string,
  over: string,
  under: string,
  book = 'draftkings',
  market = 'batter_hits',
): PropOddsByBookRow =>
  ({
    game_id: game,
    game_date: '2026-09-03',
    market,
    player_name: player,
    team: null,
    bookmaker: book,
    line,
    over_price: over,
    under_price: under,
    over_link: null,
    under_link: null,
    snapshot_at: '2026-09-03T14:17:01.760356-04:00',
  }) as unknown as PropOddsByBookRow;

const LAD = 'MLB_2026-09-03_STL_LAD';
const CHC = 'MLB_2026-09-03_MIL_CHC';
const KC = 'MLB_2026-09-03_MIA_KC';
const TOR = 'MLB_2026-09-03_TOR_CLE';
const BAL = 'MLB_2026-09-03_BOS_BAL';
const TEX = 'MLB_2026-09-03_TB_TEX';

const SLATE: PropOddsByBookRow[] = [
  row('Mookie Betts', LAD, '0.5', '-262', '193'),
  row('Mookie Betts', LAD, '1.5', '+125', '-155'),
  row('Freddie Freeman', LAD, '0.5', '-237', '176'),
  row('Tyrone Taylor', CHC, '0.5', '-150', '115'),
  row('Christian Yelich', CHC, '0.5', '-180', '135'),
  row('Salvador Perez', KC, '0.5', '-217', '161'),
  row('George Springer', TOR, '0.5', '-259', '190'),
  row('Trevor Story', BAL, '0.5', '-193', '144'),
  row('Brandon Nimmo', TEX, '0.5', '-220', '163'),
  // A second book on Betts' 0.5 — the sheet's books list, not the pill.
  row('Mookie Betts', LAD, '0.5', '-250', '185', 'fanduel'),
];
const SLATE_IDS = new Set([LAD, CHC, KC, TOR, BAL, TEX]);

const OVER_0_5 = { market: 'batter_hits', line: 0.5, side: 'over' as const, gameIds: SLATE_IDS };

// ── 1. The bug: priced by DK, never scored by a model → a number, not a dash ──

const quotes = buildQuoteIndex(SLATE, OVER_0_5);
const noPicks = buildPickIndex([], 'mlb_prop_batter_hits');

const SCREENSHOT = [
  'Mookie Betts',
  'Tyrone Taylor',
  'Freddie Freeman',
  'Salvador Perez',
  'George Springer',
  'Trevor Story',
  'Christian Yelich',
  'Brandon Nimmo',
];
const shown = SCREENSHOT.filter(
  (n) => statsOddsCell({ player_id: null, player_name: n }, noPicks, quotes, 0.5) != null,
);
check(
  'every DK-priced player on the 1+ Hits board gets a cell with no pick anywhere',
  shown.length === SCREENSHOT.length,
  `${shown.length}/${SCREENSHOT.length}`,
);

const betts = statsOddsCell({ player_id: null, player_name: 'Mookie Betts' }, noPicks, quotes, 0.5);
check(
  "Betts' cell is DK's over price at 0.5, not FanDuel's",
  betts?.kind === 'quote' && betts.quote.dkPrice === -262,
  String(betts?.kind === 'quote' ? betts.quote.dkPrice : betts?.kind),
);
check(
  'the cell carries every book for the sheet behind it',
  betts?.kind === 'quote' && betts.quote.bookRows.length === 2,
);
check(
  'a player DK does not price gets no cell (the dash still means something)',
  statsOddsCell({ player_id: null, player_name: 'Shohei Ohtani' }, noPicks, quotes, 0.5) === null,
);

// ── 2. The line is the RULER's line, never the model's ──
// "2+ Hits" is Over 1.5. The old cell printed the model's o0.5 price on it.

const at1_5 = buildQuoteIndex(SLATE, { ...OVER_0_5, line: 1.5 });
const betts2 = statsOddsCell({ player_id: null, player_name: 'Mookie Betts' }, noPicks, at1_5, 1.5);
check(
  'a 2+ Hits board shows the 1.5 price, not the 0.5 one',
  betts2?.kind === 'quote' && betts2.quote.dkPrice === 125 && betts2.quote.line === 1.5,
);
check(
  'a player DK prices only at 0.5 has no cell on a 2+ board (different bet)',
  !at1_5.has('christian yelich'),
);

const under = buildQuoteIndex(SLATE, { ...OVER_0_5, side: 'under' });
check(
  '"At most 0 Hits" reads the UNDER price',
  under.get('mookie betts')?.dkPrice === 193,
);

check('sameLine tolerates float noise', sameLine(0.1 + 0.2 - 0.3 + 1.5, 1.5));
check('sameLine rejects a different number', !sameLine(0.5, 1.5));
check('sameLine is false on a missing line', !sameLine(null, 0.5) && !sameLine(0.5, null));

// ── 3. A pick wins its own line, and only its own line ──

const pick = (
  playerId: string,
  label: string,
  line: number,
  odds: number,
  signal: 'BET' | 'NONE' = 'BET',
): EnrichedPick =>
  ({
    pick: {
      pick_id: 1,
      model_id: 'mlb_prop_batter_hits',
      player_id: playerId,
      pick_label: label,
      pick_side: 'over',
      scored_line: line,
      dk_odds: odds,
      signal_type: signal,
      model_probability: 0.72,
      edge: 0.09,
    },
    game: null,
    weather: null,
    bookRows: [],
  }) as unknown as EnrichedPick;

const picks = buildPickIndex([pick('betts', 'Mookie Betts Over 0.5 Hits', 0.5, -250)], 'mlb_prop_batter_hits');
const withPick = statsOddsCell({ player_id: 'betts', player_name: 'Mookie Betts' }, picks, quotes, 0.5);
check(
  'a pick scored at the board line wins the cell (edge, EV and betslip survive)',
  withPick?.kind === 'pick' && withPick.pick.pick.dk_odds === -250,
);
const wrongLine = statsOddsCell({ player_id: 'betts', player_name: 'Mookie Betts' }, picks, at1_5, 1.5);
check(
  'the same pick does NOT win a 2+ board — it is a different bet, so the 1.5 quote shows',
  wrongLine?.kind === 'quote' && wrongLine.quote.dkPrice === 125,
);

check(
  'a BET outranks a later dead-zone NONE on the same player (§1c)',
  buildPickIndex(
    [pick('betts', 'l', 0.5, -250, 'BET'), pick('betts', 'l', 0.5, -180, 'NONE')],
    'mlb_prop_batter_hits',
  ).get('betts')?.pick.dk_odds === -250,
);
check(
  'a retired stat (null model) indexes nothing — no pill on Home Runs or RBIs',
  buildPickIndex([pick('betts', 'l', 0.5, -250)], null).size === 0,
);
check(
  'a prob-only pick with no DK price is not indexed (nothing to print)',
  buildPickIndex([pick('x', 'l', 0.5, null as unknown as number)], 'mlb_prop_batter_hits').size === 0,
);

// ── 4. Ambiguous names are refused on BOTH sides, never guessed ──
// The fold drops generational suffixes, so these two are one key and two people.

const AMBIG = [
  row('Luis Garcia', TEX, '0.5', '-140', '110'),
  row('Luis Garcia Jr.', TEX, '0.5', '-190', '145'),
];
check(
  'two players folding to one key are both refused a quote',
  buildQuoteIndex(AMBIG, OVER_0_5).size === 0,
);
check(
  'ambiguousKeys names the collision',
  ambiguousKeys(['Luis Garcia', 'Luis Garcia Jr.']).has('luis garcia'),
);
check(
  'one player written two ways is not a collision',
  ambiguousKeys(['Mookie Betts']).size === 0,
);
check(
  'an ambiguous LEADERBOARD name is refused too',
  statsOddsCell(
    { player_id: null, player_name: 'Mookie Betts' },
    noPicks,
    quotes,
    0.5,
    new Set(['mookie betts']),
  ) === null,
);
check(
  'an accented leaderboard name still finds the feed’s flat spelling',
  buildQuoteIndex([row('Jose Ramirez', TOR, '0.5', '-170', '130')], OVER_0_5).has('jose ramirez') &&
    statsOddsCell(
      { player_id: null, player_name: 'José Ramírez' },
      noPicks,
      buildQuoteIndex([row('Jose Ramirez', TOR, '0.5', '-170', '130')], OVER_0_5),
      0.5,
    ) != null,
);

// ── 5. The sport bound: player_points is both an NBA and a WNBA market ──

const BASKET = [
  row('A. Wilson', 'WNBA_2026-09-03_LV_CHI', '19.5', '-115', '-105', 'draftkings', 'player_points'),
  row('N. Jokic', 'NBA_2026-09-03_DEN_LAL', '19.5', '-120', '100', 'draftkings', 'player_points'),
];
const wnbaOnly = buildQuoteIndex(BASKET, {
  market: 'player_points',
  line: 19.5,
  side: 'over',
  gameIds: new Set(['WNBA_2026-09-03_LV_CHI']),
});
check(
  'a WNBA board never shows an NBA price for the same market',
  wnbaOnly.size === 1 && wnbaOnly.has('a wilson'),
);
check(
  'no game bound = no sport filter (fail open, never blank the column)',
  buildQuoteIndex(BASKET, { market: 'player_points', line: 19.5, side: 'over', gameIds: null }).size === 2,
);
check(
  'a market with no rows yields an empty index, not a throw',
  buildQuoteIndex([], OVER_0_5).size === 0,
);
check(
  'a book with no price on the asked side is skipped',
  buildQuoteIndex(
    [row('Nobody Priced', TEX, '0.5', null as unknown as string, '150')],
    OVER_0_5,
  ).size === 0,
);

// ── 6. The sheet never contradicts the pill it was opened from (§1c) ──
// The pill prints the pick's STORED price; the all-books view reads the latest
// snapshot. Locked at -250 and DK has since moved to -205: the sheet's DK row
// must still say -250, or a user books a different bet from the graded one.

const MOVED = [
  { bookmaker: 'draftkings', over_price: '-205', under_price: '160', line: '0.5', over_link: null },
  { bookmaker: 'fanduel', over_price: '-240', under_price: '178', line: '0.5', over_link: null },
] as unknown as Parameters<typeof allBookPricesForPick>[1];

const locked = pick('betts', 'Mookie Betts Over 0.5 Hits', 0.5, -250).pick;
const forPick = allBookPricesForPick(locked, MOVED, 'batter_hits');
const dkRow = forPick.find((q) => q.bookmaker === MODEL_BOOK);
check(
  "the sheet's modeled-book row is the price the pick was GIVEN at, not the fresher snapshot",
  dkRow?.price === -250,
  String(dkRow?.price),
);
check(
  'every other book is still a live quote',
  forPick.find((q) => q.bookmaker === 'fanduel')?.price === -240,
);
check(
  'best is re-flagged against the stored number, not the one it replaced',
  forPick.find((q) => q.isBest)?.bookmaker === 'fanduel',
  forPick.find((q) => q.isBest)?.bookmaker,
);
check('no book is listed twice', new Set(forPick.map((q) => q.bookmaker)).size === forPick.length);
check(
  'the column prices against the modeled book, not a hard-coded string',
  buildQuoteIndex(SLATE, { ...OVER_0_5, book: MODEL_BOOK }).get('mookie betts')?.dkPrice === -262,
);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

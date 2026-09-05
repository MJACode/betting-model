/**
 * Standalone verification for the Stats tab's LINE column (src/lib/statsOdds.ts).
 * Run with:
 *
 *   npx tsx scripts/verify_stats_odds.ts
 *
 * Matt, 2026-09-03: "display all lines regardless of bet status … if they
 * select FanDuel we only show FanDuel, if the user had DK selected then we
 * only show DK … it works separately from the models."
 *
 * Rows below are the REAL 2026-09-03 MLB slate (v_latest_prop_odds_all_books,
 * batter_hits) — the eight players from Matt's screenshot, every one of them
 * priced by DraftKings, none of them holding a pick at the time; and the real
 * finding that FanDuel posts no batter_hits line at all that day.
 *
 * Pins:
 *  - the column is the SELECTED book's number, with no fallback to any other;
 *  - a book that posts nothing for the market is reported, not silently dashed;
 *  - the quote is at the line the RULER is on, never the model's own line;
 *  - no pick ever decides a cell; a pick only ever unlocks "Add to betslip",
 *    and only at its own line;
 *  - names that fold together are refused on both sides of the join;
 *  - the sport bound holds (player_points is NBA and WNBA both);
 *  - a team's line is its own side of its game, in the market its stat reads
 *    against.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  ambiguousKeys,
  anyBookPostsSide,
  bookCoverageForMarket,
  bookPostsMarket,
  buildPickIndex,
  buildQuoteIndex,
  buildTeamLineIndex,
  quoteForRow,
  sameLine,
  slipPickFor,
  teamLineCaption,
  teamLineMarketFor,
  unstartedGameIds,
} from '../src/lib/statsOdds';
import type { EnrichedPick, GameRow, OddsByBookRow, PropOddsByBookRow } from '../src/types';
import { alternateMarketFor, canonicalPropMarket, foldAlternateRows, isAlternateMarket, propLineRowKey } from '../src/lib/propLines';
import { thresholdLabel } from '../src/lib/hitMode';

const read = (p: string) => readFileSync(join(import.meta.dirname, '..', p), 'utf-8');
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
    over_link: book === 'draftkings' ? `https://dk/${player}` : null,
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
  // BetMGM on Betts' 0.5. FanDuel is deliberately ABSENT from the whole
  // market — that is what production showed on 2026-09-03.
  row('Mookie Betts', LAD, '0.5', '-250', '185', 'betmgm'),
];
const SLATE_IDS = new Set([LAD, CHC, KC, TOR, BAL, TEX]);

const DK_OVER_0_5 = {
  market: 'batter_hits',
  line: 0.5,
  side: 'over' as const,
  books: ['draftkings'],
  gameIds: SLATE_IDS,
};

// ── 1. The selected book's number for every player it prices, no pick needed ──

const dk = buildQuoteIndex(SLATE, DK_OVER_0_5);

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
const shown = SCREENSHOT.filter((n) => quoteForRow({ player_name: n }, dk) != null);
check(
  'every DK-priced player on the 1+ Hits board gets a cell with no pick anywhere',
  shown.length === SCREENSHOT.length,
  `${shown.length}/${SCREENSHOT.length}`,
);
const betts = quoteForRow({ player_name: 'Mookie Betts' }, dk);
check("Betts' cell is DK's over price at 0.5", betts?.price === -262 && betts.book === 'draftkings');
check("the cell carries the book's betslip link for the side", betts?.link === 'https://dk/Mookie Betts');
check(
  'a player the book does not price gets no cell (the dash still means something)',
  quoteForRow({ player_name: 'Shohei Ohtani' }, dk) === null,
);

// ── 2. ONLY the selected book. No fallback — "if they select FanDuel we only show FanDuel". ──

const mgm = buildQuoteIndex(SLATE, { ...DK_OVER_0_5, books: ['betmgm'] });
check('a BetMGM user sees BetMGM’s number, not DK’s', mgm.get('mookie betts')?.price === -250);
check(
  'a BetMGM user sees NOTHING for a player only DK prices — no DraftKings fallback',
  !mgm.has('freddie freeman') && !mgm.has('george springer'),
);
const fd = buildQuoteIndex(SLATE, { ...DK_OVER_0_5, books: ['fanduel'] });
check('a FanDuel user sees an empty column when FanDuel posts no batter_hits', fd.size === 0);
check(
  'and the board can SAY that: bookPostsMarket is false for FanDuel, true for DK',
  !bookPostsMarket(SLATE, 'batter_hits', ['fanduel'], SLATE_IDS) &&
    bookPostsMarket(SLATE, 'batter_hits', ['draftkings'], SLATE_IDS),
);
check(
  'bookPostsMarket is a DAY/BOOK fact, not a line fact (DK posts hits even off the 0.5 line)',
  bookPostsMarket(SLATE, 'batter_hits', ['draftkings'], SLATE_IDS) ===
    bookPostsMarket(SLATE.filter((r) => !sameLine(Number(r.line), 0.5)), 'batter_hits', ['draftkings'], SLATE_IDS),
);

// ── 2b. SEVERAL books: the best of them wins each cell, and says which ──
// Matt, 2026-09-04: "book DK and Fan Duel and it takes the best line in that
// case." American odds are monotonic in payout, so best = numeric max.

const both = buildQuoteIndex(SLATE, { ...DK_OVER_0_5, books: ['draftkings', 'betmgm'] });
check(
  'with DK + MGM selected, Betts takes MGM’s -250 over DK’s -262 (the better payout)',
  both.get('mookie betts')?.price === -250,
  `got ${both.get('mookie betts')?.price}`,
);
check(
  'and the cell is BADGED with the book that won it, so the pill can open the right app',
  both.get('mookie betts')?.book === 'betmgm',
  `got ${both.get('mookie betts')?.book}`,
);
check(
  'a player only ONE of the selected books prices still gets a cell, from that book',
  both.get('freddie freeman')?.price === -237 && both.get('freddie freeman')?.book === 'draftkings',
);
check(
  'selecting more books never REMOVES a row: DK-only ⊆ DK+MGM',
  [...dk.keys()].every((k) => both.has(k)) && both.size === dk.size,
);
check(
  'the losing book’s link never rides along — the link is the winner’s',
  both.get('mookie betts')?.link === null,
);
check(
  'a book outside the set cannot win a cell (MGM alone still ignores DK)',
  buildQuoteIndex(SLATE, { ...DK_OVER_0_5, books: ['betmgm'] }).get('mookie betts')?.book === 'betmgm',
);
check(
  'bookPostsMarket is true when ANY selected book posts it',
  bookPostsMarket(SLATE, 'batter_hits', ['fanduel', 'draftkings'], SLATE_IDS) &&
    !bookPostsMarket(SLATE, 'batter_hits', ['fanduel'], SLATE_IDS),
);

// A tie must not reshuffle the board on every refresh: earlier book wins, and
// BETTABLE_BOOKS order puts DraftKings first.
const TIED: PropOddsByBookRow[] = [
  row('Tie Guy', LAD, '0.5', '-150', '120'),
  row('Tie Guy', LAD, '0.5', '-150', '120', 'betmgm'),
];
check(
  'a tie goes to the earlier book in the member’s list, so badges are stable',
  buildQuoteIndex(TIED, { ...DK_OVER_0_5, books: ['draftkings', 'betmgm'] }).get('tie guy')?.book ===
    'draftkings' &&
    buildQuoteIndex(TIED, { ...DK_OVER_0_5, books: ['betmgm', 'draftkings'] }).get('tie guy')?.book ===
      'betmgm',
);

// Crossing the −100/+100 boundary: +125 pays more than −155, and the numeric
// max gets that right without converting to decimal.
const CROSS: PropOddsByBookRow[] = [
  row('Cross Guy', LAD, '0.5', '-155', '120'),
  row('Cross Guy', LAD, '0.5', '+125', '120', 'betmgm'),
];
check(
  'best price crosses the −100/+100 boundary correctly (+125 beats −155)',
  buildQuoteIndex(CROSS, { ...DK_OVER_0_5, books: ['draftkings', 'betmgm'] }).get('cross guy')
    ?.price === 125,
);

// ── 3. The line is the RULER's line, never the model's ──

const at1_5 = buildQuoteIndex(SLATE, { ...DK_OVER_0_5, line: 1.5 });
check(
  'a 2+ Hits board shows the 1.5 price, not the 0.5 one',
  at1_5.get('mookie betts')?.price === 125 && at1_5.get('mookie betts')?.line === 1.5,
);
// 2026-09-04, reversed: the book's OWN line shows, marked off-line, instead of
// a dash ("everyone should have a line by this point"). Still a different
// bet — the cell prints its number and the sheet adds THAT line.
check(
  'a player DK prices only at 0.5 gets that line on a 2+ board, marked off-line',
  at1_5.get('christian yelich')?.line === 0.5 && at1_5.get('christian yelich')?.offLine === true,
);
const under = buildQuoteIndex(SLATE, { ...DK_OVER_0_5, side: 'under' });
check('"At most 0 Hits" reads the UNDER price', under.get('mookie betts')?.price === 193);
check('sameLine tolerates float noise', sameLine(0.1 + 0.2 - 0.3 + 1.5, 1.5));
check('sameLine rejects a different number', !sameLine(0.5, 1.5));

// ── 4. A pick never decides a cell; it only unlocks the betslip, at its own line ──

const pick = (playerId: string, line: number, odds: number, signal: 'BET' | 'NONE' = 'BET'): EnrichedPick =>
  ({
    pick: {
      pick_id: 1,
      model_id: 'mlb_prop_batter_hits',
      player_id: playerId,
      pick_label: 'Mookie Betts Over 0.5 Hits',
      pick_side: 'over',
      scored_line: line,
      dk_odds: odds,
      signal_type: signal,
    },
    game: null,
    weather: null,
    bookRows: [],
  }) as unknown as EnrichedPick;

const picks = buildPickIndex([pick('betts', 0.5, -250)], 'mlb_prop_batter_hits');
check(
  'the cell is the BOOK’s current number even when a pick exists at a different price',
  quoteForRow({ player_name: 'Mookie Betts' }, dk)?.price === -262,
);
check(
  'a pick at the board line unlocks the betslip',
  slipPickFor({ player_id: 'betts' }, picks, 0.5)?.pick.dk_odds === -250,
);
check('the same pick does NOT unlock a 2+ board — it is a different bet', slipPickFor({ player_id: 'betts' }, picks, 1.5) === null);
check(
  'a BET outranks a later dead-zone NONE on the same player (§1c)',
  buildPickIndex([pick('betts', 0.5, -250, 'BET'), pick('betts', 0.5, -180, 'NONE')], 'mlb_prop_batter_hits').get('betts')
    ?.pick.dk_odds === -250,
);
check('a retired stat (null model) indexes no picks — no betslip button, but the LINE still shows', buildPickIndex([pick('betts', 0.5, -250)], null).size === 0 && dk.size > 0);

// ── 5. Ambiguous names are refused on BOTH sides, never guessed ──

const AMBIG = [row('Luis Garcia', TEX, '0.5', '-140', '110'), row('Luis Garcia Jr.', TEX, '0.5', '-190', '145')];
check('two players folding to one key are both refused a quote', buildQuoteIndex(AMBIG, DK_OVER_0_5).size === 0);
check('ambiguousKeys names the collision', ambiguousKeys(['Luis Garcia', 'Luis Garcia Jr.']).has('luis garcia'));
check('one player written two ways is not a collision', ambiguousKeys(['Mookie Betts']).size === 0);
check(
  'an ambiguous LEADERBOARD name is refused too',
  quoteForRow({ player_name: 'Mookie Betts' }, dk, new Set(['mookie betts'])) === null,
);
const accented = buildQuoteIndex([row('Jose Ramirez', TOR, '0.5', '-170', '130')], DK_OVER_0_5);
check('an accented leaderboard name still finds the feed’s flat spelling', quoteForRow({ player_name: 'José Ramírez' }, accented) != null);

// ── 6. The sport bound: player_points is both an NBA and a WNBA market ──

const BASKET = [
  row('A. Wilson', 'WNBA_2026-09-03_LV_CHI', '19.5', '-115', '-105', 'draftkings', 'player_points'),
  row('N. Jokic', 'NBA_2026-09-03_DEN_LAL', '19.5', '-120', '100', 'draftkings', 'player_points'),
];
const wnbaOnly = buildQuoteIndex(BASKET, {
  market: 'player_points',
  line: 19.5,
  side: 'over',
  books: ['draftkings'],
  gameIds: new Set(['WNBA_2026-09-03_LV_CHI']),
});
check('a WNBA board never shows an NBA price for the same market', wnbaOnly.size === 1 && wnbaOnly.has('a wilson'));
check(
  'no game bound = no sport filter (fail open, never blank the column)',
  buildQuoteIndex(BASKET, { market: 'player_points', line: 19.5, side: 'over', books: ['draftkings'], gameIds: null }).size === 2,
);
check('a market with no rows yields an empty index, not a throw', buildQuoteIndex([], DK_OVER_0_5).size === 0);
check(
  'a book with no price on the asked side is skipped',
  buildQuoteIndex([row('Nobody Priced', TEX, '0.5', null as unknown as string, '150')], DK_OVER_0_5).size === 0,
);

// ── 7. Teams: the team's own side of its game, in the market its stat reads against ──

const game = (id: string, home: string, away: string): GameRow =>
  ({ game_id: id, sport: 'MLB', game_date: '2026-09-03', home_team: home, away_team: away }) as unknown as GameRow;
const grow = (
  id: string,
  market: string,
  book: string,
  o: Partial<OddsByBookRow>,
): OddsByBookRow =>
  ({
    game_id: id,
    game_date: '2026-09-03',
    market,
    bookmaker: book,
    home_price: null,
    away_price: null,
    over_price: null,
    under_price: null,
    spread_home: null,
    total_line: null,
    home_link: null,
    away_link: null,
    over_link: null,
    under_link: null,
    snapshot_at: '',
    ...o,
  }) as OddsByBookRow;

const GAMES = [game(LAD, 'LAD', 'STL'), game(BAL, 'BAL', 'BOS')];
const GAME_LINES: OddsByBookRow[] = [
  grow(LAD, 'h2h', 'fanduel', { home_price: '-170' as unknown as number, away_price: '+142' as unknown as number, home_link: 'fd/lad' }),
  grow(LAD, 'spreads', 'fanduel', { spread_home: '-1.5' as unknown as number, home_price: '+118' as unknown as number, away_price: '-140' as unknown as number }),
  grow(LAD, 'totals', 'fanduel', { total_line: '8.5' as unknown as number, over_price: '-108' as unknown as number, under_price: '-112' as unknown as number }),
  grow(LAD, 'h2h', 'draftkings', { home_price: '-165' as unknown as number, away_price: '+140' as unknown as number }),
  grow(BAL, 'h2h', 'fanduel', { home_price: '+130' as unknown as number, away_price: '-155' as unknown as number }),
];

check('Win% reads the moneyline, ATS% the spread, Over% the total',
  teamLineMarketFor('win_pct') === 'h2h' && teamLineMarketFor('ats_home_pct') === 'spreads' && teamLineMarketFor('over_pct') === 'totals');
check('scoring stats read the total; margin reads the spread; efficiency reads the moneyline',
  teamLineMarketFor('points_for_pg') === 'totals' && teamLineMarketFor('point_diff_pg') === 'spreads' && teamLineMarketFor('wrc_plus') === 'h2h');

const ml = buildTeamLineIndex(GAME_LINES, GAMES, { market: 'h2h', books: ['fanduel'] });
check('the home team gets the home moneyline, with its link', ml.get('LAD')?.price === -170 && ml.get('LAD')?.link === 'fd/lad');
check('the away team gets the away moneyline of the same game', ml.get('STL')?.price === 142 && ml.get('STL')?.opponent === 'LAD' && ml.get('STL')?.isHome === false);
check('one row per team, two teams per game', ml.size === 4);
check('ONLY the selected book: DK’s number never leaks onto a FanDuel column', ml.get('LAD')?.price !== -165);
check('a team with no game on the slate has no line', !ml.has('NYY'));

const sp = buildTeamLineIndex(GAME_LINES, GAMES, { market: 'spreads', books: ['fanduel'] });
check('the favourite’s spread is negative from its side, the dog’s positive',
  sp.get('LAD')?.line === -1.5 && sp.get('STL')?.line === 1.5 && sp.get('STL')?.price === -140);
check('caption prints the sign', teamLineCaption(sp.get('LAD')!) === '−1.5' && teamLineCaption(sp.get('STL')!) === '+1.5');
check('every cell carries a caption — a moneyline says ML (no bare pill, no sub-44pt target)', teamLineCaption(ml.get('LAD')!) === 'ML');
check('a game the book has not spread yet yields no spread row', !sp.has('BAL'));

const tot = buildTeamLineIndex(GAME_LINES, GAMES, { market: 'totals', books: ['fanduel'] });
check('both sides of a game share the game total, over side', tot.get('LAD')?.line === 8.5 && tot.get('STL')?.price === -108);
check('total caption reads o8.5', teamLineCaption(tot.get('LAD')!) === 'o8.5');
check('a DK user on a FanDuel-only fixture sees the DK moneyline and nothing else',
  buildTeamLineIndex(GAME_LINES, GAMES, { market: 'h2h', books: ['draftkings'] }).size === 2);

// ── 8. A game in progress has no line — its "latest" row is a live number ──

const started = { ...game(LAD, 'LAD', 'STL'), commence_time: '2026-09-03T16:37:00Z' } as GameRow;
const later = { ...game(BAL, 'BAL', 'BOS'), commence_time: '2026-09-03T23:15:00Z' } as GameRow;
const noTime = { ...game(TEX, 'TEX', 'TB'), commence_time: null } as unknown as GameRow;
const NOW = '2026-09-03T18:04:00Z';
const live = unstartedGameIds([started, later, noTime], NOW);
check('a game past first pitch is out; one still to come is in', !live.has(LAD) && live.has(BAL));
check('a game with no commence_time is kept (fail open)', live.has(TEX));
check(
  'the team index honours the bound: the started game’s −50000 never reaches the column',
  !buildTeamLineIndex(GAME_LINES, [started, later], { market: 'h2h', books: ['fanduel'], gameIds: live }).has('LAD') &&
    buildTeamLineIndex(GAME_LINES, [started, later], { market: 'h2h', books: ['fanduel'], gameIds: live }).has('BAL'),
);
check(
  'and so does the player index (Betts’ game started → no cell)',
  !buildQuoteIndex(SLATE, { ...DK_OVER_0_5, gameIds: live }).has('mookie betts') &&
    buildQuoteIndex(SLATE, { ...DK_OVER_0_5, gameIds: live }).has('trevor story'),
);


// ── The book's OWN line when it does not post the ruler's (2026-09-04) ──────
// Matt: "everyone should have a line by this point." 23 of 313 priced hitters
// were 1.5-only at DraftKings; the cell prints that line WITH its number as a
// different bet (offLine), never the ruler's price, and never a dash.
{
  const ownLine = buildQuoteIndex(
    [
      { ...SLATE[0]!, player_name: 'George Springer', line: 1.5, over_price: 230, under_price: -320 },
      { ...SLATE[0]!, player_name: 'Bryce Harper', line: 0.5, over_price: -161, under_price: 121 },
    ],
    DK_OVER_0_5,
  );
  const springer = ownLine.get('george springer');
  const harper = ownLine.get('bryce harper');
  check('a player the book posts only at 1.5 gets that line, marked off-line', springer?.line === 1.5 && springer?.offLine === true && springer?.price === 230);
  check('a player posted at the ruler line is unchanged and not off-line', harper?.line === 0.5 && !harper?.offLine && harper?.price === -161);
  const both = buildQuoteIndex(
    [
      { ...SLATE[0]!, player_name: 'Mookie Betts', line: 0.5, over_price: -250, under_price: 184, bookmaker: 'draftkings' },
      { ...SLATE[0]!, player_name: 'Mookie Betts', line: 1.5, over_price: 200, under_price: -260, bookmaker: 'betmgm' },
    ],
    { ...DK_OVER_0_5, books: ['draftkings', 'betmgm'] },
  );
  check('the ruler line wins over another book\'s off-line number', both.get('mookie betts')?.line === 0.5 && !both.get('mookie betts')?.offLine);
  const under = buildQuoteIndex(
    [{ ...SLATE[0]!, player_name: 'George Springer', line: 1.5, over_price: 230, under_price: null }],
    DK_OVER_0_5,
  );
  check('an off-line row prices the side it posts even with the other side missing', under.get('george springer')?.price === 230);
  const stats = read('src/screens/StatsScreen.tsx');
  check('the pill prints the off-line number under the price, in the board\'s idiom',
    stats.includes('const caption = quote.offLine ? offLineCaption(quote.line, quote.side) : null;')
      && thresholdLabel(1.5, 'over') === '2+'
      && thresholdLabel(1.5, 'under') === '1 or fewer');
  check('VoiceOver hears that it is the book\'s own line', stats.includes('the book’s own line, not the board’s'));
  check('a live or finished game says Live / Final, not a dash', stats.includes('<Text style={styles.oddsStarted}>{started}</Text>') && stats.includes("kind === 'live' ? 'Live' : kind === 'final' || kind === 'ended' ? 'Final' : null"));
  check('a doubleheader team with a game still to come gets no label', stats.includes('pending.forEach((t) => out.delete(t));'));
  const teams = read('src/components/TeamsBoard.tsx');
  check('the Teams board says Live / Final too', teams.includes('<Text style={styles.lineStarted}>{started}</Text>') && teams.includes('gameStatus(g).kind'));
}

// ── Alternate lines fold onto their market (lib/propLines.ts, 2026-09-05) ──
{
  const r = (market: string, bookmaker: string, line: number, over: number | null): PropOddsByBookRow => ({
    game_id: 'MLB_2026-09-05_WSH_LAD', game_date: '2026-09-05', market, player_name: 'Mookie Betts', team: 'LAD',
    bookmaker, line, over_price: over, under_price: null, over_link: null, under_link: null, snapshot_at: 't',
  });
  check('an alternate key names its market', isAlternateMarket('batter_hits_alternate') && !isAlternateMarket('batter_hits'));
  check('canonical strips the suffix and leaves a standard key alone', canonicalPropMarket('batter_hits_alternate') === 'batter_hits' && canonicalPropMarket('batter_hits') === 'batter_hits');
  check('the alternate key for a market', alternateMarketFor('batter_hits') === 'batter_hits_alternate' && alternateMarketFor('batter_hits_alternate') === 'batter_hits_alternate');
  const rows = [r('batter_hits', 'draftkings', 0.5, -250), r('batter_hits_alternate', 'draftkings', 0.5, -245), r('batter_hits_alternate', 'draftkings', 1.5, 230), r('batter_hits_alternate', 'fanduel', 0.5, -240)];
  const folded = foldAlternateRows(rows);
  check('alternate rows come back under the standard market', folded.every((x) => x.market === 'batter_hits'));
  check('an alternate that duplicates the book\'s standard line is dropped', folded.filter((x) => x.bookmaker === 'draftkings').map((x) => `${x.line}:${x.over_price}`).join() === '0.5:-250,1.5:230');
  check('another book\'s alternate at that line is kept (that book has no standard row)', folded.some((x) => x.bookmaker === 'fanduel' && x.line === 0.5));
  check('order is preserved', folded.map((x) => x.over_price).join() === '-250,230,-240');
  check('the paging key carries the line', propLineRowKey(rows[2]!) !== propLineRowKey(rows[1]!) && propLineRowKey(rows[2]!).endsWith('|1.5'));
  // The quote index sees one market with every line: a 1.5 ruler finds the
  // alternate row where the standard line is 0.5.
  const idx = buildQuoteIndex(folded, { market: 'batter_hits', line: 1.5, side: 'over', books: ['draftkings'] });
  const q = idx.get('mookie betts');
  check('the ruler at 1.5 prices the alternate line, on the board\'s number', q?.line === 1.5 && q?.price === 230 && q?.offLine === false, `${q?.line} ${q?.price} ${q?.offLine}`);
  const queries = read('src/lib/queries.ts');
  check('the Stats read asks for the market AND its alternate key', queries.includes(".in('market', [market, alternateMarketFor(market)])"));
  check('the reads fold alternates before returning', (queries.match(/foldAlternateRows\(/g) ?? []).length >= 2);
  check('the paged Stats read orders and keys by line', queries.includes(".order('line')") && queries.includes('propLineRowKey,'));
}

// ── football: the one sport that reaches its market without a model ────────
{
  const cat = read('src/lib/statCatalog.ts');
  const mk = read('src/lib/markets.ts');
  const screen = read('src/screens/StatsScreen.tsx');

  check('both football leagues resolve through the shared map',
    cat.includes("if (def.sport === 'NCAAF' || def.sport === 'NFL')") && cat.includes('FOOTBALL_STAT_TO_MARKET'));
  check('neither league offers a model pick: rawPropModelForStat still bails on NCAAF',
    cat.includes("if (def.sport === 'NCAAF') return null;"));
  check('the half-credit tackles stat is NOT priced (CFBD halves a shared tackle, the book does not)',
    !/def_tackles: 'player_/.test(cat));
  check('a whole-credit sack maps normally', /def_sacks: 'player_sacks'/.test(cat));

  // Anytime TD: priced off a 0.5 rush+rec TD row, but never CALLED that on a bet.
  check('rush+rec TDs is priced by the anytime-TD market', /rush_rec_tds: 'player_anytime_td'/.test(cat));
  check('a bet made from it is named for the market, not the column',
    mk.includes("if (market === 'player_anytime_td') return 'Anytime TD';"));
  check('every bet made from the board carries the market name',
    screen.includes('const betLabel = propDisplayLabel(propMarket')
      && (screen.match(/statLabel=\{betLabel\}/g) ?? []).length === 2
      && !/statLabel=\{stat\?\.label \?\? ''\}[\s\S]{0,400}onOddsPress/.test(screen));
  check('the column header still shows the board\'s own stat name, never the market\'s',
    /const rightLabel =\s*\n\s*effectiveMode === 'hitRate' \? 'Hit Rate' : basis === 'perGame' \? 'Avg' : stat\.label;/.test(screen)
      && !/rightLabel[^\n]*betLabel/.test(screen));
  check('the one-way market is named as such rather than showing silent dashes',
    mk.includes("return market === 'player_anytime_td' && side === 'under';")
      && screen.includes('only posts the Yes side of'));
  check('the coverage check knows which side the board is asking',
    read('src/lib/statsOdds.ts').includes('side?: StatsOddsSide,')
      && screen.includes('bookPostsMarket(propLines.rows, propMarket, books, slateGameIds, side)'));

  // A stat no book prices must say so; a slate that is not today must say when.
  check('a column with no market at all explains itself',
    screen.includes('No sportsbook posts ${stat.label} lines.') && cat.includes('sportHasAnyPropMarket'));
  check('the note dates itself to the slate, not to "today"',
    screen.includes('const slateDayLabel =') && screen.includes('weekdayET(slate.date)'));
  check('football starts filtered to the slate, and the two places that decide agree',
    screen.includes('function defaultTonightOnly(sport: Sport)')
      && (screen.match(/defaultTonightOnly\(sport\)/g) ?? []).length === 2);
  check('the Stats board reads no model at all any more',
    !screen.includes('propModelForStat') && !screen.includes('useTodayPicks'));
}

// ── Per-book side coverage, and the Over/Under control it locks ─────────────
// Matt, 2026-09-05: "Nothing shows for Cesar's and FanDuel. I think we should
// have those lines … if we are getting betting lines for a Sportsbook we
// should show it as an option and display those lines."
//
// We DO have them, and the rows below are the real ones: FanDuel and Caesars
// post no standard `batter_hits` market at all that day, only the milestone
// market (1+ / 2+ Hits) folded onto it — which carries an OVER price and no
// Under. So their At-Least column is priced and their At-Most column can never
// be, and the two facts must be told apart.
{
  const real = (
    bookmaker: string,
    market: string,
    line: number,
    over: number | null,
    under: number | null,
  ): PropOddsByBookRow =>
    ({
      game_id: 'MLB_2026-09-05_WSH_LAD',
      market,
      player_name: 'Mookie Betts',
      bookmaker,
      line,
      over_price: over,
      under_price: under,
      over_link: null,
      under_link: null,
    }) as unknown as PropOddsByBookRow;

  // v_latest_prop_odds_all_books, 2026-09-05, Betts, batter_hits(+alternate).
  const rows = foldAlternateRows([
    real('draftkings', 'batter_hits', 0.5, -237, 175),
    real('draftkings', 'batter_hits_alternate', 1.5, 234, null),
    real('fanduel', 'batter_hits_alternate', 0.5, -260, null),
    real('fanduel', 'batter_hits_alternate', 1.5, 210, null),
    real('williamhill_us', 'batter_hits_alternate', 0.5, -280, null),
    real('williamhill_us', 'batter_hits_alternate', 1.5, 195, null),
  ]);

  const cov = bookCoverageForMarket(rows, 'batter_hits', [
    'draftkings',
    'fanduel',
    'williamhill_us',
    'betmgm',
  ]);

  check('FanDuel IS carried for Hits — the At-Least side is priced',
    cov.get('fanduel')?.over === true, `-260 at 0.5`);
  check('Caesars IS carried for Hits — the At-Least side is priced',
    cov.get('williamhill_us')?.over === true, `-280 at 0.5`);
  check('neither posts an At-Most Hits price, and that is recorded separately',
    cov.get('fanduel')?.under === false && cov.get('williamhill_us')?.under === false);
  check('DraftKings posts both sides', cov.get('draftkings')?.over === true && cov.get('draftkings')?.under === true);
  check('a selected book with no row for the market is absent, not falsely covered',
    !cov.has('betmgm'));
  // Presence in the map is read as "we have something here" everywhere. A row
  // carrying a line and no price on either side is not that.
  check('a priced-at-neither-side row never seats a book in the map',
    !bookCoverageForMarket(
      [real('betmgm', 'batter_hits', 0.5, null, null)],
      'batter_hits',
      ['betmgm'],
    ).has('betmgm'));
  check('a book the member did not select never enters the map',
    !bookCoverageForMarket(rows, 'batter_hits', ['draftkings']).has('fanduel'));
  check('the sport bound holds here too',
    bookCoverageForMarket(rows, 'batter_hits', ['fanduel'], new Set(['NBA_x'])).size === 0);

  // The control the coverage locks.
  const fdOnly = bookCoverageForMarket(rows, 'batter_hits', ['fanduel']);
  check('a FanDuel member gets At Least and loses At Most',
    anyBookPostsSide(fdOnly, 'over') && !anyBookPostsSide(fdOnly, 'under'));
  const bothBooks = bookCoverageForMarket(rows, 'batter_hits', ['draftkings', 'fanduel']);
  check('adding DraftKings gives the At-Most side back',
    anyBookPostsSide(bothBooks, 'over') && anyBookPostsSide(bothBooks, 'under'));

  const screen2 = read('src/screens/StatsScreen.tsx');
  // THE PICKER'S NOTE IS COMPUTED OVER EVERY BOOK IT LISTS, not over the ones
  // already selected. Off the selected set, a DraftKings-only member would see
  // "No Hits lines today" under FanDuel, Caesars and every other unselected
  // row — the precise false impression this change exists to remove.
  check('the picker note reads coverage for every book the picker lists',
    screen2.includes('bookCoverageForMarket(propLines.rows, propMarket, BOOKS, slateGameIds)')
      && screen2.includes('const c = coverageAll.get(book);'));
  check('while the direction lock still reads only the member\'s own books',
    screen2.includes('bookCoverageForMarket(propLines.rows, propMarket, books, slateGameIds)')
      && screen2.includes("anyBookPostsSide(coverage, 'under')"));
  check('the board knows which side the member\'s books sell',
    screen2.includes("const underAvailable = !sideKnown || anyBookPostsSide(coverage, 'under');")
      && screen2.includes("const sideOfMode = useCallback((m: HitMode) => selectionFor(1, m).side, []);"));
  check('a one-sided book marks the mode it cannot price rather than locking the control',
    // Three modes, two sides: an over-only book leaves At Least AND Over live,
    // so locking the whole pill (as the two-mode version had to) would now
    // take away more than the books took.
    read('src/components/HitModeSheet.tsx').includes("const priced = m.mode === 'under' ? underAvailable : overAvailable;")
      && read('src/components/HitModeSheet.tsx').includes('disabled={!priced}')
      && screen2.includes('overAvailable={overAvailable}'));
  check('and snaps the board off a mode the books cannot price, so nobody is stranded',
    screen2.includes('if (!modeAvailable(fallback)) return;')
      && screen2.includes('if (hitMode !== fallback) setHitMode(fallback);'));
  check('the lock FAILS OPEN while the lines are loading or the read failed',
    screen2.includes("const sideKnown = coverageReady && slateGameIds.size > 0 && coverage.size > 0;")
      && screen2.includes("propLines.status === 'ok'"));
  check('the greyed pill names the book rather than going silent',
    screen2.includes('const dirLockNote =') && screen2.includes('booksName(books)'));
  // UX review, 2026-09-05. Each of these was a finding; each is now a pin.
  check('the lock reason joins the ONE coverage note, not a second caption',
    screen2.includes('? { text: dirLockNote, canSwitch: true }')
      && !screen2.includes('styles.dirLockNote'));
  check('and it offers the action that lifts it — canSwitch opens the picker',
    screen2.includes('? { text: dirLockNote, canSwitch: true }')
      && screen2.includes('onPress={noLinesNote.canSwitch ? () => setPickerOpen(true) : undefined}'));
  // Scoped to the style block itself: a loose [\\s\\S] window runs past the
  // closing brace into later styles that legitimately use opacity.
  const dirPillLockedBlock = screen2.slice(
    screen2.indexOf('dirPillLocked: {'),
    screen2.indexOf('},', screen2.indexOf('dirPillLocked: {')),
  );
  check('the locked pill sheds the chip rather than fading it (a dimmed bordered chip reads as a button)',
    dirPillLockedBlock.includes("backgroundColor: 'transparent'")
      && dirPillLockedBlock.includes("borderColor: 'transparent'")
      && !dirPillLockedBlock.includes('opacity:'));
  check('VoiceOver hears the side once, and no disabled state on static text',
    !screen2.includes('accessibilityState={{ disabled: dirLocked }}')
      && !screen2.includes('disabled={dirLocked}'));
  check('the pill always opens the menu, and always has a touch target',
    // It is never locked now, so it is never a control without a target.
    /onPress=\{\(\) => setModeOpen\(true\)\}\s*\n\s*hitSlop=/.test(screen2));
  check('the member\'s chosen mode survives a snap and is restored',
    screen2.includes("const requestedMode = useRef<HitMode>('atLeast');")
      && screen2.includes('requestedMode.current = m;')
      && screen2.includes('if (hitMode !== wanted) setHitMode(wanted);')
      // and the picker applies through chooseMode, or the snap would forget it
      && screen2.includes('onPick={chooseMode}'));
  check('the snap is announced, and only once per stat and book set',
    screen2.includes('snapAnnounced.current = key;') && screen2.includes('showToast('));
  check('and never runs in Totals mode, where there is no pill and no caption to explain it',
    screen2.includes("if (effectiveMode !== 'hitRate') return;"));
  check('every picker row carries a sub-line, the covered case included',
    screen2.includes('return `Both sides for ${statLabel} ${when}`;')
      && screen2.includes('return `At Least only for ${statLabel} ${when}`;'));
  // A POSITIVE sentence about the books takes booksName; booksNoneName is the
  // subject of a negative one and would invert the meaning at two books
  // ("Neither DraftKings nor FanDuel post only At Least lines").
  check('and says it in the affirmative voice, not the negative helper',
    /dirLockNote[\s\S]{0,400}booksName\(books\)/.test(screen2)
      && !/dirLockNote[\s\S]{0,400}booksNoneName\(books\)/.test(screen2));

  // The picker EXPLAINS, it never removes a book.
  const picker = read('src/components/SportsbookPickerSheet.tsx');
  check('the picker still lists every bettable book — coverage is a note, not a filter',
    picker.includes('{BOOKS.map((b) => {')
      && !/BOOKS\.filter\([^)]*coverage/.test(picker));
  check('the note never disables a row',
    !/disabled=\{[^}]*note/.test(picker) && picker.includes('const note = last ? null : (coverageNote?.(b) ?? null);'));
  check('the note reaches VoiceOver as well as the eye',
    picker.includes('`${bookName(b)}. ${note}`'));
  check('the Stats screen is the only caller that passes one',
    screen2.includes('coverageNote={coverageNote}')
      && !read('src/screens/SettingsScreen.tsx').includes('coverageNote'));
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

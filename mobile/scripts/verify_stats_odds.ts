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

import {
  ambiguousKeys,
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
  book: 'draftkings',
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

const mgm = buildQuoteIndex(SLATE, { ...DK_OVER_0_5, book: 'betmgm' });
check('a BetMGM user sees BetMGM’s number, not DK’s', mgm.get('mookie betts')?.price === -250);
check(
  'a BetMGM user sees NOTHING for a player only DK prices — no DraftKings fallback',
  !mgm.has('freddie freeman') && !mgm.has('george springer'),
);
const fd = buildQuoteIndex(SLATE, { ...DK_OVER_0_5, book: 'fanduel' });
check('a FanDuel user sees an empty column when FanDuel posts no batter_hits', fd.size === 0);
check(
  'and the board can SAY that: bookPostsMarket is false for FanDuel, true for DK',
  !bookPostsMarket(SLATE, 'batter_hits', 'fanduel', SLATE_IDS) &&
    bookPostsMarket(SLATE, 'batter_hits', 'draftkings', SLATE_IDS),
);
check(
  'bookPostsMarket is a DAY/BOOK fact, not a line fact (DK posts hits even off the 0.5 line)',
  bookPostsMarket(SLATE, 'batter_hits', 'draftkings', SLATE_IDS) ===
    bookPostsMarket(SLATE.filter((r) => !sameLine(Number(r.line), 0.5)), 'batter_hits', 'draftkings', SLATE_IDS),
);

// ── 3. The line is the RULER's line, never the model's ──

const at1_5 = buildQuoteIndex(SLATE, { ...DK_OVER_0_5, line: 1.5 });
check(
  'a 2+ Hits board shows the 1.5 price, not the 0.5 one',
  at1_5.get('mookie betts')?.price === 125 && at1_5.get('mookie betts')?.line === 1.5,
);
check('a player DK prices only at 0.5 has no cell on a 2+ board (different bet)', !at1_5.has('christian yelich'));
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
  book: 'draftkings',
  gameIds: new Set(['WNBA_2026-09-03_LV_CHI']),
});
check('a WNBA board never shows an NBA price for the same market', wnbaOnly.size === 1 && wnbaOnly.has('a wilson'));
check(
  'no game bound = no sport filter (fail open, never blank the column)',
  buildQuoteIndex(BASKET, { market: 'player_points', line: 19.5, side: 'over', book: 'draftkings', gameIds: null }).size === 2,
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

const ml = buildTeamLineIndex(GAME_LINES, GAMES, { market: 'h2h', book: 'fanduel' });
check('the home team gets the home moneyline, with its link', ml.get('LAD')?.price === -170 && ml.get('LAD')?.link === 'fd/lad');
check('the away team gets the away moneyline of the same game', ml.get('STL')?.price === 142 && ml.get('STL')?.opponent === 'LAD' && ml.get('STL')?.isHome === false);
check('one row per team, two teams per game', ml.size === 4);
check('ONLY the selected book: DK’s number never leaks onto a FanDuel column', ml.get('LAD')?.price !== -165);
check('a team with no game on the slate has no line', !ml.has('NYY'));

const sp = buildTeamLineIndex(GAME_LINES, GAMES, { market: 'spreads', book: 'fanduel' });
check('the favourite’s spread is negative from its side, the dog’s positive',
  sp.get('LAD')?.line === -1.5 && sp.get('STL')?.line === 1.5 && sp.get('STL')?.price === -140);
check('caption prints the sign', teamLineCaption(sp.get('LAD')!) === '−1.5' && teamLineCaption(sp.get('STL')!) === '+1.5');
check('a game the book has not spread yet yields no spread row', !sp.has('BAL'));

const tot = buildTeamLineIndex(GAME_LINES, GAMES, { market: 'totals', book: 'fanduel' });
check('both sides of a game share the game total, over side', tot.get('LAD')?.line === 8.5 && tot.get('STL')?.price === -108);
check('total caption reads o8.5', teamLineCaption(tot.get('LAD')!) === 'o8.5');
check('a DK user on a FanDuel-only fixture sees the DK moneyline and nothing else',
  buildTeamLineIndex(GAME_LINES, GAMES, { market: 'h2h', book: 'draftkings' }).size === 2);

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
  !buildTeamLineIndex(GAME_LINES, [started, later], { market: 'h2h', book: 'fanduel', gameIds: live }).has('LAD') &&
    buildTeamLineIndex(GAME_LINES, [started, later], { market: 'h2h', book: 'fanduel', gameIds: live }).has('BAL'),
);
check(
  'and so does the player index (Betts’ game started → no cell)',
  !buildQuoteIndex(SLATE, { ...DK_OVER_0_5, gameIds: live }).has('mookie betts') &&
    buildQuoteIndex(SLATE, { ...DK_OVER_0_5, gameIds: live }).has('trevor story'),
);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

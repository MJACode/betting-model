/**
 * The Stats line pill ASKS, and the betslip prices a line leg at every book.
 *
 * Run with:  npx tsx scripts/verify_line_legs.ts
 *
 * Matt, 2026-09-04: "when you click on one of the records bet lines, it
 * shouldn't take you directly to the book, it should ask you if you want to
 * add to bet slip then bet slip should allow you to add to any book." This
 * reverses the same morning's "the pill is the bet link", so the old guard in
 * verify_stats_pill.ts is retired here and the new shape pinned:
 *
 *  1. A line leg is priced at DraftKings when DraftKings posts the line, at
 *     the best bettable book otherwise, and carries every other bettable
 *     book's price for the Open-with row. No bettable price → no leg.
 *  2. Its win probability is odds-implied (fair value): a line leg can never
 *     be a source of edge.
 *  3. The betslip does not credit DraftKings with a leg it never posted, and
 *     the hand-off button falls through to a book that prices every leg.
 *  4. The pill opens the sheet; nothing on the Stats board opens a book.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { isLineLeg, lineLegFromRows, lineLegKey, lineLegPickId, LINE_LEG_MODEL_ID } from '../src/lib/lineLegs';
import { handoffBookFor, priceBooksForParlay, savedHandoffBookFor, savedLegToParlayLeg, toSavedParlay } from '../src/lib/parlay';
import { marketClassForModel } from '../src/lib/markets';
import type { GameRow, PropOddsByBookRow } from '../src/types';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const row = (bookmaker: string, line: number, over: number | null, under: number | null, extra: Partial<PropOddsByBookRow> = {}): PropOddsByBookRow => ({
  game_id: 'MLB_2026-09-04_WSH_LAD',
  game_date: '2026-09-04',
  market: 'batter_hits',
  player_name: 'Mookie Betts',
  team: 'LAD',
  bookmaker,
  line,
  over_price: over,
  under_price: under,
  over_link: `https://${bookmaker}/over`,
  under_link: null,
  snapshot_at: '2026-09-04T16:17:01-04:00',
  ...extra,
});
const game = {
  game_id: 'MLB_2026-09-04_WSH_LAD', sport: 'MLB', season: 2026, game_date: '2026-09-04',
  home_team: 'LAD', away_team: 'WSH', home_score: null, away_score: null, home_score_f5: null,
  away_score_f5: null, commence_time: '2026-09-05T02:11:00+00:00', home_win: null, home_win_reg: null, went_to_ot: 0,
} as GameRow;
const spec = { game_id: game.game_id, sport: 'MLB', market: 'batter_hits', player_name: 'Mookie Betts', team: 'LAD', line: 0.5, side: 'over' as const, statLabel: 'Hits' };

// ── 1. pricing ──────────────────────────────────────────────────────────────
{
  const rows = [row('draftkings', 0.5, -250, 184), row('fanduel', 0.5, -235, 175), row('espnbet', 0.5, -200, 160), row('betmgm', 1.5, 230, -320)];
  const leg = lineLegFromRows(spec, rows, game);
  check('a line DraftKings posts is priced at DraftKings', leg?.americanOdds === -250 && leg?.dkPriced === true, `${leg?.americanOdds} dk=${leg?.dkPriced}`);
  check('the other bettable books ride along for Open-with', leg?.bookPrices.map((b) => b.bookmaker).join() === 'fanduel', leg?.bookPrices.map((b) => b.bookmaker).join());
  check('a reference-only book (ESPN BET) never prices a leg', !leg?.bookPrices.some((b) => b.bookmaker === 'espnbet'));
  check('a book on a DIFFERENT line is a different bet and is left out', !leg?.bookPrices.some((b) => b.bookmaker === 'betmgm'));
  check('the label is the proposition', leg?.label === 'Mookie Betts Over 0.5 Hits', leg?.label);
  check('the leg carries the game for its matchup', leg?.game?.game_id === game.game_id);
  check('DraftKings deep link rides on the leg', leg?.dkLink === 'https://draftkings/over');
}
{
  const rows = [row('fanduel', 0.5, -235, 175), row('betmgm', 0.5, -220, 170)];
  const leg = lineLegFromRows(spec, rows, game);
  check('a line DraftKings does NOT post is priced at the best bettable book', leg?.americanOdds === -220 && leg?.dkPriced === false, `${leg?.americanOdds} dk=${leg?.dkPriced}`);
  check('every bettable book still rides along', leg?.bookPrices.length === 2, `${leg?.bookPrices.length}`);
}
{
  const leg = lineLegFromRows(spec, [row('espnbet', 0.5, -200, 160), row('pinnacle', 0.5, -210, 170)], game);
  check('no bettable price at that line → no leg (the slip prunes it)', leg === null);
  const under = lineLegFromRows({ ...spec, side: 'under' }, [row('draftkings', 0.5, -250, null)], game);
  check('a side the book does not price is not a leg either', under === null);
}

// ── 2. fair value ───────────────────────────────────────────────────────────
{
  const leg = lineLegFromRows(spec, [row('draftkings', 0.5, -250, 184)], game)!;
  const implied = 250 / 350;
  check('win probability is odds-implied, so the leg adds no edge', Math.abs(leg.modelProb - implied) < 1e-9 && leg.legEdge === 0, `${leg.modelProb}`);
  check('it is not a model pick and not a game line', leg.pick === null && leg.isGameLine === false && leg.modelId === LINE_LEG_MODEL_ID);
  check('correlation treats it as offense-neutral', marketClassForModel(LINE_LEG_MODEL_ID) === 'other');
  check('isLineLeg recognises it', isLineLeg(leg));
  const key = lineLegKey(spec);
  check('the key is the proposition, not the price', key === 'line:MLB_2026-09-04_WSH_LAD|batter_hits|Mookie Betts|0.5|over', key);
  check('the pickId is stable and far below custom legs', lineLegPickId(key) === leg.pickId && leg.pickId <= -1_000_000_000);
}

// ── 3. the betslip's per-book pricing ───────────────────────────────────────
{
  const dkLess = lineLegFromRows(spec, [row('fanduel', 0.5, -235, 175), row('betmgm', 0.5, -220, 170)], game)!;
  const quotes = priceBooksForParlay([dkLess], 1, ['draftkings', 'fanduel', 'betmgm', 'betrivers']);
  const dk = quotes.find((q) => q.book === 'draftkings')!;
  const fd = quotes.find((q) => q.book === 'fanduel')!;
  const br = quotes.find((q) => q.book === 'betrivers')!;
  check('DraftKings is NOT credited with a leg it never posted', dk.priced === 0 && dk.decimalPayout == null, `${dk.priced}/${dk.total}`);
  check('FanDuel prices it at its own number', fd.priced === 1 && Math.round(fd.americanOdds ?? 0) === -235, `${fd.americanOdds}`);
  check('a book that does not post it shows coverage, not a price', br.priced === 0);
  const off = handoffBookFor([dkLess], ['draftkings']);
  check('the bet button falls through to a book that prices every leg', off.book === 'betmgm', off.book);
  const withDk = lineLegFromRows(spec, [row('draftkings', 0.5, -250, 184), row('fanduel', 0.5, -235, 175)], game)!;
  check('with DraftKings posting it the button keeps its DraftKings default', handoffBookFor([withDk], ['draftkings']).book === 'draftkings');
  check('and a FanDuel member is sent to FanDuel', handoffBookFor([withDk], ['fanduel']).book === 'fanduel');
}

// ── 3b. the review's fixes: coverage, saved parlays, the card ───────────────
{
  const dkLess = lineLegFromRows(spec, [row('fanduel', 0.5, -235, 175), row('betmgm', 0.5, -220, 170)], game)!;
  const off = handoffBookFor([dkLess], ['draftkings']);
  check('the hand-off reports coverage', off.priced === 1 && off.total === 1 && off.posted[0] === true);
  const dkOnly = { ...spec, player_name: 'Bryce Harper' };
  const withDk = lineLegFromRows(dkOnly, [row('draftkings', 0.5, -161, 121, { player_name: 'Bryce Harper' })], game)!;
  const mixed = handoffBookFor([dkLess, withDk], ['draftkings']);
  check('no book prices every leg → the button says how many it covers', mixed.priced === 1 && mixed.total === 2, `${mixed.book} ${mixed.priced}/${mixed.total}`);
  check('the leg the book does not post is marked not posted, not "add manually"', mixed.posted.includes(false));
  check('a DK-less leg names the book it was priced at', dkLess.pricedAt === 'betmgm', dkLess.pricedAt);

  const saved = toSavedParlay([dkLess, withDk], 'MLB');
  const sl = saved.legs[0]!;
  check('a saved line leg keeps its game, its coverage and its DK status', sl.gameId === game.game_id && sl.dkPriced === false && sl.bookLinks != null && 'fanduel' in sl.bookLinks);
  check('a saved DK-posted line leg carries the DK link', saved.legs[1]!.dkBetLink === 'https://draftkings/over' && saved.legs[1]!.dkPriced === true);
  const savedOff = savedHandoffBookFor([sl], ['draftkings']);
  check('the saved hand-off does not credit DK with a line it never posted', savedOff.book === 'fanduel', savedOff.book);
  const savedBoth = savedHandoffBookFor(saved.legs, ['draftkings']);
  check('with no book covering every saved leg the button falls back to DK, never to a book missing a leg', savedBoth.book === 'draftkings', savedBoth.book);
  check('a restored line leg keeps dkPriced', savedLegToParlayLeg(sl).dkPriced === false);

  const card = read('src/components/ParlayLegCard.tsx');
  check('the leg card labels a line leg\'s probability as implied', card.includes("`implied ${formatPct(leg.modelProb)}`"));
  check('the leg card names the pricing book when DK did not post it', card.includes('leg.dkPriced === false && leg.pricedAt'));
  const meta = read('src/lib/modelMeta.ts');
  check('the model chip never shows the raw stats_line id', meta.includes("if (modelId === 'stats_line') return 'Your line';"));
  const screen = read('src/screens/ParlayScreen.tsx');
  check('the slip attributes its price to DraftKings only when every leg is DK\'s', screen.includes('const allDk = legs.every((l) => l.dkPriced !== false);') && screen.includes("allDk ? 'DK imp.' : 'Implied'"));
  check('the hold note names the exception', screen.includes('Priced at DraftKings, except ${exception}'));
  check('the header count includes line legs', screen.includes('{slipCount}'));
  check('stale line legs clear through their own store', screen.includes("key.startsWith('line:') ? lineLegs.remove(key) : slip.remove(key)"));
  check('a partial hand-off says how many legs the book prices', screen.includes('prices {handoff.priced} of {handoff.total} legs'));
  const handoff = read('src/components/ParlayDkHandoff.tsx');
  check('the hand-off row says "not posted" rather than "add manually" for an unposted line', handoff.includes('Not posted at {name}'));
  const teams = read('src/components/TeamsBoard.tsx');
  check('the Teams pill, which still leaves the app, carries the arrow-out glyph', /name="open-outline"[^\n]*size=\{11\}/.test(teams));
  const sheet = read('src/components/AddLineSheet.tsx');
  check('the sheet says under its title where the book is chosen', sheet.includes("you&apos;ll choose the sportsbook there"));
  check('the sheet marks the member\'s own books', sheet.includes(">Yours<") && sheet.includes('usePreferredBooks()'));
  check('the sheet\'s title is the proposition', sheet.includes('const title = spec ? lineLegLabel(spec) : \'\';'));
  check('the close control is a button to VoiceOver', /accessibilityRole="button" accessibilityLabel="Close"/.test(sheet));
  check('no fixed-size badge and no hex literal', !/badge: \{[^}]*\bwidth: 40/.test(sheet) && !sheet.includes("'#000'"));
}

// ── 4. the pill asks ────────────────────────────────────────────────────────
{
  const stats = read('src/screens/StatsScreen.tsx');
  const sheet = read('src/components/AddLineSheet.tsx');
  const teams = read('src/components/TeamsBoard.tsx');
  check('StatsScreen never opens a sportsbook from the pill', !stats.includes('openBookBetslip('));
  check('the pill opens AddLineSheet', stats.includes('<AddLineSheet') && stats.includes('setLineSheet(quote)'));
  check('the sheet adds a LINE leg, never a pick', sheet.includes('legs.add(spec)') && !sheet.includes('slip.add('));
  check('the sheet offers Remove when the leg is already in', sheet.includes("'Remove from betslip'"));
  check('the sheet never opens a book', !sheet.includes('openBookBetslip'));
  check('VoiceOver hint says what a tap does', stats.includes('accessibilityHint="Asks to add this line to your betslip"'));
  check('the Teams board pill still opens the book (team line legs: follow-up, stated in the PR)', teams.includes('openBookBetslip('));
  const resolved = read('src/hooks/useResolvedSlip.ts');
  check('the slip re-prices line legs from the latest lines', resolved.includes('fetchPropLineRows(') && resolved.includes('lineLegFromRows('));
  check('a failed re-price HOLDS the leg rather than pruning it', resolved.includes('return [key, undefined]; // read failed: hold, never prune'));
  const bar = read('src/components/BetslipBar.tsx');
  check('the betslip bar counts line legs', bar.includes('slip.count + lineLegs.count'));
  const parlay = read('src/screens/ParlayScreen.tsx');
  check('the betslip removes and clears line legs through their own store', parlay.includes('lineLegs.remove(line.slipKey)') && parlay.includes('lineLegs.clear()'));
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);

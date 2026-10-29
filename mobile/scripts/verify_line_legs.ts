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
 *  5. (2026-09-05) A Teams-board pill asks the same way, and a GAME line leg
 *     — moneyline, spread at the board's number, the total — is priced,
 *     keyed and saved like a prop line leg, and counts as a game line for
 *     the correlation guard.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { canSaveEdit, foldAltGameRows, gameEditMenu, initialEditSegment, gameLineLegFromRows, isLineLeg, lineLegsAfterReplace, lineOptionsFromRows, withLine, type PropLineLegSpec, lineLegFromRows, lineLegKey, lineLegLabel, lineLegPickId, LINE_LEG_MODEL_ID, propLineSheetInput, teamLineSheetInput, type GameLineLegSpec } from '../src/lib/lineLegs';
import { handoffBookFor, isValidCombo, priceBooksForParlay, savedHandoffBookFor, savedLegToParlayLeg, toSavedParlay } from '../src/lib/parlay';
import { lineLegsAfterEdit } from '../src/lib/betslipGuard';
import { EMPTY_INJURY_INDEX } from '../src/lib/injuryStatus';
import { buildTeamLineIndex, type StatsOddsQuote } from '../src/lib/statsOdds';
import { marketClassForModel } from '../src/lib/markets';
import type { GameRow, OddsByBookRow, PropOddsByBookRow } from '../src/types';

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
  check('the Teams pill no longer carries the arrow-out glyph: it does not leave the app', !/name="open-outline"/.test(teams));
  const sheet = read('src/components/AddLineSheet.tsx');
  check('the sheet says under its title where the book is chosen', sheet.includes('you’ll choose the sportsbook there'));
  check('the sheet marks the member\'s own books', sheet.includes(">Yours<") && sheet.includes('usePreferredBooks()'));
  check('the sheet\'s title is the proposition',
    sheet.includes('const title = input?.title ?? (spec ? lineLegLabel(spec) : \'\');'));
  check('the close control is a button to VoiceOver', /accessibilityRole="button" accessibilityLabel="Close add line"/.test(sheet));
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
  check(
    'VoiceOver hint says what a tap does, and a sidelined pill does not offer it',
    stats.includes("accessibilityHint: 'Asks to add this line to your betslip'") &&
      stats.includes('...(pill.pressable ? { accessibilityHint:'),
  );
  check('the Teams board pill opens the sheet and never a book', teams.includes('setLineSheet(quote)') && teams.includes('<AddLineSheet') && !teams.includes('openBookBetslip'));
  check('the Teams pill hint says what a tap does', teams.includes('accessibilityHint="Asks to add this line to your betslip"'));
  const resolved = read('src/hooks/useResolvedSlip.ts');
  check('the slip re-prices line legs from the latest lines', resolved.includes('fetchPropLineRows(') && resolved.includes('lineLegFromRows('));
  check('a failed re-price HOLDS the leg rather than pruning it', resolved.includes('return [key, undefined]; // read failed: hold, never prune'));
  const bar = read('src/components/BetslipBar.tsx');
  check('the betslip bar counts line legs', bar.includes('slip.count + lineLegs.count'));
  const parlay = read('src/screens/ParlayScreen.tsx');
  check('the betslip removes and clears line legs through their own store', parlay.includes('lineLegs.remove(line.slipKey)') && parlay.includes('lineLegs.clear()'));
}

// ── 5. game line legs from the Teams board ──────────────────────────────────
{
  const grow = (bookmaker: string, extra: Partial<OddsByBookRow> = {}): OddsByBookRow => ({
    game_id: game.game_id, game_date: '2026-09-04', market: 'spreads', bookmaker,
    home_price: -120, away_price: 100, over_price: -110, under_price: -110, spread_home: -1.5, total_line: 8.5,
    home_link: `https://${bookmaker}/home`, away_link: `https://${bookmaker}/away`, over_link: `https://${bookmaker}/over`, under_link: null,
    snapshot_at: '2026-09-04T16:17:01-04:00', ...extra,
  });
  const rows = [grow('draftkings'), grow('fanduel', { home_price: -125, away_price: 105 }), grow('betmgm', { spread_home: -2.5, home_price: 110 }), grow('pinnacle', { home_price: -118 })];
  const spread: GameLineLegSpec = { kind: 'game', game_id: game.game_id, sport: 'MLB', market: 'spreads', team: 'LAD', opponent: 'WSH', isHome: true, line: -1.5, side: null };
  const leg = gameLineLegFromRows(spread, rows, game)!;
  check('a spread leg is priced at DraftKings at the board\'s number', leg.americanOdds === -120 && leg.dkPriced === true && leg.pricedAt === 'draftkings', `${leg.americanOdds}`);
  check('a book on a different number is a different bet and is left out', !leg.bookPrices.some((b) => b.bookmaker === 'betmgm'));
  check('a reference-only book never prices a game leg', !leg.bookPrices.some((b) => b.bookmaker === 'pinnacle'));
  check('the label is the picks\' own idiom', leg.label === 'LAD -1.5', leg.label);
  check('a game line leg IS a game line for the correlation guard', leg.isGameLine === true);
  check('the DraftKings link rides on the leg', leg.dkLink === 'https://draftkings/home');
  const away: GameLineLegSpec = { ...spread, team: 'WSH', opponent: 'LAD', isHome: false, line: 1.5 };
  const awayLeg = gameLineLegFromRows(away, rows, game)!;
  check('the away side prices the away price at the mirrored number', awayLeg.americanOdds === 100 && awayLeg.label === 'WSH +1.5', `${awayLeg.americanOdds} ${awayLeg.label}`);
  check('home and away spreads are different propositions', lineLegKey(spread) !== lineLegKey(away));

  const ml: GameLineLegSpec = { ...spread, market: 'h2h', line: null };
  const mlLeg = gameLineLegFromRows(ml, rows.map((r) => ({ ...r, market: 'h2h', spread_home: null })), game)!;
  check('a moneyline leg has no number, so the book on another spread prices it too', mlLeg.label === 'LAD ML' && mlLeg.bookPrices.map((b) => b.bookmaker).sort().join() === 'betmgm,fanduel', `${mlLeg.label} ${mlLeg.bookPrices.map((b) => b.bookmaker).join()}`);

  const total: GameLineLegSpec = { ...spread, market: 'totals', line: 8.5, side: 'over' };
  const totalRows = rows.map((r) => ({ ...r, market: 'totals', spread_home: null }));
  const totalLeg = gameLineLegFromRows(total, totalRows, game)!;
  check('a total leg prices the Over at the board\'s number, labelled home-first like the server', totalLeg.americanOdds === -110 && totalLeg.label === 'LAD vs WSH Over 8.5', `${totalLeg.americanOdds} ${totalLeg.label}`);
  check('a whole-number line prints one decimal, byte for byte with pick_label', lineLegLabel({ ...total, line: 8 }) === 'LAD vs WSH Over 8.0' && lineLegLabel({ ...spread, line: -1 }) === 'LAD -1.0' && lineLegLabel({ ...away, line: 3 }) === 'WSH +3.0', `${lineLegLabel({ ...total, line: 8 })} ${lineLegLabel({ ...spread, line: -1 })}`);
  const totalFromAway: GameLineLegSpec = { ...total, team: 'WSH', opponent: 'LAD', isHome: false };
  check('the total is the game\'s, not the tapped team\'s: both rows make one leg', lineLegKey(total) === lineLegKey(totalFromAway));
  check('a total at another number is another bet', lineLegKey(total) !== lineLegKey({ ...total, line: 9 }));
  check('no bettable book at the number → no leg (the slip prunes it)', gameLineLegFromRows(spread, [grow('pinnacle'), grow('draftkings', { spread_home: -2.5 })], game) === null);
  check('the key says it is a game line', lineLegKey(spread).startsWith('line:') && lineLegKey(spread).includes('|spreads|LAD|-1.5|'));

  const mlPick = { ...mlLeg, slipKey: 'pick', pickId: 1, modelId: 'mlb_moneyline', isGameLine: true };
  check('the correlation guard refuses a game line leg beside a model game leg on the same game', !isValidCombo([leg, mlPick]));
  check('and allows a game line leg beside a prop line leg', isValidCombo([leg, lineLegFromRows(spec, [row('draftkings', 0.5, -250, 184)], game)!]));

  // The sheet's input from a Teams quote: every bettable book at the number.
  const idx = buildTeamLineIndex(rows, [game], { market: 'spreads', books: ['draftkings'] });
  const q = idx.get('LAD')!;
  check('a team quote carries every book\'s row at its number', q.bookRows.map((r) => r.bookmaker).sort().join() === 'draftkings,fanduel,pinnacle', q.bookRows.map((r) => r.bookmaker).join());
  const input = teamLineSheetInput(q, 'MLB');
  check('the sheet lists bettable books only, best price first', input.prices.map((p) => p.book).join() === 'draftkings,fanduel' && input.prices[0]!.price === -120, input.prices.map((p) => `${p.book}:${p.price}`).join());
  check('the sheet title is the proposition', lineLegLabel(input.spec) === 'LAD -1.5');
  const pq: StatsOddsQuote = { playerKey: 'mookie betts', playerName: 'Mookie Betts', gameId: game.game_id, market: 'batter_hits', line: 1.5, side: 'over', book: 'betmgm', price: 230, link: null, bookRows: [row('betmgm', 1.5, 230, -320)] as unknown as StatsOddsQuote['bookRows'], offLine: true };
  const pin = propLineSheetInput(pq, 'MLB', 'Hits', '1+ Hits');
  // The book's own number, in the book's own words (2026-09-06). It read
  // "only posts 2+" until then — the fan's idiom for a line the sentence had
  // just quoted the board's half-point version of, two vocabularies in one
  // breath.
  check('an off-line prop quote explains itself under the title', (pin.explainer ?? '').startsWith('The board is on 1+ Hits; BetMGM only posts Over 1.5.'), pin.explainer);
  check('an on-line prop quote has no explainer', propLineSheetInput({ ...pq, offLine: false }, 'MLB', 'Hits', '2+ Hits').explainer === undefined);
  const sheet = read('src/components/AddLineSheet.tsx');
  check('the sheet takes the shared input and builds no prop spec of its own', sheet.includes('input: LineSheetInput | null') && !sheet.includes('player_name: quote.playerName'));
  const resolved = read('src/hooks/useResolvedSlip.ts');
  check('the slip re-prices a game leg from its market\'s latest lines', resolved.includes('fetchGameLineRows(spec.game_id, spec.market)') && resolved.includes('gameLineLegFromRows('));
  const store = read('src/hooks/useLineLegs.ts');
  check('the store accepts a stored game spec', store.includes("if (s.kind === 'game')"));
  check('the sheet warns before a second game line on one game', sheet.includes('A parlay takes one game line per game.'));
  const teamsSrc = read('src/components/TeamsBoard.tsx');
  check('the Teams board bounces back to the betslip like Players', teamsSrc.includes('onAdded={onAdded}') && read('src/screens/StatsScreen.tsx').includes("<TeamsBoard sport={sport} onAdded={fromParlay"));
  check('VoiceOver hears the side of a total, not "o8.5"', teamsSrc.includes('`total over ${quote.line}`'));
  const picks = read('src/screens/PicksHomeScreen.tsx');
  check('the partial banner is one sentence with one reason and hides while reloading', picks.includes('{!error && !loading && partial ? (') && picks.includes('numberOfLines={3}') && picks.includes('accessibilityHint="Reloads today’s picks"'));
  const hook = read('src/hooks/useTodayPicks.ts');
  check('a look-ahead failure is named for what it is', hook.includes("swallow('the upcoming UFC card')") && !hook.includes("'UFC picks'"));
}

// ── Editing a line leg (Matt, 2026-10-28: "change it to 15") ────────────────
{
  const spec: PropLineLegSpec = {
    kind: 'prop', game_id: 'G', sport: 'NBA', market: 'player_points',
    player_name: 'Jaylen Brown', team: 'BOS', line: 9.5, side: 'over', statLabel: 'Points',
  };
  const row = (bookmaker: string, line: number | null, over: number | null, under: number | null, player = 'Jaylen Brown'): PropOddsByBookRow => ({
    game_id: 'G', game_date: '2026-10-28', market: 'player_points', player_name: player, team: 'BOS',
    bookmaker, line, over_price: over, under_price: under, over_link: null, under_link: null, snapshot_at: '',
  });
  const opts = lineOptionsFromRows(spec, [
    row('draftkings', 14.5, -490, null),
    row('fanduel', 14.5, -450, 320),
    row('draftkings', 9.5, -2000, null),
    row('draftkings', 19.5, -150, 115),
    row('notabook', 24.5, 200, -260),
    row('draftkings', 29.5, 400, null, 'Someone Else'),
    row('draftkings', null, -110, -110),
  ]);
  check('edit options: every posted line, lowest first, one per number',
    opts.map((o) => o.line).join(',') === '9.5,14.5,19.5', opts.map((o) => o.line).join(','));
  // DraftKings when it posts the side, else the best book — the leg's own
  // rule, so the sheet never shows a price the slip will not use.
  check('edit options: priced the way the leg is (DraftKings first, else the best book)',
    opts[1]!.over!.price === -490 && opts[1]!.over!.book === 'draftkings'
      && opts[1]!.under!.price === 320 && opts[1]!.under!.book === 'fanduel');
  check('edit options: a side nobody posts is empty, not invented',
    opts[0]!.under === null);
  const sheetRows = [row('draftkings', 14.5, -490, null), row('fanduel', 14.5, -450, 320)];
  const picked = lineOptionsFromRows(spec, sheetRows)[0]!;
  check('the price picked in the sheet is the price the slip then shows',
    lineLegFromRows(withLine(spec, 14.5, 'over'), sheetRows, null)!.americanOdds === picked.over!.price
      && lineLegFromRows(withLine(spec, 14.5, 'under'), sheetRows, null)!.americanOdds === picked.under!.price);
  const a = withLine(spec, 14.5, 'over');
  const b: PropLineLegSpec = { ...spec, player_name: 'Franz Wagner', team: 'ORL' };
  const specs = [spec, b];
  const after = lineLegsAfterReplace(specs, lineLegKey(spec), a);
  check('edit keeps the leg in its place in the slip',
    after != null && lineLegKey(after[0]!) === lineLegKey(a) && lineLegKey(after[1]!) === lineLegKey(b) && after.length === 2);
  check('editing to the same bet is a no-op',
    lineLegsAfterReplace(specs, lineLegKey(spec), withLine(spec, 9.5, 'over')) === null);
  check('editing onto a bet already on the slip is refused, not duplicated',
    lineLegsAfterReplace([spec, a], lineLegKey(spec), withLine(spec, 14.5, 'over')) === null);
  check('editing a leg that is gone does nothing',
    lineLegsAfterReplace([b], lineLegKey(spec), a) === null);
  const slipScreen = readFileSync(join(ROOT, 'src/screens/ParlayScreen.tsx'), 'utf-8');
  // Matt, 2026-10-29: game lines get the pencil too. Still never a model pick.
  check('the betslip offers edit on every Stats line leg and custom legs, never on a model pick',
    slipScreen.includes('onEdit={canEdit(leg) ? () => onEdit(leg.pickId) : undefined}') &&
      /if \(!isLineLeg\(leg\)\) return null;/.test(slipScreen) &&
      !slipScreen.includes('!isGameSpec(spec)') &&
      slipScreen.includes('lineLegs.replace(lineLegKey(editingLine), next)'));
}

// ── Editing a GAME line leg (Matt, 2026-10-29: "Yes") ───────────────────────
{
  const g = (bookmaker: string, market: string, o: Partial<OddsByBookRow>): OddsByBookRow => ({
    game_id: 'KC@BUF', game_date: '2026-11-01', market, bookmaker,
    home_price: null, away_price: null, over_price: null, under_price: null,
    spread_home: null, total_line: null, home_link: null, away_link: null,
    over_link: null, under_link: null, snapshot_at: '', ...o,
  });
  // BUF home. DK and FD hang BUF -3.5; MGM hangs BUF -2.5; a non-US book -4.5.
  const spreadRows = [
    g('draftkings', 'spreads', { spread_home: -3.5, home_price: -110, away_price: -110 }),
    g('fanduel', 'spreads', { spread_home: -3.5, home_price: -105, away_price: -115 }),
    g('betmgm', 'spreads', { spread_home: -2.5, home_price: -130, away_price: 110 }),
    g('notabook', 'spreads', { spread_home: -4.5, home_price: 120, away_price: -140 }),
  ];
  const kc: GameLineLegSpec = { kind: 'game', game_id: 'KC@BUF', sport: 'NFL', market: 'spreads', team: 'KC', opponent: 'BUF', isHome: false, line: 3.5, side: null };
  const menu = gameEditMenu(kc, spreadRows);
  const kcLines = menu.choices.filter((c) => c.segment === 'KC').map((c) => (c.spec as GameLineLegSpec).line);
  const bufLines = menu.choices.filter((c) => c.segment === 'BUF').map((c) => (c.spec as GameLineLegSpec).line);
  check('spread edit: each team at every number a bettable book hangs, signed for that team',
    kcLines.join(',') === '2.5,3.5' && bufLines.join(',') === '-3.5,-2.5', `${kcLines} | ${bufLines}`);
  const bufChoice = menu.choices.find((c) => c.segment === 'BUF' && (c.spec as GameLineLegSpec).line === -3.5)!;
  const bufSpec = bufChoice.spec as GameLineLegSpec;
  check('spread edit: switching team flips home/away and opponent, not the game',
    bufSpec.team === 'BUF' && bufSpec.opponent === 'KC' && bufSpec.isHome === true && bufSpec.market === 'spreads'
      && bufChoice.title === 'BUF -3.5');
  check('spread edit: priced the way the slip prices it (DraftKings first)',
    bufChoice.book === 'draftkings' && bufChoice.price === -110
      && gameLineLegFromRows(bufSpec, spreadRows, null)!.americanOdds === bufChoice.price);
  const kc25 = menu.choices.find((c) => c.segment === 'KC' && (c.spec as GameLineLegSpec).line === 2.5)!;
  check('spread edit: a number DraftKings does not hang is priced at the book that does',
    kc25.book === 'betmgm' && kc25.price === 110
      && gameLineLegFromRows(kc25.spec as GameLineLegSpec, spreadRows, null)!.americanOdds === 110);

  const totalRows = [
    g('draftkings', 'totals', { total_line: 47.5, over_price: -110, under_price: -110 }),
    g('fanduel', 'totals', { total_line: 48.5, over_price: -105, under_price: -115 }),
  ];
  const over: GameLineLegSpec = { ...kc, market: 'totals', line: 47.5, side: 'over' };
  const tm = gameEditMenu(over, totalRows);
  check('total edit: Over and Under at every posted total',
    tm.segments.map((x) => x.key).join() === 'over,under'
      && tm.choices.filter((c) => c.segment === 'under').map((c) => (c.spec as GameLineLegSpec).line).join() === '47.5,48.5');
  const under485 = tm.choices.find((c) => c.segment === 'under' && (c.spec as GameLineLegSpec).line === 48.5)!;
  check('total edit: the chosen side and number are what the slip prices',
    (under485.spec as GameLineLegSpec).side === 'under'
      && gameLineLegFromRows(under485.spec as GameLineLegSpec, totalRows, null)!.americanOdds === under485.price);

  const mlRows = [g('draftkings', 'h2h', { home_price: -180, away_price: 150 })];
  const mm = gameEditMenu({ ...kc, market: 'h2h', line: null }, mlRows);
  check('moneyline edit: the two teams, each at its own price',
    mm.choices.map((c) => `${c.title}:${c.price}`).join() === 'KC ML:150,BUF ML:-180');
  // UX review, 2026-10-29.
  check('a moneyline is one flat list, no tabs',
    mm.segments.length === 1 && mm.segments[0]!.key === 'all' && mm.choices.every((c) => c.segment === 'all'));
  const oneNumber = gameEditMenu(kc, [spreadRows[0]!]);
  check('a spread every book hangs at one number is one flat list of both sides',
    oneNumber.segments.length === 1 && oneNumber.choices.map((c) => c.title).join() === 'KC +3.5,BUF -3.5');
  check('a spread with several numbers keeps the team tabs', menu.segments.map((x) => x.key).join() === 'KC,BUF');
  check('total rows read "Over 47.5", not the repeated matchup',
    tm.choices.find((c) => c.segment === 'over')!.title === 'Over 47.5');
  check('the sheet opens on the leg\'s own tab, or the only one there is',
    initialEditSegment(menu, kc) === 'KC' && initialEditSegment(mm, { ...kc, market: 'h2h' as const, line: null }) === 'all');
  const bufKey = lineLegKey(bufSpec);
  check('Update saves only a choice on the visible tab',
    canSaveEdit(menu, 'BUF', bufKey, lineLegKey(kc)) && !canSaveEdit(menu, 'KC', bufKey, lineLegKey(kc)));
  check('Update is off for the leg as it already is',
    !canSaveEdit(menu, 'KC', lineLegKey(kc), lineLegKey(kc)));
  check('game menus say what is missing in game words',
    menu.segments[0]!.empty === 'No sportsbook has a KC spread right now.'
      && tm.segments[0]!.empty === 'No sportsbook posts the Over for this game right now.'
      && /hanging right now/.test(menu.subtitle) && /Switch sides/.test(mm.subtitle));
  // Alternate ladder (2026-10-29): folded into the main market's name, main
  // row wins a tie, and an alternate number is then a real edit choice that
  // the slip prices at the same row.
  const altRows = [
    g('draftkings', 'alternate_spreads', { spread_home: -3.5, home_price: -999, away_price: -999 }),
    g('draftkings', 'alternate_spreads', { spread_home: -6.5, home_price: 160, away_price: -190 }),
    g('fanduel', 'alternate_spreads', { spread_home: -6.5, home_price: 165, away_price: -200 }),
    g('draftkings', 'alternate_totals', { total_line: 51.5, over_price: 150, under_price: -180 }),
  ];
  const folded = foldAltGameRows('spreads', spreadRows, altRows);
  check('alternate rungs join the main market, and the main row wins its own number',
    folded.length === spreadRows.length + 2
      && folded.every((r) => r.market === 'spreads')
      && !folded.some((r) => r.home_price === -999));
  check('an alternate total never leaks into a spread menu',
    !folded.some((r) => r.total_line === 51.5));
  check('a market with no ladder is untouched', foldAltGameRows('h2h', mlRows, altRows).length === mlRows.length);
  const altMenu = gameEditMenu(kc, folded);
  const kc65 = altMenu.choices.find((c) => c.segment === 'KC' && (c.spec as GameLineLegSpec).line === 6.5)!;
  check('an alternate number is an edit choice, priced as the slip prices it',
    kc65 != null && kc65.book === 'draftkings' && kc65.price === -190
      && gameLineLegFromRows(kc65.spec as GameLineLegSpec, folded, null)!.americanOdds === -190);
  // UX review, 2026-10-29: a day-old DraftKings rung must not beat a fresh
  // main line another book hangs at the same number. BetMGM's main is
  // BUF -2.5 (KC +2.5 at +110); DraftKings only has -2.5 on its 6 AM ladder.
  const staleDk = g('draftkings', 'alternate_spreads', { spread_home: -2.5, home_price: -150, away_price: 125, snapshot_at: '2026-10-29T10:05:00Z' });
  const mixed = foldAltGameRows('spreads', spreadRows, [staleDk, ...altRows]);
  const kc25Mixed = gameEditMenu(kc, mixed).choices.find((c) => c.segment === 'KC' && (c.spec as GameLineLegSpec).line === 2.5)!;
  check('a fresh main price beats a day-old DraftKings alternate at the same number',
    kc25Mixed.book === 'betmgm' && kc25Mixed.price === 110
      && gameLineLegFromRows(kc25Mixed.spec as GameLineLegSpec, mixed, null)!.americanOdds === 110
      && gameLineLegFromRows(kc25Mixed.spec as GameLineLegSpec, mixed, null)!.pricedFromLadder === false);
  const kc65Leg = gameLineLegFromRows(kc65.spec as GameLineLegSpec, folded, null)!;
  check('a leg priced from the ladder says so, with the price\'s own stamp',
    kc65Leg.pricedFromLadder === true && kc65Leg.pricedAsOf === altRows[1]!.snapshot_at);
  check('ladder rows say how old they are; main rows say they are the main line',
    /^Alt · /.test(kc65.hint ?? '') && kc25Mixed.hint === 'Main line');
  check('no ladder, no alternate claim and no "Main line" on every row',
    !/alternate/.test(menu.subtitle) && menu.choices.every((c) => c.hint === null)
      && /including alternate lines/.test(altMenu.subtitle));
  check('the betslip reads the ladder and folds it, and a failed ladder read keeps the main lines',
    /\.from\('alt_game_lines'\)/.test(readFileSync(join(ROOT, 'src/lib/queries.ts'), 'utf-8'))
      && /if \(altRes\.error\) \{[\s\S]{0,120}return main;/.test(readFileSync(join(ROOT, 'src/lib/queries.ts'), 'utf-8')));
  check('a game edit is never refused as sidelined (no player to look up)',
    lineLegsAfterEdit([kc], lineLegKey(kc), bufSpec, EMPTY_INJURY_INDEX).outcome === 'ok');
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);

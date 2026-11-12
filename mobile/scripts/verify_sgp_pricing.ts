/**
 * Same-game parlay price estimate (src/lib/sgpPricing.ts and every surface
 * that prices a slip). Run with:
 *
 *   npx tsx scripts/verify_sgp_pricing.ts
 *
 * The fixture is the slip Matt sent on 2026-11-06: four NBA legs in two games
 * (MIA@GSW: Lendeborg O24.5 pts, Klay O3.5 3PM; ORL@PHX: Booker O29.5 pts,
 * Carter O9.5 reb). The app multiplied all four and showed +5993 at DraftKings
 * and +6040 at FanDuel; FanDuel's own slip priced it +4254 as two same-game
 * parlays.
 *
 * Pins:
 *  - Legs in DIFFERENT games are multiplied, exactly as before — no cut.
 *  - Legs sharing a game are cut once per game with 2+ legs, at every surface
 *    that shows a price: the headline (computeCorrelatedMetrics), the betslip
 *    bar (betslipSummary), each book tile (priceBooksForParlay) and a saved
 *    slip (computeParlayMetrics). The four must agree.
 *  - The default cut reproduces FanDuel's quote on the fixture from the app's
 *    own FanDuel tile (the measurement the default was taken from).
 *  - A book with SGP_MIN_OBSERVATIONS entries uses its own fit; fewer, or an
 *    out-of-band fit, uses the default.
 *  - A price entered for a book replaces the estimate at that book only.
 *  - Line-shopping across books is withheld for a same-game slip: a same-game
 *    parlay is one bet at one book.
 *  - Hand-typed custom legs never form a same-game group.
 */

import {
  betslipSummary,
  computeParlayMetrics,
  lineShopParlay,
  makeCustomLeg,
  priceBooksForParlay,
  slipSignature,
  type ParlayLeg,
} from '../src/lib/parlay';
import {
  computeCorrelatedMetrics,
  PARLAY_CORRELATION_PRIORS,
  withDecimalPayout,
} from '../src/lib/parlayCorrelation';
import {
  DEFAULT_SGP_HAIRCUT,
  SGP_MIN_OBSERVATIONS,
  applySgpHaircut,
  enteredPriceIsPlausible,
  haircutFor,
  impliedHaircut,
  parseEnteredAmerican,
  sameGameGroupCount,
  sgpShape,
} from '../src/lib/sgpPricing';
import { sgpCorrelationLift, sgpShapeFor } from '../src/lib/parlayCorrelation';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  console.log(`${cond ? '[PASS]' : '[FAIL]'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!cond) failures++;
}
const near = (a: number | null | undefined, b: number, tol: number) =>
  a != null && Number.isFinite(a) && Math.abs(a - b) <= tol;
const toDec = (am: number) => (am > 0 ? 1 + am / 100 : 1 + 100 / Math.abs(am));

/** A Stats-line style leg: a real game id, a DK price, one FanDuel price. */
function leg(id: number, gameId: string, dk: number, fd: number, label: string): ParlayLeg {
  return {
    pickId: id,
    slipKey: `${gameId}|line|${id}`,
    gameId,
    modelId: 'line',
    isGameLine: false,
    isLive: false,
    isFavorite: dk < 0,
    label,
    modelProb: 1 / toDec(dk),
    decimalOdds: toDec(dk),
    americanOdds: dk,
    legEdge: 0,
    bestBook: null,
    bookPrices: [{ bookmaker: 'fanduel', american: fd, decimal: toDec(fd), link: null }],
    pick: null,
    game: null,
    dkPriced: true,
  };
}

const MIA = 'NBA_2026-11-05_MIA_GSW';
const ORL = 'NBA_2026-11-05_ORL_PHX';
// DK prices from the app screenshot; Klay's DK price backed out of +5993.
// FanDuel prices chosen so the four multiply to the app's FD tile, +6040.
const slip: ParlayLeg[] = [
  leg(1, MIA, 279, 285, 'Yaxel Lendeborg Over 24.5 Points'),
  leg(2, ORL, 215, 215, 'Devin Booker Over 29.5 Points'),
  leg(3, ORL, 120, 120, 'Wendell Carter Jr Over 9.5 Rebounds'),
  leg(4, MIA, 132, 0, 'Klay Thompson Over 3.5 3PM'),
];
// Solve Klay's FD price so the FD multiplied total is exactly 61.40 (+6040).
{
  const others = toDec(285) * toDec(215) * toDec(120);
  const klay = 61.4 / others;
  slip[3].bookPrices = [{ bookmaker: 'fanduel', american: (klay - 1) * 100, decimal: klay, link: null }];
}

// ── grouping ────────────────────────────────────────────────────────────────

check('two games with two legs each = 2 same-game groups', sameGameGroupCount(slip) === 2);
check('one leg per game = no group', sameGameGroupCount([slip[0], slip[1]]) === 0);
check('custom legs never group', sameGameGroupCount([makeCustomLeg('a', 150), makeCustomLeg('b', 150)]) === 0);

// ── cross-game slips are unchanged ──────────────────────────────────────────

{
  const two = [slip[0], slip[1]];
  const m = computeParlayMetrics(two);
  check('cross-game payout = legs multiplied', near(m.decimalPayout, toDec(279) * toDec(215), 1e-9));
  check('cross-game is not an estimate', m.sgpGroups === 0 && m.decimalPayout === m.multipliedDecimal);
  const fd = priceBooksForParlay(two, 1, ['fanduel']).find((q) => q.book === 'fanduel');
  check('cross-game FD tile = FD legs multiplied', near(fd?.decimalPayout, toDec(285) * toDec(215), 1e-9) && fd?.sgpEstimated === false);
}

// ── the screenshot slip ─────────────────────────────────────────────────────

const quotes = priceBooksForParlay(slip, 1, ['draftkings', 'fanduel']);
const fd = quotes.find((q) => q.book === 'fanduel')!;
const dk = quotes.find((q) => q.book === 'draftkings')!;
check('FD multiplied price is the old +6040', near(fd.multipliedDecimal, 61.4, 1e-6));
check('FD tile is no longer +6040', fd.americanOdds != null && fd.americanOdds < 5000, `FD ${fd.americanOdds?.toFixed(0)}`);
// Per extra leg at the default, no NBA line-leg correlation: 61.40 x 0.863^2.
// The default is fitted on this slip and the NFL one below, so this is a
// consistency check, not an out-of-sample test.
check('FD tile within 6% of FanDuel’s own +4254', near(fd.decimalPayout, toDec(4254), toDec(4254) * 0.06), `FD ${fd.americanOdds?.toFixed(0)}`);
check('FD tile is marked an estimate', fd.sgpEstimated && !fd.entered);
check('DK tile is cut by the same default, per extra leg, off the profit',
  near(dk.decimalPayout, 1 + (dk.multipliedDecimal! - 1) * (1 - DEFAULT_SGP_HAIRCUT) ** 2, 1e-9));
check('two 2-leg games = 2 extra legs, lift 1 for line legs', (() => {
  const sh = sgpShapeFor(slip);
  return sh.groups === 2 && sh.extraLegs === 2 && sh.lift === 1;
})());

const headline = computeCorrelatedMetrics(slip, PARLAY_CORRELATION_PRIORS, undefined, 2000);
const bar = betslipSummary(slip, slip.length);
const saved = computeParlayMetrics(slip);
check('headline = DK tile', near(headline.decimalPayout, dk.decimalPayout!, 1e-9));
check('bar = headline', near(bar.americanOdds, headline.americanOdds, 1e-9) && bar.sgpEstimated);
check('saved slip = headline', near(saved.decimalPayout, headline.decimalPayout, 1e-9));
check('EV is on the estimated price, not the multiplied one',
  near(headline.ev, headline.jointProb * headline.decimalPayout - 1, 1e-12) && headline.decimalPayout < headline.multipliedDecimal);
check('no line-shop row on a same-game slip', lineShopParlay(slip, headline.jointProb, headline.ev) === null);

// ── fitted cuts ─────────────────────────────────────────────────────────────

check('a book with too few entries uses the default',
  haircutFor('fanduel', { fanduel: { haircut: 0.3, n: SGP_MIN_OBSERVATIONS - 1 } }) === DEFAULT_SGP_HAIRCUT);
check('a book with enough entries uses its own fit',
  haircutFor('fanduel', { fanduel: { haircut: 0.3, n: SGP_MIN_OBSERVATIONS } }) === 0.3);
check('an out-of-band fit is ignored',
  haircutFor('fanduel', { fanduel: { haircut: 0.9, n: 50 } }) === DEFAULT_SGP_HAIRCUT);
{
  const fits = { fanduel: { haircut: 0.3, n: 10 } };
  const q = priceBooksForParlay(slip, 1, ['draftkings', 'fanduel'], fits);
  check('fit applies to its own book only',
    near(q.find((x) => x.book === 'fanduel')!.decimalPayout, 1 + 60.4 * 0.7 ** 2, 1e-9) &&
    near(q.find((x) => x.book === 'draftkings')!.decimalPayout, dk.decimalPayout!, 1e-9));
}
{
  const sh = { groups: 1, extraLegs: 4, lift: 1.866 };
  check('impliedHaircut inverts applySgpHaircut (with a lift)',
    near(impliedHaircut(applySgpHaircut(96.64, sh, 'fanduel'), 96.64, sh), DEFAULT_SGP_HAIRCUT, 1e-12));
}

// ── entered prices ──────────────────────────────────────────────────────────

{
  const q = priceBooksForParlay(slip, 1, ['draftkings', 'fanduel'], undefined, { fanduel: 4254 });
  const f = q.find((x) => x.book === 'fanduel')!;
  const d = q.find((x) => x.book === 'draftkings')!;
  check('entered FD price shows at FD', near(f.americanOdds, 4254, 1e-6) && f.entered && !f.sgpEstimated);
  check('entered FD price leaves DK on the estimate', d.sgpEstimated && !d.entered);
  const m = withDecimalPayout(headline, toDec(4199));
  check('an entered DK price moves EV and grade with it',
    near(m.ev, m.jointProb * toDec(4199) - 1, 1e-12) && near(m.americanOdds, 4199, 1e-6));
}
{
  const b = betslipSummary(slip, slip.length, undefined, 4199);
  check('bar shows a typed DK price, not the estimate', near(b.americanOdds, 4199, 1e-6) && !b.sgpEstimated);
  const b2 = betslipSummary([slip[0], slip[1]], 2, undefined, 4199);
  check('a typed DK price never applies to a slip with no same-game group', !near(b2.americanOdds, 4199, 1));
  const q = priceBooksForParlay(slip, 1, ['draftkings', 'fanduel'], undefined, { fanduel: 4254 });
  check('no best-payout star when typed and estimated prices are mixed', q.every((x) => !x.isBest));
  check('reordering the slip keeps its signature (a typed price survives)',
    slipSignature(slip) === slipSignature([...slip].reverse()));
  check('a different slip has a different signature', slipSignature(slip) !== slipSignature(slip.slice(1)));
}
// ── the 2026-11-12 NFL slip ─────────────────────────────────────────────────
// Five WAS@NYG legs, FanDuel's prices from v_latest_prop_odds_all_books
// (2026-11-12 21:25 UTC). The app showed FD +8037; FanDuel's slip said +3085.

{
  const G = 'NFL_2026_10_WAS_NYG';
  const prop = (id: number, fdPrice: number, market: string, player: string, team: string, label: string): ParlayLeg => ({
    ...leg(100 + id, G, fdPrice, fdPrice, label),
    prop: { sport: 'NFL', market, player, team, side: 'over' },
  });
  const nfl: ParlayLeg[] = [
    prop(1, 158, 'player_pass_tds', 'jayden daniels', 'WAS', 'Jayden Daniels Over 1.5 Pass TDs'),
    prop(2, 280, 'player_anytime_td', 'devin singletary', 'NYG', 'Devin Singletary Over 0.5 Anytime TD'),
    prop(3, -120, 'player_receptions', 'malik nabers', 'NYG', 'Malik Nabers Over 5.5 Receptions'),
    prop(4, -172, 'player_receptions', 'stefon diggs', 'WAS', 'Stefon Diggs Over 3.5 Receptions'),
    prop(5, 240, 'player_anytime_td', 'stefon diggs', 'WAS', 'Stefon Diggs Over 0.5 Anytime TD'),
  ];
  const sh = sgpShapeFor(nfl);
  check('one 5-leg game = 1 group, 4 extra legs', sh.groups === 1 && sh.extraLegs === 4);
  // scipy's exact bivariate-normal joint gives 1.866 on these prices.
  check('NFL lift ≈ 1.87 (the copula, ±6%)', near(sh.lift, 1.866, 0.11), `lift ${sh.lift.toFixed(3)}`);
  const q = priceBooksForParlay(nfl, 1, ['fanduel']).find((x) => x.book === 'fanduel')!;
  check('FD multiplied is +9564', near(q.multipliedDecimal, 96.64, 0.01));
  // Was +8037 (2.6x FanDuel's price). Now within 15% of it, on a default
  // partly fitted to this slip.
  check('FD tile within 15% of FanDuel’s own +3085', near(q.decimalPayout, toDec(3085), toDec(3085) * 0.15), `FD ${q.americanOdds?.toFixed(0)}`);
  check('the same legs with no prop identity get no lift',
    sgpCorrelationLift(nfl.map((l) => ({ ...l, prop: undefined }))) === 1);
  const under = nfl.map((l, i) => (i === 4 ? { ...l, prop: { ...l.prop!, side: 'under' as const } } : l));
  check('flipping a correlated leg to the under lowers the lift', sgpCorrelationLift(under) < sh.lift);
  check('the lift is stable (seeded)', sgpCorrelationLift([...nfl].reverse()) === sh.lift);
  check('sgpShape alone carries no lift', sgpShape(nfl).lift === 1);
  const headline = computeCorrelatedMetrics(nfl, PARLAY_CORRELATION_PRIORS, undefined, 20000);
  // UX review, 2026-11-12: three shapes that read wrong.
  const diggs = (id: number, price: number, market: string, side: 'over' | 'under') => ({
    ...leg(200 + id, G, price, price, `Diggs ${side} ${market}`),
    prop: { sport: 'NFL', market, player: 'stefon diggs', team: 'WAS', side },
  });
  {
    const opposite = [diggs(1, -115, 'player_receptions', 'over'), diggs(2, -115, 'player_reception_yds', 'under')];
    const m = computeParlayMetrics(opposite);
    check('legs that pull apart never price above the legs multiplied out',
      sgpCorrelationLift(opposite) < 1 && m.decimalPayout <= m.multipliedDecimal, `${m.americanOdds.toFixed(0)} vs multiplied ${((m.multipliedDecimal - 1) * 100).toFixed(0)}`);
  }
  {
    const favs = [diggs(3, -500, 'player_receptions', 'over'), diggs(4, -500, 'player_reception_yds', 'over'), diggs(5, -500, 'player_rush_reception_yds', 'over')];
    const m = computeParlayMetrics(favs);
    check('short-priced correlated legs do not collapse to -10000', m.decimalPayout > 1.15, `${m.americanOdds.toFixed(0)}`);
  }
  {
    // A pick leg has no team; the screen's resolver supplies it.
    const noTeam = nfl.map((l) => ({ ...l, prop: { ...l.prop!, team: null } }));
    const teams: Record<number, string> = { 101: 'WAS', 102: 'NYG', 103: 'NYG', 104: 'WAS', 105: 'WAS' };
    const viaResolver = computeCorrelatedMetrics(
      noTeam.map((l) => ({ ...l, pick: { player_id: String(l.pickId), pick_side: 'over', sport: 'NFL' } as never })),
      PARLAY_CORRELATION_PRIORS, (pid) => teams[Number(pid)] ?? null, 20000);
    const withTeams = computeCorrelatedMetrics(nfl, PARLAY_CORRELATION_PRIORS, undefined, 20000);
    check('a leg with no team gets it from the screen\'s resolver',
      near(viaResolver.jointProb, withTeams.jointProb, 0.002), `${viaResolver.jointProb.toFixed(4)} vs ${withTeams.jointProb.toFixed(4)}`);
  }

  check('NFL win % is no longer the naive product', headline.hasCorrelation && headline.jointProb > headline.independentProb * 1.4,
    `${(headline.jointProb * 100).toFixed(2)}% vs ${(headline.independentProb * 100).toFixed(2)}%`);
}

check('parse "+4,254"', parseEnteredAmerican('+4,254') === 4254);
check('parse "-120"', parseEnteredAmerican('-120') === -120);
check('reject "42" (not American odds)', parseEnteredAmerican('42') === null);
check('reject "abc"', parseEnteredAmerican('abc') === null);
check('a typo 10x off is implausible', !enteredPriceIsPlausible(toDec(425), 61.4));
check('FanDuel’s real quote is plausible', enteredPriceIsPlausible(toDec(4254), 61.4));

console.log(failures === 0 ? '\nAll SGP pricing checks passed.' : `\n${failures} check(s) FAILED.`);
process.exit(failures === 0 ? 0 : 1);

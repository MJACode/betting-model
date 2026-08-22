/**
 * Standalone verification for the custom-model filter engine
 * (src/lib/customModelFilters.ts + pickMatchesModel). Run with:
 *
 *   npx tsx scripts/verify_custom_model_filters.ts
 *
 * Pins the load-bearing semantics:
 *   - a model with no filters behaves exactly as it did pre-filters;
 *   - filters AND over the OR'd rules, never instead of them;
 *   - ET time bucketing, including the post-midnight wraparound;
 *   - favorite/underdog from the sign of the DK price;
 *   - the odds floor/ceiling compares correctly across the sign boundary;
 *   - picks missing the underlying datum (no price, no split) are excluded by a
 *     filter that needs it rather than silently passing.
 */

import {
  betKindOf,
  chipSelection,
  dayTypeOf,
  describeFilters,
  etHour,
  evOf,
  hasAnyFilter,
  pickMatchesFilters,
  priceSideOf,
  sanitizeFilters,
  setNumericFilter,
  timeSlotOf,
  toggleChip,
  CHIP_GROUPS,
  DEFAULT_FILTERS,
  type FilterablePick,
} from '../src/lib/customModelFilters';
import { isOutcomeGraded } from '../src/lib/customModelFilters';
import {
  latestCachedDate,
  mergeSettled,
  refreshFrom,
  REFRESH_WINDOW_DAYS,
} from '../src/lib/settledPickCache';
import {
  EMPTY_STATS,
  mergeStats,
  splitRulesByCoverage,
  summaryToStats,
} from '../src/lib/customModelBacktest';
import { pickMatchesModel } from '../src/hooks/useCustomModels';
import type { CustomModel, CustomModelFilters, SettledPick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

/** A Friday 7:10pm ET (23:10 UTC) home moneyline favorite, BET, no injury, no split. */
function pick(over: Partial<FilterablePick> = {}): FilterablePick {
  return {
    model_id: 'mlb_moneyline',
    pick_side: 'home',
    signal_type: 'BET',
    dk_odds: -130,
    scored_line: null, // moneyline picks carry no line
    game_date: '2026-08-07', // a Friday
    game_time: '2026-08-07T23:10:00+00:00',
    confidence_tier: 'HIGH',
    public_bet_pct: null,
    injury_flag: null,
    player_id: null,
    ...over,
  };
}

function model(filters?: CustomModelFilters): CustomModel {
  return {
    id: 'm1',
    name: 'test',
    rules: [{ model_id: 'mlb_moneyline', min_prob: 0.6, min_edge: 0.05 }],
    filters,
    created_at: '',
    updated_at: '',
  };
}
const scorable = { model_probability: 0.7, edge: 0.1 };

// ---------------------------------------------------------------------------
// 1. Backward compatibility — no filters means no constraint.
// ---------------------------------------------------------------------------
check('undefined filters match everything', pickMatchesFilters(pick(), undefined));
check('empty filters match everything', pickMatchesFilters(pick(), {}));
check(
  'model saved before filters still matches',
  pickMatchesModel({ ...pick(), ...scorable }, model(undefined)),
);
check('hasAnyFilter false on empty', !hasAnyFilter({}) && !hasAnyFilter(undefined));

// ---------------------------------------------------------------------------
// 2. Filters AND with the rules — they never rescue a pick that fails a rule,
//    and never pass one the rules accepted but the filters reject.
// ---------------------------------------------------------------------------
check(
  'rule failure is not rescued by a passing filter',
  !pickMatchesModel({ ...pick(), model_probability: 0.5, edge: 0.1 }, model({ sides: ['home'] })),
);
check(
  'rule pass + filter reject = no match',
  !pickMatchesModel({ ...pick(), ...scorable }, model({ sides: ['away'] })),
);
check(
  'rule pass + filter pass = match',
  pickMatchesModel({ ...pick(), ...scorable }, model({ sides: ['home'] })),
);
check(
  'wrong model_id never matches',
  !pickMatchesModel({ ...pick({ model_id: 'mlb_runline' }), ...scorable }, model({})),
);

// ---------------------------------------------------------------------------
// 3. Home vs away.
// ---------------------------------------------------------------------------
check('home-only keeps home', pickMatchesFilters(pick(), { sides: ['home'] }));
check('home-only drops away', !pickMatchesFilters(pick({ pick_side: 'away' }), { sides: ['home'] }));
check(
  'home-only drops an over prop',
  !pickMatchesFilters(pick({ pick_side: 'over' }), { sides: ['home'] }),
);
check(
  'both sides selected keeps both',
  pickMatchesFilters(pick(), { sides: ['home', 'away'] }) &&
    pickMatchesFilters(pick({ pick_side: 'away' }), { sides: ['home', 'away'] }),
);

// ---------------------------------------------------------------------------
// 4. Favorites vs underdogs.
// ---------------------------------------------------------------------------
check('minus money is a favorite', priceSideOf(pick({ dk_odds: -130 })) === 'fav');
check('plus money is a dog', priceSideOf(pick({ dk_odds: 145 })) === 'dog');
check('even money counts as a dog', priceSideOf(pick({ dk_odds: 100 })) === 'dog');
check('no price has no side', priceSideOf(pick({ dk_odds: null })) === null);
check('fav filter keeps -130', pickMatchesFilters(pick(), { price: ['fav'] }));
check('fav filter drops +145', !pickMatchesFilters(pick({ dk_odds: 145 }), { price: ['fav'] }));
check(
  'price filter drops prob-only picks (no DK price)',
  !pickMatchesFilters(pick({ dk_odds: null }), { price: ['fav'] }) &&
    !pickMatchesFilters(pick({ dk_odds: null }), { price: ['dog'] }),
);

// ---------------------------------------------------------------------------
// 5. Odds range — American odds are monotonic in payout despite the sign flip.
// ---------------------------------------------------------------------------
check('-130 clears a -140 floor', pickMatchesFilters(pick({ dk_odds: -130 }), { minOdds: -140 }));
check('-165 fails a -140 floor', !pickMatchesFilters(pick({ dk_odds: -165 }), { minOdds: -140 }));
check('+150 clears a -140 floor', pickMatchesFilters(pick({ dk_odds: 150 }), { minOdds: -140 }));
check('+250 fails a +200 ceiling', !pickMatchesFilters(pick({ dk_odds: 250 }), { maxOdds: 200 }));
check(
  'a floor and ceiling together bracket the price',
  pickMatchesFilters(pick({ dk_odds: -110 }), { minOdds: -140, maxOdds: 200 }) &&
    !pickMatchesFilters(pick({ dk_odds: -300 }), { minOdds: -140, maxOdds: 200 }) &&
    !pickMatchesFilters(pick({ dk_odds: 400 }), { minOdds: -140, maxOdds: 200 }),
);
check(
  'odds filter drops picks with no price',
  !pickMatchesFilters(pick({ dk_odds: null }), { minOdds: -140 }),
);

// ---------------------------------------------------------------------------
// 6. Game time in ET, including the post-midnight wraparound.
// ---------------------------------------------------------------------------
check('23:10 UTC is 7pm ET', etHour('2026-08-07T23:10:00+00:00') === 19);
check('unparseable time has no hour', etHour('not-a-date') === null && etHour(null) === null);
check('1:05pm ET is a day game', timeSlotOf(pick({ game_time: '2026-08-07T17:05:00+00:00' })) === 'day');
check('5pm ET is early', timeSlotOf(pick({ game_time: '2026-08-07T21:00:00+00:00' })) === 'early');
check('7:10pm ET is prime', timeSlotOf(pick()) === 'prime');
check('10:10pm ET is late', timeSlotOf(pick({ game_time: '2026-08-08T02:10:00+00:00' })) === 'late');
check(
  '12:41am ET belongs to the late slate, not the next afternoon',
  timeSlotOf(pick({ game_time: '2026-08-08T04:41:00+00:00' })) === 'late',
);
check('prime filter keeps a 7:10pm game', pickMatchesFilters(pick(), { timeSlots: ['prime'] }));
check(
  'prime filter drops a 1:05pm game',
  !pickMatchesFilters(pick({ game_time: '2026-08-07T17:05:00+00:00' }), { timeSlots: ['prime'] }),
);
check(
  'time filter drops picks with no game_time',
  !pickMatchesFilters(pick({ game_time: null }), { timeSlots: ['prime'] }),
);

// ---------------------------------------------------------------------------
// 7. Bet kind (legacy), signal removal, confidence, public splits, injuries.
// ---------------------------------------------------------------------------
check('a moneyline pick is a game bet', betKindOf(pick()) === 'game');
check(
  'a batter-hits pick is a prop',
  betKindOf(pick({ model_id: 'mlb_prop_batter_hits', player_id: '12345' })) === 'prop',
);
check(
  'legacy betKinds filter (pre-2026-08-22 models) is still honored',
  !pickMatchesFilters(
    pick({ model_id: 'mlb_prop_batter_hits', player_id: '12345', pick_side: 'over' }),
    { betKinds: ['game'] },
  ),
);
// The signal filter was REMOVED (2026-08-22): a legacy saved value is ignored
// by the matcher, stripped before the RPC, and new models start unconstrained.
check(
  'legacy signals filter is ignored by the matcher',
  pickMatchesFilters(pick({ signal_type: 'AVOID' }), { signals: ['BET'] }) &&
    pickMatchesFilters(pick({ signal_type: 'NONE' }), { signals: ['BET'] }),
);
check(
  'sanitizeFilters strips signals and nothing else',
  (() => {
    const out = sanitizeFilters({ signals: ['BET'], sides: ['home'], minOdds: -140 });
    return !('signals' in out) && out.sides?.join() === 'home' && out.minOdds === -140;
  })(),
);
check(
  'sanitizeFilters is a no-op without the legacy key',
  (() => {
    const f = { sides: ['home' as const] };
    return sanitizeFilters(f) === f && Object.keys(sanitizeFilters(undefined)).length === 0;
  })(),
);
check(
  'new models default to no filters (BET-only default removed)',
  Object.keys(DEFAULT_FILTERS).length === 0,
);
check(
  'signal and bet-kind chip groups are gone from the builder catalog',
  CHIP_GROUPS.every((g) => (g.key as string) !== 'signals' && (g.key as string) !== 'betKinds'),
);
check('HIGH-only keeps HIGH', pickMatchesFilters(pick(), { tiers: ['HIGH'] }));
check('HIGH-only drops LOW', !pickMatchesFilters(pick({ confidence_tier: 'LOW' }), { tiers: ['HIGH'] }));
check(
  'contrarian filter keeps a 30%-backed pick',
  pickMatchesFilters(pick({ public_bet_pct: 30 }), { maxPublicBetPct: 40 }),
);
check(
  'contrarian filter drops a 71%-backed pick',
  !pickMatchesFilters(pick({ public_bet_pct: 71 }), { maxPublicBetPct: 40 }),
);
check(
  'public filter drops picks with no split data',
  !pickMatchesFilters(pick({ public_bet_pct: null }), { maxPublicBetPct: 40 }),
);
check('injury filter keeps a clean pick', pickMatchesFilters(pick(), { excludeInjuries: true }));
check(
  'injury filter drops a flagged pick',
  !pickMatchesFilters(pick({ injury_flag: 'OUT: J. Soto' }), { excludeInjuries: true }),
);
check(
  'an empty injury_flag string is not a flag',
  pickMatchesFilters(pick({ injury_flag: '  ' }), { excludeInjuries: true }),
);

// ---------------------------------------------------------------------------
// 7b. Day of week — weekend = Saturday/Sunday of the ET game_date, in exact
//     lockstep with the RPC's EXTRACT(ISODOW) bucketing.
// ---------------------------------------------------------------------------
check('a Friday is a weekday', dayTypeOf(pick()) === 'weekday');
check('a Saturday is a weekend', dayTypeOf(pick({ game_date: '2026-08-08' })) === 'weekend');
check('a Sunday is a weekend', dayTypeOf(pick({ game_date: '2026-08-09' })) === 'weekend');
check('a Monday is a weekday', dayTypeOf(pick({ game_date: '2026-08-10' })) === 'weekday');
check(
  'weekend filter keeps Saturday, drops Friday',
  pickMatchesFilters(pick({ game_date: '2026-08-08' }), { dayTypes: ['weekend'] }) &&
    !pickMatchesFilters(pick(), { dayTypes: ['weekend'] }),
);
check(
  'day filter drops an unparseable game_date',
  !pickMatchesFilters(pick({ game_date: '' as unknown as string }), { dayTypes: ['weekend'] }),
);

// ---------------------------------------------------------------------------
// 7c. Line value — the total/spread/prop line the pick was priced at.
//     Moneyline picks carry no line, so either bound excludes them.
// ---------------------------------------------------------------------------
{
  const ou = (line: number | null) =>
    pick({ model_id: 'mlb_over_under', pick_side: 'over', scored_line: line });
  check('a 9.5 total clears a 9 floor', pickMatchesFilters(ou(9.5), { minLine: 9 }));
  check('an 8 total fails a 9 floor', !pickMatchesFilters(ou(8), { minLine: 9 }));
  check('a 10.5 total fails a 10 ceiling', !pickMatchesFilters(ou(10.5), { maxLine: 10 }));
  check(
    'floor and ceiling bracket the line',
    pickMatchesFilters(ou(9.5), { minLine: 9, maxLine: 10 }) &&
      !pickMatchesFilters(ou(8.5), { minLine: 9, maxLine: 10 }),
  );
  check(
    'line filter drops moneyline picks (no line to compare)',
    !pickMatchesFilters(pick(), { minLine: 9 }) && !pickMatchesFilters(pick(), { maxLine: 10 }),
  );
}

// ---------------------------------------------------------------------------
// 7d. EV — expected profit per $1 at the DK price, the always-available rule
//     floor next to model %. A pick with no DK price can never clear it.
// ---------------------------------------------------------------------------
{
  check('EV at +100 is p·2−1', Math.abs(evOf(0.6, 100)! - 0.2) < 1e-12);
  check('EV at -130 favorite', Math.abs(evOf(0.6, -130)! - (0.6 * (1 + 100 / 130) - 1)) < 1e-12);
  check('no DK price means no EV', evOf(0.6, null) === null && evOf(0.6, 0) === null);

  const evModel = (min_ev: number | null): CustomModel => ({
    id: 'm2',
    name: 'ev test',
    rules: [{ model_id: 'mlb_moneyline', min_prob: 0.6, min_edge: 0.05, min_ev }],
    created_at: '',
    updated_at: '',
  });
  // p=0.7 at -130: EV = 0.7 × 1.769 − 1 ≈ +23.8%
  check('rule with a cleared EV floor matches', pickMatchesModel({ ...pick(), ...scorable }, evModel(0.1)));
  check(
    'rule with a missed EV floor drops the pick',
    !pickMatchesModel({ ...pick(), ...scorable }, evModel(0.3)),
  );
  check(
    'an EV floor drops prob-only picks (no DK price)',
    !pickMatchesModel({ ...pick({ dk_odds: null }), ...scorable }, evModel(0)),
  );
  check(
    'a null EV floor is no floor at all',
    pickMatchesModel({ ...pick({ dk_odds: null }), ...scorable }, evModel(null)),
  );
}

// ---------------------------------------------------------------------------
// 8. Filters compose (AND) across groups.
// ---------------------------------------------------------------------------
{
  const f: CustomModelFilters = {
    sides: ['home'],
    price: ['fav'],
    timeSlots: ['prime'],
    dayTypes: ['weekday'],
    minOdds: -140,
  };
  check('a pick clearing every group matches', pickMatchesFilters(pick(), f));
  check('one failing group is enough to drop it', !pickMatchesFilters(pick({ dk_odds: -165 }), f));
  check('another failing group also drops it', !pickMatchesFilters(pick({ pick_side: 'away' }), f));
  check(
    'the day group participates in the AND',
    !pickMatchesFilters(pick({ game_date: '2026-08-08' }), f),
  );
}

// ---------------------------------------------------------------------------
// 9. Builder helpers — toggling, clearing, and the human summary.
// ---------------------------------------------------------------------------
{
  let f: CustomModelFilters = {};
  f = toggleChip(f, 'sides', 'home');
  check('toggle adds a value', chipSelection(f, 'sides').join() === 'home');
  f = toggleChip(f, 'sides', 'away');
  check('toggle accumulates', chipSelection(f, 'sides').length === 2);
  f = toggleChip(f, 'sides', 'home');
  f = toggleChip(f, 'sides', 'away');
  check('emptying a group removes the key entirely', !('sides' in f));
  check('an emptied group constrains nothing', pickMatchesFilters(pick({ pick_side: 'over' }), f));

  f = setNumericFilter(f, 'minOdds', -140);
  check('numeric filter sets', f.minOdds === -140 && hasAnyFilter(f));
  f = setNumericFilter(f, 'minOdds', null);
  check('numeric filter clears', !('minOdds' in f) && !hasAnyFilter(f));
}
{
  const chips = describeFilters({
    sides: ['home'],
    price: ['fav'],
    timeSlots: ['prime'],
    dayTypes: ['weekend'],
    minOdds: -140,
    minLine: 8.5,
    maxPublicBetPct: 40,
    excludeInjuries: true,
  });
  check('summary names the side', chips.includes('Home'), chips.join(' | '));
  check('summary names the price side', chips.includes('Favorites (−)'), chips.join(' | '));
  check('summary names the day of week', chips.includes('Weekends'), chips.join(' | '));
  check('summary formats the odds floor', chips.includes('DK ≥ -140'), chips.join(' | '));
  check('summary formats the line floor', chips.includes('Line ≥ 8.5'), chips.join(' | '));
  check('summary formats the public cap', chips.includes('Public ≤ 40%'), chips.join(' | '));
  check('summary names the injury rule', chips.includes('No injury flags'), chips.join(' | '));
  check(
    'summary still describes a legacy bet-kind filter',
    describeFilters({ betKinds: ['prop'] }).includes('Player props'),
  );
  check(
    'a fully-selected group is not summarised (it constrains nothing)',
    describeFilters({ price: ['fav', 'dog'] }).length === 0,
  );
  check('no filters summarise to nothing', describeFilters(undefined).length === 0);
}
check(
  'every chip group exposes at least two options',
  CHIP_GROUPS.every((g) => g.options.length >= 2),
);

// ---------------------------------------------------------------------------
// 10. Settled-pick cache — the backtest reads full history, so it must never be
//     silently truncated and must pick up late-settling picks.
// ---------------------------------------------------------------------------
{
  const row = (id: number, date: string): SettledPick =>
    ({ pick_id: id, game_date: date, result: 'WIN' }) as unknown as SettledPick;

  check('empty cache refetches from paper start', refreshFrom([], '2026-04-14') === '2026-04-14');
  check(
    'refresh window looks back past the settle window',
    refreshFrom([row(1, '2026-08-07')], '2026-04-14') === '2026-07-17',
    `got ${refreshFrom([row(1, '2026-08-07')], '2026-04-14')} (21 days before 08-07)`,
  );
  check(
    'the window is at least as wide as the 14-day settle windows',
    REFRESH_WINDOW_DAYS >= 14,
    `REFRESH_WINDOW_DAYS=${REFRESH_WINDOW_DAYS}`,
  );
  check(
    'refetch start is floored at paper start',
    refreshFrom([row(1, '2026-04-20')], '2026-04-14') === '2026-04-14',
  );
  check(
    'latestCachedDate picks the newest, not the last',
    latestCachedDate([row(1, '2026-05-01'), row(2, '2026-08-07'), row(3, '2026-06-01')]) ===
      '2026-08-07',
  );

  // The whole point of the window: a pick already cached as unsettled for an
  // in-window date gets replaced by the server's now-settled copy.
  const cached = [row(1, '2026-05-01'), row(2, '2026-07-20'), row(3, '2026-08-01')];
  const fresh = [row(2, '2026-07-20'), row(3, '2026-08-01'), row(4, '2026-08-07')];
  const merged = mergeSettled(cached, fresh, '2026-07-17');
  check('merge keeps history older than the window', merged.some((r) => r.pick_id === 1));
  check('merge adds newly settled picks', merged.some((r) => r.pick_id === 4));
  check('merge does not duplicate in-window rows', merged.length === 4, `got ${merged.length}`);
  check(
    'merge sorts newest first',
    merged[0].game_date === '2026-08-07' && merged[merged.length - 1].game_date === '2026-05-01',
  );
  check(
    'a pick deleted inside the window is dropped, not kept from cache',
    mergeSettled(cached, [row(4, '2026-08-07')], '2026-07-17').every((r) => r.pick_id !== 2),
  );
  check(
    'an empty refresh keeps out-of-window history intact',
    mergeSettled(cached, [], '2026-07-17').length === 1,
  );
}

// ---------------------------------------------------------------------------
// 11. Full-universe backtest plumbing — the coverage split and the merge of the
//     server (MLB/WNBA graded) and settled (UFC/NHL/golf) halves.
// ---------------------------------------------------------------------------
{
  check(
    'MLB game + prop and WNBA models are server-graded',
    isOutcomeGraded('mlb_moneyline') &&
      isOutcomeGraded('mlb_prop_batter_hits') &&
      isOutcomeGraded('wnba_moneyline') &&
      isOutcomeGraded('wnba_prop_player_points'),
  );
  check(
    'UFC / NHL / golf are not (settled fallback)',
    !isOutcomeGraded('ufc_moneyline') &&
      !isOutcomeGraded('nhl_moneyline') &&
      !isOutcomeGraded('golf_top10'),
  );

  const rules = [
    { model_id: 'mlb_moneyline', min_prob: 0.6, min_edge: 0.05 },
    { model_id: 'ufc_moneyline', min_prob: 0.65, min_edge: 0.08 },
    { model_id: 'wnba_prop_player_assists', min_prob: 0.69, min_edge: 0.08 },
  ];
  const { covered, uncovered } = splitRulesByCoverage(rules);
  check(
    'rules split cleanly by coverage',
    covered.length === 2 && uncovered.length === 1 && uncovered[0].model_id === 'ufc_moneyline',
  );

  const server = summaryToStats({
    bets: 10, wins: 6, losses: 4, pushes: 0, priced: 10, units: 1.5, roi_pct: 15,
  });
  check(
    'summaryToStats scales units to the $100 convention',
    server.profitFlat === 150 && server.stakedFlat === 1000 && server.winRate === 0.6,
  );

  const local = {
    picks: 5, wins: 2, losses: 3, pushes: 0, winRate: 0.4,
    profitFlat: -120, stakedFlat: 500, roiFlat: -0.24,
  };
  const merged = mergeStats(server, local);
  check(
    'mergeStats sums counters and recomputes ratios',
    merged.picks === 15 &&
      merged.wins === 8 &&
      merged.profitFlat === 30 &&
      merged.stakedFlat === 1500 &&
      Math.abs(merged.roiFlat - 30 / 1500) < 1e-12 &&
      Math.abs(merged.winRate - 8 / 15) < 1e-12,
  );
  check(
    'merging with an empty half is identity',
    mergeStats(server, EMPTY_STATS).picks === server.picks &&
      mergeStats(EMPTY_STATS, local).profitFlat === local.profitFlat,
  );
}

console.log(
  failures === 0 ? '\nAll custom-model filter checks passed.' : `\n${failures} check(s) FAILED.`,
);
process.exit(failures === 0 ? 0 : 1);

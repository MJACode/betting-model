/**
 * Standalone verification for the 2026-09-05 market-coverage sync: the Stats
 * board's Doubles and Triples columns, and the two honesty guards the UX
 * review asked for alongside them. Run with:
 *
 *   npx tsx scripts/verify_market_coverage.ts
 *
 * Pins: Doubles/Triples resolve a market and NOT a model; the fallback map is
 * sport-scoped, so no other sport's column can reach a baseball market; the
 * MLB board's priced-column count; and hitRateColorDiscriminates switching the
 * ramp off exactly when every row on screen sits in one band.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { hitRateBandOf, hitRateColorDiscriminates } from '../src/lib/hitRate';
import {
  STAT_CATALOG,
  propMarketForStat,
  propModelForStat,
  type StatDef,
} from '../src/lib/statCatalog';

const read = (p: string) => readFileSync(join(import.meta.dirname, '..', p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const mlb = STAT_CATALOG.filter((d) => d.sport === 'MLB');
const priced = mlb.filter((d) => propMarketForStat(d) !== null);
const byKey = (k: string): StatDef => mlb.find((d) => String(d.key) === k)!;

console.log('— the two columns that were blank because nobody had asked —');
for (const [key, market] of [
  ['doubles', 'batter_doubles'],
  ['triples', 'batter_triples'],
] as const) {
  check(`${key} resolves ${market}`, propMarketForStat(byKey(key)) === market,
    String(propMarketForStat(byKey(key))));
  // No doubles model exists and none is implied: no "Add to play" affordance.
  check(`${key} implies no model`, propModelForStat(byKey(key)) === null);
}

console.log('\n— the blanks that stay blank, because the API does not know the key —');
// batter_at_bats, pitcher_home_runs_allowed and pitcher_pitches all 422 on the
// coverage probe; batter Strikeouts is supported but was unpriced on the one
// probed event, and one event is not a population.
for (const key of ['at_bats', 'p_home_runs', 'pitches', 'strikeouts']) {
  const def = byKey(key);
  check(`${key} stays blank`, def != null && propMarketForStat(def) === null);
}
check('the MLB board prices 14 of its columns', priced.length === 14,
  `${priced.length} of ${mlb.length}`);

console.log('\n— the fallback map cannot cross sports —');
const catalog = read('src/lib/statCatalog.ts');
const body = catalog.split('STAT_KEY_TO_MARKET')[1].split('};')[0];
const entries = [...body.matchAll(/^\s*'?([A-Za-z_0-9:]+)'?:\s*'([a-z_0-9]+)'/gm)];
check('the map has entries', entries.length > 0, String(entries.length));
check('every entry is sport-scoped', entries.every((m) => /^[A-Z]+:/.test(m[1])),
  entries.map((m) => m[1]).join(', '));
// The guard is what matters: another sport's identically-named column must not
// reach a baseball market through it.
// No sport shares these two keys TODAY, so the live catalog cannot exercise the
// guard — the guard exists for the next entry (`steals`, `threes`, `blocks`),
// which SeasonTotalsRow shares across sports. So exercise it directly: a
// basketball column named `doubles` must not reach `batter_doubles`.
const impostor = { ...byKey('doubles'), sport: 'NBA' } as StatDef;
check('a same-named column from another sport resolves nothing',
  propMarketForStat(impostor) === null, String(propMarketForStat(impostor)));
check('and the real MLB column still resolves',
  propMarketForStat(byKey('doubles')) === 'batter_doubles');

console.log('\n— the two football leagues do not share a market —');
// The first real college prop pass (2026-09-05 1pm ET) covered 31 games, 615
// players and 7 books and returned zero rows for carries and sacks; the NFL
// prices both. One shared catalog, one shared map, two different answers.
for (const key of ['carries', 'def_sacks']) {
  const college = STAT_CATALOG.find((d) => d.sport === 'NCAAF' && String(d.key) === key);
  const pro = STAT_CATALOG.find((d) => d.sport === 'NFL' && String(d.key) === key);
  check(`NCAAF ${key} resolves nothing`, !!college && propMarketForStat(college) === null,
    String(college && propMarketForStat(college)));
  check(`NFL ${key} still resolves`, !!pro && propMarketForStat(pro) !== null,
    String(pro && propMarketForStat(pro)));
}
// Everything else stays shared — the exclusion is two columns, not a fork.
for (const key of ['rushing_yards', 'receptions', 'passing_yards']) {
  const college = STAT_CATALOG.find((d) => d.sport === 'NCAAF' && String(d.key) === key);
  const pro = STAT_CATALOG.find((d) => d.sport === 'NFL' && String(d.key) === key);
  if (!college || !pro) continue;
  check(`both leagues still agree on ${key}`,
    propMarketForStat(college) !== null && propMarketForStat(college) === propMarketForStat(pro),
    String(propMarketForStat(college)));
}

console.log('\n— the ramp switches itself off on a rare-event column —');
check('bands: 0.7 high, 0.5 mid, 0.2 low',
  hitRateBandOf(0.7) === 'high' && hitRateBandOf(0.5) === 'mid' && hitRateBandOf(0.2) === 'low');
// "1+ Doubles": every hitter in the league between 10% and 30%.
check('a rare-event column is not coloured',
  hitRateColorDiscriminates([0.3, 0.25, 0.22, 0.18, 0.1]) === false);
// The same column flipped to "No Doubles": a wall of green beside heavy chalk.
check('its Under side is not coloured either',
  hitRateColorDiscriminates([0.7, 0.75, 0.78, 0.82, 0.9]) === false);
// "1+ Hits" spans the bands, which is what the ramp was built to show.
check('an ordinary column keeps its ramp',
  hitRateColorDiscriminates([0.75, 0.62, 0.5, 0.38, 0.2]) === true);
check('one row cannot discriminate', hitRateColorDiscriminates([0.9]) === false);
check('an empty board cannot discriminate', hitRateColorDiscriminates([]) === false);
// Straddling a boundary is still a real distinction.
check('two rows either side of 0.6 are coloured',
  hitRateColorDiscriminates([0.61, 0.59]) === true);

console.log('\n— the unpriced note names the league, and the group when the group is empty —');
const screen = read('src/screens/StatsScreen.tsx');
// The claim "no sportsbook posts this" was true while a column unpriced here
// was unpriced everywhere. College carries and sacks broke that: the NFL
// prices both, so an unscoped sentence is one the user can disprove two taps
// away on the other football board.
check('the note names the sport',
  screen.includes('`No sportsbook posts ${sport} ${stat.label} lines.`'));
check('and says it once about the group when the whole group is unpriced',
  screen.includes('`No sportsbook posts ${sport} ${stat.group.toLowerCase()} lines.`') &&
    screen.includes('.every((s) => propMarketForStat(s) == null)'));
check('no unscoped claim survives',
  !screen.includes('`No sportsbook posts ${stat.label} lines.`'));
// The direction pill outlives the price on an unpriced column, so its
// VoiceOver label must not be the one place left promising a bet.
check('the direction pill no longer says "bets" to VoiceOver',
  screen.includes('accessibilityLabel="Threshold direction"') &&
    !screen.includes('accessibilityLabel="Show bets that are"'));

console.log('\n— a slip of only Stats lines does not claim a model —');
const parlay = read('src/screens/ParlayScreen.tsx');
check('the tile is labelled from modelBacked',
  parlay.includes("label={modelBacked ? 'Model' : 'Implied'}"));
check('modelBacked is false only when every leg is a line leg',
  parlay.includes('const modelBacked = legs.some((l) => !isLineLeg(l));'));
check('the hold note takes it too', parlay.includes('modelBacked={modelBacked}'));
check('and its positive branch stops crediting a model',
  parlay.includes('no model has an opinion on them'));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

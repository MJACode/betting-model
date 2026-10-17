/**
 * Option B headline: the hero units string is Discord's, the chart pill
 * uses that same string, and the card is one spoken stop that leads with units.
 *   npx tsx scripts/verify_record_hero.ts
 */
import { formatSigned } from '../src/lib/format';
import {
  scrubIndex,
  pillFrame,
  plotLayout,
  unitAxisTicks,
  scrubBubbleFrame,
  chartDateLabel,
} from '../src/lib/equityGeometry';
import {
  DISCORD_ALL_TIME_LABEL,
  HERO_STACK_AT,
  clvText,
  equityStrokeToken,
  heroAccessibilityLabel,
  heroStacks,
  heroUnitsText,
  recordLine,
  roiText,
  sinceLine,
  winRateText,
} from '../src/lib/recordHero';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const measured = 22.6501;
const hero = heroUnitsText(measured, false);
check('hero units match Discord +22.65u', hero === '+22.65u', hero);
check('formatSigned is the same string', formatSigned(measured, 2, 'u') === hero);
check('a loss uses U+2212', heroUnitsText(-3.2, false) === '\u22123.20u');
check('not loaded is an em dash', heroUnitsText(0, true) === '—');
check('label is Discord All-time', DISCORD_ALL_TIME_LABEL === 'All-time');
check('date line', sinceLine() === 'since Sep 1, 2026');

check('ROI is the posted-stake percent', roiText(0.024697, 900, false) === '+2.5%');
check('ROI hidden when nothing was risked', roiText(0, 0, false) === '—');
check('record keeps a push', recordLine(439, 377, 2, false) === '439–377–2');
check('record drops a zero push count', recordLine(10, 4, 0, false) === '10–4');
check('win rate', winRateText(439 / (439 + 377), 439, 377, false) === '54%');
check('win rate empty', winRateText(0, 0, 0, false) === '—');
check('clv missing', clvText(null, false) === '—');

const spoken = heroAccessibilityLabel({
  notLoaded: false,
  picks: 818,
  label: DISCORD_ALL_TIME_LABEL,
  units: measured,
  risked: 900,
  roiFlat: 0.024697,
  wins: 439,
  losses: 377,
  pushes: 2,
  winRate: 439 / (439 + 377),
  clvBeatRate: 0.54,
});
check('one stop starts with the units', spoken.startsWith('+22.65 units'), spoken.slice(0, 40));
check('spoken label names All-time and the date', spoken.includes('All-time') && spoken.includes('September 1, 2026'));
check('spoken grid names the four cells',
  spoken.includes('Flat-bet ROI +2.5%') && spoken.includes('439 wins') && spoken.includes('Win rate 54%') && spoken.includes('Beat the closing line 54%'));

const missing = heroAccessibilityLabel({
  notLoaded: true,
  picks: 0,
  label: DISCORD_ALL_TIME_LABEL,
  units: 0,
  risked: 0,
  roiFlat: 0,
  wins: 0,
  losses: 0,
  pushes: 0,
  winRate: 0,
  clvBeatRate: null,
});
check('missing count is spoken, units first', missing.startsWith('Units unavailable') && missing.includes('settled picks count not available'), missing);

check('2x text stacks', heroStacks(2, 390) && heroStacks(HERO_STACK_AT, 430) && !heroStacks(1, 390));
check('narrow phone stacks before 1.2', heroStacks(1.15, 375) && !heroStacks(1.15, 390));
check('up line is betInk', equityStrokeToken(22.65) === 'betInk');
check('down line is avoidInk', equityStrokeToken(-1) === 'avoidInk');
check('flat line is neutral', equityStrokeToken(0) === 'textSecondary');

const ticks = unitAxisTicks(-4, 22.65);
check('y-axis includes zero', ticks.includes(0), ticks.join(','));
check('y-axis spans the series', ticks[0]! <= -4 && ticks[ticks.length - 1]! >= 22.65);

const layout = plotLayout(320, 176, [-4, 0, 22.65]);
check('scrub clamps low', scrubIndex(-20, layout, 10) === 0);
check('scrub clamps high', scrubIndex(999, layout, 10) === 9);
const mid = scrubIndex(layout.plotLeft + layout.plotWidth / 2, layout, 11);
check('scrub midpoint', mid === 5, String(mid));

const pill = pillFrame(10, 10, 320, 176);
check('pill stays inside', pill.left >= 0 && pill.top >= 0 && pill.left <= 320 && pill.top <= 176);
const bubble = scrubBubbleFrame(4, 320, 148, 48);
check('bubble stays on the top edge, clear of the axis', bubble.top === 0 && bubble.left >= 48, String(bubble.left));
check('chart date', chartDateLabel('2026-09-01') === 'Sep 1');

console.log(failures === 0 ? '\nAll record-hero checks passed.' : `\n${failures} FAILED.`);
process.exit(failures === 0 ? 0 : 1);

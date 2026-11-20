/**
 * Option B headline: the hero units string is Discord's, the chart pill
 * uses that same string, and the card is one spoken stop that leads with units.
 *   npx tsx scripts/verify_record_hero.ts
 */
import { formatSigned } from '../src/lib/format';
import {
  CHART_PAD,
  scrubIndex,
  scrubIndexForSeries,
  SCRUB_RELEASE_MS,
  equitySeriesKey,
  pillFrame,
  scheduleScrubRelease,
  plotLayout,
  unitAxisTicks,
  scrubBubbleFrame,
  chartDateLabel,
} from '../src/lib/equityGeometry';
import {
  DISCORD_ALL_TIME_LABEL,
  HERO_STACK_AT,
  HERO_VISIBLE_ALL_TIME,
  ROI_SHEET_TITLE,
  UNITS_CAPTION,
  clvText,
  equityStrokeToken,
  heroAccessibilityLabel,
  heroStacks,
  heroUnitsText,
  heroVisibleLabel,
  recordLine,
  roiSheetBody,
  roiText,
  sinceLine,
  winRateText,
  closingLineBody,
} from '../src/lib/recordHero';
import { allMatchedText, formatClvBeatLine } from '../src/lib/clvBeat';
import { buildShareMessage } from '../src/lib/shareRecord';

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
check('win rate is one decimal', winRateText(439 / (439 + 377), 439, 377, false) === '53.8%');
check('win rate empty', winRateText(0, 0, 0, false) === '—');
check('clv missing', clvText(null, false) === '—');

const spoken = heroAccessibilityLabel({
  notLoaded: false,
  picks: 818,
  label: DISCORD_ALL_TIME_LABEL,
  units: measured,
  risked: 900,
  roi: 0.024697,
  wins: 439,
  losses: 377,
  pushes: 2,
  winRate: 439 / (439 + 377),
  clvBeatRate: 0.54,
});
check('one stop starts with the units', spoken.startsWith('+22.65 units, 1 to win'), spoken.slice(0, 48));
check('spoken label names All-time and the date', spoken.includes('All-time') && spoken.includes('September 1, 2026') && !spoken.includes('Total profit'));
check('visible title is not the VoiceOver label', heroVisibleLabel(DISCORD_ALL_TIME_LABEL) === HERO_VISIBLE_ALL_TIME && heroVisibleLabel('NFL') === 'Total profit · NFL');
check('units caption', UNITS_CAPTION === 'Units · 1 to win');
check('spoken grid names the four cells',
  spoken.includes('Return on bets, 2.5 percent') && spoken.includes('439 wins') && spoken.includes('Win rate 53.8%') && spoken.includes('Beat the closing line, 54%'));
check('spoken grid does not use Yesterday\'s book name', !/flat-bet roi/i.test(spoken));
const sheet = roiSheetBody();
check('sheet title and body',
  ROI_SHEET_TITLE === 'Return on bets (ROI)' &&
  sheet.includes('Each pick risks the amount needed to win 1 unit') &&
  sheet.includes('Risk is capped at 3 units') &&
  sheet.includes('a pick with no price counts as 1 unit') &&
  !sheet.includes('Nothing risks more than 3'));

const missing = heroAccessibilityLabel({
  notLoaded: true,
  picks: 0,
  label: DISCORD_ALL_TIME_LABEL,
  units: 0,
  risked: 0,
  roi: 0,
  wins: 0,
  losses: 0,
  pushes: 0,
  winRate: 0,
  clvBeatRate: null,
});
check('missing count is spoken, units first', missing.startsWith('Units unavailable') && missing.includes('settled picks count not available'), missing);
const columnsMissing = heroAccessibilityLabel({
  notLoaded: false,
  picks: 10,
  label: DISCORD_ALL_TIME_LABEL,
  units: 0,
  risked: 0,
  unitsKnown: false,
  roi: 0,
  wins: 6,
  losses: 4,
  pushes: 0,
  winRate: 0.6,
  clvBeatRate: null,
});
check('a missing units column is unavailable and the record is still spoken',
  columnsMissing.startsWith('Units unavailable') && columnsMissing.includes('Return on bets, unavailable') && columnsMissing.includes('6 wins'),
  columnsMissing);

// Every bet measured, every close at our price: say so. "0 measured" said
// the opposite (EuroLeague, 2026-11-19: eight bets, all at our price).
check('all-matched wording', allMatchedText(8) === 'all 8 matched the close' && allMatchedText(1) === '1 matched the close'
  && allMatchedText(8, { sentence: true }) === 'All 8 matched the close' && allMatchedText(1, { sentence: true }) === '1 matched the close');
const shareAll = buildShareMessage({
  picks: 8, wins: 4, losses: 4, pushes: 0, units: 0, risked: 8, roi: 0, winRate: 0.5,
  clvSettled: 8, clvBeat: 0, clvPush: 8, clvBeatRate: null,
} as unknown as Parameters<typeof buildShareMessage>[0]);
check('share text for an all-matched set does not open with a beat',
  shareAll.includes('At the book we bet, all 8 matched the close') && !shareAll.includes('Beat the closing price'), shareAll);
check('share line for an all-matched set', formatClvBeatLine(0, 0, 8) === 'all 8 matched the close');
check('share line with a beat keeps the rate', formatClvBeatLine(3, 1, 24) === '75% beat close (3/4, 24 push)');
const allMatchedSpoken = heroAccessibilityLabel({
  notLoaded: false, picks: 8, label: 'EUROLEAGUE', units: 0, risked: 8, roi: 0,
  wins: 4, losses: 4, pushes: 0, winRate: 0.5, clvBeatRate: null, clvPush: 8,
});
check('spoken label for an all-matched set', allMatchedSpoken.includes('Beat the closing line, all 8 matched the close') && !allMatchedSpoken.includes('0 measured'), allMatchedSpoken);
const allMatchedSheet = closingLineBody({
  clvSettled: 8, clvBeatRate: null, clvPush: 8,
  clvGameSettled: 8, clvGameBeatRate: null, clvGamePush: 8,
  clvPropSettled: 0, clvPropBeatRate: null, clvPropPush: 0,
  marketClvSettled: 0, marketClvBeatRate: null,
});
check('sheet for an all-matched set', allMatchedSheet.endsWith('All 8 matched the close') && !allMatchedSheet.includes('0 measured'), allMatchedSheet.slice(-60));
const splitSheet = closingLineBody({
  clvSettled: 12, clvBeatRate: 0.75, clvPush: 8,
  clvGameSettled: 8, clvGameBeatRate: null, clvGamePush: 8,
  clvPropSettled: 4, clvPropBeatRate: 0.75, clvPropPush: 0,
  marketClvSettled: 0, marketClvBeatRate: null,
});
check('a split with only matches says so', splitSheet.includes('Game lines  All 8 matched the close') && !splitSheet.includes('0 measured'), splitSheet);

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
check('pill stays inside', pill.left >= 0 && pill.left + 76 <= 320 && pill.top >= 0 && pill.top + 22 <= 176);
const wide = pillFrame(300, 40, 320, 176, 400, 48);
check('a pill wider than the chart stays inside',
  wide.left >= 0 && wide.left + Math.min(400, 320) <= 320 && wide.top >= 0 && wide.top + 48 <= 176 && wide.maxWidth === 320,
  `${wide.left},${wide.top},${wide.maxWidth}`);
check('stale scrub index is released', scrubIndexForSeries(25, 5) === null);
check('negative scrub index is released', scrubIndexForSeries(-1, 5) === null);
check('in-range scrub index is kept', scrubIndexForSeries(2, 5) === 2);
check('a one-point series cannot be scrubbed', scrubIndexForSeries(0, 1) === null);
check('a non-integer scrub index is released', scrubIndexForSeries(1.5, 5) === null);
const sameDays = [{ date: '2026-09-01' }];
check('series key changes with the dates',
  equitySeriesKey('NFL', [{ date: '2026-09-01' }, { date: '2026-09-02' }]) !== equitySeriesKey('NFL', sameDays));
check('series key includes the sport', equitySeriesKey('NFL', sameDays) !== equitySeriesKey('NBA', sameDays));
check('chart pad clears the bubble and the caption', CHART_PAD.top >= 44 && CHART_PAD.bottom >= 20);
const bubble = scrubBubbleFrame(4, 320, 148, 48);
check('bubble stays on the top edge, clear of the axis', bubble.top === 0 && bubble.left >= 48, String(bubble.left));
check('chart date', chartDateLabel('2026-09-01') === 'Sep 1');
check('scrub release waits four seconds', SCRUB_RELEASE_MS === 4000);

let released = false;
const quick = scheduleScrubRelease(null, () => { released = true; }, 20);
let stale = false;
const first = scheduleScrubRelease(null, () => { stale = true; }, 30);
const second = scheduleScrubRelease(first, () => {}, 500);
setTimeout(() => {
  check('a scrub releases when its timer fires', released);
  check('a new scrub cancels the previous release', !stale);
  clearTimeout(quick);
  clearTimeout(second);
  console.log(failures === 0 ? '\nAll record-hero checks passed.' : `\n${failures} FAILED.`);
  process.exit(failures === 0 ? 0 : 1);
}, 60);

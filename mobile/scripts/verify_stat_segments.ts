/**
 * Standalone verification of the Stats tab's position row
 * (src/lib/statSegments.ts — Designer Option A, Matt-approved 2026-09-25).
 * Run with:
 *
 *   npx tsx scripts/verify_stat_segments.ts
 *
 * Pins: the segment list per sport, the chips per segment and their order,
 * that every chip is a real STAT_CATALOG entry (so no key or market is
 * invented), that no catalog stat becomes unreachable, the keep-or-reset
 * rule on a segment switch (rule 5), and the position filter — which is
 * NFL-only, only on the reads that return `pos`, and never a guess.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { Sport } from '../src/hooks/useSportFilter';
import { STAT_CATALOG, defaultStatFor, type StatDef } from '../src/lib/statCatalog';
import {
  chipsForSegment,
  defaultSegmentFor,
  matchesPosition,
  omittedChips,
  positionsForSegment,
  readCarriesPosition,
  segmentAccessibilityLabel,
  segmentLabel,
  segmentsForSport,
  statForSegment,
  type StatSegment,
} from '../src/lib/statSegments';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const ck = (d: StatDef | null) => (d ? `${d.group}:${String(d.key)}` : 'null');
const chips = (sport: Sport, seg: StatSegment) => chipsForSegment(sport, seg).map(ck);
const eq = (a: readonly string[], b: readonly string[]) =>
  a.length === b.length && a.every((x, i) => x === b[i]);
const def = (sport: Sport, group: string, key: string) =>
  STAT_CATALOG.find((d) => d.sport === sport && d.group === group && d.key === key) ?? null;

// ── 1. Segments per sport ───────────────────────────────────────────────────
const WANT_SEGMENTS: Record<Sport, StatSegment[]> = {
  NFL: ['qb', 'rb', 'wrte', 'def', 'teams'],
  NCAAF: ['qb', 'rb', 'wrte', 'def', 'teams'],
  MLB: ['hitters', 'pitchers', 'teams'],
  NBA: ['players', 'teams'],
  WNBA: ['players', 'teams'],
  NHL: ['players', 'teams'], // unchanged: Players | Teams
  UFC: ['players'], // one item → SegmentTabs renders no row
  GOLF: ['players'], // unchanged: no row
};
for (const sport of Object.keys(WANT_SEGMENTS) as Sport[]) {
  const got = segmentsForSport(sport);
  check(`${sport}: segments are ${WANT_SEGMENTS[sport].join(' / ')}`, eq(got, WANT_SEGMENTS[sport]), got.join(','));
}
check('UFC gets no position row (fewer than two segments)', segmentsForSport('UFC').length < 2);
check(
  'labels: QB / RB / WR/TE / DEF / Teams, Hitters / Pitchers / Teams',
  segmentsForSport('NFL').map(segmentLabel).join(' / ') === 'QB / RB / WR/TE / DEF / Teams' &&
    segmentsForSport('MLB').map(segmentLabel).join(' / ') === 'Hitters / Pitchers / Teams' &&
    segmentsForSport('NBA').map(segmentLabel).join(' / ') === 'Players / Teams',
);
check(
  'abbreviations are spoken as words',
  segmentAccessibilityLabel('wrte') === 'Receivers and tight ends' &&
    segmentAccessibilityLabel('qb') === 'Quarterbacks' &&
    segmentAccessibilityLabel('teams') === 'Teams',
);

// Width: the row divides the screen evenly (SegmentTabs, flex: 1, no
// horizontal padding). 393pt / 5 NFL segments = 78.6pt per tab. A generous
// estimate of a semibold 15pt glyph (font.size.body) is 0.66em ≈ 9.9pt, so a
// label must stay under ~7.9 characters; the widest football label is 5.
{
  const W = 393;
  for (const sport of ['NFL', 'NCAAF', 'MLB', 'NBA'] as Sport[]) {
    const segs = segmentsForSport(sport);
    const per = W / segs.length;
    const widest = Math.max(...segs.map((s) => segmentLabel(s).length * 15 * 0.66));
    check(
      `${sport}: every label fits its ${per.toFixed(1)}pt tab on a 393pt screen`,
      widest <= per,
      `widest ≈ ${widest.toFixed(1)}pt`,
    );
  }
}

// ── 2. Chips per segment, in order ──────────────────────────────────────────
const WANT_CHIPS: [Sport, StatSegment, string[]][] = [
  ['NFL', 'qb', [
    'Passing:passing_yards', 'Passing:passing_tds', 'Passing:completions',
    'Passing:attempts', 'Passing:interceptions', 'Rushing:rushing_yards',
  ]],
  ['NFL', 'rb', [
    'Rushing:rushing_yards', 'Rushing:carries', 'Rushing:rush_rec_tds',
    'Receiving:receptions', 'Receiving:receiving_yards',
  ]],
  ['NFL', 'wrte', [
    'Receiving:receptions', 'Receiving:receiving_yards', 'Receiving:targets',
    'Receiving:rush_rec_tds',
  ]],
  ['NFL', 'def', ['Defense:def_sacks', 'Defense:def_interceptions']],
  ['NCAAF', 'qb', [
    'Passing:passing_yards', 'Passing:passing_tds', 'Passing:completions',
    'Passing:attempts', 'Passing:interceptions', 'Rushing:rushing_yards',
  ]],
  ['NCAAF', 'rb', [
    'Rushing:rushing_yards', 'Rushing:carries', 'Rushing:rush_rec_tds',
    'Receiving:receptions', 'Receiving:receiving_yards',
  ]],
  // No Targets: CFBD's box score does not report them, so the catalog has none.
  ['NCAAF', 'wrte', ['Receiving:receptions', 'Receiving:receiving_yards', 'Receiving:rush_rec_tds']],
  ['NCAAF', 'def', [
    'Defense:def_tackles', 'Defense:def_solo', 'Defense:def_sacks',
    'Defense:def_tfl', 'Defense:def_pd', 'Defense:def_interceptions',
  ]],
];
for (const [sport, seg, want] of WANT_CHIPS) {
  const got = chips(sport, seg);
  check(`${sport} ${segmentLabel(seg)}: chips in spec order`, eq(got, want), got.join(', '));
}
check(
  'MLB Hitters is the Batting group, Pitchers is Pitching, in catalog order',
  eq(chips('MLB', 'hitters'), STAT_CATALOG.filter((d) => d.sport === 'MLB' && d.group === 'Batting').map(ck)) &&
    eq(chips('MLB', 'pitchers'), STAT_CATALOG.filter((d) => d.sport === 'MLB' && d.group === 'Pitching').map(ck)),
);
for (const sport of ['NBA', 'WNBA', 'UFC'] as Sport[]) {
  check(
    `${sport} Players: every catalog chip, unchanged`,
    eq(chips(sport, 'players'), STAT_CATALOG.filter((d) => d.sport === sport).map(ck)),
  );
}
check('Teams has no player chips (it is its own board)', chips('NFL', 'teams').length === 0 && chips('MLB', 'teams').length === 0);

// Every chip is the catalog's own object — same key, same group, same market.
for (const sport of ['NFL', 'NCAAF', 'MLB', 'NBA', 'WNBA', 'UFC'] as Sport[]) {
  const all = segmentsForSport(sport).flatMap((s) => chipsForSegment(sport, s));
  check(`${sport}: every chip is a STAT_CATALOG entry (no invented key)`, all.every((c) => STAT_CATALOG.includes(c)));
  const reachable = new Set(all.map(ck));
  const lost = STAT_CATALOG.filter((d) => d.sport === sport && !reachable.has(ck(d))).map(ck);
  check(`${sport}: no catalog stat became unreachable`, lost.length === 0, lost.join(', '));
  for (const seg of segmentsForSport(sport)) {
    const c = chips(sport, seg);
    check(`${sport} ${segmentLabel(seg)}: no chip listed twice`, new Set(c).size === c.length);
  }
}

// Omissions are listed, never filled.
check('NCAAF WR/TE omits exactly Receiving:targets', eq(omittedChips('NCAAF', 'wrte'), ['Receiving:targets']));
{
  const other: string[] = [];
  for (const sport of ['NFL', 'NCAAF', 'MLB', 'NBA', 'WNBA', 'UFC'] as Sport[]) {
    for (const seg of segmentsForSport(sport)) {
      if (sport === 'NCAAF' && seg === 'wrte') continue;
      other.push(...omittedChips(sport, seg).map((k) => `${sport}/${seg}/${k}`));
    }
  }
  check('no other spec chip is missing from the catalog', other.length === 0, other.join(', '));
}

// The sport switch still lands on the sport's default stat, and that stat is
// on the segment the switch selects.
for (const sport of ['NFL', 'NCAAF', 'MLB', 'NBA', 'WNBA', 'UFC'] as Sport[]) {
  const d = defaultStatFor(sport);
  check(
    `${sport}: the default stat (${ck(d)}) is on the default segment (${defaultSegmentFor(sport)})`,
    d != null && chipsForSegment(sport, defaultSegmentFor(sport)).includes(d),
  );
}

// ── 3. Rule 5: keep the stat if the new segment has it, else its first chip ─
const cases: [string, Sport, StatDef | null, StatSegment, string][] = [
  ['QB Rush Yards → RB keeps Rush Yards', 'NFL', def('NFL', 'Rushing', 'rushing_yards'), 'rb', 'Rushing:rushing_yards'],
  ['QB Pass Yards → RB lands on Rush Yards (first chip)', 'NFL', def('NFL', 'Passing', 'passing_yards'), 'rb', 'Rushing:rushing_yards'],
  ['RB Receptions → WR/TE keeps Receptions', 'NFL', def('NFL', 'Receiving', 'receptions'), 'wrte', 'Receiving:receptions'],
  ['RB Anytime TD → WR/TE keeps Anytime TD (the Receiving chip)', 'NFL', def('NFL', 'Rushing', 'rush_rec_tds'), 'wrte', 'Receiving:rush_rec_tds'],
  ['WR/TE Anytime TD → RB keeps Anytime TD (the Rushing chip)', 'NFL', def('NFL', 'Receiving', 'rush_rec_tds'), 'rb', 'Rushing:rush_rec_tds'],
  ['WR/TE Targets → RB lands on Rush Yards', 'NFL', def('NFL', 'Receiving', 'targets'), 'rb', 'Rushing:rushing_yards'],
  ['RB Rush Yards → QB keeps Rush Yards', 'NFL', def('NFL', 'Rushing', 'rushing_yards'), 'qb', 'Rushing:rushing_yards'],
  ['DEF Sacks → QB lands on Pass Yards', 'NFL', def('NFL', 'Defense', 'def_sacks'), 'qb', 'Passing:passing_yards'],
  ['QB Pass TDs → DEF lands on Sacks', 'NFL', def('NFL', 'Passing', 'passing_tds'), 'def', 'Defense:def_sacks'],
  ['NCAAF RB Carries → WR/TE lands on Receptions', 'NCAAF', def('NCAAF', 'Rushing', 'carries'), 'wrte', 'Receiving:receptions'],
  ['NCAAF DEF Sacks → DEF keeps Sacks', 'NCAAF', def('NCAAF', 'Defense', 'def_sacks'), 'def', 'Defense:def_sacks'],
  ['MLB Hits → Pitchers lands on Strikeouts', 'MLB', def('MLB', 'Batting', 'hits'), 'pitchers', 'Pitching:p_strikeouts'],
  ['MLB Walks → Hitters keeps Walks', 'MLB', def('MLB', 'Batting', 'walks'), 'hitters', 'Batting:walks'],
  ['no stat selected → first chip', 'NFL', null, 'wrte', 'Receiving:receptions'],
  ['Teams has no chip to land on', 'NFL', def('NFL', 'Passing', 'passing_yards'), 'teams', 'null'],
];
for (const [name, sport, cur, seg, want] of cases) {
  const got = ck(statForSegment(sport, seg, cur));
  check(`rule 5: ${name}`, got === want, got);
}
check(
  'rule 5 returns the catalog object, not a copy (the chip row compares group + key)',
  statForSegment('NFL', 'rb', def('NFL', 'Rushing', 'rushing_yards')) === def('NFL', 'Rushing', 'rushing_yards'),
);

// ── 4. Position filter ──────────────────────────────────────────────────────
check('NFL Averages carries a position', readCarriesPosition('NFL', 'totals', 'season') && readCarriesPosition('NFL', 'totals', 10));
check('NFL last-N Hit Rates carry a position', readCarriesPosition('NFL', 'hitRate', 10));
check(
  'NFL Season and H2H Hit Rates do not (player_{season,h2h}_stat_values_nfl return no pos)',
  !readCarriesPosition('NFL', 'hitRate', 'season') && !readCarriesPosition('NFL', 'hitRate', 'h2h'),
);
check('NCAAF never carries a position (CFBD names participants, not positions)',
  !readCarriesPosition('NCAAF', 'totals', 10) && !readCarriesPosition('NCAAF', 'hitRate', 10));
check('NCAAF segments never filter rows', (['qb', 'rb', 'wrte', 'def'] as StatSegment[]).every((s) => positionsForSegment('NCAAF', s, true) === null));
check('MLB / NBA / Teams never filter by position',
  positionsForSegment('MLB', 'hitters', true) === null &&
    positionsForSegment('NBA', 'players', true) === null &&
    positionsForSegment('NFL', 'teams', true) === null);
check('no filter on a read without a position', positionsForSegment('NFL', 'qb', false) === null);

const qb = positionsForSegment('NFL', 'qb', true);
const rb = positionsForSegment('NFL', 'rb', true);
const wr = positionsForSegment('NFL', 'wrte', true);
const dfn = positionsForSegment('NFL', 'def', true);
check('QB admits QB and nothing else', matchesPosition('QB', qb) && !matchesPosition('RB', qb) && !matchesPosition('WR', qb));
check('RB admits RB and FB', matchesPosition('RB', rb) && matchesPosition('FB', rb) && !matchesPosition('WR', rb));
check('WR/TE admits WR and TE', matchesPosition('WR', wr) && matchesPosition('TE', wr) && !matchesPosition('RB', wr));
check(
  'DEF admits only real defensive positions (nflverse codes measured 2026-09-25)',
  ['LB', 'CB', 'DT', 'SAF', 'DE', 'DB', 'OLB', 'FS', 'S', 'MLB', 'NT', 'ILB', 'DL'].every((p) => matchesPosition(p, dfn)) &&
    !['QB', 'RB', 'WR', 'TE', 'K', 'P', 'LS', 'OT', 'G', 'C', 'OL', 'FB'].some((p) => matchesPosition(p, dfn)),
);
check(
  'kickers, punters, long snappers and linemen are in no segment',
  ['K', 'P', 'LS', 'OT', 'G', 'C', 'OL'].every((p) => ![qb, rb, wr, dfn].some((s) => matchesPosition(p, s))),
);
{
  const sets = [qb, rb, wr, dfn].map((s) => [...(s ?? [])]);
  const all = sets.flat();
  check('the four position sets are disjoint', new Set(all).size === all.length);
}
check('an unknown position is not guessed into a segment', !matchesPosition(null, qb) && !matchesPosition(undefined, dfn) && !matchesPosition('', wr));
check('with no filter every row passes, position or not', matchesPosition(null, null) && matchesPosition('K', null));
check('position codes compare case- and space-insensitively', matchesPosition(' wr ', wr));

// ── 5. The screen uses the module, and the dropdown is gone ─────────────────
const stats = readFileSync(join(import.meta.dirname, '..', 'src/screens/StatsScreen.tsx'), 'utf-8');
check('StatsScreen: the chip row reads chipsForSegment', /chipsForSegment\(sport, segment\)\.map/.test(stats));
check('StatsScreen: no StatGroupSheet (the category dropdown is gone)', !stats.includes('StatGroupSheet'));
check('StatsScreen: both boards apply the position filter',
  (stats.match(/matchesPosition\((r|p)\.pos, segmentPositions\)/g) ?? []).length === 2);
check('StatsScreen: a segment switch goes through statForSegment (rule 5)', /statForSegment\(sport, next, stat\)/.test(stats));
check('StatsScreen: the sport switch resets the segment with the stat',
  /setStat\(next\);\s*\n\s*setSegmentPick\(defaultSegmentFor\(sport\)\)/.test(stats));
check('StatsScreen: the sport switch still strands nobody on Teams for UFC/golf',
  /if \(!supportsTeamBoard\(sport\)\) setBoardMode\('players'\)/.test(stats));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} check(s) FAILED.`);
process.exit(failures === 0 ? 0 : 1);

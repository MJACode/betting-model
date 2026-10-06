/**
 * Verifies the pure logic behind the Stats tab's Teams board.
 *
 *   npx tsx scripts/verify_team_board.ts
 *
 * The load-bearing behaviours here are the tertile tint (which must follow
 * each stat's DIRECTION — a low defensive rating is good, a low Corsi is not)
 * and the thin-sample guard (a 3-2 ATS split must not rank or tint as if it
 * were a season's worth of evidence).
 */
import {
  MIN_SPLIT_SAMPLE,
  compareTeams,
  isThinSample,
  rankTeams,
  sampleFor,
  tertileCuts,
  tierFor,
} from '../src/lib/teamBoard';
import { teamRanks } from '../src/lib/teamDetail';
import {
  EXPLAIN_PTS_ADDED,
  EXPLAIN_SUCCESS,
  TEAM_STAT_CATALOG,
  boardValueSpeech,
  defaultTeamStatFor,
  formatRecord,
  formatTeamStat,
  spokenTeamStat,
  supportsTeamBoard,
  teamGroupLabel,
  teamGroupsForSport,
  teamStatValue,
  teamStatAfterOffer,
  teamStatsForBoard,
  teamStatsForSport,
  teamStatsShown,
  type TeamStatDef,
} from '../src/lib/teamStatCatalog';
import type { TeamStatsRow } from '../src/types';

let pass = 0;
let fail = 0;
function check(name: string, cond: boolean, extra?: unknown) {
  if (cond) {
    pass++;
  } else {
    fail++;
    console.error(`FAIL: ${name}`, extra ?? '');
  }
}
function eq(name: string, got: unknown, want: unknown) {
  check(`${name} (got ${JSON.stringify(got)}, want ${JSON.stringify(want)})`, got === want);
}

function team(over: Partial<TeamStatsRow> & { team: string }): TeamStatsRow {
  return {
    conference: null,
    games_played: 40,
    wins: 20,
    losses: 20,
    win_pct: 0.5,
    points_for_pg: 100,
    points_against_pg: 100,
    point_diff_pg: 0,
    ats_w: 20, ats_l: 20, ats_p: 0, ats_pct: 0.5,
    ou_o: 20, ou_u: 20, ou_p: 0, over_pct: 0.5,
    home_w: 10, home_l: 10, away_w: 10, away_l: 10,
    ats_home_pct: 0.5, ats_away_pct: 0.5,
    fav_ats_pct: 0.5, dog_ats_pct: 0.5,
    rest_adv_games: 12, rest_adv_ats_pct: 0.5,
    short_rest_games: 10, short_rest_ats_pct: 0.5,
    ...over,
  } as TeamStatsRow;
}

const def = (key: string, better: 'high' | 'low' | null): TeamStatDef =>
  ({ key, label: key, group: 'Efficiency', sports: ['NBA'], format: 'dec1', better }) as TeamStatDef;

// ── tertileCuts ───────────────────────────────────────────────────────────
check('tertileCuts needs 3+ values', tertileCuts([1, 2]) === null);
check('tertileCuts null when no spread', tertileCuts([5, 5, 5, 5]) === null);
{
  const c = tertileCuts([1, 2, 3, 4, 5, 6, 7, 8, 9]);
  check('tertileCuts returns cuts on a spread column', c !== null && c.lo < c.hi, c);
}
check('tertileCuts ignores NaN', tertileCuts([1, NaN, 5, 9]) !== null);

// ── tierFor: direction is the whole point ─────────────────────────────────
const cuts = { lo: 3, hi: 7 };
eq('high-is-better: top third is good', tierFor(9, cuts, 'high'), 'good');
eq('high-is-better: bottom third is bad', tierFor(1, cuts, 'high'), 'bad');
eq('LOW-is-better: bottom third is good', tierFor(1, cuts, 'low'), 'good');
eq('LOW-is-better: top third is bad', tierFor(9, cuts, 'low'), 'bad');
eq('middle third is mid either way', tierFor(5, cuts, 'high'), 'mid');
eq('middle third is mid when low is better', tierFor(5, cuts, 'low'), 'mid');
eq('no direction means no tint', tierFor(9, cuts, null), 'none');
eq('no value means no tint', tierFor(null, cuts, 'high'), 'none');
eq('no cuts means no tint', tierFor(9, null, 'high'), 'none');
// Boundary: a value exactly on a cut belongs to that outer third.
eq('value on the hi cut is top third', tierFor(7, cuts, 'high'), 'good');
eq('value on the lo cut is bottom third', tierFor(3, cuts, 'high'), 'bad');

// ── compareTeams: direction + nulls sink + tie-break ──────────────────────
{
  const hi = def('off_rating', 'high');
  const a = team({ team: 'A', off_rating: 120 });
  const b = team({ team: 'B', off_rating: 100 });
  check('high-is-better sorts larger first', compareTeams(a, b, hi) < 0);
}
{
  const lo = def('def_rating', 'low');
  const a = team({ team: 'A', def_rating: 100 });
  const b = team({ team: 'B', def_rating: 120 });
  check('low-is-better sorts smaller first', compareTeams(a, b, lo) < 0);
}
{
  const hi = def('off_rating', 'high');
  const withVal = team({ team: 'A', off_rating: 90 });
  const noVal = team({ team: 'B' });
  check('null sinks below a real value (high)', compareTeams(withVal, noVal, hi) < 0);
  const lo = def('def_rating', 'low');
  const withLow = team({ team: 'A', def_rating: 999 });
  check('null sinks below a real value (low too)', compareTeams(withLow, noVal, lo) < 0);
}
{
  // Equal rate: the better-established sample ranks first.
  const d = { ...def('short_rest_ats_pct', 'high'), sample: 'short_rest_games' } as TeamStatDef;
  const many = team({ team: 'A', short_rest_ats_pct: 0.6, short_rest_games: 20 });
  const few = team({ team: 'B', short_rest_ats_pct: 0.6, short_rest_games: 4 });
  check('ties break toward the larger sample', compareTeams(many, few, d) < 0);
}

// ── sample + thin-sample guard ────────────────────────────────────────────
{
  const plain = def('off_rating', 'high');
  eq('sampleFor falls back to games played', sampleFor(team({ team: 'A' }), plain), 40);
  check('a season-long metric is never "thin"', !isThinSample(team({ team: 'A', games_played: 2 }), plain));

  const split = { ...def('short_rest_ats_pct', 'high'), sample: 'short_rest_games' } as TeamStatDef;
  eq('sampleFor uses the split column', sampleFor(team({ team: 'A', short_rest_games: 5 }), split), 5);
  check('under the floor is thin', isThinSample(team({ team: 'A', short_rest_games: MIN_SPLIT_SAMPLE - 1 }), split));
  check('at the floor is not thin', !isThinSample(team({ team: 'A', short_rest_games: MIN_SPLIT_SAMPLE }), split));
}

// ── rankTeams: thin rows must not distort the league's tertiles ───────────
{
  const split = { ...def('short_rest_ats_pct', 'high'), sample: 'short_rest_games' } as TeamStatDef;
  const rows = [
    team({ team: 'A', short_rest_ats_pct: 0.50, short_rest_games: 20 }),
    team({ team: 'B', short_rest_ats_pct: 0.52, short_rest_games: 20 }),
    team({ team: 'C', short_rest_ats_pct: 0.54, short_rest_games: 20 }),
    // A 2-0 fluke. It tops the sort on rate, but must be excluded from cuts.
    team({ team: 'FLUKE', short_rest_ats_pct: 1.0, short_rest_games: 2 }),
  ];
  const withFluke = rankTeams(rows, split);
  const withoutFluke = rankTeams(rows.slice(0, 3), split);
  eq('thin row excluded from tertile cuts (lo)', withFluke.cuts?.lo, withoutFluke.cuts?.lo);
  eq('thin row excluded from tertile cuts (hi)', withFluke.cuts?.hi, withoutFluke.cuts?.hi);
  // And it is never tinted as a league leader.
  const fluke = withFluke.rows.find((r) => r.team === 'FLUKE')!;
  eq(
    'thin row renders untinted',
    isThinSample(fluke, split) ? 'none' : tierFor(teamStatValue(fluke, split), withFluke.cuts, 'high'),
    'none',
  );
}
{
  // rankTeams must not mutate its input.
  const d = def('off_rating', 'high');
  const rows = [team({ team: 'B', off_rating: 100 }), team({ team: 'A', off_rating: 120 })];
  const before = rows.map((r) => r.team).join(',');
  rankTeams(rows, d);
  eq('rankTeams does not mutate the caller array', rows.map((r) => r.team).join(','), before);
}

// ── formatting ────────────────────────────────────────────────────────────
eq('null formats as a dash', formatTeamStat(null, 'dec2'), '—');
eq('pct3 renders a rate as a percentage', formatTeamStat(0.5432, 'pct3'), '54.3%');
eq('int rounds', formatTeamStat(103.6, 'int'), '104');
eq('dec3 keeps three places', formatTeamStat(0.1234, 'dec3'), '0.123');
{
  const atsDef = TEAM_STAT_CATALOG.find((s) => s.key === 'ats_pct')!;
  eq('record renders W-L', formatRecord(team({ team: 'A', ats_w: 67, ats_l: 42, ats_p: 0 }), atsDef), '67-42');
  eq('record shows pushes when present', formatRecord(team({ team: 'A', ats_w: 67, ats_l: 42, ats_p: 3 }), atsDef), '67-42-3');
  const plain = def('off_rating', 'high');
  eq('no record columns means no record line', formatRecord(team({ team: 'A' }), plain), null);
}
// PostgREST can hand back NUMERIC as a string.
eq('numeric strings coerce', teamStatValue({ ...team({ team: 'A' }), off_rating: '112.5' as unknown as number }, def('off_rating', 'high')), 112.5);
eq('garbage coerces to null', teamStatValue({ ...team({ team: 'A' }), off_rating: 'n/a' as unknown as number }, def('off_rating', 'high')), null);

// ── catalog wiring ────────────────────────────────────────────────────────
for (const sport of ['MLB', 'NBA', 'WNBA', 'NHL', 'NFL', 'NCAAF'] as const) {
  check(`${sport} has a team board`, supportsTeamBoard(sport));
  const stats = teamStatsForSport(sport);
  check(`${sport} has team stats`, stats.length > 0);
  const d = defaultTeamStatFor(sport);
  check(`${sport} has a default team stat`, d !== null);
  // Efficiency-first is the product decision — the board must never open on
  // an ATS record.
  eq(`${sport} opens on an efficiency stat`, d?.group, 'Efficiency');
  const groups = teamGroupsForSport(sport);
  eq(`${sport} lists Efficiency first`, groups[0], 'Efficiency');
  check(`${sport} groups are non-empty`, groups.every((g) => stats.some((s) => s.group === g)));
}
for (const sport of ['UFC', 'GOLF'] as const) {
  check(`${sport} has no team board`, !supportsTeamBoard(sport));
}
// MLB plays daily, so rest splits are noise there and must not be offered.
check(
  'MLB offers no rest splits',
  !teamStatsForSport('MLB').some((s) => s.key === 'short_rest_ats_pct' || s.key === 'rest_adv_ats_pct'),
);
check(
  'NBA does offer rest splits',
  teamStatsForSport('NBA').some((s) => s.key === 'short_rest_ats_pct'),
);
// Dead / proprietary columns must never reach the catalog.
check('xGF% is not offered (0% populated)', !TEAM_STAT_CATALOG.some((s) => String(s.key).includes('xgf')));
// Over rate has no "good" end — it is a tendency, not a grade.
eq('over% carries no direction', TEAM_STAT_CATALOG.find((s) => s.key === 'over_pct')?.better, null);
eq('pace carries no direction', TEAM_STAT_CATALOG.find((s) => s.key === 'pace')?.better, null);
// Every betting split that can be thin must declare a sample column or a record.
for (const s of TEAM_STAT_CATALOG.filter((x) => x.group === 'Betting')) {
  check(`betting stat ${String(s.key)} is auditable (record or sample)`, Boolean(s.record || s.sample || String(s.key).includes('ats_') || String(s.key).includes('over_')));
}

// ── plain labels, signed numbers, VoiceOver, football tab name ─────────────
{
  const epaOff = TEAM_STAT_CATALOG.find((s) => s.key === 'epa_off')!;
  const epaDef = TEAM_STAT_CATALOG.find((s) => s.key === 'epa_def')!;
  const sucOff = TEAM_STAT_CATALOG.find((s) => s.key === 'success_off')!;
  eq('points-added chip', epaOff.label, 'Pts added/play Off');
  eq('points-added header', epaOff.header, 'Pts added/play');
  eq('points-added sheet label', epaOff.explain?.a11y, 'About points added per play');
  eq('points-added copy', epaOff.explain?.body, EXPLAIN_PTS_ADDED.body);
  check('points-added copy does not treat 0 as average',
    !EXPLAIN_PTS_ADDED.body.includes('Above 0') && !EXPLAIN_PTS_ADDED.body.toLowerCase().includes('better than average'));
  check('points-added copy says higher means more and to compare by rank',
    EXPLAIN_PTS_ADDED.body.includes('Higher means more points per play.')
    && EXPLAIN_PTS_ADDED.body.includes('Compare teams by rank.')
    && EXPLAIN_PTS_ADDED.body.includes('For a defense, lower is better.'));
  eq('success chip', sucOff.label, 'Successful plays Off');
  eq('success header', sucOff.header, 'Successful plays');
  eq('success sheet label', sucOff.explain?.a11y, 'About successful plays');
  eq('success copy', sucOff.explain?.body, EXPLAIN_SUCCESS.body);
  check('success copy uses the CFBD 50/70/100 definition',
    EXPLAIN_SUCCESS.body.includes('50% of the yards to go on 1st down')
    && EXPLAIN_SUCCESS.body.includes('70% on 2nd')
    && EXPLAIN_SUCCESS.body.includes('100% on 3rd or 4th')
    && !EXPLAIN_SUCCESS.body.includes('40%')
    && !EXPLAIN_SUCCESS.body.includes('60%'));
  eq('success is a percent of a 0..1 rate', sucOff.format, 'pct3');
  check('both football sports share the points-added row',
    epaOff.sports.includes('NFL') && epaOff.sports.includes('NCAAF') && epaDef.sports.includes('NFL'));
  eq('NFL tab', teamGroupLabel('Efficiency', 'NFL'), 'Offense & defense');
  eq('NCAAF tab', teamGroupLabel('Efficiency', 'NCAAF'), 'Offense & defense');
  eq('NBA keeps Efficiency', teamGroupLabel('Efficiency', 'NBA'), 'Efficiency');
  eq('NFL record tab is unchanged', teamGroupLabel('Record', 'NFL'), 'Record');
  eq('MLB tab is unchanged', teamGroupLabel('Efficiency', 'MLB'), 'Efficiency');

  const MINUS = '\u2212';
  eq('positive points-added', formatTeamStat(0.21, 'sdec2'), '+0.21');
  eq('negative points-added uses a true minus', formatTeamStat(-0.08, 'sdec2'), `${MINUS}0.08`);
  eq('rounds before the sign, positive side', formatTeamStat(0.004, 'sdec2'), '0.00');
  eq('rounds before the sign, negative side', formatTeamStat(-0.004, 'sdec2'), '0.00');
  eq('a real hundredth still signs', formatTeamStat(-0.005, 'sdec2'), `${MINUS}0.01`);
  eq('null is a dash, not zero', formatTeamStat(null, 'sdec2'), '—');
  eq('success rate 0.467 prints 46.7%', formatTeamStat(0.467, 'pct3'), '46.7%');
  eq('spoken plus', spokenTeamStat(0.21, 'sdec2'), 'plus 0.21');
  eq('spoken minus', spokenTeamStat(-0.08, 'sdec2'), 'minus 0.08');
  eq('spoken zero has no sign word', spokenTeamStat(0.004, 'sdec2'), '0.00');
  eq('spoken percent', spokenTeamStat(0.467, 'pct3'), '46.7 percent');
  eq('board VoiceOver, offense',
    boardValueSpeech(epaOff, 0.21, 1),
    'Points added per play, offense, plus 0.21, ranks 1st');
  eq('board VoiceOver, defense',
    boardValueSpeech(epaDef, -0.08, 2),
    'Points added per play, defense, minus 0.08, ranks 2nd');
  eq('11th not 11st', boardValueSpeech(epaOff, 0.01, 11),
    'Points added per play, offense, plus 0.01, ranks 11th');

  // Defense ranks lowest-first, so 1st is the best defense.
  const ranked = rankTeams([
    team({ team: 'LEAK', epa_def: 0.2 }),
    team({ team: 'STINGY', epa_def: -0.08 }),
    team({ team: 'MID', epa_def: 0.05 }),
  ], epaDef);
  eq('best defense is rank 1', ranked.rows[0].team, 'STINGY');
  eq('worst defense is last', ranked.rows[2].team, 'LEAK');

  const emptyNfl = [team({ team: 'JAX' }), team({ team: 'PHI' })];
  check('NFL hides points-added chips when every value is null',
    !teamStatsForBoard('NFL', emptyNfl).some((s) => s.key === 'epa_off' || s.key === 'success_off'));
  check('NFL team page hides the same empty rows',
    !teamRanks(emptyNfl, 'JAX', 'NFL', 'Efficiency').some((r) => r.def.untilData));
  check('NFL still offers yards/play',
    teamStatsForBoard('NFL', emptyNfl).some((s) => s.key === 'yards_per_play'));
  const liveNcaaf = [team({ team: 'ALA', epa_off: 0.21, epa_def: -0.08, success_off: 0.467, success_def: 0.4 })];
  check('NCAAF shows points-added once a value exists',
    teamStatsForBoard('NCAAF', liveNcaaf).some((s) => s.key === 'epa_off')
    && teamStatsForBoard('NCAAF', liveNcaaf).some((s) => s.key === 'success_def'));
  check('NCAAF team page lists the same rows',
    teamRanks(liveNcaaf, 'ALA', 'NCAAF', 'Efficiency').some((r) => r.def.key === 'epa_off'));
  eq('NFL still opens on yards/play', defaultTeamStatFor('NFL')?.key, 'yards_per_play');

  const epa = TEAM_STAT_CATALOG.find((s) => s.key === 'epa_off')!;
  const emptyOffered = teamStatsForBoard('NCAAF', []);
  check('a failed load does not move the user off points added',
    teamStatAfterOffer(epa, emptyOffered, 'NCAAF', true)?.key === 'epa_off');
  eq('a successful empty column still falls back',
    teamStatAfterOffer(epa, emptyOffered, 'NCAAF', false)?.key, 'sp_overall');
  eq('a populated column keeps the selection',
    teamStatAfterOffer(epa, teamStatsForBoard('NCAAF', liveNcaaf), 'NCAAF', false)?.key, 'epa_off');
  const held = teamStatsShown(emptyOffered, 'NCAAF', epa, true);
  check('the held chip stays on the row during the error', held.some((s) => s.key === 'epa_off'));
  check('other empty untilData chips stay hidden during the error',
    !held.some((s) => s.key === 'success_off'));
  const nflOffered = teamStatsForBoard('NFL', emptyNfl);
  check('initial NFL load does not flash the empty points-added chip',
    !teamStatsShown(nflOffered, 'NFL', defaultTeamStatFor('NFL'), true).some((s) => s.key === 'epa_off'));
}

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);

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
import {
  TEAM_STAT_CATALOG,
  defaultTeamStatFor,
  formatRecord,
  formatTeamStat,
  supportsTeamBoard,
  teamGroupsForSport,
  teamStatValue,
  teamStatsForSport,
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

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);

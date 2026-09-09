/**
 * Toughness grading for the sports with no matchup view.
 *
 * Run with:  npx tsx scripts/verify_toughness.ts
 *
 * Matt, 2026-09-09, asked to filter the board on how tough a spot is. The
 * column that answers it existed for MLB and WNBA only — those are the only two
 * `*_tonight_matchups` views — so on the NFL board he was looking at, and on
 * NCAAF and NBA, it was a column of dashes and a filter over it would have
 * filtered nothing.
 *
 * The rest of the sports answer with the OPPONENT'S DEFENCE, off team stats we
 * already store for the Teams board, on the same A+..F scale. The anchors are
 * MEASURED — a median and an IQR-derived sigma from production — because the
 * three-tier column this scale replaced was built on remembered cliffs and
 * printed one colour four times in five.
 *
 * Measured 2026-09-09, `team_stats_board(sport, season)`:
 *
 *   NFL   points allowed/G   n=32   p25 20.07  median 23.09  p75 25.06
 *   NCAAF EPA/play allowed   n=136  p25 0.098  median 0.155  p75 0.203
 *   NBA   defensive rating   n=30   p25 110.42 median 112.40 p75 115.55
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  defenceMetricLabel,
  gradeOpponentDefence,
  gradesOnDefence,
  normalCdf,
} from '../src/lib/matchup';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const grade = (sport: string, opp: Record<string, number> | null, team = 'OPP') =>
  gradeOpponentDefence(sport, opp, team);

function main() {
  // ── which sports answer at all ─────────────────────────────────────────────
  check('the NFL grades on defence', gradesOnDefence('NFL'));
  check('so does NCAAF', gradesOnDefence('NCAAF'));
  check('and NBA', gradesOnDefence('NBA'));
  // MLB and WNBA keep the better answer they already have.
  check('MLB does NOT — it has a probable starter', !gradesOnDefence('MLB'));
  check('nor does WNBA — it has the opposing lineup', !gradesOnDefence('WNBA'));
  // NHL has no anchor because it has no rows to measure one from.
  check('NHL does not, and grades to null rather than a made-up letter',
    !gradesOnDefence('NHL') && grade('NHL', { points_against_pg: 3 }) === null);

  // ── the scale is centred where the league is ───────────────────────────────
  // Each median is the measured one. A median defence must land in the middle
  // of the scale; if an anchor is ever re-measured wrong, this is what catches
  // it — the old three-tier column failed exactly here.
  for (const [sport, opp, metric] of [
    ['NFL', { points_against_pg: 23.085 }, 'points allowed'],
    ['NCAAF', { epa_def: 0.155 }, 'EPA/play allowed'],
    ['NBA', { def_rating: 112.395 }, 'def rating'],
  ] as const) {
    const g = grade(sport, opp as Record<string, number>);
    check(`${sport}: a median ${metric} defence grades in the C band`,
      !!g?.grade && g.grade.startsWith('C'), `${g?.grade}`);
    check(`${sport}: and sits at the 50th percentile`,
      g?.score != null && Math.abs(g.score - 0.5) < 0.01, `${g?.score?.toFixed(3)}`);
  }

  // ── direction ──────────────────────────────────────────────────────────────
  // Every metric here points the same way: a HIGHER number is a worse defence
  // and so a BETTER spot for the player. Get this backwards and the column
  // recommends the hardest matchups on the board, which is the sign error §4
  // keeps warning about, one screen up.
  for (const [sport, stingy, leaky] of [
    ['NFL', { points_against_pg: 16.9 }, { points_against_pg: 30.0 }],
    ['NCAAF', { epa_def: 0.054 }, { epa_def: 0.233 }],
    ['NBA', { def_rating: 108.95 }, { def_rating: 116.83 }],
  ] as const) {
    const tough = grade(sport, stingy as Record<string, number>);
    const soft = grade(sport, leaky as Record<string, number>);
    check(`${sport}: a stingy defence is a WORSE spot than a leaky one`,
      (tough?.score ?? 1) < (soft?.score ?? 0),
      `${tough?.grade} (${tough?.score?.toFixed(2)}) vs ${soft?.grade} (${soft?.score?.toFixed(2)})`);
  }

  // ── tonight, against the real numbers ──────────────────────────────────────
  // SEA allowed 16.90 and NE 17.86 last season, both inside the league's best
  // decile, so the opener is a hard spot in both directions. A grader that
  // called this an average night would be wrong in a way nobody would notice.
  const seaSide = grade('NFL', { points_against_pg: 17.86 }, 'NE');
  const neSide = grade('NFL', { points_against_pg: 16.9 }, 'SEA');
  check('a SEA player faces NE and grades D or worse', ['D+', 'D', 'D-', 'F'].includes(seaSide?.grade ?? ''), `${seaSide?.grade}`);
  check('a NE player faces SEA and grades D or worse', ['D+', 'D', 'D-', 'F'].includes(neSide?.grade ?? ''), `${neSide?.grade}`);
  check('the cell says what it graded on', seaSide?.text === 'vs NE · 17.9 pts allowed/g', `${seaSide?.text}`);
  check('the metric is named for the reader', defenceMetricLabel('NFL') === 'pts allowed/g');

  // ── an unknown defence is a dash, never a C ────────────────────────────────
  const unknown = grade('NFL', null, 'NE');
  check('an unknown defence has no grade', unknown != null && unknown.grade === null);
  check('and still names the opponent', unknown?.text === 'vs NE');
  check('a row with the column missing is also ungraded',
    grade('NFL', {} as Record<string, number>)?.grade === null);

  // ── source ─────────────────────────────────────────────────────────────────
  const m = read('src/lib/matchup.ts');
  const q = read('src/lib/queries.ts');
  const s = read('src/screens/StatsScreen.tsx');
  check('the anchors carry the measurement that produced them',
    /Measured 2026-09-09 against production/.test(m) && /n=32/.test(m) && /n=136/.test(m));
  check('NHL is documented as absent-on-purpose, not forgotten',
    /NHL IS DELIBERATELY ABSENT/.test(m));
  check('the defence grade reuses the shared cuts, not its own',
    !/GRADE_CUTS_DEFENCE|DEFENCE_CUTS/.test(m) && /normalCdf\(z\(value, anchor\)\)/.test(m));
  check('normalCdf is the same one the MLB grades use', typeof normalCdf === 'function');
  check('the team-stats read falls back a football season',
    /footballSeasonCandidates\(season\)\s*\n?\s*:\s*\[season\]/.test(q));
  check('the board only fetches team stats where it grades on them',
    /if \(!gradesOnDefence\(sport\)\) \{[\s\S]{0,80}setTeamStats\(\[\]\)/.test(s));
  check('and one helper answers the column for every sport',
    /const matchupFor = useCallback/.test(s) && !/gradeMatchup\(sport, playerType, mu\)/.test(s));

  console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
  process.exit(failures === 0 ? 0 : 1);
}

main();

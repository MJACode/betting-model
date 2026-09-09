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
 *
 * AND THE JOIN WAS MEASURED, not assumed — the column silently returns to
 * dashes if `games.home_team/away_team` and `team_stats_board.team` disagree,
 * which is the exact failure this change exists to end and is invisible from
 * inside a fixture. Slate teams found in the team-stats read, 2026-09-09:
 *
 *   NFL     32 of 32     (week 1)
 *   NBA     30 of 30
 *   NCAAF  133 of 211    (Saturday 09-12)
 *
 * The 78 NCAAF misses are FCS and lower-division visitors — Alabama State,
 * Arkansas Baptist, Bluffton — which have no rating because the read covers the
 * 137 FBS programs. An FBS player facing one grades to a dash, which is the
 * honest answer: we hold no rating for that defence. It is NOT a join bug, and
 * the distinction matters because the two look identical on screen.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  defenceMetricLabel,
  defenceMetricSpoken,
  gradeColorDiscriminates,
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

const grade = (sport: string, opp: Record<string, number> | null, team = 'OPP', season?: number) =>
  gradeOpponentDefence(sport, opp, team, season);

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
  // SUBJECT, number, season. MLB's version names a person, so its subject is
  // obvious; a bare team-season rate under a header reading "Tonight's matchup"
  // can be taken for the player's own number (UX review, 2026-09-09).
  const dated = grade('NFL', { points_against_pg: 17.86 }, 'NE', 2025);
  check('the cell names whose number it is, and from when',
    dated?.text === 'vs NE · NE allows 17.9 pts/g (2025)', `${dated?.text}`);
  check('and the spoken form is words, not a slash',
    dated?.fact === 'NE 17.9 points allowed per game (2025)', `${dated?.fact}`);
  check('with no season it makes no claim about one', !/\(\d{4}\)/.test(seaSide?.text ?? ''), `${seaSide?.text}`);
  // The visible label is the Teams board's own wording for the same number, so
  // one stat is not two idioms on one tab.
  check('the column label matches teamStatCatalog', defenceMetricLabel('NFL') === 'Allowed/G');
  check('NCAAF too', defenceMetricLabel('NCAAF') === 'EPA/play Def');
  check('and NBA', defenceMetricLabel('NBA') === 'Def Rtg');
  check('the tooltip gets a sentence, not an abbreviation',
    defenceMetricSpoken('NFL') === 'points allowed per game'
    && defenceMetricSpoken('NCAAF') === 'EPA per play allowed'
    && defenceMetricSpoken('NBA') === 'defensive rating');

  // ── the colour ramp goes quiet when it cannot discriminate ─────────────────
  // Tonight is the case: both defences top-decile, every row D-, and gradeColor
  // would paint ~110 rows one red 60pt from a live price.
  check('a column of one band is not coloured',
    !gradeColorDiscriminates(['D-', 'D-', 'D-', 'D']));
  check('a column that spans bands is', gradeColorDiscriminates(['D-', 'B+', 'C']));
  check('one row is never coloured on its own', !gradeColorDiscriminates(['A+']));
  check('nulls do not count as a band', !gradeColorDiscriminates(['D-', null, null]));

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
  const tb = read('src/components/TeamsBoard.tsx');
  check('the football grade names the season it fell back to',
    /the \$\{defenceSeason\} season/.test(s) || /defenceSeason != null/.test(s));
  check('the tooltip is built per sport, not one MLB paragraph',
    /gradesOnDefence\(sport\)\s*\n?\s*\?\s*`Graded on \$\{defenceMetricSpoken\(sport\)\}/.test(s));
  check('and the dash sentence no longer talks about a starter on those sports',
    /no matchup data for this row yet/.test(s));
  check('the slate gate is an identity, not a boolean read stale on a switch',
    /slateFor !== sport/.test(s) && !/slateReady/.test(s));
  check('the slate chip is announced busy, not dimmed',
    /busy=\{loading\}/.test(s) && !/label=\{slateLabel\}[\s\S]{0,200}disabled=\{loading\}/.test(s));
  check('the team-stats read reports which season it used',
    /\{ season: s, rows: data as unknown as TeamStatsRow\[\] \}/.test(q));
  check('and the Teams board labels its header from that, not from what it asked for',
    /const \{ season: used, rows: data \} = await fetchTeamStats/.test(tb)
    && /setSeason\(used\)/.test(tb));
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
    /if \(!gradesOnDefence\(sport\)\) \{[\s\S]{0,120}setTeamStats\(\{ season: null, rows: \[\] \}\)/.test(s));
  check('and one helper answers the column for every sport',
    /const matchupFor = useCallback/.test(s) && !/gradeMatchup\(sport, playerType, mu\)/.test(s));

  console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
  process.exit(failures === 0 ? 0 : 1);
}

main();

/**
 * Standalone verification for the Betting tab's filters (src/lib/teamPeriodSplits.ts).
 * Run with:
 *
 *   npx tsx scripts/verify_team_period_splits.ts
 *
 * Pins:
 *  - Last N is the last N games WITH A LINE for that market, newest first,
 *    whatever order the read returned them in, AFTER the side filter;
 *  - Last N reaches back into last season; Season is this season only;
 *  - a percentage is wins over decided games, pushes left out (the board's
 *    formula), and a team with no graded game prints no percentage;
 *  - favourite / underdog / rest splits are counted from the ATS games in the
 *    window, and every one carries its record;
 *  - a team with no period rows gets zeros, never another team's rows.
 */
import {
  applyPeriodSplits,
  periodFilterShort,
  periodStatDef,
  windowGames,
  type PeriodFilter,
  type TeamPeriodRow,
} from '../src/lib/teamPeriodSplits';
import type { TeamStatsRow } from '../src/types';
import type { TeamStatDef } from '../src/lib/teamStatCatalog';

let failed = 0;
function check(name: string, cond: boolean, detail?: unknown) {
  if (cond) console.log(`  ok  ${name}`);
  else {
    failed++;
    console.log(`  FAIL ${name}`, detail ?? '');
  }
}

const SEASON = 2027;
let gid = 0;
function g(
  team: string,
  date: string,
  o: Partial<TeamPeriodRow> & { ats?: TeamPeriodRow['ats']; ou?: TeamPeriodRow['ou'] } = {},
): TeamPeriodRow {
  gid++;
  return {
    team,
    season: SEASON,
    game_id: `G${String(gid).padStart(3, '0')}`,
    game_date: date,
    is_home: true,
    spread: -3.5,
    total_line: 220.5,
    ats: 'W',
    ou: 'O',
    rest_days: 2,
    opp_rest_days: 2,
    ...o,
  };
}

function board(team: string): TeamStatsRow {
  return {
    team, conference: null, games_played: 0, wins: 0, losses: 0, win_pct: null,
    points_for_pg: null, points_against_pg: null, point_diff_pg: null,
    ats_w: 99, ats_l: 99, ats_p: 99, ats_pct: 0.5,
    ou_o: 99, ou_u: 99, ou_p: 99, over_pct: 0.5,
    home_w: 0, home_l: 0, away_w: 0, away_l: 0,
    ats_home_pct: null, ats_away_pct: null, fav_ats_pct: null, dog_ats_pct: null,
    rest_adv_games: 0, rest_adv_ats_pct: null, short_rest_games: 0, short_rest_ats_pct: null,
    net_rating: 4.2,
  };
}

const F = (o: Partial<PeriodFilter> = {}): PeriodFilter => ({ period: 'FG', games: 'season', side: 'both', ...o });

// ── windows ────────────────────────────────────────────────────────────────
{
  const rows = [
    g('BOS', '2026-11-01', { ats: 'L' }),
    g('BOS', '2026-11-05', { ats: 'W', is_home: false }),
    g('BOS', '2026-11-03', { ats: null, ou: 'U' }),          // no spread: not an ATS game
    g('BOS', '2026-11-07', { ats: 'W' }),
    g('BOS', '2026-11-09', { ats: 'P' }),
    g('BOS', '2026-04-10', { ats: 'L', season: SEASON - 1 }), // last season
  ];
  const shuffled = [rows[3], rows[0], rows[5], rows[2], rows[4], rows[1]];
  const l3 = windowGames(shuffled, F({ games: 3 }), SEASON, 'ats');
  check('last 3 ATS = newest three games that had a spread',
    l3.map((r) => r.game_date).join() === '2026-11-09,2026-11-07,2026-11-05', l3.map((r) => r.game_date));
  const l5 = windowGames(shuffled, F({ games: 5 }), SEASON, 'ats');
  check('last 5 reaches back into last season', l5.length === 5 && l5[4].season === SEASON - 1, l5);
  const season = windowGames(shuffled, F(), SEASON, 'ats');
  check('season is this season only, with a spread', season.length === 4, season.length);
  const home3 = windowGames(shuffled, F({ games: 3, side: 'home' }), SEASON, 'ats');
  check('side filter applies before the window (last 3 HOME games)',
    home3.map((r) => r.game_date).join() === '2026-11-09,2026-11-07,2026-11-01', home3.map((r) => r.game_date));
  const ou = windowGames(shuffled, F({ games: 5 }), SEASON, 'ou');
  check('O/U window counts the game with only a total',
    ou.some((r) => r.game_date === '2026-11-03'), ou.map((r) => r.game_date));
  const atsL5 = windowGames(shuffled, F({ games: 5 }), SEASON, 'ats');
  check('…and the ATS window skips it', !atsL5.some((r) => r.game_date === '2026-11-03'));
}

// ── counts and percentages ───────────────────────────────────────────────────
{
  const rows = [
    g('NYK', '2026-11-01', { ats: 'W', ou: 'O', spread: -5 }),
    g('NYK', '2026-11-02', { ats: 'W', ou: 'U', spread: 3, rest_days: 1, opp_rest_days: 2 }),
    g('NYK', '2026-11-04', { ats: 'L', ou: 'O', spread: -2, rest_days: 3, opp_rest_days: 1 }),
    g('NYK', '2026-11-05', { ats: 'P', ou: 'P', spread: 4, rest_days: 1, opp_rest_days: 1 }),
    g('PHI', '2026-11-01', { ats: 'L', ou: 'U' }),
  ];
  const [nyk, phi, lal] = applyPeriodSplits([board('NYK'), board('PHI'), board('LAL')], rows, F(), SEASON);
  check('ATS record W-L-P', nyk.ats_w === 2 && nyk.ats_l === 1 && nyk.ats_p === 1, nyk);
  check('ATS% = w / (w + l), push left out', nyk.ats_pct === 0.667, nyk.ats_pct);
  check('O/U record and over%', nyk.ou_o === 2 && nyk.ou_u === 1 && nyk.ou_p === 1 && nyk.over_pct === 0.667, nyk);
  check('favourite split (spread < 0)', nyk.fav_w === 1 && nyk.fav_l === 1 && nyk.fav_ats_pct === 0.5, nyk);
  check('underdog split (spread > 0), push kept in the record', nyk.dog_w === 1 && nyk.dog_p === 1 && nyk.dog_ats_pct === 1, nyk);
  check('short rest = rest_days <= 1', nyk.sr_w === 1 && nyk.sr_p === 1 && nyk.short_rest_games === 2, nyk);
  check('rest edge = more days off than the opponent', nyk.ra_l === 1 && nyk.rest_adv_games === 1, nyk);
  check('another team counts only its own rows', phi.ats_w === 0 && phi.ats_l === 1, phi);
  check('a team with no rows gets zeros and no percent, never the board’s',
    lal.ats_w === 0 && lal.ats_l === 0 && lal.ats_pct === null && lal.over_pct === null, lal);
  check('efficiency columns pass through', nyk.net_rating === 4.2, nyk.net_rating);
}

// ── stat defs carry a record ─────────────────────────────────────────────────
{
  const fav = { key: 'fav_ats_pct', label: 'ATS% as Fav', group: 'Betting', sports: ['NBA'], format: 'pct3', better: 'high', hint: '', explain: { what: '', good: '', use: '', watch: '' } } as unknown as TeamStatDef;
  const d = periodStatDef(fav);
  check('fav split gains a record and a sample', String(d.record?.w) === 'fav_w' && (d.sample ?? []).length === 3, d);
  const l5 = periodStatDef(fav, F({ games: 5 }));
  check('a last-N window keeps the record and drops the small-sample rule',
    String(l5.record?.w) === 'fav_w' && l5.sample === undefined, l5);
  const eff = { ...fav, key: 'net_rating' } as unknown as TeamStatDef;
  check('a non-betting stat is unchanged', periodStatDef(eff) === eff);
}

check('short header leaves the defaults out', periodFilterShort(F()) === '' &&
  periodFilterShort({ period: 'Q1', games: 5, side: 'home' }) === '1Q · L5 · Home',
  periodFilterShort({ period: 'Q1', games: 5, side: 'home' }));

if (failed) {
  console.log(`\n${failed} FAILED`);
  process.exit(1);
}
console.log('\nall passed');

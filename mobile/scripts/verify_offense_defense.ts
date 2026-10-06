/**
 * Matchup offense-vs-defense: real box averages, and points-added /
 * successful-plays rows hidden while the column is empty.
 *
 *   npx tsx scripts/verify_offense_defense.ts
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { aggregateBox, boxBefore, buildMatchup, playCellSpeech, playRowsAvailable, rankIn, type OffenseBoxLine } from '../src/lib/offenseDefense';
import type { TeamStatsRow } from '../src/types';

const read = (p: string) => readFileSync(join(import.meta.dirname, '..', p), 'utf-8');

let fail = 0;
function check(name: string, cond: boolean, extra?: unknown) {
  if (!cond) {
    fail++;
    console.error(`FAIL: ${name}`, extra ?? '');
  }
}
function eq(name: string, got: unknown, want: unknown) {
  check(`${name} (got ${JSON.stringify(got)}, want ${JSON.stringify(want)})`, got === want);
}

function box(over: Partial<OffenseBoxLine> & { game_id: string; team: string; opponent: string }): OffenseBoxLine {
  return {
    plays: null,
    pass_yards: null,
    rush_yards: null,
    points_for: null,
    points_against: null,
    ...over,
  };
}

function board(over: Partial<TeamStatsRow> & { team: string }): TeamStatsRow {
  return {
    conference: null,
    games_played: 4,
    wins: 2, losses: 2, win_pct: 0.5,
    points_for_pg: 21, points_against_pg: 18, point_diff_pg: 3,
    ats_w: 0, ats_l: 0, ats_p: 0, ats_pct: null,
    ou_o: 0, ou_u: 0, ou_p: 0, over_pct: null,
    home_w: 0, home_l: 0, away_w: 0, away_l: 0,
    ats_home_pct: null, ats_away_pct: null,
    fav_ats_pct: null, dog_ats_pct: null,
    rest_adv_games: 0, rest_adv_ats_pct: null,
    short_rest_games: 0, short_rest_ats_pct: null,
    ...over,
  } as TeamStatsRow;
}

// A null box is not a zero. A's unplayed game must not become 0.00 points
// or 0 yards, and must not count in the average.
{
  const rates = aggregateBox([
    box({ game_id: 'g0', team: 'A', opponent: 'B' }),
    box({ game_id: 'g0', team: 'B', opponent: 'A' }),
    box({
      game_id: 'g1', team: 'A', opponent: 'B',
      plays: 60, pass_yards: 200, rush_yards: 100, points_for: 24, points_against: 17,
    }),
    box({
      game_id: 'g1', team: 'B', opponent: 'A',
      plays: 55, pass_yards: 180, rush_yards: 90, points_for: 17, points_against: 24,
    }),
    box({
      game_id: 'g2', team: 'A', opponent: 'C',
      plays: 40, pass_yards: 100, rush_yards: 60, points_for: 14, points_against: 21,
    }),
    box({
      game_id: 'g2', team: 'C', opponent: 'A',
      plays: 50, pass_yards: 150, rush_yards: 70, points_for: 21, points_against: 14,
    }),
  ]);
  const a = rates.get('A')!;
  eq('A points/game averages only scored games', a.pointsFor, 19);
  eq('A points allowed averages only scored games', a.pointsAgainst, 19);
  eq('A yards/play skips the null game', a.yardsPerPlay, (300 + 160) / (60 + 40));
  eq('A pass yards/game skips the null game', a.passYds, 150);
  eq('unplayed opponent is not stored as zero points', rates.get('B')!.pointsFor, 17);
  // C's yards allowed come from A's offense in g2, not from a zero-filled g0.
  eq('yards allowed use the opponent box, not a zero', rates.get('C')!.yardsPerPlayAllowed, 160 / 40);
}

// A missing opponent does not invent defensive yards.
{
  const rates = aggregateBox([
    box({
      game_id: 'solo', team: 'A', opponent: 'B',
      plays: 10, pass_yards: 40, rush_yards: 10, points_for: 7, points_against: null,
    }),
  ]);
  eq('no opponent row → yards allowed stay null', rates.get('A')!.yardsPerPlayAllowed, null);
  eq('null points against stay null', rates.get('A')!.pointsAgainst, null);
  eq('own yards still count', rates.get('A')!.yardsPerPlay, 5);
}

// Defense rank is lowest-first. 1st allows the least.
{
  const values = new Map<string, number | null>([
    ['LEAK', 28],
    ['STINGY', 14],
    ['MID', 21],
    ['NONE', null],
  ]);
  eq('stingy defense ranks 1st', rankIn(values, 'STINGY', false), 1);
  eq('leaky defense ranks last among those with a number', rankIn(values, 'LEAK', false), 3);
  eq('a null is unranked', rankIn(values, 'NONE', false), null);
  eq('offense ranks highest-first', rankIn(values, 'LEAK', true), 1);
}

eq(
  'matchup VoiceOver, defense',
  playCellSpeech('JAX', 'defense', 'points-added', -0.08, 2),
  'JAX defense, points added per play allowed, minus 0.08, ranks 2nd',
);
eq(
  'matchup VoiceOver, offense',
  playCellSpeech('PHI', 'offense', 'points-added', 0.21, 1),
  'PHI offense, points added per play, 0.21, ranks 1st',
);
eq(
  'missing points-added is not a zero',
  playCellSpeech('JAX', 'defense', 'points-added', null, null),
  'JAX defense, points added per play allowed, not available',
);

// NFL: counting rows from the box, play rows hidden while the board is empty.
{
  const nflBoard = [board({ team: 'JAX' }), board({ team: 'PHI', points_for_pg: 22, points_against_pg: 18 })];
  eq('NFL play rows hidden', playRowsAvailable(nflBoard).pointsAdded, false);
  eq('NFL success rows hidden', playRowsAvailable(nflBoard).success, false);
  const model = buildMatchup({
    season: 2026,
    away: 'PHI',
    home: 'JAX',
    ourTeam: 'JAX',
    box: [
      box({
        game_id: 'g', team: 'JAX', opponent: 'PHI',
        plays: 60, pass_yards: 210, rush_yards: 90, points_for: 20, points_against: 17,
      }),
      box({
        game_id: 'g', team: 'PHI', opponent: 'JAX',
        plays: 58, pass_yards: 240, rush_yards: 80, points_for: 17, points_against: 20,
      }),
    ],
    board: nflBoard,
  });
  eq('picked side leads', model.sections[0].offenseTeam, 'JAX');
  eq('each side names its own games, not the league total', model.sections[0].offenseGames, 1);
  eq('the other side names its own games', model.sections[0].defenseGames, 1);
  eq('four counting rows', model.sections[0].rows.length, 4);
  const pass = model.sections[0].rows.find((r) => r.key === 'pass')!;
  check('pass VoiceOver says passing yards per game',
    pass.offSpeech.startsWith('Passing yards per game:'), pass.offSpeech);
  eq('the visible pass label stays short', pass.label, 'Pass yds / game');
  const rush = model.sections[0].rows.find((r) => r.key === 'rush')!;
  check('rush VoiceOver says rushing yards per game',
    rush.defSpeech.startsWith('Rushing yards per game:'), rush.defSpeech);
  check('no points-added row on an empty NFL board',
    !model.sections[0].rows.some((r) => r.key === 'points-added' || r.key === 'success'));
  const pts = model.sections[0].rows[0];
  eq('JAX points print from the box', pts.displayOff, '20.0');
  eq('PHI points allowed print from the box', pts.displayDef, '20.0');
  const missing = buildMatchup({
    season: 2026, away: 'PHI', home: 'NYG', ourTeam: null,
    box: [
      box({ game_id: 'g', team: 'PHI', opponent: 'JAX', plays: 10, pass_yards: 40, rush_yards: 10, points_for: 10, points_against: 7 }),
      box({ game_id: 'g', team: 'JAX', opponent: 'PHI', plays: 10, pass_yards: 30, rush_yards: 10, points_for: 7, points_against: 10 }),
    ],
    board: nflBoard,
  });
  eq('a team with no box is a dash, not zero', missing.sections[0].rows[0].displayDef, '—');
  eq('and it is unranked', missing.sections[0].rows[0].defRank, null);
  eq('a side with no completed game has no game count', missing.sections[0].defenseGames, null);
}

// NCAAF: no box table, so points come from the board and play rows show
// because the values exist. Yards rows stay off — we do not hold yards allowed.
{
  const rows = [
    board({ team: 'ALA', epa_off: 0.21, epa_def: -0.08, success_off: 0.467, success_def: 0.401, points_for_pg: 35.2, points_against_pg: 18.1 }),
    board({ team: 'AUB', epa_off: 0.05, epa_def: 0.12, success_off: 0.41, success_def: 0.45, points_for_pg: 24.0, points_against_pg: 27.4 }),
  ];
  eq('NCAAF play rows show', playRowsAvailable(rows).pointsAdded, true);
  const model = buildMatchup({
    season: 2026, away: 'AUB', home: 'ALA', ourTeam: 'ALA', box: [], board: rows,
  });
  const keys = model.sections[0].rows.map((r) => r.key);
  eq('NCAAF rows are points plus the two play metrics', keys.join(','), 'pts,points-added,success');
  const ncaafPts = model.sections[0].rows.find((r) => r.key === 'pts')!;
  check('NCAAF points VoiceOver uses the spoken name',
    ncaafPts.offSpeech.startsWith('Points per game:'), ncaafPts.offSpeech);
  eq('NCAAF points label stays short', ncaafPts.label, 'Points / game');
  eq('NCAAF game count comes from that team', model.sections[0].offenseGames, 4);
  const added = model.sections[0].rows.find((r) => r.key === 'points-added')!;
  eq('NCAAF points-added prints unsigned', added.displayOff, '0.21');
  const alaDef = model.sections[1].rows.find((r) => r.key === 'points-added')!;
  eq('NCAAF defense prints a true minus', alaDef.displayDef, '\u22120.08');
  eq('defense rank is 1st when it allows the least', alaDef.defRank, 1);
  const success = model.sections[0].rows.find((r) => r.key === 'success')!;
  eq('successful plays print as a percent', success.displayOff, '46.7%');
}

// A settled pick must not absorb games played after it. 2025's box includes
// 13 playoff games; those, and the pick's own game, stay out of the average
// and out of that side's game count.
{
  const week1 = [
    box({
      game_id: 'w1', game_date: '2025-09-07', team: 'KC', opponent: 'BAL',
      plays: 60, pass_yards: 200, rush_yards: 100, points_for: 20, points_against: 17,
    }),
    box({
      game_id: 'w1', game_date: '2025-09-07', team: 'BAL', opponent: 'KC',
      plays: 55, pass_yards: 180, rush_yards: 80, points_for: 17, points_against: 20,
    }),
  ];
  const ownGame = [
    box({
      game_id: 'w2', game_date: '2025-09-14', team: 'KC', opponent: 'PHI',
      plays: 60, pass_yards: 300, rush_yards: 100, points_for: 40, points_against: 10,
    }),
    box({
      game_id: 'w2', game_date: '2025-09-14', team: 'PHI', opponent: 'KC',
      plays: 60, pass_yards: 100, rush_yards: 40, points_for: 10, points_against: 40,
    }),
  ];
  const playoff = [
    box({
      game_id: 'sb', game_date: '2026-02-08', team: 'KC', opponent: 'PHI',
      plays: 70, pass_yards: 400, rush_yards: 100, points_for: 35, points_against: 28,
    }),
    box({
      game_id: 'sb', game_date: '2026-02-08', team: 'PHI', opponent: 'KC',
      plays: 65, pass_yards: 250, rush_yards: 90, points_for: 28, points_against: 35,
    }),
  ];
  const all = [...week1, ...ownGame, ...playoff];
  eq('the cap drops the pick date and everything after it', boxBefore(all, '2025-09-14').length, 2);
  eq('a row with no date cannot be shown to be earlier', boxBefore([
    box({ game_id: 'x', team: 'KC', opponent: 'BAL', points_for: 3 }),
  ], '2025-09-14').length, 0);
  const model = buildMatchup({
    season: 2025, away: 'BAL', home: 'KC', ourTeam: 'KC', beforeDate: '2025-09-14',
    box: all,
    board: [board({ team: 'KC' }), board({ team: 'BAL' })],
  });
  eq('KC points are week 1 only', model.sections[0].rows[0].displayOff, '20.0');
  eq('KC game count is the games before the pick', model.sections[0].offenseGames, 1);
  eq('BAL game count matches its own earlier games', model.sections[0].defenseGames, 1);
  const q = read('src/lib/queries.ts');
  check('the season box read stops before the pick date',
    /export async function fetchNflSeasonBox\(season: number, beforeDate: string\)[\s\S]{0,500}\.lt\('game_date', beforeDate\)/.test(q));
  const card = read('src/components/OffenseDefenseCard.tsx');
  check('the card passes the pick date into that read',
    /fetchNflSeasonBox\(season, beforeDate\)/.test(card));
  check('the game count joins the number to the word with a non-breaking space',
    /\$\{games\}\\u00A0\$\{games === 1 \? 'game' : 'games'\}/.test(card));
  const screen = read('src/screens/PickDetailScreen.tsx');
  check('the date is the pick’s game_date',
    /beforeDate=\{pick\.game_date\}/.test(screen));
}

console.log(fail === 0 ? '\nALL PASS' : `\n${fail} FAILED`);
process.exit(fail === 0 ? 0 : 1);

/**
 * The GAMES filter — one selection, both tabs.
 *
 * Run with:  npx tsx scripts/verify_game_filter.ts
 *
 * Matt, 2026-09-09, from a competitor's filter sheet: *"incorporate these
 * filters for games on how to show the match ups and show bets for those games.
 * This should be on picks and stats filter."*
 *
 * The two tabs had two different ways to say the same thing — Stats had a
 * whole-slate "Playing today" chip, Picks had no game cut at all — so "the two
 * teams playing tonight and every bet on them" took a search box on one screen
 * and was impossible on the other.
 *
 * Three things this pins, each of which is a way the filter can be quietly
 * wrong rather than visibly broken:
 *
 *   1. EMPTY MEANS EVERYTHING. A filter that starts by hiding the board is a
 *      broken screen, and so is one that cannot be cleared back.
 *   2. A SELECTION OUTLIVES ITS SLATE. A game id names one fixture on one date;
 *      left un-pruned it filters tonight's board to nothing while every control
 *      still says a game is picked, and nothing on screen says why.
 *   3. THE TWO TABS AGREE. The Stats board filters on TEAM (its rows carry no
 *      game), Picks filters on game_id. They must select the same games.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  gameFilterSummary,
  isGameSelected,
  pruneSelection,
  selectableGames,
  selectedTeams,
} from '../src/lib/gameFilter';
import type { GameRow } from '../src/types';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const g = (over: Partial<GameRow>): GameRow =>
  ({
    game_id: 'g',
    sport: 'NFL',
    season: 2026,
    game_date: '2026-09-13',
    home_team: 'SEA',
    away_team: 'NE',
    commence_time: '2026-09-13T17:00:00+00:00',
    ...over,
  }) as GameRow;

const SLATE: GameRow[] = [
  g({ game_id: 'NFL_2026_01_NE_SEA', away_team: 'NE', home_team: 'SEA', commence_time: '2026-09-13T20:25:00+00:00' }),
  g({ game_id: 'NFL_2026_01_GB_MIN', away_team: 'GB', home_team: 'MIN', commence_time: '2026-09-13T17:00:00+00:00' }),
  g({ game_id: 'NFL_2026_01_DAL_NYG', away_team: 'DAL', home_team: 'NYG', commence_time: '2026-09-14T00:20:00+00:00' }),
  // Another sport's game, and a game already played — neither is selectable.
  g({ game_id: 'MLB_x', sport: 'MLB', away_team: 'BOS', home_team: 'NYY' }),
  g({ game_id: 'NFL_yesterday', game_date: '2026-09-01', commence_time: '2026-09-01T17:00:00+00:00' }),
];

function main() {
  const today = '2026-09-13';
  const games = selectableGames(SLATE, 'NFL', today);

  // ── what is selectable ─────────────────────────────────────────────────────
  check('only this sport, and only games not already played', games.length === 3, `${games.length}`);
  check('no other sport leaks in', !games.some((x) => x.gameId.startsWith('MLB')));
  // Ordered by KICKOFF, so a slate reads down the page the way the day runs.
  check('ordered by kickoff', games.map((x) => x.gameId).join(',') ===
    'NFL_2026_01_GB_MIN,NFL_2026_01_NE_SEA,NFL_2026_01_DAL_NYG', games.map((x) => x.gameId).join(','));
  check('the row is the fixture, away side first', games[1]!.matchup === 'NE @ SEA', games[1]!.matchup);
  check('and it carries both teams', games[1]!.teams.join(',') === 'NE,SEA');

  // UFC's games row stores two FIGHTERS in home/away — they are slots, not
  // venues — so "A @ B" would render one bout as two different fixtures.
  const ufc = selectableGames(
    [g({ sport: 'UFC', game_id: 'UFC_1', home_team: 'Jon Jones', away_team: 'Tom Aspinall' })],
    'UFC',
    today,
  );
  check('UFC offers no fixtures to pick', ufc.length === 0);

  // ── empty means everything ─────────────────────────────────────────────────
  const none = new Set<string>();
  check('an unset filter shows every pick', isGameSelected('anything', none));
  check('even one with no game at all', isGameSelected(null, none));
  check('the summary says so', gameFilterSummary(games, none) === 'All games');
  check('and nothing is narrowed for the server', selectedTeams(games, none) === null);

  const one = new Set(['NFL_2026_01_NE_SEA']);
  check('a picked game keeps its own picks', isGameSelected('NFL_2026_01_NE_SEA', one));
  check('and drops every other', !isGameSelected('NFL_2026_01_GB_MIN', one));
  check('a pick with no game is dropped once a game is picked', !isGameSelected(null, one));
  check('the summary names the one game', gameFilterSummary(games, one) === 'NE @ SEA', gameFilterSummary(games, one));
  check('two games are counted, not listed',
    gameFilterSummary(games, new Set(['NFL_2026_01_NE_SEA', 'NFL_2026_01_GB_MIN'])) === '2 games');

  // ── the two tabs agree ─────────────────────────────────────────────────────
  // Picks filters on game_id; the Stats leaderboard has only a team on each
  // row, so the same selection has to become teams. Same games either way.
  const teams = selectedTeams(games, one)!;
  check('a picked game becomes exactly its two teams', teams.slice().sort().join(',') === 'NE,SEA', teams.join(','));
  const twoGames = new Set(['NFL_2026_01_NE_SEA', 'NFL_2026_01_GB_MIN']);
  check('two games become four teams',
    selectedTeams(games, twoGames)!.slice().sort().join(',') === 'GB,MIN,NE,SEA');

  // ── a selection outlives its slate ─────────────────────────────────────────
  // The failure this prevents is silent: a stale id filters the board to
  // nothing while the sheet still shows a game ticked.
  const stale = new Set(['NFL_2026_01_NE_SEA', 'NFL_gone_yesterday']);
  const pruned = pruneSelection(stale, games);
  check('an id no longer on the slate is dropped', pruned.size === 1 && pruned.has('NFL_2026_01_NE_SEA'));
  check('a wholly stale selection prunes to "all games", not to nothing',
    pruneSelection(new Set(['NFL_gone', 'NFL_also_gone']), games).size === 0);
  check('an unchanged selection keeps its identity, so it cannot loop',
    pruneSelection(one, games) === one);
  check('and an empty one is returned untouched', pruneSelection(none, games) === none);

  // ── source ─────────────────────────────────────────────────────────────────
  const stats = read('src/screens/StatsScreen.tsx');
  const picks = read('src/screens/PicksHomeScreen.tsx');
  const pf = read('src/components/filters/PickFilters.tsx');
  const hook = read('src/hooks/useGameSelection.ts');

  check('both tabs read the SAME selection', /useGameSelection\(sport\)/.test(stats) && /useGameSelection\(sport\)/.test(picks));
  check('and both render the same section',
    /<GameFilterSection/.test(stats) && /<GameFilterSection/.test(pf));
  check('Stats narrows its rows by the picked teams', /gameTeams \|\| \(!!r\.team && gameTeams\.includes/.test(stats));
  check('Picks narrows its bets by the picked game', /isGameSelected\(d\.pick\.game_id, gamePicker\.selected\)/.test(picks));
  check('a picked game is also the SERVER narrowing, not just a client filter',
    /gameTeams \?\? slateTeams\(sport, slate, tonightActive\)/.test(stats));
  // The CALL, not the import — each file names it twice.
  check('both tabs prune a stale selection',
    (stats + picks).match(/pruneSelection\(gamePicker\.selected, pickableGames\)/g)?.length === 2);

  // The selection is NOT persisted, and that is deliberate: a stored game id
  // filters tonight's board by last night's games, silently.
  check('the selection is never written to storage', !/AsyncStorage/.test(hook));
  check('and a sport switch clears it', /selectionSport !== sport && selected\.size > 0/.test(hook));

  // The grade floor is the other half of the ask.
  check('the board can be cut by matchup grade', /meetsGradeFloor\(matchupFor\(/.test(stats));
  check('and only where the sport can grade one', /showMatchupCol \? \(\s*\n\s*<FilterSection\s*\n\s*title="Matchup grade"/.test(stats));

  console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
  process.exit(failures === 0 ? 0 : 1);
}

main();

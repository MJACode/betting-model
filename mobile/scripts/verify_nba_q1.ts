/**
 * Standalone verification for the NBA first-quarter card (src/lib/nbaQ1.ts).
 * Run with:
 *
 *   npx tsx scripts/verify_nba_q1.ts
 *
 * Pins:
 *  - Last 5 / Last 10 are the last N games AT THE VENUE, newest first,
 *    whatever order the read returned them in;
 *  - they reach back into last season and say how many games did;
 *  - Season is the venue's `v_nba_team_q1_season` row, not a sum of the fetched
 *    games. Once the season is longer than the fetch cap, a Season built from
 *    the cap is wrong, and this script fails;
 *  - ratings are window sums (points over possessions x 100), not a mean of
 *    per-game ratings, and an unrated game counts in the record but not the
 *    ratings;
 *  - a tied quarter is a tie, not a loss.
 */
import {
  formatQ1Record,
  formatSigned1,
  NBA_Q1_FETCH_GAMES,
  NBA_Q1_SEASON_COLUMNS,
  nbaQ1Windows,
  nbaSeasonLabel,
  newestFirst,
  q1PriorSeasonNote,
  q1RowA11yLabel,
  q1RowSub,
  q1ThisSeasonLine,
  summarizeQ1,
  type NbaQ1Game,
  type NbaQ1SeasonRow,
  type NbaQ1Venue,
} from '../src/lib/nbaQ1';

let failed = 0;
function check(name: string, cond: boolean, detail?: unknown) {
  if (cond) console.log(`  ok  ${name}`);
  else {
    failed += 1;
    console.log(`  FAIL ${name}`, detail ?? '');
  }
}

function g(
  date: string,
  season: number,
  isHome: boolean,
  pf: number,
  pa: number,
  possF: number | null = 25,
  possA: number | null = 25,
): NbaQ1Game {
  return {
    game_id: `NBA_${date}_X_${isHome ? 'BOS' : 'Y'}`,
    team: 'BOS',
    season,
    game_date: date,
    opponent: 'NYK',
    is_home: isHome,
    pts_for: pf,
    pts_against: pa,
    poss_for: possF,
    poss_against: possA,
  };
}

// Six games this season (2027) and six last season (2026), shuffled.
const games: NbaQ1Game[] = [
  g('2026-10-27', 2027, true, 30, 25),
  g('2026-04-10', 2026, true, 20, 30),
  g('2026-10-21', 2027, false, 28, 28),
  g('2026-10-25', 2027, false, 22, 31),
  g('2026-04-08', 2026, false, 33, 20),
  g('2026-10-23', 2027, true, 27, 24, null, null),
  g('2026-04-06', 2026, true, 25, 25),
  g('2026-10-26', 2027, true, 31, 29),
  g('2026-04-04', 2026, false, 18, 26),
  g('2026-10-24', 2027, false, 26, 21),
  g('2026-04-02', 2026, true, 29, 27),
  g('2026-03-31', 2026, true, 24, 22),
];

/** The season view's row for one venue: this season only, summed the way the view sums. */
function seasonRow(list: readonly NbaQ1Game[], venue: NbaQ1Venue): NbaQ1SeasonRow {
  const season = newestFirst(list)[0]?.season ?? 0;
  const rows = list.filter((g) => g.season === season && (venue === 'all' || (venue === 'home') === g.is_home));
  let wins = 0;
  let losses = 0;
  let ties = 0;
  let pf = 0;
  let pa = 0;
  let rpf = 0;
  let rpa = 0;
  let possF = 0;
  let possA = 0;
  let rated = 0;
  for (const row of rows) {
    if (row.pts_for > row.pts_against) wins += 1;
    else if (row.pts_for < row.pts_against) losses += 1;
    else ties += 1;
    pf += row.pts_for;
    pa += row.pts_against;
    if (row.poss_for != null && row.poss_against != null) {
      rated += 1;
      rpf += row.pts_for;
      rpa += row.pts_against;
      possF += row.poss_for;
      possA += row.poss_against;
    }
  }
  const round1 = (x: number) => Math.round(x * 10) / 10;
  return {
    season,
    team: 'BOS',
    venue,
    games: rows.length,
    wins,
    losses,
    ties,
    pts_for: pf,
    pts_against: pa,
    rated_games: rated,
    ortg: rated && possF ? round1((100 * rpf) / possF) : null,
    drtg: rated && possA ? round1((100 * rpa) / possA) : null,
    net_rtg: null,
    ortg_rank: 1,
    drtg_rank: 1,
    net_rank: 1,
    teams: 30,
  };
}

console.log('venue and ordering');
{
  // This fixture fits inside the fetch cap, so it cannot see the cap bug.
  const home = nbaQ1Windows(games, 'home', seasonRow(games, 'home'));
  check('current season is the newest game’s', home.season === 2027, home.season);
  const l5 = home.rows[0].summary;
  // Home, newest first: 10-27 W, 10-26 W, 10-23 W, 04-10 L, 04-06 T.
  check('last 5 home record', formatQ1Record(l5) === '3-1-1', formatQ1Record(l5));
  check('last 5 home reaches 2 games back into last season', l5.priorSeasonGames === 2, l5.priorSeasonGames);
  check('season home is this season only', home.rows[2].summary.games === 3, home.rows[2].summary.games);
  const away = nbaQ1Windows(games, 'away', seasonRow(games, 'away'));
  check('away last 10 holds every away game (5)', away.rows[1].summary.games === 5, away.rows[1].summary.games);
  const all = nbaQ1Windows(games, 'all', seasonRow(games, 'all'));
  check('all last 10 is 10 games', all.rows[1].summary.games === 10);
  check('all season is 6 games', all.rows[2].summary.games === 6);
}

console.log('ratings');
{
  const s = summarizeQ1(
    [g('2026-10-27', 2027, true, 30, 20, 20, 25), g('2026-10-26', 2027, true, 20, 30, 30, 25)],
    2027,
  );
  // Window sums: 50 on 50 = 100.0; per-game mean would be (150 + 66.7)/2 = 108.3.
  check('ortg is a window sum, not a mean of game ratings', s.ortg === 100, s.ortg);
  check('drtg is a window sum', s.drtg === 100, s.drtg);
  const u = summarizeQ1([g('2026-10-27', 2027, true, 30, 20), g('2026-10-26', 2027, true, 40, 10, null, null)], 2027);
  check('unrated game counts in the record', u.games === 2 && u.wins === 2);
  check('unrated game counts in points', u.ptsFor === 35, u.ptsFor);
  check('unrated game is left out of ratings', u.ortg === 120 && u.ratedGames === 1, u);
  const none = summarizeQ1([], 2027);
  check('empty window has no numbers', none.ortg === null && none.margin === null && none.games === 0);
}

console.log('formatting');
check('signed margin uses a real minus', formatSigned1(-2.5) === '−2.5', formatSigned1(-2.5));
check('positive margin carries a plus', formatSigned1(1) === '+1.0');
check('season label is the ending year', nbaSeasonLabel(2027) === '2026-27', nbaSeasonLabel(2027));
check('record omits zero ties', formatQ1Record({ wins: 3, losses: 2, ties: 0 }) === '3-2');

console.log('season is the view, not the fetch cap');
{
  // Oldest `extra` games are wins the capped fetch drops. The rest are losses.
  // A Season summed from the fetch is 0-40 (or whatever the cap is). The view
  // still holds the dropped wins.
  const extra = 5;
  const n = NBA_Q1_FETCH_GAMES + extra;
  const full: NbaQ1Game[] = [];
  for (let i = 0; i < n; i++) {
    const date = new Date(Date.UTC(2026, 9, 1 + i)).toISOString().slice(0, 10);
    const dropped = i < extra;
    full.push(g(date, 2027, i % 2 === 0, dropped ? 40 : 20, dropped ? 10 : 30));
  }
  const capped = newestFirst(full).slice(0, NBA_Q1_FETCH_GAMES);
  const row = seasonRow(full, 'all');
  const pf = extra * 40 + NBA_Q1_FETCH_GAMES * 20;
  const pa = extra * 10 + NBA_Q1_FETCH_GAMES * 30;
  check('the view row is the full season', row.games === n && row.wins === extra && row.pts_for === pf && row.pts_against === pa, row);
  const shown = nbaQ1Windows(capped, 'all', row).rows[2].summary;
  const fromCap = summarizeQ1(capped, 2027);
  check('season games are the view, not the fetched cap', shown.games === n && shown.games !== fromCap.games, {
    shown: shown.games,
    cap: fromCap.games,
  });
  check('season record keeps the wins the fetch dropped', formatQ1Record(shown) === `${extra}-${NBA_Q1_FETCH_GAMES}`, formatQ1Record(shown));
  check('season record is not the capped window', formatQ1Record(shown) !== formatQ1Record(fromCap));
  const ptsFor = Math.round((pf / n) * 10) / 10;
  const ptsAgainst = Math.round((pa / n) * 10) / 10;
  check('season points are the full-season averages', shown.ptsFor === ptsFor && shown.ptsAgainst === ptsAgainst, shown);
  check('this-season line uses the full-season averages',
    q1ThisSeasonLine(shown) === `This season: ${ptsFor.toFixed(1)} scored, ${ptsAgainst.toFixed(1)} allowed per first quarter.`,
    q1ThisSeasonLine(shown));
  check('this-season line is not the capped window', q1ThisSeasonLine(shown) !== q1ThisSeasonLine(fromCap));
  check('season rating is the view’s, not a rerating of the cap', shown.ortg === row.ortg && shown.ortg !== fromCap.ortg, {
    shown: shown.ortg,
    view: row.ortg,
    cap: fromCap.ortg,
  });
  const homeRow = seasonRow(full, 'home');
  const home = nbaQ1Windows(capped, 'home', homeRow);
  const homeInCap = capped.filter((row) => row.is_home).length;
  check('home season is the view’s home row, past the home games in the cap',
    home.rows[2].summary.games === homeRow.games
      && home.rows[2].summary.wins === homeRow.wins
      && home.rows[2].summary.games > homeInCap,
    { shown: home.rows[2].summary.games, wins: home.rows[2].summary.wins, cap: homeInCap, view: homeRow.games });
  check('last 5 stays the newest five, not the season row', formatQ1Record(nbaQ1Windows(capped, 'all', row).rows[0].summary) === '0-5');
  const cols = NBA_Q1_SEASON_COLUMNS.split(',');
  check('season read selects the record and the point sums',
    ['games', 'wins', 'losses', 'ties', 'pts_for', 'pts_against', 'rated_games', 'ortg', 'drtg'].every((c) => cols.includes(c)),
    cols);
}

console.log('row text and VoiceOver');
{
  const home = nbaQ1Windows(games, 'home', seasonRow(games, 'home'));
  // Home last 5 holds the 10-23 game, which has no possessions.
  check('subline names the rated count when short', q1RowSub(home.rows[0]) === 'Off/Def from 4', q1RowSub(home.rows[0]));
  check('season subline gives the count', q1RowSub(home.rows[2]) === '3 games · Off/Def from 2', q1RowSub(home.rows[2]));
  const a11y = q1RowA11yLabel(home.rows[0]);
  check('spoken record uses words', a11y.includes('3 wins, 1 loss, 1 tie'), a11y);
  check('spoken label never reads a dash', !a11y.includes('\u2014'), a11y);
  const blank = summarizeQ1([g('2026-10-27', 2027, true, 30, 20, null, null)], 2027);
  const lbl = q1RowA11yLabel({ key: 'l5', label: 'Last 5', summary: blank });
  check('a missing rating is spoken as not available', lbl.includes('offensive rating not available'), lbl);
  const note = q1PriorSeasonNote(home.rows, home.season);
  check('prior-season note covers Last 5 and Last 10',
    note === 'Last 5 includes 2 games from 2025-26. Last 10 includes 4 games from 2025-26.', note);
  check('no note when nothing reaches back',
    q1PriorSeasonNote(nbaQ1Windows(games.filter((x) => x.season === 2027), 'all', seasonRow(games, 'all')).rows, 2027) === null);
  const loading = q1RowA11yLabel({ key: 'season', label: 'Season', summary: summarizeQ1([], 2027), pending: 'loading' });
  check('a season row still loading is not "no games"', loading === 'Season, loading', loading);
  check('a loading season row says so under the label', q1RowSub({ key: 'season', label: 'Season', summary: summarizeQ1([], 2027), pending: 'loading' }) === 'Loading');
  const failedRow = { key: 'season' as const, label: 'Season', summary: summarizeQ1([], 2027), pending: 'error' as const };
  check('a failed season row does not look like no games', q1RowSub(failedRow) === 'Couldn’t load', q1RowSub(failedRow));
  check('a failed season row is spoken as a failure', q1RowA11yLabel(failedRow) === 'Season, couldn’t load');
}

if (failed) {
  console.log(`\n${failed} check(s) failed`);
  process.exit(1);
}
console.log('\nall checks passed');

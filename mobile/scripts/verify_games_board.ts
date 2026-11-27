/**
 * Stats → Games (Matt, 2026-11-27): "a separate view that just shows games
 * for the day on the stats page and you can see ML, spread or over under …
 * like CBS sports. Past games current and future but only current has bet
 * lines."
 *
 * Run with:  npx tsx scripts/verify_games_board.ts
 *
 *  1. The day strip runs three days back to three ahead, today in the middle.
 *  2. Only today carries lines.
 *  3. A game's six buttons: each team's spread and ML, the Over on the away
 *     row and the Under on the home row, each the best of the MEMBER'S books.
 *  4. Each button opens the add-to-betslip sheet on its own bet, with the
 *     team's ML / spread / Over / Under as the tabs.
 *  5. A market none of the member's books prices is no button.
 *  6. The tab is wired: every team sport gets Games, and Stats renders it.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { gameBetCells, gamesCardLabel, gamesDayHasLines, gamesDayStrip, newestSnapshot } from '../src/lib/gamesBoard';
import { gameLineLegFromRows, lineLegKey, lineLegLabel } from '../src/lib/lineLegs';
import { boardSegmentsFor, segmentLabel } from '../src/lib/statSegments';
import { buildTeamLineIndex } from '../src/lib/statsOdds';
import type { GameRow, OddsByBookRow } from '../src/types';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// 1–2. Days.
{
  const strip = gamesDayStrip('2026-11-27');
  check('the strip is seven days, today in the middle',
    strip.length === 7 && strip[0]!.date === '2026-11-24' && strip[3]!.date === '2026-11-27' && strip[6]!.date === '2026-11-30',
    strip.map((d) => d.date).join());
  check('today, yesterday and tomorrow are named', strip[3]!.label === 'Today' && strip[2]!.label === 'Yesterday' && strip[4]!.label === 'Tomorrow',
    strip.map((d) => d.label).join());
  check('only today has lines',
    gamesDayHasLines('2026-11-27', '2026-11-27') && !gamesDayHasLines('2026-11-26', '2026-11-27') && !gamesDayHasLines('2026-11-28', '2026-11-27'));
}

// 3–5. Buttons.
const game = {
  game_id: 'NFL_2026-11-27_KC_BUF',
  game_date: '2026-11-27',
  sport: 'NFL',
  home_team: 'BUF',
  away_team: 'KC',
  commence_time: '2026-11-28T01:20:00Z',
} as unknown as GameRow;
const base = {
  game_id: game.game_id,
  game_date: game.game_date,
  home_link: null, away_link: null, over_link: null, under_link: null,
  snapshot_at: '2026-11-27T15:00:00Z',
};
const row = (bookmaker: string, market: string, extra: Partial<OddsByBookRow>): OddsByBookRow => ({
  ...base,
  bookmaker,
  market,
  home_price: null, away_price: null, over_price: null, under_price: null,
  spread_home: null, total_line: null,
  ...extra,
} as unknown as OddsByBookRow);
const rows: OddsByBookRow[] = [
  row('draftkings', 'h2h', { home_price: -150, away_price: 130 }),
  row('fanduel', 'h2h', { home_price: -145, away_price: 125 }),
  row('betmgm', 'h2h', { home_price: -140, away_price: 135 }), // not the member's book
  row('draftkings', 'spreads', { spread_home: -3, home_price: -110, away_price: -110 }),
  row('fanduel', 'spreads', { spread_home: -3, home_price: -105, away_price: -115 }),
  row('draftkings', 'totals', { total_line: 47.5, over_price: -110, under_price: -112 }),
  row('fanduel', 'totals', { total_line: 47.5, over_price: -108, under_price: -110 }),
];
const books = ['draftkings', 'fanduel'] as const;
const build = (market: 'h2h' | 'spreads' | 'totals', rs = rows) => buildTeamLineIndex(rs, [game], { market, books, gameIds: null });
const idx = { h2h: build('h2h'), spreads: build('spreads'), totals: build('totals') };
const cells = gameBetCells(game, idx, books, 'NFL')!;
{
  check('away ML is the best of the member\'s books, not BetMGM', cells.away.ml?.price === 130 && cells.away.ml.book === 'draftkings', `${cells.away.ml?.price} ${cells.away.ml?.book}`);
  check('home ML is the best of the member\'s books', cells.home.ml?.price === -145 && cells.home.ml.book === 'fanduel', `${cells.home.ml?.price}`);
  check('spreads carry the team\'s own number', cells.away.spread?.line === '+3' && cells.home.spread?.line === '−3', `${cells.away.spread?.line} ${cells.home.spread?.line}`);
  check('home spread is the best price at the number', cells.home.spread?.price === -105 && cells.home.spread.book === 'fanduel');
  check('the Over sits on the away row at its best price', cells.away.total?.line === 'o47.5' && cells.away.total.price === -108 && cells.away.total.book === 'fanduel', `${cells.away.total?.line} ${cells.away.total?.price}`);
  check('the Under sits on the home row at its best price', cells.home.total?.line === 'u47.5' && cells.home.total.price === -110 && cells.home.total.book === 'fanduel', `${cells.home.total?.line} ${cells.home.total?.price}`);
  check('a moneyline button has no number on top', cells.away.ml?.line === null);
}
{
  const under = cells.home.total!;
  check('the Under button opens the sheet on an Under leg', lineLegLabel(under.input.spec) === 'BUF vs KC Under 47.5', lineLegLabel(under.input.spec));
  check('and the sheet\'s tab for it is selected (keys match)', under.choices.some((c) => c.key === under.key) && under.key === lineLegKey(under.input.spec));
  check('the sheet offers the team\'s ML, spread, Over and Under', under.choices.map((c) => c.label).join() === 'ML,−3,Over 47.5,Under 47.5', under.choices.map((c) => c.label).join());
  const leg = gameLineLegFromRows(under.input.spec as Parameters<typeof gameLineLegFromRows>[0], rows, game);
  check('the betslip can price that Under', leg != null && leg.label === 'BUF vs KC Under 47.5');
  const away = cells.away.spread!;
  check('the away spread opens on the away team\'s spread', lineLegLabel(away.input.spec) === 'KC +3.0', lineLegLabel(away.input.spec));
}
{
  const noTotals = rows.filter((r) => r.market !== 'totals');
  const c = gameBetCells(game, { h2h: build('h2h', noTotals), spreads: build('spreads', noTotals), totals: build('totals', noTotals) }, books, 'NFL')!;
  check('no total posted → no Over or Under button', c.away.total === null && c.home.total === null && c.away.ml != null);
  const onlyMgm = gameBetCells(game, {
    h2h: buildTeamLineIndex(rows, [game], { market: 'h2h', books: ['caesars'], gameIds: null }),
    spreads: buildTeamLineIndex(rows, [game], { market: 'spreads', books: ['caesars'], gameIds: null }),
    totals: buildTeamLineIndex(rows, [game], { market: 'totals', books: ['caesars'], gameIds: null }),
  }, ['caesars'], 'NFL')!;
  check('none of the member\'s books → no buttons at all', [onlyMgm.away, onlyMgm.home].every((r) => r.ml == null && r.spread == null && r.total == null));
  check('a game with no teams yet has no cells', gameBetCells({ home_team: null, away_team: 'KC' }, idx, books, 'NFL') === null);
}

// 7. A doubleheader: two games, same two teams, one day. Indexed per game,
// each game's buttons are its own prices and add its own leg (UX review,
// 2026-11-27: a team-keyed index handed game 1 game 2's prices).
{
  const g1 = { ...game, game_id: 'MLB_G1', sport: 'MLB' } as unknown as GameRow;
  const g2 = { ...game, game_id: 'MLB_G2', sport: 'MLB' } as unknown as GameRow;
  const dh: OddsByBookRow[] = [
    { ...row('draftkings', 'h2h', { home_price: -150, away_price: 130 }), game_id: 'MLB_G1' } as OddsByBookRow,
    { ...row('draftkings', 'h2h', { home_price: -200, away_price: 170 }), game_id: 'MLB_G2' } as OddsByBookRow,
  ];
  const per = (g: GameRow) => {
    const only = new Set([g.game_id]);
    const b = (market: 'h2h' | 'spreads' | 'totals') => buildTeamLineIndex(dh, [g], { market, books, gameIds: only });
    return gameBetCells(g, { h2h: b('h2h'), spreads: b('spreads'), totals: b('totals') }, books, 'MLB')!;
  };
  const c1 = per(g1);
  const c2 = per(g2);
  check('doubleheader game 1 shows game 1\'s price', c1.away.ml?.price === 130, `${c1.away.ml?.price}`);
  check('doubleheader game 2 shows game 2\'s price', c2.away.ml?.price === 170, `${c2.away.ml?.price}`);
  check('and each adds its own game\'s leg', c1.away.ml?.input.spec.game_id === 'MLB_G1' && c2.away.ml?.input.spec.game_id === 'MLB_G2');
  // The shape the board must not use: one index over both games.
  const both = buildTeamLineIndex(dh, [g1, g2], { market: 'h2h', books, gameIds: null });
  check('(one index over both games keeps only one — why the board builds per game)', both.size === 2 && both.get('KC')!.gameId === 'MLB_G2');
  check('the board builds its indexes per game', read('src/components/GamesBoard.tsx').includes('const only = new Set([g.game_id]);'));
}

// 8. Speech, freshness, lock.
{
  const upcoming = gamesCardLabel({ phase: 'upcoming', away: { name: 'KC', score: '' }, home: { name: 'BUF', score: '' }, footerText: '8:20 PM ET' });
  check('an upcoming card speaks matchup and time, no prices or book', upcoming === 'KC at BUF, 8:20 PM ET.' && !/DraftKings|−|\+/.test(upcoming), upcoming);
  const live = gamesCardLabel({ phase: 'live', away: { name: 'KC', score: '14' }, home: { name: 'BUF', score: '10' }, footerText: 'Q3 4:12' });
  check('a live card speaks the score and clock', live === 'KC 14, BUF 10. Live, Q3 4:12.', live);
  const fin = gamesCardLabel({ phase: 'final', away: { name: 'KC', score: '27' }, home: { name: 'BUF', score: '24' }, footerText: 'Final/OT' });
  check('a final card speaks the score and how it ended', fin === 'KC 27, BUF 24. Final/OT.', fin);
  check('the board does not reuse the Scoreboard\'s DraftKings speech', !read('src/components/GamesBoard.tsx').includes('card.accessibilityLabel'));
  check('the newest snapshot is the "as of" time',
    newestSnapshot([{ snapshot_at: '2026-11-27T15:00:00Z' }, { snapshot_at: '2026-11-27T16:05:00Z' }, { snapshot_at: null }]) === '2026-11-27T16:05:00Z');
  const src = read('src/components/GamesBoard.tsx');
  check('today\'s prices are re-read on a timer', src.includes('setInterval(() => void loadLines(), LINES_POLL_MS)'));
  check('a locked member gets the unlock card, not the board', src.includes('Games is Premium') && src.includes('useScoreboard(!locked'));
  check('Stats passes the membership lock', read('src/screens/StatsScreen.tsx').includes('locked={gamesLocked}'));
}

// 6. Wiring.
{
  check('NFL gets Players | Teams | Games', boardSegmentsFor('NFL').join() === 'players,teams,games', boardSegmentsFor('NFL').join());
  check('the NBA keeps 1st Basket and adds Games', boardSegmentsFor('NBA').join() === 'players,teams,firstBasket,games', boardSegmentsFor('NBA').join());
  check('UFC (no teams) gets no Games tab', !boardSegmentsFor('UFC').includes('games'));
  check('the tab reads "Games"', segmentLabel('games') === 'Games');
  const stats = read('src/screens/StatsScreen.tsx');
  check('Stats renders the Games board', stats.includes("boardMode === 'games' && supportsGamesBoard(sport)") && stats.includes('<GamesBoard'));
  const boardSrc = read('src/components/GamesBoard.tsx');
  check('the board shows bet buttons only on today\'s unstarted games',
    boardSrc.includes('showLines={withLines && unstarted.has(item.gameId)}'));
  check('the board reads lines only for today', boardSrc.includes('if (!withLines) {') && boardSrc.includes('fetchGameLinesForDate(today)'));
  check('a button opens the add-to-betslip sheet with the team\'s choices',
    boardSrc.includes('input={sheet?.input ?? null}') && boardSrc.includes('choices={sheet?.choices}'));
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);

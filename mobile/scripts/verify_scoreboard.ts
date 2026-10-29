/**
 * Scoreboard: game cards, DK lines, stored live scores only.
 * Run: npx tsx scripts/verify_scoreboard.ts
 */

import {
  SCOREBOARD_MINUS,
  feedFromMlb,
  feedFromEspn,
  feedFromNcaaf,
  mergeDkInplay,
  movementText,
  marketCell,
  orderScoreboard,
  pctText,
  presentScoreboard,
  splitsFor,
  splitsSpeech,
  scoreboardPhase,
  type ScoreboardGame,
} from '../src/lib/scoreboard';

let passed = 0;
let failed = 0;

function check(name: string, ok: boolean): void {
  if (ok) {
    passed += 1;
    return;
  }
  failed += 1;
  console.error(`FAIL ${name}`);
}

const game = (over: Partial<ScoreboardGame> = {}): ScoreboardGame => ({
  game_id: 'G',
  sport: 'NFL',
  game_date: '2026-10-28',
  away_team: 'SF',
  home_team: 'ATL',
  home_score: null,
  away_score: null,
  commence_time: '2020-01-01T18:00:00Z',
  went_to_ot: 0,
  ...over,
});

// NFL / NBA / NHL live scores from live_scoreboard (Matt, 2026-10-29).
const espnNow = Date.parse('2026-10-30T01:00:00Z');
const espnLive = feedFromEspn({
  snapshot_at: '2026-10-30T00:59:10Z', state: 'in', home_score: 17, away_score: 10,
  clock_label: 'Q3 7:42', situation: '2nd & 7 at CAR 35', possession: 'home',
}, espnNow);
check('a fresh live_scoreboard row is in progress', espnLive?.inProgress === true && espnLive.homeScore === 17);
const espnCard = presentScoreboard({ game: game({ sport: 'NFL', away_team: 'CAR', home_team: 'GB' }), pregame: [], inplay: [], feed: espnLive });
check('an ESPN live row makes the card live with its score and clock', espnCard.phase === 'live'
  && espnCard.home.score === '17' && espnCard.away.score === '10' && espnCard.footerText === 'Q3 7:42'
  && espnCard.home.possession && espnCard.situation === '2nd & 7 at CAR 35');
const espnStale = feedFromEspn({ snapshot_at: '2026-10-30T00:40:00Z', state: 'in', home_score: 3, away_score: 0 }, espnNow);
check('a live_scoreboard row older than 10 minutes is not live', espnStale === null);
const espnFinal = feedFromEspn({ snapshot_at: '2026-10-29T20:00:00Z', state: 'post', home_score: 101, away_score: 99, clock_label: 'Final' }, espnNow);
check('a completed ESPN row is final however old', espnFinal?.ended === true && espnFinal.inProgress === false);
check('no live_scoreboard row is no feed', feedFromEspn(null, espnNow) === null);

// One list: live first, then upcoming, then final; start time inside each.
const ordered = orderScoreboard([
  presentScoreboard({ game: game({ game_id: 'F', home_score: 3, away_score: 1, commence_time: '2026-10-29T23:00:00Z' }), pregame: [], inplay: [], feed: null }),
  presentScoreboard({ game: game({ game_id: 'U2', commence_time: '2026-10-30T02:00:00Z' }), pregame: [], inplay: [], feed: null }),
  presentScoreboard({ game: game({ game_id: 'L', sport: 'NFL' }), pregame: [], inplay: [], feed: espnLive }),
  presentScoreboard({ game: game({ game_id: 'U1', commence_time: '2026-10-30T00:00:00Z' }), pregame: [], inplay: [], feed: null }),
]);
const startedBare = presentScoreboard({ game: game({ commence_time: '2026-10-30T00:15:00Z' }), pregame: [], inplay: [], feed: null, now: Date.parse('2026-10-30T01:00:00Z') });
check('a started game with no live row says so, not its start time', startedBare.phase === 'upcoming'
  && startedBare.footerText === 'Started · no live score yet' && startedBare.accessibilityLabel.includes('started, no score stored'));
const notYet = presentScoreboard({ game: game({ commence_time: '2026-10-30T00:15:00Z' }), pregame: [], inplay: [], feed: null, now: Date.parse('2026-10-29T20:00:00Z') });
check('a game before its start keeps its start time', notYet.footerText !== 'Started · no live score yet' && notYet.accessibilityLabel.includes('not started'));
// % bets / % money: one market at a time (Matt, 2026-10-29).
const splitRows = [
  { game_id: 'G', market: 'spreads', side: 'away', bet_pct: 47, money_pct: '53.0' },
  { game_id: 'G', market: 'spreads', side: 'home', bet_pct: 53, money_pct: 47 },
  { game_id: 'G', market: 'totals', side: 'over', bet_pct: 60, money_pct: 70 },
  { game_id: 'G', market: 'totals', side: 'under', bet_pct: 40, money_pct: 30 },
];
const spreadSplit = splitsFor(splitRows, 'spreads');
check('spread splits land on their team rows', spreadSplit.away.bets === 47 && spreadSplit.away.money === 53
  && spreadSplit.home.bets === 53 && spreadSplit.home.money === 47);
const totalSplit = splitsFor(splitRows, 'totals');
check('total splits put Over on the away row, Under on the home row', totalSplit.away.bets === 60 && totalSplit.home.money === 30);
const mlSplit = splitsFor(splitRows, 'h2h');
check('a market with no stored split is a dash, not 0%', mlSplit.away.bets === null && pctText(mlSplit.away.bets) === '—');
check('no rows at all is a dash', splitsFor(undefined, 'spreads').home.money === null);
check('pct reads as a whole percent', pctText(47) === '47%');
const cellCard = presentScoreboard({
  game: game({ commence_time: '2099-01-01T00:00:00Z' }),
  pregame: [
    { market: 'spreads', spread_home: -3.5, home_price: -112, away_price: -108 },
    { market: 'totals', total_line: 46.5, over_price: -120, under_price: 100 },
    { market: 'h2h', home_price: -192, away_price: 160 },
  ],
  inplay: [],
  feed: null,
});
check('the odds cell follows the market', marketCell(cellCard.away, 'spreads').value === '+3.5'
  && marketCell(cellCard.away, 'totals').value === 'o46.5' && marketCell(cellCard.home, 'h2h').value === `${SCOREBOARD_MINUS}192`);
check('splits are spoken per side', splitsSpeech(cellCard, 'spreads', spreadSplit).includes('47 percent of bets, 53 percent of money'));
check('the board orders live, upcoming, final', ordered.map((c) => c.gameId).join(',') === 'L,U1,U2,F');

const kicked = game();
check('a past kickoff with no feed is not live', scoreboardPhase(kicked, null) === 'upcoming');
const bare = presentScoreboard({ game: kicked, pregame: [], inplay: [], feed: null });
check('no feed does not invent a score', bare.phase === 'upcoming' && bare.away.score === '—' && bare.home.score === '—');
check('upcoming shows the moneyline column', bare.showMl === true);

const priced = presentScoreboard({
  game: kicked,
  pregame: [
    { market: 'spreads', spread_home: -2.5, home_price: -113, away_price: -106 },
    { market: 'totals', total_line: 51, over_price: -108, under_price: -116 },
    { market: 'h2h', home_price: -165, away_price: 140 },
  ],
  inplay: [],
  feed: null,
});
check('away spread is the other side of the home number', priced.away.spread === '+2.5' && priced.home.spread === `${SCOREBOARD_MINUS}2.5`);
check('prices use a minus, not a hyphen', priced.home.spreadPrice.includes(SCOREBOARD_MINUS) && !priced.home.spreadPrice.includes('-'));
check('total is over on the away row and under on the home row', priced.away.total === 'o51' && priced.home.total === 'u51');
check('the card label speaks the spread and the moneyline', priced.accessibilityLabel.includes('spread +2.5') && priced.accessibilityLabel.includes('moneyline'));

const liveFeed = feedFromMlb({
  snapshot_at: new Date().toISOString(),
  inning: 7,
  inning_half: 'top',
  outs: 1,
  bases_state: '110',
  home_score: 2,
  away_score: 4,
  abstract_game_state: 'Live',
}, Date.now());
const liveCard = presentScoreboard({
  game: game({ sport: 'MLB', away_team: 'NYY', home_team: 'BOS' }),
  pregame: [],
  inplay: [{ market: 'spreads', spread_home: -1.5, home_price: -140, away_price: 120 }],
  feed: liveFeed,
});
check('a fresh MLB live row is live with the stored score', liveCard.phase === 'live' && liveCard.away.score === '4' && liveCard.home.score === '2');
check('top of the inning marks the away side', liveCard.away.possession && !liveCard.home.possession);
check('runners are a situation line, not a made-up play', liveCard.situation === 'Runners on 1st & 2nd');
check('live hides the moneyline column', liveCard.showMl === false);
check('live uses the in-play spread when one is stored', liveCard.home.spread === `${SCOREBOARD_MINUS}1.5`);
const mixed = presentScoreboard({
  game: game({ sport: 'MLB' }),
  pregame: [{ market: 'totals', total_line: 8.5, over_price: -110, under_price: -110 }],
  inplay: [{ market: 'spreads', spread_home: -1.5, home_price: -140, away_price: 120 }],
  feed: liveFeed,
});
check('an in-play spread does not wipe a pregame total', mixed.away.total === 'o8.5' && mixed.home.spread === `${SCOREBOARD_MINUS}1.5`);

const stale = feedFromMlb({
  snapshot_at: '2020-01-01T00:00:00Z',
  inning: 3,
  inning_half: 'bottom',
  outs: 0,
  bases_state: '000',
  home_score: 1,
  away_score: 0,
  abstract_game_state: 'Live',
}, Date.now());
check('a stale MLB snapshot is dropped', stale == null);
check('a dropped snapshot does not become a score', presentScoreboard({
  game: game({ sport: 'MLB' }),
  pregame: [],
  inplay: [],
  feed: stale,
}).away.score === '—');

const finalGame = game({ home_score: 27, away_score: 24, went_to_ot: 1 });
const stillIn = feedFromNcaaf({
  snapshot_at: new Date().toISOString(),
  period: 4,
  clock_seconds: 10,
  home_score: 20,
  away_score: 17,
  possession: 'home',
  raw_state: JSON.stringify({ state: 'in', state_name: 'in_progress', situation: '1st & 10 at ATL 35' }),
}, Date.now());
const finalCard = presentScoreboard({ game: finalGame, pregame: [], inplay: [], feed: stillIn });
check('a stored final score wins over a live-looking feed', finalCard.phase === 'final' && finalCard.away.score === '24' && finalCard.home.score === '27');
check('overtime final is labeled', finalCard.footerText === 'Final/OT');
check('the lower final score is muted', finalCard.away.scoreMuted && !finalCard.home.scoreMuted);
check('final lines are muted and the moneyline column is gone', finalCard.linesMuted && !finalCard.showMl);

const ncaaf = feedFromNcaaf({
  snapshot_at: new Date().toISOString(),
  period: 2,
  clock_seconds: 16,
  home_score: 12,
  away_score: 14,
  possession: 'away',
  raw_state: JSON.stringify({ state: 'in', situation: '2nd & Goal at ATL 4' }),
}, Date.now());
const ncaafCard = presentScoreboard({
  game: game({ sport: 'NCAAF', away_team: 'San Francisco', home_team: 'Atlanta' }),
  pregame: [],
  inplay: [],
  feed: ncaaf,
});
check('fresh NCAAF state is live', ncaafCard.phase === 'live' && ncaafCard.footerText.startsWith('Q2'));
check('the feed situation is shown as stored', ncaafCard.situation === '2nd & Goal at ATL 4');
check('away possession is the away row', ncaafCard.away.possession);

const old = feedFromNcaaf({
  snapshot_at: '2020-01-01T00:00:00Z',
  period: 4,
  clock_seconds: 29,
  home_score: 35,
  away_score: 20,
  possession: 'home',
  raw_state: JSON.stringify({ state: 'in', state_name: 'in_progress' }),
}, Date.now());
check('an old NCAAF in-progress row is not live', old == null || old.inProgress === false);

const keptSpread = mergeDkInplay(
  new Map([['G', [
    { market: 'spreads', spread_home: -3 },
    { market: 'h2h', home_price: -150 },
    { market: 'totals', total_line: 8.5 },
  ]]]),
  ['G'],
  [
    { market: 'spreads', gameIds: ['G'], ok: false, rows: [], error: 'nope' },
    { market: 'h2h', gameIds: ['G'], ok: true, rows: [{ market: 'h2h', home_price: -140, game_id: 'G' }], error: null },
    { market: 'totals', gameIds: ['G'], ok: true, rows: [], error: null },
  ],
);
const kept = keptSpread.lines.get('G') ?? [];
check('a failed spread chunk keeps the previous spread', kept.find((q) => q.market === 'spreads')?.spread_home === -3 && keptSpread.error === 'nope');
check('a successful moneyline replaces the previous one', kept.find((q) => q.market === 'h2h')?.home_price === -140);
check('a successful empty total drops that market', kept.find((q) => q.market === 'totals') == null);

check('line movement names open and now', movementText(
  { market: 'spreads', spread_home: -3, home_price: -110 },
  { market: 'spreads', spread_home: -2.5, home_price: -106 },
  'spreads',
) === `Opened ${SCOREBOARD_MINUS}3 ${SCOREBOARD_MINUS}110 · Now ${SCOREBOARD_MINUS}2.5 ${SCOREBOARD_MINUS}106`);

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
console.log('ALL PASS');

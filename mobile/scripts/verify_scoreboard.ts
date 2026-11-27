/**
 * Scoreboard: game cards, DK lines, stored live scores only.
 * Run: npx tsx scripts/verify_scoreboard.ts
 */

import {
  SCOREBOARD_MINUS,
  feedFromMlb,
  feedFromEspn,
  feedFromNcaaf,
  feedView,
  scoreSides,
  mergeDkInplay,
  movementText,
  marketCell,
  orderScoreboard,
  pctText,
  presentScoreboard,
  shownSplitLine,
  splitsFor,
  splitMove,
  splitsSpeech,
  scoreboardPhase,
  ESPN_LIVE_SPORTS,
  SCOREBOARD_SPORTS,
  nextSlateText,
  scoreboardChipSports,
  scoreboardSwitchLine,
  scoreboardMarketsFor,
  liveBookLines,
  LIVE_BOOK_QUIET_MS,
  SCOREBOARD_BOOK_NOTE,
  SCOREBOARD_LIVE_BOOK_NOTE,
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
// line_value is the number the percent was measured at.
const splitRows = [
  { game_id: 'G', market: 'spreads', side: 'away', bet_pct: 47, money_pct: '53.0', line_value: 3.5 },
  { game_id: 'G', market: 'spreads', side: 'home', bet_pct: 53, money_pct: 47, line_value: -3.5 },
  { game_id: 'G', market: 'totals', side: 'over', bet_pct: 60, money_pct: 70, line_value: 46.5 },
  { game_id: 'G', market: 'totals', side: 'under', bet_pct: 40, money_pct: 30, line_value: 46.5 },
];
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
const spreadSplit = splitsFor(splitRows, 'spreads', shownSplitLine(cellCard, 'spreads'));
check('spread splits land on their team rows when the line matches', spreadSplit.away.bets === 47 && spreadSplit.away.money === 53
  && spreadSplit.home.bets === 53 && spreadSplit.home.money === 47);
const totalSplit = splitsFor(splitRows, 'totals', shownSplitLine(cellCard, 'totals'));
check('total splits put Over on the away row, Under on the home row', totalSplit.away.bets === 60 && totalSplit.home.money === 30);
const mlSplit = splitsFor(splitRows, 'h2h', shownSplitLine(cellCard, 'h2h'));
check('a market with no stored split is a dash, not 0%', mlSplit.away.bets === null && pctText(mlSplit.away.bets) === '—');
check('the odds cell follows the market', marketCell(cellCard.away, 'spreads').value === '+3.5'
  && marketCell(cellCard.away, 'totals').value === 'o46.5' && marketCell(cellCard.home, 'h2h').value === `${SCOREBOARD_MINUS}192`);
check('a market with no split says nothing extra', splitsSpeech(cellCard, 'h2h', mlSplit) === '');
check('splits are spoken per side', splitsSpeech(cellCard, 'spreads', spreadSplit).includes('47 percent of bets, 53 percent of money'));
// Movement arrow vs DK's first split for the side (Matt, 2026-11-16).
check('no opening stored is no arrow', spreadSplit.away.moneyMove === null);
check('a 3-point move up is an arrow up, 2 points is none',
  splitMove(55, 52) === 'up' && splitMove(54, 52) === null && splitMove(32, '47.0') === 'down');
check('a dash never carries an arrow', splitMove(null, 40) === null);
const openedRows = splitRows.map((r) => (r.market === 'spreads' && r.side === 'away'
  ? { ...r, open_bet_pct: 47, open_money_pct: 60 } : r));
const openedSplit = splitsFor(openedRows, 'spreads', shownSplitLine(cellCard, 'spreads'));
check('money down 7 from its opening is an arrow down, unmoved bets none',
  openedSplit.away.moneyMove === 'down' && openedSplit.away.betsMove === null);
check('a moved split is spoken', splitsSpeech(cellCard, 'spreads', openedSplit).includes('53 percent of money, down from 60 at open'));
const movedLine = presentScoreboard({
  game: game({ commence_time: '2099-01-01T00:00:00Z' }),
  pregame: [{ market: 'spreads', spread_home: -3, home_price: -110, away_price: -110 }],
  inplay: [],
  feed: null,
});
const movedSplit = splitsFor(splitRows, 'spreads', shownSplitLine(movedLine, 'spreads'));
check('a percent measured at -3.5 is not shown next to DK -3',
  movedLine.home.spread === `${SCOREBOARD_MINUS}3` && movedSplit.home.bets === null && movedSplit.away.bets === null);
const noMeasuredLine = splitRows.map((r) => (r.market === 'spreads' ? { ...r, line_value: null } : r));
check('a spread percent with no measured line is a dash',
  splitsFor(noMeasuredLine, 'spreads', shownSplitLine(cellCard, 'spreads')).home.bets === null);
const liveSameNumber = presentScoreboard({
  game: game({ sport: 'NFL', away_team: 'CAR', home_team: 'GB' }),
  pregame: [{ market: 'spreads', spread_home: -3.5, home_price: -112, away_price: -108 }],
  inplay: [{ market: 'spreads', spread_home: -3.5, home_price: -140, away_price: 120 }],
  feed: espnLive,
});
const liveSameSplit = splitsFor(splitRows, 'spreads', shownSplitLine(liveSameNumber, 'spreads'));
check('a live DK spread does not keep the pre-game percent at the same number',
  liveSameNumber.home.spread === `${SCOREBOARD_MINUS}3.5`
  && liveSameSplit.home.bets === null && liveSameSplit.away.money === null);
const liveSpreadOnly = presentScoreboard({
  game: game({ sport: 'NFL', away_team: 'CAR', home_team: 'GB' }),
  pregame: [
    { market: 'spreads', spread_home: -3.5, home_price: -112, away_price: -108 },
    { market: 'totals', total_line: 46.5, over_price: -120, under_price: 100 },
  ],
  inplay: [{ market: 'spreads', spread_home: -2.5, home_price: -130, away_price: 110 }],
  feed: espnLive,
});
check('a pre-game total still shows when only the spread is the live DK line',
  splitsFor(splitRows, 'totals', shownSplitLine(liveSpreadOnly, 'totals')).away.bets === 60
  && splitsFor(splitRows, 'spreads', shownSplitLine(liveSpreadOnly, 'spreads')).home.bets === null);
const mlRows = [
  { game_id: 'G', market: 'h2h', side: 'away', bet_pct: 40, money_pct: 30, line_value: null },
  { game_id: 'G', market: 'h2h', side: 'home', bet_pct: 60, money_pct: 70, line_value: null },
];
check('moneyline has no point line, so the pre-game percent shows',
  splitsFor(mlRows, 'h2h', shownSplitLine(cellCard, 'h2h')).home.bets === 60);
const liveMl = presentScoreboard({
  game: game({ sport: 'NFL', away_team: 'CAR', home_team: 'GB' }),
  pregame: [{ market: 'h2h', home_price: -192, away_price: 160 }],
  inplay: [{ market: 'h2h', home_price: -150, away_price: 130 }],
  feed: espnLive,
});
check('a live DK moneyline does not keep the pre-game percent',
  splitsFor(mlRows, 'h2h', shownSplitLine(liveMl, 'h2h')).home.bets === null
  && splitsFor(mlRows, 'h2h', shownSplitLine(liveMl, 'h2h')).away.money === null);
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

// Every sport with games (Matt, 2026-11-15).
for (const id of ['NCAAB', 'NCAABW', 'EUROLEAGUE', 'WNBA', 'UFC', 'ATP', 'WTA']) {
  check(`${id} is a Scoreboard sport`, (SCOREBOARD_SPORTS as readonly string[]).includes(id));
}
check('men\'s and women\'s college basketball read live_scoreboard',
  ESPN_LIVE_SPORTS.includes('NCAAB') && ESPN_LIVE_SPORTS.includes('NCAABW'));
check('EuroLeague reads its live score from live_scoreboard (its own API, 2026-11-25)',
  ESPN_LIVE_SPORTS.includes('EUROLEAGUE'));

const chips = scoreboardChipSports({ NCAAB: 96, NHL: 10, UFC: 0 }, 'NFL');
check('chips are the sports with games plus the open one, in board order',
  chips.join(',') === 'NFL,NHL,NCAAB');
check('the open sport keeps its chip on an empty day',
  scoreboardChipSports({}, 'MLB').join(',') === 'MLB');

const school = presentScoreboard({
  game: game({ sport: 'NCAAB', away_team: 'Quinnipiac', home_team: 'Central Connecticut' }),
  pregame: [], inplay: [], feed: null,
});
check('a school gets initials in the disc and its name beside it',
  school.home.disc === 'CC' && school.home.name === 'Central Connecticut'
  && school.away.disc === 'QUIN' && school.away.name === 'Quinnipiac');

const collegeLive = presentScoreboard({
  game: game({ sport: 'NCAAB', away_team: 'Quinnipiac', home_team: 'Central Connecticut' }),
  pregame: [], inplay: [],
  feed: feedFromEspn({ snapshot_at: '2026-10-30T00:59:10Z', state: 'in', home_score: 40, away_score: 38,
    clock_label: '2H 11:02' }, espnNow),
});
check('a college basketball live row makes the card live',
  collegeLive.phase === 'live' && collegeLive.home.score === '40' && collegeLive.footerText === '2H 11:02');

const fightGame = game({ sport: 'UFC', away_team: 'Amanda Nunes', home_team: 'Kayla Harrison' });
const fight = presentScoreboard({
  game: { ...fightGame, home_score: '1', away_score: '0' }, pregame: [], inplay: [], feed: null,
});
check('a UFC final reads W and L, not 1 and 0',
  fight.phase === 'final' && fight.home.score === 'W' && fight.away.score === 'L'
  && fight.away.scoreMuted && !fight.home.scoreMuted);
check('a fighter is initials in the disc and "F. Lastname" beside it',
  fight.home.disc === 'KH' && fight.home.name === 'K. Harrison');
check('a UFC matchup is spoken as versus, and the winner is named',
  fight.accessibilityLabel.startsWith('Amanda Nunes versus Kayla Harrison, final, Kayla Harrison won'));
const draw = presentScoreboard({
  game: { ...fightGame, home_score: '0.5', away_score: '0.5' }, pregame: [], inplay: [], feed: null,
});
check('a UFC draw (0.5 / 0.5) reads D, not a rounded 1-1',
  draw.home.score === 'D' && draw.away.score === 'D' && !draw.home.scoreMuted && !draw.away.scoreMuted);
check('UFC has no Spread tab and opens on the moneyline',
  scoreboardMarketsFor('UFC').join(',') === 'h2h,totals'
  && scoreboardMarketsFor('NCAAB').join(',') === 'spreads,totals,h2h');
check('tennis next-slate text says vs with last names',
  (nextSlateText({ sport: 'WTA', away_team: 'Mirra Andreeva', home_team: 'Elina Svitolina', commence_time: null }) ?? '')
    === 'M. Andreeva vs E. Svitolina');
check('a code sport is unchanged',
  presentScoreboard({ game: game(), pregame: [], inplay: [], feed: null }).home.disc === 'ATL');

const ufcName = (n: string) => presentScoreboard({
  game: game({ sport: 'UFC', away_team: n, home_team: 'Ciryl Gane' }), pregame: [], inplay: [], feed: null,
}).away.name;
check('a suffix is not the last name', ufcName('Rodolfo Vieira Jr.') === 'R. Vieira');
check('a compound surname is kept whole', ufcName('Benoit Saint Denis') === 'B. Saint Denis');
const ncaab = (away: string, home: string) => presentScoreboard({
  game: game({ sport: 'NCAAB', away_team: away, home_team: home }), pregame: [], inplay: [], feed: null,
});
check('an apostrophe is not a word break', ncaab("St. John's", 'Kentucky').away.disc === 'SJ');
check('a short capitals word is kept whole', ncaab('UC Santa Barbara', 'Kentucky').away.disc === 'UCSB');
const clash = ncaab('North Carolina', 'Northern Colorado');
check('two sides with the same initials fall back to their last word',
  clash.away.disc === 'CARO' && clash.home.disc === 'COLO');
const tennisStarted = presentScoreboard({
  game: game({ sport: 'ATP', away_team: 'Arthur Fils', home_team: 'Ben Shelton' }),
  pregame: [], inplay: [], feed: null, now: Date.parse('2026-01-01T00:00:00Z'),
});
check('a sport with no live feed does not promise a score "yet"',
  tennisStarted.footerText === 'Started · live scores not tracked');
check('the nudge names the day, the league and its noun',
  scoreboardSwitchLine({ EUROLEAGUE: 5, UFC: 3 }, 'NFL', 'tomorrow')
    === 'Or switch sport above — EuroLeague has 5 games tomorrow.'
  && scoreboardSwitchLine({ UFC: 1 }, 'NFL') === 'Or switch sport above — UFC has 1 fight today.');

// ── The pick card's score pill (Matt, 2026-11-24) ──────────────────────────
// The row is production's, read 2026-11-24 23:48 UTC: Queens @ Wofford at the
// half while the card said a bare LIVE.
{
  const at = Date.parse('2026-11-24T23:48:23Z');
  const wofford = {
    sport: 'NCAAB', away_team: 'Queens University', home_team: 'Wofford',
    home_score: null, away_score: null,
  };
  const half = feedFromEspn({
    game_id: 'NCAAB_2026-11-24_queens-university_wofford', state: 'in',
    home_score: 39, away_score: 35, clock_label: 'Half', situation: null,
    possession: null, snapshot_at: '2026-11-24T23:48:00.000826+00:00',
  } as never, at);
  const v = feedView(wofford, half, at);
  check('the card pill shows the feed score away–home and its clock',
    v?.kind === 'live' && v.score === '35–39' && v.clock === 'Half');
  check('VoiceOver hears the score with each team named',
    v?.speech === 'Live, Half, Queens University 35, Wofford 39');
  check('a feed older than the ESPN freshness window does not read LIVE',
    feedView(wofford, half, at + 11 * 60 * 1000) === null);
  check('a stored final on games wins over the feed',
    feedView({ ...wofford, home_score: 80, away_score: 70 }, half, at) === null);
  const ended = half && { ...half, inProgress: false, ended: true, clockLabel: 'Final' };
  const fin = feedView(wofford, ended, at + 3 * 60 * 60 * 1000);
  check('an ended feed reads FINAL with the score, however old',
    fin?.kind === 'final' && fin.score === '35–39' && fin.speech === 'Final, Queens University 35, Wofford 39');
  check('no feed, no pill from the feed', feedView(wofford, null, at) === null);
  check('the feed view carries the raw away and home numbers for the labelled pill',
    v?.awayScore === 35 && v?.homeScore === 39);
}

// Labelled, picked-side score (Matt, 2026-11-27: "50–59" read as St. John's
// first on a St. John's ML card; St. John's was the away side, down 9).
{
  const sj = { sport: 'NCAAB', away_team: "St. John's", home_team: 'Iowa State' };
  const s = scoreSides(sj, 50, 59, 'away');
  check('each side is labelled, away first like the header',
    s?.away.label === 'SJ' && s.away.score === 50 && s.home.label === 'IS' && s.home.score === 59);
  check('an away pick marks the away side only', s?.away.picked === true && s.home.picked === false);
  const h = scoreSides(sj, 50, 59, 'home');
  check('a home pick marks the home side only', h?.home.picked === true && h.away.picked === false);
  const o = scoreSides(sj, 50, 59, 'over');
  check('a totals pick marks neither side', o?.away.picked === false && o.home.picked === false);
  check('no score, no labelled score', scoreSides(sj, null, 59, 'away') === null);
  const nc = scoreSides({ sport: 'NCAAB', away_team: 'North Carolina', home_team: 'Northern Colorado' }, 1, 2, 'away');
  check('two schools with the same initials fall back to the last word',
    nc?.away.label === 'CARO' && nc.home.label === 'COLO');
  const nba = scoreSides({ sport: 'NBA', away_team: 'BOS', home_team: 'LAL' }, 100, 98, 'home');
  check('a code sport keeps its code', nba?.away.label === 'BOS' && nba.home.label === 'LAL');
  const st = scoreSides({ sport: 'NCAAB', away_team: 'Iowa State', home_team: 'Illinois State' }, 1, 2, 'away');
  check('two "State" schools fall back to the first word, never STAT / STAT',
    st?.away.label === 'IOWA' && st.home.label === 'ILLI');
  check('names no label can separate show the bare score (null)',
    scoreSides({ sport: 'NCAAB', away_team: 'Miami', home_team: 'Miami' }, 1, 2, 'away') === null);
  const osu = scoreSides({ sport: 'NCAAF', away_team: 'Ohio State', home_team: 'Michigan' }, 1, 2, 'home');
  check('NCAAF with no code map uses initials, not the first three letters',
    osu?.away.label === 'OS' && osu.home.label === 'MICH');
  const coded = scoreSides({ sport: 'NCAAF', away_team: 'Ohio State', home_team: 'Michigan' }, 1, 2, 'home',
    new Map([['Ohio State', 'OSU'], ['Michigan', 'MICH']]));
  check('NCAAF with the code map uses its codes', coded?.away.label === 'OSU' && coded.home.label === 'MICH');
}


// Live at your books (mike, 2026-11-25: "why not FanDuel, MGM etc").
{
  const now = Date.parse('2026-11-25T01:00:00Z');
  const at = (sec: number) => new Date(now - sec * 1000).toISOString();
  const rows = [
    { market: 'spreads', bookmaker: 'fanduel', spread_home: -3.5, home_price: -110, away_price: -110, snapshot_at: at(90) },
    { market: 'spreads', bookmaker: 'draftkings', spread_home: -4, home_price: -105, away_price: -115, snapshot_at: at(5) },
    { market: 'spreads', bookmaker: 'draftkings', spread_home: -2, home_price: -110, away_price: -110, snapshot_at: at(600) },
    { market: 'spreads', bookmaker: 'betmgm', spread_home: -3.5, home_price: -110, away_price: -110,
      snapshot_at: at(LIVE_BOOK_QUIET_MS / 1000 + 7 * 60) },
    { market: 'spreads', bookmaker: 'pinnacle', spread_home: -3.5, home_price: -108, away_price: -108, snapshot_at: at(10) },
    { market: 'totals', bookmaker: 'fanduel', total_line: 220.5, over_price: -112, under_price: -108, snapshot_at: at(30) },
    { market: 'totals', bookmaker: 'draftkings', total_line: null, over_price: -110, under_price: -110, snapshot_at: at(3) },
    { market: 'h2h', bookmaker: 'betmgm', home_price: -160, away_price: 135, snapshot_at: at(20) },
  ];
  const books = ['draftkings', 'fanduel', 'betmgm'];
  const sp = liveBookLines(rows, 'spreads', books, now);
  check('live spreads: each book its own newest number, in the member book order',
    sp.map((l) => l.book).join(',') === 'draftkings,fanduel,betmgm');
  check('live spreads: the away side is the home number turned over, price under it',
    sp[0]?.away.main === '+4' && sp[0]?.away.sub === '−115' && sp[0]?.home.main === '−4' && sp[0]?.home.sub === '−105');
  check('live spreads: a line with no move in 15 minutes stays, said to be quiet',
    sp[2]?.quiet === true && sp[2]?.age === 'No move in 22m' && sp[2]?.ageSpoken === 'no move in 22 minutes');
  check('live spreads: a book the member does not use is left out',
    !sp.some((l) => l.book === 'pinnacle'));
  check('live spreads: age reads Now under a minute, else minutes, and VoiceOver hears words',
    sp[0]?.age === 'Now' && sp[0]?.ageSpoken === 'moved just now' && sp[1]?.age === '1m ago'
      && sp[1]?.ageSpoken === 'moved 1 minute ago' && sp[1]?.quiet === false);
  check('live spreads: VoiceOver hears the line at the price',
    sp[0]?.awaySpoken === '+4 at −115' && sp[0]?.homeSpoken === '−4 at −105');
  const tot = liveBookLines(rows, 'totals', books, now);
  check('live totals: a row with no line is no line; over and under',
    tot.map((l) => l.book).join(',') === 'fanduel' && tot[0]?.away.main === 'o220.5' && tot[0]?.home.sub === '−108'
      && tot[0]?.awaySpoken === 'over 220.5 at −112');
  const ml = liveBookLines(rows, 'h2h', books, now);
  check('live moneyline: away and home prices', ml[0]?.away.main === '+135' && ml[0]?.home.main === '−160');
  check('no rows, no lines', liveBookLines([], 'h2h', books, now).length === 0);
  check('a live card says the sheet has your books',
    (SCOREBOARD_LIVE_BOOK_NOTE as string) !== SCOREBOARD_BOOK_NOTE && SCOREBOARD_LIVE_BOOK_NOTE.includes('your books'));
}

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
console.log('ALL PASS');

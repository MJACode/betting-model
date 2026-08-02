/**
 * Standalone verification for the live game status + label helpers
 * (src/lib/format.ts: gameStatus / inningShort / inningLong / basesLabel).
 *
 *   npx tsx scripts/verify_live_status.ts
 *
 * Pins the precedence rules that decide what a card shows while a game is in
 * progress: settled scores win; a live snapshot supplies score + inning before
 * settlement; 'Preview' keeps a delayed start on the pre-game time label; and
 * with no snapshot we fall back to the time-based LIVE badge (still the case
 * for every non-MLB sport).
 *
 * Also pins the two rules that make the badge STOP: a Final snapshot never
 * expires, and the clock-only fallback is bounded by a per-sport window. Both
 * exist because `games` scores don't land until the next morning's settlement,
 * so without them a finished game read LIVE overnight.
 */

import {
  basesLabel, gameStatus, inningLong, inningShort,
  isLiveSnapshotUsable, reconcileLiveSnapshots,
} from '../src/lib/format';
import type { GameRow, LiveGameStateRow } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const HOUR = 3_600_000;
const started = new Date(Date.now() - 2 * HOUR).toISOString();
const future = new Date(Date.now() + 2 * HOUR).toISOString();

function mkGame(over: Partial<GameRow> = {}): GameRow {
  return {
    game_id: 'MLB_2026-07-28_CHC_STL', sport: 'MLB', season: 2026, game_date: '2026-07-28',
    home_team: 'STL', away_team: 'CHC', home_score: null, away_score: null,
    home_score_f5: null, away_score_f5: null, commence_time: started,
    home_win: null, home_win_reg: null, went_to_ot: 0, ...over,
  };
}

function mkLive(over: Partial<LiveGameStateRow> = {}): LiveGameStateRow {
  return {
    game_id: 'MLB_2026-07-28_CHC_STL', game_date: '2026-07-28',
    snapshot_at: new Date().toISOString(), inning: 5, inning_half: 'top', outs: 2,
    bases_state: '010', home_score: 0, away_score: 2, abstract_game_state: 'Live', ...over,
  };
}

// ── gameStatus precedence ────────────────────────────────────────────────────
const settled = gameStatus(mkGame({ home_score: 4, away_score: 3 }), mkLive());
check('settled scores beat the live feed', settled.kind === 'final' &&
  settled.awayScore === 3 && settled.homeScore === 4,
  `${settled.kind}`);

const live = gameStatus(mkGame(), mkLive());
check('live snapshot supplies score + inning',
  live.kind === 'live' && live.awayScore === 2 && live.homeScore === 0 &&
  live.inning === 5 && live.inningHalf === 'top' && live.outs === 2 && live.bases === '010');

const liveFinal = gameStatus(mkGame(), mkLive({ abstract_game_state: 'Final', away_score: 6, home_score: 1 }));
check('live Final shows the final score before settlement',
  liveFinal.kind === 'final' && liveFinal.awayScore === 6 && liveFinal.homeScore === 1,
  liveFinal.kind);

// A delayed first pitch: commence_time has passed but the feed still says Preview.
const delayed = gameStatus(mkGame(), mkLive({ abstract_game_state: 'Preview' }));
check('Preview keeps a delayed start pre-game (not a false LIVE)',
  delayed.kind === 'pre' && delayed.timeLabel.length > 0, delayed.kind);

// No snapshot at all (every non-MLB sport today) — old time-based behavior.
const noFeed = gameStatus(mkGame());
check('no snapshot after start → LIVE with unknown score',
  noFeed.kind === 'live' && noFeed.awayScore === null && noFeed.inning === null);

const pre = gameStatus(mkGame({ commence_time: future }));
check('before first pitch → pre with a time label', pre.kind === 'pre' && pre.timeLabel.length > 0);

check('null game → empty pre', gameStatus(null).kind === 'pre');

// A Final snapshot missing scores must not claim FINAL with nothing to show —
// but it must not fall through to LIVE either. Final is terminal.
const finalNoScore = gameStatus(mkGame(), mkLive({ abstract_game_state: 'Final', home_score: null, away_score: null }));
check('Final snapshot without scores → ended, not LIVE', finalNoScore.kind === 'ended', finalNoScore.kind);

// ── the game is over and must stop reading LIVE ──────────────────────────────
// The reported bug: a finished game kept the LIVE badge. Two ways it happened.

// (1) The poller captured Final, but that snapshot aged past the display
// freshness guard — the poller stops writing once a game ends, so this is the
// guaranteed steady state, not an edge case.
const staleFinal = mkLive({
  abstract_game_state: 'Final', away_score: 5, home_score: 1,
  snapshot_at: new Date(Date.now() - 64 * 60_000).toISOString(),
});
check('a Final snapshot never expires (STL @ TOR case)',
  isLiveSnapshotUsable(staleFinal, Date.now()));
const staleFinalStatus = gameStatus(mkGame(), staleFinal);
check('stale Final still renders the final score',
  staleFinalStatus.kind === 'final' && staleFinalStatus.awayScore === 5 &&
  staleFinalStatus.homeScore === 1, staleFinalStatus.kind);

// A stale *non-final* snapshot is still dropped — a frozen inning is worse
// than no inning, and we cannot infer the result from a mid-game state.
check('a stale Live snapshot is still dropped',
  !isLiveSnapshotUsable(mkLive({ snapshot_at: new Date(Date.now() - 76 * 60_000).toISOString() }), Date.now()));
check('a fresh Live snapshot is kept', isLiveSnapshotUsable(mkLive(), Date.now()));

// (2) No usable snapshot at all — the poller stopped before capturing Final
// (WSH @ ATL case), or the sport has no poller. The clock alone can no longer
// hold the badge open forever.
const longOver = gameStatus(mkGame({ commence_time: new Date(Date.now() - 7 * HOUR).toISOString() }));
check('no feed + hours past any plausible finish → ended (no badge)',
  longOver.kind === 'ended', longOver.kind);

const stillPlaying = gameStatus(mkGame({ commence_time: new Date(Date.now() - 2.5 * HOUR).toISOString() }));
check('no feed but within a normal game length → still LIVE',
  stillPlaying.kind === 'live', stillPlaying.kind);

// Window is sport-aware: the same elapsed time reads differently per sport.
const sevenHoursAgo = new Date(Date.now() - 7 * HOUR).toISOString();
const ufcLate = gameStatus(mkGame({ sport: 'UFC', commence_time: sevenHoursAgo }));
check('UFC card still LIVE 7h in (prelims-to-main-event window)',
  ufcLate.kind === 'live', ufcLate.kind);
const nbaLate = gameStatus(mkGame({ sport: 'NBA', commence_time: sevenHoursAgo }));
check('NBA game ended 7h in', nbaLate.kind === 'ended', nbaLate.kind);
const golfDay2 = gameStatus(mkGame({ sport: 'GOLF', commence_time: new Date(Date.now() - 48 * HOUR).toISOString() }));
check('golf tournament row spans days, still LIVE on day 2',
  golfDay2.kind === 'live', golfDay2.kind);
const unknownSport = gameStatus(mkGame({ sport: 'CRICKET', commence_time: sevenHoursAgo }));
check('unknown sport falls back to the default window', unknownSport.kind === 'ended', unknownSport.kind);

// Settlement still wins over everything once scores land.
const settledLate = gameStatus(mkGame({ commence_time: sevenHoursAgo, home_score: 1, away_score: 5 }));
check('settled scores still win past the window', settledLate.kind === 'final', settledLate.kind);

// ── reconcileLiveSnapshots: "the poller moved on" ────────────────────────────
// The poller stops writing for a game the instant it goes Final. So a game that
// goes quiet while OTHER games are still updating has ended — even when the
// loop exited before capturing that game's Final row (WSH @ ATL case).
const ago = (min: number) => new Date(Date.now() - min * 60_000).toISOString();
const slate = [
  mkLive({ game_id: 'quiet', snapshot_at: ago(76), inning: 9, home_score: 4, away_score: 2 }),
  mkLive({ game_id: 'ongoing', snapshot_at: ago(0.1), inning: 5 }),
  mkLive({ game_id: 'done', snapshot_at: ago(64), abstract_game_state: 'Final', home_score: 1, away_score: 5 }),
];
const live1 = reconcileLiveSnapshots(slate, Date.now());

const quiet = live1.get('quiet')!;
check('poller alive + game gone quiet → marked terminal',
  quiet.abstract_game_state === 'Final', String(quiet.abstract_game_state));
check('a quiet game\'s mid-inning score is cleared, not passed off as final',
  quiet.home_score === null && quiet.away_score === null);
check('quiet game renders as ended (no badge, no invented score)',
  gameStatus(mkGame(), quiet).kind === 'ended');
check('a still-updating game is untouched',
  live1.get('ongoing')!.abstract_game_state === 'Live');
check('a captured Final keeps its real score',
  gameStatus(mkGame(), live1.get('done')!).kind === 'final');

// With nothing updating we cannot tell "slate over" from "poller died", so we
// must NOT claim games ended — drop the stale rows and let the clock decide.
const deadPoller = reconcileLiveSnapshots(
  [mkLive({ game_id: 'quiet', snapshot_at: ago(76) }), mkLive({ game_id: 'other', snapshot_at: ago(40) })],
  Date.now(),
);
check('poller dead → stale rows dropped, nothing claimed terminal', deadPoller.size === 0);
check('dead poller falls back to the clock window',
  gameStatus(mkGame({ commence_time: ago(150) }), deadPoller.get('quiet') ?? null).kind === 'live');

// ── label helpers ────────────────────────────────────────────────────────────
check('inningShort top', inningShort(5, 'top') === 'T5', String(inningShort(5, 'top')));
check('inningShort bottom', inningShort(9, 'bottom') === 'B9', String(inningShort(9, 'bottom')));
check('inningShort null inning → null', inningShort(null, 'top') === null);
check('inningShort unknown half still shows the inning', inningShort(7, null) === '7');

check('inningLong with outs', inningLong(5, 'top', 2) === 'Top 5th · 2 out', String(inningLong(5, 'top', 2)));
check('inningLong bottom 3rd', inningLong(3, 'bottom', 0) === 'Bot 3rd · 0 out', String(inningLong(3, 'bottom', 0)));
check('inningLong 11th ordinal (not 11st)', inningLong(11, 'top', 1) === 'Top 11th · 1 out', String(inningLong(11, 'top', 1)));
check('inningLong 1st/2nd ordinals', inningLong(1, 'top', 0) === 'Top 1st · 0 out' && inningLong(2, 'top', 0) === 'Top 2nd · 0 out');
check('inningLong without outs omits the out count', inningLong(4, 'bottom') === 'Bot 4th', String(inningLong(4, 'bottom')));
check('inningLong null inning → null', inningLong(null, 'top', 1) === null);

check('bases empty', basesLabel('000') === 'Bases empty', String(basesLabel('000')));
check('bases loaded', basesLabel('111') === 'Bases loaded', String(basesLabel('111')));
check('runner on second', basesLabel('010') === '2nd', String(basesLabel('010')));
check('corners', basesLabel('101') === '1st & 3rd', String(basesLabel('101')));
check('bases null/garbage → null', basesLabel(null) === null && basesLabel('xyz') === null && basesLabel('01') === null);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

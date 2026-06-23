/**
 * Standalone verification for the model-detail "Today's potential picks /
 * Dropped today" bucketing (bucketModelSignals in src/lib/signalBoard.ts). No JS
 * test runner is configured for the app, so — like verify_signal_board.ts — we
 * assert the pure function here and run with tsx:
 *
 *   npx tsx scripts/verify_model_signal_board.ts
 *
 * Pins: a model's current BET → Live (raw BET, NOT threshold-gated, so a low-edge
 * BET still counts); a locked BET now AVOID → Dropped/avoid; now NONE →
 * Dropped/none; no current row → Dropped/off_board; a locked row whose game is
 * over → excluded; another model's lock → ignored; a still-live BET → not dropped.
 */

import { bucketModelSignals, pickFromOpeningSignal } from '../src/lib/signalBoard';
import type { EnrichedPick, GameRow, OpeningSignalRow, Pick, SignalType } from '../src/types';

const MODEL = 'mlb_runline';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (cond) {
    console.log(`  ok  ${name}`);
  } else {
    failures++;
    console.log(`FAIL  ${name}${detail ? ` — ${detail}` : ''}`);
  }
}

let idSeq = 1;
function makeOpen(
  gameId: string,
  prob: number,
  edge: number,
  modelId = MODEL,
): OpeningSignalRow {
  return {
    id: idSeq++,
    lock_key: `${gameId}:${modelId}`,
    game_id: gameId,
    model_id: modelId,
    sport: 'MLB',
    game_date: '2026-06-21',
    player_id: null,
    pick_side: 'home',
    pick_label: `${gameId} home -1.5`,
    model_probability: prob,
    dk_implied_prob: prob - edge,
    edge,
    dk_odds: -110,
    scored_line: -1.5,
    kelly_fraction: 0.02,
    recommended_bet: 20,
    bankroll_at_pick: 1000,
    confidence_tier: 'MED',
    locked_at: '2026-06-21T11:05:00-04:00',
  } as unknown as OpeningSignalRow;
}

function livePick(
  gameId: string,
  signal: SignalType,
  prob: number,
  edge: number,
  modelId = MODEL,
): EnrichedPick {
  const pick = {
    ...pickFromOpeningSignal(makeOpen(gameId, prob, edge, modelId)),
    pick_id: Math.floor(Math.random() * 1e6) + 1, // real positive id
    signal_type: signal,
    model_probability: prob,
    edge,
  } as Pick;
  return { pick, game: null, weather: null };
}

const gameById = new Map<string, GameRow>();
gameById.set('G_OFF', { game_id: 'G_OFF', home_team: 'BOS', away_team: 'NYY' } as GameRow);
gameById.set('G_OVER', { game_id: 'G_OVER', home_team: 'TOR', away_team: 'TB' } as GameRow);

// Current live state.
const liveData: EnrichedPick[] = [
  livePick('G_LIVE', 'BET', 0.75, 0.12), // still a BET → live
  livePick('G_LOWEDGE', 'BET', 0.51, 0.01), // raw BET below any threshold → still live (no gate)
  livePick('G_AVOID', 'AVOID', 0.40, -0.12), // flipped to avoid
  livePick('G_NONE', 'NONE', 0.55, 0.02), // fell to no-signal
  // G_OFF / G_OVER have no current row.
];

// Locked opening signals (all BET crosses earlier today).
const openingRows: OpeningSignalRow[] = [
  makeOpen('G_LIVE', 0.74, 0.12),
  makeOpen('G_LOWEDGE', 0.52, 0.01),
  makeOpen('G_AVOID', 0.74, 0.12),
  makeOpen('G_NONE', 0.72, 0.11),
  makeOpen('G_OFF', 0.73, 0.11),
  makeOpen('G_OVER', 0.71, 0.10), // game finished → excluded
  makeOpen('G_OTHER', 0.90, 0.20, 'mlb_over_under'), // different model → ignored
];

// G_OVER is the only finished game.
const isOver = (g: GameRow | null) => g?.game_id === 'G_OVER';

const { live, dropped } = bucketModelSignals(liveData, openingRows, gameById, MODEL, isOver);

const liveGames = new Set(live.map((d) => d.pick.game_id));
const droppedByGame = new Map(dropped.map((d) => [d.pick.game_id, d]));

check('live holds both current BETs (incl. the low-edge one — no threshold gate)', live.length === 2);
check('G_LIVE is live', liveGames.has('G_LIVE'));
check('G_LOWEDGE (raw BET) is live', liveGames.has('G_LOWEDGE'));
check('live BETs are not in dropped', !droppedByGame.has('G_LIVE') && !droppedByGame.has('G_LOWEDGE'));
check('G_AVOID → dropped/avoid', droppedByGame.get('G_AVOID')?.droppedReason === 'avoid');
check('G_NONE → dropped/none', droppedByGame.get('G_NONE')?.droppedReason === 'none');
check('G_OFF → dropped/off_board', droppedByGame.get('G_OFF')?.droppedReason === 'off_board');
check(
  'off_board card is enriched + reads inactive with a synthetic negative id',
  droppedByGame.get('G_OFF')?.game?.game_id === 'G_OFF' &&
    droppedByGame.get('G_OFF')?.pick.signal_type === 'NONE' &&
    droppedByGame.get('G_OFF')!.pick.pick_id < 0,
);
check('G_OVER (finished game) is excluded', !droppedByGame.has('G_OVER'));
check('other model lock ignored', !droppedByGame.has('G_OTHER'));
check('dropped count is exactly the three faded picks', dropped.length === 3, `got ${dropped.length}`);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);

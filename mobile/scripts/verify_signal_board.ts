/**
 * Standalone verification for the Signals "Live | Dropped" bucketing
 * (src/lib/signalBoard.ts). No JS test runner is configured for the app, so —
 * like the parlay math — we assert the pure function here and run with tsx:
 *
 *   npx tsx scripts/verify_signal_board.ts
 *
 * Pins: a locked signal now AVOID → Dropped/avoid; still-BET-and-passing → Live
 * (not Dropped); no current row → Dropped/off_board; current NONE → Dropped/none;
 * still BET but below threshold → Dropped/weakened; a lock that never cleared the
 * action filter is excluded; the other sport is ignored.
 */

import { bucketSignals, pickFromOpeningSignal, signalKey } from '../src/lib/signalBoard';
import type { EnrichedPick, GameRow, OpeningSignalRow, Pick, SignalType } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (cond) {
    console.log(`  ok  ${name}`);
  } else {
    failures++;
    console.log(`FAIL  ${name}${detail ? ` — ${detail}` : ''}`);
  }
}

// mlb_moneyline action threshold is prob ≥ 0.70 AND edge ≥ 0.10 (bundled fallback).
function livePick(
  gameId: string,
  signal: SignalType,
  prob: number,
  edge: number,
): EnrichedPick {
  const pick = {
    ...pickFromOpeningSignal(makeOpen(gameId, prob, edge)),
    pick_id: Math.floor(Math.random() * 1e6) + 1, // real positive id
    signal_type: signal,
    model_probability: prob,
    edge,
  } as Pick;
  return { pick, game: null, weather: null };
}

let idSeq = 1;
function makeOpen(gameId: string, prob: number, edge: number, sport = 'MLB'): OpeningSignalRow {
  return {
    id: idSeq++,
    lock_key: `${gameId}:mlb_moneyline`,
    game_id: gameId,
    model_id: 'mlb_moneyline',
    sport,
    game_date: '2026-06-21',
    player_id: null,
    pick_side: 'home',
    pick_label: `${gameId} home ML`,
    model_probability: prob,
    dk_implied_prob: prob - edge,
    edge,
    dk_odds: -110,
    scored_line: null,
    kelly_fraction: 0.02,
    recommended_bet: 20,
    bankroll_at_pick: 1000,
    confidence_tier: 'MED',
    locked_at: '2026-06-21T11:05:00-04:00',
  } as unknown as OpeningSignalRow;
}

const gameById = new Map<string, GameRow>();
gameById.set('G_OFF', { game_id: 'G_OFF', home_team: 'BOS', away_team: 'NYY' } as GameRow);

// Live picks (current state)
const liveData: EnrichedPick[] = [
  livePick('G_LIVE', 'BET', 0.75, 0.12), // still a passing signal
  livePick('G_AVOID', 'AVOID', 0.40, -0.12), // flipped to avoid
  livePick('G_NONE', 'NONE', 0.66, 0.04), // fell to no-signal
  livePick('G_WEAK', 'BET', 0.71, 0.05), // raw BET but below the edge floor
  // G_OFF has no current row; G_FAIL's lock never cleared the filter
];

// Locked opening signals (all cleared the filter at lock except G_FAIL)
const openingRows: OpeningSignalRow[] = [
  makeOpen('G_LIVE', 0.74, 0.12),
  makeOpen('G_AVOID', 0.74, 0.12),
  makeOpen('G_NONE', 0.72, 0.11),
  makeOpen('G_WEAK', 0.72, 0.11),
  makeOpen('G_OFF', 0.73, 0.11),
  makeOpen('G_FAIL', 0.60, 0.04), // never a displayed signal → excluded
  makeOpen('G_WNBA', 0.99, 0.30, 'WNBA'), // wrong sport → ignored
];

const { live, dropped } = bucketSignals(liveData, openingRows, gameById, 'MLB');

const droppedByGame = new Map(dropped.map((d) => [d.pick.game_id, d]));

check('signalKey is side-agnostic', signalKey({ game_id: 'g', model_id: 'm', player_id: null }) === 'g|m|');
check('live bucket holds only the still-passing signal', live.length === 1 && live[0].pick.game_id === 'G_LIVE');
check('G_LIVE is not in dropped', !droppedByGame.has('G_LIVE'));
check('G_AVOID → dropped/avoid', droppedByGame.get('G_AVOID')?.droppedReason === 'avoid');
check('G_NONE → dropped/none', droppedByGame.get('G_NONE')?.droppedReason === 'none');
check('G_WEAK → dropped/weakened', droppedByGame.get('G_WEAK')?.droppedReason === 'weakened');
check('G_OFF → dropped/off_board', droppedByGame.get('G_OFF')?.droppedReason === 'off_board');
check(
  'off_board card is enriched with the game + reads inactive',
  droppedByGame.get('G_OFF')?.game?.game_id === 'G_OFF' &&
    droppedByGame.get('G_OFF')?.pick.signal_type === 'NONE' &&
    droppedByGame.get('G_OFF')!.pick.pick_id < 0,
);
check('G_FAIL (never cleared filter) is excluded', !droppedByGame.has('G_FAIL'));
check('WNBA lock ignored under MLB sport', !droppedByGame.has('G_WNBA'));
check('dropped count is exactly the four faded MLB signals', dropped.length === 4, `got ${dropped.length}`);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);

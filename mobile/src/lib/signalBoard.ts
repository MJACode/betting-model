/**
 * Signal board — the "Live | Dropped" bucketing for the Signals tab.
 *
 * The live `picks` table is delete-and-rescored every refresh, so a signal that
 * flips to AVOID / falls to no-signal / drops off the board silently disappears.
 * `opening_signals` locks the FIRST refresh a market crossed to BET and is never
 * overwritten, so it's the persistent record of "what fired today". We combine
 * that locked set with the current live pick state to bucket signals:
 *
 *   - Live    = currently a displayed signal (passes the action filter now)
 *   - Dropped = locked as a displayed signal earlier today, no longer live
 *
 * Only signals that cleared the action filter at lock are tracked (Matt's call):
 * the Dropped set mirrors what the Live tab would have shown, not every raw BET.
 */

import type { EnrichedPick, GameRow, OpeningSignalRow, Pick, SignalType } from '@/types';
import { passesActionFilter } from './thresholds';

export type DropReason = 'avoid' | 'weakened' | 'none' | 'off_board';

export type DroppedSignal = EnrichedPick & {
  droppedReason: DropReason;
  opening: OpeningSignalRow;
};

/**
 * Side-agnostic grouping key — mirrors opening_signals.lock_key
 * (`game_id:model_id[:player_id]`). A market's signal is identified by
 * game+model (+player for props); the side can flip without changing identity.
 */
export function signalKey(p: {
  game_id: string;
  model_id: string;
  player_id: string | null;
}): string {
  return `${p.game_id}|${p.model_id}|${p.player_id ?? ''}`;
}

/**
 * Rebuild a `Pick` from an opening-signal snapshot so it can run through
 * `passesActionFilter` and render in `PickCard`. `signalType` is 'BET' by
 * default (it was a BET at lock); pass 'NONE' for an off-the-board card so it
 * reads as inactive. pick_id is namespaced negative so it can never collide
 * with a real picks.pick_id.
 */
export function pickFromOpeningSignal(
  row: OpeningSignalRow,
  signalType: SignalType = 'BET',
): Pick {
  return {
    pick_id: -row.id,
    game_id: row.game_id,
    model_id: row.model_id,
    sport: row.sport,
    game_date: row.game_date,
    pick_side: row.pick_side,
    pick_label: row.pick_label,
    model_probability: row.model_probability,
    dk_implied_prob: row.dk_implied_prob ?? 0,
    edge: row.edge ?? 0,
    dk_odds: row.dk_odds,
    scored_line: row.scored_line,
    kelly_fraction: row.kelly_fraction ?? 0,
    recommended_bet: row.recommended_bet ?? 0,
    bankroll_at_pick: row.bankroll_at_pick ?? 0,
    injury_flag: null,
    injury_detail: null,
    signal_type: signalType,
    confidence_tier: row.confidence_tier,
    result: null,
    profit_flat: null,
    profit_kelly: null,
    settled_at: null,
    created_at: row.locked_at,
    player_id: row.player_id,
    pitcher_throw_hand: null,
    public_bet_pct: null,
    public_money_pct: null,
    closing_dk_odds: null,
    closing_line: null,
    clv_pct: null,
    clv_captured_at: null,
    is_live: false,
    inning_at_pick: null,
    score_diff_at_pick: null,
    dk_bet_link: null,
  };
}

/**
 * Split today's signals into Live and Dropped buckets for one sport.
 *
 * @param liveData    today's enriched picks (all signal types), from useTodayPicks
 * @param openingRows today's locked opening signals
 * @param gameById    games for the date (enriches off-the-board dropped cards)
 * @param sport       active sport filter
 */
export function bucketSignals(
  liveData: EnrichedPick[],
  openingRows: OpeningSignalRow[],
  gameById: Map<string, GameRow>,
  sport: string,
): { live: EnrichedPick[]; dropped: DroppedSignal[] } {
  const live = liveData.filter(
    (d) => d.pick.sport === sport && passesActionFilter(d.pick),
  );
  const liveKeys = new Set(live.map((d) => signalKey(d.pick)));

  // Current state of every market for the sport, keyed side-agnostically. Prefer
  // a BET row (weakened-but-still-BET should read as "weakened", not "no signal").
  const currentByKey = new Map<string, EnrichedPick>();
  for (const d of liveData) {
    if (d.pick.sport !== sport) continue;
    const k = signalKey(d.pick);
    const prev = currentByKey.get(k);
    if (!prev) {
      currentByKey.set(k, d);
    } else if (prev.pick.signal_type !== 'BET' && d.pick.signal_type === 'BET') {
      currentByKey.set(k, d);
    }
  }

  const dropped: DroppedSignal[] = [];
  const seen = new Set<string>();
  for (const row of openingRows) {
    if (row.sport !== sport) continue;
    const synth = pickFromOpeningSignal(row);
    // Only signals that cleared the action filter at lock are tracked.
    if (!passesActionFilter(synth)) continue;
    const k = signalKey(synth);
    if (liveKeys.has(k)) continue; // still live → not dropped
    if (seen.has(k)) continue; // opening rows are unique per lock_key, but guard anyway
    seen.add(k);

    const cur = currentByKey.get(k);
    let droppedReason: DropReason;
    let enriched: EnrichedPick;
    if (!cur) {
      droppedReason = 'off_board';
      enriched = {
        pick: pickFromOpeningSignal(row, 'NONE'),
        game: gameById.get(row.game_id) ?? null,
        weather: null,
      };
    } else if (cur.pick.signal_type === 'AVOID') {
      droppedReason = 'avoid';
      enriched = cur;
    } else if (cur.pick.signal_type === 'BET') {
      droppedReason = 'weakened'; // raw BET, but no longer clears the thresholds
      enriched = cur;
    } else {
      droppedReason = 'none';
      enriched = cur;
    }
    dropped.push({ ...enriched, droppedReason, opening: row });
  }

  return { live, dropped };
}

/**
 * Model-detail variant of bucketSignals, scoped to ONE model_id instead of a
 * sport — drives the "Today's potential picks" + "Dropped today" board on the
 * model detail screen.
 *
 * Unlike the Signals tab, the model list is NOT threshold-gated: Live is the raw
 * BET set (identical to the screen's previous `signal_type === 'BET'` filter), so
 * what shows today is unchanged. Dropped = a pick this model locked as BET earlier
 * today that's no longer a live BET (flipped to AVOID, fell to no-signal, or pulled
 * off the board). A finished game's row is excluded via `isOver` so picks drop off
 * once their game ends.
 *
 * @param liveData    today's enriched picks (all signal types), from useTodayPicks
 * @param openingRows today's locked opening signals
 * @param gameById    games for the date (enriches off-the-board dropped cards)
 * @param modelId     the model whose board this is
 * @param isOver      true when a game has finished (so its picks should drop off)
 */
export function bucketModelSignals(
  liveData: EnrichedPick[],
  openingRows: OpeningSignalRow[],
  gameById: Map<string, GameRow>,
  modelId: string,
  isOver: (game: GameRow | null) => boolean,
): { live: EnrichedPick[]; dropped: DroppedSignal[] } {
  const live = liveData.filter(
    (d) => d.pick.model_id === modelId && d.pick.signal_type === 'BET',
  );
  const liveKeys = new Set(live.map((d) => signalKey(d.pick)));

  // Current state of every market for this model, keyed side-agnostically. Prefer
  // a BET row so a re-fired side reads as live, not dropped.
  const currentByKey = new Map<string, EnrichedPick>();
  for (const d of liveData) {
    if (d.pick.model_id !== modelId) continue;
    const k = signalKey(d.pick);
    const prev = currentByKey.get(k);
    if (!prev) {
      currentByKey.set(k, d);
    } else if (prev.pick.signal_type !== 'BET' && d.pick.signal_type === 'BET') {
      currentByKey.set(k, d);
    }
  }

  const dropped: DroppedSignal[] = [];
  const seen = new Set<string>();
  for (const row of openingRows) {
    if (row.model_id !== modelId) continue;
    const synth = pickFromOpeningSignal(row);
    const k = signalKey(synth);
    if (liveKeys.has(k)) continue; // still a live BET → not dropped
    if (seen.has(k)) continue; // opening rows are unique per lock_key, but guard anyway
    seen.add(k);

    const cur = currentByKey.get(k);
    // Once a game ends its picks should drop off the board entirely.
    const game = cur?.game ?? gameById.get(row.game_id) ?? null;
    if (isOver(game)) continue;

    let droppedReason: DropReason;
    let enriched: EnrichedPick;
    if (!cur) {
      droppedReason = 'off_board';
      enriched = {
        pick: pickFromOpeningSignal(row, 'NONE'),
        game: gameById.get(row.game_id) ?? null,
        weather: null,
      };
    } else if (cur.pick.signal_type === 'AVOID') {
      droppedReason = 'avoid';
      enriched = cur;
    } else {
      droppedReason = 'none';
      enriched = cur;
    }
    dropped.push({ ...enriched, droppedReason, opening: row });
  }

  return { live, dropped };
}

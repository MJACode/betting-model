import { MODEL_META } from './modelMeta';
import type { PlayerStatKey } from '@/hooks/usePlayerTrends';
import type { PlayerType } from '@/types';

export interface StatChip {
  key: PlayerStatKey;
  label: string;
}

function chipsForType(modelType: 'pitcher_prop' | 'batter_prop'): StatChip[] {
  const seen = new Set<PlayerStatKey>();
  const chips: StatChip[] = [];
  for (const meta of Object.values(MODEL_META)) {
    if (meta.type !== modelType) continue;
    if (!meta.statKey || seen.has(meta.statKey)) continue;
    seen.add(meta.statKey);
    chips.push({ key: meta.statKey, label: meta.statLabel });
  }
  return chips;
}

export const BATTER_STAT_CHIPS: StatChip[] = chipsForType('batter_prop');
export const PITCHER_STAT_CHIPS: StatChip[] = chipsForType('pitcher_prop');

export function chipsForPlayerType(playerType: PlayerType): StatChip[] {
  return playerType === 'pitcher' ? PITCHER_STAT_CHIPS : BATTER_STAT_CHIPS;
}

export function defaultChip(playerType: PlayerType): PlayerStatKey {
  return chipsForPlayerType(playerType)[0]!.key;
}

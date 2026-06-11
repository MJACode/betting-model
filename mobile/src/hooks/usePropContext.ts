import { useEffect, useState } from 'react';
import { MODEL_META } from '@/lib/modelMeta';
import { fetchBatterHand, fetchLineupSlot, fetchSavantStats, fetchUmpire } from '@/lib/queries';
import type { LineupSlotRow, Pick, SavantStatsRow, UmpireRow } from '@/types';

export interface PropContext {
  savant: SavantStatsRow | null;
  batHand: string | null;
  umpire: UmpireRow | null;
  lineup: LineupSlotRow | null;
  loading: boolean;
}

const EMPTY: PropContext = { savant: null, batHand: null, umpire: null, lineup: null, loading: false };

/**
 * Matchup context for MLB prop picks: season Statcast metrics, platoon hands,
 * HP umpire (K picks), and confirmed lineup slot. All sources are features the
 * prop models already train on — this surfaces them to the user.
 * No-ops (all nulls) for game models and WNBA player props.
 */
export function usePropContext(pick: Pick): PropContext {
  const [ctx, setCtx] = useState<PropContext>({ ...EMPTY, loading: true });

  const metaType = MODEL_META[pick.model_id]?.type;
  const isPitcherProp = metaType === 'pitcher_prop';
  const isBatterProp = metaType === 'batter_prop';

  useEffect(() => {
    let mounted = true;
    if ((!isPitcherProp && !isBatterProp) || !pick.player_id) {
      setCtx(EMPTY);
      return undefined;
    }

    const season = Number(pick.game_date.slice(0, 4));
    const playerType = isPitcherProp ? 'pitcher' : 'batter';
    const settle = <T,>(p: Promise<T>): Promise<T | null> => p.catch(() => null);

    Promise.all([
      settle(fetchSavantStats(pick.player_id, playerType, season)),
      isBatterProp ? settle(fetchBatterHand(pick.player_id)) : Promise.resolve(null),
      pick.model_id === 'mlb_prop_pitcher_k'
        ? settle(fetchUmpire(pick.game_id))
        : Promise.resolve(null),
      isBatterProp ? settle(fetchLineupSlot(pick.game_id, pick.player_id)) : Promise.resolve(null),
    ]).then(([savant, batHand, umpire, lineup]) => {
      if (!mounted) return;
      setCtx({ savant, batHand, umpire, lineup, loading: false });
    });

    return () => {
      mounted = false;
    };
  }, [pick.pick_id, pick.player_id, pick.model_id, pick.game_id, pick.game_date, isPitcherProp, isBatterProp]);

  return ctx;
}

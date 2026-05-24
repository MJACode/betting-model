import { supabase } from './supabase';
import type { PlayerType } from '@/types';

export interface PlayerSearchResult {
  playerId: string;
  playerName: string;
  team: string;
  playerType: PlayerType;
}

/**
 * Case-insensitive search over `player_game_log`. Ordered by `game_date desc`
 * with `limit 200` so currently-active players surface first, then deduped by
 * `player_id` client-side (Supabase-js has no first-class DISTINCT).
 */
export async function searchPlayers(query: string): Promise<PlayerSearchResult[]> {
  const q = query.trim();
  if (q.length < 2) return [];

  const { data, error } = await supabase
    .from('player_game_log')
    .select('player_id, player_name, team, player_type')
    .ilike('player_name', `%${q}%`)
    .order('game_date', { ascending: false })
    .limit(200);

  if (error) throw error;

  const rows = (data ?? []) as Array<{
    player_id: string;
    player_name: string;
    team: string;
    player_type: PlayerType;
  }>;

  const seen = new Set<string>();
  const results: PlayerSearchResult[] = [];
  for (const r of rows) {
    if (!r.player_id || seen.has(r.player_id)) continue;
    seen.add(r.player_id);
    results.push({
      playerId: r.player_id,
      playerName: r.player_name,
      team: r.team,
      playerType: r.player_type,
    });
  }
  return results;
}

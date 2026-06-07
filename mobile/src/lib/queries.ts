import { supabase } from './supabase';
import type {
  EnrichedPick,
  GameRow,
  GameWeather,
  Pick,
  PlayerGameLogRow,
  SeasonTotalsRow,
} from '@/types';

const MLB_TOTALS_COLUMNS =
  'player_id, player_name, team, player_type, season, games_played, at_bats, ' +
  'hits, doubles, triples, home_runs, total_bases, rbi, runs, walks, strikeouts, ' +
  'stolen_bases, p_strikeouts, p_walks, p_hits_allowed, p_earned_runs, p_home_runs, ' +
  'innings_pitched, pitches';

const WNBA_TOTALS_COLUMNS =
  'player_id, player_name, team, season, games_played, minutes, points, rebounds, ' +
  'assists, threes, steals, blocks, turnovers, pra';

/**
 * Season totals for every player in a sport/season, from the season-totals
 * views. The whole set (a few hundred rows) is loaded once; the Stats screen
 * does stat-switching, ranking basis, min-games and search client-side.
 */
export async function fetchSeasonTotals(
  sport: 'MLB' | 'WNBA',
  season: number,
  playerType?: 'batter' | 'pitcher',
): Promise<SeasonTotalsRow[]> {
  if (sport === 'WNBA') {
    const { data, error } = await supabase
      .from('v_player_season_totals_wnba')
      .select(WNBA_TOTALS_COLUMNS)
      .eq('season', season);
    if (error) throw error;
    return (data ?? []) as SeasonTotalsRow[];
  }
  let q = supabase
    .from('v_player_season_totals_mlb')
    .select(MLB_TOTALS_COLUMNS)
    .eq('season', season);
  if (playerType) q = q.eq('player_type', playerType);
  const { data, error } = await q;
  if (error) throw error;
  return (data ?? []) as SeasonTotalsRow[];
}

const PICK_COLUMNS =
  'pick_id, game_id, model_id, sport, game_date, pick_side, pick_label, ' +
  'model_probability, dk_implied_prob, edge, dk_odds, scored_line, ' +
  'kelly_fraction, recommended_bet, bankroll_at_pick, injury_flag, ' +
  'injury_detail, signal_type, confidence_tier, result, profit_flat, ' +
  'profit_kelly, settled_at, created_at, player_id, pitcher_throw_hand, ' +
  'is_live, inning_at_pick, score_diff_at_pick, ' +
  'public_bet_pct, public_money_pct, ' +
  'closing_dk_odds, closing_line, clv_pct, clv_captured_at';

const GAME_COLUMNS =
  'game_id, sport, season, game_date, home_team, away_team, home_score, ' +
  'away_score, home_score_f5, away_score_f5, commence_time, home_win, ' +
  'home_win_reg, went_to_ot';

const WEATHER_COLUMNS =
  'game_id, game_date, home_team, venue, temp_f, wind_mph, wind_dir_deg, ' +
  'wind_out_component, precip_mm, is_dome_game';

export async function fetchPicksForDate(date: string): Promise<EnrichedPick[]> {
  const [picksRes, gamesRes, weatherRes] = await Promise.all([
    supabase
      .from('picks')
      .select(PICK_COLUMNS)
      .eq('game_date', date)
      .order('created_at', { ascending: false })
      .limit(2000),
    supabase.from('games').select(GAME_COLUMNS).eq('game_date', date),
    supabase.from('game_weather').select(WEATHER_COLUMNS).eq('game_date', date),
  ]);

  if (picksRes.error) throw picksRes.error;
  if (gamesRes.error) throw gamesRes.error;
  if (weatherRes.error) throw weatherRes.error;

  const picks = (picksRes.data ?? []) as Pick[];
  const games = (gamesRes.data ?? []) as GameRow[];
  const weather = (weatherRes.data ?? []) as GameWeather[];

  const gameById = new Map<string, GameRow>();
  for (const g of games) gameById.set(g.game_id, g);
  const weatherByGame = new Map<string, GameWeather>();
  for (const w of weather) weatherByGame.set(w.game_id, w);

  // Dedupe — keep the most recent pick per (game_id, model_id, pick_side).
  const seen = new Map<string, Pick>();
  for (const p of picks) {
    const key = `${p.game_id}|${p.model_id}|${p.pick_side}|${p.pick_label}`;
    if (!seen.has(key)) seen.set(key, p);
  }

  return Array.from(seen.values()).map((pick) => ({
    pick,
    game: gameById.get(pick.game_id) ?? null,
    weather: weatherByGame.get(pick.game_id) ?? null,
  }));
}

// Live (in-play) picks for today — Phase 5 scaffolding.
// Returns only picks marked is_live=true for games that are still in progress
// (commence_time has passed, no final score yet).
export async function fetchLivePicks(date: string): Promise<EnrichedPick[]> {
  const nowIso = new Date().toISOString();
  const [picksRes, gamesRes, weatherRes] = await Promise.all([
    supabase
      .from('picks')
      .select(PICK_COLUMNS)
      .eq('game_date', date)
      .eq('is_live', true)
      .order('created_at', { ascending: false })
      .limit(2000),
    supabase
      .from('games')
      .select(GAME_COLUMNS)
      .eq('game_date', date)
      .lte('commence_time', nowIso)
      .is('home_score', null),
    supabase.from('game_weather').select(WEATHER_COLUMNS).eq('game_date', date),
  ]);

  if (picksRes.error) throw picksRes.error;
  if (gamesRes.error) throw gamesRes.error;
  if (weatherRes.error) throw weatherRes.error;

  const picks = (picksRes.data ?? []) as Pick[];
  const games = (gamesRes.data ?? []) as GameRow[];
  const weather = (weatherRes.data ?? []) as GameWeather[];

  // Restrict picks to games we just confirmed are in-progress.
  const liveGameIds = new Set(games.map((g) => g.game_id));
  const gameById = new Map<string, GameRow>();
  for (const g of games) gameById.set(g.game_id, g);
  const weatherByGame = new Map<string, GameWeather>();
  for (const w of weather) weatherByGame.set(w.game_id, w);

  return picks
    .filter((p) => liveGameIds.has(p.game_id))
    .map((pick) => ({
      pick,
      game: gameById.get(pick.game_id) ?? null,
      weather: weatherByGame.get(pick.game_id) ?? null,
    }));
}

export async function fetchPickById(pickId: number): Promise<EnrichedPick | null> {
  const { data, error } = await supabase
    .from('picks')
    .select(PICK_COLUMNS)
    .eq('pick_id', pickId)
    .single();
  if (error) throw error;
  if (!data) return null;
  const pick = data as Pick;
  const [gameRes, weatherRes] = await Promise.all([
    supabase.from('games').select(GAME_COLUMNS).eq('game_id', pick.game_id).maybeSingle(),
    supabase.from('game_weather').select(WEATHER_COLUMNS).eq('game_id', pick.game_id).maybeSingle(),
  ]);
  return {
    pick,
    game: (gameRes.data as GameRow | null) ?? null,
    weather: (weatherRes.data as GameWeather | null) ?? null,
  };
}

export async function fetchSettledPicks(startDate: string, endDate: string): Promise<Pick[]> {
  const { data, error } = await supabase
    .from('picks')
    .select(PICK_COLUMNS)
    .gte('game_date', startDate)
    .lte('game_date', endDate)
    .not('result', 'is', null)
    .order('game_date', { ascending: false })
    .limit(5000);
  if (error) throw error;
  return (data ?? []) as Pick[];
}

export async function fetchTeamRecentGames(team: string, beforeDate: string, limit = 25): Promise<GameRow[]> {
  const { data, error } = await supabase
    .from('games')
    .select(GAME_COLUMNS)
    .or(`home_team.eq.${team},away_team.eq.${team}`)
    .lt('game_date', beforeDate)
    .not('home_score', 'is', null)
    .order('game_date', { ascending: false })
    .limit(limit);
  if (error) throw error;
  return (data ?? []) as GameRow[];
}

export async function fetchPlayerRecentGames(
  playerId: string,
  beforeDate: string,
  limit = 25,
): Promise<PlayerGameLogRow[]> {
  const { data, error } = await supabase
    .from('player_game_log')
    .select(
      'player_id, player_name, team, player_type, game_id, game_date, season, ' +
        'innings_pitched, p_strikeouts, p_walks, p_hits_allowed, p_earned_runs, ' +
        'p_home_runs, at_bats, hits, doubles, triples, home_runs, rbi, runs, ' +
        'walks, strikeouts, stolen_bases, total_bases, batting_order',
    )
    .eq('player_id', playerId)
    .lt('game_date', beforeDate)
    .order('game_date', { ascending: false })
    .limit(limit);
  if (error) throw error;
  return (data ?? []) as PlayerGameLogRow[];
}

export async function fetchPlayerByName(
  playerName: string,
  beforeDate: string,
  limit = 25,
): Promise<PlayerGameLogRow[]> {
  const { data, error } = await supabase
    .from('player_game_log')
    .select(
      'player_id, player_name, team, player_type, game_id, game_date, season, ' +
        'innings_pitched, p_strikeouts, p_walks, p_hits_allowed, p_earned_runs, ' +
        'p_home_runs, at_bats, hits, doubles, triples, home_runs, rbi, runs, ' +
        'walks, strikeouts, stolen_bases, total_bases, batting_order',
    )
    .ilike('player_name', playerName)
    .lt('game_date', beforeDate)
    .order('game_date', { ascending: false })
    .limit(limit);
  if (error) throw error;
  return (data ?? []) as PlayerGameLogRow[];
}

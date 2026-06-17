import { supabase } from './supabase';
import { gameMarketForModel } from './markets';
import type {
  EnrichedPick,
  FighterRow,
  FightLogRow,
  GameRow,
  GameWeather,
  LatestDkOddsRow,
  LineupSlotRow,
  ModelRegistryRow,
  OddsSnapshotRow,
  Pick,
  PlayerGameLogRow,
  PlayerType,
  PropOddsSnapshotRow,
  SavantStatsRow,
  SeasonTotalsRow,
  UmpireRow,
} from '@/types';

const MLB_TOTALS_COLUMNS =
  'player_id, player_name, team, player_type, season, games_played, at_bats, ' +
  'hits, doubles, triples, home_runs, total_bases, rbi, runs, walks, strikeouts, ' +
  'stolen_bases, p_strikeouts, p_walks, p_hits_allowed, p_earned_runs, p_home_runs, ' +
  'innings_pitched, pitches';

const WNBA_TOTALS_COLUMNS =
  'player_id, player_name, team, season, games_played, minutes, points, rebounds, ' +
  'assists, threes, steals, blocks, turnovers, pra';

const UFC_TOTALS_COLUMNS =
  'player_id, player_name, team, season, games_played, wins, ko_wins, sub_wins, ' +
  'sig_strikes, takedowns, knockdowns, sub_attempts';

/**
 * Season totals for every player in a sport/season, from the season-totals
 * views. The whole set (a few hundred rows) is loaded once; the Stats screen
 * does stat-switching, ranking basis, min-games and search client-side.
 */
export async function fetchSeasonTotals(
  sport: 'MLB' | 'WNBA' | 'UFC' | 'GOLF',
  season: number,
  playerType?: 'batter' | 'pitcher',
): Promise<SeasonTotalsRow[]> {
  if (sport === 'GOLF') return []; // no golf leaderboard v1
  if (sport === 'UFC') {
    const { data, error } = await supabase
      .from('v_fighter_season_totals_ufc')
      .select(UFC_TOTALS_COLUMNS)
      .eq('season', season);
    if (error) throw error;
    return (data ?? []) as SeasonTotalsRow[];
  }
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

/**
 * Per-player stat totals over each player's last N games (`window`), or the
 * full season when `window` is null. Backed by the player_window_totals_*
 * RPCs, which rank each player's most recent games server-side. Same row
 * shape as fetchSeasonTotals — the Stats screen ranks/searches client-side.
 */
export async function fetchWindowTotals(
  sport: 'MLB' | 'WNBA' | 'UFC' | 'GOLF',
  season: number,
  window: number | null,
  playerType?: 'batter' | 'pitcher',
): Promise<SeasonTotalsRow[]> {
  if (sport === 'GOLF') return []; // no golf leaderboard v1
  if (sport === 'UFC') {
    // Fighters fight a handful of times a year, so the window ranks each
    // fighter's last N fights CAREER-WIDE (season only applies to totals mode).
    const { data, error } = await supabase.rpc('fighter_window_totals_ufc', {
      p_season: season,
      p_window: window,
    });
    if (error) throw error;
    return (data ?? []) as SeasonTotalsRow[];
  }
  if (sport === 'WNBA') {
    const { data, error } = await supabase.rpc('player_window_totals_wnba', {
      p_season: season,
      p_window: window,
    });
    if (error) throw error;
    return (data ?? []) as SeasonTotalsRow[];
  }
  const { data, error } = await supabase.rpc('player_window_totals_mlb', {
    p_season: season,
    p_player_type: playerType ?? 'batter',
    p_window: window,
  });
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
  'closing_dk_odds, closing_line, clv_pct, clv_captured_at, dk_bet_link';

const GAME_COLUMNS =
  'game_id, sport, season, game_date, home_team, away_team, home_score, ' +
  'away_score, home_score_f5, away_score_f5, commence_time, home_win, ' +
  'home_win_reg, went_to_ot';

const WEATHER_COLUMNS =
  'game_id, game_date, home_team, venue, temp_f, wind_mph, wind_dir_deg, ' +
  'wind_out_component, precip_mm, is_dome_game';

const LATEST_ODDS_COLUMNS =
  'game_id, game_date, market, home_price, away_price, spread_home, total_line, ' +
  'over_price, under_price, snapshot_at';

/** Freshest DK snapshot per game+market for a date (v_latest_dk_odds). */
export async function fetchLatestDkOddsForDate(date: string): Promise<LatestDkOddsRow[]> {
  const { data, error } = await supabase
    .from('v_latest_dk_odds')
    .select(LATEST_ODDS_COLUMNS)
    .eq('game_date', date);
  if (error) throw error;
  return (data ?? []) as LatestDkOddsRow[];
}

export async function fetchPicksForDate(date: string): Promise<EnrichedPick[]> {
  const [picksRes, gamesRes, weatherRes, latestOddsRes] = await Promise.all([
    supabase
      .from('picks')
      .select(PICK_COLUMNS)
      .eq('game_date', date)
      // In-play picks live on the Live tab only — they churn with every
      // inning and would otherwise mix into the locked pre-game board.
      .not('is_live', 'is', true)
      .order('created_at', { ascending: false })
      .limit(2000),
    supabase.from('games').select(GAME_COLUMNS).eq('game_date', date),
    supabase.from('game_weather').select(WEATHER_COLUMNS).eq('game_date', date),
    supabase.from('v_latest_dk_odds').select(LATEST_ODDS_COLUMNS).eq('game_date', date),
  ]);

  if (picksRes.error) throw picksRes.error;
  if (gamesRes.error) throw gamesRes.error;
  if (weatherRes.error) throw weatherRes.error;
  // Latest odds are enrichment only — a failure shouldn't take down the picks list.
  const latestOdds = (latestOddsRes.error ? [] : (latestOddsRes.data ?? [])) as LatestDkOddsRow[];

  const picks = (picksRes.data ?? []) as Pick[];
  const games = (gamesRes.data ?? []) as GameRow[];
  const weather = (weatherRes.data ?? []) as GameWeather[];

  const gameById = new Map<string, GameRow>();
  for (const g of games) gameById.set(g.game_id, g);
  const weatherByGame = new Map<string, GameWeather>();
  for (const w of weather) weatherByGame.set(w.game_id, w);
  const oddsByGameMarket = new Map<string, LatestDkOddsRow>();
  for (const o of latestOdds) oddsByGameMarket.set(`${o.game_id}|${o.market}`, o);

  // Dedupe — keep the most recent pick per (game_id, model_id, pick_side).
  const seen = new Map<string, Pick>();
  for (const p of picks) {
    const key = `${p.game_id}|${p.model_id}|${p.pick_side}|${p.pick_label}`;
    if (!seen.has(key)) seen.set(key, p);
  }

  return Array.from(seen.values()).map((pick) => {
    const market = gameMarketForModel(pick.model_id);
    return {
      pick,
      game: gameById.get(pick.game_id) ?? null,
      weather: weatherByGame.get(pick.game_id) ?? null,
      latestOdds: market ? (oddsByGameMarket.get(`${pick.game_id}|${market}`) ?? null) : null,
    };
  });
}

/**
 * Upcoming UFC picks AFTER `afterDate` through `throughDate`. UFC events are
 * weekly and the scorer prices them up to UFC_SCORE_AHEAD_DAYS early, so the
 * UFC tab shows the next card instead of sitting empty until fight day.
 * Same enrichment shape as fetchPicksForDate (UFC has no weather rows).
 */
export async function fetchUpcomingUfcPicks(
  afterDate: string,
  throughDate: string,
): Promise<EnrichedPick[]> {
  const [picksRes, gamesRes, latestOddsRes] = await Promise.all([
    supabase
      .from('picks')
      .select(PICK_COLUMNS)
      .eq('sport', 'UFC')
      .gt('game_date', afterDate)
      .lte('game_date', throughDate)
      .order('created_at', { ascending: false })
      .limit(500),
    supabase
      .from('games')
      .select(GAME_COLUMNS)
      .eq('sport', 'UFC')
      .gt('game_date', afterDate)
      .lte('game_date', throughDate),
    supabase
      .from('v_latest_dk_odds')
      .select(LATEST_ODDS_COLUMNS)
      .gt('game_date', afterDate)
      .lte('game_date', throughDate),
  ]);

  if (picksRes.error) throw picksRes.error;
  if (gamesRes.error) throw gamesRes.error;
  const latestOdds = (latestOddsRes.error ? [] : (latestOddsRes.data ?? [])) as LatestDkOddsRow[];

  const picks = (picksRes.data ?? []) as Pick[];
  const games = (gamesRes.data ?? []) as GameRow[];

  const gameById = new Map<string, GameRow>();
  for (const g of games) gameById.set(g.game_id, g);
  const oddsByGameMarket = new Map<string, LatestDkOddsRow>();
  for (const o of latestOdds) oddsByGameMarket.set(`${o.game_id}|${o.market}`, o);

  const seen = new Map<string, Pick>();
  for (const p of picks) {
    const key = `${p.game_id}|${p.model_id}|${p.pick_side}|${p.pick_label}`;
    if (!seen.has(key)) seen.set(key, p);
  }

  return Array.from(seen.values()).map((pick) => {
    const market = gameMarketForModel(pick.model_id);
    return {
      pick,
      game: gameById.get(pick.game_id) ?? null,
      weather: null,
      latestOdds: market ? (oddsByGameMarket.get(`${pick.game_id}|${market}`) ?? null) : null,
    };
  });
}

/**
 * Upcoming GOLF picks AFTER `afterDate` through `throughDate`. Tournaments are
 * weekly and the scorer prices them up to GOLF_SCORE_AHEAD_DAYS early, so the
 * Golf tab shows the upcoming event instead of sitting empty until Thursday.
 * Same enrichment shape as fetchUpcomingUfcPicks (golf has no weather rows).
 */
export async function fetchUpcomingGolfPicks(
  afterDate: string,
  throughDate: string,
): Promise<EnrichedPick[]> {
  const [picksRes, gamesRes] = await Promise.all([
    supabase
      .from('picks')
      .select(PICK_COLUMNS)
      .eq('sport', 'GOLF')
      .gte('game_date', afterDate)
      .lte('game_date', throughDate)
      .order('created_at', { ascending: false })
      .limit(3000),
    supabase
      .from('games')
      .select(GAME_COLUMNS)
      .eq('sport', 'GOLF')
      .gte('game_date', afterDate)
      .lte('game_date', throughDate),
  ]);

  if (picksRes.error) throw picksRes.error;
  if (gamesRes.error) throw gamesRes.error;

  const picks = (picksRes.data ?? []) as Pick[];
  const games = (gamesRes.data ?? []) as GameRow[];

  const gameById = new Map<string, GameRow>();
  for (const g of games) gameById.set(g.game_id, g);

  const seen = new Map<string, Pick>();
  for (const p of picks) {
    const key = `${p.game_id}|${p.model_id}|${p.pick_side}|${p.pick_label}`;
    if (!seen.has(key)) seen.set(key, p);
  }

  return Array.from(seen.values()).map((pick) => ({
    pick,
    game: gameById.get(pick.game_id) ?? null,
    weather: null,
    latestOdds: null,
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

// ── Line movement ───────────────────────────────────────────────────────────

/** All DK snapshots for one game+market, oldest first (line movement history). */
export async function fetchOddsHistory(gameId: string, market: string): Promise<OddsSnapshotRow[]> {
  const { data, error } = await supabase
    .from('odds')
    .select('market, snapshot_at, home_price, away_price, spread_home, total_line, over_price, under_price')
    .eq('game_id', gameId)
    .eq('market', market)
    .eq('bookmaker', 'draftkings')
    .order('snapshot_at', { ascending: true })
    .limit(50);
  if (error) throw error;
  return (data ?? []) as OddsSnapshotRow[];
}

/** All DK prop-line snapshots for one player+market in a game, oldest first. */
export async function fetchPropOddsHistory(
  gameId: string,
  market: string,
  playerName: string,
): Promise<PropOddsSnapshotRow[]> {
  const { data, error } = await supabase
    .from('player_prop_odds')
    .select('snapshot_at, line, over_price, under_price')
    .eq('game_id', gameId)
    .eq('market', market)
    .eq('bookmaker', 'draftkings')
    .eq('player_name', playerName)
    .order('snapshot_at', { ascending: true })
    .limit(50);
  if (error) throw error;
  return (data ?? []) as PropOddsSnapshotRow[];
}

// ── Prop matchup context ────────────────────────────────────────────────────

const SAVANT_COLUMNS =
  'player_id, player_type, season, k_pct, whiff_pct, csw_pct, xera, avg_velocity, ' +
  'gb_pct, barrel_pct, hard_hit_pct, xba, xslg, launch_angle, sprint_speed';

/** Season Statcast metrics; falls back to the prior season early in the year. */
export async function fetchSavantStats(
  playerId: string,
  playerType: PlayerType,
  season: number,
): Promise<SavantStatsRow | null> {
  for (const s of [season, season - 1]) {
    const { data, error } = await supabase
      .from('player_savant_stats')
      .select(SAVANT_COLUMNS)
      .eq('player_id', playerId)
      .eq('player_type', playerType)
      .eq('season', s)
      .maybeSingle();
    if (error) throw error;
    if (data) return data as SavantStatsRow;
  }
  return null;
}

export async function fetchBatterHand(playerId: string): Promise<string | null> {
  const { data, error } = await supabase
    .from('player_handedness')
    .select('bat_hand')
    .eq('player_id', playerId)
    .maybeSingle();
  if (error) throw error;
  return (data as { bat_hand: string | null } | null)?.bat_hand ?? null;
}

export async function fetchUmpire(gameId: string): Promise<UmpireRow | null> {
  const { data, error } = await supabase
    .from('umpires')
    .select('umpire_name, k_per_game, k_plus_minus')
    .eq('game_id', gameId)
    .maybeSingle();
  if (error) throw error;
  return (data as UmpireRow | null) ?? null;
}

/** Latest lineup slot for a player in a game (batting order + confirmation). */
export async function fetchLineupSlot(gameId: string, playerId: string): Promise<LineupSlotRow | null> {
  const { data, error } = await supabase
    .from('lineup_slots')
    .select('batting_order, position, hand, is_confirmed, snapshot_at')
    .eq('game_id', gameId)
    .eq('player_id', playerId)
    .order('snapshot_at', { ascending: false })
    .limit(1);
  if (error) throw error;
  const rows = (data ?? []) as (LineupSlotRow & { snapshot_at: string })[];
  return rows[0] ?? null;
}

// ── Model transparency ──────────────────────────────────────────────────────

/** Latest active registry row for a model (holdout metrics, version). */
export async function fetchModelRegistry(modelId: string): Promise<ModelRegistryRow | null> {
  const { data, error } = await supabase
    .from('model_registry')
    .select(
      'model_id, version, trained_on, holdout_season, holdout_accuracy, ' +
        'holdout_roi, holdout_picks, calibration_score, created_at',
    )
    .eq('model_id', modelId)
    .eq('is_active', 1)
    .order('created_at', { ascending: false })
    .limit(1);
  if (error) throw error;
  const rows = (data ?? []) as (ModelRegistryRow & { created_at: string })[];
  return rows[0] ?? null;
}

// ── UFC tale of the tape ────────────────────────────────────────────────────

/** Fighter profile by display name (exact match first, then case-insensitive). */
export async function fetchFighterByName(name: string): Promise<FighterRow | null> {
  const cols = 'fighter_id, name, height_in, reach_in, stance, dob';
  const exact = await supabase.from('fighters').select(cols).eq('name', name).limit(1);
  if (exact.error) throw exact.error;
  if (exact.data && exact.data.length > 0) return exact.data[0] as FighterRow;
  const loose = await supabase.from('fighters').select(cols).ilike('name', name).limit(1);
  if (loose.error) throw loose.error;
  return ((loose.data ?? [])[0] as FighterRow | undefined) ?? null;
}

export async function fetchFighterRecentFights(
  fighterId: string,
  beforeDate: string,
  limit = 5,
): Promise<FightLogRow[]> {
  const { data, error } = await supabase
    .from('ufc_fight_log')
    .select('game_id, game_date, result, method, end_round')
    .eq('fighter_id', fighterId)
    .lt('game_date', beforeDate)
    .order('game_date', { ascending: false })
    .limit(limit);
  if (error) throw error;
  return (data ?? []) as FightLogRow[];
}

import { supabase } from './supabase';
import { gameMarketForModel, lineShopForPick } from './markets';
import type { ServerThreshold } from './thresholds';

/** Raw row shape of the model_action_thresholds table. */
interface ActionThresholdRow {
  model_id: string;
  min_prob: number;
  min_edge: number;
  min_odds: number | null;
  prob_only: boolean;
  paused: boolean;
}
import type {
  EnrichedPick,
  FighterRow,
  FightLogRow,
  GameRow,
  GameWeather,
  LatestDkOddsRow,
  LineupSlotRow,
  LiveGameStateRow,
  ModelRegistryRow,
  OddsByBookRow,
  OddsSnapshotRow,
  OpeningVsLiveRow,
  OpeningSliceRow,
  ParlayTrackRow,
  Pick,
  PlayerGameLogRow,
  PlayerType,
  PropOddsSnapshotRow,
  RecentGameRow,
  SavantStatsRow,
  SeasonTotalsRow,
  TonightMatchupRow,
  TrackRecordDailyRow,
  TrackRecordRow,
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

// NBA season-totals view has the same basketball column shape as WNBA.
const NBA_TOTALS_COLUMNS = WNBA_TOTALS_COLUMNS;

const UFC_TOTALS_COLUMNS =
  'player_id, player_name, team, season, games_played, wins, ko_wins, sub_wins, ' +
  'sig_strikes, takedowns, knockdowns, sub_attempts';

/**
 * Season totals for every player in a sport/season, from the season-totals
 * views. The whole set (a few hundred rows) is loaded once; the Stats screen
 * does stat-switching, ranking basis, min-games and search client-side.
 */
export async function fetchSeasonTotals(
  sport: 'MLB' | 'WNBA' | 'NBA' | 'UFC' | 'GOLF' | 'NHL',
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
  if (sport === 'NBA') {
    const { data, error } = await supabase
      .from('v_player_season_totals_nba')
      .select(NBA_TOTALS_COLUMNS)
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
 * Tonight's matchups for the Stats tab: one row per team side of today's (ET)
 * games with opponent strength — MLB from v_mlb_tonight_matchups (opposing
 * probable starter + opposing lineup), WNBA from v_wnba_tonight_matchups
 * (opponent defense/pace). Other sports return [] (no matchup view yet).
 */
export async function fetchTonightMatchups(
  sport: 'MLB' | 'WNBA' | 'NBA' | 'UFC' | 'GOLF' | 'NHL',
): Promise<TonightMatchupRow[]> {
  if (sport !== 'MLB' && sport !== 'WNBA') return [];
  const view = sport === 'MLB' ? 'v_mlb_tonight_matchups' : 'v_wnba_tonight_matchups';
  const { data, error } = await supabase.from(view).select('*');
  if (error) throw error;
  return (data ?? []) as unknown as TonightMatchupRow[];
}

/**
 * Per-player stat totals over each player's last N games (`window`), or the
 * full season when `window` is null. Backed by the player_window_totals_*
 * RPCs, which rank each player's most recent games server-side. Same row
 * shape as fetchSeasonTotals — the Stats screen ranks/searches client-side.
 */
export async function fetchWindowTotals(
  sport: 'MLB' | 'WNBA' | 'NBA' | 'UFC' | 'GOLF' | 'NHL',
  season: number,
  window: number | null,
  playerType?: 'batter' | 'pitcher',
): Promise<SeasonTotalsRow[]> {
  if (sport === 'NHL') {
    // No per-player skater leaderboard for NHL (team + goalie stats only).
    return [];
  }
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
  if (sport === 'NBA') {
    const { data, error } = await supabase.rpc('player_window_totals_nba', {
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

/**
 * Raw last-N per-game rows per player (newest-first), backing the Stats tab
 * "Hit Rate" mode. The screen groups by player and computes "X of N games over
 * the line" + the per-game dot strip client-side, for any stat/threshold.
 * Only MLB/WNBA/NBA have per-game logs; other sports return []. N is capped at
 * 25 server-side.
 */
export async function fetchRecentGames(
  sport: 'MLB' | 'WNBA' | 'NBA' | 'UFC' | 'GOLF' | 'NHL',
  season: number,
  window: number,
  playerType?: 'batter' | 'pitcher',
): Promise<RecentGameRow[]> {
  if (sport === 'WNBA') {
    const { data, error } = await supabase.rpc('player_recent_games_wnba', {
      p_season: season,
      p_window: window,
    });
    if (error) throw error;
    return (data ?? []) as RecentGameRow[];
  }
  if (sport === 'NBA') {
    const { data, error } = await supabase.rpc('player_recent_games_nba', {
      p_season: season,
      p_window: window,
    });
    if (error) throw error;
    return (data ?? []) as RecentGameRow[];
  }
  if (sport === 'MLB') {
    const { data, error } = await supabase.rpc('player_recent_games_mlb', {
      p_season: season,
      p_player_type: playerType ?? 'batter',
      p_window: window,
    });
    if (error) throw error;
    return (data ?? []) as RecentGameRow[];
  }
  return []; // UFC / NHL / GOLF: no per-game player logs
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

const ODDS_BY_BOOK_COLUMNS =
  'game_id, game_date, market, bookmaker, home_price, away_price, over_price, ' +
  'under_price, spread_home, total_line, home_link, away_link, over_link, ' +
  'under_link, snapshot_at';

const LIVE_STATE_COLUMNS =
  'game_id, game_date, snapshot_at, inning, inning_half, outs, bases_state, ' +
  'home_score, away_score, abstract_game_state';

/**
 * Freshest in-play state per game for a date (v_live_game_state_latest).
 * Drives the live score + inning on the pick cards. MLB only — that's the only
 * sport the live poller covers, so other sports return no rows.
 */
export async function fetchLiveGameStates(date: string): Promise<LiveGameStateRow[]> {
  const { data, error } = await supabase
    .from('v_live_game_state_latest')
    .select(LIVE_STATE_COLUMNS)
    .eq('game_date', date);
  if (error) throw error;
  return (data ?? []) as unknown as LiveGameStateRow[];
}

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
  const [picksRes, gamesRes, weatherRes, latestOddsRes, allBooksRes] = await Promise.all([
    supabase
      .from('picks')
      .select(PICK_COLUMNS)
      .eq('game_date', date)
      // In-play picks live on the Live tab only — they churn with every
      // inning and would otherwise mix into the locked pre-game board.
      .not('is_live', 'is', true)
      // Order BET/AVOID before NONE so signals are NEVER dropped by the row cap.
      // ('AVOID' < 'BET' < 'NONE' alphabetically.) The day's NONE prop rows can
      // exceed the cap by evening; without this, the morning's locked game
      // signals (oldest rows) fell off a created_at-only ordering and vanished.
      .order('signal_type', { ascending: true })
      .order('created_at', { ascending: false })
      .limit(5000),
    supabase.from('games').select(GAME_COLUMNS).eq('game_date', date),
    supabase.from('game_weather').select(WEATHER_COLUMNS).eq('game_date', date),
    supabase.from('v_latest_dk_odds').select(LATEST_ODDS_COLUMNS).eq('game_date', date),
    supabase.from('v_latest_odds_all_books').select(ODDS_BY_BOOK_COLUMNS).eq('game_date', date),
  ]);

  if (picksRes.error) throw picksRes.error;
  if (gamesRes.error) throw gamesRes.error;
  if (weatherRes.error) throw weatherRes.error;
  // Latest odds are enrichment only — a failure shouldn't take down the picks list.
  const latestOdds = (latestOddsRes.error ? [] : (latestOddsRes.data ?? [])) as LatestDkOddsRow[];
  const allBooks = (allBooksRes.error ? [] : (allBooksRes.data ?? [])) as OddsByBookRow[];

  const picks = (picksRes.data ?? []) as Pick[];
  const games = (gamesRes.data ?? []) as GameRow[];
  const weather = (weatherRes.data ?? []) as GameWeather[];

  const gameById = new Map<string, GameRow>();
  for (const g of games) gameById.set(g.game_id, g);
  const weatherByGame = new Map<string, GameWeather>();
  for (const w of weather) weatherByGame.set(w.game_id, w);
  const oddsByGameMarket = new Map<string, LatestDkOddsRow>();
  for (const o of latestOdds) oddsByGameMarket.set(`${o.game_id}|${o.market}`, o);
  // All-book rows grouped by game+market for line shopping.
  const booksByGameMarket = new Map<string, OddsByBookRow[]>();
  for (const o of allBooks) {
    const key = `${o.game_id}|${o.market}`;
    const list = booksByGameMarket.get(key) ?? [];
    list.push(o);
    booksByGameMarket.set(key, list);
  }

  // Dedupe — keep the most recent pick per (game_id, model_id, pick_side).
  const seen = new Map<string, Pick>();
  for (const p of picks) {
    const key = `${p.game_id}|${p.model_id}|${p.pick_side}|${p.pick_label}`;
    if (!seen.has(key)) seen.set(key, p);
  }

  return Array.from(seen.values()).map((pick) => {
    const market = gameMarketForModel(pick.model_id);
    const bookRows = market ? (booksByGameMarket.get(`${pick.game_id}|${market}`) ?? []) : [];
    return {
      pick,
      game: gameById.get(pick.game_id) ?? null,
      weather: weatherByGame.get(pick.game_id) ?? null,
      latestOdds: market ? (oddsByGameMarket.get(`${pick.game_id}|${market}`) ?? null) : null,
      bestOdds: bookRows.length ? lineShopForPick(pick, bookRows) : null,
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
      // Live tab shows only actionable, recommended bets — AVOID (fade) picks
      // are still written + settled for model tracking, just not surfaced here.
      .eq('signal_type', 'BET')
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

// Every is_live pick row (settled AND unsettled) for a set of games. Used to
// grade tracked live bets: their pick_id churns, so we resolve by game.
export async function fetchLivePicksForGames(gameIds: string[]): Promise<Pick[]> {
  if (gameIds.length === 0) return [];
  const out: Pick[] = [];
  for (let i = 0; i < gameIds.length; i += 200) {
    const chunk = gameIds.slice(i, i + 200);
    const { data, error } = await supabase
      .from('picks')
      .select(PICK_COLUMNS)
      .eq('is_live', true)
      .in('game_id', chunk);
    if (error) throw error;
    out.push(...((data ?? []) as unknown as Pick[]));
  }
  return out;
}

// Games by id (for tracked-live final detection: home_score != null = final).
export async function fetchGamesByIds(gameIds: string[]): Promise<GameRow[]> {
  if (gameIds.length === 0) return [];
  const out: GameRow[] = [];
  for (let i = 0; i < gameIds.length; i += 200) {
    const chunk = gameIds.slice(i, i + 200);
    const { data, error } = await supabase
      .from('games')
      .select(GAME_COLUMNS)
      .in('game_id', chunk);
    if (error) throw error;
    out.push(...((data ?? []) as unknown as GameRow[]));
  }
  return out;
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

// All non-live picks for a single day (settled AND unsettled). The daily recap
// uses this instead of fetchSettledPicks so it can also count BET picks that are
// still awaiting a result (result NULL) — otherwise placed-but-ungraded picks
// silently vanish and the pick count looks wrong.
export async function fetchDayPicks(date: string): Promise<Pick[]> {
  const { data, error } = await supabase
    .from('picks')
    .select(PICK_COLUMNS)
    .eq('game_date', date)
    .not('is_live', 'is', true)
    // BET/AVOID before NONE so signals are never dropped by the row cap.
    .order('signal_type', { ascending: true })
    .order('created_at', { ascending: false })
    .limit(5000);
  if (error) throw error;
  return (data ?? []) as Pick[];
}

/** All games for one day — the daily recap lists every game the models scored
 *  (joined client-side to that day's pick rows). */
export async function fetchDayGames(date: string): Promise<GameRow[]> {
  const { data, error } = await supabase
    .from('games')
    .select(GAME_COLUMNS)
    .eq('game_date', date)
    .limit(500);
  if (error) throw error;
  return (data ?? []) as unknown as GameRow[];
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

/** Batch-hydrate picks by id — used to score the user's tracked bets on the
 *  Performance tab. Chunked so a long-lived tracked set never builds an
 *  oversized IN() filter. Ids with no matching pick are simply absent. */
export async function fetchPicksByIds(ids: number[]): Promise<Pick[]> {
  if (ids.length === 0) return [];
  const out: Pick[] = [];
  for (let i = 0; i < ids.length; i += 200) {
    const chunk = ids.slice(i, i + 200);
    const { data, error } = await supabase.from('picks').select(PICK_COLUMNS).in('pick_id', chunk);
    if (error) throw error;
    out.push(...((data ?? []) as unknown as Pick[]));
  }
  return out;
}

// Per-model FULL-OUTCOME record: every scored MLB pick (BET + dead-zone NONE +
// AVOID) graded from final scores / player_game_log actuals at the CURRENT cut.
// Fixes the Models-tab undercount where only historically-BET-classified picks
// were settled (so a looser current cut showed 2 picks when the true sample is 44).
export interface FullOutcomeRecord {
  model_id: string;
  paused: boolean;
  prob_only: boolean;
  bets: number;
  wins: number;
  losses: number;
  pushes: number;
  priced_bets: number;
  units: number;
  roi_pct: number | null;
}

export async function fetchModelFullOutcomeRecord(): Promise<Record<string, FullOutcomeRecord>> {
  const { data, error } = await supabase.from('v_model_full_outcome_record').select('*');
  if (error) throw error;
  const map: Record<string, FullOutcomeRecord> = {};
  for (const r of (data ?? []) as unknown as FullOutcomeRecord[]) map[r.model_id] = r;
  return map;
}

// One row per pick behind a model's full-outcome record — the exact pick set
// v_model_full_outcome_record aggregates (every scored pick graded at the
// CURRENT cut, decided outcomes only). profit_units is 1-unit flat at dk_odds,
// NULL when the pick had no real price (prob-only HR) so P&L is never fabricated.
export interface FullOutcomePickRow {
  pick_id: number;
  model_id: string;
  game_date: string;
  game_id: string;
  pick_label: string;
  pick_side: string;
  model_probability: number;
  edge: number | null;
  dk_odds: number | null;
  scored_line: number | null;
  result: 'WIN' | 'LOSS' | 'PUSH';
  profit_units: number | null;
}

export async function fetchModelFullOutcomePicks(modelId: string): Promise<FullOutcomePickRow[]> {
  const { data, error } = await supabase
    .from('v_model_full_outcome_picks')
    .select('*')
    .eq('model_id', modelId)
    .order('game_date', { ascending: false })
    .order('pick_id', { ascending: false })
    .limit(1000);
  if (error) throw error;
  return (data ?? []) as unknown as FullOutcomePickRow[];
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

// ── Parlay correlations (copula engine, Phase 2) ────────────────────────────

export interface ParlayCorrelationRow {
  sport: string;
  market_class_a: string;
  market_class_b: string;
  relationship: string;
  rho: number | string;
}

/** Empirical/prior correlation coefficients overlaid on the bundled priors. */
export async function fetchParlayCorrelations(): Promise<ParlayCorrelationRow[]> {
  const { data, error } = await supabase
    .from('parlay_correlations')
    .select('sport, market_class_a, market_class_b, relationship, rho');
  if (error) throw error;
  return (data ?? []) as unknown as ParlayCorrelationRow[];
}

/**
 * Latest team abbreviation per player_id (for same-team vs opposing in parlays).
 * Looks across MLB + NBA + WNBA game logs — id namespaces don't overlap (MLBAM
 * vs nba_api), so a given id resolves from exactly one table. Each query is
 * failure-tolerant: a single sport's log going down still resolves the others.
 */
export async function fetchPlayerTeams(playerIds: string[]): Promise<Record<string, string>> {
  const ids = Array.from(new Set(playerIds.filter((id) => !!id)));
  if (ids.length === 0) return {};
  const tables = ['player_game_log', 'nba_player_game_log', 'wnba_player_game_log'];
  const results = await Promise.all(
    tables.map((t) =>
      supabase
        .from(t)
        .select('player_id, team, game_date')
        .in('player_id', ids)
        .order('game_date', { ascending: false }),
    ),
  );
  // Latest team per id within each table (rows are date-desc → first wins).
  const perTable = results.map((res) => {
    const m = new Map<string, string>();
    if (res.error) return m; // skip a failed sport; keep the others
    const rows = (res.data ?? []) as unknown as { player_id: string; team: string }[];
    for (const r of rows) if (r.player_id && r.team && !m.has(r.player_id)) m.set(r.player_id, r.team);
    return m;
  });
  // MLBAM and nba_api ids are both numeric-as-text and could rarely collide; only
  // resolve an id that appears in exactly ONE sport's log. An ambiguous id stays
  // unresolved → the engine's team-agnostic ('na') bucket (the safe default).
  const out: Record<string, string> = {};
  for (const id of ids) {
    const hits = perTable.filter((m) => m.has(id));
    if (hits.length === 1) out[id] = hits[0].get(id)!;
  }
  return out;
}

// ── Public track record ───────────────────────────────────────────────────

/**
 * Public, verifiable track record — every settled BET pick meeting the current
 * action criteria since paper-trading start, aggregated per (sport, model_id).
 * Backed by v_public_track_record, which applies the same prob/edge cuts as
 * mobile/src/lib/thresholds.ts via the model_action_thresholds table.
 */
export async function fetchPublicTrackRecord(): Promise<TrackRecordRow[]> {
  const { data, error } = await supabase
    .from('v_public_track_record')
    .select(
      'sport, model_id, picks, wins, losses, pushes, profit_flat, staked_flat, ' +
        'clv_settled, clv_beat, avg_clv_pct, first_date, last_date',
    );
  if (error) throw error;
  return (data ?? []) as TrackRecordRow[];
}

/**
 * Live action thresholds, synced from config.py into model_action_thresholds by
 * data/threshold_sync.py. Read into the thresholds.ts server store so the action
 * filter reflects config changes with no rebuild (bundled values are the fallback).
 */
export async function fetchActionThresholds(): Promise<Record<string, ServerThreshold>> {
  const { data, error } = await supabase
    .from('model_action_thresholds')
    .select('model_id, min_prob, min_edge, min_odds, prob_only, paused');
  if (error) throw error;
  const out: Record<string, ServerThreshold> = {};
  for (const r of (data ?? []) as ActionThresholdRow[]) {
    out[r.model_id] = {
      min_prob: Number(r.min_prob),
      min_edge: Number(r.min_edge),
      min_odds: r.min_odds == null ? null : Number(r.min_odds),
      prob_only: !!r.prob_only,
      paused: !!r.paused,
    };
  }
  return out;
}

/** Daily settled totals for the equity curve (v_public_track_record_daily). */
export async function fetchTrackRecordDaily(): Promise<TrackRecordDailyRow[]> {
  const { data, error } = await supabase
    .from('v_public_track_record_daily')
    .select('game_date, sport, picks, wins, losses, pushes, profit_flat, staked_flat')
    .order('game_date', { ascending: true });
  if (error) throw error;
  return (data ?? []) as TrackRecordDailyRow[];
}

/** The daily canonical cross-game parlays (public parlay track record). */
export async function fetchParlayTrackRecord(): Promise<ParlayTrackRow[]> {
  const { data, error } = await supabase
    .from('parlay_track_record')
    .select(
      'parlay_key, sport, game_date, n_legs, leg_labels, leg_keys, combined_american, ' +
        'model_prob, dk_implied_prob, edge, result, profit_flat, settled_at',
    )
    .order('game_date', { ascending: false });
  if (error) throw error;
  return (data ?? []) as unknown as ParlayTrackRow[];
}

// ── Opening-signal vs live comparison ─────────────────────────────────────────

/**
 * Game-level settled record for the locked opening signal vs the live/closing
 * pick (v_opening_vs_live). Two rows: track = 'opening' | 'live'.
 */
export async function fetchOpeningVsLive(): Promise<OpeningVsLiveRow[]> {
  const { data, error } = await supabase
    .from('v_opening_vs_live')
    .select(
      'track, picks, wins, losses, pushes, profit_flat, staked_flat, ' +
        'clv_settled, clv_beat, avg_clv_pct',
    );
  if (error) throw error;
  return (data ?? []) as OpeningVsLiveRow[];
}

/** Opening track sliced by line move after lock + public side (v_opening_signal_slices). */
export async function fetchOpeningSlices(): Promise<OpeningSliceRow[]> {
  const { data, error } = await supabase
    .from('v_opening_signal_slices')
    .select(
      'slice_kind, slice_value, picks, wins, losses, pushes, profit_flat, staked_flat, avg_clv_pct',
    );
  if (error) throw error;
  return (data ?? []) as OpeningSliceRow[];
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

// ── Track-a-bet ──────────────────────────────────────────────────────────────
// Writes the backend row the line-change notifier watches (tracking/
// push_notifier.notify_line_changes). The "tracked" UI state itself is local
// on-device (useTrackedBets) — this table has anon INSERT/DELETE but no SELECT.

/** Track a (game-level) bet for big-line-change alerts. Idempotent: a duplicate
 *  (device_id, pick_id) is treated as already-tracked, not an error. */
export async function trackBet(deviceId: string, pick: Pick): Promise<void> {
  const { error } = await supabase.from('tracked_bets').insert({
    device_id: deviceId,
    pick_id: pick.pick_id,
    game_id: pick.game_id,
    model_id: pick.model_id,
    pick_side: pick.pick_side,
    player_id: pick.player_id,
    pick_label: pick.pick_label,
    locked_odds: pick.dk_odds,
    locked_line: pick.scored_line,
    game_date: pick.game_date,
  });
  // 23505 = unique_violation → already tracked, which is fine.
  if (error && (error as { code?: string }).code !== '23505') throw error;
}

/** Stop tracking a bet. */
export async function untrackBet(deviceId: string, pickId: number): Promise<void> {
  const { error } = await supabase
    .from('tracked_bets')
    .delete()
    .eq('device_id', deviceId)
    .eq('pick_id', pickId);
  if (error) throw error;
}

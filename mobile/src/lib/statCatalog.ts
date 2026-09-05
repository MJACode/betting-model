import { propMarketForModel } from './markets';
import type { PlayerType, RecentGameRow, SeasonTotalsRow } from '@/types';
import type { Sport } from '@/hooks/useSportFilter';
import { isModelRetired } from './thresholds';

export type StatGroup =
  | 'Batting' | 'Pitching' | 'WNBA' | 'NBA' | 'UFC'
  | 'Passing' | 'Rushing' | 'Receiving' | 'Defense';

/**
 * A selectable leaderboard stat. `key` is the column on SeasonTotalsRow.
 * For MLB, `playerType` decides which view rows to load (batter vs pitcher).
 * `defaultLine` is the threshold the Hit Rate mode uses out of the box (e.g.
 * 0.5 for counting stats → "≥1"); the user can override it per stat.
 */
export interface StatDef {
  key: keyof SeasonTotalsRow;
  label: string;
  sport: Sport;
  group: StatGroup;
  playerType?: PlayerType;
  defaultLine?: number;
}

export const STAT_CATALOG: StatDef[] = [
  // ── MLB batting ──
  { key: 'hits', label: 'Hits', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'home_runs', label: 'Home Runs', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'total_bases', label: 'Total Bases', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 1.5 },
  { key: 'rbi', label: 'RBI', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'runs', label: 'Runs', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'walks', label: 'Walks', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'stolen_bases', label: 'Stolen Bases', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'doubles', label: 'Doubles', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'triples', label: 'Triples', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'strikeouts', label: 'Strikeouts', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'at_bats', label: 'At Bats', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 3.5 },
  // ── MLB pitching ──
  { key: 'p_strikeouts', label: 'Strikeouts', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 5.5 },
  { key: 'p_walks', label: 'Walks', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 1.5 },
  { key: 'p_hits_allowed', label: 'Hits Allowed', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 5.5 },
  { key: 'p_earned_runs', label: 'Earned Runs', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 2.5 },
  { key: 'p_home_runs', label: 'HR Allowed', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 0.5 },
  { key: 'innings_pitched', label: 'Innings', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 5.5 },
  { key: 'pitches', label: 'Pitches', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 89.5 },
  // ── WNBA ──
  { key: 'points', label: 'Points', sport: 'WNBA', group: 'WNBA', defaultLine: 14.5 },
  { key: 'rebounds', label: 'Rebounds', sport: 'WNBA', group: 'WNBA', defaultLine: 5.5 },
  { key: 'assists', label: 'Assists', sport: 'WNBA', group: 'WNBA', defaultLine: 3.5 },
  { key: 'threes', label: '3PM', sport: 'WNBA', group: 'WNBA', defaultLine: 1.5 },
  { key: 'pra', label: 'PRA', sport: 'WNBA', group: 'WNBA', defaultLine: 24.5 },
  { key: 'steals', label: 'Steals', sport: 'WNBA', group: 'WNBA', defaultLine: 0.5 },
  { key: 'blocks', label: 'Blocks', sport: 'WNBA', group: 'WNBA', defaultLine: 0.5 },
  { key: 'minutes', label: 'Minutes', sport: 'WNBA', group: 'WNBA', defaultLine: 27.5 },
  // ── NBA ──
  { key: 'points', label: 'Points', sport: 'NBA', group: 'NBA', defaultLine: 14.5 },
  { key: 'rebounds', label: 'Rebounds', sport: 'NBA', group: 'NBA', defaultLine: 5.5 },
  { key: 'assists', label: 'Assists', sport: 'NBA', group: 'NBA', defaultLine: 3.5 },
  { key: 'threes', label: '3PM', sport: 'NBA', group: 'NBA', defaultLine: 1.5 },
  { key: 'pra', label: 'PRA', sport: 'NBA', group: 'NBA', defaultLine: 24.5 },
  { key: 'steals', label: 'Steals', sport: 'NBA', group: 'NBA', defaultLine: 0.5 },
  { key: 'blocks', label: 'Blocks', sport: 'NBA', group: 'NBA', defaultLine: 0.5 },
  { key: 'turnovers', label: 'Turnovers', sport: 'NBA', group: 'NBA', defaultLine: 1.5 },
  { key: 'minutes', label: 'Minutes', sport: 'NBA', group: 'NBA', defaultLine: 27.5 },
  // ── NFL (nflverse weekly stats — rush_rec_tds = rushing + receiving TDs) ──
  { key: 'passing_yards', label: 'Pass Yards', sport: 'NFL', group: 'Passing', defaultLine: 224.5 },
  { key: 'passing_tds', label: 'Pass TDs', sport: 'NFL', group: 'Passing', defaultLine: 1.5 },
  { key: 'completions', label: 'Completions', sport: 'NFL', group: 'Passing', defaultLine: 19.5 },
  { key: 'attempts', label: 'Pass Attempts', sport: 'NFL', group: 'Passing', defaultLine: 29.5 },
  { key: 'interceptions', label: 'INTs Thrown', sport: 'NFL', group: 'Passing', defaultLine: 0.5 },
  { key: 'rushing_yards', label: 'Rush Yards', sport: 'NFL', group: 'Rushing', defaultLine: 49.5 },
  { key: 'rushing_tds', label: 'Rush TDs', sport: 'NFL', group: 'Rushing', defaultLine: 0.5 },
  { key: 'carries', label: 'Carries', sport: 'NFL', group: 'Rushing', defaultLine: 12.5 },
  { key: 'rush_rec_tds', label: 'Rush+Rec TDs', sport: 'NFL', group: 'Rushing', defaultLine: 0.5 },
  { key: 'receptions', label: 'Receptions', sport: 'NFL', group: 'Receiving', defaultLine: 3.5 },
  { key: 'receiving_yards', label: 'Rec Yards', sport: 'NFL', group: 'Receiving', defaultLine: 49.5 },
  { key: 'receiving_tds', label: 'Rec TDs', sport: 'NFL', group: 'Receiving', defaultLine: 0.5 },
  { key: 'targets', label: 'Targets', sport: 'NFL', group: 'Receiving', defaultLine: 5.5 },
  { key: 'def_sacks', label: 'Sacks', sport: 'NFL', group: 'Defense', defaultLine: 0.5 },
  { key: 'def_interceptions', label: 'Interceptions', sport: 'NFL', group: 'Defense', defaultLine: 0.5 },
  // ── NCAAF (CFBD box scores — same column keys as the NFL log wherever the
  //    two sports share a stat, so one catalog key means one thing in both.
  //    No targets: CFBD's box score does not report them.) ──
  { key: 'passing_yards', label: 'Pass Yards', sport: 'NCAAF', group: 'Passing', defaultLine: 224.5 },
  { key: 'passing_tds', label: 'Pass TDs', sport: 'NCAAF', group: 'Passing', defaultLine: 1.5 },
  { key: 'completions', label: 'Completions', sport: 'NCAAF', group: 'Passing', defaultLine: 17.5 },
  { key: 'attempts', label: 'Pass Attempts', sport: 'NCAAF', group: 'Passing', defaultLine: 27.5 },
  { key: 'interceptions', label: 'INTs Thrown', sport: 'NCAAF', group: 'Passing', defaultLine: 0.5 },
  { key: 'rushing_yards', label: 'Rush Yards', sport: 'NCAAF', group: 'Rushing', defaultLine: 49.5 },
  { key: 'rushing_tds', label: 'Rush TDs', sport: 'NCAAF', group: 'Rushing', defaultLine: 0.5 },
  { key: 'carries', label: 'Carries', sport: 'NCAAF', group: 'Rushing', defaultLine: 10.5 },
  { key: 'rush_rec_tds', label: 'Rush+Rec TDs', sport: 'NCAAF', group: 'Rushing', defaultLine: 0.5 },
  { key: 'receptions', label: 'Receptions', sport: 'NCAAF', group: 'Receiving', defaultLine: 3.5 },
  { key: 'receiving_yards', label: 'Rec Yards', sport: 'NCAAF', group: 'Receiving', defaultLine: 44.5 },
  { key: 'receiving_tds', label: 'Rec TDs', sport: 'NCAAF', group: 'Receiving', defaultLine: 0.5 },
  { key: 'def_tackles', label: 'Tackles', sport: 'NCAAF', group: 'Defense', defaultLine: 4.5 },
  { key: 'def_solo', label: 'Solo Tackles', sport: 'NCAAF', group: 'Defense', defaultLine: 2.5 },
  { key: 'def_sacks', label: 'Sacks', sport: 'NCAAF', group: 'Defense', defaultLine: 0.5 },
  { key: 'def_tfl', label: 'TFL', sport: 'NCAAF', group: 'Defense', defaultLine: 0.5 },
  { key: 'def_pd', label: 'Passes Defended', sport: 'NCAAF', group: 'Defense', defaultLine: 0.5 },
  { key: 'def_interceptions', label: 'Interceptions', sport: 'NCAAF', group: 'Defense', defaultLine: 0.5 },
  // ── UFC (games_played = fights in the window; team column = weight class) ──
  { key: 'wins', label: 'Wins', sport: 'UFC', group: 'UFC' },
  { key: 'ko_wins', label: 'KO/TKO Wins', sport: 'UFC', group: 'UFC' },
  { key: 'sub_wins', label: 'Sub Wins', sport: 'UFC', group: 'UFC' },
  { key: 'sig_strikes', label: 'Sig Strikes', sport: 'UFC', group: 'UFC' },
  { key: 'takedowns', label: 'Takedowns', sport: 'UFC', group: 'UFC' },
  { key: 'knockdowns', label: 'Knockdowns', sport: 'UFC', group: 'UFC' },
  { key: 'sub_attempts', label: 'Sub Attempts', sport: 'UFC', group: 'UFC' },
];

export const GROUP_ORDER: Record<Sport, StatGroup[]> = {
  MLB: ['Batting', 'Pitching'],
  WNBA: ['WNBA'],
  NBA: ['NBA'],
  NFL: ['Passing', 'Rushing', 'Receiving', 'Defense'],
  NCAAF: ['Passing', 'Rushing', 'Receiving', 'Defense'],
  UFC: ['UFC'],
  // No per-player leaderboard for these (NHL: team+goalie only; Golf: v1).
  NHL: [],
  GOLF: [],
};

export function statsForSport(sport: Sport): StatDef[] {
  return STAT_CATALOG.filter((s) => s.sport === sport);
}

/** Sport's default leaderboard stat, or null when the sport has no leaderboard (NHL, Golf). */
export function defaultStatFor(sport: Sport): StatDef | null {
  const wantKey =
    sport === 'WNBA' || sport === 'NBA' ? 'points'
    : sport === 'UFC' ? 'wins'
    : sport === 'NFL' || sport === 'NCAAF' ? 'passing_yards'
    : 'hits';
  const list = statsForSport(sport);
  return list.find((s) => s.key === wantKey) ?? list[0] ?? null;
}

/**
 * Any row carrying stat columns: season totals, a raw Hit-Rate game row, or a
 * single player's normalized game-log entry. Structural so all three qualify
 * without this module having to import each of their types.
 */
export type StatValueSource =
  | SeasonTotalsRow
  | RecentGameRow
  | { [key: string]: number | string | boolean | null | undefined };

/** Stat value for a row under a given stat (0 if missing). Works on season-total
 * rows and raw per-game rows (Hit Rate mode) alike. */
export function statValue(row: StatValueSource, def: StatDef): number {
  const v = row[def.key];
  if (typeof v === 'number') return v;
  if (typeof v === 'string') {
    // NUMERIC Postgres columns (NFL yards, sacks) can arrive as strings.
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
}

/** Default Hit Rate line for a stat (0.5 = "≥1" fallback for counting stats). */
export function defaultThresholdFor(def: StatDef | null): number {
  return def?.defaultLine ?? 0.5;
}

// Sports that support the Hit Rate view (have per-game player logs + RPCs).
const HIT_RATE_SPORTS = new Set<Sport>(['MLB', 'WNBA', 'NBA', 'NFL', 'NCAAF']);

/** Whether a sport can show the Hit Rate mode (UFC/NHL/Golf cannot). */
export function supportsHitRate(sport: Sport): boolean {
  return HIT_RATE_SPORTS.has(sport);
}

/**
 * Map a leaderboard stat to the prop model_id that prices it, so the Stats tab
 * can offer "Add to play" on a player when today's picks include the matching
 * prop. Keyed by StatDef.key. `home_runs` and `rbi` still map to their models
 * so a historical pick resolves back to its stat (statForPropModel reads the
 * raw map), but both models are RETIRED, so propModelForStat returns null: the STAT stays
 * on the leaderboard (Matt, 2026-09-02: "you should still see home runs on the
 * stats page"), the odds pill and Add button do not.
 * Stats with no prop model (doubles, triples, pitches, steals, …) return null.
 */
const STAT_KEY_TO_MODEL: Partial<Record<keyof SeasonTotalsRow, string>> = {
  // MLB batting
  hits: 'mlb_prop_batter_hits',
  total_bases: 'mlb_prop_batter_tb',
  home_runs: 'mlb_prop_batter_hr',
  rbi: 'mlb_prop_batter_rbi',
  runs: 'mlb_prop_batter_runs',
  walks: 'mlb_prop_batter_walks',
  stolen_bases: 'mlb_prop_batter_sb',
  // MLB pitching
  p_strikeouts: 'mlb_prop_pitcher_k',
  p_walks: 'mlb_prop_pitcher_walks',
  p_hits_allowed: 'mlb_prop_pitcher_hits',
  p_earned_runs: 'mlb_prop_pitcher_er',
  innings_pitched: 'mlb_prop_pitcher_outs',
  // WNBA / NBA share these column keys — resolved per sport in propModelForStat,
  // NOT here (a bare key can't disambiguate the two basketball leagues).
};

// Basketball stat key → prop-model suffix. WNBA and NBA reuse the same column
// keys, so the prefix is chosen from def.sport. NBA-only keys (turnovers) map
// only under NBA.
const BASKETBALL_STAT_SUFFIX: Partial<Record<keyof SeasonTotalsRow, string>> = {
  points: 'prop_player_points',
  rebounds: 'prop_player_rebounds',
  assists: 'prop_player_assists',
  threes: 'prop_player_threes',
  pra: 'prop_player_pra',
  blocks: 'prop_player_blocks',
  steals: 'prop_player_steals',
  turnovers: 'prop_player_turnovers',
};

// Suffixes WNBA actually models (NBA additionally has blocks/steals/turnovers).
const WNBA_BASKETBALL_KEYS = new Set<keyof SeasonTotalsRow>([
  'points', 'rebounds', 'assists', 'threes', 'pra',
]);

/**
 * Football stat key → the player_prop_odds market it is priced in.
 *
 * BOTH football leagues reach their market through this map rather than
 * through a model, because neither has a prop model: NCAAF has four
 * game-level models and no prop model, and PROP_MARKET_BY_MODEL carries no
 * `nfl_` entry at all. Every other sport resolves its market THROUGH its
 * model id, which is why football rows showed a dash however much data was
 * stored — rawPropModelForStat returns null for both leagues, so the market
 * lookup returned null with it. 103,693 NFL prop rows were already in the
 * table and invisible for exactly this reason; college props (2026-09-05,
 * Matt: "Yes do it") would have landed into the same blank column, so the
 * map covers both rather than fixing one league and leaving the other.
 *
 * The two boards deliberately share column keys, so one map serves both.
 * A stat with no entry has no market we pull, and its column correctly stays
 * blank rather than borrowing a neighbouring market's number: solo tackles,
 * TFL, passes defended and defensive INTs (no book prices them), rushing and
 * receiving TDs separately (the book sells the combined "anytime" instead),
 * and NFL targets.
 *
 * NOT HERE, DELIBERATELY: `def_tackles`. The book's `player_tackles_assists`
 * counts solo + assists at FULL credit, while CFBD charges a shared tackle as
 * a HALF (`tests/test_ncaaf_player_stats_ingestor.py`: 5 solo + 9 assists is
 * stored as 9.5, and the book would say 14). Hanging that price beside this
 * board's number would put the hit-rate percentage and the line on two
 * different scales — a different bet, in the sense of docs/best_line.md §5.
 * It comes back when the leaderboard carries a full-credit tackles column,
 * which is a new StatDef and not this change.
 */
const FOOTBALL_STAT_TO_MARKET: Partial<Record<keyof SeasonTotalsRow, string>> = {
  passing_yards: 'player_pass_yds',
  passing_tds: 'player_pass_tds',
  completions: 'player_pass_completions',
  attempts: 'player_pass_attempts',
  interceptions: 'player_pass_interceptions',
  rushing_yards: 'player_rush_yds',
  carries: 'player_rush_attempts',
  receptions: 'player_receptions',
  receiving_yards: 'player_reception_yds',
  // "Scores a touchdown": a Yes/No market the ingestor stores at the 0.5 line,
  // which is what a 0.5 rush+rec TD board row asks. It is shown under the
  // market's own name, not the column's — see propDisplayLabel in markets.ts.
  rush_rec_tds: 'player_anytime_td',
  def_sacks: 'player_sacks',
};

/**
 * Stats with a real market and NO model, outside football.
 *
 * The market normally comes THROUGH the model id, which is why a stat nobody
 * models has always shown a dash however much data existed. Football needed
 * its own map because neither league has a prop model at all; this is the
 * same problem one stat at a time.
 *
 * Doubles and Triples have been columns on the MLB board since it shipped and
 * blank the whole time, because nobody had asked the feed whether it served
 * them. The 2026-09-05 coverage probe did, and it does. There is no doubles
 * model and none is implied: like a football line, these are research.
 *
 * The board's other MLB blanks stay blank on purpose — the API does not know
 * `batter_at_bats`, `pitcher_home_runs_allowed` or `pitcher_pitches`, so no
 * key would help.
 *
 * KEYED `sport:key`, AND THAT GUARD IS THE POINT. `SeasonTotalsRow` keys are
 * shared across sports — this file's own comments say a bare key cannot tell
 * WNBA from NBA — so a bare map would let the next entry someone adds
 * (`steals`, `threes`, `blocks`) resolve a basketball column onto a baseball
 * market with nothing failing. Football gets its early return above instead,
 * because there neither league has a prop model at all.
 */
const STAT_KEY_TO_MARKET: Record<string, string> = {
  'MLB:doubles': 'batter_doubles',
  'MLB:triples': 'batter_triples',
};

/** The prop model_id whose pick can be added from this stat's leaderboard, or null. */
export function propModelForStat(def: StatDef | null): string | null {
  if (!def) return null;
  const id = rawPropModelForStat(def);
  // Retirement is about the model tracker, not the stat: the leaderboard keeps
  // the column, the Stats tab just never offers a retired model's pick on it.
  return id != null && isModelRetired(id) ? null : id;
}

/**
 * The player_prop_odds MARKET a stat is priced in — retirement-blind on
 * purpose. Retirement is about the model tracker (Matt, 2026-09-02: HR and
 * RBI "absent from display and not counted toward anything"); the Stats tab's
 * LINE column is the sportsbook's number, not the model's, so a retired model
 * must not blank it (Matt, 2026-09-03: "works separately from the models").
 * Null for stats no book prices. Both football leagues resolve through their
 * own map rather than a model, because neither has one (2026-09-05).
 */
export function propMarketForStat(def: StatDef | null): string | null {
  if (!def) return null;
  // Neither football league has a prop model to route through — the map above
  // is the whole answer for both, and returning early keeps a shared column
  // key (passing_yards) from ever resolving through some other sport's model.
  if (def.sport === 'NCAAF' || def.sport === 'NFL') {
    return FOOTBALL_STAT_TO_MARKET[def.key] ?? null;
  }
  const id = rawPropModelForStat(def);
  // The model's market when a model prices it, else the stat's own — a stat
  // nobody models can still be one every book prices (Doubles, Triples).
  return (
    (id ? propMarketForModel(id) : null) ??
    STAT_KEY_TO_MARKET[`${def.sport}:${def.key}`] ??
    null
  );
}

/**
 * Does ANY stat on this sport's board carry a market? Lets a blank column
 * say "no sportsbook posts Solo Tackles lines" (nothing to wait for) rather
 * than going silent, without claiming that on a sport we simply do not price
 * at all — where the whole LINE column is absent and a note would be noise.
 */
export function sportHasAnyPropMarket(sport: StatDef['sport']): boolean {
  return STAT_CATALOG.some((d) => d.sport === sport && propMarketForStat(d) != null);
}

/** The forward map with no retirement filter — the inverse below needs it so
 *  a pick a retired model already made still opens its player's stat page. */
function rawPropModelForStat(def: StatDef): string | null {
  // NCAAF shares its column keys with the NFL but has no prop models of its
  // own — returning early keeps a shared key (passing_yards) from resolving to
  // an NFL model on a college player.
  if (def.sport === 'NCAAF') return null;
  if (def.sport === 'NBA') {
    const suffix = BASKETBALL_STAT_SUFFIX[def.key];
    return suffix ? `nba_${suffix}` : null;
  }
  if (def.sport === 'WNBA') {
    const suffix = BASKETBALL_STAT_SUFFIX[def.key];
    return suffix && WNBA_BASKETBALL_KEYS.has(def.key) ? `wnba_${suffix}` : null;
  }
  return STAT_KEY_TO_MODEL[def.key] ?? null;
}

/**
 * Inverse of propModelForStat — the leaderboard stat a prop model prices, so a
 * pick can open its player's detail screen on the stat the pick is about.
 * Derived from the same raw map, so the two can never disagree on a live
 * model. It deliberately IGNORES retirement: an HR pick a user tracked still
 * has a player, and that player's Home Runs page is exactly the one Matt kept.
 * Returns null for game markets and for prop models with no leaderboard stat.
 */
export function statForPropModel(modelId: string): StatDef | null {
  for (const def of STAT_CATALOG) {
    if (rawPropModelForStat(def) === modelId) return def;
  }
  return null;
}

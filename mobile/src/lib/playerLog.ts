/**
 * Per-player game-log plumbing shared by every sport's player detail screen.
 *
 * The player detail view (hit rate at a line, rolling averages, recent games)
 * used to be MLB-only: it read `player_game_log` directly and drew its stat
 * chips from the MLB prop-model registry. Each sport keeps its own log table
 * with its own columns, so this module is the one place that knows how to turn
 * any of them into a common row shape and which stats each can offer.
 *
 * Stat definitions come from the SAME `statCatalog` the Stats-tab leaderboard
 * uses, so a player's detail screen can never offer a stat the leaderboard
 * ranks differently (or vice versa).
 */
import type { Sport } from '@/hooks/useSportFilter';
import { sportOfModel } from './modelMeta';
import {
  logDerivedStatsFor,
  statForPropMarket,
  statForPropModel,
  statsForSport,
  statValue,
  type StatDef,
  type StatGroup,
} from './statCatalog';
import type { PlayerType } from '@/types';

/** Sports with a per-game player log — the ones that can show player detail. */
export type PlayerLogSport = 'MLB' | 'WNBA' | 'NBA' | 'NFL' | 'NCAAF' | 'NCAAB';

const LOG_SPORTS = new Set<Sport>(['MLB', 'WNBA', 'NBA', 'NFL', 'NCAAF', 'NCAAB']);

/** The two football leagues share a log shape (and a weekly cadence). */
const FOOTBALL = new Set<PlayerLogSport>(['NFL', 'NCAAF']);

/**
 * Whether a sport has per-player game logs, and therefore a player detail
 * screen. UFC (fight-level, no per-game stat log), NHL (the Stats tab reads
 * nhl_skater_game_log; this screen stays closed until the game-log grants
 * land) and Golf (v1 has no player leaderboard) do not.
 */
export function supportsPlayerDetail(sport: Sport): sport is PlayerLogSport {
  return LOG_SPORTS.has(sport);
}

/**
 * Per-game minutes on the player page. NBA, WNBA and NCAAB logs carry
 * `minutes`. NFL and NCAAF do not (snap share is a different design). NHL
 * player detail is still closed. MLB already shows volume as IP / AB.
 */
const MINUTES_SPORTS = new Set<Sport>(['NBA', 'WNBA', 'NCAAB']);

export function sportTracksMinutes(sport: Sport): boolean {
  return MINUTES_SPORTS.has(sport);
}

/** A game is low-minutes when it is under this share of the window average. */
export const LOW_MINUTES_RATIO = 0.7;

/** One normalized game from any sport's player log, newest-first when listed. */
export interface PlayerLogEntry {
  player_id: string;
  player_name: string;
  team: string | null;
  game_id: string;
  game_date: string;
  season: number;
  /** MLB only — decides which stat chips apply. */
  player_type?: PlayerType | null;
  /** NFL only — CFBD's box score names participants, not positions. */
  pos?: string | null;
  opponent?: string | null;
  /** Where the player's team played. Filled from `games` on fetch
   *  (attachGameSides), so every sport has it, not only the two football logs
   *  that store an opponent column. Absent when the game row was not found. */
  venue?: 'home' | 'away' | null;
  week?: number | null;
  /** Basketball logs only. Null when this logged game has no minutes. */
  minutes?: number | string | null;
  /** Every sport's stat columns, plus the derived ones added below. */
  [key: string]: number | string | null | undefined;
}

// ── Table + column config ───────────────────────────────────────────────────
// Column lists are explicit (not `*`) so a new column on a log table can never
// silently widen what the phone downloads.

const MLB_COLUMNS =
  'player_id, player_name, team, player_type, game_id, game_date, season, ' +
  'innings_pitched, pitches, p_strikeouts, p_walks, p_hits_allowed, p_earned_runs, ' +
  'p_home_runs, at_bats, hits, doubles, triples, home_runs, rbi, runs, walks, ' +
  'strikeouts, stolen_bases, total_bases, batting_order, is_starter';

const BASKETBALL_COLUMNS =
  'player_id, player_name, team, game_id, game_date, season, minutes, is_starter, ' +
  'points, rebounds, assists, steals, blocks, turnovers, fg3_made';

const NFL_COLUMNS =
  'player_id, player_name, pos, team, opponent, game_id, game_date, season, week, ' +
  'season_type, completions, attempts, passing_yards, passing_tds, interceptions, ' +
  'carries, rushing_yards, rushing_tds, receptions, targets, receiving_yards, ' +
  'receiving_tds, def_sacks, def_interceptions';

// CFBD reports no targets and no position, so the NCAAF list is the NFL one
// minus those two, plus the defensive counts college box scores carry.
const NCAAF_COLUMNS =
  'player_id, player_name, team, opponent, game_id, game_date, season, week, ' +
  'season_type, completions, attempts, passing_yards, passing_tds, interceptions, ' +
  'carries, rushing_yards, rushing_tds, receptions, receiving_yards, ' +
  'receiving_tds, def_tackles, def_solo, def_sacks, def_tfl, def_pd, ' +
  'def_interceptions';

export const LOG_TABLE: Record<PlayerLogSport, string> = {
  MLB: 'player_game_log',
  WNBA: 'wnba_player_game_log',
  NBA: 'nba_player_game_log',
  NFL: 'nfl_player_game_log',
  NCAAF: 'ncaaf_player_game_log',
  // Men's college basketball (add_ncaab_player_game_log_2026_11_03.sql):
  // WNBA's column names, so the basketball column list reads it unchanged.
  NCAAB: 'ncaab_player_game_log',
};

export const LOG_COLUMNS: Record<PlayerLogSport, string> = {
  MLB: MLB_COLUMNS,
  WNBA: BASKETBALL_COLUMNS,
  NBA: BASKETBALL_COLUMNS,
  NFL: NFL_COLUMNS,
  NCAAF: NCAAF_COLUMNS,
  NCAAB: BASKETBALL_COLUMNS,
};

/**
 * How many games back to load. MLB and basketball play near-daily, so 50 rows
 * is a few months; NFL plays weekly, so 25 rows is already a season and a half
 * and anything more would stretch the "recent form" read past usefulness.
 */
export function logFetchLimit(sport: PlayerLogSport): number {
  return FOOTBALL.has(sport) ? 25 : 50;
}

// ── Derived stats ───────────────────────────────────────────────────────────

/**
 * Adds the columns the leaderboard views compute in SQL but the raw log tables
 * do not store, so a stat chip resolves the same way on both surfaces:
 *   basketball  threes = fg3_made, pra = points + rebounds + assists
 *   NFL         rush_rec_tds = rushing_tds + receiving_tds
 *   MLB pitcher outs — see `outs` note in `chipsForPlayer` below
 * Plus two the leaderboard does not have, summed here only
 * (statCatalog.LOG_DERIVED_STATS):
 *   basketball  blocks_steals = blocks + steals,
 *               rebounds_assists = rebounds + assists
 * Missing inputs stay missing rather than becoming 0: a null stat must read as
 * "no data" (excluded from the hit rate), never as a game with zero of it.
 */
export function normalizeLogRow(sport: PlayerLogSport, raw: Record<string, unknown>): PlayerLogEntry {
  const row = { ...raw } as PlayerLogEntry;
  if (sport === 'WNBA' || sport === 'NBA' || sport === 'NCAAB') {
    row.threes = num(raw.fg3_made);
    row.pra = sum(raw.points, raw.rebounds, raw.assists);
    row.blocks_steals = sum(raw.blocks, raw.steals);
    row.rebounds_assists = sum(raw.rebounds, raw.assists);
  } else if (FOOTBALL.has(sport)) {
    row.rush_rec_tds = sum(raw.rushing_tds, raw.receiving_tds);
  } else if (sport === 'MLB') {
    row.outs = ipToOuts(raw.innings_pitched);
  }
  return row;
}

function num(v: unknown): number | null {
  if (v == null) return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Minutes on a log row, or null when the column is missing or not a number.
 *  Zero is a played game (ESPN's "0" is in the box and settles). */
export function minutesPlayed(row: { minutes?: unknown }): number | null {
  return num(row.minutes);
}

/**
 * A basketball log row with no minutes. Did-not-play players are not in the
 * game log the screen loads: NBA writes them to `nba_player_dnp`, and the
 * WNBA and NCAAB ingestors leave a didNotPlay athlete out. This is the row
 * shape if one is present, not a guess at games the log does not have.
 */
export function isDidNotPlay(sport: Sport, row: { minutes?: unknown }): boolean {
  return sportTracksMinutes(sport) && minutesPlayed(row) == null;
}

/** The Minutes chip is context, not a bet: no line, no Bet, no betslip. */
export function isMinutesContextStat(def: StatDef | null | undefined): boolean {
  return !!def && String(def.key) === 'minutes' && sportTracksMinutes(def.sport);
}

/** Minutes sits immediately after PRA on the player page. The leaderboard
 *  keeps catalog order; only this chip list moves. */
function minutesChipAfterPra(chips: StatDef[]): StatDef[] {
  const idx = chips.findIndex((c) => String(c.key) === 'minutes');
  if (idx < 0) return chips;
  const minutes = chips[idx]!;
  const rest = chips.filter((_, i) => i !== idx);
  const pra = rest.findIndex((c) => String(c.key) === 'pra');
  const at = pra < 0 ? rest.length : pra + 1;
  return [...rest.slice(0, at), minutes, ...rest.slice(at)];
}

/** Sum of parts, or null when every part is missing (see normalizeLogRow). */
function sum(...parts: unknown[]): number | null {
  let total = 0;
  let seen = false;
  for (const p of parts) {
    const n = num(p);
    if (n == null) continue;
    total += n;
    seen = true;
  }
  return seen ? total : null;
}

/**
 * Baseball innings-pitched notation → outs. 5.2 means five and TWO THIRDS
 * innings, not 5.2 innings, so it cannot be compared against a line as a plain
 * decimal — the detail screen offers outs instead.
 */
export function ipToOuts(ip: unknown): number | null {
  const n = num(ip);
  if (n == null) return null;
  const whole = Math.floor(n);
  const frac = Math.round((n - whole) * 10);
  return whole * 3 + frac;
}

// ── Stat chips ──────────────────────────────────────────────────────────────

/** Detail-screen replacement for the MLB "Innings" leaderboard stat. */
const OUTS_STAT: StatDef = {
  key: 'outs' as StatDef['key'],
  label: 'Outs',
  sport: 'MLB',
  group: 'Pitching',
  playerType: 'pitcher',
  defaultLine: 16.5,
};

/**
 * The stats a player's detail screen can chart, from the shared catalog.
 *
 * Three sport-specific adjustments:
 *  - MLB chips are split by player type, the way the leaderboard splits them.
 *  - MLB pitching swaps "Innings" for "Outs". The leaderboard SUMS innings so
 *    the notation quirk averages out there, but the detail screen compares a
 *    single game against a line, where 5.2 IP >= 5.5 is false and wrong.
 *  - NBA adds Blocks+Steals and Reb+Ast after the leaderboard's chips
 *    (statCatalog.LOG_DERIVED_STATS): markets the projection model bets, so
 *    its pick's "View all stats" opens on the stat it is written on.
 */
export function chipsForPlayer(sport: PlayerLogSport, playerType?: PlayerType | null): StatDef[] {
  const all = [...statsForSport(sport), ...logDerivedStatsFor(sport)];
  if (sport === 'MLB') {
    const type = playerType ?? 'batter';
    return all
      .filter((s) => s.playerType === type)
      .map((s) => (s.key === 'innings_pitched' ? OUTS_STAT : s));
  }
  return sportTracksMinutes(sport) ? minutesChipAfterPra(all) : all;
}

/** The stat a player's detail screen opens on. */
export function defaultChipForPlayer(
  sport: PlayerLogSport,
  playerType?: PlayerType | null,
): StatDef | null {
  return chipsForPlayer(sport, playerType)[0] ?? null;
}

/** Ordered stat groups present in a chip list, in the order the chips run. */
export function groupsOfChips(chips: StatDef[]): StatGroup[] {
  const seen: StatGroup[] = [];
  for (const c of chips) {
    if (!seen.includes(c.group)) seen.push(c.group);
  }
  return seen;
}

// ── Which groups a player can actually fill ─────────────────────────────────
//
// Lamar Jackson's screen offered a Defense tab: Sacks 0.00 on every window, a
// 0% badge in alarm red, ten charted zeroes (Matt, 2026-09-19). Nothing was
// broken. `nfl_player_game_log` stores 0, never NULL, for a stat a position
// does not produce — measured 2026-09-19, all 175,542 rows carry a value for
// def_sacks — so the tab had ten real games to chart and charted them. It is
// still a control that leads nowhere, and the same shape ran the other way: a
// linebacker got Passing, Rushing and Receiving, all zeroes.
//
// So the screen asks what this player has actually PRODUCED: the log decides,
// and the position is the safety net under it. The log is the stronger of the
// two because it is the same evidence the chart draws — a tab is offered when
// there is something in it, in either league, including the NCAAF logs that
// carry no position at all. The position map exists for the player with
// nothing on file yet, where "no tabs" and "every tab" are both wrong answers.

// THE app's one defensive set: the Stats tab's DEF segment reads this same
// object (lib/statSegments.ts). EDGE and SS joined on 2026-09-25 when the two
// copies were merged — nflverse writes neither today, and a code in the set
// that never arrives changes nothing. Nothing was removed.
export const NFL_DEFENSIVE_POSITIONS: ReadonlySet<string> = new Set<string>([
  'CB', 'DB', 'DE', 'DL', 'DT', 'EDGE', 'FS', 'ILB', 'LB', 'MLB', 'NT', 'OLB', 'S', 'SAF', 'SS',
]);

// Offense and special teams. A kicker or a long snapper produces none of these
// either, but the tabs they get are the ones their side of the ball can fill —
// never Defense.
const NFL_NON_DEFENSIVE_POSITIONS = new Set([
  'C', 'FB', 'G', 'K', 'LS', 'OL', 'OT', 'P', 'QB', 'RB', 'TE', 'WR',
]);

const DEFENSIVE_GROUPS: StatGroup[] = ['Defense'];
const NON_DEFENSIVE_GROUPS: StatGroup[] = ['Passing', 'Rushing', 'Receiving'];

/**
 * The groups a football position is expected to fill. Empty for a position we
 * do not recognise and for NCAAF (no position in the box score) — the log is
 * then the only evidence, which is the conservative way round: an unknown
 * position hides nothing on its own.
 */
export function positionGroups(pos: string | null | undefined): StatGroup[] {
  if (!pos) return [];
  const p = pos.toUpperCase();
  if (NFL_DEFENSIVE_POSITIONS.has(p)) return DEFENSIVE_GROUPS;
  if (NFL_NON_DEFENSIVE_POSITIONS.has(p)) return NON_DEFENSIVE_GROUPS;
  return [];
}

/** The player's position from their log, newest game that names one. */
export function positionOf(games: PlayerLogEntry[]): string | null {
  for (const g of games) {
    if (g.pos) return String(g.pos);
  }
  return null;
}

/**
 * The chips a loaded player's screen should actually offer: the groups they
 * have put a real number in inside the loaded window, with their position as
 * the safety net. Whole groups are kept or dropped together — a Passing tab
 * still lists Pass TDs for a quarterback who has none this month.
 *
 * "A real number" is non-NULL and non-zero, because the NFL log stores 0 where
 * NCAAF stores NULL and a tab of ten zeroes is the thing being fixed. A
 * quarterback who ran a jet sweep keeps his Rushing tab; a linebacker who
 * caught a lateral gets a Receiving one, because he did.
 *
 * Three fallbacks, each one wider than the last:
 *  - no games loaded yet -> every chip, so the tab row does not shrink to a
 *    guess and then grow back;
 *  - nothing but zeroes on file (an inactive month, a rookie's debut) -> the
 *    position's own groups, which is how a benched quarterback still gets
 *    Passing rather than Defense;
 *  - position unknown too (NCAAF, where CFBD names no position) -> every chip,
 *    rather than a screen with no tabs at all.
 */
export function chipsForLoadedPlayer(chips: StatDef[], games: PlayerLogEntry[]): StatDef[] {
  if (games.length === 0) return chips;
  const filled = filledChipCounts(chips, games);
  const played = new Set<StatGroup>();
  for (const c of chips) {
    if ((filled.get(chipKey(c)) ?? 0) > 0) played.add(c.group);
  }
  const allowed = played.size > 0 ? played : new Set<StatGroup>(positionGroups(positionOf(games)));
  const kept = chips.filter((c) => allowed.has(c.group));
  return kept.length > 0 ? kept : chips;
}

/**
 * The chip a caller asked this screen to open on, resolved against the
 * player's own chip list.
 *
 * The board (and a prop pick) hands the stat over as two loose strings on the
 * route rather than a StatDef, because a route param is serialised into
 * navigation state and restored from it — the same reason `matchupGrade`
 * travels as a string. The group is what disambiguates: football shares stat
 * keys across groups, so `receiving_tds` alone is ambiguous where
 * `Receiving:receiving_tds` is not. A key with no group still resolves, to the
 * first group holding it, so an older build's params keep working.
 *
 * The MLB innings→outs swap (chipsForPlayer) is applied here too: the board
 * sums innings, the detail screen charts outs, and they are one stat to a
 * reader tapping a pitcher's row.
 */
export function requestedChip(
  chips: StatDef[],
  statKey?: string | null,
  statGroup?: string | null,
): StatDef | null {
  if (!statKey) return null;
  const key = statKey === 'innings_pitched' ? String(OUTS_STAT.key) : statKey;
  const matches = chips.filter((c) => String(c.key) === key);
  if (matches.length === 0) return null;
  if (statGroup) {
    const inGroup = matches.find((c) => c.group === statGroup);
    if (inGroup) return inGroup;
  }
  return matches[0] ?? null;
}

/**
 * `chipsForLoadedPlayer` with the ASKED-FOR stat kept, whatever the log says.
 *
 * The two rules pull opposite ways and both are right. A tab the player has
 * never filled is a control that leads nowhere — unless the reader has just
 * tapped that very stat, in which case "he has not scored in ten games" is the
 * answer they came for, and silently rehoming them on Receptions is the bug
 * this fixes. So the filter still decides everything else and ONE chip is
 * exempt from it.
 *
 * One CHIP, not its group (UX review, 2026-09-20): readmitting the group would
 * hand a touchdown-less receiver a Rushing tab holding Rush Yards and
 * Carries as well, all flat zero — the three controls 2026-09-19 removed,
 * smuggled back in by the exemption. A one-chip tab reads honestly, and it is
 * the only chip in the tab anyone asked for.
 */
export function chipsWithRequested(
  all: StatDef[],
  kept: StatDef[],
  requested: StatDef | null,
): StatDef[] {
  if (!requested) return kept;
  const key = chipKey(requested);
  if (kept.some((c) => chipKey(c) === key)) return kept;
  const keptKeys = new Set(kept.map(chipKey));
  return all.filter((c) => keptKeys.has(chipKey(c)) || chipKey(c) === key);
}

/** A chip's identity: two sports share stat keys, and football shares them across groups. */
export function chipKey(c: StatDef): string {
  return `${c.group}:${String(c.key)}`;
}

/**
 * How many of the loaded games each chip has a real number in — non-NULL and
 * non-zero. Chips missing from the map stay tappable: a running back with no
 * receiving touchdown in twenty-five games can still be bet to score one, so
 * the chip is offered; it is only never the chip a tab OPENS on.
 */
export function filledChipCounts(chips: StatDef[], games: PlayerLogEntry[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const c of chips) {
    let n = 0;
    for (const g of games) {
      const v = logStatValue(g, c);
      if (v != null && v !== 0) n += 1;
    }
    if (n > 0) counts.set(chipKey(c), n);
  }
  return counts;
}

/**
 * The chip a screen (or one of its tabs) should open on: within a group, the
 * stat this player fills most often; across groups, the most-filled chip of
 * the group they fill most overall. Ties go to catalog order, and a player who
 * fills nothing gets the first chip there is.
 *
 * Not simply "the first filled chip", because first is catalog order and
 * catalog order is a position's: a receiver's chips run Rushing before
 * Receiving, and Rush+Rec TDs sits in the Rushing group, so one receiving
 * touchdown would open a tight end on the Rushing tab. Measured 2026-09-19:
 * 82 of 252 wide receivers and 75 of 146 tight ends with a game since 2025
 * hold their Rushing tab on that chip alone, every other chip in it flat zero.
 * Weighing the whole group settles it on one game as well as on twenty-five.
 */
export function openingChip(
  chips: StatDef[],
  filled: Map<string, number>,
  group?: StatGroup | null,
): StatDef | null {
  const inGroup = group ? chips.filter((c) => c.group === group) : chips;
  if (inGroup.length === 0) return null;
  // Minutes is on nearly every basketball game, so weighing it with the
  // betting stats would open the page on the context tab. It wins only when
  // nothing else in the group has a number.
  const betting = inGroup.filter((c) => !isMinutesContextStat(c));
  const fromBetting = betting.length > 0 ? mostFilledChip(betting, filled) : null;
  if (fromBetting) return fromBetting;
  return mostFilledChip(inGroup, filled) ?? inGroup[0] ?? null;
}

function mostFilledChip(inGroup: StatDef[], filled: Map<string, number>): StatDef | null {
  const weight = new Map<StatGroup, number>();
  for (const c of inGroup) {
    weight.set(c.group, (weight.get(c.group) ?? 0) + (filled.get(chipKey(c)) ?? 0));
  }
  let best: StatDef | null = null;
  let bestScore = 0;
  let bestGroupWeight = 0;
  for (const c of inGroup) {
    const n = filled.get(chipKey(c)) ?? 0;
    if (n === 0) continue;
    const w = weight.get(c.group) ?? 0;
    if (w > bestGroupWeight || (w === bestGroupWeight && n > bestScore)) {
      best = c;
      bestScore = n;
      bestGroupWeight = w;
    }
  }
  return best;
}

// ── Line stepper ────────────────────────────────────────────────────────────

/**
 * How much one tap of the +/- stepper moves the line. Counting stats step by
 * one; yardage steps in the increments books actually hang lines at, so
 * walking a passing-yards line from 225 to 250 is one tap, not twenty-five.
 */
export function lineStepFor(def: StatDef | null): number {
  const base = def?.defaultLine ?? 0.5;
  if (base >= 100) return 25;
  if (base >= 40) return 5;
  return 1;
}

/** Snaps the auto-picked line (the median) onto the stepper's grid, never below one step. */
export function roundLineToStep(median: number, step: number): number {
  return Math.max(step, Math.round(median / step) * step);
}

/**
 * One tap of the ± stepper from `prev`.
 *
 * The ruler opens on the book's line EXACTLY (a 50.5 line is "51+"), which is
 * off a step-5 grid, and adding ±5 to it walked 46 → 51 → 56: 50 was
 * unreachable (Matt, 2026-10-08). So a line off the grid lands on the
 * neighbouring grid stop in the tapped direction first — 51 → 50 on minus,
 * 55 on plus — and steps by `step` from there. Never below 0; never above
 * `ceiling` when stepping up.
 */
export function stepLineFrom(prev: number, deltaSteps: number, step: number, ceiling = Infinity): number {
  if (deltaSteps === 0) return prev;
  const onGrid = Math.abs(prev / step - Math.round(prev / step)) < 1e-9;
  let next: number;
  if (onGrid) next = prev + deltaSteps * step;
  else {
    const first = deltaSteps > 0 ? Math.ceil(prev / step) * step : Math.floor(prev / step) * step;
    next = first + (deltaSteps - Math.sign(deltaSteps)) * step;
  }
  // The ceiling caps STEPPING UP only: a typed line above it is the reader's
  // own, and a − from 300 goes to 295, not back down to the cap.
  if (deltaSteps > 0) next = Math.min(next, Math.max(prev, ceiling));
  return Math.max(0, next);
}

/**
 * A line the reader typed, as the whole-number threshold the card uses, or
 * null when it is not one. Read in the face's own idiom:
 *  - At Least: "50" or "50+" is 50+; a half-line "50.5" is the threshold that
 *    clears it, 51+.
 *  - Over / Under: the face prints the book line ("50.5"), so a typed "50.5"
 *    is that line (51+ / 50 or fewer), and a whole "50" is the half-point
 *    above it — the card only prices half-lines, which cannot push.
 */
/**
 * The Avg | Median | ± line row on the player card, on a 375pt phone.
 *
 * Widths are Inter advances (a stand-in for the iOS system font), measured
 * 2026-10-08 and scaled linearly with `fontScale`. The case is the one the
 * card opens on for a yards prop: "At Least", a 50.5 line, averages 112.4
 * and 98.6. Chrome that does not scale — the 12pt chevron, the 30pt − / +,
 * the 8pt gaps, the field's 8pt padding and 48pt floor — is added on top.
 *
 * At fontScale 1 that row is 309pt of the card's 319 and fits. Above 1 it
 * does not. The stepper's `flex: 1` basis is 0, so the row will not wrap by
 * itself and the + button leaves the screen. Giving the stepper its own line
 * still fits at fontScale 2 (287 of 319) and at Accessibility Large (2.143,
 * the multiplier in RCTAccessibilityManager). From Accessibility Extra Large
 * (2.643) that line overflows too. The mode control is what grows, so it
 * takes the line above and − / field / + stay together; at the largest size
 * (Accessibility Extra Extra Extra Large, 3.571) that group is 221pt.
 * The − / + stay 30pt with 8pt of slop (46pt); the field and the mode
 * control stay minHeight 44.
 */
export const STEPPER_ROW_INNER = 375 - 16 * 2 - 12 * 2;

/** How the stepper sits in the Avg | Median row. */
export type StepperRowLayout = 'inline' | 'stacked' | 'split';

export interface StepperRowMeasure {
  /** Avg, Median and the stepper on one line. */
  single: number;
  /** The stepper once it has the line to itself. */
  stacked: number;
  /** − / field / +, without the mode control. */
  controls: number;
  /** "At Least" plus the chevron. */
  mode: number;
  inner: number;
  layout: StepperRowLayout;
}

export function measureStepperRow(fontScale: number): StepperRowMeasure {
  const scale = Number.isFinite(fontScale) && fontScale > 0 ? fontScale : 1;
  // Advances at fontScale 1, from the measurement above.
  const avg = Math.max(40.039062, 18.652344) * scale;
  const med = Math.max(36.539062, 34.931641) * scale;
  const mode = 50.222656 * scale + 2 + 12 + 4;
  const input = Math.max(48, 38.291504 * scale + 8);
  const controls = 30 + 8 + input + 8 + 30;
  const stacked = mode + 8 + controls;
  const single = avg + 16 + med + 16 + stacked;
  const layout: StepperRowLayout =
    single <= STEPPER_ROW_INNER ? 'inline' : stacked <= STEPPER_ROW_INNER ? 'stacked' : 'split';
  return { single, stacked, controls, mode, inner: STEPPER_ROW_INNER, layout };
}

/**
 * Room left of a chip when its row is scrolled to it, so the chip before it
 * still shows and the row reads as scrollable (components/SportToggle.tsx).
 */
export const CHIP_ROW_LEAD = 40;

/**
 * Where a horizontal chip row scrolls so its selected chip is on screen, from
 * the chip's x inside the row; null before the chip has laid out.
 *
 * The player page's stat row runs past the right edge on every iPhone: NBA
 * has 11 chips, and a projection pick on Blocks+Steals or Reb+Ast opens on
 * the 10th or 11th, so nothing on screen said which stat the chart was
 * (UX review, 2026-10-16). Zero is a real answer: on an NFL page a group tab
 * remounts the row's chips and the new first chip can sit left of where the
 * row is scrolled to, which is why SportToggle's `x > 0` guard is not here.
 */
export function chipRowScrollX(chipX: number | null | undefined): number | null {
  if (chipX == null || !Number.isFinite(chipX)) return null;
  return Math.max(0, chipX - CHIP_ROW_LEAD);
}

/** Where the stepper sits so the + stays on a 375pt card. */
export function stepperRowLayout(fontScale: number): StepperRowLayout {
  return measureStepperRow(fontScale).layout;
}

export function parseTypedLine(text: string, mode: 'atLeast' | 'over' | 'under' = 'atLeast'): number | null {
  const t = text.trim().replace(/\+$/, '');
  if (!/^\d{1,4}(\.\d+)?$/.test(t)) return null;
  const n = Number(t);
  if (!Number.isFinite(n)) return null;
  if (mode === 'atLeast') return Number.isInteger(n) ? n : Math.ceil(n);
  return Math.floor(n) + 1;
}

/**
 * Apply a typed line once when the return key and blur both fire.
 *
 * Android delivers `onSubmitEditing` and then `onEndEditing` for one Done
 * press, in the same turn, with the same draft. The second call finds
 * `taken` and applies nothing. A field that was never opened (`draft == null`)
 * does not latch, so a later edit can still commit. iOS commits from blur
 * alone; this runs there once.
 */
export function commitTypedLineOnce(
  draft: string | null,
  taken: boolean,
  mode: 'atLeast' | 'over' | 'under',
  current: number | null,
): { line: number | null; taken: boolean } {
  if (taken) return { line: null, taken: true };
  if (draft == null) return { line: null, taken: false };
  const typed = parseTypedLine(draft, mode);
  if (typed == null || typed === current) return { line: null, taken: true };
  return { line: typed, taken: true };
}

// ── Reading a stat off a row ────────────────────────────────────────────────

/**
 * A game's value for a stat, or null when the log has no value for it. Numbers
 * arriving as strings (Postgres NUMERIC — NFL yardage, sacks) are coerced, the
 * same as the leaderboard does via statValue.
 */
export function logStatValue(row: PlayerLogEntry, def: StatDef | null): number | null {
  if (!def) return null;
  const raw = row[def.key as string];
  if (raw == null) return null;
  return statValue(row, def);
}

// ── Windows ─────────────────────────────────────────────────────────────────

/** 'all' = every game loaded (see logFetchLimit), shown with its own count. */
export type GameWindow = number | 'all';

export interface WindowOption {
  value: GameWindow;
  label: string;
}

/**
 * Deliberately NOT labelled "Season": the screen loads a player's last N games,
 * which for a mid-season MLB or NBA player is less than a season and for an NFL
 * player spans more than one. "All" plus the game count states what it is.
 */
export function windowOptionsFor(sport: PlayerLogSport): WindowOption[] {
  const spans = FOOTBALL.has(sport) ? [3, 5, 10] : [5, 10, 20];
  return [...spans.map((n) => ({ value: n as GameWindow, label: `L${n}` })), { value: 'all' as GameWindow, label: 'All' }];
}

// ── Opponent and venue, from the games table ────────────────────────────────

/** The `games` columns needed to name a log row's opponent. */
export interface GameSidesRow {
  game_id: string;
  home_team: string | null;
  away_team: string | null;
}

/**
 * Fills `opponent` and `venue` on each log row from its game.
 *
 * Matt, 2026-10-28: on the player chart "I cannot tell which is the recent game
 * and latest game. Add dates and … @ Chicago". Only the NFL and NCAAF logs
 * store an opponent; the other sports' logs have a game_id and a team. Measured
 * the same day: every log game_id is in `games` (NBA 1,286 of 1,286 this
 * season) and every log team is that game's home or away team (NBA 27,920 of
 * 27,920 rows), so the join is exact. A row whose game is missing keeps the
 * opponent its own log stored, and `venue` stays unset.
 */
export function attachGameSides(
  rows: PlayerLogEntry[],
  games: readonly GameSidesRow[],
): PlayerLogEntry[] {
  const byId = new Map(games.map((g) => [g.game_id, g]));
  return rows.map((r) => {
    const g = byId.get(r.game_id);
    if (!g || !r.team) return r;
    if (r.team === g.home_team) return { ...r, venue: 'home' as const, opponent: r.opponent ?? g.away_team };
    if (r.team === g.away_team) return { ...r, venue: 'away' as const, opponent: r.opponent ?? g.home_team };
    return r;
  });
}

/** Longest opponent name a chart label prints before shortening. 3-letter
 *  codes always fit; NCAAF school names ("Ohio State") do not. */
const OPP_LABEL_MAX = 4;

/**
 * "@CHI" (away) or "vs CHI" (home), the way every box score writes it, and
 * the bare name when the venue is unknown. With
 * `short`, a long name is replaced by its abbreviation from `abbrevs` (the
 * NCAAF school → CFBD code map, lib/ncaafAbbrevs.ts) and only cut to four
 * letters when the map has no entry — a bare cut prints "Michigan" and
 * "Michigan State" both as MICH (UX review, 2026-10-28). Null when the
 * opponent is unknown.
 *
 * `noSlice`: for a sport with no abbreviation map the app can read (NCAAB),
 * a long name is never cut — "MICH" would be Michigan and Michigan State, and
 * every "North …" school would read "NORT" (UX review, 2026-11-03). The short
 * label is then the venue marker alone, and the full name stays on the
 * selected bar's caption (`oppFull`).
 */
export function opponentLabel(
  row: Pick<PlayerLogEntry, 'opponent' | 'venue'>,
  short = false,
  abbrevs?: ReadonlyMap<string, string>,
  noSlice = false,
): string | null {
  const opp = row.opponent ? String(row.opponent) : '';
  if (!opp) return null;
  let name = opp;
  if (short && opp.length > OPP_LABEL_MAX) {
    const code = abbrevs?.get(opp);
    if (code && code.length <= 5) {
      name = code;
    } else if (noSlice) {
      return row.venue === 'away' ? '@' : row.venue === 'home' ? 'vs' : null;
    } else {
      name = opp.slice(0, OPP_LABEL_MAX).toUpperCase();
    }
  }
  if (row.venue === 'away') return `@${name}`;
  if (row.venue === 'home') return `vs ${name}`;
  // Venue unknown (no games row): the bare name, so it never claims a
  // home game it cannot vouch for (review, 2026-10-28).
  return name;
}

/** "10/26" from an ISO date, no year and no leading zeros. */
export function shortGameDate(iso: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ''));
  if (!m) return '';
  return `${Number(m[2])}/${Number(m[3])}`;
}

/** One charted game: its value plus what the chart prints under it. */
export interface ChartGame {
  value: number;
  date: string;
  opp: string | null;
  /** Full-length version for the tapped-bar caption ("@ Ohio State"). */
  oppFull: string | null;
  /** The opponent's defense rank that season (1 = toughest), when the chart
   *  is filtered by defense toughness (lib/defenseTier). */
  rank?: number | null;
  /** ISO date from the source. `date` is the printed form, which can add a year. */
  iso?: string;
  /** Log row id, so a tapped bar can outline that Recent games row. */
  gameId?: string;
  /** Minutes played. Null when this sport's log has no minutes for the game.
   *  Absent when the chart does not carry minutes at all. */
  minutes?: number | null;
  /** No bar and the caption "Did not play". A logged game whose minutes and
   *  charted stat are both missing. */
  dnp?: boolean;
  /** Under {@link LOW_MINUTES_RATIO} of the window's average minutes. */
  lowMin?: boolean;
}

/**
 * The same games `logValues` keeps, in the same order (newest first), with
 * each one's date and opponent. Built in one pass so a bar can never carry
 * another game's label: logValues DROPS games with no value, so indexing the
 * log by a value's position would shift every label after the first gap.
 *
 * When `sport` tracks minutes, a row with no stat AND no minutes is kept as
 * a DNP (no bar). A row with a stat and no minutes is kept, without a minutes
 * label. Zero minutes is a played game.
 */
export function chartGames(
  games: PlayerLogEntry[],
  valueOf: (r: PlayerLogEntry) => number | null,
  abbrevs?: ReadonlyMap<string, string>,
  noSlice = false,
  sport?: PlayerLogSport,
): ChartGame[] {
  const track = sport != null && sportTracksMinutes(sport);
  const out: ChartGame[] = [];
  for (const r of games) {
    const v = valueOf(r);
    const minutes = track ? minutesPlayed(r) : undefined;
    const dnp = track && v == null && minutes == null;
    if (v == null && !dnp) continue;
    const game: ChartGame = {
      value: v ?? 0,
      date: shortGameDate(r.game_date),
      iso: r.game_date,
      opp: opponentLabel(r, true, abbrevs, noSlice),
      oppFull: opponentLabel(r, false),
      gameId: r.game_id,
    };
    if (track) {
      game.minutes = minutes ?? null;
      if (dnp) game.dnp = true;
    }
    out.push(game);
  }
  return out;
}

export function averageAndMedian(values: readonly number[]): { avg: number | null; median: number | null } {
  if (values.length === 0) return { avg: null, median: null };
  const avg = values.reduce((a, b) => a + b, 0) / values.length;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 === 1 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2;
  return { avg, median };
}

/** True when `minutes` is under 70% of the window average. Equal to the cut is not low. */
export function isLowMinutes(minutes: number | null | undefined, windowAvg: number | null): boolean {
  if (typeof minutes !== 'number' || !Number.isFinite(minutes)) return false;
  if (windowAvg == null || !(windowAvg > 0)) return false;
  return minutes < windowAvg * LOW_MINUTES_RATIO;
}

/** Chart values with DNP slots removed, so a did-not-play is not a zero. */
export function scoredChartValues(games: readonly ChartGame[]): number[] {
  const out: number[] = [];
  for (const g of games) {
    if (g.dnp) continue;
    out.push(g.value);
  }
  return out;
}

/** Minutes for one bar. On the Minutes tab the bar's value is the minutes. */
export function chartMinutes(game: ChartGame, minutesAreValue: boolean): number | null {
  if (game.dnp) return null;
  if (typeof game.minutes === 'number' && Number.isFinite(game.minutes)) return game.minutes;
  if (minutesAreValue && Number.isFinite(game.value)) return game.value;
  return null;
}

/**
 * Average minutes across the window. Null unless every non-DNP game has a
 * number, so a partial join (a head-to-head game the loaded log does not
 * cover) is not shown as that window's average. DNP rows are excluded.
 */
export function windowAverageMinutes(games: readonly ChartGame[]): number | null {
  const played = games.filter((g) => !g.dnp);
  if (played.length === 0) return null;
  const mins: number[] = [];
  for (const g of played) {
    if (typeof g.minutes !== 'number' || !Number.isFinite(g.minutes)) return null;
    mins.push(g.minutes);
  }
  return averageAndMedian(mins).avg;
}

export function withLowMinutes(
  games: readonly ChartGame[],
  minutesAreValue: boolean,
  threshold: number | null,
): ChartGame[] {
  return games.map((g) => ({
    ...g,
    lowMin: isLowMinutes(chartMinutes(g, minutesAreValue), threshold),
  }));
}

function isoDay(iso: string | null | undefined): string {
  const m = /^(\d{4}-\d{2}-\d{2})/.exec(String(iso ?? ''));
  return m ? m[1]! : '';
}

function matchLogRow(candidates: readonly PlayerLogEntry[], game: ChartGame): PlayerLogEntry | undefined {
  if (candidates.length === 0) return undefined;
  if (candidates.length === 1) return candidates[0];
  const hay = `${game.oppFull ?? ''} ${game.opp ?? ''}`.toLowerCase();
  const hits = candidates.filter((r) => {
    const opp = String(r.opponent ?? '').trim().toLowerCase();
    return opp.length > 0 && hay.includes(opp);
  });
  return hits.length === 1 ? hits[0] : undefined;
}

/**
 * Fills `minutes` on chart rows that did not come from the game log (the
 * head-to-head and defense-tier reads do not return minutes) by the loaded
 * log's date. A day with two games attaches minutes only when the opponent
 * matches one of them. Unmatched games are left without minutes.
 */
export function lookupLogMinutes(
  chart: readonly ChartGame[],
  log: readonly PlayerLogEntry[],
  sport: PlayerLogSport,
): ChartGame[] {
  if (!sportTracksMinutes(sport)) return chart.map((g) => ({ ...g }));
  const byDay = new Map<string, PlayerLogEntry[]>();
  for (const r of log) {
    const day = isoDay(r.game_date);
    if (!day) continue;
    const list = byDay.get(day) ?? [];
    list.push(r);
    byDay.set(day, list);
  }
  return chart.map((g) => {
    const candidates = byDay.get(isoDay(g.iso)) ?? [];
    const row = matchLogRow(candidates, g);
    if (!row) return { ...g };
    return { ...g, minutes: minutesPlayed(row), gameId: g.gameId ?? row.game_id };
  });
}

const CAPTION_UNIT: Record<string, string> = {
  Points: 'pts',
  Rebounds: 'reb',
  Assists: 'ast',
  '3PM': '3pm',
  PRA: 'PRA',
  Steals: 'stl',
  Blocks: 'blk',
  Turnovers: 'tov',
  'Blocks+Steals': 'blk+stl',
  'Reb+Ast': 'reb+ast',
};

/** Short unit for the bar caption, so "8 pts · 12 min" fits one line. */
export function statCaptionUnit(label: string): string {
  return CAPTION_UNIT[label] ?? label;
}

export function minuteLabel(minutes: number): string {
  return `${Number(minutes).toFixed(0)}m`;
}

function minutePhrase(minutes: number): string {
  return `${Number(minutes).toFixed(0)} min`;
}

function fmtStat(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

function spokenOpponent(oppFull: string | null): string {
  if (!oppFull) return '';
  if (oppFull.startsWith('@')) return `at ${oppFull.replace(/^@\s*/, '')}`;
  return oppFull;
}

export interface SelectedGameReadout {
  /** Who and when. Stays on one line beside Low MIN and Hit/Miss. */
  caption: string;
  /** The stat and the minutes, on their own line so a long opponent cannot clip them. */
  detail: string | null;
  spoken: string;
  /** Null when the bar is not a hit or a miss (the Minutes tab, or a DNP). */
  result: 'Hit' | 'Miss' | null;
  low: boolean;
}

/**
 * Caption and VoiceOver for the selected bar.
 * `plain` is the chart's previous sentence. `stat` adds minutes. `minutes`
 * charts minutes and does not say hit or miss.
 */
export function describeSelectedGame(input: {
  ago: string;
  game: ChartGame;
  unit?: string;
  hit: boolean;
  mode: 'plain' | 'stat' | 'minutes';
  rankCaption: string | null;
  rankSpoken: string | null;
}): SelectedGameReadout {
  const { ago, game, unit, hit, mode, rankCaption, rankSpoken } = input;
  const dnp = game.dnp === true;
  const low = !dnp && game.lowMin === true;
  const oppSpoken = spokenOpponent(game.oppFull);

  const who = [ago, game.date, game.oppFull, rankCaption].filter(Boolean).join(' · ');

  if (dnp) {
    return {
      caption: who,
      detail: 'Did not play',
      spoken: [ago, game.date, oppSpoken, rankSpoken, 'did not play'].filter(Boolean).join(', '),
      result: null,
      low: false,
    };
  }

  if (mode === 'minutes') {
    const mins = typeof game.minutes === 'number' ? game.minutes : game.value;
    const spoken = [ago, game.date, oppSpoken, rankSpoken, `${Number(mins).toFixed(0)} minutes`];
    if (low) spoken.push('low minutes');
    return {
      caption: who,
      detail: minutePhrase(mins),
      spoken: spoken.filter(Boolean).join(', '),
      result: null,
      low,
    };
  }

  const valueText = fmtStat(game.value);
  if (mode === 'stat' && typeof game.minutes === 'number') {
    const unitShort = unit ? statCaptionUnit(unit) : '';
    const spoken = [
      ago,
      game.date,
      oppSpoken,
      rankSpoken,
      `${valueText}${unit ? ` ${unit.toLowerCase()}` : ''}`,
      `${Number(game.minutes).toFixed(0)} minutes`,
    ];
    if (low) spoken.push('low minutes');
    spoken.push(hit ? 'hit' : 'miss');
    return {
      caption: who,
      detail: [unitShort ? `${valueText} ${unitShort}` : valueText, minutePhrase(game.minutes)].join(' · '),
      spoken: spoken.filter(Boolean).join(', '),
      result: hit ? 'Hit' : 'Miss',
      low,
    };
  }

  const caption = [who, valueText].filter(Boolean).join(' · ');
  const spoken =
    `${ago}, ${game.date}` +
    (game.oppFull ? `, ${game.oppFull}` : '') +
    (rankSpoken ? `, ${rankSpoken}` : '') +
    `, ${valueText}${unit ? ` ${unit}` : ''}, ${hit ? 'hit' : 'miss'}`;
  return { caption, detail: null, spoken, result: hit ? 'Hit' : 'Miss', low: false };
}

// ── Display helpers ─────────────────────────────────────────────────────────

/** The line under the player's name: team, plus position where a sport has one. */
export function playerSubtitle(
  sport: PlayerLogSport,
  team: string | null,
  row: PlayerLogEntry | undefined,
  playerType?: PlayerType | null,
): string {
  const parts: string[] = [team ?? '—'];
  if (sport === 'MLB') parts.push(playerType === 'pitcher' ? 'Pitcher' : 'Batter');
  else if (sport === 'NFL' && row?.pos) parts.push(String(row.pos));
  return parts.join(' · ');
}

/**
 * The context line under a recent-game date — the volume behind the stat, which
 * is what tells you whether a quiet game was a bad game or a short one.
 */
export function gameContextLine(
  sport: PlayerLogSport,
  row: PlayerLogEntry,
  currentTeam?: string | null,
  /** True only when this row has no minutes and no value for the charted stat. */
  didNotPlay = false,
): string {
  const team = row.team ?? '—';
  // "@CHI" on an away game, "vs CHI" at home — every sport now, from `games`.
  const opp = opponentLabel(row);
  if (FOOTBALL.has(sport)) {
    const wk = row.week != null ? `Wk ${row.week}` : null;
    return [team, opp, wk].filter(Boolean).join(' · ');
  }
  if (sport === 'NCAAB') {
    // Two full school names on one truncating line: the minutes go first so
    // they are never the part cut (UX review, 2026-11-03). The player's own
    // school only when it is not the header's (a transfer's earlier rows).
    const min = num(row.minutes);
    const own = row.team && row.team !== currentTeam ? row.team : null;
    const minText = min == null ? (didNotPlay ? 'DNP' : '— min') : `${min.toFixed(0)} min`;
    return [minText, opp, own].filter(Boolean).join(' · ');
  }
  if (sport === 'WNBA' || sport === 'NBA') {
    const min = num(row.minutes);
    const minText = min == null ? (didNotPlay ? 'DNP' : '— min') : `${min.toFixed(0)} min`;
    return [team, opp, minText].filter(Boolean).join(' · ');
  }
  const isPitcher = row.player_type === 'pitcher';
  const vol = isPitcher ? `${row.innings_pitched ?? '—'} IP` : `${row.at_bats ?? '—'} AB`;
  return [team, opp, vol].filter(Boolean).join(' · ');
}

/**
 * The stat a prop pick's player detail should open on, with the same
 * Innings→Outs swap the chip list makes (see chipsForPlayer).
 */
export function detailStatForPropModel(modelId: string): StatDef | null {
  const def = statForPropModel(modelId);
  if (!def) return null;
  return def.key === 'innings_pitched' ? OUTS_STAT : def;
}

/**
 * The stat a prop PICK's player detail opens on. The model's own stat when it
 * prices one; otherwise the pick is from a multi-market rule (one id across
 * several markets, the market on the row) and the stat is the one its
 * prop_market is priced in, on the model's sport's board.
 */
export function detailStatForPick(pick: { model_id: string; prop_market?: string | null }): StatDef | null {
  const byModel = detailStatForPropModel(pick.model_id);
  if (byModel) return byModel;
  const def = statForPropMarket(sportOfModel(pick.model_id), pick.prop_market);
  if (!def) return null;
  return def.key === 'innings_pitched' ? OUTS_STAT : def;
}

/**
 * The player id the page's reads key on: the route's, else the loaded log's.
 * A pick from nfl_prop_market carries no player_id, so its player page opens
 * by name, and every read keyed on the id (the head-to-head row, today's pick
 * on this player) found nothing. The log the page loads by name carries the
 * id, so the page uses it once the log is in.
 */
export function pagePlayerId(
  routePlayerId: string | null | undefined,
  games: ReadonlyArray<{ player_id?: string | null }>,
): string | null {
  return routePlayerId || games[0]?.player_id || null;
}

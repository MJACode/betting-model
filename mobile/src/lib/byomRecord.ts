/**
 * Pure BYOM record math. No network. Screens rank and preview from this.
 *
 * Units are the backtest's 1u-to-win profit. ROI needs the amount risked.
 * This file does not estimate a price, and it does not read a count of
 * bets the backtest left out.
 */

import { byomFilters, type ByomFilters } from './byomFilters';
import {
  applyPropFilterKeys,
  EMPTY_PROP_FILTERS,
  propStateFromFilters,
  type ByomPropFilterState,
} from './byomPropFilters';

/** Same bound as byom.constants.DK_HISTORY_START_SEASON. */
export const BYOM_NFL_FIRST_SEASON = 2020;

/**
 * Ending-year label of the prop-history floor (2023-09-01). September
 * is still that calendar year's label. Not a count of priced slates.
 */
export const BYOM_NBA_FIRST_SEASON = 2023;

export type ByomSport = 'NFL' | 'NBA';

/** Same cap as byom_save_model: 'byom model cap is 25'. */
export const BYOM_MODEL_CAP = 25;

export const BYOM_UNITS_COPY =
  'u = units. Each bet is 1u to win at the DraftKings price at game start (or the closest DraftKings price). A push returns the stake. Win/loss only, no line locks.';

export type ByomSeasonScope = 'all' | 'current';

export type ByomGameMarket = 'h2h' | 'spreads' | 'totals';

/** Odds API keys graded into byom_prop_facts. Same twelve, same order as the builder. */
export type ByomPropMarket =
  | 'player_pass_yds'
  | 'player_pass_tds'
  | 'player_pass_attempts'
  | 'player_pass_completions'
  | 'player_rush_yds'
  | 'player_rush_attempts'
  | 'player_reception_yds'
  | 'player_receptions'
  | 'player_rush_reception_yds'
  | 'player_anytime_td'
  | 'player_tackles_assists'
  | 'player_sacks'
  | 'player_points'
  | 'player_rebounds'
  | 'player_assists'
  | 'player_threes'
  | 'player_points_rebounds_assists'
  | 'player_points_rebounds'
  | 'player_points_assists'
  | 'player_rebounds_assists'
  | 'player_blocks'
  | 'player_steals'
  | 'player_blocks_steals'
  | 'player_turnovers'
  | 'player_double_double'
  | 'player_triple_double';

export type ByomMarket = ByomGameMarket | ByomPropMarket;

export type ByomPropSide = 'over' | 'under';

/** Yes on anytime TD is this market's over leg. */
export const ANYTIME_TD_MARKET: ByomPropMarket = 'player_anytime_td';

/** Yes on a double-double is this market's over leg. */
export const DOUBLE_DOUBLE_MARKET: ByomPropMarket = 'player_double_double';

/** Yes on a triple-double is this market's over leg. */
export const TRIPLE_DOUBLE_MARKET: ByomPropMarket = 'player_triple_double';

export const NFL_PROP_MARKETS: readonly { value: ByomPropMarket; label: string }[] = [
  { value: 'player_pass_yds', label: 'Passing yards' },
  { value: 'player_pass_tds', label: 'Passing TDs' },
  { value: 'player_pass_attempts', label: 'Pass attempts' },
  { value: 'player_pass_completions', label: 'Completions' },
  { value: 'player_rush_yds', label: 'Rushing yards' },
  { value: 'player_rush_attempts', label: 'Rush attempts' },
  { value: 'player_reception_yds', label: 'Receiving yards' },
  { value: 'player_receptions', label: 'Receptions' },
  { value: 'player_rush_reception_yds', label: 'Rush + rec yards' },
  { value: 'player_anytime_td', label: 'Anytime TD' },
  { value: 'player_tackles_assists', label: 'Tackles + assists' },
  { value: 'player_sacks', label: 'Sacks' },
];

/** Full Stats-priced NBA set. Same order as the builder grid. */
export const NBA_PROP_MARKETS: readonly { value: ByomPropMarket; label: string }[] = [
  { value: 'player_points', label: 'Points' },
  { value: 'player_rebounds', label: 'Rebounds' },
  { value: 'player_assists', label: 'Assists' },
  { value: 'player_threes', label: 'Threes' },
  { value: 'player_points_rebounds_assists', label: 'PRA' },
  { value: 'player_points_rebounds', label: 'Points + Reb' },
  { value: 'player_points_assists', label: 'Points + Ast' },
  { value: 'player_rebounds_assists', label: 'Reb + Ast' },
  { value: 'player_blocks', label: 'Blocks' },
  { value: 'player_steals', label: 'Steals' },
  { value: 'player_blocks_steals', label: 'Blocks + Steals' },
  { value: 'player_turnovers', label: 'Turnovers' },
  { value: 'player_double_double', label: 'Double-double' },
  { value: 'player_triple_double', label: 'Triple-double' },
];

const PROP_MARKETS = [...NFL_PROP_MARKETS, ...NBA_PROP_MARKETS];

export function propMarketLabel(market: string | null | undefined): string | null {
  if (market == null) return null;
  for (const row of PROP_MARKETS) {
    if (row.value === market) return row.label;
  }
  return null;
}

/** Yes only. The over leg. Under is not a choice on the screen. */
export function isYesOnlyProp(market: string | null | undefined): boolean {
  return market === ANYTIME_TD_MARKET
    || market === DOUBLE_DOUBLE_MARKET
    || market === TRIPLE_DOUBLE_MARKET;
}

export function isPropMarket(market: string | null | undefined): market is ByomPropMarket {
  return propMarketLabel(market) != null;
}

export interface ByomDraft {
  market: ByomMarket;
  /** Home or away on a moneyline, a spread, or a prop player's team. Over or under on a total. */
  side: 'home' | 'away' | 'over' | 'under' | null;
  role: 'favorite' | 'underdog' | 'pickem' | null;
  /** null is any game. true is primetime only. false is the other kickoffs. */
  primetime: boolean | null;
  /** Over or under on a prop. Yes on a yes-only market is over. Null on a game market. */
  propSide: ByomPropSide | null;
  /**
   * NBA quick filter. b2b is one day since the previous game.
   * rest2 is two or more. Null is any schedule.
   */
  rest?: 'b2b' | 'rest2' | null;
  /** Phase A prop filters. Absent on a game-market draft. */
  propFilters?: ByomPropFilterState;
}

/** Matt, 2026-10-24: require a side or a favorite/underdog choice. */
export const TEAM_OR_ROLE_REQUIRED = 'Choose a team, or a favorite or underdog.';
export const TOTAL_SIDE_REQUIRED = 'Choose over or under.';
export const ANYTIME_YES_REQUIRED = 'Choose yes.';

/** The side values that belong on this market. Anything else is no choice. */
export function sideForMarket(
  market: ByomMarket,
  side: ByomDraft['side'],
): ByomDraft['side'] {
  if (market === 'totals') {
    return side === 'over' || side === 'under' ? side : null;
  }
  return side === 'home' || side === 'away' ? side : null;
}

/**
 * Prop side after a market change. Leaving Anytime TD for another prop
 * clears Over, because Yes was stored as over and was not a choice.
 * A chosen Over or Under stays when moving between the other props.
 * Anytime TD itself is always over.
 */
export function propSideAfterMarketChange(
  previous: ByomMarket | null,
  next: ByomMarket,
  current: ByomPropSide | null,
): ByomPropSide | null {
  if (isYesOnlyProp(previous) && isPropMarket(next) && !isYesOnlyProp(next)) {
    return null;
  }
  return propSideForMarket(next, current);
}

/** Over or under on a prop. A yes-only market is Yes, which is the over leg. */
export function propSideForMarket(
  market: ByomMarket,
  propSide: ByomDraft['propSide'],
): ByomDraft['propSide'] {
  if (!isPropMarket(market)) return null;
  if (isYesOnlyProp(market)) return 'over';
  return propSide === 'over' || propSide === 'under' ? propSide : null;
}

export function betTypeLabel(market: ByomMarket): string {
  if (market === 'h2h' || market === 'spreads' || market === 'totals') {
    return MARKET_LABEL[market];
  }
  return propMarketLabel(market) ?? '—';
}

/**
 * Moneyline and spread need a team or a favorite, underdog, or pick'em.
 * A total needs over or under. Team Any with a favorite or underdog set
 * is allowed. A missing choice is not both sides.
 */
export function saveBlockReason(draft: ByomDraft): string | null {
  if (isPropMarket(draft.market)) {
    if (isYesOnlyProp(draft.market)) {
      if (draft.propSide !== 'over') return ANYTIME_YES_REQUIRED;
      return null;
    }
    if (draft.propSide !== 'over' && draft.propSide !== 'under') return TOTAL_SIDE_REQUIRED;
    return null;
  }
  if (draft.market === 'totals') {
    if (draft.side !== 'over' && draft.side !== 'under') return TOTAL_SIDE_REQUIRED;
    return null;
  }
  const team = draft.side === 'home' || draft.side === 'away';
  const role = draft.role === 'favorite'
    || draft.role === 'underdog'
    || draft.role === 'pickem';
  if (!team && !role) return TEAM_OR_ROLE_REQUIRED;
  return null;
}

export interface ByomCountedRow {
  bets: number;
  wins: number;
  losses: number;
  pushes: number;
  ties: number;
  /** Null when the row did not carry units. Zero is a real zero. */
  units: number | null;
  /** Null when the row did not carry the amount risked. ROI stays unset. */
  risked: number | null;
}

export interface ByomRecord {
  bets: number;
  wins: number;
  losses: number;
  pushes: number;
  ties: number;
  units: number | null;
  risked: number | null;
}

const GAME_MARKETS = new Set<string>(['h2h', 'spreads', 'totals']);

const MARKET_LABEL: Record<ByomGameMarket, string> = {
  h2h: 'Moneyline',
  spreads: 'Spread',
  totals: 'Over/Under',
};

/**
 * NFL season from this device's America/New_York clock. September keeps
 * the calendar year. Earlier months use the year before. "This season"
 * does not use this number. It sends season null, and the server clock
 * decides. In late August and early September the two clocks can disagree.
 */
export function currentNflSeason(now: Date = new Date()): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: 'numeric',
  }).formatToParts(now);
  const year = Number(parts.find((p) => p.type === 'year')?.value);
  const month = Number(parts.find((p) => p.type === 'month')?.value);
  if (!Number.isFinite(year) || !Number.isFinite(month)) {
    throw new Error('NFL season clock');
  }
  return month >= 9 ? year : year - 1;
}

/**
 * NBA season from this device's America/New_York clock. The label is
 * the ending year. October through December are next year. Earlier
 * months, including the offseason, stay on the calendar year. "This
 * season" does not use this number. It sends season null and sport
 * NBA, and the server clock decides.
 */
export function currentNbaSeason(now: Date = new Date()): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: 'numeric',
  }).formatToParts(now);
  const year = Number(parts.find((p) => p.type === 'year')?.value);
  const month = Number(parts.find((p) => p.type === 'month')?.value);
  if (!Number.isFinite(year) || !Number.isFinite(month)) {
    throw new Error('NBA season clock');
  }
  return month >= 10 ? year + 1 : year;
}

/** 2023 through the current NBA season, inclusive. */
export function nbaSeasonList(now: Date = new Date()): number[] {
  const end = currentNbaSeason(now);
  const seasons: number[] = [];
  for (let year = BYOM_NBA_FIRST_SEASON; year <= end; year += 1) seasons.push(year);
  return seasons;
}

/** 2020 through the current NFL season, inclusive. */
export function nflSeasonList(now: Date = new Date()): number[] {
  const end = currentNflSeason(now);
  const seasons: number[] = [];
  for (let year = BYOM_NFL_FIRST_SEASON; year <= end; year += 1) seasons.push(year);
  return seasons;
}

export function isWholeSeason(filters: ByomFilters | null | undefined): boolean {
  return Object.keys(byomFilters(filters)).length === 0;
}

/**
 * Units are one side of a market. Named game markets show them. A prop
 * shows them only when the list is exactly that one market and
 * prop_side is over or under. A yes-only market shows them only for
 * over, which is Yes. An empty list, a mix, two props, or a prop with
 * no side stays hidden. A missing prop_side counts the over and the
 * under, and that total is not one bet.
 */
export function showsUnits(filters: ByomFilters | null | undefined): boolean {
  const parsed = byomFilters(filters);
  const markets = parsed.markets;
  if (markets == null || markets.length === 0) return false;
  if (markets.every((market) => GAME_MARKETS.has(market))) return true;
  if (markets.length !== 1 || !isPropMarket(markets[0])) return false;
  if (isYesOnlyProp(markets[0])) return parsed.prop_side === 'over';
  return parsed.prop_side === 'over' || parsed.prop_side === 'under';
}

export function gameMarket(filters: ByomFilters | null | undefined): ByomGameMarket | null {
  const markets = byomFilters(filters).markets;
  if (markets?.length !== 1) return null;
  const market = markets[0];
  if (market === 'h2h' || market === 'spreads' || market === 'totals') return market;
  return null;
}

export function marketLabel(filters: ByomFilters | null | undefined): string {
  const parsed = byomFilters(filters);
  const markets = parsed.markets;
  if (markets == null || markets.length === 0) return '—';
  const parts: string[] = [];
  let props = false;
  for (const market of markets) {
    if (market === 'h2h' || market === 'spreads' || market === 'totals') {
      parts.push(MARKET_LABEL[market]);
    } else {
      const label = propMarketLabel(market);
      if (label) parts.push(label);
      else props = true;
    }
  }
  if (props) parts.push('Props');
  if (parts.length === 0) return '—';
  let text = parts.join(' · ');
  if (markets.length === 1 && isPropMarket(markets[0]) && !isYesOnlyProp(markets[0])) {
    if (parsed.prop_side === 'over') text += ' · Over';
    else if (parsed.prop_side === 'under') text += ' · Under';
  }
  if (parsed.min_rest_days === 1 && parsed.max_rest_days === 1) text += ' · Back-to-back';
  else if (parsed.min_rest_days != null && parsed.min_rest_days >= 2 && parsed.max_rest_days == null) {
    text += ' · 2+ days rest';
  }
  return text;
}

export function recordFromRows(rows: readonly ByomCountedRow[]): ByomRecord {
  let bets = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let ties = 0;
  let units = 0;
  let unitsKnown = true;
  let risked = 0;
  let riskedKnown = true;
  for (const row of rows) {
    bets += row.bets;
    wins += row.wins;
    losses += row.losses;
    pushes += row.pushes;
    ties += row.ties;
    if (row.units == null || !Number.isFinite(row.units)) unitsKnown = false;
    else units += row.units;
    if (row.risked == null || !Number.isFinite(row.risked)) riskedKnown = false;
    else risked += row.risked;
  }
  return {
    bets,
    wins,
    losses,
    pushes,
    ties,
    units: unitsKnown ? units : null,
    risked: riskedKnown ? risked : null,
  };
}

/** Wins over wins and losses. Pushes and ties are not decided. */
export function byomWinRate(record: ByomRecord): number | null {
  const decided = record.wins + record.losses;
  if (decided <= 0) return null;
  return record.wins / decided;
}

/** Profit over the amount risked. Null when the stake was not returned. */
export function byomRoi(record: ByomRecord): number | null {
  if (record.units == null || record.risked == null || !(record.risked > 0)) return null;
  return record.units / record.risked;
}

/** W–L–P. Ties sit in the third count with pushes; both return the stake. */
export function formatByomRecord(record: ByomRecord): string {
  return `${record.wins}\u2013${record.losses}\u2013${record.pushes + record.ties}`;
}

function restChoice(filters: ByomFilters): ByomDraft['rest'] {
  if (filters.min_rest_days === 1 && filters.max_rest_days === 1) return 'b2b';
  if (filters.min_rest_days != null && filters.min_rest_days >= 2 && filters.max_rest_days == null) {
    return 'rest2';
  }
  return null;
}

export function filtersForDraft(
  draft: ByomDraft,
  base: ByomFilters = {},
  sport: ByomSport = 'NFL',
): ByomFilters {
  const next: ByomFilters = { ...base, markets: [draft.market] };
  if (isPropMarket(draft.market)) {
    const team = sideForMarket(draft.market, draft.side);
    if (team === 'home' || team === 'away') next.side = team;
    else delete next.side;
    if (draft.role === 'favorite' || draft.role === 'underdog') next.role = draft.role;
    else delete next.role;
    const direction = propSideForMarket(draft.market, draft.propSide);
    if (direction) next.prop_side = direction;
    else delete next.prop_side;
  } else {
    delete next.prop_side;
    const side = sideForMarket(draft.market, draft.side);
    if (side) next.side = side;
    else delete next.side;
    if (draft.market === 'totals' || !draft.role) delete next.role;
    else next.role = draft.role;
  }
  if (sport === 'NBA') {
    delete next.primetime;
    const rest = draft.rest ?? null;
    if (rest === 'b2b') {
      next.min_rest_days = 1;
      next.max_rest_days = 1;
    } else if (rest === 'rest2') {
      next.min_rest_days = 2;
      delete next.max_rest_days;
    } else {
      delete next.min_rest_days;
      delete next.max_rest_days;
    }
  } else if (draft.primetime == null) {
    delete next.primetime;
  } else {
    next.primetime = draft.primetime;
  }
  applyPropFilterKeys(next, draft.propFilters ?? EMPTY_PROP_FILTERS, {
    prop: isPropMarket(draft.market),
    sport,
    yesOnly: isYesOnlyProp(draft.market),
    marketCount: 1,
    primetime: draft.primetime,
  });
  return byomFilters(next);
}

export function draftFromFilters(filters: ByomFilters | null | undefined): ByomDraft | null {
  const markets = byomFilters(filters).markets;
  if (markets?.length !== 1) return null;
  const market = markets[0];
  const parsed = byomFilters(filters);
  if (market === 'h2h' || market === 'spreads' || market === 'totals') {
    return {
      market,
      side: sideForMarket(market, parsed.side ?? null),
      role: market === 'totals' ? null : (parsed.role ?? null),
      primetime: parsed.primetime ?? null,
      propSide: null,
      rest: restChoice(parsed),
      propFilters: propStateFromFilters(parsed),
    };
  }
  if (!isPropMarket(market)) return null;
  const stored = parsed.prop_side === 'over' || parsed.prop_side === 'under'
    ? parsed.prop_side
    : null;
  const propFilters = propStateFromFilters(parsed);
  const role = parsed.role === 'favorite' || parsed.role === 'underdog' ? parsed.role : null;
  return {
    market,
    side: sideForMarket(market, parsed.side ?? null),
    role,
    primetime: parsed.primetime ?? null,
    propSide: propSideForMarket(market, stored),
    rest: restChoice(parsed),
    propFilters,
  };
}

/** Refuses one market that still has no side. Other filters pass through. */
export function assertByomSide(filters: ByomFilters | null | undefined): void {
  const parsed = byomFilters(filters);
  if (parsed.markets?.length === 1
    && isYesOnlyProp(parsed.markets[0])
    && parsed.prop_side !== 'over') {
    throw new Error(ANYTIME_YES_REQUIRED);
  }
  const draft = draftFromFilters(filters);
  if (draft == null) return;
  const reason = saveBlockReason(draft);
  if (reason != null) throw new Error(reason);
}

/** Shown when byom_save_model refuses a name that belongs to the other sport. */
export const OTHER_SPORT_NAME =
  'This name is saved on the other sport. Choose another name.';

/** Preview copy when NBA game facts have not been built yet. */
export const NBA_NO_HISTORY = 'No history yet';

/** The sentence inside a save error, when the save was refused for that. */
export function sideBlockFromError(raw: string): string | null {
  if (raw.includes(ANYTIME_YES_REQUIRED)) return ANYTIME_YES_REQUIRED;
  if (raw.includes(TEAM_OR_ROLE_REQUIRED)) return TEAM_OR_ROLE_REQUIRED;
  if (raw.includes(TOTAL_SIDE_REQUIRED)) return TOTAL_SIDE_REQUIRED;
  if (raw.includes('name is saved on another sport')) return OTHER_SPORT_NAME;
  return null;
}

/**
 * The saved model with this name on a different sport. Same-sport names
 * are a replace, not this. A missing sport is NFL, matching the row default.
 */
export function nameTakenOnOtherSport<T extends { model_id: string; name: string; sport?: string }>(
  models: readonly T[],
  name: string,
  sport: string,
  exceptId?: string,
): T | null {
  const taken = otherModelWithName(models, name, exceptId);
  if (taken == null) return null;
  const theirs = (taken.sport ?? 'NFL').trim().toUpperCase();
  const mine = sport.trim().toUpperCase();
  if (theirs === mine) return null;
  return taken;
}

/** Moneyline, spread, total, or a rest chip. Those read byom_game_facts. */
export function filtersNeedGameFacts(filters: ByomFilters | null | undefined): boolean {
  if (filters == null) return false;
  const markets = filters.markets ?? [];
  for (const market of markets) {
    if (market === 'h2h' || market === 'spreads' || market === 'totals') return true;
  }
  return filters.min_rest_days != null || filters.max_rest_days != null;
}

/** One sentence under Game bets when the NBA read finished with no row. */
export const NBA_GAME_BETS_WHEN =
  'Game bets show up once NBA results are in.';

export function otherSportName(sport: ByomSport): ByomSport {
  return sport === 'NBA' ? 'NFL' : 'NBA';
}

export function otherSportAlert(name: string, theirs: string): { title: string; body: string } {
  const label = theirs.trim() || 'NFL';
  return {
    title: `Already saved on ${label}`,
    body: `“${name}” is saved on ${label}. Choose another name.`,
  };
}

/**
 * NBA game markets and rest chips with no game-fact row are not a
 * real 0-0. Only a finished empty read says so. A prop with no rest
 * chip keeps the ordinary empty label.
 */
export function byomEmptyLabel(
  sport: ByomSport,
  factsStatus: 'ready' | 'loading' | 'missing' | 'error',
  filters: ByomFilters | null | undefined,
): string {
  if (sport === 'NBA' && factsStatus === 'missing' && filtersNeedGameFacts(filters)) {
    return NBA_NO_HISTORY;
  }
  return 'No games match';
}

/**
 * Another saved model with this name, after trim. The save matches the
 * stored name exactly, so a different case is a different name. The model
 * being edited is not a collision with itself.
 */
export function otherModelWithName<T extends { model_id: string; name: string }>(
  models: readonly T[],
  name: string,
  exceptId?: string,
): T | null {
  const trimmed = name.trim();
  for (const model of models) {
    if (model.name === trimmed && model.model_id !== exceptId) return model;
  }
  return null;
}

function suggestedPropName(draft: ByomDraft): string {
  const label = propMarketLabel(draft.market) ?? 'Props';
  const lead: string[] = [];
  if (draft.primetime === true) lead.push('Primetime');
  if (draft.side === 'home') lead.push(lead.length ? 'home' : 'Home');
  else if (draft.side === 'away') lead.push(lead.length ? 'away' : 'Away');
  const stat = lead.length ? label.charAt(0).toLowerCase() + label.slice(1) : label;
  const parts = [...lead, stat];
  if (isYesOnlyProp(draft.market)) return parts.join(' ');
  if (draft.propSide === 'over') parts.push('over');
  else if (draft.propSide === 'under') parts.push('under');
  return parts.join(' ');
}

function withRest(draft: ByomDraft, name: string): string {
  const rest = draft.rest === 'b2b'
    ? 'Back-to-back'
    : draft.rest === 'rest2'
      ? '2+ days rest'
      : null;
  if (rest == null) return name;
  return `${rest} ${name.charAt(0).toLowerCase()}${name.slice(1)}`;
}

export function suggestedName(draft: ByomDraft): string {
  if (isPropMarket(draft.market)) return withRest(draft, suggestedPropName(draft));
  if (draft.market === 'totals') {
    const totalSide = sideForMarket('totals', draft.side);
    if (draft.primetime === true && totalSide == null) return withRest(draft, 'Primetime over/under');
    const label = totalSide === 'over' ? 'Over' : totalSide === 'under' ? 'Under' : 'Over/under';
    if (draft.primetime === true) return withRest(draft, `Primetime ${label.toLowerCase()}`);
    return withRest(draft, label);
  }
  const bits: string[] = [];
  if (draft.primetime === true) bits.push('Primetime');
  if (draft.side === 'home') bits.push('Home');
  else if (draft.side === 'away') bits.push('Away');
  if (draft.role === 'favorite') bits.push('Favorites');
  else if (draft.role === 'underdog') bits.push('Underdogs');
  else if (draft.role === 'pickem') bits.push('Pick’ems');
  if (bits.length === 0) return withRest(draft, MARKET_LABEL[draft.market]);
  const [first, ...rest] = bits;
  return withRest(draft, [first, ...rest.map((word) => word.toLowerCase())].join(' '));
}

export interface Rankable {
  id: string;
  name: string;
  bets: number;
  units: number | null;
  showsUnits: boolean;
}

function byName(a: Rankable, b: Rankable): number {
  const name = a.name.localeCompare(b.name);
  if (name !== 0) return name;
  return a.id.localeCompare(b.id);
}

/**
 * Models with a real unit total rank first, highest units first.
 * A model whose units are hidden (an unsided or mixed prop, an unknown
 * market, or units missing) ranks after those.
 * Zero included bets are unranked and sort last.
 */
export function rankByUnits<T extends Rankable>(items: readonly T[]): Array<T & { rank: number | null }> {
  const withBets: T[] = [];
  const without: T[] = [];
  for (const item of items) {
    if (item.bets > 0) withBets.push(item);
    else without.push(item);
  }
  const real = (item: T) => item.showsUnits && item.units != null && Number.isFinite(item.units);
  withBets.sort((a, b) => {
    const ar = real(a);
    const br = real(b);
    if (ar !== br) return ar ? -1 : 1;
    if (ar && br && a.units !== b.units) return (b.units as number) - (a.units as number);
    if (!ar && a.bets !== b.bets) return b.bets - a.bets;
    return byName(a, b);
  });
  without.sort(byName);
  return [
    ...withBets.map((item, index) => ({ ...item, rank: index + 1 })),
    ...without.map((item) => ({ ...item, rank: null })),
  ];
}

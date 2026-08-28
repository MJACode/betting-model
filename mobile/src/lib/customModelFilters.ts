/**
 * Custom-model filters — the data points a user can slice their own model on,
 * beyond "which model_id at what probability and edge".
 *
 * Two halves:
 *   - the matcher (`pickMatchesFilters`), pure and shared by the live preview,
 *     the Models list, and the backtest so all three agree by construction;
 *   - the catalog (`CHIP_GROUPS`, `describeFilters`), so the builder renders
 *     the chip rows from one list and a new data point is a one-line addition.
 *
 * Every field is optional; absent or empty means no constraint. That keeps
 * models saved before filters existed behaving exactly as they did.
 *
 * Filters read only columns on the `picks` row itself — no games/weather join —
 * which is what lets the same predicate run against today's board and against
 * `fetchSettledPicks` for the backtest.
 */

import { MODEL_META } from './modelMeta';
import type {
  BetKind,
  ConfidenceTier,
  CustomModelFilters,
  DayType,
  // Aliased: `Pick` is also TypeScript's built-in utility type, which this
  // module uses to describe the subset of columns the matcher reads.
  Pick as PickRow,
  PickSide,
  PriceSide,
  TimeSlot,
} from '@/types';

/** A pick as the matcher needs it — lets tests and callers pass partials. */
export type FilterablePick = Pick<
  PickRow,
  | 'model_id'
  | 'pick_side'
  | 'signal_type'
  | 'dk_odds'
  | 'scored_line'
  | 'game_date'
  | 'game_time'
  | 'confidence_tier'
  | 'public_bet_pct'
  | 'injury_flag'
  | 'player_id'
>;

export const EMPTY_FILTERS: CustomModelFilters = {};

/**
 * New models start unconstrained — the user's own model % / edge / EV minimums
 * on each bet type are what define a qualifying pick. (The old BET-only signal
 * default was removed with the signal filter, 2026-08-22.)
 */
export const DEFAULT_FILTERS: CustomModelFilters = {};

/**
 * Strip legacy keys the matcher no longer evaluates before a filters object is
 * used anywhere — client matcher or server RPC. Today that is only `signals`
 * (removed from the builder 2026-08-22): without this, an old saved model
 * would still send signals to the RPC while the client matcher ignores it, and
 * the two would disagree.
 */
export function sanitizeFilters(
  filters: CustomModelFilters | undefined,
): CustomModelFilters {
  if (!filters) return {};
  if (filters.signals === undefined) return filters;
  const { signals: _legacy, ...rest } = filters;
  return rest;
}

// ---------------------------------------------------------------------------
// Derivations
// ---------------------------------------------------------------------------

/**
 * Hour 0-23 of an ISO timestamp in America/New_York, or null if unparseable.
 * `hour12: false` renders midnight as "24" in en-US, hence the modulo.
 */
export function etHour(iso: string | null | undefined): number | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    const raw = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      hour: 'numeric',
      hour12: false,
    }).format(d);
    const n = parseInt(raw, 10);
    return Number.isFinite(n) ? n % 24 : null;
  } catch {
    return null;
  }
}

/**
 * Which slate a game belongs to, in ET. Buckets follow the real distribution of
 * scored picks: a big afternoon block, a 4-7pm shoulder, the 7-10pm bulk, and a
 * west-coast tail. Post-midnight starts belong to the previous night's tail, so
 * hours 0-4 count as late rather than as the next day's afternoon.
 */
export function timeSlotOf(pick: Pick<FilterablePick, 'game_time'>): TimeSlot | null {
  const h = etHour(pick.game_time);
  if (h == null) return null;
  if (h >= 22 || h < 5) return 'late';
  if (h < 16) return 'day';
  if (h < 19) return 'early';
  return 'prime';
}

/**
 * Minus money vs plus money on the pick side. Null when the pick carries no DK
 * price (prob-only markets), which a price filter then excludes.
 * Even money (+100) counts as a dog — it is plus money and pays over 1:1.
 */
export function priceSideOf(pick: Pick<FilterablePick, 'dk_odds'>): PriceSide | null {
  if (pick.dk_odds == null) return null;
  return Number(pick.dk_odds) < 0 ? 'fav' : 'dog';
}

/** Game market vs player prop, from the model registry (falls back to player_id). */
export function betKindOf(pick: Pick<FilterablePick, 'model_id' | 'player_id'>): BetKind {
  const type = MODEL_META[pick.model_id]?.type;
  if (type) return type === 'game' ? 'game' : 'prop';
  return pick.player_id == null ? 'game' : 'prop';
}

/**
 * Weekday vs weekend, from game_date ('YYYY-MM-DD', already the ET date the
 * pipeline stamps) — the same column the server RPC buckets on, so the live
 * preview and the backtest can't disagree. UTC-noon parse avoids the
 * previous-day rollback `new Date('YYYY-MM-DD')` gives US timezones.
 */
export function dayTypeOf(pick: Pick<FilterablePick, 'game_date'>): DayType | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(pick.game_date ?? '');
  if (!m) return null;
  const dow = new Date(Date.UTC(+m[1]!, +m[2]! - 1, +m[3]!, 12)).getUTCDay();
  return dow === 0 || dow === 6 ? 'weekend' : 'weekday';
}

/**
 * EV per $1 staked at the DK price: p × decimal − 1. Null when there is no DK
 * price (prob-only markets) — an EV floor then excludes the pick, same as the
 * price filters.
 */
export function evOf(modelProb: number, dkOdds: number | null | undefined): number | null {
  if (dkOdds == null) return null;
  const odds = Number(dkOdds);
  if (!Number.isFinite(odds) || odds === 0) return null;
  const decimal = odds > 0 ? 1 + odds / 100 : 1 + 100 / Math.abs(odds);
  return modelProb * decimal - 1;
}

// ---------------------------------------------------------------------------
// Matcher
// ---------------------------------------------------------------------------

/**
 * American odds are monotonic in payout across the whole range despite the sign
 * flip (-300 < -140 < -110 < +100 < +150 orders identically to their decimal
 * payouts 1.33 < 1.71 < 1.91 < 2.00 < 2.50), so a plain numeric compare is a
 * correct price floor/ceiling. Same convention as config.MODEL_MIN_ODDS.
 */
export function pickMatchesFilters(
  pick: FilterablePick,
  filters: CustomModelFilters | undefined,
): boolean {
  if (!filters) return true;

  // filters.signals is deliberately NOT evaluated — the signal filter was
  // removed 2026-08-22; a legacy saved value is ignored (see sanitizeFilters).
  // betKinds also left the builder, but models saved with it are still honored.
  if (filters.betKinds?.length && !filters.betKinds.includes(betKindOf(pick))) return false;
  if (filters.sides?.length && !filters.sides.includes(pick.pick_side)) return false;

  if (filters.price?.length) {
    const side = priceSideOf(pick);
    if (side == null || !filters.price.includes(side)) return false;
  }

  if (filters.timeSlots?.length) {
    const slot = timeSlotOf(pick);
    if (slot == null || !filters.timeSlots.includes(slot)) return false;
  }

  if (filters.dayTypes?.length) {
    const day = dayTypeOf(pick);
    if (day == null || !filters.dayTypes.includes(day)) return false;
  }

  if (filters.tiers?.length) {
    const tier = pick.confidence_tier;
    if (!tier || !filters.tiers.includes(tier)) return false;
  }

  if (filters.minOdds != null) {
    if (pick.dk_odds == null || Number(pick.dk_odds) < filters.minOdds) return false;
  }
  if (filters.maxOdds != null) {
    if (pick.dk_odds == null || Number(pick.dk_odds) > filters.maxOdds) return false;
  }

  // Line value — the total/spread/prop line the pick was priced at. Moneyline
  // picks carry no line, so either bound excludes them (missing-datum rule).
  if (filters.minLine != null) {
    if (pick.scored_line == null || Number(pick.scored_line) < filters.minLine) return false;
  }
  if (filters.maxLine != null) {
    if (pick.scored_line == null || Number(pick.scored_line) > filters.maxLine) return false;
  }

  // Only full-game ML/spread/totals carry Action Network splits, so a public
  // filter necessarily drops props and F5 — surfaced in the builder's helper text.
  if (filters.maxPublicBetPct != null) {
    if (pick.public_bet_pct == null || Number(pick.public_bet_pct) > filters.maxPublicBetPct) {
      return false;
    }
  }
  if (filters.minPublicBetPct != null) {
    if (pick.public_bet_pct == null || Number(pick.public_bet_pct) < filters.minPublicBetPct) {
      return false;
    }
  }

  if (filters.excludeInjuries && pick.injury_flag && pick.injury_flag.trim() !== '') return false;

  return true;
}

/**
 * Models whose every scored pick (BET + AVOID + dead-zone NONE) is graded into
 * mv_scored_pick_outcomes on the server. Rules on these models backtest through
 * the custom_model_backtest RPC against the full ~100k-pick universe; rules on
 * anything else (UFC/NHL/golf — no server grading yet) fall back to the settled
 * BET/AVOID rows, which is all that exists for them.
 * Mirrors the matview's WHERE clause — keep the two in step.
 */
export function isOutcomeGraded(modelId: string): boolean {
  return (
    modelId === 'mlb_moneyline' ||
    modelId === 'mlb_over_under' ||
    modelId === 'mlb_runline' ||
    modelId === 'mlb_f5_moneyline' ||
    modelId === 'wnba_moneyline' ||
    modelId.startsWith('mlb_prop_') ||
    modelId.startsWith('wnba_prop_')
  );
}

/** True when nothing is constrained — used to show "no filters" copy.
 *  Legacy `signals` is ignored here too, since the matcher ignores it. */
export function hasAnyFilter(filters: CustomModelFilters | undefined): boolean {
  if (!filters) return false;
  return (
    (filters.betKinds?.length ?? 0) > 0 ||
    (filters.sides?.length ?? 0) > 0 ||
    (filters.price?.length ?? 0) > 0 ||
    (filters.timeSlots?.length ?? 0) > 0 ||
    (filters.dayTypes?.length ?? 0) > 0 ||
    (filters.tiers?.length ?? 0) > 0 ||
    filters.minOdds != null ||
    filters.maxOdds != null ||
    filters.minLine != null ||
    filters.maxLine != null ||
    filters.maxPublicBetPct != null ||
    filters.minPublicBetPct != null ||
    filters.excludeInjuries === true
  );
}

// ---------------------------------------------------------------------------
// Catalog — the builder renders its chip rows from this
// ---------------------------------------------------------------------------

/** Keys of CustomModelFilters whose value is an array of string options.
 *  `signals` (removed) and `betKinds` (subsumed by the bet-type rules) no
 *  longer render as chip groups. */
export type ChipKey = 'sides' | 'price' | 'timeSlots' | 'dayTypes' | 'tiers';

export interface ChipGroup {
  key: ChipKey;
  title: string;
  help: string;
  options: Array<{ value: string; label: string }>;
}

export const CHIP_GROUPS: ChipGroup[] = [
  {
    key: 'sides',
    title: 'Pick side',
    help: 'Home and Away only exist on game markets. Over and Under cover totals and player props.',
    options: [
      { value: 'home', label: 'Home' },
      { value: 'away', label: 'Away' },
      { value: 'over', label: 'Over' },
      { value: 'under', label: 'Under' },
    ],
  },
  {
    key: 'price',
    title: 'Price',
    help: 'Favorites are minus money, underdogs plus money. Picks with no DK price are excluded either way.',
    options: [
      { value: 'fav', label: 'Favorites (−)' },
      { value: 'dog', label: 'Underdogs (+)' },
    ],
  },
  {
    key: 'timeSlots',
    title: 'Game time',
    help: 'When first pitch or tip-off is, in ET.',
    options: [
      { value: 'day', label: 'Day (before 4p)' },
      { value: 'early', label: 'Early (4–7p)' },
      { value: 'prime', label: 'Prime (7–10p)' },
      { value: 'late', label: 'Late (10p+)' },
    ],
  },
  {
    key: 'dayTypes',
    title: 'Day of week',
    help: 'Weekend slates (Saturday and Sunday, ET) play differently — more day games, more casual money.',
    options: [
      { value: 'weekday', label: 'Weekdays' },
      { value: 'weekend', label: 'Weekends' },
    ],
  },
  {
    key: 'tiers',
    title: 'Confidence',
    help: "The model's own confidence tier on the pick.",
    options: [
      { value: 'HIGH', label: 'High' },
      { value: 'MED', label: 'Medium' },
      { value: 'LOW', label: 'Low' },
    ],
  },
];

/** Current selection for a chip group, always an array. */
export function chipSelection(filters: CustomModelFilters, key: ChipKey): string[] {
  return (filters[key] as string[] | undefined) ?? [];
}

/** Toggle one option in a chip group, dropping the key entirely when emptied. */
export function toggleChip(
  filters: CustomModelFilters,
  key: ChipKey,
  value: string,
): CustomModelFilters {
  const current = chipSelection(filters, key);
  const next = current.includes(value)
    ? current.filter((v) => v !== value)
    : [...current, value];
  const out = { ...filters };
  if (next.length === 0) delete out[key];
  else if (key === 'sides') out.sides = next as PickSide[];
  else if (key === 'price') out.price = next as PriceSide[];
  else if (key === 'timeSlots') out.timeSlots = next as TimeSlot[];
  else if (key === 'dayTypes') out.dayTypes = next as DayType[];
  else out.tiers = next as Exclude<ConfidenceTier, null>[];
  return out;
}

// ---------------------------------------------------------------------------
// Scrollable option sets
// ---------------------------------------------------------------------------

/**
 * The values the line and public-backing pickers scroll through, so those
 * filters are a choice rather than a free-text box.
 *
 * Line value spans every market we price: spreads are stored home-relative and
 * go negative (an NBA -12.5), prop lines sit at 0.5-12.5, baseball and hockey
 * totals at 6-12, and basketball totals run past 230 — hence the widening
 * steps rather than one uniform increment.
 */
function buildLineValueOptions(): number[] {
  const out: number[] = [];
  for (let v = -30; v < 16; v += 0.5) out.push(Number(v.toFixed(1)));
  for (let v = 16; v < 61; v += 1) out.push(v);
  for (let v = 65; v <= 250; v += 5) out.push(v);
  return out;
}

export const LINE_VALUE_OPTIONS: number[] = buildLineValueOptions();

/** Public backing is a share of tickets — whole 5% steps are finer than the
 *  signal in the data justifies. */
export const PUBLIC_PCT_OPTIONS: number[] = Array.from({ length: 21 }, (_, i) => i * 5);

/**
 * The option a stored value should highlight. Models saved when these filters
 * were free text can hold a number that is not on the list (8.25, 63%), so the
 * picker marks the closest one rather than showing nothing selected.
 */
export function nearestOption(options: number[], value: number | null | undefined): number | null {
  if (value == null || options.length === 0) return null;
  let best = options[0]!;
  for (const o of options) {
    if (Math.abs(o - value) < Math.abs(best - value)) best = o;
  }
  return best;
}

/** Set (or clear, when value is null) one of the numeric filters. */
export function setNumericFilter(
  filters: CustomModelFilters,
  key: 'minOdds' | 'maxOdds' | 'minLine' | 'maxLine' | 'maxPublicBetPct' | 'minPublicBetPct',
  value: number | null,
): CustomModelFilters {
  const out = { ...filters };
  if (value == null) delete out[key];
  else out[key] = value;
  return out;
}

const LABEL_OF: Record<string, string> = Object.fromEntries(
  CHIP_GROUPS.flatMap((g) => g.options.map((o) => [`${g.key}:${o.value}`, o.label])),
);

/**
 * Short human chips describing what a model filters on — rendered on the model
 * detail screen and under each row in the Models list.
 */
export function describeFilters(filters: CustomModelFilters | undefined): string[] {
  if (!filters) return [];
  const out: string[] = [];
  // Legacy betKinds (pre-2026-08-22 models) still matches, so still describe it.
  if (filters.betKinds?.length === 1) {
    out.push(filters.betKinds[0] === 'game' ? 'Game bets' : 'Player props');
  }
  for (const group of CHIP_GROUPS) {
    const sel = chipSelection(filters, group.key);
    // All options selected constrains nothing — don't spend a chip saying so.
    if (sel.length === 0 || sel.length === group.options.length) continue;
    out.push(sel.map((v) => LABEL_OF[`${group.key}:${v}`] ?? v).join(' / '));
  }
  if (filters.minOdds != null) out.push(`Price ≥ ${fmtAmerican(filters.minOdds)}`);
  if (filters.maxOdds != null) out.push(`Price ≤ ${fmtAmerican(filters.maxOdds)}`);
  if (filters.minLine != null) out.push(`Line ≥ ${filters.minLine}`);
  if (filters.maxLine != null) out.push(`Line ≤ ${filters.maxLine}`);
  if (filters.maxPublicBetPct != null) out.push(`Public ≤ ${filters.maxPublicBetPct}%`);
  if (filters.minPublicBetPct != null) out.push(`Public ≥ ${filters.minPublicBetPct}%`);
  if (filters.excludeInjuries) out.push('No injury flags');
  return out;
}

function fmtAmerican(v: number): string {
  return v > 0 ? `+${v}` : String(v);
}

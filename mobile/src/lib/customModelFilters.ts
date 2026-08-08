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
  // Aliased: `Pick` is also TypeScript's built-in utility type, which this
  // module uses to describe the subset of columns the matcher reads.
  Pick as PickRow,
  PickSide,
  PriceSide,
  SignalType,
  TimeSlot,
} from '@/types';

/** A pick as the matcher needs it — lets tests and callers pass partials. */
export type FilterablePick = Pick<
  PickRow,
  | 'model_id'
  | 'pick_side'
  | 'signal_type'
  | 'dk_odds'
  | 'game_time'
  | 'confidence_tier'
  | 'public_bet_pct'
  | 'injury_flag'
  | 'player_id'
>;

export const EMPTY_FILTERS: CustomModelFilters = {};

/** New models start BET-only — the dead-zone rows exist for tracking, not betting. */
export const DEFAULT_FILTERS: CustomModelFilters = { signals: ['BET'] };

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

  if (filters.signals?.length && !filters.signals.includes(pick.signal_type)) return false;
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

/** True when nothing is constrained — used to show "no filters" copy. */
export function hasAnyFilter(filters: CustomModelFilters | undefined): boolean {
  if (!filters) return false;
  return (
    (filters.signals?.length ?? 0) > 0 ||
    (filters.betKinds?.length ?? 0) > 0 ||
    (filters.sides?.length ?? 0) > 0 ||
    (filters.price?.length ?? 0) > 0 ||
    (filters.timeSlots?.length ?? 0) > 0 ||
    (filters.tiers?.length ?? 0) > 0 ||
    filters.minOdds != null ||
    filters.maxOdds != null ||
    filters.maxPublicBetPct != null ||
    filters.minPublicBetPct != null ||
    filters.excludeInjuries === true
  );
}

// ---------------------------------------------------------------------------
// Catalog — the builder renders its chip rows from this
// ---------------------------------------------------------------------------

/** Keys of CustomModelFilters whose value is an array of string options. */
export type ChipKey = 'signals' | 'betKinds' | 'sides' | 'price' | 'timeSlots' | 'tiers';

export interface ChipGroup {
  key: ChipKey;
  title: string;
  help: string;
  options: Array<{ value: string; label: string }>;
}

export const CHIP_GROUPS: ChipGroup[] = [
  {
    key: 'signals',
    title: 'Signal',
    help: 'BET is what the model actually recommends. AVOID and no-signal rows are scored for tracking.',
    options: [
      { value: 'BET', label: 'Bet' },
      { value: 'AVOID', label: 'Avoid' },
      { value: 'NONE', label: 'No signal' },
    ],
  },
  {
    key: 'betKinds',
    title: 'Bet type',
    help: 'Game markets are moneyline, totals and spreads. Props are the player markets.',
    options: [
      { value: 'game', label: 'Game' },
      { value: 'prop', label: 'Player prop' },
    ],
  },
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
  else if (key === 'signals') out.signals = next as SignalType[];
  else if (key === 'betKinds') out.betKinds = next as BetKind[];
  else if (key === 'sides') out.sides = next as PickSide[];
  else if (key === 'price') out.price = next as PriceSide[];
  else if (key === 'timeSlots') out.timeSlots = next as TimeSlot[];
  else out.tiers = next as Exclude<ConfidenceTier, null>[];
  return out;
}

/** Set (or clear, when value is null) one of the numeric filters. */
export function setNumericFilter(
  filters: CustomModelFilters,
  key: 'minOdds' | 'maxOdds' | 'maxPublicBetPct' | 'minPublicBetPct',
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
  for (const group of CHIP_GROUPS) {
    const sel = chipSelection(filters, group.key);
    // All options selected constrains nothing — don't spend a chip saying so.
    if (sel.length === 0 || sel.length === group.options.length) continue;
    out.push(sel.map((v) => LABEL_OF[`${group.key}:${v}`] ?? v).join(' / '));
  }
  if (filters.minOdds != null) out.push(`DK ≥ ${fmtAmerican(filters.minOdds)}`);
  if (filters.maxOdds != null) out.push(`DK ≤ ${fmtAmerican(filters.maxOdds)}`);
  if (filters.maxPublicBetPct != null) out.push(`Public ≤ ${filters.maxPublicBetPct}%`);
  if (filters.minPublicBetPct != null) out.push(`Public ≥ ${filters.minPublicBetPct}%`);
  if (filters.excludeInjuries) out.push('No injury flags');
  return out;
}

function fmtAmerican(v: number): string {
  return v > 0 ? `+${v}` : String(v);
}

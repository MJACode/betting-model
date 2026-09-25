/**
 * The optional bankroll in Settings — a DISPLAY conversion and nothing else
 * (Designer Option A, Matt-approved 2026-09-25; Matt: "No daily limit. This is
 * purely informational display.").
 *
 * The app publishes every pick in flat units (lib/thresholds.ts), the same for
 * every reader and the Discord channel. A member may type their bankroll so
 * Settings can say what one of their units is worth in dollars. Nothing is
 * sized off it: no Kelly, no stake, no limit reads this module. It stays on the
 * device under `bankroll.v2`.
 *
 * The retired #786 key `bankroll` is NEVER read: it defaulted to $1,000 when
 * unset, and a figure the member never typed must not appear as theirs.
 *
 * Pure (no React, no AsyncStorage import) so scripts/verify_bankroll.ts can pin
 * every rule; hooks/useBankroll.ts wires it to AsyncStorage. Relative imports
 * only — tsx does not resolve the '@/…' alias for a value import.
 */

// ── Storage ────────────────────────────────────────────────────────────────
export const BANKROLL_KEY = 'bankroll.v2';
/** #786's key. Named only so the verify script can prove nothing reads it. */
export const LEGACY_BANKROLL_KEY = 'bankroll';

export const BANKROLL_MIN = 10;
export const BANKROLL_MAX = 10_000_000;

export const UNIT_PCT_DEFAULT = 1;
export const UNIT_PCT_MIN = 0.5;
export const UNIT_PCT_MAX = 5;
export const UNIT_PCT_STEP = 0.5;

export interface BankrollSettings {
  /** Dollars, or null when the member has not entered one (the default). */
  amount: number | null;
  /** One unit as a percent of the bankroll: 0.5–5 in 0.5 steps. */
  unitPct: number;
}

export const BANKROLL_DEFAULTS: BankrollSettings = { amount: null, unitPct: UNIT_PCT_DEFAULT };

/** Snap to the 0.5% grid inside 0.5–5%. Anything unreadable is the default. */
export function sanitizeUnitPct(raw: unknown): number {
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return UNIT_PCT_DEFAULT;
  const snapped = Math.round(raw / UNIT_PCT_STEP) * UNIT_PCT_STEP;
  return Math.min(UNIT_PCT_MAX, Math.max(UNIT_PCT_MIN, snapped));
}

/** A stored value that would fail validation today is dropped, not shown. */
export function sanitizeBankroll(raw: unknown): BankrollSettings {
  if (!raw || typeof raw !== 'object') return { ...BANKROLL_DEFAULTS };
  const o = raw as Record<string, unknown>;
  const a = o.amount;
  const amount =
    typeof a === 'number' && Number.isFinite(a) && a >= BANKROLL_MIN && a <= BANKROLL_MAX
      ? Math.round(a * 100) / 100
      : null;
  return { amount, unitPct: sanitizeUnitPct(o.unitPct) };
}

export interface KeyValueStore {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
}

/** Reads `bankroll.v2` and only that key. */
export async function readBankroll(store: KeyValueStore): Promise<BankrollSettings> {
  try {
    const raw = await store.getItem(BANKROLL_KEY);
    return raw ? sanitizeBankroll(JSON.parse(raw)) : { ...BANKROLL_DEFAULTS };
  } catch {
    return { ...BANKROLL_DEFAULTS };
  }
}

export async function writeBankroll(store: KeyValueStore, s: BankrollSettings): Promise<void> {
  const clean = sanitizeBankroll(s);
  await store.setItem(BANKROLL_KEY, JSON.stringify(clean));
}

// ── The field ──────────────────────────────────────────────────────────────
/** Integer digits kept while typing: 10M has 8, so 12 leaves room for the
 *  live over-the-limit error without letting a paste run to float noise. */
const MAX_INT_DIGITS = 12;

function group(intDigits: string): string {
  return intDigits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * What the field shows for whatever was typed or pasted: digits and one
 * decimal point, thousands separators, at most two decimals. A minus sign
 * before the first digit (only a paste can produce one — the decimal pad has
 * no minus key) is kept, so the "positive amount" error has something to
 * point at; every other character goes.
 */
export function formatBankrollInput(raw: string): string {
  const firstDigit = raw.search(/[0-9.]/);
  const negative = raw.includes('-') && (firstDigit === -1 || raw.indexOf('-') < firstDigit);
  const kept = raw.replace(/[^0-9.]/g, '');
  const dot = kept.indexOf('.');
  let intPart = dot === -1 ? kept : kept.slice(0, dot);
  const frac = dot === -1 ? null : kept.slice(dot + 1).replace(/\./g, '').slice(0, 2);
  intPart = intPart.replace(/^0+(?=\d)/, '').slice(0, MAX_INT_DIGITS);
  if (intPart === '' && frac !== null) intPart = '0';
  const body = group(intPart) + (frac !== null ? `.${frac}` : '');
  return negative && body !== '' ? `-${body}` : negative ? '-' : body;
}

/** The field's text back to a number (NaN when there is no number in it). */
export function parseBankrollInput(text: string): number {
  const cleaned = text.replace(/,/g, '');
  if (!/[0-9]/.test(cleaned)) return Number.NaN;
  return Number(cleaned);
}

export const BANKROLL_ERRORS = {
  zero: 'Enter an amount greater than $0.',
  negative: 'Enter a positive dollar amount.',
  tooSmall: 'Enter at least $10.',
  tooLarge: "That's more than we can convert. Enter $10,000,000 or less.",
} as const;

export type BankrollCheck =
  | { state: 'empty' }
  | { state: 'valid'; amount: number }
  /** `live`: shown while typing. Every other error waits for blur or Done. */
  | { state: 'invalid'; message: string; live: boolean };

export function checkBankroll(text: string): BankrollCheck {
  const t = text.trim();
  if (t === '') return { state: 'empty' };
  if (t.startsWith('-')) return { state: 'invalid', message: BANKROLL_ERRORS.negative, live: false };
  const n = parseBankrollInput(t);
  if (!Number.isFinite(n) || n <= 0) return { state: 'invalid', message: BANKROLL_ERRORS.zero, live: false };
  if (n > BANKROLL_MAX) return { state: 'invalid', message: BANKROLL_ERRORS.tooLarge, live: true };
  if (n < BANKROLL_MIN) return { state: 'invalid', message: BANKROLL_ERRORS.tooSmall, live: false };
  return { state: 'valid', amount: Math.round(n * 100) / 100 };
}

/** The error to show now: live ones always, the rest once the member has left
 *  the field or tapped Done (`committed`). Clearing the field is never one. */
export function visibleBankrollError(check: BankrollCheck, committed: boolean): string | null {
  if (check.state !== 'invalid') return null;
  return check.live || committed ? check.message : null;
}

/** The text a saved amount is shown as when the field is not being edited. */
export function bankrollFieldText(amount: number | null): string {
  if (amount == null) return '';
  const [whole, cents] = (Math.round(amount * 100) / 100).toFixed(2).split('.');
  return group(whole) + (cents === '00' ? '' : `.${cents}`);
}

// ── Units → dollars (display only) ────────────────────────────────────────
/** One unit in dollars, or null with no bankroll. */
export function unitDollars(s: BankrollSettings): number | null {
  return s.amount == null ? null : (s.amount * s.unitPct) / 100;
}

/**
 * Dollars for display. Whole dollars once a unit is worth $10 or more (cents
 * are noise at that size), cents below it (a $0.10 unit is not "$0").
 */
export function formatDollars(value: number, unit: number): string {
  if (unit >= 10) return `$${group(String(Math.round(value)))}`;
  const [whole, cents] = (Math.round(value * 100) / 100).toFixed(2).split('.');
  return `$${group(whole)}.${cents}`;
}

export function formatPct(pct: number): string {
  return `${Number.isInteger(pct) ? pct : pct.toFixed(1)}%`;
}

/** Lower (−1) / Raise (+1) by one 0.5% step, held inside 0.5–5%. */
export function stepUnitPct(pct: number, dir: -1 | 1): number {
  return sanitizeUnitPct(sanitizeUnitPct(pct) + dir * UNIT_PCT_STEP);
}

export function canStepUnitPct(pct: number, dir: -1 | 1): boolean {
  return stepUnitPct(pct, dir) !== sanitizeUnitPct(pct);
}

/** "1 unit = $20" with a bankroll; "1 unit = 1%" without — no $ anywhere. */
export function unitRowTitle(s: BankrollSettings): string {
  const u = unitDollars(s);
  return u == null ? `1 unit = ${formatPct(s.unitPct)}` : `1 unit = ${formatDollars(u, u)}`;
}

/** The suggestion is 1%; any other size simply drops the tag. */
export function unitRowSubtitle(s: BankrollSettings): string {
  const suggested = s.unitPct === UNIT_PCT_DEFAULT ? ' · suggested' : '';
  return s.amount == null
    ? `of bankroll${suggested} · add a bankroll to see $`
    : `${formatPct(s.unitPct)} of bankroll${suggested}`;
}

export const BANKROLL_CARD_COPY =
  'Only used to show your units in dollars. Nothing is sized off it, and it stays on this device.';

export const BANKROLL_FOOTER_COPY =
  'A unit is your standard bet. As a starting point, we suggest 1 unit = 1% of your bankroll. Change it to fit your budget, and only bet what you can afford to lose.';

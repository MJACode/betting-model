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

export type BankrollRead = { ok: true; value: BankrollSettings } | { ok: false };

/**
 * Reads `bankroll.v2` and only that key. `ok: false` means storage itself
 * failed, so what is on the device is unknown and must not be written over.
 * Corrupt JSON is `ok: true` with the defaults: there is nothing to keep.
 */
export async function tryReadBankroll(store: KeyValueStore): Promise<BankrollRead> {
  let raw: string | null;
  try {
    raw = await store.getItem(BANKROLL_KEY);
  } catch {
    return { ok: false };
  }
  try {
    return { ok: true, value: raw ? sanitizeBankroll(JSON.parse(raw)) : { ...BANKROLL_DEFAULTS } };
  } catch {
    return { ok: true, value: { ...BANKROLL_DEFAULTS } };
  }
}

/** The settings to show: the defaults when storage could not be read. */
export async function readBankroll(store: KeyValueStore): Promise<BankrollSettings> {
  const r = await tryReadBankroll(store);
  return r.ok ? r.value : { ...BANKROLL_DEFAULTS };
}

export async function writeBankroll(store: KeyValueStore, s: BankrollSettings): Promise<void> {
  const clean = sanitizeBankroll(s);
  await store.setItem(BANKROLL_KEY, JSON.stringify(clean));
}

export type BankrollPatch =
  | Partial<BankrollSettings>
  /** Computed from the latest value at apply time, e.g. a unit % step. */
  | ((latest: BankrollSettings) => Partial<BankrollSettings>);

/**
 * The in-memory store behind hooks/useBankroll.ts (Reviewer, #831):
 *  - Every update applies its patch to the LATEST value, after the first load —
 *    never to a value captured when the setter was called — and writes go out
 *    through one promise chain, so an amount and a unit % set back to back both
 *    survive, in memory and in storage, whatever order they land in.
 *  - The first read is shared: however many loads and updates arrive on a cold
 *    start, storage is read once (`reading ??=`).
 *  - A FAILED read is not cached. `load()` shows the defaults but leaves the
 *    store unloaded; the next update reads again, and if storage still can't be
 *    read the update is refused rather than writing defaults over real data.
 */
export function createBankrollStore(kv: KeyValueStore) {
  let current: BankrollSettings | null = null;
  let reading: Promise<void> | null = null;
  let writes: Promise<void> = Promise.resolve();
  const listeners = new Set<(s: BankrollSettings) => void>();

  /** One read in flight at a time; sets `current` only when it succeeded. */
  const readOnce = (): Promise<void> => {
    reading ??= tryReadBankroll(kv).then((r) => {
      reading = null;
      if (r.ok) current ??= r.value;
    });
    return reading;
  };

  const load = async (): Promise<BankrollSettings> => {
    if (!current) await readOnce();
    return current ?? { ...BANKROLL_DEFAULTS };
  };

  const update = async (patch: BankrollPatch): Promise<void> => {
    if (!current) await readOnce();
    const latest = current;
    if (!latest) {
      console.warn('[bankroll] storage could not be read; not saving over it');
      return;
    }
    const p = typeof patch === 'function' ? patch(latest) : patch;
    const next = sanitizeBankroll({ ...latest, ...p });
    current = next;
    listeners.forEach((fn) => fn(next));
    // Chained, and each write sends the value current AT WRITE TIME, so the
    // last write to land is always the newest state.
    writes = writes
      .then(() => writeBankroll(kv, current ?? next))
      .catch((err) => console.warn('[bankroll] save failed', err));
    return writes;
  };

  return {
    load,
    update,
    get: (): BankrollSettings | null => current,
    subscribe(fn: (s: BankrollSettings) => void): () => void {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}

// ── Separators (Reviewer, #831) ────────────────────────────────────────────
/**
 * The device's decimal and group separators. The decimal pad types the
 * region's decimal key — "," in much of Europe — so "12,50" must read as
 * 12.50, not 1,250. The locale decides; where a comma sits never does.
 */
export interface NumberSeparators {
  decimal: string;
  group: string;
}

export const FALLBACK_SEPARATORS: NumberSeparators = { decimal: '.', group: ',' };

type Part = { type: string; value: string };

/** Separators from Intl parts: the decimal from 1234.5, the group from
 *  1234567.5 (es-ES leaves four-digit numbers ungrouped). Falls back to '.' and
 *  ','; a group that would collide with the decimal becomes the other one. */
export function separatorsFromParts(decimalParts: Part[], groupParts: Part[]): NumberSeparators {
  const decimal = decimalParts.find((p) => p.type === 'decimal')?.value || FALLBACK_SEPARATORS.decimal;
  let group = groupParts.find((p) => p.type === 'group')?.value || FALLBACK_SEPARATORS.group;
  if (group === decimal) group = decimal === ',' ? '.' : ',';
  return { decimal, group };
}

/** `locale` undefined = the device's. Any Intl gap falls back to '.' and ','. */
export function deviceSeparators(locale?: string): NumberSeparators {
  try {
    const fmt = new Intl.NumberFormat(locale);
    if (typeof fmt.formatToParts !== 'function') return { ...FALLBACK_SEPARATORS };
    return separatorsFromParts(fmt.formatToParts(1234.5), fmt.formatToParts(1234567.5));
  } catch {
    return { ...FALLBACK_SEPARATORS };
  }
}

/** Read once; every field function takes separators as a parameter (injectable
 *  for the verify script) and defaults to these. */
export const DEVICE_SEPARATORS: NumberSeparators = deviceSeparators();

// ── The field ──────────────────────────────────────────────────────────────
/** Integer digits kept while typing: 10M has 8, so 12 leaves room for the
 *  live over-the-limit error without letting a paste run to float noise. */
const MAX_INT_DIGITS = 12;

function group(intDigits: string, sep = ','): string {
  return intDigits.replace(/\B(?=(\d{3})+(?!\d))/g, sep);
}

/**
 * Text → canonical "digits[.digits]" (plus whether a minus came before the
 * first digit). The locale decimal separator becomes '.', and every other
 * character — the group separator included — is dropped.
 */
function canonical(raw: string, seps: NumberSeparators): { negative: boolean; digits: string } {
  let firstNumeric = -1;
  let out = '';
  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i];
    if (ch >= '0' && ch <= '9') out += ch;
    else if (ch === seps.decimal) out += '.';
    else continue;
    if (firstNumeric === -1) firstNumeric = i;
  }
  const minus = raw.indexOf('-');
  const negative = minus !== -1 && (firstNumeric === -1 || minus < firstNumeric);
  return { negative, digits: out };
}

/**
 * What the field shows for whatever was typed or pasted: digits and one
 * decimal separator (the device's), its group separators, at most two
 * decimals. A minus sign before the first digit (only a paste can produce one
 * — the decimal pad has no minus key) is kept, so the "positive amount" error
 * has something to point at; every other character goes. Re-reading its own
 * output gives the same text.
 */
export function formatBankrollInput(raw: string, seps: NumberSeparators = DEVICE_SEPARATORS): string {
  const { negative, digits: kept } = canonical(raw, seps);
  const dot = kept.indexOf('.');
  let intPart = dot === -1 ? kept : kept.slice(0, dot);
  const frac = dot === -1 ? null : kept.slice(dot + 1).replace(/\./g, '').slice(0, 2);
  intPart = intPart.replace(/^0+(?=\d)/, '').slice(0, MAX_INT_DIGITS);
  if (intPart === '' && frac !== null) intPart = '0';
  const body = group(intPart, seps.group) + (frac !== null ? `${seps.decimal}${frac}` : '');
  return negative && body !== '' ? `-${body}` : negative ? '-' : body;
}

/**
 * One keystroke: `prev` is the field's text, `raw` what the input now holds.
 * A backspace that only removed a group separator would be re-added by the
 * formatter and the field would stick, so it deletes the digit before the
 * separator instead ("25,000" ⌫ after the comma → "2,000").
 */
export function editBankrollInput(prev: string, raw: string, seps: NumberSeparators = DEVICE_SEPARATORS): string {
  if (raw.length === prev.length - 1) {
    let i = 0;
    while (i < raw.length && raw[i] === prev[i]) i++;
    if (prev[i] === seps.group && raw === prev.slice(0, i) + prev.slice(i + 1)) {
      const before = prev.slice(0, i);
      const j = before.search(/[0-9](?=[^0-9]*$)/);
      if (j !== -1) raw = before.slice(0, j) + before.slice(j + 1) + prev.slice(i + 1);
    }
  }
  return formatBankrollInput(raw, seps);
}

/** The field's text back to a number (NaN when there is no number in it). */
export function parseBankrollInput(text: string, seps: NumberSeparators = DEVICE_SEPARATORS): number {
  const { digits } = canonical(text, seps);
  if (!/[0-9]/.test(digits)) return Number.NaN;
  const dot = digits.indexOf('.');
  return Number(dot === -1 ? digits : digits.slice(0, dot + 1) + digits.slice(dot + 1).replace(/\./g, ''));
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

export function checkBankroll(text: string, seps: NumberSeparators = DEVICE_SEPARATORS): BankrollCheck {
  const t = text.trim();
  if (t === '') return { state: 'empty' };
  if (t.startsWith('-')) return { state: 'invalid', message: BANKROLL_ERRORS.negative, live: false };
  const n = parseBankrollInput(t, seps);
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
export function bankrollFieldText(amount: number | null, seps: NumberSeparators = DEVICE_SEPARATORS): string {
  if (amount == null) return '';
  const [whole, cents] = (Math.round(amount * 100) / 100).toFixed(2).split('.');
  return group(whole, seps.group) + (cents === '00' ? '' : `${seps.decimal}${cents}`);
}

/**
 * What the unit row shows while the field is being edited: the amount in the
 * field when it is valid, otherwise the units-only empty state. Nothing is
 * saved until blur / Done (Reviewer, #831), so a half-edited "2" never becomes
 * the member's $2.
 */
export function bankrollDraft(
  text: string,
  unitPct: number,
  seps: NumberSeparators = DEVICE_SEPARATORS,
): BankrollSettings {
  const c = checkBankroll(text, seps);
  return { amount: c.state === 'valid' ? c.amount : null, unitPct };
}

export interface BankrollCommit {
  /** The field's text after blur / Done. */
  text: string;
  /** The blur-time error to keep showing (the text itself has reverted). */
  error: string | null;
  /** What to save: an amount, null to clear, or undefined to save nothing. */
  save: number | null | undefined;
}

/**
 * Blur or Done. Valid: save it and show it in its saved form. Empty: clear
 * the saved amount. Invalid: save nothing, keep the saved amount, show the
 * error, and put the saved amount back in the field.
 */
export function commitBankrollText(
  text: string,
  savedAmount: number | null,
  seps: NumberSeparators = DEVICE_SEPARATORS,
): BankrollCommit {
  const c = checkBankroll(text, seps);
  if (c.state === 'empty') return { text: '', error: null, save: savedAmount === null ? undefined : null };
  if (c.state === 'valid') {
    return { text: bankrollFieldText(c.amount, seps), error: null, save: c.amount === savedAmount ? undefined : c.amount };
  }
  return { text: bankrollFieldText(savedAmount, seps), error: c.message, save: undefined };
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
  // Compared in cents, as shown: a $9.999 unit displays as $10, so it is a
  // whole-dollar unit — never "$10.00".
  if (Math.round(unit * 100) >= 1000) return `$${group(String(Math.round(value)))}`;
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

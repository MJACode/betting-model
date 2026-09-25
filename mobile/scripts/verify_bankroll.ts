/**
 * Standalone verification of the optional, display-only bankroll in Settings
 * (src/lib/bankroll.ts — Designer Option A, Matt-approved 2026-09-25, scope cut
 * the same day: "No daily limit. This is purely informational display.").
 * Run with:
 *
 *   npx tsx scripts/verify_bankroll.ts
 *
 * Pins: the field's input rules (paste stripping, separators, the 2-decimal
 * cap), every error message and WHEN it shows, clear-to-empty, the dollar
 * display rule, the unit % bounds and steps, the `bankroll.v2` key with the
 * #786 `bankroll` key never read, the empty state (no $ figure anywhere), that
 * nothing sizes a bet off the bankroll (picks stay a flat 1u), and that the
 * daily exposure card, `responsibleGambling.v2` and the Picks banner are
 * untouched.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import {
  BANKROLL_CARD_COPY,
  BANKROLL_DEFAULTS,
  BANKROLL_ERRORS,
  BANKROLL_FOOTER_COPY,
  BANKROLL_KEY,
  BANKROLL_MAX,
  BANKROLL_MIN,
  LEGACY_BANKROLL_KEY,
  UNIT_PCT_DEFAULT,
  UNIT_PCT_MAX,
  UNIT_PCT_MIN,
  UNIT_PCT_STEP,
  bankrollFieldText,
  canStepUnitPct,
  checkBankroll,
  createBankrollStore,
  formatBankrollInput,
  formatDollars,
  formatPct,
  readBankroll,
  sanitizeBankroll,
  sanitizeUnitPct,
  stepUnitPct,
  unitDollars,
  unitRowSubtitle,
  unitRowTitle,
  visibleBankrollError,
  writeBankroll,
  type KeyValueStore,
} from '../src/lib/bankroll';
import { convictionFor, stakeFor } from '../src/lib/thresholds';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail && !cond ? ` — ${detail}` : ''}`);
}
function eq(name: string, got: unknown, want: unknown) {
  check(name, got === want, `got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
}

// ── 1. Typing and pasting ──────────────────────────────────────────────────
eq('thousands separators as you type', formatBankrollInput('2000'), '2,000');
eq('separators at 8 digits', formatBankrollInput('25000000'), '25,000,000');
eq('re-typing over separators regroups', formatBankrollInput('2,0001'), '20,001');
eq('decimals keep their separators', formatBankrollInput('1234567.8'), '1,234,567.8');
eq('at most 2 decimals', formatBankrollInput('12.345'), '12.34');
eq('a third decimal is dropped, not rounded', formatBankrollInput('0.999'), '0.99');
eq('a lone point reads as 0.', formatBankrollInput('.'), '0.');
eq('leading zeros go', formatBankrollInput('007'), '7');
eq('paste: $, commas and letters stripped', formatBankrollInput('$2,000.50abc'), '2,000.50');
eq('paste: spaces stripped', formatBankrollInput(' 1 234 '), '1,234');
eq('paste: only one decimal point survives', formatBankrollInput('1.2.3'), '1.23');
eq('paste: no digits at all is empty', formatBankrollInput('abc'), '');
eq('paste: a leading minus is kept so the error can name it', formatBankrollInput('-500'), '-500');
eq('paste: "$-1,000" is a negative', formatBankrollInput('$-1,000'), '-1,000');
eq('paste: a trailing minus is just stripped', formatBankrollInput('500-'), '500');
eq('a saved amount shows grouped, no ".00"', bankrollFieldText(2000), '2,000');
eq('a saved amount keeps real cents', bankrollFieldText(1234.5), '1,234.50');
eq('no saved amount shows the placeholder', bankrollFieldText(null), '');

// ── 2. Validation: messages and timing ─────────────────────────────────────
const inv = (t: string) => {
  const c = checkBankroll(formatBankrollInput(t));
  return c.state === 'invalid' ? c : null;
};
eq('0 → greater than $0', inv('0')?.message, 'Enter an amount greater than $0.');
eq('0.00 → greater than $0', inv('0.00')?.message, BANKROLL_ERRORS.zero);
eq('a lone point → greater than $0', inv('.')?.message, BANKROLL_ERRORS.zero);
eq('pasted negative → positive amount', inv('-500')?.message, 'Enter a positive dollar amount.');
eq('under $10 → at least $10', inv('9.99')?.message, 'Enter at least $10.');
eq('over $10M → cannot convert', inv('10000000.01')?.message,
  "That's more than we can convert. Enter $10,000,000 or less.");
check('$10 exactly is valid', checkBankroll('10').state === 'valid');
check('$10,000,000 exactly is valid', checkBankroll('10,000,000').state === 'valid');
{
  const c = checkBankroll('2,000.5');
  check('a valid entry parses through its separators', c.state === 'valid' && c.amount === 2000.5);
}
check('bounds are $10 and $10M', BANKROLL_MIN === 10 && BANKROLL_MAX === 10_000_000);
check('only the over-$10M error is live', inv('25000000')?.live === true &&
  [inv('0'), inv('-5'), inv('5')].every((c) => c?.live === false));
check('over $10M shows WHILE typing', visibleBankrollError(checkBankroll('25,000,000'), false) === BANKROLL_ERRORS.tooLarge);
check('under $10 waits for blur / Done', visibleBankrollError(checkBankroll('5'), false) === null &&
  visibleBankrollError(checkBankroll('5'), true) === BANKROLL_ERRORS.tooSmall);
check('0 waits for blur / Done', visibleBankrollError(checkBankroll('0'), false) === null &&
  visibleBankrollError(checkBankroll('0'), true) === BANKROLL_ERRORS.zero);
check('a negative waits for blur / Done', visibleBankrollError(checkBankroll('-500'), false) === null &&
  visibleBankrollError(checkBankroll('-500'), true) === BANKROLL_ERRORS.negative);
check('clearing the field is empty, never an error',
  checkBankroll('').state === 'empty' && visibleBankrollError(checkBankroll(''), true) === null);
check('a valid amount never shows an error', visibleBankrollError(checkBankroll('2,000'), true) === null);

// ── 3. Units → dollars ─────────────────────────────────────────────────────
const s = (amount: number | null, unitPct = 1) => ({ amount, unitPct });
eq('$2,000 at 1% → 1 unit = $20', unitRowTitle(s(2000)), '1 unit = $20');
eq('subtitle at the suggested 1%', unitRowSubtitle(s(2000)), '1% of bankroll · suggested');
eq('another size drops "suggested"', unitRowSubtitle(s(2000, 2)), '2% of bankroll');
eq('half-percent reads 0.5%', unitRowSubtitle(s(2000, 0.5)), '0.5% of bankroll');
eq('a $10 unit is whole dollars', unitRowTitle(s(1000)), '1 unit = $10');
eq('a unit under $10 shows cents', unitRowTitle(s(999)), '1 unit = $9.99');
eq('the smallest unit ($10 at 0.5%) is 5 cents', unitRowTitle(s(10, 0.5)), '1 unit = $0.05');
eq('the largest unit ($10M at 5%)', unitRowTitle(s(10_000_000, 5)), '1 unit = $500,000');
eq('whole dollars round, grouped', formatDollars(1234.5, 12.345), '$1,235');
eq('cents keep two places', formatDollars(0.1, 0.1), '$0.10');
eq('cents are grouped too', formatDollars(1234.5, 9), '$1,234.50');
check('unitDollars is null with no bankroll', unitDollars(s(null)) === null);
check('unitDollars is bankroll × unit %', unitDollars(s(2500, 1.5)) === 37.5);

// ── 4. Empty state: units only ─────────────────────────────────────────────
eq('empty: 1 unit = 1%', unitRowTitle(s(null)), '1 unit = 1%');
eq('empty: the % follows the setting', unitRowTitle(s(null, 2.5)), '1 unit = 2.5%');
eq('empty subtitle', unitRowSubtitle(s(null)), 'of bankroll · suggested · add a bankroll to see $');
check('empty: no dollar figure anywhere', [1, 0.5, 2, 5].every((p) =>
  !/\$\s*\d/.test(unitRowTitle(s(null, p)) + unitRowSubtitle(s(null, p)))));

// ── 5. Unit % bounds and steps ─────────────────────────────────────────────
check('unit %: 1 default, 0.5–5 in 0.5 steps',
  UNIT_PCT_DEFAULT === 1 && UNIT_PCT_MIN === 0.5 && UNIT_PCT_MAX === 5 && UNIT_PCT_STEP === 0.5);
{
  const walk: number[] = [UNIT_PCT_MIN];
  while (canStepUnitPct(walk[walk.length - 1], 1)) walk.push(stepUnitPct(walk[walk.length - 1], 1));
  eq('Raise walks 0.5 → 5 in ten stops', walk.map(formatPct).join(' '),
    '0.5% 1% 1.5% 2% 2.5% 3% 3.5% 4% 4.5% 5%');
}
check('Raise stops at 5%', stepUnitPct(5, 1) === 5 && !canStepUnitPct(5, 1));
check('Lower stops at 0.5%', stepUnitPct(0.5, -1) === 0.5 && !canStepUnitPct(0.5, -1));
check('Lower from 1% → 0.5%', stepUnitPct(1, -1) === 0.5 && canStepUnitPct(1, -1));
check('an off-grid stored % snaps', sanitizeUnitPct(0.74) === 0.5 && sanitizeUnitPct(1.26) === 1.5);
check('an out-of-range stored % clamps', sanitizeUnitPct(7) === 5 && sanitizeUnitPct(0.1) === 0.5);
check('an unreadable stored % is the default', sanitizeUnitPct('2') === 1 && sanitizeUnitPct(NaN) === 1);

// ── 6. Storage: bankroll.v2 only; the #786 key is never read ──────────────
function fakeStore(init: Record<string, string>) {
  const data = { ...init };
  const reads: string[] = [];
  const writes: string[] = [];
  const store: KeyValueStore = {
    async getItem(k) { reads.push(k); return data[k] ?? null; },
    async setItem(k, v) { writes.push(k); data[k] = v; },
  };
  return { store, data, reads, writes };
}
async function storage() {
  eq('the key is bankroll.v2', BANKROLL_KEY, 'bankroll.v2');
  {
    // A device that ran #786 has `bankroll` = "1000" (its default) or a typed value.
    const f = fakeStore({ [LEGACY_BANKROLL_KEY]: '1000' });
    const got = await readBankroll(f.store);
    check('the #786 $1,000 never shows up: no bankroll', got.amount === null && got.unitPct === 1);
    check('the #786 key is never read', !f.reads.includes('bankroll') && f.reads.join() === 'bankroll.v2');
  }
  {
    const f = fakeStore({ [BANKROLL_KEY]: JSON.stringify({ amount: 2000, unitPct: 1.5 }) });
    const got = await readBankroll(f.store);
    check('bankroll.v2 is read back', got.amount === 2000 && got.unitPct === 1.5);
    await writeBankroll(f.store, { amount: 5000, unitPct: 2 });
    check('writes go to bankroll.v2 only', f.writes.join() === 'bankroll.v2' &&
      f.data[BANKROLL_KEY] === JSON.stringify({ amount: 5000, unitPct: 2 }));
    await writeBankroll(f.store, { amount: null, unitPct: 2 });
    check('clearing stores amount null (the % stays)', f.data[BANKROLL_KEY] === JSON.stringify({ amount: null, unitPct: 2 }));
  }
  check('an empty device is the defaults', (await readBankroll(fakeStore({}).store)).amount === null);
  check('corrupt JSON falls back to the defaults',
    JSON.stringify(await readBankroll(fakeStore({ [BANKROLL_KEY]: '{oops' }).store)) === JSON.stringify(BANKROLL_DEFAULTS));
  check('a stored amount that would fail validation is dropped',
    [5, 2e7, -1, 0, '2000', null].every((a) => sanitizeBankroll({ amount: a, unitPct: 1 }).amount === null));
}

// ── 6b. Setters fired back to back both survive (Reviewer, #831) ──────────
// A slow store (every read and write yields several ticks, writes finish out
// of order when allowed to) so a setter that merged into a captured base, or a
// write that raced another, would lose one of the two values.
function slowStore(init: Record<string, string>) {
  const data = { ...init };
  const tick = (n: number) => new Promise<void>((r) => setTimeout(r, n));
  const store: KeyValueStore = {
    async getItem(k) { await tick(5); return data[k] ?? null; },
    async setItem(k, v) { await tick(v.includes('"amount":null') ? 1 : 8); data[k] = v; },
  };
  return { store, data };
}
async function interleaving() {
  const stored = (d: Record<string, string>) => JSON.parse(d[BANKROLL_KEY] ?? '{}');
  const seed = { [BANKROLL_KEY]: JSON.stringify({ amount: 1000, unitPct: 1 }) };
  {
    const f = slowStore(seed);
    const bs = createBankrollStore(f.store);
    const seen: string[] = [];
    bs.subscribe((x) => seen.push(`${x.amount}/${x.unitPct}`));
    // Before the first load has finished — the hardest case.
    await Promise.all([bs.update({ amount: 2500 }), bs.update({ unitPct: 2 })]);
    const mem = bs.get();
    check('setAmount then setUnitPct: both in memory', mem?.amount === 2500 && mem?.unitPct === 2, JSON.stringify(mem));
    const disk = stored(f.data);
    check('setAmount then setUnitPct: both in storage', disk.amount === 2500 && disk.unitPct === 2, JSON.stringify(disk));
    check('listeners end on the merged state', seen[seen.length - 1] === '2500/2', seen.join(' '));
  }
  {
    const f = slowStore(seed);
    const bs = createBankrollStore(f.store);
    await Promise.all([bs.update({ unitPct: 3.5 }), bs.update({ amount: 4000 })]);
    check('setUnitPct then setAmount: both in memory', bs.get()?.amount === 4000 && bs.get()?.unitPct === 3.5);
    const disk = stored(f.data);
    check('setUnitPct then setAmount: both in storage', disk.amount === 4000 && disk.unitPct === 3.5, JSON.stringify(disk));
  }
  {
    // After load, with a fast write (the clear) queued behind a slow one: the
    // last value to reach storage is still the newest state.
    const f = slowStore(seed);
    const bs = createBankrollStore(f.store);
    await bs.load();
    await Promise.all([bs.update({ unitPct: 1.5 }), bs.update({ amount: null })]);
    const disk = stored(f.data);
    check('a quick clear after a % change: both in storage, in order', disk.amount === null && disk.unitPct === 1.5, JSON.stringify(disk));
    check('…and in memory', bs.get()?.amount === null && bs.get()?.unitPct === 1.5);
  }
  {
    const f = slowStore(seed);
    const bs = createBankrollStore(f.store);
    await bs.update({ amount: 5 });
    check('an invalid amount never reaches the store (sanitized to none)', bs.get()?.amount === null);
  }
}

// ── 7. Nothing is sized off it: picks stay a flat 1u ───────────────────────
const SRC = join(import.meta.dirname, '..', 'src');
const read = (p: string) => readFileSync(join(SRC, p), 'utf-8');
function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? walk(p) : /\.tsx?$/.test(n) ? [p] : [];
  });
}
const files = walk(SRC).map((p) => ({ rel: relative(SRC, p).replace(/\\/g, '/'), text: readFileSync(p, 'utf-8') }));
const lib = read('lib/bankroll.ts');
check('lib/bankroll has no Kelly, stake or conviction math',
  !/kelly|stakeFor|convictionFor|unitsFor|recommended_bet/i.test(lib.replace(/\/\*[\s\S]*?\*\//g, '')));
{
  const importers = files.filter((f) => /from '(@\/lib\/|\.\.?\/(lib\/)?)bankroll'/.test(f.text)).map((f) => f.rel).sort();
  eq('only the hook and Settings import lib/bankroll', importers.join(','), 'hooks/useBankroll.ts,screens/SettingsScreen.tsx');
  const hookUsers = files.filter((f) => /useBankroll\(/.test(f.text) && f.rel !== 'hooks/useBankroll.ts').map((f) => f.rel);
  eq('only Settings reads the bankroll', hookUsers.join(','), 'screens/SettingsScreen.tsx');
}
{
  const readers = files.filter((f) => /getItem\(\s*['"]bankroll['"]/.test(f.text)).map((f) => f.rel);
  check('nothing reads the #786 `bankroll` key', readers.length === 0, readers.join(','));
}
check('picks stay a flat 1u to win, whatever the Kelly',
  [0.005, 0.01, 0.0328, 0.05].every((k) => convictionFor(k) === 1 && stakeFor(k, -110).win === 1));

// ── 8. Settings: the card, and what it leaves alone ────────────────────────
const settings = read('screens/SettingsScreen.tsx');
{
  const books = settings.indexOf('label="Connected books"');
  const bank = settings.indexOf('<SectionHeader title="Bankroll" />');
  const control = settings.indexOf('<SectionHeader title="Staying in control" />');
  check('a "Bankroll" section sits right above Staying in control', books > 0 && books < bank && bank < control &&
    /<SectionHeader title="Bankroll" \/>\s*<BankrollCard \/>\s*<SectionHeader title="Staying in control" \/>/.test(settings));
}
check('the section is "Bankroll", not "Bankroll & limits"', !settings.includes('Bankroll & limits'));
eq('card copy', BANKROLL_CARD_COPY, 'Only used to show your units in dollars. Nothing is sized off it, and it stays on this device.');
eq('footer copy, word for word', BANKROLL_FOOTER_COPY,
  'A unit is your standard bet. As a starting point, we suggest 1 unit = 1% of your bankroll. Change it to fit your budget, and only bet what you can afford to lose.');
check('Settings renders both copy constants', settings.includes('{BANKROLL_CARD_COPY}') && settings.includes('{BANKROLL_FOOTER_COPY}'));
check('the field: decimal pad, Done bar, $ prefix, placeholder, label',
  settings.includes('keyboardType="decimal-pad"') &&
    /inputAccessoryViewID=\{Platform\.OS === 'ios' \? BANKROLL_ACCESSORY_ID : undefined\}/.test(settings) &&
    /<InputAccessoryView nativeID=\{BANKROLL_ACCESSORY_ID\}>/.test(settings) &&
    /styles\.moneyPrefix[\s\S]{0,200}\$\s*<\/Text>/.test(settings) &&
    settings.includes('placeholder="Enter amount"') &&
    settings.includes('accessibilityLabel="Your bankroll in dollars, optional"'));
check('the field formats every keystroke and saves only valid or empty',
  /const next = formatBankrollInput\(raw\);/.test(settings) &&
    /if \(c\.state === 'empty'\) setAmount\(null\);\s*else if \(c\.state === 'valid'\) setAmount\(c\.amount\);/.test(settings));
check('errors: blur and Done commit, the live one does not wait',
  /onBlur=\{commit\}/.test(settings) && /visibleBankrollError\(check, committed\)/.test(settings) &&
    /setCommitted\(false\);/.test(settings));
check('Lower / Raise are labeled buttons', /accessibilityLabel=\{`\$\{word\} \$\{what\}`\}/.test(settings) &&
  settings.includes("const word = dir === -1 ? 'Lower' : 'Raise';") && /accessibilityRole="button"/.test(settings));
check('Lower / Raise reach 44pt (32 + 6 + 6)', /minHeight: 32/.test(settings) && /hitSlop=\{\{ top: 6, bottom: 6 \}\}/.test(settings));
check('out of scope stays out: no daily limit row, presets, $ switch, 24h wait',
  !/Daily limit:|Presets|Conservative|Aggressive|Show \$ next to units|24 hours|PROPOSED|DEFAULT_DAILY_LIMIT/.test(settings + lib));
check('no font-size literals in Settings', !/fontSize:\s*\d/.test(settings));

// The daily exposure card, its storage and the Picks banner are exactly master's.
check('Settings: the daily exposure card is unchanged',
  settings.includes(`        <View style={styles.card}>
          <View style={styles.capHeader}>
            <Text style={styles.cardLabel}>Daily exposure limit</Text>
            <Switch value={rg.exposureCapUnits != null} onValueChange={toggleRgCap} />
          </View>`) &&
    settings.includes('const toggleRgCap = (on: boolean) => setExposureCapUnits(on ? 10 : null);') &&
    settings.includes("Alert.alert('Invalid limit', 'Enter a number of units between 0 and 100.');") &&
    settings.includes('Off by default. Turn it on for a heads-up before a day’s picks over-extend you.'));
const rg = read('hooks/useResponsibleGambling.ts');
check('responsibleGambling.v2 is unchanged and bankroll-free',
  rg.includes("const STORAGE_KEY = 'responsibleGambling.v2';") &&
    rg.includes('exposureCapUnits: number | null;') && !/bankroll'/i.test(rg) && !/offCap|dailyLimit/i.test(rg));
const picks = read('screens/PicksHomeScreen.tsx');
check('Picks: the exposure banner is unchanged and shows no dollars',
  picks.includes(`            Today’s picks ask for {formatUnits(exposure.total)} — over your{' '}
            {formatUnits(exposure.cap)} daily limit. Consider sizing
            down or sitting some out.`) && !/bankroll|Bankroll|formatDollars/.test(picks));

// ── 8b. Error colour: text-safe red for words, `avoid` for icon + outline ──
{
  const lum = (hex: string) => {
    const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  };
  const ratio = (a: string, b: string) => {
    const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };
  // theme.ts imports react-native (Platform), which tsx cannot load, so the
  // tokens are read from its source.
  const theme = read('lib/theme.ts');
  const token = (name: string) => theme.match(new RegExp(`\\n  ${name}: '(#[0-9A-Fa-f]{6})'`))?.[1] ?? '#000000';
  const colors = {
    avoid: token('avoid'), avoidText: token('avoidText'),
    bg: token('bg'), bgCard: token('bgCard'), bgGrouped: token('bgGrouped'),
  };
  eq('avoidText is #D70015', colors.avoidText, '#D70015');
  check('the backgrounds it sits on are the light tokens (the theme has no dark variant)',
    colors.bgCard === '#FFFFFF' && colors.bgGrouped === '#F2F2F7' && colors.bg === '#F2F2F7');
  const onCard = ratio(colors.avoidText, colors.bgCard);
  const onGrouped = ratio(colors.avoidText, colors.bgGrouped);
  check(`avoidText clears AA (4.5:1) on bgCard: ${onCard.toFixed(2)}:1`, onCard >= 4.5);
  check(`avoidText clears AA (4.5:1) on bg / bgGrouped: ${onGrouped.toFixed(2)}:1`, onGrouped >= 4.5 &&
    ratio(colors.avoidText, colors.bg) >= 4.5);
  check(`avoid stays non-text only: ${ratio(colors.avoid, colors.bgCard).toFixed(2)}:1 ≥ 3:1, < 4.5:1`,
    ratio(colors.avoid, colors.bgCard) >= 3 && ratio(colors.avoid, colors.bgCard) < 4.5);
  const style = (name: string) => settings.match(new RegExp(`\\n  ${name}: \\{[^}]*\\}`))?.[0] ?? '';
  check('the error TEXT uses avoidText', /color: colors\.avoidText/.test(style('fieldErrorText')));
  check('the outline still uses avoid', /borderColor: colors\.avoid\b(?!Text)/.test(style('moneyFieldError')));
  check('the icon still uses avoid',
    /<Ionicons name="alert-circle" size=\{14\} color=\{colors\.avoid\} \/>\s*<Text style=\{styles\.fieldErrorText\}>\{error\}<\/Text>/.test(settings));
  check('avoidText is used for that text only', (settings.match(/colors\.avoidText/g) ?? []).length === 1);
}

// ── 8c. The keyboard never covers the field ────────────────────────────────
check('Settings ScrollView: automaticallyAdjustKeyboardInsets + keyboardShouldPersistTaps="handled"',
  /<ScrollView\s+contentContainerStyle=\{styles\.list\}\s+keyboardShouldPersistTaps="handled"\s+automaticallyAdjustKeyboardInsets\s*>/.test(settings));
{
  const hook = read('hooks/useBankroll.ts');
  check('useBankroll goes through the one merging store, no captured-base writes',
    /const store = createBankrollStore\(AsyncStorage\);/.test(hook) && /store\.update\(\{ amount \}\)/.test(hook) &&
      /store\.update\(\{ unitPct: sanitizeUnitPct\(pct\) \}\)/.test(hook) && !/\.\.\.base/.test(hook));
}

// ── 9. Explainer ───────────────────────────────────────────────────────────
const explainer = read('screens/ExplainerScreen.tsx').replace(/\s+/g, ' ');
check('Explainer: no longer says we never ask for a bankroll', !explainer.includes('we never ask for your bankroll'));
check('Explainer: optional, on this device, converts only, never sizes',
  /bankroll in Settings/.test(explainer) && /optional/.test(explainer) && /stays on this device/.test(explainer) &&
    /only converts your units into dollars/.test(explainer) && /never sizes a bet/.test(explainer));

storage().then(interleaving).then(() => {
  console.log(failures === 0 ? '\nALL PASS' : `\n${failures} check(s) FAILED.`);
  process.exit(failures === 0 ? 0 : 1);
});

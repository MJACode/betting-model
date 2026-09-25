/**
 * Contrast and colour tokens — usability audit PR 1 (2026-09-25: H1, H2, H6,
 * H7, H8 and the related M/L items).
 *
 *   npx tsx scripts/verify_contrast_tokens.ts
 *
 * theme.ts imports react-native, which a verify script cannot resolve, so the
 * hexes are READ from its source and measured here with the WCAG 2.x formula
 * (alpha composited over the real ground). The colour ROLES (`pnlTone`,
 * `SIGNAL_BADGE`) live in the pure lib/tone.ts and are imported directly.
 *
 * Pins:
 *   - the token values, and that the bright fills did NOT change;
 *   - every new/changed TEXT token clears 4.5:1 on each ground it is used on
 *     (the app is light-only; there is no dark palette to measure);
 *   - the signal badge: ink + ✓/–/✕ glyph per signal, each ≥ 4.5:1 on its wash;
 *   - signed results: "+" / U+2212, zero unsigned, never an ASCII hyphen;
 *   - no white text on a green fill (H6), and no bright bet/avoid/med hue left
 *     as a TEXT colour anywhere in the app (icons may keep the hue).
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import {
  formatCurrencySigned,
  formatPctSigned,
  formatSigned,
  formatSignedUnits,
  MINUS,
} from '../src/lib/format';
import { pnlTone, SIGNAL_BADGE } from '../src/lib/tone';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// ── theme.ts hexes ──────────────────────────────────────────────────────────
const themeSrc = read('src/lib/theme.ts');
const brandInk = /const BRAND_INK = '(#[0-9A-Fa-f]{6})'/.exec(themeSrc)?.[1] ?? '';
const colorsBlock = /export const colors = \{([\s\S]*?)\n\};/.exec(themeSrc)?.[1] ?? '';
const tok: Record<string, string> = {};
for (const m of colorsBlock.matchAll(/^\s*(\w+):\s*(?:'(#[0-9A-Fa-f]{6,8})'|(BRAND_INK))/gm)) {
  tok[m[1]] = (m[2] ?? brandInk).toUpperCase();
}
check('theme colours parsed', Object.keys(tok).length > 30 && brandInk !== '', `${Object.keys(tok).length} tokens`);

// ── WCAG 2.x ────────────────────────────────────────────────────────────────
function rgb(hex: string): [number, number, number, number] {
  const h = hex.replace('#', '');
  const n = (i: number) => parseInt(h.slice(i, i + 2), 16);
  return [n(0), n(2), n(4), h.length === 8 ? n(6) / 255 : 1];
}
function over(fg: string, bg: string): string {
  const [r, g, b, a] = rgb(fg);
  const [R, G, B] = rgb(bg);
  const mix = (x: number, y: number) => Math.round(x * a + y * (1 - a));
  return '#' + [mix(r, R), mix(g, G), mix(b, B)].map((v) => v.toString(16).padStart(2, '0')).join('');
}
function wash(hex: string, alphaHex: string, bg: string): string {
  return over(`${hex.slice(0, 7)}${alphaHex}`, bg);
}
function lum(hex: string): number {
  const [r, g, b] = rgb(hex).map((c, i) => (i < 3 ? c / 255 : c)) as number[];
  const f = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
function ratio(fg: string, bg: string): number {
  const a = lum(over(fg, bg));
  const b = lum(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

// ── token values ────────────────────────────────────────────────────────────
const EXPECT: Record<string, string> = {
  textTertiary: '#6C6C70', // H7
  betInk: '#1A7F37', // H1/H2
  avoidInk: '#C4281C', // H1/H2/H8
  medInk: '#9A5B00', // H8/M24
  // Fills keep the bright hues (Designer: "keep the bright colours for fills").
  bet: '#34C759',
  avoid: '#FF3B30',
  med: '#FF9500',
  positive: '#34C759',
  negative: '#FF3B30',
  betSoft: '#E8F8EC',
  avoidSoft: '#FDECEB',
  noneSoft: '#EFEFF4',
  medSoft: '#FFF4E5',
};
for (const [k, v] of Object.entries(EXPECT)) check(`token ${k} = ${v}`, tok[k] === v, tok[k]);
check(
  'textTertiary stays lighter than textSecondary (hierarchy)',
  lum(tok.textTertiary) > lum(tok.textSecondary),
);

// ── contrast on the real grounds ────────────────────────────────────────────
type Pair = { fg: string; bg: string; bgName: string; min: number; where: string };
const T = (fg: string, bgName: string, where: string, min = 4.5): Pair => ({
  fg,
  bg: tok[bgName],
  bgName,
  min,
  where,
});
const W = (fg: string, hue: string, where: string, min = 4.5): Pair => ({
  fg,
  bg: wash(tok[hue], '22', tok.bgCard),
  bgName: `${hue}@22 wash`,
  min,
  where,
});
const PAIRS: Pair[] = [
  ...['bgCard', 'bg', 'noneSoft', 'betSoft', 'avoidSoft', 'medSoft'].map((b) =>
    T('textTertiary', b, 'secondary text app-wide (H7), SportToggle muted (M17)'),
  ),
  T('betInk', 'bgCard', 'P&L / ROI / EV / CLV / Tracking text (H2)'),
  T('betInk', 'bg', 'Parlay stat row on the grouped ground (H2)'),
  T('betInk', 'betSoft', 'BET badge, HIGH tier, sharp pill, In slip, W letter (H1/H2/M5/M6)'),
  W('betInk', 'bet', 'parlay "Great" grade (H2)'),
  T('avoidInk', 'bgCard', 'loss text, error text, destructive labels (H2/H8/M1)'),
  T('avoidInk', 'bg', 'loss text on the grouped ground (H2)'),
  T('avoidInk', 'avoidSoft', 'AVOID badge, LIVE pill, error banners, L letter (H1/M22/M1)'),
  W('avoidInk', 'avoid', 'parlay "Bad" grade (H2)'),
  T('medInk', 'bgCard', 'injury flag, public tag (H8)'),
  T('medInk', 'bg', 'caution text on the grouped ground'),
  T('medInk', 'medSoft', 'MED tier, warn banners, reconnect, DOG tag (H8/M6/M24)'),
  W('medInk', 'med', 'parlay "Fair" grade (H2)'),
  T('textSecondary', 'noneSoft', 'NONE badge, LOW tier, P letter, Preview (H1)'),
  W('textPrimary', 'info', 'parlay "Good" grade (H2)'),
  T('textPrimary', 'bet', 'SportToggle count on green (H6)'),
  T('textPrimary', 'med', 'player hit-rate badge on amber (H6 class)'),
  T('textPrimary', 'avoid', 'player hit-rate badge on red'),
  T('textPrimary', 'none', 'player hit-rate badge on grey'),
  T('textInverse', 'tint', 'sportsbook sheet Apply (H6)'),
  // Non-text (WCAG 1.4.11, 3:1): the badge glyph and the Tracking bell share
  // the ink, so they clear this by construction; pinned anyway.
  T('betInk', 'bgCard', 'Tracking / In slip icon (non-text)', 3),
];
console.log('\n  token          hex        ground              ratio  min');
for (const p of PAIRS) {
  const r = ratio(tok[p.fg], p.bg);
  console.log(
    `  ${p.fg.padEnd(14)} ${tok[p.fg]}  ${p.bgName.padEnd(18)} ${r.toFixed(2).padStart(5)}  ${p.min}`,
  );
  check(`${p.fg} on ${p.bgName} ≥ ${p.min}:1 — ${p.where}`, r >= p.min, r.toFixed(2));
}
// The audit's own ratios, so a token drift shows up as a number, not a pass.
const near = (a: number, b: number) => Math.abs(a - b) < 0.015;
check('textTertiary 5.23 on bgCard / 4.69 on bg', near(ratio(tok.textTertiary, tok.bgCard), 5.23) && near(ratio(tok.textTertiary, tok.bg), 4.69));
check('betInk 5.08 on bgCard / 4.61 on betSoft', near(ratio(tok.betInk, tok.bgCard), 5.08) && near(ratio(tok.betInk, tok.betSoft), 4.61));
check('avoidInk 5.73 on bgCard / 5.01 on avoidSoft', near(ratio(tok.avoidInk, tok.bgCard), 5.73) && near(ratio(tok.avoidInk, tok.avoidSoft), 5.01));
check('medInk 5.43 on bgCard / 4.99 on medSoft', near(ratio(tok.medInk, tok.bgCard), 5.43) && near(ratio(tok.medInk, tok.medSoft), 4.99));
check('the old failures really were failures', ratio(tok.bet, tok.bgCard) < 3 && ratio('#FFFFFF', tok.bet) < 3);

// ── signal badge (H1) ───────────────────────────────────────────────────────
const GLYPH = { BET: 'checkmark', NONE: 'remove', AVOID: 'close' } as const;
for (const s of ['BET', 'NONE', 'AVOID'] as const) {
  const spec = SIGNAL_BADGE[s];
  check(`badge ${s}: word "${s}"`, spec.label === s);
  check(`badge ${s}: glyph ${GLYPH[s]}`, spec.glyph === GLYPH[s], spec.glyph);
  const r = ratio(tok[spec.ink], tok[spec.fill]);
  check(`badge ${s}: ${spec.ink} on ${spec.fill} ≥ 4.5:1`, r >= 4.5, r.toFixed(2));
}
check(
  'badge glyphs are three different shapes',
  new Set(Object.values(SIGNAL_BADGE).map((b) => b.glyph)).size === 3,
);
const badgeSrc = read('src/components/SignalBadge.tsx');
check('SignalBadge reads SIGNAL_BADGE', /SIGNAL_BADGE\[signal\]/.test(badgeSrc));
check('SignalBadge draws the glyph (Ionicons name={spec.glyph})', /name=\{spec\.glyph\}/.test(badgeSrc));
check('SignalBadge no longer colours text with bet/avoid/none', !/colors\.(bet|avoid|none)\b(?!Soft|Ink)/.test(badgeSrc));

// ── signed results (H2 / L9) ────────────────────────────────────────────────
check('pnlTone gain → betInk', pnlTone(1.2) === 'betInk');
check('pnlTone loss → avoidInk', pnlTone(-0.4) === 'avoidInk');
check('pnlTone zero → textSecondary', pnlTone(0) === 'textSecondary');
check('pnlTone missing → textSecondary', pnlTone(null) === 'textSecondary' && pnlTone(NaN) === 'textSecondary');
check('pnlTone epsilon treats 0.0005 as a push', pnlTone(0.0005, 0.001) === 'textSecondary');
check('theme.pnlColor delegates to pnlTone', /return colors\[pnlTone\(value, epsilon\)\]/.test(themeSrc));

const CASES: [string, string][] = [
  [formatSigned(1.23), '+1.2'],
  [formatSigned(-0.5, 2), `${MINUS}0.50`],
  [formatSigned(0.04), '0.0'],
  [formatSigned(-0.04), '0.0'],
  [formatSigned(2.3, 1, 'pp'), '+2.3pp'],
  [formatSigned(-1.5, 1, ' pts'), `${MINUS}1.5 pts`],
  [formatSigned(null), '—'],
  [formatPctSigned(0.125), '+12.5%'],
  [formatPctSigned(-0.03), `${MINUS}3.0%`],
  [formatPctSigned(0.0001), '0.0%'],
  [formatPctSigned(-0.0004), '0.0%'],
  [formatPctSigned(undefined), '—'],
  [formatCurrencySigned(-25), `${MINUS}$25.00`],
  [formatCurrencySigned(30), '+$30.00'],
  [formatCurrencySigned(0.004), '$0.00'],
  [formatCurrencySigned(0), '$0.00'],
  [formatSignedUnits(2.44), '+2.4u'],
  [formatSignedUnits(-0.5), `${MINUS}0.5u`],
  [formatSignedUnits(0.04), '0.0u'],
];
for (const [got, want] of CASES) check(`signed: ${JSON.stringify(want)}`, got === want, got);
check('MINUS is U+2212', MINUS === '\u2212');
check(
  'no signed result uses an ASCII hyphen-minus',
  CASES.every(([got]) => !/^-/.test(got) && !/^[+]?\$?-/.test(got)),
);

// ── static: H6 and "no bright hue as text" ──────────────────────────────────
function walk(dir: string, acc: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, acc);
    else if (/\.tsx?$/.test(name)) acc.push(p);
  }
  return acc;
}
const files = [...walk(join(ROOT, 'src')), join(ROOT, 'App.tsx')].filter(
  (f) => !f.endsWith(join('lib', 'theme.ts')),
);
const code = (src: string) =>
  src
    .split('\n')
    .map((l) => (/^\s*(\/\/|\*|\/\*)/.test(l) ? '' : l))
    .join('\n');

const whiteLits: string[] = [];
const hueText: string[] = [];
// `color:` / `tint` whose value is a bright SIGNAL hue. Ionicons' `color={…}`
// prop is not matched (icons keep the hue by design, audit H8), nor are
// objects that also carry an `icon:` (PickCard's movement summary drives the
// icon from `color` and the words through inkFor()).
const HUE_TEXT = /(?<![A-Za-z])(color:|tint:|tint=\{)[^,;\n}]*\bcolors\.(bet|avoid|med|positive|negative|high|none|low)\b(?!Soft|Ink)/;
for (const f of files) {
  const rel = relative(ROOT, f);
  code(readFileSync(f, 'utf-8'))
    .split('\n')
    .forEach((line, i) => {
      // The short form is the one the scan could not see (L3); 6-digit brand
      // whites (Discord / FanDuel tiles) are the scan's hex-color findings.
      if (/(['"])#fff\1|(['"])white\2/i.test(line)) whiteLits.push(`${rel}:${i + 1}`);
      if (HUE_TEXT.test(line) && !/\bicon:/.test(line)) hueText.push(`${rel}:${i + 1}`);
    });
}
check("no literal '#fff' / 'white' left in the app (H6)", whiteLits.length === 0, whiteLits.join(', '));
check('no bright bet/avoid/med/positive/negative hue used as a text colour', hueText.length === 0, hueText.join(', '));

const sheet = read('src/components/SportsbookPickerSheet.tsx');
const applyBtn = /applyBtn: \{[\s\S]*?\}/.exec(sheet)?.[0] ?? '';
const applyText = /applyText: \{[\s\S]*?\}/.exec(sheet)?.[0] ?? '';
check('Apply fill is tint, not bet green (H6)', /backgroundColor: colors\.tint/.test(applyBtn), applyBtn.replace(/\s+/g, ' '));
check('Apply label is textInverse (H6)', /color: colors\.textInverse/.test(applyText));
const toggle = read('src/components/SportToggle.tsx');
const badge = /\n  badge: \{[\s\S]*?\}/.exec(toggle)?.[0] ?? '';
const badgeText = /badgeText: \{[\s\S]*?\}/.exec(toggle)?.[0] ?? '';
check('SportToggle count badge: textPrimary on bet (H6)', /colors\.bet\b/.test(badge) && /color: colors\.textPrimary/.test(badgeText));
check('SportToggle muted label has no extra opacity (M17)', !/labelMuted: \{[^}]*opacity/.test(toggle));
const player = read('src/screens/PlayerStatsScreen.tsx');
check('player hit-rate badge text is dark on its bright fill', /hitBadgeText: \{[^}]*color: colors\.textPrimary/.test(player));
check('PickCard tier chip is BET-only (M6)', /showTier = [^;]*pick\.signal_type === 'BET'/.test(read('src/components/PickCard.tsx')));
const scan = read('scripts/ux_scan.mts');
check('ux_scan reads short hex, rgb() and App.tsx (L3)', /shortRe/.test(scan) && /rgbRe/.test(scan) && /APP_ROOT_FILE/.test(scan));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

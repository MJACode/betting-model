/**
 * iOS-style design tokens.
 * Modeled on Apple HIG light + dark system colors and SF system fonts.
 */

import { Platform } from 'react-native';

import { bootScheme } from './appearance';
import type { MatchupGrade } from './matchup';
import { pnlTone } from './tone';
import { FONT_SIZE_MICRO } from './typeScale';

const BRAND_INK = '#0B1320'; // the S itself; also `tint` (one literal, two names)

const lightColors = {
  // System backgrounds
  bg: '#F2F2F7',
  bgElevated: '#FFFFFF',
  bgGrouped: '#F2F2F7',
  bgCard: '#FFFFFF',

  // Text
  textPrimary: '#000000',
  textSecondary: '#3C3C43',
  // Was the iOS label-tertiary '#3C3C4399' (3.44:1 on bgCard, 3.29:1 on bg),
  // under AA at the 11–13pt it is used at for times, provenance and footnotes.
  // Opaque #6C6C70 is 5.23:1 on bgCard, 4.69:1 on bg and 4.56:1 on noneSoft —
  // still lighter than textSecondary, so the hierarchy holds (audit H7).
  textTertiary: '#6C6C70',
  // The paused-pick chip is this grey on noneSoft. textTertiary is 4.56:1
  // there, on the floor. #5C5C62 is 5.79:1 on noneSoft and still lighter
  // than textSecondary (9.55:1), so the chip stays quieter than a Pick chip.
  pausedInk: '#5C5C62',
  textInverse: '#FFFFFF',
  // Secondary text on the navy chrome (the betslip bar's "Price" / "Pays"
  // labels, the time under your own feedback bubble). White at 72%, so it
  // stays quieter than textInverse beside it. Was a literal in three places.
  textInverseSecondary: '#FFFFFFB8',
  // A light wash on a dark or tint fill — the count bubble inside an
  // active filter chip. White at 25%.
  inverseWash: '#FFFFFF40',
  // Text and icons on the navy brand chrome (tab bar, betslip bar, sign-in,
  // paywall, lock card). White in BOTH themes: the chrome stays navy, while
  // `textInverse` above means "on a tint fill" and goes dark in Dark, where
  // tint is amber. Same value as textInverse in Light, so Light is unchanged.
  onChrome: '#FFFFFF',
  onChromeSecondary: '#FFFFFFB8',
  // Text on a bright third-party fill (the DraftKings green handoff). Black in
  // both themes; textPrimary goes white in Dark.
  onBright: '#000000',

  // Separators
  separator: '#3C3C4349',
  separatorOpaque: '#C6C6C8',
  // A switch's OFF track. The iOS default (#E9E9EA, white thumb) is 1.2:1 on
  // bgCard, so an off switch on a white card all but vanished (Matt,
  // 2026-11-02, Stats > Filters > Playing today). #8E8E93 is 3.26:1 on white
  // and against the white thumb — over the 3:1 non-text floor (WCAG 1.4.11).
  switchTrackOff: '#8E8E93',

  // Brand — sampled from the @signalbasepicks mark and banner
  // (assets/brand/, fetched 2026-09-03; scripts/render_brand_icons.py).
  //
  // Amber on white is 1.9:1, so it is never text or an icon on a light
  // surface: it lives on the navy chrome (tab bar, splash) and in the mark
  // itself. Interactive elements on light surfaces use the mark's INK — the
  // same near-black navy the S is drawn in — which is why `tint` is not amber.
  brand: '#F2B01E', // amber, the mark's ground        (9.8:1 on brandNavy)
  brandInk: BRAND_INK, //                                 (18.6:1 on white)
  brandNavy: '#0B1220', // the banner's ground — dark chrome surfaces
  brandNavyRaised: '#152034', // the banner's watermark — a raised dark surface
  // Discord's own mark. Not a Signal Base colour. Named so the link sheet
  // does not hard-code the hex.
  discord: '#5865F2',
  brandMuted: '#8A97AB', // the banner's caption grey — inactive on navy (6.3:1)
  brandSeparator: '#374151', // hairline between navy chrome surfaces (1.8:1 vs navy)

  // Tints
  tint: BRAND_INK, // primary actions, links, selection
  // Selected Signals Slip / Track. A light wash of tint, so the ON state
  // reads as selected and the label stays tint (measured on this wash).
  tintSoft: '#E6E8EC',
  // The dimmed backdrop behind a bottom sheet (UX_REVIEW: #00000055).
  scrim: '#00000055',
  // A STATUS colour, never a control: the old system blue kept for the one
  // grade/pill/fill that means "good / in progress" and must not look like a
  // button now that tint is near-black (UX review 2026-09-03).
  info: '#007AFF',

  // Signals
  bet: '#34C759', // green
  betSoft: '#E8F8EC',
  avoid: '#FF3B30', // red
  avoidSoft: '#FDECEB',
  none: '#8E8E93', // gray
  // Unfilled matchup segment. The filled segments carry the contrast
  // (gradeGood / gradeMid / gradeBad, each ≥4.5:1). The count of filled
  // segments is the meaning, so the empty one stays this light gray
  // (Matt, 2026-10-28, Option A).
  matchupEmpty: '#D1D1D6',
  noneSoft: '#EFEFF4',

  // ── Text-safe inks (usability audit H1 / H2 / H8, 2026-09-25) ────────────
  // `bet` / `avoid` / `med` are FILLS, dots and icons. As text they measure
  // 2.22 / 3.55 / 1.97:1 on bgCard — under the 4.5:1 AA floor on exactly the
  // numbers people come to read (P&L, ROI, EV, CLV, warnings, BET/AVOID).
  // Wherever green, red or amber is TEXT, use the ink; keep the bright hue for
  // the fill or icon beside it. Every value also carries a sign or a word, so
  // colour is never the only carrier (WCAG 1.4.1). Measured on their real
  // grounds by scripts/verify_contrast_tokens.ts:
  //   betInk   5.08 bgCard · 4.55 bg · 4.61 betSoft   (NOT on noneSoft/avoidSoft: 4.4)
  //   avoidInk 5.73 bgCard · 5.13 bg · 5.01 avoidSoft
  //   medInk   5.43 bgCard · 4.86 bg · 4.99 medSoft
  betInk: '#1A7F37',
  avoidInk: '#C4281C',
  medInk: '#9A5B00',

  // ── The board's good / average / bad ramp ────────────────────────────────
  // Used by BOTH traffic lights on the Stats board: the matchup grade and the
  // hit-rate percentage. One standard, because the alternative shipped for
  // half a day — an accessible ramp in the MATCHUP column two columns away
  // from an inaccessible one on the board's primary number.
  //
  // Three properties, all measured (2026-09-05):
  //
  //   1. NOT `bet` / `avoid`. Those are BET/AVOID semantics, and a row already
  //      carries a price; a third thing in the same green reads as a side to
  //      take rather than a spot to weigh.
  //   2. Every step clears WCAG AA for text. `bet` is 2.22:1 on bgCard,
  //      `#FF9500` is 2.20:1 and `avoid` is 3.55:1 — the three the board used
  //      for both columns until now, all below the 4.5:1 floor, on numbers
  //      that have to be read.
  //   3. LIGHTNESS FALLS MONOTONICALLY good -> bad, which is the property the
  //      first attempt at this ramp missed: tuning five steps to ~5:1 each
  //      made them iso-luminant (relative luminance 0.1596 / 0.1603 / 0.1570 /
  //      0.1528 — B was fractionally LIGHTER than A), so a reader could see
  //      that two rows differed but not which was better, and under
  //      deuteranopia the green and the olive collapsed together. Colour that
  //      encodes a rank has to vary in lightness, not only in hue.
  //
  // Three steps, not five: the LETTER already carries thirteen steps of order,
  // so the colour only has to say good / average / bad — and three levels that
  // differ in lightness say it better than five that do not.
  gradeGood: '#198438', // L 0.1699 ·  4.77:1
  gradeMid: '#5F5F64', //  L 0.1154 ·  6.35:1
  gradeBad: '#7A1712', //  L 0.0479 · 10.72:1

  // Confidence
  high: '#34C759',
  med: '#FF9500',
  // MED wash — chips, caution banners. Never body text (`med` is 1.97:1 on
  // white). Replaces the `#FFF4E5` literals the scan used to tolerate.
  medSoft: '#FFF4E5',
  low: '#8E8E93',

  // "Best payout" marker — the star on the betslip's Open-with tiles. A dark
  // gold rather than the brand amber (1.9:1 on white) or `med` (confidence).
  best: '#B8860B',

  // Third-party brand: DraftKings' green, the one book colour the app carries
  // (its chip on every BET card, the picker badge, the betslip row). Text on
  // it is textPrimary (~10.7:1). Lives here so a dark-surface variant has one
  // home when the app gets a dark theme.
  bookDraftKings: '#53D337',
  // The DraftKings mark's ground (green on black) and FanDuel's blue, for
  // the Connect Sportsbook tiles. Brand colours of the books, not ours.
  bookDraftKingsGround: '#000000',
  bookFanDuel: '#1493FF',

  // Performance heat map
  positive: '#34C759',
  negative: '#FF3B30',
  neutral: '#C7C7CC',
};

/**
 * Dark — brand navy (Matt, 2026-11-16): the banner's #0B1220 ground, cards a
 * step up. Tint is the brand amber (8.4:1 on bgCard), which is why
 * `textInverse` (content on a tint fill) is the near-black ink here. Every
 * text token is measured on its grounds by scripts/verify_contrast_tokens.ts.
 * The bright FILLS (bet / avoid / med / brand / the books) do not change.
 */
const darkColors: typeof lightColors = {
  ...lightColors,
  bg: '#0B1220',
  bgElevated: '#1C2944',
  bgGrouped: '#0B1220',
  bgCard: '#16213A',

  textPrimary: '#F2F4F8',
  textSecondary: '#C3CBD8',
  // Darker than secondary here (the hierarchy is reversed on a dark ground).
  textTertiary: '#97A2B4',
  pausedInk: '#A9B3C3',
  textInverse: '#0B1320',
  textInverseSecondary: '#0B1320B8',
  inverseWash: '#0B132040',

  separator: '#FFFFFF26',
  separatorOpaque: '#2A3753',
  switchTrackOff: '#6E7A90',

  tint: '#F2B01E',
  tintSoft: '#3A3320',
  scrim: '#00000099',
  info: '#4DA3FF',

  betSoft: '#0F2E22',
  avoidSoft: '#3A1C22',
  matchupEmpty: '#2E3A52',
  noneSoft: '#202C44',

  betInk: '#4CD07A',
  avoidInk: '#FF8A80',
  medInk: '#FFB648',

  // Lightness still falls good -> mid -> bad (L 0.499 / 0.476 / 0.334).
  gradeGood: '#5AD282',
  gradeMid: '#B0B8C6',
  gradeBad: '#F2786E',

  medSoft: '#33280F',
  best: '#E8B53A',
  neutral: '#3A4558',
};

/** The scheme this run started in (lib/appearance.ts: it changes at the next open). */
export const isDark = bootScheme() === 'dark';

export const colors = isDark ? darkColors : lightColors;

/** For scripts/verify_contrast_tokens.ts only. */
export const __palettes = { light: lightColors, dark: darkColors };

/**
 * Abbreviation discs on the Scoreboard. White text. Dark fills only —
 * amber and the bright signal greens are too light under a white label.
 */
export const teamDisc = [
  '#0B1320',
  '#0B3D91',
  '#8C1D18',
  '#0E6B4F',
  '#5C2E91',
  '#8A4B08',
  '#1A365D',
  '#7A2E0E',
] as const;

export const radii = {
  // Small status tags (the Stats board's IR / O / Q chip).
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  pill: 999,
};

/**
 * Press and disabled feedback. Before 2026-11-14 a pressed control faded to
 * one of 12 different opacities (0.2–0.85) depending on which file drew it;
 * 0.6 was already the most common (43 sites), 0.4 the most common disabled.
 */
export const opacity = {
  pressed: 0.6,
  disabled: 0.4,
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

/**
 * The standard card: white on the grouped background, 12pt corners, 16pt
 * inside. Spread it into a StyleSheet entry (`card: { ...card, marginBottom }`)
 * so every card on every screen shares one shape. A dense list row may use
 * `cardDense` (12pt inside) — that is the only other padding.
 */
export const card = {
  backgroundColor: colors.bgCard,
  borderRadius: radii.md,
  padding: spacing.lg,
} as const;

export const cardDense = {
  ...card,
  padding: spacing.md,
} as const;

export const font = {
  family: Platform.select({
    ios: 'System',
    android: 'sans-serif',
    default: 'System',
  }),
  size: {
    // Below caption. Both were already in the StyleSheets as literals (row
    // team abbrevs, meta lines, column headers); naming them stops the next
    // sub-caption line from inventing a third size nobody agreed to
    // (UX review, 2026-09-05).
    nano: 10,
    micro: FONT_SIZE_MICRO,
    caption: 12,
    footnote: 13,
    body: 15,
    callout: 16,
    headline: 17,
    title3: 20,
    title2: 22,
    title1: 28,
    largeTitle: 34,
  },
  weight: {
    regular: '400' as const,
    medium: '500' as const,
    semibold: '600' as const,
    bold: '700' as const,
  },
};

/**
 * The one section-header text style: uppercase footnote, semibold,
 * textSecondary (UX_REVIEW §1). Before 2026-11-14, 33 headers were hand-rolled
 * at two sizes (caption / footnote), two greys and letter-spacing anywhere
 * from 0.3 to 0.6. Spread it into a StyleSheet entry and add only layout
 * (margins, padding) beside it: `heading: { ...sectionHeaderText, marginBottom: spacing.xs }`.
 * `SectionTitle` is the component form, with the standard gutter and an ⓘ.
 */
export const sectionHeaderText = {
  fontFamily: font.family,
  fontSize: font.size.footnote,
  fontWeight: font.weight.semibold,
  color: colors.textSecondary,
  letterSpacing: 0.4,
  textTransform: 'uppercase',
} as const;

/**
 * The text colour for a signed result — P&L, ROI, EV, CLV, a line move. Gain
 * reads `betInk`, loss `avoidInk`, and zero / a push / a missing value a
 * neutral `textSecondary` (never a green "+0.00" or a red "−0.00").
 *
 * The tone is taken from the value ROUNDED the way the screen shows it —
 * `digits` decimals of `value × scale` — so a ratio printed as "0.0%" is grey
 * and one printed as "+0.1%" is green. Match the formatter beside it:
 * `formatPctSigned(v)` → `pnlColor(v, 1, 100)`, `formatFlatUnits(v)` →
 * `pnlColor(v, 2, FLAT_UNIT_TONE_SCALE)`, `formatSigned(v, 1, 'pp')` → `pnlColor(v, 1)`.
 *
 * The rule itself lives in `lib/tone.ts` so the verify scripts, which cannot
 * import react-native, can pin it.
 */
export function pnlColor(value: number | null | undefined, digits: number, scale = 1): string {
  return colors[pnlTone(value, digits, scale)];
}

/**
 * The text-safe ink for a bright semantic hue: bet/positive/high → betInk,
 * avoid/negative → avoidInk, med → medInk; anything else passes through.
 * For rows where one colour drives an icon AND its words — the icon keeps
 * the bright hue, the words take the ink (usability audit H8).
 */
export function inkFor(hue: string): string {
  if (hue === colors.bet || hue === colors.positive || hue === colors.high) return colors.betInk;
  if (hue === colors.avoid || hue === colors.negative) return colors.avoidInk;
  if (hue === colors.med) return colors.medInk;
  return hue;
}

/** Intensity 0..1 for heat-map cells. Returns hex with alpha. */
export function heatColor(profit: number, max: number): string {
  if (max <= 0 || profit === 0) return colors.neutral;
  const intensity = Math.min(1, Math.abs(profit) / max);
  const alpha = Math.round((0.25 + 0.55 * intensity) * 255)
    .toString(16)
    .padStart(2, '0');
  const base = profit > 0 ? colors.positive : colors.negative;
  return `${base}${alpha}`;
}

/**
 * Filled-segment colour. 5–4 green, 3 gray, 2–1 maroon. `gradeColor` uses
 * this, so a letter and its bar cannot drift.
 *
 * It lives here rather than in the board because every matchup surface draws
 * one meter. (It cannot live in `lib/matchup.ts`: that module is imported by
 * the tsx verify scripts, and this file pulls in `react-native`, which they
 * cannot resolve.)
 */
export function strengthColor(filled: number): string {
  if (filled >= 4) return colors.gradeGood;
  if (filled === 3) return colors.gradeMid;
  return colors.gradeBad;
}

/** Letter → the same ramp `strengthColor` uses. A/B green, C gray, D/F maroon. */
export function gradeColor(grade: MatchupGrade): string {
  const letter = grade[0];
  const filled = letter === 'A' ? 5 : letter === 'B' ? 4 : letter === 'C' ? 3 : letter === 'D' ? 2 : 1;
  return strengthColor(filled);
}

/**
 * iOS-style design tokens.
 * Modeled on Apple HIG light + dark system colors and SF system fonts.
 */

import { Platform } from 'react-native';

import type { MatchupGrade } from './matchup';

const BRAND_INK = '#0B1320'; // the S itself; also `tint` (one literal, two names)

export const colors = {
  // System backgrounds
  bg: '#F2F2F7',
  bgElevated: '#FFFFFF',
  bgGrouped: '#F2F2F7',
  bgCard: '#FFFFFF',

  // Text
  textPrimary: '#000000',
  textSecondary: '#3C3C43',
  textTertiary: '#3C3C4399',
  textInverse: '#FFFFFF',

  // Separators
  separator: '#3C3C4349',
  separatorOpaque: '#C6C6C8',

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
  brandMuted: '#8A97AB', // the banner's caption grey — inactive on navy (6.3:1)
  brandSeparator: '#374151', // hairline between navy chrome surfaces (1.8:1 vs navy)

  // Tints
  tint: BRAND_INK, // primary actions, links, selection
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
  noneSoft: '#EFEFF4',

  // ── Matchup difficulty ramp (the Stats board's MATCHUP column) ───────────
  // Five steps across the A→F grade scale, NOT the bet/avoid pair. Two
  // reasons they are their own colours:
  //
  //   1. `bet` / `avoid` are BET/AVOID semantics. A row already carries a
  //      hit-rate traffic light and a price; a third thing in the same green
  //      reads as a side to take rather than a spot to weigh.
  //   2. `bet` (#34C759) is 2.22:1 on bgCard and AMBER (#FF9500) is 2.20:1 —
  //      both FAIL WCAG AA for text, and the old three-tier column was drawn
  //      in exactly those. Every value below is ≥ 4.9:1 on white (measured,
  //      2026-09-05), because here the colour sits on a two-character word
  //      that has to be read, not on a filled pill.
  //
  // C is grey on purpose: average is not a signal, and 13 grades with a
  // coloured middle turn the column into noise.
  gradeA: '#17803D', // 5.01:1
  gradeB: '#4D7C0F', // 4.99:1
  gradeC: '#6E6E73', // 5.07:1
  gradeD: '#C2410C', // 5.18:1
  gradeF: '#B3261E', // 6.54:1

  // Confidence
  high: '#34C759',
  med: '#FF9500',
  low: '#8E8E93',

  // "Best payout" marker — the star on the betslip's Open-with tiles. A dark
  // gold rather than the brand amber (1.9:1 on white) or `med` (confidence).
  best: '#B8860B',

  // Third-party brand: DraftKings' green, the one book colour the app carries
  // (its chip on every BET card, the picker badge, the betslip row). Text on
  // it is textPrimary (~10.7:1). Lives here so a dark-surface variant has one
  // home when the app gets a dark theme.
  bookDraftKings: '#53D337',

  // Performance heat map
  positive: '#34C759',
  negative: '#FF3B30',
  neutral: '#C7C7CC',
};

export const radii = {
  sm: 8,
  md: 12,
  lg: 16,
  pill: 999,
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

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
    micro: 11,
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
 * Matchup grade → its colour. Five steps across thirteen letters: the letter
 * separates neighbours, the colour separates tiers.
 *
 * It lives here rather than in the board because two screens draw a grade —
 * the Stats MATCHUP column and the player's detail header — and a second copy
 * is how they drift apart. (It cannot live in `lib/matchup.ts`: that module is
 * imported by the tsx verify scripts, and this file pulls in `react-native`,
 * which they cannot resolve.)
 */
export function gradeColor(grade: MatchupGrade): string {
  const letter = grade[0];
  if (letter === 'A') return colors.gradeA;
  if (letter === 'B') return colors.gradeB;
  if (letter === 'C') return colors.gradeC;
  if (letter === 'D') return colors.gradeD;
  return colors.gradeF;
}

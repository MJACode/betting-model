/**
 * iOS-style design tokens.
 * Modeled on Apple HIG light + dark system colors and SF system fonts.
 */

import { Platform } from 'react-native';

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

  // Tints
  tint: '#007AFF', // iOS system blue

  // Signals
  bet: '#34C759', // green
  betSoft: '#E8F8EC',
  avoid: '#FF3B30', // red
  avoidSoft: '#FDECEB',
  none: '#8E8E93', // gray
  noneSoft: '#EFEFF4',

  // Confidence
  high: '#34C759',
  med: '#FF9500',
  low: '#8E8E93',

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

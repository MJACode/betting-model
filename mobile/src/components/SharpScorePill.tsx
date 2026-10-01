import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { SharpBand } from '@/lib/sharpScore';
import { sharpScoreSpeech } from '@/lib/a11y';
import { colors, font, radii } from '@/lib/theme';

/**
 * Compact "⚡ 78" Sharp Score pill. Color tracks the band (high = green,
 * med = amber, low = muted). Shown on BET picks in the card meta row and on the
 * pick detail header.
 */
export function SharpScorePill({ score, band }: { score: number; band: SharpBand }) {
  const tone = TONE[band];
  return (
    // One spoken element, "Sharp score 78 of 100, high" — the pill was colour
    // plus a bare number, read as "78" with no scale or meaning (audit M5).
    <View
      style={[styles.pill, { backgroundColor: tone.bg }]}
      accessible
      accessibilityRole="text"
      accessibilityLabel={sharpScoreSpeech(score, BAND_WORD[band])}
    >
      <Ionicons name="flash" size={11} color={tone.fg} />
      <Text style={[styles.text, { color: tone.fg }]}>{score}</Text>
    </View>
  );
}

const BAND_WORD: Record<SharpBand, string> = { high: 'high', med: 'medium', low: 'low' };

const TONE: Record<SharpBand, { bg: string; fg: string }> = {
  // Inks on the washes (4.61 / 4.99 / 9.55:1); the bright hues were ~2:1 (M5).
  high: { bg: colors.betSoft, fg: colors.betInk },
  med: { bg: colors.medSoft, fg: colors.medInk },
  low: { bg: colors.noneSoft, fg: colors.textSecondary },
};

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  text: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    letterSpacing: 0.2,
  },
});

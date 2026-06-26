import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { SharpBand } from '@/lib/sharpScore';
import { colors, font, radii } from '@/lib/theme';

/**
 * Compact "⚡ 78" Sharp Score pill. Color tracks the band (high = green,
 * med = amber, low = muted). Shown on BET picks in the card meta row and on the
 * pick detail header.
 */
export function SharpScorePill({ score, band }: { score: number; band: SharpBand }) {
  const tone = TONE[band];
  return (
    <View style={[styles.pill, { backgroundColor: tone.bg }]}>
      <Ionicons name="flash" size={11} color={tone.fg} />
      <Text style={[styles.text, { color: tone.fg }]}>{score}</Text>
    </View>
  );
}

const TONE: Record<SharpBand, { bg: string; fg: string }> = {
  high: { bg: colors.betSoft, fg: colors.bet },
  med: { bg: '#FFF4E5', fg: colors.med },
  low: { bg: colors.noneSoft, fg: colors.low },
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

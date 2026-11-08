/**
 * The injury word chip (O / IR / D / Q / DTD) beside a player's name. Moved out
 * of StatsScreen on 2026-11-08 so the NBA 1st Basket board tags the same
 * players the leaderboard does (UX review). Hidden from VoiceOver: each row's
 * own label speaks the status in words.
 */
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { InjuryTag } from '@/lib/injuryStatus';
import { colors, font, radii, spacing } from '@/lib/theme';

export function InjuryChip({ tag }: { tag: InjuryTag }) {
  const out = tag.tone === 'out';
  return (
    <View
      style={[styles.injuryChip, { backgroundColor: out ? colors.avoidSoft : colors.medSoft }]}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Text
        style={[styles.injuryChipText, { color: out ? colors.avoidInk : colors.medInk }]}
        maxFontSizeMultiplier={1.4}
      >
        {tag.label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  injuryChip: {
    borderRadius: radii.xs,
    paddingHorizontal: spacing.xs,
    paddingVertical: 1,
    flexShrink: 0,
  },
  injuryChipText: {
    fontSize: font.size.micro,
    fontWeight: font.weight.bold,
    letterSpacing: 0.3,
  },
});

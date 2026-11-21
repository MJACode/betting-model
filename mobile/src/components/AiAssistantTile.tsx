import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useAiAssistant } from '@/hooks/useAiAssistant';
import { aiAssistantMode, aiTileBadge, aiTileSummary } from '@/lib/aiAssistant';
import { colors, font, radii, spacing, opacity } from '@/lib/theme';

/**
 * The AI Assistant tile at the top of Settings (mockup 1). Navy, full width,
 * above the grid, for paying, comped, trial and App Review accounts. Hidden
 * for everyone else, and while the status has not loaded.
 */
export function AiAssistantTile({ onPress }: { onPress: () => void }) {
  const { status } = useAiAssistant();
  const mode = aiAssistantMode(status);
  if (mode === 'hidden') return null;
  const summary = aiTileSummary(status);
  const badge = aiTileBadge(status);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`AI Assistant. ${summary}${badge ? `. ${badge}` : ''}`}
      onPress={onPress}
      style={({ pressed }) => [styles.tile, pressed && styles.pressed]}
    >
      <View style={styles.icon} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <Ionicons name="sparkles" size={20} color={colors.brandInk} />
      </View>
      <View style={styles.text}>
        <Text style={styles.title}>AI Assistant</Text>
        <Text style={styles.summary} numberOfLines={2}>{summary}</Text>
      </View>
      {badge ? (
        <View style={[styles.badge, badge === 'Locked' && styles.badgeLocked]}>
          <Text style={[styles.badgeText, badge === 'Locked' && styles.badgeTextLocked]}>{badge}</Text>
        </View>
      ) : (
        <Ionicons name="chevron-forward" size={16} color={colors.brandMuted} />
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tile: {
    backgroundColor: colors.chromeSurface,
    borderRadius: radii.md,
    padding: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    minHeight: 72,
    marginBottom: spacing.md,
  },
  pressed: { opacity: opacity.pressed },
  icon: {
    width: 40,
    height: 40,
    borderRadius: radii.md,
    backgroundColor: colors.brand,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: { flex: 1, gap: 2 },
  title: {
    fontFamily: font.family,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.onChrome,
  },
  summary: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.onChromeSecondary,
  },
  badge: {
    backgroundColor: colors.brand,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  badgeLocked: { backgroundColor: colors.chromeSurfaceRaised },
  badgeText: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.brandInk,
  },
  badgeTextLocked: { color: colors.onChrome },
});

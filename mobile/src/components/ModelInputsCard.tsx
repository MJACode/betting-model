import React, { useState } from 'react';
import { LayoutAnimation, Platform, Pressable, StyleSheet, Text, UIManager, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { Sport } from '@/hooks/useSportFilter';
import { MODEL_INPUTS_DECIDES, modelInputsForSport } from '@/lib/modelInputs';
import { colors, font, radii, spacing } from '@/lib/theme';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

/**
 * "What these models look at" — the plain-language list of data the selected
 * sport's built-in models consider, at the top of the Models tab.
 *
 * Collapsed by default: the Models list is a scanning screen and the record is
 * what a user comes for, so the card is one line of headline plus a chevron
 * until tapped. Expanded, it lists each input group as chips and names the
 * sources, and closes on the one line every sport shares — these inputs set
 * the probability; DraftKings' line decides the pick.
 *
 * Copy lives in `@/lib/modelInputs` (one entry per sport); this component only
 * lays it out.
 */
export function ModelInputsCard({ sport }: { sport: Sport }) {
  const [expanded, setExpanded] = useState(false);
  const inputs = modelInputsForSport(sport);

  const toggle = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded((e) => !e);
  };

  return (
    <View style={styles.card}>
      <Pressable
        onPress={toggle}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        accessibilityLabel={`What ${sport} models look at`}
        accessibilityHint={expanded ? 'Collapses the list of model inputs' : 'Expands the list of model inputs'}
        style={({ pressed }) => [styles.headerRow, pressed && styles.pressed]}
      >
        <Ionicons name="layers-outline" size={18} color={colors.tint} style={styles.headerIcon} />
        <View style={styles.headerText}>
          <Text style={styles.title}>What {sport} models look at</Text>
          {expanded ? null : (
            <Text style={styles.headline} numberOfLines={2}>
              {inputs.headline}
            </Text>
          )}
        </View>
        <Ionicons
          name={expanded ? 'chevron-up' : 'chevron-down'}
          size={18}
          color={colors.textTertiary}
        />
      </Pressable>

      {expanded ? (
        <View style={styles.body}>
          {inputs.groups.map((g) => (
            <View key={g.label} style={styles.group}>
              <Text style={styles.groupLabel}>{g.label}</Text>
              <View style={styles.chipWrap}>
                {g.items.map((item) => (
                  <View key={item} style={styles.chip}>
                    <Text style={styles.chipText}>{item}</Text>
                  </View>
                ))}
              </View>
            </View>
          ))}
          <Text style={styles.sources}>Sources: {inputs.sources.join(' · ')}</Text>
          <Text style={styles.decides}>{MODEL_INPUTS_DECIDES}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    minHeight: 44,
  },
  pressed: { opacity: 0.7 },
  headerIcon: { marginTop: 1 },
  headerText: { flex: 1 },
  title: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  headline: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
    lineHeight: 18,
  },
  body: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    paddingTop: spacing.sm,
  },
  group: {
    marginBottom: spacing.sm,
  },
  groupLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: spacing.xs,
  },
  chipWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  chip: {
    backgroundColor: colors.noneSoft,
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  chipText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  sources: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.xs,
    lineHeight: 16,
  },
  decides: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: spacing.sm,
    lineHeight: 18,
  },
});

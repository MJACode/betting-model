/**
 * Inline, always-visible quick filters + sort + search that sit above the pick
 * list. The advanced modal (PicksFilterBar) stays for prob/edge/EV thresholds;
 * this surfaces the most common actions in one tap so they're discoverable.
 *
 * Quick chips mutate the shared `PicksFilterState`, so they compose with the
 * modal (e.g. tap "Props" here, then set a min edge in the modal).
 */

import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  DEFAULT_FILTER,
  type ModelCategory,
  type PicksFilterState,
} from '@/components/PicksFilterBar';
import { SORT_OPTIONS, type SortKey } from '@/lib/pickSort';
import { colors, font, radii, spacing } from '@/lib/theme';

const PROP_CATS: ModelCategory[] = ['pitcher_prop', 'batter_prop', 'player_prop'];

interface Props {
  filter: PicksFilterState;
  onFilterChange: (next: PicksFilterState) => void;
  sortKey: SortKey;
  onSortChange: (key: SortKey) => void;
  search: string;
  onSearchChange: (value: string) => void;
}

function clone(state: PicksFilterState): PicksFilterState {
  return {
    signals: new Set(state.signals),
    categories: new Set(state.categories),
    modelIds: new Set(state.modelIds),
    minProb: state.minProb,
    minEdge: state.minEdge,
    minEV: state.minEV,
  };
}

export function QuickFilters({
  filter,
  onFilterChange,
  sortKey,
  onSortChange,
  search,
  onSearchChange,
}: Props) {
  const gameOnly = filter.categories.size === 1 && filter.categories.has('game');
  const propsOnly =
    !filter.categories.has('game') && PROP_CATS.every((c) => filter.categories.has(c));

  const toggleGame = () => {
    const next = clone(filter);
    next.categories = gameOnly
      ? new Set(DEFAULT_FILTER.categories)
      : new Set<ModelCategory>(['game']);
    onFilterChange(next);
  };

  const toggleProps = () => {
    const next = clone(filter);
    next.categories = propsOnly ? new Set(DEFAULT_FILTER.categories) : new Set(PROP_CATS);
    onFilterChange(next);
  };

  return (
    <View style={styles.wrap}>
      <View style={styles.searchRow}>
        <Ionicons name="search" size={15} color={colors.textTertiary} />
        <TextInput
          style={styles.searchInput}
          value={search}
          onChangeText={onSearchChange}
          placeholder="Search player or team"
          placeholderTextColor={colors.textTertiary}
          autoCapitalize="none"
          autoCorrect={false}
          returnKeyType="search"
          clearButtonMode="while-editing"
        />
        {search.length > 0 ? (
          <Pressable onPress={() => onSearchChange('')} hitSlop={8}>
            <Ionicons name="close-circle" size={16} color={colors.textTertiary} />
          </Pressable>
        ) : null}
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chipRow}
      >
        <QuickChip label="Game" active={gameOnly} onPress={toggleGame} />
        <QuickChip label="Props" active={propsOnly} onPress={toggleProps} />

        <View style={styles.divider} />
        <Text style={styles.sortLabel}>Sort</Text>
        {SORT_OPTIONS.map((o) => (
          <QuickChip
            key={o.key}
            label={o.label}
            active={sortKey === o.key}
            onPress={() => onSortChange(o.key)}
          />
        ))}
      </ScrollView>
    </View>
  );
}

function QuickChip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.chip, active && styles.chipActive, pressed && styles.pressed]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingTop: spacing.sm,
    backgroundColor: colors.bg,
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginHorizontal: spacing.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    backgroundColor: colors.bgCard,
    borderRadius: radii.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separator,
  },
  searchInput: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
    paddingVertical: spacing.xs,
  },
  chipRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  chipActive: {
    backgroundColor: colors.tint,
    borderColor: colors.tint,
  },
  chipText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  chipTextActive: {
    color: colors.textInverse,
  },
  divider: {
    width: StyleSheet.hairlineWidth,
    alignSelf: 'stretch',
    marginVertical: 2,
    marginHorizontal: spacing.xs,
    backgroundColor: colors.separator,
  },
  sortLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  pressed: { opacity: 0.6 },
});

/**
 * The one filter bar. Search + a single Filters entry point + removable pills
 * for whatever is currently narrowing the list.
 *
 * Replaces the two stacked bars the Picks tab used to render (a search/quick-chip
 * row from QuickFilters, then a separate Filter-button/count/threshold-pill row
 * from PicksFilterBar) — same controls, roughly half the vertical space, and one
 * place to look for "why am I not seeing everything?".
 *
 * Layout:
 *   row 1  search field ......................... [Filters (n)]
 *   row 2  caller-supplied quick chips (optional)
 *   row 3  active filter pills + count + Clear all   (only when filtered)
 *
 * Every active filter gets a pill, not just some of them. The old bar only
 * surfaced the three numeric thresholds, so a signal/category/model filter set
 * inside the modal was invisible from the outside.
 */

import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';

export interface ActivePill {
  key: string;
  label: string;
  onRemove: () => void;
}

interface Props {
  /** Omit both search props to hide the search field entirely. */
  search?: string;
  onSearchChange?: (v: string) => void;
  searchPlaceholder?: string;

  onOpenFilters: () => void;
  /** Count shown on the Filters button. 0 hides the badge. */
  activeCount: number;

  pills?: ActivePill[];
  onClearAll?: () => void;

  /** e.g. "24 of 51" — rendered next to the pills while filtered. */
  countLabel?: string;

  /** Quick chips row (sort, category shortcuts, …). */
  children?: React.ReactNode;
}

export function FilterBar({
  search,
  onSearchChange,
  searchPlaceholder = 'Search',
  onOpenFilters,
  activeCount,
  pills = [],
  onClearAll,
  countLabel,
  children,
}: Props) {
  const showSearch = onSearchChange != null;
  const showPills = pills.length > 0;

  return (
    <View style={styles.wrap}>
      <View style={styles.topRow}>
        {showSearch ? (
          <View style={styles.searchWrap}>
            <Ionicons name="search" size={15} color={colors.textTertiary} />
            <TextInput
              style={styles.searchInput}
              value={search}
              onChangeText={onSearchChange}
              placeholder={searchPlaceholder}
              placeholderTextColor={colors.textTertiary}
              autoCapitalize="none"
              autoCorrect={false}
              returnKeyType="search"
              clearButtonMode="while-editing"
            />
            {(search?.length ?? 0) > 0 ? (
              <Pressable onPress={() => onSearchChange?.('')} hitSlop={8}>
                <Ionicons name="close-circle" size={16} color={colors.textTertiary} />
              </Pressable>
            ) : null}
          </View>
        ) : (
          <View style={styles.searchWrap} />
        )}

        <Pressable
          onPress={onOpenFilters}
          accessibilityLabel={
            activeCount > 0 ? `Filters, ${activeCount} active` : 'Filters'
          }
          style={({ pressed }) => [
            styles.filterBtn,
            activeCount > 0 && styles.filterBtnActive,
            pressed && styles.pressed,
          ]}
        >
          <Ionicons name="options-outline" size={16} color={colors.tint} />
          <Text style={styles.filterBtnText}>Filters</Text>
          {activeCount > 0 ? (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{activeCount}</Text>
            </View>
          ) : null}
        </Pressable>
      </View>

      {children ? <View style={styles.quickRow}>{children}</View> : null}

      {showPills ? (
        <View style={styles.pillsRow}>
          {countLabel ? <Text style={styles.countLabel}>{countLabel}</Text> : null}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.pillsScroll}
            keyboardShouldPersistTaps="handled"
          >
            {pills.map((p) => (
              <Pressable
                key={p.key}
                onPress={p.onRemove}
                accessibilityLabel={`Remove filter ${p.label}`}
                style={({ pressed }) => [styles.pill, pressed && styles.pressed]}
                hitSlop={6}
              >
                <Text style={styles.pillText}>{p.label}</Text>
                <Ionicons name="close" size={12} color={colors.tint} />
              </Pressable>
            ))}
            {onClearAll ? (
              <Pressable
                onPress={onClearAll}
                style={({ pressed }) => [styles.clearBtn, pressed && styles.pressed]}
                hitSlop={6}
              >
                <Text style={styles.clearText}>Clear all</Text>
              </Pressable>
            ) : null}
          </ScrollView>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.bg,
    paddingTop: spacing.sm,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  searchWrap: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
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
  filterBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  filterBtnActive: {
    borderColor: colors.tint,
  },
  filterBtnText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  badge: {
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 5,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    fontSize: 11,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
  },
  quickRow: {
    marginTop: spacing.sm,
  },
  pillsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.sm,
    paddingLeft: spacing.lg,
  },
  countLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
  },
  pillsScroll: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingRight: spacing.lg,
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingLeft: 10,
    paddingRight: 7,
    paddingVertical: 4,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.tint,
  },
  pillText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  clearBtn: {
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  clearText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.avoid,
  },
  pressed: { opacity: 0.65 },
});

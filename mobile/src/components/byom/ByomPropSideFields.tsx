import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ByomCheckChip } from '@/components/byom/ByomCheckChip';
import { ByomChoiceGroup } from '@/components/byom/ByomChoiceGroup';
import {
  isYesOnlyProp,
  type ByomMarket,
  type ByomPropSide,
  type ByomSport,
} from '@/lib/byomRecord';
import {
  matchupSummary,
  oddsSummary,
  primeOn,
  shownKickSlots,
  timeSummary,
  withPrime,
  type ByomPropFilterState,
} from '@/lib/byomPropFilters';
import { colors, font, radii, spacing } from '@/lib/theme';

export type ByomSheetTab = 'odds' | 'time' | 'matchup';

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionLabel}>{label}</Text>
      {children}
    </View>
  );
}

export function ByomPropSideFields({
  market,
  propSide,
  role,
  primetime,
  sport,
  rest,
  propFilters,
  onPropSide,
  onRole,
  onPrimetime,
  onRest,
  onPropFilters,
}: {
  market: ByomMarket;
  propSide: ByomPropSide | null;
  role: 'favorite' | 'underdog' | 'pickem' | null;
  primetime: boolean | null;
  sport: ByomSport;
  rest: 'b2b' | 'rest2' | null;
  propFilters: ByomPropFilterState;
  onPropSide: (side: ByomPropSide | null) => void;
  onRole: (role: 'favorite' | 'underdog' | 'pickem' | null) => void;
  onPrimetime: (primetime: boolean | null) => void;
  onRest: (rest: 'b2b' | 'rest2' | null) => void;
  onPropFilters: (next: ByomPropFilterState) => void;
}) {
  const yesOnly = isYesOnlyProp(market);
  const prime = primeOn(propFilters.kickSlots, primetime);
  const setPrime = (on: boolean) => {
    const next = withPrime(propFilters.kickSlots, primetime, on);
    onPrimetime(next.primetime);
    onPropFilters({ ...propFilters, kickSlots: next.kickSlots });
  };
  return (
    <View>
      {yesOnly ? (
        <View accessible accessibilityLabel="Side, Yes">
          <Text style={styles.sectionLabel}>Side</Text>
          <Text style={styles.yes}>Yes</Text>
        </View>
      ) : (
        <Section label="Over or under">
          <ByomChoiceGroup
            marked
            hideLabel
            label="Over or under"
            value={propSide === 'over' || propSide === 'under' ? propSide : ''}
            onChange={(value) => onPropSide(value === 'over' || value === 'under' ? value : null)}
            options={[
              { value: 'over', label: 'Over' },
              { value: 'under', label: 'Under' },
            ]}
          />
        </Section>
      )}
      <Section label="Favorite or underdog">
        <ByomChoiceGroup
          marked
          hideLabel
          label="Favorite or underdog"
          value={role === 'favorite' || role === 'underdog' ? role : 'any'}
          onChange={(value) => onRole(value === 'any' ? null : value)}
          options={[
            { value: 'any', label: 'Any' },
            { value: 'favorite', label: 'Favorite' },
            { value: 'underdog', label: 'Underdog' },
          ]}
        />
      </Section>
      {sport === 'NBA' ? (
        <Section label="Quick filters">
          <ByomChoiceGroup
            marked
            hideLabel
            label="Quick filters"
            value={rest ?? ''}
            clearOnReselect
            onChange={(value) => onRest(value === 'b2b' || value === 'rest2' ? value : null)}
            options={[
              { value: 'b2b', label: 'Back-to-back' },
              { value: 'rest2', label: '2+ days rest' },
            ]}
          />
        </Section>
      ) : (
        <Section label="Quick filters">
          <View style={styles.wrap}>
            <ByomCheckChip label="Prime time" selected={prime} onPress={() => setPrime(!prime)} />
            <ByomCheckChip
              label="Short week"
              exclusive
              selected={propFilters.shortWeek}
              onPress={() => onPropFilters({
                ...propFilters,
                shortWeek: !propFilters.shortWeek,
                offBye: propFilters.shortWeek ? propFilters.offBye : false,
              })}
            />
            <ByomCheckChip
              label="Off a bye"
              exclusive
              selected={propFilters.offBye}
              onPress={() => onPropFilters({
                ...propFilters,
                offBye: !propFilters.offBye,
                shortWeek: propFilters.offBye ? propFilters.shortWeek : false,
              })}
            />
          </View>
        </Section>
      )}
    </View>
  );
}

export function ByomMoreFiltersCard({
  sport,
  side,
  primetime,
  propFilters,
  onOpen,
}: {
  sport: ByomSport;
  side: 'home' | 'away' | 'over' | 'under' | null;
  primetime: boolean | null;
  propFilters: ByomPropFilterState;
  onOpen: (tab: ByomSheetTab) => void;
}) {
  const slots = sport === 'NFL' ? shownKickSlots(propFilters.kickSlots, primetime) : [];
  const rows: { tab: ByomSheetTab; title: string; summary: { detail: string; pills: string[] } }[] = [
    { tab: 'odds', title: 'Odds', summary: oddsSummary(propFilters) },
    { tab: 'time', title: 'Time', summary: timeSummary(propFilters, sport, slots) },
    { tab: 'matchup', title: 'Matchup', summary: matchupSummary(side, propFilters) },
  ];
  return (
    <View style={styles.more}>
      <Text style={styles.sectionLabel}>More filters · optional</Text>
      <View style={styles.card}>
        {rows.map((row, index) => (
          <Pressable
            key={row.tab}
            onPress={() => onOpen(row.tab)}
            accessibilityRole="button"
            accessibilityLabel={`${row.title}, ${row.summary.detail}`}
            style={[styles.row, index < rows.length - 1 && styles.rowBorder]}
          >
            <View style={styles.rowBody}>
              <Text style={styles.rowTitle}>{row.title}</Text>
              <Text style={styles.rowDetail}>{row.summary.detail}</Text>
              {row.summary.pills.length === 1 && row.summary.pills[0] === 'Any' ? null : (
                <View style={styles.pills}>
                  {row.summary.pills.map((pill) => (
                    <View key={pill} style={styles.pill}>
                      <Text style={styles.pillText}>{pill}</Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
            <Text style={styles.chevron} accessible={false}>›</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    marginBottom: spacing.lg,
  },
  sectionLabel: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    marginBottom: spacing.sm,
  },
  yes: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.lg,
  },
  wrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  more: {
    marginBottom: spacing.md,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
  },
  row: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  rowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separatorOpaque,
  },
  rowBody: {
    flex: 1,
  },
  rowTitle: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  rowDetail: {
    marginTop: 2,
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  pills: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: spacing.xs,
  },
  pill: {
    backgroundColor: colors.tintSoft,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    marginRight: spacing.xs,
    marginTop: spacing.xs,
  },
  pillText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.tint,
  },
  chevron: {
    fontSize: font.size.title3,
    color: colors.low,
    marginLeft: spacing.sm,
  },
});

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ByomChoiceGroup } from '@/components/byom/ByomChoiceGroup';
import type { ByomGameMarket } from '@/lib/byomRecord';
import { colors, font, radii, spacing } from '@/lib/theme';

const MARKETS: { value: ByomGameMarket; label: string }[] = [
  { value: 'h2h', label: 'Moneyline' },
  { value: 'spreads', label: 'Spread' },
  { value: 'totals', label: 'Over/Under' },
];

export function ByomMarketField({
  market,
  onChange,
}: {
  market: ByomGameMarket | null;
  onChange: (market: ByomGameMarket) => void;
}) {
  return (
    <View style={styles.block} accessibilityRole="radiogroup" accessibilityLabel="Game bets">
      <Text style={styles.kicker}>Game bets</Text>
      {MARKETS.map((option) => {
        const selected = option.value === market;
        return (
          <Pressable
            key={option.value}
            onPress={() => onChange(option.value)}
            accessibilityRole="radio"
            accessibilityState={{ selected }}
            accessibilityLabel={option.label}
            style={[styles.market, selected && styles.marketOn]}
          >
            <Text style={[styles.marketText, selected && styles.marketTextOn]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function ByomSideFields({
  market,
  side,
  role,
  primetime,
  onSide,
  onRole,
  onPrimetime,
}: {
  market: ByomGameMarket;
  side: 'home' | 'away' | 'over' | 'under' | null;
  role: 'favorite' | 'underdog' | 'pickem' | null;
  primetime: boolean | null;
  onSide: (side: 'home' | 'away' | 'over' | 'under' | null) => void;
  onRole: (role: 'favorite' | 'underdog' | 'pickem' | null) => void;
  onPrimetime: (primetime: boolean | null) => void;
}) {
  return (
    <View>
      {market === 'totals' ? (
        <ByomChoiceGroup
          label="Side"
          value={side === 'over' || side === 'under' ? side : ''}
          onChange={(value) => onSide(value === 'over' || value === 'under' ? value : null)}
          options={[
            { value: 'over', label: 'Over' },
            { value: 'under', label: 'Under' },
          ]}
        />
      ) : (
        <>
          <ByomChoiceGroup
            label="Team"
            value={side === 'home' || side === 'away' ? side : 'any'}
            onChange={(value) => onSide(value === 'any' ? null : value)}
            options={[
              { value: 'any', label: 'Any' },
              { value: 'home', label: 'Home' },
              { value: 'away', label: 'Away' },
            ]}
          />
          <ByomChoiceGroup
            label="Favorite or underdog"
            value={role ?? 'any'}
            onChange={(value) => onRole(value === 'any' ? null : value)}
            options={[
              { value: 'any', label: 'Any' },
              { value: 'favorite', label: 'Favorite' },
              { value: 'underdog', label: 'Underdog' },
              { value: 'pickem', label: 'Pick’em' },
            ]}
          />
        </>
      )}
      <ByomChoiceGroup
        label="Kickoff"
        value={primetime == null ? 'any' : primetime ? 'prime' : 'other'}
        onChange={(value) => onPrimetime(value === 'any' ? null : value === 'prime')}
        options={[
          { value: 'any', label: 'Any' },
          { value: 'prime', label: 'Primetime' },
          { value: 'other', label: 'Not primetime' },
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  block: {
    marginBottom: spacing.lg,
  },
  kicker: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  market: {
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.separatorOpaque,
  },
  marketOn: {
    backgroundColor: colors.tintSoft,
    borderColor: colors.tint,
  },
  marketText: {
    fontSize: font.size.body,
    fontWeight: font.weight.medium,
    color: colors.textPrimary,
  },
  marketTextOn: {
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
});

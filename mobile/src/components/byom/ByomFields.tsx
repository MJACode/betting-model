import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ByomChoiceGroup } from '@/components/byom/ByomChoiceGroup';
import {
  ANYTIME_TD_MARKET,
  isPropMarket,
  NFL_PROP_MARKETS,
  type ByomMarket,
  type ByomPropSide,
} from '@/lib/byomRecord';
import { colors, font, radii, spacing } from '@/lib/theme';

const GAME_MARKETS: { value: ByomMarket; label: string }[] = [
  { value: 'h2h', label: 'Moneyline' },
  { value: 'spreads', label: 'Spread' },
  { value: 'totals', label: 'Over/Under' },
];

function MarketRow({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      accessibilityLabel={label}
      style={[styles.market, selected && styles.marketOn]}
    >
      <Text style={[styles.marketText, selected && styles.marketTextOn]}>{label}</Text>
    </Pressable>
  );
}

export function ByomMarketField({
  market,
  onChange,
}: {
  market: ByomMarket | null;
  onChange: (market: ByomMarket) => void;
}) {
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel="Bet type">
      <View style={styles.block}>
        <Text style={styles.kicker}>Game bets</Text>
        {GAME_MARKETS.map((option) => (
          <MarketRow
            key={option.value}
            label={option.label}
            selected={option.value === market}
            onPress={() => onChange(option.value)}
          />
        ))}
      </View>
      <View style={styles.block}>
        <Text style={styles.kicker}>NFL player props</Text>
        {NFL_PROP_MARKETS.map((option) => (
          <MarketRow
            key={option.value}
            label={option.label}
            selected={option.value === market}
            onPress={() => onChange(option.value)}
          />
        ))}
      </View>
    </View>
  );
}

export function ByomSideFields({
  market,
  side,
  role,
  primetime,
  propSide,
  onSide,
  onRole,
  onPrimetime,
  onPropSide,
}: {
  market: ByomMarket;
  side: 'home' | 'away' | 'over' | 'under' | null;
  role: 'favorite' | 'underdog' | 'pickem' | null;
  primetime: boolean | null;
  propSide: ByomPropSide | null;
  onSide: (side: 'home' | 'away' | 'over' | 'under' | null) => void;
  onRole: (role: 'favorite' | 'underdog' | 'pickem' | null) => void;
  onPrimetime: (primetime: boolean | null) => void;
  onPropSide: (propSide: ByomPropSide | null) => void;
}) {
  const prop = isPropMarket(market);
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
      ) : prop ? (
        <>
          {market === ANYTIME_TD_MARKET ? (
            <View accessible accessibilityLabel="Side, Yes">
              <Text style={styles.kicker}>Side</Text>
              <Text style={styles.yes}>Yes</Text>
            </View>
          ) : (
            <ByomChoiceGroup
              label="Side"
              value={propSide === 'over' || propSide === 'under' ? propSide : ''}
              onChange={(value) => onPropSide(value === 'over' || value === 'under' ? value : null)}
              options={[
                { value: 'over', label: 'Over' },
                { value: 'under', label: 'Under' },
              ]}
            />
          )}
          <ByomChoiceGroup
            label="Player’s team"
            value={side === 'home' || side === 'away' ? side : 'any'}
            onChange={(value) => onSide(value === 'any' ? null : value)}
            options={[
              { value: 'any', label: 'Any' },
              { value: 'home', label: 'Home' },
              { value: 'away', label: 'Away' },
            ]}
          />
        </>
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
  yes: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.lg,
  },
});

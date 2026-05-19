import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { SignalType } from '@/types';

interface Props {
  signal: SignalType;
  small?: boolean;
}

const LABELS: Record<SignalType, string> = {
  BET: 'BET',
  AVOID: 'AVOID',
  NONE: 'NONE',
};

export function SignalBadge({ signal, small }: Props) {
  const bg =
    signal === 'BET'
      ? colors.betSoft
      : signal === 'AVOID'
        ? colors.avoidSoft
        : colors.noneSoft;
  const fg =
    signal === 'BET'
      ? colors.bet
      : signal === 'AVOID'
        ? colors.avoid
        : colors.none;
  return (
    <View
      style={[
        styles.badge,
        { backgroundColor: bg, paddingHorizontal: small ? 6 : 10 },
      ]}
    >
      <Text style={[styles.label, { color: fg, fontSize: small ? 10 : 12 }]}>
        {LABELS[signal]}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderRadius: radii.pill,
    paddingVertical: 3,
    alignSelf: 'flex-start',
  },
  label: {
    fontWeight: font.weight.semibold,
    letterSpacing: 0.4,
  },
});

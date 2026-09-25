import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii } from '@/lib/theme';
import { SIGNAL_BADGE } from '@/lib/tone';
import type { SignalType } from '@/types';

interface Props {
  signal: SignalType;
  small?: boolean;
}

/**
 * BET / NONE / AVOID. The word is drawn in a text-safe ink on the soft wash
 * (betInk 4.61:1 on betSoft, avoidInk 5.01:1 on avoidSoft, textSecondary
 * 9.55:1 on noneSoft) with a leading ✓ / – / ✕ glyph, so the state survives
 * low vision, sunlight and red/green colour blindness (usability audit H1).
 * The bright `bet` / `avoid` hues were 2.02 / 3.10:1 here.
 */
export function SignalBadge({ signal, small }: Props) {
  const spec = SIGNAL_BADGE[signal];
  const fg = colors[spec.ink];
  const size = small ? font.size.nano : font.size.caption;
  return (
    <View
      style={[
        styles.badge,
        { backgroundColor: colors[spec.fill], paddingHorizontal: small ? 6 : 10 },
      ]}
    >
      {/* Decorative for VoiceOver: the word already says it. */}
      <Ionicons
        name={spec.glyph}
        size={size}
        color={fg}
        accessibilityElementsHidden
        importantForAccessibility="no"
      />
      <Text style={[styles.label, { color: fg, fontSize: size }]}>{spec.label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    borderRadius: radii.pill,
    paddingVertical: 3,
    alignSelf: 'flex-start',
  },
  label: {
    fontWeight: font.weight.semibold,
    letterSpacing: 0.4,
  },
});

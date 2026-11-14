import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { colors, font, opacity, radii, spacing } from '@/lib/theme';

/**
 * The app's one primary button: a full-width capsule, 50pt tall, label in
 * headline semibold.
 *
 * Before 2026-11-14 fifteen screens drew their own — five capsules and nine
 * rounded rectangles, at 44, 48, 50 and 52pt, disabled either faded or greyed
 * (Matt approved one shape, the capsule, after the Mobbin pass: Wealthfront,
 * Fuse and Flo all use a single full-width capsule).
 *
 *  - `primary`   ink fill, white label — every light surface.
 *  - `brand`     amber fill, ink label — the navy chrome ONLY (paywall,
 *                sign-in, the locked-signal card). Amber on white is 1.9:1
 *                (UX_REVIEW §2), so never use it on a light surface.
 *  - `secondary` grey fill, ink label — the quieter action beside a primary.
 *
 * Disabled is always the same fill at `opacity.disabled`, so a disabled
 * button still reads as the button it will become.
 */
export type PrimaryButtonVariant = 'primary' | 'brand' | 'secondary';

export function PrimaryButton({
  label,
  onPress,
  variant = 'primary',
  disabled = false,
  loading = false,
  busy = false,
  accessibilityLabel,
  accessibilityHint,
  icon,
  style,
  testID,
}: {
  label: string;
  onPress: () => void;
  variant?: PrimaryButtonVariant;
  disabled?: boolean;
  /** Shows a spinner in place of the label and blocks presses. */
  loading?: boolean;
  /** Announced busy to VoiceOver but still pressable — for a label that is
   *  updating ("Updating…") where trapping the user is the worse trade. */
  busy?: boolean;
  /** What VoiceOver reads, when it should say more than the label. */
  accessibilityLabel?: string;
  accessibilityHint?: string;
  /** Drawn before the label (an Ionicons element, sized ~18). */
  icon?: React.ReactNode;
  /** Outer spacing only (margins, alignSelf). The shape is not overridable. */
  style?: StyleProp<ViewStyle>;
  testID?: string;
}) {
  const inactive = disabled || loading;
  const fg = variant === 'primary' ? colors.textInverse : colors.brandInk;
  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: inactive, busy: loading || busy }}
      testID={testID}
      style={({ pressed }) => [
        styles.base,
        variant === 'primary' && styles.primary,
        variant === 'brand' && styles.brand,
        variant === 'secondary' && styles.secondary,
        disabled && styles.disabled,
        pressed && !inactive && styles.pressed,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <>
          {icon}
          <Text style={[styles.label, { color: fg }]} numberOfLines={1}>
            {label}
          </Text>
        </>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 50,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    alignSelf: 'stretch',
  },
  primary: { backgroundColor: colors.tint },
  brand: { backgroundColor: colors.brand },
  secondary: { backgroundColor: colors.noneSoft },
  disabled: { opacity: opacity.disabled },
  pressed: { opacity: opacity.pressed },
  label: {
    fontFamily: font.family,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
});

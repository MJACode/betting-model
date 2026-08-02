/**
 * Labeled numeric input for filter sheets ("Min edge  [ 10 ] %").
 *
 * Picks and Stats each had their own version with different label placement,
 * different input widths and different keyboard types; this is the shared one.
 * Digits-only by default so the value can always be parsed.
 */

import React from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  /** Trailing unit, e.g. "%". */
  suffix?: string;
  /** Allow a decimal point (default: integers only). */
  decimal?: boolean;
  maxLength?: number;
}

export function FilterField({
  label,
  value,
  onChange,
  placeholder,
  suffix,
  decimal = false,
  maxLength = 5,
}: Props) {
  const sanitize = (t: string) => onChange(t.replace(decimal ? /[^0-9.]/g : /[^0-9]/g, ''));
  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.inputWrap}>
        <TextInput
          style={styles.input}
          value={value}
          onChangeText={sanitize}
          placeholder={placeholder}
          placeholderTextColor={colors.textTertiary}
          keyboardType={decimal ? 'decimal-pad' : 'number-pad'}
          maxLength={maxLength}
        />
        {suffix ? <Text style={styles.suffix}>{suffix}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1 },
  label: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bg,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
  },
  input: {
    flex: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    paddingVertical: spacing.sm,
  },
  suffix: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    marginLeft: 4,
  },
});

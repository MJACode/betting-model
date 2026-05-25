import React, { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { formatCurrency, formatPct } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  amount: number;
  recommendation: number;
  bankroll: number;
  onChange: (value: number) => void;
}

/**
 * Editable stake for a tracked bet. Shown under the Placed toggle.
 *
 * The saved amount is frozen — changing bankroll or Kelly settings after the
 * fact does NOT mutate it. The "Reset to Kelly" button is the explicit way to
 * snap back to the current recommendation.
 */
export function BetAmountEditor({ amount, recommendation, bankroll, onChange }: Props) {
  const [draft, setDraft] = useState<string>(amount > 0 ? amount.toFixed(2) : '');

  // Sync inbound amount changes (e.g. Reset to Kelly) into the input.
  useEffect(() => {
    setDraft(amount > 0 ? amount.toFixed(2) : '');
  }, [amount]);

  const commit = (raw: string) => {
    if (raw.trim() === '') {
      onChange(0);
      return;
    }
    const v = parseFloat(raw);
    if (Number.isFinite(v) && v >= 0) onChange(Math.round(v * 100) / 100);
  };

  const pctOfRoll = bankroll > 0 ? amount / bankroll : 0;
  const matchesKelly = Math.abs(amount - recommendation) < 0.01;

  return (
    <View style={styles.card}>
      <View style={styles.row}>
        <Text style={styles.label}>Bet amount</Text>
        <View style={styles.inputWrap}>
          <Text style={styles.dollar}>$</Text>
          <TextInput
            style={styles.input}
            value={draft}
            onChangeText={setDraft}
            onBlur={() => commit(draft)}
            onSubmitEditing={() => commit(draft)}
            keyboardType="decimal-pad"
            placeholder="0.00"
            placeholderTextColor={colors.textTertiary}
            returnKeyType="done"
            selectTextOnFocus
          />
        </View>
      </View>

      <View style={styles.subRow}>
        <Text style={styles.sub}>
          {amount > 0
            ? `${formatPct(pctOfRoll)} of bankroll · Kelly suggests ${formatCurrency(recommendation)}`
            : `Tracking with no stake · Kelly suggests ${formatCurrency(recommendation)}`}
        </Text>
        {!matchesKelly ? (
          <Pressable
            onPress={() => onChange(recommendation)}
            hitSlop={6}
            style={({ pressed }) => [styles.resetBtn, pressed && styles.resetBtnPressed]}
          >
            <Text style={styles.resetText}>Reset to Kelly</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
  },
  label: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bg,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    minWidth: 140,
  },
  dollar: {
    fontSize: font.size.title3,
    color: colors.textPrimary,
    fontWeight: font.weight.semibold,
    marginRight: 2,
  },
  input: {
    flex: 1,
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    paddingVertical: spacing.sm,
    textAlign: 'right',
  },
  subRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
    gap: spacing.md,
  },
  sub: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  resetBtn: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  resetBtnPressed: {
    opacity: 0.6,
  },
  resetText: {
    fontSize: font.size.footnote,
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
});

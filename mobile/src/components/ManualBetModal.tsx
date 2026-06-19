import React, { useState } from 'react';
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { ManualBetInput } from '@/hooks/useManualBets';

/** Add-a-bet form for the manual fallback (sync gaps / unsupported books). */
export function ManualBetModal({
  visible,
  onClose,
  onAdd,
}: {
  visible: boolean;
  onClose: () => void;
  onAdd: (input: ManualBetInput) => void;
}) {
  const [desc, setDesc] = useState('');
  const [book, setBook] = useState('');
  const [stake, setStake] = useState('');
  const [odds, setOdds] = useState('');

  const reset = () => {
    setDesc('');
    setBook('');
    setStake('');
    setOdds('');
  };

  const stakeNum = parseFloat(stake);
  const oddsNum = odds.trim() === '' ? null : parseInt(odds, 10);
  const valid = desc.trim().length > 0 && Number.isFinite(stakeNum) && stakeNum > 0;

  const submit = () => {
    if (!valid) return;
    onAdd({
      description: desc.trim(),
      book: book.trim() || null,
      stake: stakeNum,
      odds_american: oddsNum != null && Number.isFinite(oddsNum) ? oddsNum : null,
    });
    reset();
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView
        style={styles.backdrop}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <Pressable style={styles.backdropFill} onPress={onClose} />
        <View style={styles.sheet}>
          <Text style={styles.title}>Add a bet</Text>
          <Text style={styles.subtitle}>
            For bets your sportsbook didn’t sync. Tracked on this device only.
          </Text>

          <Field label="Bet">
            <TextInput
              style={styles.input}
              value={desc}
              onChangeText={setDesc}
              placeholder="e.g. Yankees ML"
              placeholderTextColor={colors.textTertiary}
            />
          </Field>
          <Field label="Sportsbook (optional)">
            <TextInput
              style={styles.input}
              value={book}
              onChangeText={setBook}
              placeholder="DraftKings"
              placeholderTextColor={colors.textTertiary}
            />
          </Field>
          <View style={styles.row}>
            <Field label="Stake ($)" style={{ flex: 1 }}>
              <TextInput
                style={styles.input}
                value={stake}
                onChangeText={setStake}
                keyboardType="decimal-pad"
                placeholder="50"
                placeholderTextColor={colors.textTertiary}
              />
            </Field>
            <Field label="Odds (American)" style={{ flex: 1 }}>
              <TextInput
                style={styles.input}
                value={odds}
                onChangeText={setOdds}
                keyboardType={Platform.OS === 'ios' ? 'numbers-and-punctuation' : 'default'}
                placeholder="-110"
                placeholderTextColor={colors.textTertiary}
              />
            </Field>
          </View>

          <Pressable
            onPress={submit}
            disabled={!valid}
            style={({ pressed }) => [
              styles.addBtn,
              !valid && styles.addBtnDisabled,
              pressed && valid && styles.pressed,
            ]}
          >
            <Text style={styles.addBtnText}>Add bet</Text>
          </Pressable>
          <Pressable onPress={onClose} style={styles.cancelBtn}>
            <Text style={styles.cancelText}>Cancel</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

function Field({
  label,
  style,
  children,
}: {
  label: string;
  style?: object;
  children: React.ReactNode;
}) {
  return (
    <View style={[styles.field, style]}>
      <Text style={styles.fieldLabel}>{label}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: 'flex-end' },
  backdropFill: { ...StyleSheet.absoluteFillObject, backgroundColor: '#00000055' },
  sheet: {
    backgroundColor: colors.bgElevated,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    padding: spacing.lg,
    paddingBottom: spacing.xl,
  },
  title: { fontSize: font.size.title3, fontWeight: font.weight.bold, color: colors.textPrimary },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
    marginBottom: spacing.md,
  },
  field: { marginBottom: spacing.md },
  fieldLabel: { fontSize: font.size.caption, color: colors.textTertiary, marginBottom: 4 },
  row: { flexDirection: 'row', gap: spacing.md },
  input: {
    backgroundColor: colors.bg,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  addBtn: {
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  addBtnDisabled: { opacity: 0.4 },
  addBtnText: { color: colors.textInverse, fontSize: font.size.headline, fontWeight: font.weight.semibold },
  cancelBtn: { paddingVertical: spacing.md, alignItems: 'center' },
  cancelText: { color: colors.textSecondary, fontSize: font.size.body },
  pressed: { opacity: 0.8 },
});

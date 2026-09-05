import React from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { BETTING_STATES, useBettingState } from '@/hooks/useBettingState';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Your state" — the US state the member's sportsbook accounts are licensed
 * in. Three books' betslip links carry a `{state}` placeholder and cannot
 * open the app with the bet on the slip until it is filled (lib/
 * sportsbookLinks.ts). Single select, applied on tap — one value, and the
 * Settings row it opens from is the feedback. Same sheet shell as
 * SportsbookPickerSheet.
 */
export function StatePickerSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const { state, setState } = useBettingState();
  const pick = (code: string | null) => {
    setState(code);
    onClose();
  };
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityRole="button" accessibilityLabel="Close">
        <Pressable style={styles.sheet} onPress={() => {}} accessible={false} accessibilityViewIsModal>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <Text style={styles.title}>Your state</Text>
            <Pressable onPress={onClose} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          <Text style={styles.subtitle}>
            Where your sportsbook accounts are licensed. BetMGM, BetRivers and Caesars need it to
            open the app with your bet on the slip. Stored on this device only.
          </Text>
          <ScrollView style={styles.list} bounces={false}>
            <Pressable
              onPress={() => pick(null)}
              accessibilityRole="radio"
              accessibilityState={{ checked: state == null }}
              accessibilityLabel="Not set"
              style={({ pressed }) => [styles.row, state == null && styles.rowActive, pressed && styles.pressed]}
            >
              <Text style={styles.rowName}>Not set</Text>
              {state == null ? <Ionicons name="checkmark-circle" size={22} color={colors.bet} /> : <View style={styles.emptyCircle} />}
            </Pressable>
            {BETTING_STATES.map((s) => {
              const active = s.code === state;
              return (
                <Pressable
                  key={s.code}
                  onPress={() => pick(s.code)}
                  accessibilityRole="radio"
                  accessibilityState={{ checked: active }}
                  accessibilityLabel={s.name}
                  style={({ pressed }) => [styles.row, active && styles.rowActive, pressed && styles.pressed]}
                >
                  <Text style={styles.rowCode}>{s.code.toUpperCase()}</Text>
                  <Text style={styles.rowName}>{s.name}</Text>
                  {active ? <Ionicons name="checkmark-circle" size={22} color={colors.bet} /> : <View style={styles.emptyCircle} />}
                </Pressable>
              );
            })}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: '#00000066', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xxl,
    maxHeight: '85%',
  },
  grabber: {
    alignSelf: 'center',
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.separatorOpaque,
    marginBottom: spacing.sm,
  },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  title: { fontSize: font.size.title3, fontWeight: font.weight.bold, color: colors.textPrimary },
  subtitle: { fontSize: font.size.footnote, color: colors.textSecondary, marginTop: 2, marginBottom: spacing.md },
  list: { flexGrow: 0 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: 'transparent',
    paddingHorizontal: spacing.md,
    minHeight: 48,
    marginBottom: spacing.xs,
  },
  rowActive: { borderColor: colors.bet },
  rowCode: {
    minWidth: 32,
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
  },
  rowName: { flex: 1, fontSize: font.size.body, color: colors.textPrimary },
  emptyCircle: { width: 22, height: 22, borderRadius: 11, borderWidth: 1.5, borderColor: colors.separatorOpaque },
  pressed: { opacity: 0.7 },
});

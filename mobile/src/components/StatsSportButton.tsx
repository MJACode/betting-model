// Stats title sport control (Compact B, Matt 2026-10-25: "Compact B instead").
//
// The league chip row is gone from the Stats header. The sport sits in the
// title as "NFL ▾", and choosing another sport is one more tap — this sheet.
// The tap persists, the same way a SportToggle tap does (useSportFilter).

import React, { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { SPORTS, useSportFilter, type Sport } from '@/hooks/useSportFilter';
import { colors, font, radii, spacing } from '@/lib/theme';

export function StatsSportButton() {
  const { sport, setSport } = useSportFilter();
  const [open, setOpen] = useState(false);

  const pick = (next: Sport) => {
    setSport(next);
    setOpen(false);
  };

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        hitSlop={{ top: 8, bottom: 8, left: 4, right: 4 }}
        accessibilityRole="button"
        accessibilityLabel={`${sport}, sport`}
        accessibilityHint="Opens the sport list"
        style={({ pressed }) => [styles.btn, pressed && styles.pressed]}
      >
        <Text style={styles.label}>{sport}</Text>
        <Ionicons name="chevron-down" size={12} color={colors.textSecondary} />
      </Pressable>
      <Modal visible={open} animationType="slide" transparent onRequestClose={() => setOpen(false)}>
        <View style={styles.backdrop}>
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={() => setOpen(false)}
            accessibilityRole="button"
            accessibilityLabel="Close sport list"
          />
          {/* accessible={false}: an accessible Pressable groups its children into
              ONE VoiceOver element, which would leave the rows unreachable. */}
          <Pressable style={styles.sheet} onPress={() => {}} accessible={false} accessibilityViewIsModal>
            <View style={styles.grabber} />
            <View style={styles.header}>
              <Text style={styles.title}>Sport</Text>
              <Pressable
                onPress={() => setOpen(false)}
                hitSlop={12}
                accessibilityRole="button"
                accessibilityLabel="Close sport list"
              >
                <Ionicons name="close" size={24} color={colors.textSecondary} />
              </Pressable>
            </View>
            <ScrollView
              style={styles.list}
              contentContainerStyle={styles.listContent}
              bounces={false}
            >
              {SPORTS.map((s) => {
                const active = s === sport;
                return (
                  <Pressable
                    key={s}
                    onPress={() => pick(s)}
                    accessibilityRole="radio"
                    accessibilityState={{ checked: active }}
                    accessibilityLabel={s}
                    style={({ pressed }) => [styles.row, active && styles.rowActive, pressed && styles.pressed]}
                  >
                    <Text style={styles.rowName}>{s}</Text>
                    {active ? (
                      <Ionicons name="checkmark-circle" size={22} color={colors.tint} />
                    ) : (
                      <View style={styles.emptyCircle} />
                    )}
                  </Pressable>
                );
              })}
            </ScrollView>
          </Pressable>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radii.sm,
    backgroundColor: colors.bgCard,
  },
  label: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  pressed: { opacity: 0.6 },
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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  title: { fontSize: font.size.title3, fontWeight: font.weight.bold, color: colors.textPrimary },
  list: { flexGrow: 0, maxHeight: 420 },
  listContent: { gap: spacing.xs },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    paddingHorizontal: spacing.md,
    minHeight: 52,
    borderRadius: radii.md,
    backgroundColor: colors.bgCard,
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  rowActive: { borderColor: colors.tint },
  rowName: { fontSize: font.size.body, fontWeight: font.weight.semibold, color: colors.textPrimary },
  emptyCircle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
  },
});

/**
 * The one filter sheet. Picks and Stats used to ship two different modals with
 * two different mental models — Picks was Cancel/Apply over a draft copy, Stats
 * was Reset/Done editing live state. Same job, two sets of rules to learn.
 *
 * This standardizes on the live-editing model, which is what the betting apps
 * worth copying (Action Network, OddsJam, Outlier) all do: every tap applies
 * immediately and the footer button reports what you'd get — "Show 24 picks" —
 * so the result count is the feedback rather than a commit step. Nothing is
 * destructive, so there's no need to guard the edit behind Apply/Cancel.
 *
 * Header is Reset (left) / title / ✕ (right). Reset only lights up when
 * something is actually filtered.
 */

import React from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  visible: boolean;
  onClose: () => void;
  title: string;
  /** Number of rows the current filter yields — shown on the footer button. */
  resultCount: number;
  /** Singular noun for the footer, e.g. "pick" → "Show 24 picks". */
  itemNoun: string;
  /** Clears every filter. Reset is dimmed + inert when `canReset` is false. */
  onReset: () => void;
  canReset: boolean;
  children: React.ReactNode;
}

export function FilterSheet({
  visible,
  onClose,
  title,
  resultCount,
  itemNoun,
  onReset,
  canReset,
  children,
}: Props) {
  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        <View style={styles.header}>
          <Pressable onPress={onReset} disabled={!canReset} hitSlop={8}>
            <Text style={[styles.reset, !canReset && styles.resetDisabled]}>Reset</Text>
          </Pressable>
          <Text style={styles.title}>{title}</Text>
          <Pressable onPress={onClose} hitSlop={8} accessibilityLabel="Close filters">
            <Ionicons name="close" size={22} color={colors.textSecondary} />
          </Pressable>
        </View>

        <ScrollView
          contentContainerStyle={styles.body}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {children}
        </ScrollView>

        <View style={styles.footer}>
          <Pressable
            onPress={onClose}
            style={({ pressed }) => [
              styles.showBtn,
              resultCount === 0 && styles.showBtnEmpty,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.showBtnText}>
              {resultCount === 0
                ? 'No matches — adjust filters'
                : `Show ${resultCount} ${itemNoun}${resultCount === 1 ? '' : 's'}`}
            </Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

/** Labeled block inside a sheet. One card look for every group of controls. */
export function FilterSection({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {subtitle ? <Text style={styles.sectionSub}>{subtitle}</Text> : null}
      <View style={styles.sectionBody}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.bgCard,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  title: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  reset: {
    fontSize: font.size.body,
    color: colors.tint,
    fontWeight: font.weight.medium,
  },
  resetDisabled: {
    color: colors.textTertiary,
  },
  body: {
    padding: spacing.lg,
    paddingBottom: spacing.xl,
  },
  section: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  sectionTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  sectionSub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  sectionBody: {
    marginTop: spacing.md,
  },
  footer: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    backgroundColor: colors.bgCard,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  showBtn: {
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    backgroundColor: colors.tint,
  },
  showBtnEmpty: {
    backgroundColor: colors.none,
  },
  showBtnText: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  pressed: { opacity: 0.7 },
});

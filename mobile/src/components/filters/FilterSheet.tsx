/**
 * The one filter sheet. Picks and Stats used to ship two different modals with
 * two different mental models — Picks was Cancel/Apply over a draft copy, Stats
 * was Reset/Done editing live state. Same job, two sets of rules to learn.
 *
 * This standardizes on the live-editing model, which is what the betting apps
 * worth copying (Action Network, OddsJam, Outlier) all do: every tap applies
 * immediately and the footer button reports what you'd get — "Show 24 players" —
 * so the result count is the feedback rather than a commit step. Nothing is
 * destructive, so there's no need to guard the edit behind Apply/Cancel.
 *
 * Layout is a bottom sheet of COLLAPSED rows (title + the value the filter is
 * set to right now + a chevron), rather than a full-screen scroll of expanded
 * control groups. Collapsing is what makes the sheet readable: every filter the
 * screen offers fits above the fold, so "what can I filter on, and what is set
 * right now" is one glance instead of a scroll. Tapping a row expands its
 * controls in place.
 *
 * One deliberate departure from the sheets this is modeled on: they end in
 * Close + Apply, we end in a single result-count button. Apply only means
 * something when there is a draft to commit — with live editing, a second
 * button that also just closes is a decision the user has to make for no
 * reason. "Clear all" lives in the header, where those sheets put it.
 */

import React, { useEffect, useRef, useState } from 'react';
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
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
  /** Clears every filter. "Clear all" is dimmed + inert when `canReset` is false. */
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
  /**
   * A Modal keeps its children mounted while hidden, so without this the rows
   * would remember which ones were expanded last time — and `defaultOpen` would
   * never fire, because it is only read on mount. Bumping a key each time the
   * sheet OPENS (never on close, so nothing collapses mid-dismiss) remounts the
   * rows, so the sheet always presents as the compact all-collapsed list.
   */
  const [generation, setGeneration] = useState(0);
  const wasVisible = useRef(visible);
  useEffect(() => {
    if (visible && !wasVisible.current) setGeneration((g) => g + 1);
    wasVisible.current = visible;
  }, [visible]);

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      {/* The sheet is anchored to the bottom, so a focused search box or number
          field would otherwise sit under the keyboard. The avoider is the OUTER
          flex:1 element on purpose — the sheet's maxHeight is a percentage, and
          that only resolves against a parent with a definite height. */}
      <KeyboardAvoidingView
        style={styles.avoider}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        {/* Backdrop tap closes. The sheet applies live, so dismissing keeps
            whatever the user set rather than discarding it. */}
        <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="Close filters">
          <Pressable style={styles.sheet} onPress={() => {}}>
            <View style={styles.grabber} />

            <View style={styles.header}>
              <Text style={styles.title}>{title}</Text>
              <Pressable onPress={onReset} disabled={!canReset} hitSlop={8}>
                <Text style={[styles.reset, !canReset && styles.resetDisabled]}>Clear all</Text>
              </Pressable>
            </View>

            <ScrollView
              contentContainerStyle={styles.body}
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}
              bounces={false}
            >
              <View key={generation}>{children}</View>
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
          </Pressable>
        </Pressable>
      </KeyboardAvoidingView>
    </Modal>
  );
}

/**
 * One row of the sheet. Pass `summary` to make it collapsible: the row then
 * reads as `Sort by            Hit rate  ⌄` until it is tapped.
 *
 * `summary` is what the filter is set to right now, in the same words the row
 * uses once open — that is the whole reason a collapsed row is still useful.
 * A section with no `summary` renders expanded, as it always did.
 */
export function FilterSection({
  title,
  subtitle,
  summary,
  defaultOpen = false,
  children,
}: {
  title: string;
  subtitle?: string;
  /** Current value, shown on the collapsed row. Presence makes the row collapsible. */
  summary?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const collapsible = summary !== undefined;
  const [open, setOpen] = useState(defaultOpen);
  const expanded = !collapsible || open;

  if (!collapsible) {
    return (
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {subtitle ? <Text style={styles.sectionSub}>{subtitle}</Text> : null}
        <View style={styles.sectionBody}>{children}</View>
      </View>
    );
  }

  return (
    <View style={styles.section}>
      <Pressable
        onPress={() => setOpen((o) => !o)}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      >
        <Text style={styles.sectionTitle}>{title}</Text>
        <View style={styles.rowRight}>
          {/* Truncates rather than wrapping, so the collapsed rows keep a
              uniform height and read as one clean column. */}
          <Text style={styles.rowValue} numberOfLines={1}>
            {summary}
          </Text>
          <Ionicons
            name={expanded ? 'chevron-up' : 'chevron-down'}
            size={18}
            color={colors.textTertiary}
          />
        </View>
      </Pressable>

      {expanded ? (
        <View style={styles.sectionBody}>
          {subtitle ? <Text style={styles.sectionSubOpen}>{subtitle}</Text> : null}
          {children}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  avoider: { flex: 1 },
  backdrop: {
    flex: 1,
    backgroundColor: '#00000066',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl,
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
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  title: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
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
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  section: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    marginBottom: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 32,
  },
  rowRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    flexShrink: 1,
    marginLeft: spacing.md,
  },
  rowValue: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    flexShrink: 1,
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
  sectionSubOpen: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  sectionBody: {
    marginTop: spacing.md,
  },
  footer: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    backgroundColor: colors.bg,
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

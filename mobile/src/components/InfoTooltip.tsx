import React, { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  title: string;
  body: string;
  /** Accessibility label for the info icon. Defaults to "More info". */
  accessibilityLabel?: string;
  /**
   * One-line summary rendered next to the icon, making the whole row the tap
   * target. Without it the trigger is the bare ⓘ.
   *
   * This is how a note that was five lines of body copy becomes one: the claim
   * stays on the screen, the explanation moves behind the tap. A summary that
   * does not survive alone belongs in `body` — the reader who never taps must
   * still get the point (Matt, 2026-09-08).
   */
  label?: string;
  /**
   * 'warn' renders the summary as a tinted warning panel with a warning glyph,
   * for a summary the reader must not scroll past — a negative-EV slip. It also
   * drops the line cap, because that summary is the whole warning for anyone who
   * never taps through. Colour alone is not the signal: the glyph and the
   * wording carry it too.
   */
  tone?: 'info' | 'warn';
}

/**
 * Small info (ⓘ) icon — or, with `label`, a one-line summary row — that opens a
 * centered tooltip modal with the full copy. Tap the backdrop or the "Got it"
 * button to dismiss.
 */
/** The centered explanation InfoTooltip opens. One copy, so the matchup cell
 *  can open the same sheet without a second header icon. */
export function InfoSheet({
  visible,
  title,
  body,
  onClose,
  warn = false,
}: {
  visible: boolean;
  title: string;
  body: string;
  onClose: () => void;
  warn?: boolean;
}) {
  const accent = warn ? colors.gradeBad : colors.tint;
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel={`Close ${title}`}
        />
        <Pressable
          style={[styles.card, { marginTop: insets.top, marginBottom: insets.bottom }]}
          onPress={() => {}}
          accessible={false}
          accessibilityViewIsModal
        >
          <View style={styles.cardHeader}>
            <Ionicons
              name={warn ? 'warning' : 'information-circle'}
              size={22}
              color={accent}
            />
            <Text style={styles.cardTitle}>{title}</Text>
          </View>
          <ScrollView style={styles.sheetScroll} contentContainerStyle={styles.sheetContent} bounces={false}>
            <Text style={styles.cardBody}>{body}</Text>
          </ScrollView>
          <Pressable
            hitSlop={{ top: 4, bottom: 4, left: 0, right: 0 }}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Got it"
            style={({ pressed }) => [styles.dismissBtn, pressed && styles.pressed]}
          >
            <Text style={styles.dismissText}>Got it</Text>
          </Pressable>
        </Pressable>
      </View>
    </Modal>
  );
}

export function InfoTooltip({
  title,
  body,
  accessibilityLabel,
  label,
  tone = 'info',
}: Props) {
  const [open, setOpen] = useState(false);
  const warn = tone === 'warn';
  const accent = warn ? colors.gradeBad : colors.tint;

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        // Bare icon: 20pt glyph + 12 + 12 = 44pt (audit M18; 10 reached 40).
        hitSlop={12}
        accessibilityRole="button"
        // Voice Control matches the label against what is on screen, and the
        // visible word is "Details" — "More info" made "tap Details" miss.
        accessibilityLabel={accessibilityLabel ?? (label ? `${label}. Details` : 'More info')}
        accessibilityHint={label ? 'Opens the full explanation' : undefined}
        style={({ pressed }) => [
          label ? styles.summaryBtn : styles.iconBtn,
          warn && styles.summaryBtnWarn,
          pressed && styles.pressed,
        ]}
      >
        {label ? (
          <>
            <Ionicons
              name={warn ? 'warning' : 'information-circle-outline'}
              size={14}
              color={warn ? colors.gradeBad : colors.textTertiary}
            />
            {/* NO line cap and no fixed lineHeight on the warn tone (UX review,
                2026-09-08). This one sentence is the whole warning for a reader
                who never taps Details, and a 2-line cap over a 16pt line box
                clipped it at default Dynamic Type and truncated it above —
                "Negative EV — straight bets are be…". It is allowed to wrap;
                it is not allowed to disappear. The info tone still caps, where
                truncating a pricing footnote costs nothing. */}
            <Text
              numberOfLines={warn ? undefined : 2}
              style={[
                styles.summaryText,
                warn ? styles.summaryTextWarn : styles.summaryTextInfo,
              ]}
            >
              {label}
            </Text>
            {/* A trailing word, not a second glyph: "there is more behind this"
                is a thing to read, and it doubles the row's tap width. */}
            <Text style={[styles.summaryMore, { color: accent }]}>Details</Text>
          </>
        ) : (
          <Ionicons name="information-circle-outline" size={20} color={colors.tint} />
        )}
      </Pressable>
      <InfoSheet
        visible={open}
        title={title}
        body={body}
        warn={warn}
        onClose={() => setOpen(false)}
      />
    </>
  );
}

const styles = StyleSheet.create({
  iconBtn: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  summaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    // Row height, not padding: the bare icon sits inline in a header, but a
    // summary row is the whole width and needs a 44pt-class target.
    paddingVertical: spacing.sm,
  },
  // A warning on a tinted panel, not a footnote in red. The five-line paragraph
  // this replaced was loud by accident; one 12pt sub-AA line would have been
  // quiet by design, and this is now the ONLY on-card rendering of it.
  summaryBtnWarn: {
    backgroundColor: colors.avoidSoft,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    marginTop: spacing.sm,
  },
  summaryText: {
    flex: 1,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  // The line box lives here, not on summaryText: `lineHeight: undefined` in a
  // later style object does NOT unset an earlier one — RN's flattener skips
  // undefined — so the warn tone has to opt IN to a box rather than out of one.
  summaryTextInfo: {
    lineHeight: 16,
  },
  // colors.avoid is 3.55:1 on bgCard — theme.ts measures it, and it is under
  // the 4.5:1 AA floor. gradeBad is the same red taken dark enough to read
  // (10.72:1), already the app's answer to this exact problem on the board's
  // ramp. Colour is not the signal either way: the glyph and the wording are.
  summaryTextWarn: {
    color: colors.gradeBad,
    fontSize: font.size.footnote,
    fontWeight: font.weight.medium,
  },
  summaryMore: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
  },
  pressed: { opacity: 0.65 },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.4)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  card: {
    width: '100%',
    maxWidth: 360,
    maxHeight: '80%',
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
  },
  sheetScroll: { flexGrow: 0, flexShrink: 1 },
  sheetContent: { paddingBottom: spacing.xs },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  cardTitle: {
    flex: 1,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  cardBody: {
    fontSize: font.size.body,
    lineHeight: 21,
    color: colors.textSecondary,
  },
  dismissBtn: {
    marginTop: spacing.lg,
    alignItems: 'center',
    paddingVertical: spacing.sm + 2,
    borderRadius: radii.sm,
    backgroundColor: colors.tint,
  },
  dismissText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
});

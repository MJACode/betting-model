import React, { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
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
   * 'warn' paints the trigger in the AVOID colour with a warning glyph, for a
   * summary the reader must not scroll past — a negative-EV slip. Colour alone
   * is not the signal: the glyph and the wording carry it too.
   */
  tone?: 'info' | 'warn';
}

/**
 * Small info (ⓘ) icon — or, with `label`, a one-line summary row — that opens a
 * centered tooltip modal with the full copy. Tap the backdrop or the "Got it"
 * button to dismiss.
 */
export function InfoTooltip({
  title,
  body,
  accessibilityLabel,
  label,
  tone = 'info',
}: Props) {
  const [open, setOpen] = useState(false);
  const warn = tone === 'warn';
  const accent = warn ? colors.avoid : colors.tint;

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        hitSlop={10}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel ?? (label ? `${label}. More info` : 'More info')}
        style={({ pressed }) => [
          label ? styles.summaryBtn : styles.iconBtn,
          pressed && styles.pressed,
        ]}
      >
        {label ? (
          <>
            <Ionicons
              name={warn ? 'warning' : 'information-circle-outline'}
              size={14}
              color={warn ? colors.avoid : colors.textTertiary}
            />
            <Text numberOfLines={2} style={[styles.summaryText, warn && styles.summaryTextWarn]}>
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
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          {/* Inner Pressable swallows taps so touching the card doesn't dismiss. */}
          <Pressable style={styles.card} onPress={() => {}}>
            <View style={styles.cardHeader}>
              <Ionicons
                name={warn ? 'warning' : 'information-circle'}
                size={22}
                color={accent}
              />
              <Text style={styles.cardTitle}>{title}</Text>
            </View>
            <Text style={styles.cardBody}>{body}</Text>
            <Pressable
              onPress={() => setOpen(false)}
              style={({ pressed }) => [styles.dismissBtn, pressed && styles.pressed]}
            >
              <Text style={styles.dismissText}>Got it</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
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
  summaryText: {
    flex: 1,
    fontSize: font.size.caption,
    lineHeight: 16,
    color: colors.textTertiary,
  },
  summaryTextWarn: {
    color: colors.avoid,
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
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
  },
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

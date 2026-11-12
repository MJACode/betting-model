import React, { useState } from 'react';
import { AccessibilityInfo, ActivityIndicator, Keyboard, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { InfoSheet, InfoTooltip } from '@/components/InfoTooltip';
import { getDeviceId } from '@/hooks/useDeviceId';
import { refreshSgpHaircuts } from '@/hooks/useSgpHaircuts';
import { americanToDecimal, formatAmerican } from '@/lib/format';
import { bookName } from '@/lib/markets';
import { decimalToAmerican, type ParlayLeg } from '@/lib/parlay';
import { logSgpPrice } from '@/lib/queries';
import { sgpShapeFor } from '@/lib/parlayCorrelation';
import { enteredPriceIsPlausible, parseEnteredAmerican } from '@/lib/sgpPricing';
import { APP_VERSION } from '@/lib/socialLinks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Enter <book>'s slip price" — one compact row inside that book's hand-off
 * sheet, shown when the tile is a same-game estimate (Matt, 2026-11-06).
 *
 * It used to be a yellow box on the Betslip itself, with its own book chips and
 * a paragraph of explanation. Matt, 2026-11-09: the box took too much room, and
 * the out-of-range warning (a two-line red sentence) more. So the entry moved
 * to where the member already is when they read the book's price — the sheet
 * the book's tile opens — and the warning is a ⚠ next to the field that opens
 * the sentence as a tooltip. The explanation lives in the row's ⓘ.
 *
 * An entry does two things: this slip shows the book's real price at that
 * book (the tile, and the headline when it is DraftKings), and the price is
 * stored (log_sgp_price) so each book's cut is fitted from real quotes.
 */
export function SgpPriceEntry({
  book,
  multipliedDecimal,
  legs,
  sgpGroups,
  entered,
  onEntered,
  onCleared,
}: {
  book: string;
  /** This book's legs multiplied out — what an entered price is checked against. */
  multipliedDecimal: number;
  legs: ParlayLeg[];
  sgpGroups: number;
  /** The price already typed for this book, if any. */
  entered?: number;
  onEntered: (book: string, american: number) => void;
  /** Remove a typed price (a typo that passed the range check). */
  onCleared: (book: string) => void;
}) {
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);
  const [rangeNote, setRangeNote] = useState<string | null>(null);
  const [noteOpen, setNoteOpen] = useState(false);

  const american = parseEnteredAmerican(text);
  const name = bookName(book);

  // Confirmation stays in the sheet: the app-root toast draws behind an open
  // Modal on iOS (UX review, 2026-11-09).
  const save = async () => {
    if (american == null) return;
    Keyboard.dismiss();
    if (!enteredPriceIsPlausible(americanToDecimal(american), multipliedDecimal)) {
      // The check compares against the legs multiplied out, so the message
      // names that number (PR #1198 review L3).
      const multipliedAmerican = decimalToAmerican(multipliedDecimal);
      setRangeNote(`That’s far from the legs multiplied out (${formatAmerican(multipliedAmerican)}). Check the number on ${name}’s slip.`);
      AccessibilityInfo.announceForAccessibility(`Price looks off. Check the number on ${name}’s slip.`);
      return;
    }
    const shape = sgpShapeFor(legs);
    setSaving(true);
    setRangeNote(null);
    // The price shows on this slip whether or not the save reaches the server.
    onEntered(book, american);
    AccessibilityInfo.announceForAccessibility(`Using your ${name} price, ${formatAmerican(american)}`);
    try {
      await logSgpPrice({
        deviceId: await getDeviceId(),
        book,
        bookAmerican: american,
        multipliedDecimal,
        sgpGroups,
        // The same shape the tile was estimated with, so the server fits the
        // cut per extra leg after the correlation lift (lib/sgpPricing.ts).
        extraLegs: shape.extraLegs,
        corrLift: shape.lift,
        legCount: legs.length,
        legs: legs.map((l) => ({ label: l.label, gameId: l.gameId ?? null })),
        appVersion: APP_VERSION ?? null,
      });
      refreshSgpHaircuts();
    } catch {
      // Not shown as a failure: the member's price is on the slip either way;
      // only our calibration missed one entry.
    } finally {
      setSaving(false);
      setText('');
    }
  };

  return (
    <View style={styles.wrap}>
      <View style={styles.labelRow}>
        {entered != null ? <Ionicons name="checkmark-circle" size={16} color={colors.tint} /> : null}
        <Text style={styles.label}>
          {entered != null ? `Using your ${name} price, ${formatAmerican(entered)}` : `Price on ${name}’s slip`}
        </Text>
        <InfoTooltip
          title="Same-game price"
          body={`Two or more legs share a game. Books price those legs together, and legs that tend to hit together pay less than the legs multiplied out, so the ${name} tile shows our estimate.\n\nEnter the price ${name}’s slip shows and this slip uses it. It also helps us price same-game slips at ${name} for everyone.`}
          accessibilityLabel="About same-game prices"
        />
      </View>
      <View style={styles.inputRow}>
        <TextInput
          accessibilityLabel={`Price on ${name}’s slip, American odds`}
          style={[styles.input, rangeNote != null && styles.inputWarn]}
          value={text}
          onChangeText={(t) => {
            setText(t);
            setRangeNote(null);
          }}
          placeholder="e.g. +4254"
          placeholderTextColor={colors.textTertiary}
          keyboardType="numbers-and-punctuation"
          returnKeyType="done"
          onSubmitEditing={save}
        />
        {rangeNote ? (
          <Pressable
            onPress={() => {
              Keyboard.dismiss();
              setNoteOpen(true);
            }}
            accessibilityRole="button"
            accessibilityLabel="Price looks off. Details"
            style={({ pressed }) => [styles.warnBtn, pressed && styles.pressed]}
          >
            <Ionicons name="warning" size={22} color={colors.gradeBad} />
          </Pressable>
        ) : null}
        <Pressable
          onPress={save}
          disabled={american == null || saving}
          accessibilityRole="button"
          accessibilityLabel="Use this price"
          accessibilityState={{ disabled: american == null || saving }}
          style={({ pressed }) => [
            styles.save,
            (american == null || saving) && styles.saveDisabled,
            pressed && styles.pressed,
          ]}
        >
          {saving ? <ActivityIndicator color={colors.textInverse} /> : <Text style={styles.saveText}>Use</Text>}
        </Pressable>
      </View>
      {entered != null ? (
        <Pressable
          onPress={() => {
            onCleared(book);
            AccessibilityInfo.announceForAccessibility(`Back to the estimate at ${name}`);
          }}
          accessibilityRole="button"
          accessibilityLabel={`Clear your ${name} price, ${formatAmerican(entered)}`}
          hitSlop={{ top: 10, bottom: 10, left: 0, right: 0 }}
          style={({ pressed }) => [styles.clear, pressed && styles.pressed]}
        >
          <Text style={styles.clearText}>Clear your price</Text>
        </Pressable>
      ) : null}
      <InfoSheet
        visible={noteOpen}
        title="Check this price"
        body={rangeNote ?? undefined}
        warn
        onClose={() => setNoteOpen(false)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: spacing.md },
  labelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  label: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  input: {
    flex: 1,
    minHeight: 44,
    backgroundColor: colors.bgCard,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  inputWarn: {
    borderWidth: 1,
    borderColor: colors.gradeBad,
  },
  warnBtn: {
    minHeight: 44,
    minWidth: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  save: {
    minHeight: 44,
    minWidth: 64,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.sm,
    backgroundColor: colors.tint,
  },
  saveDisabled: { opacity: 0.4 },
  saveText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  pressed: { opacity: 0.7 },
  clear: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
  clearText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
});

import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { getDeviceId } from '@/hooks/useDeviceId';
import { refreshSgpHaircuts } from '@/hooks/useSgpHaircuts';
import { americanToDecimal, formatAmerican } from '@/lib/format';
import { bookLabel, bookName, BETTABLE_BOOKS, MODEL_BOOK } from '@/lib/markets';
import { priceBooksForParlay, type ParlayLeg } from '@/lib/parlay';
import { logSgpPrice } from '@/lib/queries';
import { enteredPriceIsPlausible, parseEnteredAmerican } from '@/lib/sgpPricing';
import { APP_VERSION } from '@/lib/socialLinks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Same-game legs — this price is an estimate." Shown on the Betslip when 2+
 * legs share a game (Matt, 2026-11-06). A book prices those legs together, as
 * a same-game parlay, and no feed we buy publishes that price — so the slip
 * shows an estimate (lib/sgpPricing.ts) and lets the member type in the price
 * the book's own slip shows.
 *
 * An entry does two things: this slip shows the book's real price at that
 * book (the tile, and the headline when it is DraftKings), and the price is
 * stored (log_sgp_price) so each book's cut is fitted from real quotes.
 */
export function SgpPriceEntry({
  legs,
  sgpGroups,
  entered,
  onEntered,
}: {
  legs: ParlayLeg[];
  sgpGroups: number;
  entered: Readonly<Record<string, number>>;
  onEntered: (book: string, american: number) => void;
}) {
  const [open, setOpen] = useState(false);
  // Only books that price every leg have a multiplied price to compare with.
  const books = useMemo(
    () =>
      priceBooksForParlay(legs, 1, BETTABLE_BOOKS)
        .filter((q) => q.multipliedDecimal != null)
        .sort((a, b) => (a.book === MODEL_BOOK ? -1 : b.book === MODEL_BOOK ? 1 : 0)),
    [legs],
  );
  const [book, setBook] = useState<string>(MODEL_BOOK);
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const quote = books.find((q) => q.book === book) ?? books[0];
  const american = parseEnteredAmerican(text);
  const plausible =
    american != null && quote?.multipliedDecimal != null
      ? enteredPriceIsPlausible(americanToDecimal(american), quote.multipliedDecimal)
      : false;

  if (sgpGroups <= 0 || books.length === 0) return null;

  const enteredBooks = Object.keys(entered);

  const save = async () => {
    if (american == null || quote?.multipliedDecimal == null) return;
    if (!plausible) {
      setError(`That’s far from ${formatAmerican(quote.americanOdds ?? 0)} — check the number on ${bookName(quote.book)}’s slip.`);
      return;
    }
    setSaving(true);
    setError(null);
    // The price shows on this slip whether or not the save reaches the server.
    onEntered(quote.book, american);
    try {
      await logSgpPrice({
        deviceId: await getDeviceId(),
        book: quote.book,
        bookAmerican: american,
        multipliedDecimal: quote.multipliedDecimal,
        sgpGroups,
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
      setOpen(false);
    }
  };

  return (
    <View style={styles.wrap}>
      <Pressable
        onPress={() => setOpen((o) => !o)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel="Same-game legs, the price is an estimate. Enter the price your book shows."
        hitSlop={{ top: 6, bottom: 6, left: 0, right: 0 }}
        style={styles.header}
      >
        <Ionicons name="git-merge-outline" size={16} color={colors.medInk} />
        <View style={styles.headerText}>
          <Text style={styles.title}>
            Estimated price · {sgpGroups === 1 ? 'same-game legs' : `${sgpGroups} same-game groups`}
          </Text>
          <Text style={styles.body}>
            Books price legs from the same game together, for less than the legs multiplied out.
            {enteredBooks.length > 0
              ? ` Using your price at ${enteredBooks.map(bookName).join(', ')}.`
              : ' Tap to enter the price your book shows.'}
          </Text>
        </View>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textTertiary} />
      </Pressable>

      {open ? (
        <View style={styles.form}>
          <View style={styles.chips}>
            {books.map((q) => {
              const on = q.book === quote?.book;
              return (
                <Pressable
                  key={q.book}
                  onPress={() => {
                    setBook(q.book);
                    setError(null);
                  }}
                  accessibilityRole="button"
                  accessibilityState={{ selected: on }}
                  accessibilityLabel={bookName(q.book)}
                  style={[styles.chip, on && styles.chipOn]}
                >
                  <Text style={[styles.chipText, on && styles.chipTextOn]}>{bookLabel(q.book)}</Text>
                </Pressable>
              );
            })}
          </View>
          <View style={styles.inputRow}>
            <TextInput
              accessibilityLabel={`Price on ${bookName(quote?.book ?? MODEL_BOOK)}’s slip, American odds`}
              style={styles.input}
              value={text}
              onChangeText={(t) => {
                setText(t);
                setError(null);
              }}
              placeholder={`${bookLabel(quote?.book ?? MODEL_BOOK)} slip price, e.g. +4254`}
              placeholderTextColor={colors.textTertiary}
              keyboardType="numbers-and-punctuation"
              returnKeyType="done"
              onSubmitEditing={save}
            />
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
              {saving ? (
                <ActivityIndicator color={colors.textInverse} />
              ) : (
                <Text style={styles.saveText}>Use</Text>
              )}
            </Pressable>
          </View>
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <Text style={styles.hint}>
            Your price shows on this slip and helps us price same-game slips at {bookName(quote?.book ?? MODEL_BOOK)} for everyone.
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginTop: spacing.sm,
    padding: spacing.md,
    borderRadius: radii.md,
    backgroundColor: colors.medSoft,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  headerText: { flex: 1 },
  title: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.medInk,
  },
  body: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  form: { marginTop: spacing.md },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  chip: {
    minHeight: 32,
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
  },
  chipOn: { backgroundColor: colors.tint },
  chipText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  chipTextOn: { color: colors.textInverse },
  inputRow: {
    flexDirection: 'row',
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
  error: {
    fontSize: font.size.footnote,
    color: colors.avoidInk,
    marginTop: spacing.sm,
  },
  hint: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
});

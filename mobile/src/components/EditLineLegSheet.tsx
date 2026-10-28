import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { formatAmerican, MINUS } from '@/lib/format';
import {
  lineLegKey,
  lineLegLabel,
  lineOptionsFromRows,
  withLine,
  type LineOption,
  type LineSide,
  type PropLineLegSpec,
} from '@/lib/lineLegs';
import { bookLabelShort } from '@/lib/markets';
import { fetchPropLineRows } from '@/lib/queries';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Edit a betslip leg's line — the pencil on a "Your line" leg.
 *
 * Matt, 2026-10-28: "When you add players to the parlay feature, allow the
 * user to edit a bet. So example if I select 10 points for someone I should be
 * able to edit and change it to 15." The sheet lists every number a bettable
 * book posts for that player and stat (main and alternate lines), on the side
 * chosen at the top, with the best price for each. Picking one and tapping
 * Update swaps the leg in place; the slip then re-prices it like any line leg.
 *
 * Model picks are not editable here (Matt, same day): a pick is a bet of
 * record at its own line (CLAUDE.md §1c). Only the user's own line legs are.
 */
export function EditLineLegSheet({
  spec,
  onClose,
  onSave,
}: {
  /** The leg being edited; null closes the sheet. */
  spec: PropLineLegSpec | null;
  onClose: () => void;
  /** Return false when the edit could not be applied (e.g. that bet is
   *  already another leg); the sheet then stays open with a note. */
  onSave: (next: PropLineLegSpec) => boolean;
}) {
  const [options, setOptions] = useState<LineOption[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [side, setSide] = useState<LineSide>('over');
  const [line, setLine] = useState<number | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const specKey = spec ? lineLegKey(spec) : null;
  useEffect(() => {
    if (!spec) return;
    setSide(spec.side);
    setLine(spec.line);
    setNote(null);
    setOptions(null);
    setError(null);
    let alive = true;
    fetchPropLineRows(spec.game_id, spec.market, spec.player_name)
      .then((rows) => {
        if (alive) setOptions(lineOptionsFromRows(spec, rows));
      })
      .catch(() => {
        if (alive) setError('Could not load the lines. Check your connection and try again.');
      });
    return () => {
      alive = false;
    };
    // The spec's identity, not its object, decides a reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [specKey, nonce]);

  const rows = useMemo(
    () => (options ?? []).filter((o) => (side === 'over' ? o.over : o.under) != null),
    [options, side],
  );
  const unchanged = spec != null && line === spec.line && side === spec.side;
  const canSave = spec != null && line != null && !unchanged && rows.some((o) => o.line === line);

  const save = () => {
    if (!spec || line == null || !canSave) return;
    const ok = onSave(withLine(spec, line, side));
    if (ok) onClose();
    else setNote('That bet is already on your betslip.');
  };

  return (
    <Modal visible={spec != null} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel="Close edit leg"
        />
        <Pressable style={styles.sheet} onPress={() => {}} accessible={false} accessibilityViewIsModal>
          <View style={styles.grabber} />
          <View style={styles.header}>
            <View style={styles.headerBody}>
              <Text style={styles.eyebrow}>Edit leg</Text>
              <Text style={styles.title} numberOfLines={2}>
                {spec ? lineLegLabel(spec) : ''}
              </Text>
            </View>
            <Pressable onPress={onClose} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close edit leg">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>
          <Text style={styles.subtitle}>Pick a new line. Only lines a sportsbook posts are listed.</Text>

          <View style={styles.segment} accessibilityRole="tablist">
            {(['over', 'under'] as const).map((s) => {
              const active = side === s;
              return (
                <Pressable
                  key={s}
                  onPress={() => {
                    setSide(s);
                    setNote(null);
                  }}
                  accessibilityRole="tab"
                  accessibilityState={{ selected: active }}
                  style={({ pressed }) => [styles.segBtn, active && styles.segBtnActive, pressed && styles.pressed]}
                >
                  <Text style={[styles.segText, active && styles.segTextActive]}>{s === 'over' ? 'Over' : 'Under'}</Text>
                </Pressable>
              );
            })}
          </View>

          {error ? (
            <View style={styles.state}>
              <Text style={styles.stateText}>{error}</Text>
              <Pressable
                onPress={() => setNonce((n) => n + 1)}
                accessibilityRole="button"
                accessibilityLabel="Try again"
                style={({ pressed }) => [styles.retry, pressed && styles.pressed]}
              >
                <Text style={styles.retryText}>Try again</Text>
              </Pressable>
            </View>
          ) : options == null ? (
            <View style={styles.state}>
              <ActivityIndicator />
            </View>
          ) : rows.length === 0 ? (
            <View style={styles.state}>
              <Text style={styles.stateText}>
                No sportsbook posts the {side === 'over' ? 'Over' : 'Under'} for this player right now.
              </Text>
            </View>
          ) : (
            <ScrollView style={styles.list} bounces={false}>
              <View style={styles.listCard}>
                {rows.map((o, i) => {
                  const p = (side === 'over' ? o.over : o.under)!;
                  const selected = line === o.line;
                  const isCurrent = spec != null && o.line === spec.line && side === spec.side;
                  const word = side === 'over' ? 'Over' : 'Under';
                  const hint = countHint(o.line, side);
                  const priceText = formatAmerican(p.price).replace(/-/g, MINUS);
                  return (
                    <Pressable
                      key={o.line}
                      onPress={() => {
                        setLine(o.line);
                        setNote(null);
                      }}
                      accessibilityRole="radio"
                      accessibilityState={{ selected }}
                      accessibilityLabel={`${word} ${o.line}${hint ? `, ${hint}` : ''}, ${priceText} at ${bookLabelShort(p.book)}${isCurrent ? ', current line' : ''}`}
                      style={({ pressed }) => [
                        styles.row,
                        i > 0 && styles.rowDivider,
                        selected && styles.rowSelected,
                        pressed && styles.pressed,
                      ]}
                    >
                      <Ionicons
                        name={selected ? 'radio-button-on' : 'radio-button-off'}
                        size={20}
                        color={selected ? colors.tint : colors.textTertiary}
                      />
                      <View style={styles.rowBody}>
                        <Text style={styles.rowLine}>
                          {word} {o.line}
                          {isCurrent ? <Text style={styles.current}>  · current</Text> : null}
                        </Text>
                        {hint ? <Text style={styles.rowHint}>{hint}</Text> : null}
                      </View>
                      <Text style={styles.rowBook}>{bookLabelShort(p.book)}</Text>
                      <Text style={styles.rowPrice}>{priceText}</Text>
                    </Pressable>
                  );
                })}
              </View>
            </ScrollView>
          )}

          {note ? <Text style={styles.note}>{note}</Text> : null}

          <Pressable
            onPress={save}
            disabled={!canSave}
            accessibilityRole="button"
            accessibilityLabel="Update leg"
            accessibilityState={{ disabled: !canSave }}
            style={({ pressed }) => [styles.primary, !canSave && styles.primaryDisabled, pressed && styles.pressed]}
          >
            <Ionicons name="checkmark" size={20} color={colors.textInverse} />
            <Text style={styles.primaryText}>Update leg</Text>
          </Pressable>
          <Pressable
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Cancel"
            style={({ pressed }) => [styles.secondary, pressed && styles.pressed]}
          >
            <Text style={styles.secondaryText}>Cancel</Text>
          </Pressable>
        </Pressable>
      </View>
    </Modal>
  );
}

/** "15 or more" for Over 14.5, "14 or fewer" for Under 14.5. Whole-number
 *  lines (a push is possible) get no hint. */
export function countHint(line: number, side: LineSide): string | null {
  if (!Number.isFinite(line) || Number.isInteger(line) || Math.abs((line % 1) - 0.5) > 1e-9) return null;
  return side === 'over' ? `${Math.ceil(line)} or more` : `${Math.floor(line)} or fewer`;
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: '#00000066',
    justifyContent: 'flex-end',
  },
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
    alignItems: 'flex-start',
    marginBottom: spacing.sm,
  },
  headerBody: {
    flex: 1,
    paddingRight: spacing.md,
  },
  eyebrow: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  title: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  segment: {
    flexDirection: 'row',
    backgroundColor: colors.bgCard,
    borderRadius: radii.pill,
    padding: 3,
    marginBottom: spacing.md,
  },
  segBtn: {
    flex: 1,
    minHeight: 40,
    borderRadius: radii.pill,
    alignItems: 'center',
    justifyContent: 'center',
  },
  segBtnActive: {
    backgroundColor: colors.tint,
  },
  segText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  segTextActive: {
    color: colors.textInverse,
  },
  state: {
    paddingVertical: spacing.xl,
    alignItems: 'center',
    gap: spacing.sm,
  },
  stateText: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  retry: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    justifyContent: 'center',
  },
  retryText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  list: {
    flexGrow: 0,
  },
  listCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
    minHeight: 52,
  },
  rowDivider: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  rowSelected: {
    // The radio carries the state; no fill, so the price column stays legible.
  },
  rowBody: {
    flex: 1,
  },
  rowLine: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  current: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.regular,
    color: colors.textSecondary,
  },
  rowHint: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 1,
  },
  rowBook: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
  },
  rowPrice: {
    minWidth: 52,
    textAlign: 'right',
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  note: {
    marginTop: spacing.sm,
    fontSize: font.size.footnote,
    color: colors.avoid,
  },
  primary: {
    marginTop: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    backgroundColor: colors.tint,
    borderRadius: radii.pill,
    minHeight: 48,
    paddingHorizontal: spacing.lg,
  },
  primaryDisabled: {
    opacity: 0.4,
  },
  primaryText: {
    fontSize: font.size.body,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
  },
  secondary: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
    marginTop: spacing.xs,
  },
  secondaryText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  pressed: {
    opacity: 0.6,
  },
});

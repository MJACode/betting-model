import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { formatAmerican, MINUS } from '@/lib/format';
import {
  canSaveEdit,
  editScrollTarget,
  gameEditMenu,
  GAME_OFF_BOARD,
  initialEditSegment,
  isGameSpec,
  lineLegKey,
  lineLegLabel,
  propEditMenu,
  type EditMenu,
  type LineLegSpec,
} from '@/lib/lineLegs';
import { SegmentTabs } from '@/components/GroupTabs';
import { bookLabelShort } from '@/lib/markets';
import { fetchGameLineRows, fetchPropLineRows } from '@/lib/queries';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Edit a betslip leg — the pencil on a "Your line" leg.
 *
 * Matt, 2026-10-28: "When you add players to the parlay feature, allow the
 * user to edit a bet. So example if I select 10 points for someone I should be
 * able to edit and change it to 15." And 2026-10-29: game lines too.
 *
 * A prop lists every number a bettable book posts for that player and stat
 * (main and alternate lines), Over or Under. A game line lists the other team
 * (moneyline), each team at every number a book hangs (spread), or Over/Under
 * at every total a book hangs (total). Each row is priced the way the leg will
 * be (DraftKings when it posts the side, else the best book —
 * lineLegs.anchorRow). Picking one and tapping Update swaps the leg in place;
 * the slip then re-prices it like any line leg.
 *
 * Model picks are not editable here (Matt, 2026-10-28): a pick is a bet of
 * record at its own line (CLAUDE.md §1c). Only the user's own line legs are.
 */
export function EditLineLegSheet({
  spec,
  onClose,
  onSave,
}: {
  /** The leg being edited; null closes the sheet. */
  spec: LineLegSpec | null;
  onClose: () => void;
  /** 'ok' closes the sheet. 'duplicate' (that bet is already a leg) and
   *  'sidelined' (the player is ruled out) keep it open with a note. */
  onSave: (next: LineLegSpec) => Promise<'ok' | 'duplicate' | 'sidelined'>;
}) {
  const [menu, setMenu] = useState<EditMenu | null>(null);
  const [failed, setFailed] = useState(false);
  const [segment, setSegment] = useState<string>('');
  const [picked, setPicked] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const specKey = spec ? lineLegKey(spec) : null;
  useEffect(() => {
    if (!spec) return;
    setSegment(isGameSpec(spec) ? (spec.market === 'totals' ? spec.side ?? 'over' : spec.team) : spec.side);
    setPicked(lineLegKey(spec));
    setNote(null);
    setMenu(null);
    setFailed(false);
    let alive = true;
    const load: Promise<EditMenu> = isGameSpec(spec)
      ? fetchGameLineRows(spec.game_id, spec.market).then((rows) => gameEditMenu(spec, rows))
      : fetchPropLineRows(spec.game_id, spec.market, spec.player_name).then((rows) => propEditMenu(spec, rows));
    load
      .then((m) => {
        if (!alive) return;
        setMenu(m);
        // A collapsed menu has one segment ('all'), not the leg's own side.
        setSegment(initialEditSegment(m, spec));
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
    // The spec's identity, not its object, decides a reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [specKey, nonce]);

  const rows = useMemo(() => (menu?.choices ?? []).filter((c) => c.segment === segment), [menu, segment]);
  const listRef = useRef<ScrollView>(null);
  // Scroll once per tab. Reset while rendering so a layout from the previous
  // tab cannot scroll this one after the guard was cleared.
  const scrolledFor = useRef<string | null>(null);
  const seenSegment = useRef(segment);
  if (seenSegment.current !== segment) {
    seenSegment.current = segment;
    scrolledFor.current = null;
  }
  const scrollKey = spec && menu ? editScrollTarget(menu, segment, spec) : null;
  const chosen = useMemo(
    () => (menu?.choices ?? []).find((c) => lineLegKey(c.spec) === picked) ?? null,
    [menu, picked],
  );
  const canSave = spec != null && chosen != null && canSaveEdit(menu, segment, picked, specKey);
  // A game with nothing posted is off the board; a prop keeps its own
  // segment's sentence ("…for this player"), whatever else is missing.
  const segmentEmpty = menu?.segments.find((g) => g.key === segment)?.empty ?? null;
  const emptyText =
    spec && !isGameSpec(spec)
      ? segmentEmpty ?? 'No sportsbook posts a line for this player right now.'
      : menu && menu.choices.length === 0
        ? GAME_OFF_BOARD
        : segmentEmpty ?? GAME_OFF_BOARD;
  // The leg's own bet is not on the board any more (line moved, book pulled
  // it): say so, rather than leave the list with no row marked current.
  const ownMissing = menu != null && specKey != null && !menu.choices.some((c) => lineLegKey(c.spec) === specKey);

  const save = () => {
    if (!chosen || !canSave) return;
    void onSave(chosen.spec).then((outcome) => {
      if (outcome === 'ok') onClose();
      else if (outcome === 'sidelined') setNote('This player is ruled out, so the leg can’t be changed.');
      else setNote('That bet is already on your betslip.');
    });
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
          <Text style={styles.subtitle}>
            {menu?.subtitle ?? (spec && isGameSpec(spec) ? '' : 'Pick a new line. Only lines a sportsbook posts are listed.')}
          </Text>
          {ownMissing && spec ? (
            <Text style={styles.ownMissing}>Your line, {lineLegLabel(spec).replace(/-/g, MINUS)}, isn’t posted right now.</Text>
          ) : null}

          {menu && menu.segments.length > 1 ? (
            <View style={styles.segmentWrap}>
              <SegmentTabs
                items={menu.segments.map((g) => g.key)}
                active={segment}
                onChange={(k) => {
                  setSegment(k);
                  setNote(null);
                }}
                labelFor={(k) => menu.segments.find((g) => g.key === k)?.label ?? k}
              />
            </View>
          ) : null}

          {failed ? (
            <View style={styles.state}>
              <Text style={styles.stateText}>Couldn’t load the lines. Check your connection and try again.</Text>
              <Pressable
                onPress={() => setNonce((n) => n + 1)}
                accessibilityRole="button"
                accessibilityLabel="Try again"
                style={({ pressed }) => [styles.retry, pressed && styles.pressed]}
              >
                <Text style={styles.retryText}>Try again</Text>
              </Pressable>
            </View>
          ) : menu == null ? (
            <View style={styles.state}>
              <ActivityIndicator />
            </View>
          ) : rows.length === 0 ? (
            <View style={styles.state}>
              <Text style={styles.stateText}>{emptyText}</Text>
            </View>
          ) : (
            <ScrollView key={segment} ref={listRef} style={styles.list} bounces={false}>
              <View style={styles.listCard}>
                {rows.map((c, i) => {
                  const key = lineLegKey(c.spec);
                  const selected = picked === key;
                  const isCurrent = key === specKey;
                  const priceText = formatAmerican(c.price).replace(/-/g, MINUS);
                  const titleText = c.title.replace(/-/g, MINUS);
                  return (
                    <Pressable
                      key={key}
                      onPress={() => {
                        setPicked(key);
                        setNote(null);
                      }}
                      accessibilityRole="radio"
                      accessibilityState={{ selected }}
                      accessibilityLabel={`${titleText.replace(/ ML$/, ' moneyline')}${c.hint ? `, ${c.hint}` : ''}, ${priceText} at ${bookLabelShort(c.book)}${isCurrent ? ', current line' : ''}`}
                      onLayout={key === scrollKey ? (e) => {
                        if (scrolledFor.current === segment) return;
                        scrolledFor.current = segment;
                        listRef.current?.scrollTo({ y: e.nativeEvent.layout.y, animated: false });
                      } : undefined}
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
                          {titleText}
                          {isCurrent ? <Text style={styles.current}>  · current</Text> : null}
                        </Text>
                        {c.hint ? <Text style={styles.rowHint}>{c.hint}</Text> : null}
                      </View>
                      <Text style={styles.rowBook}>{bookLabelShort(c.book)}</Text>
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
  segmentWrap: {
    marginBottom: spacing.md,
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
  ownMissing: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: -spacing.sm,
    marginBottom: spacing.md,
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
    color: colors.avoidInk,
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

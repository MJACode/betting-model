import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Swipeable from 'react-native-gesture-handler/Swipeable';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { EmptyState } from '@/components/EmptyState';
import { ParlayDkHandoff, type HandoffLeg } from '@/components/ParlayDkHandoff';
import { useSavedParlays } from '@/hooks/useSavedParlays';
import { setParlayRestore } from '@/hooks/useParlayRestore';
import {
  computeParlayMetrics,
  savedHandoffBookFor,
  savedLegToParlayLeg,
  type SavedParlay,
} from '@/lib/parlay';
import { bookName, MODEL_BOOK } from '@/lib/markets';
import { usePreferredBook } from '@/hooks/usePreferredBook';
import { betOnBookLabel, bookButtonColors } from '@/lib/sportsbookLinks';
import { modelShort } from '@/lib/modelMeta';
import { formatAmerican, formatPct, formatPctSigned } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList, 'SavedParlays'>;

/** Short relative time — "just now", "3h ago", "2d ago". */
function savedAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

const UNDO_MS = 4500;

export function SavedParlaysScreen() {
  const navigation = useNavigation<Nav>();
  const { items, remove, restore, clear } = useSavedParlays();
  // `ready` matters more here than on the builder: without it EVERY card's
  // primary button flips book, colour and label at once a frame after mount
  // (UX review).
  const { book: preferredBook, ready: bookReady } = usePreferredBook();
  const [handoff, setHandoff] = useState<{ book: string; legs: HandoffLeg[] } | null>(null);
  // Last deleted parlay, kept briefly so the user can Undo (no confirm dialog).
  const [undo, setUndo] = useState<SavedParlay | null>(null);
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (undoTimer.current) clearTimeout(undoTimer.current);
    },
    [],
  );

  const editInBuilder = (sp: SavedParlay) => {
    // Real legs with a stable key re-resolve against today's picks via the slip;
    // custom legs (and pre-upgrade saves with no slipKey) seed as snapshot legs.
    const slipKeys = sp.legs
      .filter((l) => l.pickId >= 0 && !!l.slipKey)
      .map((l) => l.slipKey as string);
    const customLegs = sp.legs
      .filter((l) => l.pickId < 0 || !l.slipKey)
      .map(savedLegToParlayLeg);
    setParlayRestore({ slipKeys, customLegs });
    navigation.navigate('Betslip');
  };

  // New parlay → open the builder in an empty "Build your own" play.
  const newParlay = useCallback(() => {
    setParlayRestore({ slipKeys: [], customLegs: [] });
    navigation.navigate('Betslip');
  }, [navigation]);

  // Instant delete with an Undo window (faster than tap → confirm dialog).
  const deleteNow = useCallback(
    (sp: SavedParlay) => {
      remove(sp.id);
      setUndo(sp);
      if (undoTimer.current) clearTimeout(undoTimer.current);
      undoTimer.current = setTimeout(() => setUndo(null), UNDO_MS);
    },
    [remove],
  );

  const undoDelete = useCallback(() => {
    if (undoTimer.current) clearTimeout(undoTimer.current);
    setUndo((sp) => {
      if (sp) restore(sp);
      return null;
    });
  }, [restore]);

  const confirmClearAll = useCallback(() => {
    Alert.alert('Clear all saved parlays?', `This removes all ${items.length}.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear all', style: 'destructive', onPress: () => clear() },
    ]);
  }, [items.length, clear]);

  // Hand off at the user's own book, like the builder's button and the Stats
  // line pill (Matt, 2026-09-04). savedHandoffBookFor falls back to DraftKings
  // unless their book has a stored link for EVERY leg — a saved slip carries
  // the links it was saved with, so an older save legitimately has DK only.
  // Each leg's link is AT the book being opened, never DK's slip under another
  // book's label.
  const betAtBook = (sp: SavedParlay) => {
    const { book, links } = savedHandoffBookFor(sp.legs, preferredBook);
    setHandoff({
      book,
      legs: sp.legs.map((l, i) => ({
        key: String(l.pickId),
        label: l.label,
        matchup: l.matchup,
        americanOdds: l.americanOdds,
        betLink: links[i] ?? null,
      })),
    });
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <FlatList
        data={items}
        keyExtractor={(p) => p.id}
        contentContainerStyle={styles.scroll}
        ListHeaderComponent={
          <View style={styles.headerRow}>
            <Pressable
              onPress={newParlay}
              style={({ pressed }) => [styles.newBtn, pressed && styles.pressed]}
            >
              <Ionicons name="add" size={18} color={colors.textInverse} />
              <Text style={styles.newBtnText}>New parlay</Text>
            </Pressable>
            {items.length > 0 ? (
              <Pressable
                onPress={confirmClearAll}
                style={({ pressed }) => [styles.clearAllBtn, pressed && styles.pressed]}
              >
                <Text style={styles.clearAllText}>Clear all</Text>
              </Pressable>
            ) : null}
          </View>
        }
        ListEmptyComponent={
          <EmptyState
            title="No saved parlays"
            subtitle="Tap “New parlay” to build one, or save one from your betslip to keep it here."
          />
        }
        renderItem={({ item }) => (
          <SavedParlayCard
            parlay={item}
            handoffBook={savedHandoffBookFor(item.legs, preferredBook).book}
            preferredBook={preferredBook}
            bookReady={bookReady}
            onBet={() => betAtBook(item)}
            onEdit={() => editInBuilder(item)}
            onDelete={() => deleteNow(item)}
          />
        )}
      />

      {undo ? (
        <View style={styles.undoBar}>
          <Text style={styles.undoText}>Parlay deleted</Text>
          <Pressable onPress={undoDelete} hitSlop={8}>
            <Text style={styles.undoAction}>Undo</Text>
          </Pressable>
        </View>
      ) : null}

      <ParlayDkHandoff
        visible={handoff != null}
        legs={handoff?.legs ?? []}
        book={handoff?.book ?? MODEL_BOOK}
        onClose={() => setHandoff(null)}
      />
    </SafeAreaView>
  );
}

function SavedParlayCard({
  parlay,
  handoffBook,
  preferredBook,
  bookReady,
  onBet,
  onEdit,
  onDelete,
}: {
  parlay: SavedParlay;
  /** Book the bet button hands off to (savedHandoffBookFor) — names the label. */
  handoffBook: string;
  /** The member's own book, to say WHY a card fell back to DraftKings. */
  preferredBook: string;
  /** False until the stored preference has loaded — see the hook's `ready`. */
  bookReady: boolean;
  onBet: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const metrics = useMemo(
    () => computeParlayMetrics(parlay.legs.map(savedLegToParlayLeg)),
    [parlay.legs],
  );
  const betColors = bookButtonColors(handoffBook);
  // Two saved slips can legitimately carry different books: this screen has no
  // "Open with" row, so without a reason on the card that reads as a bug. A
  // save made before the member chose their book has no links at that book at
  // all, which is a different sentence from "your book can't price this leg".
  const fellBack = bookReady && handoffBook !== preferredBook;
  const preUpgrade = parlay.legs.some((l) => l.bookLinks == null);
  const renderRightActions = () => (
    <Pressable
      onPress={onDelete}
      style={({ pressed }) => [styles.swipeDelete, pressed && styles.pressed]}
    >
      <Ionicons name="trash-outline" size={22} color={colors.textInverse} />
      <Text style={styles.swipeDeleteText}>Delete</Text>
    </Pressable>
  );
  return (
    <Swipeable
      renderRightActions={renderRightActions}
      overshootRight={false}
      containerStyle={styles.swipeContainer}
    >
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>
          {parlay.legs.length}-Leg · {formatAmerican(metrics.americanOdds)}
        </Text>
        <Text style={styles.cardMeta}>
          {parlay.sport} · {savedAgo(parlay.createdAt)}
        </Text>
      </View>

      <View style={styles.statsRow}>
        <Stat label="Model" value={formatPct(metrics.parlayProb)} />
        <Stat
          label="EV"
          value={formatPctSigned(metrics.ev)}
          color={metrics.ev >= 0 ? colors.bet : colors.avoid}
        />
        <Stat
          label="Edge"
          value={formatPctSigned(metrics.edgeVsDk)}
          color={metrics.edgeVsDk >= 0 ? colors.bet : colors.avoid}
        />
        <Stat label="DK imp." value={formatPct(metrics.dkImpliedProb)} />
      </View>

      <View style={styles.legsList}>
        {parlay.legs.map((leg) => (
          <View key={leg.pickId} style={styles.legRow}>
            <View style={styles.legBody}>
              {leg.matchup ? <Text style={styles.legMatchup}>{leg.matchup}</Text> : null}
              <Text style={styles.legLabel} numberOfLines={2}>
                {leg.label}
              </Text>
            </View>
            <View style={styles.legMeta}>
              <View style={styles.modelChip}>
                <Text style={styles.modelChipText}>{modelShort(leg.modelId)}</Text>
              </View>
              <Text style={styles.legOdds}>{formatAmerican(leg.americanOdds)}</Text>
            </View>
          </View>
        ))}
      </View>

      <View style={styles.actions}>
        <Pressable
          onPress={onBet}
          disabled={!bookReady}
          accessibilityRole="button"
          accessibilityState={{ disabled: !bookReady }}
          accessibilityLabel={
            fellBack
              ? `${betOnBookLabel(handoffBook)}. This slip has no ${bookName(preferredBook)} links.`
              : betOnBookLabel(handoffBook)
          }
          style={({ pressed }) => [
            styles.betBtn,
            { backgroundColor: betColors.bg },
            (pressed || !bookReady) && styles.pressed,
          ]}
        >
          <Ionicons name="open-outline" size={16} color={betColors.fg} />
          <Text style={[styles.betBtnText, { color: betColors.fg }]}>
            {betOnBookLabel(handoffBook)}
          </Text>
        </Pressable>
        {fellBack ? (
          <Text style={styles.betFallback}>
            {preUpgrade
              ? `Saved before you chose ${bookName(preferredBook)} — opens ${bookName(handoffBook)}`
              : `${bookName(preferredBook)} doesn’t price every leg — opens ${bookName(handoffBook)}`}
          </Text>
        ) : null}
        <View style={styles.secondaryRow}>
          <Pressable onPress={onEdit} style={({ pressed }) => [styles.editBtn, pressed && styles.pressed]}>
            <Ionicons name="create-outline" size={16} color={colors.tint} />
            <Text style={styles.editBtnText}>Edit in builder</Text>
          </Pressable>
          <Pressable onPress={onDelete} style={({ pressed }) => [styles.deleteBtn, pressed && styles.pressed]}>
            <Ionicons name="trash-outline" size={16} color={colors.avoid} />
            <Text style={styles.deleteBtnText}>Delete</Text>
          </Pressable>
        </View>
      </View>
    </View>
    </Swipeable>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, color ? { color } : null]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  scroll: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  newBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
  },
  newBtnText: {
    color: colors.textInverse,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  clearAllBtn: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  clearAllText: {
    color: colors.avoid,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
  },
  undoBar: {
    position: 'absolute',
    left: spacing.lg,
    right: spacing.lg,
    bottom: spacing.xl,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.textPrimary,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  undoText: {
    color: colors.bg,
    fontSize: font.size.callout,
    fontWeight: font.weight.medium,
  },
  undoAction: {
    color: colors.tint,
    textDecorationLine: 'underline',
    fontSize: font.size.callout,
    // The underline is the affordance; bold on top of it made a three-second
    // banner the loudest text on the screen.
    fontWeight: font.weight.semibold,
  },
  swipeContainer: {
    marginBottom: spacing.md,
    borderRadius: radii.lg,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
  },
  swipeDelete: {
    backgroundColor: colors.avoid,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 2,
    width: 92,
    borderTopRightRadius: radii.lg,
    borderBottomRightRadius: radii.lg,
  },
  swipeDeleteText: {
    color: colors.textInverse,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  cardTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  cardMeta: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
    paddingBottom: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  stat: {
    flex: 1,
  },
  statLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  statValue: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  legsList: {
    marginBottom: spacing.md,
  },
  legRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  legBody: {
    flex: 1,
  },
  legMatchup: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  legLabel: {
    fontSize: font.size.body,
    fontWeight: font.weight.medium,
    color: colors.textPrimary,
  },
  legMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginLeft: spacing.sm,
  },
  modelChip: {
    backgroundColor: colors.noneSoft,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  modelChipText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  legOdds: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
    minWidth: 44,
    textAlign: 'right',
  },
  actions: {
    gap: spacing.sm,
  },
  betBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
  },
  betBtnText: {
    color: colors.textInverse,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  betFallback: {
    marginTop: spacing.xs,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  secondaryRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  editBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.sm,
  },
  editBtnText: {
    color: colors.tint,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
  },
  deleteBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    borderRadius: radii.md,
    paddingVertical: spacing.sm,
  },
  deleteBtnText: {
    color: colors.avoid,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
  },
  pressed: {
    opacity: 0.6,
  },
});

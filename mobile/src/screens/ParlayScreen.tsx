import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '@/types';
import { EmptyState } from '@/components/EmptyState';
import { ParlayLegCard } from '@/components/ParlayLegCard';
import { ParlayDkHandoff, type HandoffLeg } from '@/components/ParlayDkHandoff';
import { BetslipBooksRow } from '@/components/BetslipBooksRow';
import { SettingsButton } from '@/components/SettingsButton';
import { showToast } from '@/components/Toast';
import { betOnBookLabel, bookButtonColors, DK_GREEN } from '@/lib/sportsbookLinks';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { useResolvedSlip } from '@/hooks/useResolvedSlip';
import { isLineLeg } from '@/lib/lineLegs';
import { setEditingParlayId, useEditingParlayId, useSavedParlays } from '@/hooks/useSavedParlays';
import { useParlayRestore } from '@/hooks/useParlayRestore';
import { useParlayCorrelations } from '@/hooks/useParlayCorrelations';
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { fetchPlayerTeams } from '@/lib/queries';
import {
  handoffBookFor,
  isValidCombo,
  lineShopParlay,
  makeCustomLeg,
  matchupForLeg,
  parlayRecommendedUnits,
  type LineShop,
  type ParlayLeg,
} from '@/lib/parlay';
import { formatStake } from '@/lib/thresholds';
import {
  computeCorrelatedMetrics,
  GRADE_LABEL,
  type CorrelatedMetrics,
  type ParlayGrade,
} from '@/lib/parlayCorrelation';
import { bookLabel, bookName, booksName, MODEL_BOOK } from '@/lib/markets';
import {
  americanToDecimal,
  formatAmerican,
  formatCurrency,
  formatPct,
  formatPctSigned,
} from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';

type ParlayNav = NativeStackNavigationProp<RootStackParamList>;

/** Parse an American-odds text field to a number, or null when blank/invalid. */
function parseAmerican(text: string): number | null {
  const t = text.trim();
  if (!t) return null;
  const n = Number(t.replace(/^\+/, ''));
  if (!Number.isFinite(n) || n === 0) return null;
  return n;
}

/**
 * The betslip: the bets the user has added, and nothing else.
 *
 * There is deliberately no auto-builder here. The optimizer and the same-game
 * finder both PROPOSED parlays the user never asked for, which meant the screen
 * could show a "2-leg play" while the user's own slip was empty — the slip is
 * the only thing this screen is about, so it is the only thing it shows. Legs
 * come from "Add to betslip" (Stats, Picks, pick detail) or a hand-entered
 * custom leg, and every one of them can be removed individually or all at once.
 */
export function ParlayScreen() {
  const navigation = useNavigation<ParlayNav>();
  // One hook owns the slip, the board it resolves against, and the pruning of
  // selections that no longer resolve — so this screen and the persistent
  // betslip bar can never disagree about what is in the slip.
  const {
    slip,
    lineLegs,
    count: slipCount,
    picks: { data, loading, error, refresh },
    legs: slipLegs,
    stale: staleKeys,
    removed: removedCount,
    resolving,
  } = useResolvedSlip();
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);
  const savedParlays = useSavedParlays();
  const { pending: restorePending, consume: consumeRestore } = useParlayRestore();
  const rho = useParlayCorrelations();

  // Player → team map, so the copula engine can tell same-team from opposing
  // offensive stacking (Phase 2). MLB-only source; basketball props fall back to
  // the team-agnostic ('na') correlation bucket. Failure-tolerant.
  const [playerTeams, setPlayerTeams] = useState<Record<string, string>>({});
  const resolveTeam = useCallback(
    (playerId: string): string | null => playerTeams[playerId] ?? null,
    [playerTeams],
  );

  // Session-only hand-entered legs (not persisted — they resolve against no
  // pick row, so there is nothing stable to key them on).
  const [manualCustom, setManualCustom] = useState<ParlayLeg[]>([]);
  /**
   * The saved parlay this slip is an edit of, so the next save writes back over
   * it instead of inserting a second record. Set two ways: by "Edit in builder"
   * (the restore payload), and by the builder's own save — after "Save parlay"
   * the slip on screen IS that saved parlay, so tapping save again updates it
   * rather than filing a duplicate.
   *
   * It lives in a module store (useSavedParlays) rather than here BECAUSE this
   * screen gets popped mid-edit: "Find players to add" navigates to the tabs,
   * which pops the Betslip, and adding a leg pushes a fresh one. Screen state
   * died on that trip and the save went back to inserting duplicates.
   */
  const editingId = useEditingParlayId();
  // Drives the pinned header's separator: shown only once content has scrolled
  // under it, the way every native stack header in this app behaves.
  const [scrolled, setScrolled] = useState<boolean>(false);
  const [customOpen, setCustomOpen] = useState<boolean>(false);
  const [customLabel, setCustomLabel] = useState<string>('');
  const [customOddsText, setCustomOddsText] = useState<string>('');

  // Load teams for today's prop players once picks land (drives same/opp).
  useEffect(() => {
    const ids = data.map((ep) => ep.pick.player_id).filter((id): id is string => !!id);
    if (ids.length === 0) {
      setPlayerTeams({});
      return;
    }
    let alive = true;
    fetchPlayerTeams(ids)
      .then((m) => {
        if (alive) setPlayerTeams(m);
      })
      .catch(() => {
        /* team-agnostic fallback on failure */
      });
    return () => {
      alive = false;
    };
  }, [data]);

  // slipLegs comes from useResolvedSlip (the persisted slip resolved against
  // today's picks, cross-sport, any signal); session custom legs append here.
  const legs = useMemo(() => [...slipLegs, ...manualCustom], [slipLegs, manualCustom]);
  const metrics = useMemo(
    () => computeCorrelatedMetrics(legs, rho, resolveTeam),
    [legs, rho, resolveTeam],
  );
  const valid = useMemo(() => isValidCombo(legs), [legs]);

  // The sport a saved slip is filed under: the first real pick's sport (custom
  // legs carry no pick, so they can't answer this).
  const sport = useMemo(
    () =>
      legs.find((l) => l.pick != null)?.pick?.sport ??
      legs.find((l) => isLineLeg(l))?.game?.sport ??
      'MLB',
    [legs],
  );

  const handleRemove = useCallback(
    (pickId: number) => {
      // A Stats line leg is negative too, but it lives in its own store.
      const line = slipLegs.find((l) => l.pickId === pickId && isLineLeg(l));
      if (line) {
        lineLegs.remove(line.slipKey);
        return;
      }
      if (pickId < 0) {
        setManualCustom((prev) => prev.filter((l) => l.pickId !== pickId));
        return;
      }
      // Map the (session) pickId back to its stable slip key to remove it.
      const leg = slipLegs.find((l) => l.pickId === pickId);
      if (leg) slip.remove(leg.slipKey);
    },
    [slip, slipLegs, lineLegs],
  );

  const handleClear = useCallback(() => {
    slip.clear();
    lineLegs.clear();
    setManualCustom([]);
    // A cleared slip is no longer the saved parlay it was seeded from — the
    // next save is a new one, not a write over the old.
    setEditingParlayId(null);
  }, [slip, lineLegs]);

  // Only reachable when the board isn't trusted (offline, empty slate) — the
  // pruner leaves those keys in place, so this is the manual escape hatch.
  const handleClearStale = useCallback(() => {
    // `line:` keys are Stats line legs (their read failed); the rest are picks.
    staleKeys.forEach((key) => (key.startsWith('line:') ? lineLegs.remove(key) : slip.remove(key)));
  }, [staleKeys, slip, lineLegs]);

  const openCustom = useCallback(() => {
    setCustomLabel('');
    setCustomOddsText('');
    setCustomOpen(true);
  }, []);

  const closeCustom = useCallback(() => setCustomOpen(false), []);

  // Send the user to the Stats tab to browse players; adding one brings them
  // back here automatically (fromParlay flag handled in StatsScreen). This
  // screen is pushed over the tabs, so navigating to Tabs pops it — the return
  // trip pushes a fresh one, which is also what re-opens it on the slip.
  const goFindPlayers = useCallback(() => {
    navigation.navigate('Tabs', { screen: 'Stats', params: { fromParlay: true } });
  }, [navigation]);

  // Restore a saved parlay into the slip (from the Saved Parlays screen). Real
  // pick_ids re-resolve against today's picks via the slip; reconstructed
  // custom/stale legs seed the session state directly.
  useEffect(() => {
    if (!restorePending) return;
    slip.clear();
    restorePending.slipKeys.forEach((key) => slip.add(key));
    setManualCustom(restorePending.customLegs);
    setEditingParlayId(restorePending.editingId ?? null);
    consumeRestore();
  }, [restorePending]); // eslint-disable-line react-hooks/exhaustive-deps

  // Removing the last leg ends the edit, the same way "Clear" does. Without
  // this the binding outlived the slip: empty it leg by leg, build a brand new
  // slip, and "Update parlay" would have overwritten the parlay you edited an
  // hour ago with something that shares nothing with it.
  useEffect(() => {
    if (!resolving && legs.length === 0 && editingId) setEditingParlayId(null);
  }, [resolving, legs.length, editingId]);

  const customOdds = parseAmerican(customOddsText);
  const customValid = customLabel.trim().length > 0 && customOdds != null;
  const customImpliedPct =
    customOdds != null ? 1 / americanToDecimal(customOdds) : null;

  const handleSaveCustom = useCallback(() => {
    const odds = parseAmerican(customOddsText);
    if (customLabel.trim().length === 0 || odds == null) return;
    setManualCustom((prev) => [...prev, makeCustomLeg(customLabel, odds)]);
    setCustomLabel('');
    setCustomOddsText('');
    setCustomOpen(false);
  }, [customLabel, customOddsText]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* PINNED, not scrolled with the slip. The close chevron is this screen's
          only way out (it renders its own header, so there is no stack back
          button), and it used to sit at the top of the ScrollView — on a slip
          long enough to scroll, the exit scrolled off with it. */}
      <View style={[styles.header, scrolled && styles.headerScrolled]}>
        <View style={styles.titleRow}>
          <View style={styles.titleLeft}>
            <Pressable
              onPress={() => navigation.goBack()}
              hitSlop={10}
              accessibilityRole="button"
              accessibilityLabel="Close betslip"
              style={({ pressed }) => [styles.closeBtn, pressed && styles.pressed]}
            >
              <Ionicons name="chevron-down" size={22} color={colors.textSecondary} />
            </Pressable>
            <Text style={styles.title}>Betslip</Text>
            {slipCount > 0 ? (
              <View style={styles.countBadge}>
                <Text style={styles.countBadgeText}>{slipCount}</Text>
              </View>
            ) : null}
          </View>
          <View style={styles.rightActions}>
            <Pressable
              onPress={() => navigation.navigate('SavedParlays')}
              hitSlop={8}
              style={({ pressed }) => [styles.savedLink, pressed && styles.pressed]}
            >
              <Ionicons name="bookmark-outline" size={16} color={colors.tint} />
              <Text style={styles.savedLinkText}>
                Saved{savedParlays.count > 0 ? ` (${savedParlays.count})` : ''}
              </Text>
            </Pressable>
            <SettingsButton />
          </View>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}
        onScroll={(e) => setScrolled(e.nativeEvent.contentOffset.y > 0)}
        scrollEventThrottle={16}
      >
        {/* Descriptive, not a control — so it scrolls, and only the title row
            and its buttons stay pinned (HIG: navigation bars keep controls and
            the title; descriptive text belongs to the content). It also states
            the MODE, which is why the "Update parlay" button needs no standing
            caption of its own. */}
        <Text style={styles.subtitle}>
          {legs.length === 0
            ? 'The bets you add show up here'
            : `${editingId ? 'Editing a saved parlay · ' : ''}${legs.length} leg${legs.length === 1 ? '' : 's'} · tap a leg to remove it`}
        </Text>

        {error ? (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>Connection error: {error}</Text>
          </View>
        ) : null}

        {resolving ? (
          <View style={styles.loadingWrap}>
            <ActivityIndicator />
          </View>
        ) : (
          <SlipBody
            legs={legs}
            metrics={metrics}
            valid={valid}
            staleCount={staleKeys.length}
            removedCount={removedCount}
            sport={sport}
            bankroll={bankroll}
            kelly={kelly}
            onRemove={handleRemove}
            onAddCustom={openCustom}
            onFindPlayers={goFindPlayers}
            onClear={handleClear}
            onClearStale={handleClearStale}
            editingId={editingId}
            onSaved={setEditingParlayId}
          />
        )}
      </ScrollView>

      {/* ── Custom-leg form ─────────────────────────────────────────── */}
      <Modal visible={customOpen} animationType="slide" transparent onRequestClose={closeCustom}>
        {/* Without this the keyboard slides up OVER the bottom sheet and hides
            the inputs entirely — the sheet must rise with the keyboard. */}
        <KeyboardAvoidingView
          style={styles.modalBackdrop}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Custom leg</Text>
              <Pressable
                onPress={closeCustom}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel="Close"
              >
                <Ionicons name="close" size={24} color={colors.textSecondary} />
              </Pressable>
            </View>

            <Text style={styles.panelTitle}>Pick</Text>
            <TextInput
              style={styles.customInput}
              value={customLabel}
              onChangeText={setCustomLabel}
              placeholder="e.g. Aaron Judge 2+ total bases"
              placeholderTextColor={colors.textTertiary}
              returnKeyType="next"
            />

            <Text style={styles.panelTitle}>American odds</Text>
            <TextInput
              style={styles.customInput}
              value={customOddsText}
              onChangeText={setCustomOddsText}
              placeholder="e.g. +150 or -110"
              placeholderTextColor={colors.textTertiary}
              keyboardType="numbers-and-punctuation"
              returnKeyType="done"
            />

            <Text style={styles.customHint}>
              {customImpliedPct != null
                ? `Win probability used: ${formatPct(customImpliedPct)} (odds-implied)`
                : 'Win probability comes from the odds you enter.'}
            </Text>

            <Pressable
              onPress={handleSaveCustom}
              disabled={!customValid}
              style={({ pressed }) => [
                styles.buildBtn,
                !customValid && styles.buildBtnDisabled,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons name="checkmark" size={18} color={colors.textInverse} />
              <Text style={styles.buildBtnText}>Add leg</Text>
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

/**
 * Save-for-later + sportsbook hand-off, shared by the Optimize result card and
 * the manual builder.
 *
 * THE BUTTON IS THE USER'S OWN BOOK (Matt, 2026-09-04): "the parlay button …
 * should change to match the Sportsbook the user selects as their preferred."
 * Placing a bet is the one thing the member does at THEIR book, so the button
 * that sends them there follows their pick — the Stats board's line pill and
 * this button now read the same setting.
 *
 * It is only the hand-off. The slip is still PRICED and modeled at DraftKings
 * (§6), and the "Open with" row above still ranks every bettable book by
 * payout, so a better price is always one tap away.
 *
 * `handoffBookFor` falls back to DraftKings when their book does not price
 * every leg — "Bet on FanDuel" must never open a slip FanDuel cannot take.
 * No book has a multi-leg deep link, so it opens a leg-by-leg hand-off sheet.
 */
function ParlayActions({
  legs,
  sport,
  editingId,
  droppedCount,
  onSaved,
}: {
  legs: ParlayLeg[];
  sport: string;
  /** The saved parlay this slip is an edit of, or null for a new one. */
  editingId: string | null;
  /** Legs the board could not price back — they are NOT in `legs`, so updating
   *  a save would drop them. The caption says so before the tap. */
  droppedCount: number;
  /** Called with the id the slip now lives under, so a second tap updates it. */
  onSaved: (id: string) => void;
}) {
  const { save, update } = useSavedParlays();
  const [handoffOpen, setHandoffOpen] = useState(false);
  // `ready` gates the button: the hook seeds to DraftKings and resolves storage
  // in an effect, so without it a FanDuel member sees a green "Bet on
  // DraftKings" for a frame — and a tap landing in that window hands off to the
  // wrong book with no way to tell (UX review).
  const { books: preferredBooks, ready: bookReady } = usePreferredBooks();

  const handoff = useMemo(
    () => handoffBookFor(legs, preferredBooks),
    [legs, preferredBooks],
  );
  // None of their books could take the whole slip, so the button is opening DK
  // instead. A STATE, not a standing pricing note — it renders only when the
  // app has just overridden the member's own choice on a money-moving action.
  const fellBack = bookReady && !(preferredBooks as readonly string[]).includes(handoff.book);
  // The slip is PRICED at DraftKings but this button opens somewhere else, and
  // "Potential payout" is 40pt above it. Still a state and not the standing
  // note Matt removed: with DraftKings taking the slip — the common case —
  // nothing renders (UX review).
  const opensElsewhere = bookReady && handoff.book !== MODEL_BOOK;
  const btnColors = bookButtonColors(handoff.book);

  const handoffLegs: HandoffLeg[] = useMemo(
    () =>
      legs.map((l, i) => ({
        key: String(l.pickId),
        label: l.label,
        matchup: matchupForLeg(l.game),
        americanOdds: l.americanOdds,
        betLink: handoff.links[i] ?? null,
        posted: handoff.posted[i] ?? true,
      })),
    [legs, handoff],
  );
  // No book prices every leg — a Stats line leg DraftKings never posted, on a
  // slip another book cannot complete. The button opens the book covering the
  // most, and says how many, so nobody taps a green button into a slip that
  // book cannot take (UX review).
  const partial = bookReady && handoff.priced < handoff.total;

  /**
   * Save is an INSERT once and an UPDATE thereafter.
   *
   * It used to be an insert every time, so the two commonest gestures each
   * left a duplicate behind: editing a saved parlay and saving it, and simply
   * tapping "Save parlay" twice. `editingId` is the record this slip already
   * IS — set by "Edit in builder", and by the first save — so a later save
   * writes over it. An id that no longer exists (deleted while the builder was
   * open) falls back to an insert rather than losing the slip.
   */
  const applySave = useCallback(() => {
    if (editingId) {
      const updated = update(editingId, legs, sport);
      if (updated) {
        onSaved(updated.id);
        showToast('Saved parlay updated');
        return;
      }
    }
    const parlay = save(legs, sport);
    onSaved(parlay.id);
    showToast('Saved · find it under “Saved” at the top of your betslip');
  }, [save, update, editingId, onSaved, legs, sport]);

  // An update that drops legs is a delete with extra steps, and there is no
  // undo behind it — so it asks first, naming what goes. An update that keeps
  // every leg does not: confirming a save nobody can lose anything to is noise.
  const onSave = useCallback(() => {
    if (!editingId || droppedCount === 0) {
      applySave();
      return;
    }
    Alert.alert(
      'Update without those legs?',
      `${droppedCount} leg${droppedCount === 1 ? '' : 's'} in this parlay ${droppedCount === 1 ? 'is' : 'are'} no longer on the board. Updating saves it without ${droppedCount === 1 ? 'it' : 'them'}, and that can't be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Update', style: 'destructive', onPress: applySave },
      ],
    );
  }, [applySave, editingId, droppedCount]);

  if (legs.length === 0) return null;

  return (
    <>
      <View style={styles.parlayActions}>
        <Pressable
          onPress={onSave}
          accessibilityRole="button"
          accessibilityLabel={editingId ? 'Update saved parlay' : 'Save parlay'}
          style={({ pressed }) => [styles.saveBtn, pressed && styles.pressed]}
        >
          <Ionicons
            name={editingId ? 'bookmark' : 'bookmark-outline'}
            size={18}
            color={colors.tint}
          />
          <Text style={styles.saveBtnText}>{editingId ? 'Update parlay' : 'Save parlay'}</Text>
        </Pressable>
        <Pressable
          onPress={() => setHandoffOpen(true)}
          disabled={!bookReady}
          accessibilityRole="button"
          accessibilityState={{ disabled: !bookReady }}
          accessibilityLabel={
            fellBack
              ? `${betOnBookLabel(handoff.book)}. ${booksName(preferredBooks)} ${preferredBooks.length === 1 ? 'does' : 'do'} not price every leg.`
              : betOnBookLabel(handoff.book)
          }
          style={({ pressed }) => [
            styles.dkBtn,
            { backgroundColor: btnColors.bg },
            (pressed || !bookReady) && styles.pressed,
          ]}
        >
          <Ionicons name="open-outline" size={18} color={btnColors.fg} />
          <Text style={[styles.dkBtnText, { color: btnColors.fg }]}>
            {betOnBookLabel(handoff.book)}
          </Text>
        </Pressable>
      </View>

      {/* The mode itself is stated in the subtitle and on the button — no
          standing caption here, which would render forever under an ordinary
          save and stack with the hand-off captions below. What DOES belong
          here is the loss: updating writes the shorter slip over the save.
          Shaped like the same-game warning above, because colour alone is not
          a signal — colors.med measures 2.20:1 on this card, half the AA
          floor, so the tint, the icon and the wording all have to carry it. */}
      {editingId && droppedCount > 0 ? (
        <View style={[styles.warnBanner, styles.updateWarn]}>
          <Ionicons name="warning-outline" size={16} color={colors.med} />
          <Text style={styles.warnText}>
            {droppedCount} leg{droppedCount === 1 ? '' : 's'}{' '}
            {droppedCount === 1 ? 'is' : 'are'} no longer on the board —
            “Update parlay” saves this slip without {droppedCount === 1 ? 'it' : 'them'}.
          </Text>
        </View>
      ) : null}

      {partial ? (
        <Text style={styles.handoffFallback}>
          {bookName(handoff.book)} prices {handoff.priced} of {handoff.total} legs — add the
          rest at a book that posts them
        </Text>
      ) : fellBack ? (
        <Text style={styles.handoffFallback}>
          {booksName(preferredBooks)} {preferredBooks.length === 1 ? 'doesn’t' : 'don’t'} price
          every leg — opening {bookName(handoff.book)}
        </Text>
      ) : opensElsewhere ? (
        <Text style={styles.handoffFallback}>
          Priced at DraftKings · opening {bookName(handoff.book)}
        </Text>
      ) : null}

      {/* Sibling, not a child of the row: parlayActions is flexDirection row
          with a gap, and a Modal that ever became a layout participant would
          open one. */}
      <ParlayDkHandoff
        visible={handoffOpen}
        legs={handoffLegs}
        book={handoff.book}
        onClose={() => setHandoffOpen(false)}
      />
    </>
  );
}

/**
 * Honest framing on every parlay: books love parlays because they stack hold
 * (~15-25% vs ~5% on straights). We only build +EV combos, but we say so plainly
 * and warn hard when the combined EV is negative.
 */
function ParlayHoldNote({
  ev,
  exception,
  modelBacked,
}: {
  ev: number;
  exception: string | null;
  /**
   * Does any leg carry a model's number? A slip built entirely of Stats line
   * legs does not — Doubles and Triples have no model at all — so the positive
   * branch must not credit "the model's combined probability" for a figure
   * that is the books' own price multiplied out (UX review, 2026-09-05).
   */
  modelBacked: boolean;
}) {
  const negative = ev < 0;
  // A Stats line leg DraftKings never posted is priced at another book, and
  // the note must not attribute that number to DraftKings (UX review).
  const priced = exception
    ? `Priced at DraftKings, except ${exception}.`
    : 'Every leg is priced at DraftKings — that’s the book the models score against, whichever book you bet at.';
  return (
    <View style={[styles.holdNote, negative && styles.holdNoteBad]}>
      <Ionicons
        name={negative ? 'warning-outline' : 'information-circle-outline'}
        size={14}
        color={negative ? colors.avoid : colors.textTertiary}
      />
      <Text style={[styles.holdNoteText, negative && styles.holdNoteTextBad]}>
        {negative
          ? modelBacked
            ? `Negative EV — the books’ parlay hold outweighs the model’s edge here. Straight bets are the better value. ${priced}`
            : `Negative EV — these are your own lines at the books’ own prices, so the parlay hold is the whole story. Straight bets are the better value. ${priced}`
          : modelBacked
            ? `${priced} Parlays also carry far more hold (~15–25%) than straight bets (~5%); this one only clears because the model’s combined probability beats the price.`
            : `${priced} These are your own lines, priced at what the book is offering — no model has an opinion on them. Parlays carry far more hold (~15–25%) than straight bets (~5%).`}
      </Text>
    </View>
  );
}

const GRADE_COLOR: Record<ParlayGrade, string> = {
  great: colors.bet,
  good: colors.info, // status, not a control — tint is near-black now
  fair: colors.med,
  bad: colors.avoid,
};

/** Great / Good / Fair / Bad pill, graded on the correlated EV. */
function GradeBadge({ grade, small }: { grade: ParlayGrade; small?: boolean }) {
  const c = GRADE_COLOR[grade];
  return (
    <View style={[styles.gradeBadge, small && styles.gradeBadgeSmall, { backgroundColor: `${c}22`, borderColor: c }]}>
      <Text style={[styles.gradeBadgeText, small && styles.gradeBadgeTextSmall, { color: c }]}>
        {GRADE_LABEL[grade]}
      </Text>
    </View>
  );
}

/**
 * Correlation-aware extras: fair (no-vig) odds vs DK, the book's hold (or our
 * edge) on this exact slip, and — when same-game legs are correlated — the joint
 * probability vs the naïve product, which is the whole point of the engine.
 */
function CorrelatedExtras({ m, allDk }: { m: CorrelatedMetrics; allDk: boolean }) {
  const holdPositive = m.dkHoldPct >= 0;
  return (
    <View style={styles.corrExtras}>
      <View style={styles.corrRow}>
        <Text style={styles.corrLabel}>Fair odds</Text>
        <Text style={styles.corrValue}>
          {formatAmerican(m.fairAmerican)} · {allDk ? 'DK' : 'slip'} {formatAmerican(m.americanOdds)}
        </Text>
      </View>
      <View style={styles.corrRow}>
        <Text style={styles.corrLabel}>{holdPositive ? (allDk ? 'DK hold on this slip' : 'Hold on this slip') : 'Your edge on this slip'}</Text>
        <Text style={[styles.corrValue, { color: holdPositive ? colors.avoid : colors.bet }]}>
          {formatPct(Math.abs(m.dkHoldPct))}
        </Text>
      </View>
      {m.hasCorrelation ? (
        <>
          <View style={styles.corrRow}>
            <Text style={styles.corrLabel}>Correlated win %</Text>
            <Text style={styles.corrValue}>
              {formatPct(m.jointProb)} vs {formatPct(m.independentProb)} naïve
            </Text>
          </View>
          <Text style={styles.corrHint}>
            Same-game legs move together — priced on their joint probability, not the simple product.
          </Text>
        </>
      ) : null}
    </View>
  );
}

/**
 * Line-shopping row: when a non-DK book beats DK on one or more legs, show the
 * best-book combined odds + EV (and the lift vs all-DK). Display-only — there's
 * no FanDuel deep link, so the DK hand-off still uses DK prices.
 */
function LineShopRow({ lineShop, dkAmerican }: { lineShop: LineShop | null; dkAmerican: number }) {
  if (!lineShop) return null;
  const books = lineShop.books.map(bookLabel).join(', ');
  return (
    <View style={styles.lineShop}>
      <View style={styles.lineShopHeader}>
        <Ionicons name="pricetag-outline" size={13} color={colors.bet} />
        <Text style={styles.lineShopTitle}>Line shop</Text>
      </View>
      <View style={styles.corrRow}>
        <Text style={styles.corrLabel}>Best-book odds</Text>
        <Text style={[styles.corrValue, { color: colors.bet }]}>
          {formatAmerican(lineShop.americanOdds)} vs DK {formatAmerican(dkAmerican)}
        </Text>
      </View>
      <View style={styles.corrRow}>
        <Text style={styles.corrLabel}>EV at best books</Text>
        <Text style={[styles.corrValue, { color: lineShop.ev >= 0 ? colors.bet : colors.avoid }]}>
          {formatPctSigned(lineShop.ev)} ({formatPctSigned(lineShop.evDelta)})
        </Text>
      </View>
      <Text style={styles.corrHint}>
        {lineShop.shoppedCount} leg{lineShop.shoppedCount === 1 ? '' : 's'} priced better at {books}.
        Display-only — the odds above are DraftKings’. Tap a book in Open with to place at its price.
      </Text>
    </View>
  );
}

/**
 * The slip itself. Renders an empty state, or the packaged parlay with every
 * leg individually removable.
 *
 * The notes live OUTSIDE the empty-state branch on purpose. `removedCount` is
 * the usual case now — a selection whose game ended or whose market de-listed
 * is pruned automatically, and saying so is what stops a restored parlay from
 * quietly coming back short. `staleCount` is the fallback: keys we could NOT
 * verify as gone (the board failed to load, or the slate is empty) are left
 * alone, so the user needs a way to clear them by hand.
 */
function SlipBody({
  legs,
  metrics,
  valid,
  staleCount,
  removedCount,
  sport,
  bankroll,
  kelly,
  onRemove,
  onAddCustom,
  onFindPlayers,
  onClear,
  onClearStale,
  editingId,
  onSaved,
}: {
  legs: ParlayLeg[];
  metrics: CorrelatedMetrics;
  valid: boolean;
  staleCount: number;
  removedCount: number;
  sport: string;
  bankroll: number;
  kelly: { multiplier: number; cap: number | null };
  onRemove: (pickId: number) => void;
  onAddCustom: () => void;
  onFindPlayers: () => void;
  onClear: () => void;
  onClearStale: () => void;
  editingId: string | null;
  onSaved: (id: string) => void;
}) {
  // Every leg priced at DraftKings? A Stats line leg DK never posted is not,
  // and four labels below attribute the slip's number to DK only when it is.
  const allDk = legs.every((l) => l.dkPriced !== false);
  // Every leg a Stats line the user chose themselves? Then nothing on this
  // slip is a model's number, and two labels below must not say it is.
  const modelBacked = legs.some((l) => !isLineLeg(l));
  const dkException = useMemo(() => {
    const off = legs.filter((l) => l.dkPriced === false);
    if (off.length === 0) return null;
    return off.map((l) => `${l.label} at ${bookName(l.pricedAt ?? '')}`).join(' and ');
  }, [legs]);
  const staleNote =
    staleCount > 0 ? (
      <Pressable
        onPress={onClearStale}
        style={({ pressed }) => [styles.missingNote, pressed && styles.pressed]}
      >
        <Text style={styles.missingNoteText}>
          {staleCount} selection{staleCount === 1 ? '' : 's'} can't be priced right now · tap to
          remove {staleCount === 1 ? 'it' : 'them'}
        </Text>
      </Pressable>
    ) : removedCount > 0 ? (
      <View style={styles.missingNote}>
        <Text style={styles.missingNoteText}>
          {removedCount} selection{removedCount === 1 ? ' was' : 's were'} removed — the line moved
          or the game started
        </Text>
      </View>
    ) : null;

  if (legs.length === 0) {
    return (
      <View>
        {staleNote}
        <EmptyState
          title="Your betslip is empty"
          subtitle={'Find a player you want to bet and tap "Add to betslip" — you\'ll come right back here. Picks from the Picks tab work too, or enter a custom leg.'}
        />
        <Pressable
          onPress={onFindPlayers}
          style={({ pressed }) => [styles.buildBtn, styles.manualBtn, pressed && styles.pressed]}
        >
          <Ionicons name="search" size={18} color={colors.textInverse} />
          <Text style={styles.buildBtnText}>Find players to add</Text>
        </Pressable>
        <Pressable
          onPress={onAddCustom}
          style={({ pressed }) => [styles.addCustomBtn, styles.manualBtn, pressed && styles.pressed]}
        >
          <Ionicons name="create-outline" size={18} color={colors.tint} />
          <Text style={styles.addCustomBtnText}>Add a custom leg</Text>
        </Pressable>
      </View>
    );
  }

  const stake = parlayRecommendedUnits(metrics, kelly);
  const payout = stake.risk * metrics.decimalPayout;

  return (
    <View>
      {!valid ? (
        <View style={styles.warnBanner}>
          <Ionicons name="warning-outline" size={16} color={colors.med} />
          <Text style={styles.warnText}>
            Two game-line legs from the same game can't be parlayed together — remove one.
          </Text>
        </View>
      ) : null}

      {staleNote}

      <View style={styles.resultCard}>
        <View style={styles.resultHeader}>
          <Text style={styles.resultTitle}>{legs.length}-Leg Play</Text>
          <View style={styles.resultHeaderRight}>
            <GradeBadge grade={metrics.grade} />
            <Text style={styles.resultOdds}>{formatAmerican(metrics.americanOdds)}</Text>
          </View>
        </View>

        <View style={styles.statsRow}>
          <Stat
            label={modelBacked ? 'Model' : 'Implied'}
            value={formatPct(metrics.parlayProb)}
          />
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
          <Stat label={allDk ? 'DK imp.' : 'Implied'} value={formatPct(metrics.dkImpliedProb)} />
        </View>

        <View style={styles.stakeRow}>
          <Stat label="Stake" value={formatStake(stake)} />
          <Stat label="Potential payout" value={formatCurrency(payout)} />
        </View>

        <CorrelatedExtras m={metrics} allDk={allDk} />

        <BetslipBooksRow legs={legs} />

        <LineShopRow lineShop={lineShopParlay(legs, metrics.jointProb, metrics.ev)} dkAmerican={metrics.americanOdds} />

        <ParlayHoldNote ev={metrics.ev} exception={dkException} modelBacked={modelBacked} />

        <View style={styles.legsList}>
          {legs.map((leg) => (
            <ParlayLegCard key={leg.pickId} leg={leg} onRemove={() => onRemove(leg.pickId)} />
          ))}
        </View>

        <ParlayActions
          legs={legs}
          sport={sport}
          editingId={editingId}
          droppedCount={staleCount + removedCount}
          onSaved={onSaved}
        />
      </View>

      <View style={styles.manualActions}>
        <Pressable
          onPress={onFindPlayers}
          style={({ pressed }) => [styles.addCustomBtn, styles.manualBtn, pressed && styles.pressed]}
        >
          <Ionicons name="search" size={18} color={colors.tint} />
          <Text style={styles.addCustomBtnText}>Find more players</Text>
        </Pressable>
        <Pressable
          onPress={onAddCustom}
          style={({ pressed }) => [styles.addCustomBtn, styles.manualBtn, pressed && styles.pressed]}
        >
          <Ionicons name="create-outline" size={18} color={colors.tint} />
          <Text style={styles.addCustomBtnText}>Add a custom leg</Text>
        </Pressable>
        <Pressable
          onPress={onClear}
          style={({ pressed }) => [styles.clearBtn, pressed && styles.pressed]}
        >
          <Ionicons name="trash-outline" size={18} color={colors.avoid} />
          <Text style={styles.clearBtnText}>Clear betslip</Text>
        </Pressable>
      </View>
    </View>
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
    paddingBottom: spacing.xxl,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  // Pinned above the scroll view — the hairline is what keeps a scrolled leg
  // card from reading as part of the title block, so it appears only when
  // there IS something under it (scroll-edge appearance, as the native
  // headers on every other stack screen do).
  headerScrolled: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  titleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  titleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flexShrink: 1,
  },
  closeBtn: {
    marginLeft: -spacing.xs,
    padding: 2,
  },
  countBadge: {
    minWidth: 22,
    height: 22,
    borderRadius: radii.pill,
    paddingHorizontal: 6,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  countBadgeText: {
    color: colors.textInverse,
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
  },
  rightActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  title: {
    // title2 (not largeTitle): this header row now also carries a close
    // chevron, the slip count, Saved and the gear — 34pt crowds them out.
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  savedLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
  },
  savedLinkText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  subtitle: {
    // Leads the scroll view now (it used to sit inside the header), so it owns
    // both the gutter and the gap under the title row.
    paddingHorizontal: spacing.lg,
    marginTop: spacing.md,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  errorBanner: {
    marginTop: spacing.md,
    backgroundColor: colors.avoidSoft,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    borderRadius: 8,
  },
  errorText: {
    color: colors.avoid,
    fontSize: font.size.footnote,
  },
  panelTitle: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: spacing.sm,
    marginTop: spacing.sm,
  },
  buildBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    marginTop: spacing.lg,
  },
  buildBtnDisabled: {
    opacity: 0.4,
  },
  buildBtnText: {
    color: colors.textInverse,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  addCustomBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    marginTop: spacing.sm,
  },
  addCustomBtnText: {
    color: colors.tint,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  manualBtn: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  manualActions: {
    marginBottom: spacing.lg,
  },
  clearBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
  },
  clearBtnText: {
    color: colors.avoid,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  holdNote: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    paddingTop: spacing.sm,
    marginTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  holdNoteBad: {},
  holdNoteText: {
    flex: 1,
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 16,
  },
  holdNoteTextBad: {
    color: colors.avoid,
    fontWeight: font.weight.medium,
  },
  warnBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: '#FFF4E5',
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  warnText: {
    flex: 1,
    color: colors.med,
    fontSize: font.size.footnote,
    fontWeight: font.weight.medium,
  },
  missingNote: {
    backgroundColor: colors.noneSoft,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  missingNoteText: {
    color: colors.textSecondary,
    fontSize: font.size.footnote,
  },
  customInput: {
    backgroundColor: colors.noneSoft,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  customHint: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
  loadingWrap: {
    paddingVertical: spacing.xxl,
    alignItems: 'center',
  },
  resultCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  resultHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  resultTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  resultHeaderRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  resultOdds: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.tint,
  },
  gradeBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.sm,
    borderWidth: StyleSheet.hairlineWidth,
  },
  gradeBadgeSmall: {
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  gradeBadgeText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
  },
  gradeBadgeTextSmall: {
    fontSize: font.size.caption,
  },
  corrExtras: {
    paddingVertical: spacing.sm,
    marginBottom: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    gap: 4,
  },
  corrRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  corrLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  corrValue: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  corrHint: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 2,
  },
  lineShop: {
    paddingVertical: spacing.sm,
    marginBottom: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    gap: 4,
  },
  lineShopHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 2,
  },
  lineShopTitle: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.bet,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  stakeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: spacing.md,
    marginBottom: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
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
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  parlayActions: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  saveBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
  },
  saveBtnText: {
    color: colors.tint,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  dkBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    backgroundColor: DK_GREEN,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
  },
  // The same-game warning is laid out for a full-width row above the actions;
  // here it sits inside the result card, under the button pair.
  updateWarn: {
    marginTop: spacing.sm,
    marginHorizontal: 0,
  },
  handoffFallback: {
    marginTop: spacing.xs,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  dkBtnText: {
    color: '#000',
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  pressed: {
    opacity: 0.6,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: '#00000066',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xxl,
    maxHeight: '70%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  modalTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
});

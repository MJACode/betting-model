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
  useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '@/types';
import { EmptyState } from '@/components/EmptyState';
import { ParlayLegCard } from '@/components/ParlayLegCard';
import { BetslipBooksRow } from '@/components/BetslipBooksRow';
import { InfoTooltip } from '@/components/InfoTooltip';
import { SettingsButton } from '@/components/SettingsButton';
import { showToast } from '@/components/Toast';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { useResolvedSlip } from '@/hooks/useResolvedSlip';
import { isLineLeg } from '@/lib/lineLegs';
import {
  setEditingParlayId,
  setManualCustomLegs,
  useEditingParlayId,
  useManualCustomLegs,
  useSavedParlays,
} from '@/hooks/useSavedParlays';
import { useParlayRestore } from '@/hooks/useParlayRestore';
import { useParlayCorrelations } from '@/hooks/useParlayCorrelations';
import { fetchPlayerTeams } from '@/lib/queries';
import {
  isValidCombo,
  lineShopParlay,
  makeCustomLeg,
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
import { bookLabel, bookName } from '@/lib/markets';
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
  // Module store, not screen state: this screen is popped out from under the
  // user by "Find players to add" and now by a push deep-link, and these legs
  // are hand-typed work with no other copy (see useSavedParlays).
  const manualCustom = useManualCustomLegs();
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
        setManualCustomLegs((prev) => prev.filter((l) => l.pickId !== pickId));
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
    setManualCustomLegs([]);
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
    setManualCustomLegs(restorePending.customLegs);
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
    setManualCustomLegs((prev) => [...prev, makeCustomLeg(customLabel, odds)]);
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
 * Save-for-later, shared by the Optimize result card and the manual builder.
 *
 * IT USED TO CARRY THE BET BUTTON TOO, AND NO LONGER DOES (Matt, 2026-09-08):
 * "why does it say bet DK at the bottom when we give the user the ability to
 * bet with multiple sportsbooks". The green button named ONE book — the
 * member's own, or DraftKings when theirs could not take the slip (his
 * 2026-09-04 call) — 40pt under an "Open with" row that already prices the slip
 * at every bettable book and ranks them by payout. Two controls for one action,
 * and the smaller one was the one that showed the prices.
 *
 * So the tiles ARE the bet button now: tapping one opens the leg-by-leg
 * hand-off sheet for that book, which is exactly what the green button did, at
 * the price the tile is showing. The member picks the book instead of the app
 * picking it for them — which is the guess the preferred-book fallback existed
 * to cover for.
 *
 * Save is a secondary action and now sits with the other slip-level ones below
 * the card, so the card ends on the legs.
 *
 * The slip is still PRICED and modeled at DraftKings (§6) wherever it is
 * placed — the "Priced at DraftKings" note above says so, and the sheet's own
 * odds are the chosen book's.
 */
function ParlaySaveButton({
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
    <Pressable
      onPress={onSave}
      accessibilityRole="button"
      accessibilityLabel={editingId ? 'Update saved parlay' : 'Save parlay'}
      style={({ pressed }) => [styles.gridBtn, styles.outlineBtn, pressed && styles.pressed]}
    >
      <Ionicons
        name={editingId ? 'bookmark' : 'bookmark-outline'}
        size={18}
        color={colors.tint}
      />
      <Text style={styles.gridBtnText} numberOfLines={1}>
        {editingId ? 'Update parlay' : 'Save parlay'}
      </Text>
    </Pressable>
  );
}

/**
 * Honest framing on every parlay: books love parlays because they stack hold
 * (~15-25% vs ~5% on straights). We only build +EV combos, but we say so plainly
 * and warn hard when the combined EV is negative.
 *
 * ONE LINE ON THE CARD, THE REST BEHIND A TAP (Matt, 2026-09-08). This was a
 * five-line paragraph — on a negative slip, five lines of red between the Open
 * with row and the legs, pushing the legs themselves off a small screen. The
 * paragraph was right; its PLACEMENT was the cost. So the claim the reader must
 * not miss stays on the card ("Negative EV — straight bets are better value"),
 * and the reasoning, the hold numbers and the DraftKings pricing note move into
 * the tooltip body.
 *
 * The summary is never a teaser: a reader who never taps "Details" has still
 * been told not to place the slip. That is the test for changing this copy.
 */
function ParlayHoldNote({
  ev,
  exception,
  exceptionCount,
  modelBacked,
}: {
  ev: number;
  exception: string | null;
  /** How many legs `exception` names. The one-line summary has no room for the
   *  legs themselves, and "Where each leg is priced" dropped the very fact it
   *  replaced — that a leg is NOT at DraftKings (UX review). A count fits. */
  exceptionCount: number;
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
  const body = negative
    ? modelBacked
      ? `The books’ parlay hold outweighs the model’s edge here, so this slip prices worse than the straight bets behind it.\n\n${priced}`
      : `These are your own lines at the books’ own prices, so the parlay hold is the whole story — no model edge is offsetting it.\n\n${priced}`
    : modelBacked
      ? `${priced}\n\nParlays also carry far more hold (~15–25%) than straight bets (~5%); this one only clears because the model’s combined probability beats the price.`
      : `${priced}\n\nThese are your own lines, priced at what the book is offering — no model has an opinion on them. Parlays carry far more hold (~15–25%) than straight bets (~5%).`;
  return (
    // The warn tone brings its own tinted panel, so the hairline that separates
    // a footnote from the row above would double as a border on it.
    <View style={negative ? styles.holdNoteWarn : styles.holdNote}>
      <InfoTooltip
        tone={negative ? 'warn' : 'info'}
        title={negative ? 'Negative EV' : 'How this slip is priced'}
        label={
          negative
            ? 'Negative EV — straight bets are better value'
            : exceptionCount > 0
              ? `${exceptionCount} leg${exceptionCount === 1 ? '' : 's'} priced away from DraftKings · parlay hold`
              : 'Priced at DraftKings · parlay hold'
        }
        body={body}
      />
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
        Display-only — the odds above are DraftKings’. Tap that book in “Place this bet at” to
        take its price.
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
  const dkExceptionCount = useMemo(
    () => legs.filter((l) => l.dkPriced === false).length,
    [legs],
  );
  // Past ~1.3 the two-up grid's fixed 45% cells are narrower than their own
  // labels, so it stacks instead of truncating them (UX review).
  const { fontScale } = useWindowDimensions();
  const stacked = fontScale > 1.3;
  // Clearing destroys the hand-typed custom legs, which exist nowhere else, and
  // there is no undo behind it — so it asks, the way the dropping-legs save does.
  const confirmClear = useCallback(() => {
    Alert.alert(
      'Clear your betslip?',
      'This removes every selection, including any legs you entered by hand. It can’t be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Clear', style: 'destructive', onPress: onClear },
      ],
    );
  }, [onClear]);
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

        {/* The staleness caveat has to follow the leg to the screen the bet is
            placed from, not stay on the board it was picked off. One line, and
            only when a live leg is actually in the slip. */}
        {legs.some((l) => l.isLive) ? (
          <View style={styles.liveLegNote}>
            <Ionicons name="alert-circle-outline" size={16} color={colors.med} />
            <Text style={styles.liveLegNoteText}>
              This slip has an in-play leg. Live prices are DraftKings’ and can be up to
              ~45s old — check the number at DK before you place it.
            </Text>
          </View>
        ) : null}

        {/* A NEGATIVE-EV WARNING GOES ABOVE THE BET CONTROL, NEVER BELOW IT
            (UX review, 2026-09-08). It used to sit below because the bet
            control was a button under the legs; now the book tiles are the bet
            control, and leaving the note under them let a member read the
            payout, tap a tile and reach the hand-off sheet — which says nothing
            about EV — with the warning never on screen. The "EV −0.0%" stat
            above is a number, not a recommendation.

            The non-negative note keeps its old slot: it is a pricing footnote,
            and hoisting it would put a paragraph between the payout and the
            books for no gain. */}
        {metrics.ev < 0 ? (
          <ParlayHoldNote
            ev={metrics.ev}
            exception={dkException}
            exceptionCount={dkExceptionCount}
            modelBacked={modelBacked}
          />
        ) : null}

        <BetslipBooksRow legs={legs} />

        <LineShopRow lineShop={lineShopParlay(legs, metrics.jointProb, metrics.ev)} dkAmerican={metrics.americanOdds} />

        {metrics.ev >= 0 ? (
          <ParlayHoldNote
            ev={metrics.ev}
            exception={dkException}
            exceptionCount={dkExceptionCount}
            modelBacked={modelBacked}
          />
        ) : null}

        <View style={styles.legsList}>
          {legs.map((leg) => (
            <ParlayLegCard key={leg.pickId} leg={leg} onRemove={() => onRemove(leg.pickId)} />
          ))}
        </View>
      </View>

      {/* The loss, stated before the tap: updating writes the shorter slip over
          the save, and there is no undo. Shaped like the same-game warning
          above, because colour alone is not a signal — colors.med measures
          2.20:1 here, half the AA floor, so the tint, the icon and the wording
          all have to carry it. Above the grid, not inside it: a full-width
          banner as a fifth grid cell splits the two rows apart. */}
      {editingId && staleCount + removedCount > 0 ? (
        <View style={styles.warnBanner}>
          <Ionicons name="warning-outline" size={16} color={colors.med} />
          <Text style={styles.warnText}>
            {staleCount + removedCount} leg{staleCount + removedCount === 1 ? '' : 's'}{' '}
            {staleCount + removedCount === 1 ? 'is' : 'are'} no longer on the board —
            “Update parlay” saves this slip without{' '}
            {staleCount + removedCount === 1 ? 'it' : 'them'}.
          </Text>
        </View>
      ) : null}

      {/* Two-up, not four stacked full-width rows. These are the slip's
          SECONDARY actions — the bet itself is the book row inside the card —
          and four of them stacked was ~200pt of chrome under a card the user is
          trying to read. Save joined them when the green bet button left (Matt,
          2026-09-08); at half width three fit in the height two used to take.

          ONE COLUMN ONCE THE TYPE GROWS (UX review). `flexBasis: '45%'` does not
          respond to fontScale, so at XXXL "Update parlay" is wider than its cell
          and every label collapses at accessibility sizes. Past 1.3 the grid
          gives up and stacks, which is what the labels were shortened to avoid
          having to do at the DEFAULT size. */}
      <View style={[styles.manualActions, stacked && styles.manualActionsStacked]}>
        <ParlaySaveButton
          legs={legs}
          sport={sport}
          editingId={editingId}
          droppedCount={staleCount + removedCount}
          onSaved={onSaved}
        />
        <Pressable
          onPress={onFindPlayers}
          accessibilityRole="button"
          style={({ pressed }) => [styles.gridBtn, styles.outlineBtn, pressed && styles.pressed]}
        >
          <Ionicons name="search" size={18} color={colors.tint} />
          <Text style={styles.gridBtnText}>Find players</Text>
        </Pressable>
        <Pressable
          onPress={onAddCustom}
          accessibilityRole="button"
          style={({ pressed }) => [styles.gridBtn, styles.outlineBtn, pressed && styles.pressed]}
        >
          <Ionicons name="create-outline" size={18} color={colors.tint} />
          <Text style={styles.gridBtnText}>Custom leg</Text>
        </Pressable>
      </View>

      {/* CLEAR IS NOT A PEER OF THE THREE ABOVE (UX review). In the grid it was
          the same size and shape as "Custom leg" and sat bottom-right, under a
          right thumb — and `handleClear` wipes the slip, the Stats line legs and
          the hand-typed custom legs, which have no other copy, with no undo.
          Its own row, and it asks first: the same Alert shape Save already uses
          before an update that drops legs. */}
      <Pressable
        onPress={confirmClear}
        accessibilityRole="button"
        accessibilityLabel="Clear betslip"
        style={({ pressed }) => [styles.clearBtn, pressed && styles.pressed]}
      >
        <Ionicons name="trash-outline" size={18} color={colors.avoid} />
        <Text style={styles.clearBtnText}>Clear betslip</Text>
      </Pressable>
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
  // Two-up grid for the slip's secondary actions. `flexBasis` with a gap
  // rather than a percentage width: '48%' plus a gap overflows at the
  // narrowest widths, and a fifth cell would silently start a third row.
  manualActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    marginBottom: spacing.lg,
  },
  manualActionsStacked: {
    flexDirection: 'column',
  },
  gridBtn: {
    flexGrow: 1,
    flexBasis: '45%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    // spacing.md x2 + a ~19pt line is 43pt — one point under the floor, and
    // these are half-width now, so the whole target has roughly halved.
    minHeight: 44,
  },
  // No numberOfLines cap on the label: a half-width cell that cannot grow must
  // at least be allowed to wrap (UX review).
  gridBtnText: {
    flexShrink: 1,
    textAlign: 'center',
    color: colors.tint,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  outlineBtn: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
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
  // No vertical padding of its own — InfoTooltip's summary row carries it, so
  // the note is one 44pt-class tap target rather than a rule plus a paragraph.
  holdNote: {
    marginTop: spacing.xs,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  holdNoteWarn: {},
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
  liveLegNote: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  // Amber as the icon, dark text for the sentence: colors.med is 1.97:1 on the
  // page ground and this is a disclosure, not decoration.
  liveLegNoteText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  legsList: {
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
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

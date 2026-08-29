import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  ActivityIndicator,
  FlatList,
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
import { SportToggle } from '@/components/SportToggle';
import { SettingsButton } from '@/components/SettingsButton';
import { showToast } from '@/components/Toast';
import { betOnBookLabel, bookButtonColors, DK_GREEN } from '@/lib/sportsbookLinks';
import { usePreferredBook } from '@/hooks/usePreferredBook';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useSavedParlays } from '@/hooks/useSavedParlays';
import { useParlayRestore } from '@/hooks/useParlayRestore';
import { useParlayCorrelations } from '@/hooks/useParlayCorrelations';
import { fetchPlayerTeams } from '@/lib/queries';
import {
  addLeg,
  applySwap,
  buildCandidatePool,
  computeParlayMetrics,
  handoffBookFor,
  isValidCombo,
  lineShopParlay,
  makeCustomLeg,
  matchupForLeg,
  MAX_LEGS,
  MIN_LEGS,
  optimizeParlay,
  parlayRecommendedUnits,
  removeLeg,
  resolveSlipLegs,
  swapCandidatesFor,
  type LineShop,
  type Parlay,
  type ParlayConstraints,
  type ParlayLeg,
  type ParlayResult,
  type ParlayStyle,
} from '@/lib/parlay';
import { formatStake, formatUnits } from '@/lib/thresholds';
import {
  computeCorrelatedMetrics,
  GRADE_LABEL,
  type CorrelatedMetrics,
  type ParlayGrade,
} from '@/lib/parlayCorrelation';
import {
  findSameGameParlays,
  type SgpCandidate,
  type SgpFinderResult,
} from '@/lib/sgpFinder';
import { modelShort } from '@/lib/modelMeta';
import { bookLabel } from '@/lib/markets';
import {
  americanToDecimal,
  formatAmerican,
  formatCurrency,
  formatPct,
  formatPctSigned,
} from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';

type ParlayNav = NativeStackNavigationProp<RootStackParamList>;

const STYLE_OPTIONS: { key: ParlayStyle; label: string }[] = [
  { key: 'favorites', label: 'Favorites' },
  { key: 'balanced', label: 'Balanced' },
  { key: 'underdog', label: 'Underdog' },
];

/** Parse an American-odds text field to a number, or null when blank/invalid. */
function parseAmerican(text: string): number | null {
  const t = text.trim();
  if (!t) return null;
  const n = Number(t.replace(/^\+/, ''));
  if (!Number.isFinite(n) || n === 0) return null;
  return n;
}

type BuildMode = 'optimize' | 'sgp' | 'manual';

const MODE_LABEL: Record<BuildMode, string> = {
  optimize: 'Optimize',
  sgp: 'Same-game',
  manual: 'Your slip',
};

export function ParlayScreen() {
  const navigation = useNavigation<ParlayNav>();
  const { data, loading, error, refresh } = useTodayPicks();
  const { sport } = useSportFilter();
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);
  const slip = useParlaySlip();
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

  const [mode, setMode] = useState<BuildMode>('optimize');
  // Session-only hand-entered legs for the manual builder (not persisted — same
  // as the auto builder's custom legs).
  const [manualCustom, setManualCustom] = useState<ParlayLeg[]>([]);

  const [legs, setLegs] = useState<number>(3);
  const [style, setStyle] = useState<ParlayStyle>('balanced');
  const [minText, setMinText] = useState<string>('');
  const [maxText, setMaxText] = useState<string>('');

  const [built, setBuilt] = useState<ParlayResult | null>(null);
  const [working, setWorking] = useState<Parlay | null>(null);
  const [swapTarget, setSwapTarget] = useState<number | null>(null);

  // Custom-leg form: null = closed; 'add' = append (auto); 'swap' = replace a
  // slot (auto); 'manual-add' = append to the manual builder.
  const [customForm, setCustomForm] = useState<
    { mode: 'add' } | { mode: 'manual-add' } | { mode: 'swap'; replacePickId: number } | null
  >(null);
  const [customLabel, setCustomLabel] = useState<string>('');
  const [customOddsText, setCustomOddsText] = useState<string>('');

  const pool = useMemo(() => buildCandidatePool(data, sport), [data, sport]);

  // Same-game finder — only computed in 'sgp' mode (the copula MC is bounded but
  // non-trivial). Recomputes when picks refresh or team resolution lands.
  const sgp: SgpFinderResult | null = useMemo(
    () => (mode === 'sgp' ? findSameGameParlays(pool, rho, { resolveTeam }) : null),
    [mode, pool, rho, resolveTeam],
  );

  // Load a surfaced SGP into "Build your own" for editing. Every SGP leg is a
  // real pick (positive id), so the slip + resolveSlipLegs round-trips cleanly.
  const handleEditSgp = useCallback(
    (legsToEdit: ParlayLeg[]) => {
      slip.clear();
      legsToEdit.forEach((l) => slip.add(l.slipKey));
      setManualCustom([]);
      setMode('manual');
    },
    [slip],
  );

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

  // ── Manual builder ──────────────────────────────────────────────────────
  // Resolve the persisted slip against today's picks (cross-sport, any signal),
  // then append session custom legs. Recomputed whenever picks or the slip move.
  const { legs: slipLegs, missingKeys } = useMemo(
    () => resolveSlipLegs(data, slip.keys),
    [data, slip.keys],
  );
  const manualLegs = useMemo(() => [...slipLegs, ...manualCustom], [slipLegs, manualCustom]);
  const manualMetrics = useMemo(
    () => computeCorrelatedMetrics(manualLegs, rho, resolveTeam),
    [manualLegs, rho, resolveTeam],
  );
  const manualValid = useMemo(() => isValidCombo(manualLegs), [manualLegs]);

  const handleManualRemove = useCallback(
    (pickId: number) => {
      if (pickId < 0) {
        setManualCustom((prev) => prev.filter((l) => l.pickId !== pickId));
        return;
      }
      // Map the (session) pickId back to its stable slip key to remove it.
      const leg = slipLegs.find((l) => l.pickId === pickId);
      if (leg) slip.remove(leg.slipKey);
    },
    [slip, slipLegs],
  );

  const handleManualClear = useCallback(() => {
    slip.clear();
    setManualCustom([]);
  }, [slip]);

  const handleClearStale = useCallback(() => {
    missingKeys.forEach((key) => slip.remove(key));
  }, [missingKeys, slip]);

  const openManualCustom = useCallback(() => {
    setCustomLabel('');
    setCustomOddsText('');
    setCustomForm({ mode: 'manual-add' });
  }, []);

  // Send the user to the Stats tab to browse players; adding one brings them
  // back here automatically (fromParlay flag handled in StatsScreen). This
  // screen is pushed over the tabs, so navigating to Tabs pops it — the return
  // trip pushes a fresh one, which is also what re-opens it on the slip.
  const goFindPlayers = useCallback(() => {
    navigation.navigate('Tabs', { screen: 'Stats', params: { fromParlay: true } });
  }, [navigation]);

  // Open straight onto the user's slip when it already has selections — a user
  // who tapped "Add to betslip" elsewhere lands on their slip, not the
  // optimizer. Runs once, after the persisted slip has loaded.
  const autoOpenedSlip = useRef(false);
  useEffect(() => {
    if (autoOpenedSlip.current || !slip.ready) return;
    autoOpenedSlip.current = true;
    if (slip.count > 0) setMode('manual');
  }, [slip.ready, slip.count]);

  // MLB and WNBA share no picks — clear any built parlay when the sport changes.
  useEffect(() => {
    setBuilt(null);
    setWorking(null);
    setSwapTarget(null);
    setCustomForm(null);
  }, [sport]);

  // Restore a saved parlay into "Build your own" (from the Saved Parlays screen).
  // Real pick_ids re-resolve against today's picks via the slip; reconstructed
  // custom/stale legs seed the session state directly.
  useEffect(() => {
    if (!restorePending) return;
    slip.clear();
    restorePending.slipKeys.forEach((key) => slip.add(key));
    setManualCustom(restorePending.customLegs);
    setMode('manual');
    consumeRestore();
  }, [restorePending]); // eslint-disable-line react-hooks/exhaustive-deps

  // Don't let the user request more legs than the pool can supply.
  const maxLegs = Math.min(MAX_LEGS, Math.max(MIN_LEGS, pool.length));
  useEffect(() => {
    if (legs > maxLegs) setLegs(maxLegs);
  }, [maxLegs, legs]);

  const constraints: ParlayConstraints = useMemo(
    () => ({
      legs,
      style,
      minAmerican: parseAmerican(minText),
      maxAmerican: parseAmerican(maxText),
    }),
    [legs, style, minText, maxText],
  );

  const handleBuild = useCallback(() => {
    const result = optimizeParlay(pool, constraints, rho, resolveTeam);
    setBuilt(result);
    setWorking(result.best);
    setSwapTarget(null);
  }, [pool, constraints, rho, resolveTeam]);

  const handleRemove = useCallback((pickId: number) => {
    setWorking((prev) => (prev ? removeLeg(prev, pickId) : prev));
  }, []);

  // Correlated metrics for the live working parlay (recomputed after edits/swaps,
  // since removeLeg/applySwap only refresh the independent metrics).
  const workingCorrelated = useMemo(
    () => (working ? computeCorrelatedMetrics(working.legs, rho, resolveTeam) : null),
    [working, rho, resolveTeam],
  );

  const swapCandidates: ParlayLeg[] = useMemo(() => {
    if (working == null || swapTarget == null) return [];
    return swapCandidatesFor(working, pool, swapTarget, constraints);
  }, [working, pool, swapTarget, constraints]);

  const handleSwapPick = useCallback(
    (leg: ParlayLeg) => {
      setWorking((prev) => (prev && swapTarget != null ? applySwap(prev, swapTarget, leg) : prev));
      setSwapTarget(null);
    },
    [swapTarget],
  );

  const openCustomAdd = useCallback(() => {
    setCustomLabel('');
    setCustomOddsText('');
    setCustomForm({ mode: 'add' });
  }, []);

  // From the swap sheet: replace the targeted slot with a custom leg.
  const openCustomSwap = useCallback(() => {
    if (swapTarget == null) return;
    const replacePickId = swapTarget;
    setSwapTarget(null);
    setCustomLabel('');
    setCustomOddsText('');
    setCustomForm({ mode: 'swap', replacePickId });
  }, [swapTarget]);

  const closeCustomForm = useCallback(() => setCustomForm(null), []);

  const customOdds = parseAmerican(customOddsText);
  const customValid = customLabel.trim().length > 0 && customOdds != null;
  const customImpliedPct =
    customOdds != null ? 1 / americanToDecimal(customOdds) : null;

  const handleSaveCustom = useCallback(() => {
    const odds = parseAmerican(customOddsText);
    if (customLabel.trim().length === 0 || odds == null || customForm == null) return;
    const leg = makeCustomLeg(customLabel, odds);
    if (customForm.mode === 'manual-add') {
      setManualCustom((prev) => [...prev, leg]);
    } else if (customForm.mode === 'add') {
      setWorking((prev) =>
        prev ? addLeg(prev, leg) : { legs: [leg], metrics: computeParlayMetrics([leg]) },
      );
    } else {
      const replacePickId = customForm.replacePickId;
      setWorking((prev) => (prev ? applySwap(prev, replacePickId, leg) : prev));
    }
    setCustomLabel('');
    setCustomOddsText('');
    setCustomForm(null);
  }, [customForm, customLabel, customOddsText]);

  const stepperDisabledMinus = legs <= MIN_LEGS;
  const stepperDisabledPlus = legs >= maxLegs;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}
      >
        <View style={styles.header}>
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
              {slip.count > 0 ? (
                <View style={styles.countBadge}>
                  <Text style={styles.countBadgeText}>{slip.count}</Text>
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
          <Text style={styles.subtitle}>
            {mode === 'optimize'
              ? `${pool.length} eligible BET leg${pool.length === 1 ? '' : 's'} today · highest-EV combo`
              : mode === 'sgp'
                ? 'Same-game parlays, priced on leg correlation · +EV only'
                : `${manualLegs.length} leg${manualLegs.length === 1 ? '' : 's'} in your betslip · add from the Stats or Picks tab`}
          </Text>
          <View style={styles.modeToggle}>
            {(['optimize', 'sgp', 'manual'] as BuildMode[]).map((m) => {
              const active = m === mode;
              return (
                <Pressable
                  key={m}
                  onPress={() => setMode(m)}
                  style={({ pressed }) => [
                    styles.segment,
                    active && styles.segmentActive,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text
                    style={[styles.segmentLabel, active && styles.segmentLabelActive]}
                    numberOfLines={1}
                  >
                    {MODE_LABEL[m]}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          {mode !== 'manual' ? <SportToggle /> : null}
        </View>

        {error ? (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>Connection error: {error}</Text>
          </View>
        ) : null}

        {mode === 'manual' ? (
          <ManualBuilder
            legs={manualLegs}
            metrics={manualMetrics}
            valid={manualValid}
            missingCount={missingKeys.length}
            sport={manualLegs[0]?.pick?.sport ?? sport}
            bankroll={bankroll}
            kelly={kelly}
            onRemove={handleManualRemove}
            onAddCustom={openManualCustom}
            onFindPlayers={goFindPlayers}
            onClear={handleManualClear}
            onClearStale={handleClearStale}
          />
        ) : mode === 'sgp' ? (
          <SgpFinderView
            result={sgp}
            loading={loading && data.length === 0}
            sport={sport}
            bankroll={bankroll}
            kelly={kelly}
            onEdit={handleEditSgp}
          />
        ) : (
        <>
        {/* ── Constraints ───────────────────────────────────────────── */}
        <View style={styles.panel}>
          <Text style={styles.panelTitle}>Legs</Text>
          <View style={styles.stepperRow}>
            <Pressable
              onPress={() => setLegs((n) => Math.max(MIN_LEGS, n - 1))}
              disabled={stepperDisabledMinus}
              style={({ pressed }) => [
                styles.stepBtn,
                stepperDisabledMinus && styles.stepBtnDisabled,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons name="remove" size={22} color={colors.tint} />
            </Pressable>
            <Text style={styles.stepValue}>{legs}</Text>
            <Pressable
              onPress={() => setLegs((n) => Math.min(maxLegs, n + 1))}
              disabled={stepperDisabledPlus}
              style={({ pressed }) => [
                styles.stepBtn,
                stepperDisabledPlus && styles.stepBtnDisabled,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons name="add" size={22} color={colors.tint} />
            </Pressable>
          </View>

          <Text style={styles.panelTitle}>Style</Text>
          <View style={styles.segmented}>
            {STYLE_OPTIONS.map((opt) => {
              const active = opt.key === style;
              return (
                <Pressable
                  key={opt.key}
                  onPress={() => setStyle(opt.key)}
                  style={({ pressed }) => [
                    styles.segment,
                    active && styles.segmentActive,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={[styles.segmentLabel, active && styles.segmentLabelActive]}>
                    {opt.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          <Text style={styles.panelTitle}>Target odds range (American)</Text>
          <View style={styles.oddsRow}>
            <TextInput
              style={styles.oddsInput}
              value={minText}
              onChangeText={setMinText}
              placeholder="Min (e.g. +200)"
              placeholderTextColor={colors.textTertiary}
              keyboardType="numbers-and-punctuation"
              returnKeyType="done"
            />
            <Text style={styles.oddsDash}>–</Text>
            <TextInput
              style={styles.oddsInput}
              value={maxText}
              onChangeText={setMaxText}
              placeholder="Max (e.g. +2000)"
              placeholderTextColor={colors.textTertiary}
              keyboardType="numbers-and-punctuation"
              returnKeyType="done"
            />
          </View>

          <Pressable
            onPress={handleBuild}
            disabled={pool.length < MIN_LEGS}
            style={({ pressed }) => [
              styles.buildBtn,
              pool.length < MIN_LEGS && styles.buildBtnDisabled,
              pressed && styles.pressed,
            ]}
          >
            <Ionicons name="layers-outline" size={18} color={colors.textInverse} />
            <Text style={styles.buildBtnText}>Build optimal parlay</Text>
          </Pressable>

          <Pressable
            onPress={openCustomAdd}
            style={({ pressed }) => [styles.addCustomBtn, pressed && styles.pressed]}
          >
            <Ionicons name="create-outline" size={18} color={colors.tint} />
            <Text style={styles.addCustomBtnText}>Add a custom leg</Text>
          </Pressable>
        </View>

        {/* ── Result ────────────────────────────────────────────────── */}
        {loading && !built ? (
          <View style={styles.loadingWrap}>
            <ActivityIndicator />
          </View>
        ) : null}

        {working && working.legs.length >= MIN_LEGS && workingCorrelated ? (
          <ResultCard
            parlay={working}
            metrics={workingCorrelated}
            sport={sport}
            bankroll={bankroll}
            kelly={kelly}
            onRemove={handleRemove}
            onSwap={(pickId) => setSwapTarget(pickId)}
          />
        ) : null}

        {working && working.legs.length < MIN_LEGS ? (
          <EmptyState
            title="Too few legs"
            subtitle={`A parlay needs at least ${MIN_LEGS} legs. Rebuild, or tap "Add a custom leg" to enter one.`}
          />
        ) : null}

        {built && !built.best ? <ReasonState result={built} sport={sport} legs={legs} /> : null}

        {/* ── Alternatives ──────────────────────────────────────────── */}
        {built && built.alternatives.length > 0 ? (
          <View style={styles.altSection}>
            <Text style={styles.altHeading}>Alternatives</Text>
            {built.alternatives.map((alt) => {
              const am = alt.correlated ?? alt.metrics;
              return (
                <Pressable
                  key={alt.legs.map((l) => l.pickId).join('-')}
                  onPress={() => setWorking(alt)}
                  style={({ pressed }) => [styles.altCard, pressed && styles.pressed]}
                >
                  <View style={styles.altCardBody}>
                    <View style={styles.altCardTitleRow}>
                      {alt.correlated ? <GradeBadge grade={alt.correlated.grade} small /> : null}
                      <Text style={styles.altCardTitle}>
                        {alt.legs.length}-leg · {formatAmerican(am.americanOdds)}
                      </Text>
                    </View>
                    <Text style={styles.altCardLegs} numberOfLines={1}>
                      {alt.legs.map((l) => modelShort(l.modelId)).join(' + ')}
                    </Text>
                  </View>
                  <Text style={[styles.altCardEv, { color: am.ev >= 0 ? colors.bet : colors.avoid }]}>
                    EV {formatPctSigned(am.ev)}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        ) : null}
        </>
        )}
      </ScrollView>

      {/* ── Swap modal ──────────────────────────────────────────────── */}
      <Modal
        visible={swapTarget != null}
        animationType="slide"
        transparent
        onRequestClose={() => setSwapTarget(null)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Swap leg</Text>
              <Pressable onPress={() => setSwapTarget(null)} hitSlop={8}>
                <Ionicons name="close" size={24} color={colors.textSecondary} />
              </Pressable>
            </View>
            <Pressable
              onPress={openCustomSwap}
              style={({ pressed }) => [styles.customRow, pressed && styles.pressed]}
            >
              <Ionicons name="create-outline" size={18} color={colors.tint} />
              <Text style={styles.customRowText}>Enter your own pick</Text>
            </Pressable>
            {swapCandidates.length === 0 ? (
              <Text style={styles.modalEmpty}>No model legs to swap in — enter your own above.</Text>
            ) : (
              <FlatList
                data={swapCandidates}
                keyExtractor={(l) => String(l.pickId)}
                renderItem={({ item }) => (
                  <Pressable
                    onPress={() => handleSwapPick(item)}
                    style={({ pressed }) => [styles.modalRow, pressed && styles.pressed]}
                  >
                    <View style={styles.modalRowBody}>
                      <Text style={styles.modalRowLabel} numberOfLines={1}>
                        {item.label}
                      </Text>
                      <Text style={styles.modalRowMeta}>
                        {modelShort(item.modelId)} · {formatPct(item.modelProb)} ·{' '}
                        {formatAmerican(item.americanOdds)}
                      </Text>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
                  </Pressable>
                )}
                style={styles.modalList}
              />
            )}
          </View>
        </View>
      </Modal>

      {/* ── Custom-leg form ─────────────────────────────────────────── */}
      <Modal
        visible={customForm != null}
        animationType="slide"
        transparent
        onRequestClose={closeCustomForm}
      >
        {/* Without this the keyboard slides up OVER the bottom sheet and hides
            the inputs entirely — the sheet must rise with the keyboard. */}
        <KeyboardAvoidingView
          style={styles.modalBackdrop}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>
                {customForm?.mode === 'swap' ? 'Replace leg' : 'Custom leg'}
              </Text>
              <Pressable onPress={closeCustomForm} hitSlop={8}>
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
              <Text style={styles.buildBtnText}>
                {customForm?.mode === 'swap' ? 'Replace leg' : 'Add leg'}
              </Text>
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

function ReasonState({
  result,
  sport,
  legs,
}: {
  result: ParlayResult;
  sport: string;
  legs: number;
}) {
  if (result.reason === 'no_eligible') {
    return (
      <EmptyState
        title={`No ${sport} BET signals today`}
        subtitle="A parlay is built from today's BET picks. Check back after the next refresh."
      />
    );
  }
  if (result.reason === 'no_combo_in_range') {
    return (
      <EmptyState
        title="No parlay fits that odds range"
        subtitle="Widen the min/max odds and build again."
      />
    );
  }
  // too_few_legs
  return (
    <EmptyState
      title="Not enough eligible legs"
      subtitle={`Only ${result.poolSize} eligible leg${result.poolSize === 1 ? '' : 's'} — lower the leg count (you asked for ${legs}) or wait for more picks.`}
    />
  );
}

function ResultCard({
  parlay,
  metrics,
  sport,
  bankroll,
  kelly,
  onRemove,
  onSwap,
}: {
  parlay: Parlay;
  metrics: CorrelatedMetrics;
  sport: string;
  bankroll: number;
  kelly: { multiplier: number; cap: number | null };
  onRemove: (pickId: number) => void;
  onSwap: (pickId: number) => void;
}) {
  const m = metrics;
  const stake = parlayRecommendedUnits(m, kelly);
  const payout = stake.risk * m.decimalPayout;
  return (
    <View style={styles.resultCard}>
      <View style={styles.resultHeader}>
        <Text style={styles.resultTitle}>{parlay.legs.length}-Leg Parlay</Text>
        <View style={styles.resultHeaderRight}>
          <GradeBadge grade={m.grade} />
          <Text style={styles.resultOdds}>{formatAmerican(m.americanOdds)}</Text>
        </View>
      </View>

      <View style={styles.statsRow}>
        <Stat label="Model" value={formatPct(m.parlayProb)} />
        <Stat
          label="EV"
          value={formatPctSigned(m.ev)}
          color={m.ev >= 0 ? colors.bet : colors.avoid}
        />
        <Stat
          label="Edge"
          value={formatPctSigned(m.edgeVsDk)}
          color={m.edgeVsDk >= 0 ? colors.bet : colors.avoid}
        />
        <Stat label="DK imp." value={formatPct(m.dkImpliedProb)} />
      </View>

      <View style={styles.stakeRow}>
        <Stat label="Stake" value={formatStake(stake)} />
        <Stat label="Potential payout" value={formatCurrency(payout)} />
      </View>

      <CorrelatedExtras m={m} />

      <BetslipBooksRow legs={parlay.legs} />

      <LineShopRow lineShop={lineShopParlay(parlay.legs, m.jointProb, m.ev)} dkAmerican={m.americanOdds} />

      <ParlayHoldNote ev={m.ev} />

      <View style={styles.legsList}>
        {parlay.legs.map((leg) => (
          <ParlayLegCard
            key={leg.pickId}
            leg={leg}
            onRemove={() => onRemove(leg.pickId)}
            onSwap={() => onSwap(leg.pickId)}
          />
        ))}
      </View>

      <ParlayActions legs={parlay.legs} sport={sport} />
    </View>
  );
}

/**
 * Save-for-later + sportsbook hand-off, shared by the Optimize result card and
 * the manual builder. The hand-off goes to the USER'S book when it prices every
 * leg (with that book's own betslip links), falling back to DraftKings — the
 * button label always names the book it actually opens. No book has a multi-leg
 * deep link, so it opens a leg-by-leg hand-off sheet.
 */
function ParlayActions({ legs, sport }: { legs: ParlayLeg[]; sport: string }) {
  const { save } = useSavedParlays();
  const { book: preferredBook } = usePreferredBook();
  const [handoffOpen, setHandoffOpen] = useState(false);

  const handoff = useMemo(() => handoffBookFor(legs, preferredBook), [legs, preferredBook]);
  const btnColors = bookButtonColors(handoff.book);

  const handoffLegs: HandoffLeg[] = useMemo(
    () =>
      legs.map((l, i) => ({
        key: String(l.pickId),
        label: l.label,
        matchup: matchupForLeg(l.game),
        americanOdds: l.americanOdds,
        betLink: handoff.links[i] ?? null,
      })),
    [legs, handoff],
  );

  const onSave = useCallback(() => {
    save(legs, sport);
    showToast('Saved · find it under “Saved” at the top of your betslip');
  }, [save, legs, sport]);

  if (legs.length === 0) return null;

  return (
    <View style={styles.parlayActions}>
      <Pressable onPress={onSave} style={({ pressed }) => [styles.saveBtn, pressed && styles.pressed]}>
        <Ionicons name="bookmark-outline" size={18} color={colors.tint} />
        <Text style={styles.saveBtnText}>Save parlay</Text>
      </Pressable>
      <Pressable
        onPress={() => setHandoffOpen(true)}
        style={({ pressed }) => [
          styles.dkBtn,
          { backgroundColor: btnColors.bg },
          pressed && styles.pressed,
        ]}
      >
        <Ionicons name="open-outline" size={18} color={btnColors.fg} />
        <Text style={[styles.dkBtnText, { color: btnColors.fg }]}>
          {betOnBookLabel(handoff.book)}
        </Text>
      </Pressable>

      <ParlayDkHandoff
        visible={handoffOpen}
        legs={handoffLegs}
        book={handoff.book}
        onClose={() => setHandoffOpen(false)}
      />
    </View>
  );
}

/**
 * Honest framing on every parlay: books love parlays because they stack hold
 * (~15-25% vs ~5% on straights). We only build +EV combos, but we say so plainly
 * and warn hard when the combined EV is negative.
 */
function ParlayHoldNote({ ev }: { ev: number }) {
  const negative = ev < 0;
  return (
    <View style={[styles.holdNote, negative && styles.holdNoteBad]}>
      <Ionicons
        name={negative ? 'warning-outline' : 'information-circle-outline'}
        size={14}
        color={negative ? colors.avoid : colors.textTertiary}
      />
      <Text style={[styles.holdNoteText, negative && styles.holdNoteTextBad]}>
        {negative
          ? 'Negative EV — the books’ parlay hold outweighs the model’s edge here. Straight bets are the better value. Legs are priced at DraftKings.'
          : 'Every leg is priced at DraftKings — that’s the book the models score against, whichever book you bet at. Parlays also carry far more hold (~15–25%) than straight bets (~5%); this one only clears because the model’s combined probability beats DK’s price.'}
      </Text>
    </View>
  );
}

const GRADE_COLOR: Record<ParlayGrade, string> = {
  great: colors.bet,
  good: colors.tint,
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
function CorrelatedExtras({ m }: { m: CorrelatedMetrics }) {
  const holdPositive = m.dkHoldPct >= 0;
  return (
    <View style={styles.corrExtras}>
      <View style={styles.corrRow}>
        <Text style={styles.corrLabel}>Fair odds</Text>
        <Text style={styles.corrValue}>
          {formatAmerican(m.fairAmerican)} · DK {formatAmerican(m.americanOdds)}
        </Text>
      </View>
      <View style={styles.corrRow}>
        <Text style={styles.corrLabel}>{holdPositive ? 'DK hold on this slip' : 'Your edge on this slip'}</Text>
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
 * Same-game parlay finder view. Surfaces the slate's best +EV same-game combos —
 * the legs whose correlation the books mis-price. Read-only suggestion cards with
 * save / DK hand-off / "edit in builder" actions.
 */
function SgpFinderView({
  result,
  loading,
  sport,
  bankroll,
  kelly,
  onEdit,
}: {
  result: SgpFinderResult | null;
  loading: boolean;
  sport: string;
  bankroll: number;
  kelly: { multiplier: number; cap: number | null };
  onEdit: (legs: ParlayLeg[]) => void;
}) {
  // The same-game explainer is dismissible and stays dismissed (persisted).
  const [introDismissed, setIntroDismissed] = useState(false);
  useEffect(() => {
    AsyncStorage.getItem('sgpIntroDismissed.v1')
      .then((v) => { if (v === '1') setIntroDismissed(true); })
      .catch(() => {});
  }, []);
  const dismissIntro = useCallback(() => {
    setIntroDismissed(true);
    AsyncStorage.setItem('sgpIntroDismissed.v1', '1').catch(() => {});
  }, []);
  const intro = introDismissed ? null : <SgpIntro onDismiss={dismissIntro} />;

  if (loading || result == null) {
    return (
      <View style={styles.loadingWrap}>
        <ActivityIndicator />
      </View>
    );
  }

  if (result.candidates.length === 0) {
    return (
      <View>
        {intro}
        {result.reason === 'no_eligible' ? (
          <EmptyState
            title={`No same-game ${sport} sets today`}
            subtitle="A same-game parlay needs at least two BET legs in one game. Check back after the next refresh."
          />
        ) : (
          <EmptyState
            title="No +EV same-game parlay today"
            subtitle={`Looked across ${result.gamesConsidered} game${result.gamesConsidered === 1 ? '' : 's'} — none clear DK's parlay hold once leg correlation is priced in. That's a valid result: most same-game parlays are −EV.`}
          />
        )}
      </View>
    );
  }

  return (
    <View>
      {intro}
      {result.candidates.map((c) => (
        <SgpCard
          key={c.legs.map((l) => l.pickId).join('-')}
          candidate={c}
          sport={sport}
          bankroll={bankroll}
          kelly={kelly}
          onEdit={() => onEdit(c.legs)}
        />
      ))}
    </View>
  );
}

function SgpIntro({ onDismiss }: { onDismiss: () => void }) {
  return (
    <View style={styles.sgpIntro}>
      <Ionicons name="git-network-outline" size={16} color={colors.tint} />
      <Text style={styles.sgpIntroText}>
        Legs in the same game move together. We price each combo on its true joint
        probability — not the naïve product books lean on — and surface only the
        ones that clear DK's parlay hold.
      </Text>
      <Pressable onPress={onDismiss} hitSlop={10} accessibilityLabel="Dismiss this explainer">
        <Ionicons name="close" size={16} color={colors.textSecondary} />
      </Pressable>
    </View>
  );
}

function SgpCard({
  candidate,
  sport,
  bankroll,
  kelly,
  onEdit,
}: {
  candidate: SgpCandidate;
  sport: string;
  bankroll: number;
  kelly: { multiplier: number; cap: number | null };
  onEdit: () => void;
}) {
  const m = candidate.metrics;
  const matchup = matchupForLeg(candidate.legs[0]?.game ?? null);
  const stake = parlayRecommendedUnits(m, kelly);
  const payout = stake.risk * m.decimalPayout;
  return (
    <View style={styles.resultCard}>
      <View style={styles.resultHeader}>
        <View style={styles.sgpHeaderLeft}>
          {matchup ? <Text style={styles.sgpMatchup}>{matchup}</Text> : null}
          <Text style={styles.resultTitle}>{candidate.legs.length}-Leg Same-Game</Text>
        </View>
        <View style={styles.resultHeaderRight}>
          <GradeBadge grade={m.grade} />
          <Text style={styles.resultOdds}>{formatAmerican(m.americanOdds)}</Text>
        </View>
      </View>

      <View style={styles.statsRow}>
        <Stat label="Model" value={formatPct(m.parlayProb)} />
        <Stat label="EV" value={formatPctSigned(m.ev)} color={m.ev >= 0 ? colors.bet : colors.avoid} />
        <Stat
          label="Edge"
          value={formatPctSigned(m.edgeVsDk)}
          color={m.edgeVsDk >= 0 ? colors.bet : colors.avoid}
        />
        <Stat label="DK imp." value={formatPct(m.dkImpliedProb)} />
      </View>

      <View style={styles.stakeRow}>
        <Stat label="Stake" value={formatStake(stake)} />
        <Stat label="Potential payout" value={formatCurrency(payout)} />
      </View>

      <CorrelatedExtras m={m} />

      <BetslipBooksRow legs={candidate.legs} />

      <LineShopRow lineShop={lineShopParlay(candidate.legs, m.jointProb, m.ev)} dkAmerican={m.americanOdds} />

      <ParlayHoldNote ev={m.ev} />

      <View style={styles.legsList}>
        {candidate.legs.map((leg) => (
          <ParlayLegCard key={leg.pickId} leg={leg} />
        ))}
      </View>

      <View style={styles.sgpActions}>
        <Pressable onPress={onEdit} style={({ pressed }) => [styles.saveBtn, pressed && styles.pressed]}>
          <Ionicons name="create-outline" size={18} color={colors.tint} />
          <Text style={styles.saveBtnText}>Edit in builder</Text>
        </Pressable>
      </View>

      <ParlayActions legs={candidate.legs} sport={sport} />
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
        Display-only — the DraftKings hand-off uses DK prices.
      </Text>
    </View>
  );
}

function ManualBuilder({
  legs,
  metrics,
  valid,
  missingCount,
  sport,
  bankroll,
  kelly,
  onRemove,
  onAddCustom,
  onFindPlayers,
  onClear,
  onClearStale,
}: {
  legs: ParlayLeg[];
  metrics: CorrelatedMetrics;
  valid: boolean;
  missingCount: number;
  sport: string;
  bankroll: number;
  kelly: { multiplier: number; cap: number | null };
  onRemove: (pickId: number) => void;
  onAddCustom: () => void;
  onFindPlayers: () => void;
  onClear: () => void;
  onClearStale: () => void;
}) {
  if (legs.length === 0) {
    return (
      <View>
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

      {missingCount > 0 ? (
        <Pressable onPress={onClearStale} style={({ pressed }) => [styles.missingNote, pressed && styles.pressed]}>
          <Text style={styles.missingNoteText}>
            {missingCount} selection{missingCount === 1 ? '' : 's'} no longer available today · tap to clear
          </Text>
        </Pressable>
      ) : null}

      <View style={styles.resultCard}>
        <View style={styles.resultHeader}>
          <Text style={styles.resultTitle}>{legs.length}-Leg Play</Text>
          <View style={styles.resultHeaderRight}>
            <GradeBadge grade={metrics.grade} />
            <Text style={styles.resultOdds}>{formatAmerican(metrics.americanOdds)}</Text>
          </View>
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

        <View style={styles.stakeRow}>
          <Stat label="Stake" value={formatStake(stake)} />
          <Stat label="Potential payout" value={formatCurrency(payout)} />
        </View>

        <CorrelatedExtras m={metrics} />

        <BetslipBooksRow legs={legs} />

        <LineShopRow lineShop={lineShopParlay(legs, metrics.jointProb, metrics.ev)} dkAmerican={metrics.americanOdds} />

        <ParlayHoldNote ev={metrics.ev} />

        <View style={styles.legsList}>
          {legs.map((leg) => (
            <ParlayLegCard key={leg.pickId} leg={leg} onRemove={() => onRemove(leg.pickId)} />
          ))}
        </View>

        <ParlayActions legs={legs} sport={sport} />
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
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 4,
  },
  errorBanner: {
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
  panel: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
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
  stepperRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.lg,
  },
  stepBtn: {
    width: 40,
    height: 40,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepBtnDisabled: {
    opacity: 0.4,
  },
  stepValue: {
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    minWidth: 28,
    textAlign: 'center',
  },
  modeToggle: {
    flexDirection: 'row',
    backgroundColor: colors.noneSoft,
    borderRadius: radii.sm,
    padding: 2,
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
  },
  segmented: {
    flexDirection: 'row',
    backgroundColor: colors.noneSoft,
    borderRadius: radii.sm,
    padding: 2,
  },
  segment: {
    flex: 1,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm - 2,
    alignItems: 'center',
  },
  segmentActive: {
    backgroundColor: colors.bgCard,
  },
  segmentLabel: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  segmentLabelActive: {
    color: colors.tint,
  },
  oddsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  oddsInput: {
    flex: 1,
    backgroundColor: colors.noneSoft,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  oddsDash: {
    color: colors.textTertiary,
    fontSize: font.size.body,
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
  customRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.noneSoft,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  customRowText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
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
  sgpIntro: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  sgpIntroText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  sgpHeaderLeft: {
    flex: 1,
  },
  sgpMatchup: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
    marginBottom: 2,
  },
  sgpActions: {
    marginTop: spacing.md,
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
  dkBtnText: {
    color: '#000',
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  altSection: {
    marginTop: spacing.lg,
    paddingHorizontal: spacing.lg,
  },
  altHeading: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: spacing.sm,
  },
  altCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  altCardBody: {
    flex: 1,
  },
  altCardTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  altCardTitle: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  altCardLegs: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  altCardEv: {
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
  modalEmpty: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    paddingVertical: spacing.xl,
    textAlign: 'center',
  },
  modalList: {
    flexGrow: 0,
  },
  modalRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  modalRowBody: {
    flex: 1,
  },
  modalRowLabel: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  modalRowMeta: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
});

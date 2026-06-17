import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { TabParamList } from '@/types';
import { EmptyState } from '@/components/EmptyState';
import { ParlayLegCard } from '@/components/ParlayLegCard';
import { SportToggle } from '@/components/SportToggle';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import {
  addLeg,
  applySwap,
  buildCandidatePool,
  computeParlayMetrics,
  isValidCombo,
  makeCustomLeg,
  MAX_LEGS,
  MIN_LEGS,
  optimizeParlay,
  parlayRecommendedBet,
  removeLeg,
  resolveSlipLegs,
  swapCandidatesFor,
  type Parlay,
  type ParlayConstraints,
  type ParlayLeg,
  type ParlayMetrics,
  type ParlayResult,
  type ParlayStyle,
} from '@/lib/parlay';
import { modelShort } from '@/lib/modelMeta';
import {
  americanToDecimal,
  formatAmerican,
  formatCurrency,
  formatPct,
  formatPctSigned,
} from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';

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

type BuildMode = 'optimize' | 'manual';

export function ParlayScreen() {
  const navigation = useNavigation<BottomTabNavigationProp<TabParamList>>();
  const { data, loading, error, refresh } = useTodayPicks();
  const { sport } = useSportFilter();
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);
  const slip = useParlaySlip();

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

  // ── Manual builder ──────────────────────────────────────────────────────
  // Resolve the persisted slip against today's picks (cross-sport, any signal),
  // then append session custom legs. Recomputed whenever picks or the slip move.
  const { legs: slipLegs, missingIds } = useMemo(
    () => resolveSlipLegs(data, slip.ids),
    [data, slip.ids],
  );
  const manualLegs = useMemo(() => [...slipLegs, ...manualCustom], [slipLegs, manualCustom]);
  const manualMetrics = useMemo(() => computeParlayMetrics(manualLegs), [manualLegs]);
  const manualValid = useMemo(() => isValidCombo(manualLegs), [manualLegs]);

  const handleManualRemove = useCallback(
    (pickId: number) => {
      if (pickId < 0) setManualCustom((prev) => prev.filter((l) => l.pickId !== pickId));
      else slip.remove(pickId);
    },
    [slip],
  );

  const handleManualClear = useCallback(() => {
    slip.clear();
    setManualCustom([]);
  }, [slip]);

  const handleClearStale = useCallback(() => {
    missingIds.forEach((id) => slip.remove(id));
  }, [missingIds, slip]);

  const openManualCustom = useCallback(() => {
    setCustomLabel('');
    setCustomOddsText('');
    setCustomForm({ mode: 'manual-add' });
  }, []);

  // Send the user to the Stats tab to browse players; adding one brings them
  // back here automatically (fromParlay flag handled in StatsScreen).
  const goFindPlayers = useCallback(() => {
    navigation.navigate('Stats', { fromParlay: true });
  }, [navigation]);

  // MLB and WNBA share no picks — clear any built parlay when the sport changes.
  useEffect(() => {
    setBuilt(null);
    setWorking(null);
    setSwapTarget(null);
    setCustomForm(null);
  }, [sport]);

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
    const result = optimizeParlay(pool, constraints);
    setBuilt(result);
    setWorking(result.best);
    setSwapTarget(null);
  }, [pool, constraints]);

  const handleRemove = useCallback((pickId: number) => {
    setWorking((prev) => (prev ? removeLeg(prev, pickId) : prev));
  }, []);

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
          <Text style={styles.title}>Parlay Builder</Text>
          <Text style={styles.subtitle}>
            {mode === 'optimize'
              ? `${pool.length} eligible BET leg${pool.length === 1 ? '' : 's'} today · highest-EV combo`
              : `${manualLegs.length} leg${manualLegs.length === 1 ? '' : 's'} in your play · add from the Stats or Picks tab`}
          </Text>
          <View style={styles.modeToggle}>
            {(['optimize', 'manual'] as BuildMode[]).map((m) => {
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
                  <Text style={[styles.segmentLabel, active && styles.segmentLabelActive]}>
                    {m === 'optimize' ? 'Optimize' : 'Build your own'}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          {mode === 'optimize' ? <SportToggle /> : null}
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
            missingCount={missingIds.length}
            bankroll={bankroll}
            kelly={kelly}
            onRemove={handleManualRemove}
            onAddCustom={openManualCustom}
            onFindPlayers={goFindPlayers}
            onClear={handleManualClear}
            onClearStale={handleClearStale}
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

        {working && working.legs.length >= MIN_LEGS ? (
          <ResultCard
            parlay={working}
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
            {built.alternatives.map((alt, i) => (
              <Pressable
                key={alt.legs.map((l) => l.pickId).join('-')}
                onPress={() => setWorking(alt)}
                style={({ pressed }) => [styles.altCard, pressed && styles.pressed]}
              >
                <View style={styles.altCardBody}>
                  <Text style={styles.altCardTitle}>
                    {alt.legs.length}-leg · {formatAmerican(alt.metrics.americanOdds)}
                  </Text>
                  <Text style={styles.altCardLegs} numberOfLines={1}>
                    {alt.legs.map((l) => modelShort(l.modelId)).join(' + ')}
                  </Text>
                </View>
                <Text
                  style={[
                    styles.altCardEv,
                    { color: alt.metrics.ev >= 0 ? colors.bet : colors.avoid },
                  ]}
                >
                  EV {formatPctSigned(alt.metrics.ev)}
                </Text>
              </Pressable>
            ))}
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
  bankroll,
  kelly,
  onRemove,
  onSwap,
}: {
  parlay: Parlay;
  bankroll: number;
  kelly: { multiplier: number; cap: number | null };
  onRemove: (pickId: number) => void;
  onSwap: (pickId: number) => void;
}) {
  const m = parlay.metrics;
  const stake = parlayRecommendedBet(m, bankroll, kelly);
  const payout = stake * m.decimalPayout;
  return (
    <View style={styles.resultCard}>
      <View style={styles.resultHeader}>
        <Text style={styles.resultTitle}>{parlay.legs.length}-Leg Parlay</Text>
        <Text style={styles.resultOdds}>{formatAmerican(m.americanOdds)}</Text>
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
        <Stat label="Recommended" value={formatCurrency(stake)} />
        <Stat label="Potential payout" value={formatCurrency(payout)} />
      </View>

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
    </View>
  );
}

function ManualBuilder({
  legs,
  metrics,
  valid,
  missingCount,
  bankroll,
  kelly,
  onRemove,
  onAddCustom,
  onFindPlayers,
  onClear,
  onClearStale,
}: {
  legs: ParlayLeg[];
  metrics: ParlayMetrics;
  valid: boolean;
  missingCount: number;
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
          title="Your play is empty"
          subtitle={'Find a player you want to bet and tap "Add to play" — you\'ll come right back here. Picks from the Picks/Signals tabs work too, or enter a custom leg.'}
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

  const stake = parlayRecommendedBet(metrics, bankroll, kelly);
  const payout = stake * metrics.decimalPayout;

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
          <Text style={styles.resultOdds}>{formatAmerican(metrics.americanOdds)}</Text>
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
          <Stat label="Recommended" value={formatCurrency(stake)} />
          <Stat label="Potential payout" value={formatCurrency(payout)} />
        </View>

        <View style={styles.legsList}>
          {legs.map((leg) => (
            <ParlayLegCard key={leg.pickId} leg={leg} onRemove={() => onRemove(leg.pickId)} />
          ))}
        </View>
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
          <Text style={styles.clearBtnText}>Clear play</Text>
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
  title: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
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
  resultOdds: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.tint,
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

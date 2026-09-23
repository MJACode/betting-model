import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useCustomModels, pickMatchesModel } from '@/hooks/useCustomModels';
import {
  useCustomModelBacktest,
  type CustomModelStats,
} from '@/hooks/useCustomModelStats';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { EmptyState } from '@/components/EmptyState';
import { RangeSlider } from '@/components/filters/RangeSlider';
import {
  CHIP_GROUPS,
  DEFAULT_FILTERS,
  LINE_VALUE_OPTIONS,
  ODDS_STOPS,
  PUBLIC_PCT_OPTIONS,
  SLIDER_LOW_SENTINEL,
  boundIndex,
  chipSelection,
  formatAmericanLabel,
  formatLineLabel,
  formatPublicLabel,
  formatRangeCaption,
  indexToBound,
  setNumericFilter,
  toggleChip,
} from '@/lib/customModelFilters';
import { formatPctSigned } from '@/lib/format';
import { applyBound } from '@/lib/rangeSlider';
import {
  betTypeLabel,
  betTypePickerGroups,
  choiceAddedLabel,
  PAUSED_RULE_CAPTION,
  RETIRED_RULE_CAPTION,
  type BetTypeChoice,
} from '@/lib/modelMeta';
import { isModelPaused, isModelRetired } from '@/lib/thresholds';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { CustomModel, CustomModelFilters, CustomModelRule, RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'ModelEdit'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

interface DraftRule extends CustomModelRule {
  uid: string;
}

function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function ModelEditScreen() {
  const route = useRoute<Route>();
  const navigation = useNavigation<Nav>();
  const { create, update, remove, get } = useCustomModels();
  const editingId = route.params?.modelId;
  const existing = editingId ? get(editingId) : undefined;

  const [name, setName] = useState<string>(existing?.name ?? '');
  const [rules, setRules] = useState<DraftRule[]>(
    existing ? existing.rules.map((r) => ({ ...r, uid: uid() })) : [],
  );
  // New and legacy models alike start/stay unconstrained — the per-bet-type
  // minimums are the qualification, filters only narrow further.
  const [filters, setFilters] = useState<CustomModelFilters>(
    existing ? (existing.filters ?? {}) : DEFAULT_FILTERS,
  );
  const [pickerOpen, setPickerOpen] = useState(false);

  const { data: todayPicks, loading: todayLoading } = useTodayPicks();

  useEffect(() => {
    navigation.setOptions({ title: editingId ? 'Edit model' : 'New model' });
  }, [navigation, editingId]);

  // Drop every blank floor entirely so saved rules stay minimal and the RPC
  // payload matches what older builds send for the same criteria. The RPC
  // treats an absent min_prob/min_edge/min_ev as no floor, exactly as
  // pickMatchesModel does.
  const cleanRules = useMemo<CustomModelRule[]>(
    () =>
      rules.map((r) => {
        const out: CustomModelRule = { model_id: r.model_id };
        if (r.min_prob != null) out.min_prob = r.min_prob;
        if (r.min_edge != null) out.min_edge = r.min_edge;
        if (r.min_ev != null) out.min_ev = r.min_ev;
        return out;
      }),
    [rules],
  );

  // The draft is matched exactly the way a saved model is, so the preview can
  // never disagree with what the model does once saved.
  const draft = useMemo<CustomModel>(
    () => ({
      id: editingId ?? 'draft',
      name,
      rules: cleanRules,
      filters,
      created_at: '',
      updated_at: '',
    }),
    [editingId, name, cleanRules, filters],
  );

  // Server-graded backtest over EVERY scored pick (BET + AVOID + dead-zone),
  // debounced so chip-tapping doesn't fire an RPC per touch.
  const { stats: backtestStats, loading: backtestLoading } = useCustomModelBacktest(
    cleanRules.length > 0 ? draft : null,
    { debounceMs: 350 },
  );
  const backtest: CustomModelStats | null = cleanRules.length > 0 ? backtestStats : null;

  const todayMatches = useMemo(
    () =>
      cleanRules.length === 0
        ? 0
        : todayPicks.filter((ep) => pickMatchesModel(ep.pick, draft)).length,
    [draft, todayPicks, cleanRules.length],
  );

  // A model is identified by its name everywhere it appears (the Models list,
  // its detail screen, the backtest header), so an unnamed one is unusable —
  // "Untitled model" was never a name anybody chose.
  const trimmedName = name.trim();

  const onSave = () => {
    if (trimmedName === '') {
      Alert.alert('Name your model', 'Give the model a title so you can tell it apart in the list.');
      return;
    }
    if (rules.length === 0) {
      Alert.alert('Add at least one bet type', 'A model needs one or more bet types to match picks.');
      return;
    }
    if (editingId) update(editingId, { name: trimmedName, rules: cleanRules, filters });
    else create(trimmedName, cleanRules, filters);
    navigation.goBack();
  };

  const onDelete = () => {
    if (!editingId) return;
    Alert.alert(
      'Delete this model?',
      'You can recreate it any time. Backtest history is computed live, nothing else is lost.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => {
            remove(editingId);
            navigation.goBack();
          },
        },
      ],
    );
  };

  // A new bet type starts with NO minimums. Seeding the in-house cut made the
  // model look like the user's choice when it was ours — every number a saved
  // model carries is now one they typed, and a blank field means "Any".
  // One picker row can cover several model_ids (every active player prop).
  // Each becomes its own rule so the stored shape is unchanged.
  const addRules = (modelIds: string[]) => {
    setRules((prev) => {
      const have = new Set(prev.map((r) => r.model_id));
      const next = [...prev];
      for (const modelId of modelIds) {
        if (have.has(modelId)) continue;
        next.push({ uid: uid(), model_id: modelId });
        have.add(modelId);
      }
      return next;
    });
    setPickerOpen(false);
  };

  const updateRule = (ruleUid: string, patch: Partial<CustomModelRule>) => {
    setRules((prev) => prev.map((r) => (r.uid === ruleUid ? { ...r, ...patch } : r)));
  };

  const removeRule = (ruleUid: string) => {
    setRules((prev) => prev.filter((r) => r.uid !== ruleUid));
  };

  const alreadyAdded = useMemo(() => new Set(rules.map((r) => r.model_id)), [rules]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.list} keyboardShouldPersistTaps="handled">
        <View style={styles.card}>
          <Text style={styles.label}>Name</Text>
          <Text style={styles.helper}>
            What you'll call this model in your list. Required.
          </Text>
          <TextInput
            style={styles.nameInput}
            value={name}
            onChangeText={setName}
            placeholder="e.g. Road favorites in prime time"
            placeholderTextColor={colors.textTertiary}
            maxLength={60}
          />
        </View>

        <View style={styles.card}>
          <View style={styles.rulesHeader}>
            <Text style={styles.label}>Bet types</Text>
            <Pressable
              onPress={() => setPickerOpen(true)}
              style={({ pressed }) => [styles.addRuleBtn, pressed && styles.pressed]}
              hitSlop={6}
              accessibilityRole="button"
              accessibilityLabel="Add bet type"
            >
              <Ionicons name="add" size={18} color={colors.textInverse} />
              <Text style={styles.addRuleText}>Add bet type</Text>
            </Pressable>
          </View>
          <Text style={styles.helper}>
            Pick a sport, then ML, the line (Run line in baseball, Spread in football and
            basketball), or Player props. Player props adds every active player market for that
            sport. Every minimum starts blank: leave it that way for Any and the bet type qualifies
            on its own.
          </Text>
          <Text style={styles.helper}>
            Model % is our projected win probability. Edge is model % minus DraftKings' implied
            probability. EV is expected profit per $1 at the DK price (picks with no DK price can
            never clear an EV floor).
          </Text>

          {rules.length === 0 ? (
            <Text style={styles.emptyRules}>No bet types yet. Tap Add bet type to start.</Text>
          ) : (
            rules.map((r) => (
              <RuleRow
                key={r.uid}
                rule={r}
                onChange={(p) => updateRule(r.uid, p)}
                onRemove={() => removeRule(r.uid)}
              />
            ))
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.label}>Filters</Text>
          <Text style={styles.helper}>
            Narrow the qualifying picks further. Anything you leave untouched stays unfiltered.
          </Text>

          {CHIP_GROUPS.map((group) => (
            <ChipRow
              key={group.key}
              title={group.title}
              help={group.help}
              options={group.options}
              selected={chipSelection(filters, group.key)}
              onToggle={(v) => setFilters((f) => toggleChip(f, group.key, v))}
            />
          ))}

          <View style={styles.divider} />

          <FilterRange
            title="Price range"
            help="American odds on the price the pick was measured at. Drag either end. An end left on Any does not limit that side — pull the low end in to skip heavy juice, the high end in to skip longshots."
            stops={ODDS_STOPS}
            minValue={filters.minOdds}
            maxValue={filters.maxOdds}
            formatValue={formatAmericanLabel}
            lowLabel="Lowest price"
            highLabel="Highest price"
            onChange={(min, max) =>
              setFilters((f) => setNumericFilter(setNumericFilter(f, 'minOdds', min), 'maxOdds', max))
            }
          />

          <View style={styles.divider} />

          <FilterRange
            title="Line value"
            help="The line the pick was priced at — a game total (e.g. 8.5 runs), a spread, or a prop line (e.g. 5.5 Ks). Moneyline picks carry no line, so pulling either end off Any drops them."
            stops={LINE_VALUE_OPTIONS}
            minValue={filters.minLine}
            maxValue={filters.maxLine}
            formatValue={formatLineLabel}
            lowLabel="Lowest line"
            highLabel="Highest line"
            onChange={(min, max) =>
              setFilters((f) => setNumericFilter(setNumericFilter(f, 'minLine', min), 'maxLine', max))
            }
          />

          <View style={styles.divider} />

          <FilterRange
            title="Public backing"
            help="Share of public bets on our side. Only full-game moneyline, spread and total picks carry splits, so pulling either end off Any drops every pick that has none."
            stops={PUBLIC_PCT_OPTIONS}
            minValue={filters.minPublicBetPct}
            maxValue={filters.maxPublicBetPct}
            formatValue={formatPublicLabel}
            lowLabel="Lowest public backing"
            highLabel="Highest public backing"
            onChange={(min, max) =>
              setFilters((f) =>
                setNumericFilter(setNumericFilter(f, 'minPublicBetPct', min), 'maxPublicBetPct', max),
              )
            }
          />

          <View style={styles.divider} />

          <View style={styles.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.groupTitle}>Skip injury-flagged picks</Text>
              <Text style={styles.groupHelp}>
                Drops picks where a relevant player is carrying an injury flag.
              </Text>
            </View>
            <Switch
              value={filters.excludeInjuries === true}
              onValueChange={(on) =>
                setFilters((f) => {
                  const next = { ...f };
                  if (on) next.excludeInjuries = true;
                  else delete next.excludeInjuries;
                  return next;
                })
              }
            />
          </View>
        </View>

        {editingId ? (
          <Pressable
            onPress={onDelete}
            style={styles.deleteBtn}
            accessibilityRole="button"
            accessibilityLabel="Delete model"
          >
            <Text style={styles.deleteBtnText}>Delete model</Text>
          </Pressable>
        ) : null}
      </ScrollView>

      <PreviewFooter
        hasRules={cleanRules.length > 0}
        allRetired={cleanRules.length > 0 && cleanRules.every((r) => isModelRetired(r.model_id))}
        canSave={trimmedName !== '' && cleanRules.length > 0}
        loading={backtestLoading || todayLoading}
        todayMatches={todayMatches}
        backtest={backtest}
        saveLabel={editingId ? 'Save changes' : 'Create model'}
        onSave={onSave}
      />

      <ModelPickerModal
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onPick={addRules}
        alreadyAdded={alreadyAdded}
      />
    </SafeAreaView>
  );
}

/**
 * Pinned footer showing what the draft matches right now — today's board and
 * the settled backtest — so every chip toggle has visible consequences without
 * scrolling back up.
 */
function PreviewFooter({
  hasRules,
  allRetired,
  canSave,
  loading,
  todayMatches,
  backtest,
  saveLabel,
  onSave,
}: {
  hasRules: boolean;
  /** Every rule is on a retired bet type — four zeros would read as "matches
   *  nothing" when the truth is "can never match". */
  allRetired: boolean;
  canSave: boolean;
  loading: boolean;
  todayMatches: number;
  backtest: CustomModelStats | null;
  saveLabel: string;
  onSave: () => void;
}) {
  const roi = backtest?.roiFlat ?? 0;
  const roiColor =
    !backtest || backtest.picks === 0
      ? colors.textSecondary
      : roi > 0
        ? colors.bet
        : roi < 0
          ? colors.avoid
          : colors.textSecondary;
  const decided = (backtest?.wins ?? 0) + (backtest?.losses ?? 0);

  return (
    <View style={styles.footer}>
      {hasRules && allRetired ? (
        <Text style={styles.previewEmpty}>
          Every bet type here is retired — add a live one to see matches.
        </Text>
      ) : hasRules ? (
        <View style={styles.previewRow}>
          <PreviewStat label="Today" value={loading ? '—' : String(todayMatches)} caption="matching" />
          <PreviewStat
            label="Backtest"
            value={loading ? '—' : String(backtest?.picks ?? 0)}
            caption="graded picks"
          />
          <PreviewStat
            label="Record"
            value={decided > 0 ? `${backtest?.wins}-${backtest?.losses}` : '—'}
            caption={backtest && backtest.pushes > 0 ? `${backtest.pushes} push` : 'since Apr 14'}
          />
          <PreviewStat
            label="Flat ROI"
            value={backtest && backtest.picks > 0 ? formatPctSigned(roi) : '—'}
            caption="$100/bet"
            color={roiColor}
          />
        </View>
      ) : (
        <Text style={styles.previewEmpty}>
          Add a bet type above to see what it would have matched.
        </Text>
      )}
      {/* Four dashes and a zero read as a broken builder, not as a new market.
          The picker lists every live bet type, and twelve NFL prop markets were
          unpaused on 2026-09-09 with no graded history behind them, so this is
          now a state a user reaches by picking a perfectly good market (UX
          review). Deliberately NOT the go-live-gate wording — that is banned
          from the app as copy AND as a constant (.claude/rules/frontend.md). */}
      {hasRules && !allRetired && !loading && backtest?.picks === 0 ? (
        <Text style={styles.previewEmpty}>
          New market — no settled picks yet, so there is no record to show.
        </Text>
      ) : null}
      {loading && hasRules ? (
        <ActivityIndicator style={styles.previewLoading} size="small" />
      ) : null}
      <Pressable
        onPress={onSave}
        disabled={!canSave}
        accessibilityRole="button"
        accessibilityState={{ disabled: !canSave }}
        style={({ pressed }) => [
          styles.saveBtn,
          !canSave && styles.saveBtnDisabled,
          pressed && styles.pressed,
        ]}
      >
        <Text style={styles.saveBtnText}>{saveLabel}</Text>
      </Pressable>
    </View>
  );
}

function PreviewStat({
  label,
  value,
  caption,
  color,
}: {
  label: string;
  value: string;
  caption: string;
  color?: string;
}) {
  return (
    <View style={styles.previewStat}>
      <Text style={styles.previewLabel}>{label}</Text>
      <Text style={[styles.previewValue, color ? { color } : null]} numberOfLines={1}>
        {value}
      </Text>
      <Text style={styles.previewCaption} numberOfLines={1}>
        {caption}
      </Text>
    </View>
  );
}

function ChipRow({
  title,
  help,
  options,
  selected,
  onToggle,
}: {
  title: string;
  help: string;
  options: Array<{ value: string; label: string }>;
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <View style={styles.chipGroup}>
      <View style={styles.chipGroupHead}>
        <Text style={styles.groupTitle}>{title}</Text>
        <Text style={styles.chipState}>{selected.length === 0 ? 'Any' : `${selected.length} on`}</Text>
      </View>
      <Text style={styles.groupHelp}>{help}</Text>
      <View style={styles.chips}>
        {options.map((o) => {
          const on = selected.includes(o.value);
          return (
            <Pressable
              key={o.value}
              onPress={() => onToggle(o.value)}
              accessibilityRole="button"
              accessibilityState={{ selected: on }}
              style={({ pressed }) => [styles.chip, on && styles.chipOn, pressed && styles.pressed]}
            >
              <Text style={[styles.chipText, on && styles.chipTextOn]}>{o.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

/**
 * Dual-handle range for one numeric filter pair. The outer stops are Any
 * (the filter key is omitted). Dragging inward writes min and max. There is
 * no text field.
 */
function FilterRange({
  title,
  help,
  stops,
  minValue,
  maxValue,
  formatValue,
  lowLabel,
  highLabel,
  onChange,
}: {
  title: string;
  help: string;
  stops: readonly number[];
  minValue: number | undefined;
  maxValue: number | undefined;
  formatValue: (v: number) => string;
  lowLabel: string;
  highLabel: string;
  onChange: (min: number | null, max: number | null) => void;
}) {
  const low = boundIndex(stops, minValue, 'low');
  const high = boundIndex(stops, maxValue, 'high');
  // A stored pair that crosses (legacy free text) still has to be a slider.
  const sliderLow = Math.min(low, high);
  const sliderHigh = Math.max(low, high);
  // Sentinels read Any. A thumb parked on the nearest stop for a legacy
  // off-list value shows that stored number, not the snapped stop, until
  // the user moves it and the stored value is rewritten.
  const formatIndex = (index: number) => {
    const stop = indexToBound(stops, index);
    if (stop == null) return 'Any';
    if (minValue != null && index === boundIndex(stops, minValue, 'low')) return formatValue(minValue);
    if (maxValue != null && index === boundIndex(stops, maxValue, 'high')) return formatValue(maxValue);
    return formatValue(stop);
  };
  const caption = formatRangeCaption(minValue, maxValue, formatValue);
  const constrained = minValue != null || maxValue != null;
  // Public backing is 21 stops. Price and line are fine enough that a finger
  // and a one-step VoiceOver swipe cannot land on a value.
  const fine = stops.length > 30;

  const nudge = (which: 'low' | 'high', direction: -1 | 1) => {
    const current = which === 'low' ? sliderLow : sliderHigh;
    const next = Math.min(stops.length, Math.max(SLIDER_LOW_SENTINEL, current + direction));
    const pair = applyBound(which, next, sliderLow, sliderHigh);
    if (pair.low === sliderLow && pair.high === sliderHigh) return;
    onChange(indexToBound(stops, pair.low), indexToBound(stops, pair.high));
  };

  return (
    <View>
      <View style={styles.chipGroupHead}>
        <Text style={styles.groupTitle}>{title}</Text>
        <View style={styles.rangeHeadRight}>
          <Text style={styles.rangeLive}>{caption}</Text>
          {constrained ? (
            <Pressable
              onPress={() => onChange(null, null)}
              accessibilityRole="button"
              accessibilityLabel={`Clear ${title}`}
              style={styles.rangeClear}
            >
              <Text style={styles.rangeClearText}>Clear</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
      <Text style={styles.groupHelp}>{help}</Text>
      <RangeSlider
        min={SLIDER_LOW_SENTINEL}
        max={stops.length}
        step={1}
        low={sliderLow}
        high={sliderHigh}
        onChange={(lo, hi) => onChange(indexToBound(stops, lo), indexToBound(stops, hi))}
        format={formatIndex}
        a11yStep={fine ? 10 : 1}
        onNudge={fine ? nudge : undefined}
        lowLabel={lowLabel}
        highLabel={highLabel}
      />
    </View>
  );
}

/** A rule floor as text: blank (= "Any") or a whole percentage. */
function pctText(value: number | null | undefined): string {
  return value == null ? '' : String(Math.round(value * 100));
}

function RuleRow({
  rule,
  onChange,
  onRemove,
}: {
  rule: DraftRule;
  onChange: (patch: Partial<CustomModelRule>) => void;
  onRemove: () => void;
}) {
  const [probText, setProbText] = useState<string>(pctText(rule.min_prob));
  const [edgeText, setEdgeText] = useState<string>(pctText(rule.min_edge));
  const [evText, setEvText] = useState<string>(pctText(rule.min_ev));

  /**
   * Commit one floor. Every field is optional: clearing it stores null, which
   * both the client matcher and the RPC read as no floor at all. An
   * unparseable entry snaps back to what is stored rather than silently
   * becoming "Any".
   */
  const commitFloor = (
    key: 'min_prob' | 'min_edge' | 'min_ev',
    text: string,
    setText: (t: string) => void,
    min: number,
  ) => {
    const trimmed = text.trim();
    if (trimmed === '' || trimmed === '-' || trimmed === '+') {
      onChange({ [key]: null });
      setText('');
      return;
    }
    const v = parseFloat(trimmed);
    if (Number.isFinite(v) && v >= min && v <= 100) onChange({ [key]: v / 100 });
    else setText(pctText(rule[key]));
  };

  const commitProb = () => commitFloor('min_prob', probText, setProbText, 0);
  const commitEdge = () => commitFloor('min_edge', edgeText, setEdgeText, -100);
  const commitEv = () => commitFloor('min_ev', evText, setEvText, -100);

  // A retired bet type keeps its label (the rule really was built on it) but
  // its floors do nothing — nothing will ever score another pick for it — so
  // they are shown disabled and removing the rule is the only action.
  const retired = isModelRetired(rule.model_id);
  const paused = isModelPaused(rule.model_id);
  // Floors stay editable on a paused rule: the backtest still grades its
  // settled history. Retired floors do nothing (the rule is dropped).

  return (
    <View style={styles.ruleRow}>
      <View style={styles.ruleHeader}>
        <View style={{ flex: 1 }}>
          <Text style={styles.ruleModel}>{betTypeLabel(rule.model_id)}</Text>
          {retired ? (
            <Text style={styles.ruleRetired}>{RETIRED_RULE_CAPTION}</Text>
          ) : paused ? (
            <Text style={styles.ruleRetired}>{PAUSED_RULE_CAPTION}</Text>
          ) : null}
        </View>
        <Pressable
          onPress={onRemove}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={`Remove ${betTypeLabel(rule.model_id)}`}
        >
          <Ionicons name="trash-outline" size={18} color={colors.avoid} />
        </Pressable>
      </View>
      <View style={[styles.ruleFields, retired && styles.ruleFieldsRetired]}>
        <View style={styles.ruleField}>
          <Text style={styles.ruleFieldLabel}>Min model %</Text>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.ruleInput}
              value={probText}
              onChangeText={setProbText}
              onBlur={commitProb}
              placeholder="Any"
              placeholderTextColor={colors.textTertiary}
              editable={!retired}
              accessibilityState={{ disabled: retired }}
              keyboardType="decimal-pad"
              maxLength={5}
            />
            <Text style={styles.inputSuffix}>%</Text>
          </View>
        </View>
        <View style={styles.ruleField}>
          <Text style={styles.ruleFieldLabel}>Min edge %</Text>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.ruleInput}
              value={edgeText}
              onChangeText={setEdgeText}
              onBlur={commitEdge}
              placeholder="Any"
              placeholderTextColor={colors.textTertiary}
              editable={!retired}
              accessibilityState={{ disabled: retired }}
              keyboardType="numbers-and-punctuation"
              maxLength={5}
            />
            <Text style={styles.inputSuffix}>%</Text>
          </View>
        </View>
        <View style={styles.ruleField}>
          <Text style={styles.ruleFieldLabel}>Min EV %</Text>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.ruleInput}
              value={evText}
              onChangeText={setEvText}
              onBlur={commitEv}
              placeholder="Any"
              placeholderTextColor={colors.textTertiary}
              editable={!retired}
              accessibilityState={{ disabled: retired }}
              keyboardType="numbers-and-punctuation"
              maxLength={5}
            />
            <Text style={styles.inputSuffix}>%</Text>
          </View>
        </View>
      </View>
    </View>
  );
}

/**
 * The bet-type picker. Each sport offers at most three rows — ML, the line,
 * Player props — and a row writes every active model_id in that slot.
 * Strategy names and long market labels stay off this list.
 */
function ModelPickerModal({
  visible,
  onClose,
  onPick,
  alreadyAdded,
}: {
  visible: boolean;
  onClose: () => void;
  onPick: (modelIds: string[]) => void;
  alreadyAdded: Set<string>;
}) {
  const groups = betTypePickerGroups();
  const insets = useSafeAreaInsets();

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={styles.modalContainer}>
        <View style={styles.modalHeader}>
          <Text style={styles.modalTitle} numberOfLines={1}>
            Pick a bet type
          </Text>
          <Pressable
            onPress={onClose}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel="Cancel"
            style={styles.modalCancelBtn}
          >
            <Text style={styles.modalCancel}>Cancel</Text>
          </Pressable>
        </View>
        <ScrollView
          contentContainerStyle={[styles.modalList, { paddingBottom: spacing.lg + insets.bottom }]}
        >
          {groups.length === 0 ? (
            <EmptyState
              title="No bet types right now"
              subtitle="Every market this builder offers is paused. A paused model still keeps the picks it already made."
            />
          ) : (
            groups.map((group) => (
              <View key={group.sport} style={styles.modalSection}>
                <Text style={styles.modalSectionTitle}>{group.sport}</Text>
                {group.choices.map((choice) => {
                  const present = choice.modelIds.filter((id) => alreadyAdded.has(id)).length;
                  return (
                    <BetTypeChoiceRow
                      key={choice.key}
                      choice={choice}
                      present={present}
                      onPick={onPick}
                    />
                  );
                })}
              </View>
            ))
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}

function BetTypeChoiceRow({
  choice,
  present,
  onPick,
}: {
  choice: BetTypeChoice;
  present: number;
  onPick: (modelIds: string[]) => void;
}) {
  const status = choiceAddedLabel(present, choice.modelIds.length);
  const complete = status === 'Added';
  const label = status
    ? `${choice.sport} ${choice.label}. ${choice.subtitle}. ${status}`
    : `${choice.sport} ${choice.label}. ${choice.subtitle}`;
  return (
    <Pressable
      onPress={() => onPick(choice.modelIds)}
      disabled={complete}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: complete }}
      style={({ pressed }) => [styles.modalRow, pressed && !complete && styles.pressed]}
    >
      <View style={[styles.modalRowBody, complete && styles.modalRowDisabled]}>
        <Text style={styles.modalRowText}>{choice.label}</Text>
        <Text style={styles.modalRowSub}>{choice.subtitle}</Text>
      </View>
      {status ? <Text style={styles.modalAdded}>{status}</Text> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { padding: spacing.lg, paddingBottom: spacing.xl },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  label: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  helper: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  nameInput: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    backgroundColor: colors.bg,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  rulesHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  addRuleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.tint,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radii.pill,
  },
  addRuleText: {
    color: colors.textInverse,
    fontWeight: font.weight.semibold,
    fontSize: font.size.footnote,
  },
  emptyRules: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    fontStyle: 'italic',
    paddingVertical: spacing.md,
    textAlign: 'center',
  },
  ruleRow: {
    backgroundColor: colors.bg,
    borderRadius: radii.sm,
    padding: spacing.md,
    marginTop: spacing.sm,
  },
  ruleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  ruleRetired: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    marginTop: 2,
  },
  ruleModel: {
    flex: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  ruleFields: { flexDirection: 'row', gap: spacing.md },
  // Same dim as saveBtnDisabled / modalRowDisabled: a floor that does nothing
  // must not look like one that does.
  ruleFieldsRetired: { opacity: 0.45 },
  ruleField: { flex: 1 },
  ruleFieldLabel: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginBottom: 4,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
  },
  ruleInput: {
    flex: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    paddingVertical: spacing.sm,
  },
  inputSuffix: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    marginLeft: 4,
  },

  // Filters
  chipGroup: { marginBottom: spacing.md },
  chipGroupHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  groupTitle: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  chipState: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.medium,
  },
  groupHelp: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
    marginBottom: spacing.sm,
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: radii.pill,
    backgroundColor: colors.bg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separator,
  },
  chipOn: {
    backgroundColor: colors.tint,
    borderColor: colors.tint,
  },
  chipText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  chipTextOn: {
    color: colors.textInverse,
    fontWeight: font.weight.semibold,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.separator,
    marginVertical: spacing.md,
  },
  rangeHeadRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  rangeLive: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  rangeClear: {
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rangeClearText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },

  // Footer preview
  footer: {
    backgroundColor: colors.bgCard,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  previewRow: {
    flexDirection: 'row',
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  previewStat: { flex: 1 },
  previewLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  previewValue: {
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginTop: 1,
  },
  previewCaption: {
    fontSize: font.size.nano,
    color: colors.textTertiary,
    marginTop: 1,
  },
  previewEmpty: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    marginBottom: spacing.md,
    textAlign: 'center',
  },
  previewLoading: { marginBottom: spacing.sm },
  saveBtn: {
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  saveBtnDisabled: {
    opacity: 0.4,
  },
  saveBtnText: {
    color: colors.textInverse,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  deleteBtn: {
    alignItems: 'center',
    paddingVertical: spacing.md,
    marginTop: spacing.sm,
  },
  deleteBtnText: {
    color: colors.avoid,
    fontSize: font.size.body,
    fontWeight: font.weight.medium,
  },
  pressed: { opacity: 0.7 },
  modalContainer: { flex: 1, backgroundColor: colors.bg },
  modalHeader: {
    minHeight: 52,
    justifyContent: 'center',
    paddingVertical: spacing.sm,
    backgroundColor: colors.bgCard,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  modalTitle: {
    textAlign: 'center',
    // Clears the Cancel button. The title truncates inside this inset
    // instead of sliding under it when Dynamic Type grows.
    marginHorizontal: 100,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  modalCancelBtn: {
    position: 'absolute',
    left: spacing.lg,
    top: 0,
    bottom: 0,
    zIndex: 1,
    minHeight: 44,
    justifyContent: 'center',
  },
  modalCancel: {
    fontSize: font.size.body,
    color: colors.textSecondary,
  },
  modalSection: { marginBottom: spacing.lg },
  modalList: { padding: spacing.lg },
  modalSectionTitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: spacing.sm,
  },
  modalRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginBottom: spacing.xs,
  },
  modalRowDisabled: { opacity: 0.45 },
  modalRowBody: { flex: 1 },
  modalRowText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  modalRowSub: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  modalAdded: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
    marginLeft: spacing.sm,
  },
});

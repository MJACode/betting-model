import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
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
import {
  CHIP_GROUPS,
  DEFAULT_FILTERS,
  LINE_VALUE_OPTIONS,
  PUBLIC_PCT_OPTIONS,
  chipSelection,
  nearestOption,
  setNumericFilter,
  toggleChip,
} from '@/lib/customModelFilters';
import { formatPctSigned } from '@/lib/format';
import { BET_TYPE_GROUPS, betTypeLabel } from '@/lib/modelMeta';
import { ACTION_THRESHOLDS } from '@/lib/thresholds';
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

  // Drop a blank EV floor entirely so saved rules stay minimal and the RPC
  // payload matches what older builds send for the same criteria.
  const cleanRules = useMemo<CustomModelRule[]>(
    () =>
      rules.map(({ uid: _u, ...r }) =>
        r.min_ev == null
          ? { model_id: r.model_id, min_prob: r.min_prob, min_edge: r.min_edge }
          : r,
      ),
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

  const onSave = () => {
    if (rules.length === 0) {
      Alert.alert('Add at least one bet type', 'A model needs one or more bet types to match picks.');
      return;
    }
    if (editingId) update(editingId, { name, rules: cleanRules, filters });
    else create(name, cleanRules, filters);
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

  const addRule = (modelId: string) => {
    const defaults = ACTION_THRESHOLDS[modelId] ?? { min_prob: 0.6, min_edge: 0.05 };
    setRules((prev) => [
      ...prev,
      { uid: uid(), model_id: modelId, min_prob: defaults.min_prob, min_edge: defaults.min_edge },
    ]);
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
            >
              <Ionicons name="add" size={18} color={colors.textInverse} />
              <Text style={styles.addRuleText}>Add bet type</Text>
            </Pressable>
          </View>
          <Text style={styles.helper}>
            Pick the markets your model bets — moneyline, totals, a specific player prop — and set
            your minimums for each. A pick qualifies when it's one of these bet types and clears
            that type's numbers. Add several to combine them.
          </Text>
          <Text style={styles.helper}>
            Model % is our projected win probability. Edge is model % minus DraftKings' implied
            probability. EV is expected profit per $1 at the DK price — leave it blank to skip
            (picks with no DK price can never clear an EV floor).
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

          <Text style={styles.groupTitle}>Price range</Text>
          <Text style={styles.groupHelp}>
            American odds on the price the pick was measured at. Leave blank for any price — a
            floor of −140 skips the heavily juiced side, a ceiling of +200 skips longshots.
          </Text>
          <View style={styles.numRow}>
            <NumberField
              label="Lowest price"
              placeholder="Any"
              value={filters.minOdds}
              onCommit={(v) => setFilters((f) => setNumericFilter(f, 'minOdds', v))}
            />
            <NumberField
              label="Highest price"
              placeholder="Any"
              value={filters.maxOdds}
              onCommit={(v) => setFilters((f) => setNumericFilter(f, 'maxOdds', v))}
            />
          </View>

          <View style={styles.divider} />

          <Text style={styles.groupTitle}>Line value</Text>
          <Text style={styles.groupHelp}>
            The betting line the pick was priced at — a game total (e.g. 8.5 runs), a spread, or a
            prop line (e.g. 5.5 Ks). Moneyline picks carry no line, so setting a range drops them.
          </Text>
          <View style={styles.numRow}>
            <PickerField
              label="Line at least"
              title="Line at least"
              options={LINE_VALUE_OPTIONS}
              value={filters.minLine}
              onCommit={(v) => setFilters((f) => setNumericFilter(f, 'minLine', v))}
            />
            <PickerField
              label="Line at most"
              title="Line at most"
              options={LINE_VALUE_OPTIONS}
              value={filters.maxLine}
              onCommit={(v) => setFilters((f) => setNumericFilter(f, 'maxLine', v))}
            />
          </View>

          <View style={styles.divider} />

          <Text style={styles.groupTitle}>Public backing</Text>
          <Text style={styles.groupHelp}>
            Share of public bets on our side. Only full-game moneyline, spread and total picks
            carry splits, so setting either of these drops all props and First-5 picks.
          </Text>
          <View style={styles.numRow}>
            <PickerField
              label="At most"
              title="Public backing at most"
              suffix="%"
              options={PUBLIC_PCT_OPTIONS}
              value={filters.maxPublicBetPct}
              onCommit={(v) => setFilters((f) => setNumericFilter(f, 'maxPublicBetPct', v))}
            />
            <PickerField
              label="At least"
              title="Public backing at least"
              suffix="%"
              options={PUBLIC_PCT_OPTIONS}
              value={filters.minPublicBetPct}
              onCommit={(v) => setFilters((f) => setNumericFilter(f, 'minPublicBetPct', v))}
            />
          </View>

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
          <Pressable onPress={onDelete} style={styles.deleteBtn}>
            <Text style={styles.deleteBtnText}>Delete model</Text>
          </Pressable>
        ) : null}
      </ScrollView>

      <PreviewFooter
        hasRules={cleanRules.length > 0}
        loading={backtestLoading || todayLoading}
        todayMatches={todayMatches}
        backtest={backtest}
        saveLabel={editingId ? 'Save changes' : 'Create model'}
        onSave={onSave}
      />

      <ModelPickerModal
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onPick={addRule}
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
  loading,
  todayMatches,
  backtest,
  saveLabel,
  onSave,
}: {
  hasRules: boolean;
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
      {hasRules ? (
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
      {loading && hasRules ? (
        <ActivityIndicator style={styles.previewLoading} size="small" />
      ) : null}
      <Pressable onPress={onSave} style={({ pressed }) => [styles.saveBtn, pressed && styles.pressed]}>
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

function NumberField({
  label,
  placeholder,
  suffix,
  value,
  onCommit,
}: {
  label: string;
  placeholder: string;
  suffix?: string;
  value: number | undefined;
  onCommit: (value: number | null) => void;
}) {
  const [text, setText] = useState<string>(value == null ? '' : String(value));

  // Keep the field in step when the value changes from outside (e.g. loading an
  // existing model), without stomping what the user is mid-way through typing.
  useEffect(() => {
    setText(value == null ? '' : String(value));
  }, [value]);

  const commit = () => {
    const trimmed = text.trim();
    if (trimmed === '' || trimmed === '-' || trimmed === '+') {
      onCommit(null);
      setText('');
      return;
    }
    const v = parseFloat(trimmed);
    if (Number.isFinite(v)) onCommit(v);
    else setText(value == null ? '' : String(value));
  };

  return (
    <View style={styles.numField}>
      <Text style={styles.ruleFieldLabel}>{label}</Text>
      <View style={styles.inputWrap}>
        <TextInput
          style={styles.ruleInput}
          value={text}
          onChangeText={setText}
          onBlur={commit}
          placeholder={placeholder}
          placeholderTextColor={colors.textTertiary}
          keyboardType="numbers-and-punctuation"
          maxLength={6}
        />
        {suffix ? <Text style={styles.inputSuffix}>{suffix}</Text> : null}
      </View>
    </View>
  );
}

/** Fixed row height so the sheet can open scrolled to the current value. */
const PICKER_ROW_HEIGHT = 44;

/**
 * A numeric filter you scroll and tap rather than type.
 *
 * Line values and public-backing percentages come from fixed option sets
 * (customModelFilters.LINE_VALUE_OPTIONS / PUBLIC_PCT_OPTIONS), so there is
 * nothing to mistype and no invalid state to validate. Models saved when these
 * were free-text can hold an off-list number (8.25) — it still displays as
 * stored, and the list highlights the nearest option.
 */
function PickerField({
  label,
  title,
  options,
  suffix,
  value,
  onCommit,
}: {
  label: string;
  title: string;
  options: number[];
  suffix?: string;
  value: number | undefined;
  onCommit: (value: number | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = nearestOption(options, value ?? null);
  const initialIndex = selected == null ? 0 : Math.max(0, options.indexOf(selected));

  const choose = (v: number | null) => {
    onCommit(v);
    setOpen(false);
  };

  return (
    <View style={styles.numField}>
      <Text style={styles.ruleFieldLabel}>{label}</Text>
      <Pressable
        onPress={() => setOpen(true)}
        style={({ pressed }) => [styles.pickerBox, pressed && styles.pressed]}
      >
        <Text style={value == null ? styles.pickerPlaceholder : styles.pickerValue}>
          {value == null ? 'Any' : `${value}${suffix ?? ''}`}
        </Text>
        <Ionicons name="chevron-down" size={15} color={colors.textTertiary} />
      </Pressable>

      <Modal
        visible={open}
        transparent
        animationType="slide"
        onRequestClose={() => setOpen(false)}
      >
        <Pressable style={styles.sheetBackdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <View style={styles.sheetHead}>
              <Text style={styles.sheetTitle}>{title}</Text>
              <Pressable onPress={() => setOpen(false)} hitSlop={10}>
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </Pressable>
            </View>

            <Pressable
              onPress={() => choose(null)}
              style={({ pressed }) => [styles.pickerRow, pressed && styles.pressed]}
            >
              <Text style={value == null ? styles.pickerRowTextOn : styles.pickerRowText}>
                Any
              </Text>
              {value == null ? (
                <Ionicons name="checkmark" size={18} color={colors.tint} />
              ) : null}
            </Pressable>

            <FlatList
              data={options}
              keyExtractor={(o) => String(o)}
              initialScrollIndex={initialIndex}
              getItemLayout={(_, index) => ({
                length: PICKER_ROW_HEIGHT,
                offset: PICKER_ROW_HEIGHT * index,
                index,
              })}
              renderItem={({ item }) => {
                const on = selected === item && value != null;
                return (
                  <Pressable
                    onPress={() => choose(item)}
                    style={({ pressed }) => [styles.pickerRow, pressed && styles.pressed]}
                  >
                    <Text style={on ? styles.pickerRowTextOn : styles.pickerRowText}>
                      {item}
                      {suffix ?? ''}
                    </Text>
                    {on ? <Ionicons name="checkmark" size={18} color={colors.tint} /> : null}
                  </Pressable>
                );
              }}
            />
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
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
  const [probText, setProbText] = useState<string>(String(Math.round(rule.min_prob * 100)));
  const [edgeText, setEdgeText] = useState<string>(String(Math.round(rule.min_edge * 100)));
  const [evText, setEvText] = useState<string>(
    rule.min_ev == null ? '' : String(Math.round(rule.min_ev * 100)),
  );

  const commitProb = () => {
    const v = parseFloat(probText);
    if (Number.isFinite(v) && v >= 0 && v <= 100) onChange({ min_prob: v / 100 });
    else setProbText(String(Math.round(rule.min_prob * 100)));
  };
  const commitEdge = () => {
    const v = parseFloat(edgeText);
    if (Number.isFinite(v) && v >= -100 && v <= 100) onChange({ min_edge: v / 100 });
    else setEdgeText(String(Math.round(rule.min_edge * 100)));
  };
  const commitEv = () => {
    const trimmed = evText.trim();
    if (trimmed === '' || trimmed === '-') {
      onChange({ min_ev: null });
      setEvText('');
      return;
    }
    const v = parseFloat(trimmed);
    if (Number.isFinite(v) && v >= -100 && v <= 100) onChange({ min_ev: v / 100 });
    else setEvText(rule.min_ev == null ? '' : String(Math.round(rule.min_ev * 100)));
  };

  return (
    <View style={styles.ruleRow}>
      <View style={styles.ruleHeader}>
        <Text style={styles.ruleModel}>{betTypeLabel(rule.model_id)}</Text>
        <Pressable onPress={onRemove} hitSlop={8}>
          <Ionicons name="trash-outline" size={18} color={colors.avoid} />
        </Pressable>
      </View>
      <View style={styles.ruleFields}>
        <View style={styles.ruleField}>
          <Text style={styles.ruleFieldLabel}>Min model %</Text>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.ruleInput}
              value={probText}
              onChangeText={setProbText}
              onBlur={commitProb}
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
              keyboardType="decimal-pad"
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
 * The bet-type picker — every market the database grades, grouped by sport and
 * shown by its market name ("Moneyline", "Batter Hits"). Users build from bet
 * types plus the data points below; the in-house models never surface here.
 */
function ModelPickerModal({
  visible,
  onClose,
  onPick,
  alreadyAdded,
}: {
  visible: boolean;
  onClose: () => void;
  onPick: (modelId: string) => void;
  alreadyAdded: Set<string>;
}) {
  const typeTag = (type: string): string | null => {
    if (type === 'pitcher_prop') return 'Pitcher prop';
    if (type === 'batter_prop') return 'Batter prop';
    if (type === 'player_prop') return 'Player prop';
    return null;
  };

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={styles.modalContainer}>
        <View style={styles.modalHeader}>
          <Pressable onPress={onClose} hitSlop={8}>
            <Text style={styles.modalCancel}>Cancel</Text>
          </Pressable>
          <Text style={styles.modalTitle}>Pick a bet type</Text>
          <View style={{ width: 50 }} />
        </View>
        <ScrollView contentContainerStyle={{ padding: spacing.lg }}>
          {BET_TYPE_GROUPS.map((group) => (
            <View key={group.sport} style={styles.modalSection}>
              <Text style={styles.modalSectionTitle}>{group.sport}</Text>
              {group.options.map((m) => {
                const added = alreadyAdded.has(m.id);
                const tag = typeTag(m.type);
                return (
                  <Pressable
                    key={m.id}
                    onPress={() => onPick(m.id)}
                    disabled={added}
                    style={({ pressed }) => [
                      styles.modalRow,
                      added && styles.modalRowDisabled,
                      pressed && !added && styles.pressed,
                    ]}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={styles.modalRowText}>{m.label}</Text>
                      {tag ? <Text style={styles.modalRowSub}>{tag}</Text> : null}
                    </View>
                    {added ? <Text style={styles.modalAdded}>Added</Text> : null}
                  </Pressable>
                );
              })}
            </View>
          ))}
        </ScrollView>
      </View>
    </Modal>
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
  ruleModel: {
    flex: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  ruleFields: { flexDirection: 'row', gap: spacing.md },
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
  numRow: { flexDirection: 'row', gap: spacing.md },
  numField: { flex: 1 },

  // Scroll pickers (line value, public backing)
  pickerBox: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.bgCard,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
  },
  pickerValue: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  pickerPlaceholder: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
  },
  sheetBackdrop: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.35)',
  },
  sheet: {
    maxHeight: '65%',
    backgroundColor: colors.bgElevated,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingBottom: spacing.lg,
  },
  sheetHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  sheetTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  pickerRow: {
    height: PICKER_ROW_HEIGHT,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
  },
  pickerRowText: {
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  pickerRowTextOn: {
    fontSize: font.size.body,
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
    fontSize: 10,
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
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.bgCard,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  modalTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  modalCancel: {
    fontSize: font.size.body,
    color: colors.textSecondary,
  },
  modalSection: { marginBottom: spacing.lg },
  modalSectionTitle: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
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
  modalRowText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  modalRowSub: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 2,
  },
  modalAdded: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
  },
});

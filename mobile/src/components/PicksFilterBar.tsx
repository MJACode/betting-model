import React, { useMemo, useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { MODEL_META } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { SignalType } from '@/types';

export type ModelCategory = 'game' | 'pitcher_prop' | 'batter_prop';

export interface PicksFilterState {
  signals: Set<SignalType>;
  categories: Set<ModelCategory>;
  modelIds: Set<string>; // empty = all
  minProb: number | null;
  minEdge: number | null;
}

export const DEFAULT_FILTER: PicksFilterState = {
  signals: new Set<SignalType>(['BET', 'AVOID', 'NONE']),
  categories: new Set<ModelCategory>(['game', 'pitcher_prop', 'batter_prop']),
  modelIds: new Set<string>(),
  minProb: null,
  minEdge: null,
};

const ALL_SIGNALS: SignalType[] = ['BET', 'AVOID', 'NONE'];
const CATEGORY_LABEL: Record<ModelCategory, string> = {
  game: 'Game',
  pitcher_prop: 'Pitcher',
  batter_prop: 'Batter',
};

export function activeFilterCount(state: PicksFilterState): number {
  let n = 0;
  if (state.signals.size < ALL_SIGNALS.length) n++;
  if (state.categories.size < 3) n++;
  if (state.modelIds.size > 0) n++;
  if (state.minProb != null) n++;
  if (state.minEdge != null) n++;
  return n;
}

interface Props {
  state: PicksFilterState;
  onChange: (next: PicksFilterState) => void;
  totalShown: number;
  totalAll: number;
}

export function PicksFilterBar({ state, onChange, totalShown, totalAll }: Props) {
  const [open, setOpen] = useState(false);
  const active = activeFilterCount(state);

  return (
    <>
      <View style={styles.bar}>
        <Pressable
          onPress={() => setOpen(true)}
          style={({ pressed }) => [styles.filterBtn, pressed && styles.pressed]}
        >
          <Ionicons name="filter-outline" size={16} color={colors.tint} />
          <Text style={styles.filterBtnText}>
            Filter{active > 0 ? ` (${active})` : ''}
          </Text>
        </Pressable>
        <Text style={styles.countText}>
          {totalShown === totalAll
            ? `${totalAll} pick${totalAll === 1 ? '' : 's'}`
            : `${totalShown} of ${totalAll}`}
        </Text>
        {active > 0 ? (
          <Pressable onPress={() => onChange(cloneDefault())} hitSlop={8}>
            <Text style={styles.clearText}>Clear</Text>
          </Pressable>
        ) : null}
      </View>
      <FilterModal
        visible={open}
        state={state}
        onClose={() => setOpen(false)}
        onChange={onChange}
      />
    </>
  );
}

function cloneDefault(): PicksFilterState {
  return {
    signals: new Set(DEFAULT_FILTER.signals),
    categories: new Set(DEFAULT_FILTER.categories),
    modelIds: new Set<string>(),
    minProb: null,
    minEdge: null,
  };
}

interface FilterModalProps {
  visible: boolean;
  state: PicksFilterState;
  onClose: () => void;
  onChange: (next: PicksFilterState) => void;
}

function FilterModal({ visible, state, onClose, onChange }: FilterModalProps) {
  const [draft, setDraft] = useState<PicksFilterState>(state);
  const [probText, setProbText] = useState<string>(
    state.minProb != null ? String(Math.round(state.minProb * 100)) : '',
  );
  const [edgeText, setEdgeText] = useState<string>(
    state.minEdge != null ? String(Math.round(state.minEdge * 100)) : '',
  );

  // Reset draft when modal opens
  React.useEffect(() => {
    if (visible) {
      setDraft({
        signals: new Set(state.signals),
        categories: new Set(state.categories),
        modelIds: new Set(state.modelIds),
        minProb: state.minProb,
        minEdge: state.minEdge,
      });
      setProbText(state.minProb != null ? String(Math.round(state.minProb * 100)) : '');
      setEdgeText(state.minEdge != null ? String(Math.round(state.minEdge * 100)) : '');
    }
  }, [visible, state]);

  const modelsByCategory = useMemo(() => {
    const groups: Record<ModelCategory, Array<{ id: string; label: string }>> = {
      game: [],
      pitcher_prop: [],
      batter_prop: [],
    };
    for (const [id, meta] of Object.entries(MODEL_META)) {
      groups[meta.type].push({ id, label: meta.longLabel });
    }
    return groups;
  }, []);

  const toggleSignal = (s: SignalType) => {
    const next = new Set(draft.signals);
    if (next.has(s)) next.delete(s);
    else next.add(s);
    setDraft({ ...draft, signals: next });
  };

  const toggleCategory = (c: ModelCategory) => {
    const next = new Set(draft.categories);
    if (next.has(c)) next.delete(c);
    else next.add(c);
    setDraft({ ...draft, categories: next });
  };

  const toggleModel = (id: string) => {
    const next = new Set(draft.modelIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setDraft({ ...draft, modelIds: next });
  };

  const apply = () => {
    const prob = parseFloat(probText);
    const edge = parseFloat(edgeText);
    onChange({
      signals: draft.signals,
      categories: draft.categories,
      modelIds: draft.modelIds,
      minProb: Number.isFinite(prob) && prob > 0 ? prob / 100 : null,
      minEdge: Number.isFinite(edge) ? edge / 100 : null,
    });
    onClose();
  };

  const reset = () => {
    setDraft(cloneDefault());
    setProbText('');
    setEdgeText('');
  };

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={styles.modalContainer}>
        <View style={styles.modalHeader}>
          <Pressable onPress={onClose} hitSlop={8}>
            <Text style={styles.modalCancel}>Cancel</Text>
          </Pressable>
          <Text style={styles.modalTitle}>Filter picks</Text>
          <Pressable onPress={apply} hitSlop={8}>
            <Text style={styles.modalApply}>Apply</Text>
          </Pressable>
        </View>

        <ScrollView contentContainerStyle={styles.modalBody}>
          <Section title="Signal">
            <View style={styles.chipRow}>
              {ALL_SIGNALS.map((s) => {
                const active = draft.signals.has(s);
                return (
                  <Chip key={s} label={s} active={active} onPress={() => toggleSignal(s)} />
                );
              })}
            </View>
          </Section>

          <Section title="Category">
            <View style={styles.chipRow}>
              {(['game', 'pitcher_prop', 'batter_prop'] as ModelCategory[]).map((c) => {
                const active = draft.categories.has(c);
                return (
                  <Chip
                    key={c}
                    label={CATEGORY_LABEL[c]}
                    active={active}
                    onPress={() => toggleCategory(c)}
                  />
                );
              })}
            </View>
          </Section>

          <Section title="Models" subtitle="Empty = all enabled. Tap to narrow.">
            {(['game', 'pitcher_prop', 'batter_prop'] as ModelCategory[]).map((c) => (
              <View key={c} style={styles.modelGroup}>
                <Text style={styles.modelGroupLabel}>{CATEGORY_LABEL[c]}</Text>
                <View style={styles.chipRow}>
                  {modelsByCategory[c].map((m) => {
                    const active = draft.modelIds.has(m.id);
                    return (
                      <Chip key={m.id} label={m.label} active={active} onPress={() => toggleModel(m.id)} small />
                    );
                  })}
                </View>
              </View>
            ))}
          </Section>

          <Section title="Thresholds" subtitle="Show only picks at or above.">
            <View style={styles.thresholdRow}>
              <View style={styles.thresholdField}>
                <Text style={styles.thresholdLabel}>Min model probability</Text>
                <View style={styles.inputWrap}>
                  <TextInput
                    style={styles.input}
                    value={probText}
                    onChangeText={setProbText}
                    placeholder="e.g. 65"
                    placeholderTextColor={colors.textTertiary}
                    keyboardType="decimal-pad"
                    maxLength={5}
                  />
                  <Text style={styles.inputSuffix}>%</Text>
                </View>
              </View>
              <View style={styles.thresholdField}>
                <Text style={styles.thresholdLabel}>Min edge</Text>
                <View style={styles.inputWrap}>
                  <TextInput
                    style={styles.input}
                    value={edgeText}
                    onChangeText={setEdgeText}
                    placeholder="e.g. 10"
                    placeholderTextColor={colors.textTertiary}
                    keyboardType="decimal-pad"
                    maxLength={5}
                  />
                  <Text style={styles.inputSuffix}>%</Text>
                </View>
              </View>
            </View>
          </Section>

          <Pressable onPress={reset} style={({ pressed }) => [styles.resetBtn, pressed && styles.pressed]}>
            <Text style={styles.resetBtnText}>Reset all filters</Text>
          </Pressable>
        </ScrollView>
      </View>
    </Modal>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {subtitle ? <Text style={styles.sectionSub}>{subtitle}</Text> : null}
      {children}
    </View>
  );
}

function Chip({
  label,
  active,
  onPress,
  small,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
  small?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        small && styles.chipSmall,
        active && styles.chipActive,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.chipText, small && styles.chipTextSmall, active && styles.chipTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

interface FilterablePick {
  signal_type: SignalType;
  model_id: string;
  model_probability: number;
  edge: number;
}

export function applyFilter<T extends { pick: FilterablePick }>(
  items: T[],
  state: PicksFilterState,
): T[] {
  return items.filter((it) => {
    const p = it.pick;
    if (!state.signals.has(p.signal_type)) return false;
    const meta = MODEL_META[p.model_id];
    if (meta && !state.categories.has(meta.type)) return false;
    if (state.modelIds.size > 0 && !state.modelIds.has(p.model_id)) return false;
    if (state.minProb != null && p.model_probability < state.minProb) return false;
    if (state.minEdge != null && p.edge < state.minEdge) return false;
    return true;
  });
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    gap: spacing.md,
    backgroundColor: colors.bg,
  },
  filterBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  filterBtnText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  countText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  clearText: {
    fontSize: font.size.footnote,
    color: colors.avoid,
    fontWeight: font.weight.medium,
  },
  pressed: { opacity: 0.65 },
  modalContainer: {
    flex: 1,
    backgroundColor: colors.bg,
  },
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
  modalApply: {
    fontSize: font.size.body,
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
  modalBody: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  section: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  sectionTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  sectionSub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: radii.pill,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  chipSmall: {
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  chipActive: {
    backgroundColor: colors.tint,
    borderColor: colors.tint,
  },
  chipText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  chipTextSmall: {
    fontSize: font.size.caption,
  },
  chipTextActive: {
    color: colors.textInverse,
  },
  modelGroup: {
    marginTop: spacing.md,
  },
  modelGroupLabel: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  thresholdRow: {
    flexDirection: 'row',
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  thresholdField: {
    flex: 1,
  },
  thresholdLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bg,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
  },
  input: {
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
  resetBtn: {
    alignItems: 'center',
    paddingVertical: spacing.md,
    marginTop: spacing.sm,
  },
  resetBtnText: {
    fontSize: font.size.body,
    color: colors.avoid,
    fontWeight: font.weight.medium,
  },
});

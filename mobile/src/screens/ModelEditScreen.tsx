import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useCustomModels } from '@/hooks/useCustomModels';
import { MODEL_META } from '@/lib/modelMeta';
import { ACTION_THRESHOLDS } from '@/lib/thresholds';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { CustomModelRule, RootStackParamList } from '@/types';

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
    existing
      ? existing.rules.map((r) => ({ ...r, uid: uid() }))
      : [],
  );
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    navigation.setOptions({ title: editingId ? 'Edit model' : 'New model' });
  }, [navigation, editingId]);

  const onSave = () => {
    if (rules.length === 0) {
      Alert.alert('Add at least one rule', 'A model needs one or more model_id rules to filter picks.');
      return;
    }
    const clean: CustomModelRule[] = rules.map(({ uid: _u, ...r }) => r);
    if (editingId) {
      update(editingId, { name, rules: clean });
    } else {
      create(name, clean);
    }
    navigation.goBack();
  };

  const onDelete = () => {
    if (!editingId) return;
    Alert.alert('Delete this model?', 'You can recreate it any time. Backtest history is computed live, nothing else is lost.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          remove(editingId);
          navigation.goBack();
        },
      },
    ]);
  };

  const addRule = (modelId: string) => {
    const defaults = ACTION_THRESHOLDS[modelId] ?? { min_prob: 0.6, min_edge: 0.05 };
    setRules((prev) => [...prev, { uid: uid(), model_id: modelId, min_prob: defaults.min_prob, min_edge: defaults.min_edge }]);
    setPickerOpen(false);
  };

  const updateRule = (ruleUid: string, patch: Partial<CustomModelRule>) => {
    setRules((prev) => prev.map((r) => (r.uid === ruleUid ? { ...r, ...patch } : r)));
  };

  const removeRule = (ruleUid: string) => {
    setRules((prev) => prev.filter((r) => r.uid !== ruleUid));
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.list}>
        <View style={styles.card}>
          <Text style={styles.label}>Name</Text>
          <TextInput
            style={styles.nameInput}
            value={name}
            onChangeText={setName}
            placeholder="e.g. High-conviction MLB ML"
            placeholderTextColor={colors.textTertiary}
            maxLength={60}
          />
        </View>

        <View style={styles.card}>
          <View style={styles.rulesHeader}>
            <Text style={styles.label}>Rules</Text>
            <Pressable
              onPress={() => setPickerOpen(true)}
              style={({ pressed }) => [styles.addRuleBtn, pressed && styles.pressed]}
              hitSlop={6}
            >
              <Ionicons name="add" size={18} color={colors.textInverse} />
              <Text style={styles.addRuleText}>Add rule</Text>
            </Pressable>
          </View>
          <Text style={styles.helper}>
            A pick matches the model when it passes any rule (OR'd together). Each rule = a model
            plus minimum probability and edge.
          </Text>

          {rules.length === 0 ? (
            <Text style={styles.emptyRules}>No rules yet. Tap Add rule to pick a model.</Text>
          ) : (
            rules.map((r) => <RuleRow key={r.uid} rule={r} onChange={(p) => updateRule(r.uid, p)} onRemove={() => removeRule(r.uid)} />)
          )}
        </View>

        <Pressable onPress={onSave} style={({ pressed }) => [styles.saveBtn, pressed && styles.pressed]}>
          <Text style={styles.saveBtnText}>{editingId ? 'Save changes' : 'Create model'}</Text>
        </Pressable>

        {editingId ? (
          <Pressable onPress={onDelete} style={styles.deleteBtn}>
            <Text style={styles.deleteBtnText}>Delete model</Text>
          </Pressable>
        ) : null}
      </ScrollView>

      <ModelPickerModal
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onPick={addRule}
      />
    </SafeAreaView>
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
  const meta = MODEL_META[rule.model_id];
  const [probText, setProbText] = useState<string>(String(Math.round(rule.min_prob * 100)));
  const [edgeText, setEdgeText] = useState<string>(String(Math.round(rule.min_edge * 100)));

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

  return (
    <View style={styles.ruleRow}>
      <View style={styles.ruleHeader}>
        <Text style={styles.ruleModel}>{meta?.longLabel ?? rule.model_id}</Text>
        <Pressable onPress={onRemove} hitSlop={8}>
          <Ionicons name="trash-outline" size={18} color={colors.avoid} />
        </Pressable>
      </View>
      <View style={styles.ruleFields}>
        <View style={styles.ruleField}>
          <Text style={styles.ruleFieldLabel}>Min prob</Text>
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
          <Text style={styles.ruleFieldLabel}>Min edge</Text>
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
      </View>
    </View>
  );
}

function ModelPickerModal({
  visible,
  onClose,
  onPick,
}: {
  visible: boolean;
  onClose: () => void;
  onPick: (modelId: string) => void;
}) {
  const grouped = useMemo(() => {
    const groups: Record<string, Array<{ id: string; label: string }>> = {
      game: [],
      pitcher_prop: [],
      batter_prop: [],
    };
    for (const [id, meta] of Object.entries(MODEL_META)) {
      groups[meta.type]!.push({ id, label: meta.longLabel });
    }
    return groups;
  }, []);

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={styles.modalContainer}>
        <View style={styles.modalHeader}>
          <Pressable onPress={onClose} hitSlop={8}>
            <Text style={styles.modalCancel}>Cancel</Text>
          </Pressable>
          <Text style={styles.modalTitle}>Pick a model</Text>
          <View style={{ width: 50 }} />
        </View>
        <ScrollView contentContainerStyle={{ padding: spacing.lg }}>
          {(['game', 'pitcher_prop', 'batter_prop'] as const).map((cat) => (
            <View key={cat} style={styles.modalSection}>
              <Text style={styles.modalSectionTitle}>
                {cat === 'game' ? 'Game' : cat === 'pitcher_prop' ? 'Pitcher props' : 'Batter props'}
              </Text>
              {grouped[cat].map((m) => (
                <Pressable
                  key={m.id}
                  onPress={() => onPick(m.id)}
                  style={({ pressed }) => [styles.modalRow, pressed && styles.pressed]}
                >
                  <Text style={styles.modalRowText}>{m.label}</Text>
                  <Text style={styles.modalRowSub}>{m.id}</Text>
                </Pressable>
              ))}
            </View>
          ))}
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { padding: spacing.lg, paddingBottom: spacing.xxl },
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
  saveBtn: {
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.sm,
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
    backgroundColor: colors.bgCard,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginBottom: spacing.xs,
  },
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
});

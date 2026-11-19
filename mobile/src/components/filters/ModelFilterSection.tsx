/**
 * The MODEL section of the Picks filter sheet (Matt, 2026-11-18).
 *
 * One row per model with picks on the board: its name, its total published
 * record ("+4.2u · 61 bets"), a HOT / COLD tag when its last 7 days earn one
 * (lib/modelHeat.ts), how many picks it has on this board, and a checkbox.
 * Rows, not chips: a chip cannot carry the record line under the name, and
 * the same row shape as the Games section keeps the sheet one language.
 *
 * Nothing selected = every model, the same as the Games section.
 */

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing, opacity } from '@/lib/theme';
import { modelShort } from '@/lib/modelMeta';
import {
  modelRecordLine,
  modelRecordSpoken,
  type ModelRecordSummary,
} from '@/lib/modelHeat';
import type { PresentModel } from '@/lib/pickFilterState';

export function ModelFilterSection({
  models,
  selected,
  records,
  onToggle,
  itemNoun,
}: {
  models: PresentModel[];
  selected: Set<string>;
  records: Record<string, ModelRecordSummary>;
  onToggle: (modelId: string) => void;
  itemNoun: string;
}) {
  return (
    <View>
      {models.map(({ modelId, count }) => {
        const checked = selected.has(modelId);
        const rec = records[modelId];
        const name = modelShort(modelId);
        const units = rec && rec.bets > 0 ? Math.round(rec.units * 10) / 10 : 0;
        return (
          <Pressable
            key={modelId}
            onPress={() => onToggle(modelId)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked }}
            accessibilityLabel={`${name}, ${count} ${itemNoun}${count === 1 ? '' : 's'} on this board, ${modelRecordSpoken(rec)}`}
            style={({ pressed }) => [styles.row, pressed && styles.pressed]}
          >
            <View style={styles.text}>
              <View style={styles.nameLine}>
                <Text style={styles.name} numberOfLines={1}>
                  {name}
                </Text>
                {rec?.heat ? <HeatTag heat={rec.heat} /> : null}
              </View>
              <Text
                style={[
                  styles.record,
                  units > 0 && styles.recordUp,
                  units < 0 && styles.recordDown,
                ]}
                numberOfLines={1}
              >
                {modelRecordLine(rec)}
              </Text>
            </View>
            <Text style={styles.count}>{count}</Text>
            <View style={[styles.box, checked && styles.boxOn]}>
              {checked ? <Ionicons name="checkmark" size={14} color={colors.textInverse} /> : null}
            </View>
          </Pressable>
        );
      })}
      <Text style={styles.note}>
        Record: units and settled bets since the record started. Hot or cold: up or down 3u or
        more over the last 7 days, on 8 or more bets.
      </Text>
    </View>
  );
}

function HeatTag({ heat }: { heat: 'hot' | 'cold' }) {
  const hot = heat === 'hot';
  return (
    <View
      style={[styles.tag, hot ? styles.tagHot : styles.tagCold]}
      // The row's label already says it; the tag is a picture of that.
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Ionicons name={hot ? 'flame' : 'snow'} size={11} color={hot ? colors.betInk : colors.avoidInk} />
      <Text style={[styles.tagText, { color: hot ? colors.betInk : colors.avoidInk }]}>
        {hot ? 'HOT' : 'COLD'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    minHeight: 52,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  pressed: { opacity: opacity.pressed },
  text: { flex: 1, minWidth: 0 },
  nameLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  name: {
    flexShrink: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  record: {
    marginTop: 2,
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  recordUp: { color: colors.betInk },
  recordDown: { color: colors.avoidInk },
  count: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  tag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  tagHot: { backgroundColor: colors.betSoft },
  tagCold: { backgroundColor: colors.avoidSoft },
  tagText: { fontSize: font.size.nano, fontWeight: font.weight.bold, letterSpacing: 0.4 },
  box: {
    width: 22,
    height: 22,
    borderRadius: radii.sm,
    borderWidth: 1.5,
    borderColor: colors.separator,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxOn: { backgroundColor: colors.tint, borderColor: colors.tint },
  note: {
    marginTop: spacing.sm,
    fontSize: font.size.footnote,
    color: colors.textTertiary,
  },
});

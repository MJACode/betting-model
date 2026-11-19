/**
 * The MODEL section of the Picks filter sheet (Matt, 2026-11-18).
 *
 * One row per model with picks on the board: its name, its total published
 * record ("+4.24u · 61 bets"), a HOT / COLD tag when its last 7 days earn one
 * (lib/modelHeat.ts), how many picks it has on this board, and a checkbox.
 * Rows, not chips: a chip cannot carry the record line under the name, and
 * the same row shape as the Games section keeps the sheet one language.
 *
 * Nothing selected = every model, the same as the Games section.
 */

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, opacity, pnlColor, radii, spacing } from '@/lib/theme';
import { modelShort } from '@/lib/modelMeta';
import {
  modelHeatFootnote,
  modelRecordLine,
  modelRecordSpoken,
  type ModelRecordSummary,
} from '@/lib/modelHeat';
import type { ModelRecordsStatus } from '@/hooks/useModelFilterRecords';
import type { PresentModel } from '@/lib/pickFilterState';

const NO_RECORD: ModelRecordSummary = {
  bets: 0,
  units: 0,
  windowBets: 0,
  windowUnits: 0,
  heat: null,
};

export function ModelFilterSection({
  models,
  selected,
  records,
  status,
  onToggle,
  itemNoun,
}: {
  models: PresentModel[];
  selected: Set<string>;
  records: Record<string, ModelRecordSummary>;
  status: ModelRecordsStatus;
  onToggle: (modelId: string) => void;
  itemNoun: string;
}) {
  const ready = status === 'ready';
  return (
    <View>
      {models.map(({ modelId, count }) => {
        const checked = selected.has(modelId);
        // Only a finished read may say "no settled bets"; loading and failure
        // print no record line at all.
        const rec = ready ? (records[modelId] ?? NO_RECORD) : null;
        const name = modelShort(modelId);
        const onBoard = `${count} ${itemNoun}${count === 1 ? '' : 's'}`;
        return (
          <Pressable
            key={modelId}
            onPress={() => onToggle(modelId)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked }}
            accessibilityLabel={`${name}, ${onBoard} on this board${rec ? `, ${modelRecordSpoken(rec)}` : ''}`}
            style={({ pressed }) => [styles.row, pressed && styles.pressed]}
          >
            <View style={styles.text}>
              <View style={styles.nameLine}>
                <Text style={styles.name} numberOfLines={2}>
                  {name}
                </Text>
                {rec?.heat ? <HeatTag heat={rec.heat} /> : null}
              </View>
              {rec ? (
                <Text
                  style={[
                    styles.record,
                    rec.bets > 0 && { color: pnlColor(rec.units, 2) },
                  ]}
                  numberOfLines={2}
                >
                  {modelRecordLine(rec)}
                </Text>
              ) : status === 'error' ? (
                <Text style={styles.record}>Record unavailable</Text>
              ) : null}
            </View>
            <Text style={styles.count} numberOfLines={1}>
              {onBoard}
            </Text>
            <View style={[styles.box, checked && styles.boxOn]}>
              {checked ? <Ionicons name="checkmark" size={14} color={colors.textInverse} /> : null}
            </View>
          </Pressable>
        );
      })}
      {ready ? <Text style={styles.note}>{modelHeatFootnote()}</Text> : null}
    </View>
  );
}

function HeatTag({ heat }: { heat: 'hot' | 'cold' }) {
  const hot = heat === 'hot';
  const ink = hot ? colors.betInk : colors.avoidInk;
  return (
    <View
      style={[styles.tag, hot ? styles.tagHot : styles.tagCold]}
      // The row's label already says it; the tag is a picture of that.
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Ionicons name={hot ? 'flame' : 'snow'} size={11} color={ink} />
      <Text style={[styles.tagText, { color: ink }]} maxFontSizeMultiplier={1.6}>
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
  // Wraps, so at large Dynamic Type the tag drops under the name instead of
  // truncating it to a few letters.
  nameLine: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    columnGap: spacing.xs,
    rowGap: spacing.xs,
  },
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
  count: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  tag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  tagHot: { backgroundColor: colors.betSoft },
  tagCold: { backgroundColor: colors.avoidSoft },
  tagText: { fontSize: font.size.nano, fontWeight: font.weight.bold },
  box: {
    width: 22,
    height: 22,
    borderRadius: radii.sm,
    borderWidth: 1.5,
    // textTertiary, not separator: an empty box's outline needs 3:1 against
    // the card (WCAG 1.4.11); separator measured 1.69:1 (UX review).
    borderColor: colors.textTertiary,
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

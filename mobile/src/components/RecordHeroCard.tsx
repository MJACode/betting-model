import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { EquityPoint } from '@/lib/equityGeometry';
import { RecordInfoSheet } from '@/components/RecordInfoSheet';
import { RecordSparkline } from '@/components/RecordSparkline';
import {
  CLOSING_LINE_TITLE,
  FLAT_BET_ROI_TITLE,
  clvText,
  closingLineBody,
  flatBetRoiBody,
  heroAccessibilityLabel,
  heroStacks,
  heroUnitsText,
  recordLine,
  roiText,
  sinceLine,
  winRateText,
} from '@/lib/recordHero';
import type { TrackRecordSummary } from '@/lib/trackRecord';
import { colors, font, pnlColor, radii, spacing } from '@/lib/theme';

const SPARK_W = 104;
const SPARK_H = 56;

/**
 * Option B headline. One VoiceOver stop, units first. The info buttons are
 * touch targets and rotor actions, not extra stops.
 */
export function RecordHeroCard({
  label,
  summary,
  points,
  notLoaded,
}: {
  label: string;
  summary: TrackRecordSummary;
  points: EquityPoint[];
  notLoaded: boolean;
}) {
  const { fontScale, width } = useWindowDimensions();
  const stacked = heroStacks(fontScale, width);
  const [sheet, setSheet] = useState<'roi' | 'clv' | null>(null);
  const [sparkW, setSparkW] = useState(SPARK_W);
  const units = Number(summary.units ?? 0);
  const risked = Number(summary.risked ?? 0);
  const quiet = notLoaded || summary.picks <= 0;
  const unitsText = heroUnitsText(units, quiet);
  const roi = roiText(summary.roiFlat, risked, quiet);
  const record = recordLine(summary.wins, summary.losses, summary.pushes, quiet);
  const win = winRateText(summary.winRate, summary.wins, summary.losses, quiet);
  const clv = clvText(summary.clvBeatRate, quiet);
  const heroLabel = heroAccessibilityLabel({
    notLoaded,
    picks: summary.picks,
    label,
    units,
    risked,
    roiFlat: summary.roiFlat,
    wins: summary.wins,
    losses: summary.losses,
    pushes: summary.pushes,
    winRate: summary.winRate,
    clvBeatRate: summary.clvBeatRate,
  });
  const open = (which: 'roi' | 'clv') => setSheet(which);
  const sheetTitle = sheet === 'clv' ? CLOSING_LINE_TITLE : FLAT_BET_ROI_TITLE;
  const sheetBody = sheet === 'clv' ? closingLineBody(summary) : flatBetRoiBody();

  return (
    <View style={styles.heroCard}>
      <View
        accessible
        accessibilityRole="summary"
        accessibilityLabel={heroLabel}
        accessibilityActions={[
          { name: 'roi', label: 'Flat-bet ROI details' },
          { name: 'close', label: 'Beat the closing line details' },
        ]}
        onAccessibilityAction={(e) => {
          if (e.nativeEvent.actionName === 'roi') open('roi');
          if (e.nativeEvent.actionName === 'close') open('clv');
        }}
      >
        <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <View style={[styles.top, stacked && styles.topStacked]}>
            <View style={styles.figures}>
              <Text style={styles.heroLabel}>{label}</Text>
              <Text
                style={[styles.heroUnits, { color: quiet ? colors.textSecondary : pnlColor(units, 2) }]}
                numberOfLines={1}
                adjustsFontSizeToFit
                minimumFontScale={0.6}
              >
                {unitsText}
              </Text>
              <Text style={styles.since}>{sinceLine()}</Text>
            </View>
            {points.length >= 2 ? (
              <View
                style={[styles.spark, stacked && { width: Math.max(120, width - spacing.lg * 4) }]}
                onLayout={(e) => setSparkW(e.nativeEvent.layout.width)}
              >
                <RecordSparkline points={points} width={sparkW} height={SPARK_H} endUnits={units} />
              </View>
            ) : null}
          </View>
          <View style={styles.grid}>
            <GridCell
              label="Flat-bet ROI"
              value={roi}
              valueColor={roi === '—' ? colors.textSecondary : pnlColor(summary.roiFlat, 1, 100)}
              stacked={stacked}
              onInfo={() => open('roi')}
              infoLabel="Flat-bet ROI details"
            />
            <GridCell label="Record" value={record} stacked={stacked} />
            <GridCell label="Win rate" value={win} stacked={stacked} />
            <GridCell
              label="Beat the closing line"
              value={clv}
              stacked={stacked}
              onInfo={() => open('clv')}
              infoLabel="Beat the closing line details"
            />
          </View>
        </View>
      </View>
      <RecordInfoSheet
        visible={sheet != null}
        title={sheetTitle}
        body={sheetBody}
        onClose={() => setSheet(null)}
      />
    </View>
  );
}

function GridCell({
  label,
  value,
  valueColor,
  stacked,
  onInfo,
  infoLabel,
}: {
  label: string;
  value: string;
  valueColor?: string;
  stacked: boolean;
  onInfo?: () => void;
  infoLabel?: string;
}) {
  return (
    <View style={[styles.cell, stacked && styles.cellStacked]}>
      <View style={styles.cellLabelRow}>
        <Text style={styles.cellLabel}>{label}</Text>
        {onInfo ? (
          <Pressable
            onPress={onInfo}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel={infoLabel}
            style={styles.infoBtn}
          >
            <Ionicons name="information-circle-outline" size={20} color={colors.tint} />
          </Pressable>
        ) : null}
      </View>
      <Text
        style={[styles.cellValue, valueColor ? { color: valueColor } : null]}
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.7}
      >
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  heroCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  top: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  topStacked: { flexDirection: 'column', alignItems: 'stretch' },
  figures: { flex: 1, minWidth: 0 },
  heroLabel: { fontSize: font.size.footnote, color: colors.textSecondary },
  heroUnits: { fontSize: font.size.largeTitle, fontWeight: font.weight.bold, marginVertical: 2 },
  since: { fontSize: font.size.footnote, color: colors.textSecondary },
  spark: { width: SPARK_W, height: SPARK_H },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  cell: { flexGrow: 1, flexBasis: '46%' },
  cellStacked: { width: '100%', minWidth: '100%', flexBasis: '100%' },
  cellLabelRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, flexWrap: 'wrap' },
  cellLabel: { fontSize: font.size.footnote, color: colors.textSecondary, flexShrink: 1 },
  infoBtn: { minWidth: 20, minHeight: 20, justifyContent: 'center' },
  cellValue: {
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginTop: 2,
  },
});

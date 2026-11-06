/**
 * The same model, one row per season, and a small-sample note.
 *
 * Matt, 2026-11-05: more filters to find trends. More filters also make a
 * lucky run easier to find, so the record shows whether it held season by
 * season, and says so when the sample is small. Rows use the headline's
 * timing (official, or the close while official is empty). Units are the
 * main models' staking.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { unitsSpeech } from '@/lib/a11y';
import {
  formatByomRecord,
  seasonsUpLine,
  smallSampleNote,
  type ByomRecord,
  type ByomSeasonRow,
} from '@/lib/byomRecord';
import { formatSignedUnits } from '@/lib/format';
import { colors, font, pnlColor, radii, spacing } from '@/lib/theme';

export function ByomSeasonBreakdown({
  record,
  seasons,
  showsUnits,
  currentSeason = null,
}: {
  record: ByomRecord | null;
  seasons: readonly ByomSeasonRow[];
  showsUnits: boolean;
  /** The season still being played, labelled "so far" (UX review). */
  currentSeason?: number | null;
}) {
  const current = currentSeason != null && seasons[0]?.season === currentSeason;
  const note = smallSampleNote(record);
  const up = showsUnits ? seasonsUpLine(seasons) : null;
  if (note == null && seasons.length < 2) return null;
  return (
    <View>
      {note ? (
        <Text style={styles.note}>{note}</Text>
      ) : null}
      {seasons.length >= 2 ? (
        <View style={styles.card}>
          <View style={styles.head}>
            <Text style={styles.title} accessibilityRole="header">By season</Text>
            {up ? <Text style={styles.up}>{up}</Text> : null}
          </View>
          {seasons.map((row, index) => {
            const label = index === 0 && current ? `${row.label} so far` : row.label;
            const units = row.record.units;
            const unitText = units == null ? '—' : formatSignedUnits(units);
            return (
              <View
                key={row.season}
                style={[styles.row, index < seasons.length - 1 && styles.rowBorder]}
                accessible
                accessibilityLabel={[
                  label,
                  formatByomRecord(row.record),
                  showsUnits && units != null ? unitsSpeech(unitText) : null,
                ].filter(Boolean).join(', ')}
              >
                <Text style={styles.season}>{label}</Text>
                <Text style={styles.record}>{formatByomRecord(row.record)}</Text>
                {showsUnits ? (
                  <Text style={[styles.units, { color: units == null ? colors.textSecondary : pnlColor(units, 1) }]}>
                    {unitText}
                  </Text>
                ) : null}
              </View>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  note: {
    marginTop: spacing.md,
    fontSize: font.size.footnote,
    lineHeight: 18,
    color: colors.textSecondary,
  },
  card: {
    marginTop: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  head: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    columnGap: spacing.md,
    justifyContent: 'space-between',
    alignItems: 'baseline',
    paddingVertical: spacing.sm,
  },
  title: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  up: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'baseline',
    paddingVertical: spacing.sm,
  },
  rowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  season: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  record: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  units: {
    minWidth: 72,
    textAlign: 'right',
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    fontVariant: ['tabular-nums'],
  },
});

import React, { useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, font, heatColor, radii, spacing } from '@/lib/theme';
import type { DayBucket } from '@/hooks/usePerformance';
import type { SizingMode } from '@/hooks/usePerformance';

interface Props {
  year: number;
  month: number; // 1-12
  byDay: Map<string, DayBucket>;
  mode: SizingMode;
  onSelectDay: (date: string) => void;
  onNavigate: (delta: number) => void;
}

const DAY_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function firstWeekday(year: number, month: number): number {
  return new Date(Date.UTC(year, month - 1, 1)).getUTCDay();
}

function monthName(month: number): string {
  return new Date(Date.UTC(2020, month - 1, 1)).toLocaleString('en-US', {
    month: 'long',
  });
}

export function PerformanceCalendar({ year, month, byDay, mode, onSelectDay, onNavigate }: Props) {
  const maxAbs = useMemo(() => {
    let m = 0;
    for (const bucket of byDay.values()) {
      const v = mode === 'kelly' ? bucket.netKelly : bucket.netFlat;
      if (Math.abs(v) > m) m = Math.abs(v);
    }
    return m;
  }, [byDay, mode]);

  const total = daysInMonth(year, month);
  const offset = firstWeekday(year, month);
  const cells: Array<{ day: number | null; date: string | null; bucket: DayBucket | null }> = [];
  for (let i = 0; i < offset; i++) cells.push({ day: null, date: null, bucket: null });
  for (let d = 1; d <= total; d++) {
    const date = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    cells.push({ day: d, date, bucket: byDay.get(date) ?? null });
  }
  while (cells.length % 7 !== 0) cells.push({ day: null, date: null, bucket: null });

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Pressable onPress={() => onNavigate(-1)} hitSlop={12}>
          <Text style={styles.arrow}>‹</Text>
        </Pressable>
        <Text style={styles.monthLabel}>{`${monthName(month)} ${year}`}</Text>
        <Pressable onPress={() => onNavigate(1)} hitSlop={12}>
          <Text style={styles.arrow}>›</Text>
        </Pressable>
      </View>

      <View style={styles.weekHeader}>
        {DAY_LABELS.map((d, i) => (
          <Text key={i} style={styles.weekLabel}>
            {d}
          </Text>
        ))}
      </View>

      <View style={styles.grid}>
        {cells.map((cell, i) => {
          if (cell.day == null || cell.date == null) {
            return <View key={i} style={styles.cellEmpty} />;
          }
          const bucket = cell.bucket;
          const profit = bucket ? (mode === 'kelly' ? bucket.netKelly : bucket.netFlat) : 0;
          const bg = bucket ? heatColor(profit, maxAbs) : colors.neutral + '22';
          const count = bucket ? bucket.picks.length : 0;
          return (
            <Pressable
              key={i}
              style={[styles.cell, { backgroundColor: bg }]}
              onPress={() => bucket && onSelectDay(cell.date!)}
              disabled={!bucket}
            >
              <Text style={styles.cellDay}>{cell.day}</Text>
              {count > 0 ? <Text style={styles.cellCount}>{count}</Text> : null}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.sm,
    marginBottom: spacing.md,
  },
  arrow: {
    fontSize: 28,
    color: colors.tint,
    width: 28,
    textAlign: 'center',
  },
  monthLabel: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  weekHeader: {
    flexDirection: 'row',
    marginBottom: spacing.xs,
  },
  weekLabel: {
    flex: 1,
    textAlign: 'center',
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  cell: {
    width: `${100 / 7}%`,
    aspectRatio: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 2,
  },
  cellEmpty: {
    width: `${100 / 7}%`,
    aspectRatio: 1,
  },
  cellDay: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  cellCount: {
    fontSize: 10,
    color: colors.textSecondary,
    marginTop: 1,
  },
});

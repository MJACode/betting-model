// CalendarGrid — a small dependency-free month calendar for picking a past day.
//
// The native @react-native-community/datetimepicker would need a native rebuild,
// so this renders a plain 7-column grid instead. All date math is done on
// YYYY-MM-DD strings at UTC noon (never `new Date('YYYY-MM-DD')` — that renders
// the previous day in US timezones). Days outside [minDate, maxDate] are
// disabled; month paging is clamped to the same range.

import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { colors, font, radii, spacing } from '@/lib/theme';

const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

/** 'YYYY-MM' of a 'YYYY-MM-DD' string. */
function ym(date: string): string {
  return date.slice(0, 7);
}

function monthLabel(month: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'UTC',
      month: 'long',
      year: 'numeric',
    }).format(new Date(`${month}-01T12:00:00Z`));
  } catch {
    return month;
  }
}

/** Step a 'YYYY-MM' month by ±1. */
function addMonths(month: string, delta: number): string {
  const [y, m] = month.split('-').map(Number);
  const d = new Date(Date.UTC(y!, m! - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

export function CalendarGrid({
  selected,
  minDate,
  maxDate,
  onSelect,
}: {
  selected: string;
  minDate: string;
  maxDate: string;
  onSelect: (date: string) => void;
}) {
  const [month, setMonth] = useState(() => ym(selected));

  const [y, m] = month.split('-').map(Number);
  const daysInMonth = new Date(Date.UTC(y!, m!, 0)).getUTCDate();
  const firstWeekday = new Date(`${month}-01T12:00:00Z`).getUTCDay();

  const cells: (string | null)[] = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from(
      { length: daysInMonth },
      (_, i) => `${month}-${String(i + 1).padStart(2, '0')}`,
    ),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const canPrev = month > ym(minDate);
  const canNext = month < ym(maxDate);

  return (
    <View style={styles.card}>
      <View style={styles.monthRow}>
        <Pressable
          onPress={() => canPrev && setMonth((cur) => addMonths(cur, -1))}
          disabled={!canPrev}
          hitSlop={8}
          accessibilityLabel="Previous month"
          style={({ pressed }) => [styles.monthBtn, pressed && { opacity: 0.6 }]}
        >
          <Ionicons
            name="chevron-back"
            size={18}
            color={canPrev ? colors.tint : colors.textTertiary}
          />
        </Pressable>
        <Text style={styles.monthLabel}>{monthLabel(month)}</Text>
        <Pressable
          onPress={() => canNext && setMonth((cur) => addMonths(cur, 1))}
          disabled={!canNext}
          hitSlop={8}
          accessibilityLabel="Next month"
          style={({ pressed }) => [styles.monthBtn, pressed && { opacity: 0.6 }]}
        >
          <Ionicons
            name="chevron-forward"
            size={18}
            color={canNext ? colors.tint : colors.textTertiary}
          />
        </Pressable>
      </View>

      <View style={styles.grid}>
        {WEEKDAYS.map((w, i) => (
          <View key={`wd-${i}`} style={styles.cell}>
            <Text style={styles.weekday}>{w}</Text>
          </View>
        ))}
        {cells.map((date, i) => {
          if (!date) return <View key={`empty-${i}`} style={styles.cell} />;
          const disabled = date < minDate || date > maxDate;
          const isSelected = date === selected;
          return (
            <View key={date} style={styles.cell}>
              <Pressable
                onPress={() => !disabled && onSelect(date)}
                disabled={disabled}
                style={({ pressed }) => [
                  styles.day,
                  isSelected && styles.daySelected,
                  pressed && !disabled && { opacity: 0.6 },
                ]}
              >
                <Text
                  style={[
                    styles.dayText,
                    disabled && styles.dayTextDisabled,
                    isSelected && styles.dayTextSelected,
                  ]}
                >
                  {Number(date.slice(8))}
                </Text>
              </Pressable>
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.sm,
  },
  monthRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.xs,
    marginBottom: spacing.xs,
  },
  monthBtn: { padding: 4 },
  monthLabel: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  cell: {
    width: `${100 / 7}%`,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 2,
  },
  weekday: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
  },
  day: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  daySelected: { backgroundColor: colors.tint },
  dayText: { fontSize: font.size.footnote, color: colors.textPrimary },
  dayTextDisabled: { color: colors.textTertiary, opacity: 0.5 },
  dayTextSelected: { color: colors.textInverse, fontWeight: font.weight.semibold },
});

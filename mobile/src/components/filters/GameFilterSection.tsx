/**
 * The GAMES section of the filter sheet, on both the Picks and the Stats tab.
 *
 * One component rather than one per screen, because the two tabs read the same
 * selection (`useGameSelection`) and a filter that looks or behaves differently
 * depending on which tab opened it is the thing the shared filter kit exists to
 * prevent — there were four near-identical chip implementations before
 * `FilterChip`.
 *
 * A row is the fixture and its kickoff, not a checkbox with a game id: "NE @
 * SEA" and "8:20 PM" are what a user recognises.
 *
 * GROUPED BY DAY, AND SEARCHABLE ABOVE 20 ROWS, because this list is not always
 * short. `queries.fetchSlateGames` reads a seven-day window and the widest one
 * measured (2026-09-09) is 118 NCAAF games — 118 rows inside a sheet, with the
 * weekday repeated on every one of them. A day header says it once, and the
 * search field is how you reach the game you actually want. Deliberately NOT a
 * "show more" cap: the game you are looking for is precisely the one behind it.
 */

import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { SelectableGame } from '@/lib/gameFilter';
import { todayET } from '@/lib/format';

/** Above this many rows the list gets a search field. */
const SEARCHABLE_AT = 20;

export function GameFilterSection({
  games,
  selected,
  onToggle,
  emptyNote,
}: {
  games: SelectableGame[];
  selected: Set<string>;
  onToggle: (gameId: string) => void;
  /** Why there is nothing to pick — never an empty box with no explanation. */
  emptyNote: string;
}) {
  const [query, setQuery] = useState('');

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? games.filter((g) => g.matchup.toLowerCase().includes(q)) : games;
  }, [games, query]);

  // Day groups, in the order the games are already in (kickoff ascending).
  const groups = useMemo(() => {
    const out: { day: string; games: SelectableGame[] }[] = [];
    for (const g of shown) {
      const last = out[out.length - 1];
      if (last && last.day === g.gameDate) last.games.push(g);
      else out.push({ day: g.gameDate, games: [g] });
    }
    return out;
  }, [shown]);

  if (games.length === 0) {
    return <Text style={styles.empty}>{emptyNote}</Text>;
  }

  return (
    <View>
      {games.length > SEARCHABLE_AT ? (
        <View style={styles.searchWrap}>
          <Ionicons name="search" size={15} color={colors.textTertiary} />
          <TextInput
            style={styles.searchInput}
            value={query}
            onChangeText={setQuery}
            placeholder="Find a game…"
            placeholderTextColor={colors.textTertiary}
            autoCorrect={false}
            autoCapitalize="characters"
            returnKeyType="search"
            accessibilityLabel="Find a game"
          />
          {query.length > 0 ? (
            <Pressable
              onPress={() => setQuery('')}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel="Clear the game search"
            >
              <Ionicons name="close-circle" size={16} color={colors.textTertiary} />
            </Pressable>
          ) : null}
        </View>
      ) : null}

      {groups.length === 0 ? (
        <Text style={styles.empty}>No game matches “{query.trim()}”.</Text>
      ) : null}

      {groups.map((group) => (
        <View key={group.day}>
          <Text style={styles.dayHeader}>{dayLabel(group.day)}</Text>
          {group.games.map((g) => {
            const checked = selected.has(g.gameId);
            return (
              <Pressable
                key={g.gameId}
                onPress={() => onToggle(g.gameId)}
                accessibilityRole="checkbox"
                accessibilityState={{ checked }}
                // Spoken as one phrase. The visual row splits the fixture and
                // the time across a row, which VoiceOver would otherwise read
                // as two unrelated labels.
                accessibilityLabel={`${g.matchup.replace(' @ ', ' at ')}, ${g.when}`}
                style={({ pressed }) => [styles.row, pressed && styles.pressed]}
              >
                {/* numberOfLines on BOTH: an NCAAF team id is a CFBD school
                    name, so a row is "Louisiana-Monroe @ Northwestern State"
                    and wraps to three lines at large type — on the one sport
                    where the list is ~100 rows long (UX_REVIEW §6). */}
                <Text style={styles.matchup} numberOfLines={1}>
                  {g.matchup}
                </Text>
                <Text style={styles.when} numberOfLines={1}>
                  {timeOnly(g.when)}
                </Text>
                <View style={[styles.box, checked && styles.boxOn]}>
                  {checked ? (
                    <Ionicons name="checkmark" size={14} color={colors.textInverse} />
                  ) : null}
                </View>
              </Pressable>
            );
          })}
        </View>
      ))}
    </View>
  );
}

/** '2026-09-13' → 'TODAY' / 'SAT SEP 13'. The group says the day once. */
function dayLabel(date: string): string {
  if (date === todayET()) return 'TODAY';
  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'UTC',
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    })
      .format(new Date(`${date}T12:00:00Z`))
      .toUpperCase();
  } catch {
    return date;
  }
}

/** The weekday is the group header now, so the row prints only the clock. */
function timeOnly(when: string): string {
  return when.replace(/^[A-Z]{3}\s+/, '');
}

const styles = StyleSheet.create({
  dayHeader: {
    fontSize: font.size.nano,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    letterSpacing: 0.4,
    marginTop: spacing.md,
    marginBottom: spacing.xs,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    // 44pt minimum: these are the sheet's densest tappable rows and a slate can
    // be a hundred of them (UX_REVIEW §4).
    minHeight: 44,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  pressed: { opacity: 0.6 },
  matchup: {
    flex: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  when: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  box: {
    width: 22,
    height: 22,
    borderRadius: radii.sm,
    borderWidth: 1.5,
    borderColor: colors.separator,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxOn: {
    backgroundColor: colors.tint,
    borderColor: colors.tint,
  },
  searchWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.bgCard,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    marginBottom: spacing.xs,
  },
  searchInput: {
    flex: 1,
    minHeight: 36,
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    padding: 0,
  },
  empty: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
});

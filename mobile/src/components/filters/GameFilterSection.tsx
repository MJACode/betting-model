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
 * SEA" and "8:20 PM ET" are what a user recognises, and the time is what makes
 * a Sunday slate readable at all.
 */

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { SelectableGame } from '@/lib/gameFilter';

export function GameFilterSection({
  games,
  selected,
  onToggle,
  onClear,
  emptyNote,
}: {
  games: SelectableGame[];
  selected: Set<string>;
  onToggle: (gameId: string) => void;
  onClear: () => void;
  /** Why there is nothing to pick — never an empty box with no explanation. */
  emptyNote: string;
}) {
  if (games.length === 0) {
    return <Text style={styles.empty}>{emptyNote}</Text>;
  }
  return (
    <View>
      {/* "All games" is a ROW, not the absence of a selection, so the default
          state is visible and reversible from inside the list. A sheet whose
          only way back is to untick things one at a time reads as a trap. */}
      <Pressable
        onPress={onClear}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: selected.size === 0 }}
        accessibilityLabel="All games"
        style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      >
        <View style={styles.rowText}>
          <Text style={styles.matchup}>All games</Text>
          <Text style={styles.when}>{games.length} on the slate</Text>
        </View>
        <Box checked={selected.size === 0} />
      </Pressable>

      {games.map((g) => {
        const checked = selected.has(g.gameId);
        return (
          <Pressable
            key={g.gameId}
            onPress={() => onToggle(g.gameId)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked }}
            // Spoken as one phrase: the fixture, then when it starts. The
            // visual row splits them across two lines, which VoiceOver would
            // otherwise read as two unrelated labels.
            accessibilityLabel={`${g.matchup.replace(' @ ', ' at ')}, ${g.when}`}
            style={({ pressed }) => [styles.row, pressed && styles.pressed]}
          >
            <View style={styles.rowText}>
              <Text style={styles.matchup}>{g.matchup}</Text>
              <Text style={styles.when}>{g.when}</Text>
            </View>
            <Box checked={checked} />
          </Pressable>
        );
      })}
    </View>
  );
}

/** The tick box. Its own component so the two row kinds cannot drift apart. */
function Box({ checked }: { checked: boolean }) {
  return (
    <View style={[styles.box, checked && styles.boxOn]}>
      {checked ? <Ionicons name="checkmark" size={14} color={colors.textInverse} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    // 44pt minimum: these are the sheet's densest tappable rows and a slate can
    // be seventeen of them (UX_REVIEW §4).
    minHeight: 44,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  pressed: { opacity: 0.6 },
  rowText: { flex: 1, paddingRight: spacing.sm },
  matchup: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  when: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 1,
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
  empty: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
});

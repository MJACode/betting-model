/**
 * SAME POSITION vs THE NEXT OPPONENT — "WRs vs ATL" on the player page.
 *
 * Matt, 2026-10-05: "When you click into a user stat. We should show how other
 * players at the same position have done against that team." What he chose:
 * a player-by-player list, the defence's rank vs the league, and a hit-rate
 * summary at the page's line; a This season / Last season toggle; and "real
 * role only" — a depth player's 0 on one target does not count as a miss for
 * the defence. The cut is printed on the card so the count is never a mystery.
 *
 * Numbers come from lib/positionVsOpponent; this file only draws them.
 */
import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SectionTitle } from '@/components/SectionTitle';
import { StatTile } from '@/components/StatTile';
import { dayLabelET, dayLabelSpokenET, formatPct } from '@/lib/format';
import type { HitDirection } from '@/lib/hitRate';
import {
  groupPlural,
  groupShort,
  groupSingular,
  opponentNoun,
  positionVsOpponent,
  roleCutText,
  type PositionGroup,
  type SeasonChoice,
} from '@/lib/positionVsOpponent';
import { ordinal } from '@/lib/teamDetail';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { PositionVsOpponentRow } from '@/types';

/** Rows before "Show all". A full season vs one defence is ~45 WR games. */
const ROWS_SHOWN = 6;

/** "Wk 5 · " in the NFL, "Batting 2nd · " for an MLB hitter, else nothing. */
function metaPrefix(e: { week: number | null; pos: string | null }): string {
  if (e.week != null) return `Wk ${e.week} · `;
  const spot = Number(e.pos);
  if (e.pos != null && Number.isInteger(spot) && spot >= 1 && spot <= 9) return `Batting ${ordinal(spot)} · `;
  return '';
}

function fmt(v: number): string {
  return String(Math.round(v * 10) / 10);
}

export function PositionVsOpponentCard({
  opponent,
  group,
  seasonThis,
  rows,
  loading,
  error,
  playerId,
  statLabel,
  betLabel,
  selection,
}: {
  opponent: string;
  group: PositionGroup;
  /** The season label in progress; "Last season" is the one before it. */
  seasonThis: number;
  rows: PositionVsOpponentRow[];
  loading: boolean;
  error: string | null;
  /** The page's own player — left out: the card is about the OTHERS. */
  playerId: string | null;
  statLabel: string;
  /** The page's bet in its own idiom — "70+" or "Under 2.5". */
  betLabel: string;
  /** The RESOLVED bet, so a row's ✓/✗ agrees with the game log's dots. */
  selection: { line: number; side: HitDirection };
}) {
  const [choice, setChoice] = useState<SeasonChoice>('this');
  const season = choice === 'this' ? seasonThis : seasonThis - 1;
  const [showAll, setShowAll] = useState(false);
  const card = useMemo(
    () =>
      positionVsOpponent(rows, {
        opponent,
        group,
        season,
        excludePlayerId: playerId,
        line: selection.line,
        side: selection.side,
      }),
    [rows, opponent, group, season, playerId, selection.line, selection.side],
  );
  const plural = groupPlural(group);
  const short = groupShort(group);
  const shown = showAll ? card.entries : card.entries.slice(0, ROWS_SHOWN);
  const seasonText = choice === 'this' ? 'this season' : 'last season';
  const pick = (c: SeasonChoice) => {
    setChoice(c);
    setShowAll(false);
  };

  return (
    <>
      <SectionTitle
        title={`${plural} vs ${opponent}`}
        tooltip={{
          title: `How ${plural.toLowerCase()} have done against ${opponent}`,
          body:
            `Every game ${groupSingular(group)} with a real role played against ${opponent} ${seasonText}, ` +
            `and how often they reached ${betLabel} ${statLabel} — this player's line, applied to each of ` +
            `them, so a smaller role reads as a miss. "Real role" means ${roleCutText(group)} in that game. ` +
            `The rank compares ${opponent} with the other ${opponentNoun(group)} on the average ` +
            `${statLabel} per ${short}: ` +
            '1st = allows the most.',
        }}
      />

      <View style={styles.segment} accessibilityRole="tablist">
        {(['this', 'last'] as const).map((c) => {
          const active = c === choice;
          return (
            <Pressable
              key={c}
              onPress={() => pick(c)}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              accessibilityLabel={c === 'this' ? 'This season' : 'Last season'}
              hitSlop={{ top: 8, bottom: 8, left: 2, right: 2 }}
              style={[styles.chip, active && styles.chipActive]}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>
                {c === 'this' ? 'This season' : 'Last season'}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {loading && rows.length === 0 ? (
        <View style={styles.card}>
          <ActivityIndicator />
        </View>
      ) : error ? (
        <View style={styles.card}>
          <Text style={styles.muted}>Couldn't load {plural} vs {opponent}. Pull down to retry.</Text>
        </View>
      ) : card.total === 0 ? (
        <View style={styles.card}>
          <Text style={styles.muted}>
            No {short} games vs {opponent} {seasonText}
            {choice === 'this' ? ' yet.' : '.'}
          </Text>
          {choice === 'this' ? (
            <Pressable
              onPress={() => pick('last')}
              accessibilityRole="button"
              accessibilityLabel="Show last season"
              hitSlop={{ top: 15, bottom: 15, left: 0, right: 0 }}
              style={({ pressed }) => [styles.emptyAction, pressed && { opacity: 0.7 }]}
            >
              <Text style={styles.more}>Show last season</Text>
            </Pressable>
          ) : null}
        </View>
      ) : (
        <>
          {/* Two tiles, no tilePad: the labels are longer than H2H's and need
              the width. The hit-rate tile is deliberately UNTINTED — it applies
              this player's line to every qualifying player at the position, so
              it partly measures their roles, and a grade colour would read as a
              verdict on the defence (UX review, 2026-10-05). The rank tile is
              the defence's verdict. */}
          <View style={styles.tileRow}>
            <StatTile
              label={`${betLabel} ${statLabel}`}
              value={card.hitRate == null ? '—' : formatPct(card.hitRate, 0)}
              caption={`${card.hits} of ${card.total} ${short} games at this line`}
            />
            <StatTile
              label={`Avg ${statLabel} per ${short}`}
              value={card.avgAllowed == null ? '—' : fmt(card.avgAllowed)}
              caption={
                card.rankMostAllowed != null && card.teamsRanked != null
                  ? `${ordinal(card.rankMostAllowed)}-most of ${card.teamsRanked} ${opponentNoun(group)}`
                  : undefined
              }
            />
          </View>

          {shown.map((e) => (
            <View
              key={`${e.date}:${e.playerId}`}
              style={styles.row}
              accessible
              accessibilityLabel={
                `${e.playerName}, ${e.team}, ${metaPrefix(e).replace(' · ', ', ').replace('Wk', 'week')}` +
                `${dayLabelSpokenET(e.date)}: ${fmt(e.value)} ${statLabel}, ` +
                (e.hit ? 'hit' : 'missed')
              }
            >
              {/* Shape as well as colour carries hit / miss (UX_REVIEW §5). */}
              <Ionicons
                name={e.hit ? 'checkmark-circle' : 'close-circle'}
                size={16}
                color={e.hit ? colors.betInk : colors.avoidInk}
              />
              <View style={styles.rowMain}>
                <Text style={styles.name} numberOfLines={1}>
                  {e.playerName}
                </Text>
                <Text style={styles.meta}>
                  {metaPrefix(e)}
                  {e.team} · {dayLabelET(e.date)}
                </Text>
              </View>
              <View style={styles.valueCol}>
                <Text style={styles.value}>{fmt(e.value)}</Text>
                <Text style={styles.valueLabel}>{statLabel}</Text>
              </View>
            </View>
          ))}

          {card.entries.length > ROWS_SHOWN ? (
            <Pressable
              onPress={() => setShowAll((v) => !v)}
              accessibilityRole="button"
              accessibilityLabel={showAll ? 'Show fewer games' : `Show all ${card.entries.length} games`}
              style={({ pressed }) => [styles.row, pressed && { opacity: 0.7 }]}
            >
              <Text style={styles.more}>
                {showAll ? 'Show fewer' : `Show all ${card.entries.length} games`}
              </Text>
            </Pressable>
          ) : null}

          <Text style={styles.footnote}>
            Counts {plural.toLowerCase()} with {roleCutText(group)} in the game.
          </Text>
        </>
      )}
    </>
  );
}

const styles = StyleSheet.create({
  segment: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  chipActive: { backgroundColor: colors.tint, borderColor: colors.tint },
  chipText: { fontSize: font.size.footnote, color: colors.textSecondary, fontWeight: font.weight.semibold },
  chipTextActive: { color: colors.textInverse },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  muted: { fontSize: font.size.footnote, color: colors.textSecondary, lineHeight: 18 },
  tileRow: { flexDirection: 'row', gap: spacing.sm, marginHorizontal: spacing.lg, marginBottom: spacing.sm },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    minHeight: 44,
  },
  rowMain: { flex: 1, minWidth: 0, marginLeft: spacing.xs },
  name: { fontSize: font.size.body, fontWeight: font.weight.semibold, color: colors.textPrimary },
  meta: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: 2 },
  valueCol: { alignItems: 'flex-end', marginLeft: spacing.sm },
  value: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  valueLabel: { fontSize: font.size.nano, color: colors.textTertiary, marginTop: 1 },
  more: {
    flex: 1,
    textAlign: 'center',
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  emptyAction: { marginTop: spacing.sm, alignSelf: 'flex-start' },
  footnote: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    lineHeight: 16,
  },
});

/**
 * The NBA team page's first-quarter card (Matt, 2026-10-28, from member
 * feedback). Last 5 / Last 10 / Season rows for the first quarter: the record,
 * the average margin, and offensive and defensive rating (points per 100
 * possessions), with All / Home / Away on top and the season's league ranks
 * underneath. Logic and its checks: src/lib/nbaQ1.ts, scripts/verify_nba_q1.ts.
 */
import React, { useMemo, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { SegmentTabs } from '@/components/GroupTabs';
import { friendlyCause } from '@/lib/errors';
import {
  formatQ1Record,
  formatRating,
  formatSigned1,
  NBA_Q1_VENUE_LABEL,
  NBA_Q1_VENUES,
  nbaQ1Windows,
  nbaSeasonLabel,
  type NbaQ1Game,
  type NbaQ1SeasonRow,
  type NbaQ1Venue,
  type NbaQ1WindowRow,
} from '@/lib/nbaQ1';
import { ordinal } from '@/lib/teamDetail';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  team: string;
  games: NbaQ1Game[];
  gamesLoading: boolean;
  gamesError: string | null;
  seasonRows: NbaQ1SeasonRow[];
}

export function NbaFirstQuarterCard({ team, games, gamesLoading, gamesError, seasonRows }: Props) {
  const [venue, setVenue] = useState<NbaQ1Venue>('all');
  const { season, rows } = useMemo(() => nbaQ1Windows(games, venue), [games, venue]);
  const ranks = seasonRows.find((r) => r.venue === venue) ?? null;
  const seasonSummary = rows[2].summary;
  const prior = rows[1].summary.priorSeasonGames;

  if (gamesLoading && games.length === 0) {
    return <ActivityIndicator style={styles.loading} />;
  }
  if (games.length === 0) {
    return (
      <View style={styles.card}>
        <Text style={styles.muted}>
          {gamesError
            ? `Couldn’t load first-quarter stats. ${friendlyCause(gamesError)} Pull down to retry.`
            : `No first-quarter results stored for ${team} yet.`}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <SegmentTabs
        items={NBA_Q1_VENUES}
        active={venue}
        onChange={setVenue}
        labelFor={(v) => NBA_Q1_VENUE_LABEL[v]}
        accessibilityLabelFor={(v) => `${NBA_Q1_VENUE_LABEL[v]} games`}
        second
      />

      <View style={[styles.row, styles.headRow]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <Text style={[styles.cellLabel, styles.head]} />
        <Text style={[styles.cell, styles.head]}>Record</Text>
        <Text style={[styles.cell, styles.head]}>Margin</Text>
        <Text style={[styles.cell, styles.head]}>Off</Text>
        <Text style={[styles.cell, styles.head]}>Def</Text>
      </View>
      {rows.map((r) => (
        <WindowRow key={r.key} row={r} />
      ))}

      {ranks && ranks.rated_games > 0 && ranks.ortg != null ? (
        <Text style={styles.ranks}>
          {season != null ? `${nbaSeasonLabel(season)} ranks` : 'Season ranks'}
          {venue === 'all' ? '' : ` (${NBA_Q1_VENUE_LABEL[venue].toLowerCase()})`}: Off {ordinal(ranks.ortg_rank)} · Def{' '}
          {ordinal(ranks.drtg_rank)} · Net {ordinal(ranks.net_rank)} of {ranks.teams}
        </Text>
      ) : null}
      {seasonSummary.ptsFor != null && seasonSummary.ptsAgainst != null ? (
        <Text style={styles.legend}>
          This season: {seasonSummary.ptsFor.toFixed(1)} scored, {seasonSummary.ptsAgainst.toFixed(1)} allowed per first
          quarter.
        </Text>
      ) : null}
      <Text style={styles.legend}>
        Off and Def are points scored and allowed per 100 possessions, counted from play-by-play. Lower Def is better.
        {prior > 0 && season != null
          ? ` Last 10 includes ${prior} ${prior === 1 ? 'game' : 'games'} from ${nbaSeasonLabel(season - 1)}.`
          : ''}
      </Text>
    </View>
  );
}

const WINDOW_SIZE: Record<NbaQ1WindowRow['key'], number> = { l5: 5, l10: 10, season: 0 };

function WindowRow({ row }: { row: NbaQ1WindowRow }) {
  const s = row.summary;
  const empty = s.games === 0;
  const label = empty
    ? `${row.label}: no games`
    : `${row.label}, ${s.games} games: first-quarter record ${formatQ1Record(s)}, average margin ${formatSigned1(
        s.margin,
      )}, offensive rating ${formatRating(s.ortg)}, defensive rating ${formatRating(s.drtg)}`;
  return (
    <View style={styles.row} accessible accessibilityLabel={label}>
      <View style={styles.cellLabel}>
        <Text style={styles.rowLabel}>{row.label}</Text>
        {/* The count shows on Season, and on a last-N window that is short of N. */}
        {!empty && (row.key === 'season' || s.games < WINDOW_SIZE[row.key]) ? (
          <Text style={styles.rowSub}>
            {s.games} {s.games === 1 ? 'game' : 'games'}
          </Text>
        ) : null}
      </View>
      <Text style={styles.cell}>{empty ? '—' : formatQ1Record(s)}</Text>
      <Text style={[styles.cell, marginTint(s.margin)]}>{empty ? '—' : formatSigned1(s.margin)}</Text>
      <Text style={styles.cell}>{formatRating(s.ortg)}</Text>
      <Text style={styles.cell}>{formatRating(s.drtg)}</Text>
    </View>
  );
}

// The grade ramp, as the rest of the team page: positive/negative fail AA on a card.
function marginTint(m: number | null) {
  if (m == null) return null;
  if (m >= 0.05) return { color: colors.gradeGood };
  if (m <= -0.05) return { color: colors.gradeBad };
  return null;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    paddingTop: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  loading: { marginVertical: spacing.xl },
  muted: { fontSize: font.size.footnote, color: colors.textSecondary, lineHeight: 18 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
    minHeight: 44,
  },
  headRow: { minHeight: 0, paddingTop: spacing.md, paddingBottom: spacing.xs },
  head: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  cellLabel: { flex: 1.3 },
  rowLabel: { fontSize: font.size.body, fontWeight: font.weight.semibold, color: colors.textPrimary },
  rowSub: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: 1 },
  cell: {
    flex: 1,
    textAlign: 'right',
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  ranks: {
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
    marginTop: spacing.md,
    lineHeight: 18,
  },
  // textSecondary inside a card: textTertiary is ~3.4:1 on bgCard at this size (UX_REVIEW §5).
  legend: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: spacing.sm, lineHeight: 16 },
});

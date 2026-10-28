/**
 * The NBA team page's first-quarter card (Matt, 2026-10-28, from member
 * feedback). Last 5 / Last 10 / Season rows for the first quarter: the record,
 * the average margin, and offensive and defensive rating (points per 100
 * possessions), with All / Home / Away on top and the season's league ranks
 * underneath. Last 5 / Last 10 come from the capped game fetch. Season, the
 * "This season" line, and the ranks come from `v_nba_team_q1_season`.
 * Logic and its checks: src/lib/nbaQ1.ts, scripts/verify_nba_q1.ts.
 *
 * From 1.5x text the four columns cannot hold "112.4" (48pt each on a 320pt
 * phone), so each window stacks into label-value lines. Below that the cells
 * shrink to fit rather than truncate (UX review, 2026-10-28).
 */
import React, { useMemo, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
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
  q1PriorSeasonNote,
  q1RowA11yLabel,
  q1RowSub,
  q1ThisSeasonLine,
  type NbaQ1Game,
  type NbaQ1SeasonRow,
  type NbaQ1Venue,
  type NbaQ1WindowRow,
} from '@/lib/nbaQ1';
import { ordinal } from '@/lib/teamDetail';
import { colors, font, radii, spacing } from '@/lib/theme';

/** Stack from 1.5x, not the Lines board's 2x: "112.4" outgrows a 48pt column first (UX review, second pass). */
const Q1_STACK_SCALE = 1.5;

interface Props {
  team: string;
  games: NbaQ1Game[];
  gamesLoading: boolean;
  gamesError: string | null;
  seasonRows: NbaQ1SeasonRow[];
  seasonLoading: boolean;
  seasonError: string | null;
}

export function NbaFirstQuarterCard({
  team,
  games,
  gamesLoading,
  gamesError,
  seasonRows,
  seasonLoading,
  seasonError,
}: Props) {
  const [venue, setVenue] = useState<NbaQ1Venue>('all');
  const { fontScale } = useWindowDimensions();
  const stack = Number.isFinite(fontScale) && fontScale >= Q1_STACK_SCALE;
  const seasonRow = seasonRows.find((r) => r.venue === venue) ?? null;
  const { season, rows } = useMemo(() => {
    const built = nbaQ1Windows(games, venue, seasonRow);
    if (seasonRow == null && (seasonLoading || seasonError)) {
      const pending = seasonLoading ? ('loading' as const) : ('error' as const);
      built.rows = built.rows.map((r) => (r.key === 'season' ? { ...r, pending } : r));
    }
    return built;
  }, [games, venue, seasonRow, seasonLoading, seasonError]);
  const ranks = seasonRow;
  const seasonSummary = rows.find((r) => r.key === 'season')?.summary ?? rows[2].summary;
  const seasonLine = q1ThisSeasonLine(seasonSummary);
  const priorNote = q1PriorSeasonNote(rows, season);

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

      {stack ? null : (
        <View style={[styles.row, styles.headRow]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <Text style={[styles.cellLabel, styles.head]} />
          {['Record', 'Margin', 'Off', 'Def'].map((h) => (
            <Text
              key={h}
              style={[styles.cell, styles.head]}
              numberOfLines={1}
              adjustsFontSizeToFit
              minimumFontScale={0.8}
            >
              {h}
            </Text>
          ))}
        </View>
      )}
      {rows.map((r) => (stack ? <StackedRow key={r.key} row={r} /> : <WindowRow key={r.key} row={r} />))}

      {ranks && ranks.rated_games > 0 && ranks.ortg != null ? (
        <Text style={styles.ranks}>
          {season != null ? `${nbaSeasonLabel(season)} ranks` : 'Season ranks'}
          {venue === 'all' ? '' : ` (${NBA_Q1_VENUE_LABEL[venue].toLowerCase()})`}, after {ranks.rated_games}{' '}
          {ranks.rated_games === 1 ? 'game' : 'games'}: Off {ordinal(ranks.ortg_rank)} · Def {ordinal(ranks.drtg_rank)} ·
          Net {ordinal(ranks.net_rank)} of {ranks.teams}
        </Text>
      ) : seasonError ? (
        <Text style={styles.ranks}>
          Couldn’t load season totals. {friendlyCause(seasonError)} Pull down to retry.
        </Text>
      ) : null}
      {seasonLine ? <Text style={styles.legend}>{seasonLine}</Text> : null}
      <Text style={styles.legend}>
        Off and Def are points scored and allowed per 100 possessions, counted from play-by-play. Lower Def is better.
        Net is Off minus Def.{priorNote ? ` ${priorNote}` : ''}
      </Text>
    </View>
  );
}

function WindowRow({ row }: { row: NbaQ1WindowRow }) {
  const s = row.summary;
  const empty = s.games === 0;
  const sub = q1RowSub(row);
  return (
    <View style={styles.row} accessible accessibilityLabel={q1RowA11yLabel(row)}>
      <View style={styles.cellLabel}>
        <Text style={styles.rowLabel} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
          {row.label}
        </Text>
        {sub ? <Text style={styles.rowSub}>{sub}</Text> : null}
      </View>
      <Text style={styles.cell} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
        {empty ? '—' : formatQ1Record(s)}
      </Text>
      <Text style={[styles.cell, marginTint(s.margin)]} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
        {empty ? '—' : formatSigned1(s.margin)}
      </Text>
      <Text style={styles.cell} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
        {formatRating(s.ortg)}
      </Text>
      <Text style={styles.cell} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
        {formatRating(s.drtg)}
      </Text>
    </View>
  );
}

/** The 2x-and-up layout: the window's label, then one label-value line per stat. */
function StackedRow({ row }: { row: NbaQ1WindowRow }) {
  const s = row.summary;
  const empty = s.games === 0;
  const sub = q1RowSub(row);
  const lines: [string, string, object | null][] = [
    ['Record', empty ? '—' : formatQ1Record(s), null],
    ['Margin', empty ? '—' : formatSigned1(s.margin), marginTint(s.margin)],
    ['Off', formatRating(s.ortg), null],
    ['Def', formatRating(s.drtg), null],
  ];
  return (
    <View style={styles.stackBlock} accessible accessibilityLabel={q1RowA11yLabel(row)}>
      <Text style={styles.rowLabel}>{row.label}</Text>
      {sub ? <Text style={styles.rowSub}>{sub}</Text> : null}
      {lines.map(([k, v, tint]) => (
        <View key={k} style={styles.stackLine}>
          <Text style={styles.stackKey}>{k}</Text>
          <Text style={[styles.stackValue, tint]}>{v}</Text>
        </View>
      ))}
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

// card and legend match TeamStatsScreen's own (its Card is file-local);
// paddingTop is smaller because the tab row carries its own top space.
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
  stackBlock: {
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  stackLine: { flexDirection: 'row', justifyContent: 'space-between', marginTop: spacing.xs },
  stackKey: { fontSize: font.size.body, color: colors.textSecondary },
  stackValue: { fontSize: font.size.body, color: colors.textPrimary, fontVariant: ['tabular-nums'] },
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

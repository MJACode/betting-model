/**
 * The Teams half of the Stats tab.
 *
 * Same shape as the player leaderboard — group tabs, stat chips, one ranked
 * list — so switching between Players and Teams does not mean learning a
 * second interface. What differs is the ordering of what it offers: efficiency
 * metrics first, plain record second, betting splits last and captioned, since
 * ATS and over/under records describe what happened rather than predicting
 * what will.
 *
 * Values are tinted by league tertile (top third / middle / bottom third)
 * oriented by each stat's direction, which is the glanceable pattern the
 * category's better tools use in place of a rank number.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { EmptyState } from '@/components/EmptyState';
import { FilterChip } from '@/components/filters/FilterChip';
import type { Sport } from '@/hooks/useSportFilter';
import { fetchTeamStats } from '@/lib/queries';
import {
  isThinSample,
  rankTeams,
  sampleFor,
  tierFor,
  type Tier,
} from '@/lib/teamBoard';
import {
  defaultTeamStatFor,
  formatRecord,
  formatTeamStat,
  teamGroupsForSport,
  teamStatValue,
  teamStatsForSport,
  type TeamStatDef,
  type TeamStatGroup,
} from '@/lib/teamStatCatalog';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { TeamStatsRow } from '@/types';

const AMBER = '#FF9500'; // mid tertile (no theme token)

/**
 * Seasons to try, newest first. Every league except MLB/WNBA is out of season
 * for part of the calendar year, and NFL/NCAAF label a season by its starting
 * year — so the current year is frequently empty and the board should fall
 * back to the most recent season with data rather than render blank.
 */
function seasonCandidates(): number[] {
  const y = new Date().getUTCFullYear();
  return [y, y - 1];
}

function tierColor(tier: Tier): string | undefined {
  if (tier === 'good') return colors.bet;
  if (tier === 'bad') return colors.avoid;
  if (tier === 'mid') return AMBER;
  return undefined;
}

export function TeamsBoard({ sport }: { sport: Sport }) {
  const groups = useMemo(() => teamGroupsForSport(sport), [sport]);
  const [stat, setStat] = useState<TeamStatDef | null>(() => defaultTeamStatFor(sport));
  const [rows, setRows] = useState<TeamStatsRow[]>([]);
  const [season, setSeason] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState<string>('');

  // Reset to the sport's default stat whenever the sport changes — the stat
  // sets do not overlap across sports, so keeping the old one would be invalid.
  useEffect(() => {
    setStat(defaultTeamStatFor(sport));
    setQuery('');
  }, [sport]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      for (const s of seasonCandidates()) {
        const data = await fetchTeamStats(sport, s);
        if (data.length) {
          setRows(data);
          setSeason(s);
          return;
        }
      }
      setRows([]);
      setSeason(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [sport]);

  useEffect(() => {
    void load();
  }, [load]);

  const activeGroup = stat?.group ?? groups[0];
  const pickGroup = (g: TeamStatGroup) => {
    if (g === activeGroup) return;
    const first = teamStatsForSport(sport).find((s) => s.group === g);
    if (first) setStat(first);
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) =>
        r.team.toLowerCase().includes(q) ||
        (r.conference ?? '').toLowerCase().includes(q),
    );
  }, [rows, query]);

  const { rows: ranked, cuts } = useMemo(
    () => (stat ? rankTeams(filtered, stat) : { rows: [], cuts: null }),
    [filtered, stat],
  );

  if (!stat) {
    return (
      <EmptyState
        title="No team stats"
        subtitle={`Team stats aren't available for ${sport}.`}
      />
    );
  }

  return (
    <>
      {/* Group tabs — Efficiency first by design. */}
      {groups.length > 1 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.fixedRow}
          contentContainerStyle={styles.groupTabRow}
          keyboardShouldPersistTaps="handled"
        >
          {groups.map((g) => (
            <Pressable
              key={g}
              onPress={() => pickGroup(g)}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityState={{ selected: g === activeGroup }}
              style={({ pressed }) => pressed && styles.pressed}
            >
              <Text style={[styles.groupTab, g === activeGroup && styles.groupTabActive]}>
                {g.toUpperCase()}
              </Text>
            </Pressable>
          ))}
        </ScrollView>
      ) : null}

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.fixedRow}
        contentContainerStyle={styles.chipRow}
        keyboardShouldPersistTaps="handled"
      >
        {teamStatsForSport(sport)
          .filter((s) => s.group === activeGroup)
          .map((s) => (
            <FilterChip
              key={String(s.key)}
              label={s.label}
              active={s.key === stat.key}
              onPress={() => setStat(s)}
            />
          ))}
      </ScrollView>

      {/* What this number is, and — for the betting group — what it isn't. */}
      {stat.hint ? (
        <View style={styles.hintRow}>
          <Text style={styles.hintText}>{stat.hint}</Text>
        </View>
      ) : null}
      {activeGroup === 'Betting' && !stat.hint ? (
        <View style={styles.hintRow}>
          <Text style={styles.hintText}>
            Betting records describe what already happened. They regress toward .500 once
            the market prices a trend in — read them as context, not as an edge.
          </Text>
        </View>
      ) : null}

      <View style={styles.searchWrap}>
        <Ionicons name="search" size={16} color={colors.textTertiary} />
        <TextInput
          style={styles.searchInput}
          value={query}
          onChangeText={setQuery}
          placeholder={sport === 'NCAAF' ? 'Search team or conference…' : 'Search teams…'}
          placeholderTextColor={colors.textTertiary}
          autoCorrect={false}
          returnKeyType="search"
        />
        {query.length > 0 ? (
          <Pressable onPress={() => setQuery('')} hitSlop={8}>
            <Ionicons name="close-circle" size={18} color={colors.textTertiary} />
          </Pressable>
        ) : null}
      </View>

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
        </View>
      ) : null}

      {ranked.length > 0 ? (
        <View style={styles.colHeader}>
          <Text style={styles.colHeaderRank}>RK</Text>
          <Text style={styles.colHeaderName}>
            TEAM{season ? `  ·  ${season}` : ''}
          </Text>
          <Text style={styles.colHeaderRight} numberOfLines={1}>
            {stat.label.toUpperCase()}
          </Text>
        </View>
      ) : null}

      <FlatList
        data={ranked}
        keyExtractor={(item) => item.team}
        renderItem={({ item, index }) => (
          <TeamRow rank={index + 1} row={item} def={stat} cuts={cuts} />
        )}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator style={styles.loading} />
          ) : (
            <EmptyState
              title="No teams"
              subtitle={
                query.trim()
                  ? `Nothing matched "${query.trim()}".`
                  : `No ${sport} team stats yet. Records fill in as games are played and lines are stored.`
              }
            />
          )
        }
        style={styles.listFlex}
        contentContainerStyle={styles.list}
        keyboardShouldPersistTaps="handled"
        initialNumToRender={20}
      />
    </>
  );
}

function TeamRow({
  rank,
  row,
  def,
  cuts,
}: {
  rank: number;
  row: TeamStatsRow;
  def: TeamStatDef;
  cuts: { lo: number; hi: number } | null;
}) {
  const value = teamStatValue(row, def);
  const thin = isThinSample(row, def);
  // A thin split still shows its number, but is never tinted as if it ranked.
  const tier: Tier = thin ? 'none' : tierFor(value, cuts, def.better);
  const color = tierColor(tier);
  const record = formatRecord(row, def);
  const sample = def.sample ? sampleFor(row, def) : null;

  return (
    <View style={styles.row}>
      <Text style={styles.rank}>{rank}</Text>
      <View style={styles.rowMain}>
        <Text style={styles.rowName} numberOfLines={1}>
          {row.team}
          {row.conference ? <Text style={styles.rowSub}>  {row.conference}</Text> : null}
        </Text>
        <Text style={styles.rowMeta} numberOfLines={1}>
          {row.wins}-{row.losses}
          {row.point_diff_pg != null
            ? `  ·  ${row.point_diff_pg > 0 ? '+' : ''}${Number(row.point_diff_pg).toFixed(1)}/g`
            : ''}
          {thin ? `  ·  ${sample} game${sample === 1 ? '' : 's'}` : ''}
        </Text>
      </View>
      <View style={styles.valueWrap}>
        <Text style={[styles.value, color ? { color } : null]}>
          {formatTeamStat(value, def.format)}
        </Text>
        {record ? (
          <Text style={styles.valueLabel}>{record}</Text>
        ) : thin ? (
          <Text style={styles.thinLabel}>thin</Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  fixedRow: { flexGrow: 0, flexShrink: 0 },
  listFlex: { flex: 1 },
  list: { paddingBottom: spacing.xl },
  groupTabRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xs,
    paddingBottom: spacing.xs,
  },
  groupTab: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    letterSpacing: 0.4,
    paddingVertical: 4,
  },
  groupTabActive: { color: colors.tint, fontWeight: font.weight.bold },
  chipRow: { paddingHorizontal: spacing.lg, gap: spacing.sm, paddingVertical: 2 },
  hintRow: { paddingHorizontal: spacing.lg, paddingTop: spacing.xs, paddingBottom: 2 },
  hintText: { fontSize: 11, color: colors.textTertiary, lineHeight: 15 },
  searchWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
    backgroundColor: colors.bgCard,
    gap: spacing.sm,
  },
  searchInput: { flex: 1, fontSize: font.size.body, color: colors.textPrimary, paddingVertical: 2 },
  colHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: 6,
    gap: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  colHeaderRank: {
    width: 20,
    fontSize: 11,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    letterSpacing: 0.3,
  },
  colHeaderName: {
    flex: 1,
    fontSize: 11,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    letterSpacing: 0.3,
  },
  colHeaderRight: {
    width: 72,
    textAlign: 'right',
    fontSize: 11,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    letterSpacing: 0.3,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    paddingHorizontal: spacing.lg,
    paddingVertical: 5,
    gap: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  rowMain: { flex: 1, minWidth: 0 },
  rank: {
    width: 20,
    textAlign: 'center',
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.textTertiary,
  },
  rowName: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  rowSub: { fontSize: 11, fontWeight: font.weight.semibold, color: colors.textTertiary },
  rowMeta: { fontSize: 11, color: colors.textSecondary, marginTop: 1 },
  valueWrap: { alignItems: 'flex-end', width: 72 },
  value: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  valueLabel: { fontSize: 10, color: colors.textTertiary },
  thinLabel: { fontSize: 10, color: colors.textTertiary, fontStyle: 'italic' },
  pressed: { opacity: 0.65 },
  loading: { marginVertical: spacing.xxl },
  errorBanner: {
    backgroundColor: colors.avoidSoft,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    borderRadius: 8,
  },
  errorText: { color: colors.avoid, fontSize: font.size.footnote },
});

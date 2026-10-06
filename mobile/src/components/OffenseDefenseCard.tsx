/**
 * Matchup: offense vs defense, on a game-level NFL or NCAAF pick.
 *
 * Counting rows are the season's real box scores. Points-added and
 * successful-plays rows are the same catalog entries as the Teams board,
 * and they stay off the card while every value is null (NFL, until
 * play-by-play exists). A missing number is an em dash, never a zero.
 */
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { ErrorBanner } from '@/components/ErrorState';
import { InfoTooltip } from '@/components/InfoTooltip';
import { errorText, isAbortError } from '@/lib/errors';
import { fetchNflSeasonBox, fetchTeamStats } from '@/lib/queries';
import { buildMatchup, type MatchupModel, type MatchupRow } from '@/lib/offenseDefense';
import { ordinal } from '@/lib/teamStatCatalog';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { GameRow } from '@/types';

/** Past this scale the three-column row collides ("18.813.3") and the info button overlaps the label. */
const STACK_AT = 1.3;

export function OffenseDefenseCard({
  game,
  ourTeam,
  beforeDate,
}: {
  game: GameRow;
  /** The picked side's team, or null on a total. That offense leads. */
  ourTeam: string | null;
  /** The pick's game date. NFL box lines on or after it are not counted. */
  beforeDate: string | null;
}) {
  const { fontScale } = useWindowDimensions();
  const stacked = fontScale >= STACK_AT;
  const [model, setModel] = useState<MatchupModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<unknown>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setFailure(null);
    setModel(null);
    (async () => {
      try {
        const sport = game.sport === 'NCAAF' ? 'NCAAF' : 'NFL';
        const board = await fetchTeamStats(sport, game.season);
        const season = board.season ?? game.season;
        const box = sport === 'NFL' && beforeDate ? await fetchNflSeasonBox(season, beforeDate) : [];
        if (!live) return;
        setModel(buildMatchup({
          season,
          away: game.away_team,
          home: game.home_team,
          ourTeam,
          box,
          board: board.rows,
          beforeDate,
        }));
      } catch (e: unknown) {
        if (live && !isAbortError(e)) setFailure(errorText(e));
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, [game.game_id, game.season, game.sport, game.away_team, game.home_team, ourTeam, beforeDate, reload]);

  const teams = model?.teams ?? 0;
  const subtitle = model?.season != null ? `${model.season} season` : '';
  const rankNote = teams > 0
    ? `ranks out of ${teams} teams, 1st is best (for a defense, 1st allows the least)`
    : '1st is best (for a defense, 1st allows the least)';

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Matchup: offense vs defense</Text>
      <Text style={styles.sub}>
        {subtitle ? `${subtitle} · ${rankNote}` : rankNote}
      </Text>
      {loading && !failure ? <ActivityIndicator style={styles.loading} /> : null}
      {failure ? (
        <ErrorBanner
          what="this matchup"
          error={failure}
          onRetry={() => setReload((n) => n + 1)}
          retrying={loading}
          style={styles.banner}
        />
      ) : null}
      {!loading && !failure && model && model.sections[0].rows.length === 0 ? (
        <Text style={styles.note}>No completed games stored for this season yet.</Text>
      ) : null}
      {model && model.sections[0].rows.length > 0
        ? model.sections.map((section) => (
          <View key={`${section.offenseTeam}-${section.defenseTeam}`} style={styles.section}>
            <Header
              offense={section.offenseTeam}
              defense={section.defenseTeam}
              offenseGames={section.offenseGames}
              defenseGames={section.defenseGames}
              stacked={stacked}
            />
            {section.rows.map((row) => (
              <MetricRow key={row.key} row={row} stacked={stacked} />
            ))}
          </View>
        ))
        : null}
      <Text style={styles.note}>Context, not an edge: the spread already prices team quality.</Text>
    </View>
  );
}

function sideLabel(team: string, side: 'off' | 'def', games: number | null): string {
  const base = `${team} ${side}`;
  if (games == null || games <= 0) return base;
  return `${base} · ${games} ${games === 1 ? 'game' : 'games'}`;
}

function Header({
  offense,
  defense,
  offenseGames,
  defenseGames,
  stacked,
}: {
  offense: string;
  defense: string;
  offenseGames: number | null;
  defenseGames: number | null;
  /** Match the metric row: half-and-half once the values stack, otherwise a label spacer plus two value columns. */
  stacked: boolean;
}) {
  const captions = (
    <>
      <View style={stacked ? styles.headerCol : styles.valCol}>
        <Text style={styles.headText}>{sideLabel(offense, 'off', offenseGames)}</Text>
        <Text style={styles.dir}>higher is better</Text>
      </View>
      <View style={stacked ? styles.headerCol : styles.valCol}>
        <Text style={styles.headText}>{sideLabel(defense, 'def', defenseGames)}</Text>
        <Text style={styles.dir}>lower is better</Text>
      </View>
    </>
  );
  return (
    <View style={styles.head}>
      <Text style={styles.headTitle}>{offense} offense vs {defense} defense</Text>
      {stacked ? (
        <View style={styles.stackedVals}>{captions}</View>
      ) : (
        <View style={styles.headCaps}>
          <View style={styles.labelCol} />
          {captions}
        </View>
      )}
    </View>
  );
}

function MetricRow({ row, stacked }: { row: MatchupRow; stacked: boolean }) {
  const off = <Value text={row.displayOff} rank={row.offRank} speech={row.offSpeech} />;
  const def = <Value text={row.displayDef} rank={row.defRank} speech={row.defSpeech} />;
  const label = (
    <View style={styles.labelLine}>
      <Text
        style={styles.label}
        accessibilityElementsHidden
        importantForAccessibility="no"
      >
        {row.label}
      </Text>
      {row.explain ? (
        <View style={styles.infoSlot}>
          <InfoTooltip
            title={row.explain.title}
            body={row.explain.body}
            accessibilityLabel={row.explain.a11y}
          />
        </View>
      ) : null}
    </View>
  );
  if (stacked) {
    return (
      <View style={styles.stackRow}>
        {label}
        <View style={styles.stackedVals}>
          <View style={styles.stackedCol}>{off}</View>
          <View style={styles.stackedCol}>{def}</View>
        </View>
      </View>
    );
  }
  return (
    <View style={styles.row}>
      <View style={styles.labelCol}>{label}</View>
      <View style={styles.valCol}>{off}</View>
      <View style={styles.valCol}>{def}</View>
    </View>
  );
}

function Value({ text, rank, speech }: { text: string; rank: number | null; speech: string }) {
  return (
    <Text style={styles.value} accessibilityLabel={speech}>
      {text}
      {rank != null ? <Text style={styles.rank}> {ordinal(rank)}</Text> : null}
    </Text>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  title: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  sub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
    marginBottom: spacing.sm,
  },
  note: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
    marginTop: spacing.xs,
  },
  loading: { marginVertical: spacing.sm },
  banner: { marginHorizontal: 0, marginTop: spacing.sm },
  section: { marginTop: spacing.sm },
  head: {
    paddingBottom: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  headCaps: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm,
  },
  headTitle: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    marginBottom: 2,
  },
  headText: {
    width: '100%',
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textAlign: 'right',
  },
  dir: {
    width: '100%',
    fontSize: font.size.micro,
    color: colors.textTertiary,
    textAlign: 'right',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 5,
    gap: spacing.sm,
  },
  stackRow: { paddingVertical: 6 },
  labelCol: { flex: 1.25, minWidth: 0 },
  valCol: { flex: 1, minWidth: 0, alignItems: 'flex-end' },
  labelLine: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    minWidth: 0,
  },
  label: {
    flexShrink: 1,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  infoSlot: { flexShrink: 0 },
  value: {
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    fontWeight: font.weight.semibold,
    fontVariant: ['tabular-nums'],
    textAlign: 'right',
  },
  rank: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.medium,
  },
  stackedVals: { flexDirection: 'row', gap: spacing.md, marginTop: 2 },
  stackedCol: { flex: 1, minWidth: 0, alignItems: 'flex-end' },
  headerCol: { flex: 1, minWidth: 0 },
});

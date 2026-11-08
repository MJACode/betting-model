/**
 * The NBA Stats tab's 1st Basket board (Matt, 2026-11-08). One card per game
 * on the slate: the two teams side by side (usual jumper, tips, scored first,
 * split by won / lost tip, opponent scored first), then each team's likely
 * first scorers with First shot, Made and 1st basket. Stats only: no odds,
 * no model, no pick.
 *
 * Logic and definitions: src/lib/nbaFirstBasket.ts, pinned by
 * scripts/verify_nba_first_basket.ts. Data: v_nba_first_basket_team_season and
 * v_nba_first_basket_player_season (data/ingestors/nba_first_basket.py).
 *
 * Layout follows NbaFirstQuarterCard: from 1.5x text the columns stack into
 * label-value lines, below that cells shrink to fit rather than truncate.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { friendlyCause } from '@/lib/errors';
import { boardSeasonET } from '@/lib/format';
import { nbaSeasonLabel } from '@/lib/nbaQ1';
import {
  fbCandidates,
  fbCompareLines,
  fbSlateTeams,
  NBA_FB_LEGEND,
  type FbCandidate,
  type NbaFbPlayerRow,
  type NbaFbTeamRow,
} from '@/lib/nbaFirstBasket';
import { fetchNbaFirstBasketPlayers, fetchNbaFirstBasketTeams } from '@/lib/queries';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { GameRow } from '@/types';

/** Same stacking point as the first-quarter card. */
const FB_STACK_SCALE = 1.5;

interface Props {
  /** The slate's NBA games (one date), any order. */
  games: GameRow[];
  /** "Playing today" / "Next slate Sun 11/9" (statsBoard.slateLabelFor). */
  slateLabel: string;
  /** False until the slate read has settled. */
  slateSettled: boolean;
  /** Pull-to-refresh also re-reads the slate. */
  onRefreshSlate?: () => void;
}

export function NbaFirstBasketBoard({ games, slateLabel, slateSettled, onRefreshSlate }: Props) {
  const { fontScale } = useWindowDimensions();
  const stack = Number.isFinite(fontScale) && fontScale >= FB_STACK_SCALE;
  const season = boardSeasonET('NBA');
  const ordered = useMemo(
    () => [...games].sort((a, b) => (a.commence_time ?? '').localeCompare(b.commence_time ?? '') || a.game_id.localeCompare(b.game_id)),
    [games],
  );
  const teams = useMemo(() => fbSlateTeams(ordered), [ordered]);
  const teamsKey = teams.join(',');

  const [teamRows, setTeamRows] = useState<NbaFbTeamRow[]>([]);
  const [playerRows, setPlayerRows] = useState<NbaFbPlayerRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  // The key the rows on screen were read for, so a slate change never shows
  // the last slate's numbers under the new games.
  const [shownKey, setShownKey] = useState('');

  useEffect(() => {
    if (teams.length === 0) {
      setTeamRows([]);
      setPlayerRows([]);
      setShownKey(teamsKey);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([fetchNbaFirstBasketTeams(teams, season), fetchNbaFirstBasketPlayers(teams, season)])
      .then(([t, p]) => {
        if (cancelled) return;
        setTeamRows(t);
        setPlayerRows(p);
        setShownKey(teamsKey);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // teams is derived from teamsKey; the key is the dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teamsKey, season, reload]);

  const refresh = useCallback(() => {
    setReload((n) => n + 1);
    onRefreshSlate?.();
  }, [onRefreshSlate]);

  const byTeam = useMemo(() => new Map(teamRows.map((r) => [r.team, r])), [teamRows]);
  const fresh = shownKey === teamsKey;

  let body: React.ReactNode;
  if (!slateSettled || (loading && !fresh)) {
    body = <ActivityIndicator style={styles.loading} accessibilityLabel="Loading first-basket stats" />;
  } else if (ordered.length === 0) {
    body = <Text style={styles.empty}>No NBA games on the schedule this week.</Text>;
  } else if (error && !fresh) {
    body = (
      <Text style={styles.empty}>
        Couldn’t load first-basket stats. {friendlyCause(error)} Pull down to retry.
      </Text>
    );
  } else {
    body = ordered.map((g) => (
      <GameCard
        key={g.game_id}
        game={g}
        away={byTeam.get(g.away_team) ?? null}
        home={byTeam.get(g.home_team) ?? null}
        players={playerRows}
        stack={stack}
      />
    ));
  }

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading && fresh} onRefresh={refresh} />}
    >
      <Text style={styles.slate} accessibilityRole="header">
        {slateLabel} · {nbaSeasonLabel(season)} season
      </Text>
      {error && fresh ? (
        <Text style={styles.inlineError}>Couldn’t refresh. {friendlyCause(error)} Showing the last numbers read.</Text>
      ) : null}
      {body}
      <Text style={styles.legend}>{NBA_FB_LEGEND}</Text>
      <BetslipBarSpacer />
    </ScrollView>
  );
}

function GameCard({
  game,
  away,
  home,
  players,
  stack,
}: {
  game: GameRow;
  away: NbaFbTeamRow | null;
  home: NbaFbTeamRow | null;
  players: NbaFbPlayerRow[];
  stack: boolean;
}) {
  const lines = fbCompareLines(game.away_team, game.home_team, away, home);
  const awayC = fbCandidates(game.away_team, players);
  const homeC = fbCandidates(game.home_team, players);
  const noData = away == null && home == null;
  return (
    <View style={styles.card}>
      <Text style={styles.matchup} accessibilityRole="header">
        {game.away_team} @ {game.home_team}
      </Text>
      {noData ? (
        <Text style={styles.muted}>No games stored for either team this season yet.</Text>
      ) : (
        <>
          {stack ? null : (
            <View style={[styles.row, styles.headRow]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
              <Text style={[styles.cellLabel, styles.head]} />
              <Text style={[styles.cell, styles.head]}>{game.away_team}</Text>
              <Text style={[styles.cell, styles.head]}>{game.home_team}</Text>
            </View>
          )}
          {lines.map((l) =>
            stack ? (
              <View key={l.key} style={styles.stackBlock} accessible accessibilityLabel={l.a11y}>
                <Text style={styles.rowLabel}>{l.label}</Text>
                <View style={styles.stackLine}>
                  <Text style={styles.stackKey}>{game.away_team}</Text>
                  <Text style={styles.stackValue}>{l.away}</Text>
                </View>
                <View style={styles.stackLine}>
                  <Text style={styles.stackKey}>{game.home_team}</Text>
                  <Text style={styles.stackValue}>{l.home}</Text>
                </View>
              </View>
            ) : (
              <View key={l.key} style={styles.row} accessible accessibilityLabel={l.a11y}>
                <Text style={[styles.cellLabel, styles.label]} numberOfLines={2}>
                  {l.label}
                </Text>
                <Text
                  style={[styles.cell, l.key === 'jumper' && styles.nameCell]}
                  numberOfLines={l.key === 'jumper' ? 2 : 1}
                  adjustsFontSizeToFit={l.key !== 'jumper'}
                  minimumFontScale={0.75}
                >
                  {l.away}
                </Text>
                <Text
                  style={[styles.cell, l.key === 'jumper' && styles.nameCell]}
                  numberOfLines={l.key === 'jumper' ? 2 : 1}
                  adjustsFontSizeToFit={l.key !== 'jumper'}
                  minimumFontScale={0.75}
                >
                  {l.home}
                </Text>
              </View>
            ),
          )}
        </>
      )}
      <Candidates team={game.away_team} rows={awayC} stack={stack} />
      <Candidates team={game.home_team} rows={homeC} stack={stack} />
    </View>
  );
}

function Candidates({ team, rows, stack }: { team: string; rows: FbCandidate[]; stack: boolean }) {
  return (
    <View style={styles.candidates}>
      <Text style={styles.subhead} accessibilityRole="header">
        {team} likely first scorers
      </Text>
      {rows.length === 0 ? (
        <Text style={styles.muted}>No first shots stored for {team} this season yet.</Text>
      ) : (
        <>
          {stack ? null : (
            <View style={[styles.row, styles.headRow]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
              <Text style={[styles.cellName, styles.head]} />
              {['1st shot', 'Made', '1st bskt'].map((h) => (
                <Text key={h} style={[styles.cellNum, styles.head]} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8}>
                  {h}
                </Text>
              ))}
            </View>
          )}
          {rows.map((c) =>
            stack ? (
              <View key={c.espnId} style={styles.stackBlock} accessible accessibilityLabel={c.a11y}>
                <Text style={styles.rowLabel}>{c.name}</Text>
                <Text style={styles.rowSub}>
                  {c.games} {c.games === 1 ? 'game' : 'games'}
                </Text>
                {(
                  [
                    ['First shot', c.firstShot],
                    ['Made', c.made],
                    ['First basket', c.firstBasket],
                  ] as const
                ).map(([k, v]) => (
                  <View key={k} style={styles.stackLine}>
                    <Text style={styles.stackKey}>{k}</Text>
                    <Text style={styles.stackValue}>{v}</Text>
                  </View>
                ))}
              </View>
            ) : (
              <View key={c.espnId} style={styles.row} accessible accessibilityLabel={c.a11y}>
                <View style={styles.cellName}>
                  <Text style={styles.label} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
                    {c.name}
                  </Text>
                  <Text style={styles.rowSub}>
                    {c.games} {c.games === 1 ? 'game' : 'games'}
                  </Text>
                </View>
                {[c.firstShot, c.made, c.firstBasket].map((v, i) => (
                  <Text key={i} style={styles.cellNum} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
                    {v}
                  </Text>
                ))}
              </View>
            ),
          )}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingTop: spacing.sm, paddingBottom: spacing.xl },
  loading: { marginVertical: spacing.xl },
  slate: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  inlineError: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    lineHeight: 18,
  },
  empty: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    marginHorizontal: spacing.lg,
    marginVertical: spacing.xl,
    textAlign: 'center',
    lineHeight: 21,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  matchup: { fontSize: font.size.headline, fontWeight: font.weight.semibold, color: colors.textPrimary },
  muted: { fontSize: font.size.footnote, color: colors.textSecondary, lineHeight: 18, marginTop: spacing.sm },
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
  cellLabel: { flex: 1.2, paddingRight: spacing.sm },
  label: { fontSize: font.size.body, color: colors.textPrimary },
  cell: {
    flex: 1,
    textAlign: 'right',
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  nameCell: { fontSize: font.size.footnote, fontVariant: undefined },
  cellName: { flex: 1.6, paddingRight: spacing.sm },
  cellNum: {
    flex: 1,
    textAlign: 'right',
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  rowLabel: { fontSize: font.size.body, fontWeight: font.weight.semibold, color: colors.textPrimary },
  rowSub: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: 1 },
  candidates: { marginTop: spacing.lg },
  subhead: { fontSize: font.size.callout, fontWeight: font.weight.semibold, color: colors.textPrimary },
  stackBlock: {
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  stackLine: { flexDirection: 'row', justifyContent: 'space-between', marginTop: spacing.xs },
  stackKey: { fontSize: font.size.body, color: colors.textSecondary },
  stackValue: { fontSize: font.size.body, color: colors.textPrimary, fontVariant: ['tabular-nums'] },
  // textSecondary, not textTertiary, below a card (UX_REVIEW §5).
  legend: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    lineHeight: 16,
  },
});

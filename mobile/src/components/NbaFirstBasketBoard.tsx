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
 * label-value lines. Rate cells lead with the percentage and carry "x of N"
 * under it, so the sample is never hidden and never has to fit one column.
 * A player the injury feed has ruled out is left off the candidates; Q / DTD /
 * D carry the leaderboard's chip (UX review, 2026-11-08).
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
import { EmptyState } from '@/components/EmptyState';
import { InjuryChip } from '@/components/InjuryChip';
import { friendlyCause } from '@/lib/errors';
import { boardSeasonET, formatGameTimeET, weekdayShortET } from '@/lib/format';
import { nbaSeasonLabel } from '@/lib/nbaQ1';
import {
  fbCandidates,
  fbCandidatesEmptyText,
  fbCompareLines,
  fbGameStarted,
  fbOrderGames,
  fbSlateTeams,
  NBA_FB_LEGEND,
  type FbCandidate,
  type FbCell,
  type FbInjuryLookup,
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
  /** The slate READ has returned for this sport (not the release timer). */
  slateSettled: boolean;
  /** That read failed: the board is nothing but the slate, so say so. */
  slateFailed: boolean;
  /** The Stats screen's injury lookup (useInjuryStatus). */
  injuryFor: FbInjuryLookup;
  /** The screen clock (useNow), so "started" ages with the rest of the tab. */
  nowMs: number;
  /** Pull-to-refresh also re-reads the slate and the injury feed. */
  onRefresh?: () => void;
}

export function NbaFirstBasketBoard({
  games,
  slateLabel,
  slateSettled,
  slateFailed,
  injuryFor,
  nowMs,
  onRefresh,
}: Props) {
  const { fontScale } = useWindowDimensions();
  const stack = Number.isFinite(fontScale) && fontScale >= FB_STACK_SCALE;
  const season = boardSeasonET('NBA');
  const ordered = useMemo(() => fbOrderGames(games, nowMs), [games, nowMs]);
  const teams = useMemo(() => fbSlateTeams(games), [games]);
  const teamsKey = teams.join(',');

  const [teamRows, setTeamRows] = useState<NbaFbTeamRow[]>([]);
  const [playerRows, setPlayerRows] = useState<NbaFbPlayerRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  // The key the rows on screen were read for, so a slate change never shows
  // the last slate's numbers under the new games.
  const [shownKey, setShownKey] = useState<string | null>(null);

  useEffect(() => {
    if (teams.length === 0) {
      setTeamRows([]);
      setPlayerRows([]);
      setError(null);
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
    onRefresh?.();
  }, [onRefresh]);

  const byTeam = useMemo(() => new Map(teamRows.map((r) => [r.team, r])), [teamRows]);
  const fresh = shownKey === teamsKey;

  let body: React.ReactNode;
  if (!slateSettled) {
    body = <ActivityIndicator style={styles.loading} accessibilityLabel="Loading tonight’s games" />;
  } else if (slateFailed && ordered.length === 0) {
    body = (
      <EmptyState
        title="Couldn’t load tonight’s games"
        subtitle="Pull down to retry."
        actionLabel="Retry"
        onAction={refresh}
      />
    );
  } else if (ordered.length === 0) {
    body = (
      <EmptyState
        title="No NBA games this week"
        subtitle="First-basket cards appear for the next slate once it is scheduled."
      />
    );
  } else if (!fresh && error) {
    body = (
      <EmptyState
        title="Couldn’t load first-basket stats"
        subtitle={`${friendlyCause(error)} Pull down to retry.`}
        actionLabel="Retry"
        onAction={refresh}
      />
    );
  } else if (!fresh) {
    body = <ActivityIndicator style={styles.loading} accessibilityLabel="Loading first-basket stats" />;
  } else {
    body = ordered.map((g) => (
      <GameCard
        key={g.game_id}
        game={g}
        away={byTeam.get(g.away_team) ?? null}
        home={byTeam.get(g.home_team) ?? null}
        players={playerRows}
        injuryFor={injuryFor}
        started={fbGameStarted(g, nowMs)}
        stack={stack}
      />
    ));
  }

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading && fresh} onRefresh={refresh} />}
    >
      {ordered.length > 0 ? (
        <Text style={styles.slate} accessibilityRole="header">
          {slateLabel} · {nbaSeasonLabel(season)} season
        </Text>
      ) : null}
      {error && fresh ? (
        <Text style={styles.inlineError}>Couldn’t refresh. {friendlyCause(error)} Showing the last numbers read.</Text>
      ) : null}
      {body}
      {slateSettled && ordered.length > 0 ? <Text style={styles.legend}>{NBA_FB_LEGEND}</Text> : null}
      <BetslipBarSpacer />
    </ScrollView>
  );
}

/** "Sun 7:30 PM ET", or what a started game is. */
function tipLine(g: GameRow, started: boolean): string {
  if (started) return 'Under way · first basket already scored';
  const time = formatGameTimeET(g.commence_time);
  const day = weekdayShortET(g.commence_time);
  return time ? `${day ? `${day} ` : ''}${time}` : '';
}

function GameCard({
  game,
  away,
  home,
  players,
  injuryFor,
  started,
  stack,
}: {
  game: GameRow;
  away: NbaFbTeamRow | null;
  home: NbaFbTeamRow | null;
  players: NbaFbPlayerRow[];
  injuryFor: FbInjuryLookup;
  started: boolean;
  stack: boolean;
}) {
  const lines = fbCompareLines(game.away_team, game.home_team, away, home, injuryFor);
  const awayC = fbCandidates(game.away_team, players, undefined, injuryFor);
  const homeC = fbCandidates(game.home_team, players, undefined, injuryFor);
  const noData = away == null && home == null;
  const tip = tipLine(game, started);
  return (
    <View style={styles.card}>
      <Text style={styles.matchup} accessibilityRole="header">
        {game.away_team} @ {game.home_team}
      </Text>
      {tip ? <Text style={styles.tip}>{tip}</Text> : null}
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
                <StackCell team={game.away_team} cell={l.away} />
                <StackCell team={game.home_team} cell={l.home} />
              </View>
            ) : (
              <View key={l.key} style={styles.row} accessible accessibilityLabel={l.a11y}>
                <Text style={[styles.cellLabel, styles.label]} numberOfLines={2}>
                  {l.label}
                </Text>
                <Cell cell={l.away} name={l.key === 'jumper'} />
                <Cell cell={l.home} name={l.key === 'jumper'} />
              </View>
            ),
          )}
        </>
      )}
      <Candidates team={game.away_team} rows={awayC} stack={stack} emptyText={fbCandidatesEmptyText(game.away_team, players, injuryFor)} />
      <Candidates team={game.home_team} rows={homeC} stack={stack} emptyText={fbCandidatesEmptyText(game.home_team, players, injuryFor)} />
    </View>
  );
}

function Cell({ cell, name }: { cell: FbCell; name: boolean }) {
  return (
    <View style={styles.cellBox}>
      <Text
        style={name ? styles.nameValue : styles.value}
        numberOfLines={name ? 2 : 1}
        adjustsFontSizeToFit={!name}
        minimumFontScale={0.75}
      >
        {cell.value}
      </Text>
      {cell.sub ? (
        <Text style={styles.cellSub} numberOfLines={2}>
          {cell.sub}
        </Text>
      ) : null}
    </View>
  );
}

function StackCell({ team, cell }: { team: string; cell: FbCell }) {
  return (
    <View style={styles.stackLine}>
      <Text style={styles.stackKey}>{team}</Text>
      <Text style={styles.stackValue}>
        {cell.value}
        {cell.sub ? ` · ${cell.sub}` : ''}
      </Text>
    </View>
  );
}

function Candidates({
  team,
  rows,
  stack,
  emptyText,
}: {
  team: string;
  rows: FbCandidate[];
  stack: boolean;
  emptyText: string;
}) {
  const startsLabel = (n: number) => `${n} ${n === 1 ? 'start' : 'starts'}`;
  return (
    <View style={styles.candidates}>
      <Text style={styles.subhead} accessibilityRole="header">
        {team} likely first scorers
      </Text>
      {rows.length === 0 ? (
        <Text style={styles.muted}>{emptyText}</Text>
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
                <View style={styles.nameLine}>
                  <Text style={styles.rowLabel}>{c.name}</Text>
                  {c.injury ? <InjuryChip tag={c.injury} /> : null}
                </View>
                <Text style={styles.rowSub}>{startsLabel(c.starts)}</Text>
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
                  <View style={styles.nameLine}>
                    <Text style={[styles.label, styles.nameShrink]} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
                      {c.name}
                    </Text>
                    {c.injury ? <InjuryChip tag={c.injury} /> : null}
                  </View>
                  <Text style={styles.rowSub}>{startsLabel(c.starts)}</Text>
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
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  matchup: { fontSize: font.size.headline, fontWeight: font.weight.semibold, color: colors.textPrimary },
  tip: { fontSize: font.size.footnote, color: colors.textSecondary, marginTop: 2 },
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
  cell: { flex: 1, textAlign: 'right' },
  cellBox: { flex: 1, alignItems: 'flex-end' },
  value: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
    textAlign: 'right',
  },
  nameValue: { fontSize: font.size.footnote, color: colors.textPrimary, textAlign: 'right' },
  cellSub: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
    textAlign: 'right',
    marginTop: 1,
  },
  cellName: { flex: 1.6, paddingRight: spacing.sm },
  nameLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  nameShrink: { flexShrink: 1 },
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
  stackLine: { flexDirection: 'row', justifyContent: 'space-between', marginTop: spacing.xs, gap: spacing.sm },
  stackKey: { fontSize: font.size.body, color: colors.textSecondary },
  stackValue: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
    flexShrink: 1,
    textAlign: 'right',
  },
  // textSecondary, not textTertiary, below a card (UX_REVIEW §5).
  legend: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    lineHeight: 16,
  },
});

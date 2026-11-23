/**
 * The matchup page's sections (screens/ScoreboardGameScreen, NBA first —
 * Matt, 2026-11-23). Read top to bottom the way a bet is decided: our pick or
 * "No pick", the best price at the member's books, the two teams side by
 * side, recent form against the number, rest, head-to-head, injuries.
 *
 * Every number here is read, not estimated: ranks from team_stats_board,
 * cover marks from team_period_results, injuries from injury_status_current.
 * A section whose read failed says so in its own card; the others still draw.
 */
import React from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import type { useMatchup } from '@/hooks/useMatchup';
import { MATCHUP_FORM_GAMES } from '@/hooks/useMatchup';
import { formatAmerican, formatSigned } from '@/lib/format';
import { formatAts, formatOu, pairRanks, restText, type PairedRank } from '@/lib/gameMatchup';
import { bookLabel } from '@/lib/markets';
import type { TeamLineQuote } from '@/lib/statsOdds';
import { formatTeamLine, ordinal, type TeamStatRank } from '@/lib/teamDetail';
import { formatRecord, formatTeamStat } from '@/lib/teamStatCatalog';
import { card, colors, font, spacing, sectionHeaderText } from '@/lib/theme';
import type { TeamStatsRow } from '@/types';

type Matchup = ReturnType<typeof useMatchup>;

export function Section({
  title,
  children,
  loading,
  error,
}: {
  title: string;
  children: React.ReactNode;
  loading?: boolean;
  error?: string | null;
}) {
  return (
    <View style={styles.card}>
      <Text style={styles.title} accessibilityRole="header">{title}</Text>
      {loading ? (
        <ActivityIndicator style={styles.spinner} accessibilityLabel={`Loading ${title.toLowerCase()}`} />
      ) : error ? (
        <Text style={styles.note}>Couldn’t load this section. Pull down to try again.</Text>
      ) : (
        children
      )}
    </View>
  );
}

/** "BOS" over "GSW" column heads, away left and home right, for every table here. */
function TeamHeads({ away, home, middle }: { away: string; home: string; middle?: string }) {
  return (
    <View style={styles.row} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
      <Text style={[styles.cellSide, styles.head]}>{away}</Text>
      <Text style={[styles.cellMid, styles.head]}>{middle ?? ''}</Text>
      <Text style={[styles.cellSide, styles.head, styles.right]}>{home}</Text>
    </View>
  );
}

// ── Best price ──────────────────────────────────────────────────────────────

function quoteText(q: TeamLineQuote | null): { main: string; book: string } {
  if (!q) return { main: '—', book: '' };
  const line = q.market === 'h2h' ? '' : `${formatTeamLine(q.line, q.market === 'totals' ? 'totals' : 'spreads')} `;
  return { main: `${line}${formatAmerican(q.price)}`, book: bookLabel(q.book) };
}

function PriceRow({ label, away, home }: { label: string; away: { main: string; book: string }; home: { main: string; book: string } }) {
  return (
    <View
      style={styles.row}
      accessible
      accessibilityLabel={`${label}: away ${away.main}${away.book ? ` at ${away.book}` : ''}; home ${home.main}${home.book ? ` at ${home.book}` : ''}`}
    >
      <View style={styles.cellSide}>
        <Text style={styles.value}>{away.main}</Text>
        {away.book ? <Text style={styles.sub}>{away.book}</Text> : null}
      </View>
      <Text style={[styles.cellMid, styles.label]}>{label}</Text>
      <View style={[styles.cellSide, styles.alignEnd]}>
        <Text style={[styles.value, styles.right]}>{home.main}</Text>
        {home.book ? <Text style={[styles.sub, styles.right]}>{home.book}</Text> : null}
      </View>
    </View>
  );
}

export function BestPriceSection({ m, away, home, started }: { m: Matchup; away: string; home: string; started: boolean }) {
  const b = m.best;
  const over = b?.over ? { main: `o${b.over.line} ${formatAmerican(b.over.price)}`, book: bookLabel(b.over.book) } : { main: '—', book: '' };
  const under = b?.under ? { main: `u${b.under.line} ${formatAmerican(b.under.price)}`, book: bookLabel(b.under.row.bookmaker) } : { main: '—', book: '' };
  const none = b != null && !b.awayMl && !b.homeMl && !b.awaySpread && !b.homeSpread && !b.over && !b.under;
  return (
    <Section title="Best price at your books" loading={m.linesLoading} error={m.linesError}>
      {started ? (
        <Text style={styles.note}>This game has started. These were the last pre-game prices stored.</Text>
      ) : null}
      {none ? (
        <Text style={styles.note}>None of your sportsbooks has posted this game yet.</Text>
      ) : (
        <>
          <TeamHeads away={away} home={home} />
          <PriceRow label="Moneyline" away={quoteText(b?.awayMl ?? null)} home={quoteText(b?.homeMl ?? null)} />
          <PriceRow label="Spread" away={quoteText(b?.awaySpread ?? null)} home={quoteText(b?.homeSpread ?? null)} />
          <PriceRow label="Total" away={over} home={under} />
          <Text style={styles.note}>Total: over on the left, under on the right.</Text>
        </>
      )}
    </Section>
  );
}

// ── Side-by-side ranks ──────────────────────────────────────────────────────

function rankCell(r: TeamStatRank | null): { value: string; rank: string } {
  if (!r) return { value: '—', rank: '' };
  return {
    value: formatTeamStat(r.value, r.def.format),
    rank: r.rank != null ? ordinal(r.rank) : '',
  };
}

function CompareRow({
  pair,
  away,
  home,
  awayRow,
  homeRow,
}: {
  pair: PairedRank<TeamStatRank>;
  away: string;
  home: string;
  awayRow: TeamStatsRow | null;
  homeRow: TeamStatsRow | null;
}) {
  const a = rankCell(pair.away);
  const h = rankCell(pair.home);
  // The W-L behind a betting percent, so 100% over 3 games never reads like 100% over 30.
  const aRec = pair.away && awayRow ? formatRecord(awayRow, pair.away.def) : null;
  const hRec = pair.home && homeRow ? formatRecord(homeRow, pair.home.def) : null;
  const edgeTeam = pair.edge === 'away' ? away : pair.edge === 'home' ? home : null;
  const spoken =
    `${pair.label}: ${away} ${a.value}${a.rank ? `, ${a.rank}` : ''}${aRec ? `, ${aRec}` : ''}; ` +
    `${home} ${h.value}${h.rank ? `, ${h.rank}` : ''}${hRec ? `, ${hRec}` : ''}` +
    (edgeTeam ? `. Edge ${edgeTeam}` : '');
  return (
    <View style={styles.row} accessible accessibilityLabel={spoken}>
      <View style={styles.cellSide}>
        <Text style={[styles.value, pair.edge === 'away' ? styles.edge : null]}>
          {a.value}
          {pair.edge === 'away' ? ' ▲' : ''}
        </Text>
        <Text style={styles.sub}>{[a.rank, aRec].filter(Boolean).join(' · ')}</Text>
      </View>
      <Text style={[styles.cellMid, styles.label]}>{pair.label}</Text>
      <View style={[styles.cellSide, styles.alignEnd]}>
        <Text style={[styles.value, styles.right, pair.edge === 'home' ? styles.edge : null]}>
          {pair.edge === 'home' ? '▲ ' : ''}
          {h.value}
        </Text>
        <Text style={[styles.sub, styles.right]}>{[h.rank, hRec].filter(Boolean).join(' · ')}</Text>
      </View>
    </View>
  );
}

export function CompareSection({
  m,
  away,
  home,
  group,
}: {
  m: Matchup;
  away: string;
  home: string;
  group: 'efficiency' | 'betting';
}) {
  const pairs = pairRanks(m.ranks[group].away, m.ranks[group].home);
  const empty = !m.awayRow && !m.homeRow;
  const of = m.ranks[group].away[0]?.of ?? m.ranks[group].home[0]?.of ?? 0;
  return (
    <Section
      title={group === 'efficiency' ? 'Team comparison' : 'Season betting record'}
      loading={m.board.loading}
      error={m.board.error}
    >
      {empty ? (
        <Text style={styles.note}>No team stats for these teams yet this season.</Text>
      ) : (
        <>
          <TeamHeads away={away} home={home} />
          {pairs.map((p) => (
            <CompareRow key={p.key} pair={p} away={away} home={home} awayRow={m.awayRow} homeRow={m.homeRow} />
          ))}
          <Text style={styles.note}>
            {`▲ marks the better league rank${of ? ` (of ${of})` : ''}. Pace and over rate have no better side.`}
          </Text>
        </>
      )}
    </Section>
  );
}

// ── Last 10, rest ───────────────────────────────────────────────────────────

function SimpleRow({ label, away, home, spoken }: { label: string; away: string; home: string; spoken?: string }) {
  return (
    <View style={styles.row} accessible accessibilityLabel={spoken ?? `${label}: away ${away}; home ${home}`}>
      <Text style={[styles.cellSide, styles.value]}>{away}</Text>
      <Text style={[styles.cellMid, styles.label]}>{label}</Text>
      <Text style={[styles.cellSide, styles.value, styles.right]}>{home}</Text>
    </View>
  );
}

export function FormSection({ m, away, home }: { m: Matchup; away: string; home: string }) {
  const f = m.form;
  const wl = (s: typeof f.away) => (s.games === 0 ? '—' : `${s.wins}-${s.losses}`);
  const margin = (s: typeof f.away) => (s.avgMargin == null ? '—' : formatSigned(s.avgMargin, 1));
  return (
    <Section title={`Last ${MATCHUP_FORM_GAMES} games`} loading={m.formLoading} error={m.formError}>
      <TeamHeads away={away} home={home} />
      <SimpleRow label="Record" away={wl(f.away)} home={wl(f.home)} />
      <SimpleRow label="Avg margin" away={margin(f.away)} home={margin(f.home)} />
      <SimpleRow label="ATS" away={formatAts(f.awayCover)} home={formatAts(f.homeCover)} />
      <SimpleRow label="Over / under" away={formatOu(f.awayCover)} home={formatOu(f.homeCover)} />
      <SimpleRow label="Rest" away={restText(f.awayRest)} home={restText(f.homeRest)} />
      <Text style={styles.note}>ATS and over/under are against the stored closing line.</Text>
    </Section>
  );
}

// ── Head-to-head ────────────────────────────────────────────────────────────

export function HeadToHeadSection({ m, away, home }: { m: Matchup; away: string; home: string }) {
  const h = m.h2h;
  return (
    <Section title="Head-to-head" loading={m.meetingsLoading} error={m.meetingsError}>
      {h.meetings.length === 0 ? (
        <Text style={styles.note}>{`${away} and ${home} haven’t played in the games we store.`}</Text>
      ) : (
        <>
          <Text style={styles.value}>
            {`${away} ${h.wins}-${h.losses} in the last ${h.meetings.length}`}
            {h.avgTotal != null ? ` · avg total ${h.avgTotal.toFixed(1)}` : ''}
          </Text>
          {h.meetings.map((g) => (
            <Text
              key={g.gameId}
              style={styles.meeting}
              accessibilityLabel={`${g.date}: ${away} ${g.result === 'W' ? 'won' : g.result === 'L' ? 'lost' : 'tied'} ${g.scored} to ${g.allowed}${g.isHome ? ' at home' : ' away'}`}
            >
              {`${g.date}  ${away} ${g.scored}–${g.allowed} ${g.isHome ? 'vs' : '@'} ${home}  ${g.result}`}
            </Text>
          ))}
        </>
      )}
    </Section>
  );
}

// ── Injuries ────────────────────────────────────────────────────────────────

export function InjurySection({ m, away, home }: { m: Matchup; away: string; home: string }) {
  const list = (team: string, rows: Matchup['injured']['away']) => (
    <View style={styles.injuryTeam}>
      <Text style={styles.injuryHead}>{team}</Text>
      {rows.length === 0 ? (
        <Text style={styles.note}>No one listed.</Text>
      ) : (
        rows.map((r) => (
          <Text key={r.player_key} style={styles.injuryRow}>
            {`${r.player_name} · ${r.status}${r.injury_type ? ` (${r.injury_type})` : ''}`}
          </Text>
        ))
      )}
    </View>
  );
  return (
    <Section title="Injuries" loading={m.injuriesLoading} error={m.injuriesError}>
      {list(away, m.injured.away)}
      {list(home, m.injured.home)}
    </Section>
  );
}

const styles = StyleSheet.create({
  card: { ...card, gap: spacing.sm },
  title: { ...sectionHeaderText },
  spinner: { paddingVertical: spacing.md },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 44,
    paddingVertical: spacing.xs,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  cellSide: { flex: 1 },
  cellMid: { flex: 1.1, textAlign: 'center', paddingHorizontal: spacing.xs },
  alignEnd: { alignItems: 'flex-end' },
  right: { textAlign: 'right' },
  head: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  label: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  value: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  edge: { color: colors.gradeGood, fontWeight: font.weight.bold },
  sub: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  note: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  meeting: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  injuryTeam: { gap: spacing.xs },
  injuryHead: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  injuryRow: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
});

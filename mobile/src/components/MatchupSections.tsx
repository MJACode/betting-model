/**
 * The matchup page's sections (screens/ScoreboardGameScreen, NBA first —
 * Matt, 2026-11-23). Read top to bottom the way a bet is decided: our pick or
 * "No pick", the best price at the member's books, the two teams side by
 * side, recent form against the number, rest, head-to-head, injuries.
 *
 * Every number here is read, not estimated: ranks from team_stats_board,
 * cover marks from team_period_results, injuries from injury_status_current.
 * A section whose read failed says so in its own card with a Retry; the
 * others still draw.
 *
 * Every row speaks TEAM NAMES, never "away" / "home", and the total row says
 * over and under in words — a price read to the wrong side is wrong
 * information, not missing information (UX review, 2026-11-23).
 */
import React from 'react';
import { Pressable, StyleSheet, Text, View, useWindowDimensions } from 'react-native';

import { SkeletonList } from '@/components/Skeleton';
import type { useMatchup } from '@/hooks/useMatchup';
import { MATCHUP_FORM_GAMES } from '@/hooks/useMatchup';
import { formatAmerican, formatGameDateET, formatSigned, formatStampET } from '@/lib/format';
import { formatAts, formatOu, pairRanks, restText, type PairedRank } from '@/lib/gameMatchup';
import { bookLabel } from '@/lib/markets';
import type { TeamLineQuote } from '@/lib/statsOdds';
import { formatTeamLine, ordinal, type TeamStatRank } from '@/lib/teamDetail';
import { formatRecord, formatTeamStat } from '@/lib/teamStatCatalog';
import { card, colors, font, opacity, spacing, sectionHeaderText } from '@/lib/theme';
import type { TeamStatsRow } from '@/types';

type Matchup = ReturnType<typeof useMatchup>;

/** Above this text scale a row stacks: the label on its own line, the two
 *  teams in two equal columns under it, instead of three squeezed columns. */
const STACK_FONT_SCALE = 1.35;

export function Section({
  title,
  children,
  loading,
  error,
  onRetry,
  note,
}: {
  title: string;
  children: React.ReactNode;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  /** A freshness line under the title ("Updated 6:12 PM"). */
  note?: string | null;
}) {
  return (
    <View style={styles.card}>
      <Text style={styles.title} accessibilityRole="header">{title}</Text>
      {note ? <Text style={styles.note}>{note}</Text> : null}
      {loading ? (
        <SkeletonList label={title.toLowerCase()} rows={3} />
      ) : error ? (
        <View style={styles.errorRow}>
          <Text style={[styles.note, styles.flex]}>Couldn’t load this section.</Text>
          {onRetry ? (
            <Pressable
              onPress={onRetry}
              style={({ pressed }) => [styles.retry, pressed ? styles.pressed : null]}
              accessibilityRole="button"
              accessibilityLabel={`Retry ${title.toLowerCase()}`}
            >
              <Text style={styles.retryText}>Retry</Text>
            </Pressable>
          ) : null}
        </View>
      ) : (
        children
      )}
    </View>
  );
}

/** One side's cell: the main figure, an optional line under it, and whether
 *  that side is marked as the better league rank. */
export interface Cell {
  main: string;
  sub?: string;
  better?: boolean;
}

function useStacked(): boolean {
  return useWindowDimensions().fontScale > STACK_FONT_SCALE;
}

/** "BOS" over "GSW" column heads, away left and home right. Hidden from
 *  VoiceOver: every row below speaks its own team names. */
export function TeamHeads({ away, home }: { away: string; home: string }) {
  const stacked = useStacked();
  return (
    <View style={styles.row} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
      <Text style={[styles.cellSide, styles.head]}>{away}</Text>
      {stacked ? null : <View style={styles.cellMid} />}
      <Text style={[styles.cellSide, styles.head, styles.right]}>{home}</Text>
    </View>
  );
}

function CellView({ cell, right }: { cell: Cell; right?: boolean }) {
  return (
    <View style={[styles.cellSide, right ? styles.alignEnd : null]}>
      <Text style={[styles.value, right ? styles.right : null]}>{cell.main}</Text>
      {cell.sub ? (
        <Text style={[styles.sub, right ? styles.right : null, cell.better ? styles.better : null]}>
          {cell.better ? '● ' : ''}
          {cell.sub}
        </Text>
      ) : null}
    </View>
  );
}

/** away | label | home, or label over two columns at large text. */
export function TriRow({ label, away, home, spoken }: { label: string; away: Cell; home: Cell; spoken: string }) {
  const stacked = useStacked();
  if (stacked) {
    return (
      <View style={styles.stackRow} accessible accessibilityLabel={spoken}>
        <Text style={styles.label}>{label}</Text>
        <View style={styles.stackCells}>
          <CellView cell={away} />
          <CellView cell={home} right />
        </View>
      </View>
    );
  }
  return (
    <View style={styles.row} accessible accessibilityLabel={spoken}>
      <CellView cell={away} />
      <Text style={[styles.cellMid, styles.label]}>{label}</Text>
      <CellView cell={home} right />
    </View>
  );
}

// ── Our pick ────────────────────────────────────────────────────────────────

/** The heading above the pick cards, which sit on the page, not in a card. */
export function SectionHeading({ title }: { title: string }) {
  return <Text style={[styles.title, styles.bareTitle]} accessibilityRole="header">{title}</Text>;
}

// ── Best price ──────────────────────────────────────────────────────────────

/** The line on top, the price and book under it ("−3.5" over "−110 · DraftKings"). */
function quoteCell(q: TeamLineQuote | null): Cell {
  if (!q) return { main: '—' };
  const book = bookLabel(q.book);
  if (q.market === 'h2h') return { main: formatAmerican(q.price), sub: book };
  return { main: formatTeamLine(q.line, 'spreads'), sub: `${formatAmerican(q.price)} · ${book}` };
}

function quoteSpoken(team: string, q: TeamLineQuote | null): string {
  if (!q) return `${team} not posted`;
  const book = bookLabel(q.book);
  if (q.market === 'h2h') return `${team} ${formatAmerican(q.price)} at ${book}`;
  return `${team} ${formatTeamLine(q.line, 'spreads')} at ${formatAmerican(q.price)}, ${book}`;
}

export function BestPriceSection({
  m,
  away,
  home,
  started,
  onRetry,
}: {
  m: Matchup;
  away: string;
  home: string;
  started: boolean;
  onRetry: () => void;
}) {
  const b = m.best;
  const over: Cell = b?.over
    ? { main: `Over ${b.over.line}`, sub: `${formatAmerican(b.over.price)} · ${bookLabel(b.over.book)}` }
    : { main: '—' };
  const under: Cell = b?.under
    ? { main: `Under ${b.under.line}`, sub: `${formatAmerican(b.under.price)} · ${bookLabel(b.under.row.bookmaker)}` }
    : { main: '—' };
  const totalSpoken =
    `Total: ` +
    `over ${b?.over ? `${b.over.line} at ${formatAmerican(b.over.price)}, ${bookLabel(b.over.book)}` : 'not posted'}; ` +
    `under ${b?.under ? `${b.under.line} at ${formatAmerican(b.under.price)}, ${bookLabel(b.under.row.bookmaker)}` : 'not posted'}`;
  const none = b != null && !b.awayMl && !b.homeMl && !b.awaySpread && !b.homeSpread && !b.over && !b.under;
  const asOf = m.linesAsOf ? `Prices as of ${formatStampET(m.linesAsOf)}` : null;
  return (
    <Section
      title="Best price at your books"
      loading={!m.linesLoaded || b == null}
      error={m.linesError}
      onRetry={onRetry}
      note={started ? 'This game has started. Last pre-game prices stored.' : asOf}
    >
      {none ? (
        <Text style={styles.note}>None of your sportsbooks has posted this game yet.</Text>
      ) : (
        <>
          <TeamHeads away={away} home={home} />
          <TriRow
            label="Moneyline"
            away={quoteCell(b?.awayMl ?? null)}
            home={quoteCell(b?.homeMl ?? null)}
            spoken={`Moneyline: ${quoteSpoken(away, b?.awayMl ?? null)}; ${quoteSpoken(home, b?.homeMl ?? null)}`}
          />
          <TriRow
            label="Spread"
            away={quoteCell(b?.awaySpread ?? null)}
            home={quoteCell(b?.homeSpread ?? null)}
            spoken={`Spread: ${quoteSpoken(away, b?.awaySpread ?? null)}; ${quoteSpoken(home, b?.homeSpread ?? null)}`}
          />
          <TriRow label="Total" away={over} home={under} spoken={totalSpoken} />
        </>
      )}
    </Section>
  );
}

// ── Side-by-side ranks ──────────────────────────────────────────────────────

function rankCell(r: TeamStatRank | null, record: string | null, better: boolean): Cell {
  if (!r) return { main: '—' };
  const rank = r.rank != null ? ordinal(r.rank) : '';
  const sub = [rank, record].filter(Boolean).join(' · ');
  return { main: formatTeamStat(r.value, r.def.format), sub: sub || undefined, better };
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
  // The W-L behind a betting percent, so 100% over 3 games never reads like 100% over 30.
  const aRec = pair.away && awayRow ? formatRecord(awayRow, pair.away.def) : null;
  const hRec = pair.home && homeRow ? formatRecord(homeRow, pair.home.def) : null;
  const a = rankCell(pair.away, aRec, pair.edge === 'away');
  const h = rankCell(pair.home, hRec, pair.edge === 'home');
  const side = (team: string, c: Cell, r: TeamStatRank | null, rec: string | null) =>
    `${team} ${c.main}${r?.rank != null ? `, ${ordinal(r.rank)}` : ''}${rec ? `, ${rec}` : ''}`;
  const better = pair.edge === 'away' ? away : pair.edge === 'home' ? home : null;
  const spoken =
    `${pair.label}: ${side(away, a, pair.away, aRec)}; ${side(home, h, pair.home, hRec)}` +
    (better ? `. ${better} ranks better` : '');
  return <TriRow label={pair.label} away={a} home={h} spoken={spoken} />;
}

export function CompareSection({
  m,
  away,
  home,
  group,
  onRetry,
}: {
  m: Matchup;
  away: string;
  home: string;
  group: 'efficiency' | 'betting';
  onRetry: () => void;
}) {
  const pairs = pairRanks(m.ranks[group].away, m.ranks[group].home);
  const empty = !m.awayRow && !m.homeRow;
  const of = m.ranks[group].away[0]?.of ?? m.ranks[group].home[0]?.of ?? 0;
  // Name only the stat on THIS card that has no better side.
  const unranked = pairs.filter((p) => (p.away ?? p.home)?.def.better == null).map((p) => p.label);
  return (
    <Section
      title={group === 'efficiency' ? 'Team comparison' : 'Against the spread this season'}
      loading={m.board.loading}
      error={m.board.error}
      onRetry={onRetry}
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
            {`● better league rank${of ? ` (of ${of})` : ''}.`}
            {unranked.length ? ` ${unranked.join(' and ')} ${unranked.length === 1 ? 'has' : 'have'} no better side.` : ''}
          </Text>
        </>
      )}
    </Section>
  );
}

// ── Last 10, rest ───────────────────────────────────────────────────────────

function PlainRow({ label, away, home, awayVal, homeVal }: { label: string; away: string; home: string; awayVal: string; homeVal: string }) {
  return (
    <TriRow
      label={label}
      away={{ main: awayVal }}
      home={{ main: homeVal }}
      spoken={`${label}: ${away} ${awayVal}; ${home} ${homeVal}`}
    />
  );
}

export function FormSection({ m, away, home, onRetry }: { m: Matchup; away: string; home: string; onRetry: () => void }) {
  const f = m.form;
  const wl = (s: typeof f.away) => (s.games === 0 ? '—' : `${s.wins}-${s.losses}`);
  const margin = (s: typeof f.away) => (s.avgMargin == null ? '—' : formatSigned(s.avgMargin, 1));
  return (
    <Section title={`Last ${MATCHUP_FORM_GAMES} games`} loading={m.formLoading} error={m.formError} onRetry={onRetry}>
      <TeamHeads away={away} home={home} />
      <PlainRow label="Record" away={away} home={home} awayVal={wl(f.away)} homeVal={wl(f.home)} />
      <PlainRow label="Avg margin" away={away} home={home} awayVal={margin(f.away)} homeVal={margin(f.home)} />
      <PlainRow label="ATS" away={away} home={home} awayVal={formatAts(f.awayCover)} homeVal={formatAts(f.homeCover)} />
      <PlainRow label="Over / under" away={away} home={home} awayVal={formatOu(f.awayCover)} homeVal={formatOu(f.homeCover)} />
      <PlainRow label="Rest" away={away} home={home} awayVal={restText(f.awayRest)} homeVal={restText(f.homeRest)} />
      <Text style={styles.note}>
        ATS and over/under are graded against DraftKings’ last line before tip-off (other books’ median when
        DraftKings had none).
      </Text>
    </Section>
  );
}

// ── Head-to-head ────────────────────────────────────────────────────────────

/** A stored ISO game day as "Sat, 3/14/26". 16:00 UTC is still that day in ET,
 *  so the day never slips back across midnight. */
function gameDay(date: string): string {
  return formatGameDateET(`${date}T16:00:00Z`, { withYear: true }) || date;
}

export function HeadToHeadSection({ m, away, home, onRetry }: { m: Matchup; away: string; home: string; onRetry: () => void }) {
  const h = m.h2h;
  return (
    <Section title="Head-to-head" loading={m.meetingsLoading} error={m.meetingsError} onRetry={onRetry}>
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
              accessibilityLabel={`${gameDay(g.date)}: ${away} ${g.result === 'W' ? 'won' : g.result === 'L' ? 'lost' : 'tied'} ${g.scored} to ${g.allowed} ${g.isHome ? 'at home' : `at ${home}`}`}
            >
              {`${gameDay(g.date)}  ${away} ${g.scored}–${g.allowed} ${g.isHome ? 'vs' : '@'} ${home}  ${g.result}`}
            </Text>
          ))}
        </>
      )}
    </Section>
  );
}

// ── Injuries ────────────────────────────────────────────────────────────────

/**
 * The CURRENT injury report (injury_status_current keeps no history). Before
 * tip-off that is the report for this game; once it has started it is not,
 * and the note says so rather than passing today's list off as the game's
 * (PR #1595 review, L2).
 */
export function InjurySection({
  m,
  away,
  home,
  started,
  onRetry,
}: {
  m: Matchup;
  away: string;
  home: string;
  started: boolean;
  onRetry: () => void;
}) {
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
    <Section
      title="Injuries"
      loading={m.injuriesLoading}
      error={m.injuriesError}
      onRetry={onRetry}
      note={
        started
          ? `Current report, not as of tip-off${m.injuriesAsOf ? ` · Updated ${formatStampET(m.injuriesAsOf)}` : ''}`
          : m.injuriesAsOf
            ? `Updated ${formatStampET(m.injuriesAsOf)}`
            : null
      }
    >
      {list(away, m.injured.away)}
      {list(home, m.injured.home)}
    </Section>
  );
}

const styles = StyleSheet.create({
  card: { ...card, gap: spacing.sm },
  title: { ...sectionHeaderText },
  bareTitle: { marginTop: spacing.sm },
  flex: { flex: 1 },
  errorRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  retry: { minHeight: 44, minWidth: 44, justifyContent: 'center', alignItems: 'center', paddingHorizontal: spacing.md },
  retryText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  pressed: { opacity: opacity.pressed },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 44,
    paddingVertical: spacing.xs,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  stackRow: {
    gap: spacing.xs,
    paddingVertical: spacing.xs,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  stackCells: { flexDirection: 'row', gap: spacing.md },
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
  sub: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  better: { color: colors.gradeGood, fontWeight: font.weight.bold },
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

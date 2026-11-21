import React, { useMemo, useState } from 'react';
import { Dimensions, Pressable, StyleSheet, Text, View } from 'react-native';

import { EquityCurve } from '@/components/EquityCurve';
import { unitsSpeech } from '@/lib/a11y';
import { FLAT_UNIT, FLAT_UNIT_TONE_SCALE, formatFlatUnits, formatPctSigned, formatSigned, todayET } from '@/lib/format';
import {
  periodInsights,
  streakOf,
  versusModels,
  type InsightBet,
  type InsightGroup,
  type InsightPeriod,
  type InsightRecord,
  type InsightWindow,
  type ModelDayRecord,
} from '@/lib/performanceInsights';
import { colors, font, pnlColor, radii, spacing, card } from '@/lib/theme';

/**
 * The Performance tab's Insights card (Matt, 2026-11-21): a recap for today,
 * this week (Mon–Sun), this month, this year or all time, with the best and
 * toughest bet, where the units come from, favourites vs underdogs, the
 * closing line, form, the units line, and the member against every posted
 * pick from the models they follow. Scored at "My stakes"; logged bets are
 * folded in. The maths is lib/performanceInsights.ts.
 */

const PERIODS: { value: InsightPeriod; label: string; noun: string; prev: string }[] = [
  { value: 'day', label: 'Today', noun: 'today', prev: 'yesterday' },
  { value: 'week', label: 'Week', noun: 'this week', prev: 'last week' },
  { value: 'month', label: 'Month', noun: 'this month', prev: 'last month' },
  { value: 'year', label: 'Year', noun: 'this year', prev: 'last year' },
  { value: 'all', label: 'All', noun: 'all time', prev: '' },
];

type Split = 'sport' | 'type' | 'book' | 'price';
const SPLITS: { value: Split; label: string }[] = [
  { value: 'sport', label: 'Sport' },
  { value: 'type', label: 'Bet type' },
  { value: 'book', label: 'Book' },
  { value: 'price', label: 'Price' },
];

function shortDate(d: string, opts: Intl.DateTimeFormatOptions): string {
  const [y, m, day] = d.split('-').map(Number);
  return new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', ...opts }).format(
    new Date(Date.UTC(y, m - 1, day)),
  );
}

export function windowLabel(period: InsightPeriod, w: InsightWindow): string {
  if (period === 'all' || !w.from || !w.to) return 'All time';
  if (period === 'day') return shortDate(w.from, { weekday: 'short', month: 'short', day: 'numeric' });
  if (period === 'week') {
    return `${shortDate(w.from, { month: 'short', day: 'numeric' })} – ${shortDate(w.to, { month: 'short', day: 'numeric' })}`;
  }
  if (period === 'month') return shortDate(w.from, { month: 'long', year: 'numeric' });
  return w.from.slice(0, 4);
}

function wlp(r: Pick<InsightRecord, 'wins' | 'losses' | 'pushes'>): string {
  return `${r.wins}–${r.losses}` + (r.pushes > 0 ? `–${r.pushes}` : '');
}

function wlpSpeech(r: Pick<InsightRecord, 'wins' | 'losses' | 'pushes'>): string {
  return `${r.wins} won, ${r.losses} lost` + (r.pushes > 0 ? `, ${r.pushes} pushed` : '');
}

function betsWord(n: number): string {
  return `${n} ${n === 1 ? 'bet' : 'bets'}`;
}

function roiText(roi: number | null): string | null {
  return roi == null ? null : `ROI ${formatPctSigned(roi)}`;
}

export function PerformanceInsightsCard({
  bets,
  modelDaily,
  modelDailyReady,
}: {
  bets: InsightBet[];
  modelDaily: ModelDayRecord[];
  modelDailyReady: boolean;
}) {
  const [period, setPeriod] = useState<InsightPeriod>('week');
  const [split, setSplit] = useState<Split>('sport');
  const today = todayET();
  const meta = PERIODS.find((p) => p.value === period) ?? PERIODS[1];

  const ins = useMemo(() => periodInsights(bets, period, today), [bets, period, today]);
  const streak = useMemo(() => streakOf(bets), [bets]);
  const vs = useMemo(
    () => (modelDailyReady ? versusModels(bets, modelDaily, ins.window, FLAT_UNIT) : null),
    [bets, modelDaily, modelDailyReady, ins.window],
  );

  const r = ins.record;
  const decided = r.wins + r.losses + r.pushes;
  const groups: InsightGroup[] =
    split === 'sport' ? ins.bySport : split === 'type' ? ins.byBetType : split === 'book' ? ins.byBook : ins.byPrice;
  const chartWidth = Dimensions.get('window').width - spacing.lg * 4;

  const header = (
    <View style={styles.header}>
      <Text style={styles.title} accessibilityRole="header">
        Insights
      </Text>
      <Text style={styles.window}>{windowLabel(period, ins.window)}</Text>
    </View>
  );

  if (bets.length === 0) {
    return (
      <View style={styles.card}>
        {header}
        <Text style={styles.empty}>
          Track a pick or log a bet and your daily, weekly, monthly and yearly recaps build here.
        </Text>
      </View>
    );
  }

  const prevDelta =
    ins.previous && ins.previous.wins + ins.previous.losses + ins.previous.pushes > 0
      ? r.net - ins.previous.net
      : null;

  return (
    <View style={styles.card}>
      {header}

      <View style={styles.pills} accessibilityRole="radiogroup">
        {PERIODS.map((p) => {
          const active = p.value === period;
          return (
            <Pressable
              key={p.value}
              onPress={() => setPeriod(p.value)}
              // ~28pt pill: 8 + 28 + 8 = 44pt, as the stake-basis pills.
              hitSlop={{ top: 8, bottom: 8 }}
              accessibilityRole="radio"
              accessibilityState={{ checked: active, selected: active }}
              accessibilityLabel={`Recap for ${p.noun}`}
              style={[styles.pill, active && styles.pillActive]}
            >
              <Text style={[styles.pillText, active && styles.pillTextActive]}>{p.label}</Text>
            </Pressable>
          );
        })}
      </View>

      {r.bets === 0 ? (
        <Text style={styles.empty}>No bets {meta.noun} yet.</Text>
      ) : (
        <>
          <View
            accessible
            accessibilityLabel={unitsSpeech(
              [
                `${formatFlatUnits(r.net)} ${meta.noun}`,
                decided > 0 ? wlpSpeech(r) : 'nothing settled yet',
                roiText(r.roi),
                r.open > 0 ? `${r.open} open` : null,
                prevDelta != null ? `${formatFlatUnits(prevDelta)} versus ${meta.prev}` : null,
              ]
                .filter(Boolean)
                .join(', '),
            )}
          >
            <Text style={[styles.hero, { color: pnlColor(r.net, 2, FLAT_UNIT_TONE_SCALE) }]}>
              {formatFlatUnits(r.net)}
            </Text>
            <Text style={styles.heroSub}>
              {[decided > 0 ? wlp(r) : 'Nothing settled yet', roiText(r.roi), r.open > 0 ? `${r.open} open` : null]
                .filter(Boolean)
                .join(' · ')}
            </Text>
            {prevDelta != null ? (
              <Text style={styles.caption}>
                {formatFlatUnits(prevDelta)} vs {meta.prev}
              </Text>
            ) : null}
          </View>

          {ins.curve.length >= 2 ? (
            <View style={styles.chart}>
              <EquityCurve
                points={ins.curve.map((p) => ({ date: p.date, cumUnits: p.cum / FLAT_UNIT }))}
                seriesId={`insights-${period}`}
                width={chartWidth}
                height={150}
                endUnits={r.net / FLAT_UNIT}
              />
            </View>
          ) : null}

          {ins.best || ins.worst ? (
            <View style={styles.section}>
              {ins.best ? <BetLine label="Best bet" bet={ins.best} /> : null}
              {ins.worst ? <BetLine label="Toughest loss" bet={ins.worst} /> : null}
            </View>
          ) : null}

          {decided > 0 ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Where your units come from</Text>
              <View style={styles.pills} accessibilityRole="radiogroup">
                {SPLITS.map((s) => {
                  const active = s.value === split;
                  return (
                    <Pressable
                      key={s.value}
                      onPress={() => setSplit(s.value)}
                      hitSlop={{ top: 8, bottom: 8 }}
                      accessibilityRole="radio"
                      accessibilityState={{ checked: active, selected: active }}
                      accessibilityLabel={`Group by ${s.label.toLowerCase()}`}
                      style={[styles.pill, active && styles.pillActive]}
                    >
                      <Text style={[styles.pillText, active && styles.pillTextActive]}>{s.label}</Text>
                    </Pressable>
                  );
                })}
              </View>
              {groups.length === 0 ? (
                <Text style={styles.caption}>
                  {split === 'price' ? 'None of these bets carries a price.' : 'Your logged bets don’t say this, so they sit out here.'}
                </Text>
              ) : (
                groups.map((g) => <GroupRow key={g.label} g={g} />)
              )}
              {split === 'sport' || split === 'type' ? (
                <Text style={styles.caption}>Tracked picks only: a logged bet doesn’t name its sport or market.</Text>
              ) : null}
            </View>
          ) : null}

          <ClvSection clv={ins.clv} />
        </>
      )}

      {streak.kind ? (
        <View style={styles.section} accessible accessibilityLabel={formSpeech(streak)}>
          <Text style={styles.sectionTitle}>Form</Text>
          <Text style={styles.body}>
            Last {streak.last10Wins + streak.last10Losses}: {streak.last10Wins}–{streak.last10Losses} ·{' '}
            {streak.kind === 'W' ? 'Won' : 'Lost'} {streak.length === 1 ? 'the last one' : `the last ${streak.length}`}
          </Text>
          <Text style={styles.caption}>Across every settled bet, not just {meta.noun}. Pushes are skipped.</Text>
        </View>
      ) : null}

      {vs ? <VersusSection vs={vs} noun={meta.noun} /> : null}

      <Text style={styles.caption}>Scored at your stakes. Includes the bets you logged.</Text>
    </View>
  );
}

function formSpeech(s: ReturnType<typeof streakOf>): string {
  const n = s.last10Wins + s.last10Losses;
  return `Form. Last ${n}: ${s.last10Wins} won, ${s.last10Losses} lost. ${s.kind === 'W' ? 'Won' : 'Lost'} ${
    s.length === 1 ? 'the last one' : `the last ${s.length}`
  }.`;
}

function BetLine({ label, bet }: { label: string; bet: InsightBet }) {
  return (
    <View
      style={styles.row}
      accessible
      accessibilityLabel={unitsSpeech(`${label}: ${bet.title}, ${formatFlatUnits(bet.profit)}`)}
    >
      <View style={styles.rowMain}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={styles.rowTitle} numberOfLines={2}>
          {bet.title}
        </Text>
      </View>
      <Text style={[styles.rowRight, { color: pnlColor(bet.profit, 2, FLAT_UNIT_TONE_SCALE) }]}>
        {formatFlatUnits(bet.profit)}
      </Text>
    </View>
  );
}

function GroupRow({ g }: { g: InsightGroup }) {
  const sub = [wlp(g), betsWord(g.wins + g.losses + g.pushes), roiText(g.roi)].filter(Boolean).join(' · ');
  return (
    <View
      style={styles.row}
      accessible
      accessibilityLabel={unitsSpeech(`${g.label}: ${formatFlatUnits(g.net)}, ${wlpSpeech(g)}`)}
    >
      <View style={styles.rowMain}>
        <Text style={styles.rowTitle} numberOfLines={1}>
          {g.label}
        </Text>
        <Text style={styles.rowSub}>{sub}</Text>
      </View>
      <Text style={[styles.rowRight, { color: pnlColor(g.net, 2, FLAT_UNIT_TONE_SCALE) }]}>
        {formatFlatUnits(g.net)}
      </Text>
    </View>
  );
}

function ClvSection({ clv }: { clv: ReturnType<typeof periodInsights>['clv'] }) {
  const measured = clv.beats + clv.losses + clv.pushes;
  if (measured === 0) return null;
  const pct = clv.beatRate != null ? Math.round(clv.beatRate * 100) : null;
  const line =
    pct != null
      ? `Beat the close on ${pct}% (${clv.beats} of ${clv.beats + clv.losses})` +
        (clv.pushes > 0 ? `, ${clv.pushes} matched` : '')
      : `All ${clv.pushes} matched the close`;
  return (
    <View style={styles.section} accessible accessibilityLabel={`Closing line. ${line}. Average ${clv.avgPct != null ? formatSigned(clv.avgPct, 1, '%') : 'not measured'}.`}>
      <Text style={styles.sectionTitle}>Closing line</Text>
      <Text style={styles.body}>
        {line}
        {clv.avgPct != null ? ` · avg ${formatSigned(clv.avgPct, 1, '%')}` : ''}
      </Text>
      <Text style={styles.caption}>
        Getting a better price than the close is the earliest sign of an edge, long before the record shows it.
        Tracked picks with a measured close only.
      </Text>
    </View>
  );
}

function VersusSection({ vs, noun }: { vs: NonNullable<ReturnType<typeof versusModels>>; noun: string }) {
  const you = vs.you.roi;
  const them = vs.models_record.roi;
  let verdict: string | null = null;
  if (you != null && them != null) {
    const gap = Math.abs(you - them) * 100;
    const pts = `${gap.toFixed(1)} ${gap.toFixed(1) === '1.0' ? 'point' : 'points'} of ROI`;
    if (you > them) verdict = `Your picks are ahead of tailing every one by ${pts}.`;
    else if (you < them) verdict = `Tailing every posted pick did ${pts} better.`;
    else verdict = 'Level with tailing every posted pick.';
  }
  const n = vs.models.length;
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>You vs the models you follow</Text>
      <VersusRow label="Your picks" r={vs.you} />
      <VersusRow label={`Every posted pick, same ${n === 1 ? 'model' : `${n} models`}`} r={vs.models_record} />
      {verdict ? <Text style={styles.body}>{verdict}</Text> : null}
      <Text style={styles.caption}>
        Your tracked picks {noun} against every pick those models posted over the same days. Compared on ROI, since
        your stakes differ from the posted ones. Logged bets have no model, so they sit out.
      </Text>
    </View>
  );
}

function VersusRow({ label, r }: { label: string; r: InsightRecord }) {
  const roi = roiText(r.roi);
  return (
    <View
      style={styles.row}
      accessible
      accessibilityLabel={`${label}: ${wlpSpeech(r)}${roi ? `, ${roi}` : ''}`}
    >
      <View style={styles.rowMain}>
        <Text style={styles.rowTitle}>{label}</Text>
        <Text style={styles.rowSub}>{wlp(r)}</Text>
      </View>
      <Text style={[styles.rowRight, { color: r.roi == null ? colors.textSecondary : pnlColor(r.roi * 100, 1) }]}>
        {r.roi == null ? '—' : formatPctSigned(r.roi)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    ...card,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  window: { fontSize: font.size.footnote, color: colors.textTertiary, fontWeight: font.weight.semibold },
  empty: { fontSize: font.size.footnote, color: colors.textSecondary, lineHeight: 18 },
  pills: {
    flexDirection: 'row',
    backgroundColor: colors.bg,
    borderRadius: radii.pill,
    padding: 3,
    marginBottom: spacing.sm,
  },
  pill: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 5,
    borderRadius: radii.pill,
  },
  pillActive: { backgroundColor: colors.tint },
  pillText: { fontSize: font.size.footnote, color: colors.textSecondary, fontWeight: font.weight.medium },
  pillTextActive: { color: colors.textInverse, fontWeight: font.weight.semibold },
  hero: { fontSize: font.size.title1, fontWeight: font.weight.bold, marginTop: spacing.xs },
  heroSub: { fontSize: font.size.callout, color: colors.textPrimary, fontWeight: font.weight.semibold, marginTop: 2 },
  chart: { marginTop: spacing.sm },
  section: {
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  sectionTitle: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  body: { fontSize: font.size.callout, color: colors.textPrimary, marginTop: 2 },
  caption: { fontSize: font.size.caption, color: colors.textTertiary, marginTop: spacing.xs, lineHeight: 16 },
  row: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.xs,
  },
  rowMain: { flex: 1 },
  rowLabel: { fontSize: font.size.caption, color: colors.textTertiary },
  rowTitle: { fontSize: font.size.body, color: colors.textPrimary, fontWeight: font.weight.medium },
  rowSub: { fontSize: font.size.caption, color: colors.textTertiary, marginTop: 2 },
  rowRight: { fontSize: font.size.callout, fontWeight: font.weight.semibold, marginLeft: spacing.md },
});

/**
 * One team's page, off the Stats tab's Teams board (Matt, 2026-09-19: "you
 * should be able to click in a team and see useful stats to help a user make
 * a bet — public bet vs sharp, home vs away, record against that team").
 *
 * Ordered by how a bettor actually reads a team before a game:
 *
 *  1. THE NEXT GAME — who, when, and the member's own line for each market
 *     (the same pills as the board, the same add-to-betslip tap), then the
 *     MARKET READ under them: where the line has moved since it opened, where
 *     the sharp book has it against the member's book, and where the public's
 *     tickets and money sit. These are the three signals the literature gives
 *     any weight to; the descriptive splits come after.
 *  2. FORM — last ten, from the team's side, with cover / over marks where
 *     the sport stores a closing number per game (NFL today).
 *  3. SPLITS — home / away, favourite / dog, rest, over rate, from the board's
 *     row, captioned as description rather than edge, as the board does.
 *  4. HEAD-TO-HEAD with the next opponent.
 *  5. OUR RECORD betting on and against the team — settled BETs only, units
 *     only, and the unpriced picks named rather than priced at −110.
 *  6. LEAGUE RANKS on the sport's efficiency metrics.
 *
 * Every section fails alone (hooks/useTeamDetail): a missing public split is a
 * sentence, not a blank page.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { RouteProp } from '@react-navigation/native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { AddLineSheet } from '@/components/AddLineSheet';
import { GameStatusPill } from '@/components/GameStatusPill';
import { ReadRow } from '@/components/ReadRow';
import { SectionTitle } from '@/components/SectionTitle';
import { StatTile } from '@/components/StatTile';
import { TeamLineCell } from '@/components/TeamsBoard';
import { FORM_GAMES, RECORD_GAMES, useTeamDetail, type NextGame } from '@/hooks/useTeamDetail';
import { formatPct, formatSignedUnits, weekdayShortET, formatGameTimeET, formatStampET } from '@/lib/format';
import { teamLineSheetInput } from '@/lib/lineLegs';
import { bookName } from '@/lib/markets';
import { buildTeamLineIndex, type TeamLineQuote } from '@/lib/statsOdds';
import { isThinSample, sampleFor, type Tier } from '@/lib/teamBoard';
import {
  formatTeamLine,
  formatWinLoss,
  ordinal,
  PUBLIC_SPLITS_SPORTS,
  summarizeForm,
  teamRanks,
  type FormGame,
  type PickRecord,
  type TeamMarket,
} from '@/lib/teamDetail';
import { formatTeamStat, TEAM_STAT_CATALOG, type TeamStatDef } from '@/lib/teamStatCatalog';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList, TeamSport, TeamStatsRow } from '@/types';

type Route = RouteProp<RootStackParamList, 'TeamStats'>;

const MARKET_LABEL: Record<TeamMarket, string> = { h2h: 'Moneyline', spreads: 'Spread', totals: 'Total' };
const MARKETS: TeamMarket[] = ['h2h', 'spreads', 'totals'];

export function TeamStatsScreen() {
  const route = useRoute<Route>();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { team, sport, season, conference } = route.params;
  const fromParlay = route.params.fromParlay === true;

  useEffect(() => {
    navigation.setOptions({ title: team });
  }, [navigation, team]);

  const d = useTeamDetail(sport, team, season);
  const [lineSheet, setLineSheet] = useState<TeamLineQuote | null>(null);

  // The member's own line for each market, from the team's side — the board's
  // index, run once per market against the same rows.
  const quotes = useMemo(() => {
    const out: Partial<Record<TeamMarket, TeamLineQuote | null>> = {};
    const ng = d.nextGame;
    if (!ng || !ng.unstarted) return out;
    for (const m of MARKETS) {
      const idx = buildTeamLineIndex(ng.lines, [ng.entry.game], { market: m, books: d.books });
      out[m] = idx.get(team) ?? null;
    }
    return out;
  }, [d.nextGame, d.books, team]);

  const row = d.row;
  const seasonLabel = d.board.data.season;
  const form = d.form.slice(0, FORM_GAMES);
  const formSummary = useMemo(() => summarizeForm(form), [form]);
  const last5 = useMemo(() => summarizeForm(form, 5), [form]);
  const hasCoverMarks = form.some((g) => g.ats != null);
  const efficiency = useMemo(
    () => teamRanks(d.board.data.rows, team, sport, 'Efficiency'),
    [d.board.data.rows, team, sport],
  );

  const boardEmpty = !d.board.loading && !row;

  // The pull spinner shows for a PULL, not for the first load — each section
  // already has its own indicator, and two spinners for one fetch reads as
  // two fetches (UX review).
  const [pulled, setPulled] = useState(false);
  useEffect(() => {
    if (!d.loading) setPulled(false);
  }, [d.loading]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={pulled && d.loading}
            onRefresh={() => {
              setPulled(true);
              d.refresh();
            }}
          />
        }
      >
        {/* ── Header ─────────────────────────────────────────────────────── */}
        <View style={styles.header}>
          <Text style={styles.teamName} numberOfLines={1}>
            {team}
          </Text>
          <Text style={styles.meta}>
            {conference ? `${conference} · ` : ''}
            {row
              ? `${row.wins}-${row.losses}${
                  row.point_diff_pg != null
                    ? ` · ${Number(row.point_diff_pg) > 0 ? '+' : ''}${Number(row.point_diff_pg).toFixed(1)}/g`
                    : ''
                }${seasonLabel ? ` · ${seasonLabel}` : ''}`
              : d.board.loading
                ? 'Loading record…'
                : `No ${sport} record stored yet.`}
          </Text>
        </View>

        {d.board.error ? (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>Connection error: {d.board.error}</Text>
          </View>
        ) : null}

        {/* ── 1. Next game + market read ─────────────────────────────────── */}
        <NextGameCard
          team={team}
          nextGame={d.nextGame}
          quotes={quotes}
          booksReady={d.booksReady}
          books={d.books}
          loading={d.slate.loading || d.marketLoading}
          error={d.marketError}
          onLinePress={(q) => setLineSheet(q)}
          publicCoverage={PUBLIC_SPLITS_SPORTS.has(sport)}
        />

        {/* ── 2. Form ────────────────────────────────────────────────────── */}
        <SectionTitle title={`Last ${form.length || FORM_GAMES}`} />
        {d.recent.loading && form.length === 0 ? (
          <ActivityIndicator style={styles.loading} />
        ) : form.length === 0 ? (
          <Card>
            <Text style={styles.muted}>
              {d.recent.error
                ? `Couldn’t load recent games — ${d.recent.error}`
                : `No finished ${sport} games stored for ${team} yet.`}
            </Text>
          </Card>
        ) : (
          <>
            <Card>
              {/* College names do not fit a 10-cell strip ("Northwestern State"
                  at 32pt a cell is "Nor…"), so NCAAF gets one row per game. */}
              {sport === 'NCAAF' ? (
                form.map((g) => <MeetingRow key={g.gameId} game={g} team={team} />)
              ) : (
                <FormStrip games={form} />
              )}
              {hasCoverMarks ? (
                <Text style={styles.legend}>
                  ✓ covered the closing spread · ✗ didn’t · O/U against the closing total
                </Text>
              ) : sport === 'NFL' ? null : (
                <Text style={styles.legend}>
                  Per-game spread results aren’t stored for {sport} yet — season ATS splits are below.
                </Text>
              )}
            </Card>
            <View style={styles.tileRow}>
              <StatTile
                label="Last 5"
                value={`${last5.wins}-${last5.losses}${last5.ties ? `-${last5.ties}` : ''}`}
                caption={last5.avgMargin != null ? `${signed(last5.avgMargin, 1)} margin` : undefined}
              />
              <StatTile
                label={`Last ${form.length}`}
                value={`${formSummary.wins}-${formSummary.losses}${formSummary.ties ? `-${formSummary.ties}` : ''}`}
                caption={formSummary.avgMargin != null ? `${signed(formSummary.avgMargin, 1)} margin` : undefined}
              />
              {hasCoverMarks ? (
                <StatTile
                  label="ATS"
                  value={`${formSummary.atsW}-${formSummary.atsL}${formSummary.atsP ? `-${formSummary.atsP}` : ''}`}
                  caption={`O/U ${formSummary.overs}-${formSummary.unders}`}
                />
              ) : (
                <StatTile
                  label="Scoring"
                  value={formSummary.avgScored != null ? formSummary.avgScored.toFixed(1) : '—'}
                  caption={formSummary.avgAllowed != null ? `${formSummary.avgAllowed.toFixed(1)} allowed` : undefined}
                />
              )}
            </View>
          </>
        )}

        {/* ── 3. Splits ──────────────────────────────────────────────────── */}
        <SectionTitle
          title="Situational splits"
          tooltip={{
            title: 'Description, not edge',
            body:
              'Home/away, favourite/dog and rest splits describe what already happened this season. ' +
              'They regress toward .500 once the market prices a trend in — read them as context for the ' +
              'number, not as a reason to bet against it. Rest is the one split with a documented, repeatable effect.',
          }}
        />
        {row ? <SplitsTiles row={row} sport={sport} /> : boardEmpty ? (
          <Card>
            <Text style={styles.muted}>No season splits stored for {team} yet.</Text>
          </Card>
        ) : null}

        {/* ── 4. Head-to-head ────────────────────────────────────────────── */}
        {d.h2h ? (
          <>
            <SectionTitle title={`vs ${d.h2h.opponent}`} />
            {d.h2hLoading && d.h2h.meetings.length === 0 ? (
              <ActivityIndicator style={styles.loading} />
            ) : d.h2h.meetings.length === 0 ? (
              <Card>
                <Text style={styles.muted}>No stored meetings between {team} and {d.h2h.opponent}.</Text>
              </Card>
            ) : (
              <>
                <View style={styles.tileRow}>
                  <StatTile
                    label={`Last ${d.h2h.meetings.length}`}
                    value={`${d.h2h.wins}-${d.h2h.losses}${d.h2h.ties ? `-${d.h2h.ties}` : ''}`}
                    caption={`${team} record`}
                  />
                  <StatTile
                    label="Avg margin"
                    value={d.h2h.avgMargin != null ? signed(d.h2h.avgMargin, 1) : '—'}
                    caption={`home ${d.h2h.homeW}-${d.h2h.homeL} · away ${d.h2h.awayW}-${d.h2h.awayL}`}
                  />
                  <StatTile
                    label="Avg total"
                    value={d.h2h.avgTotal != null ? d.h2h.avgTotal.toFixed(1) : '—'}
                    caption="points per meeting"
                  />
                </View>
                <Card>
                  {d.h2h.meetings.slice(0, 5).map((g) => (
                    <MeetingRow key={g.gameId} game={g} team={team} />
                  ))}
                </Card>
              </>
            )}
          </>
        ) : null}

        {/* ── 5. Our record on this team ─────────────────────────────────── */}
        <SectionTitle
          title="Our picks on this team"
          tooltip={{
            title: 'Settled bets only',
            body:
              `Every settled BET our models made in ${team}’s last ${RECORD_GAMES} games, split by side. ` +
              'Results are in units: one unit is one flat bet. A pick that carried no price counts in the ' +
              'record but not the units, so nothing here is priced at an invented −110.',
          }}
        />
        {d.picksLoading && d.pickRecords.settled === 0 ? (
          <ActivityIndicator style={styles.loading} />
        ) : d.pickRecords.settled === 0 ? (
          <Card>
            <Text style={styles.muted}>
              {d.picks.error
                ? `Couldn’t load our picks — ${d.picks.error}`
                : `No settled picks in ${team}’s last ${Math.min(RECORD_GAMES, d.recent.data.length) || RECORD_GAMES} games.`}
            </Text>
          </Card>
        ) : (
          <>
            <View style={styles.tileRow}>
              <RecordTile label={`On ${team}`} record={d.pickRecords.on} />
              <RecordTile label={`Against ${team}`} record={d.pickRecords.against} />
            </View>
            <View style={styles.tileRow}>
              <RecordTile label="Overs" record={d.pickRecords.over} />
              <RecordTile label="Unders" record={d.pickRecords.under} />
            </View>
            <Text style={styles.footnote}>
              {d.pickRecords.settled} settled {d.pickRecords.settled === 1 ? 'bet' : 'bets'} in the last{' '}
              {Math.min(RECORD_GAMES, d.recent.data.length)} games, live picks included.
            </Text>
          </>
        )}

        {/* ── 6. League ranks ────────────────────────────────────────────── */}
        <SectionTitle title="Efficiency" />
        {efficiency.length > 0 && row ? (
          <Card>
            {efficiency.map((r) => (
              <RankRow key={String(r.def.key)} label={r.def.label} value={formatTeamStat(r.value, r.def.format)} rank={r.rank} of={r.of} tier={r.tier} hint={r.def.hint} />
            ))}
          </Card>
        ) : d.board.loading ? (
          <ActivityIndicator style={styles.loading} />
        ) : (
          <Card>
            <Text style={styles.muted}>No efficiency metrics stored for {team} yet.</Text>
          </Card>
        )}
      </ScrollView>

      <AddLineSheet
        input={lineSheet ? teamLineSheetInput(lineSheet, sport) : null}
        game={lineSheet && d.nextGame ? d.nextGame.entry.game : null}
        onClose={() => setLineSheet(null)}
        onAdded={fromParlay ? () => navigation.navigate('Betslip') : undefined}
      />
    </SafeAreaView>
  );
}

// ── Next game ───────────────────────────────────────────────────────────────

function NextGameCard({
  team,
  nextGame,
  quotes,
  booksReady,
  books,
  loading,
  error,
  onLinePress,
  publicCoverage,
}: {
  team: string;
  nextGame: NextGame | null;
  quotes: Partial<Record<TeamMarket, TeamLineQuote | null>>;
  booksReady: boolean;
  books: readonly string[];
  loading: boolean;
  error: string | null;
  onLinePress: (q: TeamLineQuote) => void;
  /** Whether the public-splits feed covers this sport at all. */
  publicCoverage: boolean;
}) {
  if (!nextGame) {
    // Reserve the section while the slate loads, so the page does not reflow
    // when it lands (UX review).
    return (
      <>
        <SectionTitle title="Next game" />
        <Card>
          {loading ? (
            <ActivityIndicator style={styles.loadingInline} />
          ) : (
            <Text style={styles.muted}>No {team} game on the schedule in the next 7 days.</Text>
          )}
        </Card>
      </>
    );
  }
  const { entry, unstarted } = nextGame;
  const side = entry.isHome === null ? `vs ${entry.opponent}` : `${entry.isHome ? 'vs' : '@'} ${entry.opponent}`;
  const day = weekdayShortET(entry.game.commence_time);
  const time = formatGameTimeET(entry.game.commence_time);
  const anyQuote = MARKETS.some((m) => quotes[m]);
  const myBook = books.length === 1 ? bookName(books[0]) : 'your books';

  return (
    <>
      {/* A game already under way or finished is today's game, not the next
          one — the title and the status pill say which (UX review). */}
      <SectionTitle title={unstarted ? 'Next game' : 'Today’s game'} />
      <Card>
        <View style={styles.fixtureRow}>
          <Text style={styles.fixture} numberOfLines={1}>
            {side}
            {unstarted ? <Text style={styles.fixtureWhen}>  {day ? `${day} ` : ''}{time}</Text> : null}
          </Text>
          {unstarted ? null : <GameStatusPill game={entry.game} />}
        </View>

        {/* The member's own line for each market, from the team's side. The
            pill asks — a tap opens the add-to-betslip sheet, as on the board. */}
        {unstarted && booksReady && anyQuote ? (
          <View style={styles.pillRow}>
            {MARKETS.map((m) => (
              <View key={m} style={styles.pillCol}>
                <Text style={styles.pillLabel}>{MARKET_LABEL[m]}</Text>
                <TeamLineCell
                  quote={quotes[m] ?? null}
                  team={team}
                  onPress={quotes[m] ? () => onLinePress(quotes[m]!) : undefined}
                />
              </View>
            ))}
          </View>
        ) : unstarted && !loading ? (
          <Text style={styles.muted}>
            {error ? `Couldn’t load lines — ${error}` : `${myBook.replace(/^./, (c) => c.toUpperCase())} ${books.length === 1 ? 'hasn’t' : 'haven’t'} posted lines for this game yet.`}
          </Text>
        ) : null}
        {loading && !anyQuote ? <ActivityIndicator style={styles.loadingInline} /> : null}
      </Card>

      {unstarted ? (
        <MarketRead team={team} nextGame={nextGame} publicCoverage={publicCoverage} />
      ) : null}
    </>
  );
}

/**
 * The three signals, each as one sentence the reader can act on plus the
 * per-market numbers behind it. Written from the TEAM's side throughout:
 * "moved toward" means the team got dearer.
 */
function MarketRead({
  team,
  nextGame,
  publicCoverage,
}: {
  team: string;
  nextGame: NextGame;
  publicCoverage: boolean;
}) {
  const { moves, sharp, publicSide } = nextGame;
  const anyMove = MARKETS.some((m) => moves[m]);
  const anySharp = MARKETS.some((m) => sharp[m]);
  const anyPublic = MARKETS.some((m) => publicSide[m]);

  return (
    <>
      <SectionTitle
        title="Market read"
        tooltip={{
          title: 'Three reads on one game',
          body:
            'LINE MOVEMENT is the DraftKings number at open against now. A line that moved toward a side ' +
            'is steam on it; the move itself is the information, not a reason to chase it.\n\n' +
            'SHARP vs YOUR BOOK compares Pinnacle’s no-vig price — the book the market follows — with ' +
            'your book’s no-vig price on the same side. A positive gap means your book prices the side ' +
            'richer than Pinnacle does.\n\n' +
            'PUBLIC MONEY is the consensus share of tickets and money on this side. Money outrunning tickets ' +
            'is bigger bettors on the side; a crowd piled on one side is the side the book has already shaded.',
        }}
      />

      {/* Line movement */}
      <Card>
        <Text style={styles.readTitle}>Line movement since open</Text>
        {anyMove ? (
          <>
            <Text style={styles.readLead}>{movementLead(team, nextGame)}</Text>
            {MARKETS.map((m) => {
              const mv = moves[m];
              if (!mv) return null;
              const from = m === 'h2h' ? formatPct(mv.openProb, 0) : formatTeamLine(mv.openLine, m);
              const to = m === 'h2h' ? formatPct(mv.nowProb, 0) : formatTeamLine(mv.nowLine, m);
              return (
                <ReadRow
                  key={m}
                  label={MARKET_LABEL[m]}
                  value={`${from} → ${to}`}
                  note={mv.direction === 'flat' ? 'steady' : mv.direction === 'toward' ? (m === 'totals' ? 'toward the over' : `toward ${team}`) : (m === 'totals' ? 'toward the under' : `away from ${team}`)}
                />
              );
            })}
            <Text style={styles.source}>
              DraftKings, from the first stored line to the latest{asOf(MARKETS.map((m) => moves[m]?.asOf ?? null))}. Moneyline shown as no-vig win probability.
            </Text>
          </>
        ) : (
          <Text style={styles.muted}>No opening line stored for this game yet.</Text>
        )}
      </Card>

      {/* Sharp vs the member's book */}
      <Card>
        <Text style={styles.readTitle}>Sharp book vs yours</Text>
        {anySharp ? (
          <>
            <Text style={styles.readLead}>{sharpLead(team, nextGame)}</Text>
            {MARKETS.map((m) => {
              const s = sharp[m];
              if (!s) return null;
              const sharpTxt = m === 'h2h'
                ? formatPct(s.sharpProb, 0)
                : `${formatTeamLine(s.sharpLine, m)} (${formatPct(s.sharpProb, 0)})`;
              const mineTxt = s.book == null
                ? '—'
                : m === 'h2h'
                  ? formatPct(s.bookFairProb, 0)
                  : `${formatTeamLine(s.bookLine, m)} (${formatPct(s.bookFairProb, 0)})`;
              return (
                <ReadRow
                  key={m}
                  label={MARKET_LABEL[m]}
                  value={`Pinnacle ${sharpTxt}`}
                  note={
                    s.book
                      ? `${bookName(s.book)} ${mineTxt}${s.fairGapPp != null ? ` · ${signed(s.fairGapPp, 1)}pp` : ''}${
                          s.bookProb != null ? ` · you pay ${formatPct(s.bookProb, 0)}` : ''
                        }`
                      : 'not posted at your book'
                  }
                />
              );
            })}
            <Text style={styles.source}>
              Both books de-vigged the same way, so the gap is fair-to-fair; “you pay” is your book’s price with its vig in{asOf(MARKETS.map((m) => sharp[m]?.asOf ?? null))}.
            </Text>
          </>
        ) : (
          <Text style={styles.muted}>Pinnacle hasn’t posted this game yet.</Text>
        )}
      </Card>

      {/* Public splits */}
      <Card>
        <Text style={styles.readTitle}>Public money</Text>
        {anyPublic ? (
          <>
            <Text style={styles.readLead}>{publicLead(team, nextGame)}</Text>
            {MARKETS.map((m) => {
              const p = publicSide[m];
              if (!p) return null;
              return (
                <ReadRow
                  key={m}
                  label={MARKET_LABEL[m]}
                  value={`${p.betPct != null ? `${Math.round(p.betPct)}% of bets` : '—'}`}
                  note={p.moneyPct != null ? `${Math.round(p.moneyPct)}% of money` : 'money share not captured'}
                />
              );
            })}
            <Text style={styles.source}>
              Action Network consensus, on the {team} side (the over, on the total){asOf(MARKETS.map((m) => publicSide[m]?.snapshotAt ?? null))}.
            </Text>
          </>
        ) : (
          <Text style={styles.muted}>
            {publicCoverage
              ? 'No public splits captured for this game yet.'
              : 'Public ticket and money splits are captured for MLB only today.'}
          </Text>
        )}
      </Card>
    </>
  );
}

function movementLead(team: string, ng: NextGame): string {
  const sp = ng.moves.spreads;
  const ml = ng.moves.h2h;
  const lead = sp && sp.direction !== 'flat' ? sp : ml && ml.direction !== 'flat' ? ml : null;
  if (!lead) return `The number on ${team} hasn’t moved since it opened.`;
  const what = lead.market === 'spreads'
    ? `the spread moved ${formatTeamLine(lead.openLine, 'spreads')} → ${formatTeamLine(lead.nowLine, 'spreads')}`
    : `the moneyline moved ${formatPct(lead.openProb, 0)} → ${formatPct(lead.nowProb, 0)}`;
  return lead.direction === 'toward'
    ? `Money has come in on ${team}: ${what}. You’re buying after the move.`
    : `Money has gone the other way: ${what}. ${team} is cheaper than it opened.`;
}

// Fair-to-fair, not vig-in against fair: at −110 both ways a book's implied
// is 52.4% against a ~50% fair, so a vig-in comparison said "you're paying
// up" on every ordinary line (UX review, 2026-09-20). The band is a display
// heuristic, not a model threshold.
const SHARP_AGREE_PP = 1.0;

function sharpLead(team: string, ng: NextGame): string {
  const s = ng.sharp.h2h ?? ng.sharp.spreads ?? null;
  if (!s || s.fairGapPp == null || !s.book) return `Pinnacle has ${team} priced; your book hasn’t posted the same market yet.`;
  const gap = Math.abs(s.fairGapPp);
  if (gap < SHARP_AGREE_PP) return `${bookName(s.book)} and Pinnacle agree on ${team} once the vig is taken out.`;
  return s.fairGapPp > 0
    ? `${bookName(s.book)} rates ${team} ${gap.toFixed(1)}pp higher than Pinnacle does — the sharp book has this side cheaper.`
    : `${bookName(s.book)} rates ${team} ${gap.toFixed(1)}pp lower than Pinnacle does — the sharp book likes this side more than yours does.`;
}

// Descriptive on purpose: the board one tap back says betting splits are
// context, not an edge, and the repo's public-fade is still a shadow-tracked card
// (docs/mlb_total_public_fade.md). The tooltip carries the interpretation.
function publicLead(team: string, ng: NextGame): string {
  const p = ng.publicSide.h2h ?? ng.publicSide.spreads ?? null;
  if (!p || p.betPct == null) return `Public splits are in for the total only.`;
  const which = ng.publicSide.h2h ? 'moneyline' : 'spread';
  const money = p.moneyPct != null ? ` and ${Math.round(p.moneyPct)}% of the money` : '';
  return `${Math.round(p.betPct)}% of ${which} tickets${money} are on ${team}.`;
}

/** " · as of 4:12 PM ET" from the newest of the stamps, or nothing. */
function asOf(stamps: Array<string | null>): string {
  const known = stamps.filter((s): s is string => !!s).sort();
  if (known.length === 0) return '';
  const t = formatStampET(known[known.length - 1]!);
  return t ? ` · as of ${t}` : '';
}

/** One number per tile: the units, or the record when nothing was priced; the
 *  record and the unpriced count in the caption (UX review). */
function RecordTile({ label, record }: { label: string; record: PickRecord }) {
  const units = record.units;
  const value = units == null ? formatWinLoss(record) : formatSignedUnits(units);
  const caption =
    units == null
      ? record.unpriced > 0 ? `${record.unpriced} unpriced` : undefined
      : `${formatWinLoss(record)}${record.unpriced > 0 ? ` · ${record.unpriced} unpriced` : ''}`;
  return <StatTile label={label} value={value} caption={caption} tint={unitsTint(units)} />;
}

// ── Form ────────────────────────────────────────────────────────────────────

function FormStrip({ games }: { games: FormGame[] }) {
  // Oldest on the left, newest on the right — a strip reads like a timeline.
  const ordered = games.slice().reverse();
  return (
    <View style={styles.formStrip} accessible accessibilityLabel={formSpoken(ordered)}>
      {ordered.map((g) => (
        <View key={g.gameId} style={styles.formCell}>
          <View
            style={[
              styles.formChip,
              g.result === 'W' ? styles.formChipWin : g.result === 'L' ? styles.formChipLoss : styles.formChipTie,
            ]}
          >
            <Text
              style={[
                styles.formLetter,
                g.result === 'W' ? styles.formLetterWin : g.result === 'L' ? styles.formLetterLoss : null,
              ]}
            >
              {g.result}
            </Text>
          </View>
          <Text style={styles.formOpp} numberOfLines={1}>
            {g.isHome ? '' : '@'}{g.opponent}
          </Text>
          <Text style={styles.formScore}>{g.scored}-{g.allowed}</Text>
          {g.ats != null || g.ou != null ? (
            <Text style={styles.formMarks}>
              {g.ats === 'cover' ? '✓' : g.ats === 'loss' ? '✗' : g.ats === 'push' ? '=' : ''}
              {g.ou === 'over' ? ' O' : g.ou === 'under' ? ' U' : g.ou === 'push' ? ' P' : ''}
            </Text>
          ) : null}
        </View>
      ))}
    </View>
  );
}

function formSpoken(games: FormGame[]): string {
  return games
    .map((g) => `${g.result === 'W' ? 'won' : g.result === 'L' ? 'lost' : 'tied'} ${g.scored} to ${g.allowed} ${g.isHome ? 'versus' : 'at'} ${g.opponent}${g.ats ? `, ${g.ats === 'cover' ? 'covered' : g.ats === 'loss' ? 'did not cover' : 'pushed'}` : ''}`)
    .join('; ');
}

function MeetingRow({ game, team }: { game: FormGame; team: string }) {
  const spoken = `${game.date}, ${team} ${game.result === 'W' ? 'won' : game.result === 'L' ? 'lost' : 'tied'} ${game.scored} to ${game.allowed} ${game.isHome ? 'versus' : 'at'} ${game.opponent}`;
  return (
    <View style={styles.meetingRow} accessible accessibilityLabel={spoken}>
      <Text style={styles.meetingDate}>{game.date}</Text>
      <Text style={styles.meetingSide} numberOfLines={1}>
        {game.isHome ? 'vs' : '@'} {game.opponent}
      </Text>
      <Text style={[styles.meetingResult, game.result === 'W' ? styles.win : game.result === 'L' ? styles.loss : null]}>
        {game.result} {game.scored}-{game.allowed}
      </Text>
    </View>
  );
}

// ── Splits ──────────────────────────────────────────────────────────────────

function SplitsTiles({ row, sport }: { row: TeamStatsRow; sport: TeamSport }) {
  const def = (key: keyof TeamStatsRow): TeamStatDef | null =>
    TEAM_STAT_CATALOG.find((s) => s.key === key && s.sports.includes(sport)) ?? null;
  const pct = (key: keyof TeamStatsRow): string => {
    const v = row[key];
    const n = typeof v === 'string' ? Number(v) : v;
    return n == null || !Number.isFinite(n as number) ? '—' : formatPct(n as number, 0);
  };
  const thin = (key: keyof TeamStatsRow): string | null => {
    const d = def(key);
    if (!d || !d.sample) return null;
    const n = sampleFor(row, d);
    return isThinSample(row, d) ? `${n} game${n === 1 ? '' : 's'} · thin` : `${n} games`;
  };
  const restful = def('rest_adv_ats_pct') != null;
  return (
    <>
      <View style={styles.tileRow}>
        <StatTile label="Home" value={`${row.home_w}-${row.home_l}`} caption={`ATS ${pct('ats_home_pct')}`} />
        <StatTile label="Away" value={`${row.away_w}-${row.away_l}`} caption={`ATS ${pct('ats_away_pct')}`} />
        <StatTile label="Over" value={pct('over_pct')} caption={`${row.ou_o}-${row.ou_u}${row.ou_p ? `-${row.ou_p}` : ''}`} />
      </View>
      <View style={styles.tileRow}>
        <StatTile label="ATS as fav" value={pct('fav_ats_pct')} />
        <StatTile label="ATS as dog" value={pct('dog_ats_pct')} />
        <StatTile
          label="ATS overall"
          value={pct('ats_pct')}
          caption={`${row.ats_w}-${row.ats_l}${row.ats_p ? `-${row.ats_p}` : ''}`}
        />
      </View>
      {restful ? (
        <View style={styles.tileRow}>
          <StatTile label="ATS rest edge" value={pct('rest_adv_ats_pct')} caption={thin('rest_adv_ats_pct') ?? undefined} />
          <StatTile label="ATS short rest" value={pct('short_rest_ats_pct')} caption={thin('short_rest_ats_pct') ?? undefined} />
        </View>
      ) : null}
    </>
  );
}

// ── Ranks ───────────────────────────────────────────────────────────────────

function RankRow({
  label,
  value,
  rank,
  of,
  tier,
  hint,
}: {
  label: string;
  value: string;
  rank: number | null;
  of: number;
  tier: Tier;
  hint?: string;
}) {
  const color = tier === 'good' ? colors.gradeGood : tier === 'bad' ? colors.gradeBad : tier === 'mid' ? colors.gradeMid : colors.textPrimary;
  const rankText = rank != null && of > 0 ? `${ordinal(rank)} of ${of}` : of > 0 ? `of ${of}` : '';
  return (
    <View
      style={styles.rankRow}
      accessible
      accessibilityLabel={`${label} ${value}${rank != null ? `, ${ordinal(rank)} of ${of}` : ''}`}
    >
      <View style={styles.rankMain}>
        <Text style={styles.rankLabel}>{label}</Text>
        {hint ? <Text style={styles.rankHint} numberOfLines={2}>{hint}</Text> : null}
      </View>
      <Text style={[styles.rankValue, { color }]}>{value}</Text>
      <Text style={[styles.rankPos, rank != null ? { color } : null]}>{rankText}</Text>
    </View>
  );
}

// ── Shared bits ─────────────────────────────────────────────────────────────

function Card({ children }: { children: React.ReactNode }) {
  return <View style={styles.card}>{children}</View>;
}

function signed(n: number, digits: number): string {
  const r = n.toFixed(digits);
  if (Number(r) === 0) return `0${digits ? `.${'0'.repeat(digits)}` : ''}`;
  return n > 0 ? `+${r}` : `−${Math.abs(n).toFixed(digits)}`;
}

// The grade ramp, not positive/negative: theme.ts measures those at 2.2:1 and
// 3.6:1 on a card, under AA for a 20pt number (UX review).
function unitsTint(units: number | null): string | undefined {
  if (units == null) return undefined;
  const r = Math.round(units * 10) / 10;
  if (r > 0) return colors.gradeGood;
  if (r < 0) return colors.gradeBad;
  return undefined;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { paddingBottom: spacing.xxl },
  header: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.sm },
  teamName: { fontSize: font.size.title2, fontWeight: font.weight.bold, color: colors.textPrimary },
  meta: { fontSize: font.size.footnote, color: colors.textSecondary, marginTop: 2 },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  tileRow: { flexDirection: 'row', gap: spacing.sm, marginHorizontal: spacing.lg, marginBottom: spacing.sm },
  muted: { fontSize: font.size.footnote, color: colors.textSecondary, lineHeight: 18 },
  footnote: { fontSize: font.size.caption, color: colors.textTertiary, paddingHorizontal: spacing.lg, marginTop: 2 },
  // textSecondary inside a card: textTertiary is ~3.4:1 on bgCard at this size (UX_REVIEW §5).
  legend: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: spacing.sm, lineHeight: 16 },
  source: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: spacing.sm, lineHeight: 16 },
  loading: { marginVertical: spacing.xl },
  loadingInline: { marginTop: spacing.sm },
  errorBanner: {
    backgroundColor: colors.avoidSoft,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    borderRadius: radii.sm,
  },
  errorText: { color: colors.avoid, fontSize: font.size.footnote },

  fixtureRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
  fixture: { flexShrink: 1, fontSize: font.size.headline, fontWeight: font.weight.semibold, color: colors.textPrimary },
  fixtureWhen: { fontSize: font.size.footnote, fontWeight: font.weight.regular, color: colors.textSecondary },
  pillRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: spacing.md, gap: spacing.sm },
  pillCol: { flex: 1, alignItems: 'flex-end' },
  pillLabel: {
    alignSelf: 'flex-end',
    fontSize: font.size.micro,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    letterSpacing: 0.3,
    marginBottom: 4,
    textTransform: 'uppercase',
  },

  readTitle: { fontSize: font.size.body, fontWeight: font.weight.semibold, color: colors.textPrimary },
  readLead: { fontSize: font.size.footnote, color: colors.textSecondary, lineHeight: 18, marginTop: 4, marginBottom: spacing.sm },

  formStrip: { flexDirection: 'row', justifyContent: 'space-between', gap: 2 },
  formCell: { flex: 1, alignItems: 'center', minWidth: 0 },
  formChip: {
    width: 26,
    height: 26,
    borderRadius: radii.sm,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.noneSoft,
  },
  // A result is not a side to take: the letter carries the grade ramp on a
  // neutral ground rather than the BET / AVOID tints (UX review).
  formChipWin: { backgroundColor: colors.noneSoft },
  formChipLoss: { backgroundColor: colors.noneSoft },
  formChipTie: { backgroundColor: colors.noneSoft },
  formLetter: { fontSize: font.size.caption, fontWeight: font.weight.bold, color: colors.textSecondary },
  formLetterWin: { color: colors.gradeGood },
  formLetterLoss: { color: colors.gradeBad },
  formOpp: { fontSize: font.size.nano, color: colors.textSecondary, marginTop: 3, maxWidth: 34 },
  formScore: { fontSize: font.size.nano, color: colors.textSecondary, fontVariant: ['tabular-nums'] },
  formMarks: { fontSize: font.size.nano, fontWeight: font.weight.semibold, color: colors.textSecondary, marginTop: 1 },

  meetingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    gap: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  meetingDate: { width: 88, fontSize: font.size.caption, color: colors.textSecondary, fontVariant: ['tabular-nums'] },
  meetingSide: { flex: 1, fontSize: font.size.footnote, color: colors.textPrimary },
  meetingResult: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, color: colors.textPrimary, fontVariant: ['tabular-nums'] },
  win: { color: colors.gradeGood },
  loss: { color: colors.gradeBad },

  rankRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    gap: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  rankMain: { flex: 1, minWidth: 0 },
  rankLabel: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, color: colors.textPrimary },
  rankHint: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: 1, lineHeight: 15 },
  rankValue: { width: 64, textAlign: 'right', fontSize: font.size.footnote, fontWeight: font.weight.bold, fontVariant: ['tabular-nums'] },
  rankPos: { width: 76, textAlign: 'right', fontSize: font.size.caption, color: colors.textSecondary },
});

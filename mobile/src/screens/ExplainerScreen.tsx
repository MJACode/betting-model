import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, font, radii, spacing } from '@/lib/theme';
import { BACKTEST_START, LIVE_RECORD_START } from '@/lib/recordStart';

export function ExplainerScreen() {
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.list}>
        <Text style={styles.title}>How this works</Text>

        <Section heading="What is Edge?">
          <P>
            <Strong>Edge</Strong> is how much better the model thinks a side is
            than DraftKings is pricing it. The math:
          </P>
          <Mono>edge = model_probability − dk_implied_probability</Mono>
          <P>
            DK implied probability is just <Mono>1 / decimal_odds</Mono>.
            Example: DK lists the Yankees at <Mono>-150</Mono>. Decimal odds are{' '}
            <Mono>1.667</Mono>, so DK implies a <Mono>60.0%</Mono> chance the
            Yankees win. If our model says <Mono>72.0%</Mono>, the edge is{' '}
            <Mono>+12.0%</Mono> — meaningful.
          </P>
          <P>
            A positive edge means we think the bet is mispriced in our favor.
            Negative edge means the opposite — that's what triggers an AVOID
            signal (don't bet that side; the other side is overpriced but DK's
            vig usually eats the value).
          </P>
        </Section>

        <Section heading="Which sportsbook the numbers come from">
          <P>
            <Strong>Every signal is priced against DraftKings.</Strong> The model
            probability, the edge, the BET/AVOID call, the recommended stake, and
            every parlay you build all compare against the DraftKings line — that
            is the one book we score, track, and grade our record against.
          </P>
          <P>
            Every pick lists each book's line, <Strong>best price first</Strong>,
            so you can place it wherever pays most. We compare every book we
            price and put the best payout first. You can't change that ordering,
            and the price a pick is measured at is always DraftKings.
          </P>
          <P>
            Book coverage is uneven — DraftKings posts far more prop markets than
            anyone else. Open a pick and check <Strong>All books</Strong> to
            compare every book side by side. You choose the books you bet at in
            Settings → Your sportsbooks, and you can pick as many as you like.
            They set two things: the line the Stats leaderboard prints beside
            each player — the <Strong>best of your books</Strong> on that number,
            badged with the one offering it — and which book the betslip's bet
            button opens. They never change what a pick is measured at, and they
            never limit where you can place: the betslip lists every book we
            price, whether you selected it or not.
          </P>
        </Section>

        <Section heading="Model Probability">
          <P>
            Each market has its own model — separate XGBoost classifier or
            Poisson regressor trained on 2019–2024 historical games. Features
            depend on the market:
          </P>
          <Bullet>
            Game models use starter ERA / K9 / BB9, bullpen workload, team wOBA
            / wRC+, weather (wind out, dome, temp), and the closing DK line.
          </Bullet>
          <Bullet>
            Pitcher prop models use the starter's rolling K rate, IP, Statcast
            whiff% and xERA, opponent K%, and umpire tendency.
          </Bullet>
          <Bullet>
            Batter prop models use the hitter's recent stat avgs, batting order
            slot, opposing pitcher's HR/9 or K%, park factor, and platoon
            advantage.
          </Bullet>
          <P>
            Raw XGBoost outputs are overconfident, so every model passes its
            scores through <Strong>Platt scaling</Strong> — a sigmoid
            calibration fitted on cross-validation folds. The number you see
            (e.g. <Mono>67.3%</Mono>) is the calibrated probability — what the
            true win rate should be for a bin of picks at that prediction
            level.
          </P>
        </Section>

        <Section heading="BET / AVOID / NONE">
          <Bullet>
            <Strong>BET</Strong> — model probability AND edge both clear that
            model's threshold. Tenth-Kelly bet size attached. These are the
            picks worth backing.
          </Bullet>
          <Bullet>
            <Strong>AVOID</Strong> — model strongly disagrees with DK (edge ≤
            -3%). Informational; do NOT bet the other side blindly.
          </Bullet>
          <Bullet>
            <Strong>NONE</Strong> — edge is in the dead zone (between -3% and
            +3%). Model and DK essentially agree; no advantage either way.
          </Bullet>
          <P>
            The Signals tab applies the per-model action filter (e.g. moneyline
            needs ≥72% model prob and ≥12% edge). That's the same filter the
            Streamlit dashboard and Claude mobile use — single source of truth
            mirrored from <Mono>config.py</Mono>.
          </P>
        </Section>

        <Section heading="Tenth-Kelly bet sizing">
          <P>
            Full Kelly is the math-optimal staking fraction for a known edge.
            It's also volatile — drawdowns are brutal. We use{' '}
            <Strong>10% of full Kelly</Strong>:
          </P>
          <Mono>{`fraction = 0.10 × (model_prob − implied_prob) / (1 − implied_prob)`}</Mono>
          <Mono>bet = min(fraction × bankroll, 5% × bankroll)</Mono>
          <P>
            The 5% cap keeps any single bet survivable. Tenth-Kelly typically
            lands in the 2-4% range, letting edge differences differentiate
            sizes (vs quarter-Kelly which always hit the cap and produced flat
            bets). Change your bankroll in Settings — bet sizes recompute live.
          </P>
        </Section>

        <Section heading="Why HR picks don't show edge">
          <P>
            DraftKings juices the HR Over 0.5 market hard — typical prices are
            <Mono> +250 to +500</Mono>, implying <Mono>16-29%</Mono>. Our
            model HR probabilities top out around <Mono>25%</Mono>. Forcing an
            edge filter would mean we never fire HR picks even when the model
            is confident, so HR signals on model probability alone (≥20%) and
            ignore edge. Bet sizing is informational only on those.
          </P>
        </Section>

        <Section heading="When the money piles on one side">
          <P>
            On full-game picks we show the <Strong>public betting split</Strong>{' '}
            (from Action Network) — the share of bets and money on the side we
            picked. It's worth understanding what one-sided action means.
          </P>
          <P>
            Sportsbooks don't just post their honest opinion — they shade the
            line to balance their risk. When the crowd piles its money onto one
            side, the book moves that number to make the popular side more
            expensive. So <Strong>heavy public money usually means that side is
            overpriced, and the value sits on the other side</Strong>. The
            classic sharp move is to fade the public — bet against where all the
            money is.
          </P>
          <Bullet>
            <Strong>Green chip = good.</Strong> When only a small share of bets
            is on our pick, the crowd's money is on the <Strong>other</Strong>{' '}
            side. We're already on the contrarian, better-priced side — the
            chip turns green to confirm it.
          </Bullet>
          <Bullet>
            <Strong>Crowded = caution.</Strong> When the public is heavy on our
            own pick, that line may be inflated. We still show the pick if the
            model's edge clears the bar, but the public agreement is a yellow
            flag — watch for the line moving against you.
          </Bullet>
          <P>
            One more tell: compare <Strong>money %</Strong> to{' '}
            <Strong>bets %</Strong>. If money share runs well ahead of ticket
            share on a side, a few bigger (often sharper) bettors are loading
            it — a stronger signal than ticket count alone.
          </P>
        </Section>

        <Section heading="Sharp Score — one number for conviction">
          <P>
            Every BET pick carries a <Strong>Sharp Score</Strong> from 0 to 100 (the
            ⚡ chip). It blends three things we already track into a single read on
            how strong the bet is — green is high, amber is medium, grey is a lean.
          </P>
          <Bullet>
            <Strong>Edge strength (40 pts).</Strong> How far the pick clears that
            model's own bet threshold — a pick well past the bar scores higher than
            one that just sneaks over.
          </Bullet>
          <Bullet>
            <Strong>Model CLV pedigree (40 pts).</Strong> How often this specific
            model has <Strong>beaten the closing line</Strong> on its settled bets.
            CLV is the best evidence a model is genuinely sharp rather than lucky, so
            a model with a strong track record lifts every one of its picks. New
            models score neutral until they've proven it.
          </Bullet>
          <Bullet>
            <Strong>Contrarian / public (20 pts).</Strong> Higher when the public is
            light on our side (we hold the better-priced, contrarian side), lower when
            the crowd is piled onto our pick.
          </Bullet>
          <P>
            Open any pick to see the full breakdown. The Sharp Score is a guide, not a
            guarantee — it ranks conviction across today's board; it doesn't change the
            odds or the outcome.
          </P>
        </Section>

        <Section heading="Why picks can change between refreshes">
          <P>
            The pipeline scores at 6am, then re-scores hourly through 6pm
            and every 10 minutes from 6pm to 11pm ET. Each
            refresh deletes pre-game picks and re-scores from current DK
            prices. A BET at noon can become AVOID at 6pm if the line moved
            against us — honor the latest signal, not the morning one. Once a
            game starts, that pick is locked.
          </P>
          <P>
            We’re also running an experiment behind the scenes: we save the{' '}
            <Strong>first</Strong> time a game becomes a BET (the “opening
            signal”) and track that record separately, alongside how the line
            moves afterward. The picks you act on are still the live ones above —
            see Track Record → “Opening vs Live” for that comparison.
          </P>
        </Section>

        <Section heading="Line movement — your pick stays locked">
          <P>
            Once a pick is scored, it's <Strong>locked at the price and line we
            scored it at</Strong> — that's the bet of record, and it's what
            settles. The Line Movement card on a pick doesn't change any of that.
            It just shows how DraftKings has moved the market <Strong>since</Strong>{' '}
            we locked in, so you can see whether you'd be getting a better or worse
            number if you bet now.
          </P>
          <Bullet>
            <Strong>🟢 Moved in your favor.</Strong> DK's price drifted toward our
            side by at least <Strong>1 percentage point</Strong> of implied
            probability — you locked the better number, the market is catching up.
          </Bullet>
          <Bullet>
            <Strong>🔴 Steam against you.</Strong> The price moved against our side
            by <Strong>3+ percentage points</Strong> of implied probability (e.g.{' '}
            <Mono>-110 → -125</Mono>). The market disagrees more than it did at
            scoring — a yellow flag if you haven't bet yet.
          </Bullet>
          <Bullet>
            <Strong>🔴 Line moved.</Strong> For totals, spreads, and player props,
            the number itself moved against your side by <Strong>half a point or
            more</Strong> (e.g. an Over 8.5 that's now 9.0). That's a different
            proposition than the one we scored.
          </Bullet>
          <P>
            No chip means the line is basically where we scored it — nothing moved
            enough to mention. We only flag moves past those thresholds so small
            wiggle doesn't cry wolf. None of this re-grades the pick; it's a
            heads-up on the price you'd get today.
          </P>
        </Section>

        <Section heading="Performance tab — tracked by you">
          <P>
            The Performance tab is <Strong>your own record</Strong>. Use{' '}
            <Strong>Add a bet</Strong> to log a wager — any book, any sport,
            including DFS. It's stored on your device and counts toward your
            P&L, so nothing is missing from your record.
          </P>
          <P>
            Below that, <Strong>Tracked picks</Strong> grades the picks you tap
            Track on. Those score automatically from our settled results at the
            stake basis you choose ($100 flat, Kelly, or a custom amount), so
            you can see how the model's calls would have done for you without
            logging anything.
          </P>
          <P>
            <Strong>Automatic sportsbook sync is coming soon.</Strong> When it
            ships, your wagers and settlements from a linked book will flow in
            on their own. It won't cover every book — some require MFA and DFS
            apps often don't sync — so manual logging stays the reliable way to
            keep your record complete.
          </P>
        </Section>

        <Section heading="Why we're different — calibration, not hype">
          <P>
            Most picks services sell <Strong>accuracy</Strong> ("we hit 80%!").
            We optimize for <Strong>calibration</Strong> instead — making a "65%"
            actually win about 65% of the time. Research backs this: a 2024
            University of Bath study found calibration-optimized betting models
            massively outperformed accuracy-optimized ones over a full season.
          </P>
          <P>
            That's why every model is Platt-scaled and gated at ≤5% calibration
            error before it can go live, and why we publish a full track record
            — wins, losses, and closing-line value — instead of a hero win-rate.
            If a model isn't beating the closing line over a real sample, we'd
            rather show you that than hide it.
          </P>
        </Section>

        <Section heading="Discipline is the edge">
          <P>
            The math only works if you survive the variance. A few habits do more
            for your bottom line than any single pick:
          </P>
          <Bullet>
            <Strong>No-pick days are normal.</Strong> When nothing clears the bar,
            we show nothing. Forcing action on coin-flip games is how bankrolls
            bleed out.
          </Bullet>
          <Bullet>
            <Strong>Size with fractional Kelly.</Strong> Bets default to a small
            fraction of full Kelly so one cold stretch can't wipe you out. Set a
            bankroll you can afford to lose in Settings.
          </Bullet>
          <Bullet>
            <Strong>Shop for the best price.</Strong> Getting −105 instead of −110
            is free money over time. We flag the better number when we have it.
          </Bullet>
          <Bullet>
            <Strong>Be wary of parlays.</Strong> Same-game parlays carry 15–25%
            built-in hold vs ~5% on a straight bet — the books push them for a
            reason.
          </Bullet>
          <Bullet>
            <Strong>Never chase.</Strong> Down days happen even when every bet was
            +EV. Bet to be around next season, not to get even tonight.
          </Bullet>
        </Section>

        <Section heading="Models tab — Custom filters">
          <P>
            Build your own pick filter from any combination of model + min
            probability + min edge. The app backtests each filter against
            every scored pick since {BACKTEST_START} — the full graded history, which is longer than the published record — and shows
            win rate and flat ROI.
          </P>
          <P>
            Custom models are saved on this device. They don't change which
            picks the pipeline scores — they're a way to slice the same pick
            history through your own conviction rules.
          </P>
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.heading}>{heading}</Text>
      {children}
    </View>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return <Text style={styles.p}>{children}</Text>;
}

function Strong({ children }: { children: React.ReactNode }) {
  return <Text style={styles.strong}>{children}</Text>;
}

function Mono({ children }: { children: React.ReactNode }) {
  return <Text style={styles.mono}>{children}</Text>;
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <View style={styles.bullet}>
      <Text style={styles.bulletDot}>•</Text>
      <Text style={styles.bulletText}>{children}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  list: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xl,
  },
  title: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.lg,
  },
  section: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  heading: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  p: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    lineHeight: 22,
    marginBottom: spacing.sm,
  },
  strong: {
    fontWeight: font.weight.semibold,
  },
  mono: {
    fontFamily: 'Courier',
    backgroundColor: colors.bg,
    paddingHorizontal: 4,
    fontSize: 13,
    color: colors.textPrimary,
  },
  bullet: {
    flexDirection: 'row',
    marginBottom: spacing.sm,
    paddingLeft: 4,
  },
  bulletDot: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    marginRight: spacing.sm,
    lineHeight: 22,
  },
  bulletText: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
    lineHeight: 22,
  },
});

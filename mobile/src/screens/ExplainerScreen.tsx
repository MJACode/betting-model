import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, font, radii, spacing } from '@/lib/theme';

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

        <Section heading="Why picks can change between refreshes">
          <P>
            The pipeline re-scores every hour from 8am to 11pm ET. Each
            refresh deletes pre-game picks and re-scores from current DK
            prices. A BET at noon can become AVOID at 6pm if the line moved
            against us — honor the latest signal, not the morning one. Once a
            game starts, that pick is locked.
          </P>
        </Section>

        <Section heading="Performance tab — Synced from your sportsbook">
          <P>
            The Performance tab reflects your <Strong>real wagers from your
            connected sportsbook</Strong> — not picks you mark by hand. Connect
            DraftKings from the Performance tab or Settings to get started.
          </P>
          <P>
            Once bet-history sync ships, your DK wagers, settlements, and daily
            P&L flow in automatically and backfill from your connect date. No
            manual tracking required.
          </P>
        </Section>

        <Section heading="Models tab — Custom filters">
          <P>
            Build your own pick filter from any combination of model + min
            probability + min edge. The app backtests each filter against
            every settled pick since paper trading started (2026-04-14) and
            shows live win rate and flat ROI.
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

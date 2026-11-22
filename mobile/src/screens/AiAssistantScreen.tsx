import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { useAiAssistant } from '@/hooks/useAiAssistant';
import {
  AI_FOOTNOTE,
  MCP_SERVER_ADDRESS,
  MCP_SERVER_URL,
  SETUP_GUIDES,
  TRY_ASKING,
  aiAssistantMode,
  connectedAssistants,
  connectedSinceLine,
  maxAssistants,
  questionsLeftLine,
  questionsMeter,
  perDayLabel,
  sharedLimitLine,
  shortDateET,
  type AssistantId,
  type ConnectedAssistant,
  type McpStatus,
} from '@/lib/aiAssistant';
import { errorText } from '@/lib/errors';
import { colors, font, radii, spacing, opacity, card, sectionHeaderText } from '@/lib/theme';
import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { SegmentTabs } from '@/components/GroupTabs';
import { ErrorState } from '@/components/ErrorState';
import { showToast } from '@/components/Toast';

/**
 * Settings › AI Assistant (mockups approved by Matt, 2026-11-21).
 *
 * One screen, six states from `aiAssistantMode`: trial (unlocks on the trial's
 * end date, no purchase button), preview (App Review: the steps, no address),
 * suspended, setup, connected, and hidden for anyone else. The server enforces
 * every rule; this screen only reports it.
 *
 * Connected (Matt, 2026-11-22): up to three assistants, one row each with its
 * own Disconnect, and ONE questions meter above them, because the daily limit
 * is shared.
 *
 * The address is shared through the system share sheet, which includes Copy:
 * the app has no clipboard module, and adding one would need a store build.
 */
export function AiAssistantScreen() {
  const { status, loading, loaded, error, refresh, disconnect } = useAiAssistant();
  const mode = aiAssistantMode(status);

  if (!loaded && !status) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <View style={styles.center}>
          <ActivityIndicator color={colors.textTertiary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={loading && loaded} onRefresh={() => void refresh()} />
        }
      >
        {mode !== 'connected' ? (
          <Text style={styles.lede}>
            Ask Claude, ChatGPT or Grok about the numbers in Stats: hit rates, recent games, leaders
            and the best price. Read-only, for your own use.
          </Text>
        ) : null}

        {error && !status ? (
          <ErrorState what="AI Assistant" error={error} onRetry={() => void refresh()} retrying={loading} />
        ) : null}

        {mode === 'hidden' && status ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>For paying members</Text>
            <Text style={styles.body}>
              Connecting an AI assistant is included with a paid Signal Base membership.
            </Text>
          </View>
        ) : null}

        {mode === 'trial' && status ? <TrialCard status={status} /> : null}

        {mode === 'suspended' ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Paused on this account</Text>
            <Text style={styles.body}>
              AI Assistant access is paused. Contact Signal Base support from Settings › Legal &
              support.
            </Text>
          </View>
        ) : null}

        {mode === 'connected' && status ? (
          <ConnectedCard status={status} onDisconnect={disconnect} />
        ) : null}

        {mode === 'setup' && status ? <AddressCard status={status} /> : null}

        {mode === 'preview' ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Preview</Text>
            <Text style={styles.body}>
              This account can see how AI Assistant works. Connecting an assistant is for paying
              members, so the server address is not shown here.
            </Text>
          </View>
        ) : null}

        {mode === 'setup' || mode === 'connected' || mode === 'preview' ? (
          <>
            <Guides />
            <TryAsking />
          </>
        ) : null}

        {mode === 'setup' ? (
          <Text style={styles.footnote}>
            Connected assistants: none yet. Once you tap Allow in your assistant, pull down here to
            see it, with today’s count and a Disconnect button.
          </Text>
        ) : null}

        {mode !== 'hidden' ? <Text style={styles.footnote}>{AI_FOOTNOTE}</Text> : null}
        <BetslipBarSpacer />
      </ScrollView>
    </SafeAreaView>
  );
}

function shareAddress() {
  void Share.share({ message: MCP_SERVER_URL }).catch(() => {});
}

function AddressCard({ status, compact = false }: { status: McpStatus; compact?: boolean }) {
  const limit = status.unlimited
    ? sharedLimitLine(status)
    : `${sharedLimitLine(status)} · resets at midnight ET`;
  return (
    <View style={styles.card}>
      <Text style={styles.heading}>{compact ? 'Server address' : 'Your server address'}</Text>
      <View style={styles.addressRow}>
        <Text style={styles.address} selectable accessibilityLabel={`Server address, ${MCP_SERVER_ADDRESS}`}>
          {MCP_SERVER_ADDRESS}
        </Text>
        <Pressable
          onPress={shareAddress}
          accessibilityRole="button"
          accessibilityLabel="Copy server address"
          accessibilityHint="Opens the share sheet, where you can copy it"
          style={({ pressed }) => [styles.shareButton, pressed && styles.pressed]}
        >
          <Ionicons name="copy-outline" size={16} color={colors.textInverse} />
          <Text style={styles.shareText}>Copy</Text>
        </Pressable>
      </View>
      {compact ? null : <Text style={styles.small}>{limit}</Text>}
    </View>
  );
}

function TrialCard({ status }: { status: McpStatus }) {
  const day = shortDateET(status.trial_converts_at);
  return (
    <>
      <View style={styles.chromeCard}>
        <View style={styles.chromeIcon}>
          <Ionicons name="lock-closed" size={22} color={colors.brand} />
        </View>
        <Text style={styles.chromeTitle}>Unlocks when your paid subscription starts</Text>
        <Text style={styles.chromeBody}>
          Your free trial includes everything in the app. Connecting Claude, ChatGPT or Grok to your
          Stats is for paying members, and opens automatically
          {day ? ` on ${day}, ` : ' '}when your trial becomes a subscription.
        </Text>
      </View>
      <View style={styles.card}>
        <Text style={styles.heading}>What you’ll be able to do</Text>
        {[
          'Ask about hit rates, recent games, leaders and the best price',
          'Get the best price across the major sportsbooks',
          `${perDayLabel(status)}, from Claude, ChatGPT or Grok`,
        ].map((p) => (
          <View key={p} style={styles.checkRow}>
            <Ionicons name="checkmark" size={18} color={colors.tint} />
            <Text style={styles.checkText}>{p}</Text>
          </View>
        ))}
      </View>
    </>
  );
}

function ConnectedCard({
  status,
  onDisconnect,
}: {
  status: McpStatus;
  onDisconnect: (assistant: string | null) => Promise<void>;
}) {
  const now = new Date();
  const meter = questionsMeter(status);
  const assistants = connectedAssistants(status);
  const max = maxAssistants(status);
  const room = max - assistants.length;
  return (
    <>
      <View style={styles.card}>
        {meter ? (
          <View style={styles.meterWrap}>
            <View style={styles.meterHead}>
              <Text style={styles.body}>Questions today</Text>
              <Text style={styles.meterCount}>{`${meter.used} of ${meter.total} used`}</Text>
            </View>
            <View
              style={styles.meterTrack}
              accessible
              accessibilityRole="progressbar"
              accessibilityLabel={`${meter.used} of ${meter.total} questions used today, shared by your assistants`}
              accessibilityValue={{ min: 0, max: meter.total, now: meter.used }}
            >
              <View style={[styles.meterFill, { width: `${(meter.used / meter.total) * 100}%` }]} />
            </View>
            <Text style={styles.small}>{questionsLeftLine(status, now)}</Text>
            {assistants.length > 1 ? (
              <Text style={styles.small}>Shared by every assistant you connect.</Text>
            ) : null}
          </View>
        ) : (
          <View style={styles.meterHead}>
            <Text style={styles.body}>Questions today</Text>
            <View style={styles.founderPill}>
              <Text style={styles.founderText}>Founder · unlimited</Text>
            </View>
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Text style={[styles.heading, styles.headingGutter]}>
          {`Connected assistants · ${assistants.length} of ${max}`}
        </Text>
        <View style={[styles.card, styles.listCard]}>
          {assistants.map((a, i) => (
            <AssistantRow
              key={a.assistant ?? 'all'}
              item={a}
              first={i === 0}
              now={now}
              onDisconnect={onDisconnect}
            />
          ))}
        </View>
      </View>

      <AddressCard status={status} compact />
      <Text style={styles.footnote}>
        {room > 0
          ? `You can connect ${room === 1 ? 'one more assistant' : `${room} more assistants`}: follow its steps below. Reconnecting the same assistant doesn’t use a place.`
          : `All ${max} places are in use. Disconnect one to connect a different assistant.`}
      </Text>
    </>
  );
}

function AssistantRow({
  item,
  first,
  now,
  onDisconnect,
}: {
  item: ConnectedAssistant;
  first: boolean;
  now: Date;
  onDisconnect: (assistant: string | null) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const { name } = item;
  const count =
    item.questions_today === null
      ? null
      : `${item.questions_today} question${item.questions_today === 1 ? '' : 's'} today`;
  const confirm = () => {
    Alert.alert(
      `Disconnect ${name}?`,
      `${name} stops answering from Signal Base right away. Your other assistants keep working. To use ${name} again, remove Signal Base from its connectors and add it back.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Disconnect',
          style: 'destructive',
          onPress: () => {
            setBusy(true);
            onDisconnect(item.assistant)
              .then(() => showToast(`${name} disconnected`))
              .catch((e: unknown) => Alert.alert('Couldn’t disconnect', errorText(e)))
              .finally(() => setBusy(false));
          },
        },
      ],
    );
  };
  return (
    <View style={[styles.assistantRow, !first && styles.rowDivider]}>
      <View style={styles.dot} />
      <View style={{ flex: 1 }}>
        <Text style={styles.cardTitle}>{name}</Text>
        <Text style={styles.small}>{connectedSinceLine(item, now)}</Text>
        {count ? <Text style={styles.small}>{count}</Text> : null}
      </View>
      <Pressable
        onPress={confirm}
        disabled={busy}
        accessibilityRole="button"
        accessibilityLabel={`Disconnect ${name}`}
        accessibilityState={{ disabled: busy, busy }}
        hitSlop={8}
        style={({ pressed }) => [styles.disconnectButton, pressed && styles.pressed]}
      >
        {busy ? (
          <ActivityIndicator color={colors.avoidInk} />
        ) : (
          <Text style={styles.disconnectText}>Disconnect</Text>
        )}
      </Pressable>
    </View>
  );
}

function Guides() {
  const [tab, setTab] = useState<AssistantId>('claude');
  const guide = SETUP_GUIDES.find((g) => g.id === tab) ?? SETUP_GUIDES[0];
  return (
    <View style={styles.section}>
      <Text style={[styles.heading, styles.headingGutter]}>Choose your assistant</Text>
      <SegmentTabs
        items={SETUP_GUIDES.map((g) => g.id)}
        active={tab}
        onChange={setTab}
        labelFor={(id) => SETUP_GUIDES.find((g) => g.id === id)?.name ?? id}
        accessibilityLabelFor={(id) => `${SETUP_GUIDES.find((g) => g.id === id)?.name ?? id} setup steps`}
        fit
      />
      <View style={styles.card}>
        {guide.steps.map((s, i) => (
          <View key={s} style={styles.stepRow}>
            <View style={styles.stepNum}>
              <Text style={styles.stepNumText} maxFontSizeMultiplier={1.5}>{i + 1}</Text>
            </View>
            <Text style={styles.stepText}>{s}</Text>
          </View>
        ))}
        <Text style={styles.small}>{guide.note}</Text>
      </View>
    </View>
  );
}

function TryAsking() {
  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Try asking</Text>
      {TRY_ASKING.map((q) => (
        <Text key={q} style={styles.quote}>{`“${q}”`}</Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.xl, gap: spacing.md },
  lede: {
    fontFamily: font.family,
    fontSize: font.size.body,
    lineHeight: 21,
    color: colors.textSecondary,
  },
  section: { gap: spacing.sm },
  card: { ...card, gap: spacing.md },
  cardTitle: {
    fontFamily: font.family,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  heading: { ...sectionHeaderText },
  headingGutter: { paddingHorizontal: spacing.xs },
  body: { fontFamily: font.family, fontSize: font.size.body, lineHeight: 21, color: colors.textPrimary },
  small: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    lineHeight: 18,
    color: colors.textTertiary,
  },
  footnote: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    lineHeight: 18,
    color: colors.textTertiary,
    paddingHorizontal: spacing.xs,
  },
  addressRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  address: {
    flex: 1,
    fontFamily: font.mono,
    fontSize: font.size.body,
    color: colors.textPrimary,
    backgroundColor: colors.bg,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    overflow: 'hidden',
  },
  shareButton: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.pill,
    backgroundColor: colors.tint,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  shareText: {
    fontFamily: font.family,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  pressed: { opacity: opacity.pressed },
  chromeCard: {
    backgroundColor: colors.chromeSurface,
    borderRadius: radii.lg,
    padding: spacing.xl,
    gap: spacing.md,
  },
  chromeIcon: {
    width: 48,
    height: 48,
    borderRadius: radii.md,
    backgroundColor: colors.chromeSurfaceRaised,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chromeTitle: {
    fontFamily: font.family,
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.onChrome,
  },
  chromeBody: {
    fontFamily: font.family,
    fontSize: font.size.body,
    lineHeight: 22,
    color: colors.onChromeSecondary,
  },
  checkRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'flex-start' },
  checkText: { flex: 1, fontFamily: font.family, fontSize: font.size.body, lineHeight: 21, color: colors.textPrimary },
  listCard: { paddingVertical: 0, gap: 0 },
  assistantRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
  },
  rowDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.separator },
  disconnectButton: {
    minHeight: 44,
    minWidth: 44,
    paddingHorizontal: spacing.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  disconnectText: {
    fontFamily: font.family,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.avoidInk,
  },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.bet },
  meterWrap: { gap: spacing.sm },
  meterHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  meterCount: {
    fontFamily: font.family,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  meterTrack: { height: 8, borderRadius: 4, backgroundColor: colors.noneSoft, overflow: 'hidden' },
  meterFill: { height: 8, backgroundColor: colors.tint },
  founderPill: {
    backgroundColor: colors.chromeSurface,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  founderText: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.brand,
  },
  stepRow: { flexDirection: 'row', gap: spacing.md, alignItems: 'flex-start' },
  stepNum: {
    minWidth: 24,
    minHeight: 24,
    paddingHorizontal: spacing.xs,
    borderRadius: radii.pill,
    backgroundColor: colors.chromeSurface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumText: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.onChrome,
  },
  stepText: { flex: 1, fontFamily: font.family, fontSize: font.size.body, lineHeight: 21, color: colors.textPrimary },
  quote: { fontFamily: font.family, fontSize: font.size.body, lineHeight: 21, color: colors.textPrimary },
});

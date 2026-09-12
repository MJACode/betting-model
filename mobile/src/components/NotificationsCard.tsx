import { Ionicons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { ActivityIndicator, Linking, Pressable, StyleSheet, Switch, Text, View } from 'react-native';

import { usePushOptIn } from '@/hooks/usePushOptIn';
import { registerForPush, usePushState } from '@/hooks/usePushNotifications';
import { colors, font, radii, spacing } from '@/lib/theme';
import { sendTestPush, type TestPushResult } from '@/lib/pushTest';

/**
 * The Settings → Alerts card.
 *
 * WHAT CHANGED AND WHY. This was a switch and one line of copy. The switch
 * wrote an AsyncStorage boolean; registration failures were caught into a
 * `console.warn`; and there was no way, from the phone, to tell a working
 * setup from a broken one. On 2026-09-12 the system had 1,736 ledgered push
 * events and zero registered devices, and this card would have looked
 * identical either way.
 *
 * Three things fix that, in the order a person needs them:
 *   1. The switch still records INTENT, and a separate status row reports
 *      REALITY. They are different questions and were being answered by one
 *      control. The switch deliberately does NOT snap back on failure —
 *      reverting it would discard the setting AND the explanation, leaving
 *      the reader exactly where the old version did.
 *   2. A failure says which of the five reasons it was, what to do, and keeps
 *      the raw error to hand.
 *   3. "Send a test notification" closes the loop without waiting for a slate.
 */
export function NotificationsCard(): React.ReactElement {
  const { enabled, setOptIn } = usePushOptIn();
  const { status, token, diagnosis, registeredAt } = usePushState();
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestPushResult | null>(null);
  const [showDetail, setShowDetail] = useState(false);

  const onTest = async () => {
    if (!token) return;
    setTesting(true);
    setTestResult(null);
    const result = await sendTestPush(token);
    setTestResult(result);
    setTesting(false);
  };

  const onToggle = (next: boolean) => {
    setTestResult(null);
    setShowDetail(false);
    setOptIn(next);
  };

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.cardLabel}>Notifications</Text>
        <Switch value={enabled} onValueChange={onToggle} />
      </View>

      <Text style={styles.sub}>
        New BET signals, big line moves on bets you track, and live in-play signals.
      </Text>

      {enabled && status === 'registering' ? (
        <View style={styles.statusRow}>
          <ActivityIndicator size="small" color={colors.textTertiary} />
          <Text style={styles.statusText}>Registering this device…</Text>
        </View>
      ) : null}

      {enabled && status === 'registered' ? (
        <>
          <View style={styles.statusRow}>
            <Ionicons name="checkmark-circle" size={16} color={colors.bet} />
            <Text style={styles.statusText}>
              This device is registered{registeredAt ? ` · ${timeLabel(registeredAt)}` : ''}
            </Text>
          </View>

          <Pressable
            onPress={onTest}
            disabled={testing}
            accessibilityRole="button"
            accessibilityLabel="Send a test notification to this device"
            style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
          >
            {testing ? (
              <ActivityIndicator size="small" color={colors.tint} />
            ) : (
              <Ionicons name="paper-plane-outline" size={15} color={colors.tint} />
            )}
            <Text style={styles.buttonText}>
              {testing ? 'Sending…' : 'Send a test notification'}
            </Text>
          </Pressable>

          {testResult ? (
            testResult.ok ? (
              <Text style={styles.okText}>
                Sent. It should arrive within a few seconds — if nothing appears, notifications are
                being delivered but not shown, which is an iOS Settings question.
              </Text>
            ) : (
              <Text style={styles.errText}>
                {testResult.diagnosis?.title}. {testResult.diagnosis?.detail}
              </Text>
            )
          ) : null}
        </>
      ) : null}

      {/* NOT gated on `enabled`: turning notifications OFF can fail too (the
          row write is a network call), and gating this on the toggle would
          hide the one error the reader has no other way to learn about. */}
      {status === 'failed' && diagnosis ? (
        <View style={styles.errorBox}>
          <View style={styles.statusRow}>
            <Ionicons name="alert-circle" size={16} color={colors.avoid} />
            <Text style={styles.errTitle}>{diagnosis.title}</Text>
          </View>
          <Text style={styles.errAdvice}>{diagnosis.advice}</Text>

          <View style={styles.actions}>
            {diagnosis.retryable ? (
              <Pressable
                onPress={() => registerForPush()}
                accessibilityRole="button"
                style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
              >
                <Ionicons name="refresh" size={15} color={colors.tint} />
                <Text style={styles.buttonText}>Try again</Text>
              </Pressable>
            ) : null}
            {diagnosis.opensSettings ? (
              <Pressable
                onPress={() => void Linking.openSettings()}
                accessibilityRole="button"
                style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
              >
                <Ionicons name="settings-outline" size={15} color={colors.tint} />
                <Text style={styles.buttonText}>Open iOS Settings</Text>
              </Pressable>
            ) : null}
          </View>

          {/* The raw error, one tap away. Collapsed because it is for a bug
              report rather than for the reader, and shown verbatim because a
              message this code did not recognise is exactly the one worth
              reading unedited. */}
          <Pressable onPress={() => setShowDetail((v) => !v)} accessibilityRole="button">
            <Text style={styles.detailToggle}>
              {showDetail ? 'Hide details' : 'Show details'}
            </Text>
          </Pressable>
          {showDetail ? <Text style={styles.detailText}>{diagnosis.detail}</Text> : null}
        </View>
      ) : null}
    </View>
  );
}

/** A short local time, for "registered at". Date-less on purpose: the row is
 *  about now, and a full timestamp reads as data the reader must interpret. */
function timeLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  cardLabel: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  sub: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    marginTop: spacing.xs,
    lineHeight: 18,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  statusText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    alignSelf: 'flex-start',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radii.sm,
    backgroundColor: colors.bg,
    marginTop: spacing.md,
    // HIG's 44pt minimum target: the row is 15pt text plus 8pt of padding
    // either side, so the height is set rather than left to the content.
    minHeight: 44,
  },
  buttonPressed: {
    opacity: 0.6,
  },
  buttonText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  okText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: spacing.sm,
    lineHeight: 18,
  },
  errText: {
    fontSize: font.size.footnote,
    color: colors.avoid,
    marginTop: spacing.sm,
    lineHeight: 18,
  },
  errorBox: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  errTitle: {
    flex: 1,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  errAdvice: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    lineHeight: 18,
  },
  detailToggle: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.tint,
    marginTop: spacing.md,
  },
  detailText: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.xs,
    lineHeight: 16,
  },
});

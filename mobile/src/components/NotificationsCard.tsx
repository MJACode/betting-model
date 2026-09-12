import { Ionicons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { ActivityIndicator, Linking, Pressable, StyleSheet, Switch, Text, View } from 'react-native';

import { usePushOptIn } from '@/hooks/usePushOptIn';
import {
  registerForPush,
  unregisterForPush,
  usePushState,
} from '@/hooks/usePushNotifications';
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
 *   1. The switch records INTENT, and a separate status block reports REALITY.
 *      They are different questions and were being answered by one control.
 *      The switch deliberately does NOT snap back on failure: it is the only
 *      part that survives a relaunch, so reverting it would discard the
 *      setting AND the explanation and silently re-run the failing
 *      registration next launch. Spotify and Google Drive both do the same —
 *      toggle left where the user put it, reality stated above it.
 *   2. A failure says which reason it was, what to do, and keeps the raw error
 *      to hand.
 *   3. "Send a test notification" closes the loop without waiting for a slate.
 *
 * REALITY IS RENDERED ABOVE THE FEATURE COPY. Reading order used to be
 * title → "New BET signals, big line moves…" → "actually, it is broken", so a
 * reader scanning Settings met a promise and an ON switch and stopped. The
 * failure block sits directly under the header now, in a tinted container
 * rather than behind a hairline, because it is the card's headline when it is
 * present and not a footnote to it (UX review, 2026-09-12).
 */
export function NotificationsCard(): React.ReactElement {
  const { enabled, setOptIn } = usePushOptIn();
  const { status, token, diagnosis, registeredAt } = usePushState();
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestPushResult | null>(null);
  const [testedAt, setTestedAt] = useState<string | null>(null);
  // null = "the reader has not chosen", so the default can depend on the
  // diagnosis without an effect that fights their tap.
  const [detailOverride, setDetailOverride] = useState<boolean | null>(null);

  // 'unknown' is the one bucket whose raw text IS the answer — the advice says
  // so — so it opens expanded. The classified five stay collapsed: there, the
  // detail is for a bug report, not for the reader.
  const showDetail = detailOverride ?? diagnosis?.reason === 'unknown';

  const onTest = async () => {
    if (!token) return;
    setTesting(true);
    setTestResult(null);
    const result = await sendTestPush(token);
    setTestResult(result);
    setTestedAt(new Date().toISOString());
    setTesting(false);
  };

  const onToggle = (next: boolean) => {
    setTestResult(null);
    setTestedAt(null);
    setDetailOverride(null);
    setOptIn(next);
  };

  // Retry the direction the reader actually wants. A failed opt-OUT retried by
  // registering would re-enable the very delivery they were trying to stop.
  const onRetry = () => {
    if (enabled) void registerForPush();
    else void unregisterForPush();
  };

  const openSettings = () => void Linking.openSettings();

  const statusSentence =
    status === 'registered'
      ? 'This device is registered'
      : status === 'registering'
        ? 'Registering this device'
        : status === 'failed'
          ? (diagnosis?.title ?? 'Registration failed')
          : enabled
            ? 'On'
            : 'Off';

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.cardLabel}>Notifications</Text>
        {/* iOS does not associate an adjacent <Text> with a <Switch>, so
            without these VoiceOver announces "switch button, on" with no name
            — and reads an ON switch on a device that failed to register, which
            is the exact confusion this card exists to end. The value carries
            the same sentence the status block shows, so intent and reality
            arrive together in the audio order too. */}
        <Switch
          value={enabled}
          onValueChange={onToggle}
          accessibilityLabel="Notifications"
          accessibilityValue={{ text: statusSentence }}
        />
      </View>

      {status === 'failed' && diagnosis ? (
        <View style={styles.errorBox}>
          <View style={[styles.statusRow, styles.errorHeadRow]}>
            <Ionicons name="alert-circle" size={16} color={colors.gradeBad} />
            <Text style={styles.errTitle}>{diagnosis.title}</Text>
          </View>
          <Text style={styles.errAdvice}>{diagnosis.advice}</Text>

          <View style={styles.actions}>
            {diagnosis.retryable ? (
              <Pressable
                onPress={onRetry}
                accessibilityRole="button"
                accessibilityLabel="Try registering this device again"
                style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
              >
                <Ionicons name="refresh" size={15} color={colors.tint} />
                <Text style={styles.buttonText}>Try again</Text>
              </Pressable>
            ) : null}
            {diagnosis.opensSettings ? (
              <Pressable
                onPress={openSettings}
                accessibilityRole="button"
                style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
              >
                <Ionicons name="settings-outline" size={15} color={colors.tint} />
                <Text style={styles.buttonText}>Open iOS Settings</Text>
              </Pressable>
            ) : null}
          </View>

          {/* The raw error. Shown verbatim because a message this code did not
              recognise is exactly the one worth reading unedited. */}
          <Pressable
            onPress={() => setDetailOverride(!showDetail)}
            accessibilityRole="button"
            accessibilityState={{ expanded: showDetail }}
            // A 12pt caption is a ~16pt target against UX_REVIEW §4's 44pt
            // floor, and this row has to stay visually small.
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <Text style={styles.detailToggle}>{showDetail ? 'Hide details' : 'Show details'}</Text>
          </Pressable>
          {showDetail ? <Text style={styles.detailText}>{diagnosis.detail}</Text> : null}
        </View>
      ) : null}

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
            <Ionicons name="checkmark-circle" size={16} color={colors.gradeGood} />
            <Text style={styles.statusText}>
              This device is registered{registeredAt ? ` · ${timeLabel(registeredAt)}` : ''}
            </Text>
          </View>

          <View style={styles.actions}>
            <Pressable
              onPress={onTest}
              disabled={testing}
              accessibilityRole="button"
              accessibilityLabel="Send a test notification to this device"
              accessibilityState={{ disabled: testing }}
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
          </View>

          {testResult ? (
            testResult.ok ? (
              <>
                {/* CLAIMS ONLY WHAT IT OBSERVED. This used to read "notifications
                    are being delivered but not shown, which is an iOS Settings
                    question" — asserting an APNs delivery from an Expo ticket,
                    which pushTest.ts's own header calls unprovable. What we know
                    is that Expo accepted it; the rest is the reader's to check. */}
                <Text style={styles.statusText}>
                  Sent{testedAt ? ` · ${timeLabel(testedAt)}` : ''} — it should arrive in a few
                  seconds.
                </Text>
                <Text style={styles.sub}>
                  Not seeing it? Check Notifications → Signalbase in iOS Settings.
                </Text>
                <View style={styles.actions}>
                  <Pressable
                    onPress={openSettings}
                    accessibilityRole="button"
                    style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
                  >
                    <Ionicons name="settings-outline" size={15} color={colors.tint} />
                    <Text style={styles.buttonText}>Open iOS Settings</Text>
                  </Pressable>
                </View>
              </>
            ) : (
              // Same shape as the registration failure above, so the two read as
              // one thing. Not colours.avoid on a whole sentence: it measures
              // 3.55:1 on bgCard, under the AA floor, and the icon carries the
              // signal instead.
              <View style={styles.statusRow}>
                <Ionicons name="alert-circle" size={16} color={colors.gradeBad} />
                <Text style={styles.statusText}>
                  {testResult.diagnosis?.title}. {testResult.diagnosis?.detail}
                </Text>
              </View>
            )
          ) : null}
        </>
      ) : null}
    </View>
  );
}

/** A short local time, for "registered at" and "sent at". Date-less on
 *  purpose: both rows are about now, and a full timestamp reads as data the
 *  reader has to interpret. */
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
  // Matches SettingsScreen's own cardLabel / sub rather than inventing a
  // smaller heading and lighter body for the one card on the screen that has
  // something to say.
  cardLabel: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  sub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
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
    lineHeight: 18,
  },
  // The margin lives on the row, not on the buttons: styles.button's own
  // marginTop inside a wrapping row made the vertical gap 20pt against an 8pt
  // horizontal one once "Open iOS Settings" wrapped at large Dynamic Type.
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.md,
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
    // HIG's 44pt minimum target: set, not left to the content.
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
  errorBox: {
    backgroundColor: colors.bg,
    borderRadius: radii.sm,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  // statusRow carries a top margin for the rows that follow body copy; the
  // error box supplies its own padding, so its first row must not add to it.
  errorHeadRow: {
    marginTop: 0,
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
    color: colors.textSecondary,
    marginTop: spacing.xs,
    lineHeight: 16,
  },
});

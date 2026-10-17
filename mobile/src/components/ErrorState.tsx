import React, { useEffect, useRef } from 'react';
import { AccessibilityInfo, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';
import { errorAnnouncement, friendlyError, isAbortError, type FriendlyError } from '@/lib/errors';
import { repeatFailureAnnounce } from '@/lib/loadState';

/**
 * PATTERNS §E3, built from the Stats "Couldn’t load players / Retry" pattern
 * (usability audit H3/M1). A failed load says so, names the thing, gives one
 * plain cause, and offers Retry. The raw Supabase text never reaches the
 * screen (UX_REVIEW §3); in a dev build it goes to the console instead.
 *
 * - `ErrorState`: the whole view failed. EmptyState layout + a 44pt secondary
 *   Retry. Use it IN PLACE of the empty state, never above one.
 * - `ErrorBanner`: a failure over content that is still on screen (a reload
 *   that failed, a section that did not come back). Plain Retry.
 *
 * An intentional cancel (isAbortError: an unmount, a superseded request)
 * renders nothing and announces nothing: it is not a failure.
 *
 * Colour: the alert icon is avoidInk (5.01:1 on avoidSoft, 5.73:1 on bgCard);
 * the words are textPrimary / textSecondary. No red body text (§E3).
 */

interface Props {
  /** What failed to load, e.g. "today’s MLB picks". Becomes "Couldn’t load …". */
  what: string;
  /** The raw error the hook kept (errorText output) or the thrown value. */
  error: unknown;
  onRetry: () => void;
  /** Disable Retry while a reload is in flight. */
  retrying?: boolean;
  /** Outer margins where the screen's own gutter differs. */
  style?: StyleProp<ViewStyle>;
  /**
   * One optional line after the cause, e.g. "Nothing is wrong with your
   * picks." — for a screen where a failed load could read as lost data
   * (Designer, #845). Read out with the title and cause.
   */
  reassurance?: string;
  /**
   * Replaces the generated title and cause. Retry, the alert, and the icon
   * stay. An abort in `error` still renders nothing.
   */
  copy?: FriendlyError;
}

/**
 * Announce once per distinct failure, not on every parent render — and once
 * more when a Retry the user pressed settles on the SAME failure (Designer
 * #845 a): nothing the first effect keys on changes then, so without the
 * settled retry attempt as a second key VoiceOver heard nothing and the Retry
 * seemed dead. Returns the press marker for the Retry button.
 */
function useAnnounceAndLog(
  copy: FriendlyError,
  error: unknown,
  silent: boolean,
  retrying: boolean | undefined,
  reassurance?: string,
): () => void {
  const key = `${copy.title}|${copy.kind}|${reassurance ?? ''}`;
  const lastKey = useRef<string | null>(null);
  const pressed = useRef(false);
  const wasRetrying = useRef(Boolean(retrying));
  const announce = () => {
    AccessibilityInfo.announceForAccessibility(errorAnnouncement(copy, reassurance));
    lastKey.current = key;
  };
  // Declared FIRST so it compares against the copy read out BEFORE this
  // commit: a retry that settles on a different failure is the effect below's
  // job, and is read out once, not twice.
  useEffect(() => {
    const now = Boolean(retrying);
    if (!silent && repeatFailureAnnounce({ pressed: pressed.current, wasRetrying: wasRetrying.current, retrying: now, key, lastKey: lastKey.current })) {
      pressed.current = false;
      announce();
    }
    if (wasRetrying.current && !now) pressed.current = false;
    wasRetrying.current = now;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retrying]);
  useEffect(() => {
    if (silent) return;
    announce();
    if (__DEV__) console.warn(`[load error] ${copy.title}:`, error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copy.title, copy.kind, silent, reassurance]);
  return () => {
    pressed.current = true;
  };
}

function shownCopy(what: string, error: unknown, override?: FriendlyError): FriendlyError {
  return override ?? friendlyError(error, what);
}

export function ErrorState({ what, error, onRetry, retrying, compact, style, reassurance, copy: override }: Props & { compact?: boolean }) {
  const copy = shownCopy(what, error, override);
  const silent = isAbortError(error);
  const markRetry = useAnnounceAndLog(copy, error, silent, retrying, reassurance);
  if (silent) return null;
  return (
    <View
      style={[styles.state, compact && styles.stateCompact, style]}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      <Ionicons
        name={copy.kind === 'offline' ? 'cloud-offline-outline' : 'alert-circle-outline'}
        size={28}
        color={colors.avoidInk}
        style={styles.stateIcon}
        accessibilityElementsHidden
        importantForAccessibility="no"
      />
      <Text style={styles.stateTitle}>{copy.title}</Text>
      <Text style={styles.stateCause}>{copy.cause}</Text>
      {reassurance ? <Text style={styles.stateCause}>{reassurance}</Text> : null}
      <Pressable
        onPress={() => {
          markRetry();
          onRetry();
        }}
        disabled={retrying}
        accessibilityRole="button"
        accessibilityLabel={`Retry loading ${what}`}
        accessibilityState={{ disabled: Boolean(retrying), busy: Boolean(retrying) }}
        style={({ pressed }) => [styles.retryBtn, (pressed || retrying) && styles.pressed]}
      >
        <Ionicons name="refresh" size={16} color={colors.tint} />
        <Text style={styles.retryBtnText}>{retrying ? 'Retrying…' : 'Retry'}</Text>
      </Pressable>
    </View>
  );
}

export function ErrorBanner({ what, error, onRetry, retrying, style, reassurance, copy: override }: Props) {
  const copy = shownCopy(what, error, override);
  const silent = isAbortError(error);
  const markRetry = useAnnounceAndLog(copy, error, silent, retrying, reassurance);
  if (silent) return null;
  return (
    <View style={[styles.banner, style]} accessibilityRole="alert" accessibilityLiveRegion="polite">
      <Ionicons
        name={copy.kind === 'offline' ? 'cloud-offline-outline' : 'alert-circle-outline'}
        size={16}
        color={colors.avoidInk}
        style={styles.bannerIcon}
        accessibilityElementsHidden
        importantForAccessibility="no"
      />
      <View style={styles.bannerText}>
        <Text style={styles.bannerTitle}>{copy.title}</Text>
        <Text style={styles.bannerCause}>{copy.cause}</Text>
        {reassurance ? <Text style={styles.bannerCause}>{reassurance}</Text> : null}
      </View>
      <Pressable
        onPress={() => {
          markRetry();
          onRetry();
        }}
        disabled={retrying}
        hitSlop={{ left: 8, right: 8 }}
        accessibilityRole="button"
        accessibilityLabel={`Retry loading ${what}`}
        accessibilityState={{ disabled: Boolean(retrying), busy: Boolean(retrying) }}
        style={({ pressed }) => [styles.bannerRetry, (pressed || retrying) && styles.pressed]}
      >
        <Text style={styles.bannerRetryText}>{retrying ? 'Retrying…' : 'Retry'}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  state: {
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.xxl * 1.5,
  },
  stateCompact: { paddingVertical: spacing.lg },
  stateIcon: { marginBottom: spacing.sm },
  stateTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
    textAlign: 'center',
  },
  stateCause: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
  },
  // PATTERNS §A2 secondary: bgCard, hairline, tint label, 44pt.
  retryBtn: {
    marginTop: spacing.lg,
    minHeight: 44,
    paddingHorizontal: spacing.xl,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separatorOpaque,
  },
  retryBtnText: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.avoidSoft,
    paddingLeft: spacing.md,
    paddingRight: spacing.xs,
    paddingVertical: spacing.xs,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    borderRadius: radii.md,
  },
  bannerIcon: { alignSelf: 'flex-start', marginTop: 1 },
  bannerText: { flex: 1, gap: 2 },
  bannerTitle: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  bannerCause: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  // 44pt tall target (UX_REVIEW §4) without growing the label.
  bannerRetry: { minHeight: 44, paddingHorizontal: spacing.sm, justifyContent: 'center' },
  bannerRetryText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  pressed: { opacity: 0.6 },
});

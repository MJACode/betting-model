import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { discordErrorMessage, discordInviteIfPaid } from '@/lib/discord';
import { openLink } from '@/lib/socialLinks';
import { useAccess } from '@/hooks/useAccess';
import { useMembership } from '@/hooks/useMembership';
import { isEntitled } from '@/lib/billingHelpers';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Connect Discord. Free and trial are linking a Whop account, not joining.
 * The invite opens only when the App Store subscription is active.
 */
export function DiscordLinkModal({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const { access, link, busy } = useAccess();
  const { subscription } = useMembership();
  const applePaid = Boolean(subscription && isEntitled(subscription) && subscription.status === 'active');
  const invite = discordInviteIfPaid(applePaid);
  const [working, setWorking] = useState(false);

  const onConnect = useCallback(async () => {
    setWorking(true);
    try {
      const linked = await link();
      // A cancel is a normal outcome — leave the sheet open so the user can
      // try again without hunting for the entry point a second time.
      if (linked) onClose();
    } catch (e) {
      Alert.alert('Could not connect Discord', discordErrorMessage(e));
    } finally {
      setWorking(false);
    }
  }, [link, onClose]);

  const pending = working || busy;
  const alreadyLinked = access.discord_linked;

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <Pressable
            onPress={onClose}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel="Close Discord link"
            style={styles.close}
          >
            <Ionicons name="close" size={24} color={colors.textSecondary} />
          </Pressable>

          <Text style={styles.title}>
            {alreadyLinked
              ? 'You’re connected to the Signalbase Discord'
              : 'Connect Discord'}
          </Text>
          <Text style={styles.body}>
            {alreadyLinked
              ? applePaid
                ? 'Open Discord to jump into the subscriber channels.'
                : 'The invite unlocks when your Apple plan is paid. No invite is shown until then.'
              : applePaid
                ? 'Your subscription includes the subscriber Discord. Connect your account to join.'
                : 'Already in Discord via Whop? Connect Discord to link your account. Premium in the app is still via Apple.'}
          </Text>

          <View style={styles.iconRow}>
            <View style={[styles.iconTile, styles.discordTile]}>
              <Ionicons name="logo-discord" size={34} color={colors.textInverse} />
            </View>
            <Ionicons name="add" size={22} color={colors.tint} />
            <View style={[styles.iconTile, styles.appTile]}>
              <Ionicons name="trophy" size={30} color={colors.textInverse} />
            </View>
          </View>

          {alreadyLinked && invite ? (
            <Pressable
              accessibilityLabel="Open the Discord"
              onPress={() => openLink(invite, 'Discord')}
              accessibilityRole="button"
              style={({ pressed }) => [styles.cta, pressed && styles.pressed]}
            >
              <Text style={styles.ctaText}>Open the Discord</Text>
            </Pressable>
          ) : alreadyLinked ? null : (
            <Pressable
              accessibilityLabel="Connect Discord"
              accessibilityState={{ busy: pending, disabled: pending }}
              onPress={onConnect}
              disabled={pending}
              accessibilityRole="button"
              style={({ pressed }) => [
                styles.cta,
                pressed && styles.pressed,
                pending && styles.disabled,
              ]}
            >
              {pending ? (
                <ActivityIndicator color={colors.textInverse} />
              ) : (
                <Text style={styles.ctaText}>Connect Discord</Text>
              )}
            </Pressable>
          )}

          {/* No invite fallback. The URL is Apple-paid only, and this sheet
              is the account link — it must not hand the invite to a trial
              or a free member. */}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: '#00000099',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  sheet: {
    backgroundColor: colors.bgElevated,
    borderRadius: radii.lg,
    padding: spacing.xl,
    gap: spacing.md,
    alignItems: 'center',
  },
  close: { alignSelf: 'flex-end' },
  title: {
    fontFamily: font.family,
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  body: {
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  iconRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
  },
  iconTile: {
    width: 64,
    height: 64,
    borderRadius: radii.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  discordTile: { backgroundColor: colors.discord },
  appTile: { backgroundColor: colors.textPrimary },
  cta: {
    alignSelf: 'stretch',
    height: 50,
    borderRadius: radii.pill,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  altLink: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.tint,
    textDecorationLine: 'underline',
    paddingTop: spacing.xs,
  },
  pressed: { opacity: 0.6 },
  disabled: { opacity: 0.4 },
});

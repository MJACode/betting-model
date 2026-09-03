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

import { discordErrorMessage } from '@/lib/discord';
import { DISCORD_URL, openLink } from '@/lib/socialLinks';
import { useAccess } from '@/hooks/useAccess';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Your subscription includes access to the Discord" — the join sheet, modelled
 * on the reference Matt supplied.
 *
 * ONE TAP, not an invite link. Connecting authorizes `guilds.join`, so the
 * edge function puts the user in the server and grants the subscriber role in
 * the same round trip. The plain invite stays as the fallback for the cases
 * where that can't work: the bot being briefly unreachable, or a user who
 * declines the join scope.
 *
 * Rendered by the caller only when it is worth showing — this component does
 * not decide who sees it.
 */
export function DiscordLinkModal({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const { access, link, busy } = useAccess();
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
            accessibilityLabel="Close"
            style={styles.close}
          >
            <Ionicons name="close" size={24} color={colors.textSecondary} />
          </Pressable>

          <Text style={styles.title}>
            {alreadyLinked
              ? 'You’re connected to the Signalbase Discord'
              : 'Your subscription includes access to the Signalbase Discord'}
          </Text>
          <Text style={styles.body}>
            {alreadyLinked
              ? 'Open Discord to jump into the subscriber channels.'
              : 'Connect your Discord account to join the subscriber-only server and chat with other members.'}
          </Text>

          <View style={styles.iconRow}>
            <View style={[styles.iconTile, styles.discordTile]}>
              <Ionicons name="logo-discord" size={34} color="#FFFFFF" />
            </View>
            <Ionicons name="add" size={22} color={colors.tint} />
            <View style={[styles.iconTile, styles.appTile]}>
              <Ionicons name="trophy" size={30} color="#FFFFFF" />
            </View>
          </View>

          {alreadyLinked ? (
            <Pressable
              onPress={() => openLink(DISCORD_URL, 'Discord')}
              accessibilityRole="button"
              style={({ pressed }) => [styles.cta, pressed && styles.pressed]}
            >
              <Text style={styles.ctaText}>Open the Discord</Text>
            </Pressable>
          ) : (
            <Pressable
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
                <Text style={styles.ctaText}>Join the Discord</Text>
              )}
            </Pressable>
          )}

          {/* Fallback for a user who would rather not authorize, or for a
              guild-join that failed. The invite still works; they just won't
              get the subscriber role until they connect. */}
          {!alreadyLinked ? (
            <Pressable onPress={() => openLink(DISCORD_URL, 'Discord')} hitSlop={8}>
              <Text style={styles.altLink}>Use an invite link instead</Text>
            </Pressable>
          ) : null}
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
  discordTile: { backgroundColor: '#5865F2' },
  appTile: { backgroundColor: '#000000' },
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

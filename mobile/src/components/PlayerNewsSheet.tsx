import React from 'react';
import {
  ActivityIndicator,
  Linking,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { newsDateLabel, sourceLabel } from '@/lib/playerNews';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { PlayerNewsRow } from '@/types';

/**
 * Recent News — the sheet behind the newspaper icon on the prop screens.
 *
 * One card per note, newest first: the date it happened, the headline, what
 * happened, and (for providers that carry one) the ANALYSIS paragraph that says
 * what it means for the player's workload. That last block is the reason this
 * sheet is worth a tap on a prop screen — "72 pitches, pulled without recording
 * an out in the third" is the context a strikeout line is priced around.
 *
 * The provider is named in the header rather than assumed: `player_news.source`
 * travels with each row, so a licensed feed swapping in behind the ingestor
 * re-labels the sheet without a change here.
 */
export function PlayerNewsSheet({
  visible,
  onClose,
  playerName,
  subtitle,
  news,
  loading,
  error,
}: {
  visible: boolean;
  onClose: () => void;
  playerName: string;
  /** Team / position line under the title, when the screen knows one. */
  subtitle?: string | null;
  news: PlayerNewsRow[];
  loading?: boolean;
  error?: string | null;
}) {
  const provider = sourceLabel(news[0]?.source);

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={() => {}}>
          <View style={styles.grabber} />

          <View style={styles.header}>
            <View style={styles.headerBody}>
              <Text style={styles.title}>Recent News</Text>
              <Text style={styles.playerLine} numberOfLines={1}>
                {playerName}
                {subtitle ? ` · ${subtitle}` : ''}
              </Text>
            </View>
            {provider ? <Text style={styles.poweredBy}>Powered by {provider}</Text> : null}
          </View>

          <ScrollView contentContainerStyle={styles.list}>
            {loading ? (
              <ActivityIndicator style={styles.spinner} color={colors.tint} />
            ) : error ? (
              <Text style={styles.empty}>
                Couldn’t load news right now. The pick and its numbers are unaffected.
              </Text>
            ) : news.length === 0 ? (
              <Text style={styles.empty}>
                No recent news for {playerName}. Notes appear here when the feed writes about
                him — a scratch, a workload note, a role change.
              </Text>
            ) : (
              news.map((item) => (
                <View key={item.news_id} style={styles.card}>
                  <View style={styles.datePill}>
                    <Text style={styles.datePillText}>{newsDateLabel(item.published_at)}</Text>
                  </View>
                  <Text style={styles.headline}>{item.headline}</Text>
                  {item.body ? <Text style={styles.body}>{item.body}</Text> : null}
                  {item.analysis ? (
                    <View style={styles.analysisBlock}>
                      <Text style={styles.analysisLabel}>ANALYSIS</Text>
                      <Text style={styles.analysisBody}>{item.analysis}</Text>
                    </View>
                  ) : null}
                  {item.url ? (
                    <Pressable
                      style={styles.readMore}
                      onPress={() => Linking.openURL(item.url!).catch(() => {})}
                      accessibilityRole="link"
                    >
                      <Text style={styles.readMoreText}>
                        Read on {sourceLabel(item.source)}
                      </Text>
                      <Ionicons name="open-outline" size={14} color={colors.tint} />
                    </Pressable>
                  ) : null}
                </View>
              ))
            )}
          </ScrollView>

          <Pressable style={styles.closeButton} onPress={onClose} accessibilityRole="button">
            <Text style={styles.closeText}>Close</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.bgElevated,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingBottom: spacing.xl,
    maxHeight: '88%',
  },
  grabber: {
    alignSelf: 'center',
    width: 36,
    height: 5,
    borderRadius: radii.pill,
    backgroundColor: colors.separatorOpaque,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  headerBody: { flex: 1, paddingRight: spacing.md },
  title: { fontSize: font.size.title3, fontWeight: font.weight.bold, color: colors.textPrimary },
  playerLine: { fontSize: font.size.footnote, color: colors.textSecondary, marginTop: 2 },
  poweredBy: { fontSize: font.size.caption, color: colors.textTertiary },
  list: { padding: spacing.lg, gap: spacing.md },
  spinner: { marginTop: spacing.xl },
  empty: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    lineHeight: 20,
    paddingVertical: spacing.lg,
  },
  card: {
    backgroundColor: colors.bgGrouped,
    borderRadius: radii.md,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  datePill: {
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: colors.tint,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: 3,
  },
  datePillText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.tint,
    letterSpacing: 0.5,
  },
  headline: { fontSize: font.size.headline, fontWeight: font.weight.bold, color: colors.textPrimary },
  body: { fontSize: font.size.body, color: colors.textPrimary, lineHeight: 21 },
  analysisBlock: {
    backgroundColor: colors.bgElevated,
    borderRadius: radii.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separator,
    padding: spacing.md,
    gap: spacing.xs,
  },
  analysisLabel: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.textTertiary,
    letterSpacing: 0.6,
  },
  analysisBody: { fontSize: font.size.callout, color: colors.textSecondary, lineHeight: 20 },
  readMore: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, paddingTop: spacing.xs },
  readMoreText: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, color: colors.tint },
  closeButton: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  closeText: { fontSize: font.size.headline, fontWeight: font.weight.semibold, color: colors.textInverse },
});

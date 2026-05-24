import React, { useEffect, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { useBankroll } from '@/hooks/useBankroll';
import { usePlacedPicks } from '@/hooks/usePlacedPicks';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function SettingsScreen() {
  const navigation = useNavigation<Nav>();
  const { bankroll, setBankroll, ready } = useBankroll();
  const { reset } = usePlacedPicks();
  const [draft, setDraft] = useState<string>('');

  useEffect(() => {
    if (ready) setDraft(String(bankroll));
  }, [bankroll, ready]);

  const onSave = () => {
    const v = parseFloat(draft);
    if (!Number.isFinite(v) || v <= 0) {
      Alert.alert('Invalid bankroll', 'Enter a positive number.');
      return;
    }
    setBankroll(v);
    Alert.alert('Saved', `Bankroll set to $${v.toFixed(2)}.`);
  };

  const onResetPlaced = () => {
    Alert.alert(
      'Clear all tracked bets?',
      'Every pick will revert to not-placed. Performance and the calendar will reset to empty until you mark new picks.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: () => {
            reset();
            Alert.alert('Tracked bets cleared.');
          },
        },
      ],
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.list}>
        <Text style={styles.title}>Settings</Text>

        <View style={styles.card}>
          <Text style={styles.cardLabel}>Bankroll</Text>
          <View style={styles.bankrollRow}>
            <Text style={styles.dollar}>$</Text>
            <TextInput
              style={styles.input}
              value={draft}
              onChangeText={setDraft}
              keyboardType="decimal-pad"
              placeholder="1000"
              placeholderTextColor={colors.textTertiary}
            />
            <Pressable onPress={onSave} style={styles.saveBtn}>
              <Text style={styles.saveBtnText}>Save</Text>
            </Pressable>
          </View>
          <Text style={styles.sub}>
            Bet sizes recompute live across the app. Stored on this device.
          </Text>
        </View>

        <Pressable
          style={styles.linkCard}
          onPress={() => navigation.navigate('Explainer')}
        >
          <View style={{ flex: 1 }}>
            <Text style={styles.cardLabel}>How this works</Text>
            <Text style={styles.sub}>
              Edge, BET/AVOID/NONE, Kelly sizing, and Performance tracking explained.
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
        </Pressable>

        <Pressable style={styles.card} onPress={onResetPlaced}>
          <Text style={[styles.cardLabel, { color: colors.avoid }]}>Clear tracked bets</Text>
          <Text style={styles.sub}>
            Resets every pick you marked I'm Betting. Performance tab will fall back to empty.
          </Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
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
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  linkCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
  },
  cardLabel: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  bankrollRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  dollar: {
    fontSize: font.size.title3,
    color: colors.textPrimary,
    fontWeight: font.weight.semibold,
  },
  input: {
    flex: 1,
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    backgroundColor: colors.bg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
  },
  saveBtn: {
    backgroundColor: colors.tint,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
  },
  saveBtnText: {
    color: colors.textInverse,
    fontWeight: font.weight.semibold,
    fontSize: font.size.body,
  },
  sub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});

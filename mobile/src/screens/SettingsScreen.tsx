import React, { useEffect, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useBankroll } from '@/hooks/useBankroll';
import { usePlacedPicks } from '@/hooks/usePlacedPicks';
import { SUPABASE_PROJECT_REF } from '@/lib/supabase';
import { colors, font, radii, spacing } from '@/lib/theme';

export function SettingsScreen() {
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
      'Reset placed flags?',
      'Every pick will revert to its default (BET = placed, AVOID/NONE = not placed). Settled history in Performance will recompute.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset',
          style: 'destructive',
          onPress: () => {
            reset();
            Alert.alert('Placed flags cleared.');
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

        <Pressable style={styles.card} onPress={onResetPlaced}>
          <Text style={[styles.cardLabel, { color: colors.avoid }]}>Reset placed-bet flags</Text>
          <Text style={styles.sub}>
            Clears every override. Performance tab will fall back to defaults.
          </Text>
        </Pressable>

        <View style={styles.card}>
          <Text style={styles.cardLabel}>About</Text>
          <KV k="Build" v="0.1.0" />
          <KV k="Supabase project" v={SUPABASE_PROJECT_REF} />
          <KV k="Threshold sync" v="2026-05-15 (config.py)" />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <View style={styles.kv}>
      <Text style={styles.kvK}>{k}</Text>
      <Text style={styles.kvV}>{v}</Text>
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
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
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
  kv: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
  },
  kvK: {
    fontSize: font.size.body,
    color: colors.textSecondary,
  },
  kvV: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
});

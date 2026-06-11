import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { fetchFighterByName, fetchFighterRecentFights } from '@/lib/queries';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { FighterRow, FightLogRow } from '@/types';

interface Props {
  awayName: string;
  homeName: string;
  /** Pick date — recent fights are taken strictly before this. */
  gameDate: string;
}

interface FighterSide {
  profile: FighterRow | null;
  fights: FightLogRow[];
}

/**
 * UFC tale of the tape — height/reach/stance/age from `fighters` plus last-5
 * form from `ufc_fight_log`. The UFC analog of the MLB prop matchup card.
 * Hides itself entirely until the fighter backfill has populated the tables.
 */
export function TaleOfTheTapeCard({ awayName, homeName, gameDate }: Props) {
  const [sides, setSides] = useState<[FighterSide, FighterSide] | null>(null);

  useEffect(() => {
    let mounted = true;
    const loadSide = async (name: string): Promise<FighterSide> => {
      try {
        const profile = await fetchFighterByName(name);
        const fights = profile
          ? await fetchFighterRecentFights(profile.fighter_id, gameDate, 5)
          : [];
        return { profile, fights };
      } catch {
        return { profile: null, fights: [] };
      }
    };
    Promise.all([loadSide(awayName), loadSide(homeName)]).then(([a, h]) => {
      if (mounted) setSides([a, h]);
    });
    return () => {
      mounted = false;
    };
  }, [awayName, homeName, gameDate]);

  if (!sides || (!sides[0].profile && !sides[1].profile)) return null;
  const [away, home] = sides;

  const rows: { label: string; away: string; home: string }[] = [
    { label: 'Height', away: fmtHeight(away.profile), home: fmtHeight(home.profile) },
    { label: 'Reach', away: fmtReach(away.profile), home: fmtReach(home.profile) },
    { label: 'Stance', away: away.profile?.stance ?? '—', home: home.profile?.stance ?? '—' },
    { label: 'Age', away: fmtAge(away.profile, gameDate), home: fmtAge(home.profile, gameDate) },
    { label: 'Last 5', away: fmtRecord(away.fights), home: fmtRecord(home.fights) },
    { label: 'Finishes', away: fmtFinishes(away.fights), home: fmtFinishes(home.fights) },
  ].filter((r) => r.away !== '—' || r.home !== '—');

  if (rows.length === 0) return null;

  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Tale of the Tape</Text>
      <View style={styles.namesRow}>
        <Text style={[styles.name, styles.left]} numberOfLines={1}>
          {awayName}
        </Text>
        <Text style={[styles.name, styles.right]} numberOfLines={1}>
          {homeName}
        </Text>
      </View>
      {rows.map((r) => (
        <View key={r.label} style={styles.row}>
          <Text style={[styles.value, styles.left]}>{r.away}</Text>
          <Text style={styles.rowLabel}>{r.label}</Text>
          <Text style={[styles.value, styles.right]}>{r.home}</Text>
        </View>
      ))}
    </View>
  );
}

function fmtHeight(f: FighterRow | null): string {
  if (f?.height_in == null) return '—';
  const inches = Number(f.height_in);
  return `${Math.floor(inches / 12)}'${Math.round(inches % 12)}"`;
}

function fmtReach(f: FighterRow | null): string {
  if (f?.reach_in == null) return '—';
  return `${Math.round(Number(f.reach_in))}"`;
}

function fmtAge(f: FighterRow | null, asOf: string): string {
  if (!f?.dob) return '—';
  const dob = new Date(f.dob).getTime();
  const ref = new Date(asOf).getTime();
  if (Number.isNaN(dob) || Number.isNaN(ref)) return '—';
  return String(Math.floor((ref - dob) / (365.25 * 24 * 3600 * 1000)));
}

function fmtRecord(fights: FightLogRow[]): string {
  if (fights.length === 0) return '—';
  const w = fights.filter((f) => f.result === 'win').length;
  const l = fights.filter((f) => f.result === 'loss').length;
  const other = fights.length - w - l;
  return `${w}-${l}${other > 0 ? `-${other}` : ''}`;
}

function fmtFinishes(fights: FightLogRow[]): string {
  const wins = fights.filter((f) => f.result === 'win');
  if (wins.length === 0) return '—';
  const ko = wins.filter((f) => f.method === 'ko_tko').length;
  const sub = wins.filter((f) => f.method === 'submission').length;
  const parts: string[] = [];
  if (ko > 0) parts.push(`${ko} KO`);
  if (sub > 0) parts.push(`${sub} SUB`);
  if (parts.length === 0) parts.push('all DEC');
  return parts.join(' · ');
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  heading: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: spacing.sm,
  },
  namesRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: spacing.md,
    marginBottom: 4,
  },
  name: {
    flex: 1,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 5,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  rowLabel: {
    width: 76,
    textAlign: 'center',
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  value: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
  left: {
    textAlign: 'left',
  },
  right: {
    textAlign: 'right',
  },
});

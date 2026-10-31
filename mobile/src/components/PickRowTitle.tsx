import React from 'react';
import { Text, type StyleProp, type TextStyle } from 'react-native';
import { pickRowMatchup, pickRowTitle } from '@/lib/markets';

interface Props {
  pick: { pick_label: string };
  titleStyle: StyleProp<TextStyle>;
  matchupStyle: StyleProp<TextStyle>;
}

/**
 * The title of a pick row on a model's page and the tracked list.
 *
 * A first half's title clips its middle, never the number at the end (UX review,
 * 2026-10-31: the whole label on one line lost the side and number first at
 * larger text). Its matchup goes on a line of its own, because middle-clipping
 * the whole label removes "First Half" and leaves what reads as a plain over.
 * Every other label keeps the end clip: its middle can hold the number.
 *
 * The row's accessibility label reads the whole stored label, so these two lines
 * are not read separately.
 */
export function PickRowTitle({ pick, titleStyle, matchupStyle }: Props) {
  const matchup = pickRowMatchup(pick);
  return (
    <>
      <Text style={titleStyle} numberOfLines={1} ellipsizeMode={matchup ? 'middle' : 'tail'}>
        {pickRowTitle(pick)}
      </Text>
      {matchup ? <Text style={matchupStyle}>{matchup}</Text> : null}
    </>
  );
}

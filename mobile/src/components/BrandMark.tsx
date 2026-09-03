import React from 'react';
import { Image, StyleSheet } from 'react-native';

/**
 * The Signalbase mark (assets/brand/mark.png — the X avatar, re-drawn at
 * 512px by scripts/render_brand_icons.py), at any size.
 *
 * One component owns the shape so the corner ratio cannot drift between
 * placements: the first two call sites had invented 18% and 25% between them.
 * 22.4% is the iOS icon squircle ratio, so the in-app mark matches the home
 * screen tile. Decorative by contract — every placement sits above a title
 * that already names the app, so it carries no label and VoiceOver skips it.
 */
export function BrandMark({ size, style }: { size: number; style?: object }) {
  return (
    <Image
      source={require('../../assets/brand/mark.png')}
      style={[
        styles.base,
        { width: size, height: size, borderRadius: Math.round(size * 0.224) },
        style,
      ]}
      accessibilityIgnoresInvertColors
      accessible={false}
    />
  );
}

const styles = StyleSheet.create({
  base: { overflow: 'hidden' },
});

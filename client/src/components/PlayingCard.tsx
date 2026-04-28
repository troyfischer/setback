import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { ViewStyle } from 'react-native';

import { formatCard } from '../lib/format';
import type { SetbackCard } from '../types/setback';

type Props = {
  busy?: boolean;
  card: SetbackCard;
  caption?: string;
  compact?: boolean;
  disabled?: boolean;
  onPress?: () => void;
};

export function PlayingCard({ busy, card, caption, compact, disabled, onPress }: Props) {
  const isRed = card.suit === 'heart' || card.suit === 'diamond';
  const label = formatCard(card);

  const body = (
    <View
      style={[
        styles.tile,
        compact ? styles.tileCompact : null,
        busy ? styles.busy : null,
      ]}
    >
      <Text style={[styles.value, compact ? styles.valueCompact : null, isRed ? styles.red : styles.black]}>
        {label}
      </Text>
      {caption ? <Text style={styles.caption}>{caption}</Text> : null}
    </View>
  );

  if (!onPress) {
    return body;
  }

  return (
    <Pressable
      disabled={disabled || busy}
      onPress={onPress}
      style={({ pressed }) => {
        const base: ViewStyle[] = [];
        if (disabled || busy) {
          base.push(styles.disabled);
        }
        if (pressed && !(disabled || busy)) {
          base.push(styles.pressed);
        }
        return base;
      }}
    >
      {body}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  black: {
    color: '#0d1d31',
  },
  busy: {
    opacity: 0.7,
  },
  caption: {
    color: '#5c7593',
    fontSize: 11,
    fontWeight: '600',
    marginTop: 4,
    textTransform: 'uppercase',
  },
  disabled: {
    opacity: 0.45,
  },
  pressed: {
    transform: [{ scale: 0.96 }],
  },
  red: {
    color: '#b43c2a',
  },
  tile: {
    alignItems: 'center',
    backgroundColor: '#fffaf2',
    borderColor: '#e5d4b4',
    borderRadius: 14,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 86,
    minWidth: 64,
    paddingHorizontal: 12,
    paddingVertical: 10,
    shadowColor: '#081120',
    shadowOffset: { height: 4, width: 0 },
    shadowOpacity: 0.18,
    shadowRadius: 8,
  },
  tileCompact: {
    minHeight: 64,
    minWidth: 48,
    paddingHorizontal: 8,
    paddingVertical: 6,
  },
  value: {
    fontSize: 26,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  valueCompact: {
    fontSize: 20,
  },
});

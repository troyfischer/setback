import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import type { TextStyle, ViewStyle } from 'react-native';

type Tone = 'primary' | 'secondary' | 'ghost';

const toneStyles: Record<Tone, { button: ViewStyle; text: TextStyle }> = {
  ghost: {
    button: {
      backgroundColor: '#f1f5fa',
      borderColor: '#cbd7e6',
    },
    text: {
      color: '#14304d',
    },
  },
  primary: {
    button: {
      backgroundColor: '#b54434',
      borderColor: '#962a24',
    },
    text: {
      color: '#fffdf9',
    },
  },
  secondary: {
    button: {
      backgroundColor: '#173152',
      borderColor: '#102947',
    },
    text: {
      color: '#f8fbff',
    },
  },
};

type Props = {
  busy?: boolean;
  disabled?: boolean;
  label: string;
  onPress: () => void;
  tone?: Tone;
};

export function ActionButton({
  busy = false,
  disabled = false,
  label,
  onPress,
  tone = 'primary',
}: Props) {
  return (
    <Pressable
      disabled={disabled || busy}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        toneStyles[tone].button,
        (disabled || busy) && styles.disabled,
        pressed && !(disabled || busy) ? styles.pressed : null,
      ]}
    >
      <View style={styles.inner}>
        {busy ? <ActivityIndicator color="#f7d774" size="small" /> : null}
        <Text style={[styles.text, toneStyles[tone].text]}>{label}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    borderRadius: 16,
    borderWidth: 1,
    minHeight: 52,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  inner: {
    alignItems: 'center',
    columnGap: 10,
    flexDirection: 'row',
    justifyContent: 'center',
  },
  text: {
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
  disabled: {
    opacity: 0.55,
  },
  pressed: {
    transform: [{ scale: 0.985 }],
  },
});

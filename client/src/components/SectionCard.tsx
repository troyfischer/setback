import type { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';

type Props = {
  children: ReactNode;
  eyebrow?: string;
  subtitle?: string;
  title: string;
};

export function SectionCard({ children, eyebrow, subtitle, title }: Props) {
  return (
    <View style={styles.card}>
      {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
      <Text style={styles.title}>{title}</Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      <View style={styles.body}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  body: {
    rowGap: 14,
  },
  card: {
    backgroundColor: '#fffaf2',
    borderRadius: 28,
    paddingHorizontal: 18,
    paddingVertical: 18,
    rowGap: 6,
    shadowColor: '#081120',
    shadowOffset: { height: 10, width: 0 },
    shadowOpacity: 0.16,
    shadowRadius: 24,
  },
  eyebrow: {
    color: '#b54434',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1.6,
    textTransform: 'uppercase',
  },
  subtitle: {
    color: '#536983',
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 6,
  },
  title: {
    color: '#102947',
    fontSize: 24,
    fontWeight: '800',
  },
});

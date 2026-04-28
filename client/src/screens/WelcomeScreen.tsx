import { useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';

type Props = {
  baseUrl: string;
  busyAction: string | null;
  devUsername: string;
  error: string | null;
  notice: string | null;
  onChangeBaseUrl: (value: string) => void;
  onChangeDevUsername: (value: string) => void;
  onDevLogin: () => void;
  onGoogleLogin: () => void;
};

export function WelcomeScreen({
  baseUrl,
  busyAction,
  devUsername,
  error,
  notice,
  onChangeBaseUrl,
  onChangeDevUsername,
  onDevLogin,
  onGoogleLogin,
}: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const googleAvailable = Platform.OS === 'web';

  return (
    <View style={styles.wrapper}>
      <View style={styles.hero}>
        <Text style={styles.eyebrow}>Card Table</Text>
        <Text style={styles.brand}>Setback</Text>
        <Text style={styles.tagline}>
          A classic four-player trick-taking game. Grab a seat.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Sign in to play</Text>
        <Text style={styles.cardSubtitle}>
          Sign in to create a table, share a join code, and deal your first hand.
        </Text>

        {googleAvailable ? (
          <ActionButton
            busy={busyAction === 'Google login'}
            label="Sign In With Google"
            onPress={onGoogleLogin}
          />
        ) : (
          <View style={styles.nativeNotice}>
            <Text style={styles.nativeNoticeText}>
              Google sign-in is available in the web client. Use the guest option below
              to try the native build.
            </Text>
          </View>
        )}

        <Pressable
          hitSlop={8}
          onPress={() => setShowAdvanced((value) => !value)}
          style={styles.toggleRow}
        >
          <Text style={styles.toggleText}>
            {showAdvanced ? 'Hide advanced options' : 'More options'}
          </Text>
        </Pressable>

        {showAdvanced ? (
          <View style={styles.advanced}>
            <Text style={styles.label}>Guest name</Text>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              onChangeText={onChangeDevUsername}
              placeholder="player-one"
              placeholderTextColor="#8ca3bf"
              style={styles.input}
              value={devUsername}
            />
            <ActionButton
              busy={busyAction === 'Dev login'}
              label="Continue As Guest"
              onPress={onDevLogin}
              tone="secondary"
            />

            <Text style={[styles.label, styles.labelSpaced]}>Server</Text>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              onChangeText={onChangeBaseUrl}
              placeholder="http://localhost"
              placeholderTextColor="#8ca3bf"
              style={styles.input}
              value={baseUrl}
            />
            <Text style={styles.helper}>
              {Platform.OS === 'android'
                ? 'Android emulators usually need http://10.0.2.2 instead of localhost.'
                : 'Point this at a custom server if you are not running the default local backend.'}
            </Text>
          </View>
        ) : null}
      </View>

      {error ? (
        <View style={[styles.banner, styles.errorBanner]}>
          <Text style={styles.bannerText}>{error}</Text>
        </View>
      ) : null}
      {notice && !error ? (
        <View style={[styles.banner, styles.noticeBanner]}>
          <Text style={styles.bannerText}>{notice}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  advanced: {
    borderTopColor: '#e5d4b4',
    borderTopWidth: 1,
    marginTop: 4,
    paddingTop: 16,
    rowGap: 10,
  },
  banner: {
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  bannerText: {
    color: '#fdfefe',
    fontSize: 14,
    fontWeight: '600',
  },
  brand: {
    color: '#f8fbff',
    fontSize: 52,
    fontWeight: '900',
    letterSpacing: 1,
    lineHeight: 56,
  },
  card: {
    backgroundColor: '#fffaf2',
    borderRadius: 28,
    padding: 24,
    rowGap: 14,
    shadowColor: '#081120',
    shadowOffset: { height: 12, width: 0 },
    shadowOpacity: 0.22,
    shadowRadius: 30,
  },
  cardSubtitle: {
    color: '#4e647f',
    fontSize: 15,
    lineHeight: 22,
  },
  cardTitle: {
    color: '#102947',
    fontSize: 22,
    fontWeight: '800',
  },
  errorBanner: {
    backgroundColor: 'rgba(150, 45, 36, 0.94)',
  },
  eyebrow: {
    color: '#f7d774',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 2,
    textTransform: 'uppercase',
  },
  helper: {
    color: '#4e647f',
    fontSize: 13,
    lineHeight: 18,
  },
  hero: {
    alignItems: 'flex-start',
    rowGap: 6,
  },
  input: {
    backgroundColor: '#edf3fa',
    borderColor: '#bfd1e7',
    borderRadius: 14,
    borderWidth: 1,
    color: '#0d1d31',
    fontSize: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  label: {
    color: '#0d1d31',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },
  labelSpaced: {
    marginTop: 6,
  },
  nativeNotice: {
    backgroundColor: '#eff4fa',
    borderRadius: 14,
    padding: 14,
  },
  nativeNoticeText: {
    color: '#4e647f',
    fontSize: 14,
    lineHeight: 20,
  },
  noticeBanner: {
    backgroundColor: 'rgba(31, 134, 99, 0.92)',
  },
  toggleRow: {
    alignSelf: 'center',
    paddingVertical: 4,
  },
  toggleText: {
    color: '#4e647f',
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
  },
  tagline: {
    color: '#d2deee',
    fontSize: 16,
    lineHeight: 22,
    maxWidth: 420,
  },
  wrapper: {
    alignSelf: 'center',
    maxWidth: 520,
    rowGap: 28,
    width: '100%',
  },
});

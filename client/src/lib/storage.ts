import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'setback.client.session.v1';

export type StoredSession = {
  accessToken: string;
  activeGameId: number | null;
  baseUrl: string;
  username: string;
};

export async function loadStoredSession() {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }

    return JSON.parse(raw) as StoredSession;
  } catch {
    return null;
  }
}

export async function saveStoredSession(session: StoredSession) {
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export async function clearStoredSession() {
  await AsyncStorage.removeItem(STORAGE_KEY);
}

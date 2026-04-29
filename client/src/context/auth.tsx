import { createContext, startTransition, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';

import { fetchMe, refreshAccessToken } from '../lib/api';
import { getDefaultApiBaseUrl, normalizeBaseUrl } from '../lib/format';
import type { CurrentUser } from '../types/setback';

type AuthContextValue = {
  accessToken: string;
  baseUrl: string;
  currentUser: CurrentUser | null;
  hydrated: boolean;
  setAccessToken: (token: string) => void;
  setBaseUrl: (url: string) => void;
  setCurrentUser: (user: CurrentUser | null) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [hydrated, setHydrated] = useState(false);
  const [accessToken, setAccessToken] = useState('');
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [baseUrl, setBaseUrl] = useState(getDefaultApiBaseUrl());

  useEffect(() => {
    let cancelled = false;
    async function resume() {
      const url = normalizeBaseUrl(baseUrl);
      try {
        const token = await refreshAccessToken(url);
        if (cancelled) return;
        const user = await fetchMe(url, token.access_token);
        if (cancelled) return;
        startTransition(() => {
          setAccessToken(token.access_token);
          setCurrentUser(user);
        });
      } catch {
        // No valid refresh cookie; fall through to welcome screen.
      } finally {
        if (!cancelled) setHydrated(true);
      }
    }
    void resume();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AuthContext.Provider value={{ accessToken, baseUrl, currentUser, hydrated, setAccessToken, setBaseUrl, setCurrentUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

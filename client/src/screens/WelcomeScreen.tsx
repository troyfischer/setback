import { startTransition, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ActionButton } from '../components/ActionButton';
import { useAuth } from '../context/auth';
import { createDevToken, fetchMe } from '../lib/api';
import { loginWithGoogle } from '../lib/auth';
import { normalizeBaseUrl } from '../lib/format';

export function WelcomeScreen() {
  const { baseUrl, setBaseUrl, setAccessToken, setCurrentUser } = useAuth();
  const navigate = useNavigate();

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [devUsername, setDevUsername] = useState('');
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runAction(label: string, action: () => Promise<void>) {
    setBusyAction(label);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unknown error');
    } finally {
      setBusyAction(null);
    }
  }

  async function handleDevLogin() {
    await runAction('Dev login', async () => {
      const url = normalizeBaseUrl(baseUrl);
      const trimmedName = devUsername.trim();
      if (!trimmedName) throw new Error('Enter a name to continue as guest.');
      const token = await createDevToken(url, trimmedName);
      const user = await fetchMe(url, token.access_token);
      startTransition(() => {
        setBaseUrl(url);
        setAccessToken(token.access_token);
        setCurrentUser(user);
      });
      navigate('/lobby');
    });
  }

  async function handleGoogleLogin() {
    await runAction('Google login', async () => {
      const url = normalizeBaseUrl(baseUrl);
      const token = await loginWithGoogle(url);
      const user = await fetchMe(url, token.access_token);
      startTransition(() => {
        setBaseUrl(url);
        setAccessToken(token.access_token);
        setCurrentUser(user);
      });
      navigate('/lobby');
    });
  }

  return (
    <div className="mx-auto flex w-full max-w-lg flex-col gap-8 px-5 py-12">
      {/* Hero */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-bold uppercase tracking-[2px] text-[#f7d774]">Card Table</span>
        <h1 className="text-6xl font-black tracking-tight text-white leading-none">Setback</h1>
        <p className="mt-1 max-w-sm text-base leading-relaxed text-[#d2deee]">
          A classic four-player trick-taking game. Grab a seat.
        </p>
      </div>

      {/* Sign-in card */}
      <div className="rounded-3xl bg-[#fffaf2] p-7 shadow-2xl flex flex-col gap-5">
        <div>
          <h2 className="text-xl font-extrabold text-[#102947]">Sign in to play</h2>
          <p className="mt-1 text-sm leading-relaxed text-[#4e647f]">
            Create a table, share a join code, and deal your first hand.
          </p>
        </div>

        <ActionButton
          busy={busyAction === 'Google login'}
          label="Sign In With Google"
          onClick={() => { void handleGoogleLogin(); }}
        />

        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="self-center text-xs font-bold uppercase tracking-wider text-[#4e647f] hover:text-[#102947] transition-colors"
        >
          {showAdvanced ? 'Hide options' : 'More options'}
        </button>

        {showAdvanced && (
          <div className="flex flex-col gap-4 border-t border-[#e5d4b4] pt-5">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-bold uppercase tracking-wide text-[#0d1d31]">
                Guest name
              </label>
              <input
                type="text"
                autoComplete="off"
                value={devUsername}
                onChange={(e) => setDevUsername(e.target.value)}
                placeholder="player-one"
                className="rounded-2xl border border-[#bfd1e7] bg-[#edf3fa] px-4 py-3 text-base text-[#0d1d31] placeholder-[#8ca3bf] outline-none focus:border-[#102947] focus:ring-2 focus:ring-[#102947]/20 transition"
              />
            </div>
            <ActionButton
              busy={busyAction === 'Dev login'}
              label="Continue As Guest"
              onClick={() => { void handleDevLogin(); }}
              tone="secondary"
            />
            <div className="flex flex-col gap-1.5 mt-2">
              <label className="text-xs font-bold uppercase tracking-wide text-[#0d1d31]">
                Server
              </label>
              <input
                type="text"
                autoComplete="off"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://localhost"
                className="rounded-2xl border border-[#bfd1e7] bg-[#edf3fa] px-4 py-3 text-base text-[#0d1d31] placeholder-[#8ca3bf] outline-none focus:border-[#102947] focus:ring-2 focus:ring-[#102947]/20 transition"
              />
              <p className="text-xs text-[#4e647f] leading-relaxed">
                Point this at a custom server if you are not running the default local backend.
              </p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-2xl bg-[rgba(150,45,36,0.94)] px-4 py-3">
          <p className="text-sm font-semibold text-white">{error}</p>
        </div>
      )}
    </div>
  );
}

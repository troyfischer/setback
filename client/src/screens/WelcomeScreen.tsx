import { startTransition, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ActionButton } from "../components/ActionButton";
import { useAuth } from "../context/auth";
import { createDevToken, fetchMe } from "../lib/api";
import { loginWithGoogle } from "../lib/auth";
import { normalizeBaseUrl } from "../lib/format";

const inputClass = [
  "rounded-2xl border px-4 py-3 text-base outline-none transition w-full",
  "bg-white/70 border-slate-200/80 text-gray-900 placeholder-slate-400",
  "focus:border-slate-400/60 focus:ring-2 focus:ring-slate-200/50",
  "dark:bg-white/[0.07] dark:border-white/10 dark:text-white dark:placeholder-white/30",
  "dark:focus:border-white/25 dark:focus:ring-white/[0.08]",
].join(" ");

export function WelcomeScreen() {
  const { baseUrl, setBaseUrl, setAccessToken, setCurrentUser } = useAuth();
  const navigate = useNavigate();

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [devUsername, setDevUsername] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runAction(label: string, action: () => Promise<void>) {
    setBusyAction(label);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleDevLogin() {
    await runAction("Dev login", async () => {
      const url = normalizeBaseUrl(baseUrl);
      const trimmedName = devUsername.trim();
      if (!trimmedName) throw new Error("Enter a name to continue as guest.");
      const token = await createDevToken(url, trimmedName);
      const user = await fetchMe(url, token.access_token);
      startTransition(() => {
        setBaseUrl(url);
        setAccessToken(token.access_token);
        setCurrentUser(user);
      });
      navigate("/lobby");
    });
  }

  async function handleGoogleLogin() {
    await runAction("Google login", async () => {
      const url = normalizeBaseUrl(baseUrl);
      const token = await loginWithGoogle(url);
      const user = await fetchMe(url, token.access_token);
      startTransition(() => {
        setBaseUrl(url);
        setAccessToken(token.access_token);
        setCurrentUser(user);
      });
      navigate("/lobby");
    });
  }

  return (
    <div className="mx-auto flex w-full max-w-lg flex-col gap-8 px-5 py-16">
      {/* Hero */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-bold uppercase tracking-[2px] text-gold">
          Card Table
        </span>
        <h1 className="text-6xl font-black tracking-tight text-gray-900 dark:text-white leading-none">
          Setback
        </h1>
        <p className="mt-1 max-w-sm text-base leading-relaxed text-slate-500 dark:text-blue-200/75">
          A classic trick-taking game. As played by the Bradley family. Grab a
          seat.
        </p>
      </div>

      {/* Sign-in glass card */}
      <div className="rounded-3xl backdrop-blur-xl border shadow-xl p-7 flex flex-col gap-5 bg-white/[0.65] border-white/75 shadow-black/[0.04] dark:bg-white/[0.06] dark:border-white/[0.10] dark:shadow-black/50">
        <div>
          <h2 className="text-xl font-extrabold text-gray-900 dark:text-white">
            Sign in to play
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-slate-500 dark:text-blue-200/65">
            Create a table, share a join code, and deal your first hand.
          </p>
        </div>

        <ActionButton
          busy={busyAction === "Google login"}
          label="Sign In With Google"
          onClick={() => {
            void handleGoogleLogin();
          }}
        />

        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="self-center text-xs font-bold uppercase tracking-wider text-slate-400 hover:text-slate-600 dark:text-slate-400/70 dark:hover:text-blue-100 transition-colors"
        >
          {showAdvanced ? "Hide options" : "More options"}
        </button>

        {showAdvanced && (
          <div className="flex flex-col gap-4 border-t border-slate-200/60 dark:border-white/[0.08] pt-5">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-bold uppercase tracking-wide text-gray-700 dark:text-blue-100/70">
                Guest name
              </label>
              <input
                type="text"
                autoComplete="off"
                value={devUsername}
                onChange={(e) => setDevUsername(e.target.value)}
                placeholder="player-one"
                className={inputClass}
              />
            </div>
            <ActionButton
              busy={busyAction === "Dev login"}
              label="Continue As Guest"
              onClick={() => {
                void handleDevLogin();
              }}
              tone="secondary"
            />
            <div className="flex flex-col gap-1.5 mt-2">
              <label className="text-xs font-bold uppercase tracking-wide text-gray-700 dark:text-blue-100/70">
                Server
              </label>
              <input
                type="text"
                autoComplete="off"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://localhost"
                className={inputClass}
              />
              <p className="text-xs text-slate-400 dark:text-slate-400/70 leading-relaxed">
                Point this at a custom server if you are not running the default
                local backend.
              </p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-2xl border px-4 py-3 bg-red-50 border-red-200/60 dark:bg-red-game/[0.15] dark:border-red-game/25">
          <p className="text-sm font-semibold text-red-700 dark:text-white">
            {error}
          </p>
        </div>
      )}
    </div>
  );
}

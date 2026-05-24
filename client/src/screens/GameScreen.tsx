import { startTransition, useDeferredValue, useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { ActionButton } from "../components/ActionButton";
import { PlayingCard } from "../components/PlayingCard";
import { useAuth } from "../context/auth";
import { useGameSubscription } from "../hooks/useGameSubscription";
import { bidGame, fetchGameState, playCard } from "../lib/api";
import {
  formatCard,
  formatPhase,
  formatSuitSymbol,
  getCurrentTurnPlayer,
  getMyHand,
  isCardPlayable,
  normalizeBaseUrl,
} from "../lib/format";
import type {
  GameEvent,
  GameStatePlayerScoped,
  SetbackCard,
} from "../types/setback";

const BID_OPTIONS = [0, 2, 3, 4] as const;

type SubscriptionStatus = "idle" | "connecting" | "live" | "error";

const suitNames = {
  club: "clubs",
  diamond: "diamonds",
  heart: "hearts",
  spade: "spades",
} as const;

const glassPanel = [
  "rounded-3xl backdrop-blur-xl border shadow-xl flex flex-col gap-4",
  "bg-white/[0.65] border-white/75 shadow-black/[0.04]",
  "dark:bg-white/[0.06] dark:border-white/[0.10] dark:shadow-black/50",
].join(" ");

export function GameScreen() {
  const { accessToken, baseUrl, currentUser } = useAuth();
  const { gameId: gameIdParam } = useParams<{ gameId: string }>();
  const navigate = useNavigate();

  const activeGameId = gameIdParam ?? null;

  const [gameState, setGameState] = useState<GameStatePlayerScoped | null>(
    null,
  );
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const deferredGameState = useDeferredValue(gameState);

  useEffect(() => {
    if (!activeGameId || !accessToken) return;
    fetchGameState(normalizeBaseUrl(baseUrl), accessToken, activeGameId)
      .then((state) => {
        startTransition(() => {
          setGameState(state);
        });
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load game state",
        );
      });
  }, [accessToken, activeGameId, baseUrl]);

  const subscription = useGameSubscription({
    accessToken,
    baseUrl,
    enabled: Boolean(accessToken && activeGameId),
    gameId: activeGameId,
    onError: (message) => {
      setError(message);
    },
    onEvent: (event: GameEvent) => {
      if (!("active_round" in event.data)) return;
      startTransition(() => {
        setGameState(event.data as GameStatePlayerScoped);
      });
    },
  });

  if (!activeGameId || !currentUser) return <Navigate to="/lobby" replace />;
  const gameId = activeGameId;

  async function runAction(label: string, action: () => Promise<void>) {
    setBusyAction(label);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleBid(amount: (typeof BID_OPTIONS)[number]) {
    await runAction(`Bid ${amount}`, async () => {
      const state = await bidGame(normalizeBaseUrl(baseUrl), accessToken, {
        amount,
        game_id: gameId,
      });
      startTransition(() => {
        setGameState(state);
      });
    });
  }

  async function handlePlayCard(card: SetbackCard) {
    await runAction(`Play ${formatCard(card)}`, async () => {
      const state = await playCard(normalizeBaseUrl(baseUrl), accessToken, {
        card,
        game_id: gameId,
      });
      startTransition(() => {
        setGameState(state);
      });
    });
  }

  function handleLeaveTable() {
    navigate(activeGameId ? `/lobby/${activeGameId}` : "/lobby");
  }

  if (!deferredGameState) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-5 py-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black tracking-tight text-gray-900 dark:text-white">
              Setback
            </h1>
            <p className="text-sm text-slate-500 dark:text-blue-200/70">
              Connecting…
            </p>
          </div>
          <div className="flex items-center gap-3">
            <StreamIndicator status={subscription.status} />
            <ActionButton
              label="Leave"
              onClick={handleLeaveTable}
              tone="ghost"
            />
          </div>
        </div>
        <div className={`${glassPanel} p-8 items-center justify-center`}>
          <p className="text-sm text-slate-400 dark:text-slate-400/70">
            Waiting for game state…
          </p>
        </div>
      </div>
    );
  }

  const gs = deferredGameState;
  const currentPlayer = getCurrentTurnPlayer(gs);
  const myHand = getMyHand(gs);
  const trump = gs.active_round.trump;
  const trick = gs.active_round.trick?.collection ?? [];
  const bidHistory = gs.active_round.bid.collection;
  const scoreEntries = Object.entries(gs.score);
  const isComplete = gs.phase === "complete";
  const yourTurn = currentPlayer?.player_id === currentUser.sub;
  const canPlay = gs.phase === "play" && yourTurn;
  const dealer = gs.order.order[gs.active_round.dealer.idx];
  const trumpIsRed = trump === "heart" || trump === "diamond";

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-5 py-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-gray-900 dark:text-white">
            Setback
          </h1>
          <p className="text-sm text-slate-500 dark:text-blue-200/70">
            {formatPhase(gs.phase)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StreamIndicator status={subscription.status} />
          <ActionButton label="Leave" onClick={handleLeaveTable} tone="ghost" />
        </div>
      </div>

      {/* Score row */}
      <div className="flex flex-wrap gap-2.5">
        {scoreEntries.length > 0 ? (
          scoreEntries.map(([teamId, score]) => (
            <div
              key={teamId}
              className="flex-1 min-w-[110px] rounded-2xl backdrop-blur-md border px-4 py-3 bg-white/[0.60] border-white/70 dark:bg-white/[0.07] dark:border-gold/20"
            >
              <p className="text-xs font-bold uppercase tracking-wide text-slate-400 dark:text-blue-200/70">
                Team {teamId}
              </p>
              <p className="mt-1 text-2xl font-extrabold text-gray-900 dark:text-white">
                {score}
              </p>
            </div>
          ))
        ) : (
          <div className="flex-1 min-w-[110px] rounded-2xl backdrop-blur-md border px-4 py-3 bg-white/[0.60] border-white/70 dark:bg-white/[0.07] dark:border-gold/20">
            <p className="text-xs font-bold uppercase tracking-wide text-slate-400 dark:text-blue-200/70">
              Score
            </p>
            <p className="mt-1 text-2xl font-extrabold text-gray-900 dark:text-white">
              —
            </p>
          </div>
        )}
        <div className="flex-1 min-w-[110px] rounded-2xl backdrop-blur-md border px-4 py-3 bg-white/[0.60] border-white/70 dark:bg-white/[0.07] dark:border-gold/20">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-400 dark:text-blue-200/70">
            Target
          </p>
          <p className="mt-1 text-2xl font-extrabold text-gray-900 dark:text-white">
            {gs.max_score}
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border px-4 py-3 bg-red-50 border-red-200/60 dark:bg-red-game/[0.15] dark:border-red-game/25">
          <p className="text-sm font-semibold text-red-700 dark:text-white">
            {error}
          </p>
        </div>
      )}
      {notice && !error && (
        <div className="rounded-2xl border px-4 py-3 bg-emerald-50 border-emerald-200/60 dark:bg-emerald-500/[0.15] dark:border-emerald-500/25">
          <p className="text-sm font-semibold text-emerald-700 dark:text-white">
            {notice}
          </p>
        </div>
      )}

      {isComplete ? (
        <div className={`${glassPanel} p-8 items-center gap-5`}>
          <span className="text-xs font-extrabold uppercase tracking-[1.6px] text-red-game">
            Final
          </span>
          <h2 className="text-3xl font-extrabold text-gray-900 dark:text-white">
            Game over
          </h2>
          <div className="flex flex-wrap justify-center gap-4">
            {scoreEntries.map(([teamId, score]) => (
              <div
                key={teamId}
                className="flex min-w-[120px] flex-col items-center rounded-2xl border px-6 py-4 bg-white/50 border-white/60 dark:bg-white/[0.05] dark:border-white/[0.09]"
              >
                <p className="text-xs font-bold uppercase tracking-wide text-slate-400 dark:text-blue-200/60">
                  Team {teamId}
                </p>
                <p className="mt-1.5 text-4xl font-extrabold text-gray-900 dark:text-white">
                  {score}
                </p>
              </div>
            ))}
          </div>
          <ActionButton label="Back To Lobby" onClick={handleLeaveTable} />
        </div>
      ) : (
        <>
          {/* Round info + players */}
          <div className={`${glassPanel} p-5`}>
            <div className="flex flex-wrap gap-6">
              <div className="flex flex-col gap-1 min-w-[130px]">
                <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400 dark:text-blue-200/60">
                  Trump
                </p>
                {trump ? (
                  <div
                    className={[
                      "flex items-center gap-2",
                      trumpIsRed
                        ? "text-[#b43c2a]"
                        : "text-[#0d1d31] dark:text-white",
                    ].join(" ")}
                  >
                    <span className="text-2xl font-extrabold">
                      {formatSuitSymbol(trump)}
                    </span>
                    <span className="text-xl font-extrabold capitalize">
                      {suitNames[trump]}
                    </span>
                  </div>
                ) : (
                  <p className="text-xl font-extrabold text-gray-900 dark:text-white">
                    Not set
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-1 min-w-[130px]">
                <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400 dark:text-blue-200/60">
                  Dealer
                </p>
                <p className="text-xl font-extrabold text-gray-900 dark:text-white">
                  {dealer ? dealer.player_id : "—"}
                </p>
              </div>
              <div className="flex flex-col gap-1 min-w-[130px]">
                <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400 dark:text-blue-200/60">
                  Up next
                </p>
                <p className="text-xl font-extrabold text-gray-900 dark:text-white">
                  {currentPlayer ? currentPlayer.player_id : "Pending"}
                </p>
                {yourTurn && (
                  <p className="text-xs font-extrabold uppercase tracking-wide text-red-game">
                    Your turn
                  </p>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {gs.order.order.map((player) => {
                const active = player.player_id === currentPlayer?.player_id;
                return (
                  <div
                    key={player.player_id}
                    className={[
                      "rounded-xl px-3 py-2.5 flex flex-col gap-0.5 transition-colors border",
                      active
                        ? "bg-navy-800/90 border-navy-600/40 dark:bg-navy-700/70 dark:border-white/10"
                        : "bg-white/40 border-white/60 dark:bg-white/[0.04] dark:border-white/[0.07]",
                    ].join(" ")}
                  >
                    <p
                      className={[
                        "text-sm font-bold",
                        active ? "text-white" : "text-gray-900 dark:text-white",
                      ].join(" ")}
                    >
                      {player.player_id}
                    </p>
                    <p
                      className={[
                        "text-[11px] font-semibold uppercase",
                        active
                          ? "text-navy-200/80"
                          : "text-slate-400 dark:text-blue-200/55",
                      ].join(" ")}
                    >
                      Team {player.team_id}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Bidding */}
          {gs.phase === "bid" && (
            <div className={`${glassPanel} p-5`}>
              <div>
                <h3 className="text-base font-extrabold text-gray-900 dark:text-white">
                  Bidding
                </h3>
                <p className="mt-0.5 text-sm text-slate-500 dark:text-blue-200/65">
                  Pass or bid how many points your team will take this round.
                </p>
              </div>
              <div className="flex flex-wrap gap-2.5">
                {BID_OPTIONS.map((amount) => (
                  <ActionButton
                    key={amount}
                    busy={busyAction === `Bid ${amount}`}
                    label={amount === 0 ? "Pass" : `Bid ${amount}`}
                    onClick={() => {
                      void handleBid(amount);
                    }}
                    tone={amount === 0 ? "ghost" : "secondary"}
                  />
                ))}
              </div>
              {bidHistory.length > 0 && (
                <RoundActivityTable
                  rows={bidHistory.map((b) => ({
                    player: b.player_id,
                    action: b.amount === 0 ? "Pass" : "Bid",
                    detail: b.amount === 0 ? "—" : String(b.amount),
                  }))}
                />
              )}
            </div>
          )}

          {/* Current trick */}
          {trick.length > 0 && (
            <div className={`${glassPanel} p-5`}>
              <h3 className="text-base font-extrabold text-gray-900 dark:text-white">
                Current trick
              </h3>
              <RoundActivityTable
                rows={trick.map((c) => ({
                  player: c.player_id,
                  action: "Played",
                  detail: formatCard(c),
                }))}
              />
            </div>
          )}

          {/* Hand */}
          {myHand.length > 0 && (
            <div className={`${glassPanel} p-5`}>
              <div>
                <h3 className="text-base font-extrabold text-gray-900 dark:text-white">
                  Your hand
                </h3>
                <p className="mt-0.5 text-sm text-slate-500 dark:text-blue-200/65">
                  {gs.phase === "bid"
                    ? "Review your cards, then pass or bid."
                    : canPlay
                      ? "Click a card to play it."
                      : `Waiting on ${currentPlayer?.player_id ?? "the next player"}.`}
                </p>
              </div>
              <div className="flex flex-wrap gap-2.5">
                {myHand.map((card, i) => (
                  <PlayingCard
                    key={`${card.suit}-${card.value}-${i}`}
                    busy={busyAction === `Play ${formatCard(card)}`}
                    card={card}
                    disabled={!canPlay}
                    onPress={
                      canPlay && isCardPlayable(card, myHand, trick, trump)
                        ? () => {
                            void handlePlayCard(card);
                          }
                        : undefined
                    }
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

type ActivityRow = { player: string; action: string; detail: string };

function RoundActivityTable({ rows }: { rows: ActivityRow[] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-[10px] font-bold uppercase tracking-wide text-slate-400 dark:text-slate-400/70">
          <th className="pb-1.5 pr-4">Player</th>
          <th className="pb-1.5 pr-4">Action</th>
          <th className="pb-1.5">Detail</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr
            key={i}
            className="border-t border-slate-200/60 dark:border-white/[0.08]"
          >
            <td className="py-1.5 pr-4 font-semibold text-gray-900 dark:text-white">
              {row.player}
            </td>
            <td className="py-1.5 pr-4 text-slate-500 dark:text-blue-200/60">
              {row.action}
            </td>
            <td className="py-1.5 font-mono font-bold text-gray-900 dark:text-white">
              {row.detail}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function StreamIndicator({ status }: { status: SubscriptionStatus }) {
  const { color, label } = {
    live: { color: "bg-emerald-400", label: "Live" },
    connecting: { color: "bg-yellow-400", label: "Connecting" },
    error: { color: "bg-red-400", label: "Reconnecting" },
    idle: { color: "bg-slate-400", label: "Offline" },
  }[status];

  return (
    <div className="flex items-center gap-1.5 rounded-full backdrop-blur-md border px-3 py-1.5 bg-white/60 border-white/70 dark:bg-black/30 dark:border-white/[0.12]">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      <span className="text-xs font-bold tracking-wide text-slate-600 dark:text-blue-100/80">
        {label}
      </span>
    </div>
  );
}

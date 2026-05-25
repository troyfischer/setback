import { startTransition, useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ActionButton } from "../components/ActionButton";
import { ToastContainer } from "../components/Toast";
import { useAuth } from "../context/auth";
import { useToasts } from "../hooks/useToasts";
import {
  createGame,
  createTeam,
  deleteGame,
  deleteTeam,
  fetchUserRelevantGames,
  fetchLobbyState,
  joinGame,
  joinTeam,
  leaveTeam,
  logout,
  startGame,
} from "../lib/api";
import { normalizeBaseUrl } from "../lib/format";
import type { GameRecord, LobbyState } from "../types/setback";

const glassPanel = [
  "rounded-3xl backdrop-blur-xl border shadow-xl flex flex-col gap-4",
  "bg-white/[0.65] border-white/75 shadow-black/[0.04]",
  "dark:bg-white/[0.06] dark:border-white/[0.10] dark:shadow-black/50",
].join(" ");

const glassInner = [
  "rounded-2xl border",
  "bg-white/50 border-white/60",
  "dark:bg-white/[0.04] dark:border-white/[0.07]",
].join(" ");

const inputClass = [
  "rounded-2xl border px-4 py-3 text-base outline-none transition w-full",
  "bg-white/70 border-slate-200/80 text-gray-900 placeholder-slate-400",
  "focus:border-slate-400/60 focus:ring-2 focus:ring-slate-200/50",
  "dark:bg-white/[0.07] dark:border-white/10 dark:text-white dark:placeholder-white/30",
  "dark:focus:border-white/25 dark:focus:ring-white/[0.08]",
].join(" ");

export function LobbyScreen() {
  const { accessToken, baseUrl, currentUser, setAccessToken, setCurrentUser } =
    useAuth();
  const { gameId: gameIdParam } = useParams<{ gameId?: string }>();
  const navigate = useNavigate();

  const activeGameId = gameIdParam ?? null;

  const [joinCode, setJoinCode] = useState("");
  const [createdGame, setCreatedGame] = useState<GameRecord | null>(null);
  const [lobbyState, setLobbyState] = useState<LobbyState | null>(null);
  const [activeGames, setActiveGames] = useState<GameRecord[]>([]);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const {
    toasts,
    dismissToast,
    notice: pushNotice,
    error: pushError,
  } = useToasts();

  const inTable = Boolean(activeGameId);
  const shareCode =
    createdGame && createdGame.id === activeGameId ? createdGame.id : null;
  const displayName =
    currentUser?.given_name ||
    currentUser?.name ||
    currentUser?.sub ||
    "player";

  const refreshLobby = useCallback(async () => {
    if (!accessToken || !activeGameId) return;
    try {
      const state = await fetchLobbyState(
        normalizeBaseUrl(baseUrl),
        accessToken,
        activeGameId,
      );
      setLobbyState(state);
    } catch {
      // Silently ignore stale data
    }
  }, [accessToken, activeGameId, baseUrl]);

  useEffect(() => {
    if (!accessToken || inTable) return;
    void fetchUserRelevantGames(normalizeBaseUrl(baseUrl), accessToken).then(
      setActiveGames,
    );
  }, [accessToken, baseUrl, inTable]);

  // Poll lobby state while waiting
  useEffect(() => {
    if (!accessToken || !activeGameId) return;
    void refreshLobby();
    const id = setInterval(() => {
      void refreshLobby();
    }, 3000);
    return () => {
      clearInterval(id);
    };
  }, [accessToken, activeGameId, refreshLobby]);

  // Non-owners auto-navigate when the owner starts the game
  useEffect(() => {
    if (lobbyState?.game_status !== "active" || !activeGameId) return;
    if (currentUser && lobbyState.game_owner === currentUser.sub) return;
    navigate(`/game/${activeGameId}`);
  }, [
    activeGameId,
    currentUser,
    lobbyState?.game_owner,
    lobbyState?.game_status,
    navigate,
  ]);

  async function runAction(label: string, action: () => Promise<void>) {
    setBusyAction(label);
    try {
      await action();
    } catch (caught) {
      pushError(caught instanceof Error ? caught.message : "Unknown error");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleLogout() {
    await runAction("Logout", async () => {
      const url = normalizeBaseUrl(baseUrl);
      try {
        await logout(url, accessToken);
      } catch {
        /* ignore */
      }
      startTransition(() => {
        setAccessToken("");
        setCurrentUser(null);
      });
      navigate("/");
    });
  }

  async function handleCreateGame() {
    await runAction("Create game", async () => {
      const url = normalizeBaseUrl(baseUrl);
      const game = await createGame(url, accessToken);
      await joinGame(url, accessToken, { game_id: game.id });
      startTransition(() => {
        setCreatedGame(game);
      });
      pushNotice("Created table. Share the join code with your players.");
      navigate(`/lobby/${game.id}`);
    });
  }

  async function handleJoinGame() {
    await runAction("Join game", async () => {
      const url = normalizeBaseUrl(baseUrl);
      const gameId = joinCode.trim();
      if (!gameId) throw new Error("Paste the join code your host shared.");
      await joinGame(url, accessToken, { game_id: gameId });
      pushNotice("Joined table.");
      navigate(`/lobby/${gameId}`);
    });
  }

  async function handleCreateTeam() {
    await runAction("Create team", async () => {
      if (!activeGameId) throw new Error("Join a game before creating a team.");
      const team = await createTeam(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
      });
      pushNotice(`Created team ${team.team_number}.`);
      await refreshLobby();
    });
  }

  async function handleJoinTeam(teamNumber: number) {
    await runAction(`Join team ${teamNumber}`, async () => {
      if (!activeGameId) throw new Error("Join a game before joining a team.");
      await joinTeam(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
        team_number: teamNumber,
      });
      pushNotice(`Joined team ${teamNumber}.`);
      await refreshLobby();
    });
  }

  async function handleLeaveTeam(teamNumber: number) {
    await runAction("Leave team", async () => {
      if (!activeGameId) throw new Error("Not in a game.");
      await leaveTeam(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
        team_number: teamNumber,
      });
      pushNotice(`Left team ${teamNumber}.`);
      await refreshLobby();
    });
  }

  async function handleDeleteTeam(teamNumber: number) {
    await runAction(`Delete team ${teamNumber}`, async () => {
      if (!activeGameId) throw new Error("Not in a game.");
      await deleteTeam(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
        team_number: teamNumber,
      });
      pushNotice(`Deleted team ${teamNumber}.`);
      await refreshLobby();
    });
  }

  async function handleDeleteGame() {
    await runAction("Delete game", async () => {
      if (!activeGameId) throw new Error("Not in a game.");
      await deleteGame(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
      });
      navigate("/lobby");
    });
  }

  async function handleStartGame() {
    await runAction("Start game", async () => {
      if (!activeGameId) throw new Error("Create or join a game first.");
      await startGame(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
      });
      navigate(`/game/${activeGameId}`);
    });
  }

  function handleLeaveTable() {
    navigate("/lobby");
    pushNotice("Left the table.");
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-5 px-5 py-10">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-gray-900 dark:text-white">
            Setback
          </h1>
          <p className="text-sm text-slate-500 dark:text-blue-200/70 mt-0.5">
            Welcome, {displayName}.
          </p>
        </div>
        <ActionButton
          busy={busyAction === "Logout"}
          label="Sign Out"
          onClick={() => {
            void handleLogout();
          }}
          tone="ghost"
        />
      </div>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {!inTable ? (
        <>
          {/* Host */}
          <div className={`${glassPanel} p-6`}>
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-[1.6px] text-red-game">
                Host
              </span>
              <h2 className="text-xl font-extrabold text-gray-900 dark:text-white mt-0.5">
                Start a new table
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-blue-200/65 leading-relaxed">
                Create a table and share the join code so the other three seats
                can fill.
              </p>
            </div>
            <ActionButton
              busy={busyAction === "Create game"}
              label="Create Game"
              onClick={() => {
                void handleCreateGame();
              }}
            />
          </div>

          {activeGames.length > 0 && (
            <div className={`${glassPanel} p-6 gap-3`}>
              <div>
                <span className="text-[10px] font-extrabold uppercase tracking-[1.6px] text-red-game">
                  In Progress
                </span>
                <h2 className="text-xl font-extrabold text-gray-900 dark:text-white mt-0.5">
                  Rejoin a game
                </h2>
              </div>
              {activeGames.map((game) => (
                <div
                  key={game.id}
                  className={`flex items-center justify-between ${glassInner} px-4 py-3`}
                >
                  <span className="text-sm font-semibold text-gray-900 dark:text-white">
                    {game.status === "active"
                      ? "In Progress"
                      : "Waiting to Start"}
                  </span>
                  <div className="flex gap-2">
                    {currentUser && game.owner === currentUser.sub && (
                      <ActionButton
                        busy={busyAction === `Delete game ${game.id}`}
                        label="Delete"
                        tone="ghost"
                        onClick={() =>
                          void runAction(`Delete game ${game.id}`, async () => {
                            await deleteGame(
                              normalizeBaseUrl(baseUrl),
                              accessToken,
                              { game_id: game.id },
                            );
                            setActiveGames((prev) =>
                              prev.filter((g) => g.id !== game.id),
                            );
                          })
                        }
                      />
                    )}
                    <ActionButton
                      label="Rejoin"
                      onClick={() =>
                        navigate(
                          game.status === "active"
                            ? `/game/${game.id}`
                            : `/lobby/${game.id}`,
                        )
                      }
                      tone="secondary"
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-slate-200/80 dark:bg-white/[0.10]" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-400/70">
              or
            </span>
            <div className="h-px flex-1 bg-slate-200/80 dark:bg-white/[0.10]" />
          </div>

          {/* Join */}
          <div className={`${glassPanel} p-6`}>
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-[1.6px] text-red-game">
                Guest
              </span>
              <h2 className="text-xl font-extrabold text-gray-900 dark:text-white mt-0.5">
                Join a table
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-blue-200/65 leading-relaxed">
                Paste the join code your host shared.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-bold uppercase tracking-wide text-gray-700 dark:text-blue-100/70">
                Join code
              </label>
              <input
                type="text"
                autoComplete="off"
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value)}
                placeholder="abc123xyz"
                className={inputClass}
              />
            </div>
            <ActionButton
              busy={busyAction === "Join game"}
              label="Join Game"
              onClick={() => {
                void handleJoinGame();
              }}
              tone="secondary"
            />
          </div>
        </>
      ) : (
        <div className={`${glassPanel} p-6 gap-5`}>
          <div>
            {lobbyState && lobbyState.players.length > 0 ? (
              <div className="mt-2">
                <p className="pb-2 text-left text-[10px] font-bold uppercase tracking-wide text-slate-500 dark:text-blue-200/60">
                  Active Players
                </p>
                <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3">
                  {lobbyState.players.map((player) => (
                    <div
                      key={player}
                      className="flex min-h-14 min-w-0 items-center rounded-2xl border border-slate-200/80 bg-white/55 px-4 py-3 shadow-sm dark:border-white/[0.08] dark:bg-white/[0.05]"
                    >
                      <div className="inline-flex max-w-full min-w-0 items-center justify-center rounded-full bg-blue-300 px-3 py-1.5 text-xs font-extrabold text-blue-950 dark:bg-blue-700 dark:text-blue-100">
                        <span className="truncate font-semibold text-gray-900 dark:text-white">
                          {player}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <h2 className="text-2xl font-extrabold text-gray-900 dark:text-white mt-0.5">
                Waiting for players...
              </h2>
            )}
            <p className="mt-1 text-sm text-slate-500 dark:text-blue-200/65 leading-relaxed">
              Set up teams, then start the game when everyone is seated.
            </p>
          </div>

          {shareCode && (
            <div className="rounded-2xl bg-navy-800/90 backdrop-blur-sm border border-navy-600/40 dark:bg-navy-900/80 dark:border-white/10 px-5 py-4">
              <p className="text-[10px] font-bold uppercase tracking-[1.4px] text-gold">
                Share this join code
              </p>
              <p className="mt-1 font-mono text-2xl font-extrabold text-white tracking-wide">
                {shareCode}
              </p>
            </div>
          )}

          {/* Teams section */}
          <div className={`${glassInner} p-4 flex flex-col gap-4`}>
            <div>
              <h3 className="text-base font-extrabold text-gray-900 dark:text-white">
                Teams
              </h3>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-blue-200/60 leading-relaxed">
                Join an open team or create a new one for you and a partner.
              </p>
            </div>

            {lobbyState && lobbyState.teams.length > 0 && (
              <div className="grid grid-cols-2 gap-3">
                {lobbyState.teams.map((team) => {
                  const isMember =
                    currentUser && team.members.includes(currentUser.sub);
                  const isFull = team.members.length >= 2;
                  const isGameOwner =
                    currentUser && lobbyState.game_owner === currentUser.sub;
                  return (
                    <div
                      key={team.id}
                      className="overflow-hidden rounded-2xl shadow-sm backdrop-blur-sm border bg-white/40 border-white/60 dark:bg-white/[0.05] dark:border-white/[0.09]"
                    >
                      <div className="flex items-center justify-between bg-navy-800/90 dark:bg-navy-700/70 px-4 py-2.5">
                        <span className="text-sm font-extrabold text-white">
                          Team {team.team_number}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-navy-200/80">
                            {team.members.length}/2
                          </span>
                          {isMember ? (
                            <button
                              type="button"
                              onClick={() => {
                                void handleLeaveTeam(team.team_number);
                              }}
                              disabled={busyAction === "Leave team"}
                              className="text-[10px] font-bold uppercase tracking-wide text-gold hover:text-white transition-colors disabled:opacity-50"
                            >
                              Leave
                            </button>
                          ) : (
                            !isFull && (
                              <button
                                type="button"
                                onClick={() => {
                                  void handleJoinTeam(team.team_number);
                                }}
                                disabled={
                                  busyAction === `Join team ${team.team_number}`
                                }
                                className="text-[10px] font-bold uppercase tracking-wide text-gold hover:text-white transition-colors disabled:opacity-50"
                              >
                                Join
                              </button>
                            )
                          )}
                          {isGameOwner && (
                            <button
                              type="button"
                              onClick={() => {
                                void handleDeleteTeam(team.team_number);
                              }}
                              disabled={
                                busyAction === `Delete team ${team.team_number}`
                              }
                              className="text-[10px] font-bold uppercase tracking-wide text-red-400 hover:text-red-300 transition-colors disabled:opacity-50"
                            >
                              Delete
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="divide-y divide-white/20 dark:divide-white/[0.06]">
                        {[0, 1].map((slot) => {
                          const member = team.members[slot];
                          return member ? (
                            <div
                              key={slot}
                              className="flex items-center gap-3 px-4 py-2.5"
                            >
                              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-navy-100/80 dark:bg-navy-600/50 text-sm font-extrabold text-navy-800 dark:text-blue-100">
                                {member[0]!.toUpperCase()}
                              </div>
                              <span className="truncate text-sm font-semibold text-gray-900 dark:text-white">
                                {member}
                              </span>
                            </div>
                          ) : (
                            <div
                              key={slot}
                              className="flex items-center gap-3 px-4 py-2.5"
                            >
                              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-dashed border-slate-300/60 dark:border-white/15" />
                              <span className="text-sm italic text-slate-400 dark:text-slate-400/60">
                                Open seat
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="flex items-center justify-between">
              <ActionButton
                busy={busyAction === "Create team"}
                label="+ New Team"
                onClick={() => {
                  void handleCreateTeam();
                }}
                tone="secondary"
              />
              {lobbyState && lobbyState.players.length > 0 && (
                <p className="text-xs text-slate-400 dark:text-slate-400/70">
                  <span className="font-bold">{lobbyState.players.length}</span>{" "}
                  player{lobbyState.players.length !== 1 ? "s" : ""} in the game
                </p>
              )}
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            {currentUser && lobbyState?.game_owner === currentUser.sub && (
              <>
                <ActionButton
                  busy={busyAction === "Start game"}
                  label="Start Game"
                  onClick={() => {
                    void handleStartGame();
                  }}
                />
                <ActionButton
                  busy={busyAction === "Delete game"}
                  label="Delete Game"
                  onClick={() => {
                    void handleDeleteGame();
                  }}
                  tone="ghost"
                />
              </>
            )}
            <ActionButton
              label="Leave Table"
              onClick={handleLeaveTable}
              tone="ghost"
            />
          </div>
        </div>
      )}
    </div>
  );
}

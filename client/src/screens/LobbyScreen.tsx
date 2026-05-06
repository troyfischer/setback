import { startTransition, useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ActionButton } from "../components/ActionButton";
import { useAuth } from "../context/auth";
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

export function LobbyScreen() {
  const { accessToken, baseUrl, currentUser, setAccessToken, setCurrentUser } =
    useAuth();
  const { gameId: gameIdParam } = useParams<{ gameId?: string }>();
  const navigate = useNavigate();

  const activeGameId = gameIdParam ? Number.parseInt(gameIdParam, 10) : null;

  const [joinCode, setJoinCode] = useState("");
  const [createdGame, setCreatedGame] = useState<GameRecord | null>(null);
  const [lobbyState, setLobbyState] = useState<LobbyState | null>(null);
  const [activeGames, setActiveGames] = useState<GameRecord[]>([]);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const inTable = Boolean(activeGameId);
  const shareCode =
    createdGame?.join_code && createdGame.id === activeGameId
      ? `${createdGame.id}-${createdGame.join_code}`
      : null;
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
    if (!lobbyState?.game_started || !activeGameId) return;
    if (currentUser && lobbyState.game_owner === currentUser.sub) return;
    navigate(`/game/${activeGameId}`);
  }, [
    activeGameId,
    currentUser,
    lobbyState?.game_owner,
    lobbyState?.game_started,
    navigate,
  ]);

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
      await joinGame(url, accessToken, {
        game_id: game.id,
        secret: game.join_code,
      });
      startTransition(() => {
        setCreatedGame(game);
      });
      setNotice(
        `Created table #${game.id}. Share the join code with your players.`,
      );
      navigate(`/lobby/${game.id}`);
    });
  }

  async function handleJoinGame() {
    await runAction("Join game", async () => {
      const url = normalizeBaseUrl(baseUrl);
      const trimmed = joinCode.trim();
      const sep = trimmed.indexOf("-");
      if (sep === -1)
        throw new Error(
          "Invalid join code. Paste the full code your host shared.",
        );
      const gameId = Number.parseInt(trimmed.slice(0, sep), 10);
      const secret = trimmed.slice(sep + 1);
      if (!Number.isInteger(gameId) || !secret)
        throw new Error(
          "Invalid join code. Paste the full code your host shared.",
        );
      await joinGame(url, accessToken, { game_id: gameId, secret });
      setNotice(`Joined table #${gameId}.`);
      navigate(`/lobby/${gameId}`);
    });
  }

  async function handleCreateTeam() {
    await runAction("Create team", async () => {
      if (!activeGameId) throw new Error("Join a game before creating a team.");
      const team = await createTeam(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
      });
      setNotice(`Created team ${team.team_number}.`);
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
      setNotice(`Joined team ${teamNumber}.`);
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
      setNotice(`Left team ${teamNumber}.`);
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
      setNotice(`Deleted team ${teamNumber}.`);
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
    setNotice("Left the table.");
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-5 px-5 py-10">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-white">
            Setback
          </h1>
          <p className="text-sm text-[#d2deee] mt-0.5">
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

      {error && (
        <div className="rounded-2xl bg-[rgba(150,45,36,0.94)] px-4 py-3">
          <p className="text-sm font-semibold text-white">{error}</p>
        </div>
      )}
      {notice && !error && (
        <div className="rounded-2xl bg-[rgba(31,134,99,0.92)] px-4 py-3">
          <p className="text-sm font-semibold text-white">{notice}</p>
        </div>
      )}

      {!inTable ? (
        <>
          {/* Host */}
          <div className="rounded-3xl bg-[#fffaf2] p-6 shadow-xl flex flex-col gap-4">
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-[1.6px] text-[#b54434]">
                Host
              </span>
              <h2 className="text-xl font-extrabold text-[#102947] mt-0.5">
                Start a new table
              </h2>
              <p className="mt-1 text-sm text-[#4e647f] leading-relaxed">
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
            <div className="rounded-3xl bg-[#fffaf2] p-6 shadow-xl flex flex-col gap-3">
              <div>
                <span className="text-[10px] font-extrabold uppercase tracking-[1.6px] text-[#b54434]">
                  In Progress
                </span>
                <h2 className="text-xl font-extrabold text-[#102947] mt-0.5">
                  Rejoin a game
                </h2>
              </div>
              {activeGames.map((game) => (
                <div
                  key={game.id}
                  className="flex items-center justify-between rounded-2xl bg-[#eff4fa] px-4 py-3"
                >
                  <span className="text-sm font-semibold text-[#102947]">
                    Game #{game.id}
                  </span>
                  <ActionButton
                    label="Rejoin"
                    onClick={() => navigate(game.status === "active" ? `/game/${game.id}` : `/lobby/${game.id}`)}
                    tone="secondary"
                  />
                </div>
              ))}
            </div>
          )}

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-[rgba(247,215,116,0.28)]" />
            <span className="text-xs font-bold uppercase tracking-wider text-[#d2deee]">
              or
            </span>
            <div className="h-px flex-1 bg-[rgba(247,215,116,0.28)]" />
          </div>

          {/* Join */}
          <div className="rounded-3xl bg-[#fffaf2] p-6 shadow-xl flex flex-col gap-4">
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-[1.6px] text-[#b54434]">
                Guest
              </span>
              <h2 className="text-xl font-extrabold text-[#102947] mt-0.5">
                Join a table
              </h2>
              <p className="mt-1 text-sm text-[#4e647f] leading-relaxed">
                Paste the join code your host shared.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-bold uppercase tracking-wide text-[#0d1d31]">
                Join code
              </label>
              <input
                type="text"
                autoComplete="off"
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value)}
                placeholder="42-abc123xyz"
                className="rounded-2xl border border-[#bfd1e7] bg-[#edf3fa] px-4 py-3 text-base text-[#0d1d31] placeholder-[#8ca3bf] outline-none focus:border-[#102947] focus:ring-2 focus:ring-[#102947]/20 transition"
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
        <div className="rounded-3xl bg-[#fffaf2] p-6 shadow-xl flex flex-col gap-5">
          <div>
            <span className="text-[10px] font-extrabold uppercase tracking-[1.6px] text-[#b54434]">
              Table
            </span>
            <h2 className="text-2xl font-extrabold text-[#102947] mt-0.5">
              Game #{activeGameId}
            </h2>
            <p className="mt-1 text-sm text-[#4e647f] leading-relaxed">
              Set up teams, then start the game when everyone is seated.
            </p>
          </div>

          {shareCode && (
            <div className="rounded-2xl bg-[#102947] px-5 py-4">
              <p className="text-[10px] font-bold uppercase tracking-[1.4px] text-[#f7d774]">
                Share this join code
              </p>
              <p className="mt-1 font-mono text-2xl font-extrabold text-white tracking-wide">
                {shareCode}
              </p>
            </div>
          )}

          {/* Teams section */}
          <div className="rounded-2xl bg-[#eff4fa] p-4 flex flex-col gap-4">
            <div>
              <h3 className="text-base font-extrabold text-[#102947]">Teams</h3>
              <p className="mt-0.5 text-xs text-[#4e647f] leading-relaxed">
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
                      className="overflow-hidden rounded-2xl shadow-sm"
                    >
                      <div className="flex items-center justify-between bg-[#102947] px-4 py-2.5">
                        <span className="text-sm font-extrabold text-white">
                          Team {team.team_number}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-[#9fb6d4]">
                            {team.members.length}/2
                          </span>
                          {isMember ? (
                            <button
                              type="button"
                              onClick={() => {
                                void handleLeaveTeam(team.team_number);
                              }}
                              disabled={busyAction === "Leave team"}
                              className="text-[10px] font-bold uppercase tracking-wide text-[#f7d774] hover:text-white transition-colors disabled:opacity-50"
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
                                className="text-[10px] font-bold uppercase tracking-wide text-[#f7d774] hover:text-white transition-colors disabled:opacity-50"
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
                      <div className="divide-y divide-[#e8f0f8] bg-white">
                        {[0, 1].map((slot) => {
                          const member = team.members[slot];
                          return member ? (
                            <div
                              key={slot}
                              className="flex items-center gap-3 px-4 py-2.5"
                            >
                              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#c7d9f0] text-sm font-extrabold text-[#102947]">
                                {member[0]!.toUpperCase()}
                              </div>
                              <span className="truncate text-sm font-semibold text-[#102947]">
                                {member}
                              </span>
                            </div>
                          ) : (
                            <div
                              key={slot}
                              className="flex items-center gap-3 px-4 py-2.5"
                            >
                              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-dashed border-[#bfd1e7]" />
                              <span className="text-sm italic text-[#b0c4d8]">
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
                <p className="text-xs text-[#5c7593]">
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

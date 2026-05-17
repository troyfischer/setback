import { StatusBar } from "expo-status-bar";
import { LinearGradient } from "expo-linear-gradient";
import { startTransition, useDeferredValue, useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { GameScreen } from "./src/screens/GameScreen";
import { LobbyScreen } from "./src/screens/LobbyScreen";
import { WelcomeScreen } from "./src/screens/WelcomeScreen";
import { useGameSubscription } from "./src/hooks/useGameSubscription";
import {
  bidGame,
  createDevToken,
  createGame,
  createTeam,
  fetchLobbyState,
  fetchMe,
  joinGame,
  joinTeam,
  logout,
  playCard,
  refreshAccessToken,
  startGame,
} from "./src/lib/api";
import { loginWithGoogle } from "./src/lib/auth";
import {
  formatCard,
  getDefaultApiBaseUrl,
  normalizeBaseUrl,
} from "./src/lib/format";
import type {
  CurrentUser,
  GameEvent,
  GameRecord,
  GameStatePlayerScoped,
  LobbyState,
  SetbackCard,
} from "./src/types/setback";

const BID_OPTIONS = [0, 2, 3, 4] as const;

export default function App() {
  const [hydrated, setHydrated] = useState(false);
  const [baseUrl, setBaseUrl] = useState(getDefaultApiBaseUrl());
  const [guestName, setGuestName] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [joinCode, setJoinCode] = useState("");
  const [teamInput, setTeamInput] = useState({ number: "" });
  const [createdGame, setCreatedGame] = useState<GameRecord | null>(null);
  const [lobbyState, setLobbyState] = useState<LobbyState | null>(null);
  const [activeGameId, setActiveGameId] = useState<number | null>(null);
  const [gameState, setGameState] = useState<GameStatePlayerScoped | null>(
    null,
  );
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const deferredGameState = useDeferredValue(gameState);

  useEffect(() => {
    let cancelled = false;

    async function resume() {
      const url = normalizeBaseUrl(baseUrl);
      try {
        const token = await refreshAccessToken(url);
        if (cancelled) {
          return;
        }
        const user = await fetchMe(url, token.access_token);
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setAccessToken(token.access_token);
          setCurrentUser(user);
        });
      } catch {
        // No valid refresh cookie; fall through to welcome screen.
      } finally {
        if (!cancelled) {
          setHydrated(true);
        }
      }
    }

    void resume();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!accessToken || !activeGameId || gameState) return;

    const url = normalizeBaseUrl(baseUrl);
    let cancelled = false;

    async function poll() {
      try {
        const state = await fetchLobbyState(url, accessToken, activeGameId!);
        if (!cancelled) setLobbyState(state);
      } catch {
        // silently ignore — stale data is fine in the lobby
      }
    }

    void poll();
    const id = setInterval(() => {
      void poll();
    }, 3000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [accessToken, activeGameId, baseUrl, gameState]);

  const subscription = useGameSubscription({
    accessToken,
    baseUrl,
    enabled: Boolean(accessToken && activeGameId),
    gameId: activeGameId,
    onError: (message) => {
      setError(message);
    },
    onEvent: (event) => {
      if (!isScopedGameStateEvent(event)) {
        return;
      }

      startTransition(() => {
        setGameState(event.data);
      });
    },
  });

  async function runAction(label: string, action: () => Promise<void>) {
    setBusyAction(label);
    setError(null);
    setNotice(null);

    try {
      await action();
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Unknown error";
      setError(message);
    } finally {
      setBusyAction(null);
    }
  }

  function resetLocalGameContext() {
    setCreatedGame(null);
    setLobbyState(null);
    setActiveGameId(null);
    setGameState(null);
    setJoinCode("");
    setTeamInput({ number: "" });
  }

  async function handleDevLogin() {
    await runAction("Dev login", async () => {
      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      const trimmedName = guestName.trim();
      if (!trimmedName) {
        throw new Error("Enter a name to continue as guest.");
      }

      const token = await createDevToken(normalizedBaseUrl, trimmedName);
      const user = await fetchMe(normalizedBaseUrl, token.access_token);
      startTransition(() => {
        setBaseUrl(normalizedBaseUrl);
        setAccessToken(token.access_token);
        setCurrentUser(user);
      });

      setNotice(`Signed in as ${user.name || user.sub}.`);
    });
  }

  async function handleGoogleLogin() {
    await runAction("Google login", async () => {
      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      const token = await loginWithGoogle(normalizedBaseUrl);
      const user = await fetchMe(normalizedBaseUrl, token.access_token);

      startTransition(() => {
        setBaseUrl(normalizedBaseUrl);
        setAccessToken(token.access_token);
        setCurrentUser(user);
      });

      setNotice(`Signed in as ${user.name || user.sub}.`);
    });
  }

  async function handleLogout() {
    await runAction("Logout", async () => {
      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      if (accessToken) {
        try {
          await logout(normalizedBaseUrl, accessToken);
        } catch {
          // Server-side logout may fail if token is already gone; clear local state anyway.
        }
      }

      startTransition(() => {
        setBaseUrl(normalizedBaseUrl);
        setAccessToken("");
        setCurrentUser(null);
        setGuestName("");
        resetLocalGameContext();
      });

      setNotice("Signed out.");
    });
  }

  async function handleCreateGame() {
    await runAction("Create game", async () => {
      if (!accessToken) {
        throw new Error("Sign in before creating a game.");
      }

      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      const game = await createGame(normalizedBaseUrl, accessToken);
      await joinGame(normalizedBaseUrl, accessToken, {
        game_id: game.id,
        secret: game.join_code,
      });

      startTransition(() => {
        setCreatedGame(game);
        setLobbyState(null);
        setGameState(null);
        setActiveGameId(game.id);
        setJoinCode(`${game.id}-${game.join_code}`);
      });

      setNotice(
        `Created table #${game.id}. Share the join code with your players.`,
      );
    });
  }

  async function handleJoinGame() {
    await runAction("Join game", async () => {
      if (!accessToken) {
        throw new Error("Sign in before joining a game.");
      }

      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      const trimmed = joinCode.trim();
      const separatorIdx = trimmed.indexOf("-");
      if (separatorIdx === -1) {
        throw new Error(
          "Invalid join code. Paste the full code your host shared.",
        );
      }
      const gameId = Number.parseInt(trimmed.slice(0, separatorIdx), 10);
      const secret = trimmed.slice(separatorIdx + 1);
      if (!Number.isInteger(gameId) || !secret) {
        throw new Error(
          "Invalid join code. Paste the full code your host shared.",
        );
      }

      await joinGame(normalizedBaseUrl, accessToken, {
        game_id: gameId,
        secret,
      });

      startTransition(() => {
        setBaseUrl(normalizedBaseUrl);
        setActiveGameId(gameId);
      });

      setNotice(`Joined table #${gameId}.`);
    });
  }

  async function handleCreateTeam() {
    await runAction("Create team", async () => {
      if (!accessToken || !activeGameId) {
        throw new Error("Join a game before creating a team.");
      }

      const team = await createTeam(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
      });

      startTransition(() => {
        setTeamInput({ number: String(team.team_number) });
      });

      setNotice(`Created team ${team.team_number}.`);
    });
  }

  async function handleJoinTeam() {
    await runAction("Join team", async () => {
      if (!accessToken || !activeGameId) {
        throw new Error("Join a game before joining a team.");
      }

      const teamNumber = Number.parseInt(teamInput.number, 10);
      if (!Number.isInteger(teamNumber)) {
        throw new Error("Enter a numeric team number.");
      }

      await joinTeam(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
        team_number: teamNumber,
      });

      setNotice(`Joined team ${teamNumber}.`);
    });
  }

  async function handleStartGame() {
    await runAction("Start game", async () => {
      if (!accessToken || !activeGameId) {
        throw new Error("Create or join a game first.");
      }

      const state = await startGame(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
      });

      startTransition(() => {
        setGameState(state);
      });

      setNotice(`Started game #${activeGameId}.`);
    });
  }

  async function handleBid(amount: (typeof BID_OPTIONS)[number]) {
    await runAction(`Bid ${amount}`, async () => {
      if (!accessToken || !activeGameId) {
        throw new Error("Join a live game before bidding.");
      }

      const state = await bidGame(normalizeBaseUrl(baseUrl), accessToken, {
        amount,
        game_id: activeGameId,
      });

      startTransition(() => {
        setGameState(state);
      });
    });
  }

  async function handlePlayCard(card: SetbackCard) {
    await runAction(`Play ${formatCard(card)}`, async () => {
      if (!accessToken || !activeGameId) {
        throw new Error("Join a live game before playing a card.");
      }

      const state = await playCard(normalizeBaseUrl(baseUrl), accessToken, {
        card,
        game_id: activeGameId,
      });

      startTransition(() => {
        setGameState(state);
      });
    });
  }

  function handleLeaveTable() {
    resetLocalGameContext();
    setNotice("Left the table.");
  }

  if (!hydrated) {
    return (
      <LinearGradient
        colors={["#0f1b2e", "#132a4a", "#1b4d8c"]}
        style={styles.shell}
      >
        <View style={styles.loadingState}>
          <ActivityIndicator color="#f7d774" size="large" />
          <Text style={styles.loadingText}>Shuffling the deck…</Text>
        </View>
        <StatusBar style="light" />
      </LinearGradient>
    );
  }

  const showWelcome = !accessToken || !currentUser;
  const showGame = Boolean(activeGameId) && Boolean(deferredGameState);

  return (
    <LinearGradient
      colors={["#09111f", "#132a4a", "#7d2a24"]}
      style={styles.shell}
    >
      <StatusBar style="light" />
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {showWelcome ? (
          <WelcomeScreen
            baseUrl={baseUrl}
            busyAction={busyAction}
            devUsername={guestName}
            error={error}
            notice={notice}
            onChangeBaseUrl={setBaseUrl}
            onChangeDevUsername={setGuestName}
            onDevLogin={() => {
              void handleDevLogin();
            }}
            onGoogleLogin={() => {
              void handleGoogleLogin();
            }}
          />
        ) : showGame && activeGameId && deferredGameState && currentUser ? (
          <GameScreen
            activeGameId={activeGameId}
            busyAction={busyAction}
            currentUser={currentUser}
            error={error}
            gameState={deferredGameState}
            notice={notice}
            onBid={(amount) => {
              void handleBid(amount);
            }}
            onLeaveTable={handleLeaveTable}
            onPlayCard={(card) => {
              void handlePlayCard(card);
            }}
            streamStatus={subscription.status}
          />
        ) : (
          <LobbyScreen
            accessToken={accessToken}
            activeGameId={activeGameId}
            busyAction={busyAction}
            createdGame={createdGame}
            currentUser={currentUser}
            error={error}
            joinCode={joinCode}
            lobbyState={lobbyState}
            notice={notice}
            onChangeJoinCode={setJoinCode}
            onChangeTeamId={(value) =>
              setTeamInput((prev) => ({ ...prev, number: value }))
            }
            onCreateGame={() => {
              void handleCreateGame();
            }}
            onCreateTeam={() => {
              void handleCreateTeam();
            }}
            onJoinGame={() => {
              void handleJoinGame();
            }}
            onJoinTeam={() => {
              void handleJoinTeam();
            }}
            onLeaveTable={handleLeaveTable}
            onLogout={() => {
              void handleLogout();
            }}
            onStartGame={() => {
              void handleStartGame();
            }}
            teamIdInput={teamInput.number}
          />
        )}
      </ScrollView>
    </LinearGradient>
  );
}

function isScopedGameStateEvent(
  event: GameEvent,
): event is GameEvent & { data: GameStatePlayerScoped } {
  return "active_round" in event.data;
}

const styles = StyleSheet.create({
  loadingState: {
    alignItems: "center",
    flex: 1,
    justifyContent: "center",
    rowGap: 14,
  },
  loadingText: {
    color: "#f8fbff",
    fontSize: 16,
    fontWeight: "600",
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingVertical: 32,
  },
  shell: {
    flex: 1,
  },
});

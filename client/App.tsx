import { StatusBar } from 'expo-status-bar';
import { LinearGradient } from 'expo-linear-gradient';
import { startTransition, useDeferredValue, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { ActionButton } from './src/components/ActionButton';
import { SectionCard } from './src/components/SectionCard';
import { useGameSubscription } from './src/hooks/useGameSubscription';
import {
  bidGame,
  createDevToken,
  createGame,
  createTeam,
  joinGame,
  joinTeam,
  logout,
  playCard,
  refreshAccessToken,
  startGame,
} from './src/lib/api';
import { loginWithGoogle } from './src/lib/auth';
import {
  formatCard,
  formatPhase,
  formatTimestamp,
  getCurrentHand,
  getCurrentTurnPlayer,
  getDefaultApiBaseUrl,
  normalizeBaseUrl,
} from './src/lib/format';
import {
  clearStoredSession,
  loadStoredSession,
  saveStoredSession,
} from './src/lib/storage';
import type { GameRecord, GameState, SetbackCard, TeamRecord } from './src/types/setback';

const BID_OPTIONS = [0, 2, 3, 4] as const;

function StatusChip({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.statusChip}>
      <Text style={styles.statusLabel}>{label}</Text>
      <Text style={styles.statusValue}>{value}</Text>
    </View>
  );
}

export default function App() {
  const [hydrated, setHydrated] = useState(false);
  const [baseUrl, setBaseUrl] = useState(getDefaultApiBaseUrl());
  const [username, setUsername] = useState('player-one');
  const [accessToken, setAccessToken] = useState('');
  const [manualToken, setManualToken] = useState('');
  const [gameIdInput, setGameIdInput] = useState('');
  const [joinCode, setJoinCode] = useState('');
  const [teamIdInput, setTeamIdInput] = useState('');
  const [createdGame, setCreatedGame] = useState<GameRecord | null>(null);
  const [knownTeams, setKnownTeams] = useState<TeamRecord[]>([]);
  const [activeGameId, setActiveGameId] = useState<number | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activityLog, setActivityLog] = useState<string[]>([]);

  const deferredGameState = useDeferredValue(gameState);
  const currentPlayer = deferredGameState ? getCurrentTurnPlayer(deferredGameState) : null;
  const currentHand = deferredGameState ? getCurrentHand(deferredGameState) : [];
  const googleLoginAvailable = Platform.OS === 'web';

  useEffect(() => {
    let cancelled = false;

    async function hydrate() {
      const stored = await loadStoredSession();
      if (cancelled) {
        return;
      }

      if (stored) {
        startTransition(() => {
          setBaseUrl(stored.baseUrl || getDefaultApiBaseUrl());
          setUsername(stored.username || 'player-one');
          setAccessToken(stored.accessToken || '');
          setManualToken(stored.accessToken || '');
          setActiveGameId(stored.activeGameId ?? null);
          setGameIdInput(stored.activeGameId ? String(stored.activeGameId) : '');
        });
      }

      setHydrated(true);
    }

    void hydrate();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!hydrated) {
      return;
    }

    void saveStoredSession({
      accessToken,
      activeGameId,
      baseUrl: normalizeBaseUrl(baseUrl),
      username,
    });
  }, [accessToken, activeGameId, baseUrl, hydrated, username]);

  function logActivity(message: string) {
    const stamped = `${formatTimestamp()} ${message}`;
    setActivityLog((current) => [stamped, ...current].slice(0, 12));
  }

  async function runAction(label: string, action: () => Promise<void>) {
    setBusyAction(label);
    setError(null);
    setNotice(null);

    try {
      await action();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unknown error';
      setError(message);
      logActivity(`${label} failed: ${message}`);
    } finally {
      setBusyAction(null);
    }
  }

  const subscription = useGameSubscription({
    accessToken,
    baseUrl,
    enabled: Boolean(accessToken && activeGameId),
    gameId: activeGameId,
    onError: (message) => {
      setError(message);
    },
    onEvent: (event) => {
      startTransition(() => {
        setGameState(event.data);
      });
      logActivity(`Live update: ${event.event_type}`);
    },
  });

  async function handleDevLogin() {
    await runAction('Dev login', async () => {
      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      const trimmedUsername = username.trim();
      if (!trimmedUsername) {
        throw new Error('Enter a username for the dev token flow.');
      }

      const token = await createDevToken(normalizedBaseUrl, trimmedUsername);
      startTransition(() => {
        setBaseUrl(normalizedBaseUrl);
        setAccessToken(token.access_token);
        setManualToken(token.access_token);
      });

      setNotice(`Stored access token for ${trimmedUsername}.`);
      logActivity(`Authenticated as ${trimmedUsername}`);
    });
  }

  async function handleGoogleLogin() {
    await runAction('Google login', async () => {
      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      const token = await loginWithGoogle(normalizedBaseUrl);

      startTransition(() => {
        setBaseUrl(normalizedBaseUrl);
        setAccessToken(token.access_token);
        setManualToken(token.access_token);
      });

      setNotice('Signed in with Google.');
      logActivity('Authenticated with Google OIDC');
    });
  }

  async function handleRefreshToken() {
    await runAction('Refresh token', async () => {
      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      const token = await refreshAccessToken(normalizedBaseUrl);

      startTransition(() => {
        setBaseUrl(normalizedBaseUrl);
        setAccessToken(token.access_token);
        setManualToken(token.access_token);
      });

      setNotice('Access token refreshed from the Google session cookie.');
      logActivity('Refreshed Google access token');
    });
  }

  async function handleSaveManualToken() {
    await runAction('Store token', async () => {
      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      const trimmed = manualToken.trim();
      if (!trimmed) {
        throw new Error('Paste an access token before saving it.');
      }

      startTransition(() => {
        setBaseUrl(normalizedBaseUrl);
        setAccessToken(trimmed);
      });

      setNotice('Access token saved on this device.');
      logActivity('Stored a bearer token for API requests');
    });
  }

  async function handleClearSession() {
    await runAction('Clear session', async () => {
      await clearStoredSession();
      startTransition(() => {
        setAccessToken('');
        setManualToken('');
        setCreatedGame(null);
        setKnownTeams([]);
        setActiveGameId(null);
        setGameState(null);
        setGameIdInput('');
        setJoinCode('');
        setTeamIdInput('');
      });

      setNotice('Cleared the saved token and local game context.');
      logActivity('Cleared the local session');
    });
  }

  async function handleLogout() {
    await runAction('Logout', async () => {
      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      if (accessToken) {
        await logout(normalizedBaseUrl, accessToken);
      }

      await clearStoredSession();
      startTransition(() => {
        setBaseUrl(normalizedBaseUrl);
        setAccessToken('');
        setManualToken('');
        setCreatedGame(null);
        setKnownTeams([]);
        setActiveGameId(null);
        setGameState(null);
        setGameIdInput('');
        setJoinCode('');
        setTeamIdInput('');
      });

      setNotice('Logged out and cleared the local session.');
      logActivity('Logged out');
    });
  }

  async function handleCreateGame() {
    await runAction('Create game', async () => {
      if (!accessToken) {
        throw new Error('Authenticate before creating a game.');
      }

      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      const game = await createGame(normalizedBaseUrl, accessToken);
      await joinGame(normalizedBaseUrl, accessToken, {
        game_id: game.id,
        secret: game.join_code,
      });

      startTransition(() => {
        setCreatedGame(game);
        setKnownTeams([]);
        setGameState(null);
        setActiveGameId(game.id);
        setGameIdInput(String(game.id));
        setJoinCode(game.join_code);
      });

      setNotice(`Created and joined game ${game.id}.`);
      logActivity(`Created game ${game.id} with join code ${game.join_code}`);
    });
  }

  async function handleJoinGame() {
    await runAction('Join game', async () => {
      if (!accessToken) {
        throw new Error('Authenticate before joining a game.');
      }

      const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
      const gameId = Number.parseInt(gameIdInput, 10);
      if (!Number.isInteger(gameId)) {
        throw new Error('Enter a numeric game id.');
      }
      if (!joinCode.trim()) {
        throw new Error('Enter the join code for the table.');
      }

      await joinGame(normalizedBaseUrl, accessToken, {
        game_id: gameId,
        secret: joinCode.trim(),
      });

      startTransition(() => {
        setBaseUrl(normalizedBaseUrl);
        setActiveGameId(gameId);
      });

      setNotice(`Joined game ${gameId}.`);
      logActivity(`Joined game ${gameId}`);
    });
  }

  async function handleCreateTeam() {
    await runAction('Create team', async () => {
      if (!accessToken || !activeGameId) {
        throw new Error('Join a game before creating a team.');
      }

      const team = await createTeam(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
      });

      startTransition(() => {
        setKnownTeams((current) =>
          current.some((existing) => existing.id === team.id)
            ? current
            : [...current, team],
        );
        setTeamIdInput(String(team.id));
      });

      setNotice(`Created team ${team.id}.`);
      logActivity(`Created team ${team.id} in game ${activeGameId}`);
    });
  }

  async function handleJoinTeam() {
    await runAction('Join team', async () => {
      if (!accessToken || !activeGameId) {
        throw new Error('Join a game before joining a team.');
      }

      const teamId = Number.parseInt(teamIdInput, 10);
      if (!Number.isInteger(teamId)) {
        throw new Error('Enter a numeric team id.');
      }

      await joinTeam(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
        team_id: teamId,
      });

      setNotice(`Joined team ${teamId}.`);
      logActivity(`Joined team ${teamId}`);
    });
  }

  async function handleStartGame() {
    await runAction('Start game', async () => {
      if (!accessToken || !activeGameId) {
        throw new Error('Create or join a game first.');
      }

      const state = await startGame(normalizeBaseUrl(baseUrl), accessToken, {
        game_id: activeGameId,
      });

      startTransition(() => {
        setGameState(state);
      });

      setNotice(`Started game ${activeGameId}.`);
      logActivity(`Started game ${activeGameId}`);
    });
  }

  async function handleBid(amount: (typeof BID_OPTIONS)[number]) {
    await runAction(`Bid ${amount}`, async () => {
      if (!accessToken || !activeGameId) {
        throw new Error('Join a live game before bidding.');
      }

      const state = await bidGame(normalizeBaseUrl(baseUrl), accessToken, {
        amount,
        game_id: activeGameId,
      });

      startTransition(() => {
        setGameState(state);
      });

      logActivity(`Sent bid ${amount}`);
    });
  }

  async function handlePlayCard(card: SetbackCard) {
    await runAction(`Play ${formatCard(card)}`, async () => {
      if (!accessToken || !activeGameId) {
        throw new Error('Join a live game before playing a card.');
      }

      const state = await playCard(normalizeBaseUrl(baseUrl), accessToken, {
        card,
        game_id: activeGameId,
      });

      startTransition(() => {
        setGameState(state);
      });

      logActivity(`Played ${formatCard(card)}`);
    });
  }

  if (!hydrated) {
    return (
      <LinearGradient colors={['#0f1b2e', '#132a4a', '#1b4d8c']} style={styles.shell}>
        <View style={styles.loadingState}>
          <ActivityIndicator color="#f7d774" size="large" />
          <Text style={styles.loadingText}>Loading saved table state...</Text>
        </View>
        <StatusBar style="light" />
      </LinearGradient>
    );
  }

  return (
    <LinearGradient colors={['#09111f', '#123456', '#7d2a24']} style={styles.shell}>
      <StatusBar style="light" />
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.hero}>
          <Text style={styles.eyebrow}>Expo + TypeScript Client</Text>
          <Text style={styles.title}>Setback Table Control</Text>
          <Text style={styles.subtitle}>
            Web first, native ready. This app talks to the current FastAPI server
            without changing the gameplay model.
          </Text>
        </View>

        <View style={styles.statusRow}>
          <StatusChip label="Server" value={normalizeBaseUrl(baseUrl)} />
          <StatusChip label="Auth" value={accessToken ? 'ready' : 'missing'} />
          <StatusChip label="Game" value={activeGameId ? String(activeGameId) : 'none'} />
          <StatusChip label="Stream" value={subscription.status} />
        </View>

        {notice ? (
          <View style={[styles.banner, styles.noticeBanner]}>
            <Text style={styles.bannerText}>{notice}</Text>
          </View>
        ) : null}
        {error ? (
          <View style={[styles.banner, styles.errorBanner]}>
            <Text style={styles.bannerText}>{error}</Text>
          </View>
        ) : null}

        <SectionCard
          eyebrow="Connection"
          subtitle="Sign in with Google for production, refresh an existing cookie session, or keep dev tokens for local-only testing."
          title="Server And Auth"
        >
          <Text style={styles.label}>API base URL</Text>
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            onChangeText={setBaseUrl}
            placeholder="http://localhost"
            placeholderTextColor="#8ca3bf"
            style={styles.input}
            value={baseUrl}
          />
          <Text style={styles.helperText}>
            {Platform.OS === 'android'
              ? 'Android emulators usually need http://10.0.2.2 instead of localhost.'
              : 'For browser development, the Python server can stay on http://localhost.'}
          </Text>

          <View style={styles.authPanel}>
            <Text style={styles.authTitle}>Google OpenID Connect</Text>
            <Text style={styles.authText}>
              Opens the server&apos;s /auth/google/login flow and stores the returned bearer token for API requests.
            </Text>
            <View style={styles.buttonRow}>
              <ActionButton
                busy={busyAction === 'Google login'}
                disabled={!googleLoginAvailable}
                label="Sign In With Google"
                onPress={() => {
                  void handleGoogleLogin();
                }}
              />
              <ActionButton
                busy={busyAction === 'Refresh token'}
                label="Refresh Google Token"
                onPress={() => {
                  void handleRefreshToken();
                }}
                tone="secondary"
              />
            </View>
            {!googleLoginAvailable ? (
              <Text style={styles.helperText}>
                Native Google login needs an app redirect URI; use the web client for this server flow.
              </Text>
            ) : null}
          </View>

          <View style={styles.formRow}>
            <View style={styles.flexField}>
              <Text style={styles.label}>Dev username</Text>
              <TextInput
                autoCapitalize="none"
                autoCorrect={false}
                onChangeText={setUsername}
                placeholder="player-one"
                placeholderTextColor="#8ca3bf"
                style={styles.input}
                value={username}
              />
            </View>
            <ActionButton
              busy={busyAction === 'Dev login'}
              label="Use Dev Token"
              onPress={() => {
                void handleDevLogin();
              }}
            />
          </View>

          <Text style={styles.label}>Bearer token</Text>
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            multiline
            numberOfLines={4}
            onChangeText={setManualToken}
            placeholder="Paste an access token from /auth/google/callback or /auth/token"
            placeholderTextColor="#8ca3bf"
            style={[styles.input, styles.tokenInput]}
            value={manualToken}
          />
          <View style={styles.buttonRow}>
            <ActionButton
              busy={busyAction === 'Store token'}
              label="Save Token"
              onPress={() => {
                void handleSaveManualToken();
              }}
              tone="secondary"
            />
            <ActionButton
              busy={busyAction === 'Clear session'}
              label="Clear Session"
              onPress={() => {
                void handleClearSession();
              }}
              tone="ghost"
            />
            <ActionButton
              busy={busyAction === 'Logout'}
              disabled={!accessToken}
              label="Logout"
              onPress={() => {
                void handleLogout();
              }}
              tone="ghost"
            />
          </View>
        </SectionCard>

        <SectionCard
          eyebrow="Lobby"
          subtitle="The current backend supports create, join, start, create team, and join team."
          title="Game Setup"
        >
          <View style={styles.buttonRow}>
            <ActionButton
              busy={busyAction === 'Create game'}
              disabled={!accessToken}
              label="Create Game"
              onPress={() => {
                void handleCreateGame();
              }}
            />
            <ActionButton
              busy={busyAction === 'Start game'}
              disabled={!accessToken || !activeGameId}
              label="Start Game"
              onPress={() => {
                void handleStartGame();
              }}
              tone="secondary"
            />
          </View>

          <View style={styles.formRow}>
            <View style={styles.flexField}>
              <Text style={styles.label}>Game id</Text>
              <TextInput
                keyboardType="numeric"
                onChangeText={setGameIdInput}
                placeholder="42"
                placeholderTextColor="#8ca3bf"
                style={styles.input}
                value={gameIdInput}
              />
            </View>
            <View style={styles.flexField}>
              <Text style={styles.label}>Join code</Text>
              <TextInput
                autoCapitalize="none"
                autoCorrect={false}
                onChangeText={setJoinCode}
                placeholder="table secret"
                placeholderTextColor="#8ca3bf"
                style={styles.input}
                value={joinCode}
              />
            </View>
          </View>
          <ActionButton
            busy={busyAction === 'Join game'}
            disabled={!accessToken}
            label="Join Existing Game"
            onPress={() => {
              void handleJoinGame();
            }}
            tone="ghost"
          />

          {createdGame ? (
            <View style={styles.infoBox}>
              <Text style={styles.infoTitle}>Most recent table</Text>
              <Text style={styles.infoText}>Game {createdGame.id}</Text>
              <Text style={styles.infoText}>Join code {createdGame.join_code}</Text>
            </View>
          ) : null}

          <View style={styles.formRow}>
            <View style={styles.flexField}>
              <Text style={styles.label}>Team id</Text>
              <TextInput
                keyboardType="numeric"
                onChangeText={setTeamIdInput}
                placeholder="1"
                placeholderTextColor="#8ca3bf"
                style={styles.input}
                value={teamIdInput}
              />
            </View>
            <View style={styles.teamActionColumn}>
              <ActionButton
                busy={busyAction === 'Create team'}
                disabled={!accessToken || !activeGameId}
                label="Create Team"
                onPress={() => {
                  void handleCreateTeam();
                }}
                tone="secondary"
              />
              <ActionButton
                busy={busyAction === 'Join team'}
                disabled={!accessToken || !activeGameId}
                label="Join Team"
                onPress={() => {
                  void handleJoinTeam();
                }}
                tone="ghost"
              />
            </View>
          </View>

          {knownTeams.length > 0 ? (
            <View style={styles.teamList}>
              {knownTeams.map((team) => (
                <View key={team.id} style={styles.teamBadge}>
                  <Text style={styles.teamBadgeText}>Team {team.id}</Text>
                </View>
              ))}
            </View>
          ) : null}
        </SectionCard>

        <SectionCard
          eyebrow="Match"
          subtitle="Bidding and trick play use the exact request models the Python server already exposes."
          title="Live Table"
        >
          {!deferredGameState ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>
                No game state yet. Start the game or wait for an SSE update.
              </Text>
            </View>
          ) : (
            <>
              <View style={styles.scoreboard}>
                <StatusChip label="Phase" value={formatPhase(deferredGameState.phase)} />
                <StatusChip label="Turn" value={currentPlayer?.player_id ?? 'pending'} />
                <StatusChip
                  label="Trump"
                  value={deferredGameState.active_round.trump ?? 'unset'}
                />
              </View>

              <Text style={styles.label}>Scoreboard</Text>
              <View style={styles.scoreRow}>
                {Object.entries(deferredGameState.score).map(([teamId, score]) => (
                  <View key={teamId} style={styles.scoreTile}>
                    <Text style={styles.scoreTeam}>Team {teamId}</Text>
                    <Text style={styles.scoreValue}>{score}</Text>
                  </View>
                ))}
              </View>

              <Text style={styles.label}>Player order</Text>
              <View style={styles.orderList}>
                {deferredGameState.order.order.map((player) => (
                  <View key={player.player_id} style={styles.orderRow}>
                    <Text style={styles.orderText}>{player.player_id}</Text>
                    <Text style={styles.orderMeta}>team {player.team_id}</Text>
                  </View>
                ))}
              </View>

              {deferredGameState.phase === 'bid' ? (
                <>
                  <Text style={styles.label}>Bid actions</Text>
                  <View style={styles.buttonRow}>
                    {BID_OPTIONS.map((amount) => (
                      <ActionButton
                        key={amount}
                        busy={busyAction === `Bid ${amount}`}
                        disabled={!accessToken || !activeGameId}
                        label={`Bid ${amount}`}
                        onPress={() => {
                          void handleBid(amount);
                        }}
                        tone={amount >= 2 ? 'secondary' : 'ghost'}
                      />
                    ))}
                  </View>
                </>
              ) : null}

              {deferredGameState.active_round.bid.collection.length > 0 ? (
                <>
                  <Text style={styles.label}>Bid history</Text>
                  <View style={styles.historyList}>
                    {deferredGameState.active_round.bid.collection.map((bid, index) => (
                      <Text key={`${bid.player_id}-${index}`} style={styles.historyText}>
                        {bid.player_id} bid {bid.amount}
                      </Text>
                    ))}
                  </View>
                </>
              ) : null}

              {deferredGameState.active_round.trick?.collection.length ? (
                <>
                  <Text style={styles.label}>Current trick</Text>
                  <View style={styles.cardRow}>
                    {deferredGameState.active_round.trick.collection.map((card, index) => (
                      <View key={`${card.player_id}-${index}`} style={styles.cardTile}>
                        <Text style={styles.cardValue}>{formatCard(card)}</Text>
                        <Text style={styles.cardMeta}>{card.player_id}</Text>
                      </View>
                    ))}
                  </View>
                </>
              ) : null}

              {deferredGameState.phase === 'play' ? (
                <>
                  <Text style={styles.label}>Current-turn hand</Text>
                  <Text style={styles.helperText}>
                    The backend currently returns full hand state to clients, so this view
                    shows the cards for whoever is up next.
                  </Text>
                  <View style={styles.cardRow}>
                    {currentHand.map((card, index) => (
                      <ActionButton
                        key={`${card.suit}-${card.value}-${index}`}
                        busy={busyAction === `Play ${formatCard(card)}`}
                        disabled={!accessToken || !activeGameId}
                        label={formatCard(card)}
                        onPress={() => {
                          void handlePlayCard(card);
                        }}
                        tone="ghost"
                      />
                    ))}
                  </View>
                </>
              ) : null}
            </>
          )}
        </SectionCard>

        <SectionCard
          eyebrow="Diagnostics"
          subtitle={subscription.detail || 'Recent local actions and live event notices appear here.'}
          title="Activity"
        >
          {activityLog.length === 0 ? (
            <Text style={styles.emptyText}>No client activity yet.</Text>
          ) : (
            <View style={styles.historyList}>
              {activityLog.map((item, index) => (
                <Text key={`${item}-${index}`} style={styles.historyText}>
                  {item}
                </Text>
              ))}
            </View>
          )}
        </SectionCard>
      </ScrollView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  authPanel: {
    backgroundColor: '#eff4fa',
    borderColor: '#d5e1ef',
    borderRadius: 18,
    borderWidth: 1,
    padding: 14,
    rowGap: 10,
  },
  authText: {
    color: '#4e647f',
    fontSize: 14,
    lineHeight: 20,
  },
  authTitle: {
    color: '#102947',
    fontSize: 16,
    fontWeight: '800',
  },
  banner: {
    borderRadius: 18,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  bannerText: {
    color: '#fdfefe',
    fontSize: 14,
    fontWeight: '600',
  },
  buttonRow: {
    columnGap: 10,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 10,
  },
  cardMeta: {
    color: '#9fb6d4',
    fontSize: 12,
    marginTop: 6,
  },
  cardRow: {
    columnGap: 10,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 10,
  },
  cardTile: {
    backgroundColor: '#102947',
    borderRadius: 18,
    minWidth: 88,
    paddingHorizontal: 14,
    paddingVertical: 14,
  },
  cardValue: {
    color: '#f8fbff',
    fontSize: 22,
    fontWeight: '800',
  },
  emptyState: {
    backgroundColor: '#eff4fa',
    borderRadius: 18,
    padding: 20,
  },
  emptyText: {
    color: '#47617f',
    fontSize: 14,
    lineHeight: 20,
  },
  errorBanner: {
    backgroundColor: 'rgba(150, 45, 36, 0.94)',
  },
  eyebrow: {
    color: '#f7d774',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.8,
    textTransform: 'uppercase',
  },
  flexField: {
    flexGrow: 1,
    flexShrink: 1,
    minWidth: 220,
  },
  formRow: {
    columnGap: 12,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 12,
  },
  helperText: {
    color: '#4e647f',
    fontSize: 13,
    lineHeight: 18,
    marginTop: 6,
  },
  hero: {
    paddingTop: 28,
    rowGap: 8,
  },
  historyList: {
    rowGap: 8,
  },
  historyText: {
    color: '#173152',
    fontSize: 14,
    lineHeight: 18,
  },
  infoBox: {
    backgroundColor: '#173152',
    borderRadius: 18,
    padding: 16,
    rowGap: 4,
  },
  infoText: {
    color: '#f8fbff',
    fontSize: 15,
    fontWeight: '600',
  },
  infoTitle: {
    color: '#f7d774',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.1,
    textTransform: 'uppercase',
  },
  input: {
    backgroundColor: '#edf3fa',
    borderColor: '#bfd1e7',
    borderRadius: 16,
    borderWidth: 1,
    color: '#0d1d31',
    fontSize: 16,
    paddingHorizontal: 14,
    paddingVertical: 13,
  },
  label: {
    color: '#0d1d31',
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.4,
    marginBottom: 6,
    textTransform: 'uppercase',
  },
  loadingState: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
    rowGap: 14,
  },
  loadingText: {
    color: '#f8fbff',
    fontSize: 16,
    fontWeight: '600',
  },
  noticeBanner: {
    backgroundColor: 'rgba(31, 134, 99, 0.92)',
  },
  orderList: {
    rowGap: 8,
  },
  orderMeta: {
    color: '#5c7593',
    fontSize: 13,
    fontWeight: '600',
  },
  orderRow: {
    alignItems: 'center',
    backgroundColor: '#eff4fa',
    borderRadius: 14,
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  orderText: {
    color: '#102947',
    fontSize: 15,
    fontWeight: '700',
  },
  scoreRow: {
    columnGap: 10,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 10,
  },
  scoreboard: {
    columnGap: 10,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 10,
  },
  scoreTeam: {
    color: '#9fb6d4',
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  scoreTile: {
    backgroundColor: '#102947',
    borderRadius: 20,
    minWidth: 112,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  scoreValue: {
    color: '#f8fbff',
    fontSize: 24,
    fontWeight: '800',
    marginTop: 4,
  },
  scrollContent: {
    paddingHorizontal: 18,
    paddingVertical: 28,
    rowGap: 18,
  },
  shell: {
    flex: 1,
  },
  statusChip: {
    backgroundColor: 'rgba(8, 17, 32, 0.45)',
    borderColor: 'rgba(247, 215, 116, 0.35)',
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 9,
    rowGap: 2,
  },
  statusLabel: {
    color: '#8ca3bf',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  statusRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  statusValue: {
    color: '#f8fbff',
    fontSize: 14,
    fontWeight: '600',
  },
  subtitle: {
    color: '#d2deee',
    fontSize: 16,
    lineHeight: 23,
    maxWidth: 720,
  },
  teamActionColumn: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    paddingTop: 23,
  },
  teamBadge: {
    backgroundColor: '#f1d7a1',
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  teamBadgeText: {
    color: '#5b2f16',
    fontSize: 14,
    fontWeight: '700',
  },
  teamList: {
    columnGap: 10,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 10,
  },
  title: {
    color: '#f8fbff',
    fontSize: 34,
    fontWeight: '800',
    lineHeight: 38,
  },
  tokenInput: {
    minHeight: 112,
    textAlignVertical: 'top',
  },
});

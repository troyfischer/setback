import type {
  AuthOptions,
  BidRequest,
  CurrentUser,
  GameRecord,
  GameRequest,
  GameStatePlayerScoped,
  LobbyState,
  PlayCardRequest,
  SubscribeTokenResponse,
  TeamMemberRecord,
  TeamRecord,
  TokenResponse,
  UpdateTeamRequest,
} from "../types/setback";

async function readError(response: Response) {
  try {
    const parsed = (await response.json()) as { detail?: string } | string;
    if (typeof parsed === "string") {
      return parsed;
    }
    if (parsed.detail) {
      return parsed.detail;
    }
    return JSON.stringify(parsed);
  } catch {
    const text = await response.text();
    return text || `${response.status} ${response.statusText}`;
  }
}

async function requestJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return (await response.json()) as T;
}

function withBearer(token: string) {
  return {
    Authorization: `Bearer ${token}`,
  };
}

export async function fetchAuthOptions(baseUrl: string) {
  return requestJson<AuthOptions>(`${baseUrl}/auth/options`, {
    method: "GET",
  });
}

export async function createDevToken(baseUrl: string, username: string) {
  const form = new URLSearchParams();
  form.set("username", username);
  form.set("password", "dev-password");

  return requestJson<TokenResponse>(`${baseUrl}/auth/dev-token`, {
    body: form.toString(),
    credentials: "include",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    method: "POST",
  });
}

export async function refreshAccessToken(baseUrl: string) {
  return requestJson<TokenResponse>(`${baseUrl}/auth/refresh`, {
    credentials: "include",
    method: "GET",
  });
}

export async function fetchMe(baseUrl: string, token: string) {
  return requestJson<CurrentUser>(`${baseUrl}/auth/me`, {
    headers: withBearer(token),
    method: "GET",
  });
}

export async function logout(baseUrl: string, token: string) {
  const response = await fetch(`${baseUrl}/auth/logout`, {
    credentials: "include",
    headers: withBearer(token),
    method: "GET",
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.text();
}

export async function createGame(baseUrl: string, token: string) {
  return requestJson<GameRecord>(`${baseUrl}/game/create`, {
    headers: withBearer(token),
    method: "POST",
  });
}

export async function joinGame(
  baseUrl: string,
  token: string,
  request: GameRequest,
) {
  return requestJson(`${baseUrl}/game/join`, {
    body: JSON.stringify(request),
    headers: {
      ...withBearer(token),
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export async function createTeam(
  baseUrl: string,
  token: string,
  request: GameRequest,
) {
  return requestJson<TeamRecord>(`${baseUrl}/team/create`, {
    body: JSON.stringify(request),
    headers: {
      ...withBearer(token),
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export async function joinTeam(
  baseUrl: string,
  token: string,
  request: UpdateTeamRequest,
) {
  return requestJson<TeamMemberRecord>(`${baseUrl}/team/join`, {
    body: JSON.stringify(request),
    headers: {
      ...withBearer(token),
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export async function leaveTeam(
  baseUrl: string,
  token: string,
  request: UpdateTeamRequest,
) {
  return requestJson<TeamMemberRecord>(`${baseUrl}/team/leave`, {
    body: JSON.stringify(request),
    headers: {
      ...withBearer(token),
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export async function deleteTeam(
  baseUrl: string,
  token: string,
  request: UpdateTeamRequest,
) {
  return requestJson(`${baseUrl}/team/delete`, {
    body: JSON.stringify(request),
    headers: {
      ...withBearer(token),
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export async function fetchLobbyState(
  baseUrl: string,
  token: string,
  gameId: string,
) {
  return requestJson<LobbyState>(`${baseUrl}/game/${gameId}/lobby`, {
    headers: withBearer(token),
    method: "GET",
  });
}

export async function startGame(
  baseUrl: string,
  token: string,
  request: GameRequest,
) {
  return requestJson<GameStatePlayerScoped>(`${baseUrl}/game/start`, {
    body: JSON.stringify(request),
    headers: {
      ...withBearer(token),
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export async function bidGame(
  baseUrl: string,
  token: string,
  request: BidRequest,
) {
  return requestJson<GameStatePlayerScoped>(`${baseUrl}/game/bid`, {
    body: JSON.stringify(request),
    headers: {
      ...withBearer(token),
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export async function playCard(
  baseUrl: string,
  token: string,
  request: PlayCardRequest,
) {
  return requestJson<GameStatePlayerScoped>(`${baseUrl}/game/trick/play`, {
    body: JSON.stringify(request),
    headers: {
      ...withBearer(token),
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export async function fetchGameState(
  baseUrl: string,
  token: string,
  gameId: string,
) {
  return requestJson<GameStatePlayerScoped>(`${baseUrl}/game/${gameId}/state`, {
    headers: withBearer(token),
    method: "GET",
  });
}

export async function deleteGame(
  baseUrl: string,
  token: string,
  request: GameRequest,
) {
  return requestJson<GameRecord>(`${baseUrl}/game/delete`, {
    body: JSON.stringify(request),
    headers: {
      ...withBearer(token),
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export async function fetchUserRelevantGames(baseUrl: string, token: string) {
  return requestJson<GameRecord[]>(`${baseUrl}/game/games`, {
    headers: withBearer(token),
    method: "GET",
  });
}

export async function createSubscribeToken(
  baseUrl: string,
  token: string,
  gameId: string,
) {
  return requestJson<SubscribeTokenResponse>(
    `${baseUrl}/game/${gameId}/subscribe-token`,
    {
      headers: withBearer(token),
      method: "POST",
    },
  );
}

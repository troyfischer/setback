export type Suit = "club" | "diamond" | "heart" | "spade";
export type Phase = "bid" | "complete" | "play";

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type AuthOptions = {
  dev_auth_enabled: boolean;
  oauth_providers: string[];
};

export type CurrentUser = {
  email: string;
  email_verified: boolean;
  family_name: string;
  given_name: string;
  logged_in: boolean;
  name: string;
  picture: string;
  sub: string;
};

export type GameRecord = {
  created_at: string;
  id: string;
  owner: string;
  status: GameStatus;
};

export type PlayerRecord = {
  game_id: string;
  id: string;
};

export type TeamRecord = {
  game_id: string;
  id: number;
  owner: string;
  team_number: number;
};

export type TeamWithMembers = TeamRecord & {
  members: string[];
};

export type GameStatus = "created" | "active" | "ended";

export type LobbyState = {
  game_owner: string;
  teams: TeamWithMembers[];
  players: string[];
  game_status: GameStatus;
};

export type TeamMemberRecord = {
  game_id: string;
  player_id: string;
  team_id: number;
};

export type SubscribeTokenResponse = {
  expires_in_seconds: number;
  sse_token: string;
};

export type ModIndex = {
  idx: number;
  mod: number;
};

export type SetbackCard = {
  null: boolean;
  suit: Suit;
  value: number;
};

export type PlayedCard = SetbackCard & {
  player_id: string;
};

export type BidAction = {
  amount: 0 | 2 | 3 | 4;
  player_id: string;
};

export type TurnCollection<T> = {
  collection: T[];
  game_id: string;
  turn: ModIndex;
};

export type RoundScore = {
  game: [number, number];
  high: [number, PlayedCard];
  jack: [number, PlayedCard] | null;
  low: [number, PlayedCard];
};

export type GameRoundPlayerScoped = {
  bid: TurnCollection<BidAction>;
  dealer: ModIndex;
  game_id: string;
  hand: SetbackCard[];
  player_id: string;
  score: RoundScore | null;
  trick: TurnCollection<PlayedCard> | null;
  tricks_won: Record<string, TurnCollection<PlayedCard>[]>;
  trump: Suit | null;
};

export type GamePlayer = {
  player_id: string;
  team_id: number;
  turn: number;
};

export type PlayerOrder = {
  order: GamePlayer[];
};

export type GameStatePlayerScoped = {
  active_round: GameRoundPlayerScoped;
  game_id: string;
  max_score: number;
  order: PlayerOrder;
  phase: Phase;
  rounds: GameRoundPlayerScoped[];
  score: Record<string, number>;
};

export type GameEvent = {
  data: GameStatePlayerScoped | Record<string, unknown>;
  event_type:
    | "bid_placed"
    | "card_played"
    | "game_complete"
    | "game_started"
    | "round_complete"
    | "state_update"
    | "trick_won";
  game_id: string;
};

export type GameRequest = {
  game_id: string;
};

export type UpdateTeamRequest = GameRequest & {
  team_number: number;
};

export type BidRequest = GameRequest & {
  amount: 0 | 2 | 3 | 4;
};

export type PlayCardRequest = GameRequest & {
  card: SetbackCard;
};

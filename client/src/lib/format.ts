import type {
  GamePlayer,
  GameStatePlayerScoped,
  ModIndex,
  SetbackCard,
} from "../types/setback";

const suitSymbols: Record<SetbackCard["suit"], string> = {
  club: "♣",
  diamond: "♦",
  heart: "♥",
  spade: "♠",
};

export function getDefaultApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_SETBACK_API_URL as string | undefined;
  return envUrl ? normalizeBaseUrl(envUrl) : "http://localhost";
}

export function normalizeBaseUrl(value: string): string {
  const trimmed = value.trim() || "http://localhost";
  const withProtocol = /^https?:\/\//i.test(trimmed)
    ? trimmed
    : `http://${trimmed}`;
  return withProtocol.replace(/\/+$/, "");
}

export function formatPhase(phase: GameStatePlayerScoped["phase"]): string {
  return phase.charAt(0).toUpperCase() + phase.slice(1);
}

export function formatCard(card: SetbackCard): string {
  const face =
    card.value === 14 || card.value === 1
      ? "A"
      : card.value === 13
        ? "K"
        : card.value === 12
          ? "Q"
          : card.value === 11
            ? "J"
            : String(card.value);

  return `${face}${suitSymbols[card.suit]}`;
}

export function getCurrentTurn(state: GameStatePlayerScoped): ModIndex {
  if (state.phase === "bid") {
    return state.active_round.bid.turn;
  }
  return state.active_round.trick?.turn ?? state.active_round.bid.turn;
}

export function getCurrentTurnPlayer(
  state: GameStatePlayerScoped,
): GamePlayer | null {
  const turn = getCurrentTurn(state);
  return state.order.order[turn.idx] ?? null;
}

export function getMyHand(state: GameStatePlayerScoped): SetbackCard[] {
  return state.active_round.hand ?? [];
}

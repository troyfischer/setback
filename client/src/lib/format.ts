import { Platform } from 'react-native';

import type {
  GamePlayer,
  GameStatePlayerScoped,
  ModIndex,
  SetbackCard,
} from '../types/setback';

const suitSymbols: Record<SetbackCard['suit'], string> = {
  club: '♣',
  diamond: '♦',
  heart: '♥',
  spade: '♠',
};

export function getDefaultApiBaseUrl(): string {
  const envUrl = (globalThis as { process?: { env?: Record<string, string | undefined> } })
    .process?.env?.EXPO_PUBLIC_SETBACK_API_URL;
  if (envUrl) {
    return normalizeBaseUrl(envUrl);
  }

  if (Platform.OS === 'android') {
    return 'http://10.0.2.2';
  }

  if (Platform.OS === 'ios') {
    return 'http://127.0.0.1';
  }

  return 'http://localhost';
}

export function normalizeBaseUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    if (Platform.OS === 'android') {
      return 'http://10.0.2.2';
    }

    if (Platform.OS === 'ios') {
      return 'http://127.0.0.1';
    }

    return 'http://localhost';
  }

  const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
  return withProtocol.replace(/\/+$/, '');
}

export function formatPhase(phase: GameStatePlayerScoped['phase']): string {
  return phase.charAt(0).toUpperCase() + phase.slice(1);
}

export function formatCard(card: SetbackCard): string {
  const face =
    card.value === 14 || card.value === 1
      ? 'A'
      : card.value === 13
        ? 'K'
        : card.value === 12
          ? 'Q'
          : card.value === 11
            ? 'J'
            : String(card.value);

  return `${face}${suitSymbols[card.suit]}`;
}

export function formatTimestamp(): string {
  return new Date().toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function getCurrentTurn(state: GameStatePlayerScoped): ModIndex {
  if (state.phase === 'bid') {
    return state.active_round.bid.turn;
  }

  return state.active_round.trick?.turn ?? state.active_round.bid.turn;
}

export function getCurrentTurnPlayer(state: GameStatePlayerScoped): GamePlayer | null {
  const turn = getCurrentTurn(state);
  return state.order.order[turn.idx] ?? null;
}

export function getMyHand(state: GameStatePlayerScoped): SetbackCard[] {
  return state.active_round.my_hand ?? [];
}

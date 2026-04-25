import { useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';

import { createSubscribeToken } from '../lib/api';
import { normalizeBaseUrl } from '../lib/format';
import type { GameEvent } from '../types/setback';

type Params = {
  accessToken: string;
  baseUrl: string;
  enabled: boolean;
  gameId: number | null;
  onError?: (message: string) => void;
  onEvent: (event: GameEvent) => void;
};

type SubscriptionState = {
  detail: string | null;
  status: 'idle' | 'connecting' | 'live' | 'error';
};

type ClosableEventSource = {
  addEventListener?: (type: string, listener: (event: any) => void) => void;
  close: () => void;
  onerror?: ((event: Event) => void) | null;
  onmessage?: ((event: MessageEvent<string>) => void) | null;
  onopen?: ((event: Event) => void) | null;
};

export function useGameSubscription({
  accessToken,
  baseUrl,
  enabled,
  gameId,
  onError,
  onEvent,
}: Params): SubscriptionState {
  const [status, setStatus] = useState<SubscriptionState['status']>('idle');
  const [detail, setDetail] = useState<string | null>(null);
  const onEventRef = useRef(onEvent);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onEventRef.current = onEvent;
    onErrorRef.current = onError;
  }, [onError, onEvent]);

  useEffect(() => {
    if (!enabled || !gameId || !accessToken) {
      setStatus('idle');
      setDetail(null);
      return;
    }

    let cancelled = false;
    let source: ClosableEventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function teardown() {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }

      source?.close();
      source = null;
    }

    function scheduleReconnect(reason: string) {
      if (cancelled) {
        return;
      }

      teardown();
      setStatus('error');
      setDetail(reason);
      onErrorRef.current?.(reason);

      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        void connect();
      }, 2500);
    }

    function handlePayload(payload: string) {
      try {
        const parsed = JSON.parse(payload) as GameEvent;
        setStatus('live');
        setDetail('Receiving live updates');
        onEventRef.current(parsed);
      } catch {
        scheduleReconnect('Received an invalid SSE payload.');
      }
    }

    async function connect() {
      setStatus('connecting');
      setDetail(`Connecting to game ${gameId}...`);

      try {
        const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
        const activeGameId = gameId;
        if (!activeGameId) {
          return;
        }

        const token = await createSubscribeToken(
          normalizedBaseUrl,
          accessToken,
          activeGameId,
        );
        if (cancelled) {
          return;
        }

        const streamUrl = `${normalizedBaseUrl}/game/${activeGameId}/subscribe?sse_token=${encodeURIComponent(token.sse_token)}`;

        if (Platform.OS === 'web' && typeof globalThis.EventSource !== 'undefined') {
          const webSource = new EventSource(streamUrl);
          source = webSource;

          webSource.onopen = () => {
            setStatus('live');
            setDetail('Stream connected');
          };

          webSource.onmessage = (event) => {
            if (event.data) {
              handlePayload(event.data);
            }
          };

          webSource.onerror = () => {
            scheduleReconnect('The live stream disconnected.');
          };

          return;
        }

        const NativeEventSource = require('react-native-sse').default as new (
          url: string,
          options?: { pollingInterval?: number },
        ) => ClosableEventSource;
        const nativeSource = new NativeEventSource(streamUrl, { pollingInterval: 0 });
        source = nativeSource;

        nativeSource.addEventListener?.('open', () => {
          setStatus('live');
          setDetail('Stream connected');
        });

        nativeSource.addEventListener?.('message', (event) => {
          if (event.data) {
            handlePayload(event.data);
          }
        });

        nativeSource.addEventListener?.('error', (event) => {
          scheduleReconnect(event.message || 'The live stream disconnected.');
        });
      } catch (caught) {
        const message =
          caught instanceof Error
            ? caught.message
            : 'Unable to connect to the live stream.';
        scheduleReconnect(message);
      }
    }

    void connect();

    return () => {
      cancelled = true;
      teardown();
    };
  }, [accessToken, baseUrl, enabled, gameId]);

  return { detail, status };
}

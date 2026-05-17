import { useEffect, useRef, useState } from "react";

import { createSubscribeToken } from "../lib/api";
import { normalizeBaseUrl } from "../lib/format";
import type { GameEvent } from "../types/setback";

type Params = {
  accessToken: string;
  baseUrl: string;
  enabled: boolean;
  gameId: string | null;
  onError?: (message: string) => void;
  onEvent: (event: GameEvent) => void;
};

type SubscriptionState = {
  detail: string | null;
  status: "idle" | "connecting" | "live" | "error";
};

export function useGameSubscription({
  accessToken,
  baseUrl,
  enabled,
  gameId,
  onError,
  onEvent,
}: Params): SubscriptionState {
  const [status, setStatus] = useState<SubscriptionState["status"]>("idle");
  const [detail, setDetail] = useState<string | null>(null);
  const onEventRef = useRef(onEvent);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onEventRef.current = onEvent;
    onErrorRef.current = onError;
  }, [onError, onEvent]);

  useEffect(() => {
    if (!enabled || !gameId || !accessToken) {
      setStatus("idle");
      setDetail(null);
      return;
    }

    let cancelled = false;
    let source: EventSource | null = null;
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
      if (cancelled) return;
      teardown();
      setStatus("error");
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
        setStatus("live");
        setDetail("Receiving live updates");
        onEventRef.current(parsed);
      } catch {
        scheduleReconnect("Received an invalid SSE payload.");
      }
    }

    async function connect() {
      setStatus("connecting");
      setDetail(`Connecting to game ${gameId}...`);

      try {
        const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
        if (!gameId) return;

        const token = await createSubscribeToken(
          normalizedBaseUrl,
          accessToken,
          gameId,
        );
        if (cancelled) return;

        const streamUrl = `${normalizedBaseUrl}/game/${gameId}/subscribe?sse_token=${encodeURIComponent(token.sse_token)}`;
        const es = new EventSource(streamUrl);
        source = es;

        es.onopen = () => {
          setStatus("live");
          setDetail("Stream connected");
        };

        es.onmessage = (event) => {
          if (event.data) handlePayload(event.data as string);
        };

        es.onerror = () => {
          scheduleReconnect("The live stream disconnected.");
        };
      } catch (caught) {
        const message =
          caught instanceof Error
            ? caught.message
            : "Unable to connect to the live stream.";
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

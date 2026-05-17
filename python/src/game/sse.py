"""
SSE connection management and Redis pub/sub integration.
"""

from __future__ import annotations

import asyncio
from collections.abc import ItemsView
from typing import Any, TypedDict, final

import redis.asyncio as redis

from src.game.events import GameEvent
from src.game.manager import GameState
from src.game.types import GameId, PlayerId
from src.logging import new_logger

logger = new_logger(__name__)


type ClientQueue = asyncio.Queue[dict[str, Any]]


class GameSubscribers:
    """
    Active SSE queues for a single game, grouped by `player_id`.

    A single player may hold multiple queues (e.g. multiple tabs). Grouping by
    player_id is what lets `ConnectionManager.broadcast_to_game` send each
    player a state scoped to their own hand instead of the full table.
    """

    def __init__(self) -> None:
        self._by_player: dict[PlayerId, set[ClientQueue]] = {}

    def add(self, player_id: PlayerId, queue: ClientQueue) -> None:
        self._by_player.setdefault(player_id, set()).add(queue)

    def remove(self, player_id: PlayerId, queue: ClientQueue) -> None:
        queues = self._by_player.get(player_id)
        if not queues:
            return
        queues.discard(queue)
        if not queues:
            del self._by_player[player_id]

    def is_empty(self) -> bool:
        return not self._by_player

    @property
    def connection_count(self) -> int:
        return sum(len(queues) for queues in self._by_player.values())

    def items(self) -> ItemsView[PlayerId, set[ClientQueue]]:
        return self._by_player.items()


class ConnectionManager:
    """
    Manages SSE connections per server instance.

    Each server maintains its own set of active connections in memory, grouped
    by game and then by player so broadcasts can apply per-player scoping.
    """

    def __init__(self, max_queue_size: int = 64):
        self._games: dict[GameId, GameSubscribers] = {}
        self.max_queue_size = max_queue_size

    def connect(self, game_id: GameId, player_id: PlayerId) -> ClientQueue:
        """Register a new SSE client and return its message queue."""
        queue: ClientQueue = asyncio.Queue(maxsize=self.max_queue_size)
        subs = self._games.setdefault(game_id, GameSubscribers())
        subs.add(player_id, queue)
        logger.info(
            "client connected",
            game_id=game_id,
            player_id=player_id,
            connections=subs.connection_count,
        )
        return queue

    def disconnect(
        self, game_id: GameId, player_id: PlayerId, queue: ClientQueue
    ) -> None:
        """Remove an SSE client's queue."""
        subs = self._games.get(game_id)
        if not subs:
            return

        subs.remove(player_id, queue)
        remaining = subs.connection_count
        if subs.is_empty():
            del self._games[game_id]

        logger.info(
            "client disconnected",
            game_id=game_id,
            player_id=player_id,
            connections=remaining,
        )

    async def broadcast_to_game(self, game_id: GameId, event: GameEvent) -> None:
        """
        Broadcast an event to every client of a game, scoped per player.

        The full `GameState` on the event is re-serialized once per connected
        player so each subscriber only sees their own hand.
        """
        subs = self._games.get(game_id)
        if not subs:
            logger.debug(
                "no active sse connections for game id",
                game_id=game_id,
            )
            return

        for player_id, queues in subs.items():
            payload_data: dict[str, Any] = event.data
            try:
                payload_data = (
                    GameState.model_validate(event.data)
                    .to_player_scoped(player_id)
                    .model_dump()
                )
            except Exception:
                payload_data = event.data

            payload = {
                "event_type": event.event_type,
                "game_id": event.game_id,
                "data": payload_data,
            }
            for queue in list(queues):
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    # Drop the oldest event for slow consumers, then enqueue the latest.
                    _ = queue.get_nowait()
                    queue.put_nowait(payload)
                except Exception as e:
                    logger.error(
                        "error broadcasting to client",
                        game_id=game_id,
                        player_id=player_id,
                        error=str(e),
                    )


class RedisMessage(TypedDict):
    channel: bytes
    data: bytes
    type: str


@final
class RedisSubscriber:
    """
    Listens to Redis pub/sub channels and broadcasts events
    to local SSE connections.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        connection_manager: ConnectionManager,
    ):
        self.redis_client = redis_client
        self.connection_manager = connection_manager
        self.pubsub = self.redis_client.pubsub()  # pyright: ignore[reportUnknownMemberType]
        self._running = False

    async def start(self) -> None:
        """Start the Redis subscriber background task"""
        self._running = True

        logger.info("redis subscriber started")

        # Subscribe to a pattern that matches all game channels
        await self.pubsub.psubscribe("game:*")

        # Start listening loop
        _ = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        """Stop the Redis subscriber"""
        self._running = False
        if self.pubsub:
            await self.pubsub.unsubscribe()  # pyright: ignore[reportUnknownMemberType]
            await self.pubsub.aclose()  # type: ignore[no-untyped-call]
        if self.redis_client:
            await self.redis_client.aclose()
        logger.info("redis subscriber stopped")

    async def _listen(self) -> None:
        """
        Background task that listens to Redis pub/sub and
        broadcasts to SSE clients.
        """
        if not self.pubsub:
            raise RuntimeError("PubSub not initialized")

        try:
            while self._running:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )

                if message and message["type"] == "pmessage":
                    await self._handle_message(message)  # pyright: ignore[reportArgumentType]
        except Exception as e:
            logger.error("error in redis subscriber loop", error=str(e))
        finally:
            logger.info("redis subscriber loop exited")

    async def _handle_message(self, message: RedisMessage) -> None:
        """
        Handle a message from Redis and broadcast to relevant SSE clients.
        """
        try:
            # Extract game_id from channel name (e.g., "game:123" -> 123)
            channel = message["channel"].decode("utf-8")
            game_id = channel.split(":")[1]

            # Parse the event
            event = GameEvent.model_validate_json(message["data"])

            logger.debug(
                "received redis event",
                game_id=game_id,
                event_type=event.event_type,
            )

            # Scoping to each player's view happens inside broadcast_to_game.
            await self.connection_manager.broadcast_to_game(game_id, event)

        except Exception as e:
            logger.error("error handling redis message", error=str(e), message=message)


# Global instances (will be initialized in main.py)
redis_subscriber: RedisSubscriber | None = None

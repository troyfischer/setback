"""
SSE connection management and Redis pub/sub integration.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypedDict, final

import redis.asyncio as redis

from src.game.events import GameEvent
from src.game.types import GameId
from src.logging import new_logger

logger = new_logger(__name__)


class ConnectionManager:
    """
    Manages SSE connections per server instance.

    Each server maintains its own set of active connections in memory.
    Clients are represented by asyncio.Queue instances that the SSE
    streaming response reads from.
    """

    def __init__(self, max_queue_size: int = 64):
        # game_id -> set of asyncio.Queue instances (one per client)
        self.active_connections: dict[GameId, set[asyncio.Queue[dict[str, Any]]]] = {}
        self.max_queue_size = max_queue_size

    def connect(self, game_id: GameId) -> asyncio.Queue[dict[str, Any]]:
        """Register a new SSE client and return its message queue."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self.max_queue_size
        )
        if game_id not in self.active_connections:
            self.active_connections[game_id] = set()
        self.active_connections[game_id].add(queue)
        logger.info(
            "client connected",
            game_id=game_id,
            connections=len(self.active_connections[game_id]),
        )
        return queue

    def disconnect(self, game_id: GameId, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Remove an SSE client's queue."""
        if game_id in self.active_connections:
            self.active_connections[game_id].discard(queue)
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]
        logger.info(
            "client disconnected",
            game_id=game_id,
            connections=len(self.active_connections.get(game_id, [])),
        )

    async def broadcast_to_game(self, game_id: GameId, message: dict[str, Any]) -> None:
        """
        Broadcast a message to all clients connected to a specific game
        on this server instance by putting it on each client's queue.
        """
        if game_id not in self.active_connections:
            logger.debug(
                "no active sse connections for game id",
                game_id=game_id,
            )
            return

        for queue in list(self.active_connections[game_id]):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Drop the oldest event for slow consumers, then enqueue the latest.
                _ = queue.get_nowait()
                queue.put_nowait(message)
            except Exception as e:
                logger.error(
                    "error broadcasting to client",
                    game_id=game_id,
                    error=str(e),
                )


class WSMessage(TypedDict):
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
            await self.pubsub.aclose()
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

    async def _handle_message(self, message: WSMessage) -> None:
        """
        Handle a message from Redis and broadcast to relevant SSE clients.
        """
        try:
            # Extract game_id from channel name (e.g., "game:123" -> 123)
            channel = message["channel"].decode("utf-8")
            game_id = int(channel.split(":")[1])

            # Parse the event
            event = GameEvent.model_validate_json(message["data"])

            logger.debug(
                "received redis event",
                game_id=game_id,
                event_type=event.event_type,
            )

            # Broadcast to all local SSE connections for this game
            await self.connection_manager.broadcast_to_game(game_id, event.model_dump())

        except Exception as e:
            logger.error("error handling redis message", error=str(e), message=message)


# Global instances (will be initialized in main.py)
redis_subscriber: RedisSubscriber | None = None

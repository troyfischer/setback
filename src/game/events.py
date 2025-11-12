"""
Game event models and Redis pub/sub handling.
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel

from src.game.manager import GameState


class EventType(enum.StrEnum):
    GAME_STARTED = "game_started"
    BID_PLACED = "bid_placed"
    CARD_PLAYED = "card_played"
    TRICK_WON = "trick_won"
    ROUND_COMPLETE = "round_complete"
    GAME_COMPLETE = "game_complete"
    STATE_UPDATE = "state_update"


class GameEvent(BaseModel):
    """Base class for all game events"""

    event_type: EventType
    game_id: int
    data: dict[str, Any]


class RedisChannels:
    @staticmethod
    def game(game_id: int) -> str:
        """Channel for all events in a specific game"""
        return f"game:{game_id}"


def game_event_from_state(event_type: EventType, game_state: GameState) -> GameEvent:
    """Create a game event from the current game state"""
    return GameEvent(
        event_type=event_type,
        game_id=game_state.game_id,
        data=game_state.model_dump(),
    )

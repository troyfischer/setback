"""
Per-player scoping for game state responses.

The internal `GameState` carries every player's hand so the game manager can
validate turns and moves. When the state leaves the server — via an HTTP
response to a player or via an SSE broadcast to a subscriber — it must be
scoped so only the requesting player's hand is visible. Everyone else's hand
should be stripped.

Scoping is applied at the edges (router responses + SSE broadcast), not inside
the game manager, so the authoritative state stays intact.
"""

from __future__ import annotations

from src.game.manager import GameState, GameStatePlayerScoped
from src.game.types import PlayerId


def scope_state_for_player(
    state: GameState, player_id: PlayerId
) -> GameStatePlayerScoped:
    """
    Return the explicit player-scoped representation of `state`.
    """
    return state.to_player_scoped(player_id)

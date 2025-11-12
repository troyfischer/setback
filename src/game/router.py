from typing import Annotated, cast

import redis
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import ValidationError
from sqlmodel import select

from src.auth.sso.models import SSOUser
from src.auth.utils import get_cm, get_current_user
from src.db import DBSession
from src.game.exceptions import InvalidGameStateException
from src.game.manager import GameManager
from src.game.models import (
    BidRequest,
    Game,
    GameManagementRequest,
    PlayCardRequest,
    Player,
    Team,
    TeamMember,
)
from src.game.utils import get_game, get_player_in_game, get_team
from src.game.websocket import connection_manager
from src.logging import new_logger

logger = new_logger(__name__)

router = APIRouter(prefix="", dependencies=[Depends(get_current_user)])


redis_client = redis.from_url("redis://localhost:6379")  # pyright: ignore[reportUnknownMemberType]
print(redis_client)
gm = GameManager(redis_client)


@router.post("/game/create")
async def create(request: Request, db: DBSession):
    user = cast(SSOUser, request.state.user)

    game = Game(owner=user.sub)
    db.add(game)
    db.commit()
    db.refresh(game)

    return game


@router.post("/game/delete")
async def delete(
    request: Request,
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
):
    user = cast(SSOUser, request.state.user)
    if game.owner != user.sub:
        raise HTTPException(403, "only game owner may delete it")
    db.delete(game)
    db.commit()
    return game


@router.post("/game/join")
async def join_game(
    req: GameManagementRequest,
    request: Request,
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
):
    user = cast(SSOUser, request.state.user)

    if game.join_code != req.secret:
        raise HTTPException(400, "game join code does not match")

    p = Player(game_id=game.id, id=user.sub)
    p = db.merge(p)

    db.commit()
    db.refresh(p)

    return p


@router.post("/game/start")
def start_game(
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
):
    # TODO:
    # 1. ensure at least X teams
    # 2. ensure no empty teams
    # 3. ensure minimum players

    game_state = gm.start_game(game)

    game.started = True
    game = db.merge(game)
    return game_state


@router.post("/game/bid")
def bid_game(
    req: BidRequest,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
):
    try:
        return gm.bid_game(game, player, req)
    except InvalidGameStateException as e:
        raise HTTPException(400, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(400, detail=str(e)) from e


@router.post("/game/trick/play")
def play_trick(
    req: PlayCardRequest,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
):
    try:
        return gm.play_card(game, player, req.card)
    except InvalidGameStateException as e:
        raise HTTPException(400, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(400, detail=str(e)) from e


@router.post("/team/create")
async def create_team(
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
):
    # check if already owner of team
    team = db.exec(
        select(Team).where((Team.game_id == game.id) & (Team.owner == player.id))
    ).first()
    if team:
        raise HTTPException(400, "player already owner of team")

    t = Team(game_id=game.id, owner=player.id)

    db.add(t)
    db.flush()
    db.refresh(t)

    # owner should automatically be a member
    tm = TeamMember(game_id=game.id, team_id=t.id, player_id=player.id)
    db.add(tm)
    db.commit()
    db.refresh(t)  # not entirely clear why I have to refresh again...

    return t


@router.post("/team/delete")
async def delete_team(
    request: Request,
    db: DBSession,
    user: Annotated[SSOUser, Depends(get_current_user)],
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
):
    user = cast(SSOUser, request.state.user)

    team = db.exec(
        select(Team).where((Team.game_id == game.id) & (Team.owner == player.id))
    ).first()
    if not team or team.owner != user.sub:
        raise HTTPException(400, "team does not exist")
    if team.owner != user.sub:
        raise HTTPException(403, "owner must delete team")

    db.delete(team)
    db.commit()

    return team


@router.post("/team/join")
async def join_team(
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
    team: Annotated[Team, Depends(get_team)],
):
    member = db.get(TeamMember, (game.id, team.id, player.id))
    if member:
        return member

    tm = TeamMember(game_id=game.id, team_id=team.id, player_id=player.id)
    db.add(tm)
    db.commit()
    db.refresh(tm)

    return tm


@router.post("/team/leave")
async def leave_team(
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
    team: Annotated[Team, Depends(get_team)],
):
    member = db.get(TeamMember, (game.id, team.id, player.id))
    if not member:
        raise HTTPException(400, "player not part of team")

    db.delete(member)
    db.commit()

    return member


@router.websocket("/game/{game_id}/subscribe")
async def game_subscribe(
    request: Request, websocket: WebSocket, game_id: int, db: DBSession
):
    """
    WebSocket endpoint for clients to subscribe to game updates.

    Clients should connect to this endpoint after joining a game to receive
    real-time updates about bids, card plays, and game state changes.
    """
    # Verify the game exists
    game = db.get(Game, game_id)
    if not game:
        await websocket.close(code=1008, reason="Game not found")
        return

    # TODO: Verify the user is a player in this game
    # For now, we'll allow anyone to subscribe (you can add auth later)

    await get_cm(request).connect(game_id, websocket)

    try:
        # Keep the connection alive and handle any incoming messages
        # (though clients shouldn't send messages - they use REST for actions)
        while True:
            # Just receive to keep connection alive
            # Clients shouldn't send data here, but we need to await something
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("client disconnected", game_id=game_id)
    except Exception as e:
        logger.error("websocket error", game_id=game_id, error=str(e))
    finally:
        connection_manager.disconnect(game_id, websocket)

from typing import Annotated, cast

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

from src.auth.sso.models import OAuthUser
from src.auth.utils import get_current_user
from src.db import DBSession
from src.game.constants import Routes
from src.game.exceptions import InvalidGameStateException
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
from src.logging import new_logger
from src.request import RequestContext

logger = new_logger(__name__)


router = APIRouter(prefix=Routes.PREFIX, dependencies=[Depends(get_current_user)])


@router.post(Routes.Game.CREATE)
async def create(request: Request, db: DBSession):
    user = cast(OAuthUser, request.state.user)

    game = Game(owner=user.sub)
    db.add(game)
    db.commit()
    db.refresh(game)

    return game


@router.post(Routes.Game.DELETE)
async def delete(
    user: Annotated[OAuthUser, Depends(get_current_user)],
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
):
    if game.owner != user.sub:
        raise HTTPException(403, "only game owner may delete it")
    db.delete(game)
    db.commit()
    return game


@router.post(Routes.Game.JOIN)
async def join_game(
    req: GameManagementRequest,
    request: Request,
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
):
    user = cast(OAuthUser, request.state.user)

    if game.join_code != req.secret:
        raise HTTPException(400, "game join code does not match")

    p = Player(game_id=game.id, id=user.sub)
    p = db.merge(p)

    db.commit()
    db.refresh(p)

    return p


@router.post(Routes.Game.START)
def start_game(
    ctx: RequestContext,
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
):
    # TODO:
    # 1. ensure at least X teams
    # 2. ensure no empty teams
    # 3. ensure minimum players

    game_state = ctx.gm.start_game(game)

    game.started = True
    game = db.merge(game)
    return game_state


@router.post(Routes.Game.BID)
def bid_game(
    ctx: RequestContext,
    req: BidRequest,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
):
    try:
        return ctx.gm.bid_game(game, player, req)
    except InvalidGameStateException as e:
        raise HTTPException(400, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(400, detail=str(e)) from e


@router.post(Routes.Game.PLAY)
def play_trick(
    ctx: RequestContext,
    req: PlayCardRequest,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
):
    try:
        return ctx.gm.play_card(game, player, req.card)
    except InvalidGameStateException as e:
        raise HTTPException(400, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(400, detail=str(e)) from e


@router.post(Routes.Team.CREATE)
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


@router.post(Routes.Team.DELETE)
async def delete_team(
    db: DBSession,
    user: Annotated[OAuthUser, Depends(get_current_user)],
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
):
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


@router.post(Routes.Team.JOIN)
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


@router.post(Routes.Team.LEAVE)
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
    ctx: RequestContext,
    websocket: WebSocket,
    game_id: int,
    db: DBSession,
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

    await ctx.cm.connect(game_id, websocket)

    try:
        # Keep the connection alive and handle any incoming messages
        # (though clients shouldn't send messages - they use REST for actions)
        while True:
            # Just receive to keep connection alive
            # Clients shouldn't send data here, but we need to await something
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("client disconnected", game_id=game_id)
    except Exception as e:
        logger.error("websocket error", game_id=game_id, error=str(e))
    finally:
        ctx.cm.disconnect(game_id, websocket)

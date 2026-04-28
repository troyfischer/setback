import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated, cast

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from sqlmodel import select

from src.auth.jwt import JwtManager
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
from src.game.manager import GameStatePlayerScoped
from src.game.scope import scope_state_for_player
from src.game.sse import ConnectionManager
from src.game.utils import get_game, get_player_in_game, get_team
from src.logging import new_logger
from src.request import RequestContext

logger = new_logger(__name__)

SSE_HEARTBEAT_SECONDS = 15.0
SSE_RETRY_MILLISECONDS = 3000
SSE_AUDIENCE = "game_subscribe"
SSE_CONNECT_TOKEN_TTL_SECONDS = 60


class SubscribeTokenResponse(BaseModel):
    sse_token: str
    expires_in_seconds: int


async def sse_event_stream(
    game_id: int,
    player_id: str,
    connection_manager: ConnectionManager,
    *,
    heartbeat_seconds: float = SSE_HEARTBEAT_SECONDS,
) -> AsyncGenerator[str, None]:
    queue = connection_manager.connect(game_id, player_id)
    try:
        yield f"retry: {SSE_RETRY_MILLISECONDS}\n\n"
        while True:
            try:
                message = await asyncio.wait_for(
                    queue.get(),
                    timeout=heartbeat_seconds,
                )
                data = json.dumps(message)
                yield f"data: {data}\n\n"
            except TimeoutError:
                # Keep intermediate proxies and clients from timing out idle streams.
                yield ": keep-alive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        connection_manager.disconnect(game_id, player_id, queue)


router = APIRouter(prefix=Routes.PREFIX)
protected_router = APIRouter(
    prefix=Routes.PREFIX,
    dependencies=[Depends(get_current_user)],
)


@protected_router.post(Routes.Game.CREATE)
async def create(request: Request, db: DBSession):
    user = cast(OAuthUser, request.state.user)

    game = Game(owner=user.sub)
    db.add(game)
    db.commit()
    db.refresh(game)

    return game


@protected_router.post(Routes.Game.DELETE)
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


@protected_router.post(Routes.Game.JOIN)
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


@protected_router.post(Routes.Game.START)
def start_game(
    ctx: RequestContext,
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
    user: Annotated[OAuthUser, Depends(get_current_user)],
) -> GameStatePlayerScoped:
    # TODO:
    # 1. ensure at least X teams
    # 2. ensure no empty teams
    # 3. ensure minimum players

    game_state = ctx.gm.start_game(game)

    game.started = True
    game = db.merge(game)
    return scope_state_for_player(game_state, user.sub)


@protected_router.post(Routes.Game.BID)
def bid_game(
    ctx: RequestContext,
    req: BidRequest,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
) -> GameStatePlayerScoped:
    try:
        state = ctx.gm.bid_game(game, player, req)
    except InvalidGameStateException as e:
        raise HTTPException(400, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(400, detail=str(e)) from e
    return scope_state_for_player(state, player.id)


@protected_router.post(Routes.Game.PLAY)
def play_trick(
    ctx: RequestContext,
    req: PlayCardRequest,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
) -> GameStatePlayerScoped:
    try:
        state = ctx.gm.play_card(game, player, req.card)
    except InvalidGameStateException as e:
        raise HTTPException(400, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(400, detail=str(e)) from e
    return scope_state_for_player(state, player.id)


@protected_router.post(Routes.Team.CREATE)
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

    teams = db.exec(select(Team).where((Team.game_id == game.id)))
    team_number = max((t.team_number for t in teams), default=0)

    t = Team(game_id=game.id, owner=player.id, team_number=team_number + 1)

    db.add(t)
    db.flush()
    db.refresh(t)

    # owner should automatically be a member
    tm = TeamMember(game_id=game.id, team_id=t.id, player_id=player.id)
    db.add(tm)
    db.commit()
    db.refresh(t)  # not entirely clear why I have to refresh again...

    return t


@protected_router.post(Routes.Team.DELETE)
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


@protected_router.post(Routes.Team.JOIN)
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


@protected_router.post(Routes.Team.LEAVE)
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


@protected_router.post("/game/{game_id}/subscribe-token")
async def create_subscribe_token(
    game_id: int,
    user: Annotated[OAuthUser, Depends(get_current_user)],
    db: DBSession,
    jwt: JwtManager,
) -> SubscribeTokenResponse:
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(404, "Game not found")

    player = db.get(Player, (user.sub, game_id))
    if not player:
        raise HTTPException(403, "not an active player in game")

    token = jwt.create_sse_token(
        user.sub,
        game_id,
        audience=SSE_AUDIENCE,
        seconds_to_expire=SSE_CONNECT_TOKEN_TTL_SECONDS,
    )
    return SubscribeTokenResponse(
        sse_token=token,
        expires_in_seconds=SSE_CONNECT_TOKEN_TTL_SECONDS,
    )


@router.get("/game/{game_id}/subscribe", dependencies=[])
async def game_subscribe(
    ctx: RequestContext,
    game_id: int,
    db: DBSession,
    jwt: JwtManager,
    sse_token: str | None = None,
):
    """
    SSE endpoint for clients to subscribe to game updates.

    Clients should connect to this endpoint after joining a game to receive
    real-time updates about bids, card plays, and game state changes.
    """
    if not sse_token:
        raise HTTPException(401, "missing sse token")

    claims = jwt.validate_sse_token(
        sse_token,
        expected_game_id=game_id,
        expected_audience=SSE_AUDIENCE,
    )

    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(404, "Game not found")

    player = db.get(Player, (claims["sub"], game_id))
    if not player:
        raise HTTPException(403, "not an active player in game")

    return StreamingResponse(
        sse_event_stream(game_id, claims["sub"], ctx.cm),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@protected_router.get("/game/{game_id}/state")
def get_game_state(
    ctx: RequestContext,
    game_id: int,
    user: Annotated[OAuthUser, Depends(get_current_user)],
    db: DBSession,
) -> GameStatePlayerScoped:
    """
    Return the game state scoped to the requesting player's view.

    Useful for reconnecting clients and for driving per-player bots/tests
    without having to catch every mutation response.
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(404, "game not found")

    try:
        state = ctx.gm.get_state(game)
    except InvalidGameStateException as e:
        raise HTTPException(400, detail=str(e)) from e

    return scope_state_for_player(state, user.sub)


router.include_router(protected_router)

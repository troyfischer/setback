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
from sqlmodel import Session, col, func, select

from src.auth.jwt import JwtManager
from src.auth.sso.models import OAuthUser
from src.auth.utils import get_current_user
from src.db import DBSession
from src.game.manager import GameStatePlayerScoped
from src.game.models import (
    BidRequest,
    Game,
    GameStatus,
    LobbyState,
    PlayCardRequest,
    Player,
    Team,
    TeamMember,
    TeamWithMembers,
)
from src.game.scope import scope_state_for_player
from src.game.sse import ConnectionManager
from src.game.utils import get_game, get_player_in_game, require_owner
from src.request import RequestContext

router = APIRouter(prefix="/game", dependencies=[Depends(get_current_user)])
unauthenticated_router = APIRouter(prefix="/game")


@router.post("/create")
async def create_game(request: Request, db: DBSession):
    user = cast(OAuthUser, request.state.user)

    in_progress = db.exec(
        select(func.count())
        .select_from(Player)
        .join(Game, col(Game.id) == col(Player.game_id))
        .where(Player.id == user.sub)
        .where(Game.status != GameStatus.ENDED)
    ).one()

    if in_progress >= 5:
        raise HTTPException(429, "too many active games")

    game = Game(owner=user.sub)
    db.add(game)
    db.flush()
    db.add(Player(id=user.sub, game_id=game.id))
    db.commit()
    db.refresh(game)
    return game


@router.get("/games")
async def get_games(
    user: Annotated[OAuthUser, Depends(get_current_user)], db: DBSession
):
    return db.exec(
        select(Game)
        .outerjoin(TeamMember, col(Game.id) == col(TeamMember.game_id))
        .where((Game.owner == user.sub) | (TeamMember.player_id == user.sub))
        .where(Game.status != GameStatus.ENDED)
        .distinct()
    ).all()


@router.post("/delete")
async def delete_game(
    db: DBSession,
    game: Annotated[Game, Depends(require_owner)],
):
    db.delete(game)
    db.commit()
    return game


@router.post("/cancel")
async def cancel_game(
    db: DBSession,
    game: Annotated[Game, Depends(require_owner)],
):
    game.status = GameStatus.CANCELLED
    db.merge(game)
    db.commit()

    return game


@router.post("/leave")
async def leave_game(
    user: Annotated[OAuthUser, Depends(get_current_user)],
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
):
    p = Player(game_id=game.id, id=user.sub)
    db.delete(p)
    db.commit()

    return game


@router.post("/join")
async def join_game(
    request: Request,
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
):
    user = cast(OAuthUser, request.state.user)

    p = Player(game_id=game.id, id=user.sub)
    p = db.merge(p)

    db.commit()
    db.refresh(p)

    return p


@router.post("/start")
def start_game(
    ctx: RequestContext,
    db: DBSession,
    game: Annotated[Game, Depends(require_owner)],
    user: Annotated[OAuthUser, Depends(get_current_user)],
) -> GameStatePlayerScoped:
    game_state = ctx.gm.start_game(game)

    game.status = GameStatus.ACTIVE
    game = db.merge(game)
    db.commit()
    return scope_state_for_player(game_state, user.sub)


@router.post("/bid")
def bid_game(
    ctx: RequestContext,
    req: BidRequest,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
) -> GameStatePlayerScoped:
    try:
        state = ctx.gm.bid_game(game, player, req)
    except ValidationError as e:
        raise HTTPException(400, detail=str(e)) from e
    return scope_state_for_player(state, player.id)


@router.post("/trick/play")
def play_trick(
    ctx: RequestContext,
    req: PlayCardRequest,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
) -> GameStatePlayerScoped:
    try:
        state = ctx.gm.play_card(game, player, req.card)
    except ValidationError as e:
        raise HTTPException(400, detail=str(e)) from e
    return scope_state_for_player(state, player.id)


SSE_HEARTBEAT_SECONDS = 15.0
SSE_RETRY_MILLISECONDS = 3000
SSE_AUDIENCE = "game_subscribe"
SSE_CONNECT_TOKEN_TTL_SECONDS = 60


class SubscribeTokenResponse(BaseModel):
    sse_token: str
    expires_in_seconds: int


async def sse_event_stream(
    game_id: str,
    player_id: str,
    connection_manager: ConnectionManager,
    *,
    heartbeat_seconds: float = SSE_HEARTBEAT_SECONDS,
) -> AsyncGenerator[str, None]:
    queue = connection_manager.connect(game_id, player_id)
    try:
        # Browser EventSource retry configuration
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


@router.post("/{game_id}/subscribe-token")
async def create_subscribe_token(
    game_id: str,
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


@unauthenticated_router.get("/{game_id}/subscribe")
async def game_subscribe(
    ctx: RequestContext,
    game_id: str,
    jwt: JwtManager,
    sse_token: str | None = None,
):
    """
    SSE endpoint for clients to subscribe to game updates.

    Clients should connect to this endpoint after joining a game to receive
    real-time updates about bids, card plays, and game state changes.

    This endpoint does not use the standard Bearer token auth because the
    browser's EventSource API does not support custom headers. Instead, clients
    must first call POST /{game_id}/subscribe-token (which requires a valid
    Bearer token) to obtain a short-lived SSE token, then pass that token as
    the `sse_token` query parameter here.
    """
    if not sse_token:
        raise HTTPException(401, "missing sse token")

    claims = jwt.validate_sse_token(
        sse_token,
        expected_game_id=game_id,
        expected_audience=SSE_AUDIENCE,
    )

    # Use a short-lived session for validation so we don't hold a pool
    # connection for the lifetime of the SSE stream.
    with Session(ctx.db) as db:
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


@router.get("/{game_id}/lobby")
def get_lobby_state(
    game_id: str,
    user: Annotated[OAuthUser, Depends(get_current_user)],
    db: DBSession,
) -> LobbyState:
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(404, "game not found")

    if game.owner != user.sub:
        player = db.get(Player, (user.sub, game_id))
        if not player:
            raise HTTPException(403, "not an active player in game")

    teams = db.exec(select(Team).where(Team.game_id == game_id)).all()
    team_members = db.exec(
        select(TeamMember).where(TeamMember.game_id == game_id)
    ).all()
    players = db.exec(select(Player).where(Player.game_id == game_id)).all()

    members_by_team: dict[int, list[str]] = {}
    for m in team_members:
        members_by_team.setdefault(m.team_id, []).append(m.player_id)

    return LobbyState(
        game_owner=game.owner,
        teams=[
            TeamWithMembers(
                id=t.id,
                game_id=t.game_id,
                team_number=t.team_number,
                owner=t.owner,
                members=members_by_team.get(t.id, []),
            )
            for t in teams
        ],
        players=[p.id for p in players],
        game_status=game.status,
    )


@router.get("/{game_id}/state")
def get_game_state(
    ctx: RequestContext,
    game_id: str,
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
    state = ctx.gm.get_state(game)
    return scope_state_for_player(state, user.sub)

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import select

from src.auth.sso.models import SSOUser
from src.auth.utils import get_current_user
from src.db import DBSession
from src.game.models import Game, Player, Team, TeamMember

router = APIRouter(prefix="", dependencies=[Depends(get_current_user)])


@router.post("/game/create")
async def create(request: Request, db: DBSession):
    user = cast(SSOUser, request.state.user)
    owned_games = list(db.exec(select(Game).where(Game.owner == user.sub)))

    # for g in owned_games:
    #     print(g)
    #     db.delete(g)

    # if len(owned_games) >= 2:
    #     raise HTTPException(429, "user already owns 2 games")

    game = Game(owner=user.sub)
    db.add(game)
    db.commit()
    db.refresh(game)

    return game


class JoinRequest(BaseModel):
    id: int
    secret: str


class GameRequest(BaseModel):
    game_id: int


async def get_game(req: GameRequest, db: DBSession) -> Game:
    game = db.get(Game, req.game_id)
    if not game:
        raise HTTPException(404, "game id not found")
    return game


@router.post("/game/join")
async def join_game(
    join: JoinRequest,
    request: Request,
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
):
    user = cast(SSOUser, request.state.user)

    if game.join_code != join.secret:
        raise HTTPException(400, "game join code does not match")

    p = Player(game_id=game.id, id=user.sub)
    p = db.merge(p)

    db.commit()
    db.refresh(p)

    return p


class TeamRequest(GameRequest):
    player: str


async def get_player_in_game(req: TeamRequest, db: DBSession) -> Player:
    player = db.get(Player, (req.player, req.game_id))
    if not player:
        raise HTTPException(404, f"{req.player} not an active player in game")
    return player


@router.post("/team/create")
async def create_team(
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
):
    # check if already owner of team
    team = db.exec(
        select(Team).where(Team.game_id == game.id and Team.owner == player.id)
    ).first()
    if team:
        raise HTTPException(400, "player already owner of team")

    t = Team(game_id=game.id, owner=player.id)
    db.add(t)
    db.commit()
    db.refresh(t)

    # owner should automatically be a member
    tm = TeamMember(game_id=game.id, team_id=t.id, player_id=player.id)
    db.add(tm)
    db.commit()

    return t


@router.post("/team/delete")
async def delete_team(
    req: TeamRequest,
    db: DBSession,
    user: Annotated[SSOUser, Depends(get_current_user)],
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
):
    if req.player != user.sub:
        raise HTTPException(403, "owner must delete team")

    # check if owner of team
    team = db.exec(
        select(Team).where(Team.game_id == game.id and Team.owner == player.id)
    ).first()
    if not team:
        raise HTTPException(400, "team does not exist")

    db.delete(team)
    db.commit()

    return team


async def check_in_game(db: DBSession, sub: str, game_id: str | int):
    player = db.get(Player, (sub, game_id))
    if not player:
        raise HTTPException(404, sub + " not an active player in game")
    return player


class UpdateTeamRequest(TeamRequest):
    team_id: int


async def get_team(req: UpdateTeamRequest, db: DBSession) -> Team:
    team = db.get(Team, req.team_id)
    if not team:
        raise HTTPException(404, "team does not exist")
    return team


async def get_member(req: UpdateTeamRequest, db: DBSession) -> TeamMember:
    member = db.get(TeamMember, (req.game_id, req.team_id, req.player))
    if not member:
        raise HTTPException(404, "player not part of team")
    return member


@router.post("/team/join")
async def join_team(
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
    team: Annotated[Team, Depends(get_team)],
):
    # check if already part of a team
    member = db.get(TeamMember, (game.id, team.id, player.id))
    if member:
        raise HTTPException(400, "player already part of a team")

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
    # check if part of a team
    member = db.get(TeamMember, (game.id, team.id, player.id))
    if not member:
        raise HTTPException(400, "player not part of team")

    db.delete(member)
    db.commit()

    return member

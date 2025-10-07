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


class JoinSuccess(BaseModel):
    status: str = "success"
    player_id: str
    game_id: int


@router.post("/game/join")
async def join_game(join: JoinRequest, request: Request, db: DBSession):
    user = cast(SSOUser, request.state.user)

    game = db.get(Game, join.id)
    if not game:
        raise HTTPException(404, "game id not found")

    if game.join_code != join.secret:
        raise HTTPException(400, "game join code does not match")

    p = Player(game_id=game.id, id=user.sub)
    p = db.merge(p)

    db.commit()
    db.refresh(p)

    return p


class CreateTeamRequest(BaseModel):
    game_id: int
    owner: str


@router.post("/team/create")
async def create_team(create: CreateTeamRequest, db: DBSession):
    game = db.get(Game, create.game_id)
    if not game:
        raise HTTPException(404, "game id not found")

    # check players are part of game
    p = db.get(Player, (create.owner, game.id))
    if not p:
        raise HTTPException(404, create.owner + " not an active player in game")

    # check if already owner of team
    team = db.exec(
        select(Team).where(Team.game_id == game.id and Team.owner == p.id)
    ).first()
    if team:
        raise HTTPException(400, "player already owner of team")

    t = Team(game_id=game.id, owner=p.id)
    db.add(t)
    db.commit()
    db.refresh(t)

    # owner should automatically be a member
    tm = TeamMember(game_id=game.id, team_id=t.id, player_id=p.id)
    db.add(tm)
    db.commit()

    return t


@router.post("/team/delete")
async def delete_team(
    create: CreateTeamRequest,
    user: Annotated[SSOUser, Depends(get_current_user)],
    db: DBSession,
):
    game = db.get(Game, create.game_id)
    if not game:
        raise HTTPException(404, "game id not found")

    if create.owner != user.sub:
        raise HTTPException(403, "owner must delete team")

    # check players are part of game
    p = db.get(Player, (create.owner, game.id))
    if not p:
        raise HTTPException(404, create.owner + " not an active player in game")

    # check if owner of team
    team = db.exec(
        select(Team).where(Team.game_id == game.id and Team.owner == p.id)
    ).first()

    if not team:
        raise HTTPException(400, "team does not exist")

    db.delete(team)
    db.commit()

    return team


class JoinTeamRequest(BaseModel):
    game_id: int
    team_id: int
    player: str


@router.post("/team/join")
async def join_team(join: JoinTeamRequest, db: DBSession):
    game = db.get(Game, join.game_id)
    if not game:
        raise HTTPException(404, "game id not found")

    # check player part of game
    player = db.get(Player, (join.player, game.id))
    if not player:
        raise HTTPException(404, join.player + " not an active player in game")

    # check team exists
    team = db.get(Team, join.team_id)
    if not team:
        raise HTTPException(404, "team does not exist")

    # check if already part of a team
    member = db.get(TeamMember, (game.id, team.id, player.id))
    if member:
        raise HTTPException(400, "player already part of a team")

    tm = TeamMember(game_id=game.id, team_id=team.id, player_id=player.id)
    db.add(tm)
    db.commit()
    db.refresh(tm)

    return tm


class LeaveTeamRequest(BaseModel):
    game_id: int
    team_id: int
    player: str


@router.post("/team/leave")
async def leave_team(leave: LeaveTeamRequest, db: DBSession):
    game = db.get(Game, leave.team_id)
    if not game:
        raise HTTPException(404, "game id not found")

    # check player is part of game
    player = db.get(Player, (leave.player, game.id))
    if not player:
        raise HTTPException(404, leave.player + " not an active player in game")

    # check team exists
    team = db.get(Team, leave.team_id)
    if not team:
        raise HTTPException(404, "team does not exist")

    # check if part of a team
    member = db.get(TeamMember, (game.id, team.id, player.id))
    if not member:
        raise HTTPException(400, "player not part of team")

    db.delete(member)
    db.commit()

    return member

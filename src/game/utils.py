from typing import cast

from fastapi import HTTPException, Request

from src.auth.sso.models import SSOUser
from src.db import DBSession
from src.game.models import (
    Game,
    GameRequest,
    Player,
    Team,
    TeamMember,
    UpdateTeamRequest,
)


async def get_game(req: GameRequest, db: DBSession) -> Game:
    game = db.get(Game, req.game_id)
    if not game:
        raise HTTPException(404, "game id not found")
    return game


async def get_player_in_game(
    request: Request,
    req: GameRequest,
    db: DBSession,
) -> Player:
    user = cast(SSOUser, request.state.user)
    player = db.get(Player, (user.sub, req.game_id))
    if not player:
        raise HTTPException(404, f"{user.sub} not an active player in game")
    return player


async def check_in_game(db: DBSession, sub: str, game_id: str | int):
    player = db.get(Player, (sub, game_id))
    if not player:
        raise HTTPException(404, sub + " not an active player in game")
    return player


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

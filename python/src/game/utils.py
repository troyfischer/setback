from typing import Annotated

from fastapi import Depends, HTTPException
from sqlmodel import select

from src.auth.sso.models import OAuthUser
from src.auth.utils import get_current_user
from src.db import DBSession
from src.game.models import (
    Game,
    GameRequest,
    Player,
    Team,
    UpdateTeamRequest,
)


async def get_game(req: GameRequest, db: DBSession) -> Game:
    game = db.get(Game, req.game_id)
    if not game:
        raise HTTPException(404, "game id not found")
    return game


async def get_player_in_game(
    req: GameRequest,
    db: DBSession,
    user: Annotated[OAuthUser, Depends(get_current_user)],
) -> Player:
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
    team = db.exec(
        select(Team).where(
            Team.game_id == req.game_id, Team.team_number == req.team_number
        )
    ).first()
    if not team:
        raise HTTPException(404, "team does not exist")
    return team

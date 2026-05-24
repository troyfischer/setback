from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlmodel import select

from src.auth.sso.models import OAuthUser
from src.auth.utils import get_current_user
from src.db import DBSession
from src.game.models import (
    Game,
    Player,
    Team,
    TeamMember,
)
from src.game.utils import get_game, get_player_in_game, get_team

router = APIRouter(
    prefix="/team",
    dependencies=[Depends(get_current_user)],
)


def _get_team_membership(
    db: DBSession,
    game_id: str,
    player_id: str,
) -> TeamMember | None:
    return db.exec(
        select(TeamMember).where(
            (TeamMember.game_id == game_id) & (TeamMember.player_id == player_id)
        )
    ).first()


@router.post("/create")
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

    existing_membership = _get_team_membership(db, game.id, player.id)
    if existing_membership:
        raise HTTPException(400, "player already belongs to a team")

    teams = db.exec(select(Team).where(Team.game_id == game.id))
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


@router.post("/delete")
async def delete_team(
    db: DBSession,
    user: Annotated[OAuthUser, Depends(get_current_user)],
    team: Annotated[Team, Depends(get_team)],
):
    if team.owner != user.sub:
        raise HTTPException(403, "only the team owner can delete a team")

    db.delete(team)
    db.commit()

    return team


@router.post("/join")
async def join_team(
    db: DBSession,
    game: Annotated[Game, Depends(get_game)],
    player: Annotated[Player, Depends(get_player_in_game)],
    team: Annotated[Team, Depends(get_team)],
):
    existing_membership = _get_team_membership(db, game.id, player.id)
    if existing_membership:
        if existing_membership.team_id == team.id:
            return existing_membership
        raise HTTPException(400, "player already belongs to a different team")

    tm = TeamMember(game_id=game.id, team_id=team.id, player_id=player.id)
    db.add(tm)
    db.commit()
    db.refresh(tm)

    return tm


@router.post("/leave")
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

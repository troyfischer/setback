import datetime
import secrets
from typing import final

from sqlmodel import Field, ForeignKeyConstraint, SQLModel


class Game(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    join_code: str = Field(default_factory=lambda: secrets.token_urlsafe(8))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    owner: str = Field(foreign_key="ssouser.sub")


class Player(SQLModel, table=True):
    id: str = Field(foreign_key="ssouser.sub", primary_key=True)
    game_id: int = Field(foreign_key="game.id", primary_key=True)


class Team(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id")
    owner: str = Field(foreign_key="ssouser.sub")


class TeamMember(SQLModel, table=True):
    # one row per (game, player) -> belongs to exactly one team in that game
    game_id: int = Field(primary_key=True)
    team_id: int = Field(foreign_key="team.id", primary_key=True)
    player_id: str = Field(primary_key=True)

    # enforce the player exists (composite FK to Player)
    __table_args__ = (
        ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["player.game_id", "player.id"],
        ),
    )

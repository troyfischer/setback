from __future__ import annotations

import datetime
import enum
import itertools
import secrets
from abc import ABCMeta, abstractmethod
from typing import Literal, override

from pydantic import BaseModel
from pydantic import Field as PydField
from sqlalchemy import UniqueConstraint
from sqlmodel import Field as SqlField
from sqlmodel import ForeignKeyConstraint, SQLModel

# SQL Models


class Game(SQLModel, table=True):
    id: int = SqlField(default=None, primary_key=True)
    join_code: str = SqlField(default_factory=lambda: secrets.token_urlsafe(8))
    created_at: datetime.datetime = SqlField(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    owner: str = SqlField(foreign_key="oauthuser.sub")
    started: bool = False


class Player(SQLModel, table=True):
    id: str = SqlField(foreign_key="oauthuser.sub", primary_key=True)
    game_id: int = SqlField(foreign_key="game.id", primary_key=True)


class Team(SQLModel, table=True):
    id: int = SqlField(default=None, primary_key=True)
    game_id: int = SqlField(foreign_key="game.id")
    team_number: int
    owner: str = SqlField(foreign_key="oauthuser.sub")

    __table_args__ = (
        UniqueConstraint("game_id", "team_number"),
        UniqueConstraint("game_id", "id"),
    )


class TeamMember(SQLModel, table=True):
    # one row per (game, player) -> belongs to exactly one team in that game
    game_id: int = SqlField(primary_key=True)
    team_id: int = SqlField(primary_key=True)
    player_id: str = SqlField(primary_key=True)

    __table_args__ = (
        # enforce the player exists (composite FK to Player)
        ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["player.game_id", "player.id"],
        ),
        # enforce the team exists inside the same game
        ForeignKeyConstraint(
            ["game_id", "team_id"],
            ["team.game_id", "team.id"],
        ),
    )


# Request Models


class GameRequest(BaseModel):
    game_id: int


class GameManagementRequest(GameRequest):
    secret: str


class BidRequest(GameRequest):
    amount: Literal[0, 2, 3, 4]


class PlayCardRequest(GameRequest):
    card: SetbackCard


class UpdateTeamRequest(GameRequest):
    team_number: int


class TeamMembership(BaseModel):
    game_id: int
    player_id: str
    team_number: int


# Card Models


class Suit(enum.StrEnum):
    CLUB = "club"
    SPADE = "spade"
    HEART = "heart"
    DIAMOND = "diamond"

    @property
    def symbol(self) -> str:
        return {
            Suit.CLUB: "♣",
            Suit.HEART: "♥",
            Suit.DIAMOND: "♦",
            Suit.SPADE: "♠",
        }[self]


class FaceCard(enum.StrEnum):
    JACK = enum.auto()
    QUEEN = enum.auto()
    KING = enum.auto()
    ACE = enum.auto()

    @property
    def symbol(self) -> str:
        return {
            FaceCard.JACK: "J",
            FaceCard.QUEEN: "Q",
            FaceCard.KING: "K",
            FaceCard.ACE: "A",
        }[self]


class Card(BaseModel):
    value: int = PydField(ge=1, le=14)
    suit: Suit
    null: bool = False

    @override
    def __repr__(self) -> str:
        def fmt(v: str, s: Suit) -> str:
            return f"{v}{s.symbol}"

        match self.value:
            case 11:
                return fmt(FaceCard.JACK.symbol, self.suit)
            case 12:
                return fmt(FaceCard.QUEEN.symbol, self.suit)
            case 13:
                return fmt(FaceCard.KING.symbol, self.suit)
            case 1 | 14:
                return fmt(FaceCard.ACE.symbol, self.suit)
            case _:
                return fmt(str(self.value), self.suit)

    def __gt__(self, other: Card) -> bool:
        return other.null or self.value > other.value

    def __ge__(self, other: Card) -> bool:
        return other.null or self.value >= other.value

    def __lt__(self, other: Card) -> bool:
        return self.null or self.value < other.value

    def __le__(self, other: Card) -> bool:
        return self.null or self.value <= other.value

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Card):
            return (
                self.value == other.value
                and self.suit == other.suit
                and self.null == other.null
            )
        return False

    @staticmethod
    def JOKER() -> Card:
        class Joker(Card):
            @override
            def __repr__(self) -> str:
                return "JOKER"

        """
        A card that can be used in place of None for initial comparisons.
        """
        return Joker.model_construct(value=1, suit=None, null=True)


class SetbackCard(Card):
    @property
    def setback_value(self) -> int:
        match self.value:
            case 10:
                return 10
            case 11:
                return 1
            case 12:
                return 2
            case 13:
                return 3
            case 1 | 14:
                return 4
            case _:
                return 0


class Deck[CardT: Card](BaseModel, metaclass=ABCMeta):
    cards: list[CardT]

    def append(self, card: CardT) -> None:
        self.cards.append(card)

    def shuffle(self) -> None:
        import random

        random.shuffle(self.cards)

    def deal(self) -> CardT:
        return self.cards.pop()

    @staticmethod
    @abstractmethod
    def new(ace_high: bool = True) -> Deck[CardT]: ...

    @staticmethod
    @abstractmethod
    def empty() -> Deck[CardT]: ...


class SetbackDeck(Deck[SetbackCard]):
    @staticmethod
    @override
    def new(ace_high: bool = True) -> SetbackDeck:
        values = range(2, 15) if ace_high else range(1, 14)
        cards = [
            SetbackCard(value=v, suit=s) for v, s in itertools.product(values, Suit)
        ]
        return SetbackDeck(cards=cards)

    @staticmethod
    @override
    def empty() -> SetbackDeck:
        return SetbackDeck(cards=[])


class Bid(BaseModel):
    amount: int = PydField(ge=1, le=4)


class Dealer(BaseModel):
    user: str

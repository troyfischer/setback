from __future__ import annotations

import enum
import random
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from functools import cached_property
from typing import Literal, Self, cast, final, overload, override

import redis
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlmodel import Session, select
from structlog.types import FilteringBoundLogger

from src.game.exceptions import (
    InvalidCardException,
    InvalidGameStateException,
    InvalidPhaseException,
    InvalidTurnException,
)
from src.game.models import (
    BidRequest,
    Game,
    Player,
    SetbackCard,
    SetbackDeck,
    Suit,
    Team,
    TeamMember,
)
from src.game.types import PlayerId, TeamId
from src.logging import new_logger

"""
TODO: dealer can steal the bid if a player before passes and it is at least 2
"""


class RoundScore(BaseModel):
    high: tuple[TeamId, PlayedCard]
    low: tuple[TeamId, PlayedCard]
    jack: tuple[TeamId, PlayedCard] | None
    game: tuple[TeamId, int]

    @property
    def non_null_fields(self) -> Generator[tuple[TeamId, PlayedCard | int], None, None]:
        for f in RoundScore.model_fields:
            v = cast(tuple[TeamId, PlayedCard | int], getattr(self, f))
            if v:
                yield v

    @property
    def winning_teams(self) -> Generator[TeamId, None, None]:
        for t in self.non_null_fields:
            yield t[0]


class PlayedCard(SetbackCard):
    """
    A card played by an associated user.
    """

    player_id: PlayerId


class GamePlayer(BaseModel):
    player_id: PlayerId
    team_id: TeamId
    turn: int


class ModIdx(BaseModel):
    idx: int
    mod: int

    def __index__(self) -> int:
        return self.idx

    def __int__(self) -> int:
        return self.idx

    def __len__(self) -> int:
        return self.mod

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.idx == other
        elif isinstance(other, ModIdx):
            return self.idx == other.idx and self.mod == other.mod
        return False

    def __iadd__(self, other: int) -> Self:
        self.idx = (self.idx + other) % self.mod
        return self

    def __add__(self, other: int) -> ModIdx:
        new_idx = (self.idx + other) % self.mod
        return ModIdx(idx=new_idx, mod=self.mod)

    def __radd__(self, other: int) -> ModIdx:
        return self.__add__(other)


class Phase(enum.StrEnum):
    BID = enum.auto()
    PLAY = enum.auto()
    COMPLETE = enum.auto()


class Bid(BaseModel):
    amount: Literal[0, 2, 3, 4]
    player_id: PlayerId


class GameModel(BaseModel):
    game_id: int

    @cached_property
    def log(self) -> FilteringBoundLogger:
        return new_logger(self.__class__.__name__, game_id=self.game_id)


class TurnBased[Item](GameModel):
    turn: ModIdx = Field(description="index into order to indicate current player turn")
    collection: list[Item] = Field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return len(self.collection) == self.turn.mod

    def append(self, other: Item) -> None:
        self.collection.append(other)
        self.turn += 1


class Trick(TurnBased[PlayedCard]):
    def is_card_valid(
        self,
        hand: list[SetbackCard],
        card: SetbackCard,
        trump: Suit | None = None,
    ) -> bool:
        """
        First card of the first trick of the round is always valid (no trump
        card played yet). Otherwise a user may either play:

        1. a trump card
        2. a suit that matches the first played card of the trick
        3. a card of some other suit if they do not have 1 or 2
        """
        self.log.debug("checking card validity", card=card, trump=trump, hand=hand)

        if not trump:
            return True

        if len(self.collection) > 0:
            first_played: SetbackCard = self.collection[0]
        else:
            first_played = SetbackCard(value=1, suit=trump)

        return (
            card.suit == trump
            or card.suit == first_played.suit
            or not any(c.suit == first_played.suit for c in hand)
        )

    def best_card(self, trump: Suit) -> PlayedCard:
        """
        If a trump card is played in a trick then the best card is the highest
        trump. Otherwise the best card is the highest value card that matches
        the suit of the first card played of in the trick.
        """

        if not self.collection:
            raise InvalidGameStateException("cannot get best card from empty trick")

        trumps = [card for card in self.collection if card.suit == trump]
        first_suits = [
            card for card in self.collection if card.suit == self.collection[0].suit
        ]

        best = max(trumps, key=lambda card: card, default=None) or max(
            first_suits, key=lambda card: card
        )

        self.log.debug("best card of trick", card=best)

        return best


class BidRound(TurnBased[Bid]):
    @property
    def highest_bid(self) -> Bid:
        if not self.collection:
            raise InvalidGameStateException(
                "cannot get highest bid from empty bid round"
            )

        return max(self.collection, key=lambda b: b.amount)


class GameRound(GameModel):
    trump: Suit | None
    bid: BidRound
    trick: Trick | None
    hands: list[list[SetbackCard]] = Field(
        description="hand of each player, list order matches player order"
    )
    dealer: ModIdx = Field(description="index into order to indicate current dealer")
    tricks_won: dict[TeamId, list[Trick]] = Field(
        default_factory=dict, description="tricks won by a team"
    )
    score: RoundScore | None = None

    @property
    def player_count(self) -> int:
        return len(self.hands)

    @property
    def active_trump(self) -> Suit:
        if not self.trump:
            raise InvalidGameStateException("trump not set for current round")
        return self.trump

    @property
    def active_trick(self) -> Trick:
        if not self.trick:
            raise InvalidGameStateException("trick not set for current round")
        return self.trick

    @property
    def current_hand(self) -> list[SetbackCard]:
        return self.hands[self.active_trick.turn]

    @property
    def best_card_of_trick(self) -> PlayedCard:
        return self.active_trick.best_card(self.active_trump)

    @property
    def is_complete(self) -> bool:
        """
        A round is complete when each player has played every card in their
        hand.
        """
        return not any(hand for hand in self.hands)

    def ensure_trump(self, trump: Suit) -> None:
        self.trump = self.trump or trump

    def is_card_valid(self, card: SetbackCard) -> bool:
        return self.active_trick.is_card_valid(
            self.hands[self.active_trick.turn], card, self.trump
        )

    def next_round(self) -> GameRound:
        return self.new_round(self.game_id, self.player_count, self.dealer)

    def start_trick(self, turn: ModIdx) -> None:
        self.trick = Trick(game_id=self.game_id, turn=turn)

    def score_round(self) -> RoundScore:
        """
        After all tricks within a round have been played the round score is
        computed using the winning tricks assigned to each team.

        Setback scoring is concerned with the following:
        - high: highest TRUMP card played
        - low:  lowest TRUMP card played
        - jack: jack of TRUMP, if played
        - game: point tally of tens and face cards played
        """

        team_cards = {
            team_id: [card for trick in tricks for card in trick.collection]
            for team_id, tricks in self.tricks_won.items()
        }
        points = [
            (team_id, sum(card.setback_value for card in cards))
            for team_id, cards in team_cards.items()
        ]
        card_tuples = [
            (team_id, pc)
            for team_id, cards in team_cards.items()
            for pc in cards
            if pc.suit == self.active_trump
        ]

        high_tuple = max(card_tuples, key=lambda item: item[1])
        low_tuple = min(card_tuples, key=lambda item: item[1])
        jack_tuple = next(
            (team_pc for team_pc in card_tuples if team_pc[1].value == 11),
            None,
        )

        score = RoundScore(
            high=high_tuple,
            low=low_tuple,
            jack=jack_tuple,
            game=max(points, key=lambda item: item[1]),
        )
        self.score = score
        return score

    @staticmethod
    def new_round(
        game_id: int, players: int, dealer_idx: ModIdx | None = None
    ) -> GameRound:
        dealer_idx = dealer_idx or ModIdx(
            idx=random.randint(0, players - 1),
            mod=players,
        )
        deck = SetbackDeck.new()
        dealer = Dealer(deck)
        hands = dealer.deal(dealer_idx + 1)

        return GameRound(
            trump=None,
            game_id=game_id,
            hands=hands,
            dealer=dealer_idx,
            bid=BidRound(game_id=game_id, turn=dealer_idx + 1),
            trick=None,
        )


class PlayerOrder(BaseModel):
    order: list[GamePlayer]

    @overload
    def __getitem__(self, index: ModIdx) -> GamePlayer: ...

    @overload
    def __getitem__(self, index: PlayerId) -> GamePlayer: ...

    def __getitem__(self, index: ModIdx | PlayerId) -> GamePlayer:
        if isinstance(index, ModIdx):
            return self.order[index]

        for player in self.order:
            if player.player_id == index:
                return player
        raise KeyError(f"{index} not found")

    def get_team(self, player_id: PlayerId) -> TeamId:
        return self[player_id].team_id

    def get_idx(self, player_id: PlayerId) -> ModIdx:
        return ModIdx(idx=self[player_id].turn, mod=len(self.order))


class GameState(GameModel):
    max_score: int = 11
    phase: Phase
    score: dict[TeamId, int]
    order: PlayerOrder
    rounds: list[GameRound] = Field(default_factory=list)
    active_round: GameRound

    def next_phase(self) -> None:
        """
        A game moves between the 'bid' phase, which occurs at the start of each
        new round, and the 'play' phase, where users are adding cards to an
        active trick. The 'complete' phase is reached when a given team meets or
        exceeds the prefinded maximum score.
        """
        match self.phase:
            case Phase.BID:
                bid = self.active_round.bid.highest_bid
                self.active_round.start_trick(turn=self.order.get_idx(bid.player_id))
                self.phase = Phase.PLAY
            case Phase.PLAY:
                for team_id in self.score:
                    if self.score[team_id] >= self.max_score:
                        self.phase = Phase.COMPLETE
                        break
                else:
                    self.phase = Phase.BID
            case Phase.COMPLETE:
                raise InvalidGameStateException("game is finished")

        self.log.debug("next phase", phase=self.phase)

    @property
    def turn(self) -> ModIdx:
        match self.phase:
            case Phase.BID:
                return self.active_round.bid.turn
            case _:
                return self.active_round.active_trick.turn

    def _next_round(self) -> None:
        score = self.active_round.score_round()
        self.rounds.append(self.active_round)

        team_scores: defaultdict[TeamId, int] = defaultdict(int)
        for team_id in score.winning_teams:
            team_scores[team_id] += 1
            self.score[team_id] = self.score.get(team_id, 0) + 1

        self.active_round = self.active_round.next_round()
        self.next_phase()

    def _check_active_trick(self) -> None:
        if not self.active_round.active_trick.is_complete:
            return

        best_card = self.active_round.best_card_of_trick
        winning_team = self.order.get_team(best_card.player_id)
        self.active_round.tricks_won.setdefault(winning_team, []).append(
            self.active_round.active_trick
        )
        self.active_round.start_trick(self.order.get_idx(best_card.player_id))

    def _check_active_round(self) -> None:
        if self.active_round.is_complete:
            self._next_round()

    def process_bid(self, bid: Bid) -> None:
        self.active_round.bid.append(bid)

        if self.active_round.bid.is_complete:
            self.next_phase()

    def process_card(self, card: SetbackCard, player_id: str) -> None:
        self.active_round.ensure_trump(card.suit)

        if not self.active_round.is_card_valid(card):
            raise InvalidCardException("player must match suit when possible")

        pc = PlayedCard(value=card.value, suit=card.suit, player_id=player_id)
        self.active_round.current_hand.remove(pc)
        self.active_round.active_trick.append(pc)

        self._check_active_trick()
        self._check_active_round()

        self.log.debug("round details", phase=self.phase, score=self.score)


class RedisKeys:
    @staticmethod
    def game_state(game_id: int) -> str:
        return f"{game_id}:state"


@final
class Dealer:
    """
    setback specific dealer
    """

    CARDS_PER_DEAL = 3
    CARDS_PER_HAND = 6

    def __init__(self, deck: SetbackDeck):
        self.deck = deck

    def deal(self, start: ModIdx) -> list[list[SetbackCard]]:
        self.deck.shuffle()

        hands: list[list[SetbackCard]] = [[] for _ in range(start.mod)]

        for _ in range(self.CARDS_PER_HAND // self.CARDS_PER_DEAL):
            for i in range(len(hands)):
                for _ in range(self.CARDS_PER_DEAL):
                    hands[start + i].append(self.deck.deal())

        return hands


@final
class GameManager:
    """
    The game manager controls game state. It accesses and stores the state in redis.
    """

    def __init__(self, redis_client: redis.Redis, engine: Engine):
        self.redis = redis_client
        self.engine = engine
        self.log = new_logger(self.__class__.__name__)

    def _publish_event(self, event_type: str, game_state: GameState) -> None:
        """
        Publish a game event to Redis pub/sub.

        This allows all server instances to receive the event and broadcast
        to their connected WebSocket clients.
        """
        from src.game.events import EventType, GameEvent, RedisChannels

        try:
            event = GameEvent(
                event_type=EventType(event_type),
                game_id=game_state.game_id,
                data=game_state.model_dump(),
            )

            channel = RedisChannels.game(game_state.game_id)
            pub = cast(bool, self.redis.publish(channel, event.model_dump_json()))
            if not pub:
                raise Exception("unknown redis error")
            self.log.debug(
                "published event to redis",
                event_type=event_type,
                game_id=game_state.game_id,
                channel=channel,
            )
        except Exception as e:
            self.log.error(
                "failed to publish event",
                error=str(e),
                event_type=event_type,
                game_id=game_state.game_id,
            )

    def start_game(self, game: Game) -> GameState:
        with Session(self.engine) as db:
            teams = list(db.exec(select(Team).where(Team.game_id == game.id)).all())
            members: dict[int, list[TeamMember]] = defaultdict(list)
            for team in teams:
                for member in db.exec(
                    select(TeamMember).where(
                        (TeamMember.game_id == game.id)
                        & (TeamMember.team_id == team.id)
                    )
                ).all():
                    members[team.id].append(member)

        order: list[TeamMember] = []
        for grouped_team in zip(*members.values(), strict=True):
            order.extend(grouped_team)

        gs = GameState(
            game_id=game.id,
            order=PlayerOrder(
                order=[
                    GamePlayer(
                        player_id=member.player_id,
                        team_id=member.team_id,
                        turn=i,
                    )
                    for i, member in enumerate(order)
                ]
            ),
            phase=Phase.BID,
            score={team.id: 0 for team in teams},
            active_round=GameRound.new_round(game.id, len(order)),
        )

        self._save_state(gs)
        self._publish_event("game_started", gs)

        return gs

    def _load_state(self, game: Game) -> GameState:
        state = self.redis.get(RedisKeys.game_state(game.id))
        if not state:
            raise InvalidGameStateException("game has not been started")
        return GameState.model_validate_json(cast(bytes, state))

    def _save_state(self, state: GameState) -> None:
        redis_set = cast(
            bool,
            self.redis.set(
                RedisKeys.game_state(state.game_id),
                state.model_dump_json(),
            ),
        )
        if not redis_set:
            raise InvalidGameStateException("failed to save game state to redis")

    def _validate_state(self, gs: GameState, phase: Phase, player: str) -> None:
        if gs.phase != phase:
            raise InvalidPhaseException(f"game is not in the {phase} phase")

        current_player = gs.order[gs.turn]
        if current_player.player_id != player:
            raise InvalidTurnException("it is not this player's turn")

    @contextmanager
    def _game_state_context(
        self,
        game: Game,
        expected_phase: Phase,
        expected_player: str,
    ) -> Generator[GameState, None, None]:
        """
        Context manager for game state operations.

        Loads state, validates request against existing state, yields state,
        then saves it back.
        """
        gs = self._load_state(game)

        self._validate_state(gs, expected_phase, expected_player)

        try:
            yield gs
        finally:
            self._save_state(gs)

    def bid_game(self, game: Game, player: Player, bid: BidRequest) -> GameState:
        with self._game_state_context(game, Phase.BID, player.id) as gs:
            gs.process_bid(Bid(amount=bid.amount, player_id=player.id))
            self._publish_event("bid_placed", gs)
        return gs

    def play_card(self, game: Game, player: Player, card: SetbackCard) -> GameState:
        with self._game_state_context(game, Phase.PLAY, player.id) as gs:
            gs.process_card(card, player.id)
            self._publish_event("card_played", gs)
        return gs

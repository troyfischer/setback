# type: ignore
# pyright: basic
import contextlib
from collections import namedtuple
from dataclasses import dataclass
from typing import final

import pytest

from src.game.exceptions import InvalidGameStateException
from src.game.manager import (
    Bid,
    BidRound,
    Dealer,
    GamePlayer,
    GameRound,
    GameState,
    ModIdx,
    Phase,
    PlayedCard,
    PlayerOrder,
    RoundScore,
    Trick,
)
from src.game.models import SetbackCard, Suit

TEAM_ID = 1


@final
@pytest.mark.parametrize(
    "test_case",
    [
        (
            RoundScore(
                high=(
                    TEAM_ID,
                    PlayedCard(value=3, suit=Suit.CLUB, player_id="abc"),
                ),
                low=(TEAM_ID, PlayedCard(value=2, suit=Suit.CLUB, player_id="abc")),
                jack=(
                    TEAM_ID,
                    PlayedCard(value=11, suit=Suit.CLUB, player_id="abc"),
                ),
                game=(TEAM_ID, 10),
            ),
            4,
        ),
        (
            RoundScore(
                high=(
                    TEAM_ID,
                    PlayedCard(value=3, suit=Suit.CLUB, player_id="abc"),
                ),
                low=(TEAM_ID, PlayedCard(value=2, suit=Suit.CLUB, player_id="abc")),
                jack=None,
                game=(TEAM_ID, 10),
            ),
            3,
        ),
    ],
)
class TestRoundScore:
    @pytest.fixture
    def score(self, test_case) -> RoundScore:
        return test_case[0]

    @pytest.fixture
    def non_null(self, test_case) -> int:
        return test_case[1]

    def test_non_null_fields(self, score: RoundScore, non_null: int):
        assert len(list(score.non_null_fields)) == non_null

    def test_get_winning_teams(self, score: RoundScore):
        for team in score.winning_teams:
            assert team == TEAM_ID


class TestTrick:
    TRUMP_SUIT = Suit.CLUB
    NON_TRUMP_SUIT = Suit.HEART
    OTHER_SUIT = Suit.DIAMOND

    @pytest.fixture
    def empty_trick(self):
        return Trick(game_id="1", turn=ModIdx(idx=0, mod=1))

    @pytest.fixture
    def populated_trick(self):
        return Trick(
            game_id="1",
            turn=ModIdx(idx=0, mod=1),
            collection=[PlayedCard(value=2, suit=self.NON_TRUMP_SUIT, player_id="1")],
        )

    TC = namedtuple("TestCase", ["hand", "card", "trump", "valid"])

    @pytest.mark.parametrize(
        "tc",
        [
            TC([], SetbackCard.JOKER(), None, True),
            TC([], SetbackCard.JOKER(), TRUMP_SUIT, True),
            TC(
                [SetbackCard(value=2, suit=TRUMP_SUIT)],
                SetbackCard.JOKER(),
                TRUMP_SUIT,
                False,
            ),
            TC(
                [SetbackCard(value=2, suit=NON_TRUMP_SUIT)],
                SetbackCard.JOKER(),
                TRUMP_SUIT,
                True,
            ),
        ],
        ids=[
            "everything valid before trump",
            "nothing else in hand to play",
            "card in hand should have been played",
            "nothing else in hand is valid",
        ],
    )
    def test_is_card_valid_empty_trick(self, empty_trick: Trick, tc: TC):
        assert empty_trick.is_card_valid(tc.hand, tc.card, tc.trump) == tc.valid

    @pytest.mark.parametrize(
        "tc",
        [
            TC([], SetbackCard.JOKER(), None, True),
            TC([], SetbackCard.JOKER(), TRUMP_SUIT, True),
            TC(
                [SetbackCard(value=2, suit=TRUMP_SUIT)],
                SetbackCard.JOKER(),
                TRUMP_SUIT,
                True,
            ),
            TC(
                [SetbackCard(value=2, suit=NON_TRUMP_SUIT)],
                SetbackCard.JOKER(),
                TRUMP_SUIT,
                False,
            ),
            TC(
                [SetbackCard(value=2, suit=NON_TRUMP_SUIT)],
                SetbackCard(value=2, suit=NON_TRUMP_SUIT),
                TRUMP_SUIT,
                True,
            ),
        ],
        ids=[
            "everything valid before trump",
            "nothing else in hand to play",
            "no suit in hand matches suit of first card in trick",
            "played card does not match first card of trick and hand does",
            "played card still matches first card of trick",
        ],
    )
    def test_is_card_valid_populated_trick(self, populated_trick: Trick, tc: TC):
        assert populated_trick.is_card_valid(tc.hand, tc.card, tc.trump) == tc.valid

    @pytest.mark.parametrize(
        "trick,trump,expected",
        [
            (
                Trick(game_id="1", turn=ModIdx(idx=0, mod=1)),
                TRUMP_SUIT,
                InvalidGameStateException,
            ),
            (
                Trick(
                    game_id="1",
                    turn=ModIdx(idx=0, mod=1),
                    collection=[PlayedCard(value=2, suit=TRUMP_SUIT, player_id="1")],
                ),
                TRUMP_SUIT,
                PlayedCard(value=2, suit=TRUMP_SUIT, player_id="1"),
            ),
            (
                Trick(
                    game_id="1",
                    turn=ModIdx(idx=0, mod=1),
                    collection=[
                        PlayedCard(value=2, suit=NON_TRUMP_SUIT, player_id="1")
                    ],
                ),
                TRUMP_SUIT,
                PlayedCard(value=2, suit=NON_TRUMP_SUIT, player_id="1"),
            ),
        ],
    )
    def test_best_card(self, trick, trump, expected):
        with (
            pytest.raises(expected)
            if not isinstance(expected, SetbackCard)
            else contextlib.nullcontext()
        ):
            assert trick.best_card(trump) == expected


class TestBidRound:
    @pytest.mark.parametrize(
        "bid_round,expected",
        [
            (
                BidRound(game_id="1", turn=ModIdx(idx=0, mod=1)),
                InvalidGameStateException,
            ),
            (
                BidRound(
                    game_id="1",
                    turn=ModIdx(idx=0, mod=1),
                    collection=[Bid(amount=2, player_id="1")],
                ),
                Bid(amount=2, player_id="1"),
            ),
            (
                BidRound(
                    game_id="1",
                    turn=ModIdx(idx=0, mod=1),
                    collection=[
                        Bid(amount=2, player_id="1"),
                        Bid(amount=4, player_id="1"),
                    ],
                ),
                Bid(amount=4, player_id="1"),
            ),
        ],
    )
    def test_highest_bid(self, bid_round: BidRound, expected):
        with (
            pytest.raises(expected)
            if not isinstance(expected, Bid)
            else contextlib.nullcontext()
        ):
            assert bid_round.highest_bid == expected

    @pytest.mark.parametrize(
        "bid_round,next_bid,expected",
        [
            (
                BidRound(
                    game_id="1",
                    turn=ModIdx(idx=1, mod=2),
                    collection=[Bid(amount=2, player_id="1")],
                ),
                Bid(amount=2, player_id="2"),
                InvalidGameStateException,
            ),
            (
                BidRound(
                    game_id="1",
                    turn=ModIdx(idx=1, mod=2),
                    collection=[Bid(amount=2, player_id="1")],
                ),
                Bid(amount=3, player_id="2"),
                None,
            ),
            (
                BidRound(
                    game_id="1",
                    turn=ModIdx(idx=1, mod=2),
                    collection=[Bid(amount=0, player_id="1")],
                ),
                Bid(amount=0, player_id="2"),
                None,
            ),
        ],
        ids=["same bid fails", "higher bid succeeds", "pass bid succeeds"],
    )
    def test_new_bid(
        self,
        bid_round: BidRound,
        next_bid: Bid,
        expected: InvalidGameStateException | None,
    ):
        with (
            pytest.raises(expected)
            if expected is not None
            else contextlib.nullcontext()
        ):
            bid_round.new_bid(next_bid)
            assert bid_round.collection[-1] == next_bid


class TestGameStateBidding:
    @pytest.fixture
    def game_state(self) -> GameState:
        return GameState(
            game_id=GAME_ID,
            max_score=11,
            phase=Phase.BID,
            score={TEAM_A: 0, TEAM_B: 0},
            order=PlayerOrder(
                order=[
                    GamePlayer(player_id="A1", team_id=TEAM_A, turn=0),
                    GamePlayer(player_id="B1", team_id=TEAM_B, turn=1),
                    GamePlayer(player_id="A2", team_id=TEAM_A, turn=2),
                    GamePlayer(player_id="B2", team_id=TEAM_B, turn=3),
                ]
            ),
            active_round=GameRound(
                game_id=GAME_ID,
                trump=None,
                hands=[[], [], [], []],
                dealer=ModIdx(idx=3, mod=4),
                bid=BidRound(game_id=GAME_ID, turn=ModIdx(idx=0, mod=4)),
                trick=None,
            ),
        )

    def test_next_phase_keeps_highest_bid(self, game_state: GameState):
        game_state.active_round.bid.collection = [
            Bid(amount=0, player_id="A1"),
            Bid(amount=2, player_id="B1"),
            Bid(amount=0, player_id="A2"),
            Bid(amount=0, player_id="B2"),
        ]
        game_state.next_phase()

        assert game_state.active_round.bid.highest_bid == Bid(amount=2, player_id="B1")

    def test_next_phase_forces_dealer_bid_after_all_pass(self, game_state: GameState):
        game_state.active_round.bid.collection = [
            Bid(amount=0, player_id="A1"),
            Bid(amount=0, player_id="B1"),
            Bid(amount=0, player_id="A2"),
            Bid(amount=0, player_id="B2"),
        ]
        game_state.next_phase()

        assert game_state.phase == Phase.PLAY
        assert game_state.active_round.bid.highest_bid.amount == 0
        assert game_state.active_round.active_trick.turn == ModIdx(idx=3, mod=4)


TEAM_A = 1
TEAM_B = 2
GAME_ID = "1"


@dataclass
class GameRoundConfig:
    hands: list | None = None
    trump: Suit | None = None
    trick: Trick | None = None


class TestGameRound:
    @pytest.fixture
    def gr(self, request) -> GameRound:
        cfg = GameRoundConfig()
        if hasattr(request, "param"):
            cfg = request.param
        hands = cfg.hands or [[], []]
        mod = len(hands)
        return GameRound(
            game_id=GAME_ID,
            trump=cfg.trump,
            bid=BidRound(game_id=GAME_ID, turn=ModIdx(idx=0, mod=mod)),
            trick=cfg.trick,
            hands=hands,
            dealer=ModIdx(idx=0, mod=mod),
        )


class TestBasics(TestGameRound):
    @pytest.mark.parametrize(
        "gr,expected",
        [
            (GameRoundConfig(hands=[[], [], []]), 3),
        ],
        indirect=["gr"],
    )
    def test_player_count(self, gr: GameRound, expected: int):
        assert gr.player_count == expected

    @pytest.mark.parametrize(
        "gr,expected",
        [
            (GameRoundConfig(trump=None), InvalidGameStateException),
            (GameRoundConfig(trump=Suit.CLUB), Suit.CLUB),
        ],
        indirect=["gr"],
    )
    def test_active_trump(self, gr: GameRound, expected):
        with (
            pytest.raises(expected)
            if not isinstance(expected, Suit)
            else contextlib.nullcontext()
        ):
            assert gr.active_trump == expected

    def test_ensure_trump_idempotency(self, gr: GameRound):
        gr.ensure_trump(Suit.CLUB)
        assert gr.active_trump == Suit.CLUB

        # Should not overwrite once set
        gr.ensure_trump(Suit.HEART)
        assert gr.active_trump == Suit.CLUB

    @pytest.mark.parametrize(
        "gr,expected",
        [
            (GameRoundConfig(trick=None), InvalidGameStateException),
            (
                GameRoundConfig(trick=Trick(game_id="1", turn=ModIdx(idx=0, mod=3))),
                Trick(game_id="1", turn=ModIdx(idx=0, mod=3)),
            ),
        ],
        indirect=["gr"],
    )
    def test_active_trick(self, gr: GameRound, expected):
        with (
            pytest.raises(expected)
            if not isinstance(expected, Trick)
            else contextlib.nullcontext()
        ):
            assert gr.active_trick == expected

    HANDS = [
        [SetbackCard(value=2, suit=Suit.HEART)],
        [SetbackCard(value=3, suit=Suit.HEART)],
    ]

    @pytest.mark.parametrize(
        "gr,hands",
        [(GameRoundConfig(hands=HANDS), HANDS)],
        indirect=["gr"],
    )
    def test_start_trick_sets_active_trick(
        self, gr: GameRound, hands: list[list[SetbackCard]]
    ):
        gr.start_trick(ModIdx(idx=1, mod=2))
        assert gr.active_trick.turn == ModIdx(idx=1, mod=2)
        assert gr.current_hand == hands[1]


class TestCardValidation(TestGameRound):
    @pytest.mark.parametrize(
        "gr,turn,first_card,card_to_play,expected",
        [
            (
                GameRoundConfig(
                    hands=[[SetbackCard(value=10, suit=Suit.CLUB)], []],
                    trump=None,
                ),
                ModIdx(idx=0, mod=2),
                None,
                SetbackCard(value=10, suit=Suit.CLUB),
                True,
            ),
            (
                GameRoundConfig(
                    hands=[
                        [
                            SetbackCard(value=6, suit=Suit.HEART),
                            SetbackCard(value=7, suit=Suit.DIAMOND),
                        ],
                        [],
                    ],
                    trump=Suit.CLUB,
                ),
                ModIdx(idx=0, mod=2),
                PlayedCard(value=2, suit=Suit.HEART, player_id="X"),
                SetbackCard(value=7, suit=Suit.DIAMOND),
                False,
            ),
            (
                GameRoundConfig(
                    hands=[[SetbackCard(value=7, suit=Suit.DIAMOND)], []],
                    trump=Suit.CLUB,
                ),
                ModIdx(idx=0, mod=2),
                PlayedCard(value=2, suit=Suit.HEART, player_id="X"),
                SetbackCard(value=7, suit=Suit.DIAMOND),
                True,
            ),
            (
                GameRoundConfig(
                    hands=[[SetbackCard(value=9, suit=Suit.CLUB)], []],
                    trump=Suit.CLUB,
                ),
                ModIdx(idx=0, mod=2),
                PlayedCard(value=5, suit=Suit.HEART, player_id="X"),
                SetbackCard(value=9, suit=Suit.CLUB),
                True,
            ),
        ],
        ids=[
            "no_trump_allows_any_card",
            "must_follow_suit_when_possible",
            "off_suit_when_no_match",
            "playing_trump_is_valid",
        ],
        indirect=["gr"],
    )
    def test_is_card_valid(
        self,
        gr: GameRound,
        turn: ModIdx,
        first_card: PlayedCard | None,
        card_to_play: SetbackCard,
        expected: bool,
    ):
        gr.start_trick(turn)
        if first_card:
            gr.active_trick.collection.append(first_card)
        assert gr.is_card_valid(card_to_play) is expected


class TestBestCardAndCompletion(TestGameRound):
    @pytest.mark.parametrize(
        "gr,collection,expected",
        [
            (
                GameRoundConfig(hands=[[], []], trump=Suit.CLUB),
                [
                    PlayedCard(value=5, suit=Suit.HEART, player_id="A"),
                    PlayedCard(value=2, suit=Suit.CLUB, player_id="B"),
                ],
                PlayedCard(value=2, suit=Suit.CLUB, player_id="B"),
            ),
            (
                GameRoundConfig(hands=[[], []], trump=Suit.CLUB),
                [
                    PlayedCard(value=4, suit=Suit.HEART, player_id="A"),
                    PlayedCard(value=10, suit=Suit.HEART, player_id="B"),
                ],
                PlayedCard(value=10, suit=Suit.HEART, player_id="B"),
            ),
        ],
        indirect=["gr"],
        ids=["trump_wins", "lead_suit_high_wins"],
    )
    def test_best_card_of_trick(
        self, gr: GameRound, collection: list[PlayedCard], expected: PlayedCard
    ):
        gr.trick = Trick(game_id=GAME_ID, turn=ModIdx(idx=0, mod=len(gr.hands)))
        gr.active_trick.collection.extend(collection)
        assert gr.best_card_of_trick == expected

    @pytest.mark.parametrize(
        "gr,expected",
        [
            (GameRoundConfig(hands=[[], [], []]), True),
            (
                GameRoundConfig(
                    hands=[[SetbackCard(value=2, suit=Suit.HEART)], [], []]
                ),
                False,
            ),
        ],
        indirect=["gr"],
        ids=["complete_true", "complete_false"],
    )
    def test_is_complete(self, gr: GameRound, expected: bool):
        assert gr.is_complete is expected


class TestLifecycle(TestGameRound):
    @pytest.mark.parametrize(
        "gr,dealer",
        [
            (
                GameRoundConfig(hands=[[], [], [], []], trump=Suit.HEART),
                ModIdx(idx=2, mod=4),
            ),
        ],
        indirect=["gr"],
    )
    def test_next_round_properties(self, gr: GameRound, dealer: ModIdx):
        gr.dealer = dealer
        gr.bid.turn = dealer + 1

        nr = gr.next_round()
        assert nr.game_id == gr.game_id
        assert nr.dealer == gr.dealer
        assert nr.player_count == gr.player_count
        assert nr.trump is None
        assert nr.trick is None
        assert all(len(h) == Dealer.CARDS_PER_HAND for h in nr.hands)
        assert nr.bid.turn == dealer + 1

    @pytest.mark.parametrize(
        "gr",
        [(GameRoundConfig(trump=Suit.CLUB))],
        indirect=["gr"],
    )
    def test_score_round_high_low_jack_and_game(self, gr: GameRound):
        trick_a = Trick(game_id=GAME_ID, turn=ModIdx(idx=0, mod=2))
        trick_a.collection.extend(
            [
                PlayedCard(value=11, suit=Suit.CLUB, player_id="A1"),
                PlayedCard(value=10, suit=Suit.HEART, player_id="A2"),
                PlayedCard(value=3, suit=Suit.DIAMOND, player_id="A3"),
            ]
        )

        trick_b = Trick(game_id=GAME_ID, turn=ModIdx(idx=1, mod=2))
        trick_b.collection.extend(
            [
                PlayedCard(value=2, suit=Suit.CLUB, player_id="B1"),
                PlayedCard(value=7, suit=Suit.HEART, player_id="B2"),
            ]
        )

        gr.tricks_won = {
            TEAM_A: [trick_a],
            TEAM_B: [trick_b],
        }

        score = gr.score_round()

        assert score.high == (
            TEAM_A,
            PlayedCard(value=11, suit=Suit.CLUB, player_id="A1"),
        )
        assert score.low == (
            TEAM_B,
            PlayedCard(value=2, suit=Suit.CLUB, player_id="B1"),
        )
        assert score.jack == (
            TEAM_A,
            PlayedCard(value=11, suit=Suit.CLUB, player_id="A1"),
        )
        assert score.game[0] == TEAM_A
        assert gr.score == score

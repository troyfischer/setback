import itertools
from http import HTTPStatus
import random
from urllib.parse import urljoin

import httpx
import pytest

from src.game.manager import GameState, Phase
from src.game.models import (
    BidRequest,
    Game,
    GameManagementRequest,
    GameRequest,
    PlayCardRequest,
    Team,
    UpdateTeamRequest,
)

USERS = [f"user{i}" for i in range(6)]

BASE_URL = "http://localhost:8000/"


authenticated_users: dict[str, str] = {}


@pytest.fixture(autouse=True)
def print_first_line():
    # auto prints one line to stdout for cleaner formatting
    print()


def create_users() -> None:
    for user in USERS:
        res = httpx.post(
            urljoin(BASE_URL, "/auth/token"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"username": user, "password": "testpassword"},
        )

        assert res.status_code == HTTPStatus.OK
        data: dict[str, str] = res.json()
        access_token: str = data["access_token"]
        authenticated_users[user] = access_token


@pytest.fixture(scope="module")
def game():
    create_users()

    res = httpx.post(
        urljoin(BASE_URL, "/game/create"),
        headers={"Authorization": "Bearer " + authenticated_users[USERS[0]]},
    )

    assert res.status_code == HTTPStatus.OK

    return Game(**res.json())


def test_game(game: Game):
    print(game)


@pytest.fixture(scope="module")
def join_game(game: Game):
    for user in USERS:
        res = httpx.post(
            urljoin(BASE_URL, "/game/join"),
            headers={
                "Authorization": "Bearer " + authenticated_users[user],
            },
            json=GameManagementRequest(
                game_id=game.id, secret=game.join_code
            ).model_dump(),
        )

        assert res.status_code == HTTPStatus.OK


@pytest.fixture(scope="module")
def create_teams(game: Game, join_game) -> list[Team]:
    teams: list[Team] = []
    for owner, _ in itertools.batched(USERS, 2):
        res = httpx.post(
            urljoin(BASE_URL, "/team/create"),
            headers={
                "Authorization": "Bearer " + authenticated_users[owner],
            },
            json=GameRequest(game_id=game.id).model_dump(),
        )
        assert res.status_code == HTTPStatus.OK
        teams.append(Team.model_validate(res.json()))

    return teams


@pytest.fixture(scope="module")
def join_team(create_teams: list[Team]):
    for team, members in zip(create_teams, itertools.batched(USERS, 2), strict=True):
        for member in members:
            res = httpx.post(
                urljoin(BASE_URL, "/team/join"),
                headers={
                    "Authorization": "Bearer " + authenticated_users[member],
                },
                json=UpdateTeamRequest(
                    game_id=team.game_id, team_id=team.id
                ).model_dump(),
            )
            assert res.status_code == HTTPStatus.OK


def test_join_team(join_team):
    pass


@pytest.fixture(scope="module")
def start_game(game: Game, join_team) -> GameState:
    res = httpx.post(
        urljoin(BASE_URL, "/game/start"),
        headers={
            "Authorization": "Bearer " + authenticated_users[USERS[0]],
        },
        json=GameRequest(game_id=game.id).model_dump(),
    )

    game_state = GameState.model_validate(res.json())
    return game_state


def do_bidding(game_state: GameState) -> GameState:
    starting_turn = game_state.turn

    for _ in range(len(USERS)):
        res = httpx.post(
            urljoin(BASE_URL, "/game/bid"),
            headers={
                "Authorization": "Bearer "
                + authenticated_users[game_state.order[game_state.turn].player_id],
            },
            json=BidRequest(game_id=game_state.game_id, amount=2).model_dump(),
        )

        assert res.status_code == HTTPStatus.OK
        game_state = GameState.model_validate(res.json())

    assert game_state.phase != Phase.BID
    assert game_state.active_round.bid.turn == starting_turn

    return game_state


@pytest.fixture(scope="module")
def bid_game(start_game: GameState) -> GameState:
    return do_bidding(start_game)


def test_bid_game(bid_game):
    pass


def test_play_single_trick(bid_game: GameState):
    game_state = bid_game

    print(game_state.order)

    for _ in range(len(USERS)):
        card = game_state.active_round.current_hand[0]
        for possible_card in game_state.active_round.current_hand:
            if game_state.active_round.is_card_valid(possible_card):
                card = possible_card

        res = httpx.post(
            urljoin(BASE_URL, "/game/trick/play"),
            headers={
                "Authorization": "Bearer "
                + authenticated_users[game_state.order[game_state.turn].player_id],
            },
            json=PlayCardRequest(
                game_id=game_state.game_id,
                card=card,
            ).model_dump(),
        )

        if res.status_code != HTTPStatus.OK:
            print(
                res.text,
                game_state.active_round.trump,
                game_state.active_round.current_hand,
            )
        else:
            game_state = GameState.model_validate(res.json())
            print(
                game_state.active_round.active_trick.collection,
                game_state.active_round.trump,
            )


def test_play_single_round(bid_game: GameState):
    game_state = bid_game

    while game_state.phase != Phase.COMPLETE:
        if game_state.phase == Phase.BID:
            game_state = do_bidding(game_state)

        for _ in range(len(USERS)):
            card = game_state.active_round.current_hand[0]
            for possible_card in game_state.active_round.current_hand:
                if game_state.active_round.is_card_valid(possible_card):
                    card = possible_card

            res = httpx.post(
                urljoin(BASE_URL, "/game/trick/play"),
                headers={
                    "Authorization": "Bearer "
                    + authenticated_users[game_state.order[game_state.turn].player_id],
                },
                json=PlayCardRequest(
                    game_id=game_state.game_id,
                    card=card,
                ).model_dump(),
            )

            if res.status_code != HTTPStatus.OK:
                print(
                    res.text,
                    game_state.active_round.bid.turn,
                    game_state.active_round.active_trick.turn,
                    game_state.active_round.trump,
                    game_state.active_round.current_hand,
                )
            else:
                game_state = GameState.model_validate(res.json())

# type: ignore
# pyright: basic

import itertools
from http import HTTPStatus

import pytest
from fakeredis import FakeRedis
from fakeredis.aioredis import FakeRedis as AsyncFakeRedis
from fastapi.testclient import TestClient

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
from src.main import app

USERS = [f"user{i}" for i in range(6)]


@pytest.fixture(scope="session", autouse=True)
def patch_redis():
    from pytest import MonkeyPatch

    mp = MonkeyPatch()
    fake = FakeRedis()
    async_fake = AsyncFakeRedis()
    mp.setattr("src.main.redis_async.from_url", lambda url: async_fake)
    mp.setattr("src.main.redis.from_url", lambda url: fake)
    yield fake
    mp.undo()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


authenticated_users: dict[str, str] = {}


@pytest.fixture(autouse=True)
def print_first_line():
    # auto prints one line to stdout for cleaner formatting
    print()


def create_users(client: TestClient) -> None:
    for user in USERS:
        res = client.post(
            "/auth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"username": user, "password": "testpassword"},
        )

        assert res.status_code == HTTPStatus.OK
        data: dict[str, str] = res.json()
        access_token: str = data["access_token"]
        authenticated_users[user] = access_token


@pytest.fixture
def game(client: TestClient):
    create_users(client)

    res = client.post(
        "/game/create",
        headers={"Authorization": "Bearer " + authenticated_users[USERS[0]]},
    )

    assert res.status_code == HTTPStatus.OK

    return Game(**res.json())


def test_game(game: Game):
    print(game)


@pytest.fixture
def join_game(client: TestClient, game: Game):
    for user in USERS:
        res = client.post(
            "/game/join",
            headers={
                "Authorization": "Bearer " + authenticated_users[user],
            },
            json=GameManagementRequest(
                game_id=game.id, secret=game.join_code
            ).model_dump(),
        )

        assert res.status_code == HTTPStatus.OK


@pytest.fixture
def create_teams(client: TestClient, game: Game, join_game) -> list[Team]:
    teams: list[Team] = []
    for owner, _ in itertools.batched(USERS, 2):
        res = client.post(
            "/team/create",
            headers={
                "Authorization": "Bearer " + authenticated_users[owner],
            },
            json=GameRequest(game_id=game.id).model_dump(),
        )
        assert res.status_code == HTTPStatus.OK
        teams.append(Team.model_validate(res.json()))

    return teams


@pytest.fixture
def join_team(client: TestClient, create_teams: list[Team]):
    for team, members in zip(create_teams, itertools.batched(USERS, 2), strict=True):
        for member in members:
            res = client.post(
                "/team/join",
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


@pytest.fixture
def start_game(client: TestClient, game: Game, join_team) -> GameState:
    res = client.post(
        "/game/start",
        headers={
            "Authorization": "Bearer " + authenticated_users[USERS[0]],
        },
        json=GameRequest(game_id=game.id).model_dump(),
    )

    game_state = GameState.model_validate(res.json())
    return game_state


def do_bidding(client: TestClient, game_state: GameState) -> GameState:
    starting_turn = game_state.turn

    for _ in range(len(USERS)):
        res = client.post(
            "/game/bid",
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


@pytest.fixture
def bid_game(client: TestClient, start_game: GameState) -> GameState:
    return do_bidding(client, start_game)


def test_bid_game(bid_game):
    pass


def test_play_single_trick(client: TestClient, bid_game: GameState):
    game_state = bid_game

    print(game_state.order)

    for _ in range(len(USERS)):
        card = game_state.active_round.current_hand[0]
        for possible_card in game_state.active_round.current_hand:
            if game_state.active_round.is_card_valid(possible_card):
                card = possible_card

        res = client.post(
            "/game/trick/play",
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


def test_play_single_round(client: TestClient, bid_game: GameState):
    game_state = bid_game

    while game_state.phase != Phase.COMPLETE:
        if game_state.phase == Phase.BID:
            game_state = do_bidding(client, game_state)

        for _ in range(len(USERS)):
            card = game_state.active_round.current_hand[0]
            for possible_card in game_state.active_round.current_hand:
                if game_state.active_round.is_card_valid(possible_card):
                    card = possible_card

            res = client.post(
                "/game/trick/play",
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

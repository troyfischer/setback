# type: ignore
# pyright: basic

import pytest
from fakeredis import FakeRedis
from fakeredis.aioredis import FakeRedis as AsyncFakeRedis
from fastapi.testclient import TestClient

from src.game.manager import GameState
from src.game.models import Game, Team
from src.main import app
from tests.helpers import (
    create_and_join_teams,
    create_authenticated_users,
    create_game,
    do_bidding,
    join_game,
    play_full_game,
    play_trick,
    start_game,
)

pytestmark = pytest.mark.unit

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


@pytest.fixture(scope="session")
def authenticated_users(client: TestClient) -> dict[str, str]:
    return create_authenticated_users(client, USERS)


@pytest.fixture(autouse=True)
def print_first_line():
    print()


@pytest.fixture
def game(client: TestClient, authenticated_users: dict[str, str]) -> Game:
    return create_game(client, authenticated_users[USERS[0]])


def test_game(game: Game):
    print(game)


@pytest.fixture
def joined_game(
    client: TestClient, authenticated_users: dict[str, str], game: Game
) -> Game:
    join_game(client, authenticated_users, game, USERS)
    return game


@pytest.fixture
def teams(
    client: TestClient, authenticated_users: dict[str, str], joined_game: Game
) -> list[Team]:
    return create_and_join_teams(client, authenticated_users, joined_game, USERS)


def test_join_team(teams: list[Team]):
    assert len(teams) == 3


@pytest.fixture
def started_game(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
    teams: list[Team],
) -> GameState:
    return start_game(client, authenticated_users[USERS[0]], game.id)


@pytest.fixture
def game_after_bid(
    client: TestClient, authenticated_users: dict[str, str], started_game: GameState
) -> GameState:
    return do_bidding(client, authenticated_users, started_game)


def test_bid_game(game_after_bid: GameState):
    print(game_after_bid)


def test_play_single_trick(
    client: TestClient, authenticated_users: dict[str, str], game_after_bid: GameState
):
    game_state = game_after_bid
    print(game_state.order)

    game_state = play_trick(client, authenticated_users, game_state)
    print(
        game_state.active_round.active_trick.collection, game_state.active_round.trump
    )


def test_play_single_round(
    client: TestClient, authenticated_users: dict[str, str], game_after_bid: GameState
):
    game_state, tricks_played = play_full_game(
        client, authenticated_users, game_after_bid
    )
    print(f"Completed game with {tricks_played} tricks")

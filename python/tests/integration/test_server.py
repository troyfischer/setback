# type: ignore
# pyright: basic

import os
import time
from http import HTTPStatus

import httpx
import pytest
from testcontainers.compose import DockerCompose

from src.game.manager import GameStatePlayerScoped, Phase
from src.game.models import Game, Team
from src.logging import new_logger
from tests.helpers import (
    create_and_join_teams,
    create_authenticated_users,
    create_game,
    do_bidding,
    join_game,
    play_full_game,
    play_full_round,
    play_trick,
    start_game,
)

pytestmark = pytest.mark.integration

USERS = [f"user{i}" for i in range(6)]
TEST_SESSION_SECRET = "itest-session-secret-1234567890abcdef"
TEST_JWT_SECRET = "itest-jwt-secret-1234567890abcdef"
TEST_BASE_URL = "http://localhost"
TEST_CLIENT_ORIGIN = "http://localhost:8081"
TEST_GOOGLE_CLIENT_ID = "itest-google-client-id"
TEST_GOOGLE_CLIENT_SECRET = "itest-google-client-secret"
TEST_POSTGRES_PASSWORD = "itest-postgres-password"

log = new_logger("server-integration")


@pytest.fixture(scope="module")
def base_url() -> str:
    return os.environ.get("TEST_BASE_URL", "http://localhost:80")


@pytest.fixture(scope="module")
def docker_compose(base_url: str):
    if "TEST_BASE_URL" in os.environ:
        log.info(f"using remote server: {base_url}")
        yield None
        return

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    log.info("starting docker compose services...")

    os.environ["CADDYFILE"] = "./Caddyfile.local"
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("ENABLE_DEV_AUTH", "true")
    os.environ.setdefault("BASE_URL", TEST_BASE_URL)
    os.environ.setdefault("CLIENT_ORIGIN", TEST_CLIENT_ORIGIN)
    os.environ.setdefault("SESSION_SECRET", TEST_SESSION_SECRET)
    os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)
    os.environ.setdefault("GOOGLE_CLIENT_ID", TEST_GOOGLE_CLIENT_ID)
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", TEST_GOOGLE_CLIENT_SECRET)
    os.environ.setdefault("POSTGRES_PASSWORD", TEST_POSTGRES_PASSWORD)

    compose = DockerCompose(
        project_root,
        compose_file_name="docker-compose.yaml",
        pull=True,
        build=True,
        env_file=None,
    )

    compose.start()

    timeout = 90
    start_time = time.time()

    log.info("waiting for services to be healthy...")
    while time.time() - start_time < timeout:
        try:
            response = httpx.get(f"{base_url}/health", timeout=3.0)
            if response.status_code == 200:
                log.info("services are ready")
                break
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout):
            time.sleep(3)
        except Exception as e:
            log.info(f"waiting... ({int(time.time() - start_time)}s): {e}")
            time.sleep(3)
    else:
        raise TimeoutError("Services failed to start within 90 seconds")

    yield compose
    print()

    log.info("stopping services...")
    compose.stop()
    log.info("services stopped")


@pytest.fixture(scope="module")
def client(docker_compose, base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


@pytest.fixture(scope="module")
def authenticated_users(client: httpx.Client) -> dict[str, str]:
    users = create_authenticated_users(client, USERS)
    return users


def test_health_check(client: httpx.Client):
    response = client.get("/health")
    assert response.status_code == HTTPStatus.OK


def test_create_users(authenticated_users: dict[str, str]):
    assert len(authenticated_users) == len(USERS)
    for _user, token in authenticated_users.items():
        assert token is not None
        assert len(token) > 0


@pytest.fixture(scope="module")
def game(client: httpx.Client, authenticated_users: dict[str, str]) -> Game:
    game = create_game(client, authenticated_users[USERS[0]])
    return game


def test_create_game(game: Game):
    assert game.id is not None


@pytest.fixture(scope="module")
def joined_game(
    client: httpx.Client, authenticated_users: dict[str, str], game: Game
) -> Game:
    join_game(client, authenticated_users, game, USERS)
    print(f"\n✓ {len(USERS)} players joined game")
    return game


def test_join_game(joined_game: Game):
    assert joined_game is not None


@pytest.fixture(scope="module")
def teams(
    client: httpx.Client, authenticated_users: dict[str, str], joined_game: Game
) -> list[Team]:
    teams = create_and_join_teams(client, authenticated_users, joined_game, USERS)
    return teams


def test_create_teams(teams: list[Team]):
    assert len(teams) == 3
    for team in teams:
        assert team.id is not None


@pytest.fixture(scope="module")
def started_game(
    client: httpx.Client,
    authenticated_users: dict[str, str],
    game: Game,
    teams: list[Team],
) -> GameStatePlayerScoped:
    game_state = start_game(client, authenticated_users[USERS[0]], game.id)
    return game_state


def test_start_game(started_game: GameStatePlayerScoped):
    assert started_game.active_round is not None


@pytest.fixture(scope="module")
def game_after_bid(
    client: httpx.Client,
    authenticated_users: dict[str, str],
    started_game: GameStatePlayerScoped,
) -> GameStatePlayerScoped:
    game_state = do_bidding(client, authenticated_users, started_game)
    return game_state


def test_bidding(game_after_bid: GameStatePlayerScoped):
    assert game_after_bid.active_round.bid.highest_bid.amount >= 2


def test_play_single_trick(
    client: httpx.Client,
    authenticated_users: dict[str, str],
    game_after_bid: GameStatePlayerScoped,
):
    game_state = play_trick(client, authenticated_users, game_after_bid)
    assert game_state.phase == Phase.PLAY


def test_play_full_round(client: httpx.Client, authenticated_users: dict[str, str]):
    fresh_game = create_game(client, authenticated_users[USERS[0]])
    join_game(client, authenticated_users, fresh_game, USERS)
    create_and_join_teams(client, authenticated_users, fresh_game, USERS)
    game_state = start_game(client, authenticated_users[USERS[0]], fresh_game.id)
    game_state, tricks_played = play_full_round(client, authenticated_users, game_state)
    assert tricks_played > 0
    assert game_state.phase == Phase.BID


def test_play_full_game(client: httpx.Client, authenticated_users: dict[str, str]):
    fresh_game = create_game(client, authenticated_users[USERS[0]])
    join_game(client, authenticated_users, fresh_game, USERS)
    create_and_join_teams(client, authenticated_users, fresh_game, USERS)
    game_state = start_game(client, authenticated_users[USERS[0]], fresh_game.id)
    game_state, tricks_played = play_full_game(client, authenticated_users, game_state)
    assert tricks_played > 0
    assert game_state.phase == Phase.COMPLETE

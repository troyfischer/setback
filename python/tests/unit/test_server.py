# type: ignore
# pyright: basic

import asyncio
from http import HTTPStatus

import pytest
from fakeredis import FakeRedis
from fakeredis.aioredis import FakeRedis as AsyncFakeRedis
from fastapi.testclient import TestClient

from src.game import router as game_router
from src.game.manager import GameState
from src.game.models import Game, Team
from src.game.sse import ConnectionManager
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


def test_oauth_unknown_provider_returns_404(client: TestClient):
    res = client.get("/auth/not-a-provider/login")
    assert res.status_code == HTTPStatus.NOT_FOUND


def test_subscribe_requires_auth(client: TestClient, game: Game):
    res = client.get(f"/game/{game.id}/subscribe")
    assert res.status_code == HTTPStatus.UNAUTHORIZED


def test_subscribe_unknown_game_returns_404(
    client: TestClient,
    authenticated_users: dict[str, str],
):
    token = client.post(
        "/game/999999/subscribe-token",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
    )
    assert token.status_code == HTTPStatus.NOT_FOUND


def test_subscribe_token_requires_game_membership(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
):
    res = client.post(
        f"/game/{game.id}/subscribe-token",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[1]]}"},
    )
    assert res.status_code == HTTPStatus.FORBIDDEN


def test_subscribe_token_and_stream_connect(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
    monkeypatch: pytest.MonkeyPatch,
):
    join_game(client, authenticated_users, game, [USERS[0]])

    async def finite_stream(*args, **kwargs):
        yield "data: {\"ok\": true}\n\n"

    monkeypatch.setattr(game_router, "sse_event_stream", finite_stream)

    token_res = client.post(
        f"/game/{game.id}/subscribe-token",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
    )
    assert token_res.status_code == HTTPStatus.OK

    sse_token = token_res.json()["sse_token"]
    stream_res = client.get(f"/game/{game.id}/subscribe?sse_token={sse_token}")
    assert stream_res.status_code == HTTPStatus.OK
    assert stream_res.headers["content-type"].startswith("text/event-stream")


def test_subscribe_rejects_token_for_different_game(
    client: TestClient,
    authenticated_users: dict[str, str],
):
    game1 = create_game(client, authenticated_users[USERS[0]])
    game2 = create_game(client, authenticated_users[USERS[0]])
    join_game(client, authenticated_users, game1, [USERS[0]])
    join_game(client, authenticated_users, game2, [USERS[0]])

    token_res = client.post(
        f"/game/{game1.id}/subscribe-token",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
    )
    assert token_res.status_code == HTTPStatus.OK

    sse_token = token_res.json()["sse_token"]
    stream_res = client.get(f"/game/{game2.id}/subscribe?sse_token={sse_token}")
    assert stream_res.status_code == HTTPStatus.UNAUTHORIZED


def test_sse_event_stream_emits_keepalive_then_data():
    async def consume() -> tuple[str, str]:
        cm = ConnectionManager(max_queue_size=2)
        stream = game_router.sse_event_stream(42, cm, heartbeat_seconds=0.01)

        retry_line = await anext(stream)
        keepalive_line = await anext(stream)

        await cm.broadcast_to_game(
            42,
            {"event_type": "bid_placed", "game_id": 42, "data": {"ok": True}},
        )
        data_line = await anext(stream)

        await stream.aclose()
        return retry_line, keepalive_line + data_line

    retry, combined = asyncio.run(consume())
    assert retry == f"retry: {game_router.SSE_RETRY_MILLISECONDS}\n\n"
    assert ": keep-alive\n\n" in combined
    assert "data: " in combined
    assert '"event_type": "bid_placed"' in combined


def test_sse_connection_manager_drops_oldest_message_when_queue_is_full():
    async def consume() -> dict[str, object]:
        cm = ConnectionManager(max_queue_size=1)
        queue = cm.connect(100)

        await cm.broadcast_to_game(
            100,
            {"event_type": "first", "game_id": 100, "data": {}},
        )
        await cm.broadcast_to_game(
            100,
            {"event_type": "second", "game_id": 100, "data": {}},
        )

        message = await queue.get()
        cm.disconnect(100, queue)
        return message

    msg = asyncio.run(consume())
    assert msg["event_type"] == "second"

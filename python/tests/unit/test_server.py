# type: ignore
# pyright: basic

import asyncio
from collections.abc import Generator
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fakeredis import FakeRedis
from fakeredis.aioredis import FakeRedis as AsyncFakeRedis
from fastapi.testclient import TestClient

import src.game.routes.game as game_routes
from src.auth import routes as auth_routes
from src.auth.sso.models import OAuthUser
from src.game.events import GameEvent
from src.game.manager import GameStatePlayerScoped, Phase
from src.game.models import Game, Team
from src.game.sse import ConnectionManager
from src.main import app
from tests.helpers import (
    create_and_join_teams,
    create_authenticated_users,
    create_game,
    delete_game,
    do_bidding,
    join_game,
    play_full_game,
    play_full_round,
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


@pytest.fixture(scope="session", autouse=True)
def temp_database():
    from pytest import MonkeyPatch

    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite3"
        mp = MonkeyPatch()
        mp.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        yield db_path
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
def game(client: TestClient, authenticated_users: dict[str, str]) -> Generator[Game, None, None]:
    g = create_game(client, authenticated_users[USERS[0]])
    yield g
    delete_game(client, authenticated_users[USERS[0]], g.id)


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


def test_only_owner_can_start_game(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
    teams: list[Team],
):
    res = client.post(
        "/game/start",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[1]]}"},
        json={"game_id": game.id},
    )
    assert res.status_code == HTTPStatus.FORBIDDEN


@pytest.fixture
def started_game(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
    teams: list[Team],
) -> GameStatePlayerScoped:
    return start_game(client, authenticated_users[USERS[0]], game.id)


@pytest.fixture
def game_after_bid(
    client: TestClient,
    authenticated_users: dict[str, str],
    started_game: GameStatePlayerScoped,
) -> GameStatePlayerScoped:
    return do_bidding(client, authenticated_users, started_game)


def test_bid_game(
    client: TestClient,
    authenticated_users: dict[str, str],
    started_game: GameStatePlayerScoped,
):
    gs = do_bidding(client, authenticated_users, started_game)
    assert gs.active_round.bid.collection
    assert gs.phase == Phase.PLAY


def test_play_single_trick(
    client: TestClient,
    authenticated_users: dict[str, str],
    game_after_bid: GameStatePlayerScoped,
):
    gs = play_trick(client, authenticated_users, game_after_bid)
    assert gs.phase == Phase.PLAY


def test_play_full_round(
    client: TestClient,
    authenticated_users: dict[str, str],
    started_game: GameStatePlayerScoped,
):
    """
    A round starts in the bid phase, progress to play phase and ends back in the
    bid phase.

    NOTE: A low game state max_score value could break this test by moving the
    game to completed stage rather than back to bid
    """

    game_state, _ = play_full_round(client, authenticated_users, started_game)
    assert game_state.phase == Phase.BID


def test_play_full_game(
    client: TestClient,
    authenticated_users: dict[str, str],
    started_game: GameStatePlayerScoped,
):
    game_state, _ = play_full_game(client, authenticated_users, started_game)
    assert game_state.phase == Phase.COMPLETE


def test_oauth_unknown_provider_returns_404(client: TestClient):
    res = client.get("/auth/not-a-provider/login")
    assert res.status_code == HTTPStatus.NOT_FOUND


def test_oauth_callback_sets_refresh_cookie_and_refresh_succeeds(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeGoogleOAuth:
        async def callback(self, request):
            return OAuthUser(
                at_hash="test",
                aud="test",
                azp="test",
                email="player@example.com",
                email_verified=True,
                exp=datetime.now(),
                family_name="Player",
                given_name="Test",
                iat=datetime.now(),
                iss="test",
                name="Test Player",
                nonce="test",
                picture="test",
                sub="google-user-1",
            )

    monkeypatch.setitem(auth_routes._handlers, "google", FakeGoogleOAuth())

    callback_res = client.get("/auth/google/callback")
    assert callback_res.status_code == HTTPStatus.OK
    assert "refresh_token=" in callback_res.headers.get("set-cookie", "")
    assert "Secure" not in callback_res.headers.get("set-cookie", "")

    refresh_res = client.get("/auth/refresh")
    assert refresh_res.status_code == HTTPStatus.OK
    assert refresh_res.json()["access_token"]


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
        yield 'data: {"ok": true}\n\n'

    monkeypatch.setattr(game_routes, "sse_event_stream", finite_stream)

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
        stream = game_routes.sse_event_stream(
            42, "player-a", cm, heartbeat_seconds=0.01
        )

        retry_line = await anext(stream)
        keepalive_line = await anext(stream)

        await cm.broadcast_to_game(
            42,
            GameEvent(event_type="bid_placed", game_id=42, data={"ok": True}),
        )
        data_line = await anext(stream)

        await stream.aclose()
        return retry_line, keepalive_line + data_line

    retry, combined = asyncio.run(consume())
    assert retry == f"retry: {game_routes.SSE_RETRY_MILLISECONDS}\n\n"
    assert ": keep-alive\n\n" in combined
    assert "data: " in combined
    assert '"event_type": "bid_placed"' in combined


def test_sse_connection_manager_drops_oldest_message_when_queue_is_full():
    async def consume() -> dict[str, object]:
        cm = ConnectionManager(max_queue_size=1)
        queue = cm.connect(100, "player-a")

        await cm.broadcast_to_game(
            100,
            GameEvent(event_type="bid_placed", game_id=100, data={"tag": "first"}),
        )
        await cm.broadcast_to_game(
            100,
            GameEvent(event_type="card_played", game_id=100, data={"tag": "second"}),
        )

        message = await queue.get()
        cm.disconnect(100, "player-a", queue)
        return message

    msg = asyncio.run(consume())
    assert msg["event_type"] == "card_played"
    assert msg["data"]["tag"] == "second"

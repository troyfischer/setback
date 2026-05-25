# type: ignore
# pyright: basic

import asyncio
import os
import re
from collections.abc import Generator
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fakeredis import FakeRedis
from fakeredis.aioredis import FakeRedis as AsyncFakeRedis
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ENABLE_DEV_AUTH", "true")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")

import src.game.routes.game as game_routes
import src.rate_limit as rate_limit
from src.auth import routes as auth_routes
from src.auth.providers import OAuthUser
from src.config import AppEnv, Settings
from src.game.events import GameEvent
from src.game.manager import GameStatePlayerScoped, Phase
from src.game.models import Game, GameRequest, Team, UpdateTeamRequest
from src.game.sse import ConnectionManager, SSEConnectionLimitExceeded
from src.main import create_app
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
PROD_SESSION_SECRET = "prod-session-secret-1234567890abcdef"
PROD_JWT_SECRET = "prod-jwt-secret-1234567890abcdef"
PROD_BASE_URL = "https://setback.example.com"
PROD_CLIENT_ORIGIN = "https://app.example.com"
PROD_DATABASE_URL = "postgresql://app:prod-db-password@db.example.com:5432/appdb"
PROD_REDIS_URL = "redis://redis.example.com:6379/0"
PROD_GOOGLE_CLIENT_ID = "prod-google-client-id"
PROD_GOOGLE_CLIENT_SECRET = "prod-google-client-secret"


def prod_settings(**overrides) -> Settings:
    values = {
        "app_env": AppEnv.PROD,
        "enable_dev_auth": False,
        "auto_create_schema": False,
        "session_secret": PROD_SESSION_SECRET,
        "jwt_secret": PROD_JWT_SECRET,
        "base_url": PROD_BASE_URL,
        "client_origin": PROD_CLIENT_ORIGIN,
        "database_url": PROD_DATABASE_URL,
        "redis_url": PROD_REDIS_URL,
        "google_client_id": PROD_GOOGLE_CLIENT_ID,
        "google_client_secret": PROD_GOOGLE_CLIENT_SECRET,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(scope="session", autouse=True)
def patch_redis():
    from pytest import MonkeyPatch

    mp = MonkeyPatch()
    fake = FakeRedis()
    async_fake = AsyncFakeRedis()
    mp.setattr("src.main.redis_async.from_url", lambda _: async_fake)
    mp.setattr("src.main.redis.from_url", lambda _: fake)
    yield fake
    mp.undo()


@pytest.fixture(autouse=True)
def reset_redis(patch_redis: FakeRedis):
    patch_redis.flushall()


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
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="session")
def authenticated_users(client: TestClient) -> dict[str, str]:
    return create_authenticated_users(client, USERS)


@pytest.fixture(autouse=True)
def print_first_line():
    print()


@pytest.fixture
def game(
    client: TestClient, authenticated_users: dict[str, str]
) -> Generator[Game, None, None]:
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
        "/api/game/start",
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
    res = client.get("/api/auth/not-a-provider/login")
    assert res.status_code == HTTPStatus.NOT_FOUND


def test_auth_options_exposes_enabled_login_methods(client: TestClient):
    res = client.get("/api/auth/options")
    assert res.status_code == HTTPStatus.OK
    assert res.json() == {
        "dev_auth_enabled": True,
        "oauth_providers": ["google"],
    }


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

    callback_res = client.get("/api/auth/google/callback")
    assert callback_res.status_code == HTTPStatus.OK
    assert "refresh_token=" in callback_res.headers.get("set-cookie", "")
    assert "Secure" not in callback_res.headers.get("set-cookie", "")

    refresh_res = client.post("/api/auth/refresh")
    assert refresh_res.status_code == HTTPStatus.OK
    assert refresh_res.json()["access_token"]
    assert "refresh_token=" in refresh_res.headers.get("set-cookie", "")


def test_refresh_token_is_rotated_and_old_cookie_is_rejected(
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
                sub="google-user-rotate",
            )

    monkeypatch.setitem(auth_routes._handlers, "google", FakeGoogleOAuth())

    callback_res = client.get("/api/auth/google/callback")
    assert callback_res.status_code == HTTPStatus.OK

    set_cookie = callback_res.headers.get("set-cookie", "")
    match = re.search(r"refresh_token=([^;]+)", set_cookie)
    assert match is not None
    original_refresh = match.group(1)

    refresh_res = client.post("/api/auth/refresh")
    assert refresh_res.status_code == HTTPStatus.OK

    with TestClient(create_app()) as stale_client:
        stale_client.cookies.set("refresh_token", original_refresh)
        stale_refresh_res = stale_client.post("/api/auth/refresh")
    assert stale_refresh_res.status_code == HTTPStatus.UNAUTHORIZED


def test_refresh_rate_limit_returns_429(
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
                sub="google-user-rate-limit",
            )

    def fake_enforce_limit(redis_client, key, *, limit, window_seconds):
        if key.startswith("auth-refresh:ip:"):
            raise HTTPException(429, "rate limit exceeded")

    monkeypatch.setitem(auth_routes._handlers, "google", FakeGoogleOAuth())
    monkeypatch.setattr(rate_limit, "_enforce_limit", fake_enforce_limit)

    callback_res = client.get("/api/auth/google/callback")
    assert callback_res.status_code == HTTPStatus.OK

    refresh_res = client.post("/api/auth/refresh")
    assert refresh_res.status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_dev_auth_route_is_registered_in_test_app():
    routes = {route.path for route in create_app().routes}
    assert "/api/auth/dev-token" in routes


def test_create_app_rejects_dev_auth_in_prod():
    with pytest.raises(RuntimeError):
        create_app(prod_settings(enable_dev_auth=True))


def test_create_app_rejects_default_jwt_secret_in_prod():
    with pytest.raises(RuntimeError):
        create_app(
            prod_settings(jwt_secret="your-secret-key-change-this-in-production")
        )


def test_create_app_accepts_custom_prod_secrets():
    create_app(prod_settings())


def test_create_app_rejects_auto_create_schema_in_prod():
    with pytest.raises(RuntimeError):
        create_app(prod_settings(auto_create_schema=True))


def test_prod_settings_use_explicit_cors_origin():
    settings = Settings(
        app_env=AppEnv.PROD,
        auto_create_schema=False,
        client_origin="https://app.example.com",
    )
    assert settings.cors_allowed_origins == ["https://app.example.com"]
    assert settings.cors_origin_regex is None


def test_dev_settings_use_local_cors_regex():
    settings = Settings(
        app_env=AppEnv.DEV,
        client_origin="https://app.example.com",
    )
    assert settings.cors_allowed_origins == []
    assert settings.cors_origin_regex is not None


def test_dev_settings_auto_create_schema_enabled_by_default():
    settings = Settings(app_env=AppEnv.DEV)
    assert settings.should_auto_create_schema is True


def test_prod_settings_auto_create_schema_disabled():
    settings = prod_settings()
    assert settings.should_auto_create_schema is False


def test_lifespan_skips_create_schema_in_prod(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[Engine] = []

    def fake_create_schema(engine: Engine) -> None:
        calls.append(engine)

    monkeypatch.setattr("src.main.create_schema", fake_create_schema)

    settings = prod_settings()

    with TestClient(create_app(settings)):
        pass

    assert calls == []


def test_subscribe_requires_auth(client: TestClient, game: Game):
    res = client.get(f"/api/game/{game.id}/subscribe")
    assert res.status_code == HTTPStatus.UNAUTHORIZED


def test_subscribe_unknown_game_returns_404(
    client: TestClient,
    authenticated_users: dict[str, str],
):
    token = client.post(
        "/api/game/999999/subscribe-token",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
    )
    assert token.status_code == HTTPStatus.NOT_FOUND


def test_subscribe_token_requires_game_membership(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
):
    res = client.post(
        f"/api/game/{game.id}/subscribe-token",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[1]]}"},
    )
    assert res.status_code == HTTPStatus.FORBIDDEN


def test_join_game_rate_limit_returns_429(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_enforce_limit(redis_client, key, *, limit, window_seconds):
        if key.startswith("game-join:user:"):
            raise HTTPException(429, "rate limit exceeded")

    monkeypatch.setattr(rate_limit, "_enforce_limit", fake_enforce_limit)

    res = client.post(
        "/api/game/join",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[1]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )
    assert res.status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_join_team_rejects_membership_in_multiple_teams(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
):
    join_game(client, authenticated_users, game, [USERS[1], USERS[2]])

    team_a_res = client.post(
        "/api/team/create",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )
    team_a = Team.model_validate(team_a_res.json())

    team_b_res = client.post(
        "/api/team/create",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[1]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )
    team_b = Team.model_validate(team_b_res.json())

    first_join = client.post(
        "/api/team/join",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[2]]}"},
        json=UpdateTeamRequest(
            game_id=game.id, team_number=team_a.team_number
        ).model_dump(),
    )
    assert first_join.status_code == HTTPStatus.OK

    second_join = client.post(
        "/api/team/join",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[2]]}"},
        json=UpdateTeamRequest(
            game_id=game.id, team_number=team_b.team_number
        ).model_dump(),
    )
    assert second_join.status_code == HTTPStatus.BAD_REQUEST


def test_create_team_rejects_player_already_on_team(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
):
    join_game(client, authenticated_users, game, [USERS[1]])

    team_owner_res = client.post(
        "/api/team/create",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )
    team_owner = Team.model_validate(team_owner_res.json())

    join_res = client.post(
        "/api/team/join",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[1]]}"},
        json=UpdateTeamRequest(
            game_id=game.id, team_number=team_owner.team_number
        ).model_dump(),
    )
    assert join_res.status_code == HTTPStatus.OK

    create_second_team_res = client.post(
        "/api/team/create",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[1]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )
    assert create_second_team_res.status_code == HTTPStatus.BAD_REQUEST


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
        f"/api/game/{game.id}/subscribe-token",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
    )
    assert token_res.status_code == HTTPStatus.OK

    sse_token = token_res.json()["sse_token"]
    stream_res = client.get(f"/api/game/{game.id}/subscribe?sse_token={sse_token}")
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
        f"/api/game/{game1.id}/subscribe-token",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
    )
    assert token_res.status_code == HTTPStatus.OK

    sse_token = token_res.json()["sse_token"]
    stream_res = client.get(f"/api/game/{game2.id}/subscribe?sse_token={sse_token}")
    assert stream_res.status_code == HTTPStatus.UNAUTHORIZED


def test_sse_event_stream_emits_keepalive_then_data():
    async def consume() -> tuple[str, str]:
        cm = ConnectionManager(max_queue_size=2)
        queue = cm.connect(42, "player-a")
        stream = game_routes.sse_event_stream(
            42, "player-a", queue, cm, heartbeat_seconds=0.01
        )

        retry_line = await anext(stream)
        keepalive_line = await anext(stream)

        await cm.broadcast_to_game(
            42,
            GameEvent(event_type="bid_placed", game_id="42", data={"ok": True}),
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
        queue = cm.connect("100", "player-a")

        await cm.broadcast_to_game(
            "100",
            GameEvent(event_type="bid_placed", game_id="100", data={"tag": "first"}),
        )
        await cm.broadcast_to_game(
            "100",
            GameEvent(event_type="card_played", game_id="100", data={"tag": "second"}),
        )

        message = await queue.get()
        cm.disconnect("100", "player-a", queue)
        return message

    msg = asyncio.run(consume())
    assert msg["event_type"] == "card_played"
    assert msg["data"]["tag"] == "second"


def test_sse_connection_manager_replaces_existing_player_connection():
    cm = ConnectionManager(
        max_connections_per_game=2,
    )

    first_queue = cm.connect("100", "player-a")
    second_queue = cm.connect("100", "player-a")

    assert first_queue.get_nowait() is None

    asyncio.run(
        cm.broadcast_to_game(
            "100",
            GameEvent(event_type="card_played", game_id="100", data={"tag": "latest"}),
        )
    )

    message = second_queue.get_nowait()
    assert message is not None
    assert message["event_type"] == "card_played"
    assert message["data"]["tag"] == "latest"

    cm.disconnect("100", "player-a", first_queue)
    cm.disconnect("100", "player-a", second_queue)


def test_sse_connection_manager_rejects_new_player_at_game_limit():
    cm = ConnectionManager(max_connections_per_game=2)

    queue1 = cm.connect("100", "player-a")
    queue2 = cm.connect("100", "player-b")

    with pytest.raises(SSEConnectionLimitExceeded):
        cm.connect("100", "player-c")

    cm.disconnect("100", "player-a", queue1)
    cm.disconnect("100", "player-b", queue2)


def _start_game_request(client, token, game_id):
    return client.post(
        "/api/game/start",
        headers={"Authorization": f"Bearer {token}"},
        json=GameRequest(game_id=game_id).model_dump(),
    )


def test_cannot_start_game_with_no_teams(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
):
    res = _start_game_request(client, authenticated_users[USERS[0]], game.id)
    assert res.status_code == HTTPStatus.BAD_REQUEST


def test_cannot_start_game_with_one_team(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
):
    client.post(
        "/api/team/create",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )
    res = _start_game_request(client, authenticated_users[USERS[0]], game.id)
    assert res.status_code == HTTPStatus.BAD_REQUEST


def test_cannot_start_game_with_empty_team(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
):
    join_game(client, authenticated_users, game, [USERS[1]])

    # user0 creates team A and then leaves it, leaving it empty
    team_res = client.post(
        "/api/team/create",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )
    team_a = Team.model_validate(team_res.json())
    client.post(
        "/api/team/leave",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
        json=UpdateTeamRequest(
            game_id=game.id, team_number=team_a.team_number
        ).model_dump(),
    )

    # user1 creates team B (auto-joins)
    client.post(
        "/api/team/create",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[1]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )

    res = _start_game_request(client, authenticated_users[USERS[0]], game.id)
    assert res.status_code == HTTPStatus.BAD_REQUEST


def test_cannot_start_game_with_unequal_teams(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
):
    join_game(client, authenticated_users, game, [USERS[1], USERS[2]])

    # user0 creates team A (auto-joins: A=[user0])
    team_res = client.post(
        "/api/team/create",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )
    team_a = Team.model_validate(team_res.json())

    # user1 creates team B (auto-joins: B=[user1])
    client.post(
        "/api/team/create",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[1]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )

    # user2 joins team A → A=[user0, user2], B=[user1] (unequal)
    client.post(
        "/api/team/join",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[2]]}"},
        json=UpdateTeamRequest(
            game_id=game.id, team_number=team_a.team_number
        ).model_dump(),
    )

    res = _start_game_request(client, authenticated_users[USERS[0]], game.id)
    assert res.status_code == HTTPStatus.BAD_REQUEST


def test_cannot_start_game_with_fewer_than_four_players(
    client: TestClient,
    authenticated_users: dict[str, str],
    game: Game,
):
    join_game(client, authenticated_users, game, [USERS[1]])

    # user0 creates team A (auto-joins: A=[user0])
    client.post(
        "/api/team/create",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[0]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )
    # user1 creates team B (auto-joins: B=[user1]) → 2 teams of 1 = 2 players total
    client.post(
        "/api/team/create",
        headers={"Authorization": f"Bearer {authenticated_users[USERS[1]]}"},
        json=GameRequest(game_id=game.id).model_dump(),
    )

    res = _start_game_request(client, authenticated_users[USERS[0]], game.id)
    assert res.status_code == HTTPStatus.BAD_REQUEST

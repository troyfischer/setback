import itertools
from http import HTTPStatus
from typing import Protocol

from httpx import Response

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


class HTTPClient(Protocol):
    def post(self, url: str, **kwargs) -> Response: ...


def create_authenticated_users(client: HTTPClient, users: list[str]) -> dict[str, str]:
    tokens = {}
    for user in users:
        res = client.post(
            "/auth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"username": user, "password": "testpassword"},
        )
        assert res.status_code == HTTPStatus.OK, f"Failed to create user {user}"
        tokens[user] = res.json()["access_token"]
    return tokens


def create_game(client: HTTPClient, auth_token: str) -> Game:
    res = client.post(
        "/game/create",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res.status_code == HTTPStatus.OK, f"Failed to create game: {res.text}"
    return Game(**res.json())


def join_game(
    client: HTTPClient,
    authenticated_users: dict[str, str],
    game: Game,
    users: list[str],
) -> None:
    for user in users:
        res = client.post(
            "/game/join",
            headers={"Authorization": f"Bearer {authenticated_users[user]}"},
            json=GameManagementRequest(
                game_id=game.id, secret=game.join_code
            ).model_dump(),
        )
        assert res.status_code == HTTPStatus.OK, (
            f"User {user} failed to join: {res.text}"
        )


def create_and_join_teams(
    client: HTTPClient,
    authenticated_users: dict[str, str],
    game: Game,
    users: list[str],
) -> list[Team]:
    teams: list[Team] = []

    for owner, _ in itertools.batched(users, 2):
        res = client.post(
            "/team/create",
            headers={"Authorization": f"Bearer {authenticated_users[owner]}"},
            json=GameRequest(game_id=game.id).model_dump(),
        )
        assert res.status_code == HTTPStatus.OK, f"Failed to create team: {res.text}"
        teams.append(Team.model_validate(res.json()))

    for team, members in zip(teams, itertools.batched(users, 2), strict=True):
        for member in members:
            res = client.post(
                "/team/join",
                headers={"Authorization": f"Bearer {authenticated_users[member]}"},
                json=UpdateTeamRequest(
                    game_id=team.game_id, team_id=team.id
                ).model_dump(),
            )
            assert res.status_code == HTTPStatus.OK, f"Failed to join team: {res.text}"

    return teams


def start_game(client: HTTPClient, auth_token: str, game_id: int) -> GameState:
    res = client.post(
        "/game/start",
        headers={"Authorization": f"Bearer {auth_token}"},
        json=GameRequest(game_id=game_id).model_dump(),
    )
    assert res.status_code == HTTPStatus.OK, f"Failed to start game: {res.text}"
    return GameState.model_validate(res.json())


def do_bidding(
    client: HTTPClient, authenticated_users: dict[str, str], game_state: GameState
) -> GameState:
    starting_turn = game_state.turn

    for _ in range(len(game_state.order.order)):
        player_id = game_state.order[game_state.turn].player_id
        res = client.post(
            "/game/bid",
            headers={"Authorization": f"Bearer {authenticated_users[player_id]}"},
            json=BidRequest(game_id=game_state.game_id, amount=2).model_dump(),
        )
        assert res.status_code == HTTPStatus.OK, f"Bid failed: {res.text}"
        game_state = GameState.model_validate(res.json())

    assert game_state.phase != Phase.BID
    assert game_state.active_round.bid.turn == starting_turn
    return game_state


def play_trick(
    client: HTTPClient, authenticated_users: dict[str, str], game_state: GameState
) -> GameState:
    for _ in range(len(game_state.order.order)):
        card = game_state.active_round.current_hand[0]
        for possible_card in game_state.active_round.current_hand:
            if game_state.active_round.is_card_valid(possible_card):
                card = possible_card
                break

        player_id = game_state.order[game_state.turn].player_id
        res = client.post(
            "/game/trick/play",
            headers={"Authorization": f"Bearer {authenticated_users[player_id]}"},
            json=PlayCardRequest(
                game_id=game_state.game_id,
                card=card,
            ).model_dump(),
        )
        assert res.status_code == HTTPStatus.OK, f"Failed to play card: {res.text}"
        game_state = GameState.model_validate(res.json())

    return game_state


def play_full_game(
    client: HTTPClient, authenticated_users: dict[str, str], game_state: GameState
) -> tuple[GameState, int]:
    tricks_played = 0

    while game_state.phase != Phase.COMPLETE:
        if game_state.phase == Phase.BID:
            game_state = do_bidding(client, authenticated_users, game_state)

        game_state = play_trick(client, authenticated_users, game_state)
        tricks_played += 1

    return game_state, tricks_played

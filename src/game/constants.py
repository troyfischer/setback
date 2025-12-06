from typing import final
from urllib.parse import urljoin


@final
class Routes:
    PREFIX = ""

    @final
    class Game:
        PREFIX = "/game/"

        CREATE = urljoin(PREFIX, "create")
        DELETE = urljoin(PREFIX, "delete")
        JOIN = urljoin(PREFIX, "join")
        START = urljoin(PREFIX, "start")
        BID = urljoin(PREFIX, "bid")
        PLAY = urljoin(PREFIX, "trick/play")

    @final
    class Team:
        PREFIX = "/team/"

        CREATE = urljoin(PREFIX, "create")
        DELETE = urljoin(PREFIX, "delete")
        JOIN = urljoin(PREFIX, "join")
        LEAVE = urljoin(PREFIX, "leave")

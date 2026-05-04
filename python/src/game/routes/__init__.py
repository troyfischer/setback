from fastapi import APIRouter

from .game import router as game_router
from .game import unauthenticated_router as game_unauthenticated_router
from .team import router as team_router

router = APIRouter()
router.include_router(team_router)
router.include_router(game_router)
router.include_router(game_unauthenticated_router)

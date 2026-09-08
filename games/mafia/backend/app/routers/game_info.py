from fastapi import APIRouter

from app.schemas.game_info import GameInfoOut
from app.services.game_info_presenter import build_game_info

router = APIRouter(prefix="/api/game-info", tags=["game-info"])


@router.get("", response_model=GameInfoOut)
async def get_game_info() -> GameInfoOut:
    return build_game_info()

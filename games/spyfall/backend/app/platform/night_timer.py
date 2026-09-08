from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

_DEFAULT_DURATION_SECONDS = 60.0


class NightTimerManager:
    """Fires a callback after a fixed delay unless cancelled first, keyed by
    room_code. Fully generic — no knowledge of Mafia's game rules — so it
    only knows "call this after N seconds," leaving the caller to decide
    what auto-advancing a night actually means.
    """

    def __init__(self, duration_seconds: float = _DEFAULT_DURATION_SECONDS) -> None:
        self._duration_seconds = duration_seconds
        self._tasks: dict[str, asyncio.Task] = {}

    @property
    def duration_seconds(self) -> float:
        return self._duration_seconds

    def schedule(self, room_code: str, callback: Callable[[], Awaitable[None]]) -> None:
        self.cancel(room_code)
        self._tasks[room_code] = asyncio.create_task(self._fire_after_delay(room_code, callback))

    def cancel(self, room_code: str) -> None:
        task = self._tasks.pop(room_code, None)
        if task is not None:
            task.cancel()

    def cancel_all(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    async def _fire_after_delay(self, room_code: str, callback: Callable[[], Awaitable[None]]) -> None:
        await asyncio.sleep(self._duration_seconds)
        self._tasks.pop(room_code, None)
        await callback()

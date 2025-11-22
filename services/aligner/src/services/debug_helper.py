from collections.abc import Awaitable, Callable
from typing import Any

import numpy as np


class DebugHelper:
    """helper for clean debug visualization without polluting main logic"""

    def __init__(
        self,
        callback: Callable[[str, int, np.ndarray, dict], Awaitable[None]] | None,
        enabled: bool = False,
    ):
        self.callback = callback
        self.enabled = enabled and callback is not None
        self.step_counter = 0

    async def log(self, step_name: str, image: np.ndarray, metadata: dict[str, Any] | None = None):
        """log debug step if enabled"""
        if not self.enabled:
            return

        meta = metadata or {}
        await self.callback(step_name, self.step_counter, image.copy(), meta)
        self.step_counter += 1

    def __bool__(self):
        """allow if debugged: syntax"""
        return self.enabled

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
from paddleocr import PaddleOCR

from ..config import settings
from ..logger import get_logger
from ..observability.telemetry import get_tracer

logger = get_logger(__name__)
tracer = get_tracer(__name__)


class OCRService:
    """service for paddleocr"""

    def __init__(self):
        """init paddleocr instance"""
        self.ocr = self._init_paddle()
        self.executor = ThreadPoolExecutor(max_workers=settings.workers)
        logger.info("ocr service initialized")

    @staticmethod
    def _init_paddle() -> PaddleOCR:
        """initialize paddleocr with configured settings"""
        logger.info(
            "initializing paddleocr",
            device=settings.paddle_device,
            lang=settings.paddle_lang,
            use_gpu=settings.paddle_use_gpu,
        )

        ocr = PaddleOCR(
            device=settings.paddle_device,
            lang=settings.paddle_lang,
        )

        logger.info("paddleocr initialized successfully")
        return ocr

    async def recognize(self, image_array: np.ndarray) -> list[Any]:
        """run ocr recognition on image array"""
        with tracer.start_as_current_span("ocr_service.recognize") as span:
            span.set_attribute("image.shape", str(image_array.shape))

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self.executor, self.ocr.predict, image_array)

            logger.debug("ocr prediction completed", results_count=len(result))
            return result

    def shutdown(self):
        """cleanup resources"""
        if self.executor:
            logger.info("shutting down ocr service executor")
            self.executor.shutdown(wait=True)

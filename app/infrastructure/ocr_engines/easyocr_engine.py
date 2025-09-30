"""
Wrapper для EasyOCR
"""
import time
from typing import Optional, List

import numpy as np
import easyocr

from app.infrastructure.ocr_engines.base_engine import (
    BaseOCREngine,
    OCRResult,
    OCRTextBlock
)
from app.core.exceptions import OCRProcessingError, ConfigurationError
from app.core.logging import get_logger

logger = get_logger(__name__)


class EasyOCREngine(BaseOCREngine):
    """
    EasyOCR wrapper - стабильный движок для распознавания текста
    """

    def __init__(
            self,
            languages: List[str] = None,
            gpu: bool = False
    ):
        """
        Инициализация EasyOCR Engine

        Args:
            languages: Список языков для распознавания
            gpu: Использовать GPU (если доступен)
        """
        self.languages = languages or ['ru', 'en']
        self.gpu = gpu
        self.reader: Optional[easyocr.Reader] = None

        logger.info(
            "EasyOCR engine configured",
            languages=self.languages,
            gpu=self.gpu
        )

    def initialize(self) -> None:
        """Инициализация EasyOCR"""
        try:
            logger.info("Initializing EasyOCR...")

            # Создаём Reader с заданными языками
            self.reader = easyocr.Reader(
                lang_list=self.languages,
                gpu=self.gpu,
                verbose=False  # Отключаем лишние логи
            )

            logger.info("EasyOCR initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize EasyOCR", error=str(e))
            raise ConfigurationError(
                f"Failed to initialize EasyOCR: {str(e)}",
                details={"error": str(e)}
            )

    def extract_text(self, image: np.ndarray) -> OCRResult:
        """
        Извлечение текста с изображения через EasyOCR

        Args:
            image: Изображение в формате numpy array (RGB)

        Returns:
            OCRResult с распознанным текстом

        Raises:
            OCRProcessingError: Если не удалось распознать текст
        """
        if self.reader is None:
            raise OCRProcessingError(
                "EasyOCR not initialized. Call initialize() first."
            )

        try:
            start_time = time.time()

            # Вызываем EasyOCR
            # readtext возвращает: [([bbox], text, confidence), ...]
            logger.debug("Starting EasyOCR text extraction")
            results = self.reader.readtext(image)

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Обрабатываем результат
            if not results:
                logger.warning("EasyOCR returned empty result")
                return OCRResult(
                    text_blocks=[],
                    raw_text="",
                    average_confidence=0.0,
                    processing_time_ms=processing_time_ms
                )

            # Форматируем результаты
            text_blocks = []
            total_confidence = 0.0
            raw_text_lines = []

            for bbox, text, confidence in results:
                # Конвертируем bbox в нужный формат
                # EasyOCR возвращает [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                bbox_formatted = [[int(x), int(y)] for x, y in bbox]

                text_blocks.append(
                    OCRTextBlock(
                        text=text,
                        confidence=float(confidence),
                        bbox=bbox_formatted
                    )
                )

                total_confidence += confidence
                raw_text_lines.append(text)

            # Считаем среднюю уверенность
            average_confidence = (
                total_confidence / len(text_blocks) if text_blocks else 0.0
            )

            # Объединяем весь текст
            raw_text = "\n".join(raw_text_lines)

            logger.info(
                "EasyOCR extraction completed",
                blocks_count=len(text_blocks),
                average_confidence=round(average_confidence, 3),
                processing_time_ms=processing_time_ms
            )

            return OCRResult(
                text_blocks=text_blocks,
                raw_text=raw_text,
                average_confidence=average_confidence,
                processing_time_ms=processing_time_ms
            )

        except Exception as e:
            logger.error("EasyOCR extraction failed", error=str(e))
            raise OCRProcessingError(
                f"Failed to extract text with EasyOCR: {str(e)}",
                details={"error": str(e)}
            )

    def is_available(self) -> bool:
        """
        Проверка доступности EasyOCR

        Returns:
            True если движок инициализирован и готов к работе
        """
        return self.reader is not None

    def cleanup(self) -> None:
        """Очистка ресурсов"""
        if self.reader is not None:
            logger.info("Cleaning up EasyOCR resources")
            self.reader = None
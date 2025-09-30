"""
Wrapper для PaddleOCR
"""
import time
from typing import Optional

import numpy as np
from paddleocr import PaddleOCR

from app.infrastructure.ocr_engines.base_engine import (
    BaseOCREngine,
    OCRResult,
    OCRTextBlock
)
from app.core.exceptions import OCRProcessingError, ConfigurationError
from app.core.logging import get_logger

logger = get_logger(__name__)


class PaddleOCREngine(BaseOCREngine):
    """
    PaddleOCR wrapper - основной движок для распознавания текста
    """
    
    def __init__(
        self,
        use_angle_cls: bool = True,
        lang: str = 'ru',
        use_gpu: bool = False,
        show_log: bool = False
    ):
        """
        Инициализация PaddleOCR Engine
        
        Args:
            use_angle_cls: Использовать классификацию угла поворота
            lang: Язык распознавания ('ru', 'en', 'ch' и др.)
            use_gpu: Использовать GPU
            show_log: Показывать логи PaddleOCR
        """
        self.use_angle_cls = use_angle_cls
        self.lang = lang
        self.use_gpu = use_gpu
        self.show_log = show_log
        self.ocr: Optional[PaddleOCR] = None
        
        logger.info(
            "PaddleOCR engine configured",
            use_angle_cls=use_angle_cls,
            lang=lang,
            use_gpu=use_gpu
        )
    
    def initialize(self) -> None:
        """Инициализация PaddleOCR"""
        try:
            logger.info("Initializing PaddleOCR...")
            
            self.ocr = PaddleOCR(
                use_angle_cls=self.use_angle_cls,
                lang=self.lang,
                use_gpu=self.use_gpu,
                show_log=self.show_log
            )
            
            logger.info("PaddleOCR initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize PaddleOCR", error=str(e))
            raise ConfigurationError(
                f"Failed to initialize PaddleOCR: {str(e)}",
                details={"error": str(e)}
            )
    
    def extract_text(self, image: np.ndarray) -> OCRResult:
        """
        Извлечение текста с изображения через PaddleOCR
        
        Args:
            image: Изображение в формате numpy array (RGB)
            
        Returns:
            OCRResult с распознанным текстом
            
        Raises:
            OCRProcessingError: Если не удалось распознать текст
        """
        if self.ocr is None:
            raise OCRProcessingError(
                "PaddleOCR not initialized. Call initialize() first."
            )
        
        try:
            start_time = time.time()
            
            # Вызываем PaddleOCR
            logger.debug("Starting PaddleOCR text extraction")
            result = self.ocr.ocr(image, cls=self.use_angle_cls)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Обрабатываем результат
            if not result or not result[0]:
                logger.warning("PaddleOCR returned empty result")
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
            
            for line in result[0]:
                bbox = line[0]  # Координаты [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                text = line[1][0]  # Распознанный текст
                confidence = float(line[1][1])  # Уверенность
                
                text_blocks.append(
                    OCRTextBlock(
                        text=text,
                        confidence=confidence,
                        bbox=bbox
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
                "PaddleOCR extraction completed",
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
            logger.error("PaddleOCR extraction failed", error=str(e))
            raise OCRProcessingError(
                f"Failed to extract text with PaddleOCR: {str(e)}",
                details={"error": str(e)}
            )
    
    def is_available(self) -> bool:
        """
        Проверка доступности PaddleOCR
        
        Returns:
            True если движок инициализирован и готов к работе
        """
        return self.ocr is not None
    
    def cleanup(self) -> None:
        """Очистка ресурсов"""
        if self.ocr is not None:
            logger.info("Cleaning up PaddleOCR resources")
            self.ocr = None

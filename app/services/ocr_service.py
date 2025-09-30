"""
Главный OCR сервис - оркестратор
"""
import time
from typing import Dict, Any

from app.infrastructure.ocr_engines.paddleocr_engine import PaddleOCREngine
from app.services.receipt_parser import ReceiptParser
from app.models.domain import Receipt
from app.core.enums import OCREngine
from app.core.exceptions import OCRProcessingError
from app.core.logging import get_logger
from app.utils.image_utils import (
    decode_base64_image,
    validate_image_format,
    validate_image_size,
    bytes_to_numpy
)

logger = get_logger(__name__)


class OCRService:
    """
    Главный сервис для распознавания чеков
    Оркестрирует весь процесс: валидация → OCR → парсинг
    """
    
    def __init__(
        self,
        paddleocr_engine: PaddleOCREngine,
        receipt_parser: ReceiptParser,
        max_image_size_mb: int = 10
    ):
        """
        Инициализация OCR сервиса
        
        Args:
            paddleocr_engine: Движок PaddleOCR
            receipt_parser: Парсер чеков
            max_image_size_mb: Максимальный размер изображения в МБ
        """
        self.paddleocr_engine = paddleocr_engine
        self.receipt_parser = receipt_parser
        self.max_image_size_mb = max_image_size_mb
        
        logger.info(
            "OCR Service initialized",
            max_image_size_mb=max_image_size_mb
        )
    
    async def process_receipt(
        self,
        image_base64: str,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Полный процесс распознавания чека
        
        Args:
            image_base64: Изображение в base64
            options: Дополнительные опции
            
        Returns:
            Dict с результатами распознавания
            
        Raises:
            ImageValidationError: Ошибка валидации изображения
            OCRProcessingError: Ошибка распознавания
            ReceiptParsingError: Ошибка парсинга
        """
        start_time = time.time()
        options = options or {}
        
        logger.info("Starting receipt processing")
        
        try:
            # 1. Валидация и подготовка изображения
            logger.debug("Validating and preparing image")
            image_bytes = decode_base64_image(image_base64)
            validate_image_format(image_bytes)
            validate_image_size(image_bytes, self.max_image_size_mb)
            image_array = bytes_to_numpy(image_bytes)
            
            # 2. OCR распознавание
            logger.debug("Extracting text with PaddleOCR")
            ocr_result = self.paddleocr_engine.extract_text(image_array)
            
            # 3. Проверка что получили текст
            if not ocr_result.text_blocks:
                logger.warning("No text detected in image")
                raise OCRProcessingError(
                    "No text detected in the image",
                    details={
                        "confidence": ocr_result.average_confidence,
                        "blocks_count": 0
                    }
                )
            
            # 4. Парсинг чека
            logger.debug("Parsing receipt structure")
            receipt = self.receipt_parser.parse(
                raw_text=ocr_result.raw_text,
                confidence=ocr_result.average_confidence
            )
            
            # 5. Формирование результата
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            result = {
                "success": True,
                "confidence": ocr_result.average_confidence,
                "processing_time_ms": processing_time_ms,
                "receipt": receipt,
                "ocr_engine_used": OCREngine.PADDLEOCR,
                "error": None
            }
            
            logger.info(
                "Receipt processing completed successfully",
                confidence=round(ocr_result.average_confidence, 3),
                processing_time_ms=processing_time_ms,
                items_count=len(receipt.items)
            )
            
            return result
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            logger.error(
                "Receipt processing failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=processing_time_ms
            )
            
            # Пробрасываем исключение дальше
            raise
    
    def is_ready(self) -> bool:
        """
        Проверка готовности сервиса к работе
        
        Returns:
            True если все движки готовы
        """
        return self.paddleocr_engine.is_available()

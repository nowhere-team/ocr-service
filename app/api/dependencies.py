"""
FastAPI Dependencies для Dependency Injection
"""
from functools import lru_cache

from app.config import get_settings, Settings
from app.infrastructure.ocr_engines.easyocr_engine import EasyOCREngine
from app.services.receipt_parser import ReceiptParser
from app.services.ocr_service import OCRService
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache()
def get_easyocr_engine() -> EasyOCREngine:
    """
    Получить инстанс EasyOCR Engine (singleton)
    Инициализируется один раз и переиспользуется
    """
    settings = get_settings()

    engine = EasyOCREngine(
        languages=settings.easyocr_languages_list,
        gpu=settings.EASYOCR_USE_GPU
    )

    # Инициализируем движок
    engine.initialize()

    return engine


@lru_cache()
def get_receipt_parser() -> ReceiptParser:
    """Получить инстанс ReceiptParser (singleton)"""
    return ReceiptParser()


def get_ocr_service() -> OCRService:
    """
    Получить инстанс OCR Service
    Автоматически создаёт все необходимые зависимости
    """
    settings = get_settings()

    easyocr_engine = get_easyocr_engine()
    receipt_parser = get_receipt_parser()

    return OCRService(
        ocr_engine=easyocr_engine,
        receipt_parser=receipt_parser,
        max_image_size_mb=settings.MAX_IMAGE_SIZE_MB
    )
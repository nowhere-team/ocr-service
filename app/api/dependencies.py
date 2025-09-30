"""
FastAPI Dependencies для Dependency Injection
"""
from functools import lru_cache

from app.config import get_settings, Settings
from app.infrastructure.ocr_engines.paddleocr_engine import PaddleOCREngine
from app.services.receipt_parser import ReceiptParser
from app.services.ocr_service import OCRService
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache()
def get_paddleocr_engine() -> PaddleOCREngine:
    """
    Получить инстанс PaddleOCR Engine (singleton)
    Инициализируется один раз и переиспользуется
    """
    settings = get_settings()
    
    engine = PaddleOCREngine(
        use_angle_cls=settings.PADDLEOCR_USE_ANGLE_CLS,
        lang=settings.PADDLEOCR_LANG,
        use_gpu=settings.PADDLEOCR_USE_GPU,
        show_log=settings.PADDLEOCR_SHOW_LOG
    )
    
    # Инициализируем движок
    engine.initialize()
    
    return engine


@lru_cache()
def get_receipt_parser() -> ReceiptParser:
    """Получить инстанс ReceiptParser (singleton)"""
    return ReceiptParser()


def get_ocr_service(
    paddleocr_engine: PaddleOCREngine = None,
    receipt_parser: ReceiptParser = None
) -> OCRService:
    """
    Получить инстанс OCR Service
    
    Args:
        paddleocr_engine: PaddleOCR движок (будет создан если None)
        receipt_parser: Парсер чеков (будет создан если None)
    """
    settings = get_settings()
    
    if paddleocr_engine is None:
        paddleocr_engine = get_paddleocr_engine()
    
    if receipt_parser is None:
        receipt_parser = get_receipt_parser()
    
    return OCRService(
        paddleocr_engine=paddleocr_engine,
        receipt_parser=receipt_parser,
        max_image_size_mb=settings.MAX_IMAGE_SIZE_MB
    )

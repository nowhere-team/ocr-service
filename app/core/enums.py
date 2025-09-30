"""
Enums для типобезопасности
"""
from enum import Enum


class OCREngine(str, Enum):
    """OCR движки"""
    PADDLEOCR = "paddleocr"
    OCEAN_OCR = "ocean_ocr"  # На будущее


class ImageFormat(str, Enum):
    """Форматы изображений"""
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"


class ReceiptType(str, Enum):
    """Типы чеков"""
    FISCAL = "fiscal"  # Фискальный чек
    NON_FISCAL = "non_fiscal"  # Нефискальный чек
    UNKNOWN = "unknown"


class PaymentMethod(str, Enum):
    """Способы оплаты"""
    CASH = "cash"
    CARD = "card"
    MIXED = "mixed"  # Часть нал, часть карта
    UNKNOWN = "unknown"

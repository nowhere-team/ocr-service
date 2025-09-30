"""
Pydantic модели для ответов API
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.models.domain import Receipt
from app.core.enums import OCREngine


class OCRResponse(BaseModel):
    """Ответ с распознанным чеком"""
    success: bool = Field(..., description="Успешность операции")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Общая уверенность распознавания"
    )
    processing_time_ms: int = Field(..., description="Время обработки в миллисекундах")
    receipt: Optional[Receipt] = Field(None, description="Распознанный чек")
    ocr_engine_used: OCREngine = Field(..., description="Использованный OCR движок")
    error: Optional[str] = Field(None, description="Сообщение об ошибке")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "confidence": 0.87,
                "processing_time_ms": 1420,
                "receipt": {
                    "store": {
                        "name": "Пятёрочка",
                        "address": "г. Москва, ул. Ленина 15",
                        "inn": "5027143345"
                    },
                    "items": [
                        {
                            "name": "Молоко 3.2%",
                            "quantity": 1.0,
                            "price": "89.90",
                            "total": "89.90"
                        }
                    ],
                    "totals": {
                        "total": "89.90",
                        "payment_method": "card"
                    },
                    "metadata": {
                        "date": "2025-09-30T14:35:00",
                        "receipt_type": "fiscal"
                    },
                    "confidence": 0.87
                },
                "ocr_engine_used": "paddleocr"
            }
        }


class HealthResponse(BaseModel):
    """Ответ health check"""
    status: str = Field(..., description="Статус сервиса")
    version: str = Field(..., description="Версия приложения")
    ocr_engine_available: bool = Field(..., description="Доступность OCR движка")

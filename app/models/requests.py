"""
Pydantic модели для входящих запросов
"""
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, field_validator


class OCRRequest(BaseModel):
    """Запрос на распознавание чека"""
    image: str = Field(
        ...,
        description="Изображение в формате base64",
        min_length=100
    )
    options: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Дополнительные опции обработки"
    )
    
    @field_validator('image')
    @classmethod
    def validate_image_not_empty(cls, v: str) -> str:
        """Проверка что изображение не пустое"""
        if not v or not v.strip():
            raise ValueError("Image cannot be empty")
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "options": {
                    "use_angle_cls": True
                }
            }
        }

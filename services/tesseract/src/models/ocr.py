from pydantic import BaseModel, Field


class OCRResult(BaseModel):
    """result of text recognition"""

    text: str = Field(description="recognized text content")
    confidence: float = Field(ge=0.0, le=1.0, description="average confidence score (0-100)")

    class Config:
        json_schema_extra = {
            "example": {"text": "ООО ПРОДУКТЫ\\nИНН 1234567890\\nЧек №123", "confidence": 0.853}
        }

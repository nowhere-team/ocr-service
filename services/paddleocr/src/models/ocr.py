from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """single recognized text block with metadata"""

    text: str = Field(description="recognized text content")
    confidence: float = Field(ge=0.0, le=1.0, description="recognition confidence score")
    bbox: list[list[float]] = Field(description="bounding box coordinates")


class RecognitionResponse(BaseModel):
    """response model for text recognition"""

    text: str = Field(description="all recognized text joined by newlines")
    confidence: float = Field(ge=0.0, le=1.0, description="average confidence across all blocks")
    blocks: list[TextBlock] = Field(description="list of recognized text blocks")
    processing_time_ms: float = Field(description="processing time in milliseconds")

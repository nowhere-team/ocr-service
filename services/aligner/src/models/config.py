from pydantic import BaseModel, Field


class AlignmentConfig(BaseModel):
    """configuration for alignment algorithm"""

    simplify_percent: float = Field(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="polygon simplification as percentage of perimeter (scale-independent)",
    )
    apply_ocr_preprocessing: bool = Field(
        default=False, description="apply ocr binarization after alignment"
    )
    aggressive: bool = Field(
        default=False,
        description="aggressive preprocessing mode (sharp edges, may lose details)",
    )

    debug_mode: bool = Field(
        default=False, description="save intermediate images and publish debug events"
    )
    recognition_id: str = Field(default="", description="recognition id for debug tracking")

    @classmethod
    def default(cls) -> "AlignmentConfig":
        """default config - balanced mode"""
        return cls(
            simplify_percent=2.0,
            apply_ocr_preprocessing=False,
            aggressive=False,
            debug_mode=False,
        )

    @classmethod
    def for_high_quality(cls) -> "AlignmentConfig":
        """for high quality images - aggressive mode"""
        return cls(
            simplify_percent=1.5,
            apply_ocr_preprocessing=True,
            aggressive=True,
            debug_mode=False,
        )

    @classmethod
    def for_low_quality(cls) -> "AlignmentConfig":
        """for low quality images - gentle mode"""
        return cls(
            simplify_percent=3.0,
            apply_ocr_preprocessing=True,
            aggressive=False,
            debug_mode=False,
        )

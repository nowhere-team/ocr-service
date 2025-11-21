from pydantic import BaseModel, Field


class AlignmentConfig(BaseModel):
    """configuration for alignment algorithm"""

    simplify_step: float = Field(default=50.0, ge=1.0, description="polygon simplification epsilon")
    apply_ocr_preprocessing: bool = Field(
        default=False, description="apply ocr binarization after alignment"
    )
    aggressive: bool = Field(
        default=False, description="aggressive preprocessing mode (sharp edges, may lose details)"
    )

    @classmethod
    def default(cls) -> "AlignmentConfig":
        """default config - balanced mode"""
        return cls(
            simplify_step=50.0,
            apply_ocr_preprocessing=False,
            aggressive=False,
        )

    @classmethod
    def for_high_quality(cls) -> "AlignmentConfig":
        """for high quality images - aggressive mode"""
        return cls(
            simplify_step=30.0,
            apply_ocr_preprocessing=True,
            aggressive=True,
        )

    @classmethod
    def for_low_quality(cls) -> "AlignmentConfig":
        """for low quality images - gentle mode"""
        return cls(
            simplify_step=70.0,
            apply_ocr_preprocessing=True,
            aggressive=False,
        )

from pydantic import BaseModel, Field


class AlignmentConfig(BaseModel):
    """configuration for alignment algorithm"""

    mode: str = Field(
        default="classic",
        description="alignment mode: 'classic' for cv-based or 'neural' for nn-based detection",
    )
    simplify_percent: float = Field(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="polygon simplification as percentage of perimeter (scale-independent, used only in classic mode)",
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
        """default config - balanced classic mode"""
        return cls(
            mode="classic",
            simplify_percent=2.0,
            apply_ocr_preprocessing=False,
            aggressive=False,
            debug_mode=False,
        )

    @classmethod
    def neural(cls) -> "AlignmentConfig":
        """neural network based detection using docaligner"""
        return cls(
            mode="neural",
            simplify_percent=2.0,  # not used in neural mode, but kept for compatibility
            apply_ocr_preprocessing=False,
            aggressive=False,
            debug_mode=False,
        )

    @classmethod
    def for_high_quality(cls) -> "AlignmentConfig":
        """for high quality images - aggressive mode"""
        return cls(
            mode="classic",
            simplify_percent=1.5,
            apply_ocr_preprocessing=True,
            aggressive=True,
            debug_mode=False,
        )

    @classmethod
    def for_low_quality(cls) -> "AlignmentConfig":
        """for low quality images - gentle mode"""
        return cls(
            mode="classic",
            simplify_percent=3.0,
            apply_ocr_preprocessing=True,
            aggressive=False,
            debug_mode=False,
        )

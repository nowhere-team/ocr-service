import time
from collections.abc import Awaitable, Callable

import numpy as np

from ..logger import get_logger
from ..models import AlignmentConfig
from ..observability.telemetry import get_tracer
from .aligner import AlignerService
from .common import preprocess_for_ocr
from .neural import NeuralAligner

logger = get_logger(__name__)
tracer = get_tracer(__name__)


class HybridAligner:
    def __init__(
        self,
        enable_neural: bool = True,
        neural_backend: str = "cpu",
        neural_model_cfg: str = "fastvit_sa24",
    ):
        self.classic_aligner = AlignerService()
        self.neural_aligner: NeuralAligner | None = None
        self.enable_neural = enable_neural

        if enable_neural:
            try:
                self.neural_aligner = NeuralAligner(
                    backend=neural_backend, model_cfg=neural_model_cfg
                )
                logger.info(
                    "hybrid aligner initialized with neural support",
                    backend=neural_backend,
                    model_cfg=neural_model_cfg,
                )
            except Exception as e:
                logger.warning(
                    "failed to initialize neural aligner, falling back to classic only",
                    error=str(e),
                )
                self.enable_neural = False
        else:
            logger.info("hybrid aligner initialized without neural support")

    async def align(
        self,
        image_array: np.ndarray,
        config: AlignmentConfig,
        debug_callback: Callable[[str, int, np.ndarray, dict], Awaitable[None]] | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        start_time = time.time()

        with tracer.start_as_current_span("hybrid_aligner.align") as span:
            span.set_attribute("config.mode", config.mode)
            span.set_attribute("neural.enabled", self.enable_neural)

            try_neural = (
                config.mode == "neural" and self.enable_neural and self.neural_aligner is not None
            )

            warped: np.ndarray | None = None
            used_method: str | None = None
            fallback_used = False

            if try_neural:
                try:
                    logger.info("attempting neural alignment via docaligner")
                    warped = await self.neural_aligner.align(image_array, config, debug_callback)
                    used_method = "neural"
                    span.set_attribute("method.used", "neural")
                    span.set_attribute("method.fallback", False)

                except Exception as e:
                    logger.warning(
                        "neural alignment failed, falling back to classic",
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    span.set_attribute("neural.error", str(e))
                    span.set_attribute("neural.error_type", type(e).__name__)
                    warped = None
                    fallback_used = True

            if warped is None:
                logger.info("using classic opencv-based alignment")

                fallback_callback = None if fallback_used else debug_callback

                warped = await self.classic_aligner.align(image_array, config, fallback_callback)
                used_method = "classic"
                span.set_attribute("method.used", "classic")

                if try_neural:
                    span.set_attribute("method.fallback", True)

            preprocessed = preprocess_for_ocr(warped, config.aggressive)

            duration = (time.time() - start_time) * 1000
            span.set_attribute("processing.duration_ms", duration)

            logger.info(
                "hybrid alignment completed",
                method=used_method,
                duration_ms=round(duration, 2),
                fallback_used=try_neural and used_method == "classic",
            )

            return warped, preprocessed

    @staticmethod
    def shutdown():
        logger.info("shutting down hybrid aligner")
        AlignerService.shutdown()
        NeuralAligner.shutdown()

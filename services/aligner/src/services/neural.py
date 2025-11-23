import time
from collections.abc import Awaitable, Callable

import cv2
import numpy as np

from ..logger import get_logger
from ..models import AlignmentConfig
from ..observability.telemetry import get_tracer
from .common import (
    order_corners,
    warp_perspective,
)
from .debug_helper import DebugHelper

logger = get_logger(__name__)
tracer = get_tracer(__name__)


class NeuralAligner:
    """
    neural network based document alignment using docaligner-docsaid

    uses heatmap regression to detect corners, avoiding amplification errors
    that occur with direct coordinate regression approaches
    """

    def __init__(self, backend: str = "cpu", model_cfg: str = "fastvit_sa24"):
        """
        args:
            backend: computation backend - "cpu" or "cuda"
            model_cfg: model configuration name (lcnet100, fastvit_t8, fastvit_sa24, etc)
        """
        try:
            from capybara import Backend
            from docaligner import DocAligner, ModelType
        except ImportError as e:
            logger.error(
                "docaligner-docsaid not installed, install with: pip install docaligner-docsaid"
            )
            raise ImportError(
                "docaligner-docsaid required but not installed. run: pip install docaligner-docsaid"
            ) from e

        backend_enum = Backend.cuda if backend.lower() == "cuda" else Backend.cpu

        self.model = DocAligner(
            backend=backend_enum,
            model_type=ModelType.heatmap,
            model_cfg=model_cfg,
        )

        logger.info(
            "neural aligner initialized",
            model_cfg=model_cfg,
        )

    async def align(
        self,
        image_array: np.ndarray,
        config: AlignmentConfig,
        debug_callback: Callable[[str, int, np.ndarray, dict], Awaitable[None]] | None = None,
    ) -> np.ndarray:
        start_time = time.time()
        debug = DebugHelper(debug_callback, config.debug_mode)

        with tracer.start_as_current_span("neural_aligner.align") as span:
            span.set_attribute("image.shape", str(image_array.shape))
            span.set_attribute("config.aggressive", config.aggressive)

            try:
                await debug.log(
                    "00_original",
                    image_array,
                    {
                        "description": "original uploaded image",
                        "shape": str(image_array.shape),
                        "method": "neural",
                    },
                )

                padded_img = self._add_padding(image_array, 100)

                polygon = self.model(padded_img, do_center_crop=False)

                if polygon is not None and len(polygon) > 0:
                    polygon = polygon - 100

                span.set_attribute(
                    "neural.corners_detected", len(polygon) if polygon is not None else 0
                )

                logger.info(f"neural aligner detected corners: {polygon}")
                if polygon is None or len(polygon) != 4:
                    logger.warning(
                        "neural model failed to detect document corners",
                        detected_points=len(polygon) if polygon is not None else 0,
                    )
                    raise ValueError("neural model could not detect document")

                polygon_vis = self._draw_polygon_image(image_array, polygon)
                await debug.log(
                    "02_corners_neural",
                    polygon_vis,
                    {
                        "description": "corners detected by neural network (docaligner)",
                        "corners": polygon.tolist(),
                        "method": "neural",
                        "detection_method": "heatmap_regression",
                    },
                )

                corners = order_corners(polygon)

                warped = warp_perspective(image_array, corners)
                await debug.log(
                    "03_warped",
                    warped,
                    {
                        "description": "perspective-corrected image",
                        "output_shape": str(warped.shape),
                        "method": "neural",
                    },
                )

                duration = (time.time() - start_time) * 1000
                span.set_attribute("processing.duration_ms", duration)

                logger.info(
                    "neural alignment completed",
                    duration_ms=round(duration, 2),
                    output_shape=warped.shape,
                    method="docaligner_heatmap",
                )

                return warped

            except Exception as e:
                logger.error("neural alignment failed", error=str(e), exc_info=True)
                raise

    @staticmethod
    def _add_padding(image: np.ndarray, padding: int) -> np.ndarray:
        """
        add padding around image for better corner detection

        args:
            image: input image
            padding: padding size in pixels

        returns:
            padded image
        """
        return cv2.copyMakeBorder(
            image, padding, padding, padding, padding, cv2.BORDER_CONSTANT, value=(0, 0, 0)
        )

    def _detect_corners_neural(self, image: np.ndarray) -> np.ndarray | None:
        """
        detect document corners using docaligner neural network

        args:
            image: input image in bgr format

        returns:
            polygon with 4 corner points or none if detection failed
        """
        try:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            polygon = self.model(image_rgb, do_center_crop=False)
            logger.info(f"neural aligner detected corners: {polygon}")

            if polygon is None or len(polygon) == 0:
                logger.warning("docaligner returned empty polygon")
                return None

            if len(polygon) != 4:
                logger.warning("docaligner returned non-quadrilateral polygon", points=len(polygon))
                return None

            logger.debug("neural corners detected", corners=polygon.tolist())
            return polygon

        except Exception as e:
            logger.error("neural corner detection failed", error=str(e), exc_info=True)
            return None

    @staticmethod
    def _draw_polygon_image(img: np.ndarray, polygon: np.ndarray, thickness: int = 3) -> np.ndarray:
        colors = [(0, 255, 255), (255, 255, 0), (0, 255, 0), (0, 0, 255)]
        export_img = img.copy()
        _polys = polygon.astype(int)
        _polys_roll = np.roll(_polys, 1, axis=0)
        for p1, p2, color in zip(_polys, _polys_roll, colors, strict=False):
            export_img = cv2.circle(
                export_img,
                p2,
                radius=thickness * 2,
                color=color,
                thickness=-1,
                lineType=cv2.LINE_AA,
            )
            export_img = cv2.arrowedLine(
                export_img, p2, p1, color=color, thickness=thickness, line_type=cv2.LINE_AA
            )
        return export_img

    @staticmethod
    def shutdown():
        logger.info("shutting down neural aligner")

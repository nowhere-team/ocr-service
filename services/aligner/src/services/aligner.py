# services/aligner/src/services/aligner.py
import time
from collections import deque
from collections.abc import Awaitable, Callable, Sequence

import cv2
import numpy as np

from ..logger import get_logger
from ..models import AlignmentConfig
from ..observability.telemetry import get_tracer
from .debug_helper import DebugHelper

logger = get_logger(__name__)
tracer = get_tracer(__name__)


class AlignerService:
    """
    perspective alignment service for receipt images

    based on opencv contour detection and perspective transformation
    """

    def __init__(self):
        logger.info("aligner service initialized")

    async def align(
        self,
        image_array: np.ndarray,
        config: AlignmentConfig,
        debug_callback: Callable[[str, int, np.ndarray, dict], Awaitable[None]] | None = None,
    ) -> np.ndarray:
        """
        align receipt image perspective

        args:
            image_array: input image as numpy array (BGR)
            config: alignment configuration
            debug_callback: optional async callback for debug visualization

        returns:
            aligned image as numpy array
        """
        start_time = time.time()
        debug = DebugHelper(debug_callback, config.debug_mode)

        with tracer.start_as_current_span("aligner_service.align") as span:
            span.set_attribute("image.shape", str(image_array.shape))
            span.set_attribute("config.aggressive", config.aggressive)
            span.set_attribute("config.ocr_prep", config.apply_ocr_preprocessing)
            span.set_attribute("config.debug_mode", config.debug_mode)

            try:
                await debug.log(
                    "00_original",
                    image_array,
                    {"description": "original uploaded image", "shape": str(image_array.shape)},
                )

                is_inverted, working_image = self._handle_dark_receipt(image_array)
                span.set_attribute("preprocessing.inverted", is_inverted)

                await debug.log(
                    "01_inverted" if is_inverted else "01_input",
                    working_image,
                    {
                        "description": "inverted image (dark receipt)"
                        if is_inverted
                        else "input without inversion",
                        "is_inverted": is_inverted,
                    },
                )

                preprocessed = self._preprocess(working_image)
                await debug.log(
                    "02_preprocessed",
                    preprocessed,
                    {"description": "CLAHE illumination equalization applied"},
                )

                seed_point = self._find_best_seed_point(preprocessed)
                logger.debug("selected seed point", point=seed_point)

                if debug:
                    seed_vis = preprocessed.copy()
                    cv2.circle(seed_vis, seed_point, 20, (0, 0, 255), -1)
                    cv2.circle(seed_vis, seed_point, 22, (0, 255, 255), 2)
                    await debug.log(
                        "03_seed_point",
                        seed_vis,
                        {
                            "description": f"optimal seed point at {seed_point}",
                            "seed_x": seed_point[0],
                            "seed_y": seed_point[1],
                        },
                    )

                mask = self._find_check_mask(preprocessed, seed_point)

                mask_coverage = np.sum(mask > 0) / float(mask.shape[0] * mask.shape[1])
                span.set_attribute("mask.coverage", mask_coverage)

                if mask_coverage > 0.85 or mask_coverage < 0.03:
                    logger.warning("suspicious mask coverage", coverage=mask_coverage)

                if debug:
                    mask_vis = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                    await debug.log(
                        "04_mask_raw",
                        mask_vis,
                        {
                            "description": "flood fill mask before cleanup",
                            "coverage": mask_coverage,
                        },
                    )

                    kernel_large = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
                    clean = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_large)
                    await debug.log(
                        "05_mask_closed",
                        cv2.cvtColor(clean, cv2.COLOR_GRAY2BGR),
                        {"description": "after morphological CLOSE (15x15)"},
                    )

                    kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
                    clean = cv2.morphologyEx(clean, cv2.MORPH_OPEN, kernel_small)
                    await debug.log(
                        "06_mask_opened",
                        cv2.cvtColor(clean, cv2.COLOR_GRAY2BGR),
                        {"description": "after morphological OPEN (5x5)"},
                    )

                polygon = self._mask_to_polygon(mask, config.simplify_percent)

                if debug:
                    contour_vis = image_array.copy()
                    if len(polygon) > 0:
                        cv2.polylines(contour_vis, [polygon.astype(np.int32)], True, (0, 255, 0), 3)
                        for i, pt in enumerate(polygon):
                            # noinspection PyUnresolvedReferences
                            cv2.circle(contour_vis, tuple(pt.astype(int)), 8, (255, 0, 0), -1)
                            # noinspection PyUnresolvedReferences
                            cv2.putText(
                                contour_vis,
                                str(i),
                                tuple(pt.astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (255, 255, 255),
                                2,
                            )
                    await debug.log(
                        "07_polygon_points",
                        contour_vis,
                        {
                            "description": f"detected polygon with {len(polygon)} points",
                            "polygon_points": len(polygon),
                            "simplify_percent": config.simplify_percent,
                        },
                    )

                if len(polygon) > 0:
                    polygon = self._ensure_receipt_shape(polygon, mask)

                rect = cv2.minAreaRect(polygon)
                corners = cv2.boxPoints(rect)
                logger.debug("found corners using minAreaRect", rect=rect)

                if debug:
                    corners_vis = image_array.copy()
                    cv2.polylines(corners_vis, [corners.astype(np.int32)], True, (0, 255, 255), 3)
                    for i, corner in enumerate(corners):
                        # noinspection PyUnresolvedReferences
                        cv2.circle(corners_vis, tuple(corner.astype(int)), 12, (0, 0, 255), -1)
                        cv2.putText(
                            corners_vis,
                            f"C{i}",
                            (int(corner[0]) - 20, int(corner[1]) - 20),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.8,
                            (255, 255, 0),
                            2,
                        )
                    await debug.log(
                        "08_corners_detected",
                        corners_vis,
                        {
                            "description": "4 corners from minAreaRect",
                            "corners": corners.tolist(),
                            "rect_angle": float(rect[2]),
                        },
                    )

                warped = self._warp_perspective(image_array, corners)
                await debug.log(
                    "09_warped",
                    warped,
                    {
                        "description": "perspective-corrected image",
                        "output_shape": str(warped.shape),
                    },
                )

                if config.apply_ocr_preprocessing:
                    warped = self._preprocess_for_ocr(warped, config.aggressive)
                    await debug.log(
                        "10_ocr_preprocessed",
                        warped,
                        {
                            "description": f"OCR preprocessing ({'aggressive' if config.aggressive else 'gentle'})",
                            "aggressive": config.aggressive,
                        },
                    )

                duration = (time.time() - start_time) * 1000
                span.set_attribute("processing.duration_ms", duration)

                logger.info(
                    "alignment completed",
                    duration_ms=round(duration, 2),
                    output_shape=warped.shape,
                    mask_coverage=round(mask_coverage, 3),
                    total_steps=debug.step_counter,
                )

                return warped

            except Exception as e:
                logger.error("alignment failed", error=str(e), exc_info=True)
                raise

    @staticmethod
    def _handle_dark_receipt(image: np.ndarray) -> tuple[bool, np.ndarray]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)

        if mean_brightness < 100:
            logger.debug("detected dark receipt, inverting", brightness=mean_brightness)
            return True, 255 - image

        return False, image

    @staticmethod
    def _preprocess(image: np.ndarray) -> np.ndarray:
        blurred = cv2.GaussianBlur(image, (5, 5), 0)
        lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        lab = cv2.merge([l_channel, a_channel, b_channel])
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        return cv2.addWeighted(result, 1.2, np.zeros_like(result), 0, 0)

    def _find_best_seed_point(self, image: np.ndarray) -> tuple[int, int]:
        h, w = image.shape[:2]
        candidates = [
            (w // 2, h // 2),
            (w // 3, h // 3),
            (2 * w // 3, h // 3),
            (w // 3, 2 * h // 3),
            (2 * w // 3, 2 * h // 3),
        ]

        best_point = candidates[0]
        max_homogeneity = 0.0

        for point in candidates:
            samples = self._get_samples(image, point, radius=5)
            variance = np.std(samples)
            homogeneity = 1.0 / (1.0 + variance)

            if homogeneity > max_homogeneity:
                max_homogeneity = homogeneity
                best_point = point

        logger.debug(
            "best seed point selected", point=best_point, homogeneity=round(max_homogeneity, 4)
        )
        return best_point

    def _find_check_mask(self, image: np.ndarray, seed_point: tuple[int, int]) -> np.ndarray:
        h, w = image.shape[:2]
        samples = self._get_samples(image, seed_point, radius=3)
        mean_color = np.mean(samples, axis=0)
        tolerance = self._compute_auto_tolerance(samples, mean_color)

        logger.debug("flood fill tolerance", value=float(tolerance))

        mask = np.zeros((h, w), dtype=np.uint8)
        visited = np.zeros((h, w), dtype=bool)
        queue = deque([seed_point])
        visited[seed_point[1], seed_point[0]] = True

        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]

        while queue:
            x, y = queue.popleft()
            color = image[y, x].astype(np.float32)

            if self._color_distance(color, mean_color) <= tolerance:
                alpha = 0.005
                mean_color = mean_color * (1 - alpha) + color * alpha
                mask[y, x] = 255

                for dx, dy in dirs:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
                        visited[ny, nx] = True
                        queue.append((nx, ny))

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        return mask

    def _mask_to_polygon(self, mask: np.ndarray, simplify_percent: float) -> np.ndarray:
        kernel_large = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        clean = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_large)
        kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        clean = cv2.morphologyEx(clean, cv2.MORPH_OPEN, kernel_small)

        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        if not contours:
            logger.warning("no contours found")
            return np.array([])

        valid_contours = self._filter_receipt_contours(contours)
        best_contour = max(valid_contours, key=cv2.contourArea)

        peri = cv2.arcLength(best_contour, True)
        epsilon = (simplify_percent / 100.0) * peri
        approx = cv2.approxPolyDP(best_contour, epsilon, True)

        logger.debug(
            "polygon simplified",
            original_points=len(best_contour),
            simplified_points=len(approx),
            epsilon=round(epsilon, 2),
        )

        approx = self._filter_sharp_angles(approx, min_angle_deg=15)

        if len(approx) < 4 or len(approx) > 8:
            logger.debug("contour shape unusual, using minAreaRect", points=len(approx))
            rect = cv2.minAreaRect(best_contour)
            box = cv2.boxPoints(rect)
            approx = box.astype(np.int32).reshape(-1, 1, 2)

        return approx.squeeze()

    @staticmethod
    def _filter_receipt_contours(contours: Sequence[np.ndarray]) -> list[np.ndarray]:
        filtered = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w == 0:
                continue
            aspect = h / w
            if 1.0 < aspect < 6.0:
                filtered.append(cnt)
        return filtered if filtered else list(contours)

    @staticmethod
    def _ensure_receipt_shape(polygon: np.ndarray, mask: np.ndarray) -> np.ndarray:
        if len(polygon) < 4:
            logger.debug("polygon has less than 4 points, using mask bounding rect")
            points = cv2.findNonZero(mask)
            if points is not None:
                rect = cv2.minAreaRect(points)
                box = cv2.boxPoints(rect)
                return box.astype(np.float32)
        return polygon

    @staticmethod
    def _filter_sharp_angles(polygon: np.ndarray, min_angle_deg: float) -> np.ndarray:
        filtered = []
        pts = polygon.squeeze()

        if len(pts.shape) == 1:
            return polygon

        for i in range(len(pts)):
            angle = AlignerService._compute_angle_at_point(pts, i)
            if angle < 0:
                angle += 360

            if min_angle_deg < angle < (360 - min_angle_deg):
                filtered.append(pts[i])

        if len(filtered) < 4:
            return polygon

        return np.array(filtered, dtype=np.float32)

    def _warp_perspective(self, image: np.ndarray, corners: np.ndarray) -> np.ndarray:
        ordered = self._order_corners(corners)

        width_a = np.linalg.norm(ordered[1] - ordered[0])
        width_b = np.linalg.norm(ordered[2] - ordered[3])
        max_width = max(width_a, width_b)

        height_a = np.linalg.norm(ordered[3] - ordered[0])
        height_b = np.linalg.norm(ordered[2] - ordered[1])
        max_height = max(height_a, height_b)

        scale = 1.5
        max_width = max(64, int(max_width * scale))
        max_height = max(64, int(max_height * scale))

        dst = np.array(
            [
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1],
            ],
            dtype=np.float32,
        )

        matrix = cv2.getPerspectiveTransform(ordered, dst)
        return cv2.warpPerspective(
            image,
            matrix,
            (max_width, max_height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    @staticmethod
    def _order_corners(pts: np.ndarray) -> np.ndarray:
        sorted_by_y = pts[np.argsort(pts[:, 1])]
        top_points = sorted_by_y[:2]
        bottom_points = sorted_by_y[2:]

        top_points = top_points[np.argsort(top_points[:, 0])]
        tl, tr = top_points[0], top_points[1]

        bottom_points = bottom_points[np.argsort(bottom_points[:, 0])]
        bl, br = bottom_points[0], bottom_points[1]

        width = np.linalg.norm(tr - tl)
        height = np.linalg.norm(bl - tl)

        if width > height * 1.3:
            logger.debug(
                "receipt horizontal, rotating corner order",
                width=round(width, 1),
                height=round(height, 1),
            )
            return np.array([bl, tl, tr, br], dtype=np.float32)
        else:
            logger.debug(
                "receipt vertical, standard order", width=round(width, 1), height=round(height, 1)
            )
            return np.array([tl, tr, br, bl], dtype=np.float32)

    @staticmethod
    def _preprocess_for_ocr(image: np.ndarray, aggressive: bool) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        if aggressive:
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
            )
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        else:
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 5
            )
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        result = thresh.copy()
        cv2.normalize(thresh, result, 0, 255, cv2.NORM_MINMAX)
        return result

    @staticmethod
    def _get_samples(image: np.ndarray, center: tuple[int, int], radius: int) -> np.ndarray:
        samples = []
        x, y = center
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                sample_y = y + dy
                sample_x = x + dx
                if 0 <= sample_y < image.shape[0] and 0 <= sample_x < image.shape[1]:
                    samples.append(image[sample_y, sample_x])
        return np.array(samples, dtype=np.float32)

    @staticmethod
    def _color_distance(a: np.ndarray, b: np.ndarray) -> float:
        diff = a - b
        return float(np.sqrt(np.sum(diff * diff)))

    def _compute_auto_tolerance(self, samples: np.ndarray, mean_color: np.ndarray) -> float:
        variance = np.mean([self._color_distance(s, mean_color) for s in samples])
        brightness = mean_color[2] * 0.299 + mean_color[1] * 0.587 + mean_color[0] * 0.114
        tolerance = 13 + (255 - brightness) * 0.7 + variance * 0.7
        return float(np.clip(tolerance, 10, 65))

    @staticmethod
    def _compute_angle_at_point(pts: np.ndarray, index: int) -> float:
        prev = pts[(index - 1) % len(pts)]
        curr = pts[index]
        next_pt = pts[(index + 1) % len(pts)]
        angle = abs(
            np.degrees(
                np.arctan2(next_pt[1] - curr[1], next_pt[0] - curr[0])
                - np.arctan2(prev[1] - curr[1], prev[0] - curr[0])
            )
        )
        return float(angle)

    @staticmethod
    def shutdown():
        logger.info("shutting down aligner service")

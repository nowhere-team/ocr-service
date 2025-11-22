import time
from collections import deque

import cv2
import numpy as np

from ..logger import get_logger
from ..models import AlignmentConfig
from ..observability.telemetry import get_tracer

logger = get_logger(__name__)
tracer = get_tracer(__name__)


class AlignerService:
    """
    perspective alignment service for receipt images

    based on opencv contour detection and perspective transformation
    key features:
    - adaptive multi-point seed detection for flood fill
    - CLAHE-based illumination equalization
    - relative polygon simplification (scale-independent)
    - dark receipt inversion support
    - aspect ratio filtering for receipt detection
    - parametrized preprocessing for OCR (gentle/aggressive modes)
    """

    def __init__(self):
        """initialize aligner service"""
        logger.info("aligner service initialized")

    async def align(self, image_array: np.ndarray, config: AlignmentConfig) -> np.ndarray:
        """
        align receipt image perspective

        args:
            image_array: input image as numpy array (BGR)
            config: alignment configuration

        returns:
            aligned image as numpy array
        """
        start_time = time.time()

        with tracer.start_as_current_span("aligner_service.align") as span:
            span.set_attribute("image.shape", str(image_array.shape))
            span.set_attribute("config.aggressive", config.aggressive)
            span.set_attribute("config.ocr_prep", config.apply_ocr_preprocessing)

            try:
                # 0. detect if dark receipt and invert if needed
                is_inverted, working_image = self._handle_dark_receipt(image_array)
                if is_inverted:
                    span.set_attribute("preprocessing.inverted", True)

                # 1. preprocess - illumination equalization
                preprocessed = self._preprocess(working_image)

                # 2. find optimal seed point for flood fill
                seed_point = self._find_best_seed_point(preprocessed)
                logger.debug("selected seed point", point=seed_point)

                # 3. find check mask via flood fill
                mask = self._find_check_mask(preprocessed, seed_point)

                # validate mask coverage
                mask_coverage = np.sum(mask > 0) / (mask.shape[0] * mask.shape[1])
                span.set_attribute("mask.coverage", mask_coverage)

                if mask_coverage > 0.85 or mask_coverage < 0.03:
                    logger.warning(
                        "suspicious mask coverage, may indicate detection failure",
                        coverage=mask_coverage,
                    )

                # 4. extract polygon contour
                polygon = self._mask_to_polygon(mask, config.simplify_percent)

                # 5. filter contours by receipt aspect ratio
                if len(polygon) > 0:
                    polygon = self._ensure_receipt_shape(polygon, mask)

                # 6. get 4 corners using minAreaRect
                rect = cv2.minAreaRect(polygon)
                corners = cv2.boxPoints(rect)
                logger.debug("found corners using minAreaRect", rect=rect)

                # 7. perspective warp (apply to original, not inverted or binarized)
                warped = self._warp_perspective(image_array, corners)

                # 8. optional ocr preprocessing
                if config.apply_ocr_preprocessing:
                    warped = self._preprocess_for_ocr(warped, config.aggressive)

                duration = (time.time() - start_time) * 1000
                span.set_attribute("processing.duration_ms", duration)

                logger.info(
                    "alignment completed",
                    duration_ms=round(duration, 2),
                    output_shape=warped.shape,
                    mask_coverage=round(mask_coverage, 3),
                )

                return warped

            except Exception as e:
                logger.error("alignment failed", error=str(e), exc_info=True)
                raise

    @staticmethod
    def _handle_dark_receipt(image: np.ndarray) -> tuple[bool, np.ndarray]:
        """
        detect and invert dark receipts (dark background, light text)

        returns: (is_inverted, processed_image)
        """
        # calculate mean brightness
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)

        # dark receipt threshold
        if mean_brightness < 100:
            logger.debug("detected dark receipt, inverting", brightness=mean_brightness)
            inverted = 255 - image
            return True, inverted

        return False, image

    @staticmethod
    def _preprocess(image: np.ndarray) -> np.ndarray:
        """
        preprocessing: smoothing + illumination equalization via CLAHE
        doesn't touch details, only removes uneven lighting
        """
        # gaussian blur to remove noise
        blurred = cv2.GaussianBlur(image, (5, 5), 0)

        # LAB colorspace - better for illumination work
        lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)

        # CLAHE on L channel - adaptive histogram equalization
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        lab = cv2.merge([l_channel, a_channel, b_channel])

        # back to BGR
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        # slight contrast boost
        result = cv2.addWeighted(result, 1.2, np.zeros_like(result), 0, 0)

        return result

    def _find_best_seed_point(self, image: np.ndarray) -> tuple[int, int]:
        """
        find optimal seed point for flood fill using grid search

        selects point with highest color homogeneity (lowest variance)
        this is more robust than fixed center point
        """
        h, w = image.shape[:2]

        # candidate points: center + four quadrants
        candidates = [
            (w // 2, h // 2),  # center (highest priority)
            (w // 3, h // 3),  # top-left quadrant
            (2 * w // 3, h // 3),  # top-right quadrant
            (w // 3, 2 * h // 3),  # bottom-left quadrant
            (2 * w // 3, 2 * h // 3),  # bottom-right quadrant
        ]

        best_point = candidates[0]
        max_homogeneity = 0.0

        for point in candidates:
            # sample colors around point
            samples = self._get_samples(image, point, radius=5)

            # calculate color variance (lower = more homogeneous)
            variance = np.std(samples)
            homogeneity = 1.0 / (1.0 + variance)

            if homogeneity > max_homogeneity:
                max_homogeneity = homogeneity
                best_point = point

        logger.debug(
            "best seed point selected",
            point=best_point,
            homogeneity=round(max_homogeneity, 4),
        )

        return best_point

    def _find_check_mask(self, image: np.ndarray, seed_point: tuple[int, int]) -> np.ndarray:
        """
        find check mask via flood fill from seed point
        adaptive tolerance based on local color variance
        """
        h, w = image.shape[:2]

        # sample colors around seed point
        samples = self._get_samples(image, seed_point, radius=3)
        mean_color = np.mean(samples, axis=0)
        tolerance = self._compute_auto_tolerance(samples, mean_color)

        logger.debug("flood fill tolerance", value=float(tolerance))

        # flood fill with adaptive mean color
        mask = np.zeros((h, w), dtype=np.uint8)
        visited = np.zeros((h, w), dtype=bool)
        queue = deque([seed_point])
        visited[seed_point[1], seed_point[0]] = True

        # 8-connectivity directions
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]

        while queue:
            x, y = queue.popleft()
            color = image[y, x].astype(np.float32)

            if self._color_distance(color, mean_color) <= tolerance:
                # adapt mean color smoothly
                alpha = 0.005
                mean_color = mean_color * (1 - alpha) + color * alpha
                mask[y, x] = 255

                for dx, dy in dirs:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
                        visited[ny, nx] = True
                        queue.append((nx, ny))

        # morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        return mask

    def _mask_to_polygon(self, mask: np.ndarray, simplify_percent: float) -> np.ndarray:
        """
        convert binary mask to polygon contour

        simplify_percent: simplification as percentage of perimeter (scale-independent)
        """
        # additional morphological cleanup
        kernel_large = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        clean = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_large)
        kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        clean = cv2.morphologyEx(clean, cv2.MORPH_OPEN, kernel_small)

        # find contours
        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        if not contours:
            logger.warning("no contours found")
            return np.array([])

        # filter by aspect ratio
        valid_contours = self._filter_receipt_contours(contours)

        # largest valid contour
        best_contour = max(valid_contours, key=cv2.contourArea)

        # polygon approximation with relative epsilon (percentage of perimeter)
        peri = cv2.arcLength(best_contour, True)
        epsilon = (simplify_percent / 100.0) * peri
        approx = cv2.approxPolyDP(best_contour, epsilon, True)

        logger.debug(
            "polygon simplified",
            original_points=len(best_contour),
            simplified_points=len(approx),
            epsilon=round(epsilon, 2),
        )

        # filter sharp angles
        approx = self._filter_sharp_angles(approx, min_angle_deg=15)

        # if contour is too broken, use minAreaRect
        if len(approx) < 4 or len(approx) > 8:
            logger.debug("contour shape unusual, using minAreaRect", points=len(approx))
            rect = cv2.minAreaRect(best_contour)
            box = cv2.boxPoints(rect)
            approx = box.astype(np.int32).reshape(-1, 1, 2)

        return approx.squeeze()

    @staticmethod
    def _filter_receipt_contours(contours: list) -> list:
        """
        filter contours by receipt-like aspect ratio

        receipts are typically vertical rectangles with aspect ratio 1.2:1 to 5:1
        """
        filtered = []

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)

            if w == 0:
                continue

            aspect = h / w

            # receipts are usually taller than wide
            if 1.0 < aspect < 6.0:
                filtered.append(cnt)

        # fallback to all contours if filtering removes everything
        return filtered if filtered else contours

    def _ensure_receipt_shape(self, polygon: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        ensure polygon represents a receipt-like shape
        if not, fall back to minAreaRect of the entire mask
        """
        if len(polygon) < 4:
            logger.debug("polygon has less than 4 points, using mask bounding rect")
            # find all non-zero points in mask
            points = cv2.findNonZero(mask)
            if points is not None:
                rect = cv2.minAreaRect(points)
                box = cv2.boxPoints(rect)
                return box.astype(np.float32)

        return polygon

    @staticmethod
    def _filter_sharp_angles(polygon: np.ndarray, min_angle_deg: float) -> np.ndarray:
        """filter out points with sharp angles (likely noise)"""
        filtered = []
        pts = polygon.squeeze()

        if len(pts.shape) == 1:
            return polygon

        for i in range(len(pts)):
            angle = AlignerService._compute_angle_at_point(pts, i)
            if angle < 0:
                angle += 360

            # skip sharp angles
            if min_angle_deg < angle < (360 - min_angle_deg):
                filtered.append(pts[i])

        if len(filtered) < 4:
            # too aggressive filtering, return original
            return polygon

        return np.array(filtered, dtype=np.float32)

    def _warp_perspective(self, image: np.ndarray, corners: np.ndarray) -> np.ndarray:
        """
        apply perspective transformation to straighten image

        orders corners as TL, TR, BR, BL for warp
        """
        # order corners: top-left, top-right, bottom-right, bottom-left
        ordered = self._order_corners(corners)

        # calculate output dimensions from real side lengths
        width_a = np.linalg.norm(ordered[1] - ordered[0])
        width_b = np.linalg.norm(ordered[2] - ordered[3])
        max_width = max(width_a, width_b)

        height_a = np.linalg.norm(ordered[3] - ordered[0])
        height_b = np.linalg.norm(ordered[2] - ordered[1])
        max_height = max(height_a, height_b)

        # scale up slightly for ocr (better resolution)
        scale = 1.5
        max_width = max(64, int(max_width * scale))
        max_height = max(64, int(max_height * scale))

        # destination points for rectangle
        dst = np.array(
            [
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1],
            ],
            dtype=np.float32,
        )

        # perspective transform matrix
        matrix = cv2.getPerspectiveTransform(ordered, dst)
        warped = cv2.warpPerspective(
            image,
            matrix,
            (max_width, max_height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

        return warped

    @staticmethod
    def _order_corners(pts: np.ndarray) -> np.ndarray:
        """
        order 4 corners as: top-left, top-right, bottom-right, bottom-left

        improved detection: uses both geometric position and side length analysis
        """
        # sort by y coordinate to get top 2 and bottom 2 points
        sorted_by_y = pts[np.argsort(pts[:, 1])]

        # top two points (smaller y)
        top_points = sorted_by_y[:2]
        # bottom two points (larger y)
        bottom_points = sorted_by_y[2:]

        # sort top points by x: left is smaller x, right is larger x
        top_points = top_points[np.argsort(top_points[:, 0])]
        tl, tr = top_points[0], top_points[1]

        # sort bottom points by x: left is smaller x, right is larger x
        bottom_points = bottom_points[np.argsort(bottom_points[:, 0])]
        bl, br = bottom_points[0], bottom_points[1]

        # calculate dimensions to check if we need rotation
        width = np.linalg.norm(tr - tl)
        height = np.linalg.norm(bl - tl)

        # if width > height significantly, the receipt is horizontal
        # rotate 90 degrees by swapping corners
        if width > height * 1.3:  # increased threshold from 1.2 to 1.3 for stability
            logger.debug(
                "receipt appears horizontal, rotating corner order",
                width=round(width, 1),
                height=round(height, 1),
            )
            # rotate corners 90 degrees clockwise: TL->TR, TR->BR, BR->BL, BL->TL
            return np.array([bl, tl, tr, br], dtype=np.float32)
        else:
            logger.debug(
                "receipt appears vertical, using standard order",
                width=round(width, 1),
                height=round(height, 1),
            )
            return np.array([tl, tr, br, bl], dtype=np.float32)

    @staticmethod
    def _preprocess_for_ocr(image: np.ndarray, aggressive: bool) -> np.ndarray:
        """
        preprocessing for ocr - critical function

        problem: aggressive binarization kills thin lines
        solution: parametrized hardness + detail preservation

        aggressive=True: sharp edges, may lose details (for high quality images)
        aggressive=False: gentle mode, preserves thin strokes (default)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        if aggressive:
            # aggressive mode - sharp boundaries
            thresh = cv2.adaptiveThreshold(
                blurred,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,  # large block
                10,  # high offset
            )
            # morphology cleanup
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        else:
            # gentle mode (default) - preserve details
            thresh = cv2.adaptiveThreshold(
                blurred,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                15,  # smaller block -> fewer artifacts
                5,  # smaller offset -> more preserved
            )
            # minimal morphology - only remove single pixels
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # normalize for stability
        result = thresh.copy()
        cv2.normalize(thresh, result, 0, 255, cv2.NORM_MINMAX)

        return result

    @staticmethod
    def _get_samples(image: np.ndarray, center: tuple[int, int], radius: int) -> np.ndarray:
        """get color samples around center point"""
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
        """euclidean distance in BGR color space"""
        diff = a - b
        return float(np.sqrt(np.sum(diff * diff)))

    def _compute_auto_tolerance(self, samples: np.ndarray, mean_color: np.ndarray) -> float:
        """
        compute adaptive tolerance for flood fill

        based on:
        - local color variance (higher variance = higher tolerance)
        - brightness (darker images = higher tolerance)
        """
        # calculate variance
        variance = np.mean([self._color_distance(s, mean_color) for s in samples])

        # brightness (weighted RGB to perceived luminance)
        brightness = mean_color[2] * 0.299 + mean_color[1] * 0.587 + mean_color[0] * 0.114

        # auto tolerance formula
        tolerance = 13 + (255 - brightness) * 0.7 + variance * 0.7

        # clamp to reasonable range
        return float(np.clip(tolerance, 10, 65))

    @staticmethod
    def _compute_angle_at_point(pts: np.ndarray, index: int) -> float:
        """compute angle at point between previous and next points"""
        prev = pts[(index - 1) % len(pts)]
        curr = pts[index]
        next_pt = pts[(index + 1) % len(pts)]

        angle = abs(
            np.degrees(
                np.arctan2(next_pt[1] - curr[1], next_pt[0] - curr[0])
                - np.arctan2(prev[1] - curr[1], prev[0] - curr[0])
            )
        )
        return angle

    @staticmethod
    def shutdown():
        """cleanup resources"""
        logger.info("shutting down aligner service")

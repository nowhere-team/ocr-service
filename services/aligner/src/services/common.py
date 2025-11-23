import cv2
import numpy as np

from ..logger import get_logger

logger = get_logger(__name__)


def handle_dark_receipt(image: np.ndarray) -> tuple[bool, np.ndarray]:
    """detect and invert dark receipts"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)

    if mean_brightness < 100:
        logger.debug("detected dark receipt, inverting", brightness=mean_brightness)
        return True, 255 - image

    return False, image


def preprocess_illumination(image: np.ndarray) -> np.ndarray:
    """shared preprocessing - illumination equalization using clahe"""
    blurred = cv2.GaussianBlur(image, (5, 5), 0)
    lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)

    lab = cv2.merge([l_channel, a_channel, b_channel])
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    return cv2.addWeighted(result, 1.2, np.zeros_like(result), 0, 0)


def order_corners(pts: np.ndarray) -> np.ndarray:
    """
    order corners: top-left, top-right, bottom-right, bottom-left
    """
    sorted_by_y = pts[np.argsort(pts[:, 1])]
    top_points = sorted_by_y[:2]
    bottom_points = sorted_by_y[2:]

    top_points = top_points[np.argsort(top_points[:, 0])]
    tl, tr = top_points[0], top_points[1]

    bottom_points = bottom_points[np.argsort(bottom_points[:, 0])]
    bl, br = bottom_points[0], bottom_points[1]

    logger.debug(
        "corners ordered",
        tl=tl.tolist(),
        tr=tr.tolist(),
        br=br.tolist(),
        bl=bl.tolist(),
    )

    return np.array([tl, tr, br, bl], dtype=np.float32)


def warp_perspective(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """apply perspective transformation to straighten document"""
    ordered = corners

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


def preprocess_for_ocr(image: np.ndarray, aggressive: bool) -> np.ndarray:
    """prepare image for ocr recognition"""
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

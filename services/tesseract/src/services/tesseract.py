import time
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image

from ..config import settings
from ..logger import get_logger
from ..models import OCRResult
from ..observability.telemetry import get_tracer

logger = get_logger(__name__)
tracer = get_tracer(__name__)


class TesseractService:
    """
    ocr service using tesseract

    wrapper around pytesseract with preprocessing and confidence calculation
    supports multiple languages and various page segmentation modes
    """

    def __init__(self):
        """initialize tesseract service"""
        # configure tesseract path if provided
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

        # configure tessdata directory if provided
        if settings.tessdata_dir:
            tessdata_path = Path(settings.tessdata_dir)
            if not tessdata_path.exists():
                logger.warning("tessdata directory not found", path=str(tessdata_path))

        # verify tesseract is available
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(
                "tesseract initialized",
                version=str(version),
                default_lang=settings.default_lang,
                psm=settings.psm,
                oem=settings.oem,
            )
        except Exception as e:
            logger.error("failed to initialize tesseract", error=str(e))
            raise RuntimeError(f"tesseract not available: {e}") from e

    @staticmethod
    async def recognize(
        image_array: np.ndarray,
        lang: str | None = None,
    ) -> OCRResult:
        """
        recognize text from image

        args:
            image_array: input image as numpy array
            lang: language code(s), e.g. 'rus', 'eng', 'rus+eng'
                  if None, uses default from settings

        returns:
            OCRResult with text and confidence
        """
        start_time = time.time()

        language = lang or settings.default_lang

        with tracer.start_as_current_span("tesseract_service.recognize") as span:
            span.set_attribute("image.shape", str(image_array.shape))
            span.set_attribute("ocr.language", language)
            span.set_attribute("ocr.psm", settings.psm)

            try:
                # convert numpy array to PIL Image for pytesseract
                # tesseract works better с grayscale
                if len(image_array.shape) == 3:
                    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
                else:
                    gray = image_array

                pil_image = Image.fromarray(gray)

                # configure tesseract
                config = f"--psm {settings.psm} --oem {settings.oem}"

                # get detailed data with confidence scores
                data = pytesseract.image_to_data(
                    pil_image,
                    lang=language,
                    config=config,
                    output_type=pytesseract.Output.DICT,
                )

                # extract text and calculate average confidence
                text_parts = []
                confidences = []

                for i, conf in enumerate(data["conf"]):
                    # pytesseract returns -1 for empty blocks
                    if conf > 0:
                        text = data["text"][i].strip()
                        if text:
                            text_parts.append(text)
                            confidences.append(float(conf))

                # join text with spaces (pytesseract breaks words)
                full_text = " ".join(text_parts)

                # calculate average confidence
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                avg_confidence = avg_confidence / 100.0

                duration = (time.time() - start_time) * 1000
                span.set_attribute("processing.duration_ms", duration)
                span.set_attribute("ocr.text_length", len(full_text))
                span.set_attribute("ocr.confidence", avg_confidence)

                logger.info(
                    "recognition completed",
                    text_length=len(full_text),
                    confidence=round(avg_confidence, 3),
                    duration_ms=round(duration, 2),
                    language=language,
                )

                return OCRResult(
                    text=full_text,
                    confidence=avg_confidence,  # 0.0-1.0
                )
            except Exception as e:
                logger.error("recognition failed", error=str(e), exc_info=True)
                raise RuntimeError(f"tesseract recognition failed: {e}") from e

    @staticmethod
    def shutdown():
        """cleanup resources"""
        logger.info("shutting down tesseract service")

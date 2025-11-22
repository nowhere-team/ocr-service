import asyncio
import time

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ...config import settings
from ...dependencies import TesseractServiceDep
from ...logger import get_logger
from ...models import OCRResult
from ...observability.metrics import (
    active_recognitions,
    record_duration,
    record_error,
    record_image_size,
    record_request,
)
from ...observability.telemetry import get_tracer

logger = get_logger(__name__)
tracer = get_tracer(__name__)

router = APIRouter(prefix="/api/v1", tags=["ocr"])


@router.post("/recognize", response_model=OCRResult)
async def recognize_text(
    image: UploadFile = File(...),
    lang: str = Query(
        default=settings.default_lang,
        description="language code(s) for ocr, e.g. 'rus', 'eng', 'rus+eng'",
    ),
    tesseract_deps: TesseractServiceDep = None,
):
    """
    recognize text from uploaded image using tesseract

    accepts: image files (jpg, png, etc.)
    returns: recognized text with confidence score

    parameters:
    - lang: language(s) for recognition (use '+' for multiple, e.g. 'rus+eng')
    """
    tesseract_service, _ = tesseract_deps
    start_time = time.time()
    active_recognitions.inc()

    try:
        # read and validate file
        contents = await image.read()
        file_size = len(contents)

        if file_size > settings.max_image_size:
            logger.warning("image too large", size=file_size, max=settings.max_image_size)
            record_error("image_too_large")
            raise HTTPException(
                status_code=413,
                detail=f"image too large: {file_size} bytes (max {settings.max_image_size})",
            )

        record_image_size(file_size)

        # decode image
        try:
            nparr = np.frombuffer(contents, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("failed to decode image")
        except Exception as e:
            logger.error("failed to decode image", error=str(e))
            record_error("image_decode_error")
            raise HTTPException(status_code=400, detail=f"invalid image format: {str(e)}") from None

        # run ocr recognition
        with tracer.start_as_current_span("api.recognize") as span:
            span.set_attribute("image.size_bytes", file_size)
            span.set_attribute("image.width", img.shape[1])
            span.set_attribute("image.height", img.shape[0])
            span.set_attribute("ocr.language", lang)

            try:
                result = await asyncio.wait_for(
                    tesseract_service.recognize(img, lang=lang),
                    timeout=settings.processing_timeout,
                )
            except TimeoutError:
                logger.error("ocr processing timeout", timeout=settings.processing_timeout)
                record_error("timeout")
                raise HTTPException(status_code=504, detail="processing timeout") from None
            except Exception as e:
                logger.error("ocr processing failed", error=str(e))
                record_error("ocr_error")
                raise HTTPException(
                    status_code=500, detail=f"ocr processing failed: {str(e)}"
                ) from e

            span.set_attribute("ocr.text_length", len(result.text))
            span.set_attribute("ocr.confidence", result.confidence)

        processing_time = (time.time() - start_time) * 1000

        record_duration(processing_time / 1000)
        record_request("success")

        logger.info(
            "recognition completed",
            file_size=file_size,
            text_length=len(result.text),
            confidence=round(result.confidence, 2),
            processing_time_ms=round(processing_time, 2),
            language=lang,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("unexpected error in recognize endpoint", error=str(e), exc_info=True)
        record_error("unexpected")
        raise HTTPException(status_code=500, detail="internal server error") from e
    finally:
        active_recognitions.dec()

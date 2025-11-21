import asyncio
import io
import time

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image

from ...config import settings
from ...dependencies import OCRServiceDep
from ...logger import get_logger
from ...models.ocr import RecognitionResponse, TextBlock
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


# noinspection PyTypeHints
@router.post("/recognize", response_model=RecognitionResponse)
async def recognize_text(
    file: UploadFile = File(...),
    ocr_deps: OCRServiceDep = None,
):
    """
    recognize text from uploaded image

    - accepts: image files (jpg, png, etc.)
    - returns: recognized text with confidence scores and bounding boxes
    """
    ocr_service, _ = ocr_deps
    start_time = time.time()
    active_recognitions.inc()

    try:
        # read and validate file
        contents = await file.read()
        file_size = len(contents)

        if file_size > settings.max_image_size:
            logger.warning("image too large", size=file_size, max=settings.max_image_size)
            record_error("image_too_large")
            raise HTTPException(
                status_code=413,
                detail=f"image too large: {file_size} bytes (max {settings.max_image_size})",
            )

        record_image_size(file_size)

        # parse image
        try:
            image = Image.open(io.BytesIO(contents))

            # convert to rgb if needed
            if image.mode != "RGB":
                logger.debug("converting image to rgb", original_mode=image.mode)
                image = image.convert("RGB")

            image_array = np.array(image)
        except Exception as e:
            logger.error("failed to parse image", error=str(e))
            record_error("image_parse_error")
            raise HTTPException(status_code=400, detail=f"invalid image format: {str(e)}") from None

        # run ocr recognition
        with tracer.start_as_current_span("api.recognize") as span:
            span.set_attribute("image.size_bytes", file_size)
            span.set_attribute("image.width", image.width)
            span.set_attribute("image.height", image.height)

            try:
                results = await asyncio.wait_for(
                    ocr_service.recognize(image_array),
                    timeout=settings.processing_timeout,
                )
            except TimeoutError:
                logger.error("ocr processing timeout", timeout=settings.processing_timeout)
                record_error("timeout")
                raise HTTPException(
                    status_code=504, detail="processing timeout"
                ) from None  # no need timeout
            except Exception as e:
                logger.error("ocr processing failed", error=str(e))
                record_error("ocr_error")
                raise HTTPException(
                    status_code=500, detail=f"ocr processing failed: {str(e)}"
                ) from e

            # parse paddleocr results
            blocks = []
            all_text = []
            all_confidence = []

            for result in results:
                res = result.json.get("res", {})
                rec_texts = res.get("rec_texts", [])
                rec_scores = res.get("rec_scores", [])
                dt_polys = res.get("dt_polys", [])

                for i, text in enumerate(rec_texts):
                    confidence = float(rec_scores[i]) if i < len(rec_scores) else 0.0
                    bbox = dt_polys[i] if i < len(dt_polys) else []

                    blocks.append(TextBlock(text=text, confidence=confidence, bbox=bbox))
                    all_text.append(text)
                    all_confidence.append(confidence)

            avg_confidence = sum(all_confidence) / len(all_confidence) if all_confidence else 0.0

            span.set_attribute("ocr.blocks_count", len(blocks))
            span.set_attribute("ocr.avg_confidence", avg_confidence)

        processing_time = (time.time() - start_time) * 1000

        record_duration(processing_time / 1000)
        record_request("success")

        logger.info(
            "recognition completed",
            file_size=file_size,
            blocks_count=len(blocks),
            confidence=round(avg_confidence, 3),
            processing_time_ms=round(processing_time, 2),
        )

        return RecognitionResponse(
            text="\n".join(all_text),
            confidence=avg_confidence,
            blocks=blocks,
            processing_time_ms=round(processing_time, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("unexpected error in recognize endpoint", error=str(e), exc_info=True)
        record_error("unexpected")
        raise HTTPException(status_code=500, detail="internal server error") from e
    finally:
        active_recognitions.dec()

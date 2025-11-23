import asyncio
import base64
import json
import time

import cv2
import numpy as np
import redis.asyncio as redis
from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile

from ...config import settings
from ...dependencies import AlignerServiceDep
from ...logger import get_logger
from ...models import AlignmentConfig
from ...observability.metrics import (
    active_alignments,
    record_duration,
    record_error,
    record_image_size,
    record_request,
)
from ...observability.telemetry import get_tracer
from ...platform.storage import get_storage_client

logger = get_logger(__name__)
tracer = get_tracer(__name__)

router = APIRouter(prefix="/api/v1", tags=["aligner"])


@router.post("/align")
async def align_image(
    image: UploadFile = File(...),
    mode: str = Query(
        default="classic",
        description="alignment mode: 'classic' for opencv or 'neural' for docaligner",
    ),
    aggressive: bool = Query(
        default=False,
        description="aggressive preprocessing mode (sharp edges, may lose thin details)",
    ),
    apply_ocr_prep: bool = Query(
        default=False, description="apply ocr binarization after alignment"
    ),
    simplify_percent: float = Query(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="polygon simplification as % of perimeter (scale-independent, classic mode only)",
    ),
    debug_mode: bool = Query(
        default=False, description="enable debug mode with intermediate image saves"
    ),
    recognition_id: str = Query(
        default="", description="recognition id for tracking (required if debug_mode=true)"
    ),
    image_id: str = Query(default="", description="image id for tracking"),
    aligner_deps: AlignerServiceDep = None,
):
    aligner_service, _ = aligner_deps
    start_time = time.time()
    active_alignments.inc()

    logger.info(f"aligner service running: {mode}")

    if mode not in ["classic", "neural"]:
        return Response(
            content=f"invalid mode: {mode}. must be 'classic' or 'neural'", status_code=400
        )

    debug_callback = None
    redis_client = None
    storage_client = None

    if debug_mode:
        if not recognition_id:
            logger.warning("debug mode requested without recognition_id")
            return Response(content="recognition_id required when debug_mode=true", status_code=400)

        try:
            redis_client = await redis.from_url(settings.redis_url, decode_responses=False)
            logger.debug("connected to redis for debug events")
        except Exception as e:
            logger.warning("failed to connect to redis for debug", error=str(e))

        try:
            storage_client = get_storage_client()
            logger.debug("got storage client for debug images")
        except Exception as e:
            logger.warning("failed to get storage client for debug", error=str(e))

        async def debug_callback_func(step: str, step_num: int, img: np.ndarray, metadata: dict):
            if not redis_client or not storage_client:
                return

            try:
                is_success, encoded_buffer = cv2.imencode(".jpg", img)
                if not is_success:
                    logger.warning("failed to encode debug image", step=step)
                    return

                image_key = f"debug/{recognition_id}/{step_num:02d}_{step}.jpg"
                storage_url = storage_client.put_object(image_key, encoded_buffer.tobytes())

                if not storage_url:
                    logger.warning("failed to upload debug image", step=step)
                    return

                event_data = {
                    "event": "aligner.debug.step",
                    "recognitionId": recognition_id,
                    "imageId": image_id or "",
                    "step": step,
                    "stepNumber": step_num,
                    "imageKey": image_key,
                    "description": metadata.get("description", step),
                    "metadata": {k: v for k, v in metadata.items() if k != "description"},
                    "timestamp": time.time() * 1000,  # milliseconds for consistency with typescript
                }

                await redis_client.publish("ocr:events", json.dumps(event_data))
                logger.debug(
                    "published debug event", step=step, recognition_id=recognition_id, key=image_key
                )
            except Exception as e:
                logger.error("failed to process debug step", error=str(e), step=step)

        debug_callback = debug_callback_func

    try:
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

        try:
            nparr = np.frombuffer(contents, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("failed to decode image")
        except Exception as e:
            logger.error("failed to decode image", error=str(e))
            record_error("image_decode_error")
            raise HTTPException(status_code=400, detail=f"invalid image format: {str(e)}") from None

        with tracer.start_as_current_span("api.align") as span:
            span.set_attribute("image.size_bytes", file_size)
            span.set_attribute("image.width", img.shape[1])
            span.set_attribute("image.height", img.shape[0])
            span.set_attribute("config.mode", mode)
            span.set_attribute("preprocessing.aggressive", aggressive)
            span.set_attribute("preprocessing.apply_ocr_prep", apply_ocr_prep)
            span.set_attribute("debug.enabled", debug_mode)

            try:
                config = AlignmentConfig(
                    mode=mode,
                    simplify_percent=simplify_percent,
                    apply_ocr_preprocessing=apply_ocr_prep,
                    aggressive=aggressive,
                    debug_mode=debug_mode,
                    recognition_id=recognition_id,
                )

                warped, preprocessed = await asyncio.wait_for(
                    aligner_service.align(img, config, debug_callback),
                    timeout=settings.processing_timeout,
                )
            except TimeoutError:
                logger.error("alignment timeout", timeout=settings.processing_timeout)
                record_error("timeout")
                raise HTTPException(status_code=504, detail="processing timeout") from None
            except Exception as e:
                logger.error("alignment processing failed", error=str(e))
                record_error("alignment_error")
                raise HTTPException(
                    status_code=500, detail=f"alignment processing failed: {str(e)}"
                ) from e

            success_warped, buffer_warped = cv2.imencode(".jpg", warped)
            if not success_warped:
                raise Exception("failed to encode warped image")

            success_prep, buffer_prep = cv2.imencode(".jpg", preprocessed)
            if not success_prep:
                raise Exception("failed to encode preprocessed image")

            warped_bytes = buffer_warped.tobytes()
            preprocessed_bytes = buffer_prep.tobytes()

            span.set_attribute("output.warped_size_bytes", len(warped_bytes))
            span.set_attribute("output.preprocessed_size_bytes", len(preprocessed_bytes))

        processing_time = (time.time() - start_time) * 1000

        record_duration(processing_time / 1000)
        record_request("success")

        logger.info(
            "alignment completed",
            mode=mode,
            file_size=file_size,
            warped_size=len(warped_bytes),
            preprocessed_size=len(preprocessed_bytes),
            processing_time_ms=round(processing_time, 2),
            debug_mode=debug_mode,
        )

        response_data = {
            "warped": base64.b64encode(warped_bytes).decode("utf-8"),
            "preprocessed": base64.b64encode(preprocessed_bytes).decode("utf-8"),
        }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error("unexpected error in align endpoint", error=str(e), exc_info=True)
        record_error("unexpected")
        raise HTTPException(status_code=500, detail="internal server error") from e
    finally:
        active_alignments.dec()
        if redis_client:
            await redis_client.close()

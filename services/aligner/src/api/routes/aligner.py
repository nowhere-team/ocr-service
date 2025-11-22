import asyncio
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


# noinspection PyTypeHints
@router.post("/align")
async def align_image(
    image: UploadFile = File(...),
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
        description="polygon simplification as % of perimeter (scale-independent)",
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
    """
    perspective alignment for receipt images

    accepts: image files (jpg, png, etc.)
    returns: aligned image as jpeg

    parameters:
    - aggressive: use aggressive binarization (for high quality images)
    - apply_ocr_prep: apply ocr preprocessing after alignment
    - simplify_percent: polygon simplification as percentage (scale-independent, default 2%)
    - debug_mode: save intermediate images and publish events
    - recognition_id: tracking id for debug
    - image_id: image id for debug events
    """
    aligner_service, _ = aligner_deps
    start_time = time.time()
    active_alignments.inc()

    # setup debug infrastructure
    debug_callback = None
    redis_client = None
    storage_client = None

    if debug_mode:
        if not recognition_id:
            logger.warning("debug mode requested without recognition_id")
            return Response(content="recognition_id required when debug_mode=true", status_code=400)

        # connect to redis
        try:
            redis_client = await redis.from_url(settings.redis_url, decode_responses=False)
            logger.debug("connected to redis for debug events")
        except Exception as e:
            logger.warning("failed to connect to redis for debug", error=str(e))

        # get storage client
        try:
            storage_client = get_storage_client()
            logger.debug("got storage client for debug images")
        except Exception as e:
            logger.warning("failed to get storage client for debug", error=str(e))

        # create debug callback
        async def debug_callback_func(step: str, step_num: int, img: np.ndarray, metadata: dict):
            """save debug image and publish event"""
            if not redis_client or not storage_client:
                return

            try:
                # encode image to jpg
                is_success, encoded_buffer = cv2.imencode(".jpg", img)
                if not is_success:
                    logger.warning("failed to encode debug image", step=step)
                    return

                # save to minio
                image_key = f"debug/{recognition_id}/{step_num:02d}_{step}.jpg"
                storage_url = storage_client.put_object(image_key, encoded_buffer.tobytes())

                if not storage_url:
                    logger.warning("failed to upload debug image", step=step)
                    return

                # publish event
                event_data = {
                    "event": "aligner.debug.step",
                    "recognitionId": recognition_id,
                    "imageId": image_id or "",
                    "step": step,
                    "stepNumber": step_num,
                    "imageKey": image_key,
                    "description": metadata.get("description", step),
                    "metadata": {k: v for k, v in metadata.items() if k != "description"},
                    "timestamp": time.time(),
                }

                await redis_client.publish("ocr:events", json.dumps(event_data))
                logger.debug(
                    "published debug event", step=step, recognition_id=recognition_id, key=image_key
                )
            except Exception as e:
                logger.error("failed to process debug step", error=str(e), step=step)

        debug_callback = debug_callback_func

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

        # run alignment
        with tracer.start_as_current_span("api.align") as span:
            span.set_attribute("image.size_bytes", file_size)
            span.set_attribute("image.width", img.shape[1])
            span.set_attribute("image.height", img.shape[0])
            span.set_attribute("preprocessing.aggressive", aggressive)
            span.set_attribute("preprocessing.apply_ocr_prep", apply_ocr_prep)
            span.set_attribute("debug.enabled", debug_mode)

            try:
                config = AlignmentConfig(
                    simplify_percent=simplify_percent,
                    apply_ocr_preprocessing=apply_ocr_prep,
                    aggressive=aggressive,
                    debug_mode=debug_mode,
                    recognition_id=recognition_id,
                )

                aligned = await asyncio.wait_for(
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

            # encode to jpeg
            success, buffer = cv2.imencode(".jpg", aligned)
            if not success:
                raise Exception("failed to encode result image")

            result_bytes = buffer.tobytes()
            span.set_attribute("output.size_bytes", len(result_bytes))

        processing_time = (time.time() - start_time) * 1000

        record_duration(processing_time / 1000)
        record_request("success")

        logger.info(
            "alignment completed",
            file_size=file_size,
            result_size=len(result_bytes),
            processing_time_ms=round(processing_time, 2),
            debug_mode=debug_mode,
        )

        return Response(
            content=result_bytes,
            media_type="image/jpeg",
            headers={"Content-Disposition": "inline; filename=aligned.jpg"},
        )

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

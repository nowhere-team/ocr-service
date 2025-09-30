"""
Health check handlers
"""
from fastapi import APIRouter, Depends

from app.models.responses import HealthResponse
from app.services.ocr_service import OCRService
from app.api.dependencies import get_ocr_service
from app.config import get_settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
@router.get("/", response_model=HealthResponse, include_in_schema=False)
async def health_check(
    ocr_service: OCRService = Depends(get_ocr_service)
) -> HealthResponse:
    """
    Базовый health check
    Проверяет что сервис запущен и OCR движок доступен
    """
    settings = get_settings()
    
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        ocr_engine_available=ocr_service.is_ready()
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness_check(
    ocr_service: OCRService = Depends(get_ocr_service)
) -> HealthResponse:
    """
    Readiness check для Kubernetes
    Проверяет что сервис готов принимать запросы
    """
    settings = get_settings()
    is_ready = ocr_service.is_ready()
    
    return HealthResponse(
        status="ready" if is_ready else "not_ready",
        version=settings.APP_VERSION,
        ocr_engine_available=is_ready
    )

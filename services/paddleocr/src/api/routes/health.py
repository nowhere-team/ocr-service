from fastapi import APIRouter, HTTPException

from ...config import settings
from ...observability.metrics import metrics_endpoint

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """health check endpoint"""
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": "0.1.0",
    }


@router.get("/metrics")
async def metrics():
    """prometheus metrics endpoint"""
    if not settings.enable_metrics:
        raise HTTPException(status_code=404, detail="metrics disabled")
    return metrics_endpoint()

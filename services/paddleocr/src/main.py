from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import health, ocr
from .dependencies import OCRServiceDependency
from .logger import configure_logging, get_logger
from .observability.telemetry import configure_telemetry, instrument_app

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """application lifecycle manager"""
    logger.info("starting paddleocr service")

    # startup
    configure_telemetry()
    OCRServiceDependency.get_instance()

    logger.info("service ready")

    yield

    # shutdown
    logger.info("shutting down service")
    OCRServiceDependency.shutdown()
    logger.info("service stopped")


app = FastAPI(
    title="PaddleOCR Service",
    description="OCR recognition service using PaddleOCR with observability",
    version="0.1.0",
    lifespan=lifespan,
)

instrument_app(app)

app.include_router(health.router)
app.include_router(ocr.router)

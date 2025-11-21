from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import aligner, health
from .dependencies import AlignerServiceDependency
from .logger import configure_logging, get_logger
from .observability.telemetry import configure_telemetry, instrument_app

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """application lifecycle manager"""
    logger.info("starting aligner service")

    # startup
    configure_telemetry()
    AlignerServiceDependency.get_instance()

    logger.info("service ready")

    yield

    # shutdown
    logger.info("shutting down service")
    AlignerServiceDependency.shutdown()
    logger.info("service stopped")


app = FastAPI(
    title="Aligner Service",
    description="perspective alignment service for receipt images with observability",
    version="0.1.0",
    lifespan=lifespan,
)

instrument_app(app)

app.include_router(health.router)
app.include_router(aligner.router)

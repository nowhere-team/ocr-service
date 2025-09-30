"""
FastAPI приложение - точка входа OCR сервиса
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.api.v1.router import api_router

# Настройка логирования при импорте
settings = get_settings()
setup_logging(log_level=settings.LOG_LEVEL, is_debug=settings.DEBUG)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle events для FastAPI
    Выполняется при старте и остановке приложения
    """
    # Startup
    logger.info(
        "Starting OCR Service",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down OCR Service")


# Создаём FastAPI приложение
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="OCR Service for receipt recognition - ChopCheck microservice",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root():
    """Редирект с корня на документацию"""
    return RedirectResponse(url="/docs")


@app.get("/ping", include_in_schema=False)
async def ping():
    """Простой ping endpoint"""
    return {"status": "pong"}


if __name__ == "__main__":
    import uvicorn
    
    logger.info(
        "Starting server",
        host=settings.HOST,
        port=settings.PORT
    )
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )

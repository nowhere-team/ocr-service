"""
Главный роутер API v1
Объединяет все handlers
"""
from fastapi import APIRouter

from app.api.v1.handlers import ocr_handler, health_handler

# Создаём главный роутер для v1
api_router = APIRouter(prefix="/api/v1")

# Подключаем все handlers
api_router.include_router(ocr_handler.router)
api_router.include_router(health_handler.router)

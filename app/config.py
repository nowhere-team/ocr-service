"""
Конфигурация приложения через Pydantic Settings
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения"""
    
    # Application Settings
    APP_NAME: str = "ocr-service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS Settings
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    # EasyOCR Settings
    EASYOCR_LANGUAGES: str = "ru,en"
    EASYOCR_USE_GPU: bool = False

    @property
    def easyocr_languages_list(self) -> List[str]:
        """Парсинг языков EasyOCR из строки в список"""
        return [lang.strip() for lang in self.EASYOCR_LANGUAGES.split(",")]

    # Image Settings
    MAX_IMAGE_SIZE_MB: int = 10
    ALLOWED_IMAGE_FORMATS: str = "jpg,jpeg,png,webp"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    @property
    def allowed_origins_list(self) -> List[str]:
        """Парсинг CORS origins из строки в список"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def allowed_image_formats_list(self) -> List[str]:
        """Парсинг форматов изображений из строки в список"""
        return [fmt.strip() for fmt in self.ALLOWED_IMAGE_FORMATS.split(",")]


# Singleton instance
_settings: Settings = None


def get_settings() -> Settings:
    """Получить настройки (singleton)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """application settings with environment variables support"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # server
    host: str = Field(default="0.0.0.0", description="host to bind")
    port: int = Field(default=8000, ge=1, le=65535, description="port to bind")
    workers: int = Field(default=2, ge=1, description="number of thread pool workers")

    # tesseract config
    tesseract_cmd: str = Field(default="tesseract", description="path to tesseract executable")
    default_lang: str = Field(
        default="rus+eng", description="default language for ocr (can use + for multiple)"
    )
    tessdata_dir: str | None = Field(
        default=None, description="path to tessdata directory (auto-detected if None)"
    )

    # ocr settings
    psm: int = Field(default=3, ge=0, le=13, description="page segmentation mode (3 = automatic)")
    oem: int = Field(
        default=3,
        ge=0,
        le=3,
        description="ocr engine mode (3 = default, based on what's available)",
    )

    # processing
    max_image_size: int = Field(
        default=10 * 1024 * 1024, description="max image size in bytes (10mb)"
    )
    processing_timeout: float = Field(default=30.0, description="processing timeout in seconds")

    # logging
    log_level: str = Field(default="INFO", description="logging level")
    log_format: str = Field(default="json", description="log format: json or console")

    # telemetry
    enable_telemetry: bool = Field(default=True, description="enable opentelemetry")
    otlp_endpoint: str = Field(default="http://localhost:4317", description="otlp grpc endpoint")
    service_name: str = Field(default="tesseract-service", description="service name for traces")

    # metrics
    enable_metrics: bool = Field(default=True, description="enable prometheus metrics")


settings = Settings()

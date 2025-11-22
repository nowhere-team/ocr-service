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

    # alignment config
    simplify_percent: float = Field(
        default=2.0, description="polygon simplification as % of perimeter"
    )
    default_aggressive: bool = Field(default=False, description="default aggressive mode")
    default_ocr_prep: bool = Field(default=False, description="apply ocr preprocessing by default")

    # processing
    max_image_size: int = Field(
        default=10 * 1024 * 1024, description="max image size in bytes (10mb)"
    )
    processing_timeout: float = Field(default=30.0, description="processing timeout in seconds")

    # redis for debug events
    redis_url: str = Field(default="redis://localhost:6379", description="redis url for events")

    # minio for debug images
    minio_endpoint: str = Field(default="localhost:9000", description="minio endpoint")
    minio_access_key: str = Field(default="minioadmin", description="minio access key")
    minio_secret_key: str = Field(default="minioadmin", description="minio secret key")
    minio_use_ssl: bool = Field(default=False, description="use ssl for minio")
    minio_bucket: str = Field(default="images", description="minio bucket name")

    # logging
    log_level: str = Field(default="INFO", description="logging level")
    log_format: str = Field(default="json", description="log format: json or console")

    # telemetry
    enable_telemetry: bool = Field(default=True, description="enable opentelemetry")
    otlp_endpoint: str = Field(default="http://localhost:4317", description="otlp grpc endpoint")
    service_name: str = Field(default="aligner-service", description="service name for traces")

    # metrics
    enable_metrics: bool = Field(default=True, description="enable prometheus metrics")


settings = Settings()

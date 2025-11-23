from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """application settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # redis
    redis_url: str = Field(default="redis://localhost:6379", description="redis url")

    # minio
    minio_endpoint: str = Field(default="localhost:9000", description="minio endpoint")
    minio_access_key: str = Field(default="minioadmin", description="minio access key")
    minio_secret_key: str = Field(default="minioadmin", description="minio secret key")
    minio_use_ssl: bool = Field(default=False, description="use ssl for minio")
    minio_bucket: str = Field(default="images", description="minio bucket name")

    # gateway
    gateway_url: str = Field(default="http://localhost:8080", description="ocr gateway url")

    # deepseek
    deepseek_api_key: str = Field(default="", description="deepseek api key")
    deepseek_api_url: str = Field(
        default="https://api.deepseek.com/v1/chat/completions", description="deepseek api url"
    )

    # ui
    page_title: str = Field(default="OCR Pipeline Visualizer", description="page title")
    max_jobs_display: int = Field(default=50, description="max jobs to display in sidebar")
    auto_refresh_interval: int = Field(default=2, description="auto refresh interval in seconds")


settings = Settings()

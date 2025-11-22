import io
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from ..config import settings
from ..logger import get_logger

logger = get_logger(__name__)


class StorageClient:
    """minio storage client for debug images"""

    def __init__(self):
        """initialize minio client"""
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )
        self.bucket = settings.minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self):
        """ensure bucket exists"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("created minio bucket", bucket=self.bucket)
            else:
                logger.debug("minio bucket exists", bucket=self.bucket)
        except S3Error as e:
            logger.error("failed to ensure bucket", error=str(e), bucket=self.bucket)
            raise

    def put_object(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str | None:
        """
        upload object to minio

        args:
            key: object key (path)
            data: object data as bytes
            content_type: mime type

        returns:
            object url or none if failed
        """
        try:
            # noinspection PyTypeChecker
            data_stream = io.BytesIO(data)
            self.client.put_object(
                self.bucket,
                key,
                data_stream,
                length=len(data),
                content_type=content_type,
            )

            url = f"minio://{self.bucket}/{key}"
            logger.debug("uploaded object to minio", key=key, size=len(data))
            return url
        except S3Error as e:
            logger.error("failed to upload to minio", error=str(e), key=key)
            return None

    def get_presigned_url(self, key: str, expiry: int = 3600) -> str | None:
        """get presigned url for object"""
        try:
            url = self.client.presigned_get_object(
                self.bucket, key, expires=timedelta(seconds=expiry)
            )
            return url
        except S3Error as e:
            logger.error("failed to get presigned url", error=str(e), key=key)
            return None


# singleton instance
_storage_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    """get or create storage client singleton"""
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
        logger.info("storage client initialized")
    return _storage_client

import io
from datetime import timedelta

from minio import Minio
from minio.error import S3Error
from PIL import Image

from .config import settings


class StorageClient:
    """minio storage client for loading debug images"""

    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )
        self.bucket = settings.minio_bucket

    def get_presigned_url(self, key: str, expiry: int = 3600) -> str | None:
        """
        get presigned url for object

        args:
            key: object key
            expiry: url expiry in seconds

        returns:
            presigned url or none if failed
        """
        try:
            url = self.client.presigned_get_object(self.bucket, key, expires=timedelta(expiry))
            return url
        except S3Error:
            return None

    def get_image(self, key: str) -> Image.Image | None:
        """
        get image from minio

        args:
            key: object key

        returns:
            PIL image or none if failed
        """
        try:
            response = self.client.get_object(self.bucket, key)
            data = response.read()
            response.close()
            response.release_conn()

            image = Image.open(io.BytesIO(data))
            return image
        except S3Error:
            return None

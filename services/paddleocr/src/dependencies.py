from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import Depends

from .config import settings
from .logger import get_logger

logger = get_logger(__name__)


class OCRServiceDependency:
    """singleton for ocr service and thread pool"""

    _service = None
    _executor = None

    @classmethod
    def get_instance(cls):
        """get or create service instance"""
        if cls._service is None:
            from .services.ocr_service import OCRService

            logger.info("creating ocr service instance")
            cls._service = OCRService()
            cls._executor = ThreadPoolExecutor(max_workers=settings.workers)
            logger.info("ocr service created", workers=settings.workers)

        return cls._service, cls._executor

    @classmethod
    def shutdown(cls):
        """cleanup"""
        if cls._executor:
            logger.info("shutting down thread pool")
            cls._executor.shutdown(wait=True)

        if cls._service:
            logger.info("shutting down ocr service")
            cls._service.shutdown()


def get_ocr_service():
    """dependency injection for fastapi endpoints"""
    service, executor = OCRServiceDependency.get_instance()
    return service, executor


OCRServiceDep = Annotated[tuple, Depends(get_ocr_service)]

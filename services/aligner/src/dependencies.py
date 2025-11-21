from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import Depends

from .config import settings
from .logger import get_logger

logger = get_logger(__name__)


class AlignerServiceDependency:
    """singleton for aligner service and thread pool"""

    _service = None
    _executor = None

    @classmethod
    def get_instance(cls):
        """get or create service instance"""
        if cls._service is None:
            from .services.aligner import AlignerService

            logger.info("creating aligner service instance")
            cls._service = AlignerService()
            cls._executor = ThreadPoolExecutor(max_workers=settings.workers)
            logger.info("aligner service created", workers=settings.workers)

        return cls._service, cls._executor

    @classmethod
    def shutdown(cls):
        """cleanup"""
        if cls._executor:
            logger.info("shutting down thread pool")
            cls._executor.shutdown(wait=True)

        if cls._service:
            logger.info("shutting down aligner service")
            cls._service.shutdown()


def get_aligner_service():
    """dependency injection for fastapi endpoints"""
    service, executor = AlignerServiceDependency.get_instance()
    return service, executor


AlignerServiceDep = Annotated[tuple, Depends(get_aligner_service)]

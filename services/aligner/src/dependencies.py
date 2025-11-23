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
            from .services import HybridAligner

            logger.info("creating hybrid aligner service instance")

            # initialize hybrid aligner with neural support
            # you can configure this via environment variables if needed
            cls._service = HybridAligner(
                enable_neural=True,  # set to False to disable neural mode
                neural_backend="cpu",  # or "cuda" if GPU available
                neural_model_cfg="fastvit_sa24",  # docaligner model config
            )

            cls._executor = ThreadPoolExecutor(max_workers=settings.workers)
            logger.info("hybrid aligner service created", workers=settings.workers)

        return cls._service, cls._executor

    @classmethod
    def shutdown(cls):
        """cleanup"""
        if cls._executor:
            logger.info("shutting down thread pool")
            cls._executor.shutdown(wait=True)

        if cls._service:
            logger.info("shutting down hybrid aligner service")
            cls._service.shutdown()


def get_aligner_service():
    """dependency injection for fastapi endpoints"""
    service, executor = AlignerServiceDependency.get_instance()
    return service, executor


AlignerServiceDep = Annotated[tuple, Depends(get_aligner_service)]

"""
OCR handlers - основные эндпоинты для распознавания чеков
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.requests import OCRRequest
from app.models.responses import OCRResponse
from app.services.ocr_service import OCRService
from app.api.dependencies import get_ocr_service
from app.core.exceptions import (
    ImageValidationError,
    OCRProcessingError,
    ReceiptParsingError
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ocr", tags=["OCR"])


@router.post("/receipt", response_model=OCRResponse, status_code=status.HTTP_200_OK)
async def process_receipt(
    request: OCRRequest,
    ocr_service: OCRService = Depends(get_ocr_service)
) -> OCRResponse:
    """
    Распознать чек с изображения
    
    Принимает изображение в base64, распознаёт текст и парсит структуру чека.
    
    Args:
        request: Запрос с изображением в base64
        ocr_service: OCR сервис (DI)
        
    Returns:
        OCRResponse с распознанным чеком
        
    Raises:
        HTTPException 400: Ошибка валидации изображения
        HTTPException 422: Ошибка обработки/парсинга
        HTTPException 500: Внутренняя ошибка сервера
    """
    try:
        logger.info("Received OCR request")
        
        # Обрабатываем чек
        result = await ocr_service.process_receipt(
            image_base64=request.image,
            options=request.options
        )
        
        # Возвращаем результат
        return OCRResponse(**result)
    
    except ImageValidationError as e:
        logger.warning("Image validation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Image validation failed",
                "message": e.message,
                "details": e.details
            }
        )
    
    except (OCRProcessingError, ReceiptParsingError) as e:
        logger.error("OCR processing failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "OCR processing failed",
                "message": e.message,
                "details": e.details
            }
        )
    
    except Exception as e:
        logger.error("Unexpected error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "An unexpected error occurred"
            }
        )

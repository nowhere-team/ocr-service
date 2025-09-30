"""
Утилиты для работы с изображениями
"""
import base64
import io
from typing import Tuple

import numpy as np
from PIL import Image

from app.core.exceptions import ImageValidationError
from app.core.enums import ImageFormat


def decode_base64_image(base64_string: str) -> bytes:
    """
    Декодирование base64 строки в bytes
    
    Args:
        base64_string: Изображение в base64
        
    Returns:
        Декодированные байты изображения
        
    Raises:
        ImageValidationError: Если не удалось декодировать
    """
    try:
        # Убираем data:image prefix если есть
        if "base64," in base64_string:
            base64_string = base64_string.split("base64,")[1]
        
        # Декодируем
        image_bytes = base64.b64decode(base64_string)
        
        if not image_bytes:
            raise ImageValidationError("Decoded image is empty")
        
        return image_bytes
    
    except Exception as e:
        raise ImageValidationError(
            f"Failed to decode base64 image: {str(e)}",
            details={"error": str(e)}
        )


def validate_image_format(image_bytes: bytes) -> ImageFormat:
    """
    Проверка формата изображения
    
    Args:
        image_bytes: Байты изображения
        
    Returns:
        Формат изображения
        
    Raises:
        ImageValidationError: Если формат не поддерживается
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            format_lower = img.format.lower() if img.format else "unknown"
            
            # Проверяем что формат поддерживается
            try:
                return ImageFormat(format_lower)
            except ValueError:
                raise ImageValidationError(
                    f"Unsupported image format: {format_lower}",
                    details={
                        "format": format_lower,
                        "supported_formats": [f.value for f in ImageFormat]
                    }
                )
    
    except ImageValidationError:
        raise
    except Exception as e:
        raise ImageValidationError(
            f"Failed to validate image format: {str(e)}",
            details={"error": str(e)}
        )


def validate_image_size(image_bytes: bytes, max_size_mb: int = 10) -> None:
    """
    Проверка размера изображения
    
    Args:
        image_bytes: Байты изображения
        max_size_mb: Максимальный размер в мегабайтах
        
    Raises:
        ImageValidationError: Если размер превышен
    """
    size_mb = len(image_bytes) / (1024 * 1024)
    
    if size_mb > max_size_mb:
        raise ImageValidationError(
            f"Image size {size_mb:.2f}MB exceeds maximum {max_size_mb}MB",
            details={
                "size_mb": round(size_mb, 2),
                "max_size_mb": max_size_mb
            }
        )


def bytes_to_numpy(image_bytes: bytes) -> np.ndarray:
    """
    Конвертация bytes в numpy array для OCR
    
    Args:
        image_bytes: Байты изображения
        
    Returns:
        Numpy array изображения (BGR формат для OpenCV)
        
    Raises:
        ImageValidationError: Если не удалось конвертировать
    """
    try:
        # Открываем через PIL
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Конвертируем в RGB если нужно
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Конвертируем в numpy array
            img_array = np.array(img)
            
            # PIL использует RGB, OpenCV - BGR, конвертируем
            # Но PaddleOCR умеет работать с RGB, так что оставляем как есть
            return img_array
    
    except Exception as e:
        raise ImageValidationError(
            f"Failed to convert image to numpy array: {str(e)}",
            details={"error": str(e)}
        )


def get_image_dimensions(image_bytes: bytes) -> Tuple[int, int]:
    """
    Получение размеров изображения
    
    Args:
        image_bytes: Байты изображения
        
    Returns:
        Tuple (ширина, высота)
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            return img.size
    except Exception:
        return (0, 0)

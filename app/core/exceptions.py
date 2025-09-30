"""
Кастомные исключения для OCR сервиса
"""


class OCRException(Exception):
    """Базовое исключение для OCR сервиса"""
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ImageValidationError(OCRException):
    """Ошибка валидации изображения"""
    pass


class OCRProcessingError(OCRException):
    """Ошибка при распознавании текста"""
    pass


class ReceiptParsingError(OCRException):
    """Ошибка при парсинге чека"""
    pass


class ConfigurationError(OCRException):
    """Ошибка конфигурации"""
    pass

"""
Абстрактный базовый класс для OCR движков
"""
from abc import ABC, abstractmethod
from typing import List, Tuple
from dataclasses import dataclass

import numpy as np


@dataclass
class OCRTextBlock:
    """Блок распознанного текста с координатами"""
    text: str
    confidence: float
    bbox: List[List[int]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]


@dataclass
class OCRResult:
    """Результат распознавания OCR"""
    text_blocks: List[OCRTextBlock]
    raw_text: str
    average_confidence: float
    processing_time_ms: int


class BaseOCREngine(ABC):
    """
    Абстрактный базовый класс для всех OCR движков
    Определяет единый интерфейс для работы с разными OCR библиотеками
    """
    
    @abstractmethod
    def initialize(self) -> None:
        """Инициализация OCR движка"""
        pass
    
    @abstractmethod
    def extract_text(self, image: np.ndarray) -> OCRResult:
        """
        Извлечение текста из изображения
        
        Args:
            image: Изображение в формате numpy array (RGB)
            
        Returns:
            OCRResult с распознанным текстом
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Проверка доступности движка
        
        Returns:
            True если движок готов к работе
        """
        pass
    
    def cleanup(self) -> None:
        """Очистка ресурсов (опционально)"""
        pass

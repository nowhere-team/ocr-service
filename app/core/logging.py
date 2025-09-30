"""
Настройка логирования с использованием structlog
"""
import logging
import sys
from typing import Any

import structlog


def setup_logging(log_level: str = "INFO", is_debug: bool = False) -> None:
    """
    Настройка структурированного логирования
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        is_debug: Режим отладки (более читаемый вывод)
    """
    
    # Настройка стандартного logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Процессоры для structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    # В режиме отладки - красивый вывод, в продакшене - JSON
    if is_debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """
    Получить логгер для модуля
    
    Args:
        name: Имя модуля
        
    Returns:
        Настроенный structlog логгер
    """
    return structlog.get_logger(name)

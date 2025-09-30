"""
Доменные модели - бизнес-сущности
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field

from app.core.enums import ReceiptType, PaymentMethod


class Store(BaseModel):
    """Информация о магазине"""
    name: Optional[str] = Field(None, description="Название магазина")
    address: Optional[str] = Field(None, description="Адрес точки продажи")
    inn: Optional[str] = Field(None, description="ИНН организации")


class Item(BaseModel):
    """Товарная позиция в чеке"""
    name: str = Field(..., description="Название товара")
    quantity: float = Field(1.0, description="Количество")
    price: Decimal = Field(..., description="Цена за единицу")
    total: Decimal = Field(..., description="Итоговая стоимость позиции")
    discount: Optional[Decimal] = Field(None, description="Скидка на позицию")


class Totals(BaseModel):
    """Итоговые суммы"""
    subtotal: Optional[Decimal] = Field(None, description="Подытог (до налогов)")
    tax: Optional[Decimal] = Field(None, description="Сумма НДС")
    discount: Optional[Decimal] = Field(None, description="Общая скидка")
    total: Decimal = Field(..., description="Итоговая сумма к оплате")
    payment_method: PaymentMethod = Field(
        PaymentMethod.UNKNOWN,
        description="Способ оплаты"
    )


class Metadata(BaseModel):
    """Метаданные чека"""
    date: Optional[datetime] = Field(None, description="Дата и время покупки")
    receipt_type: ReceiptType = Field(
        ReceiptType.UNKNOWN,
        description="Тип чека"
    )
    fiscal_sign: Optional[str] = Field(None, description="Фискальный признак (ФП)")
    fiscal_document: Optional[str] = Field(None, description="Номер фискального документа (ФД)")


class Receipt(BaseModel):
    """Полная модель распознанного чека"""
    store: Store = Field(..., description="Информация о магазине")
    items: List[Item] = Field(default_factory=list, description="Список товаров")
    totals: Totals = Field(..., description="Итоговые суммы")
    metadata: Metadata = Field(..., description="Метаданные чека")
    raw_text: Optional[str] = Field(None, description="Исходный распознанный текст")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность распознавания")

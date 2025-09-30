"""
Парсинг сырого OCR текста в структурированный чек
"""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Tuple

from app.models.domain import Receipt, Store, Item, Totals, Metadata
from app.core.enums import ReceiptType, PaymentMethod
from app.core.exceptions import ReceiptParsingError
from app.core.logging import get_logger

logger = get_logger(__name__)


class ReceiptParser:
    """
    Парсер для извлечения структурированных данных из OCR текста чека
    """
    
    # Паттерны для поиска
    TOTAL_KEYWORDS = [
        'итого', 'итог', 'сумма', 'к оплате', 'всего',
        'total', 'sum', 'amount'
    ]
    
    INN_PATTERN = re.compile(r'\b(\d{10}|\d{12})\b')
    DATE_PATTERNS = [
        re.compile(r'(\d{2})[./\-](\d{2})[./\-](\d{4})'),  # DD.MM.YYYY
        re.compile(r'(\d{4})[./\-](\d{2})[./\-](\d{2})'),  # YYYY-MM-DD
    ]
    TIME_PATTERN = re.compile(r'(\d{2}):(\d{2})(?::(\d{2}))?')
    
    # Паттерн для товарной позиции: "Название ... цена"
    ITEM_PATTERN = re.compile(
        r'^(.+?)\s+(\d+[\.,]\d{2})\s*(?:руб|₽|р)?\.?\s*$',
        re.IGNORECASE
    )
    
    def parse(self, raw_text: str, confidence: float) -> Receipt:
        """
        Парсинг сырого текста в структурированный чек
        
        Args:
            raw_text: Распознанный текст
            confidence: Уверенность распознавания
            
        Returns:
            Объект Receipt
            
        Raises:
            ReceiptParsingError: Если не удалось распарсить обязательные поля
        """
        try:
            logger.debug("Starting receipt parsing")
            
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            
            # Извлекаем данные
            store = self._extract_store(lines)
            items = self._extract_items(lines)
            totals = self._extract_totals(lines)
            metadata = self._extract_metadata(lines)
            
            receipt = Receipt(
                store=store,
                items=items,
                totals=totals,
                metadata=metadata,
                raw_text=raw_text,
                confidence=confidence
            )
            
            logger.info(
                "Receipt parsed successfully",
                items_count=len(items),
                total=str(totals.total) if totals.total else "N/A"
            )
            
            return receipt
            
        except Exception as e:
            logger.error("Failed to parse receipt", error=str(e))
            raise ReceiptParsingError(
                f"Failed to parse receipt: {str(e)}",
                details={"error": str(e), "raw_text_length": len(raw_text)}
            )
    
    def _extract_store(self, lines: List[str]) -> Store:
        """Извлечение информации о магазине"""
        name = None
        address = None
        inn = None
        
        # Название обычно в первых 3 строках
        if lines:
            name = lines[0]
        
        # ИНН ищем по всему тексту
        for line in lines:
            inn_match = self.INN_PATTERN.search(line)
            if inn_match:
                inn = inn_match.group(1)
                break
        
        # Адрес - обычно строка с "г.", "ул.", "д."
        for line in lines[:10]:  # Смотрим первые 10 строк
            if any(word in line.lower() for word in ['г.', 'ул.', 'д.', 'пр.']):
                address = line
                break
        
        return Store(name=name, address=address, inn=inn)
    
    def _extract_items(self, lines: List[str]) -> List[Item]:
        """Извлечение товарных позиций"""
        items = []
        
        for line in lines:
            # Пробуем найти паттерн товара
            match = self.ITEM_PATTERN.match(line)
            if match:
                try:
                    name = match.group(1).strip()
                    price_str = match.group(2).replace(',', '.')
                    price = Decimal(price_str)
                    
                    # Для простоты считаем quantity=1
                    item = Item(
                        name=name,
                        quantity=1.0,
                        price=price,
                        total=price
                    )
                    items.append(item)
                    
                except (InvalidOperation, ValueError):
                    continue
        
        logger.debug(f"Extracted {len(items)} items")
        return items
    
    def _extract_totals(self, lines: List[str]) -> Totals:
        """Извлечение итоговых сумм"""
        total = None
        payment_method = PaymentMethod.UNKNOWN
        
        # Ищем строку с итоговой суммой
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Проверяем наличие ключевых слов
            if any(keyword in line_lower for keyword in self.TOTAL_KEYWORDS):
                # Ищем число в этой строке или следующей
                amount = self._extract_amount_from_line(line)
                if not amount and i + 1 < len(lines):
                    amount = self._extract_amount_from_line(lines[i + 1])
                
                if amount:
                    total = amount
                    break
        
        # Определяем способ оплаты
        text_lower = '\n'.join(lines).lower()
        if 'карт' in text_lower or 'безнал' in text_lower:
            payment_method = PaymentMethod.CARD
        elif 'наличн' in text_lower:
            payment_method = PaymentMethod.CASH
        
        # Если не нашли итог, берём максимальную сумму из товаров или последнее число
        if not total:
            total = self._find_largest_amount(lines)
        
        if not total:
            logger.warning("Could not extract total amount")
            total = Decimal('0.00')
        
        return Totals(
            total=total,
            payment_method=payment_method
        )
    
    def _extract_metadata(self, lines: List[str]) -> Metadata:
        """Извлечение метаданных"""
        date_time = self._extract_datetime(lines)
        receipt_type = ReceiptType.UNKNOWN
        
        # Определяем тип чека
        text_lower = '\n'.join(lines).lower()
        if any(word in text_lower for word in ['фн', 'фд', 'фп', 'фискальн']):
            receipt_type = ReceiptType.FISCAL
        else:
            receipt_type = ReceiptType.NON_FISCAL
        
        return Metadata(
            date=date_time,
            receipt_type=receipt_type
        )
    
    def _extract_datetime(self, lines: List[str]) -> Optional[datetime]:
        """Извлечение даты и времени"""
        date_obj = None
        time_obj = None
        
        # Ищем дату
        for line in lines:
            for pattern in self.DATE_PATTERNS:
                match = pattern.search(line)
                if match:
                    try:
                        if len(match.group(1)) == 4:  # YYYY-MM-DD
                            year, month, day = match.groups()
                        else:  # DD.MM.YYYY
                            day, month, year = match.groups()
                        
                        date_obj = datetime(int(year), int(month), int(day))
                        break
                    except ValueError:
                        continue
            if date_obj:
                break
        
        # Ищем время
        for line in lines:
            match = self.TIME_PATTERN.search(line)
            if match:
                try:
                    hour, minute = int(match.group(1)), int(match.group(2))
                    second = int(match.group(3)) if match.group(3) else 0
                    
                    if date_obj:
                        date_obj = date_obj.replace(
                            hour=hour,
                            minute=minute,
                            second=second
                        )
                    else:
                        # Если нет даты, используем сегодня
                        date_obj = datetime.now().replace(
                            hour=hour,
                            minute=minute,
                            second=second
                        )
                    break
                except ValueError:
                    continue
        
        return date_obj
    
    def _extract_amount_from_line(self, line: str) -> Optional[Decimal]:
        """Извлечение суммы из строки"""
        # Ищем паттерн: число с точкой/запятой
        amount_pattern = re.compile(r'(\d+[\.,]\d{2})')
        matches = amount_pattern.findall(line)
        
        if matches:
            try:
                # Берём последнее число в строке (обычно это итог)
                amount_str = matches[-1].replace(',', '.')
                return Decimal(amount_str)
            except InvalidOperation:
                pass
        
        return None
    
    def _find_largest_amount(self, lines: List[str]) -> Optional[Decimal]:
        """Поиск максимальной суммы во всём тексте"""
        max_amount = None
        
        for line in lines:
            amount = self._extract_amount_from_line(line)
            if amount and (max_amount is None or amount > max_amount):
                max_amount = amount
        
        return max_amount

# OCR Service - ChopCheck

Микросервис для распознавания текста с фотографий чеков.

## 🎯 Зона ответственности

OCR сервис делает **ТОЛЬКО**:
- Принимает изображение чека (base64)
- Распознаёт текст с помощью PaddleOCR
- Парсит структурированные данные (магазин, товары, суммы)
- Возвращает JSON с результатом

**НЕ делает:**
- Сохранение результатов (это ChopCheck backend)
- Улучшение текста товаров (это сервис каталога)
- Сканирование QR-кодов (это фронтенд ChopCheck)

## 🏗️ Архитектура

Проект построен по **Clean Architecture**:

```
Handler Layer (API) → Service Layer (Business Logic) → Infrastructure Layer (External deps)
```

### Структура проекта

```
ocr-service/
├── app/
│   ├── api/                    # 🔵 Handler Layer
│   │   └── v1/handlers/       # HTTP handlers
│   ├── services/              # 🟢 Service Layer
│   │   ├── ocr_service.py     # Главный оркестратор
│   │   └── receipt_parser.py  # Парсинг чека
│   ├── infrastructure/        # 🟡 Infrastructure Layer
│   │   └── ocr_engines/       # PaddleOCR wrapper
│   ├── models/                # 📦 Data Models
│   ├── core/                  # ⚙️ Core (exceptions, logging, enums)
│   └── utils/                 # 🛠️ Utilities
└── requirements.txt
```

## 🚀 Установка и запуск

### Требования

- Python 3.13.2
- pip

### 1. Создать виртуальное окружение

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

**Важно**: Установка PaddleOCR может занять несколько минут, так как скачиваются модели.

### 3. Настроить переменные окружения

Создать файл `.env` (можно скопировать из `.env.example`):

```bash
# Application Settings
APP_NAME=ocr-service
APP_VERSION=1.0.0
DEBUG=true
LOG_LEVEL=INFO

# Server Settings
HOST=0.0.0.0
PORT=8000

# CORS Settings
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# PaddleOCR Settings
PADDLEOCR_USE_ANGLE_CLS=true
PADDLEOCR_LANG=ru
PADDLEOCR_USE_GPU=false
PADDLEOCR_SHOW_LOG=false

# Image Settings
MAX_IMAGE_SIZE_MB=10
ALLOWED_IMAGE_FORMATS=jpg,jpeg,png,webp
```

### 4. Запустить сервис

```bash
python app/main.py
```

Или через uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Сервис будет доступен на: http://localhost:8000

## 📚 API Документация

После запуска:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Основные endpoints

#### POST /api/v1/ocr/receipt

Распознать чек с изображения.

**Request:**
```json
{
  "image": "base64_encoded_image",
  "options": {}
}
```

**Response:**
```json
{
  "success": true,
  "confidence": 0.87,
  "processing_time_ms": 1420,
  "receipt": {
    "store": {
      "name": "Пятёрочка",
      "address": "г. Москва, ул. Ленина 15",
      "inn": "5027143345"
    },
    "items": [
      {
        "name": "Молоко 3.2%",
        "quantity": 1.0,
        "price": "89.90",
        "total": "89.90"
      }
    ],
    "totals": {
      "total": "89.90",
      "payment_method": "card"
    },
    "metadata": {
      "date": "2025-09-30T14:35:00",
      "receipt_type": "fiscal"
    },
    "confidence": 0.87
  },
  "ocr_engine_used": "paddleocr"
}
```

#### GET /api/v1/health

Health check - статус сервиса.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "ocr_engine_available": true
}
```

## 🧪 Тестирование

Для быстрого теста можно использовать curl:

```bash
# Конвертировать изображение в base64
base64 receipt.jpg > receipt_base64.txt

# Отправить запрос
curl -X POST http://localhost:8000/api/v1/ocr/receipt \
  -H "Content-Type: application/json" \
  -d '{
    "image": "'$(cat receipt_base64.txt)'"
  }'
```

Или через Python:

```python
import requests
import base64

# Читаем изображение
with open("receipt.jpg", "rb") as f:
    image_base64 = base64.b64encode(f.read()).decode()

# Отправляем запрос
response = requests.post(
    "http://localhost:8000/api/v1/ocr/receipt",
    json={"image": image_base64}
)

print(response.json())
```

## 🔧 Технологический стек

- **FastAPI** - веб-фреймворк
- **PaddleOCR v3** - OCR движок
- **Pydantic** - валидация данных
- **Structlog** - структурированное логирование
- **OpenCV** - обработка изображений
- **NumPy** - работа с массивами
- **Pillow** - работа с изображениями

## 📊 Производительность

- **Средняя latency**: 1-3 секунды на чек (CPU)
- **Точность**: 85-95% на чистых чеках
- **Max image size**: 10MB (настраивается)
- **Поддерживаемые форматы**: JPG, PNG, WEBP

## 🐛 Troubleshooting

### PaddleOCR не устанавливается

Попробуйте обновить pip:
```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### Ошибка "No module named 'paddleocr'"

Убедитесь что виртуальное окружение активировано и зависимости установлены.

### Медленная работа

При первом запросе PaddleOCR скачивает модели, это может занять время. Последующие запросы будут быстрее.

## 📝 TODO (для production)

- [ ] Добавить Ocean-OCR для fallback на сложных чеках
- [ ] Добавить image preprocessing (улучшение качества)
- [ ] Метрики для мониторинга (Prometheus)
- [ ] Кеширование результатов (Redis)
- [ ] Rate limiting
- [ ] Batch processing для нескольких чеков
- [ ] Unit и integration тесты
- [ ] Docker контейнер
- [ ] CI/CD pipeline

## 👨‍💻 Разработка

### Структура слоёв

**Handler Layer** (`app/api/`)
- Принимает HTTP запросы
- Валидирует через Pydantic
- Вызывает Service Layer
- Возвращает JSON ответы

**Service Layer** (`app/services/`)
- Вся бизнес-логика
- Оркестрация процессов
- Парсинг и валидация данных

**Infrastructure Layer** (`app/infrastructure/`)
- Обёртки над внешними библиотеками
- PaddleOCR engine
- Работа с файлами (если нужно)

### Добавление новой функциональности

1. Добавить domain model в `app/models/domain.py`
2. Реализовать логику в `app/services/`
3. Добавить endpoint в `app/api/v1/handlers/`
4. Обновить документацию

## 📄 Лицензия

MIT

## 🤝 Контакты

Вопросы? Пиши в ChopCheck team!

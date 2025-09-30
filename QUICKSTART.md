# 🚀 Быстрый старт

## Запуск за 3 шага

### 1. Установка зависимостей

```bash
# Создать venv
python -m venv venv

# Активировать (Windows)
venv\Scripts\activate

# Активировать (Linux/Mac)
source venv/bin/activate

# Установить пакеты
pip install -r requirements.txt
```

**⏱️ Время**: ~5-10 минут (PaddleOCR скачивает модели)

### 2. Создать .env файл

```bash
# Скопировать пример
cp .env.example .env
```

Или создать вручную:

```env
DEBUG=true
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
PADDLEOCR_LANG=ru
MAX_IMAGE_SIZE_MB=10
```

### 3. Запустить сервис

```bash
python app/main.py
```

**Готово!** 🎉

Сервис доступен на: http://localhost:8000/docs

## 🧪 Первый тест

### Через Swagger UI

1. Открой http://localhost:8000/docs
2. Нажми на `POST /api/v1/ocr/receipt`
3. Нажми "Try it out"
4. Вставь base64 изображение чека
5. Нажми "Execute"

### Через curl

```bash
# Конвертировать изображение
base64 receipt.jpg > receipt.txt

# Отправить запрос
curl -X POST http://localhost:8000/api/v1/ocr/receipt \
  -H "Content-Type: application/json" \
  -d '{"image": "'$(cat receipt.txt)'"}'
```

### Через Python

```python
import requests
import base64

with open("receipt.jpg", "rb") as f:
    img_base64 = base64.b64encode(f.read()).decode()

response = requests.post(
    "http://localhost:8000/api/v1/ocr/receipt",
    json={"image": img_base64}
)

print(response.json())
```

## ⚠️ Частые проблемы

### numpy не устанавливается

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### PaddleOCR медленно работает

Первый запрос медленный (скачивание моделей).  
Последующие запросы - быстрые (~1-3 сек).

### Порт 8000 занят

Измени в `.env`:
```env
PORT=8001
```

## 📖 Полная документация

Смотри [README.md](README.md)

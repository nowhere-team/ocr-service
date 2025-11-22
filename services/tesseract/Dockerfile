FROM python:3.13-slim

WORKDIR /app

# install tesseract and language data
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    libtesseract-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# verify tesseract installation
RUN tesseract --version

COPY pyproject.toml ./
COPY uv.lock ./

RUN pip install uv
RUN uv sync --no-dev

COPY src/ ./src/

# set tessdata path
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
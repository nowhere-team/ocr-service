FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# install uv
RUN pip install uv

# copy dependency files
COPY pyproject.toml ./
COPY uv.lock ./

# install dependencies
RUN uv sync --no-dev

# copy application code
COPY app.py ./
COPY src/ ./src/

# expose streamlit port
EXPOSE 8501

# run streamlit
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
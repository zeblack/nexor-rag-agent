FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# torch é instalado primeiro, isolado, com o índice CPU-only — sem isso o pip
# resolve a variante CUDA completa (torch+cudnn+nccl+cublas... ~2GB extras)
# mesmo em ambiente sem GPU, porque sentence-transformers/FlagEmbedding puxam
# torch como dependência transitiva antes do índice CPU ser considerado.
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config/ ./config/

FROM base AS api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker
CMD ["celery", "-A", "app.queue.celery_app", "worker", "--loglevel=info", "--concurrency=1"]

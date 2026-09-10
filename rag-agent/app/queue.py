from celery import Celery

from app.config import settings

celery_app = Celery(
    "rag_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker", "app.ingestion.entity_extraction_task"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # 1 tarefa por vez por worker — consistente com ingestão sequencial
)

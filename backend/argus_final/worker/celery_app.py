from __future__ import annotations

from celery import Celery

from argus_final.core.settings import settings

celery_app = Celery(
    "argus_final",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["argus_final.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=300,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

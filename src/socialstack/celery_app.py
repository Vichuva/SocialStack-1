from celery import Celery
from celery.schedules import crontab

from socialstack.config import get_settings

settings = get_settings()

celery_app = Celery(
    "socialstack",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "socialstack.tasks.generation_tasks",
        "socialstack.tasks.publish_tasks",
        "socialstack.tasks.metrics_tasks",
        "socialstack.tasks.regeneration_tasks",
        "socialstack.tasks.notification_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_time_limit=settings.celery_task_time_limit,
    task_routes={
        "socialstack.tasks.generation_tasks.generate_asset_task": {"queue": "images"},
        "socialstack.tasks.publish_tasks.*": {"queue": "publishing"},
        "socialstack.tasks.metrics_tasks.*": {"queue": "metrics"},
        "socialstack.tasks.*": {"queue": "default"},
    },
    beat_schedule={
        "publish-due-slots": {
            "task": "socialstack.tasks.publish_tasks.publish_orchestrator_task",
            "schedule": crontab(minute=f"*/{settings.publish_cron_every_minutes}"),
        },
        "collect-metrics": {
            "task": "socialstack.tasks.metrics_tasks.collect_metrics_task",
            "schedule": crontab(hour=f"*/{settings.metrics_cron_every_hours}", minute="0"),
            "kwargs": {"business_id": None, "run_id": None},
        },
    },
    redbeat_redis_url=settings.redis_url,
)

"""unit tests for celery app configuration."""

from __future__ import annotations


def test_celery_app_is_importable() -> None:
    """celery_app can be imported from app.tasks.celery_app."""
    from app.tasks.celery_app import celery_app

    assert celery_app is not None


def test_celery_app_broker_matches_redis_url() -> None:
    """celery_app broker is set to the REDIS_URL from settings."""
    from app.core.config import settings
    from app.tasks.celery_app import celery_app

    assert celery_app.conf.broker_url == settings.REDIS_URL


def test_celery_app_backend_matches_redis_url() -> None:
    """celery_app result backend is set to REDIS_URL from settings."""
    from app.core.config import settings
    from app.tasks.celery_app import celery_app

    assert celery_app.conf.result_backend == settings.REDIS_URL


def test_celery_app_task_serializer_is_json() -> None:
    """task_serializer is 'json'."""
    from app.tasks.celery_app import celery_app

    assert celery_app.conf.task_serializer == "json"


def test_celery_app_result_expires() -> None:
    """result_expires is 3600 seconds."""
    from app.tasks.celery_app import celery_app

    assert celery_app.conf.result_expires == 3600


def test_celery_app_prefetch_multiplier() -> None:
    """worker_prefetch_multiplier is 1 for fair dispatch."""
    from app.tasks.celery_app import celery_app

    assert celery_app.conf.worker_prefetch_multiplier == 1


def test_celery_app_task_acks_late() -> None:
    """task_acks_late is True so tasks ack after completion."""
    from app.tasks.celery_app import celery_app

    assert celery_app.conf.task_acks_late is True


def test_celery_app_reject_on_worker_lost() -> None:
    """task_reject_on_worker_lost is True to requeue on worker crash."""
    from app.tasks.celery_app import celery_app

    assert celery_app.conf.task_reject_on_worker_lost is True

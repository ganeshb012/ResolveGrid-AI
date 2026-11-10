import asyncio
import logging
import socket
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from backend.app.core.config import settings

logger = logging.getLogger("resolvegrid.tasks")


def is_redis_available(host: str = "127.0.0.1", port: int = 6379, timeout: float = 1.0) -> bool:
    """Check whether a Redis or Memurai service is actively listening on the target port."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


class TaskRegistry:
    _handlers: Dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(fn: Callable):
            cls._handlers[name] = fn
            return fn
        return decorator

    @classmethod
    def get(cls, name: str) -> Optional[Callable]:
        return cls._handlers.get(name)


class TaskManager:
    """
    Unified background task manager.
    Selects Celery+Redis when an active broker is reachable;
    otherwise falls back cleanly to the async recoverable scheduler.
    """

    def __init__(self):
        self.redis_available = False
        self.mode = "ASYNC_SCHEDULER_FALLBACK"
        self._queue: Optional[asyncio.Queue] = None
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._periodic_task: Optional[asyncio.Task] = None

    def detect_broker(self):
        """Lazy detection of Redis broker."""
        if not settings.TASK_FALLBACK_MODE:
            self.redis_available = is_redis_available()
            if self.redis_available:
                self.mode = "CELERY_REDIS"
        logger.info(
            "TaskManager initialized in mode: %s (Redis available: %s)",
            self.mode,
            self.redis_available
        )

    async def start(self):
        """Start async fallback task processor loop and periodic escalation checker."""
        if self._running:
            return
        self.detect_broker()
        self._running = True
        self._queue = asyncio.Queue()
        self._worker_task = asyncio.create_task(self._process_queue())
        self._periodic_task = asyncio.create_task(self._periodic_monitor())
        logger.info("TaskManager background worker and monitor loop started.")

    async def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
        if self._periodic_task:
            self._periodic_task.cancel()
        logger.info("TaskManager stopped.")

    async def enqueue(self, task_name: str, **kwargs) -> str:
        """Enqueue an asynchronous background task with arguments."""
        task_id = f"task_{int(time.time()*1000)}_{task_name}"
        logger.info("Dispatching task [%s]: %s (mode=%s)", task_id, task_name, self.mode)

        if self.mode == "CELERY_REDIS":
            try:
                from backend.app.tasks.worker_tasks import execute_celery_task
                execute_celery_task.delay(task_name, kwargs)
                return task_id
            except Exception as e:
                logger.warning("Celery dispatch failed (%s), routing to fallback runner", str(e))

        if self._queue is not None:
            await self._queue.put({"id": task_id, "name": task_name, "kwargs": kwargs, "retries": 0})
        else:
            # Direct async task if queue is not initialized yet
            asyncio.create_task(self._execute_direct(task_name, kwargs))

        return task_id

    async def schedule_delayed(self, delay_seconds: float, task_name: str, **kwargs):
        """Schedule a task to run after a specific delay in seconds."""
        async def _delayed():
            await asyncio.sleep(delay_seconds)
            await self.enqueue(task_name, **kwargs)

        asyncio.create_task(_delayed())

    async def _execute_direct(self, task_name: str, kwargs: dict):
        handler = TaskRegistry.get(task_name)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(**kwargs)
                else:
                    handler(**kwargs)
            except Exception as e:
                logger.error("Error executing background task %s: %s", task_name, str(e), exc_info=True)
        else:
            logger.warning("No handler registered for task: %s", task_name)

    async def _process_queue(self):
        while self._running:
            try:
                item = await self._queue.get()
                task_name = item["name"]
                kwargs = item["kwargs"]
                handler = TaskRegistry.get(task_name)

                if handler:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(**kwargs)
                        else:
                            handler(**kwargs)
                        logger.info("Task completed successfully: %s", task_name)
                    except Exception as exc:
                        logger.error("Task %s failed: %s", task_name, str(exc))
                        if item["retries"] < 3:
                            item["retries"] += 1
                            logger.info("Retrying task %s (attempt %d/3) in 5s", task_name, item["retries"])
                            await asyncio.sleep(5)
                            await self._queue.put(item)
                else:
                    logger.warning("Unknown task handler for %s", task_name)

                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Exception in background task worker loop: %s", str(e))
                await asyncio.sleep(1)

    async def _periodic_monitor(self):
        """Periodic background sweep for delayed follow-ups and automated escalations."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every 60 seconds
                handler = TaskRegistry.get("periodic_escalation_sweep")
                if handler:
                    if asyncio.iscoroutinefunction(handler):
                        await handler()
                    else:
                        handler()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in periodic monitor sweep: %s", str(e))


task_manager = TaskManager()

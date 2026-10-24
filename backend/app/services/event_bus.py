import asyncio
from typing import Dict, List, Any
from app.schemas.task import TaskEvent
from app.db.session import SessionLocal
from app.db.models import TaskEventModel, TaskModel
import json

class EventBus:
    """
    In-memory asynchronous event broadcast system supporting Server-Sent Events (SSE)
    and persistent database event logging.
    """

    def __init__(self):
        # Mapping of task_id -> list of subscriber queues
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """Subscribe to live events for a given task."""
        queue: asyncio.Queue = asyncio.Queue()
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        self._subscribers[task_id].append(queue)
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue):
        """Unsubscribe queue from task event stream."""
        if task_id in self._subscribers:
            if queue in self._subscribers[task_id]:
                self._subscribers[task_id].remove(queue)
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]

    async def publish(self, event: TaskEvent):
        """Broadcasts event to all active listeners and persists to database."""
        # 1. Broadcast to in-memory subscribers
        if event.task_id in self._subscribers:
            for queue in list(self._subscribers[event.task_id]):
                await queue.put(event)

        # 2. Persist to SQLite/Postgres DB
        try:
            with SessionLocal() as db:
                event_record = TaskEventModel(
                    task_id=event.task_id,
                    event=event.event,
                    step=event.step,
                    status=event.status,
                    message=event.message,
                    data_json=json.dumps(event.data) if event.data else None,
                    timestamp=event.timestamp
                )
                db.add(event_record)

                # Update current step and status on TaskModel
                task_record = db.query(TaskModel).filter(TaskModel.id == event.task_id).first()
                if task_record:
                    task_record.current_step = event.step
                    if event.event in ["task_completed", "task_failed", "task_cancelled"]:
                        task_record.status = event.status
                db.commit()
        except Exception as e:
            # Prevent logging DB error from failing the workflow
            pass

event_bus = EventBus()

import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import TaskModel, TaskEventModel
from app.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskStatus,
    ExecutionPlan,
    FileChange,
    TestResult,
    ReviewResult,
    PullRequestInfo,
    TaskEvent
)
from app.tasks.orchestrator import AgentOrchestrator, active_orchestrators
from app.services.event_bus import event_bus

router = APIRouter()

def model_to_response(task: TaskModel) -> TaskResponse:
    plan = ExecutionPlan(**json.loads(task.plan_json)) if task.plan_json else None
    files_changed = [FileChange(**f) for f in json.loads(task.files_changed_json)] if task.files_changed_json else []
    test_result = TestResult(**json.loads(task.test_result_json)) if task.test_result_json else None
    review = ReviewResult(**json.loads(task.review_json)) if task.review_json else None
    pull_request = PullRequestInfo(**json.loads(task.pull_request_json)) if task.pull_request_json else None

    return TaskResponse(
        task_id=task.id,
        repository=task.repository,
        task=task.task,
        status=TaskStatus(task.status),
        current_step=task.current_step,
        iteration=task.iteration,
        max_iterations=task.max_iterations,
        plan=plan,
        files_changed=files_changed,
        test_result=test_result,
        review=review,
        pull_request=pull_request,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at
    )

@router.post("/tasks", response_model=dict, status_code=201)
async def create_task(payload: TaskCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Submits a new autonomous software engineering task.
    Immediately queues the task and spawns the agent orchestrator.
    """
    task_id = f"task_{uuid.uuid4().hex[:8]}"

    # Save to DB
    new_task = TaskModel(
        id=task_id,
        repository=payload.repository,
        task=payload.task,
        status=TaskStatus.QUEUED.value,
        current_step="queued",
        iteration=1,
        max_iterations=5,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_task)
    db.commit()

    # Create orchestrator and start background execution
    orchestrator = AgentOrchestrator(task_id, payload)
    active_orchestrators[task_id] = orchestrator
    background_tasks.add_task(orchestrator.run)

    return {
        "task_id": task_id,
        "status": TaskStatus.QUEUED.value,
        "message": f"Task {task_id} successfully queued."
    }

@router.get("/tasks", response_model=List[TaskResponse])
def list_tasks(limit: int = 50, db: Session = Depends(get_db)):
    """Lists recent engineering tasks."""
    tasks = db.query(TaskModel).order_by(TaskModel.created_at.desc()).limit(limit).all()
    return [model_to_response(t) for t in tasks]

@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """Retrieves full task details, execution state, artifacts, diffs, and PR."""
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return model_to_response(task)

@router.get("/tasks/{task_id}/events")
async def stream_task_events(task_id: str, db: Session = Depends(get_db)):
    """
    Server-Sent Events (SSE) endpoint providing real-time streaming updates
    of the agent's thoughts, tool actions, diffs, sandbox runs, and status.
    """
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    # Fetch past events
    past_events = db.query(TaskEventModel).filter(TaskEventModel.task_id == task_id).order_by(TaskEventModel.id.asc()).all()

    async def event_generator():
        # First yield past historical events
        for pe in past_events:
            data = {
                "task_id": pe.task_id,
                "event": pe.event,
                "step": pe.step,
                "status": pe.status,
                "message": pe.message,
                "timestamp": pe.timestamp.isoformat(),
                "data": json.loads(pe.data_json) if pe.data_json else None
            }
            yield {
                "event": pe.event,
                "data": json.dumps(data)
            }

        # If already completed or failed, stop
        if task.status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value]:
            return

        # Subscribe to live events
        queue = event_bus.subscribe(task_id)
        try:
            while True:
                event: TaskEvent = await queue.get()
                payload = {
                    "task_id": event.task_id,
                    "event": event.event,
                    "step": event.step,
                    "status": event.status,
                    "message": event.message,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.data
                }
                yield {
                    "event": event.event,
                    "data": json.dumps(payload)
                }
                if event.event in ["task_completed", "task_failed", "task_cancelled"]:
                    break
        finally:
            event_bus.unsubscribe(task_id, queue)

    return EventSourceResponse(event_generator())

@router.post("/tasks/{task_id}/approve")
def approve_task(task_id: str):
    """
    Human-in-the-Loop endpoint: grants approval for committing and creating PR.
    """
    orchestrator = active_orchestrators.get(task_id)
    if not orchestrator:
        raise HTTPException(status_code=404, detail=f"Active task orchestrator for '{task_id}' not found.")

    orchestrator.approve()
    return {"status": "success", "message": f"Approval granted for task {task_id}."}

@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = Depends(get_db)):
    """Cancels a running engineering task."""
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    task.status = TaskStatus.CANCELLED.value
    db.commit()

    if task_id in active_orchestrators:
        del active_orchestrators[task_id]

    return {"status": "cancelled", "message": f"Task {task_id} marked as cancelled."}

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Autonomous Engineering Agent API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

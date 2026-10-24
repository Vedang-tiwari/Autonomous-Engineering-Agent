import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base

class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(String(64), primary_key=True, index=True)
    repository = Column(String(512), nullable=False)
    task = Column(Text, nullable=False)
    status = Column(String(64), default="queued", index=True)
    current_step = Column(String(128), nullable=True)
    iteration = Column(Integer, default=1)
    max_iterations = Column(Integer, default=5)
    
    # JSON-encoded workflow artifacts
    plan_json = Column(Text, nullable=True)
    files_changed_json = Column(Text, nullable=True)
    test_result_json = Column(Text, nullable=True)
    review_json = Column(Text, nullable=True)
    pull_request_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship("TaskEventModel", back_populates="task", cascade="all, delete-orphan", order_by="TaskEventModel.id")


class TaskEventModel(Base):
    __tablename__ = "task_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), ForeignKey("tasks.id"), index=True, nullable=False)
    event = Column(String(128), nullable=False)
    step = Column(String(128), nullable=False)
    status = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    data_json = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    task = relationship("TaskModel", back_populates="events")

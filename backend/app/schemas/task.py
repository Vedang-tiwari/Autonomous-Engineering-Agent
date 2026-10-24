from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    ANALYZING = "analyzing"
    CODING = "coding"
    TESTING = "testing"
    REVIEWING = "reviewing"
    AWAITING_APPROVAL = "awaiting_approval"
    GIT_OPERATIONS = "git_operations"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class ExecutionPlanStep(BaseModel):
    step_number: int
    title: str
    description: str
    status: StepStatus = StepStatus.PENDING
    details: Optional[str] = None

class ExecutionPlan(BaseModel):
    overview: str
    steps: List[ExecutionPlanStep] = Field(default_factory=list)

class FileChange(BaseModel):
    path: str
    action: str  # "modify", "create", "delete"
    diff: str
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    lines_added: int = 0
    lines_removed: int = 0

class TestResult(BaseModel):
    __test__ = False
    command: str
    exit_code: int
    passed: bool
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    duration_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    failures_summary: List[str] = Field(default_factory=list)

class ReviewResult(BaseModel):
    decision: str = "APPROVED"  # "APPROVED" or "CHANGES_REQUIRED"
    summary: str = ""
    quality_score: int = 100
    issues: List[str] = Field(default_factory=list)
    security_concerns: List[str] = Field(default_factory=list)
    regression_risk: str = "low"  # "low", "medium", "high"
    recommendations: Optional[str] = None

class PullRequestInfo(BaseModel):
    title: str
    body: str
    branch_name: str
    base_branch: str = "main"
    commit_sha: Optional[str] = None
    commit_message: Optional[str] = None
    pr_url: Optional[str] = None
    created_at: Optional[datetime] = None

class TaskEvent(BaseModel):
    task_id: str
    event: str
    step: str
    status: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Optional[Dict[str, Any]] = None

class TaskCreate(BaseModel):
    repository: str = Field(..., description="Git repository URL or local directory path")
    task: str = Field(..., description="Engineering objective or bug description")
    branch: Optional[str] = Field(None, description="Target branch to base work on")
    auto_pr: bool = Field(True, description="Automatically generate Pull Request on test pass")
    require_human_approval: bool = Field(False, description="Pause for human approval before committing/PR")

class TaskResponse(BaseModel):
    task_id: str
    repository: str
    task: str
    status: TaskStatus
    current_step: Optional[str] = None
    iteration: int = 1
    max_iterations: int = 5
    plan: Optional[ExecutionPlan] = None
    files_changed: List[FileChange] = Field(default_factory=list)
    test_result: Optional[TestResult] = None
    review: Optional[ReviewResult] = None
    pull_request: Optional[PullRequestInfo] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

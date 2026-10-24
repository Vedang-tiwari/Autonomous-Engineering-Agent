import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from app.core.config import settings
from app.core.llm import get_llm_client
from app.db.session import SessionLocal
from app.db.models import TaskModel
from app.schemas.task import (
    TaskCreate,
    TaskStatus,
    StepStatus,
    TaskEvent,
    ExecutionPlan,
    FileChange,
    TestResult,
    ReviewResult,
    PullRequestInfo
)
from app.services.event_bus import event_bus
from app.services.git_service import GitService
from app.services.tools import RepositoryTools
from app.sandbox.manager import SandboxManager
from app.vector_db.retriever import CodeRetriever
from app.agents.planner import PlannerAgent
from app.agents.repository import RepositoryAgent
from app.agents.coding import CodingAgent
from app.agents.testing import TestingAgent
from app.agents.review import ReviewAgent
from app.agents.git import GitAgent

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """
    Central orchestration engine for the Autonomous Engineering Agent.
    Executes the autonomous loop:
    Plan -> Analyze -> Retrieve -> Code -> Sandbox Test -> (Iterate) -> Review -> (Approval) -> Git/PR.
    """

    def __init__(self, task_id: str, create_data: TaskCreate):
        self.task_id = task_id
        self.create_data = create_data
        self.llm = get_llm_client()
        self.repo_dir: Optional[Path] = None
        self.approval_event = asyncio.Event()

    async def emit(self, event_name: str, step: str, status: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Helper to emit live event across bus and DB."""
        event = TaskEvent(
            task_id=self.task_id,
            event=event_name,
            step=step,
            status=status,
            message=message,
            timestamp=datetime.utcnow(),
            data=data
        )
        await event_bus.publish(event)

    async def run(self):
        """Main execution workflow running in background."""
        try:
            await self.emit("task_created", "setup", TaskStatus.QUEUED, f"Task {self.task_id} initialized.")

            # 1. Workspace & Git Setup
            await self.emit("workspace_setup_started", "workspace", TaskStatus.ANALYZING, "Preparing repository workspace...")
            self.repo_dir = GitService.clone_or_setup(self.create_data.repository, self.task_id)
            tools = RepositoryTools(self.repo_dir)
            git_service = GitService(self.repo_dir)
            sandbox = SandboxManager(self.repo_dir)
            retriever = CodeRetriever(self.repo_dir)

            await self.emit("workspace_setup_completed", "workspace", "success", "Repository workspace ready.", {
                "workspace_path": str(self.repo_dir)
            })

            # 2. Repository Understanding
            await self.emit("repository_analysis_started", "repository_analysis", TaskStatus.ANALYZING, "Analyzing repository architecture...")
            repo_agent = RepositoryAgent(self.repo_dir, tools)
            repo_analysis = await repo_agent.analyze()

            await self.emit("repository_analysis_completed", "repository_analysis", "success", "Repository structure indexed.", {
                "tech_stack": repo_analysis["tech_stack"],
                "test_info": repo_analysis["test_info"]
            })

            # 3. Planning Phase
            await self.emit("planning_started", "planning", TaskStatus.PLANNING, "Decomposing task objective into execution plan...")
            planner = PlannerAgent(self.llm)
            plan = await planner.create_plan(repo_analysis["summary"], self.create_data.task)

            # Persist plan to DB
            self._update_task_record(plan=plan)

            await self.emit("planning_completed", "planning", "success", f"Generated execution plan with {len(plan.steps)} steps.", {
                "plan": plan.dict()
            })

            # 4. Code Retrieval & Indexing
            await self.emit("retrieval_started", "retrieval", TaskStatus.ANALYZING, "Retrieving relevant code files and symbols...")
            retriever.index_repository()
            relevant_chunks = retriever.retrieve(self.create_data.task, top_k=6)
            relevant_files = list({c["file_path"] for c in relevant_chunks})

            await self.emit("retrieval_completed", "retrieval", "success", f"Located {len(relevant_files)} relevant source files.", {
                "files": relevant_files
            })

            # 5. Baseline Sandbox Execution
            await self.emit("test_started", "testing", TaskStatus.TESTING, "Running baseline test suite in sandbox...")
            testing_agent = TestingAgent(sandbox)
            test_result = await testing_agent.run_validation()

            await self.emit("test_completed", "testing", "completed", f"Baseline tests executed: {test_result.passed_tests} passed, {test_result.failed_tests} failed.", {
                "test_result": test_result.dict()
            })
            self._update_task_record(test_result=test_result)

            # Prepare Agent Feature Branch
            git_agent = GitAgent(git_service)
            branch_name = git_agent.prepare_branch(self.create_data.task)
            await self.emit("git_branch_created", "git", "success", f"Created feature branch '{branch_name}'.", {
                "branch": branch_name
            })

            # 6. Iterative Coding & Testing Loop
            coding_agent = CodingAgent(self.repo_dir, tools, self.llm)
            review_agent = ReviewAgent(self.llm)

            iteration = 1
            max_iter = settings.MAX_AGENT_ITERATIONS
            is_resolved = False
            last_review: Optional[ReviewResult] = None
            review_feedback = None

            while iteration <= max_iter and not is_resolved:
                await self.emit("iteration_started", "coding", TaskStatus.CODING, f"Starting iteration {iteration}/{max_iter}...", {
                    "iteration": iteration
                })
                self._update_task_record(iteration=iteration)

                # Diagnosis & Code Modification
                test_failure_context = testing_agent.extract_failure_context(test_result)
                fix_res = await coding_agent.diagnose_and_fix(
                    task_goal=self.create_data.task,
                    relevant_chunks=relevant_chunks,
                    test_failure_context=test_failure_context,
                    previous_feedback=review_feedback
                )

                # Capture git diff
                diff_text = git_service.get_diff()
                changed_files = git_service.get_changed_files()
                self._update_task_record(files_changed=changed_files)

                await self.emit("code_modified", "coding", "success", f"Applied changes across {len(changed_files)} file(s).", {
                    "root_cause": fix_res.get("root_cause"),
                    "files_changed": [f.dict() for f in changed_files],
                    "diff": diff_text[:1000]
                })

                # Re-run Sandbox Tests
                await self.emit("test_started", "testing", TaskStatus.TESTING, "Validating modifications in sandbox environment...")
                test_result = await testing_agent.run_validation()
                self._update_task_record(test_result=test_result)

                await self.emit("test_completed", "testing", "completed" if test_result.passed else "failed",
                    f"Test validation: {test_result.passed_tests} passed, {test_result.failed_tests} failed.", {
                    "test_result": test_result.dict()
                })

                # Run Review Agent
                await self.emit("review_started", "review", TaskStatus.REVIEWING, "Reviewing git diff and test verification...")
                last_review = await review_agent.review(self.create_data.task, diff_text, test_result)
                self._update_task_record(review=last_review)

                await self.emit("review_completed", "review", "success", f"Review decision: {last_review.decision}", {
                    "review": last_review.dict()
                })

                if test_result.passed and last_review.decision == "APPROVED":
                    is_resolved = True
                    break

                # Prepare feedback for next iteration
                review_feedback = f"Review requested changes: {', '.join(last_review.issues)}. Tests passed: {test_result.passed}."
                iteration += 1

            # 7. Human-in-the-Loop Approval Check
            if self.create_data.require_human_approval:
                await self.emit("awaiting_approval", "approval", TaskStatus.AWAITING_APPROVAL, "Awaiting developer approval to commit and create PR.", {
                    "diff": git_service.get_diff(),
                    "review": last_review.dict() if last_review else None
                })
                # Wait for approval signal via POST /api/tasks/{task_id}/approve
                await self.approval_event.wait()
                await self.emit("approval_granted", "approval", "success", "Human approval confirmed. Proceeding with Git PR operations.")

            # 8. Git Operations & PR Generation
            await self.emit("commit_started", "git", TaskStatus.GIT_OPERATIONS, "Committing verified changes to feature branch...")
            commit_sha = git_agent.commit_changes(self.create_data.task)

            await self.emit("commit_created", "git", "success", f"Changes committed: {commit_sha or 'HEAD'}", {
                "commit_sha": commit_sha
            })

            pr_info = await git_agent.create_pull_request(
                task_id=self.task_id,
                task_goal=self.create_data.task,
                branch_name=branch_name,
                commit_sha=commit_sha,
                test_summary=f"{test_result.passed_tests} passed, {test_result.failed_tests} failed",
                review_summary=last_review.summary if last_review else "Automated review passed."
            )
            self._update_task_record(pull_request=pr_info, status=TaskStatus.COMPLETED)

            await self.emit("pull_request_created", "git", "success", f"Pull Request generated for branch {branch_name}.", {
                "pull_request": pr_info.dict()
            })

            await self.emit("task_completed", "completed", TaskStatus.COMPLETED, f"Task {self.task_id} successfully completed!", {
                "pull_request": pr_info.dict()
            })

        except Exception as e:
            logger.error(f"Error executing task {self.task_id}: {e}", exc_info=True)
            self._update_task_record(status=TaskStatus.FAILED, error_message=str(e))
            await self.emit("task_failed", "failed", TaskStatus.FAILED, f"Task failed: {str(e)}", {
                "error": str(e)
            })

    def approve(self):
        """Signal human approval to proceed."""
        self.approval_event.set()

    def _update_task_record(
        self,
        status: Optional[TaskStatus] = None,
        iteration: Optional[int] = None,
        plan: Optional[ExecutionPlan] = None,
        files_changed: Optional[list] = None,
        test_result: Optional[TestResult] = None,
        review: Optional[ReviewResult] = None,
        pull_request: Optional[PullRequestInfo] = None,
        error_message: Optional[str] = None
    ):
        """Updates task record in SQLite/Postgres DB."""
        try:
            with SessionLocal() as db:
                task = db.query(TaskModel).filter(TaskModel.id == self.task_id).first()
                if not task:
                    return
                if status:
                    task.status = status.value if hasattr(status, "value") else str(status)
                if iteration is not None:
                    task.iteration = iteration
                if plan:
                    task.plan_json = json.dumps(plan.dict())
                if files_changed is not None:
                    task.files_changed_json = json.dumps([f.dict() for f in files_changed])
                if test_result:
                    task.test_result_json = json.dumps(test_result.dict())
                if review:
                    task.review_json = json.dumps(review.dict())
                if pull_request:
                    task.pull_request_json = json.dumps(pull_request.dict())
                if error_message:
                    task.error_message = error_message
                task.updated_at = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.warning(f"Error persisting task state: {e}")

# Global registry of active orchestrators
active_orchestrators: Dict[str, AgentOrchestrator] = {}
